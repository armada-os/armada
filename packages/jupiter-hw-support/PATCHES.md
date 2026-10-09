# Patches

Patches applied on top of BASE.env. Each entry's `source` is an upstream URL pinned
to a commit, or `armada` if it's original; a URL source with no `notes` is verbatim.
`notes` mean the file was modified.

- `patches/0001-armada-storage-behavior.patch`
  source: armada
  notes: Adapts SteamOS storage helpers to Armada's `armada` user, uses
    `/usr/bin/steam` for mount-result URLs, extends the block-device settle
    window, limits automount/formatting to non-system SD-card devices, and
    removes `/dev/sd*` USB/UFS handling.
- `patches/0002-armada-polkit-helper-safety.patch`
  source: armada
  notes: Adds hostname validation before calling `hostnamectl`, and makes the
    SSH helper target `sshd.service` explicitly.
