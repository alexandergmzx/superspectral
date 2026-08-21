# LilyGoLib + XPowersLib — AXP2101 rails, ST7789 init and the PDM path (D4 reference-project loop)

- **Projects:** `Xinyuan-LilyGO/LilyGoLib` ([bibliography 06 #4](../../bibliography/06-reference-projects.md)) and `lewisxhe/XPowersLib` ([06 #8](../../bibliography/06-reference-projects.md)) — read together, because LilyGoLib's `initPMU()` is a list of *method names* and XPowersLib is the only place where those names become register writes. Cross-checked against `Xinyuan-LilyGO/TTGO_TWatch_Library` branch `t-watch-s3` ([06 #5](../../bibliography/06-reference-projects.md)) and `lewisxhe/SensorLib` ([06 #7](../../bibliography/06-reference-projects.md)) where the two vendor libraries disagree, and against the filed AXP2101 datasheet ([01 #17](../../bibliography/01-datasheets.md)).
- **Studied commits:** LilyGoLib `38e6f8dee3ba78b340512af9a013365ef248a7d0` (2026-08-11, "Fix docs …/issues/32") · XPowersLib `d6997586e68f65afd51baa775903df930db39821` (2026-07-01, "fix axp2101 getIrqStatus byte order") · TTGO_TWatch_Library `9884d62` (2026-01-08, branch `t-watch-s3`) · SensorLib `2b9e591` (2026-07-30). All shallow clones under [`../clones/`](../README.md) (gitignored).
- **Licences:** both **MIT**, confirmed from each repository's own `LICENSE` (LilyGoLib "Copyright (c) 2025 Xinyuan Electronics"; XPowersLib "Copyright (c) 2022 lewis he"). Apache-2.0-compatible ⇒ code *may* sit on the firmware link line with `NOTICE` attribution (ADR 0004, [backlog](../../adr/README.md)). Nothing below is copied verbatim; what transfers is the register sequence, which is a hardware fact.
- **Studied:** 2026-08-21, against the measured facts of 2026-08-20/21 ([`docs/hw/README.md`](../../hw/README.md), [ADR 0016](../../adr/0016-backlight-gpio45-vdd-spi-strap.md), [ADR 0017](../../adr/0017-no-radio-in-v1-trimmed-component-set.md), [experiment 0002](../../validation/experiments/0002-rollback-and-boot-guard-race.md), [`firmware/idf-gate/README.md`](../../../firmware/idf-gate/README.md)). **Where a measurement and a vendor source disagree, the measurement wins and the disagreement is recorded in §6.**
- **Feeds:** ADR 0018 (project-study ADR), [ADR 0003](../../adr/README.md) (mic path), ADR 0007 (canvas), an amendment to [ADR 0015](../../adr/0015-anti-brick-policy.md) §10, corrections to [`docs/hw/twatch-s3-pins.md`](../../hw/twatch-s3-pins.md); component [`twatch_bsp`](../../../firmware/twatch-s3/components/twatch_bsp/README.md) (`twatch_pmu_axp2101.c`, `twatch_display.c`, `twatch_audio.c`).

> **LGPL boundary.** `arduino-esp32` is not cloned and `variants/lilygo_twatch_s3/pins_arduino.h` was **not opened** at any point in this study — see §2, which is the reason it matters more here than anywhere else. The arduino-esp32 `ESP_I2S` library (`I2SClass`) was likewise not read; where LilyGoLib calls into it, this note records only the *arguments LilyGoLib passes*, which are LilyGoLib's own MIT source.

## 1. What each repository is, and what was read

`LilyGoLib` is the vendor's Arduino board-support library for the whole T-family (T-Watch-S3, T-Watch-Ultra, T-LoRa-Pager). For us it is exactly three things: `src/LilyGoWatchS3.cpp` (`begin()` → `initPMU()` → display init → peripherals → `setRotation(0)`), `src/LilyGoDispInterface.cpp` (`LilyGoDispSPI::init()` — the `esp_lcd` argument list and the vendor ST7789 command list), and `src/PDM.{h,cpp}` + `initMicrophone()` (the mic path). `docs/hardware/lilygo-t-watch-s3.md` is the MIT pin/rail/address table that [`docs/hw/twatch-s3-pins.md`](../../hw/twatch-s3-pins.md) was derived from.

`XPowersLib` is a header-only C++ PMU library; `src/XPowersAXP2101.hpp` (3 142 lines) holds the whole AXP2101 implementation (the `.tpp` is an 18-line stub), and `src/REG/AXP2101Constants.h` the register addresses. Read as a **register reference**, not as a dependency: bibliography 06 #8 already forbids adding it as a component next to SensorLib (duplicate AXP2101 symbols), and the gate established that the registry tarball of `lewisxhe/sensorlib 0.4.1` ships no AXP2101 code at all — so `twatch_bsp` writes its own driver either way.

Files read in full or in the relevant part: `LilyGoWatchS3.cpp` (1 062 lines), `LilyGoWatchS3.h`, `LilyGoDispInterface.{h,cpp}` (818 lines), `BrightnessController.h`, `PDM.{h,cpp}` (207 lines), `docs/hardware/lilygo-t-watch-s3.md`, `examples/peripheral/RecordWAV/RecordWAV.ino`, `examples/factory/hal_interface.cpp` (audio/FFT part); XPowersLib `REG/AXP2101Constants.h`, `XPowersAXP2101.hpp`, `XPowersParams.hpp`, `XPowersCommon.hpp`, `examples/ESP_IDF_Example/main/port_axp2101.cpp`; TTGO `src/LilyGoLib.cpp` (PMU block); SensorLib `src/pmic/xpowers/axp2101/AXP2101Core.cpp`, `AXP2101Watchdog.{hpp,cpp}`.

## 2. The LGPL boundary — LilyGoLib contains no pin numbers

This is the single most important structural finding, and it changes how the repository must describe its own provenance.

`LilyGoWatchS3.cpp` uses `SDA`, `SCL`, `TP_SDA`, `TP_SCL`, `TP_INT`, `DISP_SCK`, `DISP_MISO`, `DISP_MOSI`, `DISP_CS`, `DISP_RST`, `DISP_DC`, `DISP_BL`, `DISP_WIDTH`, `DISP_HEIGHT`, `PMU_INT`, `SENSOR_INT`, `RTC_INT`, `MIC_SCK`, `MIC_DAT`, `I2S_BCLK`, `I2S_WCLK`, `I2S_DOUT`, `IR_SEND`, `LORA_*`, `GPS_RX/TX`. **None of them is defined anywhere in LilyGoLib** — `grep -rn 'define DISP_WIDTH' .` and `grep -rn 'MIC_SCK' .` over the whole clone return only *uses*. They come from `arduino-esp32/variants/lilygo_twatch_s3/pins_arduino.h`, which is **LGPL-2.1-only**; LilyGoLib's own hardware document links to that file as its "Pins Map" heading.

Consequences:

- LilyGoLib's **source** cannot be an MIT pin source, only an MIT *sequence* source. The MIT pin source is `docs/hardware/lilygo-t-watch-s3.md` (a table, reproduced in §6), plus the schematics ([01 #6/#7](../../bibliography/01-datasheets.md)) whose facts are not copyrightable. This is exactly what [`docs/hw/twatch-s3-pins.md`](../../hw/twatch-s3-pins.md) already claims, so the claim survives — but the wording "LilyGoLib's MIT-licensed … headers" should become "LilyGoLib's MIT-licensed hardware **document**", because the headers do not carry pin numbers.
- Every register address, bit position, voltage code and delay in this note is from MIT sources (LilyGoLib `.cpp`, XPowersLib `.hpp`) or from the filed datasheet. No LGPL file was consulted.
- The pin *values* in §6 that appear in both the MIT document and (presumably) the LGPL header are facts about copper, verified independently by our own I²C scan and by the working gate build.

## 3. AXP2101 — the vendor's rail sequence, decoded to registers

### 3.1 The call sequence as written (`LilyGoWatch2022::initPMU()`)

`begin()` calls, in order: `Wire.begin(SDA, SCL)` and `Wire1.begin(TP_SDA, TP_SCL)`; `SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI)`; optional dual-bus I²C dump; **`initPMU()`**; `LilyGoDispSPI::init(…, 80)`; optional boot image + `incrementalBrightness(250, 20)`; `initTouch()`; `initSensor()`; `initRTC()`; `initDrv()`; `initGPS()`; `initMicrophone()`; `initAmplifier()`; `initLoRa()`; one-shot `calibrationPMU(470)` gated by an NVS flag; `setRotation(0)`.

Two facts about this order matter for `twatch_bsp`:

1. **There is no delay anywhere in `initPMU()`, and no settle wait between it and the display init.** The vendor enables the display rail and starts SPI traffic in consecutive statements.
2. **`initPMU()` returns before the I²C bus clock is raised.** `initSensor()` sets `Wire.setClock(1000000UL)` for the BMA423 probe and leaves it at `400000UL`; nothing sets a clock before that, so the whole PMU sequence runs at the Arduino `Wire` default. Our driver should state its own `scl_speed_hz` explicitly (the gate used 100 kHz for the AXP2101 device handle).

### 3.2 Register-level table — the specification `twatch_pmu_axp2101.c` can be written from

Every row is `LilyGoLib call → XPowersLib body → register write`, with the datasheet's own reset default alongside so the driver author can see which writes actually change something. `RMW` = read-modify-write of the named mask. Addresses from `REG/AXP2101Constants.h`; semantics and defaults from the filed AXP2101 datasheet §6.13.2 ([01 #17](../../bibliography/01-datasheets.md)).

| # | Vendor call | Reg | Write | Meaning | DS default |
|---|---|---|---|---|---|
| 0a | `pmu.init(Wire)` → `initImpl()` | `0x03` | read | `IC_TYPE`, must be `0x4A` | — |
| 0b | …`disableTSPinMeasure()` | `0x50` | `(old & 0xF0) \| 0x10` | TS pin = external fixed input (no NTC on this board) | — |
| 0c | …same | `0x30` | bit1 ← 0 | TS ADC channel off | 1 |
| 1 | `setVbusVoltageLimit(VBUS_VOL_LIM_4V36)` | `0x15` | `(old & 0xF0) \| 0x06` | VINDPM 4.36 V | `0110b` — **no-op** |
| 2 | `setVbusCurrentLimit(VBUS_CUR_LIM_900MA)` | `0x16` | `(old & 0xF8) \| 0x02` | VBUS input limit 900 mA | `100b` (1500 mA) |
| 3 | `setSysPowerDownVoltage(2600)` | `0x24` | `(old & 0xF8) \| 0x00` | VSYS power-off threshold 2.6 V | EFUSE |
| 4 | `setALDO2Voltage(3300)` | `0x93` | `(old & 0xE0) \| 0x1C` | ALDO2 = 3.3 V (**backlight**) | EFUSE |
| 5 | `setALDO3Voltage(3300)` | `0x94` | `(old & 0xE0) \| 0x1C` | ALDO3 = 3.3 V (**display + touch**) | EFUSE |
| 6 | `setALDO4Voltage(3300)` | `0x95` | `(old & 0xE0) \| 0x1C` | ALDO4 = 3.3 V (**SX1262**) | EFUSE |
| 7 | `setBLDO2Voltage(3300)` | `0x97` | `(old & 0xE0) \| 0x1C` | BLDO2 = 3.3 V (**DRV2605L enable**) | EFUSE |
| 8 | `setBLDO1Voltage(3300)` | `0x96` | `(old & 0xE0) \| 0x1C` | BLDO1 = 3.3 V (GPS — *not fitted on T-Watch-S3*) | EFUSE |
| 9 | `setDC3Voltage(3300)` | `0x84` | `(old & 0x80) \| 0x69` | DC3 = 3.3 V (GPS on older variants) — see §3.8 | EFUSE |
| 10 | `setButtonBatteryChargeVoltage(3300)` | `0x6A` | `(old & 0xF8) \| 0x07` | RTC coin-cell charge termination 3.3 V | `011b` (2.9 V) |
| 11 | `setDC4Voltage(850)` | `0x85` | `(old & 0x80) \| 0x23` | DC4 = 0.85 V (LS550G GPS core) | EFUSE |
| 12 | `disableDC2()` | `0x80` | bit1 ← 0 | DC2 off | EFUSE |
| 13 | `disableDC5()` | `0x80` | bit4 ← 0 | *bit4 is **RO** and there is no DCDC5 at all in the filed (SWcharge) datasheet variant, which lists 4 DCDCs — see §3.8. Harmless either way* | RO/0 |
| 14 | `disableALDO1()` | `0x90` | bit0 ← 0 | ALDO1 off | EFUSE |
| 15 | `disableCPUSLDO()` | `0x90` | bit6 ← 0 | CPUSLDO off | EFUSE |
| 16 | `disableDLDO1()` | `0x90` | bit7 ← 0 | DLDO1 off — **see §6, this is the audio rail** | EFUSE |
| 17 | `disableDLDO2()` | `0x91` | bit0 ← 0 | DLDO2 off | EFUSE |
| 18 | `enableALDO2()` | `0x90` | bit1 ← 1 | **backlight rail ON — before the display rail** | — |
| 19 | `enableALDO3()` | `0x90` | bit2 ← 1 | display + touch rail ON | — |
| 20 | `enableALDO4()` | `0x90` | bit3 ← 1 | radio rail ON | — |
| 21 | `enableBLDO2()` | `0x90` | bit5 ← 1 | haptic enable ON | — |
| 22 | `enableDC3()` | `0x80` | bit2 ← 1 | DC3 ON | — |
| 23 | `enableDC4()` | `0x80` | bit3 ← 1 | DC4 ON | — |
| 24 | `enableBLDO1()` | `0x90` | bit4 ← 1 | BLDO1 ON | — |
| 25 | `enableButtonBatteryCharge()` | `0x18` | bit2 ← 1 | RTC coin-cell charging ON | 0 |
| 26 | `setPowerKeyPressOffTime(POWEROFF_4S)` | `0x27` | `(old & 0xF3) \| (0<<2)` | long-press power-off = **4 s** | `01b` (**6 s**) |
| 27 | `setPowerKeyPressOnTime(POWERON_128MS)` | `0x27` | `(old & 0xFC) \| 0x00` | power-on press = 128 ms | EFUSE |
| 28 | `enableBattDetection()` | `0x68` | bit0 ← 1 | battery detection ON | 1 — no-op |
| 29 | `enableVbusVoltageMeasure()` | `0x30` | bit2 ← 1 | VBUS ADC | 0 |
| 30 | `enableBattVoltageMeasure()` | `0x30` | bit0 ← 1 | VBAT ADC | 1 — no-op |
| 31 | `enableSystemVoltageMeasure()` | `0x30` | bit3 ← 1 | VSYS ADC | 0 |
| 32 | `enableTemperatureMeasure()` | `0x30` | bit4 ← 1 | die-temperature ADC | 0 |
| 33 | `setChargingLedMode(CHG_LED_OFF)` | `0x69` | `(old & 0xC8) \| 0x05` | CHGLED pin enabled, driven by `chgled_out_ctrl`, output **Hi-Z** | EFUSE/1 |
| 34 | `disableIRQ(ALL_IRQ)` | `0x40`,`0x41`,`0x42` | `0x00`,`0x00`,`0x00` | mask everything first | 0 |
| 35 | `enableIRQ(…)` | `0x41` | `0xFC` | PKEY long+short, BAT ins/rem, VBUS ins/rem | — |
| 36 | …same | `0x42` | `0x18` | charge start + charge done | — |
| 37 | `clearIrqStatus()` | `0x48`,`0x49`,`0x4A` | `0xFF` ×3 | write-1-to-clear all latches | — |
| 38 | `setPrechargeCurr(PRECHARGE_50MA)` | `0x61` | `(old & 0xF0) \| 0x02` | pre-charge 50 mA | `0101b` (125 mA) |
| 39 | `setChargerConstantCurr(CHG_CUR_125MA)` | `0x62` | `(old & 0xE0) \| 0x05` | **CC charge 125 mA** (< the 130 mA guidance) | EFUSE |
| 40 | `setChargerTerminationCurr(CHG_ITERM_25MA)` | `0x63` | `(old & 0xF0) \| 0x01` | termination 25 mA (bit4 "termination enable" preserved) | bit4=1, `0101b` |
| 41 | `setChargeTargetVoltage(CHG_VOL_4V35)` | `0x64` | `(old & 0xF8) \| 0x04` | **CV target 4.35 V** | `011b` (4.2 V) |
| 42 | `pinMode(PMU_INT, INPUT_PULLUP)` + `attachInterrupt(FALLING)` | — | — | GPIO21, registered **last**, after all rail work | — |

**Resulting register state** (assuming the write order above, with `0x90` bits not listed left as found):

| Reg | Value after `initPMU()` | Note |
|---|---|---|
| `0x90` | `0x3E` = `0b0011_1110` | ALDO2/3/4 + BLDO1 + BLDO2 on; ALDO1, CPUSLDO, DLDO1 off |
| `0x91` | bit0 = 0 | DLDO2 off |
| `0x80` | bits 2,3 = 1; bit 1 = 0; bit 0 (DC1) untouched | **DC1 is never written — correct, it powers the SoC** |
| `0x30` | `0x1D` = `0b0001_1101` | VBAT + VBUS + VSYS + TDIE on, TS off |
| `0x41` / `0x42` | `0xFC` / `0x18` | see §3.4 |

Bit map for `0x90`, confirmed identical in XPowersLib and in the datasheet: `b0` ALDO1 · `b1` ALDO2 · `b2` ALDO3 · `b3` ALDO4 · `b4` BLDO1 · `b5` BLDO2 · `b6` CPUSLDO · `b7` DLDO1; `0x91 b0` DLDO2. LDO voltage registers are contiguous: `0x92` ALDO1 … `0x95` ALDO4, `0x96` BLDO1, `0x97` BLDO2, `0x98` CPUSLDO, `0x99` DLDO1, `0x9A` DLDO2; all encode `(mV − 500) / 100` in bits `4:0` with `7:5` read-only — so **3300 mV is always `0x1C`**, and the `& 0xE0` read-modify-write in XPowersLib is preserving read-only bits, i.e. a plain write of `0x1C` is equivalent.

### 3.3 Rail enable order — the vendor does **not** do what our pin document says it does

[`docs/hw/twatch-s3-pins.md`](../../hw/twatch-s3-pins.md) states the order "set voltages → disable unused channels → ALDO3 → settle → (display init, touch init) → ALDO2 ramped … Source: LilyGoLib `initPMU()` sequence read as a register reference." Rows 18–19 of the table above show that LilyGoLib enables **ALDO2 (backlight) before ALDO3 (display + touch)**, with no settle delay and no ramp — the ramp is a later LEDC duty ramp on GPIO45 (§4.4), not a rail ramp. The vendor gets away with it because LEDC duty is 0 until `setBrightness()` runs, so the backlight rail is live but dark.

Our order (ALDO3 → ≥10 ms → ALDO2 last) is **better and stays**, but its provenance line is wrong and must be corrected to "our own, informed by the ADR 0016 GPIO45 rule; LilyGoLib enables ALDO2 first". The gate already implements our order and passed (`ALDO3 → 20 ms → I²C1 scan → ST7789 → ALDO2 + LEDC ramp`), so nothing in firmware changes — only the attribution.

Similarly, "DC2, DC3, DC4, DC5, ALDO1, BLDO1, CPUSLDO, DLDO1, DLDO2 … **explicitly disabled** at boot" is *our* policy, not the vendor's: LilyGoLib leaves **DC3, DC4 and BLDO1 enabled** on every board including the plain T-Watch-S3, because the same function serves the GPS-equipped T-Watch-Plus. On a watch with no GPS that is three unused regulators burning quiescent current for the life of the product — a concrete argument for our policy and for the §4 autonomy metric.

### 3.4 IRQ setup

`disableIRQ(ALL)` → `enableIRQ(mask)` → `clearIrqStatus()`, then the GPIO. The mask decodes as (XPowersLib packs `INTEN1/2/3` into one 24-bit word, low byte = `0x40`):

| Reg | Value | Bits set |
|---|---|---|
| `0x40` (INTEN1) | `0x00` | *(untouched — XPowersLib only writes a group if the mask has bits in it, and `disableIRQ(ALL)` had already zeroed it)* |
| `0x41` (INTEN2) | `0xFC` | b2 PKEY long · b3 PKEY short · b4 BAT remove · b5 BAT insert · b6 VBUS remove · b7 VBUS insert |
| `0x42` (INTEN3) | `0x18` | b3 charge start · b4 charge done |

Notable omissions for a battery-powered analyzer: **`WARNING_LEVEL1/2`** (SOC drop, `0x40` b6/b7) and **`GAUGE_NEW_SOC`** (`0x40` b4) are *not* enabled by LilyGoLib, yet `checkPowerStatus()` tests `isDropWarningLevel1Irq()`/`Level2Irq()` — and XPowersLib's `is*Irq()` helpers gate on the cached `intRegister[]`, so those two branches are permanently dead in the vendor firmware. If we want a low-battery warning we must enable `0x40` bits 6/7 ourselves; `setLowBatWarnThreshold()` writes `0x1A` (5–20 %, defaults 20 %/6 %).

Reading the status: `getIrqStatus()` reads `0x48`,`0x49`,`0x4A` into `statusRegister[0..2]` and returns `(s[2]<<16)|(s[1]<<8)|s[0]` — i.e. **`INTSTS1` is the low byte**. The studied commit is the fix for that byte order (upstream issue #60), so any code written from an older copy of XPowersLib has it backwards. Clearing writes `0xFF` to all three (write-1-to-clear).

The pin: `pinMode(PMU_INT, INPUT_PULLUP)` + `attachInterrupt(…, FALLING)` on GPIO21, ISR sets a FreeRTOS event bit only, `loop()` calls `checkPowerStatus()`. The AXP2101 IRQ pin is open-drain and stays low until the status registers are cleared, so an **edge**-triggered handler that misses a clear wedges silently; prefer level-low in `twatch_bsp`, or guarantee the clear.

### 3.5 Charging, and the numbers that follow from it

- **CC = 125 mA** (`0x62` ← 5), against LilyGoLib's own documented guidance "*use a charging current below 130 mA. Excessive charging current can damage the battery*". Confirms the `< 130 mA` cap in our rail table, now with the exact code.
- **CV target = 4.35 V** (`0x64` ← 4), commented "T-Watch-S3 uses a high-voltage (4.35 V) battery by default". This is **new** to our documentation: [`docs/hw/twatch-s3-pins.md`](../../hw/twatch-s3-pins.md) records only "470 mAh @ 3.8 V" (nominal). A 4.35 V high-voltage cell has ~5 % more usable capacity than a 4.2 V one, and the datasheet POR default is 4.2 V — so a `twatch_bsp` that never writes `0x64` will silently under-charge the cell by ~5 %, which lands directly on the §4 **autonomy ≥ 3 h** metric. Decide deliberately; do not leave `0x64` at its default by accident.
- Pre-charge 50 mA, termination 25 mA (both below the POR default of 125 mA).
- `0x67` (charge safety timers, defaults: 12 h charge-done timer, 60 min pre-charge timer, both enabled) is **never touched** by the vendor.

### 3.6 Fuel-gauge calibration — `calibrationPMU()`

`begin()` reads an NVS bool `lilygo/calibration`; if unset it calls `calibrationPMU(470)` (or 940 for the GPS variant, selected by GPS presence) and sets the flag. `writeGaugeData(BATTERY_PARAMS_470mAh, 128)` in XPowersLib is: `0x17` bit2 set then cleared (reset fuel gauge) → `0xA2` bit0 cleared then set (enable ROM register) → **128 sequential single-byte writes to `0xA1`** → `0xA2` bit0 cleared then set again → read-back compare. `BATTERY_PARAMS_470mAh[]` is a 128-byte opaque blob in `LilyGoWatchS3.h` (MIT).

For us: the parameters live in the **PMU**, not in ESP flash, so whatever the factory image wrote is still there and survives our re-partitioning (our NVS is a new partition; the vendor's flag is not visible to us, which is precisely why re-running this would be a *second* write). Recommendation for `twatch_bsp` v1: **do not write gauge data.** The E-Gauge percentage is a convenience readout, not a measurement instrument — the §4 autonomy number is anchored to PPK2/Otii, not to `0xA4`. If it is ever wanted, it needs its own ADR, because it is a one-way write to a peripheral we cannot re-image.

### 3.7 Sleep and wake — rail handling and the vendor's own power numbers

`lightSleep()`: radio sleep → backlight/haptic/GPS/speaker rails off → `disableIRQ(ALL)` + `clearIrqStatus()` → optionally `rtc_gpio_pullup_en(PMU_INT)` and `enableIRQ(PKEY_SHORT)` → `esp_sleep_enable_ext1_wakeup_io(mask, ESP_EXT1_WAKEUP_ANY_LOW)` → `esp_light_sleep_start()` → rails back on, IRQ mask restored.

`sleep()` (deep): `enableSleep()` (`0x26` bit0), all ADC channels disabled, ALDO3 off *only if* touch is not a wake source (`touch.sleep()` first), ALDO2/ALDO4/BLDO2/DC3/BLDO1 off, optionally the RTC backup charge off, then a 4-second countdown printed to serial, then `Serial1.end()`/`SPI.end()`/`Wire.end()`/`Wire1.end()`, then `gpio_reset_pin()` + `pinMode(pin, OPEN_DRAIN)` over an explicit pin list, then `esp_deep_sleep_start()`.

Useful numbers, from vendor comments and the hardware document — inputs to the planned `docs/architecture/06-power-budget.md`:

| Item | Value | Source |
|---|---|---|
| Leaving the display rail (ALDO3) off in deep sleep | **+≈600 µA** anomalous increase | code comment in `sleep()` |
| Display + touch asleep but powered | ≈103.4 µA (screen 100 + touch 3.4) | same comment |
| Light sleep, PWR + BOOT + touch wake | 2.38 mA | hardware doc |
| Deep sleep, PWR + BOOT wake, backup on / off | 530 µA / 460 µA | hardware doc |
| Deep sleep, touch wake | 1.08 mA | hardware doc |
| Power off, backup only | 50 µA | hardware doc |
| RTC backup battery charging | ≈+200 µA | code comment |

Two anti-brick observations ([ADR 0015](../../adr/0015-anti-brick-policy.md)):

- The vendor's deep-sleep pin list is **USB-safe**: it contains display, I²C, I²S, mic, IR, LoRa, GPS and SPI pins, and *not* GPIO19/20. A vendor library that does the right thing here is worth recording, because the naive `gpio_reset_pin()` loop over a range is exactly what ADR 0015 rule 2 forbids.
- The same list **does** contain `DISP_BL` (GPIO45): `gpio_reset_pin()` then `pinMode(OPEN_DRAIN)` leaves the VDD_SPI strap in a state decided by the pull network across the wake reset. On this unit `VDD_SPI_FORCE = 1` ([ADR 0016](../../adr/0016-backlight-gpio45-vdd-spi-strap.md)), so it is harmless; on a unit where the eFuse is not forced it is precisely the hazard ADR 0016 exists for. Keep the per-unit check.

### 3.8 One datasheet discrepancy worth recording

`setDC3Voltage(3300)` encodes `0x84 ← 0x69` (105) using XPowersLib's third DCDC3 range, 1.6–3.4 V at 100 mV/step from base 88. The **filed** AXP2101 PDF — revision 1.0, 2022-11-04, the *SWcharge* variant ([01 #17](../../bibliography/01-datasheets.md), Waveshare mirror) — documents REG 84 as 0.5–1.54 V only, with codes `1011000`–`1111111` (88–127) **reserved**. XPowersLib mirrors `AXP2101_Datasheet_V1.4_en.pdf` in its own `datasheet/` folder, which evidently documents the wider DCDC3 range; LilyGO ships DC3 = 3.3 V on real GPS hardware, so the wider range is real on the part we have. Everything else we touch (`0x15`, `0x16`, `0x18`, `0x19`, `0x24`, `0x26`, `0x27`, `0x30`, `0x61`–`0x64`, `0x68`–`0x6A`, `0x80`, `0x82`, `0x90`–`0x9A`) matches between the two documents bit for bit. **Action:** note the variant mismatch in bibliography 01 #17 and acquire `AXP2101_Datasheet_V1.4_en.pdf` in the next D3 pass. Nothing is blocked — we never enable DC3.

## 4. Display — the init argument list, the vendor command list, rotation and offset

### 4.1 The call

`LilyGoWatchS3.cpp` calls `LilyGoDispSPI::init(DISP_SCK, DISP_MISO, DISP_MOSI, DISP_CS, DISP_RST, DISP_DC, DISP_BL, 80)`. Note the last argument: **80 MHz**, overriding the class default `CONFIG_SPI_MAX_FREQ = 20`.

| Stage | Field | Vendor value | Our gate (2026-08-20) |
|---|---|---|---|
| `spi_bus_config_t` | host | **`SPI3_HOST`** (`SPI2_HOST` only on T-LoRa-Pager) | `SPI2_HOST` |
| | `miso_io_num` | `DISP_MISO` — panel MISO is *not connected* on this board | `-1` |
| | `max_transfer_sz` | `240 × 80 × 2` = 38 400 B | `240 × 40 × 2` = 19 200 B |
| | DMA | `SPI_DMA_CH_AUTO` | same |
| `esp_lcd_panel_io_spi_config_t` | `spi_mode` | 0 | 0 |
| | `pclk_hz` | **80 000 000** | 20 000 000 |
| | `trans_queue_depth` | 2 | 2 |
| | `on_color_trans_done` | `NULL` — every draw is blocking | `NULL` |
| | `lcd_cmd_bits` / `lcd_param_bits` | 8 / 8 | 8 / 8 |
| `esp_lcd_panel_dev_config_t` | `reset_gpio_num` | `DISP_RST` (panel reset not connected → follows the ALDO3 rail) | `GPIO_NUM_NC` |
| | `bits_per_pixel` | 16 | 16 |
| | element order / endian | `LCD_RGB_ELEMENT_ORDER_RGB`, `LCD_RGB_DATA_ENDIAN_LITTLE` | `RGB` |
| | **`flags`, `vendor_config`** | **never initialised** — the struct is declared `esp_lcd_panel_dev_config_t panel_config;` with no `= {}` and only three or four members assigned | brace-initialised |
| after `esp_lcd_panel_init()` | inversion | `esp_lcd_panel_invert_color(panel, true)` | same |
| | gap | `set_gap(0, 0)` … then overwritten by `setRotation(0)` → `(0, 80)` | `set_gap(0, 0)` |
| | orientation | `swap_xy(false)`, `mirror(true, false)` … then `setRotation(0)` → `mirror(true, true)` | `swap_xy=false, mirror_x=false, mirror_y=false` |
| | display on | `esp_lcd_panel_disp_on_off(panel, true)` | via `esp_lvgl_port` |

The uninitialised `panel_config` is a genuine defect, not a style point: on the `ESP_ARDUINO_VERSION > 4.0.0` path `vendor_config` and `flags.reset_active_high` are read by `esp_lcd_new_panel_st7789()` from stack garbage. Do not copy the pattern; brace-initialise.

The screen is then cleared with `std::vector<uint16_t> draw_buf(_width * _height * 2, 0)` — **twice** the pixels needed (230 400 B for a 240×240 RGB565 frame) — and pushed with a single `draw_bitmap(0, 0, 240, 240, …)`.

### 4.2 The vendor ST7789 command list

Sent by `esp_lcd_panel_io_tx_param()` **after** `esp_lcd_panel_init()` has already run the driver's own init, so several commands are duplicated. `len & 0x80` means "delay 120 ms after this command"; `len & 0x7F` is the parameter count.

| Cmd | Params | Conventional name | Note |
|---|---|---|---|
| `0x11` | — (+120 ms) | SLPOUT | second sleep-out; the IDF driver already sent one |
| `0xB2` | `1F 1F 00 33 33` | PORCTRL | porch control |
| `0x35` | `00` | TEON | tearing-effect line **on**, mode 0 — but TE is not wired to a GPIO on this board |
| `0x36` | `00` | MADCTL | **written behind `esp_lcd`'s back** — desynchronises the driver's cached MADCTL from the panel |
| `0x3A` | `05` | COLMOD | 16 bit/pixel, 65 k colours |
| `0xB7` | `00` | GCTRL | gate control |
| `0xBB` | `36` | VCOMS | |
| `0xC0` | `2C` | LCMCTRL | |
| `0xC2` | `01` | VDVVRHEN | |
| `0xC3` | `13` | VRHS | |
| `0xC4` | `20` | VDVS | |
| `0xC6` | `13` | FRCTRL2 | **frame-rate control** — the number that caps the panel's own refresh; map it against the ST7789V3 table ([01 #13](../../bibliography/01-datasheets.md)) before ADR 0007's 50 Hz budget leans on anything |
| `0xD6` | `A1` (sent **twice**) | — | not a documented ST7789 command in the public specification |
| `0xD0` | `A4 A1` | PWCTRL1 | |
| `0xE0` | 14 bytes | PVGAMCTRL | positive gamma |
| `0xE1` | 14 bytes | NVGAMCTRL | negative gamma |
| `0xE4` | `1D 00 00` | GATECTRL | `NL = 0x1D` ⇒ 240 gate lines, `SCN = 0` *(reading per the ST7789 GATECTRL definition — confirm against 01 #13)* |
| `0xFF` | — | terminator | |

There is **no `0x21` (INVON)** in the active list — inversion comes from `esp_lcd_panel_invert_color(panel, true)`, which is what our gate does. A disabled `#if 0` alternative list in the same file *does* include `0x21` and a different `0x36` value (`0x08`), i.e. a different colour order; it is dead code for a different panel lot.

### 4.3 Rotation and offset — and why the gate's image is upside down relative to the vendor's

`LilyGoDispSPI::setRotation()`:

| rotation | `set_gap(x, y)` | `swap_xy` | `mirror(x, y)` |
|---|---|---|---|
| 0 | **(0, 80)** | false | (true, **true**) |
| 1 | (0, 0) | true | (true, false) |
| 2 | **(0, 0)** | false | **(false, false)** |
| 3 | (80, 0) | true | (false, true) |
| *(init-time, before `setRotation`)* | (0, 0) | false | (true, false) |

`begin()` ends with `setRotation(0)`, so the vendor's shipped orientation is row 0. The 80-pixel gap is the 240×240 window inside the ST7789's 240×320 GRAM: with `MY = 1` the controller addresses rows from the far end, so the offset is needed; with `MY = 0` it is not.

**Our gate ran `set_gap(0, 0)` with `swap_xy = false, mirror_x = false, mirror_y = false` — which is exactly LilyGoLib rotation 2, i.e. rotated 180° from the vendor's rotation 0.** The frame was "confirmed visually" in the gate, which proves the geometry is self-consistent, not that it is the right way up relative to the crown. `twatch_display.c` must pick an orientation deliberately, against the crown position, and the pair `(mirror_y, y_gap)` must always move together: `mirror_y = true ⇒ y_gap = 80`, `mirror_y = false ⇒ y_gap = 0`. Getting one without the other yields an 80-pixel band of garbage at one edge — the classic ST7789 240×240 symptom.

This also matters for [ADR 0007](../../adr/README.md): the hardware vertical-scroll registers (`VSCRDEF 0x33` / `VSCSAD 0x37`) address the same 320-line GRAM the gap compensates for, so the scroll-axis verification must be done in the *final* orientation, not in the init-time one.

### 4.4 Backlight

`ledcAttach(DISP_BL, LEDC_BACKLIGHT_FREQ = 1000 Hz, LEDC_BACKLIGHT_BIT_WIDTH = 8)`; on the pre-IDF-5 path, LEDC channel 3. Brightness range is `BrightnessController<LilyGoWatch2022, 0, 255, 5>` — min 0, max 255, default step delay 5 ms.

- `incrementalBrightness(250, 20)` — the call our rail table cites as "ramped" — is a **LEDC duty ramp**, not a rail ramp: 250 single-step increments at 20 ms each ≈ **5 s** from black to 250/255. (The gate's ramp is 0→160 in steps of 8 at 20 ms ≈ 0.4 s at 5 kHz.) Correct the wording in [`docs/hw/twatch-s3-pins.md`](../../hw/twatch-s3-pins.md): the rail is switched, the *duty* is ramped.
- `LilyGoDispSPI::setBrightness()` has a hidden coupling: level 0 also sends **SLPIN** (`0x10`), and any non-zero level from a zero level sends **SLPOUT** (`0x11`). A backlight API that silently sleeps the panel is a trap for a redraw loop; keep the two concerns separate in `twatch_display.c`.
- `_brightness` is a public `uint8_t` that the `LilyGoDispSPI` constructor never initialises, so the first `incrementalBrightness()` reads an indeterminate start value.

## 5. PDM microphone path

### 5.1 `initMicrophone()` — two different drivers, two different slot answers

```
ESP-IDF < 5.0 :  mic.init(MIC_SCK, MIC_DAT)                       // src/PDM.cpp, legacy driver/i2s.h
ESP-IDF >= 5.0:  mic.setPinsPdmRx(MIC_SCK, MIC_DAT);
                 mic.begin(I2S_MODE_PDM_RX, 16000,
                           I2S_DATA_BIT_WIDTH_16BIT,
                           I2S_SLOT_MODE_MONO, I2S_STD_SLOT_LEFT); // arduino-esp32 ESP_I2S (LGPL — not read)
```

### 5.2 The legacy path, in full (`PDM::init`, MIT, readable)

| Field | Value | Comment |
|---|---|---|
| `mode` | `I2S_MODE_MASTER \| I2S_MODE_RX \| I2S_MODE_PDM` | |
| `sample_rate` | `MIC_I2S_SAMPLE_RATE` = **16000** | header comment: "*!The PDM microphone can only be up to 16KHZ and cannot be changed*" |
| `bits_per_sample` | 16 | |
| `channel_format` | **`I2S_CHANNEL_FMT_ONLY_RIGHT`** | contradicts the ≥5.0 path's `I2S_STD_SLOT_LEFT` |
| `communication_format` | `I2S_COMM_FORMAT_STAND_PCM_SHORT` | |
| `intr_alloc_flags` | `ESP_INTR_FLAG_LEVEL1` | |
| `dma_buf_count` / `dma_buf_len` | 6 / 512 | 6 × 512 × 2 B = 6 144 B ring = 3 072 samples = **192 ms** at 16 kHz |
| `use_apll` | **`true`** | the ESP32-S3 **has no APLL** (PLAN §2 correction 4) — vendor code that cannot mean what it says on this silicon |
| pins | `bck_io_num = NO_CHANGE`, **`ws_io_num = sck_pin` (44)**, `data_in_num = data_pin` (47), `data_out_num`/`mck_io_num = NO_CHANGE` | in the legacy driver the PDM clock is emitted on the **WS** pin |
| port | `MIC_I2S_PORT = I2S_NUM_0` | header comment: "*!The PDM microphone can only use I2S channel 0 and cannot be changed*" |

`PDM::recordWAV(sec)` allocates `ps_malloc(sec × 32000 + 44)` in PSRAM, writes a `PCM_WAV_HEADER_DEFAULT(size, 16, 16000, 1)` header and does **one blocking `i2s_read()` of the whole take** — 5 s = 160 044 B.

`Player::init` (the MAX98357A side, for contrast): 44 100 Hz, 16-bit, `I2S_CHANNEL_FMT_ALL_RIGHT`, `dma_buf_count = 4`, `dma_buf_len = 1024`, `use_apll = false`, `tx_desc_auto_clear = true`, pins BCLK 48 / WS 15 / DOUT 46, port `I2S_NUM_1`. On the ≥5.0 path `initAmplifier()` calls `player.begin(I2S_MODE_STD, 160000, …)` — **160 000 Hz**, an obvious digit slip for 16 000; the rate is overwritten by `playWAV()` from the WAV header before anything is heard, which is why the typo survives.

### 5.3 The slot question is *not* answered by this vendor

Three vendor artefacts, three different answers:

1. `PDM.cpp` (legacy): `I2S_CHANNEL_FMT_ONLY_RIGHT`.
2. `initMicrophone()` (IDF ≥ 5): `I2S_STD_SLOT_LEFT`.
3. `examples/factory/hal_interface.cpp`: reads `FFT_SIZE × 2` int16 (`FFT_SIZE = 512`, `SAMPLE_RATE = 16000`), then de-interleaves even/odd indices into `left_channel[]` and `right_channel[]` and runs two FFTs — **treating a mono PDM stream as interleaved stereo**. What it actually produces is two ×2-decimated copies of the same signal, aliased above 4 kHz. (The same function also calls `dsps_cplx2reC_fc32()` after a full complex FFT of a real-only input, which is the two-real-signals unpack applied to one signal.)

So **open question H-slot stays open** and remains an E2 bench item, as [`docs/hw/twatch-s3-pins.md`](../../hw/twatch-s3-pins.md) already says. The one thing the vendor *does* settle is the constraint, not the value: PDM RX is I2S0-only and 16-bit — asserted twice in LilyGoLib's own comments, independently of the `ESP_RETURN_ON_FALSE` guards in `esp_driver_i2s/i2s_pdm.c` that ADR 0003 cites.

The 16 kHz ceiling is confirmed to be exactly what PLAN §2 calls it — a **legacy-driver artefact**, traceable to one `#define` and one comment in `PDM.h`, with no datasheet basis (the SPM1423 clock window is 1.0–3.25 MHz, [01 #9](../../bibliography/01-datasheets.md)). Nothing in LilyGoLib argues against 32 kHz/`DSR_8S`.

## 6. Confirms and contradicts — against `docs/hw/twatch-s3-pins.md` and the gate

### 6.1 Confirmed

| Fact | Confirmation |
|---|---|
| Pin map (I²C 10/11 · touch 39/40/16 · display 12/13/18/38/45, MISO+RESET NC · mic CLK 44 / DATA 47 · amp 48/15/46 · IR 2 · LoRa 3/4/1/8/7/5/9 · PMU IRQ 21 · RTC IRQ 17 · BMA423 INT 14) | LilyGoLib `docs/hardware/lilygo-t-watch-s3.md` table, identical to ours |
| I²C addresses `0x34` PMU, `0x19` BMA423, `0x51` PCF8563, `0x5A` DRV2605L on bus 0; `0x38` FT6336U on bus 1 | vendor table + the gate's own scan (`I2C0 devices: 0x19 0x34 0x51 0x5A`, `I2C1 devices: 0x38`) |
| `IC_TYPE = 0x4A` at `0x03` | `XPOWERS_AXP2101_CHIP_ID`; gate read `0x4A` |
| Rail map DC1 = SoC · ALDO2 = backlight · ALDO3 = display + touch · ALDO4 = radio · BLDO2 = DRV2605L enable · VBACKUP = RTC cell | vendor comment block + hardware doc + the register table above |
| Charge current cap < 130 mA | vendor doc's warning; `0x62 ← 5` = 125 mA |
| 470 mAh cell | `BATTERY_PARAMS_470mAh[]` and `calibrationPMU(_is_watch_plus ? 940 : 470)`; hardware doc "Battery capacity 470 mA" |
| Panel is ST7789V3, 240×240, colours inverted | hardware doc + `esp_lcd_panel_invert_color(true)`; matches the gate |
| `rgb_ele_order = RGB` | vendor sets `LCD_RGB_ELEMENT_ORDER_RGB`; matches the gate |
| PDM RX is I2S0-only, 16-bit; amp on I2S1 | `PDM.h` comments + `PLAYER_IS2_PORT = I2S_NUM_1` |
| FT6336U (not FT5336) at `0x38`, no reset pin | `TouchDrvFT6X36`, `touch.setPins(-1, TP_INT)`, doc note "*T-Watch-S3 does not have a touch reset pin connected*" — closes **H-touch** on paper in LilyGoLib's favour |
| PMU IRQ handler attached **after** all rail work | `initPMU()` ends with `pinMode` + `attachInterrupt` |
| PSRAM is 8 MB | `while (!psramFound())` gate in `begin()`; capacity from our own `esp_psram` log |

### 6.2 Contradicts or corrects

| Our text | What the vendor sources actually show | Action |
|---|---|---|
| pins doc: rail order "ALDO3 → settle → … → ALDO2 last … **Source: LilyGoLib `initPMU()`**" | LilyGoLib enables **ALDO2 before ALDO3**, with no delay anywhere | Keep our order; fix the provenance sentence (§3.3) |
| pins doc: unused rails "**explicitly disabled** at boot" attributed to the vendor flow | LilyGoLib leaves **DC3, DC4, BLDO1 enabled** on every board | Keep our policy; mark it as ours |
| pins doc: "ALDO2 … ramped (LilyGoLib `incrementalBrightness(250, 20)`)" | that is a 5 s **LEDC duty** ramp, not a rail ramp | Reword (§4.4) |
| pins doc: rail table lists **DLDO1 as unused** | `powerControl(POWER_SPEAK, …)` toggles **DLDO1**; TTGO's `t-watch-s3` branch comments `enableDLDO1(); //! Speaker`; `RecordWAV.ino` says "*Turn on the audio power, the default is off*" before playback | **Partially closes H-rail** — see §6.3 |
| pins doc: battery "470 mAh @ **3.8 V**" | nominal 3.8 V, but the charger is programmed to a **4.35 V** CV target | Add the CV target to the rail table; it moves the autonomy metric |
| [ADR 0015](../../adr/0015-anti-brick-policy.md) §10 + [01 #17](../../bibliography/01-datasheets.md): "XPowersLib's init arms a 4 s PMU watchdog that power-cycles the SoC if not fed" | Neither `XPowersAXP2101::init()`/`initImpl()` (which only reads `0x03` and calls `disableTSPinMeasure()`), nor SensorLib's `AXP2101Core::initImpl()` (identical), nor LilyGoLib's `initPMU()` touches `0x18` bit0 or `0x19`. The datasheet default of `0x18` bit0 is **0 (disabled)**; `0x19[2:0]` defaults to `110b` = **64 s**, not 4 s; `0x19[5:4]` defaults to `00` = **IRQ only, no reset**. The 4 s figure comes from `XPowersLib/examples/ESP_IDF_Example/main/port_axp2101.cpp` — a *different board's* example — which calls `setWatchdogTimeout(WDT_TIMEOUT_4S)` + `enableWatchdog()` with its `setWatchdogConfig(...)` line **commented out**, so even there it would only raise an IRQ | **Amend ADR 0015 §10:** the decision (do not arm it) is unchanged and still right; the premise is wrong. Correct wording: "*XPowersLib's IDF example arms a 4 s PMU watchdog; the library's own init does not, and the AXP2101 powers up with the watchdog disabled (`0x18` b0 = 0), 64 s timeout and reset action 'IRQ only'. We leave all three at their defaults.*" |
| gate README: "`LDO_ONOFF_CTRL0` read `0x2F` on arrival (ALDO1–4 + BLDO2 already on — **the vendor firmware's state survives an ESP reset** because the PMU is not reset with the SoC)" | The observation and the operational conclusion are right; the *mechanism* has a simpler candidate. The datasheet marks every `0x90` enable bit `Reset: System Reset, Default: **EFUSE**` — the power-up value is factory-programmed in the PMU. `0x2F` = ALDO1+ALDO2+ALDO3+ALDO4+BLDO2, which is exactly the boot-on set Zephyr's `twatch_s3` device tree declares, and matches **no** vendor firmware sequence studied here: LilyGoLib's leaves `0x3E` (ALDO1 off, BLDO1 on) and TTGO's current `t-watch-s3` branch leaves `0xBF` (+BLDO1 +DLDO1) | Reword the gate README's parenthetical to "*the PMU's eFuse-programmed power-up state (and/or a prior firmware's writes) — the PMU is not reset with the SoC either way*". **The conclusion "do not rely on that: set voltages and enable explicitly" stands and is now better justified**, since the eFuse defaults differ per board lot |
| pins doc: PSRAM/flash "QSPI" wording in LilyGoLib "loses" | Re-confirmed: the vendor hardware doc still says "Flash 16MB(QSPI) / PSRAM 8MB (QSPI)" while our unit is octal PSRAM (`esp_psram: Found 8MB PSRAM device, Speed: 80MHz`) and 3.3 V `ef 4018` flash | No change; the note stands |
| ADR 0015 consequence: "the crown is long-pressed (the AXP2101 power-off, **6 s**)" | 6 s is the datasheet POR default of `0x27[3:2]`; **LilyGoLib programs 4 s**, while LilyGoLib's own hardware document tells the user "press for 6 seconds to shut down" | Our firmware writes `0x27` explicitly, so we choose; state the chosen value in `twatch_bsp` and in ADR 0015's consequence bullet |
| pins doc H-lcd: "tolerated pixel clock (20 → 80 MHz stepping)" | The vendor ships **80 MHz** (`pclk_hz = 80 MHz`, `SPI3_HOST`, GPIO-matrix routed, no MISO). Our gate proved 20 MHz on `SPI2_HOST` | 80 MHz is *achievable* on this panel per vendor evidence; still measure our own stepping before ADR 0007 depends on it |

### 6.3 H-rail — half closed on paper

`RecordWAV.ino` records 5 s from the PDM microphone **before** it calls `powerControl(POWER_SPEAK, true)`, and `initPMU()` has explicitly executed `disableDLDO1()`. Therefore:

- **DLDO1 supplies the audio output path (MAX98357A), not the microphone.** Two independent witnesses: LilyGoLib's `POWER_SPEAK → DLDO1` mapping (with a `// TODO:` beside it) and TTGO's `enableDLDO1(); //! Speaker`.
- **The SPM1423 is on a rail that is on before any firmware runs** — it is not ALDO2/3/4, not BLDO1/2, not DLDO1, not DC3/DC4. The remaining candidate is the 3.3 V system rail (DC1/VDD3V3). *(prov.)* until the schematic sheet is read.

Consequences for `twatch_bsp`: disabling DLDO1 at boot is safe for v1 (no playback) and **does not silence the microphone** — a real risk that this reading removes. If the amplifier is ever used, DLDO1 must be enabled and its voltage set first (LilyGoLib never sets `0x99`, so it would run at the eFuse default). And if the mic is indeed on the always-on 3.3 V rail, then GPIO47 sits at 3.3 V, consistent with the eFuse reading `VDD_SPI_FORCE = 1` on this unit ([ADR 0016](../../adr/0016-backlight-gpio45-vdd-spi-strap.md)).

## 7. What transfers to `twatch_bsp`, and what must not be copied

**Transfers (as a specification, re-implemented in C99 over `i2c_master_bus_handle_t`):**

- The whole §3.2 table: addresses, masks, encodings, and the `(mV − 500)/100` LDO rule. That is the ~300-line driver's content.
- The "voltages before enables" discipline, and never writing `0x80` bit0 (DC1).
- `disableTSPinMeasure()` as a mandatory step — this board has no NTC on the TS pin, and the datasheet warns that leaving TS measurement on causes abnormal charging. Both XPowersLib and SensorLib do it inside `init()`; a hand-written driver must not forget it.
- IRQ discipline: mask-all → enable-wanted → clear-all → attach the pin last; `INTSTS1` is the low byte.
- The display argument list of §4.1 (with `flags`/`vendor_config` brace-initialised), the command list of §4.2 as a *starting point to bisect against* the in-tree `esp_lcd` ST7789 init, and the `(mirror_y, y_gap)` pairing of §4.3.
- The mic constraint (I2S0, 16-bit) and the rail knowledge of §6.3.

**Must not be copied:**

- **Any pin macro** — they are LGPL (§2).
- `use_apll = true` for PDM RX (no APLL on the S3), `160000` as an I²S sample rate, the "16 kHz maximum" comment.
- The factory example's audio maths: mono-as-stereo de-interleave, `dsps_cplx2reC_fc32` after a real-only complex FFT, symmetric `dsps_wind_hann_f32` (ADR 0006 requires periodic windows), and the `(dB + 40)/40` normalisation with no window or one-sided correction.
- The uninitialised `esp_lcd_panel_dev_config_t`, the 2× over-allocated clear buffer, the raw `0x36` MADCTL write behind `esp_lcd`'s cached state, and `setBrightness(0) ⇒ SLPIN`.
- The blocking `portMAX_DELAY` single-shot `i2s_read()` of a whole take with no `on_recv_q_ovf` callback (same finding as the [xiao-edge-audio notes](xiao-edge-audio_notes.md) §2.2 — two independent precedents, both silently dropping DMA overruns).
- `calibrationPMU()` — a one-way write to the PMU's gauge ROM; ADR-gated if ever wanted (§3.6).
- Enabling DC3/DC4/BLDO1 on a board that has no GPS.
- The AXP2101 watchdog, for the reason ADR 0015 already gives (a flash write or a debugger halt must never race a PMU reset) — but with the corrected premise of §6.2.

## 8. Status of the open questions this study touched

| # | Question | Status after this study |
|---|---|---|
| H-rail | Which rail powers the SPM1423 and the MAX98357A? | **Amp = DLDO1** (two vendor witnesses); **mic = an always-on 3.3 V rail, not any switchable LDO** (RecordWAV ordering). Both *(prov.)* until the schematic sheet is read in D3/D4 |
| H-touch | FT6336U vs FT5336 | **FT6336U**, `0x38`, no reset pin — LilyGoLib code + doc; matches the gate's `I2C1 devices: 0x38` |
| H-lcd | Tolerated pixel clock | Vendor ships **80 MHz**; our gate proved 20 MHz. Still a bench stepping test (E2) |
| H-slot | PDM slot mask | **Still open** — the vendor contradicts itself three ways (§5.3). E2 bench item, unchanged |
| H-batt | 470 vs 400 mAh | 470 mAh from two vendor sources; **plus** a 4.35 V CV target that our documentation did not record |
| H-R8 | R8 vs R8V | Already closed by the eFuse read (`VDD_SPI_FORCE = 1`, 3.3 V); §6.3's mic-rail reading is consistent with it |
| — | AXP2101 datasheet variant | The filed PDF is the **SWcharge v1.0** variant and disagrees with XPowersLib on REG 84's upper range (§3.8). Acquire `AXP2101_Datasheet_V1.4_en.pdf`; nothing blocked |

Reference basis: LilyGoLib `38e6f8d` (`src/LilyGoWatchS3.cpp`, `src/LilyGoDispInterface.cpp`, `src/PDM.{h,cpp}`, `src/BrightnessController.h`, `docs/hardware/lilygo-t-watch-s3.md`, `examples/peripheral/RecordWAV`, `examples/factory/hal_interface.cpp`) and XPowersLib `d699758` (`src/REG/AXP2101Constants.h`, `src/XPowersAXP2101.hpp`, `src/XPowersParams.hpp`, `examples/ESP_IDF_Example/main/port_axp2101.cpp`) — [bibliography 06 #4 and #8](../../bibliography/06-reference-projects.md); TTGO_TWatch_Library `9884d62` branch `t-watch-s3` and SensorLib `2b9e591` as second witnesses ([06 #5](../../bibliography/06-reference-projects.md), [06 #7](../../bibliography/06-reference-projects.md)); AXP2101 register semantics and reset defaults from the filed datasheet ([01 #17](../../bibliography/01-datasheets.md), §6.13.2); ST7789V3 command names to be confirmed against [01 #13](../../bibliography/01-datasheets.md); measured facts from [`docs/hw/README.md`](../../hw/README.md), [`docs/hw/twatch-s3-pins.md`](../../hw/twatch-s3-pins.md), [ADR 0016](../../adr/0016-backlight-gpio45-vdd-spi-strap.md), [ADR 0017](../../adr/0017-no-radio-in-v1-trimmed-component-set.md) and [`firmware/idf-gate/README.md`](../../../firmware/idf-gate/README.md) (2026-08-20/21).
