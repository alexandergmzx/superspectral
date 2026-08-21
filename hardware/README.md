# Hardware

Everything physical about Super Spectral. There is **no custom PCB, enclosure or wiring**: the device is an off-the-shelf LilyGO T-Watch S3, and the hardware work of this project is (a) knowing the board precisely, (b) measuring what the vendor does not document, and (c) choosing and qualifying the bench that validates it.

| Subdirectory | Contents |
|--------------|----------|
| [bom/](bom/) | Bill of materials (`bill-of-materials.csv`) — the device under test **and** the bench instruments with their tolerances; single source of truth for cost rollups |
| [acoustic-port/](acoustic-port/) | The largest hardware-documentation gap: microphone port / case / gasket geometry, planned teardown measurements, Helmholtz estimate |

Derived board facts (pin map with attribution, eFuse baseline, decoded vendor partition table) live under [`../docs/hw/`](../docs/hw/) because they are cross-cutting inputs to firmware, devenv and validation; vendor documents live in the reference library ([`../docs/datasheets/lilygo/t-watch-s3/`](../docs/datasheets/lilygo/t-watch-s3/)).

## The device

LilyGO T-Watch S3, SX1262 variant — schematic `T_WATCH_S3.pdf` V1.4 and the 2025-03-24 revision; LilyGoLib hardware doc ([`01-datasheets.md`](../docs/bibliography/01-datasheets.md)).

| Block | Part | Facts that bind the design |
|---|---|---|
| SoC | ESP32-S3-R8, chip-down QFN56 | Not a module ⇒ **no inherited FCC/RED certification** (stated, not assumed — ADR 0005/0017 territory); 512 KB SRAM, 8 MB octal PSRAM; single-precision FPU |
| Flash | Winbond W25Q128JW, 16 MB, **1.8 V only** | Forces the R8-vs-R8V / VDD_SPI question; backlight GPIO45 is the VDD_SPI strapping pin — resolve from the eFuse read (roadmap E2) **before any backlight code** |
| Microphone | Knowles SPM1423HM4H-B, PDM, top port, on GPIO44 (CLK) / GPIO47 (DATA) | −22 dBFS sensitivity, 61.5 dB(A) SNR, PDM clock 1.0–3.25 MHz, AOP 110 dB SPL (Rev A, page-verified; Rev D says 115 — pin one revision); **obsolete** at distributors; its rail is not documented — read it from the schematic |
| Amplifier / speaker | MAX98357A on I2S1 (BCLK 48 / LRCLK 15 / DIN 46); transducer **undocumented** | Calibration-tone source only; needs the speaker spec from LilyGO before gain is set |
| Display | 240×240 IPS, ST7789V3, SPI (CS 12 / MOSI 13 / SCK 18 / DC 38), BL GPIO45, MISO and RESET not connected | T_SCYCW differs 4× between ST7789 revisions (66 ns vs 16 ns) — pixel-clock ceiling is empirical; start at 20 MHz |
| Touch | FT6336U on I²C1 (SDA 39 / SCL 40), 0x38, INT 16; reset net unpopulated | Low-power modes must be recoverable without reset |
| PMU | AXP2101 on I²C0 (SDA 10 / SCL 11), 0x34, IRQ 21 | DC1 = SoC, ALDO2 = backlight, ALDO3 = display + touch, ALDO4 = LoRa, BLDO2 = haptic enable; charge current ≤ 130 mA (LilyGO); E-Gauge coulomb counter is the on-device energy cross-check |
| Sensors | BMA423 (0x19, INT 14), PCF8563 RTC (0x51, INT 17, MS412FE backup cell), DRV2605L (0x5A) | Wrist-raise arming and haptic confirmation (ADR 0012) |
| Radio | SX1262 on SPI2, DIO3 (GPIO6) undocumented in LilyGO's pin table | Held in reset, ALDO4 off, no radio in v1 (ADR 0017) |
| Battery | 470 mAh (LilyGoLib) vs 400 mAh (resellers) — **unresolved** | ±15 % straight into the autonomy target; confirm against the shipped cell |
| I/O | Micro-USB, native USB-Serial-JTAG on GPIO19/20; **zero exposed GPIO**; BOOT button on the internal PCB only | The only flash/debug path; every anti-brick rule in [`../docs/devenv/`](../docs/devenv/) follows from this row |
| Ingress | IP54 claimed by resellers only | No vendor statement for the S3 |

## Hardware questions this directory owns

Routed in the roadmap; each lands as a `_notes.md`, a BOM row, a validation row or an ADR:

1. **Acoustic port / case / gasket geometry** — [`acoustic-port/`](acoustic-port/). Outranks the speaker as the largest gap: it bounds the headline measurement.
2. Which AXP2101 rail powers the microphone and the amplifier (schematic; affects the power budget and the QEMU/boot-off regulator states).
3. R8 vs R8V and `VDD_SPI_FORCE` (eFuse read, E2) — gate for ADR 0016.
4. 470 vs 400 mAh; panel 1.3″ vs 1.54″; ST7789V vs V3 marking; FT6336U vs FT5336; mic second-sourced in 2025?; `ULC0511C` identity; speaker transducer spec.
5. How a PPK2/Otii is inserted into a sealed watch (battery pigtail procedure) — prerequisite for the ≥3 h metric.
6. Thermal: 240 MHz dual-core + backlight in a sealed case on skin — a comfort question and the thermal-drift row in validation.

## Bring-up checklist (hardware side, before any custom firmware — roadmap E2)

1. Order the spares row of the BOM (gasket, screws, drivers).
2. [`../docs/devenv/first-flash-checklist.md`](../docs/devenv/first-flash-checklist.md): `chip-id`, `flash-id`, full 16 MB `read-flash` backup (sha256, stored off-repo), `espefuse summary --format json` → `docs/hw/efuse-baseline.json`, decode and commit the vendor partition table, verify the backup restores.
3. Flash the vendor factory image once to prove display, touch, PMU and radio are alive. LilyGoLib's involvement ends there.
4. Read `VDD_SPI_FORCE`; write ADR 0016; only then touch GPIO45.
5. Teardown for [`acoustic-port/`](acoustic-port/) measurements while the case is open for the battery pigtail.
