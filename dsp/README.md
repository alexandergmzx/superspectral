# DSP

The signal-processing design of Super Spectral, shared by the two halves of the companion architecture: the watch's real-time path (`firmware/twatch-s3/components/spectral_core/`, pure C99) and the host's offline path (`host/`, Python). This subsystem is **self-contained**: design notes live alongside the reference material under [`design/`](design/), not under `docs/`.

| Subdirectory | Contents |
|--------------|----------|
| [design/](design/) | Math, conventions, parameter choices and rationale for each DSP block — the single-source specs that ADR 0006 (FFT conventions) and ADR 0008 (ring/twang readout) bind |

Code does **not** live here. The on-device implementation is `firmware/twatch-s3/components/spectral_core/` (zero `esp_*` includes, `REQUIRES ""`, host-buildable) with the esp-dsp binding in `spectral_fft_backend/`; host-side implementations live under [`../host/`](../host/); Apache-2.0 reference scripts (signal generators, golden-vector comparators) live under [`../python-scripts/`](../python-scripts/). This directory holds the prose both sides must agree with.

## The rule that makes the two halves comparable

The watch and the host never share a process; they share **definitions**. Every DSP block here states its conventions explicitly so that a result computed on the watch and the same result computed on the host differ only by a stated numerical tolerance:

- window family and **periodic vs symmetric** form (`fftbins=True` in SciPy terms);
- FFT normalization (**power spectrum vs power spectral density**, `1/N` vs `1/√N` vs none) and the normalized equivalent noise bandwidth (NENBW) of each window, per Heinzel, Rüdiger & Schilling 2002;
- dB reference (dBFS relative to a full-scale **sine**, not a full-scale square — a 3 dB trap);
- sample format and scaling (PDM RX delivers 16-bit; `int16 → float32` with a stated divisor);
- accumulation precision (float32 on the S3 — its FPU is single-precision; `-Wdouble-promotion` is on so a `double` cannot sneak in — float64 on the host) and the consequence that **bit-exactness is not a goal**: the artifact is a tolerance table per metric ([`../docs/validation/golden-files.md`](../docs/validation/golden-files.md)).

## Envelope the design works inside (measured esp-dsp cycle counts, ESP32-S3 @ 240 MHz)

| Block | Cost | Consequence |
|---|---|---|
| Real FFT N = 4096 at 50 Hz | ≈ 6 % of one core with pipeline overhead | The FFT is not the bottleneck; SRAM and display bandwidth are |
| Real FFT N = 8192 | ≈ 112–144 KB internal SRAM `(prov.)` — the radix-4 kernel's twiddle table alone is 64 KB, which is what separates the estimates ([03-dsp-pipeline §4.1](../docs/architecture/03-dsp-pipeline.md)) | Comfortable ceiling; N = 16384 (≈ 192–224 KB) is the hard ceiling; N ≥ 32768 infeasible |
| `dsps_fft2r_sc16` (fixed-point, PIE SIMD) | 6.3× faster than `fc32` but loses one bit per stage | Not usable for a 60–90 dB display without a block-floating-point layer — use `fc32` |
| `log10f` on every bin | 6–8 % of a core at 2048 bins × 50 Hz | Use a float-exponent fast log, or convert only rendered columns |
| Time-domain f0 (YIN/MPM, 1024 lags) | ≈ 6 % | MPM needs ~2 periods and fits the 20 ms `live_singing` hop where YIN does not |
| 4-stage decimation biquad cascade | ≈ 1.4 % | Spectroid-style "decimations" are cheap if done with a real IIR low-pass |

Sources: esp-dsp benchmark table and issue #98 measurements, catalogued in [`../docs/bibliography/02-application-notes.md`](../docs/bibliography/02-application-notes.md). Every figure is re-measured on target in Phase 1 (`dsp_get_cpu_cycle_count()`), including the `bit_rev` + `cplx2real` overhead that the published table omits.

## Background reading

Spectral estimation and windows: Heinzel 2002, Harris 1978, Nuttall 1981 ([`05-papers.md`](../docs/bibliography/05-papers.md)); Smith, *Spectral Audio Signal Processing* (peak interpolation) and Lyons ([`04-books.md`](../docs/bibliography/04-books.md)). Pitch: de Cheveigné & Kawahara 2002 (YIN), McLeod & Wyvill 2005 (MPM), Mauch & Dixon 2014 (pYIN) — the host-side reference. Voice: Sundberg (singer's formant), Omori 1996 (SPR), Müller 2022 (FHE) in [`08-voice-metrology-on-the-wrist.md`](../docs/bibliography/08-voice-metrology-on-the-wrist.md).
