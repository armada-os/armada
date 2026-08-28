<p align="center">
  <a href="https://armadaos.dev/">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset=".github/assets/armada-mark-white.svg">
      <img src=".github/assets/armada-mark-black.svg" alt="Armada" width="112">
    </picture>
  </a>
</p>

<h1 align="center">Armada</h1>

<p align="center"><strong>SteamOS-like Linux for ARM handhelds</strong></p>

<p align="center">
  Armada brings Steam, FEX, Proton, and a full Linux desktop to supported ARM64 gaming handhelds.
</p>

<p align="center">
  <a href="https://github.com/armada-os/armada/actions/workflows/build.yml"><img alt="Build status" src="https://github.com/armada-os/armada/actions/workflows/build.yml/badge.svg?branch=main"></a>
  <a href="https://armadaos.dev/"><img alt="Documentation" src="https://img.shields.io/badge/docs-armadaos.dev-18181a?style=flat"></a>
  <a href="LICENSE.md"><img alt="GPL-2.0-or-later license" src="https://img.shields.io/badge/license-GPL--2.0--or--later-18181a?style=flat"></a>
  <a href="https://discord.gg/HdmdSxTD5S"><img alt="Discord community" src="https://img.shields.io/badge/chat-Discord-5865F2?style=flat&amp;logo=discord&amp;logoColor=white"></a>
</p>

<p align="center">
  <a href="https://armadaos.dev/getting-started/flashing-to-an-sd-card/"><strong>Install Armada</strong></a>
  ·
  <a href="https://armadaos.dev/devices/supported-devices/">Supported devices</a>
  ·
  <a href="https://armadaos.dev/">Documentation</a>
  ·
  <a href="https://armadaos.dev/troubleshooting/known-issues/">Known issues</a>
</p>

> [!WARNING]
> Armada is prototype software under active development. Installation requires
> bootloader changes that can brick a device, corrupt partitions, or cause data
> loss. Check the current [supported-device list](https://armadaos.dev/devices/supported-devices/),
> back up your data, and read the complete [installation guide](https://armadaos.dev/getting-started/flashing-to-an-sd-card/)
> before proceeding.

## About Armada

Armada is a gaming-focused Linux distribution built on
[Fedora bootc](https://github.com/bootc-dev/bootc) with device support derived
from [ROCKNIX](https://github.com/ROCKNIX). It combines a console-first Steam
experience with a full KDE Plasma desktop while remaining an open, image-based
operating system.

Highlights include:

- ARM64 Steam with FEX translation and Proton compatibility
- Gaming Mode and a full KDE Plasma Desktop Mode
- Over-the-air operating system updates
- SD-card boot with optional internal-storage installation
- Handheld-focused power, fan, controller, and calibration controls
- Per-game compatibility settings through Armada Control

## Documentation

The [Armada documentation](https://armadaos.dev/) is the source of truth for
device support, installation, updates, current limitations, and recovery. Use
the guides there rather than instructions copied from older releases or posts.

| I want to… | Guide |
|---|---|
| Install Armada | [Flash to an SD card](https://armadaos.dev/getting-started/flashing-to-an-sd-card/) |
| Check my handheld | [Supported devices](https://armadaos.dev/devices/supported-devices/) |
| Learn the interface | [Using Armada](https://armadaos.dev/using-armada/) |
| Update an installation | [Updating](https://armadaos.dev/getting-started/updating/) |
| Find help | [FAQ](https://armadaos.dev/troubleshooting/frequently-asked-questions/) · [Known issues](https://armadaos.dev/troubleshooting/known-issues/) |
| Report a bug | [Github Issues](https://github.com/armada-os/armada/issues)

## Development

This repository assembles the Armada bootc image and its flashable disk images.
The development recipes require [just](https://just.systems/) and
[Podman](https://podman.io/):

```console
$ just check   # Run the test suite and check recipe formatting
$ just build   # Build the local bootc container image
$ just --list  # Show disk-image, VM, and other development recipes
```

Issues and pull requests are welcome. For installation or device support, check
the [troubleshooting documentation](https://armadaos.dev/troubleshooting/frequently-asked-questions/)
or ask in the [Armada Discord community](https://discord.gg/HdmdSxTD5S).

## Credits

See the [project credits](https://armadaos.dev/project/credits/) for the upstream
projects and contributors that make Armada possible. The Armada logo was
created by [Rax](https://github.com/Raxcoms).

## License

Armada's own code is licensed under **GPL-2.0-or-later**. Bundled components
retain their upstream licenses. See [LICENSE.md](LICENSE.md).
