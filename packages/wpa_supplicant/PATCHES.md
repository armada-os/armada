# Patches

Patches applied on top of BASE.env. Each entry's `source` is an upstream URL pinned
to a commit, or `armada` if it's original; a URL source with no `notes` is verbatim.
`notes` mean the file was modified.

- `patches/0001-avoid-redundant-6ghz-rescan-after-resume.patch`
  source: https://steamdeck-packages.steamos.cloud/archlinux-mirror/sources/holo-3.9/wpa_supplicant-2%3A2.12-1.2.src.tar.gz
  upstream: https://lists.infradead.org/pipermail/hostap/2026-August/045451.html
- `patches/0002-no-forced-rescan-after-restricted-scan.patch`
  source: https://steamdeck-packages.steamos.cloud/archlinux-mirror/sources/holo-3.9/wpa_supplicant-2%3A2.12-1.2.src.tar.gz
  upstream: https://lists.infradead.org/pipermail/hostap/2026-August/045452.html
