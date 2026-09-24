#!/usr/bin/env python3
import importlib.machinery
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/armada"))
import armada_tools as backend


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader))
    loader.exec_module(module)
    return module


bridge = load("tools_bridge", ROOT / "system_files/usr/libexec/armada/armada-tools-priv")


class ToolsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.addCleanup(patch.stopall)

    def test_helper_rejects_unknown_commands_and_extra_arguments(self):
        for arguments in ([], ["write_config"], ["enable-ssh", "sshd"], ["rollback-os"],
                          ["get-os", "extra"], ["update-os", "extra"], ["restart-os", "extra"], ["channel-example"]):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                bridge.request(arguments)

    def test_helper_calls_os_operations_directly(self):
        with patch.object(bridge.armada_os, "execute", return_value={"ok": True}) as start:
            self.assertEqual(bridge.request(["rollback-os", "b" * 64]), {"ok": True})
            start.assert_called_once_with("rollback", "b" * 64)
            bridge.request(["update-os"])
            self.assertEqual(start.call_args.args, ("update",))
        with patch.object(bridge.armada_os, "select_channel") as channel:
            bridge.request(["channel-preview"])
            channel.assert_called_once_with("preview")

    def test_os_operation_output_is_text_and_waits_for_completion(self):
        def execute(*args):
            print("70%")
            return {"message": "Update staged"}
        output = io.StringIO()
        with patch.object(sys, "argv", ["helper", "update-os"]), \
                patch.object(bridge.os, "geteuid", return_value=0), \
                patch.object(sys, "stdout", output), \
                patch.object(bridge.armada_os, "execute", side_effect=execute):
            bridge.main()
        self.assertEqual(output.getvalue(), "70%\nUpdate staged\n")

    def test_export_requires_root_and_accepts_no_source_arguments(self):
        with patch.object(bridge, "export_steam") as export:
            with patch.object(sys, "argv", ["helper", "export-steam"]), \
                    patch.object(bridge.os, "geteuid", return_value=1000):
                with self.assertRaises(RuntimeError):
                    bridge.main()
            for arguments in (["export-steam", "/tmp/source"], ["export-steam", "checksum"]):
                with patch.object(sys, "argv", ["helper", *arguments]), \
                        patch.object(bridge.os, "geteuid", return_value=0):
                    with self.assertRaises(ValueError):
                        bridge.main()
            export.assert_not_called()

    def test_export_stream_is_not_wrapped_in_json(self):
        output = io.TextIOWrapper(io.BytesIO())
        payload = b"archive\x00\xff"
        with patch.object(sys, "argv", ["helper", "export-steam"]), \
                patch.object(bridge.os, "geteuid", return_value=0), \
                patch.object(sys, "stdout", output), \
                patch.object(bridge, "export_steam", side_effect=lambda: sys.stdout.buffer.write(payload)):
            bridge.main()
        output.flush()
        self.assertEqual(output.buffer.getvalue(), payload)

    def test_export_reads_booted_commit_without_a_write_lock(self):
        gi = Mock()
        repository = Mock()
        sysroot = repository.OSTree.Sysroot.new_default.return_value
        repo = Mock()
        sysroot.get_repo.return_value = (True, repo)
        sysroot.get_booted_deployment.return_value.get_csum.return_value = "b" * 64
        repo_fd = os.open(self.home, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, repo_fd)
        repo.get_path.return_value.get_path.return_value = f"/proc/self/fd/{repo_fd}"
        sysroot.lock.side_effect = OSError("Read-only file system")
        for failure in (None, "missing", "incomplete", "export"):
            with self.subTest(failure=failure), \
                    patch.dict(sys.modules, {"gi": gi, "gi.repository": repository}), \
                    patch.object(bridge.subprocess, "run") as run, \
                    patch.object(sys, "stderr", io.StringIO()):
                sysroot.reset_mock()
                sysroot.get_booted_deployment.return_value = None if failure == "missing" else Mock(get_csum=Mock(return_value="b" * 64))
                repo.load_commit.return_value = (True, None, 1 if failure == "incomplete" else 0)
                if failure == "export":
                    run.side_effect = subprocess.CalledProcessError(1, "ostree")
                if failure:
                    with self.assertRaises((RuntimeError, subprocess.CalledProcessError)):
                        bridge.export_steam()
                else:
                    bridge.export_steam()
                    run.assert_called_once_with([
                        "/usr/bin/ostree", "export", f"--repo={self.home.resolve()}",
                        "--no-xattrs", "--subpath=/var/home/armada/.local/share/Steam", "b" * 64,
                    ], check=True)
                if failure in {"missing", "incomplete"}:
                    run.assert_not_called()
                sysroot.lock.assert_not_called()
                sysroot.unlock.assert_not_called()

    def test_ssh_state_reports_service_activity(self):
        with patch.object(bridge.subprocess, "run", return_value=subprocess.CompletedProcess([], 3)) as run:
            self.assertEqual(bridge.request(["get-ssh"]), {"active": False})
            run.assert_called_once_with(["/usr/bin/systemctl", "is-active", "--quiet", "sshd"],
                                        timeout=5, check=False, capture_output=True, text=True)
            run.return_value = subprocess.CompletedProcess([], 0)
            self.assertEqual(bridge.request(["get-ssh"]), {"active": True})

    def test_ssh_status_failure_is_not_reported_as_stopped(self):
        result = subprocess.CompletedProcess([], 1, stderr="Failed to connect to bus")
        with patch.object(bridge.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "Failed to connect to bus"):
                bridge.request(["get-ssh"])

    def test_privileged_command_failure_preserves_diagnostic(self):
        error = subprocess.CalledProcessError(1, "systemctl", stderr="Unit sshd.service is masked")
        with patch.object(bridge.subprocess, "run", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "Unit sshd.service is masked"):
                bridge.request(["enable-ssh"])

    def test_ssh_toggle_is_persistent(self):
        with patch.object(bridge.armada_os, "command") as command, \
                patch.object(bridge.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)):
            bridge.request(["enable-ssh"])
            command.assert_called_once_with(["/usr/bin/systemctl", "enable", "--now", "sshd"], timeout=30)
            command.reset_mock()
            bridge.request(["disable-ssh"])
            command.assert_called_once_with(["/usr/bin/systemctl", "disable", "--now", "sshd"], timeout=30)

    def test_network_addresses_exclude_unusable_addresses(self):
        addresses = backend.network_addresses([
            {"ifname": "lo", "addr_info": [{"scope": "global", "local": "127.0.0.1"}]},
            {"ifname": "wlan0", "addr_info": [
                {"scope": "global", "local": "192.0.2.44"},
                {"scope": "global", "local": "2001:db8::44"},
                {"scope": "link", "local": "fe80::1"},
                {"scope": "global", "local": "2001:db8::55", "tentative": True},
                {"scope": "global", "local": "bad address"},
            ]},
        ])
        self.assertEqual(addresses, [("wlan0", "192.0.2.44"), ("wlan0", "2001:db8::44")])

    def test_client_version_reads_installed_manifest_and_ignores_pending_and_log(self):
        package = self.home / ".local/share/Steam/package"
        package.mkdir(parents=True)
        installed = package / "steam_client_steamdeck_publicbeta_linuxarm64.manifest"
        pending = package / "steam_client_steamdeck_publicbeta_linuxarm64"
        log = package.parent / "logs/bootstrap_log.txt"
        log.parent.mkdir()
        log.write_text("installed version 1788989629,\n")
        pending.write_text('"linuxarm64" { "version" "1790036264" }')
        with patch.object(backend.Path, "home", return_value=self.home):
            self.assertEqual(backend.steam_client_version(), "Unknown")
            installed.write_text('"linuxarm64" { "version" "1788652215" }')
            self.assertEqual(backend.steam_client_version(), "1788652215")
            installed.write_text('"linuxarm64" { "version" "1790036264" }')
            self.assertEqual(backend.steam_client_version(), "1790036264")
            installed.write_text('"linuxarm64" { "version" "0" }')
            self.assertEqual(backend.steam_client_version(), "Unknown")
            installed.write_text("truncated")
            self.assertEqual(backend.steam_client_version(), "Unknown")

    def test_client_version_does_not_guess_between_conflicting_installed_manifests(self):
        package = self.home / ".local/share/Steam/package"
        package.mkdir(parents=True)
        (package / "steam_client_linuxarm64.manifest").write_text('"linuxarm64" { "version" "1788652215" }')
        (package / "steam_client_steamdeck_publicbeta_linuxarm64.manifest").write_text('"linuxarm64" { "version" "1790036264" }')
        with patch.object(backend.Path, "home", return_value=self.home):
            self.assertEqual(backend.steam_client_version(), "Unknown")

    def run_repair(self, code):
        script = self.home / "health-check"
        script.write_text(f'#!/bin/sh\necho "Verifying factory Steam"\nsleep 0.2\necho "Finished <diagnostic>"\nexit {code}\n')
        script.chmod(0o755)
        patch.object(backend, "TOOLS", str(script)).start()
        patch.object(backend.Path, "home", return_value=self.home).start()
        job = backend.SteamJob()
        job.start()
        self.addCleanup(lambda: job.process.kill() if job.process.poll() is None else None)
        with self.assertRaises(RuntimeError):
            job.start()
        job.process.wait(timeout=5)
        return job

    def test_repair_keeps_a_private_log_and_process_result(self):
        job = self.run_repair(0)
        self.assertEqual(job.status()["code"], 0)
        self.assertIn("Finished", job.status()["message"])
        self.assertEqual(job.log.stat().st_mode & 0o777, 0o600)

    def test_failed_repair_retains_diagnostic_details(self):
        job = self.run_repair(1)
        self.assertEqual(job.status()["code"], 1)
        self.assertIn("<diagnostic>", job.status()["output"])

    def test_operation_logs_are_reused_and_failure_shows_reason(self):
        with patch.object(backend.Path, "home", return_value=self.home):
            job = backend.CommandJob()
            job.start([sys.executable, "-c", "print('previous operation')"], "os-operation.log")
            job.process.wait(timeout=5)
            job.start([sys.executable, "-c",
                       "import sys; print('Not enough free space'); print('42%'); sys.exit(7)"], "os-operation.log")
            job.process.wait(timeout=5)
            self.assertEqual(job.status()["code"], 7)
            self.assertEqual(job.status()["message"], "Not enough free space")
            self.assertNotIn("previous operation", job.log.read_text())
            self.assertEqual(list(job.log.parent.iterdir()), [job.log])

    def test_missing_log_does_not_lose_repair_completion(self):
        job = self.run_repair(0)
        job.log.unlink()
        self.assertEqual(job.status()["code"], 0)
        self.assertIn("unavailable", job.status()["message"])


if __name__ == "__main__":
    unittest.main()
