# Core-dump runbook — the only post-mortem a sealed device gives you

**Decision:** core dumps go to the 60 KiB `coredump` flash partition (`0xFF1000`, [`partitions.csv`](../../firmware/twatch-s3/partitions.csv)), are retrieved with `idf.py coredump-info`, and are symbolised against an **archived ELF keyed by `app_elf_sha256`** — one archive per build that ever left the bench (critic B8).

**Trade-off:** 60 KiB of flash and a per-release archiving step, for a backtrace from a device with no UART, no exposed pins and no debugger attached when it crashed.

## Configuration (what is, and is not, in `sdkconfig.defaults`)

| Symbol | Value | Note |
|---|---|---|
| `CONFIG_ESP_COREDUMP_ENABLE_TO_FLASH` | `y` | the load-bearing choice (`components/espcoredump/Kconfig`, choice `ESP_COREDUMP_TO_FLASH_OR_UART`) |
| `CONFIG_ESP_COREDUMP_DATA_FORMAT_ELF`, `CONFIG_ESP_COREDUMP_CHECKSUM_SHA256` | selected automatically | in v6.0.x these are `select`ed by `ESP_COREDUMP_ENABLE` and have **no prompt** — the format is ELF + SHA256 only. Do not write them into `sdkconfig.defaults`; the line would be silently ignored |
| `CONFIG_ESP_COREDUMP_CHECK_BOOT` | default | verifies an existing dump's checksum at boot |
| `CONFIG_ESP_COREDUMP_FLASH_NO_OVERWRITE` | decide in ADR 0015 | `y` keeps the *first* crash if several happen before retrieval; `n` keeps the *last* |
| `CONFIG_ESP_COREDUMP_MAX_TASKS_NUM`, `CONFIG_ESP_COREDUMP_STACK_SIZE` | defaults until measured | raise the stack size only if the dump itself faults; SHA256 needs more than CRC32 (Kconfig help) |
| `CONFIG_ESP_TASK_WDT_PANIC=y`, `CONFIG_ESP_INT_WDT=y` | `y` | a watchdog *panic* produces a dump; the Kconfig default for the task watchdog only logs ([pitfalls](pitfalls.md) D2) |
| `CONFIG_APP_REPRODUCIBLE_BUILD=y` | `y` | paths inside the ELF are remapped to `/IDF`, `/IDF_PROJECT`, …; gdb needs `build/gdbinit/prefix_map` (see below) |

Partition subtype `coredump`, 60 KiB: enough for the DSP and UI task stacks plus TCBs at the configured task count; if `ESP_COREDUMP_MAX_TASKS_NUM` grows, re-check the size against `idf.py coredump-info` output before the layout is frozen by ADR 0014.

## At boot: make the dump findable

Every build logs, right after the boot guard, the first 8 hex characters of `esp_app_get_elf_sha256_str()` and `esp_app_get_description()->version` (the `git describe` string, ≤ 31 characters). That pair is the archive key. Log `esp_reset_reason()` alongside, and keep the NVS reset-reason histogram (critic B12) — it tells you whether the dump you are about to read is the crash you are hunting.

## Retrieval

From the repo shell, with the build that produced the firmware checked out **or** the archived ELF at hand:

```bash
cd firmware/twatch-s3
idf.py -p /dev/ttyTWATCH coredump-info                 # reads the coredump partition, prints registers, backtrace, tasks, memory regions
idf.py -p /dev/ttyTWATCH coredump-info --save-core cores/<sha8>-<date>.elf   # keep the raw dump
idf.py -p /dev/ttyTWATCH coredump-debug                # same, then a gdb session on the dump
```

`idf.py` passes `build/super_spectral.elf` and the partition offset from the build automatically. With an archived ELF instead of a build directory:

```bash
esptool --chip esp32s3 --port /dev/ttyTWATCH read-flash 0xFF1000 0xF000 cores/<sha8>-<date>.bin
esp-coredump --chip esp32s3 info_corefile --core cores/<sha8>-<date>.bin --core-format raw \
             --save-core cores/<sha8>-<date>.elf releases/<tag>/<sha8>/super_spectral.elf
esp-coredump --chip esp32s3 dbg_corefile  --core cores/<sha8>-<date>.bin --core-format raw \
             releases/<tag>/<sha8>/super_spectral.elf
```

(`esp-coredump` is pinned `~=1.14` by the upstream v6.0 constraints file, <https://dl.espressif.com/dl/esp-idf/espidf.constraints.v6.0.txt>, verified 2026-08-20; the exact installed version is recorded by `tools/env-lock.sh` in [env.lock.md](env.lock.md). The `--off` option takes the partition offset if the dump is read live from the device instead of a file. `espcoredump.py` is the deprecated spelling.)

Because of `CONFIG_APP_REPRODUCIBLE_BUILD`, a hand-launched gdb needs `source build/gdbinit/prefix_map` (or the archived copy of that file) to find sources; `idf.py gdb`/`coredump-debug` do it for you ([pitfalls](pitfalls.md) B19).

If `coredump-info` reports a checksum mismatch: the app was rebuilt after the crash (the ELF does not match) or the partition holds a dump from an older build — check the `app_elf_sha256` printed in the dump header against the archive index before concluding the dump is corrupt.

## The ELF archive — no ELF, no backtrace

A core dump is addresses; only the exact ELF turns them into symbols. Stripping is not the issue — **a rebuild from the same commit is not byte-identical unless every input matched** (that is what `env.lock.md` + `dependencies.lock` + the container digest make *likely*, not certain). Archive, do not hope to rebuild.

| What | Where | Key |
|---|---|---|
| `super_spectral.elf`, `super_spectral.map`, `sdkconfig`, `dependencies.lock`, `build/gdbinit/prefix_map`, `flasher_args.json`, the `.bin` | `releases/<tag>/<sha8>/` off-repo (and as release assets once a remote exists) | `sha8` = first 8 hex of `app_elf_sha256` (`esp_app_get_elf_sha256_str()`); `<tag>` = the `git describe` string |
| Archive index | `docs/validation/` release table (tag · sha8 · date · which units carry it) | lets a dump's header be mapped to an archive without guessing |

**When to archive:** at every tag, and for *any* build flashed to a unit that leaves the bench (a friend's wrist counts). `tools/flash.sh` prints the build's `flasher_args.json` path; make the archive step part of the same session. **Retention:** as long as any unit may still run that build — in practice the life of the project.

## Triage flow

1. Boot log → `sha8` + version + reset reason.
2. `idf.py coredump-info --save-core` → raw dump saved under `cores/` (gitignored: it contains RAM contents and is private to the project).
3. Symbolise against `releases/<tag>/<sha8>/super_spectral.elf`.
4. Crashing task + backtrace → issue; if it is a watchdog panic on `IDLE1`, start with [pitfalls](pitfalls.md) D1 (DSP task starving the idle task), if `Cache disabled but cached memory region accessed`, D4.
5. Fix → new build → `tools/flash.sh` (ota_1, rollback armed) → the health check must pass before `esp_ota_mark_app_valid_cancel_rollback()`.
6. Erase the consumed dump from download mode — `python3 "$IDF_PATH/components/partition_table/parttool.py" --port /dev/ttyTWATCH --partition-table-file partitions.csv erase_partition --partition-name coredump` (or `esptool erase-region 0xFF1000 0xF000`) — or let the next crash overwrite it per `ESP_COREDUMP_FLASH_NO_OVERWRITE`.

Sources: ESP-IDF core dump and panic-handler guides, `components/espcoredump/Kconfig` (v6.0.1, symbols cited above), `esp-coredump` CLI help — bibliography [11 §E](../bibliography/11-esp-idf-platform-and-toolchain.md).
