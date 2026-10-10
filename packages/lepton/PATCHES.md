# Patches

`android-*.patch` are the source of `prebuilt/`: they apply to Valve's Android
tree for the tag in BASE.env, 0001 to its `android_hardware_waydroid`, 0002 to
`hardware/interfaces` and 0003 to `packages/apps/DocumentsUI`
(`build-android.sh`). `rro/` builds there too.

- `patches/android-0001-hwcomposer-add-an-external-display.patch`
  source: armada
- `patches/android-0002-hwc2on1adapter-set-displays-the-client-has-not-revalidated.patch`
  source: armada
- `patches/android-0003-documentsui-drop-the-cross-profile-attribute.patch`
  source: armada
