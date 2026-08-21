# T-Watch S3 pin map, rail map and I²S allocation

**Provenance — read before trusting a number.** Every pin below is derived from two sources that may be used in an Apache-2.0 project: the LilyGO schematic (`T_WATCH-S3 25-03-24.pdf` and the earlier `T_WATCH_S3.pdf` V1.4, LilyGoLib repository, `schematic/` — facts are not copyrightable) and LilyGoLib's MIT-licensed hardware document (`docs/hardware/lilygo-t-watch-s3.md`) and headers, with attribution. Cross-checked against Zephyr's `boards/lilygo/twatch_s3` device tree (Apache-2.0) and the CircuitPython board definition (MIT) where they agree. **Nothing here was taken from `arduino-esp32/variants/lilygo_twatch_s3/pins_arduino.h`, which is LGPL-2.1-only** (ADR 0004, pre-registered in the [ADR backlog](../adr/README.md) as `0004-split-licensing.md`; [pitfalls H6](../devenv/pitfalls.md#h-ecosystem-and-expectations)). Status **(prov.)**: the schematic is filed in phase D3 and the eFuses are read in E2; until then every row is "three sources agree" rather than "verified on the bench". Bibliography: [01](../bibliography/01-datasheets.md) (schematic, ESP32-S3 datasheet), [11 §F](../bibliography/11-esp-idf-platform-and-toolchain.md).

The firmware's single source of truth is [`firmware/twatch-s3/components/twatch_bsp/include/twatch_pins.h`](../../firmware/twatch-s3/components/twatch_bsp/include/twatch_pins.h), generated **from this table** with one `_Static_assert(pin != 19 && pin != 20)` per constant. When the schematic and this table disagree, the schematic wins and both files change in one commit.

## SoC and memories

| Item | Value | Source |
|---|---|---|
| SoC | ESP32-S3-R8, bare QFN56 **chip-down** (not a module → no inherited RF certification) | schematic string `ESP32-S3-R8` |
| SRAM / PSRAM | 512 KB / 8 MB **octal** in-package (R8) | schematic; Zephyr; PlatformIO `qio_opi` — LilyGoLib's "QSPI" wording loses |
| Flash | 16 MB Winbond, **JEDEC `ef 4018` = W25Q128JV-class, 3.3 V** on this unit (read 2026-08-20). The schematic/Zephyr marking `W25Q128JWPIQ` (1.8 V) does **not** match the silicon here — treat the schematic part number as unverified per unit | `esptool flash-id`; schematic; Zephyr board doc |
| USB | Micro-USB, native USB-Serial-JTAG; `303a:821b` under the shipped Arduino/TinyUSB firmware, `303a:1001` under native ESP-IDF | Espressif `usb-pids` registry; `60-openocd.rules` |
| Exposed GPIO | **none** (VBUS/GND/D± only); BOOT (GPIO0) on the internal PCB; the crown is the AXP2101 PWRKEY, not a GPIO | schematic; LilyGoLib |

## Pin map

| Function | GPIO | Dir | Peripheral / bus | Notes |
|---|---|---|---|---|
| **USB D−** | **19** | — | USB-Serial-JTAG | **NEVER reconfigure.** `_Static_assert` + pre-commit grep (ADR 0015) |
| **USB D+** | **20** | — | USB-Serial-JTAG | **NEVER reconfigure.** |
| LCD MOSI | 13 | out | SPI (ST7789V3) | IOMUX-capable group for 80 MHz; start at 20 MHz (Zephyr `mipi-max-frequency = <20000000>`) |
| LCD SCK | 18 | out | SPI | |
| LCD CS | 12 | out | SPI | |
| LCD DC | 38 | out | SPI | |
| LCD backlight | **45** | out (PWM) | LEDC | VDD_SPI strapping pin (MTDI) — **neutralised on this unit: `VDD_SPI_FORCE=1`** (see cautions); rail ALDO2 |
| LCD MISO / RESET | — | — | — | **not connected** (panel reset follows the ALDO3 rail) |
| Touch SDA | 39 | i/o | I²C1 (FT6336U, addr `0x38`) | separate bus from the main I²C |
| Touch SCL | 40 | out | I²C1 | |
| Touch INT | 16 | in | GPIO | |
| Touch RST | — | — | net `T_RST` **unpopulated** | |
| Main I²C SDA | 10 | i/o | I²C0 | AXP2101 `0x34`, BMA423 `0x19`, PCF8563 `0x51`, DRV2605L `0x5A` |
| Main I²C SCL | 11 | out | I²C0 | |
| PMU IRQ | 21 | in | AXP2101 | attach the handler **after** all rail work |
| RTC IRQ | 17 | in | PCF8563 | |
| Accelerometer INT1 | 14 | in | BMA423 | wrist-raise wake source (ADR 0012) |
| **PDM mic CLK** | **44** | out | I2S0 PDM RX | SPM1423HM4H-B; PDM clock 1.0–3.25 MHz per the Knowles datasheet |
| **PDM mic DATA** | **47** | in | I2S0 PDM RX | VDD_SPI-domain pin (`SPICLK_P`) — **3.3 V on this unit** (eFuse-forced); see cautions |
| I²S BCLK | **48** | out | I2S1 std TX (MAX98357A) | VDD_SPI-domain pin (`SPICLK_N`) — **3.3 V on this unit** (eFuse-forced); see cautions |
| I²S LRCLK / WS | 15 | out | I2S1 | |
| I²S DIN (to amp) | 46 | out | I2S1 | **strapping pin** (ROM messages / download-mode qualifier with GPIO0) — see cautions |
| IR LED | 2 | out | GPIO → MMBT3904 → IR12-21C | |
| LoRa SCK | 3 | out | SPI2 (SX1262) | **strapping pin** (JTAG signal source) — held in reset in v1 (ADR 0017) |
| LoRa MISO | 4 | in | SPI2 | |
| LoRa MOSI | 1 | out | SPI2 | |
| LoRa CS | 5 | out | SPI2 | |
| LoRa RST | 8 | out | GPIO | hold low in v1 |
| LoRa BUSY | 7 | in | GPIO | |
| LoRa DIO1 | 9 | in | GPIO | |
| LoRa DIO3 | 6 | — | SX1262 | present in LilyGoLib `utilities.h`, absent from its public pin table; TCXO question open |
| BOOT | 0 | in | strapping | internal PCB only; [brick-runbook step 6](../devenv/brick-runbook.md) |

## AXP2101 rail map and bring-up order

| Rail | Powers | Boot state in Zephyr DTS (independent confirmation) | Our policy |
|---|---|---|---|
| DC1 | ESP32-S3 core | boot-on | never touched by firmware |
| ALDO2 | **Display backlight** | boot-on | enabled **last**, ramped (LilyGoLib `incrementalBrightness(250, 20)`); 3300 mV |
| ALDO3 | **Display + touch** | boot-on | enabled **before any SPI/I²C traffic** to LCD or FT6336U; ≥ 10 ms settle; 3300 mV |
| ALDO4 | SX1262 LoRa | boot-on | **off** in v1 (ADR 0017) |
| BLDO2 | DRV2605L enable (no GPIO enable) | boot-on | on only while haptics are needed |
| VBACKUP | PCF8563 via MS412FE coin cell | — | — |
| DC2, DC3, DC4, DC5, ALDO1, BLDO1, CPUSLDO, DLDO1, DLDO2 | unused on this board | Zephyr: dcdc3/aldo1 boot-on, rest boot-off | **explicitly disabled** at boot (standby current; no back-powering through a floating rail) |

Order encoded in `twatch_bsp`: set voltages → disable unused channels → ALDO3 → settle → (display init, touch init) → ALDO2 ramped → cap charge current **< 130 mA** (LilyGO guidance for the 470 mAh cell) → PMU IRQ handler. A full I²C scan hitting **all five addresses** (`0x34 0x19 0x51 0x5A` on I²C0, `0x38` on I²C1) is the "board file is correct" gate. Source: LilyGoLib `initPMU()` sequence read as a register reference; Zephyr regulator block as the second witness (its PR notes only DC/DC1 and ALDO were tested on hardware — the AXP2101 datasheet is the arbiter).

Battery: **470 mAh @ 3.8 V** per LilyGoLib (`BATTERY_PARAMS_470mAh[]`) and Zephyr; resellers say 400 mAh — unresolved, confirm against the shipped cell before any autonomy figure is published (§4 metric "≥ 3 h").

## I²S allocation — fixed by silicon, not by preference

| Port | Mode | Pins | Device | Why this way |
|---|---|---|---|---|
| **I2S0** | `i2s_channel_init_pdm_rx_mode()` | CLK 44, DIN 47 | SPM1423 PDM mic | `components/esp_driver_i2s/i2s_pdm.c` rejects any other port: *"This channel handle is registered on I2S1, but PDM is only supported on I2S0"* (`ESP_RETURN_ON_FALSE`, two guards); PDM RX is **16-bit only** |
| **I2S1** | `i2s_channel_init_std_mode()` (Philips) | BCLK 48, WS 15, DOUT 46 | MAX98357A | full-duplex on one port needs matching clock/slot configs, which PDM RX and standard TX can never share |

Two independent `i2s_new_channel()` calls with different `i2s_chan_config_t.id`. DMA and ring buffers `MALLOC_CAP_INTERNAL | MALLOC_CAP_DMA` ([pitfalls D5](../devenv/pitfalls.md#d-memory-placement-and-runtime)). PDM slot: LilyGoLib captures one channel only — which `slot_mask` (`I2S_PDM_SLOT_LEFT`/`RIGHT`) carries the SPM1423 is an E2 experiment; the wrong one captures silence and looks like a dead mic. Rates: 16 kHz/`DSR_16S` → 2.048 MHz clock; 32 kHz/`DSR_8S` comfortable; 48 kHz needs 3.072 MHz, 5.8 % under the mic's 3.25 MHz maximum — verify (ADR 0003). No hardware PDM high-pass on the S3 (`SOC_I2S_SUPPORTS_PDM_RX_HP_FILTER` absent from `soc_caps.h` in v6.0.x): DC removal is software.

## Cautions — strapping pins and the 1.8 V domain

> **Resolved on the first unit (2026-08-20, E2 step 3).** `espefuse summary` read `VDD_SPI_FORCE=True`, `VDD_SPI_XPD=True`, `VDD_SPI_TIEH="VDD_SPI connects to VDD3P3_RTC_IO"` — VDD_SPI is **forced to 3.3 V by eFuse**, so GPIO45 is never sampled as a strap and GPIO47/48 sit in the 3.3 V domain; the flash is a 3.3 V W25Q128JV-class part (`ef 4018`). The rows below are kept as the general hazard description and the check every *new* unit must pass ([`README.md`](README.md) ledger) before its backlight code runs.

| Pin | Hazard | What we do |
|---|---|---|
| **GPIO45 — backlight = VDD_SPI strap** | With `VDD_SPI_FORCE == 0`, the level of GPIO45 at reset selects VDD_SPI: low/floating → **3.3 V into a 1.8 V flash**; high → 1.8 V. Any firmware that drives GPIO45 low across a reset boundary risks destroying the W25Q128JW | **Read `VDD_SPI_FORCE`/`TIEH`/`XPD` before a single line of backlight code** ([first-flash-checklist step 3](../devenv/first-flash-checklist.md)). `FORCE == 1` → pin is free. `FORCE == 0` → LEDC idle-high, release-to-input inside the one permitted reboot wrapper, pull-up confirmed on the schematic (ADR 0016) |
| **GPIO47 (PDM DATA), GPIO48 (I²S BCLK) — VDD_SPI domain** | ESP32-S3 datasheet: `SPICLK_P`/`SPICLK_N` are powered from VDD_SPI; *"for the ESP32-S3R8V chip … the working voltage for these pins is also 1.8 V"*. A 3.3 V SPM1423 would over-drive GPIO47; a 1.8 V BCLK is marginal against the MAX98357A's `V_IH` ≈ 0.65 × DVDD | **Resolve on paper first** from the schematic (which rail feeds mic and amp; any level translation) and the datasheet pin table, before debugging any audio ([pitfalls C9](../devenv/pitfalls.md#c-flash-psram-power)). If there is no translation and both parts sit on 3.3 V, then VDD_SPI is 3.3 V and the R8-vs-R8V question resolves the other way — which also changes the `VDDSDIO_BOOST` reasoning |
| GPIO46 (I²S DIN) — strapping pin | ROM-message printing / download-mode qualifier together with GPIO0; internal weak pull-down at reset (verify in the datasheet strapping table) | The MAX98357A input is high-impedance at reset, so the strap sees the pull-down; never add an external pull-up; I2S1 is configured after boot |
| GPIO3 (LoRa SCK) — strapping pin | JTAG signal-source select (verify) | SX1262 held in reset, ALDO4 off (ADR 0017); SPI2 is not initialised in v1 |
| GPIO0 (BOOT) — strapping pin | download mode when low at reset | internal button only; never a firmware GPIO |
| GPIO19/20 | USB-Serial-JTAG; the only recovery path | `_Static_assert` + CI grep; never `gpio_reset_pin()` over a range |

## Open questions that change this file

| # | Question | Closed by |
|---|---|---|
| H-R8 | R8 or R8V (3.3 V vs 1.8 V VDD_SPI)? | schematic SoC power page (D3) + `VDD_SPI_FORCE` read (E2) |
| H-rail | Which rail powers the SPM1423 and the MAX98357A? | schematic (D3/D4) |
| H-touch | FT6336U (LilyGoLib, `0x38`, `TouchDrvFT6X36`) vs FT5336 (Zephyr binding)? LilyGoLib wins until a board revision proves otherwise; `esp_lcd_touch_ft5x06` performs no chip-ID check and works for both | bench (E2) |
| H-lcd | ST7789V3 revision and tolerated pixel clock (20 → 80 MHz stepping, on the wrist too) | bench (E2), experiment in `docs/validation/experiments/` |
| H-slot | PDM slot mask | bench (E2) |
| H-batt | 470 vs 400 mAh | cell label / teardown (E2) |
| H-dio3 | SX1262 DIO3 / TCXO | deferred with the radio (ADR 0017) |
