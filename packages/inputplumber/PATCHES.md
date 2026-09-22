# Patches

Patches applied on top of BASE.env. Each entry's `source` is an upstream URL pinned
to a commit, or `armada` if it's original; a URL source with no `notes` is verbatim.
`notes` mean the file was modified.

- `patches/0001-fix-gamepad-share-raw-input.patch`
  source: armada
- `patches/0002-fix-force-feedback-reset-effects-when-replacing-targets.patch`
  source: armada
- `patches/0004-feat-Hardware-Support-Add-AYN-Thor-Lite.patch`
  source: armada
  notes: Matches the Thor Lite device-tree compatible and its Retroid-protocol MCU gamepad, reusing the existing Retroid Type 1 capability map.
