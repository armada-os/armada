# Patches

Patches applied on top of BASE.env. Each entry's `source` is an upstream URL pinned
to a commit, or `armada` if it is original; a URL source with no `notes` is verbatim.
`notes` mean the file was modified.

- `patches/0001-armada-disable-session-xtrace.patch`
  source: armada
- `patches/0002-armada-extend-startup-socket-timeout.patch`
  source: armada
- `patches/0003-armada-add-independent-itm-target.patch`
  source: armada
- `patches/0004-add-device-quirks.patch`
  source: https://github.com/OpenGamingCollective/gamescope-session/commit/2e3dd1ad5f50e2efc5a554bd5fda0e27c2d131a0
- `patches/0005-update-AYANEO-Pocket-DMG-scaling.patch`
  source: https://github.com/OpenGamingCollective/gamescope-session/commit/6a6f8216c36836fdf38571c259a811a105e55033
- `patches/0006-add-KONKR-Pocket-FIT-Elite.patch`
  source: https://github.com/OpenGamingCollective/gamescope-session/commit/b45f0ad079d48f021faae4a9bb859ce66933c774
- `patches/0007-add-Retroid-Pocket-Nova.patch`
  source: https://github.com/OpenGamingCollective/gamescope-session/commit/c01b4bff0eba5a64455b610c212265c76e339b62
- `patches/0008-source-armada-specific-quirks.patch`
  source: armada
- `patches/0009-add-drm-lease-functions.patch`
  source: armada
- `patches/0010-armada-force-vulkan-realtime-option.patch`
  source: armada
- `patches/0008-fix-konkr-fit-elite-scaling.patch`
  source: armada
  notes: Corrects the KONKR Pocket FIT Elite quirk from `OUTPUT_MM` to
  `FAKE_OUTPUT_MM`, which is the variable forwarded to Gamescope for SteamUI
  physical-size scaling.
