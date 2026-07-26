# Odin 3 HDR and AutoHDR integration

This integration exposes the AYN Odin 3 internal OLED HDR path to Gamescope and
Steam Game Mode. It also adds an optional compositor AutoHDR path for SDR games.
The feature is scoped to the qualified internal Odin 3 display and fails closed
on unknown devices and outputs.

## User experience

- Steam Display settings provide the HDR switch and the standard
  SDR-content-brightness control.
- AutoHDR appears in Steam Display settings only while HDR output is verified.
- The Performance quick-access menu provides a contextual AutoHDR switch below
  Allow Tearing.
- The quick-access switch follows Steam's per-game profile scope. A game can
  override the global AutoHDR preference without changing other games.
- Steam's HDR badge reflects native HDR content or AutoHDR that Gamescope
  confirms it actually rendered.
- AutoHDR uses the Quality policy only. Efficient processing remains an
  internal compositor fallback and is not exposed as a user-selectable mode.

## Safety model

HDR capability is not enabled by the device profile alone. At session startup,
`hdr-session-finalize` verifies the exact Odin 3 identity, internal DSI output,
panel policy, EDID policy digest, and required immutable image artifacts.
Failure leaves `ARMADA_HDR_CAPABLE=0` and preserves the normal SDR session.

AutoHDR can report effective conversion only when all of the following are
true:

1. A qualified HDR output.
2. Verified active HDR output from Gamescope.
3. The expected Gamescope inverse-tone-mapping runtime protocol.
4. An SDR game surface eligible for compositor conversion.

Native HDR surfaces bypass AutoHDR in Gamescope. If shader creation or the
Quality path fails, Gamescope may use its internal Efficient fallback. If no
AutoHDR pipeline renders, the content stays SDR and the HDR badge does not claim
AutoHDR activity.

## Display profile

The current internal-panel profile uses 203 nits for SDR reference white and
650 nits for target peak. These values are inherited and provisional. They have
not been established by a colorimeter measurement of the retail panel.
Internal-panel values must not be applied to external displays.

## Paired Gamescope changes

The userspace integration expects the matching Armada Gamescope package
patches. That compositor work provides:

- native HDR surface detection and bypass
- SDR-to-HDR inverse tone mapping
- Quality scene analysis and temporal adaptation
- output-space feedback for native HDR and rendered AutoHDR
- runtime properties used by the Steam and quick-access controls
- safe fallback when an AutoHDR pipeline cannot be created

The kernel display dither patch is packaged separately from this userspace
change. It is limited to the Odin 3 8-bit DPU output path and does not enable an
experimental 10-bit transport.

## Validation

From `decky/armada-control`:

```text
npm ci
npm test
npm run typecheck
npm run build
python -m unittest test.test_system
```

From the repository root:

```text
python tests/odin3-hdr-production-test.py
bash tests/gamescope-capability-gate-test.sh
```

Device acceptance still requires a matching AArch64 image and an Odin 3 test of
native HDR, SDR with AutoHDR disabled, SDR with AutoHDR enabled, per-game
overrides, the contextual badge, suspend and resume, and rollback.
