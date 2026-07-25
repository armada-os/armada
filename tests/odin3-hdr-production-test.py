#!/usr/bin/python3
"""Focused production-policy tests for the AYN Odin 3 HDR session."""

from __future__ import annotations

import hashlib
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "system_files/usr/lib/armada/devices/defaults.conf"
ODIN3 = ROOT / "system_files/usr/lib/armada/devices/ayn-odin-3.conf"
DEVICE_ENV = ROOT / "system_files/usr/libexec/armada/device-env"
FINALIZER = ROOT / "system_files/usr/libexec/armada/hdr-session-finalize"
WRAPPER = ROOT / "system_files/usr/libexec/armada/gamescope-odin3-hdr"
SESSION = ROOT / "system_files/etc/gamescope-session-plus/sessions.d/steam"
POLICY_LUA = ROOT / "system_files/usr/share/gamescope/scripts/00-armada-session-policy.lua"
PROFILE_LUA = ROOT / "system_files/usr/share/gamescope/scripts/10-armada/ayn.odin3.oled.lua"
EDID_HEX = ROOT / "system_files/usr/share/armada/hdr/ayn-odin-3.edid.hex"
INSTALL_STEAM = ROOT / "build_files/30-install-steam-session.sh"
VALIDATE_GAMESCOPE = ROOT / "build_files/validate-gamescope-hdr-package.sh"
VENDOR_FILES = ROOT / "build_files/40-vendor-system-files.sh"

EDID_SHA256 = "a6ee4ff0c7f43723c093ea2575221a52668e7d610c13738274bf0cef61c96695"


def find_bash() -> str | None:
    candidates = [shutil.which("bash")]
    if os.name == "nt":
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        candidates.extend(
            [
                str(program_files / "Git/bin/bash.exe"),
                str(program_files / "Git/usr/bin/bash.exe"),
            ]
        )
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        try:
            result = subprocess.run(
                [candidate, "--version"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0 and "GNU bash" in result.stdout:
            return candidate
    return None


BASH = find_bash()


def bash_path(path: Path) -> str:
    """Return a path understood by GNU Bash on POSIX and Git-for-Windows."""
    # Keep the final path component intact so symlink-rejection tests remain valid.
    absolute = path.absolute()
    if os.name != "nt":
        return str(absolute)
    drive = absolute.drive.rstrip(":").lower()
    tail = absolute.as_posix().split(":", 1)[1].lstrip("/")
    return f"/{drive}/{tail}"


def assignment_map(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key] = value.strip("'")
    return result


def parse_emitted_exports(output: str) -> dict[str, str]:
    exports: dict[str, str] = {}
    for line in output.splitlines():
        fields = shlex.split(line)
        if len(fields) != 7 or fields[:3] != ["builtin", "export", "--"]:
            continue
        if fields[4:] != ["||", "exit", "1"] or "=" not in fields[3]:
            continue
        key, value = fields[3].split("=", 1)
        exports[key] = value
    return exports


class ProductionPolicyStaticTests(unittest.TestCase):
    def test_device_policy_is_exact_and_fail_closed_elsewhere(self) -> None:
        defaults = assignment_map(DEFAULTS)
        odin3 = assignment_map(ODIN3)

        self.assertEqual(defaults["ARMADA_HDR_CAPABLE"], "0")
        self.assertEqual(defaults["ARMADA_HDR_PROFILE"], "")
        self.assertNotIn("ARMADA_HDR_CAPABLE", odin3)
        self.assertEqual(odin3["ARMADA_DEVICE_ID"], "ayn-odin-3")
        self.assertEqual(odin3["ARMADA_PRIMARY_CONNECTOR"], "DSI-1")
        self.assertEqual(odin3["ARMADA_HDR_PROFILE"], "ayn-odin-3-oled-gamma22-v1")
        self.assertEqual(odin3["ARMADA_HDR_OUTPUT_EOTF"], "gamma22")
        self.assertEqual(odin3["ARMADA_HDR_MAX_CLL"], "650")
        self.assertEqual(odin3["ARMADA_HDR_MAX_FALL"], "650")
        self.assertEqual(odin3["ARMADA_HDR_SDR_WHITE"], "203")
        self.assertEqual(odin3["ARMADA_HDR_EDID_SHA256"], EDID_SHA256)

        helper = DEVICE_ENV.read_text(encoding="utf-8")
        for name in (
            "ARMADA_HDR_PROFILE",
            "ARMADA_HDR_CAPABLE",
            "ARMADA_HDR_OUTPUT_EOTF",
            "ARMADA_HDR_MAX_CLL",
            "ARMADA_HDR_MAX_FALL",
            "ARMADA_HDR_EDID_SHA256",
        ):
            self.assertEqual(helper.count(name), 1)

    def test_edid_seed_is_exact_and_checksum_valid(self) -> None:
        payload = bytes.fromhex(EDID_HEX.read_text(encoding="ascii"))
        self.assertEqual(len(payload), 256)
        self.assertEqual(hashlib.sha256(payload).hexdigest(), EDID_SHA256)
        self.assertEqual(sum(payload[:128]) & 0xFF, 0)
        self.assertEqual(sum(payload[128:]) & 0xFF, 0)

        vendor = VENDOR_FILES.read_text(encoding="utf-8")
        self.assertIn("bytes.fromhex", vendor)
        self.assertIn(EDID_SHA256, vendor)
        self.assertIn("ayn-odin-3.edid.bin", vendor)

    def test_session_and_wrapper_do_not_force_hdr_on(self) -> None:
        session = SESSION.read_text(encoding="utf-8")
        wrapper = WRAPPER.read_text(encoding="utf-8")
        finalizer = FINALIZER.read_text(encoding="utf-8")
        installer = INSTALL_STEAM.read_text(encoding="utf-8")

        self.assertNotIn("ARMADA_HDR_CAPABLE", session)
        self.assertIn("production_block = environment_block +", installer)
        self.assertIn("/usr/libexec/armada/hdr-session-finalize", installer)
        self.assertIn('XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-}"', installer)
        self.assertIn('emit_export ARMADA_HDR_CAPABLE 1', finalizer)
        self.assertIn('emit_export gamescope_hdr_enabled false', finalizer)
        self.assertNotIn('emit_export ENABLE_GAMESCOPE_HDR', finalizer)
        self.assertIn("qualified_options+=(--hdr-itm-target-nits 650)", wrapper)
        self.assertIn("qualified_options+=(--expose-client-sampleable-formats)", wrapper)
        self.assertNotIn("qualified_options+=(--hdr-enabled", wrapper)
        self.assertNotIn("qualified_options+=(--hdr-itm-enable", wrapper)

        self.assertIn("validate-gamescope-hdr-package.sh", installer)
        self.assertNotIn("/usr/bin/gamescope --help", installer)

    def test_lua_profile_requires_exact_device_connector_and_calibration(self) -> None:
        policy = POLICY_LUA.read_text(encoding="utf-8")
        profile = PROFILE_LUA.read_text(encoding="utf-8")

        for token in (
            '"ayn-odin-3:DSI-1"',
            '"immutable-image"',
            '"ayn-odin-3"',
            'connector == "DSI-1"',
            "display.has_edid == false",
            "eotf = gamescope.eotf.gamma22",
            "max_cll == 650",
            "max_fall == 650",
            "sdr_white == 203",
        ):
            self.assertIn(token, profile)
        self.assertIn("script_use_local_scripts.value = false", policy)
        self.assertIn("script_use_user_scripts.value = false", policy)


@unittest.skipUnless(BASH, "requires GNU Bash")
class ProductionFinalizerIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.model = self.root / "model"
        self.model.write_bytes(b"AYN Odin 3\0")

        self.gamescope = self._file("gamescope", "#!/bin/bash\nexit 0\n", executable=True)
        self.wrapper = self._file("wrapper", "#!/bin/bash\nexit 0\n", executable=True)
        self.marker = self._file("capabilities", "expose-client-sampleable-formats-v1\n")
        self.policy_lua = self._file("policy.lua", "-- policy\n")
        self.profile_lua = self._file("profile.lua", "-- profile\n")
        self.edid = self.root / "edid.bin"
        self.edid.write_bytes(bytes.fromhex(EDID_HEX.read_text(encoding="ascii")))
        self.device_env = self.root / "device-env"
        self.finalizer = self.root / "hdr-session-finalize"
        self._write_device_env("DSI-1")
        self._write_finalizer()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _file(self, name: str, contents: str, *, executable: bool = False) -> Path:
        path = self.root / name
        path.write_text(contents, encoding="utf-8")
        path.chmod(0o755 if executable else 0o644)
        return path

    def _write_device_env(self, connector: str) -> None:
        values = {
            "ARMADA_DEVICE_ID": "ayn-odin-3",
            "ARMADA_DEVICE_NAME": "AYN Odin 3",
            "ARMADA_PRIMARY_CONNECTOR": connector,
            "ARMADA_PANEL_TYPE": "internal",
            "ARMADA_HDR_PROFILE": "ayn-odin-3-oled-gamma22-v1",
            "ARMADA_HDR_CAPABLE": "0",
            "ARMADA_HDR_OUTPUT_EOTF": "gamma22",
            "ARMADA_HDR_R_X": "0.6800",
            "ARMADA_HDR_R_Y": "0.3200",
            "ARMADA_HDR_G_X": "0.2650",
            "ARMADA_HDR_G_Y": "0.6900",
            "ARMADA_HDR_B_X": "0.1500",
            "ARMADA_HDR_B_Y": "0.0600",
            "ARMADA_HDR_W_X": "0.3127",
            "ARMADA_HDR_W_Y": "0.3290",
            "ARMADA_HDR_MAX_CLL": "650",
            "ARMADA_HDR_MAX_FALL": "650",
            "ARMADA_HDR_MIN_CLL": "0.0020000000949949",
            "ARMADA_HDR_SDR_WHITE": "203",
            "ARMADA_HDR_PANEL_NATIVE_WIDTH_MM": "75",
            "ARMADA_HDR_PANEL_NATIVE_HEIGHT_MM": "133",
            "ARMADA_HDR_EDID_SHA256": EDID_SHA256,
        }
        lines = ["#!/bin/bash"]
        for key, value in values.items():
            assignment = f"{key}={shlex.quote(value)}"
            lines.append(f"printf '%s\\n' {shlex.quote(assignment)}")
        self.device_env.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.device_env.chmod(0o755)

    def _write_finalizer(self) -> None:
        text = FINALIZER.read_text(encoding="utf-8")
        replacements = {
            "MODEL_PATH": self.model,
            "DEVICE_ENV": self.device_env,
            "GAMESCOPE": self.gamescope,
            "GAMESCOPE_WRAPPER": self.wrapper,
            "GAMESCOPE_CAPABILITIES": self.marker,
            "POLICY_SCRIPT": self.policy_lua,
            "PROFILE_SCRIPT": self.profile_lua,
            "EDID_SEED": self.edid,
        }
        for name, value in replacements.items():
            replacement = f"readonly {name}={shlex.quote(bash_path(value))}"
            text, count = re.subn(
                rf"^readonly {name}=.*$",
                lambda _match: replacement,
                text,
                count=1,
                flags=re.MULTILINE,
            )
            self.assertEqual(count, 1, name)
        self.finalizer.write_text(text, encoding="utf-8")
        self.finalizer.chmod(0o755)

    def run_finalizer(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(BASH), "--noprofile", "--norc", "-p", bash_path(self.finalizer)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )

    def test_complete_policy_emits_decky_contract_and_client_hdr(self) -> None:
        result = self.run_finalizer()
        self.assertEqual(result.returncode, 0, result.stderr)
        exports = parse_emitted_exports(result.stdout)
        self.assertEqual(exports["ARMADA_HDR_CAPABLE"], "1")
        self.assertEqual(exports["GAMESCOPE_HDR_ITM_TARGET_NITS"], "650")
        self.assertEqual(exports["GAMESCOPE_ARMADA_HDR_MAX_CLL"], "650")
        self.assertEqual(exports["ENABLE_GAMESCOPE_WSI"], "1")
        self.assertEqual(exports["ENABLE_HDR_WSI"], "1")
        self.assertEqual(exports["DXVK_HDR"], "1")
        self.assertEqual(exports["gamescope_hdr_enabled"], "false")
        self.assertNotIn("ENABLE_GAMESCOPE_HDR", exports)

    def test_wrong_connector_and_incomplete_artifact_fail_closed(self) -> None:
        self._write_device_env("DSI-2")
        result = self.run_finalizer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(parse_emitted_exports(result.stdout)["ARMADA_HDR_CAPABLE"], "0")
        self.assertNotIn("DXVK_HDR", parse_emitted_exports(result.stdout))

        self._write_device_env("DSI-1")
        self.marker.unlink()
        result = self.run_finalizer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(parse_emitted_exports(result.stdout)["ARMADA_HDR_CAPABLE"], "0")

    def test_other_hardware_is_untouched(self) -> None:
        self.model.write_bytes(b"AYN Odin 2\0")
        result = self.run_finalizer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")


@unittest.skipUnless(BASH, "requires GNU Bash")
class GamescopePackageValidatorIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.gamescope = self.root / "gamescope"
        self.marker = self.root / "gamescope-hdr-capabilities"
        self.rpm_query = self.root / "rpm"
        self.execution_sentinel = self.root / "gamescope-was-executed"
        self._write_gamescope(with_option=True)
        self._write_rpm_query(provides_feature=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_gamescope(self, *, with_option: bool) -> None:
        option = "--expose-client-sampleable-formats" if with_option else "--unrelated-option"
        self.gamescope.write_text(
            "#!/bin/bash\n"
            f"touch {shlex.quote(bash_path(self.execution_sentinel))}\n"
            f"# compiled payload: {option}\n",
            encoding="utf-8",
        )
        self.gamescope.chmod(0o644)

    def _write_rpm_query(self, *, provides_feature: bool) -> None:
        exit_code = 0 if provides_feature else 1
        self.rpm_query.write_text(
            "#!/bin/bash\n"
            "[[ \"$#\" == 3 ]] || exit 97\n"
            "[[ \"$1\" == -q ]] || exit 98\n"
            "[[ \"$2\" == --whatprovides ]] || exit 99\n"
            "[[ \"$3\" == armada-gamescope-expose-client-sampleable-formats ]] || exit 96\n"
            f"exit {exit_code}\n",
            encoding="utf-8",
        )
        self.rpm_query.chmod(0o755)

    def run_validator(self) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.update(
            {
                "ARMADA_GAMESCOPE_VALIDATOR_BINARY": bash_path(self.gamescope),
                "ARMADA_GAMESCOPE_VALIDATOR_RPM": bash_path(self.rpm_query),
                "ARMADA_GAMESCOPE_VALIDATOR_MARKER": bash_path(self.marker),
            }
        )
        return subprocess.run(
            [str(BASH), "--noprofile", "--norc", bash_path(VALIDATE_GAMESCOPE)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            env=environment,
        )

    def assert_validation_failed_without_marker(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.marker.exists())
        self.assertFalse(self.execution_sentinel.exists())

    def write_stale_marker(self) -> None:
        self.marker.write_text("stale-capability\n", encoding="utf-8")

    def test_non_executable_gamescope_validates_without_execution(self) -> None:
        self.assertFalse(bool(self.gamescope.stat().st_mode & 0o111))
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.marker.read_text(encoding="utf-8"),
            "expose-client-sampleable-formats-v1\n",
        )
        if os.name != "nt":
            self.assertEqual(self.marker.stat().st_mode & 0o777, 0o644)
        self.assertFalse(self.execution_sentinel.exists())

    def test_missing_rpm_provide_fails_without_marker(self) -> None:
        self._write_rpm_query(provides_feature=False)
        self.write_stale_marker()
        self.assert_validation_failed_without_marker(self.run_validator())

    def test_missing_option_literal_fails_without_marker(self) -> None:
        self._write_gamescope(with_option=False)
        self.write_stale_marker()
        self.assert_validation_failed_without_marker(self.run_validator())

    def test_gamescope_symlink_is_refused_without_marker(self) -> None:
        if os.name == "nt":
            self.skipTest("Git-for-Windows does not preserve POSIX symlink tests")
        target = self.root / "gamescope-target"
        self.gamescope.replace(target)
        try:
            self.gamescope.symlink_to(target)
        except OSError as error:
            self.skipTest(f"symlinks unavailable: {error}")
        self.write_stale_marker()
        self.assert_validation_failed_without_marker(self.run_validator())


if __name__ == "__main__":
    unittest.main()
