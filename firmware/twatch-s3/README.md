# T-Watch S3 firmware (ESP-IDF v6.0.x, native)

The on-device half of Super Spectral: PDM capture → windowed FFT → spectrum / spectrogram / f0 / band-energy display, all in real time on the LilyGO T-Watch S3 (ESP32-S3-R8, 8 MB octal PSRAM, 16 MB 1.8 V flash, one Knowles SPM1423 PDM mic, 240×240 ST7789V3). Offline science stays on the host ([`host/`](../../host/README.md), ADR 0002).

**Decision.** Pure ESP-IDF, pinned to **v6.0.2** by [ADR 0001](../../docs/adr/0001-toolchain-esp-idf-v6-pinned-environment.md): no Arduino in any phase, Zephyr rejected (no Espressif PDM driver, board unmaintained), v5.5.5 kept as an escape hatch, and a 30-minute gate build required before feature code. **Trade-off:** we write the AXP2101/board layer ourselves instead of inheriting LilyGoLib's, in exchange for an Apache-2.0-clean link line, the only toolchain in which the PDM microphone works, and the longest support runway of any shipped IDF line (v6.0 EOL 2028-09-20).

> **Status: scaffold (roadmap E0).** Configuration and component contracts are committed; no peripheral code exists yet. **There is no `dependencies.lock` yet — it is generated and committed by the E1 gate build** ([roadmap](../../docs/roadmap/documentation-roadmap.md)). Until then the CI firmware job is `if: false`.
>
> **Scope note.** The plan scoped this pass to config files and component *stubs*. Three C files go one step further and are deliberately kept: `main/app_main.c` (boot guard + TODO list, the one body that must exist from commit one per ADR 0015), `components/twatch_bsp/include/twatch_pins.h` (pin table with `_Static_assert`s — the mechanism the GPIO19/20 rule is enforced by) and `components/spectral_core/include/spectral_core/spectral.h` (**public API sketch, declarations only, no bodies** — the contract that `host-tests/` and the golden-file manifest are written against; ADR 0006/0009). Bodies land in E1. All three are formatted with the committed `.clang-format` (clang-format 20), so the first `pre-commit run -a` is a no-op on them.

## Build

Environment first — [`docs/devenv/setup.md`](../../docs/devenv/setup.md) (manual clone to `~/esp/idf/v6.0.2`, private tools root, activation **only** through the committed `.envrc` via direnv). Then, from this directory:

```bash
idf.py set-target esp32s3          # once; writes sdkconfig from sdkconfig.defaults(.esp32s3)
idf.py build
idf.py -p /dev/ttyTWATCH flash monitor   # udev SYMLINK rule from setup.md; USB-Serial-JTAG
```

CI configurations (also built locally with `idf-build-apps`, config rule `sdkconfig.ci.*=`):

```bash
idf.py -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.ci.qemu"     build && idf.py qemu monitor
idf.py -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.ci.release"  build
idf.py -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.ci.analyzer" build
```

`sdkconfig.defaults` only seeds a *new* `sdkconfig`: after editing any defaults file run `rm -f sdkconfig && idf.py reconfigure`. Never commit `sdkconfig`; never create `version.txt` (it shadows `git describe`).

**Before the first flash of real hardware:** [`docs/devenv/first-flash-checklist.md`](../../docs/devenv/first-flash-checklist.md) (flash backup, eFuse baseline, decoded vendor partition table). **If the port disappears:** [`docs/devenv/brick-runbook.md`](../../docs/devenv/brick-runbook.md).

## Files in this directory

| File | Role | Grounding |
|---|---|---|
| [`CMakeLists.txt`](CMakeLists.txt) | Build System v1; `PROJECT_VER` from `git describe --tags --always --dirty --match "v[0-9]*"` cut to 31 chars (`esp_app_desc_t.version` is `char[32]`; ESP-IDF itself silently cuts any longer `PROJECT_VER` to 31 in `esp_app_format/CMakeLists.txt` via `PROJECT_VER_CUT` — our `SUBSTRING` makes the cut visible and logs the full `git describe` next to it) | ADR 0019, ADR 0001 |
| [`partitions.csv`](partitions.csv) | 16 MB exact: nvs 24K · otadata 8K · phy_init 4K · **ota_0 / ota_1 4 MB each, no factory** · nvs_keys 4K · presets (littlefs) 1 MB · takes (FAT) ~6.8 MB · coredump 60K. `ota_0` = golden recovery image, dev builds go to `ota_1`. Offsets frozen. Deliberately **not gap-free**: 0x12000–0x20000 is the unnamed 64 KB alignment pad before `ota_0` (growth room for nvs/otadata without moving an app offset); the pre-commit arithmetic hook allows it | ADR 0014, ADR 0015 |
| [`sdkconfig.defaults`](sdkconfig.defaults) | Target-neutral: reproducible build, custom table, rollback + bootloader WDT, secure boot/flash-enc **n**, console on USB-Serial-JTAG, coredump to flash, watchdogs panic at 10 s, brownout `SEL_7`, BT off. `LIBC_NEWLIB_NANO_FORMAT=n` is kept but **inert under the default GCC toolchain** (v6.0 libc is Picolibc; the symbol `depends on LIBC_NEWLIB`) — `%f` is confirmed by the E1 smoke test below | ADR 0015, ADR 0017 |
| [`sdkconfig.defaults.esp32s3`](sdkconfig.defaults.esp32s3) | Board: QIO 80 MHz, 16 MB, auto-detect off, 1.9 V VDDSDIO boost, octal PSRAM **80 MHz explicit** (Kconfig default is 40 MHz), `SPIRAM_IGNORE_NOTFOUND=n`, 240 MHz, no 120 MHz / experimental options | ADR 0001 §board config |
| `sdkconfig.ci.qemu` · `.release` · `.analyzer` | Overlays: UART console + no secondary (QEMU has no USB) · `LOG_DEFAULT_LEVEL_WARN` + `-O2` · `COMPILER_STATIC_ANALYZER` | CI plan in [`docs/devenv/`](../../docs/devenv/README.md) |
| [`main/idf_component.yml`](main/idf_component.yml) | Tilde pins: esp-dsp `~1.8.2`, lvgl `~9.5.0`, esp_lvgl_port `~2.9.0`, esp_lcd_touch_ft5x06 `~1.1.1`, sensorlib `~0.4.1`, esp_codec_dev `~1.6.2`, littlefs `~1.22.3`; ST7789 is in-tree, no component; radiolib deferred | ADR 0001, ADR 0004, ADR 0017 |
| [`main/Kconfig.projbuild`](main/Kconfig.projbuild) | `SPECTRAL_BOOT_GUARD_MS` (3000, range 1000–10000, never reduced) · `SPECTRAL_DEV_SLEEP_ARMED` (n) | ADR 0015 |
| [`main/app_main.c`](main/app_main.c) | Boot guard as the **first statement**, reset-reason log, bring-up TODO list in the order of [`docs/hw/twatch-s3-pins.md`](../../docs/hw/twatch-s3-pins.md) | ADR 0015 |
| [`components/twatch_bsp/include/twatch_pins.h`](components/twatch_bsp/include/twatch_pins.h) | Every pin/address/port allocation as a macro, each followed by `TWATCH_ASSERT_NOT_USJ(...)`; GPIO45 hazard comment; LoRa pins marked `(verify)` | ADR 0015, ADR 0016, [`docs/hw/twatch-s3-pins.md`](../../docs/hw/twatch-s3-pins.md) |
| [`components/spectral_core/include/spectral_core/spectral.h`](components/spectral_core/include/spectral_core/spectral.h) | **API sketch, no bodies**: window enum (wire values), PS/PSD scale, `spectral_config_t` / `spectral_frame_t`, injected `spectral_rfft_fn`, `spectral_init/process/window_fill` prototypes | ADR 0006, ADR 0009 |

Every `CONFIG_*` symbol in the defaults was grepped against the local ESP-IDF v6.0.1 tree on 2026-08-20 (symbol names only; line numbers rot). Two notes are recorded inline: `ESP_WIFI_ENABLED` is promptless on the S3 and cannot be overridden (the radio guard is structural — no component requires `esp_wifi`), and the coredump format/checksum symbols are `select`ed but not defined in v6.0.x, so they are not set.

## Component map

```
firmware/twatch-s3/
├── main/                      app_main: boot guard, reset reason, wiring (kept tiny)
└── components/
    ├── spectral_core/         pure C99, REQUIRES "" - windows, S1/S2 normalisation,
    │                          peaks, f0 front end; FFT injected (host-buildable)
    ├── spectral_fft_backend/  the one place esp-dsp is included
    ├── twatch_bsp/            pins (_Static_assert != 19/20), AXP2101 rails, I2S0 mic /
    │                          I2S1 amp, ST7789V3 + FT6336U factories
    ├── audio_source/          seam: pdm_mic | file_blob | synthetic   (QEMU has no I2S)
    ├── display_backend/       seam: st7789_spi | qemu_rgb              (QEMU has no SPI)
    └── ui/                    LVGL chrome + raw esp_lcd analyzer canvas; no hardware access
```

```
            PDM mic (I2S0)                                    ST7789V3 (SPI)
                 │                                                  ▲
   audio_source ─┴─ int16 → float ─► spectral_core ─► frames ─► ui ─┴─ display_backend
        ▲                              │  ▲                    (core 0)
        │                              ▼  │ rfft
    file_blob / synthetic      spectral_fft_backend (esp-dsp)
    (QEMU, host, CI)                 (core 1)
```

| Component | README | Depends on | Host-buildable |
|---|---|---|---|
| `spectral_core` | [README](components/spectral_core/README.md) | nothing | ✅ (`host-tests/`) |
| `spectral_fft_backend` | [README](components/spectral_fft_backend/README.md) | `spectral_core`, esp-dsp | QEMU/target |
| `twatch_bsp` | [README](components/twatch_bsp/README.md) | `esp_driver_*`, `esp_lcd` | target |
| `audio_source` | [README](components/audio_source/README.md) | `twatch_bsp`, `esp_driver_i2s` | synthetic/file_blob on QEMU |
| `display_backend` | [README](components/display_backend/README.md) | `esp_lcd`, `twatch_bsp` | qemu_rgb on QEMU |
| `ui` | [README](components/ui/README.md) | `spectral_core`, `display_backend`, LVGL | LVGL native screenshot harness |

Each component stub lists its planned sources behind `if(EXISTS ...)` guards, so the tree configures today and grows without CMake edits. Per-component flags: `-Wall -Wextra -Werror -Wshadow -Wconversion -Wdouble-promotion -Wformat=2 -Wvla` (the S3 FPU is single precision; `-Wdouble-promotion` is the one that pays). `-Wundef` is kept only on `spectral_core` (pure C99): ESP-IDF headers use `#if CONFIG_X` idioms that trip it under `-Werror` (found in the E1 build on v6.0.2).

## Rules that are enforced here, not by memory

| Rule | Mechanism |
|---|---|
| GPIO19/20 are never configured | `_Static_assert` on every pin in [`twatch_pins.h`](components/twatch_bsp/include/twatch_pins.h) + pre-commit grep |
| 3 s boot guard before anything | first statement of `app_main`, Kconfig range floor 1000 ms |
| Console is USB-Serial-JTAG, always | `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y`; QEMU overlay is the only exception |
| No secure boot, no flash encryption, no radio stacks | `sdkconfig.defaults` + pre-commit assert |
| eFuses read-only; `ota_0` never overwritten by dev flashes | [`docs/devenv/first-flash-checklist.md`](../../docs/devenv/first-flash-checklist.md), [`tools/`](../../tools/README.md) flash script |
| Sleep unreachable in dev | `CONFIG_SPECTRAL_DEV_SLEEP_ARMED=n` + runtime "awake ≥ N s AND no USB host" gate |
| Rollback only cancelled after display + touch + PMU + USB are proven | `esp_ota_mark_app_valid_cancel_rollback()` placement (TODO 7 in `app_main.c`) |

## What comes next

| Phase | Firmware deliverable |
|---|---|
| **E1** (next session) | Gate build on v6.0.2 with the pinned component set; commit `dependencies.lock`; fill `docs/devenv/env.lock.md`; flip ADR 0001 to accepted; un-`if: false` the CI job; **`printf("%f")` smoke test over the USJ console under Picolibc** (one `ESP_LOGI` of `1.0f / 3.0f` in `app_main`, expected `0.333333`); first bodies for `spectral.h` (`window.c`, `fft_ref.c`) + synthetic source + host tests |
| **E2** (needs the watch) | Flash backup, eFuse baseline (`VDD_SPI_FORCE` → ADR 0016), decoded vendor table; AXP2101 driver; display at 20 MHz; rollback + boot-guard race tests |
| Phase 1+ | PDM → FFT → canvas; validation per [`docs/validation/`](../../docs/validation/README.md) |

Design prose lives next to its subject: DSP in [`dsp/design/`](../../dsp/design/README.md), record/preset formats in [`protocols/specs/`](../../protocols/specs/README.md), hardware facts in [`docs/hw/`](../../docs/hw/README.md) and [`hardware/`](../../hardware/README.md). Cross-cutting decisions are ADRs in [`docs/adr/`](../../docs/adr/README.md).
