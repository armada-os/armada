#!/usr/bin/env python3
"""Isolated policy tests for the Odin 3 external-audio router."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "system_files/usr/libexec/armada/odin3-audio-hotplug"
UNIT = (
    ROOT
    / "system_files/usr/lib/systemd/user/armada-odin3-audio-hotplug.service"
)
loader = importlib.machinery.SourceFileLoader("odin3_audio_hotplug", str(HELPER))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
hotplug = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = hotplug
loader.exec_module(hotplug)


def sink(name: str, serial: int, **properties: str) -> dict:
    values = {"object.serial": str(serial), **properties}
    return {"name": name, "index": serial, "properties": values}


BT_ONE = sink(
    "bluez_output.AA_BB_CC_DD_EE_FF.1",
    100,
    **{"device.api": "bluez5"},
)
BT_TWO = sink(
    "bluez_output.11_22_33_44_55_66.1",
    200,
    **{"device.bus": "bluetooth"},
)
HEADPHONES = sink(hotplug.HEADPHONE_SINK, 150)


class FakePactl:
    def __init__(self, snapshots: list) -> None:
        self.snapshots = snapshots
        self.commands: list[tuple[str, ...]] = []
        self.default = ""

    def snapshot(self):
        current = self.snapshots.pop(0)
        self.default = current.default
        return current

    def run(self, *arguments: str, check: bool = True):
        self.commands.append(arguments)
        if arguments[:1] == ("set-default-sink",):
            self.default = arguments[1]
        output = f"{self.default}\n" if arguments == ("get-default-sink",) else ""
        return mock.Mock(stdout=output)


class FailFirstDefaultPactl(FakePactl):
    def __init__(self, snapshots: list) -> None:
        super().__init__(snapshots)
        self.failed = False

    def run(self, *arguments: str, check: bool = True):
        if arguments and arguments[0] == "set-default-sink" and not self.failed:
            self.commands.append(arguments)
            self.failed = True
            raise subprocess.CalledProcessError(1, arguments)
        return super().run(*arguments, check=check)


class FakeChoice:
    def __init__(self, value: str | None = None) -> None:
        self.value = value
        self.saved: list[str] = []

    def load_valid(self) -> str | None:
        return self.value if self.value in hotplug.INTERNAL_SINKS else None

    def load(self) -> str:
        return self.load_valid() or "Stereo"

    def save(self, value: str) -> None:
        self.value = value
        self.saved.append(value)


class FakeRuntime:
    def __init__(self, pending: str | None = None) -> None:
        self.pending = pending
        self.active: str | None = None
        self.recorded: list[str] = []
        self.cleared = 0

    def record_active(self, value: str) -> None:
        self.active = value if value in hotplug.INTERNAL_SINKS else None
        self.recorded.append(value)

    def load_pending(self) -> str | None:
        return self.pending

    def clear_pending(self) -> None:
        self.pending = None
        self.cleared += 1


def snapshot(
    default: str,
    *externals: dict,
    inputs=(7, 8),
    card=None,
    internal=hotplug.INTERNAL_SINKS,
):
    return hotplug.Snapshot(
        default=default,
        sinks=frozenset(
            (*internal, *(item["name"] for item in externals))
        ),
        external={item["name"]: item for item in externals},
        sink_inputs=tuple(inputs),
        card=card,
    )


def stereo_sink(front: int, other: int) -> dict:
    channels = hotplug.StereoVolumeMigration.CHANNELS
    values = {
        channel: {"value": front if index < 2 else other}
        for index, channel in enumerate(channels)
    }
    return {"name": "Stereo", "volume": values}


class MigrationPactl:
    def __init__(self, sink: dict) -> None:
        self.sink = sink
        self.commands: list[tuple[str, ...]] = []

    def json_list(self, kind: str):
        self.assert_kind = kind
        return [self.sink]

    def run(self, *arguments: str, check: bool = True):
        self.commands.append(arguments)
        if arguments[:2] == ("set-sink-volume", "Stereo"):
            value = int(arguments[2])
            self.sink = stereo_sink(value, value)
        return mock.Mock(stdout="")


class ClassificationTests(unittest.TestCase):
    def test_only_exact_headphone_or_positive_bluez_output_is_external(self):
        self.assertTrue(hotplug.external_sink(HEADPHONES))
        self.assertTrue(hotplug.external_sink(BT_ONE))
        self.assertTrue(hotplug.external_sink(BT_TWO))
        self.assertFalse(
            hotplug.external_sink(
                sink("bluez_output.fake.1", 1, **{"device.api": "alsa"})
            )
        )
        self.assertFalse(
            hotplug.external_sink(
                sink("alsa_output.usb_headset", 1, **{"device.api": "bluez5"})
            )
        )
        self.assertFalse(hotplug.external_sink(sink("Stereo", 1)))

    def test_headphone_profile_availability_shapes(self):
        self.assertTrue(
            hotplug.profile_available(
                {
                    "profiles": [
                        {"name": hotplug.HEADPHONE_PROFILE, "available": "yes"}
                    ]
                },
                hotplug.HEADPHONE_PROFILE,
            )
        )
        self.assertFalse(
            hotplug.profile_available(
                {
                    "profiles": {
                        hotplug.HEADPHONE_PROFILE: {"available": "no"}
                    }
                },
                hotplug.HEADPHONE_PROFILE,
            )
        )
        self.assertFalse(
            hotplug.profile_available(
                {"profiles": {hotplug.HEADPHONE_PROFILE: {}}},
                hotplug.HEADPHONE_PROFILE,
            )
        )

    def test_internal_hrir_playback_legs_are_never_migrated(self):
        self.assertFalse(
            hotplug.migratable_sink_input(
                {
                    "properties": {
                        "media.class": "Stream/Output/Audio/Internal",
                        "node.name": "effect_output.odin3_dvs",
                    }
                }
            )
        )
        self.assertFalse(
            hotplug.migratable_sink_input(
                {
                    "properties": {
                        "media.class": "Stream/Output/Audio",
                        "node.name": "effect_output.odin3_stereo",
                    }
                }
            )
        )
        self.assertTrue(
            hotplug.migratable_sink_input(
                {
                    "properties": {
                        "media.class": "Stream/Output/Audio",
                        "application.name": "Game",
                    }
                }
            )
        )


class RoutingTests(unittest.TestCase):
    def policy(self, pactl, choice, runtime=None):
        policy = hotplug.HotplugPolicy(
            pactl, choice, runtime or FakeRuntime()
        )
        policy._notify_steam = mock.Mock()
        return policy

    def test_pending_virtual_is_restored_before_stereo_can_be_saved(self):
        pactl = FakePactl([snapshot("Stereo")])
        choice = FakeChoice("Virtual Surround Sound")
        runtime = FakeRuntime("Virtual Surround Sound")
        policy = self.policy(pactl, choice, runtime)

        policy.reconcile()

        self.assertIn(
            ("set-default-sink", "Virtual Surround Sound"), pactl.commands
        )
        self.assertIn(
            ("move-sink-input", "7", "Virtual Surround Sound"),
            pactl.commands,
        )
        self.assertEqual(choice.saved, ["Virtual Surround Sound"])
        self.assertIsNone(runtime.pending)
        self.assertEqual(runtime.cleared, 1)
        self.assertEqual(runtime.active, "Virtual Surround Sound")
        policy._notify_steam.assert_called_once()

    def test_failed_pending_restore_keeps_request_and_durable_choice(self):
        pactl = FailFirstDefaultPactl([snapshot("Stereo")])
        choice = FakeChoice("Virtual Surround Sound")
        runtime = FakeRuntime("Virtual Surround Sound")
        policy = self.policy(pactl, choice, runtime)

        with self.assertRaisesRegex(
            RuntimeError, "present but could not be activated"
        ):
            policy.reconcile()

        self.assertEqual(runtime.pending, "Virtual Surround Sound")
        self.assertEqual(runtime.cleared, 0)
        self.assertEqual(choice.saved, [])
        policy._notify_steam.assert_not_called()

    def test_missing_virtual_keeps_guard_during_safe_stereo_fallback(self):
        pactl = FakePactl(
            [
                snapshot("Stereo", internal=("Stereo",)),
                snapshot("Stereo"),
            ]
        )
        choice = FakeChoice("Virtual Surround Sound")
        runtime = FakeRuntime("Virtual Surround Sound")
        policy = self.policy(pactl, choice, runtime)

        policy.reconcile()
        self.assertEqual(runtime.pending, "Virtual Surround Sound")
        self.assertEqual(choice.saved, [])
        self.assertEqual(choice.value, "Virtual Surround Sound")
        self.assertEqual(runtime.active, "Stereo")
        self.assertIn(("move-sink-input", "7", "Stereo"), pactl.commands)

        policy.reconcile()
        self.assertIsNone(runtime.pending)
        self.assertEqual(choice.saved, ["Virtual Surround Sound"])
        self.assertEqual(runtime.active, "Virtual Surround Sound")
        self.assertIn(
            ("set-default-sink", "Virtual Surround Sound"), pactl.commands
        )
        self.assertEqual(policy._notify_steam.call_count, 2)

    def test_external_active_output_is_not_recorded_as_internal(self):
        runtime = FakeRuntime()
        policy = self.policy(
            FakePactl([snapshot(BT_ONE["name"], BT_ONE)]),
            FakeChoice("Virtual Surround Sound"),
            runtime,
        )
        policy.reconcile()
        self.assertIsNone(runtime.active)

    def test_startup_external_switches_and_remembers_virtual(self):
        pactl = FakePactl([snapshot("Virtual Surround Sound", BT_ONE)])
        choice = FakeChoice()
        policy = self.policy(pactl, choice)
        policy.reconcile()
        self.assertEqual(choice.saved, ["Virtual Surround Sound"])
        self.assertIn(("set-default-sink", BT_ONE["name"]), pactl.commands)
        self.assertIn(("move-sink-input", "7", BT_ONE["name"]), pactl.commands)
        policy._notify_steam.assert_called_once()

    def test_startup_already_on_external_still_moves_and_notifies(self):
        pactl = FakePactl([snapshot(BT_ONE["name"], BT_ONE)])
        policy = self.policy(pactl, FakeChoice("Virtual Surround Sound"))
        policy.reconcile()
        self.assertNotIn(
            ("set-default-sink", BT_ONE["name"]), pactl.commands
        )
        self.assertIn(("move-sink-input", "7", BT_ONE["name"]), pactl.commands)
        policy._notify_steam.assert_called_once()

    def test_newest_new_connection_wins(self):
        pactl = FakePactl(
            [
                snapshot("Stereo"),
                snapshot("Stereo", BT_ONE, HEADPHONES, BT_TWO),
            ]
        )
        policy = self.policy(pactl, FakeChoice())
        policy.reconcile()
        policy.reconcile()
        self.assertIn(("set-default-sink", BT_TWO["name"]), pactl.commands)

    def test_settling_graph_retries_new_connection(self):
        pactl = FailFirstDefaultPactl(
            [
                snapshot("Stereo"),
                snapshot("Stereo", BT_ONE),
                snapshot("Stereo", BT_ONE),
            ]
        )
        policy = self.policy(pactl, FakeChoice())
        policy.reconcile()
        policy.reconcile()
        policy.reconcile()
        attempts = [
            command
            for command in pactl.commands
            if command == ("set-default-sink", BT_ONE["name"])
        ]
        self.assertEqual(len(attempts), 2)
        self.assertEqual(policy.active_external, BT_ONE["name"])

    def test_restart_enumeration_does_not_overwrite_saved_virtual(self):
        pactl = FakePactl(
            [
                snapshot("Stereo"),
                snapshot("Stereo", BT_ONE),
            ]
        )
        choice = FakeChoice("Virtual Surround Sound")
        policy = self.policy(pactl, choice)
        policy.reconcile()
        policy.reconcile()
        self.assertEqual(choice.value, "Virtual Surround Sound")
        self.assertEqual(choice.saved, [])
        self.assertIn(("set-default-sink", BT_ONE["name"]), pactl.commands)

    def test_last_external_removal_restores_saved_internal(self):
        pactl = FakePactl(
            [
                snapshot("Virtual Surround Sound", BT_ONE),
                snapshot("auto_null"),
            ]
        )
        choice = FakeChoice("Virtual Surround Sound")
        policy = self.policy(pactl, choice)
        policy.reconcile()
        policy.reconcile()
        self.assertEqual(choice.value, "Virtual Surround Sound")
        self.assertIn(
            ("set-default-sink", "Virtual Surround Sound"),
            pactl.commands,
        )

    def test_pulse_fallback_does_not_overwrite_saved_internal(self):
        pactl = FakePactl(
            [
                snapshot("Virtual Surround Sound", BT_ONE),
                snapshot("Stereo"),
            ]
        )
        choice = FakeChoice()
        policy = self.policy(pactl, choice)
        policy.reconcile()
        policy.reconcile()
        self.assertEqual(choice.value, "Virtual Surround Sound")
        self.assertIn(
            ("set-default-sink", "Virtual Surround Sound"), pactl.commands
        )

    def test_removal_uses_remaining_external(self):
        pactl = FakePactl(
            [
                snapshot("Stereo", BT_ONE, BT_TWO),
                snapshot("auto_null", BT_ONE),
            ]
        )
        policy = self.policy(pactl, FakeChoice())
        policy.reconcile()
        policy.reconcile()
        self.assertIn(("set-default-sink", BT_ONE["name"]), pactl.commands)

    def test_manual_internal_selection_is_respected(self):
        pactl = FakePactl(
            [
                snapshot("Stereo", BT_ONE),
                snapshot("Virtual Surround Sound", BT_ONE),
                snapshot("Virtual Surround Sound"),
            ]
        )
        choice = FakeChoice()
        policy = self.policy(pactl, choice)
        policy.reconcile()
        policy.reconcile()
        policy.reconcile()
        defaults = [
            command
            for command in pactl.commands
            if command and command[0] == "set-default-sink"
        ]
        self.assertEqual(defaults, [("set-default-sink", BT_ONE["name"])])
        self.assertEqual(choice.value, "Virtual Surround Sound")

    def test_jack_profile_is_switched_before_routing(self):
        card = {
            "name": hotplug.ODIN_CARD,
            "active_profile": hotplug.SPEAKER_PROFILE,
            "profiles": [
                {"name": hotplug.HEADPHONE_PROFILE, "available": "yes"}
            ],
        }
        pactl = FakePactl(
            [
                snapshot("Stereo", card=card),
                snapshot("Stereo", HEADPHONES),
            ]
        )
        policy = self.policy(pactl, FakeChoice())
        with mock.patch.object(hotplug.time, "sleep"):
            policy.reconcile()
        self.assertEqual(
            pactl.commands[0],
            (
                "set-card-profile",
                hotplug.ODIN_CARD,
                hotplug.HEADPHONE_PROFILE,
            ),
        )
        self.assertIn(("set-default-sink", hotplug.HEADPHONE_SINK), pactl.commands)

    def test_steam_retry_limit_is_reset_before_restart(self):
        policy = hotplug.HotplugPolicy(
            FakePactl([]), FakeChoice(), FakeRuntime()
        )
        policy._steam_is_reachable = mock.Mock(return_value=True)
        calls = mock.Mock()
        run = mock.Mock()
        popen = mock.Mock()
        calls.attach_mock(run, "run")
        calls.attach_mock(popen, "popen")
        with (
            mock.patch.object(hotplug.subprocess, "run", run),
            mock.patch.object(hotplug.subprocess, "Popen", popen),
        ):
            policy._notify_steam()
        self.assertEqual(
            [call[0] for call in calls.mock_calls],
            ["run", "popen"],
        )
        run.assert_called_once_with(
            [
                "/usr/bin/systemctl",
                "--user",
                "reset-failed",
                hotplug.STEAM_RESTORE_UNIT,
            ],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        popen.assert_called_once_with(
            [
                "/usr/bin/systemctl",
                "--user",
                "--no-block",
                "restart",
                hotplug.STEAM_RESTORE_UNIT,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


class StateAndArtifactTests(unittest.TestCase):
    def test_runtime_active_output_is_atomic_and_internal_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            active = Path(temporary) / "active"
            pending = Path(temporary) / "pending"
            with mock.patch.dict(
                hotplug.os.environ,
                {
                    "ARMADA_AUDIO_ACTIVE_OUTPUT": str(active),
                    "ARMADA_AUDIO_RESUME_PREFERENCE": str(pending),
                },
                clear=False,
            ):
                state = hotplug.RuntimeOutputState()
                state.record_active("Virtual Surround Sound")
                self.assertEqual(
                    active.read_text(encoding="ascii"),
                    "Virtual Surround Sound\n",
                )
                state.record_active(BT_ONE["name"])
                self.assertFalse(active.exists())

    def test_state_is_bounded_and_atomic(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.dict(
                hotplug.os.environ,
                {"ARMADA_AUDIO_STATE_DIR": temporary},
                clear=False,
            ):
                choice = hotplug.ReturnChoice()
                choice.save("Virtual Surround Sound")
                self.assertEqual(choice.load(), "Virtual Surround Sound")
                choice.save("not-an-output")
                self.assertEqual(choice.load(), "Virtual Surround Sound")
                if os.name != "nt":
                    self.assertEqual(
                        oct(
                            (
                                Path(temporary)
                                / "odin3-audio-speaker-default"
                            ).stat().st_mode
                            & 0o777
                        ),
                        "0o600",
                    )

    def test_existing_wireplumber_internal_default_seeds_return_choice(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "armada-state"
            configured = root / "default-nodes"
            configured.write_text(
                "[default-nodes]\n"
                "default.configured.audio.sink=Virtual Surround Sound\n",
                encoding="utf-8",
            )
            with mock.patch.dict(
                hotplug.os.environ,
                {
                    "ARMADA_AUDIO_STATE_DIR": str(state),
                    "ARMADA_AUDIO_WIREPLUMBER_DEFAULT_NODES": str(configured),
                },
                clear=False,
            ):
                choice = hotplug.ReturnChoice()
                choice.seed_from_wireplumber()
                self.assertEqual(choice.load(), "Virtual Surround Sound")
                self.assertEqual(
                    (
                        state / "odin3-audio-speaker-default"
                    ).read_text(encoding="ascii"),
                    "Virtual Surround Sound\n",
                )

    def test_legacy_two_channel_volume_is_migrated_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            pactl = MigrationPactl(stereo_sink(49151, 0))
            migration = hotplug.StereoVolumeMigration(Path(temporary))
            migration.reconcile(pactl)
            migration.reconcile(pactl)
            self.assertEqual(
                pactl.commands,
                [("set-sink-volume", "Stereo", "49151")],
            )
            self.assertTrue(
                (
                    Path(temporary)
                    / "odin3-audio-stereo-8ch-volume-v1.done"
                ).is_file()
            )

    def test_nonlegacy_channel_volume_layout_is_left_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            pactl = MigrationPactl(stereo_sink(49151, 32768))
            migration = hotplug.StereoVolumeMigration(Path(temporary))
            migration.reconcile(pactl)
            self.assertEqual(pactl.commands, [])

    def test_unsettled_stereo_layout_is_retried_before_marking_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            pactl = MigrationPactl(
                {
                    "name": "Stereo",
                    "volume": {
                        "front-left": {"value": 49151},
                        "front-right": {"value": 49151},
                    },
                }
            )
            migration = hotplug.StereoVolumeMigration(Path(temporary))
            migration.reconcile(pactl)
            self.assertFalse(migration.complete)
            self.assertFalse(migration.marker.exists())
            pactl.sink = stereo_sink(49151, 0)
            migration.reconcile(pactl)
            self.assertTrue(migration.complete)
            self.assertTrue(migration.marker.is_file())

    def test_unit_is_bounded_and_restartable(self):
        unit = UNIT.read_text(encoding="utf-8")
        self.assertIn(
            "ExecStart=/usr/bin/python3 /usr/libexec/armada/odin3-audio-hotplug",
            unit,
        )
        self.assertIn("Restart=on-failure", unit)
        self.assertIn("WantedBy=default.target", unit)

    def test_helper_contains_exact_device_and_route_bounds(self):
        source = HELPER.read_text(encoding="utf-8")
        for value in (
            "ayn-odin-3",
            "AYN Odin 3",
            "SM8750",
            hotplug.ODIN_CARD,
            hotplug.HEADPHONE_SINK,
            "bluez_output.",
            "device.api",
            "bluez5",
            "pactl",
            "move-sink-input",
            hotplug.STEAM_RESTORE_UNIT,
            "http://127.0.0.1:8080/json",
            "os.replace",
            "effect_output.odin3_stereo",
            "odin3-audio-stereo-8ch-volume-v1.done",
            "armada-odin3-audio-active-output",
            "armada-odin3-audio-resume",
            "restored pre-suspend output",
        ):
            self.assertIn(value, source)


if __name__ == "__main__":
    unittest.main()
