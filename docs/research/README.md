# Research

The founding document of the project, preserved as it was written — before the decision to move the live path onto a wrist-worn device.

- [`00-linux-analyzer-architecture-and-build-guide.md`](00-linux-analyzer-architecture-and-build-guide.md) — *Architecture & Build Guide: A Preset-Driven Singing-Voice Spectral Analyzer for Linux*. A prior-art study (Friture, parselmouth/Praat, Demucs, pYIN/CREPE, Sundberg's singer's formant, SPR, LTAS, H1–H2) and an opinionated architecture for a browser + Python analyzer with six Spectroid-style presets (`live_singing`, `vowel_formant_study`, `sustained_pitch_lab`, `diction_consonants`, `stem_analysis`, `room_noise_floor`). Moved here from the repository root by `git mv`, **byte-identical**; it is not edited.

## How it relates to Super Spectral

The document's central split — "by physics": a low-latency **live path** and a heavy **offline path** — is the origin of the companion architecture ([ADR 0002](../adr/0002-companion-architecture.md), accepted). Super Spectral moves the live path from a browser tab onto the T-Watch S3 and keeps the offline path on the Linux host under [`../../host/`](../../host/):

| In the research document | In Super Spectral |
|---|---|
| Live path: `getUserMedia` → AudioWorklet → FFT → WebGL waterfall at 50 Hz | Watch: PDM mic on I2S0 → esp-dsp FFT → ST7789 canvas at 50 Hz (`live_singing`) / ≥30 Hz |
| Six JSON presets (FFT size, window, interval, smoothing, decimations, overlays) | Same presets, schema owned by [`../../protocols/specs/`](../../protocols/specs/) with explicit bandwidth/ENBW and a mic-EQ slot (ADR 0010) |
| Offline path: FastAPI + parselmouth + librosa + Demucs, DTW alignment, LTAS/SPR/H1–H2 | [`../../host/`](../../host/) (GPL-3.0-or-later): the same libraries, run on recorded takes instead of uploads |
| "Golden-file tests: run parselmouth on fixed WAVs and snapshot formant/f0 arrays" | [`../../host/golden/`](../../host/golden/) with a pinned parselmouth → Praat → method → floor/ceiling → sha256 manifest ([`../validation/golden-files.md`](../validation/golden-files.md)) |
| "Use synthetic signals as unit tests" (sines, sweeps, noise, two-tone) | Tier 0 of [`../../datasets/`](../../datasets/) |
| `stem_analysis` preset (DTW + Demucs) | Host-only; not portable to the watch |
| Decimations: "use a real low-pass filter, not decimate-by-averaging" | [`../../dsp/design/`](../../dsp/design/) `decimation-cascade.md` |

Claims in the document that the research syntheses later corrected are **not** propagated into new files (for example, "parselmouth is numerically identical to Praat" holds only for the bundled Praat version, hence the golden-file manifest). Such corrections are recorded where they matter — ADRs, the validation plan, the bibliography — not by editing this document.

## Conventions

- This directory holds founding or historical research material only. New analysis goes to [`../../analysis/`](../../analysis/); new design prose goes with its subsystem; new literature goes to [`../bibliography/`](../bibliography/).
- Files here are numbered `NN-<slug>.md` in order of arrival and are never rewritten; if a successor supersedes one, add the successor and a one-line pointer at the top of this README.
