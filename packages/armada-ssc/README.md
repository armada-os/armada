# SSC Data

Per-board data for the Snapdragon Sensor Core (SSC), which serves the gyro and
accelerometer. The ADSP has no storage of its own; `hexagonrpcd` answers its
file requests from `/usr/share/armada/ssc/<device id>/`, which this package
unpacks from `data/<device id>.tar.gz`. A board supports gyro when its
archive exists.

The ADSP writes a few bookkeeping files at boot, so `armada-ssc` serves a
fresh copy of that directory from `/run/armada/ssc`. Every boot starts from
the shipped data.

Each archive is a straight copy from the board's stock Android partitions:

| Archive path | Android source |
|---|---|
| `sensors/config/` | `vendor/etc/sensors/config/` |
| `sensors/sns_reg.conf` | `vendor/etc/sensors/sns_reg_config` |
| `sensors/registry/` | `persist/sensors/registry/registry/` |
| `sensors/sns_reg_version` | `persist/sensors/registry/sns_reg_version` |

One change: `registry/sns_reg_config` records each config file's mtime, and
the image ships every file with mtime 0, so the capture writes 0 there.
Otherwise the ADSP re-parses every config at boot, which the Thor does not
survive.

`patches/<device id>/` holds changes applied on top of a board's capture, so
the archive stays a straight copy. The Odin 3 turns off SSC island mode
there: with island on, s2idle entered right after a sensor close hangs the
SoC.

`socinfo` links to `/sys/devices/soc0`, and `SOURCE` records the Android build
and the sha256 of each ADSP firmware file the board was running at capture.
The registry is only valid for that firmware, so the image build fails if the
board's files under `system_files/usr/lib/firmware/qcom/` differ, even with the
same version string; recapture on an image that runs the new firmware. Split
images (`.mdt`) are hashed with every `.bNN` segment. When the board has an
SLPI remoteproc, its firmware is hashed the same way: the Pocket 5 gyro runs
there, not in the audio ADSP image. The capture refuses to run when the ADSP
may be running other firmware: `firmware_class.path` set, a runtime firmware
override, or a copy in a directory the kernel searches first.

## Capture

On the board, booted into Armada, with the Android partitions mounted
read-only. `vendor` sits in the `super` partition; map it with
[make-dynpart-mappings](https://gitlab.com/flamingradian/make-dynpart-mappings).

```sh
make-dynpart-mappings "$(readlink -f /dev/disk/by-partlabel/super)"
mkdir -p /run/vendor /run/persist
mount -o ro /dev/mapper/vendor_a /run/vendor   # vendor_b on slot b
mount -o ro,noload /dev/disk/by-partlabel/persist /run/persist
packages/armada-ssc/capture.sh <device id> /run/vendor /run/persist /tmp
```

The script skips stray files and the calibration Android learned on that
unit, and prints any non-default factory calibration for review. A value
that also appears in the stock configs (the Portal's gyro bias, for one) is
the same on every unit; anything else belongs to one unit only.

## Adding a board

1. Capture its archive into `data/`.
2. Add an `imu` FastRPC source with a `mount_matrix` to the board's
   InputPlumber device config. Lying flat, the deck-uhid target must read
   gravity on +Z. The matrix depends on the IMU chip, and a board's configs
   can list more than one (`ssccli --sensor accelerometer -v` names the one
   fitted); note the chip beside the matrix. The source name is `fastrpc-adsp`
   on the ADSP boards. The Pocket 5 IMU is an ICM-4x6xx on the SLPI, so its
   source is `fastrpc-sdsp` and the device conf sets
   `ARMADA_SSC_FASTRPC=fastrpc-sdsp`. Its SLPI image is
   `qcom/sm8250/retroidpocket/rp5/slpi.mdt` plus its `slpi.bNN` segments,
   taken from that board's Android modem partition. The shared
   `qcom/sm8250/slpi.mbn` name is a different image and is not in
   linux-firmware. Boot that image before capturing, so `SOURCE` hashes the
   firmware the registry belongs to.
3. Boot and check `journalctl -b -u armada-ssc -u inputplumber`. InputPlumber
   logs `SSC sensors opened` once the SSC is up. `hexagonrpcd` logs
   `Could not open` for each file the ADSP asks for and does not find; every
   such file must be missing from the stock partitions too.
