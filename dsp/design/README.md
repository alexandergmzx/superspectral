# DSP design notes

Math + rationale for every DSP block, written once and bound by ADR so the watch (`spectral_core`, C99) and the host (`host/`, Python) implement the **same definitions**. Each note states its conventions, its parameters, what it deliberately does not do, and the validation row that checks it.

Written:

- *(none yet — Phase 0 is documentation; the notes below are written in roadmap D5/D6 as their ADRs are accepted)*

Planned documents:

- `fft-normalization.md` — the single-source spectral convention (ADR 0006): power spectrum vs power spectral density, `1/N` scaling, NENBW/ENBW per window (Hann, Blackman-Harris, Gaussian as a Praat-compatible option), periodic-window rule, dBFS reference defined against a full-scale sine, the `int16 → float32` divisor, and the stated bandwidth of each preset (the presets currently name an FFT size and a window but no bandwidth — "wideband/narrowband" is undefined until this note exists). Never defines display smoothing; that belongs to the preset schema.
- `decimation-cascade.md` — Spectroid-style "decimations" for finer low-frequency resolution: cascaded decimate-by-2 stages with a real elliptic/Butterworth IIR low-pass (never decimate-by-averaging), `dsps_biquad_gen_*` coefficients, group-delay alignment between stages, and the measured mAh-per-stage cost that RQ objective 4 reports. Does not define the octave-band filter bank's class compliance (ANSI S1.11 is a validation anchor, not a design target).
- `pitch-mpm-yin.md` — time-domain f0 on the watch: McLeod–Wyvill MPM as default (fits the 20 ms hop), YIN as fallback, lag range for C2 (65 Hz) to C6 (1046 Hz), parabolic peak interpolation, voicing decision and octave-error guard; reports RPA/RCA/OA/VR/VFA against mir_eval on the injection path and median |Δcents| against the Praat golden files (floor/ceiling pinned in the golden manifest). Does not attempt Praat-grade pitch; that is the host's job.
- `band-energy-and-fhe.md` — the ring/twang readout (ADR 0008): Omori peak-to-peak SPR (greatest harmonic peak 2–4 kHz minus greatest peak 0–2 kHz) and Müller's formant-cluster FHE as the primary, voice-type-adaptive readout; fixed bands (ring 2.5–3.5 kHz, twang 3.5–5 kHz) only as overlays; all values **relative, within-session**, reported uncorrected and post-EQ. States why a raw band ratio on this microphone is biased until `mic-eq.md` delivers a fitted curve.
- `mic-eq.md` — the SPM1423HM4H-B in-situ correction: the measured through-the-case response (Phase 1 experiment 0001, swept sine per Farina 2000 against the reference mic), fitted as a low-order IIR or a per-bin table; whether it is per-part-number or per-unit (a per-unit EQ makes the band readouts non-reproducible on a second watch without a calibration step — an open question routed in the roadmap); the preset-schema slot it occupies. Does not claim absolute SPL; that needs the calibrator chain in [`../../docs/validation/README.md`](../../docs/validation/README.md).

Each note ends with `## Verification hooks` naming the validation rows and golden vectors that check it, and a `Reference basis:` bullet with positional bibliography addresses.

## Background reading

See [`../../docs/bibliography/05-papers.md`](../../docs/bibliography/05-papers.md) (Heinzel 2002, Harris 1978, Nuttall 1981; de Cheveigné & Kawahara 2002, McLeod & Wyvill 2005, Mauch & Dixon 2014; Omori 1996, Müller 2022; Farina 2000), [`../../docs/bibliography/04-books.md`](../../docs/bibliography/04-books.md) (Smith SASP, Lyons, Oppenheim & Schafer) and [`../../docs/bibliography/08-voice-metrology-on-the-wrist.md`](../../docs/bibliography/08-voice-metrology-on-the-wrist.md) for the microphone admissibility and placement literature (Švec & Granqvist 2010/2018, Titze & Winholtz 1993).
