# Patches

Patches applied on top of BASE.env. Each entry's `source` is an upstream URL pinned
to a commit, or `armada` if it's original; a URL source with no `notes` is verbatim.
`notes` mean the file was modified.

- `patches/0001-disable-turnip-sparse-sync.patch`
  source: https://github.com/batocera-linux/batocera.linux/blob/bca5c05d90b606ad859ba2e4e82ab0a515ccb956/board/batocera/patches/mesa3d/001-fix-freedreno-vulkan.patch
  notes: temporary diagnostic workaround for A740 GPU translation-fault storms;
  disables the graphics/sparse-queue cross-sync introduced by Mesa commit
  `0cc0e786e096dca8cfd88d7088ab7e1a0147d045`; context trimmed to apply to both
  stable and devel
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
- `patches/0009-freedreno-a722-tile-align-32.patch`
  source: armada
  affects: A722
- `patches/0010-tu-autotune-lower-gmem-bandwidth-multiplier.patch`
  source: https://github.com/WinNative-Emu/Drivers/blob/c71f600a2977a141f21a922c9ed2e14fb09b13d3/patches/apply_balance_variant.py
  affects: all GPUs
  notes: script converted to a patch
- `patches/0011-tu-z-mutable-ubwc.patch`
  source: https://github.com/Vauzi-17/710/blob/6828465a8bc2ae08b705e4a67a6a2bb76197e231/patches/30-tu-z-mutable.py
  affects: A6xx and A7xx up to A740 (not A750 or A8xx)
  notes: script converted to a patch; modified to allow RGBA-type images with no format list to
  go linear, so apps that view them as BGRA render red and blue correctly
- `patches/0012-tu-z-mutable-ubwc-copy-format.patch`
  source: armada
  affects: A740
- `patches/0013-freedreno-a7xx-gen1-no-early-preamble.patch`
  source: armada
  affects: A710, A720, A722, A725, A730 (A710 and A720 only on devel)
- `patches/0015-ir3-array-to-ssa-resolve-trivial-phi-chains.patch`
  source: https://github.com/armada-os/armada/issues/748#issuecomment-6373073950
  affects: all GPUs
  notes: comment shortened
- `patches/0016-freedreno-a8xx-wait-for-zpass-sample-counts.patch`
  source: armada
  affects: A8xx (freedreno GL only)
- `patches/0017-freedreno-a8xx-rb-done-ts-after-each-draw.patch`
  source: armada
  affects: A8xx (freedreno GL only)
- `patches/0018-freedreno-a7xx-write-the-autotune-fence.patch`
  source: armada
  affects: A7xx, A8xx (freedreno GL only)
- `patches/0019-freedreno-pick-gmem-or-sysmem-by-gpu-time.patch`
  source: armada
  affects: A7xx, A8xx by default, older with FD_AUTOTUNE_ALGO=profiled (freedreno GL only)
- `patches/0020-dri3-gamescope-limiter-swap-interval-override.patch`
  source: https://steamdeck-packages.steamos.cloud/archlinux-mirror/sources/jupiter-main/mesa-26.1.2.221562.radeonsi_26.1.2-5.src.tar.gz (steamos-mesa commit `18b3910ac08ebf58e7f43ff1bcf864bee4a077ab`)
  affects: OpenGL over X11 (GLX/EGL DRI3), all GPUs
  notes: line offsets refreshed for 26.3.0. While gamescope's frame limiter is on
  (`GAMESCOPE_LIMITER_FILE` reads 1), GL windows swap with interval 1, so the
  limiter can pace games that turned vsync off.

## Variants

Each `variants/<id>/` is an extra Turnip-only build. `VARIANT.env` sets its Mesa
source (`SOURCE_URL` + `SOURCE_SHA256`, default BASE.env's) and which patches above
apply (`BASE_PATCHES`, default all), or takes both from another variant
(`BASED_ON`). Its own `patches/` go on top.

### devel

Mesa main with 0001, 0005-0013 and 0015.

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
