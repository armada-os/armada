# Patches

Patches applied on top of Terra's libssc spec at TERRA.env. Each entry's `source`
is an upstream URL pinned to a commit, or `armada` if it is original; a URL source
with no `notes` is verbatim. `notes` mean the file was modified.

- `patches/0002-sensor-let-callers-pick-the-sample-rate.patch`
  source: armada
  notes: Opt-in `LIBSSC_SAMPLE_RATE=<Hz>`. Without it libssc enables continuous sensors at their first advertised rate (12.5 Hz on the Odin 2 family's ICM-426xx). Numbered after Terra's own 0001 so both apply.
