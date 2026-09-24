# Patches

Patches applied on top of BASE.env. Each entry's `source` is an upstream URL pinned
to a commit, or `armada` if it's original; a URL source with no `notes` is verbatim.
`notes` mean the file was modified.

- `patches/0001-armada-keep-devices-active-on-suspend.patch`
  source: armada
- `patches/0002-wifi-scan-only-last-associated-freq-after-resume.patch`
  source: https://steamdeck-packages.steamos.cloud/archlinux-mirror/sources/holo-3.9/networkmanager-1.58.0-1.7.src.tar.gz
  upstream: https://gitlab.freedesktop.org/NetworkManager/NetworkManager/-/merge_requests/2514
