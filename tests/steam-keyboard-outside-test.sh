#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

[[ -x "$ROOT/system_files/usr/libexec/armada/steam-keyboard-outside" ]]

printf '%s\n' '#!/usr/bin/env bash' 'printf "%s\n" "$*" >>"$TEST_LOG"' >"$WORK/steam"
printf '%s\n' '#!/usr/bin/env bash' 'printf "mouse %s\n" "$*" >>"$TEST_LOG"' >"$WORK/keyboard-mouse"
printf '%s\n' '#!/usr/bin/env bash' "echo ARMADA_PRIMARY_CONNECTOR=DSI-1" "echo ARMADA_PANEL_ORIENTATION=left" >"$WORK/device-env"
chmod +x "$WORK"/*

python3 - "$ROOT" "$WORK" <<'PYEOF'
import importlib.machinery
import importlib.util
import os
import pathlib
import sys

root, work = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
os.environ.update(
    TEST_LOG=str(work / "log"),
    ARMADA_STEAM=str(work / "steam"),
    ARMADA_KEYBOARD_MOUSE=str(work / "keyboard-mouse"),
    ARMADA_DEVICE_ENV=str(work / "device-env"),
    ARMADA_STEAM_KEYBOARD_CLOSED=str(work / "closed"),
)
loader = importlib.machinery.SourceFileLoader(
    "steam_keyboard_outside", str(root / "system_files/usr/libexec/armada/steam-keyboard-outside"))
spec = importlib.util.spec_from_loader(loader.name, loader)
outside = importlib.util.module_from_spec(spec)
loader.exec_module(outside)


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


# Taps on an Odin 2 Portal (panel orientation left, touch 0-1079 x 0-1919) against
# where the app saw them on the 1280x720 screen.
for raw, seen in [((28, 1865), (37 / 1280, 19 / 720)),
                  ((7, 7), (1275 / 1280, 5 / 720)),
                  ((1071, 1895), (17 / 1280, 714 / 720))]:
    x, y = outside.to_screen("left", raw[0] / 1079, raw[1] / 1919)
    if abs(x - seen[0]) > 0.03 or abs(y - seen[1]) > 0.03:
        fail(f"left: raw {raw} mapped to ({x:.3f},{y:.3f}), app saw ({seen[0]:.3f},{seen[1]:.3f})")
for orientation in ("normal", "right", "inverted"):
    corners = {outside.to_screen(orientation, u, v) for u in (0, 1) for v in (0, 1)}
    if corners != {(0, 0), (0, 1), (1, 0), (1, 1)}:
        fail(f"{orientation} does not map the panel onto the screen: {corners}")
if outside.to_screen("right", 0.2, 0.1) != (0.1, 0.8) or outside.to_screen("inverted", 0.2, 0.1) != (0.8, 0.9):
    fail("right/inverted rotate the wrong way")

if outside.panel_orientation() != "left":
    fail("panel orientation not read from device-env")


class App:
    def __init__(self):
        self.warped = None

    def warp(self, x, y):
        self.warped = (x, y)


app = App()
outside.close_keyboard(app, 0.25, 0.1)
if (work / "log").read_text() != "mouse off\nsteam://close/keyboard\n":
    fail(f"unexpected close sequence: {(work / 'log').read_text()!r}")
if not (work / "closed").exists():
    fail("closed marker not left for steam-keyboard-follow")
if app.warped != (0.25, 0.1):
    fail(f"pointer not put back where the tap was: {app.warped}")
outside.close_keyboard(None, 0.5, 0.2)  # no host display to warp on
if outside.OUTSIDE_ABOVE != 0.5:
    fail("outside threshold changed; the keyboard can reach just under half the screen")
print("steam keyboard outside tests passed")
PYEOF
