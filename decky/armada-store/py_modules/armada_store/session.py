import subprocess

from .proc import clean_env

SESSION_CONTROL = "/usr/libexec/armada/session-control"


# Steam rewrites shortcuts.vdf on exit, so tools that edit it have to run with
# Steam closed. Switching sessions is the only way to get there from game mode.
def switch_to_desktop():
    result = subprocess.run([SESSION_CONTROL, "switch-desktop"], capture_output=True, timeout=30,
                            env=clean_env())
    if result.returncode != 0:
        raise RuntimeError((result.stderr or b"").decode("utf-8", "replace").strip()
                           or "session switch failed ({})".format(result.returncode))
