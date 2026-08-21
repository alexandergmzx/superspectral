# SensorLib — study notes (D4 reference-project loop)

- **Project:** `lewisxhe/SensorLib` — "Commonly used I2C & SPI sensor drivers for ESP-IDF / Arduino" ([bibliography 06 #7](../../bibliography/06-reference-projects.md))
- **Two trees studied, and they are not the same code:**
  - **GitHub master** at `2b9e591f245e447d3d00ec8798c3f49b897882d9` (2026-07-30, "fix(arduino): handle STM32 typed GPIO API compatibility"; the shallow clone holds this single commit). Clone: `docs/reference-projects/clones/SensorLib/` (gitignored). Its `idf_component.yml` still says `version: "0.4.1"` — master is **unreleased work on top of 0.4.1**, not a newer release.
  - **The registry release we actually link**, `lewisxhe/sensorlib 0.4.1`, packed 2026-04-02, `component_hash eb4217bd…c27d3` ([`dependencies.lock`](../../../firmware/twatch-s3/dependencies.lock)), unpacked at `firmware/twatch-s3/managed_components/lewisxhe__sensorlib/` (gitignored, like every managed component — see [`firmware/twatch-s3/README.md`](../../../firmware/twatch-s3/README.md)).
  Everything below states **which tree** a fact comes from. Where they differ, the registry tarball is normative for us: it is what `~0.4.1` resolves to and what the E1 gate built ([ADR 0001](../../adr/0001-toolchain-esp-idf-v6-pinned-environment.md)).
- **Licence:** **MIT** for SensorLib itself, confirmed from `LICENSE` ("Copyright (c) 2022 lewis he", standard MIT). The vendored Bosch code under `src/bosch/` is **not uniformly BSD-3-Clause** — see §4.2, which is the main licence finding of this study.
- **Studied:** 2026-08-21, against the pinned ESP-IDF v6.0.2 tree (`~/esp/idf/v6.0.2`) and the configured `firmware/twatch-s3` build. Compile evidence in §6.4 was produced with the project's own `build/compile_commands.json` flags.
- **Feeds:** ADR 0018 (project-study ADR), [ADR 0012](../../adr/README.md) (hands-free interaction — BMA423 wrist-raise), ADR 0004 (split licensing — the Bosch licence question), component [`twatch_bsp`](../../../firmware/twatch-s3/components/twatch_bsp/README.md), [`NOTICE`](../../../NOTICE).

## 1. What it is

A header-dominant C++ driver collection for ~40 I²C/SPI parts (Bosch BMA4xx/BHI/BMM, FocalTech/Goodix/Chipsem touch, PCF8563/PCF85063 RTC, DRV2605/AW86224 haptics, XL9555, QMI8658, X-Powers/TI/Silergy PMICs). It is the only maintained, Arduino-free, registry-published source of the **Bosch BMA4 Sensor API plus the BMA423 binary feature-config blob**, which is the whole reason ADR 0001 pins it. Four of the parts it covers sit on our board: BMA423 `0x19`, PCF8563 `0x51`, DRV2605L `0x5A` on I²C0 and the FT6336U `0x38` on I²C1 ([pins doc](../../hw/twatch-s3-pins.md); all five confirmed present by the E1 gate scan).

Platform abstraction is a three-layer template sandwich: `SensorPlatform.hpp` picks a comm/HAL pair by preprocessor, `platform/comm/*` supplies CRTP-ish mixins (`I2CDeviceWithHal`, `I2CDeviceNoHal`, `SPIDeviceWithHal`), and `platform/{arduino,espidf}/*` implement the leaves. Nothing under `platform/espidf/` includes an Arduino header, and `SensorLib.h` guards `<Arduino.h>`/`<SPI.h>`/`<Wire.h>` behind `#if defined(ARDUINO)`. The library therefore satisfies rule 5 of [CLAUDE.md](../../../CLAUDE.md) (no Arduino on the link line) as shipped.

## 2. The ESP-IDF platform layer

### 2.1 Dispatch and the API-version switch

`src/SensorPlatform.hpp` selects the leaf implementation with `#if defined(ARDUINO) … #elif !defined(ARDUINO) && defined(ESP_PLATFORM)`, then always pulls in `platform/SensorCommCustom.hpp`, `SensorCommCustomHal.hpp` and `SensorCommStatic.hpp`. `beginCommon<CommType, HalType>()` / `beginCommonStatic<>()` are variadic templates that `make_unique` the HAL, the comm object and (for the Bosch parts) the `SensorCommStatic` trampoline that supplies C function pointers to the Bosch C API.

`src/platform/espidf/SensorCommEspIDF_I2C.hpp` chooses the driver at compile time:

```c
#if ((ESP_IDF_VERSION >= ESP_IDF_VERSION_VAL(5,0,0)) && defined(CONFIG_SENSORLIB_ESP_IDF_NEW_API))
#include "driver/i2c_master.h"
#else
#include "driver/i2c.h"
#define SENSORLIB_USE_I2C_LEGACY 1
#endif
```

`CONFIG_SENSORLIB_ESP_IDF_NEW_API` is **mandatory for us, not merely preferred**, and the reason is stronger than "the legacy header is gone": in v6.0.2 `driver/i2c.h` still exists (`components/driver/i2c/include/driver/i2c.h`) and prints *"This legacy I2C driver (driver/i2c.h) is officially END-OF-LIFE (EOL) as of ESP-IDF v6.0"*. Selecting `CONFIG_SENSORLIB_ESP_IDF_OLD_API` would therefore still compile, then install a second, EOL driver on a port `twatch_bsp` already owns through `i2c_master_bus_handle_t` and trip the driver's legacy-conflict check (`CONFIG_I2C_SKIP_LEGACY_CONFLICT_CHECK`, `components/driver/Kconfig`). This sharpens [pitfall B14](../../devenv/pitfalls.md), which currently frames the symbol as a build-compatibility switch.

The new-API constructor takes a **bus handle, not pins** — `SensorCommI2C(i2c_master_bus_handle_t, uint8_t addr, SensorHal * = nullptr)` — and `init_ll_hal()` calls `i2c_master_bus_add_device()` with `dev_addr_length = I2C_ADDR_BIT_LEN_7`, `scl_speed_hz = SENSORLIB_I2C_MASTER_SPEED` (**400 000**, a hard `#define`, not a parameter), `scl_wait_us = 0` and `flags.disable_ack_check = 0`. Transfers are `i2c_master_transmit()` / `i2c_master_transmit_receive()` with **timeout `-1` (wait forever)**. Two consequences for us: 400 kHz is imposed on every SensorLib device on the shared bus, and a stuck slave blocks the calling task indefinitely rather than returning `ESP_ERR_TIMEOUT` — the same anti-pattern the [xiao note](xiao-edge-audio_notes.md) flags for `portMAX_DELAY` I²S reads.

On v6.0.2 `i2c_device_config_t` has exactly the five members SensorLib assigns, so the un-zero-initialised `i2c_device_config_t devConf;` is currently benign; the padding bits of the anonymous `flags` bitfield are still indeterminate, so a future IDF that adds a device flag would read garbage. Worth a line in the [upgrade procedure](../../devenv/upgrade-procedure.md) checklist rather than a patch today.

### 2.2 `SensorCommEspIDF_HW.hpp` — the HAL, and a real defect

`HalEspIDF` maps `pinMode`/`digitalWrite`/`digitalRead` onto `gpio_config()`/`gpio_set_level()`/`gpio_get_level()` (with optional user callbacks), `millis`/`micros` onto `esp_timer_get_time()`, and `delayMicroseconds()` onto `ets_delay_us()`. `delay()` is broken in both trees:

```c
void delay(uint32_t ms) { ets_delay_us((ms % portTICK_PERIOD_MS) * 1000UL); }
```

`portTICK_PERIOD_MS == 1000 / CONFIG_FREERTOS_HZ`. Our `sdkconfig.defaults` sets `CONFIG_FREERTOS_HZ=1000`, so `portTICK_PERIOD_MS == 1` and **`ms % 1 == 0` for every argument: `delay()` is an unconditional no-op**. At the IDF default `FREERTOS_HZ=100` it is merely wrong (`delay(100)` → 0 µs, `delay(5)` → a 5 ms busy-wait). The one call that matters is `SensorBMA4XX::initImpl()`, which does `bma4_soft_reset(); hal->delay(20);` before reading the chip ID — on our build the BMA423 gets **0 ms**, not 20 ms, to come out of soft reset. It is also a busy-wait everywhere else: nothing in the ESP-IDF HAL ever calls `vTaskDelay`, and the Bosch API's `dev->delay_us` is wired straight to `HalEspIDF::delayMicroseconds`, so `bma4_write_config_file()`'s mandatory `delay_us(150 000)` ASIC-init wait is **150 ms of spinning on whichever core calls it**.

Mitigation for `twatch_bsp` (§6.3): construct the BMA423 through the **custom-HAL** constructor and supply our own `delay` callback backed by `vTaskDelay`, or accept the busy-wait but keep every BMA call on core 0 and before the DSP task exists.

### 2.3 Build integration as published

| Item | Registry 0.4.1 | GitHub master `2b9e591` |
|---|---|---|
| `CMakeLists.txt` | 570 B. `SRC_DIRS` = `src`, `src/touch`, `src/platform`, `src/bosch{,/BMM150,/bma4xx,/bhi260x,/bhi36x}`. Nothing else is compiled. | ~250 lines: per-driver `sensorlib_excluded()` gating, `src_dirs` assembled from Kconfig, `EXCLUDE_SRCS`, `target_compile_definitions(SENSORLIB_EXCLUDE_*=1)` |
| `Kconfig` | 18 lines: the `SensorLib_ESP_IDF_API` choice only | The same choice **plus** a "Driver exclusion" menu with **60** `SENSORLIB_EXCLUDE_*` symbols |
| `REQUIRES` | `esp_timer esp_driver_gpio esp_driver_i2c esp_driver_spi driver` | identical |
| `idf_component.yml` | `license: MIT`, `idf >=4.4`, `files.use_gitignore: true`, excludes `examples/`, `tools/`, `tests/`, `docs/`, `datasheet/`, PlatformIO/Arduino metadata | identical |
| README | no exclusion documentation; registry badge reads `v0.4.0` | documents `idf.py menuconfig → Component config → SensorLib Configuration → Driver exclusion` |

`REQUIRES driver` drags the legacy umbrella component into our deliberately trimmed set ([ADR 0017](../../adr/0017-no-radio-in-v1-trimmed-component-set.md)). SensorLib is **not** uniquely responsible: `espressif__esp_lcd_touch` and `espressif__esp_codec_dev` also require `driver`, so removing SensorLib would not remove it. Cost is small in v6.0.2 (the umbrella itself requires only `esp_hal_i2c esp_hal_twai esp_hal_touch_sens`), but it should be recorded, not discovered later.

## 3. Registry tarball vs GitHub tree — the `src/pmic` question, resolved

**The hypothesis is half right, and the half that is wrong is the important half.** `src/pmic` exists in *both* trees. What the registry release lacks is the X-Powers family inside it — i.e. **there is no AXP2101 driver in `lewisxhe/sensorlib 0.4.1` at all** — and what it lacks additionally is any build wiring for the PMIC sources it does ship.

| Evidence | Registry 0.4.1 tarball | GitHub master `2b9e591` |
|---|---|---|
| `find src/pmic -type f \| wc -l` | **34** | **120** |
| `find src/pmic -type d` | `src/pmic`, `silergy/sy6970`, `ti/bq25896` | the same **plus** `xpowers/{axp192,axp1xx,axp202,axp2101,axp517}` |
| files matching `xpowers` (case-insensitive) | **0** | **84** |
| `PmicAXP2101.hpp`, `AXP2101Regs.hpp`, `AXP2101Core.cpp`, … | absent | present (20 files under `src/pmic/xpowers/axp2101/`) |
| `CHECKSUMS.json` (the registry's own manifest of the published archive) | 1 283 files, `created_at 2026-04-02T08:31:31Z`; `src/pmic` = 34 entries, `xpowers` = **0** entries | n/a |
| `src/pmic` in `SRC_DIRS` | **no** — none of the 13 `.cpp` files under `src/pmic` is compiled | yes, gated by `CONFIG_SENSORLIB_EXCLUDE_PMIC_*` |
| `src/haptic_drivers` in `SRC_DIRS` | **no** — `HapticDriver_DRV2605.cpp` (46 out-of-line member definitions) is never compiled | yes (`src/haptic`), gated by `CONFIG_SENSORLIB_EXCLUDE_HAPTIC_DRV2605` |
| Top-level `src/` subdirectories | `bosch haptic_drivers platform pmic sensor touch` (357 files) | `actuator bosch expander gauge haptic pmic platform sensor time touch` (438 files) |
| Objects actually built by our configured project | **52**, listed in `build/esp-idf/lewisxhe__sensorlib/CMakeFiles/__idf_lewisxhe__sensorlib.dir/` — Bosch BHI/BMA/BMM `.c`, 11 touch `.cpp`, `SensorRtcHelper.cpp`, `SensorWireHelper.cpp`, `SensorCommStatic.cpp`, `SensorCommDebug.cpp`, `SensorLibExceptionFix.cpp` | n/a |

Three practical conclusions:

1. **`CONFIG_SENSORLIB_EXCLUDE_*` does not exist at our pin.** `idf.py menuconfig` at 0.4.1 offers only the API-version choice. Any exclusion plan must wait for the release that ships master's Kconfig, or be replaced by an `EXCLUDE_SRCS` override in our own build. Since IDF compiles with `-ffunction-sections -fdata-sections` and links with `--gc-sections`, the *binary* cost of the un-excludable drivers is near zero; the cost is build time (52 objects, 9.0 MB archive) and review surface, not flash.
2. **SensorLib is not an AXP2101 fallback at 0.4.1.** The "schedule-pressure fallback" recorded in [bibliography 06 #7](../../bibliography/06-reference-projects.md), in [ADR 0001](../../adr/0001-toolchain-esp-idf-v6-pinned-environment.md)'s consequences and in [`twatch_bsp/README.md`](../../../firmware/twatch-s3/components/twatch_bsp/README.md) does not exist in the artefact we link. The AXP2101 register cross-check must come from [bibliography 06 #8](../../bibliography/06-reference-projects.md) (XPowersLib, read-only, never added as a component) or from the AXP2101 datasheet ([01 #17](../../bibliography/01-datasheets.md)); the hand-written `twatch_pmu_axp2101.c` is now the only plan, not the preferred one of two.
3. **DRV2605L via SensorLib does not link at 0.4.1.** `SensorDRV2605.hpp` → `HapticDrivers.hpp` → `haptic_drivers/HapticDriver_DRV2605.hpp` resolves (because `src/` is on the include path), but the definitions are in a `.cpp` outside `SRC_DIRS`, so any use is an undefined-reference at link. ADR 0012's haptic confirmation therefore needs either a local `EXCLUDE_SRCS`-free re-registration of that file, a wait for the next release, or a ~60-line DRV2605L driver of our own — a decision ADR 0012 must make explicitly.

Why the divergence: master carries a large post-0.4.1 refactor (new `actuator`/`expander`/`gauge`/`time` trees, `AccelerometerDrv.hpp`-style aggregate headers, the deprecation shims that turn `src/SensorBMA423.hpp` from an 839-line class into a 9-line `#pragma message` alias, and the exclusion machinery). None of it is on the registry as of 2026-08-21. `files.use_gitignore: true` in the manifest is worth remembering as a packaging hazard in general, but it is not the cause here: the tarball's own `CMakeLists.txt` and `Kconfig` are simply the pre-refactor versions.

## 4. The BMA423 driver and the Bosch feature-config blob

### 4.1 Where the blob is and what loading it costs

`src/bosch/bma4xx/bma423.c` (76 581 B, 1 700 lines) opens with `const uint8_t bma423_config_file[] = { … }` — **6 144 bytes** (`BMA423_CONFIG_FILE_SIZE UINT16_C(6144)` in `bma423.h`), confirmed as `.rodata.bma423_config_file  6144` in the compiled object. This is the microcode for the sensor's feature engine; without it the BMA423 is a plain accelerometer with no step counter, no tilt, no wake-up. It cannot be regenerated from a datasheet, which is the whole argument of ADR 0001's "mandatory for the BMA423's Bosch feature blob".

Upload path: `SensorBMA423::boschInitImpl()` → `bma423_init()` → `bma423_write_config_file()` → `bma4_write_config_file()`, which disables advanced power save, clears `BMA4_INIT_CTRL_ADDR`, streams the 6 144 bytes in `dev->read_write_len` chunks (**32** bytes, set by `SensorBMA4XX::initImpl()`, i.e. **192 I²C transactions**), re-enables config loading, waits `delay_us(BMA4_MS_TO_US(150))` and verifies `BMA4_INTERNAL_STAT == BMA4_ASIC_INITIALIZED`. At 400 kHz that is roughly 190 ms of bus time plus the 150 ms wait — and per §2.2 the wait is a busy-wait. Budget ≈350 ms of blocking init and run it before the DSP task exists.

### 4.2 Licence findings for the Bosch part — the one that needs an ADR sentence

SensorLib's `THIRD_PARTY_NOTICES.md` states, for `src/bosch/`: *"BSD 3-Clause License … Copyright (c) 2023 Bosch Sensortec GmbH … The original license text and copyright notices are retained in the header of each source file."* `src/bosch/bma4xx/LICENSE` likewise carries plain BSD-3-Clause (2024 Bosch Sensortec). **Per-file inspection contradicts the blanket claim.** Of the 17 files in `src/bosch/bma4xx/`:

| Files | Header |
|---|---|
| `bma4.c`, `bma4.h`, `bma4_defs.h`, `bma422_an.{c,h}`, `bma456{h,mm,w,_an,_tablet}.{c,h}` (15 files) | `Copyright (c) 2023 Bosch Sensortec GmbH` + **explicit `BSD-3-Clause`** text |
| **`bma423.c`, `bma423.h`** (the two files that carry the blob and the BMA423 API) | `Copyright (C) 2017 - 2018 Bosch Sensortec GmbH` + the **legacy Bosch Sensortec "Disclaimer / Special" notice**, no SPDX identifier, no BSD grant |

The legacy notice is not an open-source licence. Its operative sentences: the software *"is provided free of charge for the sole purpose to support your application work"*; it *"is specifically designed for the exclusive use for Bosch Sensortec products by personnel who have special experience and training"*; *"No license is granted by implication or otherwise under any patent or patent rights of Bosch"*; plus a fitness disclaimer and a purchaser-indemnification clause. It contains **no redistribution permission at all** — neither source nor binary.

What this means for us, stated without pretending to be legal advice:

- (+) Our use is squarely inside the notice's stated purpose: we drive a genuine Bosch BMA423 on a Bosch-supported platform, which is exactly "exclusive use for Bosch Sensortec products".
- (+) The transitive dependency is invisible in the tree — `managed_components/` is gitignored, the bytes arrive from the registry, and nothing of Bosch's is copied into our sources.
- (−) [ADR 0004](../../adr/README.md)'s rule as written ("the firmware link line admits only MIT/BSD/Apache code") is **violated by two files at the pin**, and [`NOTICE`](../../../NOTICE) currently records the Bosch part as flatly "BSD-3-Clause". That line is wrong for `bma423.{c,h}` and must be amended.
- (−) Redistributing a *binary* that embeds the blob (any `.bin` we hand to a third party, and every OTA image) has no express grant. Bosch's own SDK ([bibliography 06 #50](../../bibliography/06-reference-projects.md), [01 #23](../../bibliography/01-datasheets.md)) is catalogued here as BSD-3-Clause; **verify upstream `boschsensortec/BMA423-Sensor-API` directly** — if the upstream repository's current `bma423.c` carries the 2023/2024 BSD-3-Clause header, the clean fix is to state that the same code is available under BSD-3-Clause upstream and cite that, rather than relying on SensorLib's stale copy. If upstream is also legacy-licensed, ADR 0004 needs an explicit named exception for the BMA423 feature blob (vendor-supplied firmware for the vendor's own part, used in the manner the notice describes), and ADR 0012 must weigh that against dropping the feature engine and computing wrist-raise from raw ±2 g / 50 Hz samples on the SoC.
- (−) The mismatch also means SensorLib's `THIRD_PARTY_NOTICES.md` cannot be used as our audit source. Our SBOM step (`esp-idf-sbom`, roadmap E-track CI) must read per-file headers, not the project's summary file.

### 4.3 Features relevant to ADR 0012 (wrist-raise arming)

Feature bits (`bma423.h`): `BMA423_STEP_CNTR 0x01`, `BMA423_ANY_MOTION 0x02`, `BMA423_NO_MOTION 0x04`, `BMA423_ACTIVITY 0x08`, `BMA423_TILT 0x10`, `BMA423_WAKEUP 0x20` — any-motion and no-motion are documented mutually exclusive, and the wrapper enforces that. Interrupt-status bits: `BMA423_STEP_CNTR_INT 0x02`, `BMA423_ACTIVITY_INT 0x04`, `BMA423_TILT_INT 0x08`, `BMA423_WAKEUP_INT 0x20`, `BMA423_ANY_NO_MOTION_INT 0x40`, `BMA423_ERROR_INT 0x80`.

- **Wrist-raise = `BMA423_TILT`**, surfaced as `enableTiltDetector(bool enable, bool interrupt_enable, InterruptPinMap pin_map)`, which maps `BMA423_TILT_INT` to INT1/INT2 and then calls `bma423_feature_enable(BMA423_TILT, …)`. Our INT1 is **GPIO14** ([pins doc](../../hw/twatch-s3-pins.md)); the wrapper's `update()` reads `bma423_read_int_status()` and dispatches `callbacks.onTiltDetected`. This is the primitive ADR 0012 needs: the watch arms a take when the wrist comes up, with no touch during singing.
- **`bma423_select_platform()` / `selectPlatform(Platform::WRISTBAND)` changes tilt behaviour**, not just step counting. `BMA423_PHONE_CONFIG 0x00` vs `BMA423_WRIST_CONFIG 0x01` select two 25-entry parameter sets (`BMA423_{PHONE,WRIST}_SC_PARAM_1…25`); the header's own note on `selectPlatform` reads *"This setting affects tilt detection."* **`WRISTBAND` must be selected explicitly** — nothing in `SensorBMA4XX::initImpl()` or `bma423_init()` does it, and the untouched default is the phone parameter set. This is the single highest-value line of configuration for ADR 0012 and belongs in its decision text.
- **`BMA423_WAKEUP` is tap/double-tap, not wrist-raise.** The wrapper exposes it as `enableTapDetector()` (with `bma423_tap_selection()` for single vs double) and — confusingly — routes `BMA423_WAKEUP_INT` to a callback named `callbacks.onTap`. A double-tap on the case is a plausible *second* hands-free gesture (start/stop a take) that costs nothing extra once the blob is loaded; `bma423_wakeup_set_sensitivity()` tunes it.
- **Step counter:** `enableStepCounter(bool, uint16_t watermark = 1, bool reset)`, `bma423_step_counter_output()` (32-bit), `bma423_reset_step_counter()`, `bma423_activity_output()` (`STATIONARY`/`WALKING`/`RUNNING`). Watermark resolution is **20 steps per unit** (watermark 1 → an interrupt every 20 steps), per the header's own note. Steps are not a Super Spectral feature; the *activity* output is interesting for one narrow purpose — annotating a take with "subject was walking", i.e. a motion-artefact flag for the acoustic path — and `enableFeature()` deliberately co-enables the step **detector** whenever the step counter is enabled, so the two are not independent.
- **Defaults set by `SensorBMA4XX::initImpl()`:** `BMA4_ACCEL_RANGE_2G`, `BMA4_OUTPUT_DATA_RATE_50HZ`, `BMA4_ACCEL_NORMAL_AVG4`, `BMA4_CIC_AVG_MODE` (the low-power averaging mode), operation mode `SUSPEND`, identity axis remap. 50 Hz / ±2 g is the right envelope for tilt and costs little; the power figure for the feature engine still has to come from the datasheet ([01 #22](../../bibliography/01-datasheets.md)) for the ≥3 h autonomy budget.

## 5. The FT6X36 touch driver

`src/touch/TouchDrvFT6X36.{hpp,cpp}` (206 lines of `.cpp`) is a plain FocalTech driver: address `0x38`; `getTouchPoints()` reads `0x02` (TD_STATUS) then bursts `numPoints × 6` bytes from `0x03`, decoding `eventFlag = b[0] >> 6`, `x = (b[0] & 0x0F) << 8 | b[1]`, `touchId = b[2] >> 4`, `y = (b[2] & 0x0F) << 8 | b[3]`, `weight = b[4]`, area `= b[5] >> 4`. Power modes `PMODE_ACTIVE (≈4 mA) / PMODE_MONITOR (≈3 mA) / PMODE_DEEP_SLEEP (≈100 µA)`, the last annotated *"The reset pin must be pulled down to wake up"* — which on our board is unrecoverable, because `T_RST` is unpopulated ([01 #16](../../bibliography/01-datasheets.md)). `beforeBegin()` sets `rstHoldTimeMs = 30`, `rstReleaseTimeMs = 160`.

The part worth taking is the **identity gate**, which is exactly what our chosen touch component lacks:

```
0xA8 VENDOR1_ID  ∈ {0x11, 0xCD, 0x51}
0xA3 CHIP_ID     ∈ {0x06 FT6206, 0x36 FT6236, 0x64 FT6336U, 0x33 FT3267, 0x14 FT5336, 0xA0 FT3068}
0xA6 FIRM_VERS · 0xA1/0xA2 LIB_VERSION · 0x88 PERIOD_ACTIVE · 0x80 THRESHOLD · 0xA9 ERROR_STATUS
```

`espressif/esp_lcd_touch_ft5x06 ~1.1.1` performs **no chip-ID check** ([02 #26](../../bibliography/02-application-notes.md)) — the property that lets us drive an FT6336U with it at all, and simultaneously the property that makes a dead or mis-populated controller look like "no touches". `twatch_bsp` should read `0xA8`/`0xA3`/`0xA6` once during the I²C gate and log/assert `0x64`, then hand the bus to `esp_lcd_touch_ft5x06` for the LVGL-integrated path. Those are documented register numbers — facts, not code — so this needs no SensorLib code on the link line and no second touch driver.

Two defects not to inherit: `_maxTouchPoints = MAX_FINGER_NUM` (**5**) whereas the FT6336U reports at most 2, and the TD_STATUS byte is used whole instead of `& 0x0F`.

## 6. How `twatch_bsp` should consume SensorLib on IDF 6.0

### 6.1 Configuration

- `CONFIG_SENSORLIB_ESP_IDF_NEW_API=y` — currently present in the generated `sdkconfig` **only because it is the Kconfig default**, not because we assert it. Add the line to `sdkconfig.defaults` and to the `sdkconfig-invariants` pre-commit hook, next to the ADR 0015 assertions; a silent flip to `OLD_API` would install an EOL I²C driver behind our back (§2.1).
- Do **not** write `CONFIG_SENSORLIB_EXCLUDE_*` lines yet. At 0.4.1 those symbols do not exist and `kconfgen` will not fail on them — the lines would sit in `sdkconfig.defaults` looking effective and doing nothing, which is worse than not having them. Revisit at the release that ships master's Kconfig, and record `idf.py size --diff` across the change.
- Exclusion, when it becomes available, should be **subtractive from a named list**: keep `BMA4XX`/`BMA423`, `RTC`/`PCF8563`, `HAPTIC_DRV2605`; exclude `IMU` (BHI260/BHI360 are the largest objects here and are not on the board), `MAGNETOMETER`, `LIGHT_SENSOR`, `GAUGE`, `IO_EXPANDER`, `ACTUATOR`, `FINGER_NAVIGATION`, `TOUCH` (we use `esp_lcd_touch_ft5x06`), `PMIC`, `BMA422`, `BMA456H`, `BMA4XX_EXTRA`, `WIRE_HELPER`.

### 6.2 Component wiring

Add `lewisxhe__sensorlib` to `twatch_bsp`'s `REQUIRES` only when the first caller exists (the CMakeLists already says so). The caller must be a **C++ translation unit** — `src/twatch_imu_bma423.cpp` — exposing a C-linkage facade (`twatch_imu_init`, `twatch_imu_enable_wrist_raise`, `twatch_imu_poll`) so the rest of the BSP stays C. Static/`unique_ptr` construction is fine: exceptions and RTTI are off in our build (`CONFIG_COMPILER_CXX_EXCEPTIONS` and `CONFIG_COMPILER_CXX_RTTI` unset) and SensorLib already accommodates both — `SensorLibExceptionFix.cpp` supplies weak `__throw_bad_function_call`/`__throw_length_error`/`__throw_out_of_range` stubs and a nothrow `operator new`, and `SensorCommI2C::setParams()` switches on `#if defined(__cpp_rtti)` to avoid `dynamic_cast`.

Logging inside the library is `ESP_LOG_LEVEL_LOCAL` under the single fixed tag **`"SensorLib"`** (`SensorLib.h`), so `esp_log_level_set("SensorLib", …)` is the only lever; there is no per-driver tag.

### 6.3 Init order

1. `twatch_bsp` owns the I²C0 bus (`i2c_new_master_bus`, SDA 10 / SCL 11) and the AXP2101 rails — SensorLib never creates a bus in the new-API path, which is exactly what we want.
2. Rails up, five-address scan gate (`0x19 0x34 0x51 0x5A`, and `0x38` on I²C1) — already the E1-verified sequence.
3. `SensorBMA423::begin(bus_handle, 0x19)` on **core 0, before the DSP task is created**: soft reset (with the `delay(20)` caveat of §2.2), 6 144-byte blob upload, 150 ms busy-wait ⇒ ≈350 ms blocking.
4. `selectPlatform(Platform::WRISTBAND)`, then `enableTiltDetector(true, /*interrupt_enable=*/true, InterruptPinMap::PIN1)`; ISR on GPIO14 posts to a queue, the UI task calls `update()`.
5. If the `delay(20)` no-op proves to matter on hardware (intermittent chip-ID mismatch at cold boot), switch to SensorLib's custom-HAL constructor and pass a `delay` callback that calls `vTaskDelay(pdMS_TO_TICKS(ms))`. Write it up as a validation item before working around it silently.

### 6.4 Compile-warning contract — measured, 2026-08-21

`twatch_bsp` compiles its own sources with `-Wall -Wextra -Werror -Wshadow -Wconversion -Wdouble-promotion -Wformat=2 -Wvla`. SensorLib's headers do not survive that set, and IDF adds component include dirs with `-I`, not `-isystem`. Measured with the project's own flags from `build/compile_commands.json`, on a one-file TU that includes `SensorPlatform.hpp` + `SensorBMA423.hpp` + `TouchDrvFT6X36.hpp` and calls `begin(bus, addr)` on both:

| Flags | Result |
|---|---|
| SensorLib's own component flags (what the E1 gate exercised) | **clean** — 0 errors, 0 warnings on v6.0.2 |
| \+ the `twatch_bsp` strict set | **73 `-Werror` diagnostics**, all from SensorLib headers: `-Wshadow` (constructor parameters shadowing members throughout `platform/`), `-Wconversion` (`uint32_t`→`uint8_t` in `SensorPlatform.hpp`, `SensorCommEspIDF_*.hpp`) |
| \+ strict set, `-Wno-shadow -Wno-conversion` | still fails: `-Wdouble-promotion` in `SensorBMA4XX.hpp` (`data_rate_hz * 100 + 0.5`, and `%.2f` varargs promotion) and `AccelerometerUtils.hpp:138` (`rad * 180.0f / M_PI`) |
| \+ strict set, SensorLib's include dirs re-added with **`-isystem`** | **clean** — 0 diagnostics, our own strictness fully retained |

So the rule for the BSP is: keep the full strict set for our code and mark SensorLib's include directories as system directories (`target_include_directories(${COMPONENT_LIB} SYSTEM PRIVATE …)` over the component's `INCLUDE_DIRS`, which GCC honours even though the same paths also arrive via `-I`). Do **not** blanket-disable `-Wdouble-promotion` on the file — [CLAUDE.md](../../../CLAUDE.md) names it the high-value warning on this single-precision FPU.

The E1 gate's "zero warnings" result covers SensorLib's own translation units only: `firmware/idf-gate/main/gate_main.c` is C and includes no SensorLib header. Nothing in this repository has yet included one — this study is the first time it was compiled as a consumer.

## 7. What not to copy, and why

- (−) **`HalEspIDF::delay()`.** A no-op at `FREERTOS_HZ=1000` (§2.2). Never reuse the `ms % portTICK_PERIOD_MS` idiom; ours is `vTaskDelay(pdMS_TO_TICKS(ms))` with a busy-wait only below one tick.
- (−) **Infinite I²C timeouts.** `i2c_master_transmit*(…, -1)`. `twatch_bsp`'s own transactions carry a real timeout and surface `ESP_ERR_TIMEOUT` so a wedged bus becomes a task-watchdog panic ([ADR 0015](../../adr/0015-anti-brick-policy.md) item 6), not a silent freeze.
- (−) **The hard-coded 400 kHz `SENSORLIB_I2C_MASTER_SPEED`.** Our bus speed is a `twatch_bsp` decision made once, per bus, next to the rail order.
- (−) **`THIRD_PARTY_NOTICES.md` as an audit source** (§4.2). Per-file headers only.
- (−) **SensorLib's touch stack.** `esp_lcd_touch_ft5x06` already owns the LVGL-integrated path; two touch drivers on one controller is a coherency bug waiting to happen. Take the register numbers for the ID gate, not the driver.
- (−) **`_maxTouchPoints = 5` and the unmasked TD_STATUS byte** (§5).
- (−) **`SensorWireHelper`, the BHI260/BHI360 sensor-hub layer, `SensorRTC_POSIX.hpp`.** None of it is on this board; at 0.4.1 it cannot be excluded, so it must at least never be *called*.
- (−) **Assuming master's API.** `src/SensorBMA423.hpp` is a real class at 0.4.1 and a deprecation shim on master (`#pragma message`, `using SensorBMA423 = ...`); `AccelerometerDrv.hpp`, `PmicXPowers.hpp`, `TouchDrv.hpp` do not exist at our pin. Write against the tarball, and re-read this section at every version bump.

## 8. Corrections to carry into existing documents

| Document | Current statement | Correction |
|---|---|---|
| [bibliography 06 #7](../../bibliography/06-reference-projects.md) | "`src/pmic/xpowers/axp2101` is the schedule-pressure fallback … read `AXP2101Regs.hpp` as the register cross-check" | True of GitHub master; **absent from the registry 0.4.1 tarball**. Point the cross-check at 06 #8 (XPowersLib) or the datasheet |
| [bibliography 11](../../bibliography/11-esp-idf-platform-and-toolchain.md), entry keyed `06 #7` ("SensorLib README (ESP-IDF section) + `Kconfig`") | "the full `CONFIG_SENSORLIB_EXCLUDE_*` matrix that trims the build to BMA423 + PCF8563 + DRV2605 (+ AXP2101 as fallback)" | The matrix exists only on master; 0.4.1's `Kconfig` has the API choice and nothing else |
| [pitfalls H4](../../devenv/pitfalls.md) | "SensorLib 0.4.x absorbed the X-Powers PMIC drivers … `CONFIG_SENSORLIB_EXCLUDE_PMIC_AXP2101=y` if the AXP2101 driver is written in-house" | Neither the driver nor the symbol exists at 0.4.1. The pitfall's *conclusion* (use one library, not both) still holds — for the opposite reason |
| [pitfalls B14](../../devenv/pitfalls.md) | frames `CONFIG_SENSORLIB_ESP_IDF_NEW_API=y` as a build-compatibility switch | On v6.0.2 the legacy path still **compiles**; the real hazard is an EOL second I²C driver and the legacy-conflict check (§2.1) |
| [`NOTICE`](../../../NOTICE) | "includes Bosch BMA4 Sensor API, BSD-3-Clause" | True for 15 of 17 files; `bma423.{c,h}` carry the 2017–2018 legacy Bosch Sensortec notice (§4.2) |
| [`twatch_bsp/README.md`](../../../firmware/twatch-s3/components/twatch_bsp/README.md), [ADR 0001](../../adr/0001-toolchain-esp-idf-v6-pinned-environment.md) consequences | "SensorLib `PmicAXP2101` is the fallback" | No fallback exists at the pin; amend rather than supersede |
| [`main/idf_component.yml`](../../../firmware/twatch-s3/main/idf_component.yml) comment | "the per-driver `CONFIG_SENSORLIB_EXCLUDE_*` trims are added to `sdkconfig.defaults` once the lock exists" | The lock exists; the symbols do not. Note the version they are expected in |

## 9. Alternatives considered for the study (input to ADR 0018)

- *Drop SensorLib and hand-roll a BMA423 driver.* **Rejected.** The 6 144-byte feature blob is not derivable from any datasheet, and without it the tilt/wake engine ADR 0012 depends on does not exist. Revisit trigger: the licence review of §4.2 concluding that the blob may not be redistributed in our binaries — in which case the alternative is not a hand-rolled *feature engine* but wrist-raise computed from raw ±2 g / 50 Hz samples on the SoC, which is a different (and cheaper-to-license) ADR 0012.
- *Vendor `boschsensortec/BMA423-Sensor-API` ([06 #50](../../bibliography/06-reference-projects.md)) directly and skip SensorLib.* **Rejected for now**, kept as the licence escape hatch: it removes the MIT C++ layer we do not need and gives a first-party licence header to cite, at the cost of writing the `bma4_dev` bus/delay shim ourselves (~80 lines) and losing the PCF8563/DRV2605 coverage. Revisit trigger: §4.2's upstream check showing upstream is BSD-3-Clause while SensorLib's copy is not.
- *Track SensorLib's GitHub master (git dependency or vendored) to get the exclusion Kconfig and the AXP2101 driver now.* **Rejected.** ADR 0001 forbids `path:`/git dependencies precisely because they make `dependencies.lock` environment-specific, and master is unreleased, unversioned work. Revisit trigger: a registry release ≥ 0.5.0 carrying the refactor — at which point the pin moves through [`upgrade-procedure.md`](../../devenv/upgrade-procedure.md), not in place.
- *Use SensorLib for touch as well, and drop `esp_lcd_touch_ft5x06`.* **Rejected.** SensorLib's FT6X36 has the better identity gate but no `esp_lcd_touch` handle, so `esp_lvgl_port`'s `lvgl_port_add_touch()` could not consume it and we would own the LVGL input plumbing. We take the register numbers instead (§5). No revisit trigger.
- *Add XPowersLib ([06 #8](../../bibliography/06-reference-projects.md)) alongside SensorLib for the AXP2101.* **Rejected** — but note the recorded reason ("duplicate AXP2101 symbols", pitfall H4) is **not true at 0.4.1**, since SensorLib ships no AXP2101. The surviving reasons are that XPowersLib has no `idf_component.yml` and is not registry-published, so it cannot be pinned or locked. It stays a read-only register reference.

## 10. Facts verified outside the project while studying it

| Fact | Where verified |
|---|---|
| Legacy `driver/i2c.h` still ships in v6.0.2 and announces itself *"officially END-OF-LIFE (EOL) as of ESP-IDF v6.0"*; `CONFIG_I2C_SKIP_LEGACY_CONFLICT_CHECK` and the deprecation-warning suppressor live in `components/driver/Kconfig` | `~/esp/idf/v6.0.2/components/driver/i2c/include/driver/i2c.h`, `components/driver/Kconfig` |
| `i2c_device_config_t` in v6.0.2 has exactly `dev_addr_length`, `device_address`, `scl_speed_hz`, `scl_wait_us`, `flags.disable_ack_check` | `components/esp_driver_i2c/include/driver/i2c_master.h`, v6.0.2 |
| Legacy `driver` umbrella requires only `esp_hal_i2c esp_hal_twai esp_hal_touch_sens`; three registry components in our build require it (`lewisxhe__sensorlib`, `espressif__esp_lcd_touch`, `espressif__esp_codec_dev`) | `components/driver/CMakeLists.txt` v6.0.2; the three managed components' `CMakeLists.txt` |
| `portTICK_PERIOD_MS == 1` in our build (`CONFIG_FREERTOS_HZ=1000`) | [`firmware/twatch-s3/sdkconfig.defaults`](../../../firmware/twatch-s3/sdkconfig.defaults) |
| BMA423 at `0x19` on I²C0 (SDA 10 / SCL 11), INT1 on **GPIO14**; DRV2605L `0x5A`; FT6336U `0x38` on I²C1; all five addresses answered on hardware at the E1 gate | [`docs/hw/twatch-s3-pins.md`](../../hw/twatch-s3-pins.md), [ADR 0001](../../adr/0001-toolchain-esp-idf-v6-pinned-environment.md) |
| C++ exceptions and RTTI are off in this project | `CONFIG_COMPILER_CXX_EXCEPTIONS` / `CONFIG_COMPILER_CXX_RTTI` absent from the generated `sdkconfig` |
| The compiled `bma423.c` object contains `.rodata.bma423_config_file` of exactly 6 144 B; the component archive is 9.0 MB over 52 objects | `xtensa-esp32s3-elf-size -A` on `build/esp-idf/lewisxhe__sensorlib/…/bma423.c.obj`, 2026-08-21 |
| GPIO14 (BMA423 INT1) is a 3.3 V pin on this unit; VDD_SPI is eFuse-forced | [ADR 0016](../../adr/0016-backlight-gpio45-vdd-spi-strap.md), [`docs/hw/README.md`](../../hw/README.md), measured 2026-08-20 |

Reference basis: [bibliography 06 #7](../../bibliography/06-reference-projects.md) (the project), [06 #8](../../bibliography/06-reference-projects.md) (XPowersLib), [06 #50](../../bibliography/06-reference-projects.md) and [01 #23](../../bibliography/01-datasheets.md) (Bosch BMA4xx Sensor API upstream), [01 #22](../../bibliography/01-datasheets.md) (BMA423 datasheet), [01 #16](../../bibliography/01-datasheets.md) (FT6236/FT6336/FT6436 family datasheet), [02 #26](../../bibliography/02-application-notes.md) (`esp_lcd_touch_ft5x06` source and its missing chip-ID gate), [02 #9](../../bibliography/02-application-notes.md) and [02 #10](../../bibliography/02-application-notes.md) (IDF Component Manager manifest / versioning / lock references), [02 #4](../../bibliography/02-application-notes.md) (v6.0 peripherals migration guide), and the SensorLib README + `Kconfig` entry in [bibliography 11](../../bibliography/11-esp-idf-platform-and-toolchain.md); [ADR 0001](../../adr/0001-toolchain-esp-idf-v6-pinned-environment.md), [0015](../../adr/0015-anti-brick-policy.md), [0016](../../adr/0016-backlight-gpio45-vdd-spi-strap.md), [0017](../../adr/0017-no-radio-in-v1-trimmed-component-set.md) and the [ADR backlog](../../adr/README.md) for 0004 and 0012; [`docs/hw/twatch-s3-pins.md`](../../hw/twatch-s3-pins.md) and [`docs/hw/README.md`](../../hw/README.md) for the measured board facts; the clone at `2b9e591`, the registry tarball `0.4.1` (`component_hash eb4217bd…c27d3`) and the pinned ESP-IDF v6.0.2 tree for every call, field, symbol and size named above.
