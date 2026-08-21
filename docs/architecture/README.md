# Architecture

Design notes for the Super Spectral companion architecture: one wrist-worn device (LilyGO T-Watch S3, ESP32-S3-R8) that captures, analyzes and displays in real time, and a Linux host that does the offline science on recorded takes. The split is fixed by proposal §3 and will be recorded as [ADR 0002](../adr/README.md); the toolchain and environment by [ADR 0001](../adr/0001-toolchain-esp-idf-v6-pinned-environment.md).

```
  acoustic path                              digital-injection path (tests)
  singer ──► case/port ──► SPM1423 PDM ─┐     corpus WAV ──► file_blob ──┐
                                         ▼                               ▼
                         I2S0 PDM→PCM (16-bit, 32/48 kHz)  ─────► PCM ring (internal SRAM)
                                                                   │
                             core 1: DC removal → window → esp-dsp FFT (fc32) → |X|² → dB
                                     → f0 (MPM/YIN) → band energy / FHE / SPR → features
                                                                   │ double-buffered magnitude + queue of pointers
                             core 0: analyzer canvas (raw esp_lcd + ST7789 vertical scroll)
                                     LVGL chrome · touch · PMU · haptics · take recorder
                                                                   │
                         ST7789V3 240×240 ◄── SPI ──┘             takes (FAT) · presets (littlefs)
                                                                   │ USB-Serial-JTAG / file transfer (binary records)
                         Linux host (host/, GPL-3.0-or-later): Praat/parselmouth formants, LTAS/SPR, H1–H2, DTW, Demucs
```

## Architectural tenets

1. **Real-time DSP runs on the device.** Capture → FFT → f0 → band features → pixels never leaves the ESP32-S3; the research question is only answerable if it does not. DSP is pinned to core 1, UI to core 0; buffers are handed over by pointer, never by copy, and the renderer is never given a buffer the DSP task is still writing.
2. **The host is never required for live use.** The watch completes useful work — live spectrum, spectrogram, f0, band readouts, take recording — with no phone, no PC, no radio. The host adds offline depth (Praat-grade formants, LTAS/SPR over takes, H1–H2, DTW, Demucs); it never closes the live loop.
3. **Record formats are sacred.** The on-flash take record, the feature-vector layout and the preset JSON schema are contracts owned by [`../../protocols/specs/`](../../protocols/specs/README.md). Changing one requires an ADR and coordinated commits across firmware and host; `_Static_assert` guards every on-flash struct size; no code crosses the `host/` licence boundary in either direction.
4. **Validation is part of the design.** Every architectural choice maps to a measurable row in [`../validation/README.md`](../validation/README.md), reported on both the injection and the acoustic path; a choice without a metric is not finished.
5. **The recovery path is sacred.** GPIO19/20 are USB-Serial-JTAG and are never reconfigured (`_Static_assert` + CI grep); the console stays on USB-Serial-JTAG; the 3 s boot guard is never reduced; `ota_0` holds the golden recovery image and development builds flash to `ota_1` only; eFuses are read-only for the life of the project; no sleep entry is unconditional. A sealed watch with the BOOT button inside the case has no other safety margin.
6. **Binary on the wire and on the flash.** Takes, feature records and the watch↔host transfer are compact binary; JSON appears only in the preset schema (human-edited, schema-validated) and never in a real-time path.
7. **Honest numbers.** Level readouts are dBFS unless a calibrator has been applied in-session; timbre readouts (SPR, FHE, ring ratio) are relative, within-subject, within-session; the uncorrected value is always available next to the EQ-corrected one.

## Planned documents (one per file as the design solidifies)

| File | Contents | Grounded by |
|---|---|---|
| `01-overview.md` | System block diagram, the two paths, responsibilities of watch vs host, data flow, milestone map (M0 PDM→FFT→USJ dump · M1 canvas at 30/50 Hz · M2 presets + takes) | proposal §3; ADR 0002 |
| `02-audio-capture-path.md` | SPM1423 → I2S0 PDM RX (CLK 44 / DATA 47, 16-bit slots, `DSR_8S`), MAX98357A on I2S1 (BCLK 48 / LRCLK 15 / DIN 46) for the calibration tone, software DC removal, ring buffer in internal DMA-capable SRAM, the rail that powers the mic (E2) | ADR 0003; experiment 0001; Knowles DS (01) |
| `03-dsp-pipeline.md` | Window/FFT conventions, N per preset (2048–8192 real, ≤ 112 KB SRAM), decimation cascade for the octave bank, f0 estimator choice (MPM vs YIN vs dywapitchtrack), band energy / FHE / SPR, the log approximation and its error budget, cycle budget per preset (`log_performance()` trend) | ADR 0006, 0008; Heinzel 2002, Harris 1978, McLeod & Wyvill 2005 (05) |
| `04-display-render-path.md` | Raw `esp_lcd` analyzer canvas + ST7789 `VSCRDEF`/`VSCSAD` scroll (gated on the scroll-axis check, threshold T4), LVGL chrome with 2 × ~1/8-screen internal-SRAM partial buffers, colormap as a pre-quantized RGB565 LUT with dithering, refresh targets and their power cost | ADR 0007, 0011; ST7789V3 DS (01); `esp_lvgl_port/docs/performance.md` (02) |
| `05-host-companion-link.md` | Take record format, feature-record format, transfer over USB-Serial-JTAG / mass storage, host-side ingestion into `host/`, the licence boundary as a directory boundary | ADR 0002, 0004; `protocols/specs/` |
| `06-power-budget.md` | **Rail map** (DC1 = SoC · ALDO2 = backlight · ALDO3 = display + touch · ALDO4 = LoRa (off) · BLDO2 = haptic enable · VBACKUP = RTC coin cell · **mic and amp rails: TBD from the schematic in E2/D4**), per-rail current budget with the two unknowns (octal PSRAM active, backlight at usable brightness), autonomy derivation ending in a verdict against the ≥ 3 h bound, the AXP2101 E-Gauge cross-check, the battery-capacity threshold T9 | ADR 0015, 0016, 0017; AXP2101 DS (01); ESP32-S3 DS Tables 5-7…5-12 (01) |
| `07-preset-schema.md` | The six presets carried over from the Linux analyzer, explicit bandwidth/ENBW per preset, the mic-EQ slot, the clock-correction constant, storage on the littlefs `presets` partition; schema owned by `protocols/specs/` | ADR 0010; research doc §B |
| `08-simulator-and-host-target.md` | Native-Linux simulator (LVGL sim + `spectral_core` on host), the `audio_source` (pdm_mic · file_blob · synthetic) and `display_backend` (st7789_spi · qemu_rgb) seams, QEMU lane and its limits (no I²C/I²S/GP-SPI/USB/GPIO matrix), plain-CMake host tests with ASan/UBSan | ADR 0009, 0013; ESP-IDF host-apps and QEMU guides (11) |
| `09-memory-and-task-topology.md` | Internal SRAM vs PSRAM placement rules (I²S DMA, LVGL partial buffers, SPI bounce **and FFT working buffers** → internal DMA-capable SRAM, 16-byte aligned; spectrogram history, fonts and LVGL assets → PSRAM), task priorities and core pinning, the double-buffer handoff, watchdog policy (`ESP_TASK_WDT_PANIC=y`, 10 s), stack sizing with FPU context | ADR 0015; ESP-IDF external-RAM, FreeRTOS SMP, memory-types guides (02/11); the published ESP32-S3 IRAM/PSRAM bandwidth matrix (06), re-measured on target |
| [`12-interaction-model.md`](12-interaction-model.md) | **Written.** The hands-free rule (you cannot touch the watch while singing): the take state machine and where touch is refused, the BMA423 wrist-raise / DRV2605L haptic input inventory, glance zones on 240×240, the haptic vocabulary and its guard interval, the all-`TBD` timing budget, accessibility as a binding constraint, and the sleep-gate interaction | ADR 0012 (**proposed**), 0015; 09 R3/R4 + 05 #75 (bibliography); BMA423 / DRV2605L / FT6336U DS (01); SensorLib study notes |

Subsystem-specific notes live with their code, not here: DSP design prose in [`../../dsp/design/`](../../dsp/design/README.md), record and preset specs in [`../../protocols/specs/`](../../protocols/specs/README.md), board bring-up in [`../../firmware/twatch-s3/README.md`](../../firmware/twatch-s3/README.md), enclosure and acoustic port in [`../../hardware/`](../../hardware/README.md).

## Background reading

Platform and toolchain documents are catalogued by claim in [`../bibliography/11-esp-idf-platform-and-toolchain.md`](../bibliography/11-esp-idf-platform-and-toolchain.md); DSP and spectral-estimation references in [`05-papers.md`](../bibliography/05-papers.md) and [`04-books.md`](../bibliography/04-books.md) (Smith *SASP*, Lyons, Oppenheim & Schafer); reference firmware architectures (xiao-edge-audio, esp-bsp, espp, LilyGoLib as a register reference) in [`06-reference-projects.md`](../bibliography/06-reference-projects.md); the on-wrist measurement constraints that shape tenet 7 in [`08-voice-metrology-on-the-wrist.md`](../bibliography/08-voice-metrology-on-the-wrist.md).
