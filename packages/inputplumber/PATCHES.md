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
  source: https://github.com/ShadowBlip/InputPlumber/pull/590
  notes: Rebased on latest InputPlumber; adds the FastRPCDevice.Id polkit action the upstream policy test requires.
- `patches/0006-fix-ssc-keep-SSC-libraries-loaded.patch`
  source: https://github.com/tycosnh/InputPlumber/commit/a60b3192eb76b1758a481cbffecbc3487ca2d232
  notes: Only the RTLD_NODELETE change. The accelerometer pre-scaling is dropped: InputPlumber now carries m/s² and the targets scale it, so it scaled twice.
- `patches/0007-add-fastrpc-config-to-devices.patch`
  source: armada
  notes: fastrpc matcher pinned to fastrpc-adsp. Boards like the Retroid Pocket 6 also expose fastrpc-cdsp/-cdsp-secure, and an unqualified matcher spawns doomed SSC CompositeDevices on the compute DSP.
- `patches/0008-feat-Manager-opt-in-to-FastRPC-devices.patch`
  source: armada
  notes: FastRPC sources stay off unless INPUTPLUMBER_FASTRPC=1, armada-control's "Enable Gyro" toggle sets it and restarts InputPlumber. Struct and initializer context refreshed for 0.82.0.
- `patches/0009-fix-ssc-pass-gyro-rad-s-through.patch`
  source: armada
  notes: Same double-scaling as above for the gyro (about 917x on deck-uhid).
- `patches/0010-fix-ssc-drain-glib-main-context.patch`
  source: armada
  notes: One GLib iteration per poll handled about one QRTR message, so the SSC backlog stalled the stream for good (within seconds at 200 Hz).
