#!/usr/bin/env python3
"""Exercise device gamma conversion, profile selection, and write permissions."""

import os
import fcntl
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPERS = ROOT / "system_files/usr/libexec/armada"
CONVERTER = HELPERS / "steam-backlight-value"
conversion_tmp = tempfile.TemporaryDirectory()
conversion_root = Path(conversion_tmp.name)
for name in ('source', 'target'):
    (conversion_root / name).mkdir()


def convert(value, source_max, target_max, gamma=1, input_min=0, output_min=0, output_max=1):
    for name, maximum in (('source', source_max), ('target', target_max)):
        (conversion_root / name / 'max_brightness').write_text(str(maximum) + '\n')
    result = subprocess.run([str(CONVERTER), str(value), str(conversion_root / 'source'),
                             str(conversion_root / 'target'), str(gamma),
                             str(input_min), str(output_min), str(output_max)],
                            text=True, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr)
    return int(result.stdout)


class SteamBacklightTest(unittest.TestCase):
    def test_light_demand_conversion(self):
        # Known light fractions, independent of Steam's slider implementation.
        self.assertEqual(convert(25, 100, 1000, 2), 500)
        self.assertEqual(convert(625, 10000, 1000, 4), 500)
        self.assertEqual(convert(100, 100, 1000, 2.4), 1000)
        self.assertEqual(convert(250, 1000, 2000, 2), 1000)

    def test_sdr_and_hdr_writes_share_one_mapping(self):
        # Requests captured from the Nova in SDR and HDR respectively.
        sdr = convert(1024, 3445, 3445, 2.4)
        hdr = convert(3072, 3445, 3445, 2.4)
        self.assertGreater(hdr, sdr)
        self.assertAlmostEqual(hdr / sdr, 3 ** (1 / 2.4), delta=.002)
        self.assertEqual(convert(3445, 3445, 3445, 2.4), 3445)

    def test_monotonic_and_bounded(self):
        values = [convert(v, 3445, 3445, 2.4, .01, .05) for v in range(3446)]
        self.assertEqual(values, sorted(values))
        self.assertEqual(values[0], 173)
        self.assertEqual(values[-1], 3445)
        self.assertGreater(values[1], 0)

    def test_minimum_brightness(self):
        for value in (0, 1, 34):
            self.assertEqual(convert(value, 3445, 3445, 2.4, .01, .05), 173)
        self.assertGreater(convert(35, 3445, 3445, 2.4, .01, .05), 173)
        self.assertEqual(convert(0, 3445, 255, 2.4, .01, .05), 13)
        self.assertEqual(convert(0, 3445, 1, 2.4, .01, .05), 1)

    def test_configurable_endpoints(self):
        # gamma 2 maps input .25 to .5, so raw .5625 is the midpoint
        # of the corrected .5..1 range. Output .1..1 puts that at .55.
        self.assertEqual(convert(2500, 10000, 1000, 2, .25, .1), 100)
        self.assertEqual(convert(5625, 10000, 1000, 2, .25, .1), 550)
        self.assertEqual(convert(10000, 10000, 1000, 2, .25, .1), 1000)
        self.assertEqual(convert(5625, 10000, 2000, 2, .25, .1), 1100)
        self.assertEqual(convert(60, 100, 1000, 1, .2, .1), 550)

    def test_maximum_ends_the_range_early(self):
        values = [convert(v, 4095, 4095, 2.4, .01, .01, .84) for v in range(4096)]
        self.assertEqual(values, sorted(values))
        self.assertEqual(values[-1], 3439)
        self.assertEqual(values[0], 41)
        self.assertEqual(convert(2048, 4096, 4096, 1, 0, 0, .5), 1024)
        self.assertEqual(convert(4096, 4096, 4096, 1, 0, 0, .5), 2048)
        for output_min, output_max in ((0, 0), (.5, .4), (0, 1.1), (0, -1)):
            with self.assertRaises(ValueError):
                convert(1024, 3445, 3445, 2.4, 0, output_min, output_max)

    def test_default_minimum(self):
        for maximum, minimum in ((1, 1), (100, 1), (255, 3), (4095, 41)):
            self.assertEqual(convert(0, maximum, maximum, 1, 0, .01), minimum)
            self.assertEqual(convert(maximum, maximum, maximum, 1, 0, .01), maximum)
        values = [convert(v, 100, 255, 1, 0, .01) for v in range(101)]
        self.assertEqual(values, sorted(values))
        self.assertGreater(min(values), 0)

    def test_default_floor_preserves_linear_requests(self):
        # Thor's driver already exposes linear luminance. Preserve requests
        # above the floor, including when steering between backlight ranges.
        for source_max, target_max in ((4096, 4096), (100, 4096), (4096, 255)):
            minimum = (target_max + 99) // 100
            for value in (0, 1, source_max // 100, source_max // 2, source_max):
                expected = max(minimum, value * target_max // source_max)
                self.assertEqual(convert(value, source_max, target_max, 1, 0, .01),
                                 expected)
        self.assertEqual(convert(2048, 4096, 4096, 1, 0, .01), 2048)

    def test_low_slider_steps_have_no_clamped_region(self):
        # Steam's integer outputs at 0%, 1%, 2%, and 5% slider positions.
        values = [convert(v, 3445, 3445, 2.4, .01, .05) for v in (34, 36, 39, 48)]
        self.assertEqual(values[0], 173)
        self.assertTrue(all(left < right for left, right in zip(values, values[1:])))

    def test_passthrough_and_primary_rescaling(self):
        self.assertEqual(convert(250, 1000, 2000), 500)
        self.assertEqual(convert(250, 1000, 2000, 1), 500)
        self.assertEqual(convert(0, 3445, 3445, 1), 0)

    def test_invalid_ranges(self):
        for value, source, target in ((-1, 3445, 3445), (3446, 3445, 3445),
                                      (1, 0, 3445), (1, 3445, 0)):
            with self.assertRaises(ValueError):
                convert(value, source, target, 2.4)
        for gamma in (0, -1, float('nan'), float('inf'), -float('inf')):
            with self.assertRaises(ValueError):
                convert(1024, 3445, 3445, gamma)
        for input_min, output_min in ((-1, 0), (1, 0), (0, -1), (0, 1.1),
                                      (float('nan'), 0), (0, float('nan')),
                                      (float('inf'), 0), (0, float('inf'))):
            with self.assertRaises(ValueError):
                convert(1024, 3445, 3445, 2.4, input_min, output_min)

    def test_sysfs_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "max_brightness").write_text("3445\n")
            args = [str(CONVERTER), "1024", tmp, tmp]
            self.assertEqual(subprocess.check_output(args, text=True).strip(), "1024")
            (path / "scale").write_text("non-linear\n")
            self.assertEqual(subprocess.check_output(args, text=True).strip(), "1024")
            args.append('2.4')
            self.assertEqual(int(subprocess.check_output(args, text=True)),
                             convert(1024, 3445, 3445, 2.4))
            args.extend(('0.01', '0.05'))
            args[1] = '34'
            self.assertEqual(subprocess.check_output(args, text=True).strip(), '173')
            args[1] = "3446"
            result = subprocess.run(args, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")

    def test_acl_policy(self):
        # Substitute only device discovery and the sysfs root; chmod/chgrp
        # operate on a temporary regular file, never on a real backlight.
        source = (HELPERS / "backlight-acl").read_text()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            brightness = path / "panel/brightness"
            brightness.parent.mkdir()
            brightness.touch()
            for primary, gamma, input_min, minimum, maximum, scale, writable in (
                ("", "1", "0", "0", "1", "linear", True),
                ("", "1", "0", "0", "1", "non-linear", True),
                ("", "2.4", ".01", ".05", "1", "non-linear", False),
                ("", "2.4", ".01", ".05", "1", "unknown", False),
                ("", "2.4", ".01", ".05", "1", None, False),
                ("", "1", ".01", "0", "1", "linear", False),
                ("", "1", "0", ".05", "1", "linear", False),
                ("", "1", "0", ".01", "1", "non-linear", False),
                ("", "1", "0", "0", ".84", "linear", False),
                ("primary", "1", "0", "0", "1", "linear", False),
            ):
                scale_path = brightness.parent / "scale"
                if scale is None:
                    scale_path.unlink(missing_ok=True)
                else:
                    scale_path.write_text(scale + "\n")
                brightness.chmod(0o666)
                script = source.replace('eval "$(/usr/libexec/armada/device-env)"',
                                        f'ARMADA_PRIMARY_BACKLIGHT={primary}\nARMADA_BACKLIGHT_GAMMA={gamma}\n'
                                        f'ARMADA_BACKLIGHT_INPUT_MIN={input_min}\nARMADA_BACKLIGHT_MIN={minimum}\n'
                                        f'ARMADA_BACKLIGHT_MAX={maximum}')
                script = script.replace("/sys/class/backlight", tmp)
                subprocess.run(["bash", "-s", "--", "panel"], input=script,
                               text=True, check=True)
                self.assertEqual(bool(brightness.stat().st_mode & 0o020), writable)
                if not writable:
                    self.assertEqual(brightness.stat().st_mode & 0o022, 0)

    def test_priv_write_integration(self):
        source = (ROOT / "system_files/usr/bin/steamos-polkit-helpers/steamos-priv-write").read_text()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            for name in ("primary", "secondary"):
                panel = path / name
                panel.mkdir()
                (panel / "brightness").write_text("200\n")
                (panel / "max_brightness").write_text("3445\n")
                (panel / "scale").write_text("non-linear\n" if name == "primary" else "linear\n")
            # Exercise logind routing regardless of the test runner's UID.
            source = source.replace('if [[ $EUID -eq 0 ]]; then', 'if false; then')
            source = source.replace('if [[ $EUID -ne 0 ]]; then', 'if true; then')
            source = source.replace('eval "$(/usr/libexec/armada/device-env)"',
                                    'ARMADA_PRIMARY_BACKLIGHT=primary\nARMADA_BACKLIGHT_GAMMA=2.4\n'
                                    'ARMADA_BACKLIGHT_INPUT_MIN=0.01\nARMADA_BACKLIGHT_MIN=0.05')
            source = source.replace('/usr/libexec/armada/steam-backlight-value', str(CONVERTER))
            source = source.replace('/sys/class/backlight', tmp)
            source = source.replace('systemd-cat -t armada-steamos-priv-write -p info', 'cat >/dev/null')
            async_source = source
            # Finish the background logind write before returning, so each call is observable.
            source = source.replace('</dev/null >/dev/null 2>&1 &\n  exit 0', '</dev/null >/dev/null 2>&1 &\n  wait\n  exit 0')
            commands = path / 'bin'
            commands.mkdir()
            bus_log = path / 'bus-call.json'
            busctl = commands / 'busctl'
            busctl.write_text('#!/usr/bin/env python3\n'
                              'import json, os, sys\nfrom pathlib import Path\n'
                              f'Path({str(bus_log)!r}).write_text(json.dumps(sys.argv[1:]))\n'
                              'if os.environ.get("TEST_BUSCTL_FAIL"): sys.exit(1)\n'
                              f'(Path({tmp!r}) / sys.argv[-2] / "brightness").write_text(sys.argv[-1] + "\\n")\n')
            busctl.chmod(0o755)
            pkexec = commands / 'pkexec'
            pkexec.write_text('#!/bin/sh\necho "unexpected pkexec" >&2\nexit 99\n')
            pkexec.chmod(0o755)
            env = dict(os.environ, PATH=f"{commands}:{os.environ['PATH']}", XDG_RUNTIME_DIR=tmp)
            target = path / "secondary/brightness"
            result = subprocess.run(["bash", "-s", "--", str(target), "1024"],
                                    input=source, text=True, capture_output=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(int((path / "primary/brightness").read_text()),
                             convert(1024, 3445, 3445, 2.4, .01, .05))
            self.assertEqual(target.read_text(), "200\n")
            self.assertEqual(json.loads(bus_log.read_text()), [
                '--system', 'call', 'org.freedesktop.login1',
                '/org/freedesktop/login1/session/auto', 'org.freedesktop.login1.Session',
                'SetBrightness', 'ssu', 'backlight', 'primary', '1925'])
            result = subprocess.run(["bash", "-s", "--", str(target), "34"],
                                    input=source, text=True, capture_output=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((path / "primary/brightness").read_text(), "173\n")
            previous = (path / "primary/brightness").read_text()
            bus_log.unlink()
            # Out of range: the converter rejects it before logind is called.
            result = subprocess.run(["bash", "-s", "--", str(target), "3446"],
                                    input=source, text=True, capture_output=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(bus_log.exists())
            self.assertEqual((path / "primary/brightness").read_text(), previous)

            # A failed logind write happens after the helper has returned.
            result = subprocess.run(['bash', '-s', '--', str(target), '1024'],
                                    input=source, text=True, capture_output=True,
                                    env=dict(env, TEST_BUSCTL_FAIL='1'))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(bus_log.exists())
            self.assertEqual((path / 'primary/brightness').read_text(), previous)
            bus_log.unlink()
            root_source = source.replace('if false; then', 'if true; then')
            result = subprocess.run(['bash', '-s', '--', str(target), '1024'],
                                    input=root_source, text=True, capture_output=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(bus_log.exists())
            self.assertEqual((path / 'primary/brightness').read_text(), '1925\n')
            capped_source = root_source.replace('ARMADA_BACKLIGHT_MIN=0.05',
                                                'ARMADA_BACKLIGHT_MIN=0.05\nARMADA_BACKLIGHT_MAX=0.84')
            result = subprocess.run(['bash', '-s', '--', str(target), '3445'],
                                    input=capped_source, text=True, capture_output=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(int((path / 'primary/brightness').read_text()),
                             convert(3445, 3445, 3445, 2.4, .01, .05, .84))
            self.assertLess(int((path / 'primary/brightness').read_text()), 3445)
            result = subprocess.run(['bash', '-s', '--',
                '/sys/class/drm/card0/device/power_dpm_force_performance_level', 'auto'],
                input=source, text=True, capture_output=True, env=env)
            self.assertEqual(result.returncode, 99)

            # A drag against a slow logind: every call returns at once and only the last request is written.
            writes = path / 'writes'
            busctl.write_text('#!/usr/bin/env python3\n'
                              'import sys, time\nfrom pathlib import Path\n'
                              f'with open({str(writes)!r}, "a") as f: f.write(sys.argv[-1] + "\\n")\n'
                              'time.sleep(0.2)\n'
                              f'(Path({tmp!r}) / sys.argv[-2] / "brightness").write_text(sys.argv[-1] + "\\n")\n')
            values = list(range(300, 3300, 300))
            final = str(convert(values[-1], 3445, 3445, 2.4, .01, .05))
            # Hold the writers' lock so every request queues before any is applied.
            with open(path / 'armada-backlight-request.lock', 'w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                for value in values:
                    start = time.monotonic()
                    result = subprocess.run(['bash', '-s', '--', str(target), str(value)],
                                            input=async_source, text=True, capture_output=True, env=env)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertLess(time.monotonic() - start, 1)
                self.assertFalse(writes.exists())
            deadline = time.monotonic() + 10
            while (path / 'primary/brightness').read_text().strip() != final:
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.05)
            with open(path / 'armada-backlight-request.lock') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
            self.assertEqual(writes.read_text().split(), [final])

    def test_device_profiles(self):
        for model, expected in (("Retroid Pocket Nova", '2.4'), ("AYN Thor", '1'),
                                ("AYN Odin 3 Portal", '2.4'), ("unrecognised", '1')):
            env = dict(os.environ, ARMADA_MODEL=model,
                       ARMADA_DEVICE_DIR=str(ROOT / 'system_files/usr/lib/armada/devices'),
                       ARMADA_SLEEP_CONFIG='/dev/null', ARMADA_MEM_SLEEP_PATH='/dev/null')
            output = subprocess.check_output([str(HELPERS / 'device-env')], env=env, text=True)
            self.assertIn(f'ARMADA_BACKLIGHT_GAMMA={expected}\n', output)
            minima = {'Retroid Pocket Nova': ('0.01', '0.05'), 'AYN Odin 3 Portal': ('0.01', '0.01')}
            input_min, minimum = minima.get(model, ('0', '0'))
            self.assertIn(f'ARMADA_BACKLIGHT_INPUT_MIN={input_min}\n', output)
            self.assertIn(f'ARMADA_BACKLIGHT_MIN={minimum}\n', output)
            self.assertIn('ARMADA_BACKLIGHT_MAX=' +
                          ('0.84' if model == 'AYN Odin 3 Portal' else '1') + '\n', output)


if __name__ == "__main__":
    unittest.main()
