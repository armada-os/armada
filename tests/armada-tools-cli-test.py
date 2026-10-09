#!/usr/bin/env python3
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "system_files/usr/lib/armada"
sys.path.insert(0, str(LIB))
import armada_tools as tools


class CliTests(unittest.TestCase):
    def invoke(self, *arguments):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return tools.main(list(arguments))

    def test_help_and_status_do_not_import_gtk(self):
        code = """
import sys
class NoGtk:
    def find_spec(self, fullname, *args):
        if fullname == 'gi' or fullname == 'armada_tools_ui':
            raise AssertionError('CLI imported GTK')
sys.meta_path.insert(0, NoGtk())
from unittest.mock import patch
import armada_tools as tools
with patch.object(tools, 'print_status', return_value=0):
    assert tools.main(['status']) == 0
try:
    tools.main(['steam', '--help'])
except SystemExit as error:
    assert error.code == 0
"""
        result = subprocess.run([sys.executable, "-c", code], env={**os.environ, "PYTHONPATH": str(LIB)},
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("repair", result.stdout)

    def test_no_command_opens_gui(self):
        from types import SimpleNamespace
        with patch.dict(sys.modules, {"armada_tools_ui": SimpleNamespace(main=lambda: 7)}):
            self.assertEqual(self.invoke(), 7)

    def test_noninteractive_repair_requires_explicit_confirmation(self):
        with patch.object(tools.sys.stdin, "isatty", return_value=False), patch.object(tools, "repair_steam") as operation:
            self.assertEqual(self.invoke("steam", "repair"), 1)
            operation.assert_not_called()
            self.assertEqual(self.invoke("steam", "repair", "--yes"), 0)
            operation.assert_called_once_with()

    def test_repair_uses_factory_client(self):
        import armada_steam
        with patch.object(tools.os, "geteuid", return_value=1000), patch.object(armada_steam, "SteamMaintenance") as factory:
            self.assertEqual(self.invoke("steam", "repair", "--yes"), 0)
            factory.return_value.restore.assert_called_once_with()

    def test_rollback_confirms_named_target_and_passes_its_checksum(self):
        state = {"rollback": {"version": "previous", "checksum": "b" * 64, "incompatible": False}}
        with patch.object(tools, "privileged_request", return_value=state), \
                patch.object(tools, "privileged_operation") as operation, \
                patch.object(tools, "confirm") as confirm:
            self.assertEqual(self.invoke("update", "rollback", "--yes"), 0)
            self.assertIn("previous", confirm.call_args.args[0])
            self.assertEqual(operation.call_args.args, ("rollback-os", "b" * 64))

    def test_backend_failure_returns_nonzero(self):
        with patch.object(tools, "privileged_operation", side_effect=RuntimeError("failed")):
            self.assertEqual(self.invoke("update", "install", "--yes"), 1)

    def test_subprocess_failure_does_not_append_python_command_repr(self):
        with patch.object(tools, "privileged_operation", side_effect=subprocess.CalledProcessError(7, "pkexec")), \
                contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(tools.main(["update", "install", "--yes"]), 7)
        self.assertEqual(errors.getvalue(), "")

    def test_update_cli_waits_and_propagates_exit_status(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "finished"
            for code in (0, 7):
                marker.unlink(missing_ok=True)
                command = [sys.executable, "-c",
                           "import sys,time; from pathlib import Path; time.sleep(.1); "
                           "Path(sys.argv[1]).write_text('done'); sys.exit(int(sys.argv[2]))",
                           str(marker), str(code)]
                with patch.object(tools, "privileged_command", return_value=command):
                    self.assertEqual(self.invoke("update", "install", "--yes"), code)
                self.assertEqual(marker.read_text(), "done")

    def test_ssh_and_branch_use_shared_backend(self):
        with patch.object(tools, "privileged_request", return_value={"active": True}) as request:
            self.assertEqual(self.invoke("ssh", "enable"), 0)
            request.assert_called_with("enable-ssh")
            self.assertEqual(self.invoke("update", "channel", "preview"), 0)
            request.assert_called_with("channel-preview")

    def test_removed_steam_commands_are_rejected(self):
        for command in (("restore",), ("games", "list"), ("games", "uninstall", "100", "--yes")):
            with self.subTest(command=command), self.assertRaises(SystemExit) as error:
                self.invoke("steam", *command)
            self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
