# Patches

Patches applied on top of BASE.env. Each entry's `source` is an upstream URL pinned
to a commit, or `armada` if it's original; a URL source with no `notes` is verbatim.
`notes` mean the file was modified.

The 0001-0009 is `arunr/steam-frame` rebased onto BASE.env's commit. Two of its
eleven commits (`47f8cea` rustfmt.toml, `cc4b8c6` sh bash-ism) are already
upstream and dropped out.

- `patches/0001-Initial-support-for-Steam-Frame.patch`
  source: https://gitlab.steamos.cloud/holo/steamos-manager/-/commit/90d24abea305704876ac4884cda3bb4942527945
  notes: Rebase drops the `#[cfg(target_arch)]` gating and the aarch64 `device_match()` stub that hardcoded Steam Frame. main's matcher already does DMI and devicetree, and its `steam_deck_variant()` already returns `Unknown` without DMI. Keeps the `sysfs_path` field the devfreq driver reads. `DevfreqPerformanceLevel` gains `Eq`/`Hash` because main's `GpuPerformanceLevel` now derives them. `steam-frame.toml` keeps main's devicetree match rather than reverting it to DMI.
- `patches/0002-Factor-out-platform-profiles-into-its-own-manager.patch`
  source: https://gitlab.steamos.cloud/holo/steamos-manager/-/commit/e6a4bbc732967093029eb3819bb3125f29279546
- `patches/0003-Add-a-custom-platform-profile-mechanism.patch`
  source: https://gitlab.steamos.cloud/holo/steamos-manager/-/commit/127edcd396364829b5af6bb1e56dceb340d37672
- `patches/0004-Explicitly-track-state-in-devfreq-gpu-driver.patch`
  source: https://gitlab.steamos.cloud/holo/steamos-manager/-/commit/dda5c635733f68a8d573803044bc7dd26c662b46
  notes: Keeps the `&mut self` signature change but not the `#[allow(irrefutable_let_patterns)]` it re-adds. main removed that in `8e2883d` once a second `GpuPerformanceLevel` variant made the pattern refutable.
- `patches/0005-Add-instructions-to-resolve-common-build-issues.patch`
  source: https://gitlab.steamos.cloud/holo/steamos-manager/-/commit/468ae099eb0e2a9879627a69b26f5bae1dc91683
- `patches/0006-Add-gpufreq_limit-to-custom-profiles.patch`
  source: https://gitlab.steamos.cloud/holo/steamos-manager/-/commit/bc0737936daa1f641849e2aea71c15c379fed4ea
- `patches/0007-Fix-a-bug-where-UI-could-latch-a-bad-manual-clock-va.patch`
  source: https://gitlab.steamos.cloud/holo/steamos-manager/-/commit/c8d0bcd1ed9911d531a3f2adbb0a3d5e2b7f2538
- `patches/0008-Add-GPU-manual-clock-minimum-value.patch`
  source: https://gitlab.steamos.cloud/holo/steamos-manager/-/commit/2f7c1c3028425e63bc1191fbfa1ef801e9300334
- `patches/0009-Rename-minfreq-field-to-min_freq-for-consistency.patch`
  source: https://gitlab.steamos.cloud/holo/steamos-manager/-/commit/9d43f89f1f252da8f1e1b6ad2b8bccff30edbb3b
- `patches/0010-Allow-CpuScaling1-to-be-served-by-a-remote-interface.patch`
  source: armada
  notes: `armada-powerd` owns the governor as part of a power profile and `steamos-priv-write` refuses Steam's writes, so remoting it lands Steam's control in our profile model. Needs both halves: a remote only fills a hole where no local implementation exists, and `CpuScaling1` is the one that registers unconditionally.
- `patches/0011-inputplumber-Only-manage-target-devices-when-configu.patch`
  source: armada
  notes: `DeckService` races `armada-controller-type.service` at boot and re-asserts on every composite-device recreation. With no `[inputplumber]` section it forces `[deck-uhid]`, and `is_deck()` wants exactly one target, so our keyboard/mouse extras are dropped with no user involvement. We cannot express our targets in the config either - an unknown `InputPlumberTargetDevice` fails deserialization and drops the whole SoC file.
- `patches/0012-wifi-Always-write-wpa_supplicant-as-the-backend.patch`
  source: armada
  notes: Steam derives the backend it wants from its own `steamos_wifi_force_wpa_supplicant` setting and only skips the write when the current value already matches, so no NetworkManager config can refuse it. With the setting off it writes `iwd` on every launch. Pinning it in the daemon is the only place the request can be declined.
