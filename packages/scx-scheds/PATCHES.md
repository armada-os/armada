# Patches

Patches applied to the SteamOS scx tree from BASE.env. Each entry's `source` is
an upstream URL pinned to a commit, or `armada` if it's original; a URL source
with no `notes` is verbatim. `notes` mean the file was modified.

- `patches/0001-Cargo-bump-libbpf-sys-to-1.7.1.patch`
  source: https://github.com/sched-ext/scx/commit/83e64fe4796b7dcba395226fc5f0458574b13beb
  notes: Only the libbpf-sys bump; the upstream commit's other lockfile updates are dropped.
