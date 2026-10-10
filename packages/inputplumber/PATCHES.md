# Patches

Patches applied on top of BASE.env. Each entry's `source` is an upstream URL pinned
to a commit, or `armada` if it's original; a URL source with no `notes` is verbatim.
`notes` mean the file was modified.

- `patches/0001-fix-gamepad-share-raw-input.patch`
  source: armada
- `patches/0002-fix-force-feedback-reset-effects-when-replacing-targets.patch`
  source: armada
- `patches/0003-feat-Hardware-Support-Add-AYN-Thor-Lite.patch`
  source: https://github.com/ShadowBlip/InputPlumber/pull/746
  notes: AYN Thor Lite support
- `patches/0004-fix-AyaneoHaptics-sleep-between-polls.patch`
  source: armada
- `patches/0005-add-dbus-touch-events.patch`
  source: armada
  notes: Adds a polkit-protected D-Bus method for injecting normalized multitouch values into Steam Deck touchpad targets.
- `patches/0006-native-virtual-trackpad-haptics.patch`
  source: armada
  notes: Uses Steam's native trackpad pulse timing with configurable amplitude and short finite effects while the virtual-pad service holds a live lease. Zero suppresses trackpad pulses without stopping game rumble, which has priority in the shared effect slot. Includes six package tests for scaling, fade, mute, game-rumble priority and lease expiry.
