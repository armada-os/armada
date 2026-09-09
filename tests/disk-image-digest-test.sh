#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir "$WORK/bin"

python3 - "$ROOT/Justfile" "$WORK/load-image" <<'PY'
from pathlib import Path
import sys
# Extraction depends on these recipe names and their order.
recipe = Path(sys.argv[1]).read_text().split('_rootful_load_image $', 1)[1]
recipe = recipe.split('\n', 1)[1].split('\n_build-bib ', 1)[0]
Path(sys.argv[2]).write_text('\n'.join(line[4:] for line in recipe.splitlines()))
PY

cat > "$WORK/bin/just" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$TEST_LOG"
[[ "${FAIL_PULL:-}" != 1 || "$3" != pull ]]
SH
cat > "$WORK/bin/sudo" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$TEST_LOG"
SH
chmod +x "$WORK/bin/just" "$WORK/bin/sudo"
export PATH="$WORK/bin:$PATH" TEST_LOG="$WORK/log"
export target_image=ghcr.io/armada-os/armada tag=testing
export ARMADA_IMAGE_DIGEST="sha256:$(printf 'a%.0s' {1..64})"

bash "$WORK/load-image" 2>/dev/null
printf 'sudoif podman pull %s@%s\nsudoif podman tag %s@%s %s:testing\n' \
    "$target_image" "$ARMADA_IMAGE_DIGEST" "$target_image" "$ARMADA_IMAGE_DIGEST" \
    "$target_image" > "$WORK/expected"
cmp "$WORK/expected" "$TEST_LOG"

: > "$TEST_LOG"
if ARMADA_IMAGE_DIGEST=invalid bash "$WORK/load-image" 2>"$WORK/error"; then
    echo 'Invalid image digest accepted' >&2
    exit 1
fi
[[ ! -s "$TEST_LOG" ]]
grep -q 'Invalid ARMADA_IMAGE_DIGEST' "$WORK/error"

if FAIL_PULL=1 bash "$WORK/load-image" 2>/dev/null; then
    echo 'Failed digest pull accepted' >&2
    exit 1
fi
[[ "$(wc -l < "$TEST_LOG")" == 1 ]]

: > "$TEST_LOG"
ARMADA_IMAGE_DIGEST='' SUDO_USER=fixture bash "$WORK/load-image" 2>/dev/null
[[ "$(cat "$TEST_LOG")" == "podman pull ${target_image}:testing" ]]

python3 - "$ROOT" "$WORK" <<'PY'
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

workflow = (Path(sys.argv[1]) / '.github/workflows/build-disk.yml').read_text()
# Extraction depends on the step name and the following step boundary.
step = workflow.split('      - name: Inspect disk source image\n', 1)[1]
script = textwrap.dedent(step.split('        run: |\n', 1)[1].split('\n      - name:', 1)[0])
root = Path(sys.argv[2])
(root/'bin/sudo').write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$INSPECTION"\n')
digest = 'sha256:' + 'a'*64
revision = 'b'*40
for case in ['pinned', 'mismatch', 'manual', 'missing-revision', 'artifact']:
    labels = {} if case in ('missing-revision', 'artifact') else {'org.opencontainers.image.revision': revision}
    output = root / ('inspect-' + case)
    env = dict(os.environ, IMAGE_REGISTRY='ghcr.io/armada-os', IMAGE_NAME='armada',
               CONTAINER_TAG='testing', EXPECTED_DIGEST='sha256:'+'c'*64 if case == 'mismatch' else digest,
               PUBLISH_R2='false' if case == 'artifact' else 'true', GITHUB_OUTPUT=str(output),
               INSPECTION=json.dumps([{'Digest': digest, 'Config': {'Labels': labels}}]))
    if case in ('manual', 'artifact'):
        env['EXPECTED_DIGEST'] = ''
    result = subprocess.run(['bash', '-c', script], env=env, capture_output=True, text=True)
    if case in ('mismatch', 'missing-revision'):
        assert result.returncode != 0 and not output.exists(), case
    else:
        assert result.returncode == 0, result.stderr
        assert f'digest={digest}\n' in output.read_text()
        assert f'revision={revision if labels else ""}\n' in output.read_text()
    print(f'PASS: Disk source inspection {case}')
PY

echo 'Disk image digest tests passed'
