# Patches

`launcher-*.patch` apply at first launch to a per-user copy of the launcher
scripts Steam installs (app 3029110). `android-*.patch` are the source of
`prebuilt/`: they apply to Valve's Android tree for the tag in BASE.env, 0001
to its `android_hardware_waydroid`, 0002 to `hardware/interfaces` and 0003 to
`packages/apps/DocumentsUI` (`build-android.sh`). `rro/` builds there too.

- `patches/launcher-0001-pass-steam-input-gamepads-to-android.patch`
  source: armada
- `patches/launcher-0002-second-display.patch`
  source: armada
- `patches/launcher-0003-share-the-home-folder-and-sd-cards.patch`
  source: armada
- `patches/launcher-0004-forward-only-the-debug-ports-on-loopback.patch`
  source: armada
- `patches/launcher-0005-phone-density-for-the-android-ui.patch`
  source: armada
- `patches/launcher-0006-keep-the-baked-app-after-an-early-exit.patch`
  source: armada
- `patches/android-0001-hwcomposer-add-an-external-display.patch`
  source: armada
- `patches/android-0002-hwc2on1adapter-set-displays-the-client-has-not-revalidated.patch`
  source: armada
- `patches/android-0003-documentsui-drop-the-cross-profile-attribute.patch`
  source: armada
