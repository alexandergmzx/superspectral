# CLAUDE.md — Project guide for Claude

This file is read by Claude Code at the start of every session in this repo. It defines who the user is, what we're building, what phase we're in, and the conventions Claude must follow.

## Who you are working with

You are working with **Alexander Gomez** (GitHub: `alexandergmzx`), an embedded software engineer based in the Monterrey, MX metropolitan area. He has explicitly framed your role as his **scientific assistant**: rigorous, evidence-based, and oriented around the research method (hypothesis → experiment → measurement → publication). Skip beginner-level explanations of embedded, RTOS, DSP, or voice-acoustics concepts. Lead with trade-offs and concrete code/schematic decisions. Push back with data when warranted.

This project deliberately follows the method of his earlier `swarm` repository: **documentation before firmware** — research question → bibliography/acquisition list → reference library → ADRs → validation plan → code. When in doubt about *how* to do something here, the answer is usually "the way swarm did it"; when in doubt about *whether* a number is settled, it is `(prov.)` until an ADR or a measurement says otherwise.

## What we are building

**Super Spectral** — a wrist-worn singing-voice spectral analyzer on the LilyGO T-Watch S3 (ESP32-S3-R8, one Knowles SPM1423HM4H-B PDM microphone, 240×240 ST7789V3 display). The watch is the **live-capture and real-time-display front end** of a preset-driven analyzer; a Linux host does the offline science on recorded takes. The watch carries forward the six Spectroid-style presets of the founding research document, [`docs/research/00-linux-analyzer-architecture-and-build-guide.md`](docs/research/00-linux-analyzer-architecture-and-build-guide.md).

The **research question** binds the project (proposal §1, *provisional until D2 freezes it*):

> Can a wrist-worn ESP32-S3 device with a single PDM MEMS microphone, acting as the live-capture and real-time-display front end of a preset-driven singing-voice analyzer, estimate singing f0 within ±20 cents median absolute error (≥90 % RPA @ 50 cents) on the acoustic path and ≤5 cents vs Praat on the digital-injection path, render a ≥30 Hz spectrogram (50 Hz for the live-singing preset) with ≤80 ms acoustic-to-photon latency, and sustain ≥3 h of continuous analysis on its own battery — with all real-time DSP on-device and the host used only for offline analysis of recorded takes?

Authoritative source: [`docs/proposal/01-super-spectral-proposal.md`](docs/proposal/01-super-spectral-proposal.md).

### Companion architecture (fixed unless changed by ADR — see ADR 0002 in the [ADR index](docs/adr/README.md))

| Half | Role |
|------|------|
| **Watch — live path** (`firmware/twatch-s3/`, pure ESP-IDF v6.0.2) | PDM capture on I2S0 (CLK GPIO44 / DATA GPIO47, 16-bit, 32 kHz default *(prov.)*) → software DC removal → window → esp-dsp float FFT → magnitude spectrum, spectrogram waterfall, time-domain f0 (MPM/YIN), band-energy readouts → ST7789V3 over SPI. All real-time DSP on-device, DSP task on core 1, UI on core 0. Records **takes** to the FAT partition. No Wi-Fi, no BLE, no LoRa in v1 (ADR 0017, accepted). |
| **Host — offline path** (`host/`, Linux, Python, GPL-3.0-or-later) | Praat-grade formants (parselmouth), LTAS/SPR over whole takes, H1–H2, DTW alignment, Demucs stem separation, golden-file generation. Never real-time, never linked into firmware. |
| **Record formats** ([`protocols/`](protocols/)) | The take/record format the watch writes and the host reads, and the preset JSON schema both halves load. The only contract between the halves. |
| **Validation** ([`docs/validation/`](docs/validation/)) | Two-path rule: every metric is reported separately for the **digital-injection** path (corpus WAV into the PCM ring buffer, mic bypassed) and the **acoustic** path (reproduced sound → watch mic + reference mic). Only the injection path may carry a "vs Praat" claim. |

Hardware facts that shape every decision (schematic `T_WATCH_S3.pdf` V1.4 + LilyGoLib hardware doc; see [`docs/hw/`](docs/hw/)): chip-down ESP32-S3-R8 (no inherited RF certification), 512 KB SRAM, 8 MB octal PSRAM, 16 MB flash reading JEDEC `ef 4018` (W25Q128JV-class, **3.3 V** — the schematic says the 1.8 V `W25Q128JW`; it does not describe this unit), AXP2101 PMU on I²C0 (SDA 10 / SCL 11), FT6336U touch on I²C1 (SDA 39 / SCL 40), display backlight on **GPIO45 = the VDD_SPI strapping pin**, native USB-Serial-JTAG on GPIO19/20 as the **only** flash/debug path, **zero exposed GPIO, BOOT button inside the case**. FFT working buffers live in internal SRAM (PSRAM is too slow for them); PSRAM holds spectrogram history.

## Current phase: Phase 0 — Documentation & environment

The phase goal is a **complete, citable documentation base and a reproducible ESP-IDF environment before any feature firmware exists**. The roadmap ([`docs/roadmap/documentation-roadmap.md`](docs/roadmap/documentation-roadmap.md)) runs two tracks — D (documentation/acquisition: D0–D6) and E (environment: E0–E2). This pass delivers D0 (constitution), D1 (acquisition list) and E0 (environment specification); the rest are follow-up sessions because they change system state, touch the watch, or need the user present.

### Phase definition of done — documentation phase (gate to firmware M0)

*(State synced with [the roadmap's D6 list](docs/roadmap/documentation-roadmap.md) on 2026-08-21; that file is where the evidence for each tick lives. **O** = yours, **A** = mine.)*

- [ ] **O/A** Every ★★★ document filed + 📥 stamped, or ledgered with a reason tag
- [ ] **O** `doc_ocr` manifest covers 100 % of filed PDFs *(46/46, `doc_ocr verify` clean)*; the gating docs `checked` — the `checked` flag records a **human** read, so this one cannot be ticked by an assistant: Knowles SPM1423, ST7789V3, ESP32-S3 datasheet + TRM, HW Design Guidelines, both schematics
- [ ] **O** Proposal RQ frozen; CLAUDE.md and research-statement quote it verbatim *(the prose is drafted and cited; the voice and the freeze are the author's)*
- [x] ADRs 0001 (toolchain+env, accepted after the gate), 0002 (companion split), 0003 (mic path), 0004 (split licensing), 0005 (no-clinical-claim) accepted — [ ] **O** 0006 (FFT conventions) **written 2026-08-21 and `proposed`**; accepting it is one reading
- [ ] **O** E1 complete: `dependencies.lock` committed ✓, `env.lock.md` filled ✓, CI firmware job green ✓, **old installs removed** — `rm -rf ~/esp/esp-idf ~/esp/idf/v5.5.5 ~/esp/tools/v5.5.5` is your shell, not mine
- [x] E2 complete: eFuse baseline + vendor partition table committed; rollback + boot guard tested *(experiment 0002: rollback 4/4, race 10/10 + 5/5)*
- [x] Validation metrics table: every target has an external anchor and a measurement method *(plus the GUM uncertainty budget)*
- [x] First reference-project ADR written ([ADR 0018](docs/adr/0018-first-reference-project-study.md)); first experiment recipe written (0001, and 0002 executed)
- [x] CI link-check green

When a task is proposed, prefer work that closes an item on this list over polishing a single document in isolation. Firmware beyond configuration stubs and the 3 s boot guard is **out of scope** until the list is green.

## Repository layout (high-level)

Each engineering subsystem is **self-contained** — code and design/spec notes live together under the same root. `docs/` is reserved for cross-cutting material (proposal, roadmap, architecture, ADRs, validation, devenv, bibliography) plus an organised library of acquired reference documents (datasheets, app notes, standards, papers, reports).

| Path | Purpose |
|------|---------|
| [`docs/`](docs/) | Proposal, roadmap, architecture, ADRs, validation, devenv, hardware facts, bibliography (index), and the reference library |
| [`docs/datasheets/`](docs/datasheets/) · [`docs/app-notes/`](docs/app-notes/) · [`docs/standards/`](docs/standards/) · [`docs/papers/`](docs/papers/) · [`docs/reports/`](docs/reports/) · [`docs/books/`](docs/books/) | Acquired reference documents, filed by category (mirrors [`docs/bibliography/`](docs/bibliography/)) |
| [`docs/devenv/`](docs/devenv/) | ESP-IDF environment: setup, lock, upgrade procedure, first-flash checklist, brick runbook, backup policy |
| [`firmware/twatch-s3/`](firmware/twatch-s3/) | ESP-IDF v6.0.2 application for the T-Watch S3 (components: `spectral_core`, `spectral_fft_backend`, `twatch_bsp`, `audio_source`, `display_backend`, `ui`) |
| [`dsp/`](dsp/) | DSP design notes (`design/`) and reference implementations shared by watch and host |
| [`protocols/`](protocols/) | Take/record format and preset JSON schema (`specs/` for prose) |
| [`host/`](host/) | Linux companion (offline analysis, Praat golden-file generator) — **GPL-3.0-or-later, own `LICENSE`** |
| [`host-tests/`](host-tests/) | Plain-CMake host tests for `spectral_core` (ASan/UBSan, ctest) — Apache-2.0, no ESP-IDF |
| [`hardware/`](hardware/) | BOM, acoustic-port notes, teardown measurements |
| [`python-scripts/`](python-scripts/) | All Apache-2.0 Python tooling (see rule below); `doc_ocr/` lives here |
| [`datasets/`](datasets/) | Tier-0 synthetic signals, corpus manifests, licence ledger |
| [`analysis/`](analysis/) | Notebooks and reports |
| [`tools/`](tools/) | Environment lock, flashing, bench utilities (shell entry points) |
| [`tests/`](tests/) | Integration, QEMU and hardware-in-the-loop tests |

A full layout summary lives in [`README.md`](README.md).

## Conventions and ground rules

### Where Python lives

**Every Apache-2.0 Python file in this repo must live under [`python-scripts/`](python-scripts/).** Other directories (firmware, dsp, tools, analysis, tests) reference scripts by relative path; they never contain `.py` files of their own. This rule comes directly from Alexander and predates everything else in this file.

**Deliberate, sole exception:** GPL-licensed companion code lives in [`host/`](host/) — the Linux offline-analysis path and the Praat/parselmouth golden-file generator under [`host/golden/`](host/golden/). It imports parselmouth (GPLv3) in-process, so it cannot be Apache-2.0, and the licence boundary must be a **directory boundary** that a reviewer can see at a glance. Nothing under `host/` is imported by anything outside `host/`; nothing outside `host/` is imported by `host/` except through files on disk (takes, manifests, golden vectors). Do not add Python outside `python-scripts/` on the strength of this precedent; it exists solely because of the licence.

### Build systems and the environment pin

- **Firmware → ESP-IDF v6.0.2, native, pinned** ([ADR 0001](docs/adr/0001-toolchain-esp-idf-v6-pinned-environment.md)). The pin is the committed [`.envrc`](.envrc) (direnv), which sources `~/esp/idf/v6.0.2/export.sh` with `IDF_TOOLS_PATH=~/esp/tools/v6.0.2`, strips the ROS 2 and `IDF_COMPONENT_LOCAL_STORAGE_URL` leaks, and asserts `idf.py --version`. **Activate only through `.envrc`** — never through `get_idf`, a `.bashrc` alias, or an EIM activation script. Components are tilde-pinned in `main/idf_component.yml` and frozen by a committed `dependencies.lock` (generated in roadmap E1). Upgrades follow [`docs/devenv/upgrade-procedure.md`](docs/devenv/upgrade-procedure.md), never in place.
- **Host tests → plain CMake** in [`host-tests/`](host-tests/) with ASan/UBSan + ctest. esp-dsp cannot build on the IDF `linux` target, so the pure-C99 `spectral_core` is tested here and esp-dsp is validated by a backend-agreement test on QEMU/target.
- **Host companion → Python** under `host/`, its own environment, its own licence.
- **No Arduino in any phase.** LilyGoLib and arduino-esp32 are read-only artefacts (schematic, prebuilt factory binary flashed once to prove hardware, MIT source read as a register reference). Never copy pin macros from `arduino-esp32/variants/` (LGPL-2.1); derive them from the schematic or LilyGoLib's MIT headers with attribution. Zephyr is the recorded rejected alternative (no Espressif PDM driver; board unmaintained).
- **Do not introduce Bazel, west, or a second build system.** The CI oracle is the digest-pinned `espressif/idf:v6.0.2` container.

### Record formats are sacred

- The take/record format the watch writes and the preset JSON schema are owned by [`protocols/specs/`](protocols/specs/) and are the only contract between the watch and the host. Changing either requires an ADR and coordinated commits across firmware + host + validation.
- A `_Static_assert` guards the on-disk size of every record struct; do not relax it. Record headers carry a version field and the `app_elf_sha256` of the writing build.
- Binary on flash — no JSON in the take stream. Presets are JSON because the host edits them; their schema is versioned.

### Never — rules with no exceptions

1. **Never reconfigure, drive, or `_Static_assert`-exempt GPIO19/GPIO20.** They are USB D−/D+ — the only flash and debug path on a sealed board. Every pin constant in `twatch_bsp` is statically asserted ≠ 19/20 and CI greps for the literals.
2. **Never burn an eFuse.** No `espefuse burn-*`, no `set-flash-voltage`, no `DIS_USB_JTAG`, no secure boot, no flash encryption. `SECURE_BOOT=n` and `SECURE_FLASH_ENC_ENABLED=n` are asserted by pre-commit. The eFuse baseline (`docs/hw/efuse-baseline.json`) is read once in E2 and is thereafter a record, not a target.
3. **Never flash `ota_0`.** It holds the golden recovery image. Development builds go to `ota_1`; OTA rollback (`esp_ota_mark_app_valid_cancel_rollback()` only after display + touch + PMU + USB are confirmed) is the safety net, and the 3 s unconditional boot guard at the top of `app_main` (`CONFIG_SPECTRAL_BOOT_GUARD_MS`, never reduced) is the last one.
4. **Never enter light or deep sleep without the gate** ("awake ≥ N s AND no USB host present", NVS "armed" flag during development, timer wake configured). Early sleep is one of the five documented ways to lose the USB-Serial-JTAG port.
5. **Never put Arduino, LilyGoLib, or arduino-esp32 in the tree, in `idf_component.yml`, or on the link line.**
6. **Never compile with `-ffast-math`** (or `-Ofast`). The watch and the host must agree to a stated tolerance; fast-math breaks IEEE semantics on one side only. `APP_REPRODUCIBLE_BUILD=y` stays on.
7. **Never touch the backlight (GPIO45) before the `VDD_SPI_FORCE` eFuse has been read and ADR 0016 is written.** GPIO45 is the VDD_SPI strap on a 1.8 V flash; a wrong level across a reset is a hardware-destruction risk.
8. **Never enable `APP_PROJECT_VER_FROM_CONFIG`, `IDF_EXPERIMENTAL_FEATURES`, 120 MHz PSRAM, or the ESP-SR/ESP-ADF AFE/NS/AGC/AEC** — the first three for reproducibility and silicon reasons, the last because non-linear pre-processing corrupts spectra, formants and H1–H2.

### Architectural tenets (proposal §3, to be confirmed by ADR 0002/0003/0006)

1. **All real-time DSP stays on the watch.** The host never sees live audio; it sees takes. Latency and refresh are therefore properties of the firmware alone.
2. **The microphone decides everything.** One PDM mic on I2S0, 16-bit, software DC removal, no hardware high-pass on the S3. Its in-situ response through the case is measured, not assumed; every level or band-ratio readout is relative/within-session until a calibration chain says otherwise.
3. **Internal SRAM is the binding resource.** FFT working buffers (real-8192 costs ≈ 112–144 KB depending on whether it runs on the radix-2 or radix-4 kernel — `(prov.)`, see [`docs/architecture/03-dsp-pipeline.md`](docs/architecture/03-dsp-pipeline.md) §4.1) are internal and 16-byte aligned; PSRAM is for history, fonts and LVGL assets only, never DMA.
4. **The analyzer canvas may bypass LVGL** (raw `esp_lcd` + ST7789 hardware vertical scroll) to reach 50 Hz; LVGL renders chrome. Gated on verifying the scroll axis against `MADCTL` (ADR 0007).
5. **Recovery before features.** Boot guard, USJ console, OTA rollback, partition offsets frozen (ADR 0014/0015) ship from the first firmware commit.
6. **Validation is part of the design.** Every architectural choice maps to a measurable acceptance metric in [`docs/validation/`](docs/validation/), reported on both measurement paths, with an external anchor and a stated uncertainty.

### Architecture Decision Records

- One non-trivial decision per ADR, kept short. Format, numbering and the pre-registered backlog live in [`docs/adr/README.md`](docs/adr/README.md); numbers are allocated when a decision is *identified*, not written.
- An ADR ships as a coordinated multi-file commit: the record, the index update, and every downstream document it changes (proposal §, validation row, bibliography "Why" cell, BOM row). Update the index in the **same** commit.
- Amend rather than supersede. Consequences are sign-tagged `(+)` / `(−)`; alternatives carry a verdict and a revisit trigger; every ADR closes with a `Reference basis:` bullet citing bibliography entries by positional address (`01 #3`, `05 #12`).
- Hardware-gated ADRs (0016 VDD_SPI/GPIO45) stay `proposed` until the E2 eFuse read; toolchain ADR 0001 stays `proposed` until the E1 gate build passes.

### Documentation style

- Markdown for new docs; vendor-supplied PDFs kept verbatim, `_notes.md` alongside for human annotations, generated `.ocr.md` sidecars gitignored.
- English everywhere (single-language rule).
- Cross-link with relative paths so docs work both on GitHub and offline. ASCII box-drawing diagrams in fenced blocks; no Mermaid.
- Cite proposal sections (`§3`, `§4`), ADR numbers, datasheet pages and ESP-IDF **symbols or strings** (never line numbers — they rot across minor releases).
- Unsettled values are `(prov.)` or `TBD`; never invent a number. Bibliography rows name what they ground; files end with `## Acquisition links` and `## Disclosure`.
- When a document is filed, add a `📥 Filed locally:` blockquote to its bibliography entry and run `python3 -m doc_ocr extract` from [`python-scripts/doc_ocr/`](python-scripts/doc_ocr/).

### When to commit and push

- Make small, semantically meaningful, subsystem-prefixed commits (`docs: …`, `devenv: …`, `firmware: …`, `ADR 0003: …`). Avoid "WIP" commits to `main`.
- **There is no remote yet.** Commits stay local on `main` until Alexander creates the GitHub repository and asks to push. Never add a remote or push on your own initiative.
- Never `git push --force` or `git reset --hard` on `main` without explicit authorization for the specific operation.
- The orchestrating session commits; agents writing files do not run state-mutating git commands.

## Working style with Alexander

- Lead with the design decision and the trade-off, not the rationale. He'll ask if he wants more.
- Cite proposal sections (`§3`, `§4`), ADR numbers, and datasheet pages when arguing for a choice.
- When a question has a clean experimental answer, propose the experiment instead of guessing — and write it as a recipe under `docs/validation/experiments/`.
- Prefer professional tooling — ESP-IDF, CMake/Ninja, OpenOCD, QEMU, pytest-embedded, Praat/parselmouth, mir_eval — over hobbyist alternatives (Arduino IDE, copy-pasted pin tables).
- Respect the 16-week timeline and the irreversible operations list. Measurements on the watch that cannot be undone (first custom flash, first backlight write) wait for their checklist.
- Don't add scope beyond what the current task asks.

## Quick reference

- **Proposal:** [`docs/proposal/01-super-spectral-proposal.md`](docs/proposal/01-super-spectral-proposal.md) · **Research statement:** [`docs/proposal/research-statement.md`](docs/proposal/research-statement.md)
- **Roadmap:** [`docs/roadmap/documentation-roadmap.md`](docs/roadmap/documentation-roadmap.md)
- **Environment:** [`.envrc`](.envrc) · [`docs/devenv/setup.md`](docs/devenv/setup.md) · [`docs/devenv/brick-runbook.md`](docs/devenv/brick-runbook.md) · [`docs/devenv/first-flash-checklist.md`](docs/devenv/first-flash-checklist.md)
- **Board facts:** [`docs/hw/twatch-s3-pins.md`](docs/hw/twatch-s3-pins.md) · [`hardware/bom/bill-of-materials.csv`](hardware/bom/bill-of-materials.csv)
- **Record formats:** [`protocols/specs/`](protocols/specs/)
- **Architecture decisions:** [`docs/adr/`](docs/adr/) — toolchain: [0001](docs/adr/0001-toolchain-esp-idf-v6-pinned-environment.md); companion split 0002, mic path 0003, split licensing 0004, anti-brick 0015 are pre-registered in the index
- **Validation:** [`docs/validation/README.md`](docs/validation/README.md) · **Bibliography:** [`docs/bibliography/README.md`](docs/bibliography/README.md)
