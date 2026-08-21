# Tools

Operator-facing utilities — anything you'd run from a laptop while setting up the environment, flashing, recovering, or running the bench. Not part of the firmware build. Per project convention, any Python tool goes under [`../python-scripts/`](../python-scripts/) and is invoked from a thin shell-script entry point in this tree; the scripts here are Bash with SPDX headers and `bash -n`-clean.

| File | Purpose |
|------|---------|
| [`env-lock.sh`](env-lock.sh) | Regenerates the environment manifest [`../docs/devenv/env.lock.md`](../docs/devenv/env.lock.md): ESP-IDF tag **and commit SHA** (`git -C "$IDF_PATH" rev-parse HEAD`), `idf.py --version`, `idf_tools.py list` (toolchain build ids, OpenOCD, QEMU), the resolved Python interpreter and version, the CI container index digest, host distro, `cmake`/`ninja`/`ccache` versions. Run inside the `.envrc`-activated shell; CI diffs its output against the committed file (deferred job `env-lock-diff`). |
| [`flash.sh`](flash.sh) | The only sanctioned way to put a build on the watch. Writes the app to the **`ota_1`** offset read from `partitions.csv` (never hard-coded) with the flash arguments from `build/flasher_args.json`, switches `otadata` to `ota_1` with `otatool.py`, and **arms rollback** by patching the entry to `ESP_OTA_IMG_NEW` so the app must call `esp_ota_mark_app_valid_cancel_rollback()` after its health checks or the next reset boots `ota_0`. Refuses to touch `ota_0` without `--recovery-image` (the golden image, confirmation required), the bootloader without `--bootloader`, the partition table without `--table`. esptool v5 hyphenated commands only; `--after no-reset` between chained steps, `default-reset`/`hard-reset` by default with `watchdog-reset` as the opt-in fallback because it **re-enumerates the port** on Linux. `ESPPORT` (`/dev/ttyTWATCH`) comes from `.envrc`. See [`../docs/devenv/first-flash-checklist.md`](../docs/devenv/first-flash-checklist.md). |

Planned entry points (each wraps a `python-scripts/` package when it lands):

| Script | Purpose |
|--------|---------|
| `backup-factory.sh` | Roadmap E2 phase-0 checklist: `chip-id`, `flash-id`, full 16 MB `read-flash` to an **off-repo** path with sha256, `espefuse summary --format json` → `docs/hw/efuse-baseline.json`, vendor partition table dump + `gen_esp32part.py` decode → `docs/hw/vendor-partition-table.md`. Read-only on the device. |
| `recover.sh` | Steps 1–4 of the brick runbook in order (`usb-reset`/`watchdog-reset` probe → 115200 baud → OpenOCD `program_esp_bins`), stopping before anything physical. |
| `coredump.sh` | Pulls the coredump partition and symbolizes it against the ELF archive keyed by `app_elf_sha256` ([`../docs/devenv/coredump-runbook.md`](../docs/devenv/coredump-runbook.md)). |
| `gate-build.sh` | The 30-minute go/no-go of ADR 0001: throwaway project on v6.0.2 with the pinned components and the four headers; fails ⇒ record and fall back to v5.5.5. |
| `bench-*.sh` | Bench capture wrappers (PPK2/Otii, oscilloscope latency, GPSDO tone) calling `python-scripts/bench/`. |

## Rules every script here obeys

- Activation comes from the committed [`.envrc`](../.envrc) (direnv); scripts never source `export.sh` themselves, never use `get_idf`, and abort if `idf.py --version` is not the pinned v6.0.2.
- Never burn an eFuse, never `set-flash-voltage`, never enable secure boot or flash encryption, never write `ota_0`, never touch GPIO19/20 configuration — the NEVER rules of [`CLAUDE.md`](../CLAUDE.md#never--rules-with-no-exceptions) apply to tooling as much as to firmware.
- Irreversible operations (first custom flash, first backlight write) are gated by their checklist and ask for an explicit `yes`.
