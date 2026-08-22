# Super Spectral

A wrist-worn singing-voice spectral analyzer on the LilyGO T-Watch S3 (ESP32-S3), **documented before it is built**. The watch is the live-capture and real-time-display front end of a preset-driven analyzer; a Linux companion does the offline science on recorded takes and carries the founding document's web application — a browser-native live analyzer and offline-compare UI — as its own instrument ([ADR 0021](docs/adr/0021-host-web-application.md)). It carries the six Spectroid-style presets of the founding research document — [`docs/research/00-linux-analyzer-architecture-and-build-guide.md`](docs/research/00-linux-analyzer-architecture-and-build-guide.md) — onto a device you can wear in a rehearsal room.

> **Research question (provisional).** Can a wrist-worn ESP32-S3 device with a single PDM MEMS microphone, acting as the live-capture and real-time-display front end of a preset-driven singing-voice analyzer, estimate singing f0 within ±20 cents median absolute error (≥90 % RPA @ 50 cents) on the acoustic path and ≤5 cents vs Praat on the digital-injection path, render a spectrogram at ≥30 Hz for the presets whose hop supports it (50 Hz for the live-singing and diction-consonants presets) with ≤80 ms acoustic-to-photon latency, and sustain ≥3 h of continuous analysis on its own battery — with all real-time DSP behind these bounds on-device, the host never in the watch's live loop, and files the only contract between them?

Full proposal: [`docs/proposal/01-super-spectral-proposal.md`](docs/proposal/01-super-spectral-proposal.md) · Project guide for Claude Code sessions: [`CLAUDE.md`](CLAUDE.md)

---

## System at a glance

```
┌──────────────────────────── T-WATCH S3 — LIVE PATH (all real-time DSP on-device) ────────────────────────────┐
│                                                                                                              │
│  Knowles SPM1423HM4H-B   PDM CLK GPIO44 / DATA GPIO47          ESP32-S3-R8 (240 MHz, 512 KB SRAM, 8 MB OPI)  │
│  (obsolete part; the     ───────────────────────────►   I2S0 PDM RX, 16-bit, PDM→PCM in hardware             │
│   only audio input)      1.0–3.25 MHz PDM clock         32 kHz / DSR_8S default (prov.); 48 kHz gated on     │
│                                                         a measured 3.072 MHz clock                           │
│                                                              │                                               │
│                            core 1 — DSP task                 ▼                                               │
│                            ┌──────────────────────────────────────────────────────────────┐                  │
│                            │ int16→float · 1-pole DC HPF (no HW HPF on S3) · window       │                  │
│                            │ esp-dsp fc32 FFT, N = 1024…8192 per preset (internal SRAM,   │                  │
│                            │ 16-byte aligned) · |X|² → dB · MPM/YIN f0 · band energies    │                  │
│                            │ decimation cascade (Spectroid "decimations", real IIR LPF)   │                  │
│                            └──────────────────────────────┬───────────────────────────────┘                  │
│                                                           │ double-buffered magnitude frame + queue          │
│                            core 0 — UI task               ▼                                                  │
│                            ┌──────────────────────────────────────────────────────────────┐                  │
│                            │ analyzer canvas: raw esp_lcd + ST7789 vertical scroll        │  SPI CS12 MOSI13 │
│                            │   (50/50/25/25/25 Hz per preset — scroll axis TBD)            │  SCK18 DC38     │
│                            │ LVGL 9.5 chrome: preset picker, readouts, status            │ ───────────────►  │
│                            │ spectrogram history → PSRAM (≈10 min of 256-bin columns)     │  ST7789V3 240×240│
│                            └──────────────────────────────────────────────────────────────┘  BL = GPIO45 (!) │
│                                                                                                              │
│  AXP2101 PMU (I²C0 SDA10/SCL11, 0x34) · FT6336U touch (I²C1 SDA39/SCL40, 0x38) · BMA423 · PCF8563 · DRV2605L │
│  470 mAh (prov., vendor) · USB-Serial-JTAG on GPIO19/20 = the ONLY flash/debug path · zero exposed GPIO      │
│                                                                                                              │
│  takes ──► FAT partition (binary record format, protocols/specs/) · presets ◄── LittleFS partition (JSON)    │
└──────────────────────────────────────────────────────────────────────┬───────────────────────────────────────┘
                                                                       │ takes + manifests over USB (prov.;
                                                                       │ mass-storage or serial dump, ADR-gated)
                                                                       ▼
┌──────────────────────────── LINUX HOST — OFFLINE PATH + WEB APPLICATION (host/, GPL-3.0-or-later) ───────────┐
│  parselmouth/Praat: f0 golden files, Burg formants F1–F3 · LTAS / SPR / FHE over whole takes · H1–H2         │
│  librosa: DTW alignment against a Demucs-separated reference stem · mir_eval / mirdata corpus evaluation     │
│  host/golden/: pinned parselmouth → bundled Praat → method → floor/ceiling → sha256 manifest                 │
│  web app (ADR 0021): host/web/ live analyzer on the HOST's OWN mic · offline compare UI · measured, no claim │
│  Python side never real-time; never in firmware; never in the watch's live loop. Takes in, reports out.      │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Two measurement paths are reported separately for every metric: **digital injection** (corpus WAV into the PCM ring buffer, mic bypassed — the only path that may claim "vs Praat") and **acoustic** (reproduced sound → watch mic + reference mic). Details in [`docs/validation/README.md`](docs/validation/README.md).

## Repository layout

Each engineering subsystem is **self-contained** — code, design notes, and specs live together. `docs/` holds only cross-cutting material plus the reference library.

| Path | Purpose |
|------|---------|
| [`docs/`](docs/) | Proposal, roadmap, architecture, ADRs, validation, devenv, hardware facts, bibliography, and the reference library |
| [`docs/datasheets/`](docs/datasheets/) · [`docs/app-notes/`](docs/app-notes/) · [`docs/standards/`](docs/standards/) · [`docs/papers/`](docs/papers/) · [`docs/reports/`](docs/reports/) · [`docs/books/`](docs/books/) | Acquired reference documents, filed by category (mirrors [`docs/bibliography/`](docs/bibliography/)) |
| [`docs/devenv/`](docs/devenv/) | Reproducible ESP-IDF v6.0.2 environment: setup, lock, upgrade procedure, first-flash checklist, brick runbook, backup policy |
| [`docs/research/`](docs/research/) | The founding Linux-analyzer research document (byte-identical move) |
| [`firmware/twatch-s3/`](firmware/twatch-s3/) | ESP-IDF application: `spectral_core` (pure C99 DSP), FFT backend, board support, audio-source and display-backend seams, LVGL UI |
| [`dsp/`](dsp/) | DSP design notes ([`dsp/design/`](dsp/design/)) shared by watch and host: FFT normalization, decimation cascade, pitch, band energy, mic EQ |
| [`protocols/`](protocols/) | Take/record format and preset JSON schema ([`protocols/specs/`](protocols/specs/)) — the watch↔host contract |
| [`host/`](host/) | Linux companion: offline analysis, the Praat golden-file generator ([`host/golden/`](host/golden/)) and the web application — front end `host/web/` (Vite + TypeScript), backend `host/src/spectral_host/web/` (FastAPI), [ADR 0021](docs/adr/0021-host-web-application.md) — **GPL-3.0-or-later** |
| [`host-tests/`](host-tests/) | Plain-CMake tests for `spectral_core` with ASan/UBSan — Apache-2.0, no ESP-IDF |
| [`hardware/`](hardware/) | BOM with instruments and tolerances, acoustic-port/case notes |
| [`python-scripts/`](python-scripts/) | All Apache-2.0 Python tooling, including the `doc_ocr` reference-library extractor |
| [`datasets/`](datasets/) | Tier-0 synthetic signals, corpus manifests, licence ledger (raw audio gitignored) |
| [`analysis/`](analysis/) | Notebooks and per-phase reports |
| [`tools/`](tools/) | `env-lock.sh`, `flash.sh`, bench utilities |
| [`tests/`](tests/) | QEMU, integration and hardware-in-the-loop tests |

## Roadmap

All dates provisional. The documentation roadmap (tracks D0–D6, E0–E2 and W0–W4 — the host web application, [ADR 0021](docs/adr/0021-host-web-application.md) — with a definition of done per phase) is [`docs/roadmap/documentation-roadmap.md`](docs/roadmap/documentation-roadmap.md).

| Phase | Weeks | Deliverable |
|-------|-------|-------------|
| 0 — Documentation & environment | 0–3 | Proposal with frozen RQ, bibliography 01–11 with acquisition ledger, ADRs 0001–0006, reproducible ESP-IDF v6.0.2 environment (`.envrc`, `dependencies.lock`, `env.lock.md`), eFuse baseline and vendor partition table read, recovery path tested |
| 1 — Component characterization | 4–7 | In-situ mic response and EIN vs reference mic, SPL calibration vs B&K 4231, sample-rate error vs GPSDO, esp-dsp cycle counts per preset, display refresh ceiling, per-preset current — deliverables: the mic EQ filter and the clock-correction constant |
| 2 — Bench validation | 8–11 | Injection path over Tier-1 corpora with mir_eval and Praat golden files; acoustic path through a fixed playback geometry over the factorial matrix (6 presets × 3 SPL × 3 distances × 2 arm angles = 108 trials *(prov.)*); Bland–Altman / ICC agreement |
| 3 — In-use validation & release | 12–16 | Live singers wearing the watch with a simultaneous reference mic, autonomy runs per preset, wrist/sleeve sensitivity envelope, public release with replication guide |

## Getting started

The repo is in Phase 0: documentation first, firmware as configuration stubs only.

- **Environment:** [`docs/devenv/setup.md`](docs/devenv/setup.md) — clone ESP-IDF v6.0.2 to `~/esp/idf/v6.0.2`, install tools to `~/esp/tools/v6.0.2`, `direnv allow` the committed [`.envrc`](.envrc), run the 30-minute gate build. [ADR 0001](docs/adr/0001-toolchain-esp-idf-v6-pinned-environment.md) records why.
- **Firmware build:** `cd firmware/twatch-s3 && idf.py set-target esp32s3 && idf.py build` — see [`firmware/twatch-s3/README.md`](firmware/twatch-s3/README.md).
- **Before the watch is ever flashed:** [`docs/devenv/first-flash-checklist.md`](docs/devenv/first-flash-checklist.md) (factory flash backup, eFuse read, decoded vendor partition table, restore test).
- **If the watch stops enumerating over USB:** [`docs/devenv/brick-runbook.md`](docs/devenv/brick-runbook.md) — ordered from `esptool --before usb-reset` down to opening the case. The board has zero exposed GPIO and its BOOT button is inside; read the runbook before you need it.
- **Reference library:** [`docs/bibliography/README.md`](docs/bibliography/README.md) is the acquisition list; `python3 -m doc_ocr extract` (from [`python-scripts/doc_ocr/`](python-scripts/doc_ocr/)) makes filed PDFs grep-able.

## License

**Split licensing, on purpose** ([ADR 0004](docs/adr/0004-split-licensing.md), accepted; stated in [`NOTICE`](NOTICE)):

- **Apache-2.0** — the repository default: firmware, DSP core, protocols, documentation, tooling, host tests. See [`LICENSE`](LICENSE). Permissive so the firmware stays upstreamable to ESP-IDF/Zephyr and reusable by other permissive projects; the firmware link line admits only MIT/BSD/Apache components, with copyright lines carried in `NOTICE` and SPDX headers on every file.
- **GPL-3.0-or-later** — [`host/`](host/) only, under its own [`host/LICENSE`](host/LICENSE). The Linux companion imports parselmouth/Praat (GPLv3) in-process, which a permissive licence cannot do. No code crosses the `host/` boundary in either direction: firmware never depends on `host/`, and `host/` is never linked into firmware. The same licence covers the web application's TypeScript, CSS and HTML under `host/web/` — it is the user interface of that same program ([ADR 0021](docs/adr/0021-host-web-application.md)); its npm dependencies are **permissive-only** (MIT, ISC, 0BSD, BSD-2/3-Clause, Apache-2.0, CC0-1.0, Unlicense, BlueOak-1.0.0, Python-2.0, Zlib, CC-BY-4.0), **AGPL is forbidden**, and a fail-closed CI licence gate over `package-lock.json` enforces both.

Consequences on the watch side: GPL/AGPL embedded code (arduinoFFT, cyberwisk, ikostoski, Friture) and LGPL-2.1 `arduino-esp32` are **read-only references**; the field-of-use "Espressif MIT" licence of ESP-ADF/ESP-SR is excluded; esp-dsp (Apache-2.0), LVGL (MIT), SensorLib (MIT) are in.
