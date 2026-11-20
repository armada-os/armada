import re
import subprocess

CONTROL = "armada_auto_hdr"


def auto_hdr_supported(env):
    try:
        return int(env.get("ARMADA_HDR_NITS", "0")) > 0
    except (TypeError, ValueError):
        return False


class AutoHdrController:
    def __init__(self, env, command):
        self.supported = auto_hdr_supported(env)
        self.command = command
        self.available = None
        self.active = False

    def apply(self, enabled):
        enabled = bool(enabled)
        if not self.supported or enabled == self.active:
            return self.active
        if not self.control_available():
            return self.active
        try:
            self.command(CONTROL, str(int(enabled)))
        except (OSError, subprocess.SubprocessError):
            # Preserve uncertain state: the command may have reached Gamescope.
            self.active = None
        else:
            self.active = enabled
        return self.active

    def clear(self):
        return self.apply(False)

    def control_available(self):
        if self.available is not None:
            return self.available
        try:
            result = self.command("help")
        except (OSError, subprocess.SubprocessError):
            return False
        output = (result.stdout or "") + (result.stderr or "")
        self.available = bool(re.search(r"\barmada_auto_hdr:", output))
        return self.available
