import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

PRIVILEGED_HELPER = "/usr/libexec/armada/armada-tools-priv"
TOOLS = "/usr/bin/armada-tools"


def privileged_command(action, *arguments):
    return ["pkexec", "--disable-internal-agent", PRIVILEGED_HELPER, action, *arguments]


def privileged_operation(action, *arguments):
    subprocess.run(privileged_command(action, *arguments), check=True)


def privileged_request(action, *arguments):
    result = subprocess.run(privileged_command(action, *arguments),
                            capture_output=True, text=True, timeout=90, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Armada Tools operation failed")
    return json.loads(result.stdout)


def ssh_request(action):
    return privileged_request(action)


def network_addresses(interfaces):
    addresses = []
    for interface in interfaces:
        if interface.get("ifname") == "lo":
            continue
        for address in interface.get("addr_info", []):
            if address.get("scope") != "global" or any(address.get(flag) for flag in ("tentative", "dadfailed", "deprecated")):
                continue
            try:
                value = ipaddress.ip_address(address["local"])
            except (KeyError, ValueError):
                continue
            if value.is_loopback or value.is_unspecified or value.is_link_local:
                continue
            addresses.append((interface["ifname"], str(value)))
    return sorted(set(addresses), key=lambda item: (ipaddress.ip_address(item[1]).version, item))


def connection_info():
    result = subprocess.run(["ip", "-j", "address", "show", "up"], capture_output=True,
                            text=True, timeout=5, check=True)
    return {"addresses": network_addresses(json.loads(result.stdout))}


def steam_client_version():
    package = Path.home() / ".local/share/Steam/package"
    versions = set()
    try:
        for manifest in package.glob("steam_client_*linuxarm64.manifest"):
            with manifest.open("rb") as stream:
                contents = stream.read(65536)
            match = re.match(rb'\s*"linuxarm64"\s*\{\s*"version"\s*"([1-9][0-9]*)"', contents)
            if not match:
                return "Unknown"
            versions.add(match[1].decode("ascii"))
    except OSError:
        return "Unknown"
    return versions.pop() if len(versions) == 1 else "Unknown"


def system_info():
    def read(path, default="Unknown"):
        try:
            return Path(path).read_text().strip("\x00\n ") or default
        except OSError:
            return default

    disk = shutil.disk_usage(Path.home())
    gib = 1024 ** 3
    return {
        "Device": read("/proc/device-tree/model", os.uname().machine),
        "Kernel": os.uname().release,
        "Storage": f"{disk.free / gib:.1f} GiB free of {disk.total / gib:.1f} GiB",
    }


class CommandJob:
    def __init__(self):
        self.process = None
        self.log = None

    def start(self, command, log_name):
        if self.process is not None and self.process.poll() is None:
            raise RuntimeError("An operation is already running")
        directory = Path.home() / ".local/state/armada"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.log = directory / log_name
        fd = os.open(self.log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as output:
            self.process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)

    def status(self):
        if self.process is None:
            raise RuntimeError("No operation has started")
        code = self.process.poll()
        try:
            with self.log.open("rb") as stream:
                stream.seek(max(0, os.fstat(stream.fileno()).st_size - 4096))
                output = stream.read().decode(errors="replace").strip()
        except OSError as error:
            output = f"Operation log unavailable: {error}"
        lines = output.splitlines()
        if code not in (None, 0):
            lines = [line for line in lines if line.strip() and not re.fullmatch(r"\d{1,3}%", line.strip())]
            message = "\n".join(lines[-3:]) or "Operation failed"
        else:
            message = lines[-1] if lines else "Preparing operation…"
        return {"code": code, "output": output, "message": message}


class SteamJob(CommandJob):
    def start(self):
        super().start([TOOLS, "steam", "repair", "--yes"], "steam-repair.log")


def repair_steam():
    if os.geteuid() == 0:
        raise RuntimeError("Run armada-tools as the desktop user, without sudo")
    from armada_steam import SteamMaintenance
    SteamMaintenance().restore()


def confirm(message, yes):
    if yes:
        return
    print(message, flush=True)
    if not sys.stdin.isatty():
        raise RuntimeError("Confirmation requires a terminal; pass --yes to proceed")
    if input("Continue? [y/N] ").strip().lower() not in {"y", "yes"}:
        raise RuntimeError("Cancelled")


def print_status(only=None):
    failed = False
    for title, collectors in (
            ("System Information", (system_info,)),
            ("Remote Access", (lambda: ssh_request("get-ssh"), connection_info)),
            ("Operating System", (lambda: privileged_request("get-os"),)),
            ("Steam", (lambda: {"Client Version": steam_client_version()},))):
        if only is not None and title != only:
            continue
        print(f"{title}:")
        for collect in collectors:
            try:
                values = collect()
                if title == "Remote Access":
                    if "active" in values:
                        values = {"SSH": "Running" if values["active"] else "Stopped"}
                    else:
                        values = {"IP Address": ", ".join(ip for _, ip in values["addresses"]) or "No network address available"}
                elif title == "Operating System":
                    pending = values["rollback"] if values["rollback_queued"] else values["staged"]
                    values = {"Current Version": values["booted"]["version"],
                              "Previous Version": (values["rollback"] or {}).get("version", "No previous version available"),
                              "Update Channel": values["channel"] or "Unavailable"}
                    channel = values.pop("Update Channel")
                    if pending:
                        values["After Restart"] = pending["version"]
                    values["Update Channel"] = channel
                for key, value in values.items():
                    print(f"  {key}: {value}")
            except Exception as error:
                failed = True
                print(f"  Unavailable: {error}")
    return int(failed)


def main(arguments=None):
    parser = argparse.ArgumentParser(description="Armada recovery and maintenance. Without arguments, open the desktop app.")
    objects = parser.add_subparsers(dest="object")
    objects.add_parser("status", help="show system information, remote access, OS and Steam status")
    actions = {}
    for name, description in (("ssh", "persistent remote access"),
                              ("steam", "Steam client recovery"), ("update", "OS updates and rollback")):
        group = objects.add_parser(name, help=description)
        actions[name] = group.add_subparsers(dest="action", required=True)
    for action in ("status", "enable", "disable"):
        actions["ssh"].add_parser(action)
    actions["steam"].add_parser("status", help="show the installed client version")
    actions["update"].add_parser("status", help="show OS versions and channel")
    channel = actions["update"].add_parser("channel", help="choose the channel used by subsequent OS updates")
    channel.add_argument("channel", choices=("stable", "beta", "preview"))
    for obj, action, description in (
            ("steam", "repair", "repair Steam by reinstalling the factory client from the booted OS image; use Desktop Mode, including when running over SSH"),
            ("update", "install", "install an OS update using the selected channel"),
            ("update", "rollback", "select the previous OS version for the next restart")):
        command = actions[obj].add_parser(action, help=description, description=description)
        command.add_argument("--yes", "-y", action="store_true", help="skip confirmation")
    args = parser.parse_args(arguments)
    try:
        if args.object is None:
            from armada_tools_ui import main as gui_main
            return gui_main()
        if args.object == "status":
            return print_status()
        if args.object == "steam":
            if args.action == "status":
                return print_status("Steam")
            confirm("Reinstall the factory Steam client and clear its web cache. Your games, saves, accounts, and settings will be kept.", args.yes)
            repair_steam()
        elif args.object == "ssh":
            action = "get" if args.action == "status" else args.action
            state = ssh_request(action + "-ssh")
            print("SSH is running" if state["active"] else "SSH is stopped")
        elif args.action == "status":
            return print_status("Operating System")
        elif args.action == "channel":
            privileged_request("channel-" + args.channel)
            print(f"Update channel set to {args.channel}. Run armada-tools update install to install it.")
        elif args.action == "rollback":
            state = privileged_request("get-os")
            target = state["rollback"]
            if not target or target["incompatible"] or not target.get("checksum"):
                raise RuntimeError("No compatible previous deployment is available")
            confirm(f"Roll back to {target['version']}? Any queued update will be discarded. System settings return to that version; games and personal files are kept.", args.yes)
            privileged_operation("rollback-os", target["checksum"])
        elif args.action == "install":
            confirm("Install the latest OS version from the selected channel?", args.yes)
            privileged_operation("update-os")
        return 0
    except subprocess.CalledProcessError as error:
        return error.returncode
    except (Exception, KeyboardInterrupt) as error:
        print(f"Armada Tools: {error or 'Interrupted'}", file=sys.stderr)
        return 1
