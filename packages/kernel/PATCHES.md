# Patches

Patches applied on top of BASE.env. Each entry's `source` is a URL pinned to a
commit, or `armada` for original work; a URL source with no `notes` is verbatim.
`notes` explain modifications or important differences from linked upstream work.
A patch entry's `upstream` is `local` for an Armada-authored change, `unknown` when
no equivalent submission was found, or a permanent URL to the upstream submission.

- `patches/0002-qcom-dispcc-sm8550-Fix-disp_cc_mdss_mdp_clk_src.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0002-qcom-dispcc-sm8550-Fix-disp_cc_mdss_mdp_clk_src.patch
  upstream: unknown
- `patches/0004-drm-msm-a6xx-Enable-IFPC-on-Adreno-740.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0004-drm-msm-a6xx-Enable-IFPC-on-Adreno-740.patch
  upstream: unknown
- `patches/0010-msm-resource-cleanup.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/packages/linux/patches/7.0/0010-msm-resource-cleanup.patch
  upstream: unknown
  notes: Armada initialises cstate before the num_mixers reset it adds; the ROCKNIX version writes through an uninitialised pointer.
- `patches/0048-drm-msm-dsi-reparent-byte-pixel-src-to-xo-on-disable.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0048-drm-msm-dsi-reparent-byte-pixel-src-to-xo-on-disable.patch
  upstream: unknown
- `patches/0048a-drm-msm-dsi-round-byte-clock-rate-after-reparenting-to-PLL.patch`
  source: https://git.kernel.org/torvalds/c/2028280686f4fa78e2f1f6dede4b6c1fd782b9e3
  upstream: https://lore.kernel.org/r/20260903-fix-eliza-dsi-v1-1-3474a6c9f2e0@oss.qualcomm.com
  notes: Context of the struct msm_dsi_host hunk refreshed to apply after `0048`.
- `patches/0049-drm-msm-dpu-panel-opt-in-8bpc-dither.patch`
  source: armada
  upstream: local
  notes: Armada wrote this patch; it has not been submitted upstream.
- `patches/0066-drm-msm-dpu-enable-inline-rotation.patch`
  source: https://github.com/ROCKNIX/distribution/blob/60bb58c1db053255b700f3953b72d619ec5aa85d/projects/ROCKNIX/devices/SM8550/patches/linux/0066-drm-msm-dpu-enable-sm8550-inline-rotation.patch
  upstream: unknown
  notes: Armada merged the ROCKNIX SM8550, SM8650 and SM8750 patches into one for the combined kernel, with one shared feature mask and rotation config.
- `patches/0067-drm-msm-dpu-enable-qseed-detail-enhancer.patch`
  source: https://github.com/ROCKNIX/distribution/blob/60bb58c1db053255b700f3953b72d619ec5aa85d/projects/ROCKNIX/devices/SM8550/patches/linux/0067-drm-msm-dpu-enable-qseed-detail-enhancer.patch
  upstream: unknown
- `patches/0068-drm-msm-dpu-lutdma-dspp-igc-gamut.patch`
  source: armada
  upstream: local
- `patches/0069-dt-bindings-display-msm-dpu-lutdma-reg.patch`
  source: armada
  upstream: local
- `patches/0070-arm64-dts-qcom-dpu-lutdma-reg.patch`
  source: armada
  upstream: local
- `patches/0016-rp5-smooth-brightness-adjustment.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/0016-rp5-smooth-brightness-adjustment.patch
  upstream: unknown
  notes: Armada limited the ROCKNIX brightness change to SM8250 panels. A [related upstream proposal](https://lore.kernel.org/r/20260706180753.408753-1-kavansmith82@gmail.com) uses a different implementation.
- `patches/0028-drm-panel-Add-panel-driver-for-Chipone-ICNA35XX-base.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0028-drm-panel-Add-panel-driver-for-Chipone-ICNA35XX-base.patch
  upstream: https://lore.kernel.org/r/20260607-icna35xx-v4-2-64de514add34@gmail.com
  notes: The carried implementation differs from the linked upstream submission and is ported to Linux 7.2's managed DRM panel allocator.
- `patches/0051-gpu-panel-add-Pocket-ACE-panel-driver.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0051-gpu-panel-add-Pocket-ACE-panel-driver.patch
  upstream: unknown
  notes: Ported to Linux 7.2's managed DRM panel allocator.
- `patches/0052-gpu-panel-add-Pocket-DMG-panel-driver.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0052-gpu-panel-add-Pocket-DMG-panel-driver.patch
  upstream: unknown
  notes: Ported to Linux 7.2's managed DRM panel allocator.
- `patches/0053-gpu-panel-st7703-add-Pocket-DS-lower-panel.patch`
  source: https://github.com/ROCKNIX/distribution/blob/7651a1b97d762d2c7dc335fa82a7a254c3a12927/projects/ROCKNIX/devices/SM8550/patches/linux/0053-gpu-panel-st7703-add-Pocket-DS-lower-panel.patch
  upstream: https://lore.kernel.org/r/20260723-b4-st7703-pocketds-lower-v1-2-e3db246589f4@gmail.com
- `patches/0055_Synaptics-TD4328-LCD-panel.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0055_Synaptics-TD4328-LCD-panel.patch
  upstream: https://lore.kernel.org/r/20240424-ayn-odin2-initial-v1-4-e0aa05c991fd@gmail.com
  notes: The carried implementation predates the linked upstream submission and is ported to Linux 7.2's managed DRM panel allocator.
- `patches/0056_Xm-Plus-XM91080G-panel.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0056_Xm-Plus-XM91080G-panel.patch
  upstream: unknown
  notes: Ported to Linux 7.2's managed DRM panel allocator.
- `patches/0057_DDIC-CH13726A-panel.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0057_DDIC-CH13726A-panel.patch
  upstream: unknown
  notes: Retains additional compatibles and the 120 ms sleep-out delay, using Linux 7.2's managed DRM panel allocator.
- `patches/0059-drm-panel-add-brightness-levels-helper.patch`
  source: armada
  upstream: not submitted
- `patches/0060-drm-panel-icna35xx-luminance-linear-backlight-scale.patch`
  source: armada
  upstream: not submitted
- `patches/0060a-drm-panel-icna35xx-add-mangmi-pocket-max.patch`
  source: https://github.com/ROCKNIX/distribution/blob/807c74fc46c124891d8aa9b57a68533d38e9a6b2/projects/ROCKNIX/devices/SM8250/patches/linux/0057_Chipone-ICNA35XX-panel.patch
  upstream: unknown
  notes: Ports the Pocket Max init sequence, four vendor modes and per-panel shutdown delays onto Armada's Linux 7.2 managed-panel driver while retaining Armada's luminance-linear backlight scale.
- `patches/0106-drm-panel-il97680a-luminance-linear-backlight-scale.patch`
  source: armada
  upstream: not submitted
- `patches/0062-gpu-drm-panel-add-wt0630-panel.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0062-gpu-drm-panel-add-wt0630-panel.patch
  upstream: https://lore.kernel.org/r/20260625-topic-sm8650-ayaneo-pocket-s2-r63419-v8-2-8570e692143e@linaro.org
  notes: Ported to Linux 7.2's managed DRM panel allocator.
- `patches/0063-gpu-drm-panel-add-wt0600-1k-panel.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0063-gpu-drm-panel-add-wt0600-1k-panel.patch
  notes: Standalone single-DSI driver for the 1080x1920 60Hz WT0600 panel (Pocket S 1K) from ROCKNIX PR #3007.
- `patches/0104-drm-panel-Add-Retroid-Pocket-6-panel.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0104-drm-panel-Add-Retroid-Pocket-6-panel.patch
  upstream: unknown
  notes: Ported to Linux 7.2's managed DRM panel allocator.
- `patches/0105-drm-panel-Add-Retroid-Pocket-Nova-panel.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0105-drm-panel-Add-Retroid-Pocket-Nova-panel.patch
  upstream: unknown
  notes: Ported to Linux 7.2's managed DRM panel allocator.
- `patches/0104a-drm-panel-visionox-vtdr6130-add-sm8250.patch`
  source: https://github.com/armada-os/armada/issues/327
  upstream: unknown
  notes: Adds support for Visionox VTDR6130 panel revisions found in the Retroid Pocket Flip 2, derived from the affected device's live Android device tree. Reuses the Pocket 6 initialization sequence and DSC configuration with the Flip 2 regulator supplies.
- `patches/0064_Mangmi-Air-Y-Pro-panel.patch`
  source: https://github.com/ROCKNIX/distribution/blob/807c74fc46c124891d8aa9b57a68533d38e9a6b2/projects/ROCKNIX/devices/SM8250/patches/linux/0064_Mangmi-Air-Y-Pro-panel.patch
  upstream: unknown
- `patches/0058_AYN-Odin2-Mini--backlight.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0058_AYN-Odin2-Mini--backlight.patch
  upstream: unknown
  notes: Armada refreshed only the Makefile context for Linux 7.1's backlight object list; driver behavior is unchanged.
- `patches/0060-backlight-Add-SY7758-LED-driver.patch`
  source: https://patchwork.kernel.org/project/dri-devel/patch/20260529-topic-sm8650-ayaneo-pocket-s2-sy7758-v5-2-03aacd49747c@linaro.org/
  upstream: https://lore.kernel.org/r/178300990349.2239788.13080024963462152507.b4-ty@b4
  notes: Armada made the enable GPIO optional (`devm_gpiod_get_optional`). The AYANEO Pocket DS wires no discrete enable line to its SY7758, and requiring one left the whole lower DSI chain deferred; boards that do have one are unaffected. The binding patch carries the matching change.
- `patches/0060-dt-bindings-silergy-sy7758.patch`
  source: https://patchwork.kernel.org/project/dri-devel/patch/20260529-topic-sm8650-ayaneo-pocket-s2-sy7758-v5-1-03aacd49747c@linaro.org/
  upstream: https://lore.kernel.org/r/178300990349.2239788.13080024963462152507.b4-ty@b4
  notes: Armada dropped `enable-gpios` from the required list to match the driver change above; the AYANEO Pocket DS reaches its SY7758 without a separately described enable pin.
- `patches/0054-regulator-add-sgm3804-i2c-regulator-for-panel-power-.patch`
  source: armada
  upstream: local
  notes: Armada adds compatibility for existing flat fixed-5-V nodes; child-regulator nodes use the Linux 7.2 upstream behavior unchanged.
- `patches/0056-backlight-aw99706-enable-hwen-before-chip-id-read.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0056-backlight-aw99706-enable-hwen-before-chip-id-read.patch
  upstream: unknown
- `patches/0057-backlight-aw99706-konkr-cfg7.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0057-backlight-aw99706-konkr-cfg7.patch
  upstream: unknown
- `patches/0066-regulator-add-qcom-pm8150l-lcdb.patch`
  source: https://github.com/ROCKNIX/distribution/blob/807c74fc46c124891d8aa9b57a68533d38e9a6b2/projects/ROCKNIX/devices/SM8250/patches/linux/0066-regulator-add-qcom-pm8150l-lcdb.patch
  upstream: unknown
- `patches/0015-touchscreen-edt-ft5x06-allow-to-override-input-name.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/0015-touchscreen-edt-ft5x06-allow-to-override-input-name.patch
  upstream: https://lore.kernel.org/r/20260409-ft5x06-label-v1-1-21e8a9ae9a60@gmail.com
- `patches/0030-input-rmi4-add-reset-gpio.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0030-input-rmi4-add-reset-gpio.patch
  upstream: https://lore.kernel.org/r/20250210050220.634497-2-felix@kaechele.ca
- `patches/0032-rmi4-silence-spam-irq-errors.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0032-rmi4-silence-spam-irq-errors.patch
  upstream: unknown
- `patches/0053-add-hynitron-touchscreen.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0053-add-hynitron-touchscreen.patch.disabled
  upstream: unknown
  notes: Armada retains this disabled ROCKNIX driver for the Pocket DMG and refreshed only its Makefile context for Linux 7.1's Himax entry; driver behavior is unchanged.
- `patches/0053a-input-hynitron-port-to-gpiod.patch`
  source: armada
  upstream: local
  notes: Armada added this follow-up because Linux 7.1 removed the legacy OF GPIO-number API; it ports the retained Hynitron driver to GPIO descriptors.
- `patches/0053b-input-hynitron-restore-gpio-init-order.patch`
  source: armada
  upstream: local
  notes: Armada added this follow-up to preserve the vendor driver's pinctrl, GPIO-direction, power, and reset ordering after the GPIO-descriptor port.
- `patches/0065-input-touchscreen-add-hynitron-cst66xx.patch`
  source: https://github.com/ROCKNIX/distribution/blob/807c74fc46c124891d8aa9b57a68533d38e9a6b2/projects/ROCKNIX/devices/SM8250/patches/linux/0065-input-touchscreen-add-hynitron-cst66xx.patch
  upstream: unknown
- `patches/0054-input-goodix-override-resolution-from-dt.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0054-input-goodix-override-resolution-from-dt.patch
  upstream: unknown
  notes: Armada replaced ROCKNIX's automatic resolution-mismatch heuristic and hardcoded fallback with explicit `goodix,native-size-x` and `goodix,native-size-y` properties. Scaling is dormant unless a device opts in with both native and standard touchscreen dimensions.
- `patches/0054a-dt-bindings-input-goodix-document-input-device-label.patch`
  source: armada
  upstream: local
  notes: Documents the optional Goodix `label` property used to name the input device.
- `patches/0054b-input-goodix-allow-overriding-input-device-name.patch`
  source: armada
  upstream: local
  notes: Allows the Pocket DS lower GT911 to expose its `bottom_touchscreen` label as the input device name.
- `patches/0029-Input-edt-ft5x06-add-no_regmap_bulk_read-option.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0029-Input-edt-ft5x06-add-no_regmap_bulk_read-option.patch
  upstream: https://lore.kernel.org/r/20260723-b4-ft5426-v1-3-d4b4e32be042@gmail.com
- `patches/0059_AYN-Odin2-Mini--hynitron--cstxxx.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0059_AYN-Odin2-Mini--hynitron--cstxxx.patch
  upstream: unknown
- `patches/0060-input-touchscreen-add-synaptics-dsx-kconfig.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0060-input-touchscreen-add-synaptics-dsx-kconfig.patch
  upstream: unknown
- `patches/0060-input-touchscreen-add-synaptics-dsx-driver.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0060-input-touchscreen-add-synaptics-dsx-driver.patch
  upstream: unknown
- `patches/0058-input-joystick-add-ayaneo-mcu-joystick.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0058-input-joystick-add-ayaneo-mcu-joystick.patch
  upstream: unknown
- `patches/0069-input-misc-add-konkr-sysbtn-MCU-system-buttons.patch`
  source: https://github.com/ROCKNIX/distribution/blob/024028b4f3fdd139ae1e575efb25914b8f76595d/projects/ROCKNIX/devices/SM8750/patches/linux/0069-input-misc-add-konkr-sysbtn-MCU-system-buttons.patch
  upstream: unknown
  notes: Updated to ROCKNIX #3089, which adds the MCU-rendered stick lighting effects (sysfs "effect": static/breath/rainbow) and fixes the PM notifier to replay the active lighting mode after resume instead of only the last static colour.
- `patches/0060_Mangmi-Pocket-Max-SPI-joypad.patch`
  source: https://github.com/ROCKNIX/distribution/blob/807c74fc46c124891d8aa9b57a68533d38e9a6b2/projects/ROCKNIX/devices/SM8250/patches/linux/0060_Mangmi-Pocket-Max-SPI-joypad.patch
  upstream: unknown
- `patches/0031_input--Add-driver-for-RSInput-Gamepad.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0031_input--Add-driver-for-RSInput-Gamepad.patch
  upstream: unknown
- `patches/0508-input-rsinput-add-pm-resume-to-reinit-mcu-after-suspend.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0508-input-rsinput-add-pm-resume-to-reinit-mcu-after-suspend.patch
  upstream: unknown
- `patches/0515-input-rsinput-reassemble-uart-frames-instead-of-dropping-them.patch`
  source: armada
  upstream: not submitted
  notes: serdev delivers arbitrary byte batches and the old parser dropped any batch that was not exactly one frame, visible as resume-correlated checksum mismatches on the rsinput gamepad devices.
- `patches/0504-Enable-64-bit-processes-to-use-compat-input-syscalls.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/0504-Enable-64-bit-processes-to-use-compat-input-syscalls.patch
  upstream: unknown
  notes: Armada rebased the unchanged compat-input prctl behavior onto Linux 7.1's current task-structure, UAPI, and prctl switch layout.
- `patches/0506-usbcore-add-interrupt-interval-override.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0506-usbcore-add-interrupt-interval-override.patch
  upstream: unknown
- `patches/0071-HACK-fix-usb-boot-hang.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0071-HACK-fix-usb-boot-hang.patch
  upstream: unknown
  notes: ROCKNIX carries this workaround in its SM8550 and SM8650 kernels. Armada preserves the normal xHCI readiness handshake on every other SoC.
- `patches/1000-input-misc-qcom-hv-haptics-sm8750.patch`
  source: https://github.com/ROCKNIX/distribution/blob/47e077d0bbc714abb05afea6b68144b6f28ee19a/projects/ROCKNIX/devices/SM8750/patches/linux/1000-input-misc-qcom-hv-haptics-sm8750.patch
  upstream: unknown
- `patches/1001-input-qcom-haptics-update-assign-str.patch`
  source: armada
  upstream: local
  notes: Armada updates the vendored driver for Linux 7.1's one-argument `__assign_str()` API.
- `patches/1001-haptics-driver-support-periodic-sine-and-fixes.patch`
  source: https://github.com/ROCKNIX/distribution/blob/47e077d0bbc714abb05afea6b68144b6f28ee19a/projects/ROCKNIX/devices/SM8750/patches/linux/1001-haptics-driver-support-periodic-sine-and-fixes.patch
  upstream: unknown
- `patches/1002-input-rsinput-sm8750-ff.patch`
  source: https://github.com/ROCKNIX/distribution/blob/47e077d0bbc714abb05afea6b68144b6f28ee19a/projects/ROCKNIX/devices/SM8750/patches/linux/1002-input-rsinput-sm8750-ff.patch
  upstream: unknown
  notes: Armada rebased ROCKNIX's force-feedback bridge because its final hunk is malformed and it targets a different RSInput revision. ROCKNIX enables rumble for every RSInput device; Armada gates it with a DT property set only by the supported SM8550 and SM8750 trees that also instantiate the Qualcomm haptics device. The SM8550 common tree intentionally covers both AYN and Retroid products.
- `patches/1003-input-haptics-fix-rumble-bridge-atomic-sleep.patch`
  source: armada
  upstream: local
  notes: The imported bridge called the haptics driver's sleeping upload, playback, and erase callbacks under spin_lock_irq, which emitted "BUG: scheduling while atomic" on every rumble stop and intermittently hard-locked the Odin 3 (reproduced on hardware). The bridge now serializes with a mutex and is process-context only, RSInput defers its atomic playback callback to a work item, and the haptics suspend path cancels the pending stop and set-gain workers so they cannot fire into resume. ROCKNIX carries the identical bug as of 2026-08-04; worth upstreaming once soak-tested.
- `patches/1004-input-haptics-stop-zero-amplitude-immediately.patch`
  source: armada
  upstream: local
  notes: The imported periodic-sine compatibility patch changed zero-amplitude updates to gain 1, then stopped the motor five seconds later. The configured brake pattern made that stop a distinct delayed tap. Zero-amplitude updates now erase immediately, a following playback request cannot restart stale motor state when no effect is loaded, and in-place gain updates balance their transient runtime-PM reference.
- `patches/1005-input-rsinput-quiesce-the-mcu-across-system-sleep.patch`
  source: https://github.com/shuuri-labs/pocknix-os/blob/d2544c1481b55e9dec18ff74a8751d4a67b351f8/kernel/sm8550/patches/20-sm8550/1004-input-rsinput-suspend-resume-gamepad-mcu.patch
  upstream: local
  notes: Carries only the suspend-side MCU quiesce from the source patch; the source's resume and pm_ops additions are omitted because this tree already has both and rsinput_init_commands() performs the full power-on itself.
- `patches/1006-tty-serial-qcom-geni-mask-non-console-irq-on-suspend.patch`
  source: https://github.com/thorch-os/thorch/blob/2614a262d7de3f31bd47a0c92981461146663847/packages/linux-thorch/patches/0010-tty-serial-qcom-geni-mask-non-console-irq-on-suspend.patch
  upstream: unknown
- `patches/1300-input-rsinput-axis-deadzone.patch`
  source: armada
  upstream: local
  notes: Armada replaced ROCKNIX's global experimental Odin 3 range and deadzone defaults with a per-device `axis-deadzone` property. The Odin 3 DTS supplies its range and deadzone explicitly.
- `patches/0059-ASoC-aw88395-lib-skip-monitor-sections-in-V1-ACF-parse.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0059-ASoC-aw88395-lib-skip-monitor-sections-in-V1-ACF-parse.patch
  upstream: unknown
- `patches/0063-ASoC-wcd939x-route-usbss-on-integrated-jack-insert.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0063-ASoC-wcd939x-route-usbss-on-integrated-jack-insert.patch
  upstream: unknown
- `patches/0064-ASoC-wcd-mbhc-clear-stale-jack-report-on-mechanical-removal.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0064-ASoC-wcd-mbhc-clear-stale-jack-report-on-mechanical-removal.patch
  upstream: unknown
- `patches/0036_ASoC--qcom--sc8280xp-Add-support-for-Primary-I2S.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0036_ASoC--qcom--sc8280xp-Add-support-for-Primary-I2S.patch
  upstream: https://lore.kernel.org/r/20251008-topic-sm8x50-next-hdk-i2s-v2-3-6b7d38d4ad5e@linaro.org
- `patches/0032-ASoC-codecs-aw88166-AYN-Products-Specific-modificati.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0032-ASoC-codecs-aw88166-AYN-Products-Specific-modificati.patch
  upstream: unknown
- `patches/0030-leds-Add-driver-for-HEROIC-HTR3212.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0030-leds-Add-driver-for-HEROIC-HTR3212.patch
  upstream: unknown
- `patches/0061_leds-aw200xx-vdd-supply.patch`
  source: https://github.com/ROCKNIX/distribution/blob/807c74fc46c124891d8aa9b57a68533d38e9a6b2/projects/ROCKNIX/devices/SM8250/patches/linux/0061_leds-aw200xx-vdd-supply.patch
  upstream: unknown
- `patches/0054_sn3112-pwm-driver.patch`
  source: https://github.com/ROCKNIX/distribution/blob/4609c5017f350e6e2307ec909e328454d5bec062/projects/ROCKNIX/devices/SM8550/patches/linux/0054_sn3112-pwm-driver.patch
  upstream: https://lore.kernel.org/r/20240424-ayn-odin2-initial-v1-2-e0aa05c991fd@gmail.com
  notes: Includes ROCKNIX #3110's fix for the arm64 probe crash: set_bit()/clear_bit() on a cast uint8_t[3] alignment-faults under LSE atomics, replaced with plain bitwise ops under priv->lock. The matching Odin 2 DTS change re-enables the sn3112 nodes that were disabled to dodge the crash.
- `patches/20260424_neil_armstrong_arm64_dts_qcom_sm8_456_50_add_missing_cx_power_domain_to_gcc.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/20260424_neil_armstrong_arm64_dts_qcom_sm8_456_50_add_missing_cx_power_domain_to_gcc.patch
  upstream: https://lore.kernel.org/r/20260615-topic-sm8x50-tie-gcc-to-cx-v2-0-6b5752dd4747@linaro.org
- `patches/v9_20260729_qualcomm_crypto_qce_runtime_pm_interconnect.patch`
  source: https://lore.kernel.org/r/20260729110455.641256-1-kuldeep.singh@oss.qualcomm.com
  upstream: https://lore.kernel.org/r/20260729110455.641256-1-kuldeep.singh@oss.qualcomm.com
  notes: Refreshed only its include context for Linux 7.2; runtime-PM and interconnect behavior is unchanged.
- `patches/0504-mailbox-qcom-ipcc-mask-summary-irq-for-suspend-to-ram.patch`
  source: https://github.com/ROCKNIX/distribution/commit/f955f5b6137554253e4d52bbe72f9b4936fb253d
  upstream: not submitted
  notes: Reworked from ROCKNIX's blanket IRQF_NO_SUSPEND removal: the summary
  irq is masked (unlazy) only for suspend-to-RAM on the SM8550/SM8750
  compatibles, so suspend-to-idle keeps the doorbell live and charging can
  start while asleep.
- `patches/0505-msm_gem-lock-before-put_iova_spaces.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/0505-msm_gem-lock-before-put_iova_spaces.patch
  upstream: unknown
- `patches/0204-thermal-qcom-tsens-mask-lower-threshold-irqs-across-suspend.patch`
  source: armada
  upstream: local
  notes: Lower threshold crossings during the suspend transition cannot be serviced while thermal zones are quiesced, so the level IRQ storms and aborts suspend; masking LOWER across the transition removes the cause and keeps upper/critical wake armed.
- `patches/0510-soc-qcom-ice-unwind-clocks-on-resume-failure.patch`
  source: armada
  upstream: local
- `patches/0511-scsi-ufs-qcom-reenable-irq-on-host-reset-failure.patch`
  source: armada
  upstream: local
- `patches/0512-PCI-qcom-skip-L23-ready-poll-on-SM8550.patch`
  source: armada
  upstream: local
- `patches/0513-PCI-qcom-honour-an-opp-suspend-opp-as-the-non-s2ram-memory-floor.patch`
  source: armada
  upstream: not submitted
  notes: On OPP-scaling platforms the OPP carries the only PCIe memory-path votes, so dropping it to NULL on non-S2RAM suspend leaves the RPMh sleep set with no DDR/LLCC contract and the AOP never resumes. Deliberately does not populate `pcie->icc_mem` on OPP platforms: `qcom_pcie_icc_opp_update()` prefers an `icc_mem` handle over the OPP branch, so providing one silently disables the post-link-training OPP update and pins the OPP at the probe-time maximum.
- `patches/0514-PCI-qcom-honor-iommu-map-cell-count.patch`
  source: https://lkml.iu.edu/2609.0/16096.html
  upstream: https://lore.kernel.org/r/20260907143349.317495-1-mani@kernel.org
- `patches/0514a-of-property-honor-iommu-cells-in-iommu-map-devlinks.patch`
  source: armada
  upstream: local
- `patches/0001-pcie-update-sm8550-dtsi.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0001-pcie-update-sm8550-dtsi.patch
  upstream: https://lore.kernel.org/r/20260611-wake-v2-33-2744251b1181@oss.qualcomm.com
- `patches/0520-arm64-dts-qcom-sm8550-add-a-pcie-suspend-opp.patch`
  source: armada
  upstream: not submitted
  notes: Companion DT for 0513. `opp-hz` is synthetic and `opp-level` is omitted so the OPP can never be selected for a trained link by either match in `qcom_pcie_icc_opp_update()`. pcie1 is disabled in the SM8550 board DTS files that use this table and gets no suspend OPP.
- `patches/0120-20250728_konradybcio_gpu_cc_power_requirements_reality_check.patch`
  source: https://github.com/ROCKNIX/distribution/blob/ef264a238d5e2ba960145e3fda663dc27de49a80/projects/ROCKNIX/devices/SM8550/patches/linux/0120-20250728_konradybcio_gpu_cc_power_requirements_reality_check.patch
  upstream: https://lore.kernel.org/r/20250728-topic-gpucc_power_plumbing-v1-22-09c2480fe3e6@oss.qualcomm.com
- `patches/0121-pmdomain-qcom-rpmhpd-presync-floor-gmu-rails.patch`
  source: https://github.com/ROCKNIX/distribution/blob/ef264a238d5e2ba960145e3fda663dc27de49a80/projects/ROCKNIX/devices/SM8550/patches/linux/0121-pmdomain-qcom-rpmhpd-presync-floor-gmu-rails.patch
  source: https://github.com/ROCKNIX/distribution/blob/ef264a238d5e2ba960145e3fda663dc27de49a80/projects/ROCKNIX/devices/SM8750/patches/linux/0052-pmdomain-qcom-rpmhpd-presync-floor-gmu-rails.patch
  upstream: unknown
  notes: Armada applies the presync_floor and skip_retention_level flags via private descriptors (gfx_gmu for SM8550+SM8750, gmxc_sm8750) so GMU rail pre-sync behavior cannot change on other SoCs; ROCKNIX instead flags the shared gfx/gmxc structs, which would leak onto every SoC sharing them in a combined kernel. SM8250 and SM8650 have no Linux-side voter on these rails (their gpucc/gmu nodes reference only gpucc GDSCs), so the flags would be inert there today; revisit the scoping if the upstream gpucc power plumbing series lands and adds voters on more SoCs.
- `patches/0122-interconnect__qcom__sm8550__Enable_QoS_configuration.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0122-interconnect__qcom__sm8550__Enable_QoS_configuration.patch
  upstream: unknown
- `patches/0200-ASoC-wcd938x-add-DMIC-DAPM-inputs.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0200-ASoC-wcd938x-add-DMIC-DAPM-inputs.patch
  upstream: unknown
- `patches/1020-wifi-ath12k-send-the-computed-scan-priority-to-the-f.patch`
  source: https://github.com/ROCKNIX/distribution/blob/10b09e8df73b2b07ff04a243ded7425e41cd67fa/projects/ROCKNIX/devices/SM8550/patches/linux/1020-wifi-ath12k-send-the-computed-scan-priority-to-the-f.patch
  upstream: unknown
- `patches/0500-ROCKNIX-set-boot-fanspeed.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0500-ROCKNIX-set-boot-fanspeed.patch
  upstream: unknown
- `patches/0501-ROCKNIX-fix-wifi-and-bt-mac.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0501-ROCKNIX-fix-wifi-and-bt-mac.patch
  upstream: unknown
  notes: Armada refreshed only the ath12k insertion context for Linux 7.1's rate-table macros; MAC derivation behavior is unchanged.
- `patches/0503-ROCKNIX-battery-name.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0503-ROCKNIX-battery-name.patch
  upstream: unknown
- `patches/0901-power-supply-qcom-battmgr-fix-charge-unit.patch`
  source: https://lkml.iu.edu/2608.3/10893.html
  upstream: https://lkml.iu.edu/2608.3/10893.html
  notes: Carries the upstream SM8350-class fix that initializes the charge unit to mAh so CHARGE_FULL* is available to userspace.
- `patches/0902-power-supply-qcom-battmgr-expose-charge-now.patch`
  source: https://lkml.iu.edu/2608.3/10890.html
  upstream: https://lkml.iu.edu/2608.3/10890.html
  notes: Carries the upstream SM8350/SM8550 mapping of the firmware remaining-charge counter to CHARGE_NOW.
- `patches/0900-power-supply-qcom-battmgr-log-usb-adapter-type.patch`
  source: armada
  upstream: local
  notes: Armada wrote this diagnostic patch to log the USB type and Qualcomm firmware's adapter type when either value changes.
- `patches/0001-pcie-update-sm8650-dtsi.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8650/patches/linux/0001-pcie-update-sm8650-dtsi.patch
  upstream: https://lore.kernel.org/r/20260611-wake-v2-35-2744251b1181@oss.qualcomm.com
- `patches/0006-add-hw_params-callback-function-to-drm_connector_hdmi_audio_ops.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0006-add-hw_params-callback-function-to-drm_connector_hdmi_audio_ops.patch
  upstream: https://lore.kernel.org/r/20250925040530.20731-1-liujianfeng1994@gmail.com
- `patches/0007-ASoC-qcom-audioreach-compute-active-channel-maps.patch`
  source: https://lore.kernel.org/r/20260728-topic-sm8650-ayaneo-pocket-s2-wsa2-fix-v3-1-b29f44720178@linaro.org
  upstream: https://lore.kernel.org/r/178550094533.136247.8108653420741029312.b4-ty@b4
- `patches/0008-ASoC-dt-bindings-qcom-sm8250-Add-Ayaneo-Pocket-S2.patch`
  source: https://lore.kernel.org/r/20260728-topic-sm8650-ayaneo-pocket-s2-wsa2-fix-v3-2-b29f44720178@linaro.org
  upstream: https://lore.kernel.org/r/178550094533.136247.8108653420741029312.b4-ty@b4
- `patches/0009-ASoC-qcom-sc8280xp-add-Ayaneo-Pocket-S2-card.patch`
  source: https://lore.kernel.org/r/20260728-topic-sm8650-ayaneo-pocket-s2-wsa2-fix-v3-3-b29f44720178@linaro.org
  upstream: https://lore.kernel.org/r/178550094533.136247.8108653420741029312.b4-ty@b4
  notes: Backported to Armada's Linux 7.2 machine-driver layout; the accepted WSA2 channel map and constraints are unchanged.
- `patches/0010-ASoC-qcom-add-KONKR-Pocket-FIT-WSA2-card.patch`
  source: armada
  upstream: local
  notes: Pocket FIT uses the same WSA2-only speaker wiring as Pocket S2. Armada adds a board-specific compatible backed by the accepted Pocket S2 channel mapping.
- `patches/0011-ASoC-qcom-audioreach-use-wsa-interface-for-sm8650-wsa2.patch`
  source: armada
  upstream: local
  notes: Restores the WSA2-to-WSA interface rewrite that ROCKNIX bundled inside its replaced channel-map workaround; the SM8650 topology declares the speaker backend as WSA2, which the shipped ADSP firmware rejects. Gated to `qcom,sm8650`; remove once a corrected topology stops declaring WSA2.
- `patches/v2_20260420_neil_armstrong_arm64_qcom_sm8650_misc_enhancements.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8650/patches/linux/v2_20260420_neil_armstrong_arm64_qcom_sm8650_misc_enhancements.patch
  upstream: https://lore.kernel.org/r/20260615-topic-sm8650-upstream-cpu-props-v3-0-eeb6e9fa7581@linaro.org
- `patches/0063-gpu-drm-panel-add-pocket-fit-panel.patch`
  source: https://github.com/ROCKNIX/distribution/blob/5cff2f7918ca6bd56d8a884f0837309529a058bc/projects/ROCKNIX/devices/SM8750/patches/linux/0055-gpu-drm-panel-add-pocket-fit-panel.patch
  upstream: unknown
  notes: Uses the four-mode SM8750 variant and Linux 7.2's managed DRM panel allocator.
- `patches/0064-input-touchscreen-add-rocknix-chipone-tddi.patch`
  source: https://github.com/ROCKNIX/chipone_tddi/commit/af27029fa2b27c4a77d16809298ed5d03c9da5a6
  upstream: unknown
  notes: ROCKNIX ships this full driver as an out-of-tree module for the SM8650 KONKR Pocket FIT. Armada converts the pinned fork to an in-tree patch; its C and header files are unchanged, while Kconfig and Kbuild are adapted for the combined kernel. The fork includes ROCKNIX's Linux 7.1 GPIO compatibility update.
- `patches/0014-sm8250-ath11k-fix-wifi-mac.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/0014-fix-wifi-and-bt-mac.patch
  upstream: unknown
  notes: Armada carries only the ath11k portion of the shared ROCKNIX patch; the Bluetooth and SoC-serial changes are supplied by `0501-ROCKNIX-fix-wifi-and-bt-mac.patch`.
- `patches/0067-arm64-dts-qcom-pm8150l-add-lcdb-node.patch`
  source: https://github.com/ROCKNIX/distribution/blob/063e530e58d380aa17a7c608f0853898cc3911a5/projects/ROCKNIX/devices/SM8250/patches/linux/0067-arm64-dts-qcom-pm8150l-add-lcdb-node.patch
  upstream: unknown
- `patches/0004-pm8150b.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/0004-pm8150b.patch
  upstream: unknown
- `patches/0009-qcom-spmi-haptics.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/0009-qcom-spmi-haptics.patch
  upstream: unknown
  notes: Armada refreshed only the Kconfig insertion context so the SM8250 haptics driver follows Linux 7.1's high-voltage haptics entry; driver behavior is unchanged.
- `patches/0008-retroid-gamepad.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/0008-retroid-gamepad.patch
  upstream: unknown
- `patches/0013-add-force-feedback.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/0013-add-force-feedback.patch
  upstream: unknown
- `patches/0063_Mangmi-Pocket-Max-HL7139-charge-pump.patch`
  source: https://github.com/ROCKNIX/distribution/blob/807c74fc46c124891d8aa9b57a68533d38e9a6b2/projects/ROCKNIX/devices/SM8250/patches/linux/0063_Mangmi-Pocket-Max-HL7139-charge-pump.patch
  upstream: unknown
- `patches/0011-qcom-pm8150b-charger.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/0011-qcom-pm8150b-charger.patch
  upstream: unknown
  notes: Armada refreshed only the Makefile context for Linux 7.2's expanded Surface power-supply entries; charger and fuel-gauge behavior is unchanged.
- `patches/0005-sm8250-uart.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/0005-sm8250-uart.patch
  upstream: unknown
- `patches/9998-sm8250-gpu-tuning.patch`
  source: https://github.com/ROCKNIX/distribution/blob/f3e2b6187cd2ae2dc5122edfebe84228a314f2c5/projects/ROCKNIX/devices/SM8250/patches/linux/9998-gpu-tuning.patch
  upstream: unknown
  notes: Contents are verbatim; Armada renamed the file from the ROCKNIX `9998-gpu-tuning.patch`.
- `patches/0001-msm-dsi-restore-wide_bus-bpp-calculation.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/0001-msm-dsi-restore-wide_bus-bpp-calculation.patch
  upstream: unknown
  notes: Armada limited the ROCKNIX change to SM8250 so it does not alter the shared DSI path on other supported SoCs.
- `patches/0012-ASoC-qcom-q6asm-dai-Change-some-default-periods.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/0012-ASoC-qcom-q6asm-dai-Change-some-default-periods.patch
  upstream: unknown
- `patches/0062_wsa881x-shared-powerdown-gpio.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/0062_wsa881x-shared-powerdown-gpio.patch
  upstream: unknown
  notes: Ported to Linux 7.2's `GPIOD_OUT_LOW` initialization while retaining the non-exclusive request needed by boards whose two amplifiers share one powerdown GPIO.
- `patches/0100-revert-force-16bit-audio.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/0100-revert-force-16bit-audio.patch
  upstream: unknown
- `patches/0300-batocera-fix-headphone-jack-detection.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/0300-batocera-fix-headphone-jack-detection.patch
  upstream: unknown
  notes: Armada limited the ROCKNIX headphone-jack workaround to SM8250 so it does not alter shared codec behavior on other supported SoCs.
- `patches/0102-arm64-dts-qcom-pm8150-Add-nvmem-support-for-PM8150-R.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/0102-arm64-dts-qcom-pm8150-Add-nvmem-support-for-PM8150-R.patch
  upstream: unknown
- `patches/9999-sm8250-disable-coresight-stm.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/patches/linux/9999-remove-log-spam.patch
  upstream: unknown
  notes: Armada carries only the ROCKNIX device-tree change that disables CoreSight STM and omits the broader log-suppression changes from the source patch.
- `patches/0026-dt-bindings-arm-qcom-ids-Add-SoC-ID-for-CQ8725S.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0026-dt-bindings-arm-qcom-ids-Add-SoC-ID-for-CQ8725S.patch
  upstream: https://lore.kernel.org/r/20260605-cq8725s-soc-id-v1-1-bb1ef93de649@gmail.com
- `patches/0027-soc-qcom-socinfo-Add-CQ8725S-SoC-ID.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0027-soc-qcom-socinfo-Add-CQ8725S-SoC-ID.patch
  upstream: https://lore.kernel.org/r/20260605-cq8725s-soc-id-v1-2-bb1ef93de649@gmail.com
- `patches/0034-arm64-dts-qcom-sm8750-Add-UART15.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0034-arm64-dts-qcom-sm8750-Add-UART15.patch
  upstream: https://lore.kernel.org/r/20260605-sm8750-uart15-v1-1-93e660722e61@gmail.com
- `patches/0033-arm64-dts-qcom-sm8750-gpu-clock-controllers.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0033-arm64-dts-qcom-sm8750-gpu-clock-controllers.patch
  upstream: https://lore.kernel.org/r/20260714-gpucc_dt_v6-v6-1-16bf5289572d@oss.qualcomm.com
- `patches/0038-arm64-dts-qcom-sm8750-add-GPU-nodes.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0038-arm64-dts-qcom-sm8750-add-GPU-nodes.patch
  upstream: unknown
- `patches/0038a-arm64-dts-qcom-sm8750-map-A8xx-RSCC-registers.patch`
  source: armada
  upstream: local
  notes: Armada expands the SM8750 GPU register mapping to `0x6c000` so Linux 7.1's A8xx recovery path can access RSCC at GPU offset `0x50000` without faulting.
- `patches/0035-arm64-dts-qcom-sm8750-set-CPU-capacity-dmips-mhz.patch`
  source: https://github.com/ROCKNIX/distribution/blob/f3e2b6187cd2ae2dc5122edfebe84228a314f2c5/projects/ROCKNIX/devices/SM8750/patches/linux/0076-arm64-dts-qcom-sm8750-set-CPU-capacity-dmips-mhz.patch
  upstream: unknown
- `patches/0037-arm64-dts-qcom-sm8750-add-CPU-thermal-cooling.patch`
  source: https://github.com/ROCKNIX/distribution/blob/b1e9d07b251c5a013d303a518106c547db001b74/projects/ROCKNIX/devices/SM8750/patches/linux/0075-arm64-dts-qcom-sm8750-add-CPU-thermal-cooling.patch
  upstream: unknown
  notes: Linux 7.2 supplies the CPU cooling-cell properties; Armada retains the missing passive trips and cooling maps.
- `patches/0049-drm-msm-a8xx-add-adreno-830-catalog.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0049-drm-msm-a8xx-add-adreno-830-catalog.patch
  upstream: unknown
- `patches/0039-wifi-ath12k-add-initial-hardware-definition-for-WCN7.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0039-wifi-ath12k-add-initial-hardware-definition-for-WCN7.patch
  upstream: unknown
  notes: Armada refreshed only the hardware-parameter insertion context for Linux 7.2's expanded IPQ5332 entry; WCN7860 behavior is unchanged.
- `patches/0040-wifi-ath12k-send-QDSS-config-when-CNSS_QDSS_CFG_MISS.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0040-wifi-ath12k-send-QDSS-config-when-CNSS_QDSS_CFG_MISS.patch
  upstream: unknown
- `patches/0041-wifi-ath12k-disable-CNSS_QDSS_CFG_MISS_V01-for-the-W.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0041-wifi-ath12k-disable-CNSS_QDSS_CFG_MISS_V01-for-the-W.patch
  upstream: unknown
- `patches/0042-PCI-pwrctrl-pwrseq-add-support-for-WCN7860.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0042-PCI-pwrctrl-pwrseq-add-support-for-WCN7860.patch
  upstream: unknown
- `patches/0043-power-sequencing-qcom-wcn-add-support-for-WCN7860.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0043-power-sequencing-qcom-wcn-add-support-for-WCN7860.patch
  upstream: unknown
- `patches/0044-clk-qcom-gcc-sm8750-Do-not-turn-off-PCIe-GDSCs-durin.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0044-clk-qcom-gcc-sm8750-Do-not-turn-off-PCIe-GDSCs-durin.patch
  upstream: https://lore.kernel.org/r/20260102-pci_gdsc_fix-v1-3-b17ed3d175bc@oss.qualcomm.com
- `patches/0045-Bluetooth-qca-add-WCN7860-support.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0045-Bluetooth-qca-add-WCN7860-support.patch
  upstream: unknown
  notes: Armada rebased ROCKNIX's WCN7860 additions onto Linux 7.1 after upstream restructured the QCA Bluetooth switch cases and renamed the power-off helper.
- `patches/0066-scsi-ufs-ufs-qcom-add-sm8750-compatible.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0066-scsi-ufs-ufs-qcom-add-sm8750-compatible.patch
  upstream: unknown
- `patches/0509-soc-qcom-pmic_glink_altmode-defer-until-mux-switch-ready.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0509-soc-qcom-pmic_glink_altmode-defer-until-mux-switch-ready.patch
  upstream: unknown
  notes: Armada gates both deferrals on `qcom,sm8750`. ROCKNIX runs this only in its SM8750 kernel, where the mode-switch supplier registers late. Boards that declare no mode-switch at all (the AYANEO SM8550 family) would defer forever, which blocks the DP aux bridges, keeps the msm DRM aggregate from binding, and leaves the internal panel dark. Hardware-confirmed on the Pocket EVO. In Linux 7.2.6, a declared-but-late provider already returns `-EPROBE_DEFER` through the `IS_ERR()` path ahead of these NULL checks, so the gated checks are ROCKNIX's SM8750 fallback on top of that distinction rather than the primary defer mechanism.
- `patches/0519-usb-typec-ucsi-clear-USB-role.patch`
  source: https://github.com/ROCKNIX/distribution/commit/c9629c95a5655dcfb68e8f3aaf75f9967a9e9656
  upstream: unknown
- `patches/0517-usb-typec-mux-dont-swallow-EPROBE_DEFER.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0517-usb-typec-mux-dont-swallow-EPROBE_DEFER.patch
  upstream: unknown
  notes: Retains only array initialization; Linux 7.2.6 includes the probe-deferral fixes.
- `patches/0603-ASoC-codecs-wcd939x-keep-the-codec-resumed-while-a-ja.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0603-ASoC-codecs-wcd939x-keep-the-codec-resumed-while-a-ja.patch
  upstream: unknown
- `patches/0060-ASoC-qcom-sc8280xp-enable-MI2S-bit-clock-on-BE-startup.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0060-ASoC-qcom-sc8280xp-enable-MI2S-bit-clock-on-BE-startup.patch
  upstream: unknown
  notes: Armada combined ROCKNIX's SM8750 clock-reference fix with Armada's Primary-MI2S clock handling while rebasing the shared driver onto Linux 7.1.
- `patches/0072-ASoC-lpass-rx-macro-add-HPH-PCM-mode.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0072-ASoC-lpass-rx-macro-add-HPH-PCM-mode.patch
  upstream: unknown
- `patches/0073-ASoC-wcd939x-add-HPH-PCM-HiFi-mode.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0073-ASoC-wcd939x-add-HPH-PCM-HiFi-mode.patch
  upstream: unknown
- `patches/0074-soundwire-qcom-PCM-data-port-format-enable.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0074-soundwire-qcom-PCM-data-port-format-enable.patch
  upstream: unknown
- `patches/0612-ROCKNIX-odin3-q6apm-start-mi2s-port-at-prepare.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0612-ROCKNIX-odin3-q6apm-start-mi2s-port-at-prepare.patch
  upstream: unknown
- `patches/0613-ASoC-q6apm-scope-prepare-start-to-MI2S.patch`
  source: armada
  upstream: local
  notes: Armada added this follow-up to limit `0612` to playback MI2S DAIs; without it, the ROCKNIX change would affect every playback DAI using the shared q6apm driver.
- `patches/0618-drm-msm-dp-dont-fail-audio-prepare-when-display-off.patch`
  source: https://github.com/ROCKNIX/distribution/pull/3187
  upstream: unknown
  notes: Imported unchanged from the linked ROCKNIX pull request.
- `dts/qcs8550-ayaneo-pocketace.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/linux/dts/qcom/qcs8550-ayaneo-pocketace.dts
- `dts/qcs8550-ayaneo-pocket-common.dtsi`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/linux/dts/qcom/qcs8550-ayaneo-pocket-common.dtsi
- `dts/qcs8550-ayaneo-pocketdmg.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/linux/dts/qcom/qcs8550-ayaneo-pocketdmg.dts
- `dts/qcs8550-ayaneo-pocketds.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/linux/dts/qcom/qcs8550-ayaneo-pocketds.dts
- `dts/qcs8550-ayaneo-pocketevo.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/linux/dts/qcom/qcs8550-ayaneo-pocketevo.dts
- `dts/qcs8550-ayaneo-pockets1k.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/linux/dts/qcom/qcs8550-ayaneo-pockets1k.dts
- `dts/qcs8550-ayaneo-pockets2k.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/linux/dts/qcom/qcs8550-ayaneo-pockets2k.dts
- `dts/qcs8550-ayn-common.dtsi`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/linux/dts/qcom/qcs8550-ayn-common.dtsi
- `dts/qcs8550-ayn-odin2.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/linux/dts/qcom/qcs8550-ayn-odin2.dts
- `dts/qcs8550-ayn-odin2mini.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/linux/dts/qcom/qcs8550-ayn-odin2mini.dts
- `dts/qcs8550-ayn-odin2portal.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/linux/dts/qcom/qcs8550-ayn-odin2portal.dts
- `dts/qcs8550-ayn-thor.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/linux/dts/qcom/qcs8550-ayn-thor.dts
- `dts/qcs8550-retroidpocket-rp6.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/linux/dts/qcom/qcs8550-retroidpocket-rp6.dts
- `dts/qcs8550-retroidpocket-rp6-top-dpad.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/linux/dts/qcom/qcs8550-retroidpocket-rp6-top-dpad.dts
- `dts/qcs8550-retroidpocket-rpnova.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/linux/dts/qcom/qcs8550-retroidpocket-rpnova.dts
- `dts/sm8650-ayaneo-common.dtsi`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8650/linux/dts/qcom/sm8650-ayaneo-common.dtsi
- `dts/sm8650-ayaneo-ps2.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8650/linux/dts/qcom/sm8650-ayaneo-ps2.dts
- `dts/sm8650-konkr-pf.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8650/linux/dts/qcom/sm8650-konkr-pf.dts
- `dts/sm8250-retroidpocket-common.dtsi`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/linux/dts/qcom/sm8250-retroidpocket-common.dtsi
- `dts/sm8250-ayn-thorlite.dts`
  source: https://github.com/ROCKNIX/distribution/blob/dbea089dd83e156babbbcabc677117cef08f1148/projects/ROCKNIX/devices/SM8250/linux/dts/qcom/sm8250-ayn-thorlite.dts
  notes: Imported verbatim from ROCKNIX; SHA-256 `62a06545c46fe052c69699c20c8c6b330c4b64a3ecdb6b5ba99420868a78597d`. Authored by Philippe Simons; retains the original BSD-3-Clause SPDX identifier and Retroid Pocket copyright notice.
- `dts/sm8250-ayn-thorlite.dts.patch`
  source: armada
  notes: Armada removes the kernel touchscreen coordinate transforms after copying `dts/sm8250-ayn-thorlite.dts`; Gamescope/libinput maps the native digitizer coordinates to the rotated outputs, and applying both transforms makes the right edge behave as the top edge. This matches Armada's full Thor handling.
- `dts/sm8250-mangmi-air-y-pro.dts`
  source: https://github.com/ROCKNIX/distribution/blob/807c74fc46c124891d8aa9b57a68533d38e9a6b2/projects/ROCKNIX/devices/SM8250/linux/dts/qcom/sm8250-mangmi-air-y-pro.dts
  notes: Imported verbatim from ROCKNIX; SHA-256 `d98f1104f4fe29f9bf8c94692beb491e840332a851f1f6994f015973ba24c018`.
- `dts/sm8250-mangmi-pocket-max.dts`
  source: https://github.com/ROCKNIX/distribution/blob/807c74fc46c124891d8aa9b57a68533d38e9a6b2/projects/ROCKNIX/devices/SM8250/linux/dts/qcom/sm8250-mangmi-pocket-max.dts
  notes: Imported verbatim from ROCKNIX; SHA-256 `f6128a97cf510fcd9ecf568a2e512c3f6f4210ad43e4fb1f542740f4b140dfd2`.
- `dts/sm8250-mangmi-pocket-max.dts.patch`
  source: armada
  notes: Drops ROCKNIX's kernel thermal-zone fan include after copying the DTS; Armada powerd owns the PWM fan curve and must not race a second controller.
- `dts/sm8250-retroidpocket-flip2.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/linux/dts/qcom/sm8250-retroidpocket-flip2.dts
- `dts/sm8250-retroidpocket-flip2-visionox.dts`
  source: armada
  notes: Support for Visionox display panel models
- `dts/sm8250-retroidpocket-rp5.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/linux/dts/qcom/sm8250-retroidpocket-rp5.dts
- `dts/sm8250-retroidpocket-rp5-visionox.dts`
  source: armada
  notes: Support for Visionox display panel models
- `dts/sm8250-retroidpocket-rpmini.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/linux/dts/qcom/sm8250-retroidpocket-rpmini.dts
- `dts/sm8250-retroidpocket-rpminiv2.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8250/linux/dts/qcom/sm8250-retroidpocket-rpminiv2.dts
- `dts/sm8750-konkr-pf-elite.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/linux/dts/qcom/sm8750-konkr-pf-elite.dts
- `dts/sm8750-konkr-pf-elite.dts.patch`
  source: armada
  notes: Armada adapts the Elite touchscreen node to the full ROCKNIX Chipone fork shared with the SM8650 Pocket FIT, keeps volume-up from waking the system, and adds the DisplayPort playback link required for USB-C DP Alt Mode audio; the touchscreen driver is selected only by those two device-tree nodes.
- `dts/cq8725s-ayn-common.dtsi`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0046-arm64-dts-qcom-Add-AYN-CQ8725S-Common.patch
  notes: Armada extracted this DTS from the cited ROCKNIX patch and then applied later ROCKNIX DTS updates, including the Odin 3 haptics nodes from ROCKNIX commit `81a31e3d0f`.
- `dts/cq8725s-ayn-odin3.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0047-arm64-dts-qcom-Add-AYN-Odin3.patch
  notes: Armada extracted this DTS from the cited ROCKNIX patch and then applied later ROCKNIX DTS updates.
- `dts/cq8725s-ayn-odin3.dts.patch`
  source: armada
  notes: Armada enables DPU dithering after copying `dts/cq8725s-ayn-odin3.dts`.
- `dts/cq8725s-ayn-common.dtsi.patch`
  source: armada
  notes: Armada keeps volume-up from waking the system, marks Odin 3's RSInput node as connected to the Qualcomm haptics device, and supplies the device's 1024 range. The 70-count `axis-deadzone` (an unmeasured ROCKNIX bring-up value) was dropped; like the RP6 and every other RSInput device the Odin 3 now passes its stick value through, leaving deadzone policy to Steam Input and the game.
- `dts/qcs8550-ayaneo-pocket-common.dtsi.patch`
  source: armada
  notes: Armada keeps volume-up from waking the system and removes the SDHCI capability mask after copying `dts/qcs8550-ayaneo-pocket-common.dtsi`.
- `dts/qcs8550-ayaneo-pocketace.dts.patch`
  source: armada
  notes: Armada applies this local patch after copying `dts/qcs8550-ayaneo-pocketace.dts`.
- `dts/qcs8550-ayaneo-pocketdmg.dts.patch`
  source: armada
  notes: Armada applies this local patch after copying `dts/qcs8550-ayaneo-pocketdmg.dts`.
- `dts/qcs8550-ayaneo-pockets1k.dts.patch`
  source: armada
  notes: Armada applies this local patch after copying `dts/qcs8550-ayaneo-pockets1k.dts`.
- `dts/qcs8550-ayaneo-pockets2k.dts.patch`
  source: armada
  notes: Armada applies this local patch after copying `dts/qcs8550-ayaneo-pockets2k.dts`.
- `dts/qcs8550-ayaneo-pocketds.dts.patch`
  source: armada
  notes: Armada applies this local patch after copying `dts/qcs8550-ayaneo-pocketds.dts`. It labels the lower GT911 input device as `bottom_touchscreen` and moves the lower panel onto the ST7703 driver contract: `vcc-supply` for the SGM3804 charge pump, and the former `enable-gpio` on TCA6408 GPIO0 re-modeled as a fixed regulator consumed as `iovcc-supply`. It also declares `vin-supply = <&tca6424_vcc>` on both expander-switched fixed regulators (`vdd_ts`, `panel1-iovcc`): the pca953x suspend callback disables its own VCC, and without the vin link the regulator core would cut the expander while the GT911 still holds VDDIO enabled, aborting async deep suspend mid Goodix screen-off write. It also adds a `gpio-keys-lid` node for the hinge hall sensor: stock Android reads it as a ROHM BU52053NVx (`qti.sensor.hall_effect`) through the SLPI sensor HAL rather than any Linux input driver, with no devicetree node of its own — its GPIO (TLMM 166, active-low, no internal pull; confirmed live via `/sys/kernel/debug/gpio` while toggling the lid) came from `dri_irq_num` in the vendor's `/vendor/etc/sensors/config/kailua_bu52053nvx_0.json` on-device.
- `dts/qcs8550-ayaneo-pocketevo.dts.patch`
  source: armada
  notes: Armada keeps the AYA Space, Menu, LC, and RC auxiliary keys from waking the system.
- `dts/qcs8550-ayn-common.dtsi.patch`
  source: armada
  notes: Armada keeps volume-up from waking the system, removes the SDHCI capability mask, and marks the shared RSInput node as connected to the PM8550B haptics device declared in the same common tree. This intentionally covers the AYN and Retroid products that inherit both nodes, including Pocket 6 and Nova.
- `dts/qcs8550-ayn-odin2portal.dts.patch`
  source: armada
  notes: Adds the back buttons from the Odin 2 DTS into the Odin 2 Portal DTS
- `dts/qcs8550-retroidpocket-rp6.dts.patch`
  source: armada
  notes: Armada switches Pocket 6 from ROCKNIX's Odin 2 fallback to audio firmware extracted from a Pocket 6 vendor image.
- `dts/qcs8550-ayn-thor.dts.patch`
  source: armada
  notes: Armada fixes the hall-sensor pinctrl, makes only the lid-open edge wake, corrects touch orientation, and enables DPU dithering on the top panel after copying `dts/qcs8550-ayn-thor.dts`.
- `dts/sm8650-ayaneo-common.dtsi.patch`
  source: armada
  notes: Armada keeps volume-up from waking the system and wires the upstream SY7758 driver after copying `dts/sm8650-ayaneo-common.dtsi`.
- `dts/sm8650-ayaneo-ps2.dts.patch`
  source: armada
  notes: Armada selects the accepted Pocket S2 WSA2 sound-card mapping after copying the ROCKNIX DTS.
- `dts/sm8650-konkr-pf.dts.patch`
  source: armada
  notes: Armada selects the shared WSA2 channel mapping through a Pocket FIT-specific sound-card compatible.

- `patches/0505-arm64-emulate-unaligned-atomics.patch`
  source: https://github.com/bylaws/linux/commit/7ae989a43ae7e3cb8007ac21c28dacc24c9d8320
  upstream: unknown
  notes: Rebased patch context for Linux 7.2.3 and Armada's compat-input patch; the unaligned-atomic handler is unchanged.
