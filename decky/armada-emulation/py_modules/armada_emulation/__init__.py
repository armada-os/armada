"""Armada Emulation: emulators and their setup. Importing this package
configures the shared engine in armada_apps for Emulation."""

from armada_apps.catalog import BundledSource
from armada_apps.profile import configure

from . import setup

configure(
    name="armada-emulation",
    env="ARMADA_EMULATION",
    source=BundledSource(),
    after_install=setup.after_install,
    base_overrides=setup.BASE_OVERRIDES,
    payload_extra=setup.payload_extra,
)
