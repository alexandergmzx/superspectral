# Tests

System-level tests that need an emulator, a tethered watch or the bench. Unit tests live next to the code they test: the pure-C DSP core in [`../host-tests/`](../host-tests/) (plain CMake, ASan/UBSan), Python packages in their own `tests/` (e.g. `python-scripts/doc_ocr/tests/`), and on-target Unity cases inside the firmware components.

| Subdirectory | Purpose |
|--------------|---------|
| `qemu/` *(planned)* | `pytest-embedded` (2.8.1) against the `sdkconfig.ci.qemu` build on Espressif QEMU: boot, boot-guard timing, **backend-agreement test** (esp-dsp `_aes3` path vs the `fft_ref` implementation on the same golden vectors, compared in dB), UI smoke via the `esp_lcd_qemu_rgb` virtual framebuffer. QEMU emulates the S3 CPU, PSRAM OPI, eFuse, GPIO strap and an RGB framebuffer — **not** I²C, I²S, GP-SPI, USB or the GPIO matrix — hence the `audio_source` (synthetic) and `display_backend` (qemu_rgb) seams. |
| `target/` *(planned)* | Hardware-in-the-loop: Unity suites run over USB-Serial-JTAG on `/dev/ttyTWATCH`, flashed to **an OTA slot only** (`ota_1`; never `ota_0`, which holds the golden recovery image), with the firmware under test required to call `esp_ota_mark_app_valid_cancel_rollback()` after proving display + touch + PMU + USB. Includes experiment 0002 (rollback and boot-guard race). |
| `lvgl/` *(planned)* | LVGL native screenshot regression (`lv_test_screenshot_compare`) for the analyzer widgets and note ladder, fully off-device. |
| `integration/` *(planned)* | End-to-end: take written by the watch → transferred → read by `host/` → frame-by-frame agreement of `FEATURE_FRAME` against the host's recomputation; injection-path replay of a Tier-0 signal through the real pipeline. |
| `bench/` *(planned)* | Instrumented procedures of the validation plan: acoustic-to-photon latency (oscilloscope + phototransistor), sustained refresh, autonomy (PPK2/Otii vs AXP2101 E-Gauge), sample-rate error vs GPSDO, wrist-position envelope. Each is a recipe under [`../docs/validation/experiments/`](../docs/validation/experiments/) with its data landing in [`../datasets/`](../datasets/). |

## Acceptance gate

A firmware change is shippable to the watch's `ota_1` slot only after:

1. `host-tests` pass under ASan/UBSan with the golden vectors at the tolerances in [`../docs/validation/golden-files.md`](../docs/validation/golden-files.md).
2. The `qemu` suite passes, including the backend-agreement test with `CONFIG_DSP_OPTIMIZED=y`.
3. The release build is reproducible (build-twice sha256 diff in CI) and `idf.py size` stays inside the budget.
4. On hardware: the boot guard is observed (3 s, `CONFIG_SPECTRAL_BOOT_GUARD_MS`), the USB-Serial-JTAG console enumerates, and rollback to `ota_0` has been exercised at least once for the current partition layout.

HIL jobs never run on fork pull requests and never cancel mid-flash (a cancelled `write-flash` is a half-written partition).

## Background reading

QEMU peripheral matrix, `pytest-embedded`, `idf-build-apps`, host-apps and unit-test guides, OTA/rollback and the USB-Serial-JTAG console guide are catalogued in [`../docs/bibliography/11-esp-idf-platform-and-toolchain.md`](../docs/bibliography/11-esp-idf-platform-and-toolchain.md); the anti-brick rules they enforce are ADR 0015 (backlog, [`../docs/adr/README.md`](../docs/adr/README.md)) and [`../docs/devenv/`](../docs/devenv/).
