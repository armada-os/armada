# Armada Direct Input

The direct controller mode masks InputPlumber, so games and Steam read the raw
rsinput gamepad node. The kernel driver does the extra buttons itself, so no
userspace process sits between any button and the game.

| Input | Sent by rsinput as |
|---|---|
| Left back paddle (`BTN_Z` on `gpio-keys-paddles`) | `BTN_SOUTH` (A), patch 1312 `forward_paddles` |
| Right back paddle (`BTN_C` on `gpio-keys-paddles`) | `BTN_EAST` (B), patch 1312 `forward_paddles` |
| Bottom right button (`BTN_BACK`) | Guide, then A 80 ms later, patch 1313 `qam_chord` |

SDL maps no gamepad button to `BTN_BACK`, so Steam ignores that button on the
raw node. Guide plus A is Steam's Quick Access Menu chord; the order and the
80 ms steps are the ones InputPlumber's xpad target uses. With Steam Input off,
a game also sees that A press.

This package holds the one service direct mode still needs, the gyro.

## armada-direct-motion

Gyro and accelerometer for the raw gamepad. The IMU sits behind the Snapdragon
Sensor Core, so it reads it through libssc (loaded at runtime, the same calls
as InputPlumber's SSC driver) and writes the samples into the motion sensors
node that rsinput registers when loaded with `motion_sensors=1`
(kernel patch 1308). SDL and Steam pair that node with the gamepad because
both report the same uniq.

`controller-type set direct` writes `/etc/modprobe.d/armada-direct.conf` and
reloads rsinput. It always sets `xbox_face_codes=1` (kernel patch 1311; without
InputPlumber SDL would otherwise swap X and Y) and `forward_paddles=1` (patch
1312; the paddles reach the gamepad inside the kernel) and `qam_chord=1` (patch
1313), with the paddle buttons from
`/etc/armada/direct-paddles.conf`. `controller-type paddles <left> <right>`
sets them by name (a, b, x, y, lb, rb, select, start, guide, l3, r3, up, down,
left, right; default a and b) and reloads rsinput when direct mode is on. The
paddles stay real gamepad buttons, so they work in every game and app, with or
without Steam Input. It adds `motion_sensors=1` on devices
whose profile sets `ARMADA_DIRECT_IMU_MATRIX`. That row-major matrix rotates the sensor axes into SDL's (X right, Y top, Z
toward the player). Run `armada-direct-motion --raw` with the device flat,
upright and on its left edge to measure it for a new board.

An optional per-unit accelerometer correction goes in
`/etc/armada/direct-imu.conf`:

```
ARMADA_DIRECT_ACCEL_OFFSET=-1.430,0.290,0.840
ARMADA_DIRECT_ACCEL_SCALE=1.0152,1.0089,0.9955
```

Both are sensor-axis values from a six-position calibration (each axis up and
down), applied as `(reading - offset) * scale` before the matrix.
