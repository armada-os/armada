"""Capture suspend attempts before formatting their diagnostic reports."""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import uuid

SCHEMA = 3
SYS = Path(os.environ.get('ARMADA_SLEEP_DEBUG_SYS_ROOT', '/sys'))
PROC = Path(os.environ.get('ARMADA_SLEEP_DEBUG_PROC_ROOT', '/proc'))
RUN = Path(os.environ.get('ARMADA_SLEEP_DEBUG_RUN_ROOT', '/run')) / 'armada/sleep-debug'
STATE = Path(os.environ.get('ARMADA_SLEEP_DEBUG_STATE_DIR', '/var/tmp/armada-sleep-debug'))
JOURNAL = os.environ.get('ARMADA_SLEEP_DEBUG_JOURNALCTL', '/usr/bin/journalctl')
SYSTEMCTL = os.environ.get('ARMADA_SLEEP_DEBUG_SYSTEMCTL', '/usr/bin/systemctl')
DEVICE_ENV = os.environ.get('ARMADA_SLEEP_DEBUG_DEVICE_ENV', '/usr/libexec/armada/device-env')
SCRIPT = os.environ.get('ARMADA_SLEEP_DEBUG_COMMAND', '/usr/bin/armada-sleep-debug')

TRACE_EVENTS = (
    'power/suspend_resume', 'power/device_pm_callback_start', 'power/device_pm_callback_end',
    'rpm/rpm_status', 'rpm/rpm_usage', 'rpm/rpm_idle', 'rpm/rpm_suspend',
    'rpm/rpm_resume', 'rpm/rpm_return_int',
    'clk/clk_enable_complete', 'clk/clk_disable_complete',
    'clk/clk_prepare_complete', 'clk/clk_unprepare_complete',
    'regulator/regulator_enable_complete', 'regulator/regulator_disable_complete',
    'interconnect/icc_set_bw', 'interconnect/icc_set_bw_end',
    'rpmh/rpmh_send_msg',
    'ufs/ufshcd_system_suspend', 'ufs/ufshcd_system_resume',
    'ufs/ufshcd_wl_suspend', 'ufs/ufshcd_wl_resume',
    'ufs/ufshcd_clk_gating', 'ufs/ufshcd_profile_hibern8',
)
TRACE_FILTERS = {
    **{event: '!(name ~ "genpd:*:cpu*")' for event in TRACE_EVENTS if event.startswith('rpm/')},
    # RPMh state 2 is active-only; retain sleep and wake requests.
    'rpmh/rpmh_send_msg': 'state != 2',
}
TRACE_LIMIT = 8_000_000


def trace_instance():
    return SYS / 'kernel/tracing/instances/armada-sleep-debug'


def trace_remove(instance):
    (instance / 'tracing_on').write_text('0')
    (instance / 'events/enable').write_text('0')
    instance.rmdir()


def trace_start(cycle):
    path = cycle_path(cycle)
    instance = trace_instance()
    result = {'status': 'starting', 'enabled_events': [], 'unavailable_events': [],
              'started': clock(), 'buffer_kb_per_cpu': 1024, 'filters': {}, 'event_errors': {}}
    save(path / 'trace.json', result)
    created = False
    # Defer the hook's SIGTERM until trace ownership and setup cleanup are recorded.
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
    try:
        instance.mkdir()
        created = True
        save(STATE / 'trace-owner.json', {'cycle_id': cycle,
             'boot_id': read(PROC / 'sys/kernel/random/boot_id')})
        (instance / 'tracing_on').write_text('0')
        (instance / 'buffer_size_kb').write_text('1024')
        (instance / 'trace_clock').write_text('boot')
        for event in TRACE_EVENTS:
            try:
                if event in TRACE_FILTERS:
                    (instance / 'events' / event / 'filter').write_text(TRACE_FILTERS[event])
                    result['filters'][event] = TRACE_FILTERS[event]
                (instance / 'events' / event / 'enable').write_text('1')
                result['enabled_events'].append(event)
            except OSError as exc:
                result['unavailable_events'].append(event)
                result['event_errors'][event] = str(exc)
        if not result['enabled_events']:
            raise ValueError('No supported sleep trace events')
        result['status'] = 'recording'
        save(path / 'trace.json', result)
        (instance / 'tracing_on').write_text('1')
        (instance / 'trace_marker').write_text('armada_sleep_prepare ' + cycle)
    except (OSError, ValueError) as exc:
        result['status'] = 'unavailable'
        result['error'] = str(exc)
        if created:
            try:
                trace_remove(instance)
                (STATE / 'trace-owner.json').unlink(missing_ok=True)
            except OSError as cleanup:
                result['cleanup_error'] = str(cleanup)
        save(path / 'trace.json', result)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


def trace_finish(cycle):
    path = cycle_path(cycle)
    result = load(path / 'trace.json')
    if not result or result.get('status') not in ('starting', 'recording'):
        return
    owner = load(STATE / 'trace-owner.json') or {}
    if owner.get('cycle_id') != cycle or owner.get('boot_id') != read(PROC / 'sys/kernel/random/boot_id'):
        result.update(status='unavailable', error='Trace ownership lost or previous boot; memory buffer unavailable')
        save(path / 'trace.json', result)
        return
    instance = trace_instance()
    try:
        (instance / 'tracing_on').write_text('0')
        result['finished'] = clock()
        result['cpu_stats'] = {p.parent.name: read(p) for p in instance.glob('per_cpu/cpu*/stats')}
        with (instance / 'trace').open('rb') as stream:
            raw = stream.read(TRACE_LIMIT + 1)
        result['text'] = raw[:TRACE_LIMIT].decode(errors='replace')
        result['truncated'] = len(raw) > TRACE_LIMIT
        result['status'] = 'captured'
    except OSError as exc:
        result.update(status='failed', error=str(exc))
    finally:
        try:
            trace_remove(instance)
            (STATE / 'trace-owner.json').unlink(missing_ok=True)
        except OSError as exc:
            result['cleanup_error'] = str(exc)
        save(path / 'trace.json', result)


def trace_restore():
    owner = load(STATE / 'trace-owner.json') or {}
    if owner.get('boot_id') == read(PROC / 'sys/kernel/random/boot_id'):
        instance = trace_instance()
        if instance.exists():
            trace_remove(instance)
    (STATE / 'trace-owner.json').unlink(missing_ok=True)


def redact_text(value):
    value = re.sub(r'(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])', '[MAC]', value)
    value = re.sub(r'(?i)\bdev_(?:[0-9a-f]{2}_){5}[0-9a-f]{2}\b', 'device_[MAC]', value)
    value = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '[IP]', value)
    import ipaddress
    def ipv6(match):
        try:
            ipaddress.IPv6Address(match[0])
            return '[IP]'
        except ValueError:
            return match[0]
    value = re.sub(r'(?<![\w:])[0-9a-fA-F]*:[0-9a-fA-F:]+(?:%[\w.-]+)?', ipv6, value)
    lines = []
    for line in value.splitlines(keepends=True):
        if re.search(r'\b(?:ssid|essid)\b', line, re.I):
            line = '[network-name message omitted]' + ('\n' if line.endswith('\n') else '')
        lines.append(line)
    return ''.join(lines)


class PrivateOutput:
    def __init__(self, output):
        self.output = output
        self.pending = ''

    def write(self, value):
        self.pending += value
        lines = self.pending.split('\n')
        self.pending = lines.pop()
        for line in lines:
            self.output.write(redact_text(line) + '\n')
        return len(value)

    def flush(self):
        if self.pending:
            self.output.write(redact_text(self.pending))
            self.pending = ''
        self.output.flush()


def private_snapshot(snap):
    if not snap:
        return snap
    import copy
    snap = copy.deepcopy(snap)
    health_data = data(snap, 'health', {})
    health_data.pop('mounts', None)
    for path, values in data(snap, 'peripherals', {}).items():
        if path.startswith('class/input/') and values.get('id/bustype') == '0005':
            values.pop('name', None)
    pw = data(snap, 'pipewire', {})
    for entry in pw.get('sink_inputs', []) + pw.get('objects', []):
        props = entry.get('properties', entry.get('props', {}))
        for key in list(props):
            if key not in ('application.name', 'application.process.id', 'application.process.binary', 'media.class', 'client.id', 'device.id', 'api.alsa.path'):
                del props[key]
    store_data = data(snap, 'pstore', {})
    if 'files' in store_data:
        store_data['record_count'] = len(store_data.pop('files'))
        store_data['contents'] = 'omitted: crash records may contain personal data'
    return snap


def private_journal(journal):
    import copy
    result = copy.deepcopy(journal)
    result['reported_loss'] = bool(result.get('reported_loss')) or any(
        re.search(r'buffer overrun|messages? (?:lost|suppressed)|missed \d+ kernel', e.get('message', ''), re.I)
        for e in result.get('events', []))
    for event in result.get('events', []):
        message = redact_text(event.get('message', ''))
        unit = event.get('unit') or ''
        if re.match(r'(?:NetworkManager|wpa_supplicant|iwd|connman|bluetooth)(?:@[^.]+)?\.service$', unit):
            lines = []
            for line in message.splitlines(keepends=True):
                if re.search(r"\b(?:connection|profile)(?:\.id)?\s*(?:[:=]\s*)?['\"]|"
                             r'\b(?:name|alias)\s*[:=]|'
                             r'\b(?:connected|connecting|associating) (?:to|with) (?!\[MAC\]|\[IP\])', line, re.I):
                    line = '[network-name message omitted]' + ('\n' if line.endswith('\n') else '')
                lines.append(line)
            message = ''.join(lines)
        event['message'] = message
        if unit:
            event['unit'] = redact_text(unit)
    result['privacy_omitted_messages'] = sum(any(marker in e['message'] for marker in (
        '[message omitted for privacy;', '[network-name message omitted]', '[user path omitted]'))
        for e in result.get('events', []))
    if result.get('error'):
        result['error'] = redact_text(result['error'])
    return result


def read(path):
    try:
        return Path(path).read_text(errors='replace').strip()
    except OSError:
        return None


def load(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex)
    try:
        temp.write_text(json.dumps(value, indent=2) + '\n')
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def command(args, timeout=2, limit=2_000_000):
    with tempfile.TemporaryFile(dir=RUN) as output, tempfile.TemporaryFile(dir=RUN) as errors:
        try:
            import resource

            def bound_output():
                resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))

            proc = subprocess.Popen(args, stdout=output, stderr=errors, start_new_session=True,
                                    preexec_fn=bound_output)
        except OSError as exc:
            return {'status': 'unavailable', 'error': 'command unavailable', 'text': ''}
        status = 'complete'
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            status = 'timeout'
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                pass
        size = os.fstat(output.fileno()).st_size
        output.seek(0)
        errors.seek(0)
        return {'status': status if status != 'complete' else ('complete' if proc.returncode == 0 else 'failed'),
                'returncode': proc.returncode, 'truncated': size >= limit,
                'text': output.read(limit).decode(errors='replace'),
                'error': errors.read(4096).decode(errors='replace')}


def clock():
    return {'wall': time.time(), 'boottime': time.clock_gettime(time.CLOCK_BOOTTIME),
            'monotonic': time.monotonic()}


def fields(directory, names):
    return {name: read(directory / name) for name in names}


def supplies():
    names = ('type', 'status', 'online', 'present', 'health', 'temp', 'current_now',
             'voltage_now', 'power_now', 'charge_counter', 'charge_now', 'charge_full',
             'charge_full_design', 'capacity', 'usb_type')
    return {p.name: fields(p, names) for p in (SYS / 'class/power_supply').glob('*')}


def qcom():
    return {p.name: read(p) for p in (SYS / 'kernel/debug/qcom_stats').glob('*') if p.is_file()}


def processes():
    blocked = []
    owners = []
    for p in PROC.glob('[0-9]*'):
        status = read(p / 'status') or ''
        state = re.search(r'^State:\s+(\w)', status, re.M)
        if state and state[1] in ('D', 'T'):
            blocked.append({'pid': p.name, 'comm': read(p / 'comm'), 'state': state[1],
                            'wchan': read(p / 'wchan'), 'stack': read(p / 'stack')})
        try:
            for fd in (p / 'fd').iterdir():
                target = os.readlink(fd)
                if '/dev/snd/pcm' in target:
                    owners.append({'pid': p.name, 'comm': read(p / 'comm'), 'device': target})
        except OSError:
            continue
    return {'blocked': blocked, 'pcm_owners': owners}


def audio():
    return {'pcms': {str(p.relative_to(PROC)): read(p) for p in PROC.glob('asound/card*/pcm*/sub*/status')},
            'bias': {str(p.relative_to(SYS)): read(p) for p in SYS.glob('kernel/debug/asoc/*/dapm/bias_level')}}


def pipewire():
    user = os.environ.get('ARMADA_SESSION_USER', 'armada')
    import pwd
    try:
        uid = pwd.getpwnam(user).pw_uid
    except KeyError:
        return {'status': 'unavailable'}
    launcher = ['/usr/sbin/runuser', '-u', user, '--', 'env', f'XDG_RUNTIME_DIR=/run/user/{uid}']
    if not Path('/usr/bin/pw-dump').is_file():
        result = command(launcher + ['/usr/bin/pactl', '--format=json', 'list', 'sink-inputs'], timeout=1)
        try:
            inputs = json.loads(result.pop('text'))
            return dict(result, source='pipewire-pulse', sink_inputs=[
                {'index': x.get('index'), 'sink': x.get('sink'), 'corked': x.get('corked'),
                 'properties': {k: v for k, v in x.get('properties', {}).items()
                                if k in ('application.name', 'application.process.id',
                                         'application.process.binary', 'node.name')}} for x in inputs])
        except (ValueError, TypeError, AttributeError):
            result.pop('text', None)
            return dict(result, status='unavailable', source='pipewire-pulse')
    result = command(launcher + ['/usr/bin/pw-dump'], timeout=1)
    if result['status'] != 'complete' or result.get('truncated'):
        result.pop('text', None)
        return result
    try:
        entries = json.loads(result['text'])
        keys = ('application.name', 'application.process.id', 'application.process.binary',
                'node.name', 'media.class', 'client.id', 'device.id', 'api.alsa.path')
        return {'status': 'complete', 'objects': [
            {'id': x.get('id'), 'type': x.get('type'), 'state': x.get('info', {}).get('state'),
             'props': {k: v for k, v in x.get('info', {}).get('props', {}).items() if k in keys}}
            for x in entries if any(k in x.get('info', {}).get('props', {}) for k in keys)]}
    except (ValueError, TypeError, AttributeError):
        return {'status': 'invalid-output'}


def bluetooth_connections(probe):
    result = {k: probe[k] for k in ('status', 'returncode', 'truncated') if k in probe}
    if probe.get('status') != 'complete' or probe.get('truncated'):
        return result
    try:
        objects = json.loads(probe['text'])['data'][0]
        adapters, connected = [], []
        for path, interfaces in objects.items():
            def props(interface, keys):
                values = interfaces.get(interface, {})
                return {key: values.get(key, {}).get('data') for key in keys}
            if 'org.bluez.Adapter1' in interfaces:
                adapters.append(dict(props('org.bluez.Adapter1', (
                    'Powered', 'Discovering', 'Discoverable', 'Pairable')),
                    adapter=path.rsplit('/', 1)[-1]))
            device = props('org.bluez.Device1', ('Connected', 'Icon', 'Class',
                'Appearance', 'UUIDs', 'ServicesResolved', 'WakeAllowed', 'Paired', 'Trusted'))
            if device['Connected'] is True:
                device['device'] = 'connected-device-' + str(len(connected) + 1)
                device['Icon'] = device['Icon'] if device['Icon'] in ('input-gaming', 'input-keyboard', 'input-mouse', 'audio-headset', 'audio-headphones', 'audio-card', 'phone', 'computer') else 'other'
                device['supported_service_ids'] = [u[4:8] for u in (device.pop('UUIDs') or []) if re.fullmatch(r'0000[0-9a-f]{4}-0000-1000-8000-00805f9b34fb', u)]
                device['adapter'] = path.rsplit('/', 2)[-2]
                device['battery_percent'] = props('org.bluez.Battery1', ('Percentage',))['Percentage']
                connected.append(device)
        result.update(adapters=adapters, connected_devices=connected)
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        result['status'] = 'invalid-output'
    return result


def wifi_link(probe):
    result = {k: probe[k] for k in ('status', 'returncode', 'truncated') if k in probe}
    if probe.get('status') != 'complete' or probe.get('truncated'):
        return result
    raw = probe.get('text', '')
    result['connected'] = True if raw.startswith('Connected to ') else False if raw.startswith('Not connected') else None
    result['details'] = {}
    for line in raw.splitlines():
        key, sep, value = line.strip().partition(':')
        if sep and key in ('freq', 'signal', 'rx bitrate', 'tx bitrate', 'dtim period', 'beacon int'):
            number = re.match(r'^\s*(-?\d+(?:\.\d+)?)\b', value)
            if number:
                unit = ' dBm' if key == 'signal' else ' MBit/s' if key.endswith('bitrate') else ''
                result['details'][key] = number[1] + unit
    return result


def wifi_settings(probe, kind):
    result = {k: probe[k] for k in ('status', 'returncode', 'truncated') if k in probe}
    if probe.get('status') != 'complete' or probe.get('truncated'):
        return result
    raw = probe.get('text', '')
    if kind == 'power_save':
        match = re.search(r'^Power save: (on|off)$', raw.strip())
        result['text'] = 'Power save: ' + (match[1] if match else 'unknown')
    elif kind == 'wake_on_wlan':
        enabled = 'WoWLAN is enabled' in raw
        disabled = 'WoWLAN is disabled' in raw
        result['text'] = 'WoWLAN: ' + ('enabled' if enabled else 'disabled' if disabled else 'unknown')
        result['triggers'] = [label for phrase, label in (
            ('any activity', 'any activity'), ('disconnect', 'disconnect'), ('magic packet', 'magic packet'),
            ('GTK rekey', 'GTK rekey'), ('EAP identity', 'EAP identity'), ('4-way handshake', '4-way handshake'),
            ('pattern', 'packet pattern'), ('TCP', 'TCP wake')) if phrase in raw]
    else:
        fields = {}
        for key, pattern in (('channel', r'channel (\d+)'), ('frequency_mhz', r'channel \d+ \(([0-9.]+) MHz\)'),
                             ('width_mhz', r'width: (\d+) MHz'), ('txpower_dbm', r'txpower (-?[0-9.]+) dBm')):
            match = re.search(pattern, raw)
            fields[key] = match[1] if match else None
        result['details'] = fields
    return result


def connectivity():
    deadline = time.monotonic() + 2

    def query(args):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {'status': 'capture-budget-exhausted', 'text': ''}
        return command(args, timeout=min(0.6, remaining), limit=256_000)

    result = {'bluetooth': bluetooth_connections(query([
        '/usr/bin/busctl', '--system', '--auto-start=no', '--json=short', 'call',
        'org.bluez', '/', 'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects'])), 'wifi': []}
    interfaces = [p for p in sorted(SYS.glob('class/net/*')) if (p / 'phy80211').exists()]
    result['wifi_interfaces_omitted'] = max(0, len(interfaces) - 4)
    for p in interfaces[:4]:
        item = {'interface': 'wifi' + str(len(result['wifi'])), 'driver': (p / 'device/driver').resolve().name if (p / 'device/driver').exists() else None,
                'operstate': read(p / 'operstate'),
                'device_power': fields(p / 'device/power', ('runtime_status', 'control', 'wakeup'))}
        item['link'] = wifi_link(query(['/usr/bin/iw', 'dev', p.name, 'link']))
        item['power_save'] = wifi_settings(query(['/usr/bin/iw', 'dev', p.name, 'get', 'power_save']), 'power_save')
        phy = (p / 'phy80211').resolve().name
        item['wake_on_wlan'] = wifi_settings(query(['/usr/bin/iw', 'phy', phy, 'wowlan', 'show']), 'wake_on_wlan')
        item['channel'] = wifi_settings(query(['/usr/bin/iw', 'dev', p.name, 'info']), 'channel')
        result['wifi'].append(item)
    result['scope'] = 'before kernel suspend; automatic capture follows the sleep request; read-only queries, no scan; remote UUIDs describe supported services, not active profiles'
    return result


def health():
    services = command([SYSTEMCTL, 'show', '--no-pager',
                        '--property=Id,ActiveState,SubState,Result,NRestarts,MainPID,ExecMainStatus',
                        'armada-powerd.service', 'inputplumber.service', 'systemd-journald.service',
                        'NetworkManager.service'], timeout=1)
    return {'services': services, 'processes': processes(),
            'blocks': {p.name: fields(p, ('stat', 'inflight', 'ro', 'device/state'))
                       for p in SYS.glob('class/block/*')}}


def peripherals():
    result = {}
    patterns = ('class/backlight/*', 'class/rfkill/*', 'class/input/event*/device',
                'class/thermal/thermal_zone*', 'class/devfreq/*', 'bus/platform/devices/*usb*',
                'bus/platform/devices/*ufs*', 'bus/platform/devices/*remoteproc*',
                'bus/platform/devices/*sound*', 'bus/platform/devices/*i2c*',
                'bus/platform/devices/*dsi*', 'bus/platform/devices/*gpu*')
    names = ('name', 'type', 'state', 'soft', 'hard', 'brightness', 'actual_brightness',
             'bl_power', 'temp', 'cur_freq', 'min_freq', 'max_freq', 'governor',
             'power/runtime_status', 'power/control', 'power/wakeup')
    for pattern in patterns:
        for p in SYS.glob(pattern):
            values = {k: v for k, v in fields(p, names).items() if v is not None}
            if pattern == 'class/input/event*/device':
                values['id/bustype'] = read(p / 'id/bustype')
            result[str(p.relative_to(SYS))] = values
    return result


def journal_cursor():
    result = command([JOURNAL, '-b', '0', '-n', '1', '-o', 'json', '--no-pager'], timeout=1)
    try:
        entry = json.loads(result['text'].strip().splitlines()[-1])
        return {'cursor': entry['__CURSOR'], 'status': result['status']}
    except (ValueError, KeyError, IndexError):
        return {'status': 'unavailable'}


def wake_inventory():
    sources = {p.name: fields(p, ('name', 'active_count', 'event_count', 'wakeup_count',
                                'expire_count', 'device/power/wakeup'))
               for p in SYS.glob('class/wakeup/*')}
    rtc = {p.name: read(p / 'wakealarm') for p in SYS.glob('class/rtc/*')}
    lids = {}
    for p in SYS.glob('class/input/event*/device'):
        switches = read(p / 'capabilities/sw')
        if not switches:
            continue
        try:
            if not int(switches.split()[-1], 16) & 1:
                continue
        except ValueError:
            continue
        device = str(Path(os.environ.get('ARMADA_SLEEP_DEBUG_DEV_ROOT', '/dev')) / 'input' / p.parent.name)
        query = command([os.environ.get('ARMADA_SLEEP_DEBUG_EVTEST', '/usr/bin/evtest'),
                         '--query', device, 'EV_SW', 'SW_LID'], timeout=0.5)
        lids[p.parent.name] = {'state': {0: 'open', 10: 'closed'}.get(query.get('returncode'), 'unknown')}
    return {'sources': sources, 'rtc_alarms': rtc, 'lids': lids}


def pstore():
    count = sum(1 for root in (SYS / 'fs/pstore', Path('/var/lib/systemd/pstore'))
                for p in root.glob('*') if p.is_file())
    return {'status': 'available' if count else 'unavailable-or-empty', 'record_count': count,
            'contents': 'omitted: crash records may contain personal data'}


def fake_suspend():
    root = Path(os.environ.get('ARMADA_SLEEP_DEBUG_RUN_ROOT', '/run')) / 'armada'
    saved = root / 'fake-suspend'
    cgroup = read(saved / 'app-cgroup')
    return {'active': (root / 'fake-suspend.active').exists(),
            'wake_request_pending': (root / 'fake-suspend.wake').exists(),
            'saved_files': [p.name for p in saved.glob('*')],
            'app_cgroup': cgroup,
            'app_cgroup_freeze': read(SYS / ('fs/cgroup' + cgroup) / 'cgroup.freeze') if cgroup else None}


def identity():
    return {'kernel': read(PROC / 'sys/kernel/osrelease'), 'kernel_build': read(PROC / 'version'),
            'cmdline': read(PROC / 'cmdline'), 'device': command([DEVICE_ENV], timeout=1),
            'rpmh_command_db': read(SYS / 'kernel/debug/cmd-db'),
            'os_version': read('/usr/lib/armada/version'), 'os_release': read('/usr/lib/os-release'),
            'logger_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'hook_sha256': hashlib.sha256(Path('/etc/armada/sleep-debug-hook').read_bytes()).hexdigest()
            if Path('/etc/armada/sleep-debug-hook').is_file() else None}


def snapshot(path, phase):
    snap = {'schema': SCHEMA, 'boot_id': read(PROC / 'sys/kernel/random/boot_id'),
            'started': clock(), 'complete': False, 'groups': {}}
    save(path, snap)
    # power/wakeup_count blocks until wake events settle; use per-source counters.
    probes = [('suspend', lambda: {'stats': {p.name: read(p) for p in SYS.glob('power/suspend_stats/*') if p.is_file()},
                                  'mem_sleep': read(SYS / 'power/mem_sleep'),
                                  'wake_irq': read(SYS / 'power/pm_wakeup_irq'),
                                  'settings': fields(SYS / 'power', ('pm_debug_messages', 'pm_print_times', 'pm_async'))}),
              ('battery', supplies), ('qcom', qcom), ('audio', audio),
              ('interrupts', lambda: read(PROC / 'interrupts')),
              ('wake_sources', lambda: read(SYS / 'kernel/debug/wakeup_sources')),
              ('wake_actions', lambda: {p.parent.name: read(p) for p in SYS.glob('kernel/irq/*/actions')}),
              ('peripherals', peripherals), ('health', health),
              ('wake_inventory', wake_inventory), ('fake_suspend', fake_suspend), ('pstore', pstore), ('journal', journal_cursor)]
    if phase == 'before':
        probes += [('identity', identity), ('pipewire', pipewire), ('connectivity', connectivity)]
    for name, probe in probes:
        group = {'started': clock(), 'status': 'in-progress'}
        snap['groups'][name] = group
        save(path, snap)
        try:
            group['data'] = probe()
            group['status'] = 'complete'
        except (OSError, ValueError) as exc:
            group['status'] = 'failed'
            group['error'] = str(exc)
        snap = private_snapshot(snap)
        group = snap['groups'][name]
        group['finished'] = clock()
        snap['groups'][name] = group
        save(path, snap)
    snap['finished'] = clock()
    snap['complete'] = all(g['status'] == 'complete' for g in snap['groups'].values())
    snap = private_snapshot(snap)
    save(path, snap)
    return snap


def cycle_path(cycle):
    if not re.fullmatch(r'[a-f0-9]{32}', cycle):
        raise ValueError('Invalid sleep attempt ID')
    return RUN / cycle


def debug_settings(enable=False):
    path = STATE / 'debug-settings.json'
    boot = read(PROC / 'sys/kernel/random/boot_id')
    saved = load(path)
    if not enable:
        if saved and saved['boot_id'] == boot:
            for name, value in saved['values'].items():
                try:
                    (SYS / 'power' / name).write_text(value)
                except OSError:
                    pass
        path.unlink(missing_ok=True)
        return
    if not saved or saved['boot_id'] != boot:
        values = {name: read(SYS / 'power' / name) for name in ('pm_debug_messages', 'pm_print_times')}
        save(path, {'boot_id': boot, 'values': {k: v for k, v in values.items() if v is not None}})
    for name in ('pm_debug_messages', 'pm_print_times'):
        try:
            (SYS / 'power' / name).write_text('1')
        except OSError:
            pass


def begin(cycle, verbose=False, trace=False):
    path = cycle_path(cycle)
    path.mkdir(mode=0o700, parents=True, exist_ok=False)
    meta = {'schema': SCHEMA, 'cycle_id': cycle, 'boot_id': read(PROC / 'sys/kernel/random/boot_id'),
            'started': clock(), 'outcome': 'pending', 'verbose': verbose}
    save(path / 'attempt.json', meta)
    save(STATE / 'attempts' / cycle / 'attempt.json', meta)
    save(STATE / 'latest.json', {'cycle_id': cycle})
    if verbose:
        debug_settings(enable=True)
    snapshot(path / 'before.json', 'before')
    save(STATE / 'attempts' / cycle / 'before.json', load(path / 'before.json'))
    if trace:
        trace_start(cycle)
        save(STATE / 'attempts' / cycle / 'trace.json', load(path / 'trace.json'))
    return cycle


def hydrate(cycle):
    path = cycle_path(cycle)
    if not (path / 'attempt.json').exists():
        old = STATE / 'attempts' / cycle
        meta = load(old / 'attempt.json')
        if not meta:
            raise ValueError('Sleep attempt is unavailable')
        for name in ('attempt.json', 'before.json', 'after.json', 'journal.json', 'trace.json'):
            value = load(old / name)
            if value is not None:
                save(path / name, value)
    return path


def finish(cycle):
    path = hydrate(cycle)
    trace_finish(cycle)
    if (path / 'after.json').exists():
        return cycle
    try:
        with (path / 'capture-started').open('x'):
            pass
    except FileExistsError:
        return cycle
    meta = load(path / 'attempt.json')
    meta['service_result'] = os.environ.get('SERVICE_RESULT', 'manual')
    meta['exit_code'] = os.environ.get('EXIT_CODE')
    meta['exit_status'] = os.environ.get('EXIT_STATUS')
    meta['outcome'] = 'completion-capture-in-progress'
    save(path / 'attempt.json', meta)
    after = snapshot(path / 'after.json', 'after')
    meta['outcome'] = ('incomplete-previous-boot' if after['boot_id'] != meta['boot_id'] else
                       'failed' if meta['service_result'] not in ('success', 'manual') else 'returned')
    meta['finished'] = clock()
    save(path / 'attempt.json', meta)
    if meta.get('verbose'):
        debug_settings()
    return cycle


def data(snap, name, default=None):
    return (snap or {}).get('groups', {}).get(name, {}).get('data', default)


def integer(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def interval(before, after, group=None):
    if not before or not after or not before.get('boot_id') or before['boot_id'] != after.get('boot_id'):
        return None
    b = before.get('groups', {}).get(group, before) if group else before
    a = after.get('groups', {}).get(group, after) if group else after
    if not b or not a:
        return None
    elapsed = a['started']['boottime'] - b['started']['boottime']
    return elapsed if elapsed > 0 else None


def delta(before, after):
    b, a = integer(before), integer(after)
    return a - b if a is not None and b is not None and a >= b else None


def stat(raw, name):
    match = re.search(r'^' + re.escape(name) + r':\s*(\d+)', raw or '', re.M)
    return int(match[1]) if match else None


def irq_counts(raw):
    counts = {}
    for line in (raw or '').splitlines():
        parts = line.split()
        if not parts or not re.fullmatch(r'\d+:', parts[0]):
            continue
        i, total = 1, 0
        while i < len(parts) and parts[i].isdigit():
            total += int(parts[i])
            i += 1
        counts[parts[0][:-1]] = (total, ' '.join(parts[i:]))
    return counts


def service_changes(before, after):
    def services(snap):
        raw = data(snap, 'health', {}).get('services', {})
        if raw.get('status') != 'complete':
            return {}
        parsed = [dict(line.split('=', 1) for line in block.splitlines() if '=' in line)
                  for block in raw.get('text', '').strip().split('\n\n')]
        return {s['Id']: s for s in parsed if s.get('Id')}

    old, new = services(before), services(after)
    return {name: {'restart_delta': delta(old.get(name, {}).get('NRestarts'), values.get('NRestarts')),
                   'changed': {key: {'before': old[name].get(key), 'after': value}
                               for key, value in values.items()
                               if name in old and old[name].get(key) != value}}
            for name, values in new.items()}


def summarize(before, after, meta):
    result = {'cycle_id': meta['cycle_id'], 'outcome': meta['outcome'],
              'service_result': meta.get('service_result'),
              'capture_complete': bool(before and after and before.get('complete') and after.get('complete'))}
    if result['outcome'] == 'completion-capture-in-progress' and not meta.get('finished'):
        result['outcome'] = 'completion-capture-interrupted'
    mode = re.search(r'^ARMADA_SUSPEND_MODE=[\"\']?(fake|s2idle)',
                     data(before, 'identity', {}).get('device', {}).get('text', ''), re.M)
    result['configured_sleep_mode'] = mode[1] if mode else 'unknown'
    result['native_counter_scope'] = ('not applicable to fake suspend' if mode and mode[1] == 'fake'
                                      else 'kernel system-suspend counters')
    result['qcom_tick_hz'] = 19_200_000
    elapsed = interval(before, after)
    if elapsed is None:
        result['measurements'] = 'unavailable: missing, cross-boot or invalid baseline'
        return result
    result['window_seconds'] = round(elapsed, 3)
    active = after['started']['monotonic'] - before['started']['monotonic']
    result['timekeeping_suspended_seconds'] = round(max(0, elapsed - active), 3)
    result['awake_and_transition_seconds'] = round(max(0, active), 3)
    bstats = data(before, 'suspend', {}).get('stats', {})
    astats = data(after, 'suspend', {}).get('stats', {})
    for key in ('success', 'fail'):
        result[key + '_delta'] = delta(bstats.get(key), astats.get(key))
    if result['fail_delta']:
        result['failure'] = {k: v for k, v in astats.items() if k.startswith('last_failed')}
    result['wake_irq'] = data(after, 'suspend', {}).get('wake_irq')
    result['wake_actions'] = data(after, 'wake_actions', {}).get(result['wake_irq'])
    result['wake_irq_scope'] = 'last kernel wake IRQ; may be stale if this attempt did not sleep'
    irqs_before = irq_counts(data(before, 'interrupts'))
    changes = []
    for irq, (count, description) in irq_counts(data(after, 'interrupts')).items():
        old = irqs_before.get(irq)
        change = delta(old[0], count) if old and old[1] == description else None
        if change != 0:
            changes.append({'irq': irq, 'description': description, 'delta': change})
    result['irq_changes'] = sorted(changes, key=lambda x: x['delta'] or 0, reverse=True)[:40]
    result['irq_scope'] = 'capture interval including entry/resume; not evidence of in-sleep interrupts alone'
    result['qcom'] = {}
    secs = interval(before, after, 'qcom')
    for name, raw in data(after, 'qcom', {}).items():
        old = data(before, 'qcom', {}).get(name)
        count = delta(stat(old, 'Count'), stat(raw, 'Count'))
        duration = delta(stat(old, 'Accumulated Duration'), stat(raw, 'Accumulated Duration'))
        result['qcom'][name] = {'count_delta': count, 'duration_ticks_delta': duration}
        if count is not None and duration is not None and secs:
            result['qcom'][name]['sleep_seconds'] = round(duration / 19_200_000, 3)
            pct = duration / 19_200_000 / secs * 100
            result['qcom'][name]['sleep_pct_of_window'] = round(pct, 2) if pct <= 101 else None
        else:
            result['qcom'][name]['validity'] = 'missing baseline or counter reset'
    pcms = data(before, 'audio', {}).get('pcms', {})
    result['open_pcms_at_prepare'] = sum(bool(v and not v.startswith('closed')) for v in pcms.values()) if pcms else None
    result['audio_attribution'] = 'PCM snapshots and owners are evidence of open devices; low DSP residency alone does not identify a cause'
    result['battery'] = {}
    secs = interval(before, after, 'battery')
    for name, end in data(after, 'battery', {}).items():
        start = data(before, 'battery', {}).get(name, {})
        if end.get('type') != 'Battery' or not secs:
            continue
        b, a = integer(start.get('charge_counter')), integer(end.get('charge_counter'))
        item = {'window_seconds': round(secs, 3), 'before': start, 'after': end}
        if b is not None and a is not None:
            item['charge_counter_delta_uAh'] = a - b
            item['net_battery_current_mA'] = round((a - b) * 3.6 / secs, 1)
            full = integer(end.get('charge_full')) or integer(end.get('charge_full_design'))
            item['gauge_discontinuity_suspected'] = bool(
                (full and abs(a - b) > full) or
                (a > b and start.get('status') == end.get('status') == 'Discharging'))
        item['interpretation'] = 'gauge estimate over capture window, including transitions; not isolated sleep current'
        item['short_window'] = secs < 300
        result['battery'][name] = item
    result['charger_conditions'] = {}
    for phase, snap in (('before', before), ('after', after)):
        sources = data(snap, 'battery', {})
        connected = any(x.get('online') == '1' for x in sources.values())
        discharging = any(x.get('type') == 'Battery' and x.get('status') == 'Discharging' for x in sources.values())
        result['charger_conditions'][phase] = {'any_supply_online': connected, 'battery_discharging': discharging,
                                                'conflicting_or_mixed_status': connected and discharging}
    result['charger_endpoint_change'] = data(before, 'battery', {}) != data(after, 'battery', {}) and any(
        source.get('online') != data(before, 'battery', {}).get(name, {}).get('online')
        for name, source in data(after, 'battery', {}).items())
    result['service_changes'] = service_changes(before, after)
    result['blocked_tasks_scope'] = 'boundary snapshots; a blocked task alone does not establish a persistent hang'
    result['charger_transition_scope'] = 'endpoint states only; intermediate changes require journal evidence'
    return result


def capture_journal(path, before, after):
    saved = load(path / 'journal.json')
    if saved is not None:
        return saved
    cursor = data(before, 'journal', {}).get('cursor')
    if not cursor or not (before or {}).get('boot_id'):
        result = {'status': 'unavailable: no saved journal boundary', 'events': []}
    else:
        same_boot = interval(before, after) is not None
        args = [JOURNAL, '-b', before['boot_id'].replace('-', ''), '--after-cursor=' + cursor, '-o', 'json', '--no-pager']
        if same_boot:
            args += ['--until=@' + str(after.get('finished', after['started'])['wall'])]
        probe = command(args, timeout=4)
        probe['scope'] = 'attempt window' if same_boot else 'original boot after prepare; completion unavailable'
        events = []
        malformed = 0
        for line in probe.pop('text').splitlines():
            try:
                entry = json.loads(line)
                message = entry.get('MESSAGE', '')
                if isinstance(message, list):
                    message = bytes(message).decode(errors='backslashreplace')
                if not isinstance(message, str):
                    message = repr(message)
                message = re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', lambda m: f'\\x{ord(m[0]):02x}', message)
                events.append({'timestamp_us': entry.get('__REALTIME_TIMESTAMP'),
                               'monotonic_us': entry.get('__MONOTONIC_TIMESTAMP'),
                               'unit': entry.get('_SYSTEMD_UNIT'), 'transport': entry.get('_TRANSPORT'),
                               'priority': entry.get('PRIORITY'), 'message': message})
            except (ValueError, TypeError):
                malformed += 1
        result = dict(probe, events=events, malformed_lines=malformed)
    result = private_journal(result)
    save(path / 'journal.json', result)
    return result


def trace_summary(trace):
    result = {'status': trace.get('status', 'unavailable'), 'event_counts': {}, 'loss': {},
              'callbacks': [], 'unmatched_callbacks': [], 'sleep_entries': [], 'rpmh_commands': [], 'parse_failures': 0}
    for cpu, raw in trace.get('cpu_stats', {}).items():
        for label in ('overrun', 'commit overrun', 'dropped events'):
            count = stat(raw, label)
            if count is None or count:
                result['loss'][cpu + '/' + label] = count
    result['coverage'] = ('incomplete' if trace.get('status') != 'captured' or trace.get('truncated') or
                          result['loss'] or not trace.get('cpu_stats') else 'no buffer loss reported')
    clocks, bandwidth, runtime, ufs, pending, accounting = {}, {}, {}, {}, {}, {}
    for line in trace.get('text', '').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        match = re.search(r'\s(\d+\.\d+): (\w+): (.*)$', line)
        if not match:
            result['parse_failures'] += 1
            continue
        timestamp, event, message = match.groups()
        result['event_counts'][event] = result['event_counts'].get(event, 0) + 1
        if event == 'device_pm_callback_start':
            m = re.match(r'(\S*) (.*?), parent: (.*?), (.*?)\[(.*?)\]$', message)
            if m:
                driver, device, parent, callback, action = m.groups()
                pending[(driver, device)] = {'driver': driver, 'device': device, 'parent': parent,
                    'callback': callback, 'action': action, 'start': float(timestamp)}
            else:
                result['parse_failures'] += 1
        elif event == 'device_pm_callback_end':
            m = re.match(r'(\S*) (.*?), err=(-?\d+)$', message)
            if m:
                driver, device, error = m.groups()
                item = pending.pop((driver, device), {'driver': driver, 'device': device, 'action': 'unknown'})
                item.update(error=int(error), end=float(timestamp))
                result['callbacks'].append(item)
            else:
                result['parse_failures'] += 1
        elif event in ('clk_enable_complete', 'clk_disable_complete', 'clk_prepare_complete', 'clk_unprepare_complete'):
            kind = 'enable' if event in ('clk_enable_complete', 'clk_disable_complete') else 'prepare'
            clocks.setdefault(message, {})[kind] = event[4:-9]
        elif event == 'rpm_status':
            m = re.match(r'(.*?) status=(\w+)$', message)
            if m:
                runtime[m[1]] = m[2]
            else:
                result['parse_failures'] += 1
        elif event in ('rpm_usage', 'rpm_idle', 'rpm_suspend', 'rpm_resume'):
            m = re.fullmatch(r'(.*?) flags-([0-9a-fA-F]+) cnt-(-?\d+)\s+dep-(-?\d+)\s+'
                             r'auto-(-?\d+)\s+p-(-?\d+)\s+irq-(-?\d+)\s+child-(-?\d+)', message)
            if m:
                item = accounting.setdefault(m[1], {'last': {}, 'calls': {}, 'returns': {}})
                item['last'] = dict(zip(('usage', 'disable_depth', 'auto', 'pending', 'irq_safe', 'children'),
                                        map(int, m.groups()[2:])))
                item['last'].update(event=event, flags=int(m[2], 16))
                if event != 'rpm_usage':
                    item['calls'][event] = item['calls'].get(event, 0) + 1
            else:
                result['parse_failures'] += 1
        elif event == 'rpm_return_int':
            m = re.fullmatch(r'(.*?):(.*?) ret=(-?\d+)', message)
            if m:
                item = accounting.setdefault(m[2], {'last': {}, 'calls': {}, 'returns': {}})
                key = m[1] + ' ret=' + m[3]
                item['returns'][key] = item['returns'].get(key, 0) + 1
            else:
                result['parse_failures'] += 1
        elif event == 'icc_set_bw':
            m = re.match(r'path=(.*?) dev=(.*?) node=(.*?) avg_bw=(\d+) peak_bw=(\d+) agg_avg=(\d+) agg_peak=(\d+)$', message)
            if m:
                path, device, node, avg, peak, agg_avg, agg_peak = m.groups()
                bandwidth[(device, path, node)] = {'device': device, 'path': path, 'node': node,
                    'avg': int(avg), 'peak': int(peak), 'aggregate_avg': int(agg_avg), 'aggregate_peak': int(agg_peak)}
            else:
                result['parse_failures'] += 1
        elif event == 'rpmh_send_msg':
            m = re.match(r'(.*?): tcs\(m\): \d+ \[(sleep|wake)\].* addr: (\w+) data: (\w+)', message)
            if m:
                controller, state, address, word = m.groups()
                result['rpmh_commands'].append({'controller': controller, 'state': state, 'address': address, 'word': word})
            else:
                result['parse_failures'] += 1
        elif event in ('ufshcd_system_suspend', 'ufshcd_wl_suspend', 'ufshcd_system_resume', 'ufshcd_wl_resume'):
            ufs[message.split(':', 1)[0]] = event + ': ' + message
        elif event == 'suspend_resume' and re.fullmatch(r'machine_suspend\[\d+\] begin', message):
            result['sleep_entries'].append({'timestamp': float(timestamp),
                'clocks': {k: dict(v) for k, v in clocks.items()}, 'bandwidth': list(bandwidth.values()),
                'runtime': dict(runtime), 'ufs': dict(ufs),
                'runtime_accounting': {k: {name: dict(values) for name, values in v.items()}
                                       for k, v in accounting.items()}})
    result['unmatched_callbacks'] = list(pending.values())
    if result['parse_failures']:
        result['coverage'] = 'incomplete: unparsed trace records'
    return result


def trace_report(trace):
    summary = trace_summary(trace)
    print('\n## Device sleep transitions')
    print(f"Capture: {summary['status']}; coverage: {summary['coverage']}")
    print('Software transitions and requests do not by themselves confirm physical power collapse.')
    if trace.get('error'):
        print('Capture error: ' + trace['error'])
    if trace.get('cleanup_error'):
        print('Trace cleanup failed: ' + trace['cleanup_error'])
    if trace.get('unavailable_events'):
        print('Unsupported events: ' + ', '.join(trace['unavailable_events']))
    if summary['loss']:
        render({'Buffer loss': summary['loss']})
    print(f"Kernel low-power entry markers: {len(summary['sleep_entries'])}; unparsed records: {summary['parse_failures']}")
    failures = [c for c in summary['callbacks'] if c['error']]
    print(f"Completed PM callbacks: {len(summary['callbacks'])}; errors: {len(failures)}; unmatched starts: {len(summary['unmatched_callbacks'])}")
    if failures:
        render({'Callback errors': failures})
    print('Selected hardware-driver callbacks (return 0 means success; all callbacks remain in the raw trace):')
    devices = {}
    selected = re.compile(r'ufs|usb|dwc|xhci|gpu|adreno|mdss|dpu|dsi|display|msm_drm|serial|bluetooth|adsp|lpass|sound|remoteproc', re.I)
    virtual_drivers = {'', 'backlight', 'bluetooth', 'bsg', 'ctrl', 'devfreq', 'drm',
                       'genpd', 'genpd_provider', 'misc', 'port', 'power_supply', 'remoteproc',
                       'rpmsg', 'rpmsg_ctrl', 'serial', 'serial8250', 'sound', 'soundwire',
                       'udc', 'usb_role', 'workqueue'}
    for item in summary['callbacks']:
        if item['driver'] in virtual_drivers or 'glink-edge' in item['device']:
            continue
        key = item['driver'] + ' ' + item['device']
        if selected.search(key):
            actions = devices.setdefault(key, {})
            actions.setdefault(item['action'], []).append(item['error'])
    for device, actions in sorted(devices.items()):
        descriptions = []
        for action, errors in actions.items():
            failed = [str(error) for error in errors if error]
            descriptions.append(f"{action}: {len(errors)} callbacks, " +
                                ('errors ' + ', '.join(failed) if failed else 'all returned 0'))
        print('  ' + device + ': ' + '; '.join(descriptions))
    if not devices:
        print('  No matching callbacks captured; devices may already have been runtime-suspended.')
    if summary['sleep_entries']:
        first = summary['sleep_entries'][0]
        print('\nLast observed resource transitions before FIRST kernel low-power entry:')
        print('Only resources that changed during capture appear here. Unchanged resources have unknown state.')
        print('UFS expectation: low-power link at sleep entry; these are driver-reported states:')
        render(first['ufs'], 2)
        print('Last selected runtime PM transitions before entry:')
        render({k: v for k, v in first['runtime'].items() if selected.search(k)}, 2)
        print('Runtime PM accounting before entry (observed devices only):')
        print('  Last event counts are not hardware state; system suspend can hold references and disable runtime PM.')
        print('  Return values include normal busy/already-suspended cases; reference owners are not recorded.')
        if not first['runtime_accounting']:
            print('  No accounting events captured; counts and operation outcomes are unknown.')
        for name, item in sorted(first['runtime_accounting'].items()):
            last = item['last']
            counts = ', '.join(f'{key}={last[key]}' for key in ('usage', 'children', 'disable_depth', 'pending') if key in last)
            state = first['runtime'].get(name, 'unobserved')
            print(f"  {name}: {counts or 'counts unknown'}; last_status={state}")
            calls = ', '.join(f'{key[4:]}={count}' for key, count in sorted(item['calls'].items()))
            print('    observed calls: ' + (calls or 'none') + '; last count event: ' + last.get('event', 'unobserved'))
            if item['returns']:
                print('    returns: ' + '; '.join(f'{key} ({count}x)' for key, count in sorted(item['returns'].items())))
        print('Selected clocks (framework operations, not hardware readback):')
        clocks = {k: v for k, v in first['clocks'].items() if selected.search(k)}
        for name, states in sorted(clocks.items()):
            print('  ' + name + ': ' + ', '.join(states.values()))
        if not clocks:
            print('  No selected clock transitions observed.')
        print('Last bandwidth values observed before entry (path enable state is not recorded):')
        print('  Nonzero values can belong to disabled paths; these are not effective sleep votes.')
        requests = {}
        for item in first['bandwidth']:
            requests.setdefault((item['device'], item['path']), set()).add((item['avg'], item['peak']))
        for (device, path), values in sorted(requests.items()):
            print(f"  {device} / {path}: " + '; '.join(f'avg={avg} peak={peak}' for avg, peak in sorted(values)))
    print('RPMh sleep/wake commands observed during capture (encoded words, not hardware acknowledgement):')
    requests = {}
    for item in summary['rpmh_commands']:
        states = requests.setdefault((item['controller'], item['address']), {})
        states.setdefault(item['state'], set()).add(item['word'])
    for (controller, address), states in sorted(requests.items()):
        print(f"  {controller} {address}: " + '; '.join(state + '=' + ','.join(sorted(words)) for state, words in sorted(states.items())))
    if not requests:
        print('  No commands captured; this does not imply zero retained votes.')
    print('Trace event counts:')
    render(summary['event_counts'], 2)


def render(value, indent=0):
    pad = ' ' * indent
    if isinstance(value, dict):
        if not value:
            print(pad + '(none)')
        missing = []
        for key, item in value.items():
            if item is None:
                missing.append(str(key))
            elif isinstance(item, (dict, list)) or '\n' in str(item):
                print(pad + str(key) + ':')
                render(item, indent + 2)
            else:
                print(pad + str(key) + ': ' + scalar(item))
        if missing:
            import textwrap
            print(textwrap.fill('Unavailable: ' + ', '.join(missing), width=110,
                                initial_indent=pad, subsequent_indent=pad + '  '))
    elif isinstance(value, list):
        if not value:
            print(pad + '(none)')
        for i, item in enumerate(value, 1):
            if isinstance(item, (dict, list)):
                print(pad + str(i) + '.')
                render(item, indent + 2)
            else:
                print(pad + '- ' + scalar(item))
    else:
        for line in scalar(value).splitlines():
            print(pad + line)


def scalar(value):
    if value is None:
        return 'unavailable'
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    return str(value) if value != '' else '(empty)'


def journal_report(journal):
    events = journal.get('events', [])
    dropped = journal.get('reported_loss') or any(re.search(r'buffer overrun|messages? (?:lost|suppressed)|missed \d+ kernel', e['message'], re.I) for e in events)
    incomplete = dropped or journal.get('status') != 'complete' or journal.get('truncated') or journal.get('malformed_lines')
    print('Capture: ' + ('incomplete' if incomplete else 'bounded; no reported loss'))
    print('Unreported kernel loss cannot be excluded; callback coverage is not inferred from journal messages.')
    render({k: v for k, v in journal.items() if k != 'events'})
    counts = {}
    for event in events:
        message = event['message']
        if re.search(r'error|fail|timeout|timed out|\bwarning\b|\bbug\b|\bblocked\b|overrun|watchdog|abort|panic', message, re.I):
            counts[message] = counts.get(message, 0) + 1
    print('Error signatures (occurrences):')
    render(counts, 2)
    print(f'All {len(events)} captured journal events follow (privacy-filtered):')
    for e in events:
        try:
            stamp = datetime.datetime.fromtimestamp(int(e['timestamp_us']) / 1_000_000,
                                                     datetime.timezone.utc).isoformat(timespec='milliseconds')
        except (ValueError, TypeError, KeyError, OverflowError):
            stamp = str(e.get('timestamp_us', 'unknown'))
        print(f"[{stamp}; mono_us={e.get('monotonic_us', 'unknown')}] {e.get('unit') or e.get('transport') or 'unknown'}: {e['message']}")


def presleep_context(before):
    result = {}
    for kind, label in (('wlan', 'Wi-Fi radio'), ('bluetooth', 'Bluetooth radio')):
        radios = []
        for path, values in data(before, 'peripherals', {}).items():
            if not path.startswith('class/rfkill/') or values.get('type') != kind:
                continue
            if values.get('hard') == '1':
                state = 'hardware blocked'
            elif values.get('soft') == '1':
                state = 'software blocked'
            elif values.get('state') == '1' or values.get('hard') == values.get('soft') == '0':
                state = 'enabled'
            elif values.get('state') == '0':
                state = 'blocked'
            else:
                state = 'unknown'
            radios.append(state + ' (' + values.get('name', path.rsplit('/', 1)[-1]) + ')')
        result[label] = ', '.join(radios) if radios else None
    network = data(before, 'connectivity', {})
    bt = network.get('bluetooth', {})
    if bt.get('status') == 'complete' and not bt.get('truncated'):
        result['Bluetooth adapters'] = '; '.join(
            a['adapter'] + ': powered=' + scalar(a.get('Powered')) + ', discovering=' + scalar(a.get('Discovering'))
            for a in bt.get('adapters', [])) or 'none reported'
        result['Bluetooth connections'] = '; '.join(
            d.get('device', 'connected device') + ' (' + (d.get('Icon') or 'type unknown') +
            '), services resolved=' + scalar(d.get('ServicesResolved')) + ', wake allowed=' + scalar(d.get('WakeAllowed'))
            for d in bt.get('connected_devices', [])) or 'none'
    else:
        result['Bluetooth connections'] = 'unknown (' + bt.get('status', 'not captured') + ')'
    wifi = []
    for interface in network.get('wifi', []):
        link = interface.get('link', {})
        description = 'connected' if link.get('connected') is True else 'disconnected' if link.get('connected') is False else 'connection unknown'
        details = link.get('details', {})
        if details.get('freq'):
            description += ', ' + details['freq'] + ' MHz'
        if details.get('signal'):
            description += ', ' + details['signal']
        for key in ('power_save', 'wake_on_wlan'):
            probe = interface.get(key, {})
            description += '; ' + (probe.get('text', '').strip() if probe.get('status') == 'complete' else key + ' unavailable')
        wifi.append(interface['interface'] + ': ' + description)
    result['Wi-Fi connection'] = '; '.join(wifi) if wifi else ('no interfaces reported' if network else 'unknown (not captured)')
    supplies = data(before, 'battery', {})
    result['Battery'] = '; '.join(
        name + ': ' + (values['capacity'] + '%' if values.get('capacity') else 'capacity unavailable') +
        ', ' + (values.get('status') or 'status unavailable')
        for name, values in supplies.items() if values.get('type') == 'Battery') or None
    online = [values.get('online') for values in supplies.values() if values.get('type') != 'Battery']
    result['External power'] = ('online' if '1' in online else 'none reported' if '0' in online else None)
    owners = data(before, 'health', {}).get('processes', {}).get('pcm_owners', [])
    result['PCM owners'] = ', '.join(sorted({str(x.get('comm') or 'unknown') + ' (PID ' + str(x['pid']) + ')' for x in owners})) or None
    pw = data(before, 'pipewire', {})
    clients = []
    for entry in pw.get('sink_inputs', []):
        props = entry.get('properties', {})
        clients.append((props, 'corked' if entry.get('corked') is True else 'uncorked' if entry.get('corked') is False else 'state unknown'))
    for entry in pw.get('objects', []):
        props = entry.get('props', {})
        if props.get('media.class') == 'Stream/Output/Audio':
            clients.append((props, entry.get('state') or 'state unknown'))
    result['Playback clients'] = '; '.join(sorted({
        (props.get('application.process.binary') or 'application unknown') + ' (' + state + ')'
        for props, state in clients})) or ('none reported' if pw.get('status') == 'complete' else None)
    return result


def overview(summary, before, after):
    print('\n## Summary')
    ident = data(before, 'identity', {})
    print(f"Attempt: {summary['cycle_id']}")
    print(f"Result: {summary['outcome']} / service: {scalar(summary.get('service_result'))}")
    device = re.search(r'^ARMADA_DEVICE_NAME=(.*)$', ident.get('device', {}).get('text', ''), re.M)
    if device:
        import shlex
        try:
            print('Device: ' + ' '.join(shlex.split(device[1])))
        except ValueError:
            print('Device: ' + device[1])
    print(f"Kernel: {scalar(ident.get('kernel'))}; OS: {scalar(ident.get('os_version'))}")
    print(f"Sleep mode: {summary['configured_sleep_mode']}; snapshots complete: {scalar(summary['capture_complete'])}")
    if 'measurements' in summary:
        print(summary['measurements'])
        return
    print(f"Kernel suspend count: +{scalar(summary.get('success_delta'))} successful, +{scalar(summary.get('fail_delta'))} failed")
    print(f"Timekeeping suspended: {summary['timekeeping_suspended_seconds']:.3f} s; awake/transition portion: {summary['awake_and_transition_seconds']:.3f} s")
    print(f"Last wake IRQ: {scalar(summary.get('wake_irq'))} ({scalar(summary.get('wake_actions'))}); may be stale if no suspend occurred")
    print('\nSnapshot before kernel suspend:')
    context = presleep_context(before)
    context['Open PCM devices'] = summary.get('open_pcms_at_prepare')
    render(context, 2)
    print('Radio status is rfkill state; connection details describe the snapshot, not in-sleep traffic.')
    print('Automatic capture runs after sleep preparation begins; Wi-Fi may already be disconnected.')
    print('This does not establish connection state before the sleep request.')
    changes = {k: v for k, v in summary.get('service_changes', {}).items() if v.get('changed')}
    print('Monitored service changes: ' + (', '.join(changes) if changes else 'none observed'))
    if summary.get('failure'):
        render(summary['failure'])
    print('\nFirmware sleep residency across the capture window:')
    print(f"  {'Subsystem':<20} {'Entries':>10} {'Asleep (s)':>14} {'Window (%)':>14}")
    unavailable = []
    for name, item in summary.get('qcom', {}).items():
        if item.get('sleep_seconds') is None:
            unavailable.append(name)
            continue
        print(f"  {name:<20} {scalar(item.get('count_delta')):>10} {scalar(item.get('sleep_seconds')):>14} {scalar(item.get('sleep_pct_of_window')):>14}")
    if unavailable:
        print('  Unavailable residency: ' + ', '.join(unavailable))
    print('Residency includes boundary sampling time; zero residency alone does not identify a culprit.')
    print('Battery endpoints are retained below; they do not measure isolated sleep power.')


def capture_report(before, after):
    print('\n## Capture timing and completeness')
    print('Unavailable values mean absent, unsupported, unreadable, or uncaptured; they never mean zero.')
    boots = [(snap or {}).get('boot_id') for snap in (before, after)]
    print('Before/after boot: ' + ('unknown' if not all(boots) else 'same' if boots[0] == boots[1] else 'different'))
    for phase, snap in (('Before', before), ('After', after)):
        print(phase + ':')
        if not snap:
            print('  unavailable')
            continue
        print(f"  Complete: {scalar(snap.get('complete'))}")
        for name, group in snap.get('groups', {}).items():
            duration = group.get('finished', {}).get('monotonic', group['started']['monotonic']) - group['started']['monotonic']
            print(f"  {name:<18} {group['status']:<12} {duration:>7.3f} s" + ('; ' + group['error'] if group.get('error') else ''))


def snapshot_report(name, before, after):
    print('\n## ' + name.replace('_', ' ').capitalize())
    old, new = data(before, name), data(after, name)
    if name in ('identity', 'pipewire', 'connectivity'):
        print('Captured before kernel suspend:')
        render(old, 2)
    elif old == new and old is not None:
        print('Before and after (unchanged):')
        render(old, 2)
    else:
        print('Before:')
        render(old, 2)
        print('After:')
        render(new, 2)


def report(cycle, details=False):
    import contextlib
    output = PrivateOutput(sys.stdout)
    with contextlib.redirect_stdout(output):
        try:
            report_body(cycle, details)
        finally:
            output.flush()


def report_body(cycle, details=False):
    path = hydrate(cycle)
    meta = load(path / 'attempt.json')
    before, after = private_snapshot(load(path / 'before.json')), private_snapshot(load(path / 'after.json'))
    print('Armada sleep debug report')
    print(f'logger_schema={SCHEMA}')
    print('Privacy: Wi-Fi/Bluetooth names and MAC/IP addresses filtered; journal and trace diagnostics retained.')
    print('generated=' + datetime.datetime.now(datetime.timezone.utc).isoformat())
    summary = summarize(before, after, meta)
    overview(summary, before, after)
    trace = load(path / 'trace.json') or {'status': 'not requested'}
    trace_report(trace)
    capture_report(before, after)
    print('\n## Supporting measurements')
    supporting = {k: v for k, v in summary.items() if k not in (
        'cycle_id', 'outcome', 'service_result', 'qcom', 'capture_complete',
        'configured_sleep_mode', 'service_changes')}
    supporting['battery'] = {name: {k: v for k, v in item.items() if k not in ('before', 'after')}
                             for name, item in summary.get('battery', {}).items()}
    render(supporting)
    print('\n## Attempt boundaries')
    render({'attempt': meta, 'before': {k: v for k, v in (before or {}).items() if k != 'groups'},
            'after': {k: v for k, v in (after or {}).items() if k != 'groups'}})
    print('\nRAW EVIDENCE — fixed snapshots, followed by the journal and transition trace')
    for name in ('identity', 'suspend', 'battery', 'qcom', 'audio', 'pipewire', 'connectivity', 'health',
                 'interrupts', 'wake_sources', 'wake_actions', 'wake_inventory', 'fake_suspend', 'peripherals', 'pstore'):
        snapshot_report(name, before, after)
    print('\n## Attempt journal')
    journal_report(private_journal(capture_journal(path, before, after)))
    pending = []
    for p in sorted((STATE / 'attempts').glob('*/attempt.json')):
        m = load(p)
        if m and m.get('outcome') == 'pending' and m['cycle_id'] != cycle:
            pending.append(m)
    print('\n## Other attempts without a saved completion')
    render(pending)
    print('\n## Raw sleep transition trace')
    render({k: v for k, v in trace.items() if k != 'text'})
    print(trace.get('text', '(no captured events)'))
    if details:
        print('Unfiltered live inventories are excluded from shareable reports for privacy.')
    for name in ('attempt.json', 'before.json', 'after.json', 'journal.json', 'trace.json'):
        value = load(path / name)
        if value is not None:
            try:
                save(STATE / 'attempts' / cycle / name, value)
            except OSError as exc:
                print('persistence_error=' + str(exc))
    # Retain bounded history without touching another collector's runtime files.
    attempts = sorted((STATE / 'attempts').glob('*/attempt.json'), key=lambda p: p.stat().st_mtime)
    for old in attempts[:-32]:
        if old.parent.name != cycle:
            import shutil
            shutil.rmtree(old.parent, ignore_errors=True)
    completed = sorted(RUN.glob('*/exported'), key=lambda p: p.stat().st_mtime)
    for old in completed[:-10]:
        if old.parent.name != cycle:
            import shutil
            shutil.rmtree(old.parent, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', nargs='?', default='collect', choices=('prepare', 'begin', 'finish', 'collect', 'report', 'restore', 'stop-trace'))
    parser.add_argument('cycle', nargs='?')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--details', action='store_true')
    parser.add_argument('--trace', action='store_true', help='Capture bounded device and resource transitions around sleep')
    args = parser.parse_args()
    if os.geteuid() != 0 and os.environ.get('ARMADA_SLEEP_DEBUG_ALLOW_NONROOT') != '1':
        parser.error('Run this command with sudo')
    os.umask(0o077)
    RUN.mkdir(parents=True, exist_ok=True, mode=0o700)
    if args.action == 'restore':
        trace_restore()
        debug_settings()
        return
    if args.action in ('prepare', 'begin'):
        cycle = args.cycle or uuid.uuid4().hex
        begin(cycle, args.verbose, args.trace)
        print(cycle)
        return
    cycle = args.cycle or (load(STATE / 'latest.json') or {}).get('cycle_id')
    if not cycle:
        if args.action != 'collect':
            parser.error('No saved attempt; run prepare before suspending')
        cycle = uuid.uuid4().hex
        save(cycle_path(cycle) / 'attempt.json', {
            'schema': SCHEMA, 'cycle_id': cycle, 'boot_id': read(PROC / 'sys/kernel/random/boot_id'),
            'started': clock(), 'outcome': 'unprepared'})
    if args.action == 'stop-trace':
        trace_finish(cycle)
        if (load(STATE / 'trace-owner.json') or {}).get('cycle_id') == cycle:
            trace_restore()
        return
    if args.action in ('finish', 'collect'):
        finish(cycle)
    if args.action == 'finish':
        print(cycle)
    else:
        report(cycle, args.details)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as exc:
        print('sleep_debug_error=' + str(exc), file=sys.stderr)
        sys.exit(1)
