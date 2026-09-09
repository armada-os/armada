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
from unittest.mock import patch

path = Path(sys.argv[1]) / '.github/scripts/prune-preview-images.py'
spec = importlib.util.spec_from_file_location('retention', path)
retention = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retention)

def image(day):
    return f'preview/armada-202609{day:02}.abcdef0.img.gz'

def obj(key, day):
    return {'Key': key, 'LastModified': f'2026-09-{day:02}T00:00:00Z'}

objects = [obj(image(day) + suffix, day) for day in range(1, 8) for suffix in ('', '.sha256')]
protected = ['release/armada-20260901.img.gz', 'testing/armada-20260901.abcdef0.img.gz', 'preview/latest.json', 'preview/notes.txt',
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
       'R2_PREFIX': 'preview', 'CURRENT_IMAGE_KEY': image(7)}
unmanaged = 'preview/armada-20260801.1234567.img.gz'
objects += [obj(unmanaged, 1), obj(unmanaged + '.sha256', 1)]
def aws_output(args, **kwargs):
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
    assert {call.args[0][-1] for call in deletion.call_args_list} == expected

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

print('Preview image retention tests passed')
PY
