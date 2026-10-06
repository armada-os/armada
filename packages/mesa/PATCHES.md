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
  notes: modified — ported from ROCKNIX, chip-id additions verbatim
- `patches/0003-ir3-disable-bindless-ubo-const-lowering.patch`
  source: https://github.com/ROCKNIX/distribution/blob/0adbe00f1745512609b289ef9435df897c28b780/projects/ROCKNIX/packages/graphics/mesa/patches/SM8550/0001-freedreno-ir3-vulkan-disable-bindless-ubo-const-lowering.patch
  notes: offsets updated for Mesa 26.2.0

`patches/autotune/` only goes into the side Turnip build used by
`armada-autotune-report`, never into the shipped driver.

- `patches/autotune/0001-tu-autotune-track-binning-pass-for-rp-duration.patch`
  source: https://github.com/sunshineinabox/distribution/blob/ba1dad96c1007edd661341b70bf7d9811a825231/projects/ROCKNIX/packages/graphics/mesa/patches/0001-tu-autotune-Track-binning-pass-for-RP-duration.patch
  upstream: https://gitlab.freedesktop.org/mesa/mesa/-/commit/79e16e72329bc871cee6ea23489cfa3b25779ac7
- `patches/autotune/0002-tu-autotune-stabilize-rp-hash-for-replays.patch`
  source: https://github.com/sunshineinabox/distribution/blob/ba1dad96c1007edd661341b70bf7d9811a825231/projects/ROCKNIX/packages/graphics/mesa/patches/0002-tu-autotune-Stabilize-RP-hash-for-replays.patch
  upstream: https://gitlab.freedesktop.org/mesa/mesa/-/commit/af16b1ceb1e60f8b1718bbb7522c105a2b5698b1
- `patches/autotune/0003-tu-autotune-calibrate-bandwidth-model.patch`
  source: https://github.com/sunshineinabox/distribution/blob/ba1dad96c1007edd661341b70bf7d9811a825231/projects/ROCKNIX/packages/graphics/mesa/patches/0003-tu-autotune-calibrate-the-bandwidth-model-and-adapt-it-at-runtime.patch
