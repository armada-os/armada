`armada-autohdr` builds an optional color provider. The runtime RPM installs
`libarmada-autohdr.so.2`; the development RPM installs the plain C interface,
linker symlink and pkg-config metadata.

```sh
just package armada-autohdr
just package gamescope
```

The provider accepts matrices, luminance values and frame facts. It owns inverse
tone mapping, eligibility, color plans, presentation sequencing and scanout
retries. It has no Gamescope, GLM, Vulkan, DRM or libliftoff header dependency.

Gamescope's host bridge and shader selection live in
[`0035-drm-add-direct-auto-hdr.patch`](../gamescope/patches/0035-drm-add-direct-auto-hdr.patch),
applied through its numbered patch stack. Gamescope builds against the interface
header and loads the provider at runtime. An absent or incompatible provider
keeps the native path. The host reuses its SDR mapping and LUT builder for both
scanout and composition while SDR overlays keep their own LUTs.

The host keeps its textures, frame references and atomic requests. Synchronous
callbacks attach LUTs, present frames and test plane allocation. Each provider
instance owns its state; callbacks do not retain host objects. A configured
color plan stays valid until that instance is configured again or destroyed.

The disabled setting bypasses provider processing after one-time cleanup.
Gamescope's normal pending/current color state decides when to rebuild LUTs.
Updates still need review of color-stage order, frame/layer facts, shader slots
and the libliftoff callback boundary.

Build and test the library without Gamescope:

```sh
cmake -S packages/armada-autohdr -B /tmp/armada-autohdr-build
cmake --build /tmp/armada-autohdr-build
ctest --test-dir /tmp/armada-autohdr-build --output-on-failure
```

The production build enables fast math to match Gamescope. Configure with
`-DARMADA_AUTOHDR_FAST_MATH=OFF` to test the strict floating-point build.
`gamescope_color_provider_get_interface` is the only exported entry point. It
returns the requested versioned table or null. Consumers check its version,
size and required callbacks before creating an instance. Breaking interface
changes need a new provider ABI. Soname 2 replaces the former direct-call API.
Gamescope's package hash follows the interface header and its own package files;
compatible provider-only updates can reuse the existing Gamescope binary.

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
