# twatch_bsp — T-Watch S3 board support

**Decision.** One component owns every board fact: pins, I²C addresses, AXP2101 rail sequence, I²S port allocation, and the hazard rules that go with them. Application code never names a GPIO. **Trade-off:** a thin extra layer over `esp_driver_*`/`esp_lcd`, in exchange for a single place where the anti-brick rules (ADR 0015) and the VDD_SPI/GPIO45 rule (ADR 0016) are enforced mechanically rather than by discipline.

This pass ships only [`include/twatch_pins.h`](include/twatch_pins.h): every pin as a `#define` with a `_Static_assert(pin != 19 && pin != 20)`, the rail table, and provenance. Prose with the full source matrix and open questions: [`docs/hw/twatch-s3-pins.md`](../../../../docs/hw/twatch-s3-pins.md).

## What the header fixes now

| Item | Value | Note |
|---|---|---|
| Display SPI | CS 12 · MOSI 13 · SCK 18 · DC 38 · BL **45** | MISO/RESET not connected; GPIO45 = VDD_SPI strap — **no backlight code before ADR 0016** |
| Touch (FT6336U, 0x38) | I²C1: SDA 39 · SCL 40 · INT 16 | separate bus from the PMU bus |
| Main I²C | SDA 10 · SCL 11 | AXP2101 0x34 · BMA423 0x19 · PCF8563 0x51 · DRV2605L 0x5A |
| PDM mic (SPM1423) | **I2S0**: CLK 44 · DATA 47 | PDM RX is I2S0-only, 16-bit-only (ADR 0003) |
| Amp (MAX98357A) | **I2S1**: BCLK 48 · LRCLK 15 · DIN 46 | cannot share I2S0 with PDM RX |
| Interrupts | PMU 21 · BMA423 14 · RTC 17 · touch 16 | |
| SX1262 | SPI: SCK 3 · MISO 4 · MOSI 1 · CS 5 · RST 8 · BUSY 7 · DIO1 9 · DIO3 6 (verify) | held in reset, ALDO4 off (ADR 0017) |
| USB | **GPIO19/20 — never referenced** | USB-Serial-JTAG: console, debug, and the only re-flash path |

Rails: DC1 = SoC · ALDO2 = backlight (**last**, ramped) · ALDO3 = display + touch (**first**, ≥10 ms settle) · ALDO4 = LoRa (off) · BLDO2 = DRV2605L enable · VBACKUP = RTC cell. Charge current ≤ 130 mA. Which rail powers the mic and amp is **unresolved** (schematic read, roadmap D4).

## Planned sources (E2, after the eFuse baseline)

| File | Owns | Gate |
|---|---|---|
| `twatch_pmu_axp2101.c` | ~300-line AXP2101 driver over `i2c_master_bus_handle_t`; SensorLib `PmicAXP2101` is the fallback | `docs/hw/efuse-baseline.json` committed (roadmap E2) |
| `twatch_display.c` | in-tree `esp_lcd_new_panel_st7789()` at 20 MHz first; `set_gap`/invert/mirror tuned on hardware | ALDO3 sequencing proven |
| `twatch_touch.c` | `esp_lcd_touch_new_i2c_ft5x06()`, `max_point_num = 2` | same |
| `twatch_audio.c` | `i2s_channel_init_pdm_rx_mode()` on I2S0; `i2s_channel_init_std_mode()` on I2S1; DMA in `MALLOC_CAP_INTERNAL \| MALLOC_CAP_DMA` | mic/amp rail question answered |
| `twatch_bsp.c` | bring-up order + five-address I²C scan gate; the **only** permitted reboot wrapper (releases GPIO45 if `VDD_SPI_FORCE == 0`) | ADR 0016 |

Licence note: pin numbers are facts derived from the schematic and LilyGoLib's MIT material with attribution; `arduino-esp32/variants/` (LGPL-2.1) is never opened while editing this component (ADR 0004).
