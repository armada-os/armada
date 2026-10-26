# openabl-updater

Ships OpenABL bootloader images and updates the device's ABL to them at shutdown.

The build downloads the pinned OpenABL release's image for each supported chipset
(SM8250, SM8550, SM8650, SM8750) and checks it against that release's `.sha256`.

| Path | Purpose |
|---|---|
| `/usr/lib/openabl-updater/abl_signed-<SOC>.elf` | OpenABL images |
| `/usr/lib/openabl-updater/manifest` | Packaged version and each image's SHA-256 |
| `/usr/lib/openabl-updater/legacy-releases.tsv` | Known ABL builds, by hash |
| `/usr/libexec/openabl-updater/abl-version` | Identifies an installed or booted ABL |
| `/usr/libexec/openabl-updater/armada-abl-update` | Writes the image to `abl_a` and `abl_b` |
| `/usr/libexec/openabl-updater/armada-abl-finalize` | Runs the updater at shutdown, after `/KERNEL` is synced |

## Update policy

Updates are always on. At shutdown, each ABL copy is checked in this order:

1. **Already the packaged image:** nothing to do.
2. **Listed in `legacy-releases.tsv`:** the hash decides, whatever the firmware
   reports. ROCKNIX and older OpenABL are replaced. A newer release, another
   chipset's image, or the packaged version with different bytes is refused.
3. **Not listed:** the booted OpenABL's reported version decides (ESRT or
   `LoaderInfo`). Older is replaced. The same or newer version is a custom or CI
   build and is left alone. With no report, the copy is refused.

`legacy-releases.tsv` covers ROCKNIX and certain OpenABL releases, which expose no UEFI
variables when booting `/KERNEL`. Later releases report their own version, so
they only need rows if one misreports it.

Reading UEFI variables needs the kernel patch that allows QSEECOM on these
chipsets (from OpenABL's `Linux/`).

## Bumping OpenABL

Set `openabl_version` in `openabl-updater.spec` and add a changelog entry.

`sdcard/` holds the scripts for flashing from Android.
`post_process/finalize-armada-image.sh` copies it to the image's ESP.
