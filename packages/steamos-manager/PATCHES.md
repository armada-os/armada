# Patches

Patches applied on top of BASE.env. Each entry's `source` is an upstream URL pinned
to a commit, or `armada` if it's original; a URL source with no `notes` is verbatim.
`notes` mean the file was modified.

- `patches/0001-Allow-CpuScaling1-to-be-served-by-a-remote-interface.patch`
  source: armada
  notes: `armada-powerd` owns the governor as part of a power profile and `steamos-priv-write` refuses Steam's writes, so remoting it lands Steam's control in our profile model. Needs both halves: a remote only fills a hole where no local implementation exists, and `CpuScaling1` is the one that registers unconditionally.
- `patches/0002-inputplumber-Only-manage-target-devices-when-configu.patch`
  source: armada
  notes: `DeckService` races `armada-controller-type.service` at boot and re-asserts on every composite-device recreation. With no `[inputplumber]` section it forces `[deck-uhid]`, and `is_deck()` wants exactly one target, so our keyboard/mouse extras are dropped with no user involvement. We cannot express our targets in the config either - an unknown `InputPlumberTargetDevice` fails deserialization and drops the whole SoC file.
- `patches/0003-wifi-Always-write-wpa_supplicant-as-the-backend.patch`
  source: armada
  notes: Steam derives the backend it wants from its own `steamos_wifi_force_wpa_supplicant` setting and only skips the write when the current value already matches, so no NetworkManager config can refuse it. With the setting off it writes `iwd` on every launch. Pinning it in the daemon is the only place the request can be declined. `set_wifi_backend` lost its `Connection` argument upstream in `6962ead`, so the patch and its test go through the global connection.
- `patches/0004-session-Track-gamescope-session-plus-steam.service-a.patch`
  source: armada
  notes: Upstream hardcodes `gamescope-session.service` as game mode, which we never run, so the session manager reports Desktop forever. The screen reader setup only exports `ScreenReader0`/`ScreenReader1` on a switch to Game, so Steam's screen reader toggle hit a missing interface and orca never started.
- `patches/0005-power-Add-a-power_supply-battery-charge-limit-method.patch`
  source: armada
  notes: `acpi_sb` only searches the ACPI battery driver's paths, so `qcom_battmgr`'s `charge_control_end_threshold` was never found and `BatteryChargeLimit1` could not register on ARM. Adds `method = "power_supply"`, which searches `/sys/class/power_supply` (symlinked entries) with the same logic. Also writes 100 for Steam's reset (`-1`, sent as 0): an end threshold has no off value, and `qcom_battmgr` clamps 0 to 55.
- `patches/0006-Allow-LowPowerMode1-to-be-served-by-a-remote-interfa.patch`
  source: armada
  notes: Steam's `CSleepController` only offers low-power downloads (screen off, finish the download, then sleep) when `LowPowerMode1` is on the bus. Upstream only registers it with a `tdp_limit.download_mode_limit`, which Qualcomm has no knob for, so `armada-powerd` serves it instead. The local `Fd<'_>` return becomes `OwnedFd` so the relay can pass the remote's handle straight through. It is imported from the `zbus` root, where zbus 6 re-exports it.
