#!/usr/bin/env python3
"""Off-device production-policy tests for the Odin 3 audio profiles."""

from __future__ import annotations

import hashlib
import math
import os
import re
import shutil
import stat
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYSTEM = ROOT / "system_files"
PACKAGE = SYSTEM / "usr/share/armada/audio/odin3"
PIPEWIRE = PACKAGE / "pipewire.conf.d"
PULSE = PACKAGE / "pipewire-pulse.conf.d"
WIREPLUMBER = PACKAGE / "wireplumber.conf.d"
HRIR = PACKAGE / "hrir/vss_speaker.wav"
IMMUTABLE_HRIR = "/usr/share/armada/audio/odin3/hrir/vss_speaker.wav"
ROUTE_HOOK = (
    SYSTEM / "usr/share/wireplumber/scripts/odin3-speaker-route-unity.lua"
)
SETUP = SYSTEM / "usr/libexec/armada/odin3-audio-setup"
DEFAULT = SYSTEM / "usr/libexec/armada/odin3-audio-default"
STEAM_RESTORE = SYSTEM / "usr/libexec/armada/odin3-audio-steam-restore"
HOTPLUG = SYSTEM / "usr/libexec/armada/odin3-audio-hotplug"
LAUNCH_STEAM = SYSTEM / "usr/libexec/armada/launch-steam"
SETUP_UNIT = (
    SYSTEM / "usr/lib/systemd/system/armada-odin3-audio-setup.service"
)
DEFAULT_UNIT = (
    SYSTEM / "usr/lib/systemd/user/armada-odin3-audio-default.service"
)
STEAM_RESTORE_UNIT = (
    SYSTEM / "usr/lib/systemd/user/armada-odin3-audio-steam-restore.service"
)
RESUME_PATH_UNIT = (
    SYSTEM / "usr/lib/systemd/user/armada-odin3-audio-resume.path"
)
RESUME_SERVICE_UNIT = (
    SYSTEM / "usr/lib/systemd/user/armada-odin3-audio-resume.service"
)
RESUME_HELPER = SYSTEM / "usr/libexec/armada/odin3-audio-resume"
RESUME_HOOK = (
    SYSTEM / "usr/lib/systemd/system-sleep/60-armada-odin3-audio-resume"
)
HOTPLUG_UNIT = (
    SYSTEM / "usr/lib/systemd/user/armada-odin3-audio-hotplug.service"
)
VENDOR_FILES = ROOT / "build_files/40-vendor-system-files.sh"

EXPECTED_FRAGMENTS = {
    PIPEWIRE / "50-hrir-7_1.conf",
    PIPEWIRE / "55-odin3-stereo.conf",
    PULSE / "10-no-flat.conf",
    PULSE / "20-odin3-stereo-downmix.conf",
    WIREPLUMBER / "51-odin3-audio-names.conf",
    WIREPLUMBER / "90-odin3-speaker-route-unity.conf",
}
BASE_GAIN = 0.295248
CLAMP = 0.8912509381
HRIR_SHA256 = "f88ee26f5af80e73365ea1428cea970eeb383c8dfaa1fb77b0fc5a1efb48a7cb"
POSITIONS = ("FL", "FR", "RL", "RR", "FC", "LFE", "SL", "SR")


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def numbers(source: str) -> list[float]:
    return [
        float(value)
        for value in re.findall(r"(?<![\w.])-?(?:\d+\.\d+|\d+)(?![\w.])", source)
    ]


def riff_metadata(path: Path) -> dict[str, int]:
    raw = path.read_bytes()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise AssertionError("HRIR is not a RIFF/WAVE file")
    chunks: dict[bytes, bytes] = {}
    offset = 12
    while offset + 8 <= len(raw):
        chunk_id = raw[offset : offset + 4]
        size = struct.unpack_from("<I", raw, offset + 4)[0]
        start = offset + 8
        end = start + size
        if end > len(raw):
            raise AssertionError(f"truncated HRIR chunk {chunk_id!r}")
        chunks[chunk_id] = raw[start:end]
        offset = end + (size & 1)
    if b"fmt " not in chunks or b"data" not in chunks:
        raise AssertionError("HRIR lacks fmt or data")
    format_tag, channels, rate, _, block_align, bits = struct.unpack_from(
        "<HHIIHH", chunks[b"fmt "]
    )
    return {
        "format_tag": format_tag,
        "channels": channels,
        "rate": rate,
        "bits": bits,
        "frames": len(chunks[b"data"]) // block_align,
    }


class ArtifactContractTests(unittest.TestCase):
    def test_exact_packaged_artifacts_exist(self) -> None:
        self.assertEqual(
            {
                path
                for directory in (PIPEWIRE, PULSE, WIREPLUMBER)
                for path in directory.glob("*.conf")
            },
            EXPECTED_FRAGMENTS,
        )
        for path in (
            *EXPECTED_FRAGMENTS,
            ROUTE_HOOK,
            SETUP,
            DEFAULT,
            STEAM_RESTORE,
            HOTPLUG,
            RESUME_HELPER,
            SETUP_UNIT,
            DEFAULT_UNIT,
            STEAM_RESTORE_UNIT,
            HOTPLUG_UNIT,
            RESUME_PATH_UNIT,
            RESUME_SERVICE_UNIT,
            RESUME_HOOK,
        ):
            self.assertTrue(path.is_file(), path.relative_to(ROOT))

    @unittest.skipUnless(os.name != "nt", "POSIX executable modes are not exposed on Windows")
    def test_installed_helpers_are_executable(self) -> None:
        for path in (SETUP, DEFAULT, STEAM_RESTORE, HOTPLUG):
            self.assertTrue(
                path.stat().st_mode & stat.S_IXUSR,
                f"{path.relative_to(ROOT)} must be executable",
            )

    def test_setup_and_units_install_only_on_odin3(self) -> None:
        setup = text(SETUP)
        setup_unit = text(SETUP_UNIT)
        default_unit = text(DEFAULT_UNIT)

        self.assertIn("/usr/libexec/armada/device-env", setup)
        self.assertRegex(
            setup,
            r'ARMADA_DEVICE_ID[^=\n]*"?\s*==\s*"?ayn-odin-3',
        )
        self.assertIn("/usr/share/armada/audio/odin3", setup)
        for directory in (
            "pipewire/pipewire.conf.d",
            "pipewire/pipewire-pulse.conf.d",
            "wireplumber/wireplumber.conf.d",
        ):
            self.assertIn(directory, setup)
        self.assertRegex(setup, r"\bln\b.*-[^ \n]*s")
        self.assertRegex(setup.lower(), r"backup|\.bak")
        self.assertNotRegex(setup, r"rm\s+-rf")

        self.assertIn("/usr/libexec/armada/odin3-audio-setup", setup_unit)
        self.assertRegex(setup_unit, r"(?m)^Before=.*display-manager")
        self.assertIn("/usr/libexec/armada/odin3-audio-default", default_unit)
        self.assertRegex(default_unit, r"(?m)^After=.*(pipewire|wireplumber)")

        vendor = text(VENDOR_FILES)
        self.assertIn("systemctl enable armada-odin3-audio-setup.service", vendor)
        self.assertIn(
            "systemctl --global enable armada-odin3-audio-default.service",
            vendor,
        )
        self.assertIn(
            "test -x /usr/libexec/armada/odin3-audio-steam-restore",
            vendor,
        )
        self.assertIn(
            "test -f /usr/lib/systemd/user/armada-odin3-audio-steam-restore.service",
            vendor,
        )
        self.assertIn(
            "test -f /usr/lib/systemd/user/armada-odin3-audio-resume.path",
            vendor,
        )
        self.assertIn(
            "test -f /usr/lib/systemd/user/armada-odin3-audio-resume.service",
            vendor,
        )
        self.assertIn(
            "test -x /usr/libexec/armada/odin3-audio-resume", vendor
        )
        self.assertIn(
            "test -x /usr/libexec/armada/odin3-audio-hotplug",
            vendor,
        )
        self.assertIn(
            "test -f /usr/lib/systemd/user/armada-odin3-audio-hotplug.service",
            vendor,
        )
        self.assertIn(
            "systemctl --global enable armada-odin3-audio-hotplug.service",
            vendor,
        )
        self.assertIn(
            "systemctl --global enable armada-odin3-audio-resume.path",
            vendor,
        )
        self.assertIn(
            "chmod 0755 /usr/lib/systemd/system-sleep/60-armada-odin3-audio-resume",
            vendor,
        )

    def test_managed_link_names_are_complete(self) -> None:
        setup = text(SETUP)
        for fragment in EXPECTED_FRAGMENTS:
            self.assertIn(fragment.name, setup)

    def test_steam_restore_is_bounded_exact_and_launch_triggered(self) -> None:
        helper = text(STEAM_RESTORE)
        unit = text(STEAM_RESTORE_UNIT)
        launcher = text(LAUNCH_STEAM)

        for token in (
            "ayn-odin-3",
            "AYN Odin 3",
            "SM8750",
            "pactl",
            "get-default-sink",
            '"--format=json", "list", "sinks"',
            'VIRTUAL_SINK = "Virtual Surround Sound"',
            'STEREO_SINK = "Stereo"',
            "http://127.0.0.1:8080/json",
            'target.get("title") != "SharedJSContext"',
            'page.hostname == "steamloopback.host"',
            'websocket_endpoint.hostname == "127.0.0.1"',
            "websocket_endpoint.port == 8080",
            'websocket_endpoint.path.startswith("/devtools/page/")',
            "SteamClient.System.Audio",
            "audio.GetDevices()",
            'device.sName === requested.name',
            "audio.SetDefaultDeviceOverride(id, 1)",
            "after.overrideOutputDeviceId === id",
            "after.activeOutputDeviceId === id",
            "virtualOffset",
            "stereoOffset",
            "SELECT_EXPRESSION",
            'SELECT_EXPRESSION.replace("__SELECTION__", payload)',
            "ensure_ascii=True",
            '"awaitPromise": True',
        ):
            self.assertIn(token, helper)
        self.assertNotIn("set-default-sink", helper)
        self.assertNotIn("ClearDefaultDeviceOverride", helper)
        self.assertNotIn('f"""', helper)
        self.assertRegex(helper, r"WAIT_ATTEMPTS\s*=\s*[1-9]\d*")
        self.assertRegex(helper, r"WEBSOCKET_TIMEOUT\s*=\s*[0-9.]+")
        self.assertLess(
            helper.index("target = find_shared_context()"),
            helper.index("selection = selected_sink()"),
            "Steam readiness must precede the final default-sink decision",
        )
        self.assertRegex(
            helper,
            r"return 0 if update_steam_override\(target, selection\) else 1",
        )

        self.assertRegex(unit, r"(?m)^Type=oneshot$")
        self.assertRegex(unit, r"(?m)^After=.*pipewire.*wireplumber")
        self.assertIn(
            "ExecStart=/usr/libexec/armada/odin3-audio-steam-restore",
            unit,
        )
        self.assertRegex(unit, r"(?m)^TimeoutStartSec=\d+s$")
        self.assertRegex(unit, r"(?m)^Restart=on-failure$")
        self.assertRegex(unit, r"(?m)^StartLimitBurst=[1-9]\d*$")
        self.assertNotIn("[Install]", unit)

        resume_path = text(RESUME_PATH_UNIT)
        resume_service = text(RESUME_SERVICE_UNIT)
        resume_helper = text(RESUME_HELPER)
        resume_hook = text(RESUME_HOOK)
        self.assertIn(
            "PathExists=%t/armada-odin3-audio-resume-trigger", resume_path
        )
        self.assertNotIn("PathChanged=", resume_path)
        self.assertIn(
            "Unit=armada-odin3-audio-resume.service", resume_path
        )
        self.assertNotIn("steam-restore", resume_path)
        self.assertRegex(resume_path, r"(?m)^WantedBy=default.target$")
        self.assertRegex(resume_service, r"(?m)^Type=oneshot$")
        self.assertIn(
            "ExecStart=/usr/libexec/armada/odin3-audio-resume",
            resume_service,
        )
        self.assertNotIn("steam-restore", resume_service)
        self.assertIn("armada-odin3-audio-resume-trigger", resume_helper)
        self.assertIn("armada-odin3-audio-resume", resume_helper)
        self.assertIn('mv -fT "$trigger" "$pending"', resume_helper)
        self.assertIn("--user --no-block restart", resume_helper)
        self.assertIn("armada-odin3-audio-hotplug.service", resume_helper)
        self.assertLess(
            resume_helper.index('mv -fT "$trigger" "$pending"'),
            resume_helper.index("--user --no-block restart"),
        )
        self.assertIn("odin3-audio-active-output", resume_hook)
        self.assertIn("odin3-audio-resume-trigger", resume_hook)
        self.assertNotIn("odin3-audio-speaker-default", resume_hook)
        for value in ("ayn-odin-3", "AYN Odin 3", "SM8750"):
            self.assertIn(value, resume_hook)
        self.assertIn('choice="$pending_choice"', resume_hook)
        self.assertIn("case \"${1:-}\"", resume_hook)
        self.assertIn("pre)", resume_hook)
        self.assertIn("post)", resume_hook)
        self.assertIn("mv -fT", resume_hook)
        self.assertIn('rm -f "$snapshot"', resume_hook)
        self.assertIn('rm -f "$resume_marker"', resume_hook)

        trigger = (
            "systemctl --user --no-block restart "
            "armada-odin3-audio-steam-restore.service || true"
        )
        self.assertIn(trigger, launcher)
        self.assertLess(launcher.index(trigger), launcher.index('exec "${steam_arm}"'))


class AudioGraphPolicyTests(unittest.TestCase):
    def test_two_public_profiles_and_hidden_physical_sink(self) -> None:
        graphs = text(PIPEWIRE / "50-hrir-7_1.conf") + text(
            PIPEWIRE / "55-odin3-stereo.conf"
        )
        names = text(WIREPLUMBER / "51-odin3-audio-names.conf")

        for public_name in ("Stereo", "Virtual Surround Sound"):
            self.assertIn(public_name, graphs + names)
        self.assertEqual(
            len(re.findall(r"media\.class\s*=\s*[\"']?Audio/Sink[\"']?", graphs)),
            2,
        )
        self.assertGreaterEqual(len(re.findall(r"node\.virtual\s*=\s*true", graphs)), 2)

        self.assertIn("alsa_output.platform-sound.HiFi__Speaker__sink", names)
        self.assertTrue(
            re.search(r"node\.hidden\s*=\s*true", names)
            or "Audio/Sink/Internal" in names
        )
        self.assertIn("Audio/Sink/Internal", names)

    def test_default_priorities_prefer_stereo(self) -> None:
        stereo = text(PIPEWIRE / "55-odin3-stereo.conf")
        surround = text(PIPEWIRE / "50-hrir-7_1.conf")
        priority_pattern = r"priority\.(?:session|driver)\s*=\s*(\d+)"
        stereo_priorities = [int(n) for n in re.findall(priority_pattern, stereo)]
        surround_priorities = [int(n) for n in re.findall(priority_pattern, surround)]
        self.assertTrue(stereo_priorities, "Stereo has no explicit priority")
        self.assertTrue(surround_priorities, "Virtual Surround has no explicit priority")
        self.assertGreater(max(stereo_priorities), max(surround_priorities))

        default = text(DEFAULT)
        self.assertIn("Stereo", default)
        self.assertIn("Virtual Surround Sound", default)
        self.assertRegex(default.lower(), r"marker|initialized|first")

    def test_all_eight_channel_paths_and_hrir_convolution_are_declared(self) -> None:
        surround = text(PIPEWIRE / "50-hrir-7_1.conf")
        for position in POSITIONS:
            self.assertRegex(
                surround,
                rf"(?<![A-Z]){re.escape(position)}(?![A-Z])",
                position,
            )
        self.assertRegex(
            surround,
            r"audio\.channels\s*=\s*8|audio\.position\s*=\s*\[\s*FL\s+FR\s+"
            r"(?:RL\s+RR\s+FC\s+LFE\s+SL\s+SR|FC\s+LFE\s+RL\s+RR\s+SL\s+SR)",
        )
        self.assertGreaterEqual(len(re.findall(r"label\s*=\s*convolver", surround)), 8)
        self.assertEqual(len(re.findall(re.escape(IMMUTABLE_HRIR), surround)), 16)
        self.assertEqual(
            len(
                re.findall(
                    re.escape(IMMUTABLE_HRIR),
                    text(PIPEWIRE / "55-odin3-stereo.conf"),
                )
            ),
            4,
        )
        for graph in PIPEWIRE.glob("*.conf"):
            self.assertNotIn(
                "/var/home/armada/.local/share/armada/odin3-audio/hrir.wav",
                text(graph),
            )
        for graph in PIPEWIRE.glob("*.conf"):
            source = text(graph)
            self.assertEqual(
                len(re.findall(r"label\s*=\s*convolver", source)),
                len(re.findall(r"resample_quality\s*=\s*15", source)),
                f"{graph.name} must declare the selected resampling quality",
            )
        self.assertGreaterEqual(len(re.findall(r"label\s*=\s*clamp", surround)), 2)
        for position in POSITIONS:
            for ear in ("L", "R"):
                self.assertRegex(
                    surround,
                    rf'output\s*=\s*"copy{position}:Out"\s+'
                    rf'input\s*=\s*"conv{position}_{ear}:In"',
                    f"{position} has no path to {ear}",
                )
                self.assertRegex(
                    surround,
                    rf'output\s*=\s*"conv{position}_{ear}:Out"\s+'
                    rf'input\s*=\s*"mix{ear}:In [1-8]"',
                    f"{position} {ear} does not reach the final mixer",
                )
        expected_indices = {
            "FL_L": 0,
            "FL_R": 1,
            "SL_L": 2,
            "SL_R": 3,
            "RL_L": 4,
            "RL_R": 5,
            "FC_L": 6,
            "FR_R": 7,
            "FR_L": 8,
            "SR_R": 9,
            "SR_L": 10,
            "RR_R": 11,
            "RR_L": 12,
            "FC_R": 13,
            "LFE_L": 6,
            "LFE_R": 13,
        }
        actual_indices = {
            name: int(index)
            for name, index in re.findall(
                r"name\s*=\s*conv([A-Z]+_[LR]).*?"
                r"filename\s*=\s*\"[^\"]+\"\s+channel\s*=\s*(\d+)",
                surround,
            )
        }
        self.assertEqual(actual_indices, expected_indices)

    def test_downmix_consumes_center_surround_and_lfe(self) -> None:
        pulse = text(PULSE / "20-odin3-stereo-downmix.conf")
        stereo = text(PIPEWIRE / "55-odin3-stereo.conf")
        surround = text(PIPEWIRE / "50-hrir-7_1.conf")
        documentation = text(ROOT / "docs/odin3-audio/README.md")
        self.assertNotRegex(
            pulse,
            r"(?:stream\.rules|channelmix\.)\s*",
            "the compatibility fragment must not modify external channel mixing",
        )
        self.assertRegex(pulse, r"stream\.properties\s*=\s*\{\s*\}")
        self.assertRegex(stereo, r"audio\.channels\s*=\s*8")
        self.assertRegex(
            stereo,
            r"audio\.position\s*=\s*\[\s*FL\s+FR\s+FC\s+LFE\s+RL\s+RR\s+SL\s+SR\s*\]",
        )
        self.assertIn("downmix inside its own", documentation)
        self.assertIn("external sinks retain their own", documentation)
        expected_links = {
            "FL": ("downmixL", 1),
            "FC_L": ("downmixL", 2),
            "LFE_L": ("downmixL", 3),
            "RL": ("downmixL", 4),
            "SL": ("downmixL", 5),
            "FR": ("downmixR", 1),
            "FC_R": ("downmixR", 2),
            "LFE_R": ("downmixR", 3),
            "RR": ("downmixR", 4),
            "SR": ("downmixR", 5),
        }
        source_positions = {
            "FC_L": "FC",
            "LFE_L": "LFE",
            "FC_R": "FC",
            "LFE_R": "LFE",
        }
        for key, (mixer, port) in expected_links.items():
            position = source_positions.get(key, key)
            self.assertRegex(
                stereo,
                rf'output\s*=\s*"copy{position}:Out"\s+'
                rf'input\s*=\s*"{mixer}:In {port}"',
            )
        for mixer, expected in (
            ("downmixL", (1.0, 0.707106781, 0.353553391, 0.707106781, 0.707106781)),
            ("downmixR", (1.0, 0.707106781, 0.353553391, 0.707106781, 0.707106781)),
        ):
            block = re.search(
                rf"name\s*=\s*{mixer}\s+control\s*=\s*\{{(?P<body>.*?)\}}",
                stereo,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(block, f"{mixer} is missing")
            for index, coefficient in enumerate(expected, start=1):
                self.assertRegex(
                    block.group("body"),
                    rf'"Gain {index}"\s*=\s*{re.escape(str(coefficient))}',
                )
        for position in ("FC", "LFE", "RL", "RR", "SL", "SR"):
            self.assertRegex(stereo + surround, rf"(?<![A-Z]){position}(?![A-Z])")

    def test_gain_ratios_and_final_clamps_are_exact(self) -> None:
        graphs = "\n".join(text(path) for path in sorted(PIPEWIRE.glob("*.conf")))
        values = numbers(graphs)
        self.assertTrue(any(math.isclose(v, BASE_GAIN, abs_tol=5e-7) for v in values))

        for ratio in (1.0, 0.9, 0.8, 1.2):
            expected = BASE_GAIN * ratio
            self.assertTrue(
                any(math.isclose(v, expected, abs_tol=7e-7) for v in values),
                f"missing {ratio:g}x gain {expected:.7f}",
            )
        self.assertGreaterEqual(
            sum(math.isclose(abs(v), CLAMP, abs_tol=1e-10) for v in values),
            4,
            "both graphs must clamp both final outputs to +/-0.8912509381",
        )
        for graph in PIPEWIRE.glob("*.conf"):
            source = text(graph)
            for ear in ("L", "R"):
                self.assertRegex(
                    source,
                    rf'output\s*=\s*"mix{ear}:Out"\s+'
                    rf'input\s*=\s*"clamp{ear}:In"',
                )
            self.assertRegex(
                source,
                r'outputs\s*=\s*\[\s*"clampL:Out"\s+"clampR:Out"\s*\]',
            )

        loud = 1.0
        quiet = 0.25
        perceived_interval_gain = math.exp(
            math.log(quiet) + 0.12 * (math.log(loud) - math.log(quiet))
        )
        self.assertTrue(
            math.isclose(BASE_GAIN, perceived_interval_gain, abs_tol=5e-7)
        )

    def test_route_unity_hook_targets_only_the_internal_speaker(self) -> None:
        fragment = text(WIREPLUMBER / "90-odin3-speaker-route-unity.conf")
        hook = text(ROUTE_HOOK)
        combined = fragment + hook
        for token in (
            "odin3-speaker-route-unity",
            "alsa_card.platform-sound",
            "[Out] Speaker",
        ):
            self.assertIn(token, combined)
        self.assertRegex(hook, r"(?i)mute")
        self.assertRegex(hook, r"(?i)volume")
        self.assertRegex(hook, r"(?i)save")
        self.assertRegex(hook, r"(?<![\d.])1(?:\.0+)?(?![\d.])")


class HrirTests(unittest.TestCase):
    def test_hrir_metadata_and_checksum(self) -> None:
        self.assertTrue(HRIR.is_file(), "packaged HRIR asset is missing")
        self.assertEqual(
            riff_metadata(HRIR),
            {
                "format_tag": 3,
                "channels": 14,
                "rate": 48000,
                "bits": 32,
                "frames": 8400,
            },
        )

        digest = hashlib.sha256(HRIR.read_bytes()).hexdigest()
        self.assertEqual(digest, HRIR_SHA256)
        self.assertEqual(list(HRIR.parent.glob("*.wav")), [HRIR])
        self.assertEqual(
            {path.name for path in HRIR.parent.iterdir()},
            {"vss_speaker.wav"},
        )

    def test_single_immutable_hrir_contract_is_documented_and_enforced(self) -> None:
        setup = text(SETUP)
        documentation = text(ROOT / "docs/odin3-audio/README.md")
        for token in (
            "${TEMPLATE_ROOT}/hrir/vss_speaker.wav",
            "PACKAGED_HRIR",
            HRIR_SHA256,
            "/usr/bin/sha256sum",
            "immutable HRIR checksum mismatch",
        ):
            self.assertIn(token, setup)
        self.assertNotIn("HRIR_DIR", setup)
        self.assertNotIn("HRIR_PATH", setup)
        self.assertNotIn("seed_hrir", setup)
        self.assertIn(IMMUTABLE_HRIR, documentation)
        self.assertIn("There is no fallback HRIR", documentation)


class SetupIntegrationTests(unittest.TestCase):
    def test_non_odin_gate_precedes_mutating_commands(self) -> None:
        """The exact gate must run before link, backup, or service mutations."""
        setup = text(SETUP)
        gate = setup.find("ayn-odin-3")
        self.assertGreaterEqual(gate, 0)
        mutation_offsets = [
            offset
            for token in ("ln ", "ln\t", "mv ", "cp ", "systemctl")
            if (offset := setup.find(token)) >= 0
        ]
        self.assertTrue(mutation_offsets)
        self.assertLess(gate, min(mutation_offsets))

    @unittest.skipUnless(
        os.name != "nt" and shutil.which("bash"),
        "requires GNU Bash with native POSIX symlinks",
    )
    def test_mock_non_odin_is_noop_and_odin_links_backup_restore(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            home = fixture / "home"
            home.mkdir()
            device_env = fixture / "device-env"
            target_rel = Path(
                ".config/pipewire/pipewire.conf.d/50-hrir-7_1.conf"
            )
            target = home / target_rel
            target.parent.mkdir(parents=True)
            target.write_text("user-owned\n", encoding="utf-8")

            def write_policy(device_id: str, name: str, soc: str) -> None:
                device_env.write_text(
                    "#!/bin/bash\n"
                    f"printf '%s\\n' 'ARMADA_DEVICE_ID={device_id}'\n"
                    f"printf '%s\\n' 'ARMADA_DEVICE_NAME={name}'\n"
                    f"printf '%s\\n' 'ARMADA_SOC_CLASS={soc}'\n",
                    encoding="utf-8",
                )
                device_env.chmod(0o755)

            environment = os.environ.copy()
            environment.update(
                {
                    "ARMADA_AUDIO_DEVICE_ENV": str(device_env),
                    "ARMADA_AUDIO_TEMPLATE_ROOT": str(PACKAGE),
                    "ARMADA_AUDIO_USER_HOME": str(home),
                    "ARMADA_AUDIO_STATE_DIR": str(home / ".local/state/armada"),
                    "ARMADA_AUDIO_USER": str(os.getuid()),
                    "ARMADA_AUDIO_GROUP": str(os.getgid()),
                }
            )

            write_policy("ayn-odin-2", "AYN Odin 2", "SM8550")
            before = {
                path.relative_to(home): (
                    path.is_symlink(),
                    path.read_bytes() if path.is_file() and not path.is_symlink() else b"",
                )
                for path in home.rglob("*")
            }
            result = subprocess.run(
                [shutil.which("bash") or "bash", str(SETUP)],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            after = {
                path.relative_to(home): (
                    path.is_symlink(),
                    path.read_bytes() if path.is_file() and not path.is_symlink() else b"",
                )
                for path in home.rglob("*")
            }
            self.assertEqual(after, before)

            # Pre-create every managed parent and saved-state directory so this
            # unprivileged fixture never needs the production chown path.
            for fragment in EXPECTED_FRAGMENTS:
                if fragment.parent == PIPEWIRE:
                    relative = Path(".config/pipewire/pipewire.conf.d") / fragment.name
                elif fragment.parent == PULSE:
                    relative = (
                        Path(".config/pipewire/pipewire-pulse.conf.d") / fragment.name
                    )
                else:
                    relative = (
                        Path(".config/wireplumber/wireplumber.conf.d") / fragment.name
                    )
                (home / relative).parent.mkdir(parents=True, exist_ok=True)
            (home / ".config/pulse").mkdir(parents=True)

            write_policy("ayn-odin-3", "AYN Odin 3", "SM8750")
            result = subprocess.run(
                [shutil.which("bash") or "bash", str(SETUP)],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(target.is_symlink())
            backup = target.with_name(target.name + ".armada-odin3-audio.backup")
            self.assertEqual(backup.read_text(encoding="utf-8"), "user-owned\n")

            # If a later image no longer identifies this as an Odin 3, remove
            # only the package-managed links and restore the original files.
            write_policy("ayn-odin-2", "AYN Odin 2", "SM8550")
            result = subprocess.run(
                [shutil.which("bash") or "bash", str(SETUP)],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(target.is_symlink())
            self.assertEqual(target.read_text(encoding="utf-8"), "user-owned\n")
            for link in home.rglob("*.conf"):
                self.assertFalse(link.is_symlink(), link)

            # Explicit rollback remains independently reversible.
            write_policy("ayn-odin-3", "AYN Odin 3", "SM8750")
            result = subprocess.run(
                [shutil.which("bash") or "bash", str(SETUP)],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(target.is_symlink())

            result = subprocess.run(
                [shutil.which("bash") or "bash", str(SETUP), "--restore"],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(target.is_symlink())
            self.assertEqual(target.read_text(encoding="utf-8"), "user-owned\n")

    @unittest.skipUnless(
        os.name != "nt" and shutil.which("bash"),
        "requires GNU Bash on a POSIX filesystem",
    )
    def test_mock_default_initializes_once_and_preserves_later_choice(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary)
            home = fixture / "home"
            state = home / ".local/state/armada"
            state.mkdir(parents=True)
            device_env = fixture / "device-env"
            device_env.write_text(
                "#!/bin/bash\n"
                "printf '%s\\n' 'ARMADA_DEVICE_ID=ayn-odin-3'\n"
                "printf '%s\\n' 'ARMADA_DEVICE_NAME=AYN Odin 3'\n"
                "printf '%s\\n' 'ARMADA_SOC_CLASS=SM8750'\n",
                encoding="utf-8",
            )
            device_env.chmod(0o755)
            calls = fixture / "pactl.calls"
            pactl = fixture / "pactl"
            pactl.write_text(
                "#!/bin/bash\n"
                "if [[ \"$*\" == 'list short sinks' ]]; then\n"
                "  printf '1\\tStereo\\tmodule\\n'\n"
                "  printf '2\\tVirtual Surround Sound\\tmodule\\n'\n"
                "  exit 0\n"
                "fi\n"
                "printf '%s\\n' \"$*\" >>\"$MOCK_PACTL_CALLS\"\n",
                encoding="utf-8",
            )
            pactl.chmod(0o755)

            environment = os.environ.copy()
            environment.update(
                {
                    "ARMADA_AUDIO_DEVICE_ENV": str(device_env),
                    "ARMADA_AUDIO_USER_HOME": str(home),
                    "ARMADA_AUDIO_STATE_DIR": str(state),
                    "ARMADA_AUDIO_PACTL": str(pactl),
                    "ARMADA_AUDIO_SLEEP": "/bin/true",
                    "ARMADA_AUDIO_WAIT_ATTEMPTS": "1",
                    "ARMADA_AUDIO_WAIT_SECONDS": "0",
                    "MOCK_PACTL_CALLS": str(calls),
                }
            )

            # Without setup's pending marker, the helper must not infer
            # permission to alter an existing default.
            result = subprocess.run(
                [shutil.which("bash") or "bash", str(DEFAULT)],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(calls.exists())

            pending = state / "odin3-audio-default.pending"
            done = state / "odin3-audio-default.done"
            pending.touch()
            result = subprocess.run(
                [shutil.which("bash") or "bash", str(DEFAULT)],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                calls.read_text(encoding="utf-8").splitlines(),
                [
                    "set-sink-volume Stereo 100%",
                    "set-sink-volume Virtual Surround Sound 100%",
                    "set-default-sink Stereo",
                ],
            )
            self.assertTrue(done.is_file())
            self.assertFalse(pending.exists())

            calls.unlink()
            result = subprocess.run(
                [shutil.which("bash") or "bash", str(DEFAULT)],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(calls.exists())


if __name__ == "__main__":
    unittest.main()
