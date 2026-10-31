# Patches

Patches applied on top of BASE.env. Each entry's `source` is an upstream URL pinned
to a commit, or `armada` if it's original; a URL source with no `notes` is verbatim.
`notes` mean the file was modified.

- `patches/0001-disable-turnip-sparse-sync.patch`
  source: https://github.com/batocera-linux/batocera.linux/blob/bca5c05d90b606ad859ba2e4e82ab0a515ccb956/board/batocera/patches/mesa3d/001-fix-freedreno-vulkan.patch
  notes: temporary diagnostic workaround for A740 GPU translation-fault storms;
  disables the graphics/sparse-queue cross-sync introduced by Mesa commit
  `0cc0e786e096dca8cfd88d7088ab7e1a0147d045`
- `patches/0002-add-a830-chip-id.patch`
  source: https://github.com/ROCKNIX/distribution/blob/e485495a942daba186d4a8543e18a1ad09c9a5d5/projects/ROCKNIX/packages/graphics/mesa/patches/SM8750/0001-add-a830-chip-id.patch
  affects: A830
  notes: new patch header; chip IDs verbatim.
- `patches/0004-freedreno-add-a722-support.patch`
  source: https://gitlab.freedesktop.org/mesa/mesa/-/commit/803731f7ed4aa8e8265fe0aff08b85efb3f3c7e9
  affects: A722
  notes: `magic_regs` moved beside `num_vsc_pipes` so 0005 also fits the devel pin.
- `patches/0005-freedreno-a722-blob-regs.patch`
  source: https://github.com/Vauzi-17/710/blob/5db89bde562d/add_710_720_722.py
  affects: A722
  notes: verified on device, adapted into patch
- `patches/0006-freedreno-a722-skip-bv-bin-preamble.patch`
  source: armada
  affects: A722
- `patches/0007-freedreno-a722-no-lpac.patch`
  source: armada
  affects: A722
- `patches/0008-freedreno-a722-disable-uav-ubwc.patch`
  source: armada
  affects: A722
- `patches/0009-freedreno-a722-two-ccus-tile-align-32.patch`
  source: armada
  affects: A722
- `patches/0010-tu-autotune-lower-gmem-bandwidth-multiplier.patch`
  source: https://github.com/WinNative-Emu/Drivers/blob/c71f600a2977a141f21a922c9ed2e14fb09b13d3/patches/apply_balance_variant.py
  affects: all GPUs
  notes: script converted to a patch
- `patches/0011-tu-z-mutable-ubwc.patch`
  source: https://github.com/Vauzi-17/710/blob/6828465a8bc2ae08b705e4a67a6a2bb76197e231/patches/30-tu-z-mutable.py
  affects: A6xx and A7xx up to A740 (not A750 or A8xx)
  notes: script converted to a patch, without its change that kept images with
  component-swapped view formats tiled (swapped red and blue in shadPS4)
- `patches/0012-tu-z-mutable-ubwc-copy-format.patch`
  source: armada
  affects: A740
- `patches/0013-freedreno-a7xx-gen1-no-early-preamble.patch`
  source: armada
  affects: A710, A720, A722, A725, A730 (A710 and A720 only on devel)

Disabled (kept in `patches/disabled/`, which isn't applied):

- `patches/disabled/0001-disable-turnip-sparse-sync.patch`
  source: https://github.com/batocera-linux/batocera.linux/blob/bca5c05d90b606ad859ba2e4e82ab0a515ccb956/board/batocera/patches/mesa3d/001-fix-freedreno-vulkan.patch
  notes: disables the graphics/sparse-queue cross-sync added by Mesa 0cc0e786e096.
  disabled: a temporary diagnostic workaround for A740 GPU translation-fault storms.
- `patches/disabled/0003-ir3-disable-bindless-ubo-const-lowering.patch`
  source: https://github.com/ROCKNIX/distribution/blob/0adbe00f1745512609b289ef9435df897c28b780/projects/ROCKNIX/packages/graphics/mesa/patches/SM8550/0001-freedreno-ir3-vulkan-disable-bindless-ubo-const-lowering.patch
  notes: offsets updated for 26.2.0.
  disabled: ROCKNIX dropped it as no longer needed, and upstream fixed the related
  bugs in 2a841d0d and 2755d64a.

## Variants

Each `variants/<id>/` is an extra Turnip-only build. `VARIANT.env` sets its Mesa
source (`SOURCE_URL` + `SOURCE_SHA256`, default BASE.env's) and which patches above
apply (`BASE_PATCHES`, default all), or takes both from another variant
(`BASED_ON`). Its own `patches/` go on top.

### devel

Mesa main with 0005-0013 (0002 and 0004 are upstream).

### winnative

Based on devel, plus:

- `variants/winnative/patches/0001-tu-emulate-mesh-shaders.patch`
  source: https://github.com/WinNative-Emu/Drivers/blob/c71f600a2977a141f21a922c9ed2e14fb09b13d3/linux/patches/0001-tu-Emulate-VK_EXT_mesh_shader-with-compute.patch
  affects: A7xx and A8xx
  notes: rebased onto the devel pin.
- `variants/winnative/patches/0002-ir3-support-half-wave-subgroups.patch`
  source: https://github.com/WinNative-Emu/Drivers/blob/c71f600a2977a141f21a922c9ed2e14fb09b13d3/linux/patches/0002-tu-ir3-Support-a-required-subgroup-size-of-half-a-wa.patch
  affects: A722, A740, A750, A830 (not A650)
  notes: offsets updated for the devel pin.
- `variants/winnative/patches/0003-ir3-sanitize-a8xx-cube-map-directions.patch`
  source: https://github.com/WinNative-Emu/Drivers/blob/c71f600a2977a141f21a922c9ed2e14fb09b13d3/linux/patches/0003-ir3-Sanitize-cube-map-directions-on-A8XX.patch
  affects: A8xx
  notes: offsets updated for the devel pin.
- `variants/winnative/patches/0004-tu-invalidate-a8xx-bindless-descriptors.patch`
  source: https://github.com/WinNative-Emu/Drivers/blob/c71f600a2977a141f21a922c9ed2e14fb09b13d3/linux/patches/0004-tu-Invalidate-bindless-descriptors-through-the-A8XX-.patch
  affects: A8xx
  notes: flush hunk dropped (upstream c88b6ebd3 covers it); offsets updated.

Disabled (kept in `variants/winnative/patches/disabled/`, which isn't applied):

- `variants/winnative/patches/disabled/0005-freedreno-enable-a740-ubwc-hint.patch`
  source: https://github.com/WinNative-Emu/Drivers/blob/c71f600a2977a141f21a922c9ed2e14fb09b13d3/patches/apply_a7xx_gen2_ubwc_hint.py
  notes: script converted to a patch.
  disabled: upstream Mesa uses this as a compatibility switch when a mismatch
  between drivers breaks scaled blits. Since these are system driver builds this
  switch is unnecessary.
