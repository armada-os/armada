# decky/loader

Armada runs Decky Loader natively: the tagged release's Python backend (with
its frontend built in the `decky-build` stage of the Containerfile) on the
system `python3`, launched by `PluginLoader`, instead of the upstream x86-64
PyInstaller binary under FEX. `build_files/45-install-decky-plugins.sh`
installs it; `loader.env` pins the release. The upstream binary stays as the
launcher's fallback.

Patches are applied to the release's `backend/` directory. Each entry's
`source` is `armada` if it's original.

- `0001-updater-leave-loader-updates-to-the-os-image.patch`
  source: armada
  notes: With DECKY_OS_MANAGED_UPDATES set (by the launcher), the updater reports the loader as not updatable and ignores update requests, so a self-update can't put the x86-64 binary back.
- `0002-plugin-keep-forking-plugin-processes.patch`
  source: armada
  notes: Python 3.14 made forkserver the Linux default start method; plugin processes rely on fork semantics.
