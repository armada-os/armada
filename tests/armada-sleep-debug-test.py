#!/usr/bin/env python3
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
LIB = Path(os.environ.get('ARMADA_SLEEP_DEBUG_TEST_LIB', ROOT / 'system_files/usr/lib/armada/armada_sleep_debug.py'))
HOOK = Path(os.environ.get('ARMADA_SLEEP_DEBUG_TEST_HOOK', ROOT / 'decky/armada-control/py_modules/armada_control/sleep_debug_hook.sh'))
PLUGIN = Path(os.environ.get('ARMADA_SLEEP_DEBUG_TEST_PLUGIN', ROOT / 'decky/armada-control/py_modules/armada_control/system.py'))
PUBLIC_ROOT = Path(os.environ.get('ARMADA_SLEEP_DEBUG_TEST_ROOT', ROOT))
spec = importlib.util.spec_from_file_location('sleep_debug', LIB)
debug = importlib.util.module_from_spec(spec)
spec.loader.exec_module(debug)
REAL_COMMAND = debug.command
REAL_PIPEWIRE = debug.pipewire


class SleepDebugTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for key in ('SYS', 'PROC', 'RUN', 'STATE'):
            p = self.root / key.lower()
            p.mkdir()
            self.enterContext(patch.object(debug, key, p))
        self.write(debug.PROC / 'sys/kernel/random/boot_id', 'boot-one')
        self.write(debug.SYS / 'power/suspend_stats/success', '0')
        self.write(debug.SYS / 'power/suspend_stats/fail', '0')
        self.write(debug.SYS / 'power/mem_sleep', '[s2idle] deep')
        self.write(debug.SYS / 'class/power_supply/battery/type', 'Battery')
        self.write(debug.SYS / 'class/power_supply/battery/charge_counter', '1000000')
        self.write(debug.SYS / 'class/power_supply/battery/status', 'Discharging')
        self.write(debug.SYS / 'kernel/debug/qcom_stats/adsp', 'Count: 10\nAccumulated Duration: 19200000')
        self.enterContext(patch.object(debug, 'pipewire', return_value={'status': 'unavailable'}))
        self.enterContext(patch.object(debug, 'command', return_value={
            'status': 'complete', 'returncode': 0, 'truncated': False,
            'text': '{"__CURSOR":"cursor-one"}\n', 'error': ''}))
        self.cycle = 'a' * 32

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)

    def snapshots(self):
        debug.begin(self.cycle)
        self.write(debug.SYS / 'power/suspend_stats/success', '1')
        self.write(debug.SYS / 'class/power_supply/battery/charge_counter', '990000')
        self.write(debug.SYS / 'power/pm_wakeup_irq', '199')
        self.write(debug.SYS / 'kernel/irq/199/actions', 'Hall Lid Sensor')
        debug.finish(self.cycle)
        path = debug.cycle_path(self.cycle)
        return debug.load(path / 'before.json'), debug.load(path / 'after.json'), debug.load(path / 'attempt.json')

    def test_bluetooth_connected_device_details_exclude_personal_identifiers(self):
        payload = {'type': 'a{oa{sa{sv}}}', 'data': {
            '/org/bluez/hci0': {'org.bluez.Adapter1': {'Powered': {'data': True}}},
            '/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF': {'org.bluez.Device1': {
                'Connected': {'data': True}, 'Alias': {'data': 'Alice headphones'},
                'Name': {'data': 'Alice headphones'}, 'Address': {'data': 'AA:BB:CC:DD:EE:FF'},
                'Icon': {'data': 'audio-headphones'}, 'ServicesResolved': {'data': True},
                'WakeAllowed': {'data': False}, 'UUIDs': {'data': ['0000110b-0000-1000-8000-00805f9b34fb',
                                                               '01234567-89ab-cdef-0123-456789abcdef']}}},
            '/org/bluez/hci0/dev_11_22_33_44_55_66': {'org.bluez.Device1': {
                'Connected': {'data': False}, 'Alias': {'data': 'Private keyboard'}}}}}
        payload['data'] = [payload['data']]
        result = debug.bluetooth_connections({'status': 'complete', 'text': json.dumps(payload)})
        devices = result['connected_devices']
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]['Icon'], 'audio-headphones')
        self.assertEqual(devices[0]['supported_service_ids'], ['110b'])
        self.assertTrue(devices[0]['ServicesResolved'])
        self.assertFalse(devices[0]['WakeAllowed'])
        for secret in ('Alice', 'Private', 'AA_BB', 'AA:BB', '01234567'):
            self.assertNotIn(secret, json.dumps(result))

    def test_bluetooth_query_failure_does_not_mean_no_connections(self):
        result = debug.bluetooth_connections({'status': 'timeout', 'text': 'partial private output', 'error': 'Alice'})
        self.assertEqual(result['status'], 'timeout')
        self.assertNotIn('connected_devices', result)
        self.assertNotIn('Alice', json.dumps(result))

    def test_wifi_link_keeps_metrics_but_not_network_identity(self):
        result = debug.wifi_link({'status': 'complete', 'text':
            'Connected to aa:bb:cc:dd:ee:ff (on wlan0)\nSSID: AliceHome\nfreq: 5975.0\nsignal: -33 dBm\nrx bitrate: 2000.0 MBit/s\ndtim period: 1\n'})
        self.assertTrue(result['connected'])
        self.assertEqual(result['details']['freq'], '5975.0')
        self.assertEqual(result['details']['signal'], '-33 dBm')
        self.assertNotIn('Alice', json.dumps(result))
        self.assertNotIn('aa:bb', json.dumps(result))
        self.assertFalse(debug.wifi_link({'status': 'complete', 'text': 'Not connected.\n'})['connected'])
        self.assertNotIn('connected', debug.wifi_link({'status': 'failed', 'text': ''}))

    def test_wifi_settings_omit_wake_packet_and_channel_identifiers(self):
        result = debug.wifi_settings({'status': 'complete', 'text':
            'WoWLAN is enabled:\n * wake up on magic packet\n * pattern: AliceHome aa:bb:cc:dd:ee:ff\n'}, 'wake_on_wlan')
        self.assertIn('magic packet', result['triggers'])
        self.assertNotIn('Alice', json.dumps(result))
        result = debug.wifi_settings({'status': 'complete', 'text':
            'SSID AliceHome\naddr aa:bb:cc:dd:ee:ff\nchannel 5 (5975 MHz), width: 320 MHz\ntxpower 8.00 dBm'}, 'channel')
        self.assertEqual(result['details']['width_mhz'], '320')
        self.assertNotIn('Alice', json.dumps(result))

    def test_privacy_export_filters_all_sections_including_legacy_snapshots(self):
        before, after, meta = self.snapshots()
        identity = before['groups']['identity']['data']
        identity.update(kernel_build='builder@armada-builder', os_release='DEFAULT_HOSTNAME=armada',
                        cmdline='root=UUID=01234567-89ab-cdef-0123-456789abcdef sm8550.ns=1 drm.debug=0x1')
        before['groups']['health']['data']['mounts'] = '/home/Alice/Documents /mnt/AliceDrive ext4 rw 0 0'
        before['groups']['peripherals']['data']['class/input/event20/device'] = {'name': 'Alice keyboard', 'id/bustype': '0005'}
        before['groups']['pstore']['data'] = {'files': {'/pstore/crash': 'Alice private crash data'}}
        before['groups']['pipewire']['data'] = {'status': 'complete', 'sink_inputs': [
            {'properties': {'application.name': 'Steam', 'node.name': 'AliceHome',
                            'application.process.binary': 'steamwebhelper'}, 'corked': False}]}
        path = debug.cycle_path(self.cycle)
        debug.save(path / 'before.json', before)
        debug.save(path / 'trace.json', self.trace_fixture([
            ('rpm_status', 'device-AA:BB:CC:DD:EE:FF status=RPM_SUSPENDED')]))
        event = {'message': 'Connected to AliceHome at 192.168.1.99 for Alice',
                 'transport': 'syslog', 'unit': 'NetworkManager.service', 'timestamp_us': '123'}
        debug.save(path / 'journal.json', {'status': 'complete', 'events': [event]})
        with contextlib.redirect_stdout(io.StringIO()) as out:
            debug.report(self.cycle)
        for secret in ('Alice', '192.168.1.99', 'AA:BB:CC:DD:EE:FF'):
            self.assertNotIn(secret, out.getvalue())
        self.assertIn('steamwebhelper', out.getvalue())
        self.assertIn('sm8550.ns=1', out.getvalue())
        self.assertIn('RPM_SUSPENDED', out.getvalue())
        self.assertIn('worker-10', out.getvalue())
        self.assertNotIn('task-10', out.getvalue())
        for detail in ('builder@armada-builder', 'DEFAULT_HOSTNAME=armada', 'drm.debug=0x1',
                       '01234567-89ab-cdef-0123-456789abcdef', 'application.name: Steam'):
            self.assertIn(detail, out.getvalue())

    def test_snapshot_preserves_diagnostic_names_and_boot_identity(self):
        before, _, _ = self.snapshots()
        before['boot_id'] = '01234567-89ab-cdef-0123-456789abcdef'
        before['groups']['health']['data']['processes'] = {
            'blocked': [{'pid': '123', 'comm': 'my-game'}],
            'pcm_owners': [{'pid': '124', 'comm': 'audio-server'}]}
        before['groups']['health']['data']['blocks'] = {'sda': {'device/model': 'SD card model'}}
        before['groups']['peripherals']['data'] = {
            'class/input/event0/device': {'name': 'Odin gamepad', 'id/bustype': '0003'},
            'class/input/event1/device': {'name': 'Alice keyboard', 'id/bustype': '0005'},
            'class/input/event2/device': {'name': 'Unknown bus gamepad'}}
        before['groups']['pipewire']['data'] = {'objects': [{'props': {
            'application.name': 'My Game', 'application.process.binary': 'my-game',
            'media.name': 'Alice private video', 'node.name': 'Alice speakers'}}]}
        filtered = debug.private_snapshot(before)
        self.assertEqual(filtered['boot_id'], before['boot_id'])
        self.assertEqual(debug.data(filtered, 'health'), debug.data(before, 'health'))
        self.assertEqual(debug.data(filtered, 'peripherals')['class/input/event0/device']['name'], 'Odin gamepad')
        self.assertNotIn('name', debug.data(filtered, 'peripherals')['class/input/event1/device'])
        self.assertEqual(debug.data(filtered, 'peripherals')['class/input/event2/device']['name'], 'Unknown bus gamepad')
        props = debug.data(filtered, 'pipewire')['objects'][0]['props']
        self.assertEqual(props, {'application.name': 'My Game', 'application.process.binary': 'my-game'})
        self.assertEqual(debug.private_snapshot(filtered), filtered)
        self.assertEqual(debug.redact_text(before['boot_id']), before['boot_id'])

    def test_journal_privacy_keeps_loss_and_error_evidence_when_repeated(self):
        original = {'status': 'complete', 'events': [
            {'message': 'ath12k_wifi7_pci private device: error -110', 'transport': 'syslog'},
            {'message': 'journal: missed 25 kernel messages', 'transport': 'syslog'}]}
        filtered = debug.private_journal(original)
        self.assertEqual(filtered, debug.private_journal(filtered))
        self.assertTrue(filtered['reported_loss'])
        self.assertEqual(filtered['events'][0]['message'], original['events'][0]['message'])
        with contextlib.redirect_stdout(io.StringIO()) as out:
            debug.journal_report(filtered)
        self.assertIn('Capture: incomplete', out.getvalue())
        self.assertIn('ath12k_wifi7_pci private device: error -110', out.getvalue())

    def test_journal_preserves_userspace_diagnostics_and_default_account(self):
        messages = ["Successfully froze unit 'user.slice'.", "Performing sleep operation 'suspend'...",
                    'Power key pressed short.', "System returned from sleep operation 'suspend'.",
                    "Successfully thawed unit 'user.slice'.", 'Clock change detected. Flushing caches.',
                    'Failed to enqueue SYSTEMD_WANTS job: Unit systemd-backlight@backlight:ae94000.dsi.0.service is masked.',
                    'pam_unix(runuser:session): session closed for user armada',
                    'watching /dev/input/event0', '836489cf0ad7496b9767709f1c407857',
                    'BUG: sleeping function called from invalid context', 'watchdog: GPU timed out']
        filtered = debug.private_journal({'status': 'complete', 'events': [
            {'message': message, 'unit': 'user@1000.service', 'transport': 'journal'} for message in messages]})
        self.assertEqual(filtered, debug.private_journal(filtered))
        self.assertEqual([e['message'] for e in filtered['events']], messages)
        self.assertTrue(all(e['unit'] == 'user@1000.service' for e in filtered['events']))
        self.assertEqual(filtered['privacy_omitted_messages'], 0)

    def test_kernel_journal_keeps_audit_and_diagnostics_but_filters_identifiers(self):
        messages = ['Freezing user space processes completed (elapsed 0.001 seconds)',
                    'Timekeeping suspended for 27.298 seconds',
                    'ath12k: failed peer aa:bb:cc:dd:ee:ff at 192.168.1.9 errno=-22',
                    'audit: type=1130 acct="armada" hostname=? addr=?', 'ath12k: SSID AliceHome', 'Connected to AliceHome']
        events = [{'message': msg, 'transport': 'kernel' if i < 5 else 'syslog',
                   'unit': 'wpa_supplicant.service'} for i, msg in enumerate(messages)]
        filtered = debug.private_journal({'status': 'complete', 'events': events})
        self.assertEqual(filtered, debug.private_journal(filtered))
        self.assertEqual(filtered['events'][0]['message'], messages[0])
        self.assertEqual(filtered['events'][1]['message'], messages[1])
        self.assertEqual(filtered['events'][3]['message'], messages[3])
        self.assertEqual(filtered['events'][2]['unit'], 'wpa_supplicant.service')
        with contextlib.redirect_stdout(io.StringIO()) as out:
            debug.journal_report(filtered)
        for secret in ('Alice', 'aa:bb:cc:dd:ee:ff', '192.168.1.9'):
            self.assertNotIn(secret, out.getvalue())
        self.assertIn('errno=-22: 1', out.getvalue())

    def test_interrupted_completion_and_boot_comparison_are_explicit(self):
        before, after, meta = self.snapshots()
        meta.update(outcome='completion-capture-in-progress')
        meta.pop('finished', None)
        self.assertEqual(debug.summarize(before, after, meta)['outcome'], 'completion-capture-interrupted')
        after['boot_id'] = 'another-boot'
        with contextlib.redirect_stdout(io.StringIO()) as out:
            debug.capture_report(before, after)
        self.assertIn('Before/after boot: different', out.getvalue())

    def test_targeted_network_names_do_not_hide_other_network_diagnostics(self):
        sensitive = [
            ('NetworkManager.service', "Activation: starting connection 'AliceHome' ([UUID])"),
            ('NetworkManager.service', 'audit: op="connection-activate" name="AliceHome" result="success"'),
            ('bluetooth.service', 'Device [MAC] Alias: Alice headphones'),
            ('bluetooth.service', 'Name: Alice headphones'),
            ('wpa_supplicant@wlan0.service', 'Trying to associate with SSID AliceHome'),
            ('iwd.service', 'Connected to AliceHome'),
        ]
        safe = [
            ('NetworkManager.service', 'hostname: set hostname to ArmadaDeck'),
            ('NetworkManager.service', 'device (wlan0): state change: activated -> disconnected'),
            ('bluetooth.service', 'Controller resume with wake event 0x0'),
            ('wpa_supplicant.service', 'CTRL-EVENT-CONNECTED - Connection to aa:bb:cc:dd:ee:ff completed'),
            ('systemd-resolved.service', 'Clock change detected. Flushing caches.'),
            ('systemd-suspend.service', 'device name=89c000.serial failed with errno=-22'),
        ]
        filtered = debug.private_journal({'events': [
            {'unit': unit, 'message': msg, 'transport': 'journal'} for unit, msg in sensitive + safe]})
        self.assertEqual(filtered, debug.private_journal(filtered))
        self.assertEqual(filtered['privacy_omitted_messages'], len(sensitive))
        self.assertNotIn('Alice', json.dumps(filtered))
        for event, (_, message) in zip(filtered['events'][len(sensitive):], safe):
            self.assertEqual(event['message'], debug.redact_text(message))

    def test_legacy_journal_omissions_stay_explicit(self):
        original = {'events': [{'message': '[message omitted for privacy; category=failed]', 'transport': 'journal'}]}
        filtered = debug.private_journal(original)
        self.assertEqual(filtered['events'], original['events'])
        self.assertEqual(filtered['privacy_omitted_messages'], 1)

    def test_privacy_output_handles_identifiers_split_between_writes(self):
        out = io.StringIO()
        stream = debug.PrivateOutput(out)
        stream.write('peer=aa:bb:cc:')
        stream.write('dd:ee:ff ip=2001:db8::1 email=alice@example.com\n')
        stream.flush()
        self.assertEqual(out.getvalue(), 'peer=[MAC] ip=[IP] email=alice@example.com\n')
        path = 'chm_apps@24100000.interconnect-qhs_ufs_mem_cfg@1600000.interconnect'
        self.assertEqual(debug.redact_text(path + ' email=alice@example.com'), path + ' email=alice@example.com')

    def test_presleep_context_distinguishes_enabled_radios_from_connections(self):
        before, after, meta = self.snapshots()
        before['groups']['peripherals']['data'] = {
            'class/rfkill/rfkill0': {'type': 'bluetooth', 'name': 'hci0', 'hard': '0', 'soft': '0'},
            'class/rfkill/rfkill1': {'type': 'wlan', 'name': 'phy0', 'hard': '0', 'soft': '1'}}
        context = debug.presleep_context(before)
        self.assertIn('enabled', context['Bluetooth radio'])
        self.assertIn('blocked', context['Wi-Fi radio'])
        self.assertIn('unknown', context['Bluetooth connections'])

    def test_minimal_filter_keeps_paths_urls_emails_and_probe_errors(self):
        message = ('failed to open /home/armada/game/config; see https://armadaos.dev/help '
                   'contact=alice@example.com unit=user@1000.service')
        self.assertEqual(debug.redact_text(message), message)
        raw = REAL_COMMAND([sys.executable, '-c', 'import sys; print(sys.argv[1], file=sys.stderr); sys.exit(1)', message])
        self.assertEqual(raw['returncode'], 1)
        self.assertEqual(raw['error'].strip(), message)
        journal = debug.private_journal({'error': message, 'events': [
            {'message': message, 'unit': 'user@1000.service', 'transport': 'journal'}]})
        self.assertEqual(journal['error'], message)
        self.assertEqual(journal['events'][0]['message'], message)
        self.assertEqual(journal['privacy_omitted_messages'], 0)
        self.assertEqual(debug.redact_text('https://192.168.1.2/debug'), 'https://[IP]/debug')

    def trace_fixture(self, records, **kwargs):
        return dict({'status': 'captured', 'cpu_stats': {'cpu0':
            'overrun: 0\ncommit overrun: 0\ndropped events: 0'},
            'text': '\n'.join(f'worker-10 [000] .... {i + 1:.6f}: {event}: {message}'
                              for i, (event, message) in enumerate(records))}, **kwargs)

    def test_trace_summary_uses_sleep_entry_not_resume_state(self):
        trace = self.trace_fixture([
            ('clk_disable_complete', 'gcc_ufs_phy_axi_clk'),
            ('icc_set_bw', 'path=ufs-ddr dev=1d84000.ufshc node=ufs avg_bw=0 peak_bw=0 agg_avg=0 agg_peak=0'),
            ('ufshcd_system_suspend', '1d84000.ufshc: took 1 usecs, dev_state: UFS_SLEEP_PWR_MODE, link_state: UIC_LINK_HIBERN8_STATE, err 0'),
            ('suspend_resume', 'machine_suspend[2] begin'),
            ('suspend_resume', 'machine_suspend[2] end'),
            ('clk_enable_complete', 'gcc_ufs_phy_axi_clk'),
            ('icc_set_bw', 'path=ufs-ddr dev=1d84000.ufshc node=ufs avg_bw=100 peak_bw=100 agg_avg=100 agg_peak=100'),
            ('ufshcd_system_resume', '1d84000.ufshc: took 1 usecs, dev_state: UFS_ACTIVE_PWR_MODE, link_state: UIC_LINK_ACTIVE_STATE, err 0'),
        ])
        summary = debug.trace_summary(trace)
        entry = summary['sleep_entries'][0]
        self.assertEqual(entry['clocks']['gcc_ufs_phy_axi_clk']['enable'], 'disable')
        self.assertEqual(entry['bandwidth'][0]['peak'], 0)
        self.assertIn('UIC_LINK_HIBERN8_STATE', entry['ufs']['1d84000.ufshc'])
        self.assertEqual(summary['coverage'], 'no buffer loss reported')

    def test_trace_summary_keeps_sleep_and_wake_words_distinct(self):
        trace = self.trace_fixture([
            ('suspend_resume', 'machine_suspend[1] begin'),
            ('rpmh_send_msg', 'apps_rsc: tcs(m): 3 [sleep] cmd(n): 0 msgid: 0x10008 addr: 0x50030 data: 0x60000001 complete: 0'),
            ('rpmh_send_msg', 'apps_rsc: tcs(m): 5 [wake] cmd(n): 0 msgid: 0x10008 addr: 0x50030 data: 0x60004001 complete: 1'),
        ])
        commands = debug.trace_summary(trace)['rpmh_commands']
        self.assertEqual([(c['state'], c['word']) for c in commands], [('sleep', '0x60000001'), ('wake', '0x60004001')])
        with contextlib.redirect_stdout(io.StringIO()) as out:
            debug.trace_report(trace)
        self.assertIn('sleep=0x60000001; wake=0x60004001', out.getvalue())

    def test_runtime_accounting_preserves_counts_at_each_entry(self):
        trace = self.trace_fixture([
            ('rpm_usage', '89c000.serial flags-4 cnt-1  dep-0  auto-1 p-0 irq-0 child-1'),
            ('rpm_suspend', 'genpd:2:89c000.serial flags-a cnt-0  dep-0  auto-1 p-0 irq-0 child-0'),
            ('rpm_return_int', 'rpm_suspend+0x10/0x30:genpd:2:89c000.serial ret=-16'),
            ('suspend_resume', 'machine_suspend[1] begin'),
            ('suspend_resume', 'machine_suspend[1] end'),
            ('rpm_resume', '89c000.serial flags-4 cnt-2  dep-1  auto-1 p-1 irq-0 child-2'),
            ('rpm_return_int', 'rpm_resume+0x10/0x30:89c000.serial ret=1'),
            ('rpm_return_int', 'rpm_suspend+0x10/0x30:genpd:2:89c000.serial ret=0'),
            ('suspend_resume', 'machine_suspend[1] begin'),
        ])
        summary = debug.trace_summary(trace)
        first, second = [entry['runtime_accounting'] for entry in summary['sleep_entries']]
        self.assertEqual(first['89c000.serial']['last']['usage'], 1)
        self.assertEqual(first['89c000.serial']['last']['children'], 1)
        self.assertEqual(first['89c000.serial']['calls'], {})
        self.assertEqual(first['89c000.serial']['returns'], {})
        self.assertEqual(second['89c000.serial']['last']['usage'], 2)
        self.assertEqual(second['89c000.serial']['calls'], {'rpm_resume': 1})
        self.assertEqual(first['genpd:2:89c000.serial']['last']['flags'], 10)
        self.assertEqual(first['genpd:2:89c000.serial']['returns'], {'rpm_suspend+0x10/0x30 ret=-16': 1})
        self.assertEqual(summary['parse_failures'], 0)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            debug.trace_report(trace)
        self.assertIn('89c000.serial: usage=1, children=1, disable_depth=0, pending=0', out.getvalue())
        self.assertIn('rpm_suspend+0x10/0x30 ret=-16 (1x)', out.getvalue())
        self.assertNotIn('ret=1 (1x)', out.getvalue())

    def test_runtime_accounting_negative_counts_and_repeated_returns(self):
        trace = self.trace_fixture([
            ('rpm_idle', 'uart flags-0 cnt--1 dep-2  auto-0 p-1 irq-1 child-0'),
            ('rpm_return_int', 'rpm_idle:uart ret=-11'),
            ('rpm_return_int', 'rpm_idle:uart ret=-11'),
            ('rpm_status', 'uart status=RPM_ACTIVE'),
            ('suspend_resume', 'machine_suspend[2] begin'),
        ])
        entry = debug.trace_summary(trace)['sleep_entries'][0]
        self.assertEqual(entry['runtime_accounting']['uart']['last']['usage'], -1)
        self.assertEqual(entry['runtime_accounting']['uart']['returns'], {'rpm_idle ret=-11': 2})
        self.assertEqual(entry['runtime_accounting']['uart']['calls'], {'rpm_idle': 1})
        self.assertEqual(entry['runtime']['uart'], 'RPM_ACTIVE')

    def test_runtime_accounting_absent_or_malformed_is_not_clean_evidence(self):
        for records in ([], [('rpm_usage', 'uart unexpected-format'), ('rpm_return_int', 'uart invalid')]):
            trace = self.trace_fixture(records + [('suspend_resume', 'machine_suspend[2] begin')])
            with contextlib.redirect_stdout(io.StringIO()) as out:
                debug.trace_report(trace)
            self.assertIn('counts and operation outcomes are unknown', out.getvalue())
            summary = debug.trace_summary(trace)
            self.assertEqual(summary['parse_failures'], len(records))
            if records:
                self.assertIn('incomplete', summary['coverage'])

    def test_trace_report_deduplicates_path_requests_without_stale_aggregates(self):
        trace = self.trace_fixture([
            ('icc_set_bw', 'path=ufs-ddr dev=1d84000.ufshc node=ufs avg_bw=0 peak_bw=0 agg_avg=900 agg_peak=900'),
            ('icc_set_bw', 'path=ufs-ddr dev=1d84000.ufshc node=ddr avg_bw=0 peak_bw=0 agg_avg=400 agg_peak=400'),
            ('suspend_resume', 'machine_suspend[1] begin'),
        ])
        with contextlib.redirect_stdout(io.StringIO()) as out:
            debug.trace_report(trace)
        self.assertEqual(out.getvalue().count('1d84000.ufshc / ufs-ddr: avg=0 peak=0'), 1)
        self.assertNotIn('peak=900', out.getvalue())
        self.assertNotIn('avg=400', out.getvalue())

    def test_trace_callbacks_pair_interleaved_devices_and_keep_failure(self):
        trace = self.trace_fixture([
            ('device_pm_callback_start', 'dwc3 a.usb, parent: soc, platform_pm_suspend[suspend]'),
            ('device_pm_callback_start', 'ufshcd b.ufs, parent: soc, platform_pm_suspend[suspend]'),
            ('device_pm_callback_end', 'ufshcd b.ufs, err=-16'),
            ('device_pm_callback_end', 'dwc3 a.usb, err=0'),
        ])
        summary = debug.trace_summary(trace)
        self.assertEqual([(v['device'], v['error']) for v in summary['callbacks']], [('b.ufs', -16), ('a.usb', 0)])
        self.assertEqual(summary['unmatched_callbacks'], [])

    def test_trace_loss_or_missing_stats_never_looks_complete(self):
        for stats in ({}, {'cpu0': 'overrun: 10\ncommit overrun: 0\ndropped events: 0'}, {'cpu0': ''}):
            summary = debug.trace_summary(self.trace_fixture([], cpu_stats=stats))
            self.assertEqual(summary['coverage'], 'incomplete')
        self.assertEqual(debug.trace_summary(self.trace_fixture([], truncated=True))['coverage'], 'incomplete')

    def test_trace_unparsed_records_are_reported(self):
        trace = self.trace_fixture([])
        trace['text'] = 'unknown record layout'
        summary = debug.trace_summary(trace)
        self.assertEqual(summary['parse_failures'], 1)
        self.assertIn('incomplete', summary['coverage'])

    def test_unavailable_trace_does_not_abort_snapshot(self):
        debug.begin(self.cycle, trace=True)
        path = debug.cycle_path(self.cycle)
        self.assertTrue(debug.load(path / 'before.json')['complete'])
        self.assertEqual(debug.load(path / 'trace.json')['status'], 'unavailable')
        debug.finish(self.cycle)
        self.assertTrue(debug.load(path / 'after.json')['complete'])

    def test_trace_does_not_modify_an_existing_instance(self):
        instance = debug.trace_instance()
        self.write(instance / 'tracing_on', '1')
        self.write(instance / 'events/enable', '1')
        debug.begin(self.cycle, trace=True)
        self.assertEqual((instance / 'tracing_on').read_text(), '1')
        self.assertEqual((instance / 'events/enable').read_text(), '1')
        self.assertFalse((debug.STATE / 'trace-owner.json').exists())
        self.assertEqual(debug.load(debug.cycle_path(self.cycle) / 'trace.json')['status'], 'unavailable')

    def test_trace_setup_sigterm_does_not_leave_an_unowned_instance(self):
        script = r"""
import importlib.util, os, shutil, signal, sys
from pathlib import Path
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('debug', sys.argv[1])
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
root = Path(sys.argv[2])
for key in ('SYS', 'PROC', 'RUN', 'STATE'):
    setattr(d, key, root / key.lower())
instance = d.trace_instance()
instance.parent.mkdir(parents=True)
real_mkdir = Path.mkdir
def mkdir(path, *args, **kwargs):
    result = real_mkdir(path, *args, **kwargs)
    if path == instance:
        os.kill(os.getpid(), signal.SIGTERM)
    return result
with patch.object(Path, 'mkdir', mkdir), patch.object(d, 'trace_remove', shutil.rmtree):
    d.trace_start('a' * 32)
"""
        child = subprocess.run([sys.executable, '-c', script, str(LIB), str(self.root)])
        self.assertEqual(child.returncode, -15)
        owner = debug.load(debug.STATE / 'trace-owner.json')
        self.assertTrue(not debug.trace_instance().exists() or owner is not None)

    def test_trace_finish_stops_before_reading_and_cleans_on_read_failure(self):
        path = debug.cycle_path(self.cycle)
        debug.save(path / 'trace.json', {'status': 'recording'})
        debug.save(debug.STATE / 'trace-owner.json', {'cycle_id': self.cycle, 'boot_id': 'boot-one'})
        instance = debug.trace_instance()
        self.write(instance / 'tracing_on', '1')
        def remove(p):
            self.assertEqual((p / 'tracing_on').read_text(), '0')
        with patch.object(debug, 'trace_remove', side_effect=remove) as cleanup:
            debug.trace_finish(self.cycle)
        cleanup.assert_called_once()
        self.assertEqual(debug.load(path / 'trace.json')['status'], 'failed')
        self.assertFalse((debug.STATE / 'trace-owner.json').exists())

    def test_stop_trace_retries_cleanup_only_for_the_requested_owner(self):
        for owner in (self.cycle, 'b' * 32):
            debug.save(debug.STATE / 'trace-owner.json', {'cycle_id': owner, 'boot_id': 'boot-one'})
            with patch.object(sys, 'argv', ['armada-sleep-debug', 'stop-trace', self.cycle]), patch.dict(
                    os.environ, {'ARMADA_SLEEP_DEBUG_ALLOW_NONROOT': '1'}):
                with patch.object(debug, 'trace_finish'), patch.object(debug, 'trace_restore') as cleanup:
                    debug.main()
                    self.assertEqual(cleanup.call_count, int(owner == self.cycle))

    def test_trace_after_reboot_never_reads_another_buffer(self):
        path = debug.cycle_path(self.cycle)
        debug.save(path / 'trace.json', {'status': 'recording'})
        debug.save(debug.STATE / 'trace-owner.json', {'cycle_id': self.cycle, 'boot_id': 'old-boot'})
        with patch.object(debug, 'trace_remove') as cleanup:
            debug.trace_finish(self.cycle)
        cleanup.assert_not_called()
        self.assertIn('previous boot', debug.load(path / 'trace.json')['error'])

    def test_report_multiline_values_are_readable_and_unknown_is_not_zero(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            debug.render({'os_release': 'NAME="Armada"\nVERSION="test"', 'hook_sha256': None})
        self.assertIn('  NAME="Armada"\n  VERSION="test"', out.getvalue())
        self.assertNotIn('\\n', out.getvalue())
        self.assertIn('Unavailable: hook_sha256', out.getvalue())

    def test_journal_exports_all_captured_messages(self):
        event = {'message': 'An ordinary unrelated message', 'timestamp_us': '123000000',
                 'transport': 'kernel', 'unit': None}
        with contextlib.redirect_stdout(io.StringIO()) as out:
            debug.journal_report({'status': 'complete', 'events': [event]})
        self.assertIn(event['message'], out.getvalue())
        self.assertIn('All 1 captured journal events', out.getvalue())

    def test_success_and_full_irq_name(self):
        before, after, meta = self.snapshots()
        result = debug.summarize(before, after, meta)
        self.assertEqual(result['success_delta'], 1)
        self.assertEqual(result['wake_actions'], 'Hall Lid Sensor')
        self.assertEqual(result['battery']['battery']['charge_counter_delta_uAh'], -10000)
        self.assertTrue(result['capture_complete'])

    def test_failed_attempt_is_reportable(self):
        debug.begin(self.cycle)
        self.write(debug.SYS / 'power/suspend_stats/fail', '1')
        self.write(debug.SYS / 'power/suspend_stats/last_failed_dev', '2-005d')
        self.write(debug.SYS / 'power/suspend_stats/last_failed_errno', '-11')
        with patch.dict(os.environ, {'SERVICE_RESULT': 'exit-code', 'EXIT_CODE': 'exited', 'EXIT_STATUS': '1'}):
            debug.finish(self.cycle)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            debug.report(self.cycle)
        self.assertIn('Result: failed', out.getvalue())
        self.assertIn('2-005d', out.getvalue())
        self.assertIn('fail_delta: 1', out.getvalue())

    def test_next_cycle_does_not_overwrite_previous(self):
        self.snapshots()
        path = debug.cycle_path(self.cycle)
        before = (path / 'before.json').read_bytes()
        after = (path / 'after.json').read_bytes()
        debug.begin('b' * 32)
        self.write(debug.SYS / 'class/power_supply/battery/charge_counter', '1')
        debug.finish(self.cycle)
        self.assertEqual((path / 'before.json').read_bytes(), before)
        self.assertEqual((path / 'after.json').read_bytes(), after)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            debug.report(self.cycle)
        self.assertIn('charge_counter_delta_uAh: -10000', out.getvalue())

    def test_previous_boot_never_subtracts_counters(self):
        debug.begin(self.cycle)
        self.write(debug.PROC / 'sys/kernel/random/boot_id', 'boot-two')
        self.write(debug.SYS / 'power/suspend_stats/success', '0')
        debug.finish(self.cycle)
        path = debug.cycle_path(self.cycle)
        result = debug.summarize(debug.load(path / 'before.json'), debug.load(path / 'after.json'), debug.load(path / 'attempt.json'))
        self.assertEqual(result['outcome'], 'incomplete-previous-boot')
        self.assertNotIn('success_delta', result)
        self.assertNotIn('qcom', result)

    def test_reboot_can_recover_before_snapshot(self):
        debug.begin(self.cycle)
        import shutil
        shutil.rmtree(debug.cycle_path(self.cycle))
        self.write(debug.PROC / 'sys/kernel/random/boot_id', 'boot-two')
        debug.finish(self.cycle)
        self.assertIsNotNone(debug.load(debug.cycle_path(self.cycle) / 'before.json'))
        self.assertEqual(debug.load(debug.cycle_path(self.cycle) / 'attempt.json')['outcome'], 'incomplete-previous-boot')

    def test_journal_uses_normalized_boot_id(self):
        boot_id = '01234567-89ab-cdef-0123-456789abcdef'
        self.write(debug.PROC / 'sys/kernel/random/boot_id', boot_id)
        before, after, meta = self.snapshots()
        event = {'MESSAGE': list(b'rsinput: MCU \x02 peer aa:bb:cc:dd:ee:ff'), '_TRANSPORT': 'kernel'}
        with patch.object(debug, 'command', return_value={'status': 'complete', 'text': json.dumps(event)}) as cmd:
            result = debug.capture_journal(debug.cycle_path(self.cycle), before, after)
        self.assertEqual(result['events'][0]['message'], r'rsinput: MCU \x02 peer [MAC]')
        args = cmd.call_args.args[0]
        self.assertEqual(args[args.index('-b') + 1], '0123456789abcdef0123456789abcdef')

    def test_reboot_report_keeps_original_boot_journal_without_counter_deltas(self):
        debug.begin(self.cycle)
        import shutil
        shutil.rmtree(debug.cycle_path(self.cycle))
        self.write(debug.PROC / 'sys/kernel/random/boot_id', 'boot-two')
        debug.finish(self.cycle)
        event = {'MESSAGE': 'PM: suspend entry (s2idle)', '_TRANSPORT': 'kernel',
                 '__REALTIME_TIMESTAMP': '123', '__MONOTONIC_TIMESTAMP': '12'}
        with patch.object(debug, 'command', return_value={
                'status': 'complete', 'text': json.dumps(event), 'truncated': False}) as cmd:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                debug.report(self.cycle)
        args = cmd.call_args.args[0]
        self.assertEqual(args[args.index('-b') + 1], 'bootone')
        self.assertFalse(any(x.startswith('--until=') for x in args))
        self.assertIn('original boot after prepare; completion unavailable', out.getvalue())
        self.assertIn('PM: suspend entry (s2idle)', out.getvalue())
        self.assertNotIn('"success_delta"', out.getvalue())

    def test_service_restart_and_process_changes_are_explicit(self):
        before, after, meta = self.snapshots()
        for snap, pid, restarts in ((before, 12, 0), (after, 50, 1)):
            snap['groups']['health']['data']['services'] = {
                'status': 'complete',
                'text': f'Id=armada-powerd.service\nMainPID={pid}\nNRestarts={restarts}\nResult=success\n'}
        result = debug.summarize(before, after, meta)['service_changes']['armada-powerd.service']
        self.assertEqual(result['restart_delta'], 1)
        self.assertEqual(result['changed']['MainPID'], {'before': '12', 'after': '50'})

    def test_fake_mode_labels_native_counters_inapplicable(self):
        before, after, meta = self.snapshots()
        before['groups']['identity']['data']['device']['text'] = 'ARMADA_SUSPEND_MODE=fake\n'
        result = debug.summarize(before, after, meta)
        self.assertEqual(result['native_counter_scope'], 'not applicable to fake suspend')
        self.assertFalse(debug.data(before, 'fake_suspend')['active'])

    def test_reset_dsp_counters_are_invalid(self):
        before, after, meta = self.snapshots()
        after['groups']['qcom']['data']['adsp'] = 'Count: 1\nAccumulated Duration: 1'
        result = debug.summarize(before, after, meta)['qcom']['adsp']
        self.assertIsNone(result['count_delta'])
        self.assertNotIn('sleep_pct_of_window', result)

    def test_zero_pcm_does_not_imply_audio_culprit(self):
        self.write(debug.PROC / 'asound/card0/pcm0p/sub0/status', 'closed')
        before, after, meta = self.snapshots()
        result = debug.summarize(before, after, meta)
        self.assertEqual(result['open_pcms_at_prepare'], 0)
        self.assertIn('alone does not identify a cause', result['audio_attribution'])

    def test_pcm_owner_is_recorded(self):
        self.write(debug.PROC / '42/status', 'Name:\tpipewire\nState:\tS (sleeping)')
        self.write(debug.PROC / '42/comm', 'pipewire')
        (debug.PROC / '42/fd').mkdir()
        (debug.PROC / '42/fd/3').symlink_to('/dev/snd/pcmC0D0p')
        self.assertEqual(debug.processes()['pcm_owners'][0]['pid'], '42')

    def test_partial_capture_preserves_prior_groups_and_probe_name(self):
        with patch.object(debug, 'health', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                debug.begin(self.cycle)
        before = debug.load(debug.cycle_path(self.cycle) / 'before.json')
        self.assertFalse(before['complete'])
        self.assertEqual(before['groups']['health']['status'], 'in-progress')
        self.assertEqual(before['groups']['battery']['data']['battery']['charge_counter'], '1000000')
        with contextlib.redirect_stdout(io.StringIO()) as out:
            debug.report(self.cycle)
        self.assertIn('snapshots complete: no', out.getvalue())

    def test_irq_identity_change_is_not_a_counter_delta(self):
        before, after, meta = self.snapshots()
        before['groups']['interrupts']['data'] = '21: 5 2 chip 100 Edge old_device'
        after['groups']['interrupts']['data'] = '21: 10 3 chip 101 Edge different_device'
        changes = debug.summarize(before, after, meta)['irq_changes']
        self.assertIsNone(changes[0]['delta'])

    def test_overrun_and_first_error_survive_repetition(self):
        events = [{'message': 'Goodix: suspend failed -11', 'unit': None, 'transport': 'kernel', 'timestamp_us': '1'}]
        events += [{'message': 'UFS timestamp failed -22', 'unit': None, 'transport': 'kernel', 'timestamp_us': str(i)} for i in range(1000)]
        events += [{'message': '/dev/kmsg buffer overrun, some messages lost.', 'unit': None, 'transport': 'kernel', 'timestamp_us': '1002'}]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            debug.journal_report({'events': events, 'status': 'complete'})
        self.assertIn('Capture: incomplete', out.getvalue())
        self.assertIn('Goodix: suspend failed -11', out.getvalue())
        self.assertIn('callback coverage is not inferred', out.getvalue())
        self.assertIn('UFS timestamp failed -22: 1000', out.getvalue())

    def test_battery_endpoints_and_conflicting_supply_status(self):
        before, after, meta = self.snapshots()
        after['groups']['battery']['data']['ucsi'] = {'online': '1', 'status': 'Charging'}
        result = debug.summarize(before, after, meta)
        self.assertTrue(result['charger_conditions']['after']['conflicting_or_mixed_status'])
        self.assertEqual(result['battery']['battery']['before']['charge_counter'], '1000000')

    def test_wall_clock_change_does_not_change_elapsed(self):
        before, after, meta = self.snapshots()
        before['started'] = {'wall': 5000, 'boottime': 100, 'monotonic': 50}
        after['started'] = {'wall': 4000, 'boottime': 200, 'monotonic': 55}
        result = debug.summarize(before, after, meta)
        self.assertEqual(result['window_seconds'], 100)
        self.assertEqual(result['timekeeping_suspended_seconds'], 95)

    def test_restore_only_owned_debug_settings(self):
        self.write(debug.SYS / 'power/pm_debug_messages', '1')
        self.write(debug.SYS / 'power/pm_print_times', '0')
        debug.debug_settings(enable=True)
        self.assertEqual(debug.read(debug.SYS / 'power/pm_print_times'), '1')
        debug.debug_settings()
        self.assertEqual(debug.read(debug.SYS / 'power/pm_debug_messages'), '1')
        self.assertEqual(debug.read(debug.SYS / 'power/pm_print_times'), '0')

    def test_attempt_path_cannot_escape_state_directory(self):
        with self.assertRaises(ValueError):
            debug.cycle_path('../../etc')

    def test_command_timeout_and_output_limit(self):
        result = REAL_COMMAND([sys.executable, '-c', 'import time; time.sleep(10)'], timeout=0.05)
        self.assertEqual(result['status'], 'timeout')
        result = REAL_COMMAND([sys.executable, '-c', 'print("x" * 10000)'], limit=1024)
        self.assertTrue(result['truncated'])
        self.assertLessEqual(len(result['text']), 1024)

    def test_pulse_client_fallback(self):
        payload = [{'index': 4, 'sink': 2, 'corked': False,
                    'properties': {'application.name': 'Game', 'application.process.id': '42'}}]
        with patch.object(Path, 'is_file', return_value=False), patch.object(debug, 'command', return_value={
                'status': 'complete', 'text': json.dumps(payload), 'returncode': 0}):
            with patch.dict(os.environ, {'ARMADA_SESSION_USER': __import__('pwd').getpwuid(os.getuid()).pw_name}):
                result = REAL_PIPEWIRE()
        self.assertEqual(result['source'], 'pipewire-pulse')
        self.assertEqual(result['sink_inputs'][0]['properties']['application.name'], 'Game')

    def test_unprepared_collect_reports_unknown_measurements(self):
        with patch.object(sys, 'argv', ['armada-sleep-debug', 'collect']), patch.dict(
                os.environ, {'ARMADA_SLEEP_DEBUG_ALLOW_NONROOT': '1'}):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                debug.main()
        self.assertIn('missing, cross-boot or invalid baseline', out.getvalue())
        self.assertNotIn('"success_delta"', out.getvalue())

    def test_failed_formatter_keeps_partial_report(self):
        cli = self.root / 'collector'
        self.write(cli, '#!/bin/bash\necho "partial evidence"\necho "Alice private formatter error" >&2\nexit 1\n')
        cli.chmod(0o755)
        (self.root / 'armada/sleep-debug' / self.cycle).mkdir(parents=True)
        owner = __import__('pwd').getpwuid(os.getuid()).pw_name
        env = dict(os.environ, ARMADA_SLEEP_DEBUG_COMMAND=str(cli), ARMADA_SLEEP_DEBUG_RUN_ROOT=str(self.root),
                   ARMADA_SLEEP_DEBUG_REPORT_DIR=str(self.root / 'Documents/sleep-logs'), ARMADA_SESSION_USER=owner)
        subprocess.run(['bash', str(HOOK), 'collect-report', self.cycle], env=env, check=True)
        report = next((self.root / 'Documents/sleep-logs').glob('*.txt')).read_text()
        self.assertIn('partial evidence', report)
        self.assertIn('report_incomplete=collector failed', report)
        self.assertNotIn('Alice', report)
        self.assertIn('Alice', (self.root / 'armada/sleep-debug' / self.cycle / 'formatter.stderr').read_text())
        self.assertEqual((self.root / 'Documents').stat().st_uid, os.getuid())
        self.assertEqual((self.root / 'Documents').stat().st_mode & 0o777, 0o755)

    def test_automatic_hook_completes_failed_attempt_then_exports_same_id(self):
        bindir = self.root / 'bin'
        bindir.mkdir()
        cli = bindir / 'collector'
        self.write(cli, '#!/bin/bash\nprintf "%s|%s|%s\\n" "$*" "${SERVICE_RESULT:-}" "${EXIT_STATUS:-}" >>"$TEST_CALLS"\nif [[ $1 == begin ]]; then mkdir -p "$ARMADA_SLEEP_DEBUG_RUN_ROOT/armada/sleep-debug/$2"; touch "$ARMADA_SLEEP_DEBUG_RUN_ROOT/armada/sleep-debug/$2/attempt.json"; fi\n')
        runner = bindir / 'runner'
        self.write(runner, '#!/bin/bash\nprintf "%s\\n" "$*" >>"$TEST_RUNNER"\n')
        envcmd = bindir / 'env'
        self.write(envcmd, '#!/bin/bash\necho ARMADA_SUSPEND_MODE=s2idle\n')
        for p in (cli, runner, envcmd):
            p.chmod(0o755)
        env = dict(os.environ, ARMADA_SLEEP_DEBUG_COMMAND=str(cli), ARMADA_SLEEP_DEBUG_DEVICE_ENV=str(envcmd),
                   ARMADA_SLEEP_DEBUG_RUN_ROOT=str(self.root), ARMADA_SLEEP_DEBUG_SYSTEMD_RUN=str(runner),
                   TEST_CALLS=str(self.root / 'calls'), TEST_RUNNER=str(self.root / 'runner'),
                   INVOCATION_ID=self.cycle, SERVICE_RESULT='exit-code', EXIT_STATUS='1')
        subprocess.run(['bash', str(HOOK), 'prepare'], env=env, check=True)
        subprocess.run(['bash', str(HOOK), 'collect'], env=env, check=True)
        self.assertIn('finish ' + self.cycle + '|exit-code|1', (self.root / 'calls').read_text())
        self.assertIn('collect-report ' + self.cycle, (self.root / 'runner').read_text())

    def test_plugin_migrates_existing_success_only_hook(self):
        sys.path.insert(0, str(PUBLIC_ROOT / 'decky/armada-control/py_modules'))
        spec = importlib.util.spec_from_file_location('armada_control.system_review', PLUGIN)
        plugin = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin)
        plugin.SLEEP_DEBUG_COMMAND = self.root / 'collector'
        plugin.SLEEP_DEBUG_MODULE = self.root / 'module.py'
        plugin.SLEEP_LOG_HOOK_SOURCE = HOOK
        plugin.SLEEP_LOG_HOOK = self.root / 'hook'
        plugin.SLEEP_LOG_DROPIN = self.root / 'dropin'
        plugin.SLEEP_DEBUG_COMMAND.touch()
        plugin.SLEEP_DEBUG_MODULE.touch()
        plugin.SLEEP_LOG_DROPIN.write_text('[Service]\nExecStartPost=old-hook\n')
        with patch.object(plugin, 'set_sleep_logs_enabled', side_effect=RuntimeError('reload failed')):
            self.assertTrue(plugin.get_sleep_logs_enabled())
        with patch.object(plugin.subprocess, 'run'), patch.object(plugin, 'run_cmd') as run:
            self.assertTrue(plugin.get_sleep_logs_enabled())
            self.assertIn('ExecStopPost=', plugin.SLEEP_LOG_DROPIN.read_text())
            self.assertNotIn('ExecStartPost=', plugin.SLEEP_LOG_DROPIN.read_text())
            self.assertEqual(plugin.SLEEP_LOG_HOOK.read_bytes(), HOOK.read_bytes())
            plugin.set_sleep_logs_enabled(False)
            run.assert_called_once_with([str(plugin.SLEEP_DEBUG_COMMAND), 'restore'])
            self.assertFalse(plugin.SLEEP_LOG_DROPIN.exists())


if __name__ == '__main__':
    unittest.main()
