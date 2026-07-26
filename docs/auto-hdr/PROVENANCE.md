# HDR implementation provenance

## License boundary

Armada-original session, settings, and Steam integration in this repository are
licensed under `GPL-2.0-or-later` as described by the root `LICENSE.md`.
Gamescope compositor changes remain under Gamescope's BSD-2-Clause license and
are carried by the paired package patch series, not copied into Armada
userspace.

## Implementation sources

| Source | License or status | Use |
|---|---|---|
| Armada repository | GPL-2.0-or-later for Armada-original code | Device qualification, session integration, persistent preferences, Steam settings, quick-access controls, tests |
| Valve Gamescope | BSD-2-Clause with its documented file-level exceptions | Existing compositor HDR path, color-management architecture, native HDR state, inverse-tone-mapping baseline |
| ITU-R BT.709 | Technical standard | SDR primaries, white point, and signal interpretation |
| ITU-R BT.2020 | Technical standard | HDR working and output primaries |
| ITU-R BT.2446 | Technical report | Inverse-tone-mapping reference |
| SMPTE ST 2084 | Technical standard | PQ transfer function |
| Khronos Vulkan specifications | API specification | Image formats, color spaces, shader and presentation behavior |

No implementation code, shader code, constants, lookup tables, or control flow
were copied from Special K. It was used only as a black-box functional and
image-quality comparison during development.

The Quality scene analysis, temporal policy, highlight behavior, gamut
protection, runtime protocol, and user controls were independently implemented
from compatible source code, standards, published research, and direct device
testing. Exact compositor file and commit provenance is recorded alongside the
paired Gamescope package patches.
