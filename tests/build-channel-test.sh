#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$ROOT" <<'PY'
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap

workflow = (Path(sys.argv[1]) / '.github/workflows/build.yml').read_text()

def script(name):
    step = workflow.split(f'      - name: {name}\n', 1)[1]
    return textwrap.dedent(step.split('        run: |\n', 1)[1].split('\n      - name:', 1)[0])

def run(name, **env):
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / 'outputs'
        result = subprocess.run(['bash', '-c', script(name)],
                                env=dict(os.environ, GITHUB_OUTPUT=str(output), **env),
                                capture_output=True, text=True)
        values = dict(line.split('=', 1) for line in output.read_text().splitlines()) if output.exists() else {}
        return result, values

for event in ['push', 'workflow_dispatch']:
    for branch, tag, channel in [('main', 'testing', 'preview'),
                                 ('staging', 'staging', 'staging'),
                                 ('feature-a', 'feature-a', '')]:
        result, values = run('Resolve publication channel', EVENT_NAME=event, BUILD_REF=f'refs/heads/{branch}')
        assert result.returncode == 0, result.stderr
        assert values == {'tag': tag, 'channel': channel}

for branch in ['testing', 'preview', 'beta', 'stable', 'latest', 'feature/slash', 'bad tag', '$(false)']:
    result, values = run('Resolve publication channel', EVENT_NAME='workflow_dispatch', BUILD_REF=f'refs/heads/{branch}')
    assert result.returncode != 0 and not values, branch

result, values = run('Resolve publication channel', EVENT_NAME='pull_request', BUILD_REF='refs/pull/123/merge')
assert result.returncode == 0 and not values

for ref in ['refs/tags/main', 'refs/tags/staging', 'refs/tags/v1.0', 'main', '']:
    result, values = run('Resolve publication channel', EVENT_NAME='workflow_dispatch', BUILD_REF=ref)
    assert result.returncode != 0 and not values, ref

print('Build channel resolution tests passed')
PY
