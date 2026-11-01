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
- `patches/0048b-drm-msm-dsi-fix-pll-init-in-bonded-mode.patch`
  source: armada
  upstream: local
- `patches/0049-drm-msm-dpu-panel-opt-in-8bpc-dither.patch`
  source: armada
  upstream: local
  notes: Armada wrote this patch; it has not been submitted upstream.
- `patches/0066-drm-msm-dpu-enable-inline-rotation.patch`
  source: https://github.com/ROCKNIX/distribution/blob/60bb58c1db053255b700f3953b72d619ec5aa85d/projects/ROCKNIX/devices/SM8550/patches/linux/0066-drm-msm-dpu-enable-sm8550-inline-rotation.patch
  upstream: unknown
  notes: Armada merged the ROCKNIX SM8550, SM8650 and SM8750 patches into one for the combined kernel, with one shared feature mask and rotation config.
- `patches/0068-drm-msm-dpu-lutdma-dspp-igc-gamut.patch`
  source: armada
  upstream: local
- `patches/0069-dt-bindings-display-msm-dpu-lutdma-reg.patch`
  source: armada
  upstream: local
- `patches/0070-arm64-dts-qcom-dpu-lutdma-reg.patch`
  source: armada
  upstream: local
- `patches/0076-drm-msm-dpu-expose-abgr-xbgr-2101010-on-planes.patch`
  source: armada
  upstream: local
- `patches/0077-drm-msm-dpu-plane-igc-3d-lut-color-pipelines.patch`
  source: armada
  upstream: local
- `patches/0078-drm-msm-dpu-fix-vblank-timestamps-on-command-mode-panels.patch`
  source: armada
  upstream: local
- `patches/0078a-drm-msm-dpu-program-merge3d-for-command-mode.patch`
  source: https://github.com/RetroidPocket/linux/commit/b547718c91dbaf8fe27745afced8de00d1f7415b
  upstream: unknown
  notes: Unmodified Retroid fix that programs and flushes MERGE_3D for command-mode displays using two layer mixers. Required by the uncompressed 1280x960 Nova/Duo panel; otherwise DSI receives half a line and reports FIFO underflow.
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
- `patches/0518-ROCKNIX-odin3-panel-frame-length-calibration.patch`
  source: https://github.com/ROCKNIX/distribution/blob/abfdcfb57ff42180a50fca60a2a150641608d57e/projects/ROCKNIX/devices/SM8750/patches/linux/0518-ROCKNIX-odin3-panel-frame-length-calibration.patch
  upstream: unknown
  notes: Context refreshed onto Armada's 0060 and 0060a; the code is unchanged.
- `patches/0518a-drm-panel-icna35xx-serialise-live-frame-length-writes.patch`
  source: armada
  upstream: local
- `patches/0518b-drm-panel-icna35xx-calibrate-the-ICNA3512-frame-length.patch`
  source: armada
  upstream: local
- `patches/0105-dt-bindings-display-panel-retroid-il97680a.patch`
  source: https://github.com/RetroidPocket/linux/commit/9bfe85be2179d03338d09b8900f3b1916999ef15
  upstream: not submitted
- `patches/0105a-drm-panel-retroid-il97680a.patch`
  source: https://github.com/JPyke3/linux/commit/c102403bfcfe545d34e7124630f60e56d090753b
  upstream: not submitted
- `patches/0105b-drm-panel-il97680a-backport-orientation-helper.patch`
  source: armada
  upstream: not applicable
  notes: Only renames drm_of_get_panel_orientation() to of_drm_get_panel_orientation() for Linux 7.2.6. Drop when the base kernel provides the new name.
- `patches/0108-drm-msm-dpu-send-the-flip-event-after-the-vblank-irq.patch`
  source: https://github.com/portare-ch/portareos/blob/be06100b6d127692ed99401d23980fc04888ae01/projects/PortareOS/devices/SM8550/patches/linux/1098-drm-msm-dpu-send-the-flip-event-after-the-vblank-irq.patch
  upstream: unknown
  notes: Companion flip-event ordering fix for AVR; refreshed offsets for Armada and added the source link to the patch header. Armada restricts the kickoff-count wait to encoders that receive the vblank irq: a bonded DSI slave never does, so on dual-DSI panels (AYANEO Pocket S 2K) every commit hit the 50 ms timeout.
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
- `patches/0069a-input-konkr-sysbtn-add-pocket-fit-mcu.patch`
  source: armada
  upstream: local
- `patches/0541-input-joystick-mcu-joystick-power-the-mcu-off-in-suspend.patch`
  source: armada
  upstream: local
- `patches/0060_Mangmi-Pocket-Max-SPI-joypad.patch`
  source: https://github.com/ROCKNIX/distribution/blob/807c74fc46c124891d8aa9b57a68533d38e9a6b2/projects/ROCKNIX/devices/SM8250/patches/linux/0060_Mangmi-Pocket-Max-SPI-joypad.patch
  upstream: unknown
- `patches/0060b-input-mangmi-pocket-max-keep-trigger-conversion-independent-of-calibration.patch`
  source: armada
  upstream: local
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
- `patches/1008-HID-uhid-read-the-output-queue-under-qlock.patch`
  source: armada
  upstream: local
  notes: Fixes a NULL dereference in `uhid_char_read()` on arm64 that orphans InputPlumber's virtual controller and stalls Steam's controller thread until reboot. Mainline carries the same lockless read; this is a candidate for upstream submission.
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
- `patches/0534-serial-qcom-geni-add-force-suspend-resume-to-system-sleep-callbacks.patch`
  source: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=d0cd9c8d0fd59bc7d140f3d60cf02e1d80376dab
  upstream: https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=d0cd9c8d0fd59bc7d140f3d60cf02e1d80376dab
  notes: Backported to Linux 7.2 on top of 1006, re-enabling the masked IRQ when the force suspend or force resume fails.
- `patches/1007-input-rsinput-drop-the-mcu-supply-across-system-sleep.patch`
  source: armada
  upstream: local
- `patches/1300-input-rsinput-axis-deadzone.patch`
  source: armada
  upstream: local
  notes: Armada replaced ROCKNIX's global experimental Odin 3 range and deadzone defaults with a per-device `axis-deadzone` property. The Odin 3 DTS supplies its range and deadzone explicitly.
- `patches/1301-input-rsinput-decouple-trigger-reference-from-calibration.patch`
  source: armada
  upstream: local
  notes: Keeps the RSInput MCU trigger release reference independent of the calibrated evdev maximum, fixing incomplete travel and deteriorating repeated calibration on AYN devices (issue #423).
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
- `patches/0054c-pwm-sn3112-power-down-across-system-suspend.patch`
  source: armada
  upstream: local
- `patches/20260424_neil_armstrong_arm64_dts_qcom_sm8_456_50_add_missing_cx_power_domain_to_gcc.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/20260424_neil_armstrong_arm64_dts_qcom_sm8_456_50_add_missing_cx_power_domain_to_gcc.patch
  upstream: https://lore.kernel.org/r/20260615-topic-sm8x50-tie-gcc-to-cx-v2-0-6b5752dd4747@linaro.org
- `patches/v9_20260729_qualcomm_crypto_qce_runtime_pm_interconnect.patch`
  source: https://lore.kernel.org/r/20260729110455.641256-1-kuldeep.singh@oss.qualcomm.com
  upstream: https://lore.kernel.org/r/20260729110455.641256-1-kuldeep.singh@oss.qualcomm.com
  notes: Refreshed only its include context for Linux 7.2; runtime-PM and interconnect behavior is unchanged.
- `patches/v3_20261002_anandu_e_misc_fastrpc_fix_context_leak_and_hang_on_signal_interrupted_invoke.patch`
  source: https://lore.kernel.org/r/20261002-anandu-fastrpc-interrupted-invoke-v3-v3-1-31e90439d2ba@oss.qualcomm.com
  upstream: https://lore.kernel.org/r/20261002-anandu-fastrpc-interrupted-invoke-v3-v3-1-31e90439d2ba@oss.qualcomm.com
  notes: Backported to 7.2's inline wait, and put_work_scheduled uses xchg() instead of fl->lock because the rpmsg callback runs in hard IRQ; the commit message still describes v3.
- `patches/0569-soc-qcom-smp2p-reset-inbound-state-only-on-restart.patch`
  source: armada
  upstream: local
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
- `patches/0533-scsi-ufs-ufs-qcom-enable-only-lane-clocks-in-lane-clock-apis.patch`
  source: https://git.kernel.org/pub/scm/linux/kernel/git/mkp/scsi.git/commit/?id=f07317a8d57f382ec505597816271dd72ffa20c7
  upstream: https://git.kernel.org/pub/scm/linux/kernel/git/mkp/scsi.git/commit/?id=f07317a8d57f382ec505597816271dd72ffa20c7
- `patches/0535-scsi-ufs-core-fast-abort-unsupported-query-idns.patch`
  source: https://git.kernel.org/pub/scm/linux/kernel/git/mkp/scsi.git/commit/?id=d1fa5cea5dcd72a9ec21b835c572a28c0c3f4fbf
  upstream: https://git.kernel.org/pub/scm/linux/kernel/git/mkp/scsi.git/commit/?id=d1fa5cea5dcd72a9ec21b835c572a28c0c3f4fbf
- `patches/0536-scsi-ufs-core-dynamically-disable-timestamp-on-unsupported-devices.patch`
  source: https://git.kernel.org/pub/scm/linux/kernel/git/mkp/scsi.git/commit/?id=00eec343c7306be7f1103f5002abd77496937ff9
  upstream: https://git.kernel.org/pub/scm/linux/kernel/git/mkp/scsi.git/commit/?id=00eec343c7306be7f1103f5002abd77496937ff9
- `patches/0537-usb-xhci-pci-renesas-let-the-controller-power-off-in-suspend.patch`
  source: armada
  upstream: local
- `patches/0566-clk-qcom-gcc-sm8550-let-the-pcie-gdscs-collapse-in-suspend.patch`
  source: armada
  upstream: local
- `patches/0567-clk-qcom-gcc-sm8650-let-the-pcie-gdscs-collapse-in-suspend.patch`
  source: armada
  upstream: local
- `patches/0568-arm64-dts-qcom-sm8250-cpu-ddr-votes-active-only.patch`
  source: https://github.com/kettlelinux/kettlelinux/blob/c2849b95b3af9bf6d1d52cefa1e66167a22c86b4/kernel/patches/21-sm8250/0114-arm64-dts-qcom-sm8250-cpu-ddr-votes-active-only.patch
  upstream: unknown
- `patches/0512-PCI-qcom-skip-L23-ready-poll-on-SM8550.patch`
  source: armada
  upstream: local
- `patches/0513-PCI-qcom-honour-an-opp-suspend-opp-as-the-non-s2ram-memory-floor.patch`
  source: armada
  upstream: not submitted
  notes: On OPP-scaling platforms the OPP carries the only PCIe memory-path votes, so dropping it to NULL on non-S2RAM suspend leaves the RPMh sleep set with no DDR/LLCC contract and the AOP never resumes. Deliberately does not populate `pcie->icc_mem` on OPP platforms: `qcom_pcie_icc_opp_update()` prefers an `icc_mem` handle over the OPP branch, so providing one silently disables the post-link-training OPP update and pins the OPP at the probe-time maximum.
- `patches/0556-remoteproc-qcom-pas-manage-the-sm8750-soccp.patch`
  source: armada
  upstream: local
- `patches/0522-PCI-host-common-let-only-endpoints-veto-d3cold.patch`
  source: armada
  upstream: local
- `patches/0523-regulator-qcom-rpmh-add-suspend-state-support.patch`
  source: https://github.com/thorch-os/thorch/blob/82e7472e6cad5c08a55c3aef92ef5be218621b2c/packages/linux-thorch/patches/0218-regulator-qcom-rpmh-add-suspend-state-support.patch
  upstream: unknown
  notes: Uses the PMIC's own bypass mode (`pmic_bypass_mode`) instead of `PMIC4_BOB_MODE_PASS`, which is wrong on PMIC5.
- `patches/0524-regulator-core-apply-mem-state-for-s2idle.patch`
  source: https://github.com/thorch-os/thorch/blob/82e7472e6cad5c08a55c3aef92ef5be218621b2c/packages/linux-thorch/patches/0219-regulator-core-apply-mem-state-for-s2idle.patch
  upstream: unknown
- `patches/0525-regulator-core-log-missing-suspend-configuration-at-debug.patch`
  source: armada
  upstream: local
- `patches/0526-regulator-apply-state-mem-in-s2idle-only-for-opted-in-drivers.patch`
  source: armada
  upstream: local
- `patches/0514-PCI-qcom-honor-iommu-map-cell-count.patch`
  source: https://lkml.iu.edu/2609.0/16096.html
  upstream: https://lore.kernel.org/r/20260907143349.317495-1-mani@kernel.org
- `patches/0514a-of-property-honor-iommu-cells-in-iommu-map-devlinks.patch`
  source: armada
  upstream: local
- `patches/0001-pcie-update-sm8550-dtsi.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0001-pcie-update-sm8550-dtsi.patch
  upstream: https://lore.kernel.org/r/20260611-wake-v2-33-2744251b1181@oss.qualcomm.com
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
- `patches/1021-wifi-ath12k-convert-scan-timeout-to-wiphy-delayed-work.patch`
  source: https://lkml.iu.edu/2609.1/17957.html
  upstream: https://lkml.iu.edu/2609.1/17957.html
- `patches/1030-media-iris-send-the-stream-POC-type.patch`
  source: armada
  upstream: local
- `patches/1031-media-iris-stop-AV1-tier-overwriting-HEVC-tier.patch`
  source: armada
  upstream: local
- `patches/v9_20260801_sachin_garg_media_iris_cache_work_mode_in_iris_set_stage.patch`
  source: https://lore.kernel.org/r/20260801-iris_multi_slice-v9-1-bddf1449c280@oss.qualcomm.com
  upstream: https://lore.kernel.org/r/20260801-iris_multi_slice-v9-1-bddf1449c280@oss.qualcomm.com
- `patches/1032-media-iris-count-CABAC-cost-in-the-decoder-VSP-clock.patch`
  source: armada
  upstream: local
- `patches/1033-media-iris-add-decoder-display-delay-controls.patch`
  source: armada
  upstream: local
- `patches/1034-media-iris-decode-in-stage-1-for-decode-order.patch`
  source: armada
  upstream: local
- `patches/1035-media-iris-run-decode-order-sessions-at-the-highest-clock.patch`
  source: armada
  upstream: local
- `patches/1036-media-iris-only-rescale-decoder-power-on-bitstream-queue.patch`
  source: armada
  upstream: local
- `patches/1037-media-iris-decode-in-stage-1-at-the-top-clock-by-default.patch`
  source: armada
  upstream: local
- `patches/1370-media-iris-a-resolution-change-last-buffer-is-not-an-error.patch`
  source: https://github.com/kettlelinux/kettlelinux/blob/2b7661b4d937d7efbb487c4bba84f8705be7cc5d/kernel/patches/40-kettle/1370-media-iris-a-resolution-change-last-buffer-is-not-an-error.patch
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
- `patches/0903-power-supply-qcom-battmgr-expose-the-charge-current-limit.patch`
  source: armada
  upstream: local
- `patches/0904-power-supply-qcom-battmgr-report-charge-threshold-set-failures.patch`
  source: armada
  upstream: local
- `patches/0910-firmware-qcom-scm-allow-QSEECOM-on-OpenABL-s-platforms.patch`
  source: https://github.com/OpenHandheldCollective/OpenABL/blob/8f09253f8f93e7d9ff0b5baf3bda87976f0c54ac/Linux/0001-firmware-qcom-scm-allow-QSEECOM-on-OpenABL-s-platforms.patch
  upstream: unknown
  notes: Upstream tested it on SM6115 only. Armada needs it for SM8250, SM8550, SM8650 and SM8750, where OpenABL keeps its settings in UEFI variables.
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
- `patches/0008a-input-retroid-keep-trigger-conversion-independent-of-calibration.patch`
  source: armada
  upstream: local
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
- `patches/0301-drm-panel-add-ayaneo-ar18-panel.patch`
  source: https://github.com/ROCKNIX/distribution/blob/aa418ad72e3e661b3834f46168bdf183276df2ac/projects/ROCKNIX/devices/SM8550/patches/linux/0064-gpu-drm-panel-add-ar16-4inch-panel.patch
  upstream: not submitted
  notes: Rewritten for the AYANEO Pocket MICRO 2 ST7123 panel on the mipi_dsi_multi_context API; timings and init sequence from the vendor device tree.
- `patches/0302-input-touchscreen-add-sitronix-st7123.patch`
  source: https://github.com/raspberrypi/linux/commit/6d4adb6bfea64581dff1c670a17333b63b8ba05d
  upstream: not submitted
  notes: Waveshare's Sitronix ST7123 driver from the Raspberry Pi kernel (rpi-6.18.y), with chip id 0x87 accepted for the AYANEO Pocket MICRO 2.
- `patches/0303-hid-add-ayaneo-pocket-micro2-force-feedback.patch`
  source: armada
  upstream: local
  notes: Rumble report format from the stock Android kernel's hid-ayaneo. Binds on every AYANEO 4001:0428 pad, rumble only on the Pocket MICRO 2.
- `patches/0304-ASoC-wcd938x-treat-failed-zdet-ramp-as-floating.patch`
  source: armada
  upstream: local
- `patches/0305-backlight-qcom-wled-always-disable-ovp-irq-at-probe.patch`
  source: armada
  upstream: local
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
- `patches/0556a-arm64-dts-qcom-sm8750-add-the-soccp.patch`
  source: armada
  upstream: local
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
  notes: Armada keeps the HPH PCM remap off the TX device, whose channel ids overlap the HPH ones, and writes the crosstalk coefficients before the compander-off return.
- `patches/0081-ASoC-wcd939x-fix-headphone-analog-volume-controls.patch`
  source: armada
  upstream: local
- `patches/0081b-ASoC-wcd939x-program-Class-H-transport-fields.patch`
  source: armada
  upstream: local
  notes: Declare the Class-H sink FULL so SoundWire programs its window and packing fields. Based on ovid-io’s analysis in https://github.com/armada-os/armada/pull/803#issuecomment-6481609416 and Pocket S2 Android/Linux captures.
- `patches/0074-soundwire-qcom-PCM-data-port-format-enable.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0074-soundwire-qcom-PCM-data-port-format-enable.patch
  upstream: unknown
- `patches/0081c-soundwire-qcom-configure-Class-H-master-transport.patch`
  source: armada
  upstream: local
  notes: Add optional master channel masks and SSP periods while preserving codec masks and existing defaults. Keep the PCM/PDM32 formatter enabled until both banks stop. Adapts Qualcomm’s master mapping and formatter lifecycle from https://api.github.com/repos/OnePlusOSS/android_kernel_modules_and_devicetree_oneplus_sm8650/git/blobs/a42eca8f2ea2c3692decabf48930a12e83d2c426 and ovid-io’s transport analysis in PR #803.
- `patches/0081d-dt-bindings-soundwire-qcom-describe-master-transport.patch`
  source: armada
  upstream: local
  notes: Document optional master channel masks, SSP period and the PCM/PDM32 formatter mask. The Pocket S2 device tree selects these settings.
- `patches/0081e-ASoC-wcd939x-initialize-revision-specific-bias-and-RCO.patch`
  source: armada
  upstream: local
  notes: Adapt Qualcomm’s revision-specific bias/RCO initialization, checked against the retained Pocket S2 Android module. Revisions 1.1 and 2.0 receive checked initialization; revision 1.0 and unknown IDs retain existing behavior. Reference: https://api.github.com/repos/OnePlusOSS/android_kernel_modules_and_devicetree_oneplus_sm8650/git/blobs/108c2b4bfa69fc5d372dfde2cdc46778422e49b5.
- `patches/0081f-ASoC-wcd939x-preserve-PCM-ULP-mode-before-PA-enable.patch`
  source: armada
  upstream: local
  notes: Keep PCM ULP selected during PA startup, following the Pocket S2 Android callback. Patch 0081g subsequently generalizes the selected-mode handling and replaces the intermediate startup sequence.
- `patches/0081g-ASoC-wcd939x-align-PCM-headphone-lifecycle.patch`
  source: https://api.github.com/repos/OnePlusOSS/android_kernel_modules_and_devicetree_oneplus_sm8650/git/blobs/108c2b4bfa69fc5d372dfde2cdc46778422e49b5
  upstream: unknown
  notes: Adapt Qualcomm’s PCM setup order, per-channel compander shutdown and selected power mode. Relevant callbacks were compared with the retained Pocket S2 Android WCD939x module; Linux register masks and lifecycle handling are retained.
- `patches/0081h-ASoC-wcd939x-sequence-shared-headphone-supplies-once.patch`
  source: https://github.com/diogotr7/armada/commit/d7896cae0a0f1b957140ec779d609b6d6e0e889d
  upstream: unknown
  notes: Adapt Diogo Trindade’s first-start/last-stop Class-H handling while retaining the PCM lifecycle changes. Shared supplies are started once and stopped after the final headphone channel.
- `patches/0081i-ASoC-wcd939x-sequence-revision-2-impedance-supplies.patch`
  source: armada
  upstream: local
  notes: Adapt Qualcomm’s revision-2 impedance supply sequence, checked against the retained Pocket S2 Android WCD939x callback. Check temporary supply ownership and cleanup; invalidate failed measurements.
- `patches/0081j-ASoC-wcd939x-manage-jack-leakage-override.patch`
  source: armada
  upstream: local
  notes: Add the initial leakage lifecycle hook from Qualcomm WCD939x/common-MBHC source, including blob 19eec1c2782406139ae7ff47fc46a2c92cbf2346. Patch 0081k corrects its routing dependency and event semantics using the subsequently retained Pocket S2 common-MBHC module and jack traces.
- `patches/0081k-ASoC-wcd939x-separate-jack-leakage-control.patch`
  source: armada
  upstream: local
  notes: Separate codec leakage control from optional Type-C switch routing. Follow the retained Pocket S2 codec/common-MBHC insertion and removal sequence, including unclassified-plug cleanup.
- `patches/0081l-ASoC-wcd939x-add-USBSS-jack-measurement-provider.patch`
  source: armada
  upstream: local
  notes: Add a managed independent-jack USBSS provider with checked RDAC selection and serialized save/setup/tap/restore transactions. Adapts the retained Pocket S2 Android codec and Qualcomm USBSS sequence; Type-C audio routing remains separate.
- `patches/0081m-ASoC-wcd939x-use-PCM-PA-settling-delays.patch`
  source: armada
  upstream: local
  notes: Use the Android PCM path’s 20/21 ms PA settling delays instead of the PDM-compander 7 ms branch. Preserve PDM conditions and the shared delay flag; Android/Linux startup traces corroborate the sequence difference.
- `patches/0081n-ASoC-wcd-mbhc-drain-workers-before-free.patch`
  source: armada
  upstream: local
  notes: Drain jack detection, correction and delayed button work in producer order without holding the plug worker’s mutex. This shared MBHC teardown change protects provider and consumer removal.
- `patches/0081o-dt-bindings-sound-wcd939x-describe-jack-measurement.patch`
  source: armada
  upstream: local
  notes: Describe the independent-jack USBSS measurement supplier and exclude reciprocal Type-C audio routing dependencies.
- `patches/0081p-ASoC-wcd939x-coordinate-codec-reset-with-USBSS.patch`
  source: armada
  upstream: local
  notes: Coordinate USBSS protection fields before the first driver-controlled reset transition and restore operating values afterward. Adapt the retained Pocket S2 Android sequence with checked I/O, GPIO operations and cleanup; boards without the provider association keep their reset path.
- `patches/0081q-dt-bindings-sound-wcd939x-describe-reset-coordination.patch`
  source: armada
  upstream: local
  notes: Extend the independent-jack supplier binding to describe codec-reset protection as well as impedance measurement.
- `patches/0081r-ASoC-wcd939x-handle-SoundWire-cache-recovery-errors.patch`
  source: armada
  upstream: local
  notes: Preserve WCD939x cache state across detach/replay errors, check RX/TX initialization and provide one deferred PM recovery opportunity per successful attachment. Uses Linux 7.2.6 SoundWire/runtime-PM lifecycle APIs; no stream reconstruction or codec reset is added.
- `patches/0081s-usb-typec-wcd939x-usbss-add-S2-state-recovery.patch`
  source: https://api.github.com/repos/OnePlusOSS/android_kernel_oneplus_sm8650/git/blobs/8effe5ea6a8216bf5db182f673ca02b04a1fd14d
  upstream: unknown
  notes: Adapt Qualcomm’s periodic conditional recovery, checked against the installed Pocket S2 module. An S2 quirk restores only Linux-owned stable fields with uncached reads, transactional targets and suspend/removal cancellation. Android’s full cache replay and USB-C analogue-accessory codec notification are excluded.
- `patches/0075-ASoC-wsa884x-preserve-Pocket-S2-compander-gain.patch`
  source: armada
  upstream: local
  notes: AYANEO Pocket S2, Pocket DS and KONKR Pocket FIT fix. The WSA884x amplifier's POST_PMU sequence selects the SoundWire compander, but the unmute path immediately overrode it with the fixed CSR gain, discarding the boards' matched compander plus digital-volume configuration. The driver now keeps the compander selection when its port is enabled, gated on the `ayaneo,pocket-s2`, `ayaneo,pocketds` and `konkr,pocket-fit` machine compatibles, so every other WSA884x machine keeps the original fixed-gain behavior. This requires a matching UCM that enables both macro companders, initializes both PA controls to 17 (hardware gain index 14, unity), and uses digital volume. Scoped to the Armada distribution; not a Linux upstream submission.
- `patches/0612-ROCKNIX-odin3-q6apm-start-mi2s-port-at-prepare.patch`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8550/patches/linux/0612-ROCKNIX-odin3-q6apm-start-mi2s-port-at-prepare.patch
  upstream: unknown
- `patches/0613-ASoC-q6apm-scope-prepare-start-to-MI2S.patch`
  source: armada
  upstream: local
  notes: Armada added this follow-up to limit `0612` to playback MI2S DAIs; without it, the ROCKNIX change would affect every playback DAI using the shared q6apm driver.
- `patches/0528-ASoC-qcom-sc8280xp-suspend-the-card-and-its-streams.patch`
  source: armada
  upstream: local
- `patches/0538-ASoC-qcom-sc8280xp-cap-Pocket-DS-speaker-digital-volume.patch`
  source: armada
  upstream: local
  notes: AYANEO Pocket DS only. With the compander speaker path from `0075`, the speakers audibly distorted at WSA RX digital volume 73 and were clean at 71 across the bass, hot-master and vocal test clips, so the upstream limit of 81 is lowered to 71 on this board. A peak limiter in userspace could allow a higher cap later.
- `patches/0529-ASoC-qdsp6-q6apm-fail-the-graph-open-when-the-DSP-rejects-it.patch`
  source: armada
  upstream: local
- `patches/0530-ASoC-qdsp6-release-AudioReach-graphs-across-system-suspend.patch`
  source: armada
  upstream: local
- `patches/0531-ASoC-qcom-sc8280xp-release-the-board-i2s-clock-across-system-suspend.patch`
  source: armada
  upstream: local
- `patches/0532-hwmon-pwm-fan-optionally-run-the-fan-while-charging-in-s2idle.patch`
  source: armada
  upstream: local
- `patches/0540-arm64-signal-reapply-the-ssbs-policy-on-sigreturn.patch`
  source: armada
  upstream: local
- `patches/0618-drm-msm-dp-dont-fail-audio-prepare-when-display-off.patch`
  source: https://github.com/ROCKNIX/distribution/pull/3187
  upstream: unknown
  notes: Imported unchanged from the linked ROCKNIX pull request.
- `patches/0619-drm-msm-map-submitqueue-priority-onto-high-low.patch`
  source: armada
  upstream: local
- `patches/0620-drm-msm-a6xx-hfi-irq-clears-only-the-cm3-fault.patch`
  source: https://github.com/kettlelinux/kettlelinux/blob/d379ae1d0efeb8dd282647a1598efd719c6ecd4d/kernel/patches/40-kettle/1350-drm-msm-a6xx-hfi-irq-clears-only-the-cm3-fault.patch
  upstream: unknown
- `patches/0621-drm-msm-a6xx-bound-the-gmu-wait-for-a-fault-devcoredump.patch`
  source: https://github.com/kettlelinux/kettlelinux/blob/d379ae1d0efeb8dd282647a1598efd719c6ecd4d/kernel/patches/40-kettle/1351-drm-msm-a6xx-bound-the-gmu-wait-for-a-fault-devcoredump.patch
  upstream: unknown
- `patches/0622-drm-msm-a6xx-mask-the-hfi-interrupt-before-booting-the-gmu.patch`
  source: armada
  upstream: local
- `patches/0623-arm64-dts-qcom-sm8550-sm8650-add-the-ADSP-FastRPC-remote-heap.patch`
  source: https://github.com/hashtagbasit/SteamOS-ARM-Port/blob/162a3d97e61d94e0740193a8af49fc95de408439/external-and-mods/kernel-sm8550/dts/qcs8550-ayn-odin2-gyro.dtsi
  upstream: not submitted
  notes: justjoseorg's heap node, memory-region and qcom,vmids, moved from a board file into the SM8550, QCS8550 and SM8650 SoC dtsi so every board on those SoCs has them; qcom,fastrpc-adsp-sensors-pdr is dropped because this kernel does not read it.
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
- `dts/sm8250-ayaneo-pocket-micro2.dts`
  source: armada
  notes: Board file for the AYANEO Pocket MICRO 2; fan is left to armada-powerd (no thermal-zone include).
- `dts/sm8250-ayn-thorlite.dts`
  source: https://github.com/ROCKNIX/distribution/blob/dbea089dd83e156babbbcabc677117cef08f1148/projects/ROCKNIX/devices/SM8250/linux/dts/qcom/sm8250-ayn-thorlite.dts
  notes: Imported verbatim from ROCKNIX; SHA-256 `62a06545c46fe052c69699c20c8c6b330c4b64a3ecdb6b5ba99420868a78597d`. Authored by Philippe Simons; retains the original BSD-3-Clause SPDX identifier and Retroid Pocket copyright notice.
- `dts/sm8250-ayn-thorlite.dts.patch`
  source: armada
  notes: Armada removes the kernel touchscreen coordinate transforms after copying `dts/sm8250-ayn-thorlite.dts`; Gamescope/libinput maps the native digitizer coordinates to the rotated outputs, and applying both transforms makes the right edge behave as the top edge. This matches Armada's full Thor handling. Also enables the AYN button.
- `dts/sm8250-mangmi-air-y-pro.dts`
  source: https://github.com/ROCKNIX/distribution/blob/807c74fc46c124891d8aa9b57a68533d38e9a6b2/projects/ROCKNIX/devices/SM8250/linux/dts/qcom/sm8250-mangmi-air-y-pro.dts
  notes: Imported verbatim from ROCKNIX; SHA-256 `d98f1104f4fe29f9bf8c94692beb491e840332a851f1f6994f015973ba24c018`.
- `dts/sm8250-mangmi-air-y-pro.dts.patch`
  source: armada
  notes: Exposes the two centre-logo RGB LEDs on left AW20036 channels 24–29, verified on Air Y Pro hardware.
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
  notes: Armada adapts the Elite touchscreen node to the full ROCKNIX Chipone fork shared with the SM8650 Pocket FIT, keeps volume-up from waking the system, and adds the DisplayPort playback link required for USB-C DP Alt Mode audio; the touchscreen driver is selected only by those two device-tree nodes. Armada also marks PCIe WAKE# active-low and idles the codec rails in LPM during s2idle, and points the SoCCP remoteproc at the Elite's own firmware.
- `dts/cq8725s-ayn-common.dtsi`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0046-arm64-dts-qcom-Add-AYN-CQ8725S-Common.patch
  notes: Armada extracted this DTS from the cited ROCKNIX patch and then applied later ROCKNIX DTS updates, including the Odin 3 haptics nodes from ROCKNIX commit `81a31e3d0f`.
- `dts/cq8725s-ayn-odin3.dts`
  source: https://github.com/ROCKNIX/distribution/blob/bcf3b5bc574990b96543484575b06f912153a715/projects/ROCKNIX/devices/SM8750/patches/linux/0047-arm64-dts-qcom-Add-AYN-Odin3.patch
  notes: Armada extracted this DTS from the cited ROCKNIX patch and then applied later ROCKNIX DTS updates.
- `dts/cq8725s-ayn-odin3.dts.patch`
  source: armada
  notes: Armada enables DPU dithering, codec-rail LPM sleep states, the PM8550 RGB charge LED and the WCD DMIC internal mic route after copying `dts/cq8725s-ayn-odin3.dts`.
- `dts/cq8725s-ayn-common.dtsi.patch`
  source: armada
  notes: Armada keeps volume-up from waking the system, marks Odin 3's RSInput node as connected to the Qualcomm haptics device, supplies the device's 1024 range, marks PCIe WAKE# active-low, and keeps the four switched WCN7860 PMU supply rails always-on because re-enabling them at resume can hang the SoC. The 70-count `axis-deadzone` (an unmeasured ROCKNIX bring-up value) was dropped; like the RP6 and every other RSInput device the Odin 3 now passes its stick value through, leaving deadzone policy to Steam Input and the game.
- `dts/qcs8550-ayaneo-pocket-common.dtsi.patch`
  source: armada
  notes: Armada keeps volume-up from waking the system, removes the SDHCI capability mask, marks PCIe WAKE# active-low, and idles the codec rail in LPM during s2idle after copying `dts/qcs8550-ayaneo-pocket-common.dtsi`.
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
  notes: Armada keeps volume-up from waking the system, removes the SDHCI capability mask, and marks the shared RSInput node as connected to the PM8550B haptics device declared in the same common tree; this covers the AYN and Retroid products that inherit both nodes, including Pocket 6 and Nova. Armada also marks PCIe WAKE# active-low, idles the codec rails in LPM during s2idle, and powers RSInput from `vdd_mcu_3v3` instead of the shared `vreg_bob2`, without always-on, so the driver can cut the MCU in suspend.
- `dts/qcs8550-ayn-odin2.dts.patch`
  source: armada
  upstream: local
- `dts/qcs8550-ayn-odin2portal.dts.patch`
  source: armada
  notes: Adds the back buttons from the Odin 2 DTS into the Odin 2 Portal DTS
- `dts/qcs8550-retroidpocket-rp6.dts.patch`
  source: armada
  notes: Armada switches Pocket 6 from ROCKNIX's Odin 2 fallback to audio firmware extracted from a Pocket 6 vendor image, and drives its haptics actuator as an LRA with the stock Android values (board-id 0x1001f overlay) instead of the inherited Odin 2 ERM config.
- `dts/qcs8550-retroidpocket-rpnova.dts.patch`
  source: armada
  reference: https://github.com/RetroidPocket/linux/blob/2209a42da1a891d0d140293f5831c50e4aa9cc61/arch/arm64/boot/dts/qcom/qcs8550-retroidpocket-rpnova.dts
  notes: Armada disables the inherited Pocket 6 PWM backlight and removes its panel reference so Nova uses its panel driver’s DSI backlight. Matches Retroid’s Nova panel wiring: L11B/L12B/L13B for vdd/vddio/vci, GPIO 70/143 fixed regulators for vdd18/vdd28, and rotation 0. Removes the inherited avdd supply and retains Armada DPU dithering and Nova's own ADSP firmware. The ROCKNIX Nova → RP6 → AYN common inheritance remains unchanged for other systems.
- `dts/qcs8550-ayn-thor.dts.patch`
  source: armada
  notes: Armada fixes the hall-sensor pinctrl, makes only the lid-open edge wake, corrects touch orientation, and enables DPU dithering on the top panel after copying `dts/qcs8550-ayn-thor.dts`.
- `dts/sm8650-ayaneo-common.dtsi.patch`
  source: armada
  notes: Armada keeps volume-up from waking the system, wires the upstream SY7758 driver, marks PCIe WAKE# active-low, idles the codec rails in LPM during s2idle, and keeps the RTC offset in an SDAM cell with the alarm enabled after copying `dts/sm8650-ayaneo-common.dtsi`.
- `dts/sm8650-ayaneo-ps2.dts.patch`
  source: armada
  notes: Selects the Pocket S2 sound-card mapping, normally-closed jack switches from rafalrojek's [PR #663](https://github.com/armada-os/armada/pull/663), and HPH PCM adapted from ovid-io's [PR #803](https://github.com/armada-os/armada/pull/803). The Android reference supplies Class-H master mask 3 with codec mask 1, interval 0x3f, PCM/PDM32 formatter enable, SSP period 6 and headphone port 9 packing 1. Headphone port packing is supported by the Android table and codec DP6 capture; master readback alone is not sufficient.
- `dts/sm8650-konkr-pf.dts.patch`
  source: armada
  notes: Armada selects the shared WSA2 channel mapping through a Pocket FIT-specific sound-card compatible and binds `konkr_sysbtn` to the controller MCU UART, and loads its own ADSP firmware.

- `patches/0505-arm64-emulate-unaligned-atomics.patch`
  source: https://github.com/bylaws/linux/commit/7ae989a43ae7e3cb8007ac21c28dacc24c9d8320
  upstream: unknown
  notes: Rebased patch context for Linux 7.2.3 and Armada's compat-input patch; the unaligned-atomic handler is unchanged.
- `patches/0505a-arm64-unaligned-atomics-cover-the-load128-store-exclusive.patch`
  source: armada
  upstream: local
- `patches/0557-ASoC-codecs-lpass-wsa-macro-switch-to-pm-clock-framework.patch`
  source: https://git.kernel.org/torvalds/c/cd054a6e272caa97ab808ef6f5588749a1429108
  upstream: https://patch.msgid.link/20260702-xo-sd-codec-v7-b4-v8-1-d39d0fdb7859@oss.qualcomm.com
- `patches/0558-ASoC-codecs-lpass-va-macro-switch-to-pm-clock-framework.patch`
  source: https://git.kernel.org/torvalds/c/eb667d0fbdd38d5a800b9e7aafc9a6c14530b9bf
  upstream: https://patch.msgid.link/20260702-xo-sd-codec-v7-b4-v8-2-d39d0fdb7859@oss.qualcomm.com
- `patches/0559-ASoC-codecs-lpass-wsa-macro-use-devm-clk-hw-register-for-mclk.patch`
  source: https://git.kernel.org/torvalds/c/541735571578b84987868c5662089f73bac36895
  upstream: https://patch.msgid.link/20260702-xo-sd-codec-v7-b4-v8-3-d39d0fdb7859@oss.qualcomm.com
- `patches/0560-ASoC-codecs-lpass-tx-macro-switch-to-pm-clock-framework.patch`
  source: https://git.kernel.org/torvalds/c/b9b23e72abef91ab4689f1467cefc2517042ab26
  upstream: https://patch.msgid.link/20260707-xo-sd-codec-tx-rx-v2-1-f61b4622f97f@oss.qualcomm.com
- `patches/0561-ASoC-codecs-lpass-rx-macro-switch-to-pm-clock-framework.patch`
  source: https://git.kernel.org/torvalds/c/b05482e7ce1b110f86b08a99768ac41e4c9e4dfa
  upstream: https://patch.msgid.link/20260707-xo-sd-codec-tx-rx-v2-2-f61b4622f97f@oss.qualcomm.com
- `patches/0562-ASoC-codecs-lpass-tx-rx-macro-check-clk-set-rate-return-value.patch`
  source: https://git.kernel.org/torvalds/c/b8ca90fafe6adc401601f91d1394ba76bacf67ed
  upstream: https://patch.msgid.link/20260707-xo-sd-codec-tx-rx-v2-3-f61b4622f97f@oss.qualcomm.com
- `patches/0563-ASoC-codecs-lpass-macro-force-runtime-suspend-across-system-sleep.patch`
  source: armada
  upstream: local
- `patches/0080-ASoC-codecs-lpass-tx-macro-track-every-active-decimator.patch`
  source: armada
  upstream: local
- `patches/0564-soundwire-qcom-force-runtime-suspend-across-system-sleep.patch`
  source: armada
  upstream: local
- `patches/0565-pinctrl-qcom-sm8650-lpass-lpi-force-runtime-suspend-across-system-sleep.patch`
  source: armada
  upstream: local

- `patches/1021-wifi-ath12k-fix-single-pdev-frequency-ranges.patch`
  source: https://lore.kernel.org/r/20260715065218.41232-1-gsh20040816@gmail.com
  upstream: https://lore.kernel.org/r/20260715065218.41232-1-gsh20040816@gmail.com
  notes: Backports Shenghan Gao's proposed single-pdev range fix to Linux 7.2.6. The upstream discussion identifies this as a local workaround pending a per-radio regulatory-state redesign; it is not a merged upstream architectural fix.
- `patches/1022-wifi-ath12k-split-WCN7860-scans-by-firmware-ranges.patch`
  source: armada
  upstream: local
  notes: Splits WCN7860 scans by firmware range, preserving one overall timeout and completion. Tested on KONKR Pocket FIT Elite.
- `patches/1023-wifi-ath12k-protect-TX-during-associated-range-scans.patch`
  source: armada
  upstream: local
  notes: Uses single-channel associated scans with TX draining and home-channel rest. Tested on KONKR Pocket FIT Elite.

- `patches/1303-serial-qcom-geni-allow-shorter-rx-dma-transfer.patch`
  source: armada
  upstream: local
  notes: Adds an optional qcom,rx-dma-len DT property to shorten GENI UART RX DMA transfers. The Duo gamepad MCU streams without idle gaps, so the default 2048-byte transfer delivered input in ~245 ms bursts.

- `patches/0624-drm-msm-a6xx-increase-gmu-fw-init-timeout.patch`
  source: https://github.com/RetroidPocket/linux/commit/ba970587a0e1203b6a0934b5b9174886b4c4d24c
  upstream: https://patchwork.freedesktop.org/patch/753014/

- `dts/sm7750-retroidpocket-duo.dts`
  source: armada
  upstream: local
  notes: Standalone Duo board description using the shared IL97680A driver for the bottom panel, with three supplies and normal orientation.

- `patches/1100-drm-msm-a6xx-fix-a730-hwcg.patch`
  source: https://git.kernel.org/torvalds/c/01bcc0398f43099acb407a6067481e635c3e1b84
  upstream: https://git.kernel.org/torvalds/c/01bcc0398f43099acb407a6067481e635c3e1b84

- `patches/1101-drm-msm-a6xx-rename-gbif-cx-config.patch`
  source: https://git.kernel.org/torvalds/c/352116dbc4fc61ae22eae748da36e46a3f45f65c
  upstream: https://git.kernel.org/torvalds/c/352116dbc4fc61ae22eae748da36e46a3f45f65c

- `patches/1102-drm-msm-a6xx-add-adreno-722.patch`
  source: https://git.kernel.org/torvalds/c/a25fd4227f59b9147ae6d23336878c28e5437a4d
  upstream: https://git.kernel.org/torvalds/c/a25fd4227f59b9147ae6d23336878c28e5437a4d

- `patches/1103-dt-bindings-arm-smmu-eliza-gpu.patch`
  source: https://git.kernel.org/torvalds/c/925f98235a729a87e632d6366fc749faac0463b4
  upstream: https://git.kernel.org/torvalds/c/925f98235a729a87e632d6366fc749faac0463b4

- `patches/1104-dt-bindings-display-msm-adreno-722.patch`
  source: https://git.kernel.org/torvalds/c/0b69e4f4ee325ee0b50396657fd19d4d7b0a6294
  upstream: https://git.kernel.org/torvalds/c/0b69e4f4ee325ee0b50396657fd19d4d7b0a6294

- `patches/1105-dt-bindings-clock-eliza-gpucc.patch`
  source: https://git.kernel.org/torvalds/c/26461dcf5de1a3645bf9bdb1558f12ea20df991f
  upstream: https://git.kernel.org/torvalds/c/26461dcf5de1a3645bf9bdb1558f12ea20df991f

- `patches/1106-clk-qcom-add-eliza-gpucc.patch`
  source: https://git.kernel.org/torvalds/c/4cfe35f2ef21c4b6281d8b73fdbabaa6a8aa1440
  upstream: https://git.kernel.org/torvalds/c/4cfe35f2ef21c4b6281d8b73fdbabaa6a8aa1440
  notes: Makefile context refreshed for Linux 7.2.6, which has no Eliza video clock entry; driver unchanged.

- `patches/1107-arm64-dts-qcom-eliza-gpu-clock.patch`
  source: https://lore.kernel.org/r/20260806-eliza-mm-cc-v9-v10-10-6ba52dd14343@oss.qualcomm.com
  upstream: https://lore.kernel.org/r/20260806-eliza-mm-cc-v9-v10-10-6ba52dd14343@oss.qualcomm.com
  notes: Extracted only the GPUCC header and node from the multimedia clock series; camera/video controllers omitted. GPU clock and power-domain definitions unchanged.

- `patches/1108-arm64-dts-qcom-eliza-gpu-smmu.patch`
  source: https://git.kernel.org/torvalds/c/0cb81794dea5b236122578bd49e3e6bfdc6adf87
  upstream: https://git.kernel.org/torvalds/c/0cb81794dea5b236122578bd49e3e6bfdc6adf87

- `patches/1109-arm64-dts-qcom-eliza-gpu.patch`
  source: https://git.kernel.org/torvalds/c/5cc169156d877a4aa947092dd3c9dbd784d62f93
  upstream: https://git.kernel.org/torvalds/c/5cc169156d877a4aa947092dd3c9dbd784d62f93

- `patches/1110-arm64-dts-qcom-eliza-gpu-cooling.patch`
  source: https://git.kernel.org/torvalds/c/c53d30b2814e0f0215cdafe9ccf691eace2949ff
  upstream: https://git.kernel.org/torvalds/c/c53d30b2814e0f0215cdafe9ccf691eace2949ff
  notes: Include context refreshed for Linux 7.2.6; GPU thermal trips and cooling maps unchanged.

- `patches/1111-drm-panel-vtdr6130-add-pocket-duo.patch`
  source: Armada implementation from the unit's Android panel properties.
  upstream: No.

- `patches/1114-remoteproc-qcom-add-eliza-wpss.patch`
  source: Armada; existing Linux Milos/SC7280 WPSS support and Qualcomm Kera downstream sources, checked against the Duo Android FDT.
  upstream: No.
  notes: Reuses the PAS driver with auto_boot=false. Adds the WPSS firmware processor support used by the WCN7750 ath12k backport.

- `patches/1140-wifi-ath12k-move-MSI-state-from-ath12k-pci-to-ath12k-base.patch`
  source: https://github.com/RetroidPocket/linux/commit/be7f234a62cd0a47ce043fa9329faaef509eb030
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support. Move the existing WCN7860 MSI reference as well.

- `patches/1141-wifi-ath12k-share-the-register-window-geometry-with-the-core.patch`
  source: https://github.com/RetroidPocket/linux/commit/d1ef16ccc3d1c67d590986e51f15d3cbb5797942
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support.

- `patches/1142-wifi-ath12k-let-the-MSI-CE-DP-IRQ-setup-serve-platform-devices.patch`
  source: https://github.com/RetroidPocket/linux/commit/f2c4631acf1e6a497cee3610d1bcddbe13d1a75c
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support.

- `patches/1143-wifi-ath12k-allow-receive-only-services-in-map-service-to-pipe.patch`
  source: https://github.com/RetroidPocket/linux/commit/7dae8198ef2133b30fadc1f2ac312031dab3d2ee
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support.

- `patches/1144-wifi-ath12k-keep-the-CE-interrupt-mask-balanced-across-restarts.patch`
  source: https://github.com/RetroidPocket/linux/commit/ca800f8cd0e2b19ffca0df6a5fdbeea312ddb479
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support.

- `patches/1145-wifi-ath12k-add-an-optional-cfg-static-window-hif-op.patch`
  source: https://github.com/RetroidPocket/linux/commit/bdbf8cc0bb5a31a32251f9cdc8718fba2c500373
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support.

- `patches/1146-wifi-ath12k-take-the-shadow-register-base-from-hw-params.patch`
  source: https://github.com/RetroidPocket/linux/commit/7d9b6f2688952f71b4125cdb2974054330823609
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support.

- `patches/1147-wifi-ath12k-support-targets-with-fixed-firmware-memory.patch`
  source: https://github.com/RetroidPocket/linux/commit/444bb9b352908ce84ab7425a1e747772bc7ec6da
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support.

- `patches/1148-wifi-ath12k-cap-the-shadow-register-configuration-at-38-entries.patch`
  source: https://github.com/RetroidPocket/linux/commit/364880382bfaa6ed1c96522dd9070dfd8ebc6d94
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support.

- `patches/1149-wifi-ath12k-add-the-QMI-device-info-request.patch`
  source: https://github.com/RetroidPocket/linux/commit/c8d5b4abbc9af8fa3e1d4fc8fd530bb3f6353677
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support.

- `patches/1150-wifi-ath12k-send-ddr-range-and-gpio-info-in-host-cap.patch`
  source: https://github.com/RetroidPocket/linux/commit/814e706988b98ca39714133980021b39ae3f7403
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support. Use the 7.2 host-capability layout without dynamic_mem.

- `patches/1151-wifi-ath12k-support-cold-boot-calibration.patch`
  source: https://github.com/RetroidPocket/linux/commit/2f10dd06904a0af0897bdaa00dcb2e17cffe6b0d
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support. Use 7.2 QMI constants and reuse Armada 0040 for QDSS download.

- `patches/1152-wifi-ath12k-track-the-firmware-generation-across-recovery.patch`
  source: https://github.com/RetroidPocket/linux/commit/f23d44355701c909ab63a3253644af114eb0427c
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support.

- `patches/1153-wifi-ath12k-add-ath12k-core-firmware-crashed.patch`
  source: https://github.com/RetroidPocket/linux/commit/ef330ed2a7cdbd5ae20ee89ec26f62dda1623822
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support.

- `patches/1154-wifi-ath12k-stop-touching-srngs-after-the-HAL-is-torn-down.patch`
  source: https://github.com/RetroidPocket/linux/commit/5c301a42fc1d833eca66ed8dc5d58a650b3bd66c
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support.

- `patches/1155-wifi-ath12k-tolerate-a-missing-hwmon-device-on-thermal-cleanup.patch`
  source: https://github.com/RetroidPocket/linux/commit/ecda60ed15f6d05dc2648bf28eb50e0bef800f73
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support.

- `patches/1156-wifi-ath12k-guard-the-link-peer-table-against-concurrent-teardown.patch`
  source: https://github.com/RetroidPocket/linux/commit/1877d7230554c26f9558b215d0349253df378f5e
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support.

- `patches/1157-wifi-ath12k-add-the-WCN7750-copy-engine-configuration.patch`
  source: https://github.com/RetroidPocket/linux/commit/c560f20177338be2a376b24e927574e1e0e207f2
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support.

- `patches/1158-wifi-ath12k-add-WCN7750-hw1-0.patch`
  source: https://github.com/RetroidPocket/linux/commit/a432a615be0498793cde6a7524a2746e547c87e6
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support. Omit supports_cong_ctrl_max_msdus, absent in 7.2.

- `patches/1159-wifi-ath12k-ahb-add-the-WCN7750-hybrid-bus-transport.patch`
  source: https://github.com/RetroidPocket/linux/commit/69b93ff4671eb07c1e81015ed3a0ccc106486a02
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Backport to Armada Linux 7.2.6; retain existing WCN7860 and QDSS support. Keep the 7.2 IPQ probe and UserPD paths; add only the WCN7750 branch.

- `patches/1160-wifi-ath12k-unwind-WCN7750-probe-failures.patch`
  source: Armada; review of the RetroidPocket hybrid-bus transport.
  upstream: No.
  notes: Propagates PDC errors and unmaps MSI on probe failure.

- `patches/1161-dt-bindings-net-wireless-describe-WCN7750-resources.patch`
  source: Armada; RetroidPocket WCN7750 driver and board resources.
  upstream: No.
  notes: Documents the hybrid-bus resources in place of the experimental supplies-only binding.

- `patches/1162-scsi-ufs-ufs-qcom-add-Eliza-match-data.patch`
  source: https://github.com/RetroidPocket/linux/commit/1213eb175774de1f4ba6577a4329bba58729840d
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Reuses SM8550 match data for Eliza's lack of PHY retention and legacy-doorbell capability quirk. Refreshed context for Armada's SM8750 entry; driver change otherwise unchanged.

- `patches/1163-dt-bindings-ufs-allow-Eliza-legacy-doorbell-mode.patch`
  source: Armada; RetroidPocket Duo UFS configuration.
  upstream: No.
  notes: Allows the Eliza board to omit MCQ resources while preserving Nord's requirement.

- `patches/1164-arm64-dts-qcom-eliza-add-i2c6.patch`
  source: https://github.com/RetroidPocket/linux/commit/aaa9c19f21f7c651f4a5dd270170f5862b6cabc0
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.

- `patches/1166-Bluetooth-qca-add-WCN7750-support.patch`
  source: https://github.com/RetroidPocket/linux/commit/762bc03f0c4863bad8b935e844cc570517314784
  upstream: RetroidPocket downstream tree, not confirmed merged in mainline.
  notes: Context refreshed for Armada's WCN7860 support, which is retained. Uses ORN firmware from the existing atheros-firmware package.

- `patches/1167-drm-msm-dpu-enable-eliza-inline-rotation.patch`
  source: armada
  upstream: local
  notes: Adds inline rotation for Eliza

- `patches/1168-drm-msm-dpu-enable-eliza-lutdma.patch`
  source: armada
  upstream: local
  notes: Enables LUTDMA for Eliza, matching downstream kera (https://git.codelinaro.org/clo/la/platform/vendor/opensource/display-devicetree/-/blob/1c5de2a5c1743f0693d3b0ca5ff7ca158627fc6b/display/kera-sde-common.dtsi). Needs `0068`.

- `patches/1169-arm64-dts-qcom-eliza-dpu-lutdma.patch`
  source: armada
  upstream: local
  notes: Maps the Eliza DPU LUTDMA registers. Needs `0069`.

- `patches/1170-arm64-dts-qcom-eliza-add-adsp-gpr.patch`
  source: https://github.com/RetroidPocket/linux/commit/23da74833df803c5e8bea71feb878173764ef121
  upstream: https://lore.kernel.org/r/20260724-dts-qcom-eliza-add-gpr-v3-1-2595beb0cdec@oss.qualcomm.com
  notes: Context refreshed for Armada's Eliza DTS.

- `patches/1171-arm64-dts-qcom-eliza-add-lpass.patch`
  source: https://github.com/RetroidPocket/linux/commit/b9f1f97846bcb1989bb52b6cbd1205ecc22c8e43
  upstream: https://lore.kernel.org/r/20260731084032.3106477-2-ravi.hothi@oss.qualcomm.com
  notes: Context refreshed for Armada's Eliza DTS.

- `patches/1172-pinctrl-qcom-add-eliza-lpass-lpi.patch`
  source: https://github.com/RetroidPocket/linux/commit/82c3edf8701154e2768973ebd4c0d2f3bd29621e
  upstream: https://patch.msgid.link/20260715132150.1322663-3-ravi.hothi@oss.qualcomm.com

- `patches/1173-ASoC-qcom-q6apm-add-mi2s-clocks.patch`
  source: https://github.com/RetroidPocket/linux/commit/cc8495c1d45ab113a638b5df6c2e0bfa150a7376
  upstream: https://patch.msgid.link/20260724182446.1484894-3-mohammad.rafi.shaik@oss.qualcomm.com
  notes: Retains Armada's graph suspend/restore state and prepare-time RX start.

- `patches/1174-ASoC-qcom-enable-quaternary-jack.patch`
  source: https://github.com/RetroidPocket/linux/commit/19e15b7d6f340dd636e54eb5b39a2991453d8ad5
  upstream: unknown
  notes: Context refreshed; Armada lacks the newer LPI_MI2S_RX_0 case.

- `patches/1175-ASoC-qcom-configure-eliza-mi2s-clocks.patch`
  source: https://github.com/RetroidPocket/linux/commit/592a27a5a0376a80db2271c6e97c4f7643b279d8
  upstream: unknown
  notes: Adapts the reference hw_params clock/codec setup to Armada's existing machine driver, scoped to Eliza. Configures both speaker codecs; retains the existing 48 kHz stereo S16_LE backend format.

- `patches/1176-ASoC-es8326-enable-codec-supplies.patch`
  source: https://github.com/RetroidPocket/linux/commit/f8dfc9104b7c24de07fd839c1cc6468640f2e2a1
  upstream: unknown
  notes: Uses managed bulk regulator enable, propagating probe deferral and unwinding on probe failure/unbind.

- `patches/1177-dt-bindings-describe-eliza-audio-resources.patch`
  source: armada
  upstream: local

- `patches/1178-ASoC-qcom-q6prm-add-missing-mclk-ids.patch`
  source: https://github.com/RetroidPocket/linux/commit/a2fdf929fbb491f3bf4d3cadb5a7cc7c90182c0f
  upstream: https://patch.msgid.link/20260731162626.1588561-3-srinivas.kandagatla@oss.qualcomm.com

- `patches/1179-ASoC-qcom-fix-duo-speaker-slot-width.patch`
  source: armada; register definitions from https://github.com/awinic-driver/aw883xx/blob/main/aw883xx_pid_2066_reg.h
  upstream: local

- `patches/1180-ASoC-qcom-q6apm-allow-s32-playback.patch`
  source: armada
  upstream: local

- `patches/1181-cpufreq-dt-platdev-blocklist-eliza.patch`
  source: Armada
  upstream: local

- `patches/1182-arm64-dts-qcom-eliza-add-cpu-l3-scaling.patch`
  source: Armada
  upstream: local

- `patches/0515a-input-rsinput-accept-large-uart-batches.patch`
  source: armada
  upstream: local
  notes: Feed large UART receive batches through the existing frame reassembly buffer without dropping complete frames.

- `patches/1302-input-rsinput-support-retroid-pocket-duo.patch`
  source: armada
  upstream: local
  notes: Add configurable ADC references and share reset and supply sequencing between probe and resume; existing board defaults are retained.
