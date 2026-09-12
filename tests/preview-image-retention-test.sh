#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$ROOT" <<'PY'
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

path = Path(sys.argv[1]) / '.github/scripts/publish-preview-index.py'
spec = importlib.util.spec_from_file_location('retention', path)
retention = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retention)

def image(day):
    return f'preview/armada-202609{day:02}.abcdef0.img.gz'

def obj(key, day):
    return {'Key': key, 'Size': 100, 'LastModified': f'2026-09-{day:02}T00:00:00+00:00'}

objects = [obj(image(day) + suffix, day) for day in range(1, 8) for suffix in ('', '.sha256')]
protected = ['release/armada-20260901.img.gz', 'testing/armada-20260901.abcdef0.img.gz', 'preview/builds.json', 'preview/notes.txt',
             'preview/nested/armada-20260901.abcdef0.img.gz',
             'preview/armada-custom.img.gz', 'preview/armada-20260801.abcdef0.img.gz.sha256']
objects += [obj(key, 1) for key in protected]
expected = {image(day) + suffix for day in (1, 2) for suffix in ('', '.sha256')}
assert set(retention.expired_keys(objects, image(7))) == expected

# The just-published image remains protected even if timestamps sort it older.
assert image(1) not in retention.expired_keys(objects, image(1))
assert len(retention.expired_keys(objects, image(1))) == 4
assert retention.expired_keys([obj(image(1), 1), obj(image(1)+'.sha256', 1)], image(1)) == []

# Incomplete uploads are removed without displacing complete pairs.
legacy = 'preview/armada-20260801.img.gz'
assert legacy in retention.expired_keys(objects + [obj(legacy, 1)], image(7))
assert set(retention.expired_keys(objects + [obj(image(8), 8)], image(7))) == expected | {image(8)}
empty_checksum = {**obj(image(8) + '.sha256', 8), 'Size': 0}
deletions = retention.expired_keys(objects + [obj(image(8), 8), empty_checksum], image(7))
assert set(deletions) == expected | {image(8), image(8) + '.sha256'}
assert deletions.index(image(8) + '.sha256') < deletions.index(image(8))
deletions = retention.expired_keys(objects, image(7))
for day in (1, 2):
    assert deletions.index(image(day)+'.sha256') < deletions.index(image(day))
# A failed image deletion is retried after its checksum has been removed.
remaining = [obj for obj in objects if obj['Key'] != image(2)+'.sha256']
assert set(retention.expired_keys(remaining, image(7))) == expected - {image(2)+'.sha256'}
for current, listing in [('release/armada-20260901.img.gz', objects),
                         (image(8), objects), (image(1), [obj(image(1), 1)])]:
    try:
        retention.expired_keys(listing, current)
    except ValueError:
        pass
    else:
        raise AssertionError('Unsafe pruning accepted')

env = {'R2_ENDPOINT_URL': 'https://fixture.example.com', 'R2_BUCKET': 'fixture',
       'R2_PREFIX': 'preview'}
unmanaged = 'preview/armada-20260801.1234567.img.gz'
objects += [obj(unmanaged, 1), obj(unmanaged + '.sha256', 1)]
tmp = tempfile.TemporaryDirectory(prefix='armada-preview-index-')
os.chdir(tmp.name)
Path('output').mkdir()
current = {'version': '20260907.abcdef0', 'image': {'key': image(7)}}
Path('output/current-build.json').write_text(json.dumps(current))
previous = {'version': '20260903.abcdef0', 'build_commit_title': 'Keep this title',
            'published_at': '2026-09-02T00:00:00Z',
            'image': {'key': image(3), 'size': 100, 'sha256': 'a'*64},
            'container': {'digest': 'sha256:' + 'a'*64}}

previous_builds = [previous] + [
    {'version': f'202609{day:02}.abcdef0', 'published_at': f'2026-09-{day:02}T00:00:00Z',
     'image': {'key': image(day), 'size': 100, 'sha256': 'a'*64}}
    for day in (1, 2, 4, 5, 6)
]

def aws_output(args, **kwargs):
    if args[:3] == ['aws', 's3', 'cp']:
        if args[3].endswith('builds.json'):
            return json.dumps({'builds': previous_builds})
        assert args[3].endswith('.sha256')
        return 'a'*64 + '  image.img.gz\n'
    if 'list-objects-v2' in args:
        return json.dumps({'Contents': objects})
    assert 'head-object' in args
    key = args[args.index('--key') + 1]
    return json.dumps({'Metadata': {} if key == unmanaged else {'armada-preview': 'true'}})

with patch.dict(os.environ, env, clear=True), \
     patch.object(retention.subprocess, 'check_output', side_effect=aws_output) as listing, \
     patch.object(retention.subprocess, 'run') as deletion:
    retention.main()
    list_args = listing.call_args_list[0].args[0]
    assert '--no-paginate' not in list_args
    assert list_args[-4:] == ['--prefix', 'preview/', '--output', 'json']
    calls = [call.args[0] for call in deletion.call_args_list]
    assert {args[-1] for args in calls[:-1]} == expected
    assert calls[-1][:4] == ['aws', 's3', 'cp', 'output/builds.json']
    index = json.loads(Path('output/builds.json').read_text())
    assert index['latest'] == current['version']
    assert len(index['builds']) == 5 and index['builds'][0] == current
    assert {build['image']['key'] for build in index['builds']} == {image(day) for day in range(3, 8)}
    assert previous in index['builds']
    assert all(build['published_at'].endswith('Z') for build in index['builds'][1:])
    assert all('schema_version' not in build and 'channel' not in build for build in index['builds'])

# A rebuilt pair can have newer bytes than the last successfully published index.
with patch.dict(previous['image'], {'size': 50, 'sha256': 'b'*64}), \
     patch.dict(os.environ, env, clear=True), \
     patch.object(retention.subprocess, 'check_output', side_effect=aws_output), \
     patch.object(retention.subprocess, 'run'):
    retention.main()
    builds = json.loads(Path('output/builds.json').read_text())['builds']
    refreshed = next(build for build in builds if build['image']['key'] == image(3))
    assert refreshed['image'] == {'key': image(3), 'size': 100, 'sha256': 'a'*64}
    assert refreshed['build_commit_title'] == previous['build_commit_title']
    assert refreshed['container'] == previous['container']
    assert refreshed['published_at'] == '2026-09-03T00:00:00Z'

def invalid_checksum(args, **kwargs):
    if args[:3] == ['aws', 's3', 'cp'] and args[3].endswith(image(3) + '.sha256'):
        return 'invalid checksum'
    return aws_output(args, **kwargs)

with patch.dict(os.environ, env, clear=True), \
     patch.object(retention.subprocess, 'check_output', side_effect=invalid_checksum), \
     patch.object(retention.subprocess, 'run') as writes:
    try:
        retention.main()
    except ValueError:
        pass
    else:
        raise AssertionError('Invalid checksum accepted for an existing build')
    writes.assert_not_called()

with patch.dict(os.environ, env, clear=True), \
     patch.object(retention.subprocess, 'check_output', side_effect=aws_output), \
     patch.object(retention.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'aws')) as deletion:
    try:
        retention.main()
    except subprocess.CalledProcessError:
        pass
    else:
        raise AssertionError('Deletion failure ignored')
    assert deletion.call_count == 1
    assert 'delete-object' in deletion.call_args.args[0]

with patch.dict(os.environ, env, clear=True), \
     patch.object(retention.subprocess, 'check_output', side_effect=subprocess.CalledProcessError(1, 'aws')), \
     patch.object(retention.subprocess, 'run') as deletion:
    try:
        retention.main()
    except subprocess.CalledProcessError:
        pass
    else:
        raise AssertionError('Listing failure ignored')
    deletion.assert_not_called()

for prefix in ['release', 'testing']:
    with patch.dict(os.environ, dict(env, R2_PREFIX=prefix), clear=True), \
         patch.object(retention.subprocess, 'check_output') as listing:
        try:
            retention.main()
        except ValueError:
            pass
        else:
            raise AssertionError('Pruning outside preview accepted')
        listing.assert_not_called()

# First publication starts with the current build, ignoring old metadata and unindexed files.
objects = [obj for obj in objects if obj['Key'] != 'preview/builds.json']
objects.append(obj('preview/latest.json', 1))
with patch.dict(os.environ, env, clear=True), \
     patch.object(retention.subprocess, 'check_output', side_effect=aws_output), \
     patch.object(retention.subprocess, 'run'):
    retention.main()
    assert json.loads(Path('output/builds.json').read_text())['builds'] == [current]

# If the final index upload fails, it is attempted only after deletions.
def fail_index(args, **kwargs):
    if args[:3] == ['aws', 's3', 'cp']:
        raise subprocess.CalledProcessError(1, 'aws')
with patch.dict(os.environ, env, clear=True), \
     patch.object(retention.subprocess, 'check_output', side_effect=aws_output), \
     patch.object(retention.subprocess, 'run', side_effect=fail_index) as writes:
    try:
        retention.main()
    except subprocess.CalledProcessError:
        pass
    else:
        raise AssertionError('Index publication failure ignored')
    assert all('delete-object' in call.args[0] for call in writes.call_args_list[:-1])
    assert writes.call_args_list[-1].args[0][:3] == ['aws', 's3', 'cp']

tmp.cleanup()
print('Preview image retention and index tests passed')
PY
