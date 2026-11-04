`armada-autohdr` builds an independent shared library with a C API. The runtime
RPM installs `libarmada-autohdr.so.1`; the development RPM installs its header,
linker symlink and pkg-config metadata.

```sh
just package armada-autohdr
just package gamescope
```

The core in `src/` accepts plain matrices, luminance values and frame facts.
It owns inverse tone mapping, eligibility, presentation state and pipeline
retry policy. It has no Gamescope, Vulkan or DRM header dependency.

All Gamescope hooks, adapter code and shader selection live in
[`0035-drm-add-direct-auto-hdr.patch`](../gamescope/patches/0035-drm-add-direct-auto-hdr.patch),
applied through its normal numbered patch stack. Gamescope builds against this
library's development RPM. The adapter reuses Gamescope's SDR mapping and LUT
builder for both scanout and composition while SDR overlays keep their own LUTs.
Gamescope updates still need review of the LUT stage order, frame/layer contract,
shader slots and libliftoff boundary.

The disabled setting bypasses library presentation and allocation processing.
Switching it off clears the previous frame's constraints once. Color generation,
allocation and shader selection use separate hooks at their existing stages;
combining them at presentation would replace more of Gamescope's pipeline.

Build and test the library without Gamescope:

```sh
cmake -S packages/armada-autohdr -B /tmp/armada-autohdr-build
cmake --build /tmp/armada-autohdr-build
ctest --test-dir /tmp/armada-autohdr-build --output-on-failure
```

The production build enables fast math to match Gamescope. Configure with
`-DARMADA_AUTOHDR_FAST_MATH=OFF` to test the strict floating-point build.
Compatible updates keep the version 1 C ABI; breaking changes need a new soname.
Gamescope's package hash follows the public header and its own package files.
Core-only updates can reuse the existing Gamescope binary.

Run the integration color tests against a fully prepared Gamescope source tree
with the library's development files installed:

```sh
bash packages/gamescope/tests/gamescope-auto-hdr-test.sh /path/to/gamescope
CXXFLAGS='-O2 -ffast-math' bash packages/gamescope/tests/gamescope-auto-hdr-test.sh /path/to/gamescope
```

These tests use the compiler, Catch2 and GLM already required by Gamescope.
They do not verify hardware presentation. Device checks must cover direct
scanout, composition, SDR overlays, native HDR, the disabled setting and a
leased secondary screen.
