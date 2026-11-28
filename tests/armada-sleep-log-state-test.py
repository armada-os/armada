import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "decky/armada-control/py_modules"))
from armada_control import system


class SleepLogStateTest(unittest.TestCase):
    def directory(self, environment=(), files=(), passed=(), unset=(), manager=()):
        def run(command):
            values = [manager] if command[-1] == "Environment" else [environment, files, passed, unset]
            return SimpleNamespace(returncode=0, stdout="\n".join(json.dumps({"data": value}) for value in values))
        with patch.object(system, "run_cmd", side_effect=run):
            return system.sleep_log_directory()

    def test_hook_is_the_single_source_of_the_default_directory(self):
        self.assertEqual(self.directory(), "/var/home/armada/Documents/sleep-logs")

    def test_unit_overrides_and_runtime_changes_are_read_each_time(self):
        for value in ("/tmp/custom logs", "/var/home/armada/new-logs"):
            self.assertEqual(self.directory([f"ARMADA_SLEEP_DEBUG_REPORT_DIR={value}"]), value)

    def test_plugin_environment_cannot_override_the_service_environment(self):
        with patch.dict(os.environ, {"ARMADA_SLEEP_DEBUG_REPORT_DIR": "/incorrect-plugin-directory"}):
            self.assertEqual(self.directory(), "/var/home/armada/Documents/sleep-logs")

    def test_passed_manager_environment_and_unit_precedence(self):
        name = "ARMADA_SLEEP_DEBUG_REPORT_DIR"
        self.assertEqual(self.directory(passed=[name], manager=[f"{name}=/manager"]), "/manager")
        self.assertEqual(self.directory([f"{name}=/unit"], passed=[name], manager=[f"{name}=/manager"]), "/unit")
        self.assertEqual(self.directory([f"{name}=/unit"], unset=[name]), "/var/home/armada/Documents/sleep-logs")

    def test_unresolved_or_malformed_configuration_does_not_show_a_guessed_path(self):
        self.assertIsNone(self.directory(files=[["/etc/custom-environment", False]]))
        self.assertIsNone(self.directory(["ARMADA_SLEEP_DEBUG_REPORT_DIR=relative/path"]))
        with patch.object(system, "run_cmd", return_value=SimpleNamespace(returncode=0, stdout="invalid")):
            self.assertIsNone(system.sleep_log_directory())
        with patch.object(system, "run_cmd", return_value=None):
            self.assertIsNone(system.sleep_log_directory())

    def test_status_reports_enabled_and_current_directory_together(self):
        with patch.object(system, "get_sleep_logs_enabled", return_value=True), patch.object(system, "sleep_log_directory", return_value="/custom"):
            self.assertEqual(system.get_sleep_logs_status(), {"enabled": True, "directory": "/custom"})


if __name__ == "__main__":
    unittest.main()
