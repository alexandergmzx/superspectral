# Environment lock — what exactly is installed

**Status: template — to be filled in roadmap phase E1** (the first `tools/env-lock.sh` run after the gate build). Until then every field inside the markers reads `TBD`.

[`../../.envrc`](../../.envrc) pins the ESP-IDF *path* (`~/esp/idf/v6.0.2`, `~/esp/tools/v6.0.2`). It does not pin the *contents*: the commit the tag resolved to, which toolchain build IDs `install.sh` downloaded, which Python the venv was built on, which container digest CI used. This file does (critic B4). It is the companion of `firmware/twatch-s3/dependencies.lock` (which pins registry components) and of the digest-pinned container in [`../../.github/workflows/ci.yml`](../../.github/workflows/ci.yml).

Together those three artefacts are the reproducibility claim of [ADR 0001](../adr/0001-toolchain-esp-idf-v6-pinned-environment.md): `CONFIG_APP_REPRODUCIBLE_BUILD=y` + committed `dependencies.lock` + digest-pinned image + this inventory. Espressif is explicit that the reproducible-build option does **not** normalise IDF, CMake, Ninja or compiler versions — the Docker image and this file are how those are frozen (bibliography [11](../bibliography/11-esp-idf-platform-and-toolchain.md), section G).

## How to regenerate

```bash
cd ~/Development/Spectral          # direnv activates v6.0.2
tools/env-lock.sh                  # rewrites the block between the markers below
tools/env-lock.sh --check          # CI: exit 1 if a machine-invariant row is stale
git diff -- docs/devenv/env.lock.md
```

`--check` compares only the **machine-invariant rows** — IDF tag, IDF commit SHA, submodule sync count, esptool / esp-coredump / idf-component-manager / esp-idf-kconfig / esp-idf-size versions, the CI container digest and the `dependencies.lock` sha256. The remaining rows (paths, distro, kernel, glibc, cmake/ninja/ccache, udev symlink, leaked variables, generation date) are informational: they legitimately differ between this laptop and the digest-pinned container, so CI must not fail on them. A reviewer reads them; the script does not compare them.

Regenerate (and commit the diff in the same commit) whenever any of these change: the IDF tag or its submodules, `IDF_TOOLS_PATH` contents (`install.sh` re-run, `idf_tools.py install qemu-xtensa`), the Python interpreter, the container digest, `dependencies.lock`, or the host distro. The [upgrade procedure](upgrade-procedure.md) step 6 requires a fresh block.

## What a reviewer checks in the block

| Field | Must be | Why |
|---|---|---|
| ESP-IDF tag | `v6.0.2` | the pin in `.envrc` and ADR 0001 |
| ESP-IDF commit SHA | the SHA `git rev-parse HEAD` gave at clone time; identical on every machine | a tag can be moved; a SHA cannot |
| Submodules out of sync | `0` | stale submodules are the first cause of "IDF suddenly will not build after a tag change" ([pitfalls](pitfalls.md) A11) |
| Python base (`pyvenv.cfg home`) | `/usr/bin` | `/usr/local/bin/python3` is a root-owned symlink next to a disabled hand-built interpreter on this host ([pitfalls](pitfalls.md) A6) |
| Leaked env vars | `none` | ROS 2 `PYTHONPATH`/`CMAKE_PREFIX_PATH`/`LD_LIBRARY_PATH` and the EIM `IDF_COMPONENT_LOCAL_STORAGE_URL` mirror must never reach a build ([pitfalls](pitfalls.md) A1, A2, B8) |
| glibc | ≥ 2.31 | prebuilt QEMU binaries since the 2025-02 release require it ([pitfalls](pitfalls.md) G8) |
| esptool | 5.x (`>=5.3.0.dev0,<6` per the upstream v6.0 constraints file) | hyphenated command names in every script and runbook |
| esp-idf-kconfig | 3.x (`>=3.2.0,<4.0.0`) | matches the pre-commit hook pin |
| idf-component-manager | 3.x (`~=3.0`) | lock-file format; CM 3 is IDF ≥ 6.0 only |
| CI container | `espressif/idf:v6.0.2@sha256:…` (index digest) | `latest` and `release-v6.0` are rebuilt continuously; even `v6.0.2` is a repointable tag ([pitfalls](pitfalls.md) G10) |
| `dependencies.lock` sha256 | matches the committed lock | the block and the lock change together |

Constraint file to cite for the Python pins: <https://dl.espressif.com/dl/esp-idf/espidf.constraints.v6.0.txt> — **never a host copy**; this host carries two files of that name that disagree (a 2025 one pinning esptool 4.9 sits in the old tools root; [pitfalls](pitfalls.md) A21).

## Generated block

<!-- env-lock:begin -->
_Not yet generated — run `tools/env-lock.sh` from the activated v6.0.2 shell (phase E1)._

| Field | Value |
|---|---|
| ESP-IDF tag | TBD |
| ESP-IDF commit SHA | TBD |
| ESP-IDF submodules out of sync | TBD |
| `idf.py --version` | TBD |
| `IDF_PATH` | TBD |
| `IDF_TOOLS_PATH` | TBD |
| Python (venv interpreter) | TBD |
| Python base (`pyvenv.cfg home`) | TBD |
| Host distro | TBD |
| Kernel | TBD |
| glibc | TBD |
| cmake | TBD |
| ninja | TBD |
| ccache | TBD |
| git | TBD |
| direnv | TBD |
| xtensa-esp32s3-elf-gcc | TBD |
| esp-clang (installed dirs) | TBD |
| openocd-esp32 | TBD |
| qemu-xtensa (installed dirs) | TBD |
| esptool | TBD |
| esp-coredump | TBD |
| idf-component-manager | TBD |
| esp-idf-kconfig | TBD |
| esp-idf-size | TBD |
| idf-build-apps | TBD |
| pytest-embedded | TBD |
| esp-idf-sbom | TBD |
| CI container (digest-pinned) | TBD |
| `dependencies.lock` sha256 | TBD |
| `/dev/ttyTWATCH` | TBD |
| Leaked env vars (must be none) | TBD |

`idf_tools.py check` (what is actually installed):

```text
TBD
```

`idf_tools.py list` (what `tools/tools.json` in the pinned tree recommends):

```text
TBD
```
<!-- env-lock:end -->

## Provenance

Expected values on 2026-08-20 (from the research session, to be confirmed by the first run): ESP-IDF v6.0.2 released 2026-06-29; Linux Mint 22.3 (Ubuntu 24.04 base), Python 3.12.3 at `/usr/bin/python3.12`; esp-clang `esp-20.1.1_20250829`; OpenOCD `v0.12.0-esp32-20260304`; QEMU `esp-develop-9.2.2-20260417` (the copy currently on disk, `esp_develop_9.0.0_20240606`, is stale and must be reinstalled — critic A7); container index digest `sha256:0d8c9773d48a327233f9c1d7c654ff0bcf133ae24503ea2e97a57cfe02b8cb67` for `espressif/idf:v6.0.2`, **re-derive before use** with `docker buildx imagetools inspect espressif/idf:v6.0.2 --format '{{println .Manifest.Digest}}'`.
