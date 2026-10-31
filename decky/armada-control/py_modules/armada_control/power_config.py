from io import StringIO
from pathlib import Path
from threading import RLock


POWER_CONFIG = Path("/etc/armada/power-profiles.conf")
FACTORY_POWER_CONFIG = Path("/usr/share/armada/power-profiles.conf")

# Decky runs saves in separate worker threads against the same power config.
POWER_CONFIG_LOCK = RLock()


def render_config(parser):
    output = StringIO()
    parser.write(output)
    return output.getvalue()
