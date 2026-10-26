# Patches

Patches applied on top of BASE.env. Each entry's `source` is an upstream URL pinned
to a commit, or `armada` if it's original; a URL source with no `notes` is verbatim.
`notes` mean the file was modified.

- `patches/0001-fix-gamepad-share-raw-input.patch`
  source: armada
- `patches/0002-fix-force-feedback-reset-effects-when-replacing-targets.patch`
  source: armada
- `patches/0004-fix-Hardware-Support-KONKR-Pocket-FIT-MCU-system-buttons.patch`
  source: armada
- `patches/0005-feat-ssc-qualcomm-sensor-core-support.patch`
  source: https://github.com/ShadowBlip/InputPlumber/pull/590/commits/3caa7902d92e49b86fed567df61a0677304ae8bf
  notes: Adds the FastRPCDevice.Id polkit action and the INPUTPLUMBER_FASTRPC opt-in, fixes scaling, polling, opening, library loading and sample rate, and moves the driver to the 0.83 pattern.
- `patches/0006-feat-ssc-gyro-auto-calibration.patch`
  source: armada
- `patches/0007-feat-ssc-device-enablement.patch`
  source: armada
