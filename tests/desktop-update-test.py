#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UpdateHookTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        bootc = self.bin / "bootc"
        bootc.write_text('#!/bin/sh\n[ "${BAD_BOOTC:-0}" = 0 ] || exit 1\ncat "$BOOTC_STATE"\n')
        bootc.chmod(0o755)
        (self.base / "bootc.json").write_text(json.dumps({"status": {"booted": {"image": {}}, "rollbackQueued": False}}))
        library = self.base / "update-lib"
        library.write_text((ROOT / "system_files/usr/lib/armada/update-lib").read_text() + '''
ARMADA_CHANNEL_STATE="$TEST_CHANNEL_STATE"
armada_update_log() { echo "$*" >&2; }
armada_booted_ref() { echo "${BOOTED_REF:-ostree-image-signed:docker://ghcr.io/armada-os/armada:stable}"; }
armada_update_reserve_bytes() { echo 0; }
armada_available_bytes() { echo "${AVAILABLE_BYTES:-1000}"; }
armada_update_target() { echo ghcr.io/armada-os/armada stable; }
armada_local_state() { echo "sha256:booted ${STAGED_DIGEST:--} ${STAGED_REF:--} staged-version"; }
armada_staged_ref() { echo "${STAGED_REF:-}"; }
armada_remote_info() {
    [[ "${NETWORK_FAILURE:-0}" = 0 ]] || return 1
    echo "100 ${REMOTE_DIGEST:-sha256:new} new-version"
}
armada_bootc_with_progress() { echo "$*" >> "$BOOTC_CALLS"; echo '70%'; }
''')
        self.hook = self.base / "update"
        self.hook.write_text((ROOT / "system_files/usr/libexec/armada/armada-update").read_text().replace(
            "source /usr/lib/armada/update-lib", f"source {library}"))
        self.hook.chmod(0o755)
        self.login = self.base / "loginusers.vdf"
        self.wrapper = self.base / "steamos-update"
        self.wrapper.write_text((ROOT / "system_files/usr/bin/steamos-update").read_text().replace(
            "/var/home/armada/.local/share/Steam/config/loginusers.vdf", str(self.login)).replace(
            "/usr/libexec/armada/armada-update", str(self.hook)))
        self.wrapper.chmod(0o755)
        self.selector = self.base / "select-branch"
        self.selector.write_text((ROOT / "system_files/usr/libexec/armada/armada-select-branch").read_text().replace(
            "source /usr/lib/armada/update-lib", f"source {library}"))
        self.env = {**os.environ, "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
                    "BOOTC_STATE": str(self.base / "bootc.json"), "BOOTC_CALLS": str(self.base / "calls"),
                    "TEST_CHANNEL_STATE": str(self.base / "channel")}

    def run_hook(self, *arguments, **kwargs):
        return subprocess.run(["bash", str(self.hook), *arguments], env=self.env,
                              text=True, capture_output=True, timeout=5, **kwargs)

    def run_wrapper(self, *arguments):
        return subprocess.run([str(self.wrapper), *arguments], env=self.env,
                              text=True, capture_output=True, timeout=5)

    def test_direct_update_and_check_do_not_require_steam_login(self):
        result = self.run_hook("check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "new-version")
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.base / "calls").read_text().strip(), "bootc upgrade")

    def test_steam_suppresses_check_and_apply_without_saved_account(self):
        self.hook.write_text('#!/bin/sh\necho "Updater must not run"\nexit 99\n')
        for contents in (None, '"users" {}\n'):
            if contents is not None:
                self.login.write_text(contents)
            for arguments in ((), ("--enable-duplicate-detection", "check")):
                with self.subTest(contents=contents, arguments=arguments):
                    result = self.run_wrapper(*arguments)
                    self.assertEqual(result.returncode, 7)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "")

    def test_steam_capability_probe_works_before_login(self):
        self.hook.write_text('#!/bin/sh\nexit 99\n')
        for arguments in (("--supports-duplicate-detection",), ("check", "--supports-duplicate-detection")):
            result = self.run_wrapper(*arguments)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")

    def test_steam_check_and_apply_work_with_saved_account(self):
        self.login.write_text('"users" { "123" { "AccountName" "test" } }\n')
        result = self.run_wrapper("--enable-duplicate-detection", "check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "new-version")
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "70%\n")
        self.assertEqual((self.base / "calls").read_text().strip(), "bootc upgrade")

    def test_steam_wrapper_preserves_arguments_output_and_exit_status(self):
        self.login.write_text('"AccountName" "test"\n')
        self.hook.write_text('#!/usr/bin/python3\nimport json,os,sys\n'
                             'print(json.dumps(sys.argv[1:]))\nprint("diagnostic", file=sys.stderr)\n'
                             'sys.exit(int(os.environ["UPDATE_EXIT"]))\n')
        arguments = ("--enable-duplicate-detection", "check", "argument with spaces", "*")
        for code in (0, 1, 7):
            self.env["UPDATE_EXIT"] = str(code)
            result = self.run_wrapper(*arguments)
            self.assertEqual(result.returncode, code)
            self.assertEqual(json.loads(result.stdout), list(arguments))
            self.assertEqual(result.stderr, "diagnostic\n")

    def test_check_retains_steam_version_and_exit_code_contract(self):
        self.env["REMOTE_DIGEST"] = "sha256:booted"
        self.assertEqual(self.run_hook("check").returncode, 7)
        self.env.update(REMOTE_DIGEST="sha256:staged", STAGED_DIGEST="sha256:staged", STAGED_REF="ghcr.io/armada-os/armada:stable")
        self.assertEqual(self.run_hook("check").stdout.strip(), "staged-version")
        self.env["NETWORK_FAILURE"] = "1"
        result = self.run_hook("check")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.returncode, 7)

    def test_storage_failure_does_not_apply(self):
        self.env["AVAILABLE_BYTES"] = "1"
        self.assertNotEqual(self.run_hook().returncode, 0)
        self.assertFalse((self.base / "calls").exists())

    def test_desktop_apply_keeps_signature_policy(self):
        self.env["BOOTED_REF"] = "ostree-unverified-registry:ghcr.io/armada-os/armada:stable"
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.base / "calls").read_text().strip(), "bootc switch --enforce-container-sigpolicy ghcr.io/armada-os/armada:stable")

    def test_queued_rollback_does_not_block_explicit_updates(self):
        (self.base / "bootc.json").write_text(json.dumps({"status": {"booted": {"image": {}}, "rollbackQueued": True}}))
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.base / "calls").read_text().splitlines(), ["bootc upgrade"])

    def test_channel_selection_replaces_state_and_allows_queued_rollback(self):
        (self.base / "bootc.json").write_text(json.dumps({"status": {"booted": {"image": {}}, "rollbackQueued": True}}))
        for channel in ("beta", "testing"):
            result = subprocess.run(["bash", str(self.selector), channel], env=self.env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((self.base / "channel").read_text(), channel + "\n")
        self.assertEqual((self.base / "channel").stat().st_mode & 0o777, 0o644)
        self.assertFalse(list(self.base.glob("channel.*")))


if __name__ == "__main__":
    unittest.main()
