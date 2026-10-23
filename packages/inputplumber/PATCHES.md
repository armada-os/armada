# Patches

Patches applied on top of BASE.env. Each entry's `source` is an upstream URL pinned
to a commit, or `armada` if it's original; a URL source with no `notes` is verbatim.
`notes` mean the file was modified.

- `patches/0001-fix-gamepad-share-raw-input.patch`
  source: armada
- `patches/0002-fix-force-feedback-reset-effects-when-replacing-targets.patch`
  source: armada
- `patches/0003-fix-AyaneoHaptics-sleep-between-polls.patch`
  source: armada
- `patches/0004-fix-Hardware-Support-KONKR-Pocket-FIT-MCU-system-buttons.patch`
  source: armada
- `patches/0005-feat-Hardware-Support-Qualcomm-SSC-sensors.patch`
  source: https://github.com/ShadowBlip/InputPlumber/pull/590/commits/3caa7902d92e49b86fed567df61a0677304ae8bf
  notes: Rebased on latest InputPlumber; adds the FastRPCDevice.Id polkit action the upstream policy test requires.
- `patches/0007-add-fastrpc-config-to-devices.patch`
  source: armada
- `patches/0008-feat-Manager-opt-in-to-FastRPC-devices.patch`
  source: armada
- `patches/0009-fix-ssc-pass-gyro-rad-s-through.patch`
  source: armada
- `patches/0010-fix-ssc-drain-glib-main-context.patch`
  source: armada
- `patches/0011-fix-ssc-keep-retrying-until-the-SSC-answers.patch`
  source: armada
- `patches/0012-fix-ssc-load-libssc-by-its-versioned-soname.patch`
  source: armada
- `patches/0013-feat-ssc-open-the-sensors-at-200-Hz.patch`
  source: armada
