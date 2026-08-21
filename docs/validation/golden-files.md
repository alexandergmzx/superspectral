# Golden files — Praat/parselmouth reference vectors for the on-device DSP

**Status:** specification. [ADR 0009](../adr/0009-golden-file-strategy.md) is **accepted**; this file is its normative detail, amended 2026-08-21 when the bundled-Praat version was measured. **Owner:** the generator lives in [`../../host/golden/`](../../host/golden/README.md) (GPL-3.0-or-later side of the licence boundary, because it imports parselmouth); the generated vectors and this manifest are **data**, consumed by the Apache-2.0 host tests in [`../../host-tests/`](../../host-tests/README.md) and by the QEMU/target backend-agreement test. No code crosses the boundary; only files do.

## Why a manifest, not a file

"Parselmouth is numerically identical to Praat" holds only for the Praat version parselmouth **bundles**. praat.org is at 7.0.01 (Boersma, Weenink & Shchupak — read 2026-08-21); Praat changed its default pitch method from raw to **filtered** autocorrelation in 2023; parselmouth's bundled Praat predates both. Praat's pitch floor, ceiling, voicing threshold, silence threshold and octave-jump cost all change the answer. **An unpinned golden file is not a golden file.** Before any tolerance is frozen, one WAV is run through the bundled Praat and through Praat 7.0.01 and the difference is recorded (roadmap threshold **T7b**; T7a — *which* Praat parselmouth bundles — closed on 2026-08-21 at 6.1.38).

## Manifest schema (`manifest.yaml` — one manifest per vector set, per the schema's `set` field)

```yaml
schema: 1
set: tier0-synthetic          # also the output directory: outputs/<set>/
generated: "2026-MM-DD"       # quoted: an unquoted date is not a JSON string
generator:
  script: host/golden/generate.py
  sha256: <64 hex of generate.py>
  commit: <40 hex repo commit>
  python: 3.12.3              # `python3 --version`
  numpy: <version>
  scipy: <version>
  parselmouth: <version>      # `praat-parselmouth` PyPI version
  praat_bundled: <version>    # parselmouth.PRAAT_VERSION
  praat_reference: null       # T7b open: no out-of-process Praat has been run yet
  platform: <uname -srm>
  blas: <numpy.show_config() vendor + version>
inputs:
  # 32 kHz is the watch's default rate (ADR 0003) and the only rate any preset
  # is set to today, so the primary Tier-0 set is generated at it. A 48 kHz
  # twin is generated too -- it exercises the host-only stem_analysis preset --
  # but nothing may depend on 48 kHz on the watch until experiment 0001
  # clause 4 passes (ADR 0003 decision 5, roadmap threshold T3).
  - path: datasets/tier0/sine_440_0dBFS_32k.wav
    sha256: <64 hex>
    sample_rate: 32000
    bit_depth: 16
    channels: 1
    source: {kind: tier0-synthetic, name: sine,
             parameters: {frequency_hz: 440.0, level_dbfs: 0.0, phase_rad: 0.0}}
  - path: datasets/tier0/sine_440_0dBFS_48k.wav   # host-only until T3 passes
    sha256: <64 hex>
    sample_rate: 48000
    bit_depth: 16
    channels: 1
    source: {kind: tier0-synthetic, name: sine,
             parameters: {frequency_hz: 440.0, level_dbfs: 0.0, phase_rad: 0.0}}
analyses:
  pitch:
    # `raw`, not `filtered`, and this is a measurement rather than a preference:
    # every released praat-parselmouth (0.4.0 ... 0.4.7) bundles Praat 6.1.38,
    # which registers `To Pitch (ac)` and `To Pitch (cc)` and nothing else.
    # Asking for the filtered method raises, verbatim from 0.4.7 on 2026-08-21:
    #   PraatError: Command "To Pitch (filtered autocorrelation)" not available
    #   for given objects.
    # Praat introduced it in 6.4 (2023-11-15). Filtered's own defaults --
    # silence 0.09, voicing 0.50, octave cost 0.055, floor 50 / TOP 800 with an
    # `attenuation at top` of 0.03 -- are recorded in ADR 0009 for the day a
    # parselmouth release reaches Praat >= 6.4. Note "top", not "ceiling": the
    # filtered method does not take the `pitch_ceiling` this block carries, so
    # a filtered set will need a schema minor bump, not just a new enum value.
    method: raw                # Praat 6.1.38 `To Pitch (ac)...`
    time_step: 0.01            # s -- pinned; Praat's own default is 0.0 (auto)
    pitch_floor: 65            # Hz (C2) -- widened for singing (prov.); raw default 75
    pitch_ceiling: 1100        # Hz (above C6) -- widened for singing (prov.); raw default 600
    silence_threshold: 0.03    # raw default
    voicing_threshold: 0.45    # raw default
    octave_cost: 0.01          # raw default
    octave_jump_cost: 0.35     # raw default
    voiced_unvoiced_cost: 0.14 # raw default
    max_candidates: 15         # raw default
    very_accurate: false       # same in both
  formant:
    method: burg
    time_step: 0.01
    max_formants: 5            # Praat fits 2 x max_formants poles: LPC order 10, not 12
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
  - path: host/golden/outputs/tier0-synthetic/pitch_sine_440.npy
    sha256: <64 hex>
    analysis: pitch
    input: datasets/tier0/sine_440_0dBFS_32k.wav
    dtype: float64
    shape: [<n frames>, 2]     # Praat's frame grid decides n; compare by time, never by index
    units: "s, Hz"
    columns: [time, f0]
    unvoiced_sentinel: 0       # Praat writes 0 for unvoiced; never read it as a frequency
tolerances:
  source: docs/validation/golden-files.md   # a pointer, never the limits themselves
  revision: <40 hex commit of this file>
regeneration:
  date: "2026-MM-DD"
  reason: initial generation
  approved_by: <the human who reviewed the manifest diff>
  previous_manifest_sha256: null
  previous_set: null
```

Every field above is **required**; a vector set whose manifest entry is missing any of them is rejected by the test harness, not silently defaulted. The example is prose *and* machine-checked: the required lists live once, in [`../../host/golden/manifest.schema.yaml`](../../host/golden/manifest.schema.yaml) (JSON Schema draft 2020-12, `additionalProperties: false`), and this block validates against it once the `<…>` placeholders are filled — that schema, not this page, is what `verify.py` loads. Where the two ever disagree the schema wins and this block is the bug. The sha256 of every input WAV and every output array is the only identity the tests trust.

## Tolerance table, not equality (prov.)

Bit-exactness between an Xtensa LX7 single-precision pipeline and an x86-64 double-precision Praat is **not achievable** and is not the goal. The artefact is a tolerance per metric, each with the reason it is not tighter.

| Comparison | Metric | Tolerance (prov.) | Why not tighter |
|---|---|---|---|
| Device f0 vs Praat, injection path | median \|Δcents\| over voiced frames | ≤ 5 cents | different estimator class (time-domain MPM/YIN vs Praat's autocorrelation with candidate tracking); frames near voicing boundaries excluded by mir_eval convention |
| Device f0 vs Praat, acoustic path | median \|Δcents\| | ≤ 20 cents | whole-chain metric (see [README](README.md) two-path rule) |
| Device voicing vs Praat | VR / VFA | ≥ 90 % / ≤ 10 % | voicing thresholds are estimator-specific |
| `spectral_core` window **table digest** per `(family, N)` | sha256 of the float32 table | **exact** | [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md) D1: a window that quietly changes shape shifts every level by a fraction of a dB and nothing else notices. The digest is a golden-manifest field; a mismatch is a red `verify`, not a widened tolerance |
| `spectral_to_dbfs_fast()` vs `log10()` in double | max abs. error over the float32 domain | **≤ 0.005 dB** `(prov.)` | [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md) D9. Its **own** row, deliberately: the fast log is an approximation we choose, not a platform difference we absorb, so it may not eat the 0.01 dB spectrum budget. Verified exhaustively in host-tests, not sampled. M0 ships exact `log10f` and this row is dormant until a polynomial exists |
| `spectral_core` window coefficients vs `scipy.signal.windows.general_cosine(N, a, sym=False)` | `assert_allclose`, float32 | `atol = 1e-6`, `rtol = 0` | float32 evaluation of `cos()` on Xtensa libm vs x86 glibc differs in the last ULP |

**Do not build the reference window from `get_window(<name>, N, fftbins=True)`.** Four of the six preset families happen to match a SciPy name exactly, and two do not, in opposite directions (measured with SciPy 1.18.0 at N = 4096, 2026-08-21):

| preset family | nearest SciPy name | max abs. difference |
|---|---|---:|
| `hann`, `blackman`, `blackman_harris` (→ `blackmanharris`), `flat_top` (→ `flattop`) | matches | **0** |
| `blackman_nuttall` | `nuttall` | **0** — SciPy's `nuttall` *is* the Blackman–Nuttall set |
| `nuttall` | *none* | **0.0163** — esp-dsp's Nuttall set is a different window |

So the oracle builds every window from the coefficient table in [`preset-schema.md` §4.3](../../protocols/specs/preset-schema.md) via `general_cosine(N, a, sym=False)`, and records the *preset* name. Two independent checks that the periodic form is the right one, same run: `N·S2/S1²` equals the closed form `(a₀² + Σ_{k≥1} a_k²/2)/a₀²` **and** the `enbw_bins` each preset ships, to the printed precision, for all six families; the symmetric form does not (`hann` gives 1.500366, not 1.5).
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
- **Praat-version trap.** Bundled Praat ≠ praat.org Praat; raw vs filtered autocorrelation. *Signature:* the same WAV gives two f0 tracks that differ by a few cents in vibrato cycles and by whole frames at onsets. *Pin:* `praat_bundled`, `method` in the manifest; threshold T7b result recorded. **Measured 2026-08-21:** the trap does not currently have two sides to fall between — parselmouth 0.4.7 bundles Praat **6.1.38**, the filtered method does not exist there, and praat.org is at 7.0.01. Every golden set is therefore `method: raw` on 2021-era code until T7b measures the gap; the RQ's "vs Praat" anchor must name that version.

## Tooling

- **Host (Python, GPL side):** `host/golden/generate.py` writes the vectors and the manifest; `pytest-regressions` (`num_regression`, `file_regression`) keeps the host-side numeric snapshots; `numpy.testing.assert_allclose(rtol=…, atol=…)` with the explicit values from the table above.
- **Host (C, Apache side):** `host-tests/` is a plain-CMake build of `spectral_core` (pure C99, `REQUIRES ""`) with ASan/UBSan and `ctest`; it reads the vectors and the manifest and applies the tolerance table. esp-dsp cannot build on the ESP-IDF `linux` target (its `CMakeLists.txt` registers the Xtensa `.S` files unconditionally), so the host lane tests `spectral_core` against NumPy, not esp-dsp.
- **QEMU / target (backend agreement):** `sdkconfig.ci.qemu` builds with `CONFIG_DSP_OPTIMIZED=y`; the test loads the same vectors through the `file_blob` audio source, runs esp-dsp's `_aes3` path and the ANSI path, and compares both to the golden magnitudes in dB. QEMU for the ESP32-S3 emulates PSRAM, the PSRAM MMU, eFuse and GPIO strapping but **not** I²C, I²S, GP-SPI, USB or the GPIO matrix — which is exactly why the audio-source and display-backend seams exist. Whether QEMU executes the S3 TIE/PIE vector instructions correctly is open question H12; the ANSI lane is the fallback.
- **Where the numbers go:** every CI run emits the per-metric residuals as an artifact; `check_performance()` fails a regression; the tolerance table here is the only place a limit is defined.

## Reference basis

Boersma 1993 and Jadoul et al. 2018 (05); the Praat manual pages for `To Pitch (filtered ac)`, `To Formant (burg)`, `To Spectrogram` (06); Heinzel 2002 and Harris 1978 for the conventions (05); the ESP-IDF host-apps and QEMU guides (11). ADR 0009 will cite this file as its specification.
