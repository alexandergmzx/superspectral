# Brick runbook — when the watch stops talking

**Read this at 2 a.m. in order. Do not skip to step 6.** The T-Watch S3 has zero exposed GPIO and its BOOT button is on the internal PCB: the only re-flash path is esptool driving the on-chip USB-Serial-JTAG (USJ) controller over the Micro-USB port, and the only alternative is opening the case. Everything below is ordered from "free" to "teardown" (critic B9). Prevention lives in ADR 0015 and [pitfalls §E](pitfalls.md#e-usb-serial-jtag-flashing-recovery).

All commands use esptool **v5** (hyphenated names). `PORT` is `/dev/ttyTWATCH` if the udev symlink exists, else whatever `ls /dev/ttyACM*` shows *after* the re-plug.

## Before you start: what kind of silence is it?

| Symptom | Likely state | Go to |
|---|---|---|
| `lsusb -d 303a:` lists the device, `idf.py flash` fails with `Wrong boot mode detected` / `Timed out waiting for packet header` | app is running or crash-looping faster than the ~1 s USJ enumeration | steps 1–2 |
| Device appears in `lsusb`, disappears after ~1–3 s, reappears | crash loop, brownout loop on low battery, or a host daemon grabbing the port | steps 1–3 |
| `lsusb` shows nothing at all, on a cable that charges | USJ disabled by firmware (GPIO19/20 reconfigured, USJ peripheral off, early deep sleep) or PMU holding the SoC off | steps 3–6 |
| Enumerates, `esptool flash-id` works, but the app never prints | not a brick — port is fine; flash a known-good build to ota_1 with `tools/flash.sh`, then read the core dump ([coredump-runbook.md](coredump-runbook.md)) | — |

Always check `esp_reset_reason()` in the last log you have; `ESP_RST_BROWNOUT` repeats point at the battery, not the firmware.

## Step 1 — Force the reset sequence over USJ

```bash
esptool --chip esp32s3 --port "$PORT" --before usb-reset --after watchdog-reset flash-id
```

`--before usb-reset` drives the USJ-specific reset-to-download sequence; `--after watchdog-reset` is what the esptool docs recommend "when the RTS control line is not available, especially in the USB-OTG and USB-Serial/JTAG modes" and the chip is stuck in download mode.

> **`--after watchdog-reset` re-enumerates the port on Linux** (critic B7). `/dev/ttyTWATCH` (or `/dev/ttyACMn`) disappears and comes back — possibly under a different number if the symlink rule is not installed. Never chain two esptool invocations on a fixed path after it; wait for `udevadm settle` / re-read `ls /dev/ttyACM*`, or use `--after no-reset` while chaining and reset once at the end (this is what [`tools/flash.sh`](../../tools/flash.sh) does).

If `flash-id` answers, the chip is alive: flash a known-good build **to ota_1** with `tools/flash.sh`, or, if `ota_0` holds the golden recovery image, just erase `otadata` to make the bootloader fall back to it (`idf.py -p "$PORT" erase-otadata` does the same from the build directory):

```bash
python3 "$IDF_PATH/components/app_update/otatool.py" --port "$PORT" \
  --partition-table-file firmware/twatch-s3/partitions.csv erase_otadata
```

(With both otadata copies erased and no factory partition, the bootloader logs `No factory image, trying OTA 0` — verified in `bootloader_utility.c`, v6.0.1.)

The 3 s unconditional boot guard at the top of `app_main` (`CONFIG_SPECTRAL_BOOT_GUARD_MS`) exists precisely so that step 1 always wins the race against a crash loop. Retry it up to ten times with the cable re-plugged between attempts before moving on.

## Step 2 — Drop the baud rate, retry

```bash
esptool --chip esp32s3 --port "$PORT" --baud 115200 --before usb-reset flash-id
```

`Invalid head of packet` / `Timed out waiting for packet header` at 460800 and success at 115200 means cable or supply, not firmware. 9600 is the last resort. Always exit any `idf.py monitor` first (Ctrl-]) — a monitor holding the port looks exactly like a dead device.

## Step 3 — Cable, hub, battery, daemons

1. A **different, short, known-good data cable** (many Micro-USB cables are charge-only).
2. **No hub**, no front-panel port, no USB-C adapter chain — directly into the machine.
3. **Charge the battery** for 30 minutes with the watch "off". A brownout loop on an empty 470 mAh cell re-enumerates the device endlessly; the AXP2101 can also refuse to bring up DC1 when the cell is below its cut-off.
4. `dmesg -w` while plugging in: `cdc_acm … ttyACM0: USB ACM device` then silence = healthy; repeated connect/disconnect = crash/brownout loop; a `brltty` or `ModemManager` line = a host daemon grabbed the port. On this host ModemManager is masked and brltty is not installed ([setup.md §0](setup.md#0-host-audit--what-is-already-on-this-machine-read-only-2026-08-20)); on another machine: `sudo systemctl mask ModemManager.service brltty-udev.service brltty.service`.
5. Another computer, if available — it separates host problems from device problems in one move.

Then repeat step 1.

## Step 4 — Flash over JTAG with OpenOCD

The built-in JTAG shares GPIO19/20 with the CDC side but is a **separate protocol path**; when the CDC endpoint is confused, JTAG often still attaches.

```bash
openocd -f board/esp32s3-builtin.cfg \
  -c "program_esp_bins firmware/twatch-s3/build flasher_args.json verify exit"
```

`program_esp_bins` writes what `flasher_args.json` lists (bootloader, table, app at the build's app offset = **ota_0**). That is acceptable in a recovery: it overwrites the golden image with the build you are recovering with — re-establish the golden image afterwards with `tools/flash.sh --recovery-image`. For a single region instead: `openocd -f board/esp32s3-builtin.cfg -c "program_esp build/super_spectral.bin 0x420000 verify exit"`.

If OpenOCD reports the target but flashing fails, at least `openocd` + `xtensa-esp32s3-elf-gdb -ex "target remote :3333"` lets you `monitor reset halt` and inspect what the app did to GPIO19/20. The OpenOCD build in the v6.0.x tools root (`v0.12.0-esp32-20260304` on this host) is recent enough.

## Step 5 — Let the battery drain, retry from cold

If the firmware disabled USJ or deep-sleeps immediately, the ROM bootloader still re-enumerates for a moment **at every cold power-on**. The crown is the AXP2101 PWRKEY — it does not reset the SoC, it asks the PMU; and with a charged cell the PMU keeps DC1 up, so there is no cold start without opening the case. The free version of a cold start is waiting: leave the watch unplugged until the cell is empty (hours to days depending on what the firmware does), then plug in **with step 1 already running in a loop**:

```bash
until esptool --chip esp32s3 --port "$PORT" --before usb-reset --after no-reset flash-id; do sleep 0.2; done
```

The race is winnable because the ROM's download-mode window precedes the app entirely. This step costs time, not hardware.

## Step 6 — Open the case (last resort)

LilyGO's documented recovery: *remove the battery, hold the BOOT button, press the crown briefly, then release BOOT; long-press the crown afterwards to exit.* With the back cover off and the battery lifted, BOOT (GPIO0) + power-on puts the ROM into download mode regardless of what the firmware did to GPIO19/20 — unless `DIS_USB_SERIAL_JTAG` was burned, which this project never does ([first-flash-checklist.md](first-flash-checklist.md)).

- Have the correct drivers and **a spare back-cover gasket and screws** on hand *before* you need them; the flex cables to the display and touch panel are the parts that die in a hurried teardown.
- While the cover is off, **do not touch GPIO45** with anything. On *this* unit the strap is neutralised — VDD_SPI is eFuse-forced to 3.3 V, so GPIO45 is never sampled ([ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md)) — but it is still the backlight driver, and on a unit whose eFuses have not been read it is the VDD_SPI strap and a hardware-destruction risk. Read the eFuses first; treat every unread unit as strapped.
- In download mode, restore either the factory backup (`write-flash 0 twatch-s3-factory-backup-<date>.bin`, see the checklist) or a known-good build to ota_0 with `tools/flash.sh --recovery-image`.
- Before closing the case: flash a build whose first log line is the boot guard, and verify `esptool flash-id` works through USJ with the case still open.

## After recovery — do not close the incident without these

1. Write the reset reason, the last log, and what you did into `docs/validation/experiments/` (a one-paragraph incident note is enough).
2. If the cause was a regression of an ADR 0015 invariant (GPIO19/20, USJ console, sleep gate, boot guard), add the missing assertion: a `_Static_assert` in `twatch_bsp/include/twatch_pins.h`, a line in the `no-usb-pins` or `sdkconfig-invariants` pre-commit hook, or a test in experiment 0002.
3. Re-establish the golden image in `ota_0` (`tools/flash.sh --recovery-image`) if step 4 or 6 overwrote it.
4. Decide, if not yet decided, whether the AXP2101 4 s PMU watchdog is armed (XPowersLib's init sequence arms it; a hung app then gets power-cycled by the PMU independently of any ESP32 watchdog). It is either a third recovery layer or a surprise — record the choice in ADR 0015 (critic B2).

## Why these steps exist (the five ways to lose the port)

| # | Cause | Mitigation shipped from commit one |
|---|---|---|
| 1 | GPIO19/GPIO20 reconfigured as GPIO | `_Static_assert` on every pin constant + `no-usb-pins` pre-commit grep; never `gpio_reset_pin()` over a range |
| 2 | USJ peripheral disabled / console moved | `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y` asserted by pre-commit; `CONFIG_USJ_NO_AUTO_LS_ON_CONNECTION=y` |
| 3 | `esp_deep_sleep_start()` early | every sleep entry gated on "awake ≥ N s AND no USB host"; NVS "armed" flag during development; timer wake always paired |
| 4 | Light sleep | no PM in development builds; `fflush(stdout)` + delay before any sleep |
| 5 | Crash loop faster than ~1 s enumeration | 3 s boot guard (`CONFIG_SPECTRAL_BOOT_GUARD_MS`, never reduced); `CONFIG_ESP_TASK_WDT_PANIC=y`; OTA rollback with `esp_ota_mark_app_valid_cancel_rollback()` only after display + touch + PMU + USB are confirmed |

Sources: USB Serial/JTAG Console guide, esptool advanced options and troubleshooting pages, espefuse documentation — bibliography [11 §E](../bibliography/11-esp-idf-platform-and-toolchain.md).
