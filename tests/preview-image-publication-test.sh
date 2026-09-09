#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$ROOT" <<'PY'
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap

workflow = (Path(sys.argv[1]) / '.github/workflows/build-disk.yml').read_text()
# Extraction depends on the step name and the following step boundary.
step = workflow.split('      - name: Publish disk image to R2\n', 1)[1]
script = textwrap.dedent(step.split('        run: |\n', 1)[1].split('\n      - name:', 1)[0])
mock = '''#!/usr/bin/env python3
import json, os, shutil, sys
from pathlib import Path
args = sys.argv[1:]
if args[:2] == ['configure', 'set']:
    sys.exit(0)
if args[:2] == ['s3', 'cp']:
    source, destination = args[2:4]
    if source.startswith('s3://'):
        assert destination == '-'
        print((Path('remote') / source.removeprefix('s3://')).read_text(), end='')
        sys.exit(0)
    assert args[args.index('--cache-control') + 1] == 'no-store'
    kind = 'manifest' if source.endswith('builds.json') else 'checksum' if source.endswith('.sha256') else 'image'
    if os.environ.get('FAIL_UPLOAD') == kind:
        sys.exit(1)
    if kind == 'manifest':
        assert args[args.index('--content-type') + 1] == 'application/json'
        assert args[args.index('--cache-control') + 1] == 'no-store'
    else:
        assert args[args.index('--metadata') + 1] == 'armada-preview=true'
    target = Path('remote') / destination.removeprefix('s3://')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    sys.exit(0)
if 'list-objects-v2' in args:
    print(json.dumps({'Contents': [{'Key': str(p.relative_to('remote/fixture')), 'Size': p.stat().st_size,
          'LastModified': '2026-09-09T00:00:00Z'} for p in Path('remote/fixture').rglob('*') if p.is_file()]}))
    sys.exit(0)
if 'head-object' in args:
    target = Path('remote') / args[args.index('--bucket')+1] / args[args.index('--key')+1]
    if '--query' in args:
        print(0 if os.environ.get('BAD_SIZE') else target.stat().st_size)
    else:
        print(json.dumps({'Metadata': {'armada-preview': 'true'}}))
    sys.exit(0)
raise SystemExit('Unexpected AWS call: ' + repr(args))
'''

registry_mock = '''#!/usr/bin/env python3
import os, sys
from pathlib import Path
assert sys.argv[1:] == ['inspect', '--no-creds', '--override-arch', 'arm64', '--format', '{{.Digest}}',
                        'docker://ghcr.io/armada-os/armada:testing']
case = os.environ['TEST_CASE']
if case == 'registry-failure':
    sys.exit(1)
stale = case == 'stale' or (case == 'advanced-during-upload' and Path('registry-checked').exists())
Path('registry-checked').touch()
print('sha256:' + ('c' if stale else 'a') * 64)
'''

for case in ['success', 'relative-urls', 'image-failure', 'checksum-failure', 'manifest-failure',
             'size-mismatch', 'stale', 'advanced-during-upload', 'registry-failure']:
    with tempfile.TemporaryDirectory(prefix='armada-preview-publish-') as tmp:
        root = Path(tmp)
        title = 'fix(ci): preserve "quotes", 100% & <markup> — café 🚀 $(false) `false`'
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.com',
                        '-c', 'commit.gpgsign=false', 'commit', '-q', '--allow-empty', '-m', title],
                       cwd=root, check=True)
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        (root/'.github/scripts').mkdir(parents=True)
        shutil.copyfile(Path(sys.argv[1]) / '.github/scripts/publish-preview-index.py',
                        root/'.github/scripts/publish-preview-index.py')
        (root/'bin').mkdir()
        aws = root/'bin/aws'
        aws.write_text(mock)
        aws.chmod(0o755)
        skopeo = root/'bin/skopeo'
        skopeo.write_text(registry_mock)
        skopeo.chmod(0o755)
        (root/'output').mkdir()
        version = f'20260908.{commit[:7]}'
        filename = f'armada-{version}.img.gz'
        content = b'disk image fixture'
        digest = hashlib.sha256(content).hexdigest()
        (root/'output'/filename).write_bytes(content)
        (root/'output'/f'{filename}.sha256').write_text(f'{digest}  {filename}\n')
        remote = root/'remote/fixture/preview'
        remote.mkdir(parents=True)
        previous = '{"channel": "preview", "latest": "old", "builds": []}\n'
        (remote/'builds.json').write_text(previous)
        env = dict(os.environ, PATH=str(root/'bin')+':'+os.environ['PATH'], TEST_CASE=case,
                   R2_PREFIX='preview', R2_BUCKET='fixture', R2_ENDPOINT_URL='https://fixture.example.com',
                   R2_PUBLIC_URL='' if case == 'relative-urls' else 'https://downloads.armadaos.dev/',
                   CONTAINER_TAG='testing', CONTAINER_DIGEST='sha256:'+'a'*64, BUILD_COMMIT=commit,
                   TEST_COMMIT_TITLE=title,
                   DISK_IMAGE=f'output/{filename}', IMAGE_REGISTRY='ghcr.io/armada-os', IMAGE_NAME='armada',
                   GITHUB_OUTPUT=str(root/'outputs'), GITHUB_STEP_SUMMARY=str(root/'summary'))
        if case.endswith('-failure'):
            env['FAIL_UPLOAD'] = case.removesuffix('-failure')
        if case == 'size-mismatch':
            env['BAD_SIZE'] = '1'
        result = subprocess.run(['bash', '-c', script], cwd=root, env=env, capture_output=True, text=True)
        if case in ('success', 'relative-urls'):
            assert result.returncode == 0, result.stderr
            index = json.loads((remote/'builds.json').read_text())
            assert index['channel'] == 'preview'
            assert 'schema_version' not in index
            assert index['latest'] == version and len(index['builds']) == 1
            latest = index['builds'][0]
            assert 'schema_version' not in latest and 'channel' not in latest
            assert latest['version'] == version
            assert latest['container'] == {'reference': 'ghcr.io/armada-os/armada:testing', 'digest': 'sha256:'+'a'*64}
            assert latest['build_commit'] == commit
            assert latest['build_commit_title'] == title
            assert latest['image']['filename'] == filename
            assert latest['image']['key'] == f'preview/{filename}'
            assert latest['checksum']['key'] == latest['image']['key'] + '.sha256'
            assert latest['image']['sha256'] == digest and latest['image']['size'] == len(content)
            public = '' if case == 'relative-urls' else 'https://downloads.armadaos.dev'
            assert latest['image']['url'] == f'{public}/preview/{filename}'
            assert latest['checksum']['url'] == f'{public}/preview/{filename}.sha256'
            subprocess.run(['sha256sum', '-c', filename+'.sha256'], cwd=remote, check=True, capture_output=True)
        else:
            assert result.returncode != 0, case
            assert (remote/'builds.json').read_text() == previous, case
            assert not (root/'summary').exists() and not (root/'outputs').exists(), case
            if case in ('stale', 'registry-failure'):
                assert list(remote.iterdir()) == [remote/'builds.json'], case
        print(f'PASS: Preview publication {case}')
PY
