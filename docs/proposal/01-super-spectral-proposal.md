# Super Spectral: a wrist-worn, real-time singing-voice spectral analyzer with a Linux companion

> **Revision note (2026-08-20).** Skeleton filed in documentation-roadmap phase D0; prose is written in phase D2 once the bibliography ([`../bibliography/`](../bibliography/README.md)) exists to cite. Values marked `(prov.)` are provisional and `TBD` values are unsettled; each is tracked in the [roadmap routing table](../roadmap/documentation-roadmap.md). The research question becomes binding when its `(prov.)` tag is removed in the D2 closing commit.
>
> **Citation note.** Technical claims carry inline citation addresses of the form `NN #k` (bibliography file number and entry) that resolve in [`../bibliography/`](../bibliography/README.md); thematic files 08–11 use letter-prefixed entries. Addresses marked `#TBD` are resolved in D2.

## Section 1: Motivation and research question

### Motivation

*(D2 prose.)* Singers and voice teachers have had real-time visual feedback on desktop systems since the 1990s (WinSingad, Sing&See, VoceVista — 09 #TBD) and generic spectrum analyzers on phones since the 2010s (Spectroid; Friture on the desktop — 07 #TBD). A singer's own wrist is the one place a display can be glanced at mid-phrase without a stand, a phone or a laptop. The prior-art study in [`../research/00-linux-analyzer-architecture-and-build-guide.md`](../research/00-linux-analyzer-architecture-and-build-guide.md) designed a preset-driven analyzer for Linux; this proposal carries its live half onto a commodity ESP32-S3 smartwatch and asks whether the result is metrologically honest.

### Research question

> **RQ (prov.)** — Can a wrist-worn ESP32-S3 device with a single PDM MEMS microphone, acting as the live-capture and real-time-display front end of a preset-driven singing-voice analyzer, estimate singing f0 within ±20 cents median absolute error (≥90 % RPA @ 50 cents) on the acoustic path and ≤5 cents vs Praat on the digital-injection path, render a ≥30 Hz spectrogram (50 Hz for the live-singing preset) with ≤80 ms acoustic-to-photon latency, and sustain ≥3 h of continuous analysis on its own battery — with all real-time DSP on-device and the host used only for offline analysis of recorded takes?

The question follows the swarm grammar — *system class + method + primary metric + secondary constraint + bounded environment + architectural prohibition* — and carries three numeric bounds plus one prohibition:

1. **Fidelity bound.** f0 within **±20 cents median absolute error and ≥ 90 % raw pitch accuracy at 50 cents** on the *acoustic* path (the whole chain: case, port, microphone, PDM→PCM, clock, estimator), and **≤ 5 cents median vs Praat** on the *digital-injection* path (the estimator alone). Two paths, reported separately, always (§4.1). The anchors are the MIREX/`mir_eval` convention for RPA (05 #TBD, 07 #TBD) and the Praat/parselmouth golden files (05 #TBD; [`../validation/golden-files.md`](../validation/golden-files.md)).
2. **Real-time bound.** A spectrogram refreshed at **≥ 30 Hz** for every preset and **50 Hz for `live_singing`**, with **≤ 80 ms acoustic-to-photon latency** measured stimulus-onset-to-first-pixel with a phototransistor. The refresh figure is what the display path can sustain (03/04 architecture notes; ADR 0007); the latency anchor is the action–sound and visual-feedback literature (09 #TBD), which tolerates more for visual biofeedback than for audio — the bound is deliberately conservative.
3. **Autonomy bound.** **≥ 3 h** of continuous analysis on the watch's own cell (470 mAh per the vendor library, 400 mAh per resellers — `TBD`, roadmap Q9), measured full-charge-to-PMU-cutoff per preset with an external energy analyzer cross-checked against the AXP2101 coulomb counter.
4. **Architectural prohibition.** All real-time DSP runs on the device; the Linux host ([`../../host/`](../../host/README.md)) is used **only** for offline analysis of recorded takes. Without this clause the question is trivially answerable by streaming audio to a PC and is not a wearable result.

## Section 2: Objectives

1. **Design and validate an on-device DSP front end** — PDM capture, windowed FFT with stated normalization, time-domain f0 estimation, band-energy / FHE / SPR readouts — on the ESP32-S3, meeting the fidelity bound on both measurement paths.
2. **Define the companion architecture and its record-format contract** — the normative split of features between watch and host (§3.2), the on-flash take and feature records, and the preset schema — so that the watch is useful with no host and the host can reproduce every on-device number offline.
3. **Build and evaluate a prototype on the wrist** with at least **N sessions × M singers** (`N`, `M` TBD pending a power analysis; prov. N ≥ 10 sessions, M ≥ 5 singers) under a stated wrist-position envelope, with simultaneous reference-microphone capture.
4. **Quantify the trade-off between preset, refresh rate and energy** — cycles, mAh/h and mJ per analysis frame per preset, including the marginal energy cost per decimation stage — so that the autonomy bound is a measured frontier rather than a single point.
5. **Publish an open, reproducible validation framework** — `mirdata`-managed corpora with checksums, `mir_eval` metrics, the Praat golden-file manifest, host and QEMU CI lanes, a pinned toolchain — so that a third party can rebuild the device, rerun the experiments, and land within the stated tolerances.

## Section 3: Technical approach

### 3.1 Hardware and platform

*(D2 prose.)* LilyGO T-Watch S3: ESP32-S3-R8 chip-down (not a module), 512 KB SRAM, 8 MB octal PSRAM, 16 MB 1.8 V W25Q128JW flash; one Knowles SPM1423HM4H-B PDM microphone (GPIO44 CLK / GPIO47 DATA; sensitivity −22 dBFS, SNR 61.5 dB(A), PDM clock 1.0–3.25 MHz; **obsolete at distributors**); MAX98357A Class-D amplifier (calibration-tone source); 240×240 ST7789V3 over SPI (backlight on GPIO45, which is also the VDD_SPI strapping pin); FT6336U touch; AXP2101 PMU; BMA423, PCF8563, DRV2605L; SX1262 (held off in v1); native USB-Serial-JTAG as the only port; BOOT button inside the case. Bill of materials: [`../../hardware/bom/bill-of-materials.csv`](../../hardware/bom/bill-of-materials.csv). Datasheets: 01 #TBD. Pinout derivation: [`../hw/twatch-s3-pins.md`](../hw/twatch-s3-pins.md).

Toolchain and environment: ESP-IDF v6.0.2 native, pinned and reproducible ([ADR 0001](../adr/0001-toolchain-esp-idf-v6-pinned-environment.md), 11 #TBD); no Arduino in any phase; esp-dsp for the FFT (Apache-2.0), LVGL for chrome (MIT).

### 3.2 Companion split (normative; to be recorded as ADR 0002)

| Feature | On-watch (live) | Host (offline, on takes) | Rationale |
|---|:---:|:---:|---|
| FFT magnitude spectrum, all six presets | ✅ | ✅ | 1.3–8.9 % of one core at 50 Hz (real N = 512…8192) |
| Spectrogram waterfall (hardware-scrolled) | ✅ | ✅ | ~480 B per frame with ST7789 vertical scroll (gated, ADR 0007); 10 min of history in PSRAM |
| Peak markers, max-hold, exponential smoothing | ✅ | ✅ | negligible |
| Time-domain f0 (MPM / YIN / dywapitchtrack) | ✅ | ✅ (pYIN / Praat reference) | ~6 % of a core; MPM needs ~2 periods |
| Band energy: ring 2.5–3.5 kHz, twang 3.5–5 kHz | ✅ with the fitted mic EQ | ✅ | uncorrected value always shown too |
| FHE (Müller 2022) and Omori peak-to-peak SPR | ✅ relative, within-session | ✅ with SPL co-report | Nordenberg & Sundberg 2004: uninterpretable without a level estimate |
| Octave / 1/3-octave bank (decimation cascade) | ✅ | ✅ | IIR, ~1.4 % for 4 stages |
| A/C/Z weighting, Leq | ✅ (dBFS unless calibrated in-session) | ✅ | relative only without a calibrator |
| Low-order LPC F1/F2 overlay | ⚠️ marginal | ✅ Praat Burg + FormantPath | hand-ported; degrades at high f0 |
| Praat-grade Burg formants, FormantPath ceiling optimization | ✗ | ✅ | golden-file reference |
| LTAS / SPR over whole takes | ⚠️ accumulate only | ✅ | interpretation needs the SPL co-report |
| H1–H2 (Iseli–Alwan corrected), Kreiman 4-parameter slope | ✗ | ✅ | needs F1–F3 *and* bandwidths |
| CPP/CPPS, AVQI-class composites | ✗ | ✅ | acoustic material only; no clinical claim (ADR 0005) |
| DTW alignment, Demucs stem separation | ✗ | ✅ | host only |
| Take recording (OPUS / PCM) | ✅ | ingests | coexists with the FFT load |
| AFE / NS / AGC / AEC | ✗ never | ✗ never | non-linear; corrupts spectra, formants, H1–H2 |

### 3.3 Signal path

```
singer ─► case / acoustic port ─► SPM1423 (PDM, 1.024–3.072 MHz)
      ─► ESP32-S3 I2S0 PDM→PCM (16-bit, 32 kHz default · 48 kHz gated on T3)
      ─► PCM ring (internal SRAM)  ◄─── file_blob (corpus WAV)   ◄─── synthetic generator
      ─► core 1: DC removal ─► window ─► esp-dsp FFT fc32 ─► |X|² ─► dB (fast log)
                 ├─► f0 (MPM/YIN)  ─► cents · vibrato
                 ├─► band energy ─► ring / twang (EQ-corrected + raw) ─► FHE · SPR
                 └─► decimation cascade ─► octave bank ─► A/C/Z · Leq
      ─► double-buffered magnitude + feature record ─► queue of pointers
      ─► core 0: analyzer canvas (raw esp_lcd + ST7789 VSCRDEF/VSCSAD) · LVGL chrome · PMU · haptics
      ─► ST7789V3 240×240 (≥ 30 Hz; 50 Hz live_singing)   ·   takes → FAT · presets → littlefs
      ─► (offline) USB ─► host/: Praat/parselmouth · LTAS/SPR · H1–H2 · DTW · Demucs
```

### 3.4 Presets

*(D2 prose.)* The six presets of the Linux analyzer (`live_singing` 4096 BH 20 ms · `vowel_formant_study` 8192 Hann · `sustained_pitch_lab` 8192 BH 40 ms · `diction_consonants` 1024 Hann 10 ms · `room_noise_floor` 8192 Hann, linear average, min-hold · `stem_analysis` host-only) are carried over with **explicit bandwidth/ENBW**, a mic-EQ slot and a clock-correction constant (ADR 0010; [`../architecture/README.md`](../architecture/README.md) planned doc 07).

### 3.5 Energy budget

*(D2; derived in [`../architecture/README.md`](../architecture/README.md) planned doc 06.)* Ends in a pass/fail verdict against the ≥ 3 h bound with the two unknown terms (octal PSRAM active current, backlight at usable brightness) measured in Phase 1, not estimated. Power levers in order of effect: backlight PWM, 240 → 160 MHz when N ≤ 2048, `fc32` not PIE `sc16`, 50 → 25–30 Hz on static signals, no radio (ADR 0017).

### 3.6 Recovery and safety

*(D2 prose.)* Partition layout frozen with `ota_0` as the golden recovery image (ADR 0014); anti-brick policy — boot guard, GPIO19/20 static asserts, rollback mark-valid criteria, sleep gating, USB-Serial-JTAG console, eFuses read-only (ADR 0015); GPIO45 backlight handling decided by the eFuse read (ADR 0016). Verified by [experiment 0002](../validation/experiments/0002-rollback-and-boot-guard-race.md) before any feature code.

### 3.7 Licensing

Apache-2.0 for the repository, firmware, documentation and tooling; `host/` GPL-3.0-or-later so that it may import parselmouth/Praat in-process; no code crosses the boundary ([ADR 0004](../adr/README.md); `NOTICE`).

## Section 4: Validation plan and experimental methodology

### 4.1 Strategy

**The two-path rule.** Every signal-chain metric is reported on the digital-injection path (algorithm error) and the acoustic path (whole-chain error), separately, in every table — with an optional injection ⊛ RIR path to isolate room effects. Reporting only the acoustic path hides algorithm bugs behind acoustics; reporting only injection is not a wearable result (see [`../validation/README.md`](../validation/README.md)).

**Phases** (weeks per the root README): Phase 1 component characterization (4–7) → the mic EQ filter and the clock-correction constant; Phase 2 bench validation (8–11) → corpus runs and the factorial matrix; Phase 3 in-use validation and release (12–16) → singers on the wrist, autonomy runs, the wrist-position envelope.

**Factorial matrix (prov., pending a power analysis):**

```
BENCH VALIDATION - ACOUSTIC PATH MATRIX (prov.)

Preset:      live_singing | vowel_formant_study | sustained_pitch_lab | diction_consonants | room_noise_floor | (stem_analysis: host only, injection control)
SPL:         60 dB | 75 dB | 90 dB SPL at the reference point
Distance:    15 cm | 30 cm | 45 cm mouth-to-watch   (to be replaced by an anthropometric distribution, ISO 7250-1 / ANSUR II)
Arm angle:   0° | 45° relative to the source axis

Total trials: 6 presets × 3 SPL × 3 distances × 2 angles = 108 trials (acoustic) + 108 injection controls

Example:
─────────────────────────────────────────────────────────────────
Trial 1: live_singing, 75 dB SPL, 30 cm, 45°
→ vocadito excerpt V-07 through the mouth simulator (ITU-T P.51 / P.58 geometry)
→ simultaneous capture: watch (PDM, 32 kHz) + reference mic; time-aligned by cross-correlation
→ device f0 track vs corpus ground truth → RPA@50/25/10, RCA−RPA, OA, VR/VFA (mir_eval)
→ device f0 track vs Praat golden file on the identical WAV (injection control) → median |Δcents|
→ 1/3-octave levels vs reference analysis → bias, Bland–Altman limits of agreement
→ record in the trial table with instrument serials and env.lock.md hash

[Repeat 108 times...]

Post-trial analysis:
  cents error: median, p90, p99 (CEP-style percentiles, not means)
  level: Bland–Altman bias + LoA; ICC for repeatability; TOST for the ±1.5 dB claim
  RPA/OA per preset × SPL × distance; the wrist-position envelope as a surface, not a pass/fail
```

### 4.2 Metrics

The acceptance-metrics table — definition, target, external anchor, how to measure — lives in [`../validation/README.md`](../validation/README.md) and is not duplicated here. Golden-file provenance and tolerances: [`../validation/golden-files.md`](../validation/golden-files.md). Equipment with tolerances and corpora with licences: same file. First experiments: [0001 mic in-situ](../validation/experiments/0001-pdm-mic-in-situ-characterization.md), [0002 recovery path](../validation/experiments/0002-rollback-and-boot-guard-race.md).

### 4.3 Calibration of the microphone path

*(D2 prose; produced by experiment 0001.)* In-situ response through the case, the fitted EQ and its per-unit vs per-part-number status (Q38), absolute sensitivity in dBFS per dB SPL from a Class-1 calibrator (if available; else "not claimed"), the sample-rate correction constant, and the measured noise floor — with a GUM-style uncertainty budget for the level metrics.

## Section 5: Expected contributions and significance

### 5.1 Technical

An open, permissively licensed, on-device singing-voice analyzer on commodity smartwatch hardware with a stated accuracy on both measurement paths; a measured energy/refresh/resolution frontier for preset-driven spectral analysis on the ESP32-S3; a reusable ESP-IDF board file and anti-brick policy for a sealed USB-Serial-JTAG-only device.

### 5.2 Methodological

The two-path reporting rule and the Praat golden-file manifest as a reproducibility instrument for embedded voice DSP; an explicit substitute for the missing "EPA-style" anchor in wearable voice metrology — the ASHA (Patel et al. 2018) and ELS (Dejonckere et al. 2001) protocols, Švec & Granqvist's microphone guidelines, and the IEC 61672 / 61260 / `mir_eval` triple (08 #TBD); the documentation-before-firmware method itself, carried from `swarm` and extended with a routed open-question table.

### 5.3 Practical

A singer's feedback tool that works with no phone, PC or network; a calibration-and-limits statement honest enough that a voice teacher knows which readouts are relative and which are absolute; an accessible visual voice display with a colorblind-safe default and non-colour redundancy.

## Section 6: Timeline and milestones (prov.)

| Phase | Weeks | Deliverables |
|---|---|---|
| 0 — Documentation & environment | 0–3 | Roadmap D0–D6 and E0–E2: bibliography, acquisition pass, ADRs 0001–0006 accepted, validation plan frozen, environment pinned and gated, eFuse baseline, recovery path tested |
| 1 — Component characterization | 4–7 | Experiment 0001 (mic EQ filter, EIN, 3.072 MHz verdict), clock-correction constant, per-preset cycle counts, refresh ceiling, per-rail current; firmware M0 (PDM → FFT → USB dump) |
| 2 — Bench validation | 8–11 | Firmware M1 (analyzer canvas at 30/50 Hz); 108-trial matrix; golden-file CI green on host and QEMU lanes; corpus results with `mir_eval` |
| 3 — In-use validation & release | 12–16 | Firmware M2 (presets, takes, host ingestion); N × M on-wrist sessions; 1-hour autonomy per preset; wrist-position envelope; public release with replication guide and data-availability statement |

## Section 7: Limitations and future work

### 7.1 Limitations

- **The microphone is obsolete.** The Knowles SPM1423HM4H-B is end-of-life at distributors; a later board revision may have second-sourced it (Q12), which would invalidate every quoted sensitivity/SNR/AOP figure. Results are stated per unit and per schematic revision.
- **Chip-down design, no inherited radio certification.** The T-Watch S3 carries a bare ESP32-S3-R8, not a pre-certified module; no FCC/RED grant transfers. Irrelevant to a research prototype with the radio held off (ADR 0017), but stated.
- **No clinical claim.** Pathology corpora are acoustic material only; nothing here is a diagnostic or therapeutic device (MDR Rule 11 / MDCG 2019-11 / FDA General Wellness; ADR 0005).
- **The microphone's high-frequency response in the ring/twang band is unverified** until the datasheet's raster curve is digitized and the in-situ response is measured (experiment 0001). A "+5 dB by 10 kHz" figure says nothing about 3.5–5 kHz; no ring/twang number is interpretable before the EQ exists.
- **Single device.** One unit, one case, one wrist; per-unit vs per-part-number calibration (Q38) cannot be decided from it.
- Absolute SPL is claimed only with a Class-1 calibrator; otherwise every level is device-relative.
- The 1/3-octave level target is a repeatability statement unless the reference chain is IEC 61094-4 class (threshold T6).
- Corpora with non-commercial or unstated terms are quarantined from headline figures.

### 7.2 Future work

- Per-unit calibration procedure and a second unit; the T-Watch Ultra (T3902 microphone, AMOLED) as the successor platform.
- Native-Linux simulator target (ADR 0013) as the UI design loop.
- Vibrato readout (rate, extent, regularity, waveform) from the f0 track; voice-range profile (phonetogram) once absolute SPL is calibrated.
- A Zephyr `dmic_esp32.c` driver as shared upstream work with `swarm`, if a Zephyr end-state is ever reopened (ADR 0001).
- Companion-app link over BLE, re-benchmarked against the audio-dropout risk of coexistence (ADR 0017 revisit trigger).

## References

Citation addresses are resolved in D2 against the bibliography; until then each entry names its file and `#TBD`.

| Topic | Entries (file) |
|---|---|
| Spectral estimation and windows | Heinzel, Rüdiger & Schilling 2002; Harris 1978; Nuttall 1981; Allen & Rabiner 1977; Welch 1967 (05 #TBD); Smith *SASP* (04 #TBD) |
| Pitch estimation and evaluation | Boersma 1993; de Cheveigné & Kawahara 2002; McLeod & Wyvill 2005; Mauch & Dixon 2014; Kim et al. 2018 (CREPE); Raffel et al. 2014 (mir_eval); Bittner et al. 2019 (mirdata); Jadoul et al. 2018 (05 #TBD); MIREX task description (07 #TBD) |
| Singer's formant, SPR, spectral tilt | Sundberg 1974, 1987, 2001; Omori et al. 1996; Nordenberg & Sundberg 2004; Müller et al. 2022; Bloothooft & Plomp 1986; Hanson & Chuang 1999; Iseli & Alwan 2004; Kreiman et al. 2021; Lundy et al. 2000 (05 #TBD; 08 #TBD) |
| On-wrist voice metrology | Švec & Granqvist 2010, 2018; Titze & Winholtz 1993; Katz & d'Alessandro 2007; Patel et al. 2018 (ASHA); Dejonckere et al. 2001 (ELS); JCGM 100; Bland & Altman 1986; Koo & Li 2016 (08 #TBD; 03 #TBD) |
| Visual feedback and latency | Howard et al. (WinSingad); Welch/Howard review; Jack et al. 2018; McPherson et al. 2016; Nuñez et al. 2018; Crameri et al. 2020 (09 #TBD) |
| Standards | IEC 61672-1/-2/-3; IEC 61260-1; ANSI S1.11-2004; IEC 60942; ISO 226; ITU-T P.51/P.56/P.58; ITU-R BS.1770; MDR 2017/745 Rule 11; MDCG 2019-11; FDA General Wellness (03 #TBD) |
| Hardware | ESP32-S3 datasheet, TRM, errata, Hardware Design Guidelines; T-Watch S3 schematics V1.4 and 2025-03-24; Knowles SPM1423HM4H-B; ST7789V3; AXP2101; MAX98357A; FT6336U; W25Q128JW (01 #TBD) |
| Platform and toolchain | ESP-IDF v6.0 support policy, migration guides, I2S/PDM driver, USB-Serial-JTAG console, OTA/rollback, partition tables, reproducible builds, host apps, QEMU; esp-dsp benchmarks; `esp_lvgl_port` performance notes (02 #TBD; 11 #TBD) |
| Datasets | vocadito; Dagstuhl ChoirSet; VocalSet; PTDB-TUG; MDB-stem-synth; PVQD; Saarbrücken; DEMAND; OpenAIR (10 #TBD) |
| Reference projects | esp-dsp; xiao-edge-audio; LilyGoLib; SensorLib; circuitpython `lilygo_twatch_s3`; Parselmouth; friture; mir_eval; mirdata (06 #TBD) |
