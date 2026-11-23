# steam

The native ARM64 Steam client, built and launched the way the Steam Frame image
does it. One package, two outputs:

- **The tree.** `unpack.py` unzips every package of a pinned `steamdeck_stable`
  manifest in order and writes `package/beta`, as Valve's own tarball is made
  (steamrt3c included). Nothing is run, so it builds on any host. The image build
  stages it into `/var/home/armada`, which also makes it the copy that repairs
  restore from, through the booted OSTree commit. There is no second copy in `/usr`.
  `.bootstrap-manifest` lists every file with its size and CRC for `steam-verify`.
- **The RPM.** Frame's launcher layout (`bin_steam.sh`, the `steam` symlink,
  `steam.desktop`, `/usr/bin/steam`) plus Armada's scripts.

`/usr/bin/steam` runs `armada-steam-run`: it makes sure the client is installed,
refreshes the `~/.steam` links, sets the environment from Frame's `RUNSTEAM.sh`,
and runs the unmodified `bin_steam.sh`. After five failed starts in a row it runs
`steam-install --repair`.

`steam-install` installs only when the client is missing or `.install-in-progress`
was left behind. `--repair` re-extracts over the existing root; `--reset` first
deletes everything except `userdata`, `compatibilitytools.d`, `config`,
`controller_base`, `steamapps` and `music`, which also signs the user out. Both
check the result with `steam-verify` (sizes only; `--crc` reads every file).
