# Recovery path: OTA rollback and the boot-guard race

**Date:** 2026-08-20 (pre-registered) · **Status:** planned — runs in **E2 week 1**, before any feature code ([roadmap](../../roadmap/documentation-roadmap.md) E2 #8). An untested safety net is not a safety net; on a board with zero exposed GPIO and the BOOT button inside the case, this is the single most important thing to verify on real hardware.

## What changed / hypothesis

No product code is involved. Two deliberately broken images are flashed to `ota_1` while the golden recovery image sits in `ota_0` (ADR 0014). The hypothesis is that the mechanisms configured in E0 — `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y`, `CONFIG_BOOTLOADER_WDT_ENABLE=y`, `CONFIG_ESP_TASK_WDT_PANIC=y`, the console on USB-Serial-JTAG, and the 3 s unconditional boot guard (`CONFIG_SPECTRAL_BOOT_GUARD_MS=3000`) — actually recover the device without opening the case.

```sh
# A. rollback: image that never marks itself valid
idf.py -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.ci.release" build
tools/flash.sh --slot ota_1 build/super_spectral.bin        # flash.sh refuses --slot ota_0
# B. boot-guard race: image that crashes right after the guard expires
idf.py -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.ci.release" -D SPECTRAL_TEST_CRASH_AFTER_GUARD=1 build
tools/flash.sh --slot ota_1 build/super_spectral.bin
```

## Provenance

| | |
| --- | --- |
| Golden image in `ota_0` | commit TBD, `PROJECT_VER` TBD, sha256 TBD — the first image that rendered a frame, read the PMU and enumerated USB |
| Test images | commit TBD; A = `app_main` returns after the guard without calling `esp_ota_mark_app_valid_cancel_rollback()`; B = null dereference on the first statement after `vTaskDelay(pdMS_TO_TICKS(CONFIG_SPECTRAL_BOOT_GUARD_MS))` |
| ESP-IDF | `v6.0.2` @ SHA from `env.lock.md` |
| Host | `esptool` v5 (hyphenated commands), `/dev/ttyTWATCH` udev symlink, no USB hub, known-good cable |
| Device | unit s/n / MAC TBD; `docs/hw/efuse-baseline.json` committed **before** this test (E2 #3); factory backup sha256 recorded off-repo |

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

*(to be filled when the experiment runs)*

### Baseline (what the vendor procedure costs)

LilyGO's documented recovery — remove the battery, hold the internal BOOT button, press the crown, release BOOT — requires opening the case (~20 minutes per occurrence, flex-cable risk). The headline of this experiment is the number of times that procedure was **not** needed.

### Wire-path smoke test

After the last recovery, the golden image in `ota_0` boots, renders a frame, reads the AXP2101 chip ID, and the host sees `303a:1001` on `/dev/ttyTWATCH` within 3 s of reset.

## Interpretation and follow-up

*(to be filled)* — the result fixes the guard value in `Kconfig.projbuild` for the life of the project and is cited by ADR 0015; the brick runbook ([`../../devenv/brick-runbook.md`](../../devenv/brick-runbook.md)) is updated with the measured enumeration window.
