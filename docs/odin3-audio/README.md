# Odin 3 stereo and virtual surround audio

This integration gives the AYN Odin 3 two user-facing speaker outputs:

- **Stereo** downmixes multichannel content to the built-in stereo speakers.
- **Virtual Surround Sound** applies an HRIR convolution to 7.1 content before
  sending the result to the built-in stereo speakers.

The physical speaker sink remains an internal transport. Steam sees the two
profiles above instead of exposing **Built-In Audio** as a third selectable
output.

## Device scope

The setup is restricted to an exact device-policy match for the AYN Odin 3 on
SM8750. A non-matching device activates no audio configuration and removes only
this package's exact managed links if they survived an earlier image. Original
files displaced by those links are restored. Internal Odin 3 audio values and
policy must not be applied to other handhelds or external audio devices.

## Defaults and persistence

On a new account with no saved audio state, the first session:

1. Sets both public sinks to 100 percent.
2. Selects **Stereo** as the default.
3. Records that initialization has completed.

That initialization is not repeated. If the user later selects **Virtual
Surround Sound**, the normal PipeWire and WirePlumber state preserves that
choice across sessions and reboots. Selecting **Stereo** makes it the persistent
choice again. An update must not replace an existing user selection.

The physical speaker route is held at unity gain. User volume is applied to the
selected public sink, so a restored hardware-route volume cannot silently make
both profiles quieter or louder.

Steam keeps a separate output-device override inside its SharedJSContext. On
each Steam launch, `launch-steam` nonblockingly restarts
`armada-odin3-audio-steam-restore.service`. If and only if the exact Odin 3 /
SM8750 device policy matches, the bounded helper waits for Steam CEF and
synchronizes PipeWire's current default output in Steam. It selects only the
`SharedJSContext` target served for `steamloopback.host` through a loopback
WebSocket, verifies Steam exposes one exact matching output, applies the
override, and reads it back. A missing
target, ambiguous device, timeout, or protocol error leaves the system audio
default unchanged and is reported in the user journal. For **Stereo**,
Bluetooth, and wired headphones, the helper selects the exact current
PipeWire sink in Steam and verifies both Steam's override and active output.
It first matches the exact sink name; if Steam exposes a different friendly
name, it derives the live Steam device ID from the independently checked
**Stereo** and **Virtual Surround Sound** PipeWire/Steam ID offset. Device IDs
are rediscovered on every run and are never persisted.

## External audio

Bluetooth outputs and the Odin 3's 3.5 mm headphone output are independent of
both built-in-speaker HRIR graphs. They remain ordinary public PipeWire sinks,
so Steam lists them alongside **Stereo** and **Virtual Surround Sound** while
the raw **Built-In Audio** speaker transport remains hidden.

`armada-odin3-audio-hotplug.service` watches the live card and sink topology.
On its first start after an update, it preserves an existing bounded
**Stereo** or **Virtual Surround Sound** selection from WirePlumber's
`default-nodes` state before observing the newly created graph.
It also detects the exact legacy 2-channel `Stereo` volume pattern in which
FL/FR retain the user's equal volume but the six newly introduced 7.1 channels
are zero. Once, it copies that existing raw front volume to all eight channels,
verifies the result, and records a versioned migration marker. Other volume
layouts are left unchanged.
Connecting wired headphones switches the exact Odin card to its headphone
profile; connecting a positively identified BlueZ output selects that output.
The newest newly connected external output becomes the PipeWire default,
already-playing streams are moved to it, and Steam is resynchronized. If
several external outputs are connected, removing the active one selects the
most recently created remaining output. Removing the final external output
restores the user's saved **Stereo** or **Virtual Surround Sound** choice.

While running, the hotplug router atomically records an active **Stereo** or
**Virtual Surround Sound** sink in per-user runtime state and removes that
record for headphones, Bluetooth, or any other output. Before real suspend,
the system sleep hook snapshots only that confirmed active internal sink. On
resume, the hook creates a one-shot trigger. `armada-odin3-audio-resume.path`
starts a dedicated service whose validated helper atomically consumes that
trigger into the retained pending-request path before restarting the hotplug
router. Clearing the pending request therefore cannot retrigger the resume
service.

The restarted router handles the pending resume choice before ordinary
preference capture. It restores the exact sink, moves existing streams, updates
the durable return preference, clears the pending marker, and then requests the
bounded Steam synchronization. If **Virtual Surround Sound** is still being
created, **Stereo** can provide temporary audio without replacing the saved
surround preference; a later sink event completes the requested restore. A
second sleep during that fallback retains the still-pending surround request.

The router never applies Odin speaker gain, HRIR convolution, hidden-transport
policy, or the graph-local Stereo downmix to an external sink. Unknown USB,
HDMI, and unrelated outputs do not trigger this Bluetooth/headphone policy.

## Signal level

Both profiles use a base gain of `0.295248`. This is 12 percent of the
logarithmic interval from the earlier `0.25` setting (`-12.0412 dB`) toward
unity (`0 dB`):

```text
-12.0412 dB + (0.12 * 12.0412 dB) = -10.5963 dB
10 ^ (-10.5963 / 20) = 0.295248
```

Virtual-surround channel weights retain the established relative balance:

| Input | Gain |
|---|---:|
| Front and LFE | `0.295248` |
| Side | `0.265723` |
| Rear | `0.236199` |
| Center | `0.354298` |

The final left and right samples are clamped to `+/-0.8912509381`, which is a
hard `-1 dBFS` sample ceiling. This is an emergency peak limit, not a loudness
normalizer or a guarantee that all upstream combinations are free of audible
compression.

The Stereo profile accepts 7.1 input and performs its downmix inside its own
filter graph. Front channels use unity coefficients, center and surround
channels use `0.707106781`, and LFE uses `0.353553391`. The resulting left and
right signals then use the existing front HRIR paths. This retains every input
channel without applying speaker-specific downmix policy to Bluetooth,
headphone, or other external sinks.

## Installation lifecycle

The image contains immutable profile templates under
`/usr/share/armada/audio/odin3`. Before the display manager starts,
`armada-odin3-audio-setup.service` verifies the device and installs only the six
managed configuration links in the `armada` user's PipeWire and WirePlumber
directories. Both built-in-speaker graphs reference the same immutable
`/usr/share/armada/audio/odin3/hrir/vss_speaker.wav`. Setup verifies its exact
SHA-256 before changing any user configuration and fails closed if the file is
missing or differs. There is no fallback HRIR and no per-user replacement.

If a managed path already contains a regular file, setup moves it to an
adjacent file ending in `.armada-odin3-audio.backup` before creating the link.
Setup refuses to replace foreign symlinks, special files, unsafe parent paths,
or an existing backup.

The user service `armada-odin3-audio-default.service` performs the one-time
clean-account initialization after PipeWire, PipeWire Pulse, and WirePlumber
are available. Existing audio state suppresses that initialization.

`armada-odin3-audio-steam-restore.service` is launch-triggered and intentionally
is not enabled. Its bounded one-shot failure cannot prevent Steam from starting.

`armada-odin3-audio-hotplug.service` is globally enabled for user sessions but
exits without changing audio unless the immutable device policy exactly matches
an AYN Odin 3 on SM8750.

## Rollback

On an Odin 3, restore displaced configuration with:

```text
sudo /usr/libexec/armada/odin3-audio-setup --restore
systemctl --user restart pipewire pipewire-pulse wireplumber
```

The restore operation removes only links owned by this integration and puts
the adjacent backups back in place. It refuses to remove a foreign link or
overwrite a current user file. Reboot instead of restarting the user services
if the Qualcomm audio path does not return cleanly.

## Limitations

- Virtual surround is a perceptual widening preset for the Odin 3 built-in
  speakers; it does not create discrete physical surround channels. HRIRs
  assume isolated ears, while speakers introduce acoustic crosstalk and the
  listener's own head response, so this is not geometrically accurate binaural
  rendering.
- Perceived localization varies by listener and by the HRIR dataset.
- The hard sample ceiling protects the final graph output but is not a
  true-peak limiter.
- The virtual sinks, hidden transport, unity-route enforcement, downmix, and
  gain tuning apply only to the built-in Odin 3 speakers. Bluetooth, headphone,
  and other external sinks retain their own PipeWire routing and mixing policy.
- The bundled HRIR is checksum-pinned. Replacing it requires updating the
  expected checksum and audio validation tests.

## Tests

Run the repository checks from the repository root:

```text
bash tests/odin3-audio-test.sh
```

Run the opt-in, read-only live-session checks on an Odin 3:

```text
ODIN3_AUDIO_DEVICE_TEST=1 bash tests/odin3-audio-device-test.sh
```

The repository test validates the device gate, managed installation and
rollback, first-run default policy, Steam rehydration contract, graph structure,
channel routing, gain ratios, final sample clamps, external-output
classification, connection ordering, stream migration, and saved-speaker
restoration. The device check verifies the two speaker-profile sinks, the
internal hardware route, and an expected persistent default selection.

Physical release validation still requires one Bluetooth output and one 3.5 mm
headset or speaker. For each, verify that connection adds the device to Steam's
audio picker and selects it, audio bypasses both HRIR profiles, and disconnection
restores the prior speaker profile.

For an audible built-in-speaker channel test on PipeWire 1.6.8, use ALSA's
canonical 7.1 order:

```text
speaker-test -D pipewire -r 48000 -c 8 \
  -m FL,FR,RL,RR,FC,LFE,SL,SR -t wav -l 1
```

Do not reorder the `-m` list to match the graph declaration. PipeWire 1.6.8's
ALSA plugin publishes the canonical order even when another map is requested,
which makes `speaker-test` place the center, LFE, and rear samples in the wrong
semantic ports. The ALSA test sound pack has no spoken LFE sample and uses its
“Rear Center” recording for the LFE slot; the stream position is still LFE.
