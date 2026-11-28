"""Armada Store: the general app catalog. Importing this package configures
the shared engine in armada_apps for the Store."""

from armada_apps.profile import configure

from . import android, remote_catalog

# Armada Emulation manages these. The Store keeps its records for them (an
# older image still uses them) but never offers, retires or acts on them.
MOVED_TO_EMULATION = frozenset((
    "retroarch", "dolphin", "cemu", "ppsspp", "duckstation", "armsx2", "rpcs3",
    "vita3k", "melonds", "azahar", "xemu", "flycast", "scummvm", "bigpemu",
    "mame", "primehack", "ymir", "es-de", "steam-rom-manager",
))

configure(
    name="armada-store",
    env="ARMADA_STORE",
    source=remote_catalog,
    kinds={"android": android},
    extra_apps=lambda: android.apps(),
    hidden_ids=MOVED_TO_EMULATION,
    reserved_categories=("android",),
)
