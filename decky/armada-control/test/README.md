# Frontend tests

Run `npm test` from `decky/armada-control`. The suite uses Node's test runner and the existing TypeScript dependency. Locale validation also runs through this command.

## Coverage ownership

| Area | Owning tests |
| --- | --- |
| Steam discovery, routing and default migrations | `compatManager`, `compatTools`, `protonPolicy`, `steamCompat` |
| Game overrides, environment variables and Advanced drafts | `gameSettings`, `steamSettings`, `gameSettingsQueue` |
| Save ordering, rollback, stale responses and close/reopen persistence | `configMutations`, `debouncedSave`, `debouncedApply` |
| Initial loading, retries, runtime selection and parallel tab warming | `bootstrapCompatPolicy`, `backendStartup`, `backendState`, `configSectionLoading`, `contentLoading`, `contentSelection`, `tabData` |
| Fan/performance drafts and graph input | `profileWorkflows`, `fanCurveGraph` |
| Display calibration cancellation and saving | `panelCalibration` |
| Controller navigation and modal focus restoration | `tabNavigationView`, `modalFocus`, `modalRoot` |
| Scroll bounds, responsive loading and interrupted animation | `scrolling`, `panelHeight`, `tabCarouselMotion` |
| Native download notifications and pure configuration utilities | `lowPowerDownloads`, `envPresets`, `freq` |

Test plugin-owned behavior at its owning layer. Shared persistence contracts should not be repeated for every panel that calls them. Keep editor workflows focused on target isolation, persistence and failure handling.

The module loader only supplies explicit imports and a JSX element factory for fixtures. Fixtures model the small part of React or Steam used by each scenario. They are not browser or Steam emulators.

Do not add tests just to assert native Decky prop forwarding, CSS classes, markup order or exact visual dimensions. Such assertions cannot establish correct native focus, controller input or layout. Verify those in live Steam QAM, including long translations, touch input and unsupported hardware. Add a focused regression when a plugin-owned decision can be reproduced independently.
