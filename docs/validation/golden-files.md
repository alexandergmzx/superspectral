# Golden files — Praat/parselmouth reference vectors for the on-device DSP

**Status:** specification, provisional until [ADR 0009](../adr/0009-golden-file-strategy.md) is accepted. **Owner:** the generator lives in [`../../host/golden/`](../../host/golden/README.md) (GPL-3.0-or-later side of the licence boundary, because it imports parselmouth); the generated vectors and this manifest are **data**, consumed by the Apache-2.0 host tests in [`../../host-tests/`](../../host-tests/README.md) and by the QEMU/target backend-agreement test. No code crosses the boundary; only files do.

## Why a manifest, not a file

"Parselmouth is numerically identical to Praat" holds only for the Praat version parselmouth **bundles**. praat.org is at 7.0.01 (Boersma, Weenink & Shchupak); Praat changed its default pitch method from raw to **filtered** autocorrelation in 2023; parselmouth's bundled Praat predates both. Praat's pitch floor, ceiling, voicing threshold, silence threshold and octave-jump cost all change the answer. **An unpinned golden file is not a golden file.** Before any tolerance is frozen, one WAV is run through the bundled Praat and through Praat 7.0.01 and the difference is recorded (roadmap threshold T7).

## Manifest schema (`golden/manifest.yaml`, one entry per vector set)

```yaml
schema: 1
generated: 2026-MM-DD
generator:
  script: host/golden/generate.py
  commit: <repo sha>
  python: 3.12.3              # `python3 --version`
  numpy: <version>
  scipy: <version>
  parselmouth: <version>      # `praat-parselmouth` PyPI version
  praat_bundled: <version>    # parselmouth.PRAAT_VERSION
  praat_reference: 7.0.01     # the version the T7 comparison was run against
inputs:
  - path: datasets/tier0/sine_440_0dBFS_48k.wav
    sha256: <64 hex>
    sample_rate: 48000
    bit_depth: 16
    channels: 1
analyses:
  pitch:
    method: filtered | raw     # Praat "To Pitch (filtered ac)" vs "To Pitch (raw ac)"
    time_step: 0.01            # s -- pinned; Praat's own default is 0.0 (auto)
    pitch_floor: 65            # Hz (C2) -- widened for singing (prov.)
    pitch_ceiling: 1100        # Hz (above C6) -- widened for singing (prov.)
    silence_threshold: 0.09    # filtered; raw's default is 0.03
    voicing_threshold: 0.50    # filtered; raw's default is 0.45
    octave_cost: 0.055         # filtered; raw's default is 0.01
    octave_jump_cost: 0.35     # same in both
    voiced_unvoiced_cost: 0.14 # same in both
    max_candidates: 15         # same in both
    very_accurate: false       # same in both
  formant:
    method: burg
    time_step: 0.01
    max_formants: 5
    ceiling_hz: 5500           # per Praat: ~5000 male / 5500 female; FormantPath later
    window_length: 0.025
    preemphasis_from_hz: 50
  spectrogram:
    window_shape: gaussian     # Praat: bandwidth = 1.2982804 / window length
    window_length: 0.005       # 260 Hz wideband; 0.030 → 43 Hz narrowband
    time_step: 0.002
    frequency_step: 20
    max_frequency: 8000
  ltas:
    bandwidth_hz: 100
outputs:
  - path: golden/pitch/sine_440.npy
    sha256: <64 hex>
    dtype: float64
    shape: [N, 2]              # (time, f0); 0 = unvoiced
tolerances: see table below    # referenced, not duplicated
```

Every field above is **required**; a vector set whose manifest entry is missing any of them is rejected by the test harness, not silently defaulted. The sha256 of every input WAV and every output array is the only identity the tests trust.

## Tolerance table, not equality (prov.)

Bit-exactness between an Xtensa LX7 single-precision pipeline and an x86-64 double-precision Praat is **not achievable** and is not the goal. The artefact is a tolerance per metric, each with the reason it is not tighter.

| Comparison | Metric | Tolerance (prov.) | Why not tighter |
|---|---|---|---|
| Device f0 vs Praat, injection path | median \|Δcents\| over voiced frames | ≤ 5 cents | different estimator class (time-domain MPM/YIN vs Praat's autocorrelation with candidate tracking); frames near voicing boundaries excluded by mir_eval convention |
| Device f0 vs Praat, acoustic path | median \|Δcents\| | ≤ 20 cents | whole-chain metric (see [README](README.md) two-path rule) |
| Device voicing vs Praat | VR / VFA | ≥ 90 % / ≤ 10 % | voicing thresholds are estimator-specific |
| `spectral_core` window coefficients vs `scipy.signal.get_window(..., fftbins=True)` | `assert_allclose`, float32 | `atol = 1e-6`, `rtol = 0` | float32 evaluation of `cos()` on Xtensa libm vs x86 glibc differs in the last ULP |
| `spectral_core` magnitude spectrum vs `numpy.fft.rfft` (same window, same normalization per ADR 0006) | per-bin level in dB | `atol = 0.01 dB` for bins ≥ −80 dBFS; bins below are masked | float32 accumulation across 11 radix-2 stages |
| esp-dsp `_aes3` (optimized) vs esp-dsp ANSI-C, on QEMU/target ("backend agreement") | per-bin magnitude | `rtol = 1e-4` in linear magnitude (≈ 1e-3 dB) | the assembly kernels reorder the butterflies; same precision, different rounding path |
| Interpolated peak frequency vs known synthetic tone | cents | ≤ 3 cents on-bin and off-bin | quadratic interpolation bias per window (Smith SASP) |
| Device F1/F2 vs Praat Burg | Hz or % | ≤ 5 % or 50 Hz, whichever larger | LPC order, pre-emphasis and ceiling must match the manifest exactly or the comparison is meaningless (roadmap Q36) |
| Device LTAS band levels vs Praat `To Ltas` (same bandwidth) | dB per band | ≤ 0.2 dB | window and normalization conventions (ADR 0006) |
| Device FHE / SPR vs host | Hz / dB | ≤ 50 Hz / ≤ 0.5 dB | both are read off the same LTAS; differences are band-edge interpolation |

A tolerance is only ever **widened with a recorded reason** in the commit message and in this table; it is never widened to make a failing test pass on the day.

## Gotchas — each with its false-result signature

Bold callouts in swarm's style: name, cost, what the wrong answer looks like, what must be pinned.

- **Periodic-vs-symmetric window trap.** `scipy.signal.get_window('hann', N)` is periodic (`fftbins=True`); `scipy.signal.windows.hann(N)` defaults to symmetric (`sym=True`); esp-dsp's `dsps_wind_hann_f32` and Praat's Gaussian follow their own conventions. *Signature:* every bin off by a fraction of a dB, worst at small N; the two-tone test resolves one bin later than theory. *Pin:* the `fftbins`/`sym` flag in the manifest and in `spectral_core`'s window header comment.
- **Normalization trap.** 1/N, 1/√N, none; power spectrum vs power spectral density (S1 vs S2 sums, NENBW per Heinzel 2002). *Signature:* a sine's peak reads right but the noise floor is "2 dB off", or vice versa. *Pin:* ADR 0006 fixes one convention; the test multiplies by the documented factor, never by a fudge.
- **dBFS reference trap.** A full-scale **sine** is 0 dBFS in one convention and −3.01 dBFS in the other (full-scale square = 0 dBFS). *Signature:* a constant 3 dB offset between device and host that "goes away" if someone edits a constant. *Pin:* sine-referenced dBFS, stated in ADR 0006 and in the preset schema.
- **int16 scaling trap.** ÷32768 vs ÷32767; PDM slots are fixed at 16 bits on the S3. *Signature:* 0.00026 dB — invisible until a clipping test at exactly full scale disagrees on the flag. *Pin:* ÷32768 and a clipping threshold stated in counts, not in float.
- **Mel-filterbank norm trap** (host-side feature parity only). `slaney` vs `htk`; librosa changed defaults across 0.8 → 0.10. *Signature:* band levels scale with centre frequency. *Pin:* norm and librosa version in the manifest if mel features are ever golden-filed.
- **Float32 accumulation trap.** Summing 4096 squared magnitudes in float32 in a different order (SIMD lanes vs scalar) changes the last bits; Kahan on one side and not the other changes more. *Signature:* backend-agreement test passes on the ANSI lane and fails by ~1e-5 on `_aes3`. *Pin:* compare in dB with the stated `rtol`, never `==`.
- **Xtensa libm vs x86 libm trap.** `sinf`, `expf`, `log10f` differ in the last ULP between newlib/picolibc on Xtensa and glibc on x86; GCC may contract `a*b+c` into FMA on one target. *Signature:* identical code, identical inputs, 1-ULP differences that compound through a log. *Pin:* `-ffast-math` forbidden; `-ffp-contract=off` in the host build when chasing a discrepancy; tolerances, not equality.
- **`log10f` cost trap** (not a correctness trap, but it changes what gets golden-filed). ~150 cycles per call; the device uses a float-exponent bit-trick log or computes only the rendered columns. *Signature:* device dB values match the host to ±0.05 dB, not ±0.001 dB. *Pin:* the device-side log approximation's documented max error is part of the tolerance budget.
- **Frame-grid trap.** librosa `center=True` pads by N/2; Praat places its first frame at `t1 = (duration − (nFrames − 1)·dt) / 2`; the device frames from sample 0 with a hop. *Signature:* RPA fine, but per-frame comparisons show a constant time offset → cents error spikes at every note onset. *Pin:* resample the host f0 track onto the device's frame times before comparing; never compare frame indices.
- **Resampling trap.** CREPE's published numbers are at 16 kHz / 1024-sample frames; the device runs 32 or 48 kHz. *Signature:* apparent accuracy gap vs the literature that is really a resampler. *Pin:* the sample rate of every vector set in the manifest; compare like with like.
- **Praat-version trap.** Bundled Praat ≠ praat.org Praat; raw vs filtered autocorrelation. *Signature:* the same WAV gives two f0 tracks that differ by a few cents in vibrato cycles and by whole frames at onsets. *Pin:* `praat_bundled`, `method` in the manifest; threshold T7 result recorded.

## Tooling

- **Host (Python, GPL side):** `host/golden/generate.py` writes the vectors and the manifest; `pytest-regressions` (`num_regression`, `file_regression`) keeps the host-side numeric snapshots; `numpy.testing.assert_allclose(rtol=…, atol=…)` with the explicit values from the table above.
- **Host (C, Apache side):** `host-tests/` is a plain-CMake build of `spectral_core` (pure C99, `REQUIRES ""`) with ASan/UBSan and `ctest`; it reads the vectors and the manifest and applies the tolerance table. esp-dsp cannot build on the ESP-IDF `linux` target (its `CMakeLists.txt` registers the Xtensa `.S` files unconditionally), so the host lane tests `spectral_core` against NumPy, not esp-dsp.
- **QEMU / target (backend agreement):** `sdkconfig.ci.qemu` builds with `CONFIG_DSP_OPTIMIZED=y`; the test loads the same vectors through the `file_blob` audio source, runs esp-dsp's `_aes3` path and the ANSI path, and compares both to the golden magnitudes in dB. QEMU for the ESP32-S3 emulates PSRAM, the PSRAM MMU, eFuse and GPIO strapping but **not** I²C, I²S, GP-SPI, USB or the GPIO matrix — which is exactly why the audio-source and display-backend seams exist. Whether QEMU executes the S3 TIE/PIE vector instructions correctly is open question H12; the ANSI lane is the fallback.
- **Where the numbers go:** every CI run emits the per-metric residuals as an artifact; `check_performance()` fails a regression; the tolerance table here is the only place a limit is defined.

## Reference basis

Boersma 1993 and Jadoul et al. 2018 (05); the Praat manual pages for `To Pitch (filtered ac)`, `To Formant (burg)`, `To Spectrogram` (06); Heinzel 2002 and Harris 1978 for the conventions (05); the ESP-IDF host-apps and QEMU guides (11). ADR 0009 will cite this file as its specification.
