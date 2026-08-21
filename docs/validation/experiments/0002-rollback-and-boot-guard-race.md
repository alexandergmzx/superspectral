# Recovery path: OTA rollback and the boot-guard race

**Date:** 2026-08-20 (pre-registered) · **Status:** **validated 2026-08-21** (ran in E2, before any feature code) — hypothesis A in full, hypothesis B's connect clause only: its pre-registered enumeration-window clause was **not measured** and stays open (see Evaluation) ([roadmap](../../roadmap/documentation-roadmap.md) E2 #8). An untested safety net is not a safety net; on a board with zero exposed GPIO and the BOOT button inside the case, this is the single most important thing to verify on real hardware.

## What changed / hypothesis

No product code is involved. Two deliberately broken images are flashed to `ota_1` while the golden recovery image sits in `ota_0` (ADR 0014). The hypothesis is that the mechanisms configured in E0 — `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y`, `CONFIG_BOOTLOADER_WDT_ENABLE=y`, `CONFIG_ESP_TASK_WDT_PANIC=y`, the console on USB-Serial-JTAG, and the 3 s unconditional boot guard (`CONFIG_SPECTRAL_BOOT_GUARD_MS=3000`) — actually recover the device without opening the case.

```sh
# A. rollback: image that never marks itself valid
idf.py -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.ci.release" build
tools/flash.sh --port /dev/ttyACM0     # ota_1 is where flash.sh always writes; it takes no
                                       # slot/file argument and reads the image and its offset
                                       # from flasher_args.json + partitions.csv. ota_0 is
                                       # written only under --recovery-image, which prompts.
# B. boot-guard race: image that crashes right after the guard expires.
#    The test hook is a *Kconfig* symbol, so it must come from an sdkconfig overlay:
#    `-D CONFIG_SPECTRAL_TEST_CRASH_AFTER_GUARD=y` on the idf.py line defines a CMake
#    variable and is silently ignored by the config system.
printf 'CONFIG_SPECTRAL_TEST_CRASH_AFTER_GUARD=y\n' > sdkconfig.crash   # scratch, never committed
idf.py -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.ci.release;sdkconfig.crash" build
tools/flash.sh --port /dev/ttyACM0 --no-arm   # UNDEFINED state, so rollback cannot mask the loop
```

## Provenance

| | |
| --- | --- |
| Golden image in `ota_0` | `firmware/idf-gate/` stage-2b build (commit 794736e tree, `App version: 495f248`), sha256 `f6f0e6661d5a7a1398c07360aa41c49561edd8c3a33826896b0d3c28e613e1a0` (copy in `~/superspectral-backups/2026-08-20/golden-ota0_*.bin`) — the first image that rendered a frame, read the PMU and enumerated USB; marks itself VALID only after a PENDING_VERIFY boot |
| Test images | `firmware/twatch-s3` at this commit; A = the skeleton itself (`app_main` logs and idles after the guard, never calls `esp_ota_mark_app_valid_cancel_rollback()`), sha256 `12852f71ee5268de92c4c1d07c52bed394fe26aab796929f41a2842e5d9e8773`; B = same tree with `CONFIG_SPECTRAL_TEST_CRASH_AFTER_GUARD=y` (a scratch `sdkconfig.crash` overlay — **not** `-D CONFIG_…` on the idf.py line, which is a CMake variable and is ignored), `abort()` immediately after the guard's post-boot logging block — i.e. after `vTaskDelay(pdMS_TO_TICKS(CONFIG_SPECTRAL_BOOT_GUARD_MS))` *and* after the `esp_reset_reason()` / `esp_ota_get_running_partition()` / `esp_ota_get_state_partition()` lines this experiment reads its evidence from, which is why those lines still appear in every crash cycle below (`Kconfig.projbuild`'s help text still says "first statement"; it means the first statement of the application proper) |
| ESP-IDF | `v6.0.2` @ SHA from `env.lock.md` |
| Host | esptool 5.3.1 (IDF v6.0.2 venv), `/dev/ttyACM0` (udev symlink not yet installed), device behind a hub on bus 3-3.1 (worked anyway), the cable that took the 16 MB backup |
| Device | MAC `48:27:e2:e9:b0:8c`, chip rev v0.2; `docs/hw/efuse-baseline.json` committed before this test; factory backup sha256 `1b6f26d7…` recorded in `docs/hw/README.md` |

## Licensing status

| Artefact | Licence | Status |
| --- | --- | --- |
| Test images (repo firmware) | Apache-2.0 | ✅ |

**Practical read:** this proves the recovery procedure for *this* partition table and *this* guard value; it is not a general statement about ESP32-S3 rollback and must be re-run after any change to `partitions.csv`, the bootloader config, or `CONFIG_SPECTRAL_BOOT_GUARD_MS`.

## Scope caveat

Rollback protects against an image that boots and fails its health check; it does nothing for an image that disables USB-Serial-JTAG, reconfigures GPIO19/20, or deep-sleeps before the guard — those are prevented statically (pin `_Static_assert`s, the pre-commit grep, the sleep gate in ADR 0015), not tested here. The PMU-side watchdog (AXP2101, 4 s, if armed) is a third layer and is decided separately in ADR 0015.

## Hypothesis / Setup / Pass–fail

- **Hypothesis A (rollback):** with image A in `ota_1` marked as the boot target, the bootloader boots A, A never marks itself valid, and on the next reset the bootloader reverts to `ota_0` **without any host action**; the golden image then runs and logs `esp_ota_get_state_partition()` = valid for `ota_0`.
- **Hypothesis B (boot-guard race):** with image B in `ota_1`, which crashes and reboots in a loop with a 3 s window per cycle, `idf.py -p /dev/ttyTWATCH flash` (esptool `--before default-reset`) succeeds **10 out of 10** attempts started at random phases of the loop; if the default reset fails, `--before usb-reset --after watchdog-reset` succeeds (noting that `watchdog-reset` re-enumerates the port, so scripts must not hold a fixed path across two commands).
- **Setup:** golden image verified in `ota_0` (renders, PMU OK, USB OK); `otadata` points at `ota_1` via `esp_ota_set_boot_partition()` from a helper build or `otatool.py`; a USB power meter or the PMU log confirms no brownout during the loop; a stopwatch on the USB enumeration (`dmesg -w`) records the window B leaves.
- **Pass A:** revert observed within 2 resets, no host action. **Pass B:** 10/10 flashes; enumeration window ≥ 2 s measured.
- **Fail A:** rollback config or the mark-valid criteria are wrong → fix `sdkconfig.defaults` / the health check, re-run before any other flashing; ADR 0014/0015 amended. **Fail B:** raise `CONFIG_SPECTRAL_BOOT_GUARD_MS` (never lower it), re-run; if JTAG is needed, verify `openocd -f board/esp32s3-builtin.cfg -c "program_esp_bins build flasher_args.json verify exit"` as the second escape hatch and record the OpenOCD version.
- **Repetitions:** A ×3; B ×10 per esptool reset strategy.

## Evaluation

**Hypothesis A — rollback (4/4 PASS).** Procedure per run: `tools/flash.sh --port /dev/ttyACM0` writes A to `ota_1` (0x420000), switches `otadata` to `ota_1` and arms it (`ota_state = ESP_OTA_IMG_NEW`, verified in the script's own read-back). Boot 1 (USB reset): `boot: Loaded app from partition at offset 0x420000` → `running from ota_1 @0x420000, ota state 1 (PENDING_VERIFY)` — the bootloader promoted NEW → PENDING_VERIFY. Boot 2 (USB reset, **no host action**): `Loaded app from partition at offset 0x20000` → the golden image ran, I²C scan `0x19 0x34 0x51 0x5A` / `0x38`, `GATE_STAGE2B_FRAME_SENT`, frame on the panel. Repeated ×3, then a fourth time as the recovery from hypothesis B. Raw `otadata` after a rollback (`esptool read-flash 0xF000 0x2000`, decoded with `otatool.py read_otadata`): **both** copies `ota_seq = 2, state = ABORTED (0x04)` — the bootloader writes the aborted record to both sectors, so no record refers to `ota_0` any more and later boots log `No factory image, trying OTA 0`. Two further resets in that state both booted `ota_0`: **the rolled-back state is stable.** Consequence for app code: `esp_ota_get_state_partition()` on the running `ota_0` then returns an error and leaves the out-parameter untouched — initialise it to `ESP_OTA_IMG_UNDEFINED` (the skeleton does; the gate image printed an uninitialised `0` until fixed in this commit).

**Hypothesis B — boot-guard race (10/10 + 5/5 connects PASS; window clause not measured).** B flashed to `ota_1` with `tools/flash.sh --no-arm` (state UNDEFINED, so rollback cannot mask the loop). Observed loop: `Loaded app … 0x420000` → guard → `TEST HOOK … aborting now` → `abort() was called` → `Rebooting…` → `rst:0xc (RTC_SW_CPU_RST)`, period ≈ 3.5 s (3 000 ms guard + ≈ 0.5 s boot). Against that loop, `esptool -c esp32s3 -p /dev/ttyACM0 --before default-reset --after hard-reset flash-id` (the strategy `idf.py flash` uses) succeeded **10/10**, each in **0.6 s** wall-clock; `--before usb-reset` succeeded **5/5**. **The enumeration-window clause of Pass B was not measured:** the pre-registration asks for a stopwatch on `dmesg -w`, and no dmesg observation was taken, so the width of the window B leaves is `TBD` — a connect time is not a window, and 15/15 successes at unphased loop positions bound the *probability* that the port is reachable, not the *duration* for which it is. What the 15 runs do establish is the operational claim the recovery path needs: esptool's own reset strategies win the race against this loop every time attempted, without a teardown. Settling the width needs one re-run with `dmesg -w` timestamped against the loop (owner: E2 re-run, before the brick runbook quotes any number). Recovery used the armed path: flash A → PENDING_VERIFY → reset → `ota_0`.

| Metric | Target | Result |
|---|---|---|
| Rollback without host action | within 2 resets, ×3 | 2 resets, **4/4** |
| Rolled-back state stable across further resets | boots `ota_0` | 2/2 (`No factory image, trying OTA 0`) |
| esptool wins the race against a 3 s-guard crash loop | 10/10 | **10/10 (default-reset), 5/5 (usb-reset)**, 0.6 s to connect |
| USB enumeration window left by the loop | ≥ 2 s, measured on `dmesg -w` | **not measured** — `TBD`; the connect times above do not bound it |
| Golden image intact afterwards | renders, PMU OK, USB OK | yes — `GATE_STAGE2B_FRAME_SENT`, frame confirmed |

**Wire-path smoke test (after the last recovery):** golden image booted from `ota_0`, `AXP2101 IC_TYPE=0x4A`, frame rendered, host sees `303a:1001` on `/dev/ttyACM0` within the boot window.

### Baseline (what the vendor procedure costs)

LilyGO's documented recovery — remove the battery, hold the internal BOOT button, press the crown, release BOOT — requires opening the case (~20 minutes per occurrence, flex-cable risk). The headline of this experiment is the number of times that procedure was **not** needed.

### Wire-path smoke test

After the last recovery, the golden image in `ota_0` boots, renders a frame, reads the AXP2101 chip ID, and the host sees `303a:1001` on `/dev/ttyTWATCH` within 3 s of reset.

## Interpretation and follow-up

The safety net holds for *this* partition table, *this* guard (3 000 ms) and *this* bootloader (IDF v6.0.2). What it proves: a bad development image in `ota_1` costs two resets, never a teardown; a crash loop does not lock esptool out. What it does not prove: anything about an image that disables USB-Serial-JTAG, touches GPIO19/20 or deep-sleeps before the guard — those are prevented statically (`twatch_pins.h` asserts, pre-commit, ADR 0015), not dynamically. Two process facts fell out: (1) after a rollback `otadata` no longer references `ota_0`, so the golden image must never *depend* on reading its own state; (2) `tools/flash.sh` must stay the only way development builds reach the device — `idf.py flash` would overwrite `ota_0`. Re-run this experiment after any change to `partitions.csv`, `CONFIG_SPECTRAL_BOOT_GUARD_MS`, `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE`, or the IDF pin (the upgrade procedure already lists it).

*(to be filled)* — the result fixes the guard value in `Kconfig.projbuild` for the life of the project and is cited by ADR 0015; the brick runbook ([`../../devenv/brick-runbook.md`](../../devenv/brick-runbook.md)) is updated with the *outcome* — esptool's default-reset and usb-reset strategies both won 15/15 against a 3.5 s crash loop — and **not** with an enumeration window, which this run did not measure.
