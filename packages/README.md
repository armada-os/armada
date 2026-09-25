# packages

Upstream-derived packages for Armada. Each top-level directory is one
component: a pinned upstream (`BASE.env`) + `patches/` + a `build.sh`.
`PATCHES.md` records where each patch came from.

## How a package builds

`build.sh` runs **inside** the builder container, not on the host. It sees:

| path    | contents                                                    |
| ------- | ----------------------------------------------------------- |
| `/work` | the package directory, cwd, artifacts go to `./out`          |
| `/src`  | this directory: `toolchain.env`, `TERRA.env`, sibling packages |

`Containerfile` turns each one into a pair of stages: `pkg-<name>`, which runs
`build.sh` as a `RUN` step, and `out-<name>`, a scratch stage holding just the
artifacts in the layout the image build bind-mounts at `/packages/<name>`.
Running the build as a step is what lets it cache as a layer, so an unchanged
package is not rebuilt.

## Building one

From the repository root:

```bash
just package gamescope
```

That builds the stage and tags it `localhost/armada/pkg/gamescope:<hash>`,
where the hash comes from `package-hash.sh`, the same tag CI publishes under.
`just build` prefers a locally built package and falls back to the published
image for every other one, so you only ever build what you are changing. `just
packages-status` shows which is which.

To iterate inside the builder instead, a shell-level edit/retry loop without
going through the layer cache:

```bash
./build-local.sh gamescope
```

It wraps `build.sh` in the same `podman run` the stages replaced, with the same
`/work` and `/src`, and leaves output in `gamescope/out/`.

## CI

`.github/workflows/packages.yml` resolves each package's content hash first and
builds only the ones with no published image, one per job so they stay parallel
across runners. Most commits change no package, so the matrix is usually empty.
Each build publishes `ghcr.io/<owner>/armada/pkg/<name>:<hash>`, which the image
build resolves by the same hash. Layer cache lives in a per-package GHCR repo
under `armada/buildcache/`, so one package's cache can be expired or purged
without disturbing the others.

Most packages build natively on `ubuntu-24.04-arm`. `mesa-android`,
`guestos-android` and `mesa-x86` build on `ubuntu-24.04`: they cross-compile
Android arm64 and x86 targets from an x86_64 host, and emulating that would be
far too slow. Only the runner differs, but the stages are built the same way.
