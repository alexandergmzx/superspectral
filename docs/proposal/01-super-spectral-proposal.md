# Super Spectral: a wrist-worn, real-time singing-voice spectral analyzer with a Linux companion

> **DRAFT (2026-08-21, unattended session).** Structure, evidence and citations are in
> place; the prose is a starting point, not the author's voice. Nothing here is frozen —
> §1's research question is the only part already treated as binding elsewhere in the repo
> and must not be altered.

> **Revision note (2026-08-20).** Skeleton filed in documentation-roadmap phase D0; prose is written in phase D2 once the bibliography ([`../bibliography/`](../bibliography/README.md)) exists to cite. Values marked `(prov.)` are provisional and `TBD` values are unsettled; each is tracked in the [roadmap routing table](../roadmap/documentation-roadmap.md). The research question becomes binding when its `(prov.)` tag is removed in the D2 closing commit.
>
> **Citation note.** Technical claims carry inline citation addresses of the form `NN #k` (bibliography file number and entry) that resolve in [`../bibliography/`](../bibliography/README.md); thematic files 08–11 use letter-prefixed entries (`08 #S9`, `09 #R1`, `11 #A33`).

## Section 1: Motivation and research question

### Motivation

Real-time visual feedback for singers is a thirty-year-old field with its own evidence base, not a novelty. Howard et al.'s **WinSingad** (05 #68) put a narrow-band spectrogram, an f0 trace and a singer's-formant ratio in front of teachers and students in a studio; Hoppe, Sadakata & Desain's review (05 #70) surveys Singad, Albert, Sing&See and WinSingad and concludes that real-time visual feedback improves singing ability; Wilson et al. (05 #71) is the controlled pitch-accuracy study behind the f0 display specifically; a 2022 review (05 #73) and a 2026 survey of automatic singing assessment (05 #74) bring the lineage up to date and name the persistent gap as the absence of standardised evaluation frameworks. Commercial descendants — Sing&See (09 #R1), VoceVista (09 #R2) — are desktop products. **Every one of them lives on a screen that a singer cannot look at while singing.**

The founding document of this project, [`../research/00-linux-analyzer-architecture-and-build-guide.md`](../research/00-linux-analyzer-architecture-and-build-guide.md), designed the Linux answer: a preset-driven analyzer whose six presets (`live_singing`, `vowel_formant_study`, `sustained_pitch_lab`, `diction_consonants`, `room_noise_floor`, `stem_analysis`) encode chosen operating points on the Δf·Δt curve, with the live path in the browser and the offline science — Praat-grade formants, LTAS, H1–H2, DTW against a separated stem — in Python. It is a good design and it is the ancestor of everything below. What it cannot fix is the *place* the display has to be.

A phone or laptop analyzer fails in a rehearsal room for four reasons that are not about DSP:

1. **It needs a surface and a hand.** A stand, a music desk or a held phone; a singer mid-phrase has neither.
2. **It is not glanceable.** The useful feedback interval is one phrase; the interaction budget is one glance and no touch. That is precisely the budget the small-screen design guidelines are written for (09 #R3, 09 #R4) — and it is the budget a wrist display is built around, whereas a phone on a stand is not.
3. **Its audio front end is not yours.** Mobile and browser capture chains apply echo cancellation, noise suppression and automatic gain control by default; all three are non-linear and corrupt exactly the quantities being measured — spectra, formants, H1–H2. The founding document's own remedy (`echoCancellation:false, noiseSuppression:false, autoGainControl:false`) is a request, not a guarantee, and some drivers process regardless.
4. **It is a second device to carry, charge and keep unlocked** for a practice session that may be twenty minutes in a corridor.

The honest counter-argument is that the wrist is also the *worst* acoustic position available: roughly 30 cm from the mouth, off-axis, moving, behind a sealed plastic case, with a consumer PDM MEMS microphone whose datasheet was written for voice pickup, not measurement. That objection is the reason this proposal exists rather than a feature list. Titze & Winholtz (05 #65) already measured the degradation of perturbation measures at 4 cm / 30 cm / 1 m and 0° / 45° / 90° — the wrist sits inside that grid. Švec & Granqvist (05 #63) state the admissibility criteria a microphone must meet to be used in voice-production research at all, and (05 #64) that an SPL figure without its mouth-to-microphone distance is meaningless. Katz & d'Alessandro (05 #66) show that singing directivity is strongly frequency-dependent in exactly the 2.5–5 kHz band the timbre readouts care about.

So the question is not "can an ESP32-S3 compute an FFT" — it can, comfortably (§3.3). The question is whether a wrist-worn consumer-MEMS device can produce numbers a voice teacher may act on, **with the errors stated**, and whether saying so is falsifiable.

### Research question

> **RQ (prov.)** — Can a wrist-worn ESP32-S3 device with a single PDM MEMS microphone, acting as the live-capture and real-time-display front end of a preset-driven singing-voice analyzer, estimate singing f0 within ±20 cents median absolute error (≥90 % RPA @ 50 cents) on the acoustic path and ≤5 cents vs Praat on the digital-injection path, render a ≥30 Hz spectrogram (50 Hz for the live-singing preset) with ≤80 ms acoustic-to-photon latency, and sustain ≥3 h of continuous analysis on its own battery — with all real-time DSP on-device and the host used only for offline analysis of recorded takes?

The question follows the swarm grammar — *system class + method + primary metric + secondary constraint + bounded environment + architectural prohibition* — and carries three numeric bounds plus one prohibition. Each bound names the instrument that can refute it; a bound whose refutation procedure is not written down is a slogan.

1. **Fidelity bound.** f0 within **±20 cents median absolute error and ≥ 90 % raw pitch accuracy at a 50-cent threshold** on the *acoustic* path (the whole chain: case, port, microphone, PDM→PCM, clock, estimator), and **≤ 5 cents median vs Praat** on the *digital-injection* path (the estimator alone). Two paths, reported separately, always (§4.1). The anchors are the MIREX / `mir_eval` convention for RPA (05 #53, 07 #13) and Praat/parselmouth golden files (05 #7, 05 #55; [`../validation/golden-files.md`](../validation/golden-files.md)). **Falsifiable by:** running the Tier-1 corpora (10 #1, 10 #2) through both paths and reporting `mir_eval` RPA/RCA/OA/VR/VFA plus median |Δcents| against a pinned Praat manifest. A single corpus run below 90 % RPA @ 50 c on the acoustic path refutes the bound as stated. The RCA − RPA gap is reported alongside because that gap *is* the octave-error rate (05 #9).
2. **Real-time bound.** A spectrogram refreshed at **≥ 30 Hz** for every preset and **50 Hz for `live_singing`**, with **≤ 80 ms acoustic-to-photon latency** measured stimulus-onset-to-first-pixel with a phototransistor on the panel. The refresh figure is what the display path can sustain (§3.4); the latency anchor is the action–sound and visual-biofeedback literature (05 #83, 05 #84, 05 #85), which puts action–sound thresholds near 10 ms but tolerates considerably more for *visual* biofeedback — the 80 ms bound is deliberately conservative and is stated with its anchor rather than inherited from a desktop tool. **Falsifiable by:** an oscilloscope with the drive signal on channel 1 and a phototransistor taped to the LCD on channel 2, 100 repetitions per preset, plus a firmware frame counter that is *cross-checked* against the phototransistor and never trusted alone.
3. **Autonomy bound.** **≥ 3 h** of continuous analysis on the watch's own cell, measured full-charge-to-PMU-cutoff per preset with an external energy analyzer (01 #33, 01 #34) on a battery pigtail, cross-checked against the AXP2101 coulomb counter (01 #17) — where a disagreement between the two is a finding, not a nuisance. The cell capacity is itself unsettled: **470 mAh per the vendor library and the Zephyr board files, 400 mAh per resellers** — `TBD`, roadmap Q9/T9 ([`../hw/twatch-s3-pins.md`](../hw/twatch-s3-pins.md)). **Falsifiable by:** one 3-hour run per preset; the bound stands or falls per preset, and a preset that fails it becomes a documented operating limit rather than a hidden one.
4. **Architectural prohibition.** All real-time DSP runs on the device; the Linux host ([`../../host/README.md`](../../host/README.md)) is used **only** for offline analysis of recorded takes. Without this clause the question is trivially answerable by streaming audio to a PC, and the result is not a wearable result. It also makes latency and refresh properties of the firmware alone, which is what makes bound 2 measurable at all.

A fifth thing the question deliberately does *not* claim: absolute sound pressure level, clinical meaning, or accuracy against a class-conformant sound level meter. Those are ruled out in §7.1 and by the no-clinical-claim decision pre-registered in the ADR backlog as ADR 0005 ([`../adr/README.md`](../adr/README.md)).

## Section 2: Objectives

Five objectives, in list order; the rest of the repository refers to them as **O1–O5** (the bibliography's "Why" cells and the validation rows use those labels).

1. **Design and validate an on-device DSP front end** — PDM capture, windowed FFT with stated normalisation and window conventions, time-domain f0 estimation, band-energy / FHE / SPR readouts — on the ESP32-S3, meeting the fidelity bound on both measurement paths and with every convention (S1/S2, NENBW, periodic windows, dBFS reference) pinned in a single spec shared by watch and host (05 #1, 05 #2, 05 #3; ADR 0006, pre-registered in the ADR backlog).
2. **Define the companion architecture and its record-format contract** — the normative split of features between watch and host (§3.2), the on-flash take and feature records, and the preset schema ([`../../protocols/specs/README.md`](../../protocols/specs/README.md)) — so that the watch is useful with no host present and the host can reproduce every on-device number offline from the recorded take.
3. **Build and evaluate a prototype on the wrist** with at least **N sessions × M singers** (`N`, `M` `TBD` pending a power analysis; prov. N ≥ 10 sessions, M ≥ 5 singers) under a stated wrist-position envelope, with simultaneous reference-microphone capture and the session design taken from the visual-feedback efficacy studies (05 #71, 05 #72) rather than invented.
4. **Quantify the trade-off between preset, refresh rate and energy** — cycles, mAh/h and mJ per analysis frame per preset, including the marginal energy cost per decimation stage — so that the autonomy bound is a measured frontier rather than a single point, and so that a user-facing "long session" mode is a documented position on that frontier.
5. **Publish an open, reproducible validation framework** — `mirdata`-managed corpora with checksums (05 #54, 06 #30), `mir_eval` metrics (05 #53, 06 #29), the Praat golden-file manifest (06 #31), host and QEMU CI lanes (11 #A36, 11 #A33), a pinned toolchain (11 #A31) — so that a third party can rebuild the device, rerun the experiments, and land within the stated tolerances.

## Section 3: Technical approach

### 3.1 Hardware and platform

The platform is a **LilyGO T-Watch S3**, chosen because it is a commodity, purchasable, sealed consumer smartwatch — the point is not to build ideal hardware but to find out what honest measurement is possible on hardware a singer could actually buy. The facts below marked **measured** were read off *this* unit (MAC `48:27:e2:e9:b0:8c`) in roadmap phase E2 and are recorded with their commands in [`../hw/README.md`](../hw/README.md); the rest are derived from the schematic and vendor sources per [`../hw/twatch-s3-pins.md`](../hw/twatch-s3-pins.md).

| Fact | Value | Status |
|---|---|---|
| SoC | ESP32-S3-R8, bare QFN56 **chip-down** (not a WROOM module), **chip revision v0.2**, 40 MHz crystal, dual Xtensa LX7 @ 240 MHz | **measured** (`esptool chip-id`) |
| Memory | 512 KB internal SRAM; **8 MB in-package octal PSRAM** reported as `AP_3v3` | **measured**; 01 #21 |
| Flash | 16 MB, JEDEC `ef 4018` → Winbond **W25Q128JV-class, 3.3 V**; *"Flash voltage set by eFuse: 3.3V"*. The schematic and the Zephyr board files name a **1.8 V W25Q128JW** — **the part number does not describe this unit** | **measured** (`esptool flash-id`); contradicts 01 #6/#20 |
| VDD_SPI domain | `VDD_SPI_FORCE = True`, `VDD_SPI_XPD = True`, `VDD_SPI_TIEH = VDD3P3_RTC_IO` → **VDD_SPI is forced to 3.3 V by eFuse**; GPIO45 (backlight) is never sampled as a strap; GPIO47/48 sit in the 3.3 V domain | **measured** ([ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md)) |
| Microphone | one **Knowles SPM1423HM4H-B** PDM MEMS, CLK GPIO44 / DATA GPIO47, on **I2S0 only, PDM RX is 16-bit only**; sensitivity −22 dBFS, SNR 61.5 dB(A), PDM clock 1.0–3.25 MHz; AOP **110 dB SPL** (Rev A, page-verified; Rev D says 115 — pin the revision, Q13). **Obsolete at distributors** | 01 #9, 02 #15; revision `TBD` |
| Sample rates | 16 kHz (`DSR_16S`, 2.048 MHz) · **32 kHz default** (`DSR_8S`, 2.048 MHz) · 48 kHz needs 3.072 MHz — **178 kHz of margin, 5.5 % of the mic's 3.25 MHz ceiling** — gated on measurement (threshold T3) | 01 #9, 02 #14 |
| No hardware PDM high-pass | `SOC_I2S_SUPPORTS_PDM_RX_HP_FILTER` is absent from the esp32s3 `soc_caps.h` **in the pinned v6.0.x tree** — DC removal is in software, and the claim is pinned to that IDF version because the header is a moving target | 02 #16 |
| Display | 240×240 **ST7789V3** over SPI (MOSI 13 / SCK 18 / CS 12 / DC 38), backlight GPIO45 on LEDC, panel reset follows the ALDO3 rail | 01 #13; pins doc |
| Other | FT6336U touch on I²C1 (01 #16) · AXP2101 PMU on I²C0 (01 #17) · MAX98357A Class-D amplifier on I2S1 as the calibration-tone source (01 #11) · BMA423 · PCF8563 · DRV2605L · SX1262 (held in reset, [ADR 0017](../adr/0017-no-radio-in-v1-trimmed-component-set.md)) | pins doc |
| Access | **zero exposed GPIO**; native USB-Serial-JTAG on GPIO19/20 is the *only* flash and debug path; BOOT button inside the case; `DIS_USB_JTAG` and `DIS_USB_SERIAL_JTAG` both `False` | **measured**; [ADR 0015](../adr/0015-anti-brick-policy.md) |

Bill of materials: [`../../hardware/bom/bill-of-materials.csv`](../../hardware/bom/bill-of-materials.csv). Toolchain: **ESP-IDF v6.0.2 native, pinned and reproducible** ([ADR 0001](../adr/0001-toolchain-esp-idf-v6-pinned-environment.md), accepted after the gate build passed on hardware; 11 #R1, 11 #A31); no Arduino in any phase; Zephyr is the recorded rejected alternative (no Espressif PDM driver). esp-dsp for the FFT (Apache-2.0, 06 #1), LVGL for chrome (MIT, 06 #12). The build contains only `main` and what it requires — no Wi-Fi, BT, lwIP or OpenThread ([ADR 0017](../adr/0017-no-radio-in-v1-trimmed-component-set.md)).

### 3.2 Companion split (normative; [ADR 0002](../adr/0002-companion-architecture.md), accepted)

The split is decided by physics and by licence, not by convenience: anything whose value depends on being *live* runs on the watch; anything that needs Praat, a whole take, or more numerical care than a 16-bit consumer capture deserves runs on the host. The line is drawn once, here, and every feature is on one side of it.

| Feature | On-watch (live) | Host (offline, on takes) | Rationale |
|---|:---:|:---:|---|
| FFT magnitude spectrum, all six presets | ✅ | ✅ | 1.3–8.9 % of one core at 50 Hz for real N = 1024…8192 (§3.3) |
| Spectrogram waterfall (hardware-scrolled) | ✅ | ✅ | ~480 B per new column with ST7789 vertical scroll (gated, T4); ≈10 min of 256-bin history in PSRAM |
| Peak markers, max-hold, exponential smoothing | ✅ | ✅ | negligible |
| Time-domain f0 (MPM / YIN / dywapitchtrack) | ✅ | ✅ (pYIN / Praat reference) | ≈6 % of a core `(prov.)`; MPM needs ~2 periods, which is what fits a 20 ms hop (05 #8) |
| Band energy: ring 2.5–3.5 kHz, twang 3.5–5 kHz | ✅ with the fitted mic EQ | ✅ | the uncorrected value is always shown too |
| FHE (05 #37) and Omori peak-to-peak SPR (05 #35) | ✅ relative, within-session | ✅ with an SPL co-report | LTAS level tracks loudness strongly up to 4 kHz (05 #36): uninterpretable without a level estimate |
| Octave / 1/3-octave bank (decimation cascade) | ✅ | ✅ | IIR, ≈1.4 % of a core for 4 stages `(prov.)`; the cascade method is Crochiere & Rabiner / Hogenauer (05 #91, 05 #90) |
| A/C/Z weighting, Leq | ✅ (dBFS unless calibrated in-session) | ✅ | relative only without a calibrator (01 #30) |
| Low-order LPC F1/F2 overlay | ⚠️ marginal | ✅ Praat Burg + FormantPath | hand-ported (no LPC in esp-dsp); degrades at high f0 (05 #16, 05 #17) |
| Praat-grade Burg formants, FormantPath ceiling optimisation | ✗ | ✅ | the golden-file reference (05 #55) |
| LTAS / SPR over whole takes | ⚠️ accumulate only | ✅ | interpretation needs the SPL co-report (05 #36) |
| H1–H2 (Iseli–Alwan corrected), Kreiman 4-parameter slope | ✗ | ✅ | needs F1–F3 *and* bandwidths (05 #20, 05 #23) |
| CPP / CPPS, AVQI-class composites | ✗ | ✅ | acoustic material only; no clinical claim ([ADR 0005](../adr/0005-no-clinical-claim.md), accepted) |
| DTW alignment, Demucs stem separation | ✗ | ✅ | host only; the founding document's offline compare mode |
| Take recording (OPUS / PCM) | ✅ | ingests | coexists with the FFT load (02 #19) |
| AFE / NS / AGC / AEC | ✗ never | ✗ never | non-linear; corrupts spectra, formants and H1–H2 — the same rule as the browser path's disabled constraints |

Licensing follows the same line: Apache-2.0 for the repository, firmware, documentation and tooling; `host/` **GPL-3.0-or-later** with its own `LICENSE` so it may import parselmouth/Praat in-process; no code crosses the boundary in either direction, only files on disk ([ADR 0004](../adr/0004-split-licensing.md), accepted; 03 #36, 03 #37, `NOTICE`).

### 3.3 DSP feasibility envelope

**The headline is that the FFT is not the bottleneck.** The binding constraints are, in order: microphone acoustics → internal SRAM → display pixel bandwidth → power → clock accuracy. The tables below are derived from published benchmarks (02 #21, 11 #A1) and the ESP32-S3 datasheet (01 #1); **every one is replaced by an on-target measurement in Phase 1** and is `(prov.)` until then.

**Cost vs resolution.** FFT cost depends only on N, not on the sample rate: `f_s` changes the hop (`f_s`/refresh) and the physical window duration (`N/f_s`), not the arithmetic. The meaning changes enormously, which is what the presets encode.

| Real N | Bin width @ 16 / 32 / 48 kHz | Window duration @ 16 / 32 / 48 kHz | % of one core @ 50 Hz `(prov.)` |
|---|---|---|---|
| 512 | 31.3 / 62.5 / 93.8 Hz | 32 / 16 / 10.7 ms | 0.39 % |
| 1024 | 15.6 / 31.3 / 46.9 Hz | 64 / 32 / 21.3 ms | 1.30 % |
| 2048 | 7.8 / 15.6 / 23.4 Hz | 128 / 64 / 42.7 ms | 1.88 % |
| **4096** | **3.9 / 7.8 / 11.7 Hz** | **256 / 128 / 85.3 ms** | **6.21 %** |
| 8192 | 2.0 / 3.9 / 5.9 Hz | 512 / 256 / 171 ms | 8.89 % |
| 16384 | 1.0 / 2.0 / 2.9 Hz | 1024 / 512 / 341 ms | ≈29 % (extrapolated) |

**Internal SRAM is the binding resource.** The figures below are computed from esp-dsp 1.8.2's own allocation sites ([esp-dsp notes §4.1](../reference-projects/notes/esp-dsp_notes.md)), not from the "10·N bytes" rule of thumb inherited from the research — that rule does not match even its own itemisation and is not used here. There are two figures per size because the cost turns on a single dependency: `dsps_cplx2real_fc32` needs `dsps_fft4r_init_fc32`'s twiddle table (`16·N_c` bytes, i.e. `8·N`) **even when the transform itself runs on the radix-2 kernel**, so writing our own `cplx2real` — which needs only the `4·(N_c+2)` bytes of half-bin angles — removes `6·N`. Linearly: **`12·N` with our own `cplx2real`, `18·N` with esp-dsp's tables**, plus a sub-linear bit-reversal copy. One S3 special case: at `N_c ≤ 1024` (real N ≤ 2048) the radix-2 twiddles come from a const ROM table and cost no heap at all.

| Real N | Own `cplx2real` | esp-dsp's own tables | Verdict |
|---|---:|---:|---|
| 2048 | ≈ 22 KB | ≈ 36 KB | trivial |
| 4096 | ≈ 52 KB | ≈ 78 KB | comfortable |
| **8192** | **≈ 104 KB** | **≈ 160 KB** | **the largest preset; ADR 0006 decides which column we pay — [03-dsp-pipeline §4.1](../architecture/03-dsp-pipeline.md)** |
| 16384 | ≈ 200 KB | ≈ 304 KB | hard ceiling (LVGL small, no radio); not in v1 |
| 32768 | ≈ 400 KB | ≈ 592 KB | not viable — larger than the whole internal heap |

These are the **FFT working set only**: the int16 input ring (`2·N`), the display-side column buffers and LVGL's own draw buffers are separate. They are computed from the library's allocation calls, not yet measured on target — roadmap Q21 closes that with `heap_caps_get_free_size()` either side of init.

**PSRAM cannot rescue this, and the reason is bandwidth, not capacity.** Published ESP32-S3 octal-PSRAM measurements (06 #23, to be re-measured on target) put IRAM→IRAM `memcpy` at ≈366 MB/s against IRAM→PSRAM ≈32.5 MB/s and PSRAM→IRAM ≈56.8 MB/s. An in-place radix-2 real-4096 FFT makes ~11 passes ≈ 360 KB of traffic, which turns ~0.9 ms of arithmetic into 6–12 ms of memory stalls — a 7–13× slowdown `(prov.)`. Hence the architectural rule, already a tenet in `CLAUDE.md`: **FFT working buffers live in internal SRAM, 16-byte aligned** (the esp-dsp assembly kernels require the alignment); **PSRAM holds spectrogram history, fonts and LVGL assets, never DMA and never FFT scratch.** History is cheap: 256 bins × 1 byte × 50 columns/s = 12.8 KB/s, so 8 MB holds ≈10.4 minutes.

Three further points worth stating because each is easy to get wrong, and two of them were got wrong in the research syntheses this proposal is built on:

- **`sc16` fixed-point is not usable here.** The PIE integer SIMD path is much faster than `fc32`, but it applies a fixed `>>1` per stage with no block-floating-point exponent — one bit lost per stage of the complex-`N/2` transform, so real N = 2048 loses ≈60 dB of headroom (10 stages) and real N = 8192 ≈72 dB (12 stages) — out of a 16-bit input that leaves roughly 6 and 4 bits. Against the 90–100 dB range every shipped preset asks for (`db_floor_dbfs` of −90 or −100 under a 0 dBFS ceiling) that is disqualifying without writing a block-floating-point layer first, and PIE also costs measurable extra current. **`fc32` is mandated** (ADR 0006, backlog); `sc16` is a rejected alternative with a revisit trigger.
- **The dynamic range of the *display* is not capped by the microphone's broadband SNR.** A common error is to read the mic's 61.5 dB(A) SNR as a 60 dB ceiling on the spectrogram. It is not: an N-point FFT distributes broadband noise over N/2 bins, so for a tonal component the per-bin floor sits roughly `10·log₁₀(N/2 / NENBW)` below the broadband figure — about **+30 dB of processing gain at N = 4096** (05 #1). The mic's SNR bounds *wideband level* accuracy; the per-bin spectral dynamic range is a separate, measurable quantity and has its own row in [`../validation/README.md`](../validation/README.md).
- **esp-dsp 1.8.2 has no dedicated real-FFT entry point.** The research synthesis recorded one (`fft4real`); reading the tree at v1.8.2 shows that `examples/fft4real/` is a *directory* and that no `dsps_fft4real_*` symbol exists ([esp-dsp notes §2.1](../reference-projects/notes/esp-dsp_notes.md)). The budgets above are for the route that does exist — pack into complex `N/2`, `dsps_fft2r_fc32`, `dsps_bit_rev*`, `dsps_cplx2real_fc32` — with a `(prov.)` +10–20 % overhead that is **not** in the published benchmark table. Measured on target in Phase 1 (roadmap Q21) via `dsp_get_cpu_cycle_count()`, trended in CI.

### 3.4 Display path and why 50 Hz needs the hardware scroll

240×240 RGB565 is **115,200 bytes per full frame**. At the 80 MHz an IOMUX-routed SPI master can reach, a full-frame blit costs ≈11.5 ms of bus time before any DSP runs; through LVGL's normal widget-redraw path with partial internal-SRAM buffers, measured comparable hardware lands near **30 fps** (02 #25). That is enough for the ≥ 30 Hz bound and **not** enough for the 50 Hz `live_singing` bound.

The ST7789's hardware vertical scroll (`VSCRDEF` 0x33 / `VSCSAD` 0x37, 01 #13) changes the arithmetic completely: a waterfall advances by writing **one new 240-pixel row — 480 bytes, ≈48 µs** — and letting the controller move the scroll origin. The spectrum strip and chrome are then the only redrawn regions. This is what makes 50 Hz reachable, and it is why the analyzer canvas bypasses LVGL and talks to `esp_lcd` directly, with LVGL rendering only menus, the preset picker and the status bar (ADR 0007, backlog; 02 #23).

**This is a gated design, not a settled one.** `VSCRDEF`/`VSCSAD` scroll along the panel's *native* vertical axis and interact with `MADCTL` rotation; the non-scrolling spectrum strip must fall inside the fixed top/bottom areas; and the chosen `esp_lcd` driver may not expose the commands without a raw `esp_lcd_panel_io_tx_param()`. If the time axis does not align with the native scroll axis, roadmap **threshold T4** fires: the canvas reverts to full-frame blits, the refresh target becomes ≈30 Hz for all presets, **the 50 Hz clause is dropped from the research question**, and the power budget is re-derived. That consequence is pre-committed so the plan changes by rule rather than by argument on the day.

### 3.5 Signal path

```
                      ┌──────────────────────── WATCH (live path, ESP-IDF v6.0.2) ──────────────────────┐
 singer ─► case/port ─┤                                                                                 │
                      │  SPM1423 PDM ──► I2S0 PDM RX ──► PCM ring (internal SRAM, DMA-capable)          │
                      │  (1.024-3.072 MHz)  16-bit                │                                     │
                      │                                            ├──◄── file_blob  (corpus WAV)       │
                      │                                            └──◄── synthetic  (Tier-0 generator) │
                      │                                                                                 │
                      │  CORE 1 (DSP)                                                                   │
                      │   DC removal ─► window ─► esp-dsp FFT fc32 ─► |X|² ─► dB (fast log)             │
                      │      ├─► f0 (MPM / YIN) ────────────► cents · vibrato                           │
                      │      ├─► band energy ─► ring/twang (EQ-corrected + raw) ─► FHE · SPR            │
                      │      └─► decimation cascade ─► octave bank ─► A/C/Z · Leq                       │
                      │                                                                                 │
                      │   double-buffered magnitude + feature record ──► queue of POINTERS (no memcpy)   │
                      │                                                                                 │
                      │  CORE 0 (UI)                                                                    │
                      │   analyzer canvas: raw esp_lcd + ST7789 VSCRDEF/VSCSAD  ─┐                      │
                      │   LVGL chrome · PMU · haptics · touch                    ├─► ST7789V3 240x240   │
                      │   spectrogram history ──► PSRAM (~10 min)                ┘   >=30 Hz; 50 Hz LS  │
                      │                                                                                 │
                      │   takes ──► FAT partition          presets ──► littlefs partition               │
                      └──────────────────────────────────┬──────────────────────────────────────────────┘
                                                         │  USB-Serial-JTAG (the only port)
                      ┌──────────────────────────────────┴──────── HOST (offline, GPL-3.0-or-later) ────┐
                      │  ingest takes ─► Praat/parselmouth (formants, pitch reference) · LTAS/SPR · FHE  │
                      │                 H1-H2 (Iseli-Alwan) · CPPS · DTW align · Demucs stems           │
                      │                 golden-file generation ─► tolerance table ─► CI                  │
                      └─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.6 Presets

The six presets of the Linux analyzer are carried over unchanged in intent and made explicit in specification: `live_singing` (4096, Blackman-Harris, 20 ms hop) · `vowel_formant_study` (8192, Hann) · `sustained_pitch_lab` (8192, Blackman-Harris, 40 ms) · `diction_consonants` (1024, Hann, 10 ms) · `room_noise_floor` (8192, Hann, linear average, min-hold) · `stem_analysis` (host-only). Three fields are added that the founding document did not need: an **explicit analysis bandwidth / ENBW** per preset instead of the informal "wideband/narrowband" convention (05 #6, 05 #2), a **mic-EQ slot** filled by experiment 0001, and a **clock-correction constant**. The schema is JSON, versioned, owned by [`../../protocols/specs/README.md`](../../protocols/specs/README.md) and stored on the littlefs partition ([ADR 0010](../adr/0010-preset-schema.md), accepted; [`../architecture/README.md`](../architecture/README.md) planned doc `07-preset-schema.md`).

### 3.7 Energy budget

Derived in [`../architecture/README.md`](../architecture/README.md) planned doc `06-power-budget.md`, and it ends in a pass/fail verdict against the ≥ 3 h bound rather than an estimate. The SoC term is bounded by the datasheet (01 #1, Table 5-9): 240 MHz dual-core 32-bit is **66.2 mA (Typ1) / 81.3 mA (Typ2)**, 160 MHz dual-core **49.6 / 64.1 mA**, 240 MHz WAITI **32.9 / 47.6 mA**. **The two largest terms are unmeasured and are not estimated here:** the active current of the in-package octal PSRAM (not in Espressif's datasheet — vendor-specific) and the backlight at a usable outdoor brightness, which is plausibly the single largest consumer. Both are Phase-1 per-rail measurements (roadmap Q26); until they exist, the autonomy figure in this proposal is `TBD`, not a range.

Power levers, in order of expected effect: backlight PWM and auto-dim; 240 → 160 MHz when N ≤ 2048; `fc32` rather than PIE `sc16`; 50 → 25–30 Hz refresh on a static signal; and no radio at all ([ADR 0017](../adr/0017-no-radio-in-v1-trimmed-component-set.md)). The AXP2101 charge current is capped below 130 mA per vendor guidance for the fitted cell.

### 3.8 Recovery and safety

On a sealed board with zero exposed GPIO and the BOOT button inside the case, recovery is not a feature — it is the precondition for having a project at all, and it ships before any analysis code.

- The 16 MB partition layout is **frozen**: two 4 MB OTA slots, no factory app, `ota_0` reserved as the golden recovery image ([ADR 0014](../adr/0014-partition-layout-frozen.md)).
- The anti-brick policy is a stack of independently tested layers: a 3 s unconditional boot guard, `_Static_assert` + CI grep on GPIO19/20, mark-valid criteria that require display + touch + PMU + USB to be alive before an image commits itself, a sleep gate, the USB-Serial-JTAG console, and eFuses that are read-only for the life of the project ([ADR 0015](../adr/0015-anti-brick-policy.md)).
- GPIO45 (backlight) was decided **by measurement, not by the schematic** ([ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md)).
- All of it was verified before any feature code: [experiment 0002](../validation/experiments/0002-rollback-and-boot-guard-race.md) — rollback to `ota_0` with no host action **4/4**, and `esptool` winning the race against a 3 s-guard crash loop **10/10** (default reset) and **5/5** (USB reset), each connecting in 0.6 s against a ≈3.5 s loop period.

## Section 4: Validation plan and experimental methodology

### 4.1 The two-path rule

**This comes first because it is the rule the rest of the plan exists to serve.** Every metric that involves the signal chain is reported on **two paths, separately, in every table**:

1. **Digital-injection path** — a corpus WAV or Tier-0 synthetic signal is written straight into the firmware's PCM ring buffer through the `file_blob` audio source; the microphone is bypassed. This measures *algorithm* error. It is **the only path on which a "≤ 5 cents vs Praat" claim is legitimate.**
2. **Acoustic path** — the same signal is reproduced through a calibrated source at a fixed, stated geometry (mouth simulator per ITU-T P.51 or HATS per ITU-T P.58 — 03 #11, 03 #10, 01 #35 — or a reference monitor at a stated distance and angle), captured simultaneously by the watch and a reference microphone, then time-aligned by cross-correlation. This measures the *whole chain*: case, port, microphone, PDM→PCM, clock, estimator.
3. *(optional third path)* **Injection ⊛ RIR** — the corpus convolved with a measured room impulse response (10 #24) and injected. It isolates room effects from microphone effects at zero bench cost.

**Reporting only the acoustic path hides algorithm bugs behind acoustics; reporting only the injection path is not a wearable result at all.** Both failure modes are common in embedded-audio work and both are invisible to a reader who is given one number. The research question names both paths explicitly (±20 cents acoustic, ≤ 5 cents injection) precisely so that the two cannot be quietly merged later. The rule is normative in [`../validation/README.md`](../validation/README.md) and applies to level, band, timbre and latency metrics as well as to f0.

### 4.2 Metrics

The acceptance-metrics table — definition, target, external anchor, how to measure — **lives in [`../validation/README.md`](../validation/README.md) and is deliberately not duplicated here.** One table, one source; this proposal links to it. The same file carries the equipment list with the tolerance that matters for each instrument and the corpus tiers with their licences. Golden-file provenance and the tolerance table are in [`../validation/golden-files.md`](../validation/golden-files.md).

Three properties of that table are worth stating in the proposal itself, because they are design commitments rather than bookkeeping:

- **Every target names an external anchor.** A row whose number comes from nowhere is not frozen. Where no anchor exists the row says so.
- **Percentiles, not means.** Cents error is reported as median, p90 and p99; a mean cents error hides exactly the octave errors that matter.
- **Agreement, not correlation.** Level and timbre metrics are Bland–Altman problems (05 #86) with ICC for repeatability (05 #87) and TOST for equivalence claims (05 #89) — an `r ≥ 0.9` target would be the specific error Bland & Altman was written to correct.

### 4.3 The uncertainty budget

Every "± x dB" and "± y cents" in this proposal is meaningless without the uncertainty of the *reference* attached, so a GUM-structured budget ([`../validation/uncertainty-budget.md`](../validation/uncertainty-budget.md); 03 #20, 08 #S9) is written **before** the measurements, not after — a budget assembled afterwards is a rationalisation. It has three models: peak frequency in cents (dominated by the sample-rate error), 1/3-octave band level in dB (dominated by the reference microphone's own calibration uncertainty), and the SPR/ring ratio, where the common terms cancel and which is therefore honest as a *relative* quantity and dishonest as an absolute one.

The budget is also what makes threshold **T6** actionable: if only a UMIK-1-class reference is available (01 #31), its factory-calibration uncertainty is of the same order as the ±1.5 dB target, so the band-level metric is **restated as within-session repeatability** with the budget attached, and no absolute accuracy is claimed. An IEC 61094-4 working-standard reference (03 #7, 08 #S5) is what would change that.

### 4.4 Factorial matrix `(prov.)`

```
BENCH VALIDATION - ACOUSTIC PATH MATRIX (prov., pending a power analysis)

Preset:    live_singing | vowel_formant_study | sustained_pitch_lab |
           diction_consonants | room_noise_floor | (stem_analysis: host only, injection control)
SPL:       60 dB | 75 dB | 90 dB SPL at the reference point
Distance:  15 cm | 30 cm | 45 cm mouth-to-watch
           (to be replaced by an anthropometric distribution, ISO 7250-1 / ANSUR II - 03 #21)
Arm angle: 0 deg | 45 deg relative to the source axis

Total: 6 presets x 3 SPL x 3 distances x 2 angles = 108 acoustic trials
       + 108 digital-injection controls (one per cell)

One trial, end to end:
---------------------------------------------------------------------------
Trial 1: live_singing, 75 dB SPL, 30 cm, 45 deg
  -> vocadito excerpt through the mouth simulator (ITU-T P.51 / P.58 geometry)
  -> simultaneous capture: watch (PDM, 32 kHz) + reference mic; aligned by cross-correlation
  -> device f0 track vs corpus ground truth -> RPA@50/25/10, RCA-RPA, OA, VR/VFA (mir_eval)
  -> device f0 track vs the Praat golden file on the identical WAV (injection control)
                                             -> median |delta cents|
  -> 1/3-octave levels vs the reference analysis -> bias, Bland-Altman limits of agreement
  -> row appended to the trial table with instrument serials and the env.lock.md hash
[repeat 108 times]

Post-trial analysis:
  cents error : median, p90, p99  (CEP-style percentiles, never means)
  level       : Bland-Altman bias + LoA; ICC for repeatability; TOST for the +/-1.5 dB claim
  f0          : RPA/OA per preset x SPL x distance
  wrist       : the position envelope reported as a SURFACE, not a pass/fail
```

The trial count is `(prov.)` and explicitly **pending a power analysis** — 108 is a structure, not a sample size. The distance levels are a placeholder for an anthropometric distribution (03 #21); the fact that they are currently three round numbers is a known defect, not a design.

### 4.5 Corpora and the licence quarantine rule

Three ledgers are kept separately and never conflated: **corpus licences**, **software licences** ([ADR 0004](../adr/0004-split-licensing.md), accepted; `NOTICE`) and **golden-file provenance**. Every corpus used gets a manifest with a sha256 per file and the licence text ([`../../datasets/corpora/manifest.yaml`](../../datasets/corpora/manifest.yaml)); `mirdata` (05 #54, 06 #30) manages fetch and validation so that "the same corpus" means the same bytes.

- **Tier 0 — synthetic, generated in-repo** (10 #P1): sines on and off bin centres, linear and log sweeps, Farina exponential sweeps (05 #88), two-tone at Δf = 0.5/1/2/4 bins, white and pink noise, Rosenberg / Liljencrants–Fant glottal-source vowels with known f0 and F1–F3, AM/FM tones at 5–7 Hz for vibrato. Ground truth exact by construction. **This tier must exist before any real corpus is touched.**
- **Tier 1 — CC BY 4.0 with usable ground truth:** vocadito (10 #1, 05 #58) and Dagstuhl ChoirSet (10 #2, 05 #60) carry the f0 ground truth; VocalSet (10 #3, 05 #57) carries the technique/timbre axis; PVQD (10 #18) is used as acoustic material only.
- **Tier 2 — restricted or non-commercial:** PTDB-TUG (10 #10, 05 #56) is the most physiologically grounded ground truth available (simultaneous laryngograph) but carries institutional terms; MDB-stem-synth (10 #11) is CC BY-NC.
- **Tier 3 — pathology:** Saarbrücken (10 #19) and PVQD, **acoustic material only, no clinical claim** ([ADR 0005](../adr/0005-no-clinical-claim.md), accepted; 03 #32, 03 #33, 03 #34).

**The quarantine rule:** a corpus whose licence is non-commercial, unstated or unverified may appear in bench work but **never in a headline figure**, and the ledger records which figures it touched. A licence that cannot be quoted is treated as "all rights reserved" until it can be.

### 4.6 Phases

Weeks follow the project-phase table in the [root README](../../README.md); Phase 0 produces no measurements.

- **Phase 1 — component characterisation (weeks 4–7).** In-situ microphone response and EIN through the case; SPL calibration against a calibrator if one is available; sample-rate error against a GPSDO-referenced tone; esp-dsp and decimation cycle counts per preset; the display refresh ceiling; per-rail and per-preset current. **Deliverables: the mic EQ filter and the clock-correction constant — every later number depends on both.** Recipe: [experiment 0001](../validation/experiments/0001-pdm-mic-in-situ-characterization.md), which is also the experiment that decides thresholds **T2** (host-first pivot) and **T3** (48 kHz vs 32 kHz cap).
- **Phase 2 — bench validation (weeks 8–11).** Injection path across the Tier-0/1/2 corpora with `mirdata` + `mir_eval`; golden-file regression against parselmouth on host and QEMU CI lanes; then the acoustic path through the fixed playback geometry over the factorial matrix.
- **Phase 3 — in-use validation and release (weeks 12–16).** Singers wearing the watch with a simultaneous reference microphone (optional EGG); one-hour autonomy runs per preset; the wrist/sleeve sensitivity envelope; SPR/FHE repeatability within subject and within session; public release with a replication guide and a data-availability statement (03 #42, 03 #43).

## Section 5: Expected contributions and significance

### 5.1 Technical

An open, permissively licensed, **on-device** singing-voice analyzer on commodity smartwatch hardware, with a stated accuracy on **both** measurement paths — not a demonstration that an FFT fits, but a stated error bar on a wearable measurement. Alongside it: a measured energy/refresh/resolution frontier for preset-driven spectral analysis on the ESP32-S3 (objective 4), which does not currently exist in public form; and a reusable ESP-IDF board file plus an anti-brick policy for a sealed, USB-Serial-JTAG-only device, already demonstrated rather than asserted ([experiment 0002](../validation/experiments/0002-rollback-and-boot-guard-race.md), [ADR 0014](../adr/0014-partition-layout-frozen.md)/[0015](../adr/0015-anti-brick-policy.md)/[0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md)).

Scoped honestly: none of the DSP is novel. The novelty is the *position* — wrist, sealed case, consumer MEMS — and the fact that the errors that position introduces are measured rather than assumed.

### 5.2 Methodological — the strongest of the three

**An uncertainty-budgeted, two-path validation of a consumer-MEMS wearable against Praat-grade references, with the whole acquisition and decision trail in git.** Concretely, four transferable artefacts:

1. **The two-path reporting rule** as a discipline for embedded voice DSP, with the Praat golden-file manifest (parselmouth version → bundled Praat version → method → floor/ceiling → sha256 of every input and output) as its reproducibility instrument (06 #31, 05 #55; [`../validation/golden-files.md`](../validation/golden-files.md)). The manifest exists because "parselmouth is numerically identical to Praat" is only true *within a bundled version* — the default pitch method changed in 2023 — and the project treats that as a threshold (**T7**) rather than an assumption.
2. **A GUM uncertainty budget written before the measurements** ([`../validation/uncertainty-budget.md`](../validation/uncertainty-budget.md); 03 #20) for a device class that normally ships with a marketing figure. It is what converts "±1.5 dB" from a claim into either a defensible repeatability statement or an honest refusal.
3. **An explicit substitute for the "missing anchor" problem.** It is sometimes asserted that wearable voice metrology has no external performance-target document. For voice it has several, and they should be named rather than replaced: the ASHA recommended protocols for instrumental voice assessment (05 #31), the ELS basic protocol (05 #32), Švec & Granqvist's microphone-selection and SPL-measurement tutorials (05 #63, 05 #64), and the IEC 61672 / IEC 61260 / `mir_eval` triple for the measurement side (03 #2, 03 #4, 05 #53) — with the caveat that IEC 61672-1 alone states tolerances, and a *conformance* claim would additionally need Parts 2 and 3 (03 #3), which this project does not make.
4. **The documentation-before-firmware method itself**, carried from the author's `swarm` project and extended here with a routed open-question table: 65 open questions, each assigned to exactly one of four homes (an ADR, a validation metric row, an acquisition line, or a hardware-read checklist step), and ten pre-committed thresholds whose consequences are written down *before* the measurement that could trigger them ([`../roadmap/documentation-roadmap.md`](../roadmap/documentation-roadmap.md) §3–§4).

### 5.3 Practical

A singer's feedback tool that works with **no phone, no PC and no network** — which is also what makes it usable in a corridor, a church, or a rehearsal room with no table. A calibration-and-limits statement honest enough that a voice teacher can tell at a glance which readouts are absolute and which are within-session relative, surfaced in the UI and not only in a paper. And an accessible visual voice display: real-time visual feedback is assistive technology for deaf and hard-of-hearing singers and for speech training (05 #75), which makes a colourblind-safe, perceptually uniform default colormap with non-colour redundancy (05 #76, 05 #77; [ADR 0011](../adr/0011-spectrogram-colormap.md), proposed) a functional requirement rather than a preference.

## Section 6: Timeline and milestones `(prov.)`

All weeks are provisional and follow the project-phase table in the [root README](../../README.md); the internal structure of Phase 0 is the D/E track roadmap.

| Phase | Weeks | Deliverables | Status |
|---|---|---|---|
| **0 — Documentation & environment** | 0–3 | Constitution (`CLAUDE.md`, layout, CI); bibliography files 01–11 + acquisition ledger; this proposal with the RQ frozen; ADRs 0001–0006 accepted; pinned reproducible ESP-IDF v6.0.2 environment; eFuse baseline and vendor partition table read; recovery path tested; validation plan frozen (gate to firmware M0) | **partly done** — see below |
| 1 — Component characterisation | 4–7 | [Experiment 0001](../validation/experiments/0001-pdm-mic-in-situ-characterization.md): mic EQ filter, in-situ response, EIN, the 3.072 MHz verdict; clock-correction constant; per-preset cycle counts on target; display refresh ceiling; per-rail current. Firmware **M0** (PDM → FFT → USB-Serial-JTAG dump) | planned |
| 2 — Bench validation | 8–11 | Firmware **M1** (analyzer canvas at 30/50 Hz); the 108-trial matrix `(prov.)`; golden-file CI green on the host and QEMU lanes; corpus results with `mir_eval` on both paths | planned |
| 3 — In-use validation & release | 12–16 | Firmware **M2** (presets, takes, host ingestion); N × M on-wrist sessions `(prov.)`; one-hour autonomy runs per preset; the wrist-position envelope; public release with a replication guide and a data-availability statement | planned |

**Already done in Phase 0, with its evidence:**

| Item | Evidence |
|---|---|
| Toolchain pinned; gate build passed on hardware; ADR 0001 accepted | [ADR 0001](../adr/0001-toolchain-esp-idf-v6-pinned-environment.md); [`../devenv/env.lock.md`](../devenv/env.lock.md); `firmware/twatch-s3/dependencies.lock` |
| Reproducible build verified (identical `.bin` sha256 twice after `fullclean`) | roadmap E1 definition of done, 2026-08-20 |
| Factory flash backup, eFuse baseline, decoded vendor partition table | [`../hw/README.md`](../hw/README.md) ledger; `docs/hw/efuse-baseline.json`; `docs/hw/vendor-partition-table.md` |
| GPIO45 / VDD_SPI question closed by measurement | [ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md) |
| Partition layout frozen; radio removed from the build | [ADR 0014](../adr/0014-partition-layout-frozen.md), [ADR 0017](../adr/0017-no-radio-in-v1-trimmed-component-set.md) |
| Recovery path demonstrated (rollback 4/4; boot-guard race 10/10 + 5/5) | [experiment 0002](../validation/experiments/0002-rollback-and-boot-guard-race.md), validated 2026-08-21 |
| Bibliography 01–11 filed with a "Why" cell per row | [`../bibliography/README.md`](../bibliography/README.md) |
| Validation plan, uncertainty budget and first two experiment recipes drafted | [`../validation/README.md`](../validation/README.md), [`../validation/uncertainty-budget.md`](../validation/uncertainty-budget.md) |

**Still open in Phase 0:** the bulk acquisition pass (roadmap D3) including the figure digitisation of the Knowles raster tables (06 #38); hardware-fact closure and the rail map (D4); ADRs 0002–0006 (D5); and the D6 freeze of the validation plan, which is the gate to firmware M0.

## Section 7: Limitations and future work

### 7.1 Limitations

Stated as specifically as possible, because a limitation with no mechanism attached is a disclaimer, not a limitation.

- **One unit, one case revision, one wrist.** Every acoustic number in this project describes the microphone-in-*this*-case-on-*this*-arm. Whether the fitted EQ is per-unit or per-part-number cannot be decided from a single device (roadmap Q38); deciding it needs a second unit and is out of scope for the 16 weeks. Results are stated per unit and per schematic revision.
- **The microphone is obsolete and its in-situ response is unmeasured.** The Knowles SPM1423HM4H-B is end-of-life at distributors; a later board revision may have second-sourced it (Q12), which would invalidate every quoted sensitivity/SNR/AOP figure — and the two datasheet revisions already disagree on AOP (110 dB SPL Rev A vs 115 Rev D, Q13). More importantly, **the response through the case, port and gasket in the 2.5–5 kHz ring/twang band is not known.** A datasheet figure describing a rise "by 10 kHz" says nothing about the value at 3.5–5 kHz, and the acoustic port geometry — hole diameter, channel length, cavity volume, gasket, any vent membrane with its own 0.4–4 dB frequency-dependent insertion loss (02 #65) — is undocumented for this case. **No ring, twang or SPR number is interpretable before the EQ from [experiment 0001](../validation/experiments/0001-pdm-mic-in-situ-characterization.md) exists.** If that experiment finds a response outside the fittable envelope or a case resonance inside the ring band, roadmap **threshold T2** fires and the project executes a **host-first pivot**: the watch becomes capture plus live preview, every timbre metric moves to host-offline analysis of takes, and the research question is restated to f0 + latency + autonomy. That is a pre-committed outcome, not a failure mode to be argued about later.
- **The low-frequency end is unverified, in both directions.** A datasheet plot that *starts* at 100 Hz is not a −3 dB corner at 100 Hz; MEMS package vents typically put the corner well below that. The measured corner is a Phase-1 deliverable, and until it exists no claim is made about bass and baritone fundamentals (roughly 82–110 Hz).
- **SPR and the ring ratio are within-session relative metrics only, and the effect-size literature says why.** Bloothooft & Plomp (05 #38) measured, for the singer's-formant level, a between-male-singer spread of ≈4 dB against ≈16 dB for vowel, 9–14 dB for f0 and **more than 30 dB for overall SPL**. The quantity the device is asked to compare between singers is smaller than three confounds it cannot hold constant. Nordenberg & Sundberg (05 #36) add that LTAS level tracks loudness strongly and non-uniformly up to 4 kHz, so an SPR figure without an SPL co-estimate is uninterpretable; and Lundy et al. (05 #42) found no SPR difference between sung and spoken voice in 55 singing students, which is the honest ballast for any claim built on it. Hence: **relative, within-subject, within-session, with a level co-report — and never a score.**
- **No clinical claim.** Pathology corpora are used as acoustic material only; nothing here is a diagnostic or therapeutic device (03 #32 MDR Annex VIII Rule 11, 03 #33 MDCG 2019-11, 03 #34 FDA *General Wellness*; [ADR 0005](../adr/0005-no-clinical-claim.md), accepted). The boundary is stated because the feature set — LTAS, spectral tilt, CPPS-adjacent measures — drifts into regulated territory silently if nobody writes it down.
- **Chip-down design: there is no radio certification to inherit.** The T-Watch S3 carries a bare ESP32-S3-R8, not a pre-certified module, so no FCC or RED grant and no Bluetooth SIG qualification transfers (03 #25, 07 #21). Irrelevant to a research prototype whose radio is held in reset ([ADR 0017](../adr/0017-no-radio-in-v1-trimmed-component-set.md)), and *not* irrelevant to anyone who reads this as a product plan.
- **The schematic does not describe the silicon, so per-unit verification is mandatory.** The schematic and the Zephyr board files name a 1.8 V W25Q128JW flash; this unit reads JEDEC `ef 4018`, a 3.3 V W25Q128JV-class part, with VDD_SPI eFuse-forced to 3.3 V ([ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md)). Because GPIO45 is both the backlight and the VDD_SPI strap, guessing wrong here is a hardware-destruction risk, not a bug. **Every new unit must have its own eFuse row filled in the [`../hw/README.md`](../hw/README.md) ledger before its backlight code runs.** Treat all LilyGO part markings as "verify per unit".
- **The sample-rate error must be measured before any cents claim is made.** The reported PCM rate is set by the 40 MHz crystal's tolerance and the I²S fractional divider's resolution (the ESP32-S3 has **no APLL**, so the failure mechanism is not the one the ESP32 folklore describes). A relative rate error maps to pitch at ≈ 1200/ln 2 ≈ **1731 cents per unit relative error**, i.e. 1 ppm ≈ 0.0017 cents ([uncertainty budget](../validation/uncertainty-budget.md), Model A). The accepted budget is ≤ 200 ppm ≈ **0.35 cents**, which is already 7 % of the ≤ 5-cent injection bound; an uncorrected error ten times that would consume the injection bound entirely. It is a *systematic* term — it adds the same offset to every frame, so it is invisible in repeatability statistics and cannot be averaged away — which is why it is row **A1** of the budget and a Phase-1 blocking measurement against a disciplined reference, not a Phase-3 detail.
- **The 50 Hz refresh clause is conditional on unverified silicon behaviour.** It depends on the ST7789 hardware vertical scroll aligning with the desired time axis under the configured `MADCTL` (threshold T4, §3.4). If it does not, the clause is dropped from the research question.
- **Absolute level is claimed only with a Class-1 calibrator in the chain**; otherwise every level readout is device-relative and is labelled as such in the UI. The 1/3-octave level target is a *repeatability* statement unless the reference chain is IEC 61094-4 class (threshold T6, §4.3), and no IEC 61672 conformance is claimed at all.
- **The wrist is an uncontrolled acoustic position.** Distance, arm angle, sleeve occlusion, arm-movement wind noise and body-conducted sound all vary within a single phrase. This is reported as an *envelope*, never as a pass/fail (05 #64, 05 #65, 05 #66) — and it is the wearable-specific confound with no analogue in the Linux ancestor.
- **Every corpus with non-commercial or unstated terms is quarantined from headline figures** (§4.5), which measurably reduces the amount of ground-truth data available for the f0 bound.
- **No neural pitch estimator runs on-device.** The public accuracy ceiling is a GPU model (05 #11); the gap between it and a frame-independent time-domain estimator is reported rather than hidden (05 #10 as the host-side comparator).

### 7.2 Future work

- **A second unit and a per-unit calibration procedure** — the only way to answer whether the mic EQ is per-part-number or per-device (Q38). The T-Watch Ultra (T3902 microphone, 01 #10; AMOLED) is the obvious successor platform and would also test whether the method transfers across microphones.
- **Native-Linux simulator target** ([ADR 0013](../adr/0013-native-linux-simulator-target.md), accepted): the LVGL simulator plus the DSP core compiled for the host, giving the UI design loop and the golden-file harness in one target (11 #A36).
- **Vibrato readout** — rate, extent, regularity, waveform — from the f0 track the device already produces; the Tier-0 AM/FM generators exist for exactly this.
- **Voice range profile / phonetogram** (05 #46), the canonical singing measurement, which becomes possible the moment absolute SPL is calibrated — and is therefore the natural payoff of solving §7.1's calibration limitation rather than a separate feature.
- **CPP / CPPS on the host**, computable from the cepstrum of a spectrum already being calculated, as the most validated single acoustic voice measure — still under the no-clinical-claim boundary.
- **A shared upstream Zephyr `dmic_esp32.c` driver** with the author's `swarm` project, if a Zephyr end-state is ever reopened ([ADR 0001](../adr/0001-toolchain-esp-idf-v6-pinned-environment.md) records why it is not now).
- **A BLE companion link**, re-benchmarked against the audio-dropout risk of radio/audio coexistence before any audio task shares a core with a controller ([ADR 0017](../adr/0017-no-radio-in-v1-trimmed-component-set.md) revisit trigger).

## References

Citation addresses are positional: `NN #k` resolves to entry `k` of bibliography file `NN` ([`../bibliography/README.md`](../bibliography/README.md)). Thematic files 08–11 carry letter-prefixed entries. This table lists the entries this proposal leans on; it is not the bibliography.

| Topic | Entries |
|---|---|
| Spectral estimation, windows, normalisation | Heinzel, Rüdiger & Schilling 2002 (05 #1); Harris 1978 (05 #2); Nuttall 1981 (05 #3); Allen & Rabiner 1977 (05 #4); Welch 1967 (05 #5); Koenig et al. 1946 (05 #6); Smith *SASP* (04 #1) |
| Pitch estimation and its evaluation | Boersma 1993 (05 #7); McLeod & Wyvill 2005 (05 #8); de Cheveigné & Kawahara 2002 (05 #9); Mauch & Dixon 2014 (05 #10); Kim et al. 2018 CREPE (05 #11); Raffel et al. 2014 `mir_eval` (05 #53); Bittner et al. 2019 `mirdata` (05 #54); Jadoul et al. 2018 Parselmouth (05 #55); MIREX task description (07 #13) |
| Formants and spectral tilt | Makhoul 1975 (05 #16); Weenink 2023 FormantPath (05 #17); Hillenbrand et al. 1995 (05 #18); Iseli & Alwan 2004 (05 #20); Kreiman et al. 2021 (05 #23); Kent & Read (04 #7) |
| Singer's formant, SPR, FHE, LTAS | Sundberg 1974 (05 #33); Sundberg 2001 (05 #34); Omori et al. 1996 (05 #35); Nordenberg & Sundberg 2004 (05 #36); Müller et al. 2022 FHE (05 #37); Bloothooft & Plomp 1986 (05 #38); Lundy et al. 2000 (05 #42); Ternström et al. 2016 VRP (05 #46); Sundberg, *The Science of the Singing Voice* (04 #5) |
| Voice metrology on the wrist | Švec & Granqvist 2010 (05 #63) and 2018 (05 #64); Titze & Winholtz 1993 (05 #65); Katz & d'Alessandro 2007 (05 #66); Patel et al. 2018 ASHA (05 #31); Dejonckere et al. 2001 ELS (05 #32); JCGM 100 GUM (03 #20, 08 #S9); IEC 61094-4 (03 #7, 08 #S5); Knowles datasheet (01 #9, 08 #D1); TDK AN-1003 / AN-100 (02 #62, 08 #A2); case/port drawing (08 #D5) |
| Agreement and study design | Bland & Altman 1986 (05 #86); Koo & Li 2016 (05 #87); Lakens 2017 TOST (05 #89); Farina 2000 (05 #88); ISO 7250-1 / ANSUR II / DINED (03 #21, 08 #S1) |
| Visual feedback, latency, legibility | Howard et al. WinSingad (05 #68); Welch et al. 2005 (05 #69); Hoppe et al. 2006 review (05 #70); Wilson et al. 2008 (05 #71); Leong & Cheng 2014 (05 #72); 2022 review (05 #73); dos Santos & Masiero 2026 survey (05 #74); Öster 2006 (05 #75); Nuñez et al. 2018 cividis (05 #76); Crameri et al. 2020 (05 #77); Jack et al. 2018 (05 #83); McPherson et al. 2016 (05 #84); Schmid et al. 2024 (05 #85); Sing&See (09 #R1); VoceVista (09 #R2); ITU-R BT.1359 (09 #S1); ST7789V3 `COLMOD` (09 #D1); watchOS HIG (09 #R3); Wear OS guidelines (09 #R4) |
| Standards and the regulatory boundary | ANSI S1.11-2004 (03 #1); IEC 61672-1 (03 #2) and Parts 2/3 (03 #3); IEC 61260-1 (03 #4); IEC 60942 (03 #6); IEC 61094-4 (03 #7); ITU-T P.58 / P.51 / P.56 (03 #10, #11, #12); ISO 26101-1 (03 #18); ANSI/ASA S12.2 (03 #19); MDR Rule 11 (03 #32); MDCG 2019-11 (03 #33); FDA General Wellness (03 #34); RED 2014/53/EU (03 #25); Apache-2.0 / GPL-3.0 texts (03 #36, #37); FAIR (03 #42); CFF (03 #43); Microchip RED chip-down FAQ (07 #21) |
| Hardware | ESP32-S3 datasheet (01 #1), TRM (01 #2), errata (01 #3), hardware design guidelines (01 #4); T-Watch S3 schematics V1.4 (01 #6) and 2025-03-24 (01 #7); Knowles SPM1423HM4H-B (01 #9); TDK T3902 (01 #10); MAX98357A (01 #11); ST7789V3 (01 #13); FT6336U (01 #16); AXP2101 (01 #17); battery (01 #18); W25Q128JW (01 #20); octal PSRAM (01 #21); B&K 4231 (01 #30); UMIK-1 (01 #31); PPK2 (01 #33); Otii Arc Pro (01 #34); HATS 4128-C (01 #35) |
| Platform and toolchain | I²S driver (02 #14); `driver/i2s_pdm.h` guards (02 #15); `soc_caps.h` (02 #16); `esp_audio_codec` (02 #19); esp-dsp guide (02 #20) and benchmarks (02 #21, 11 #A1); `esp_lcd` (02 #23); `esp_lvgl_port` performance (02 #25); flash/PSRAM configuration (02 #29, #30); GORE acoustic vents (02 #65); ESP-IDF v6.0.2 (11 #R1); USB-Serial-JTAG console (11 #A17); OTA/rollback (11 #A21); reproducible builds (11 #A31); QEMU (11 #A33); host apps and unit testing (11 #A36) |
| Datasets | vocadito (10 #1, 05 #58); Dagstuhl ChoirSet (10 #2, 05 #60); VocalSet (10 #3, 05 #57); PTDB-TUG (10 #10, 05 #56); MDB-stem-synth (10 #11); PVQD (10 #18); Saarbrücken (10 #19); DEMAND (10 #20); OpenAIR (10 #24); Tier-0 in-repo generator (10 #P1) |
| Reference projects | esp-dsp (06 #1); xiao-edge-audio (06 #3); LVGL (06 #12); ESP32-S3 memory-bandwidth measurements (06 #23); `mir_eval` (06 #29); `mirdata` (06 #30); Parselmouth/Praat (06 #31); friture (06 #32); WebPlotDigitizer (06 #38) |
