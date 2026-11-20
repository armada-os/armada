#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

grep -q '"steam_keyboard_mouse"' "$ROOT/system_files/usr/libexec/armada/armada-control"
[[ -x "$ROOT/system_files/usr/libexec/armada/steam-keyboard-mouse" ]]

# A fake InputPlumber: targets and the loaded profile live in files.
cat >"$WORK/busctl" <<'EOF'
#!/usr/bin/env python3
import json, os, sys
work = os.environ["TEST_WORK"]
args = [a for a in sys.argv[1:] if a not in ("--system", "--json=short")]
def read(name):
    with open(f"{work}/{name}") as f:
        return f.read()
def write(name, text):
    with open(f"{work}/{name}", "w") as f:
        f.write(text)
with open(f"{work}/calls", "a") as f:
    f.write(args[4] + "\n")
if args[0] == "get-property":
    name = args[4]
    if name == "TargetDevices":
        print(json.dumps({"type": "as", "data": json.loads(read("targets"))}))
    elif name == "ProfilePath":
        print(json.dumps({"type": "s", "data": read("path")}))
    sys.exit(0)
method, rest = args[4], args[5:]
if method == "GetProfileYaml":
    print(json.dumps({"type": "s", "data": [read("profile")]}))
elif method == "SetTargetDevices":
    paths, counts = [], {}
    for kind in rest[2:]:
        base = "gamepad" if kind not in ("mouse", "keyboard") else kind
        paths.append(f"/org/shadowblip/InputPlumber/devices/target/{base}{counts.get(base, 0)}")
        counts[base] = counts.get(base, 0) + 1
    write("targets", json.dumps(paths))
    write("target_types", " ".join(rest[2:]))
elif method == "LoadProfileFromYaml":
    write("profile", rest[1])
    write("path", "")
elif method == "LoadProfilePath":
    with open(rest[1]) as f:
        write("profile", f.read())
    write("path", rest[1])
EOF
printf '%s\n' '#!/usr/bin/env bash' 'echo deck-uhid' >"$WORK/controller-type"
chmod +x "$WORK/busctl" "$WORK/controller-type"

python3 - "$ROOT" "$WORK" <<'PYEOF'
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import socket
import sys
import re
import threading

root, work = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
os.environ.update(
    TEST_WORK=str(work),
    ARMADA_BUSCTL=str(work / "busctl"),
    ARMADA_CONTROLLER_TYPE=str(work / "controller-type"),
    ARMADA_KEYBOARD_MOUSE_STATE=str(work / "state.json"),
    ARMADA_SESSION_SOCKET=str(work / "session.sock"),
)
loader = importlib.machinery.SourceFileLoader(
    "steam_keyboard_mouse", str(root / "system_files/usr/libexec/armada/steam-keyboard-mouse"))
spec = importlib.util.spec_from_loader(loader.name, loader)
mouse = importlib.util.module_from_spec(spec)
loader.exec_module(mouse)


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


original = "version: 1\nkind: DeviceProfile\nname: Gyro\nmapping:\n- name: LeftTop\n  source_event:\n    gamepad:\n      button: LeftTop\n  target_events:\n  - gamepad:\n      button: LeftPaddle1\n"
saved = work / "gyro.yaml"
saved.write_text(original)
(work / "profile").write_text(original)
(work / "path").write_text(str(saved))
(work / "targets").write_text(json.dumps(["/org/shadowblip/InputPlumber/devices/target/gamepad0"]))

os.geteuid = lambda: 0
mouse.main(["steam-keyboard-mouse", "on"])
loaded = (work / "profile").read_text()
names = re.findall(r"^- name: (.*)$", loaded, re.M)
if names != ["LeftTop", "Armada Steam keyboard mouse", "Armada Steam keyboard mouse click"]:
    fail(f"mappings not appended to the active profile: {names}")
if not loaded.startswith(original):
    fail("active profile replaced instead of extended")
if "      axis:\n        name: RightStick\n" not in loaded or "      button: Left\n" not in loaded:
    fail("right stick mappings malformed")
if (work / "target_types").read_text() != "deck-uhid mouse":
    fail(f"mouse target missing: {(work / 'target_types').read_text()}")

# A second on keeps the original it saved first.
mouse.main(["steam-keyboard-mouse", "on"])
mouse.main(["steam-keyboard-mouse", "off"])
if (work / "path").read_text() != str(saved) or (work / "profile").read_text() != original:
    fail("original profile not restored")
if (work / "target_types").read_text() != "deck-uhid":
    fail(f"targets not restored: {(work / 'target_types').read_text()}")
if (work / "state.json").exists():
    fail("state left behind")

# Off without on touches nothing.
(work / "calls").unlink()
mouse.main(["steam-keyboard-mouse", "off"])
if (work / "calls").exists():
    fail("off without on called InputPlumber")

# A mouse target that was already there stays.
(work / "targets").write_text(json.dumps([
    "/org/shadowblip/InputPlumber/devices/target/gamepad0",
    "/org/shadowblip/InputPlumber/devices/target/keyboard0",
    "/org/shadowblip/InputPlumber/devices/target/mouse0",
]))
(work / "target_types").write_text("untouched")
mouse.main(["steam-keyboard-mouse", "on"])
mouse.main(["steam-keyboard-mouse", "off"])
if (work / "target_types").read_text() != "untouched":
    fail("changed targets that already had a mouse")

# A profile loaded from YAML has no path; it comes back from the saved YAML.
(work / "path").write_text("")
mouse.main(["steam-keyboard-mouse", "on"])
mouse.main(["steam-keyboard-mouse", "off"])
if (work / "profile").read_text() != original:
    fail("pathless profile not restored")

# An empty mapping list becomes a block list.
(work / "profile").write_text("version: 1\nkind: DeviceProfile\nname: Empty\nmapping: []\n")
(work / "path").write_text("")
mouse.main(["steam-keyboard-mouse", "on"])
if not (work / "profile").read_text().startswith("version: 1\nkind: DeviceProfile\nname: Empty\nmapping:\n- name: Armada"):
    fail(f"empty mapping not extended: {(work / 'profile').read_text()!r}")
mouse.main(["steam-keyboard-mouse", "off"])

# A profile not ending in its mapping list is left alone.
(work / "profile").write_text("version: 1\nmapping:\n- name: A\nkind: DeviceProfile\n")
try:
    mouse.main(["steam-keyboard-mouse", "on"])
    fail("extended a profile with an unexpected layout")
except RuntimeError:
    pass
if (work / "profile").read_text() != "version: 1\nmapping:\n- name: A\nkind: DeviceProfile\n":
    fail("changed a profile with an unexpected layout")
(work / "state.json").unlink(missing_ok=True)

# The session user asks armada-control instead.
server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(str(work / "session.sock"))
server.listen(1)
requests = []


def serve():
    conn, _ = server.accept()
    with conn:
        requests.append(json.loads(conn.makefile().readline()))
        conn.sendall(b'{"ok":true,"result":{"enabled":true}}\n')


thread = threading.Thread(target=serve)
thread.start()
os.geteuid = lambda: 1000
(work / "calls").unlink(missing_ok=True)
mouse.main(["steam-keyboard-mouse", "on"])
thread.join(5)
if requests != [{"action": "steam_keyboard_mouse", "enabled": True}]:
    fail(f"unexpected session request: {requests}")
if (work / "calls").exists():
    fail("session user called InputPlumber directly")
if mouse.main(["steam-keyboard-mouse", "toggle"]) != 2:
    fail("accepted an unknown command")
print("steam keyboard mouse tests passed")
PYEOF
