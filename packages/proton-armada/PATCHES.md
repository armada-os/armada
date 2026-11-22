# Patches

Patches applied on top of BASE.env, one directory per tree:

- `patches/proton/` the Proton repo itself (`proton` script, `Makefile.in`)
- `patches/<submodule>/` that submodule, by its path in the Proton repo
  (`wine`, `FEX`, `dxvk`, `vkd3d-proton`, ...)

Each directory applies in `sort -V` order. Each entry's `source` is an upstream
URL pinned to a commit, or `armada` if it's original; a URL source with no
`notes` is verbatim.

- `patches/proton/0001-proton-Add-DXVK-Sarek-fallback-for-GPUs-current-DXVK.patch`
  source: https://github.com/CachyOS/proton-cachyos/tree/cffffad374a5ed5b40ebe3aea6d6c2b5a0cfed23
  notes: Only the DXVK-Sarek build rules, `vulkan.py`, the GPU probe from
  `utilities.py` and its `proton` hooks, ported to Valve's tree. Sarek is
  cloned by `build.sh` instead of a submodule. The probe also requires
  `storageBuffer8BitAccess`, the Sarek choice is part of the prefix config, a
  missing Vulkan loader falls back to DXVK, and GPU grouping no longer uses
  `itertools.groupby`.
- `patches/wine/0001-kernelbase-Fix-GetNativeSystemInfo-in-an-x86_64-process-on-ARM64.patch`
  source: https://gitlab.winehq.org/wine/wine/-/commit/c5a96a0b6c635995718602ca0d0792833de1f46f
- `patches/wine/0002-ntdll-bounds-check-RtlIsEcCode.patch`
  source: https://github.com/The412Banner/proton-wine/commit/5330d49066e4b7fa8e2b96d935d5d76a38ea491e
