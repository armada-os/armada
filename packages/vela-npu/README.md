# vela-npu

The system part of [Vela](https://github.com/zrprod9-cmyk/vela) (a Decky plugin that swaps a
game's DLSS / FSR 2-3 / XeSS for FSR 4): `fsr4npud` runs the AMD FSR 4 network on the Hexagon NPU
of Snapdragon 8 Gen 2 (SM8550) devices. Vela's Vulkan layer hands each frame to the daemon over
an abstract unix socket and falls back to FSR 4 on the GPU whenever the daemon is missing, busy
or slow.

The build downloads the pinned Vela release image `vela-npu-sysext-<version>.raw` (the same
image Vela's own installer uses), checks it against the SHA-256 in `vela-npu.spec` and takes
the binaries and graphs out of it. Units, udev rule and modules-load file are the ones in `src/`.

| Path | Purpose |
|---|---|
| `/usr/lib64/vela-npu/fsr4npud` | NPU daemon, one instance per graph, `DynamicUser`, group `render` |
| `/usr/lib64/vela-npu/fsr4npu-check` (`/usr/bin/fsr4npu-check`) | Runs a fixed input through a daemon and prints the output hash |
| `/usr/lib64/vela-npu/nf4*.bin` | 7 FSR 4 graphs compiled for HTP v73 (SM8550) |
| `/usr/lib64/vela-npu/cdsprpcd`, `libcdsprpc.so*`, `libcdsp_default_listener.so*` | quic/fastrpc `a56e9d4` (v1.0.8-2), BSD-3-Clause, private copy |
| `/usr/lib64/vela-npu/libQnnHtp.so`, `libQnnHtpV73Stub.so`, `libQnnSystem.so`; `/usr/lib/rfsa/adsp/libQnnHtpV73Skel.so`, `libQairtHtpV73Skel.so`, `libQnnHtpV73.so` | Qualcomm AI Engine Direct SDK runtime 2.47.0.260601 (QNN HTP v73), unmodified, Qualcomm AI Stack License |
| `/usr/lib64/vela-npu/MANIFEST.sha256` | Hashes of the files above |
| `vela-npu@<graph>.service` | One daemon per graph |
| `vela-npu-listener.service` | `cdsprpcd` on `/dev/fastrpc-cdsp-secure` (root, reduced capabilities) |
| `vela-npu-setup.service` | Loads `system_heap`, waits for the cDSP nodes, re-applies the udev rule |
| `70-vela-npu.rules` | `render` group on `/dev/fastrpc-cdsp` and `/dev/dma_heap/system` |

## When it runs

Every unit has `ConditionFirmware=device-tree-compatible(qcom,sm8550)`: on any other chip it is
skipped. **The package contains the Qualcomm AI Engine Direct (QNN) HTP runtime** (6 files, see
the table). The daemons and the listener also need the cDSP shell with its C++ runtime
(`fastrpc_shell_unsigned_3`, `libc++.so.1`, `libc++abi.so.1`), which this package does not ship:
Vela's installer copies them from the device's own `dsp` partition into a system extension
(`armada-vela-npu-qnn`); until then the units are skipped by
`ConditionPathExists=/usr/lib/rfsa/adsp/fastrpc_shell_unsigned_3`.

Library search paths: `fsr4npud` and `libcdsp_default_listener` look only in `/usr/lib64/vela-npu`;
the Qualcomm host libraries carry `$ORIGIN` (the same directory). No setuid file, all root:root.

## Updating

Set `vela_npu_version` and `vela_npu_sha256` in `vela-npu.spec` and add a changelog entry.
Package versions follow Vela's NPU part (12 = Vela 0.8.16).

## Turning it off

`sudo systemctl mask vela-npu-listener.service 'vela-npu@nf4_exact.service'` (and the other six
instances), or remove the `armada-vela-npu-qnn` extension (the cDSP shell); Vela then runs FSR 4
on the GPU.

## Check

```bash
for s in nf4_exact nf4_k1h nf4_k1h_360 nf4_k1h_450 nf4up_k1h nf4up_k1h_360 nf4up_k1h_450; do
    fsr4npu-check --name "fsr4npud_${s}" --runs 20
done
```

Each prints `RESULT OK` and the same output hash in every run.
