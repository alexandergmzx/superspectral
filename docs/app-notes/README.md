# Application notes and programme-documentation snapshots

Vendor application notes, API references and programme documentation — the driver contracts, configuration rules, measured performance ladders and mounting guidance that do not fit in a datasheet. Acquisition list and rationale: [`../bibliography/02-application-notes.md`](../bibliography/02-application-notes.md). Nothing is filed yet; the directories are pre-carved with `.gitkeep` for the first bulk pass ([roadmap](../roadmap/documentation-roadmap.md) D3).

Two kinds of document live here, with one rule each:

- **Living web documentation captured as a dated PDF snapshot.** Espressif's programme guide tracks `stable` and drifts; the project pins ESP-IDF **v6.0.2** ([ADR 0001](../adr/0001-toolchain-esp-idf-v6-pinned-environment.md)), so every ESP-IDF page is captured from the `…/en/v6.0.2/esp32s3/…` rendering with the capture date in the filename, and re-captured only through the [upgrade procedure](../devenv/upgrade-procedure.md). The same applies to esp-dsp, LVGL, Zephyr and component-registry pages (capture at the pinned tag).
- **Classical vendor PDFs** (TDK AN-1003, GORE datasheets, Knowles guides) — filed as-is with their AN number.

## Layout

Organised by vendor / publisher:

```
app-notes/
├── espressif/        # ESP-IDF v6.0.2 guides (build system, partitions, component manager, I2S/PDM, esp_lcd, SPI,
│                     # PSRAM, power, watchdogs, USB-Serial-JTAG, OTA, bootloader, core dump, espefuse, QEMU, CI tools),
│                     # esp-dsp API + benchmarks, esp_lvgl_port README + performance.md, esp_lcd_touch_ft5x06 source,
│                     # esp_codec_dev / esp_audio_codec / ESP-SR pages, esptool guides, pinned headers (i2s_pdm.h, soc_caps.h)
├── knowles/          # MEMS microphone selection guide / specifications explained; PDM interfacing note (on request)
├── tdk-invensense/   # AN-1003 mounting and connecting, AN-100 handling and assembly, AN-1112 specifications explained
├── infineon/         # PCB and housing design guidelines for MEMS microphones
├── gore/             # acoustic-vent portfolio datasheet, GAW334
├── lvgl/             # LVGL v9 display-porting / draw-buffer / canvas docs, benchmark and tests READMEs (at tag 9.5.0)
└── zephyr/           # twatch_s3 board files (dts, pinctrl, Kconfig) at a named commit; DMIC API pages
```

Board-support sources that function as documents (LilyGoLib bring-up files, SensorLib README + Kconfig, XPowersLib ESP-IDF example, arduino-esp32 `Kconfig.projbuild`) are small enough to file under `espressif/` or a new `lilygo/` / `lewisxhe/` directory when captured; create the directory with a README when the first file lands.

## Filing convention

- Filename pattern: `<vendor>_<an-id>_<short-title>.pdf` — for example `tdk-invensense_an-1003_mounting-and-connecting-mems-microphones.pdf`, `gore_gaw334_acoustic-vent_datasheet.pdf`, `knowles_mic-selection-guide_r5.pdf`.
- Snapshots of living pages carry the **pinned version and the capture date**: `espressif_esp-idf-v6.0.2_usb-serial-jtag-console_2026-MM-DD.pdf`, `espressif_esp-dsp-v1.8.2_benchmarks_2026-MM-DD.pdf`, `espressif_esp-bsp_esp-lvgl-port-2.9.0_performance_2026-MM-DD.pdf`, `lvgl_v9.5.0_display-porting_2026-MM-DD.pdf`, `zephyr_twatch-s3-board-files_<commit7>.zip` (or the individual `.dts`/`.dtsi` files next to a `_notes.md` naming the commit).
- For notes without a numeric ID, use a slug: `knowles_pdm-interfacing-note.pdf`.
- Lowercase, hyphens or underscores, no spaces. Keep originals unmodified; hand-written notes go alongside as `<original>_notes.md` (tracked). Generated `<original>.ocr.md` sidecars are gitignored — see [`../OCR/README.md`](../OCR/README.md).
- Where a note underpins a specific driver or configuration block, cite its entry address (`02 #36`) from the source file's header comment or the `sdkconfig.defaults` comment so the connection survives refactors — e.g. `audio_source/pdm_mic.c` cites `02 #14–16`, `twatch_bsp/pins.h` cites `02 #35–36`, `partitions.csv` cites `02 #8`.

## How this couples to the bibliography

Each entry in [`../bibliography/02-application-notes.md`](../bibliography/02-application-notes.md) says which ADR, proposal section, metric, runbook or firmware component it grounds, and the thematic file [`../bibliography/11-esp-idf-platform-and-toolchain.md`](../bibliography/11-esp-idf-platform-and-toolchain.md) re-lists the Espressif documents by the environment claim each defends (cross-map at the end of 02). When a document lands here, add a `📥 Filed locally: <relative path>` blockquote to its entry in 02 (11 inherits it through the cross-map), remove it from the gap table in [`acquisition-status.md`](../bibliography/acquisition-status.md), and run `python3 -m doc_ocr extract` so the snapshot is registered in [`../OCR/manifest.tsv`](../OCR/manifest.tsv) by sha256 — which is also how a drifted re-capture is detected.
