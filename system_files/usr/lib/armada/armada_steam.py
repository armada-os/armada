#!/usr/bin/python3
import contextlib
import fcntl
import os
from pathlib import Path, PurePosixPath
import signal
import select
import subprocess
import tarfile
import time
import zlib
import shutil

SOURCE = "/usr/libexec/armada/armada-tools-priv"
PRESERVE = {"steamapps", "userdata", "config", "compatibilitytools.d", "logs", "appcache", "registry.vdf"}


def exists(path):
    return os.path.lexists(path)


def stop_clients(root):
    handles = []
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdecimal():
                continue
            fd = None
            try:
                fd = os.pidfd_open(int(entry.name))
                executable = Path(os.readlink(entry / "exe").removesuffix(" (deleted)"))
                if entry.stat().st_uid == os.getuid() and executable.is_relative_to(root) and executable.name in {"steam", "steamwebhelper", "steamservice"}:
                    handles.append(fd)
                    signal.pidfd_send_signal(fd, signal.SIGTERM)
                else:
                    os.close(fd)
            except (OSError, RuntimeError):
                if fd is not None and fd not in handles:
                    with contextlib.suppress(OSError):
                        os.close(fd)
        pending = set(handles)
        poller = select.poll()
        for fd in pending:
            poller.register(fd, select.POLLIN)
        for timeout, sig in ((15, signal.SIGKILL), (5, None)):
            deadline = time.monotonic() + timeout
            while pending and time.monotonic() < deadline:
                for fd, _ in poller.poll(100):
                    pending.discard(fd)
                    poller.unregister(fd)
            if sig:
                for fd in pending:
                    with contextlib.suppress(ProcessLookupError):
                        signal.pidfd_send_signal(fd, sig)
        if pending:
            raise RuntimeError("Steam processes did not stop; client files were not replaced")
    finally:
        for fd in handles:
            os.close(fd)


def progress(message):
    print(message, flush=True)


def verify_client(root):
    manifests = list((root / "package").glob("steam_client_*_linuxarm64.installed"))
    if not manifests:
        raise RuntimeError("Factory client has no installed-file manifest")
    count = 0
    for manifest in manifests:
        for line in manifest.read_text().splitlines():
            if "," not in line:
                continue
            name, fields = line.rsplit(",", 1)
            size, timestamp, checksum = map(int, fields.split(";"))
            relative = PurePosixPath(name)
            if relative.is_absolute() or ".." in relative.parts:
                raise RuntimeError(f"Unsafe manifest path: {name}")
            path = root / relative
            if size == -1:
                if not path.is_dir() or path.is_symlink():
                    raise RuntimeError(f"Missing factory directory: {name}")
            elif size == -2:
                if not path.is_symlink():
                    raise RuntimeError(f"Missing factory symlink: {name}")
            elif size >= 0:
                if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
                    raise RuntimeError(f"Invalid factory file: {name}")
                crc = 0
                with path.open("rb") as stream:
                    while chunk := stream.read(1024 * 1024):
                        crc = zlib.crc32(chunk, crc)
                if crc != checksum:
                    raise RuntimeError(f"Factory checksum mismatch: {name}")
                # Steam validates manifest mtimes; OSTree exports them as epoch.
                os.utime(path, (timestamp, timestamp))
                count += 1
    if not count or not os.access(root / "steamrtarm64/steam", os.X_OK):
        raise RuntimeError("Factory client has no executable ARM Steam")
    return count


def extract_source(destination, log):
    with log.open("wb") as errors:
        process = subprocess.Popen(["pkexec", "--disable-internal-agent", SOURCE, "export-steam"], stdout=subprocess.PIPE, stderr=errors)
        try:
            with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
                for member in archive:
                    if shutil.disk_usage(destination).free < member.size + 64 * 1024 * 1024:
                        raise RuntimeError("Not enough free space to stage the factory client")
                    archive.extract(member, destination, filter="data")
            process.stdout.close()
            if process.wait() != 0:
                raise RuntimeError(f"Cannot read factory Steam: {log.read_text().strip()}")
        except tarfile.ReadError as error:
            raise RuntimeError(f"Cannot read factory Steam: {log.read_text().strip() or error}") from error
        finally:
            process.stdout.close()
            if process.poll() is None:
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    with contextlib.suppress(ProcessLookupError, PermissionError):
                        process.kill()
                    with contextlib.suppress(subprocess.TimeoutExpired):
                        process.wait(timeout=2)


class SteamMaintenance:
    def __init__(self, home=None, runtime=None):
        self.home = Path(home or Path.home())
        self.root = self.home / ".local/share/Steam"
        self.runtime = Path(runtime or os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "armada-steam-health"
        self.runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.work = self.root.parent / ".armada-steam-repair"

    def check_root(self):
        if (self.home / ".steam").is_symlink():
            raise RuntimeError("Refusing to modify a symlinked ~/.steam directory")
        configured = Path(os.environ.get("STEAM_ROOT", self.root))
        if configured != self.root or self.root.is_symlink():
            raise RuntimeError("Repair is disabled for a custom or symlinked Steam installation")
        if (self.home / "devkit-game/devkit-steam").exists():
            raise RuntimeError("Repair is disabled for a sideloaded Steam installation")

    @contextlib.contextmanager
    def lock(self):
        with (self.runtime / "repair.lock").open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("Another Steam maintenance operation is already running") from None
            yield

    def repair_links(self):
        dot = self.home / ".steam"
        if dot.is_symlink():
            raise RuntimeError("Refusing to replace a symlinked ~/.steam directory")
        dot.mkdir(exist_ok=True)
        links = {"steam": "", "root": "", "sdk32": "linux32", "sdk64": "linux64",
                 "sdkarm64": "linuxarm64", "binarm64": "steamrtarm64",
                 "bin32": "ubuntu12_32", "bin64": "ubuntu12_64"}
        for name, target in links.items():
            path = dot / name
            desired = os.path.relpath(self.root / target, dot)
            if path.is_symlink() and os.readlink(path) == desired:
                continue
            if exists(path) and not path.is_symlink():
                backup = dot / f"{name}.before-repair-{time.time_ns()}"
                path.rename(backup)
                progress(f"Preserved unexpected {path} at {backup}")
            temporary = dot / f".{name}.repair"
            temporary.unlink(missing_ok=True)
            temporary.symlink_to(desired)
            temporary.replace(path)

    def restore(self):
        self.check_root()
        with self.lock():
            if self.work.exists():
                shutil.rmtree(self.work)
            self.work.mkdir(mode=0o700, parents=True)
            new, old = self.work / "new", self.work / "old"
            new.mkdir()
            old.mkdir()
            progress("Preparing factory Steam restoration")
            extract_source(new, self.work / "source.log")
            progress("Verifying factory Steam")
            verify_client(new)
            entries = sorted(p.name for p in new.iterdir()
                             if p.name not in PRESERVE and not p.name.startswith("ssfn"))
            progress("Flushing factory Steam to disk")
            os.sync()
            stop_clients(self.root.resolve())
            self.root.mkdir(parents=True, exist_ok=True)
            for name in entries:
                live = self.root / name
                if exists(live):
                    live.rename(old / name)
                (new / name).rename(live)
            self.repair_links()
            self.reset_caches()
            self.clear_runtime_files()
            progress("Removing old client files")
            shutil.rmtree(self.work, ignore_errors=True)
            progress("Factory Steam restored; games and account data preserved")

    def clear_runtime_files(self):
        for name in ("steam.pid", "steam.token", "steam.pipe"):
            (self.home / ".steam" / name).unlink(missing_ok=True)

    def cache_paths(self):
        for relative in ("config/htmlcache", "config/widevine", "appcache/httpcache", "appcache/cefdata"):
            path = self.root / relative
            if exists(path) and path.parent.resolve().is_relative_to(self.root.resolve()):
                yield path

    def reset_caches(self):
        for path in self.cache_paths():
            if path.is_symlink() or not path.is_dir():
                path.unlink(missing_ok=True)
            else:
                shutil.rmtree(path)
