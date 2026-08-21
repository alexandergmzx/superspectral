# idf-gate — the ESP-IDF go/no-go gate (ADR 0001)

A one-file ESP-IDF project that answers, on the real T-Watch S3, "does the exact pinned
component set build **and run** on the pinned ESP-IDF?" It is the instrument behind
[ADR 0001](../../docs/adr/0001-toolchain-esp-idf-v6-pinned-environment.md) and step 2 of the
[upgrade procedure](../../docs/devenv/upgrade-procedure.md): run it on the candidate IDF
before any feature code moves.

**Passed 2026-08-20 on ESP-IDF v6.0.2 (`7101770d`)** — stage 1 (build, zero warnings) and
stage 2 (running on the watch: PMU rails, ST7789 over SPI, LVGL 9.5 frame, backlight).

## What it exercises

| Stage | Check | Evidence (2026-08-20) |
|---|---|---|
| 1 | `espressif/esp-dsp ==1.8.2`, `lvgl/lvgl ==9.5.0`, `espressif/esp_lvgl_port ==2.9.0`, `espressif/esp_lcd_touch_ft5x06 ==1.1.1`, `joltwallet/littlefs ==1.22.3`, `lewisxhe/sensorlib ==0.4.1` compile under v6.0's warnings-as-errors | 0 warnings; `dependencies.lock` committed here |
| 2a | Boots from `ota_0 @ 0x20000` on the project partition table; octal PSRAM 8 MB @ 80 MHz memory test; USB-Serial-JTAG console; 3 s boot guard; esp-dsp 1024-pt FFT; OTA state read | log: `esp_psram: Found 8MB PSRAM device / Speed: 80MHz`, `running from ota_0 @0x20000, ota state 2` |
| 2b | I²C0 scan, AXP2101 `IC_TYPE`, ALDO3 → settle → I²C1 scan (touch), ST7789 init at 20 MHz, `esp_lvgl_port` display, a frame, then ALDO2 + LEDC backlight ramp | `I2C0 devices: 0x19 0x34 0x51 0x5A`, `AXP2101 IC_TYPE=0x4A`, `I2C1 devices: 0x38`, frame confirmed visually |

Pins and register addresses come from [`docs/hw/twatch-s3-pins.md`](../../docs/hw/twatch-s3-pins.md)
and XPowersLib's MIT `REG/AXP2101Constants.h` — **not** from arduino-esp32's LGPL `variants/`.

## Bring-up facts it established (feed `twatch_bsp`)

- The AXP2101 answers at `0x34` with `IC_TYPE = 0x4A`; `LDO_ONOFF_CTRL0` read `0x2F` on arrival
  (ALDO1–4 + BLDO2 already on — the vendor firmware's state survives an ESP reset because the PMU
  is not reset with the SoC). Do not rely on that: set voltages and enable explicitly.
- ST7789 works with `rgb_ele_order = RGB`, `invert_color = true`, `set_gap(0, 0)`, 20 MHz SPI,
  `esp_lvgl_port` `swap_bytes = true`, 2 × 240×30 RGB565 DMA buffers in internal SRAM.
- The **registry tarball** `lewisxhe/sensorlib 0.4.1` contains **no AXP2101 code** (the `src/pmic/`
  tree and `PmicXPowers.hpp` present in the GitHub repo at the same version are stripped from the
  component-manager package). So the "SensorLib PMIC fallback" exists upstream but not via
  `idf_component.yml`; `twatch_bsp` writes its own ~300-line driver, as ADR 0001 preferred anyway.
- `PROJECT_VER` is captured at **configure** time: a build from a stale configure differs from a
  fresh one only in the version stamp. Reconfigure (`fullclean`) before comparing binaries.

## Run it

```sh
cd firmware/idf-gate
idf.py set-target esp32s3 && idf.py build            # stage 1
idf.py -p "$ESPPORT" flash                            # stage 2 — first flash of a fresh unit (bootloader + table + ota_0)
# On a unit that already carries the golden recovery image in ota_0, flash to ota_1 instead:
#   tools/flash.sh build/idf60_gate.bin                 (refuses ota_0 unless --recovery-image)
```

Read the log with `idf.py monitor` (or any 115200 terminal on the USB-Serial-JTAG port). Then look at
the screen. If either stage fails on a candidate IDF, the upgrade does not proceed.
