# components — project components

Six project-local ESP-IDF components, namespaced so none can shadow a managed component (a local `lvgl/` would silently win over `lvgl__lvgl`). Each directory has its own README stating the contract; each `CMakeLists.txt` lists planned sources behind `if(EXISTS ...)` guards so the tree configures before the sources land, and applies the per-component warning set (`-Werror -Wshadow -Wconversion -Wdouble-promotion -Wformat=2 -Wundef -Wvla`).

| Component | Contract | Runs on |
|---|---|---|
| [`spectral_core/`](spectral_core/README.md) | pure C99, `REQUIRES ""`: windows, Heinzel S1/S2 normalisation, peaks, f0 front end; FFT injected (ADR 0006) | host, QEMU, target |
| [`spectral_fft_backend/`](spectral_fft_backend/README.md) | the only component that includes `esp_dsp.h`; backend-agreement test vs `fft_ref.c` | QEMU, target |
| [`twatch_bsp/`](twatch_bsp/README.md) | pins with `_Static_assert(pin != 19 && pin != 20)`, AXP2101 rail order, I2S0 = PDM mic / I2S1 = amp, panel + touch factories | target |
| [`audio_source/`](audio_source/README.md) | seam: `pdm_mic` \| `file_blob` \| `synthetic` (QEMU has no I²S) | synthetic/file_blob everywhere |
| [`display_backend/`](display_backend/README.md) | seam: `st7789_spi` \| `qemu_rgb` (QEMU has no GP-SPI) | `qemu_rgb` on QEMU |
| [`ui/`](ui/README.md) | LVGL chrome + raw `esp_lcd` analyzer canvas; no hardware access | LVGL native screenshot harness |

Dependency direction is one-way: `ui` → `spectral_core`/`display_backend`; `audio_source`/`display_backend` → `twatch_bsp`; nothing depends on `main`. Component search order (project `components/` → `managed_components/` → ESP-IDF) is why the names carry a project prefix.
