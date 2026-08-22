# Backup policy — back up the right things, refuse to back up the wrong ones

**Decision:** back up only what cannot be regenerated; explicitly *do not* back up the tool roots, virtualenvs, the component mirror, or stale constraints files — carrying those forward is how two of the catalogued environment hazards re-enter a clean machine (critic B5).

| Back up | Where | Why |
|---|---|---|
| The git repository (incl. `firmware/twatch-s3/dependencies.lock`, `sdkconfig.defaults*`, `partitions.csv`, `.envrc`) | the remote once one exists; until then a second local clone on another disk | the lock is the reproducibility keystone; everything else in the build is derived from it plus the IDF tag |
| [`../hw/efuse-baseline.json`](../hw/efuse-baseline.json) | in the repo (committed) | irreplaceable hardware record; the `VDD_SPI_FORCE` answer lives here |
| `twatch-s3-factory-backup-<date>.bin` (16 MB) + its `.sha256` + the carved vendor `nvs`/calibration slices | **off-repo, two locations** (external drive + private object store); the sha256 lines in [`../hw/README.md`](../hw/README.md) | the only way back to the shipped state; vendor NVS may carry calibration/BLE identity. Not in git and not in git-LFS in this repo: a vendor firmware image is not ours to redistribute |
| [`../hw/vendor-partition-table.md`](../hw/vendor-partition-table.md) (decoded) | in the repo | the map needed to interpret the backup and to restore selectively |
| [`env.lock.md`](env.lock.md) + the CI container index digest | in the repo | re-creates the toolchain byte-for-byte with `setup.md` |
| Per-release ELF + `.map` + `sdkconfig` + `dependencies.lock` archive keyed by `app_elf_sha256` | release assets / off-repo archive ([coredump-runbook.md](coredump-runbook.md)) | a field core dump cannot be symbolised without the exact ELF |
| Golden vectors and Praat golden files with their manifest (`host/golden/`, `docs/validation/golden-files.md`) | in the repo (small) / `datasets/` policy for large | the validation claim depends on them |

| Do **not** back up | Why it is harmful, not just wasteful |
|---|---|
| `IDF_TOOLS_PATH` (`~/esp/tools/<tag>`, and the legacy `~/.espressif/tools/`) | ~2 GB per root, fully reconstructible from the tag via `install.sh`; a restored root silently reintroduces whatever was wrong with it |
| `python_env/` virtualenvs | a venv is not self-contained — `pyvenv.cfg` records the base interpreter path; the existing ones point at `/usr/local/bin` ([pitfalls](pitfalls.md) A6). Recovery is `rm -rf … && ./install.sh esp32s3` |
| `~/.espressif/tools/components/` (the EIM local component mirror) | carrying it forward **reintroduces the silent-resolution bug** (`IDF_COMPONENT_LOCAL_STORAGE_URL`, [pitfalls](pitfalls.md) B8) |
| `~/.espressif/espidf.constraints.v6.0.txt` (2025-05-28) | pins esptool 4.9 / kconfig 2.x / component-manager 2.x — every runbook in this repo assumes esptool 5. Cite <https://dl.espressif.com/dl/esp-idf/espidf.constraints.v6.0.txt>, never a host copy ([pitfalls](pitfalls.md) A21) |
| `~/esp/esp-idf` (master snapshot, **removed 2026-08-21**), `~/.espressif/v6.0.1` (EIM tree, still present) | superseded trees; a new clone at the tag is the backup. *(`~/esp/v5.4.1` is intentionally excluded from this row — the owner keeps it as a second reference environment, 2026-08-20 decision. It still needs no backup: reconstructible from its own tag, same reasoning, different reason to have it on disk.)* |
| `build/`, `build_*/`, `managed_components/`, `sdkconfig`, `sdkconfig.old`, `.direnv/`, `.cache/` | generated; `managed_components/` is regenerated from the lock; a restored `sdkconfig` shadows `sdkconfig.defaults` ([pitfalls](pitfalls.md) B2) |
| `docs/**/*.ocr.md`, `docs/reference-projects/clones/` | regenerated in seconds; several sources are not redistributable |

## Cadence and verification

- **Factory backup:** once (phase E2), verified with `esptool verify-flash` and a scratch-region restore ([first-flash-checklist.md](first-flash-checklist.md) steps 2 and 5). Re-read the sha256 of both copies annually.
- **Repo:** every commit is a backup once a remote exists; until then, `git clone --mirror` to the second disk after each session.
- **Release archives:** at every tag, before the binary leaves the bench (coredump runbook).
- **Test the restore path, not the backup:** a backup whose restore has never been exercised is an assumption. The scratch-region test is mandatory; a full 16 MB restore is rehearsed once on the bench before any OTA goes to a second unit.

## What this protects against

Losing the machine (everything needed is the repo + two off-repo files), losing the watch's shipped state (full image + decoded table), and — the actual risk on this host — *restoring* a tangled environment onto a clean one (the right-hand column).
