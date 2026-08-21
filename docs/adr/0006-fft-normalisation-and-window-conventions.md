# 0006 — One spectral convention for both halves: periodic cosine-sum windows built from the preset's own coefficients, Heinzel S1/S2 scaling, 0 dBFS = full-scale sine, `fc32` only, and our own `cplx2real` because esp-dsp's drags in a 64 KB table and a `double`

- **Status:** **proposed** — the engineering is settled and evidenced below; what needs the owner is the *acceptance*, because two of these decisions (D5 own `cplx2real`, D7 DC-blocker form) trade internal SRAM and maintenance against each other and CLAUDE.md tenet 3 makes SRAM the binding resource. Flip to `accepted` and this closes the last named ADR line of the Phase-0 definition of done.
- **Date:** 2026-08-21
- **Context:** `spectral_core`'s header has carried the whole convention in comments since E1 — periodic windows, S1/S2, `PS = 2|X|²/S1²`, one-sided factor 2 on bins `1 … N/2−1`, 0 dBFS as a full-scale sine — and nothing ratifies it. That is not a formality: the watch and the host must agree to a stated tolerance ([ADR 0009](0009-golden-file-strategy.md)), so every one of those sentences is a two-sided contract, and a golden file generated against an unratified convention pins a guess. [`03-dsp-pipeline.md` §3](../architecture/03-dsp-pipeline.md) lists what is still owed and §12 routes thirteen open questions here. Meanwhile `spectral_core/src/` is empty, so nothing has been written against the wrong answer yet — this is the cheapest moment to fix the conventions in place.

  Three constraints shape every decision below.
  - **Internal SRAM is the binding resource** (CLAUDE.md tenet 3). 512 KB total; FFT working buffers must be internal and 16-byte aligned; PSRAM is for history and assets, never DMA and never FFT scratch.
  - **The host is the reference, and it is NumPy/SciPy/Praat.** A convention that is awkward to reproduce in NumPy costs a permanent translation layer in `host/`, and translation layers are where golden files quietly stop meaning what they say.
  - **esp-dsp is a kernel supplier, not a framework.** [ADR 0018](0018-first-reference-project-study.md) already established that its windows are the wrong form and its allocations are not capability-aware. This record extends that to its real-FFT unpacking.

- **Decision:**

  **1. Windows are periodic cosine sums, generated in `spectral_core` from the coefficients carried in the preset file.** `w[j] = Σ_k (−1)^k a_k cos(2πkj/N)` for `j = 0 … N−1` — the length-`N` period, not the symmetric `1/(N−1)` form. `dsps_wind_*_f32` are never called: all six are symmetric ([ADR 0018](0018-first-reference-project-study.md) §2). The coefficient table lives in **one** place, [`preset-schema.md` §4.3](../../protocols/specs/preset-schema.md), and both halves read it from there — the firmware compiles it in and asserts it against the preset's own `coefficients` on load (rule V8), the host builds the window with `scipy.signal.windows.general_cosine(N, a, sym=False)`.

  This closes **OQ1** by choosing "compute the cosine sum from the preset's coefficients" over "generate `N+1` and drop the last sample".

  **The two routes are mathematically identical, and this record originally claimed otherwise.** Measured 2026-08-21, SciPy 1.18.0, `N = 4096`: `general_cosine(N+1, a, sym=True)[:-1] − general_cosine(N, a, sym=False)` has `max|Δ| = 0` for **all six** coefficient sets — necessarily so, since the symmetric length-`N+1` form divides by `(N+1)−1 = N`, which *is* the periodic length-`N` formula. So the drop-last route is rejected on cost and clarity (an extra sample generated and discarded, and a formula whose correctness depends on an off-by-one), **not** on a numerical difference.

  What the measurement below actually supports is the *separate* decision to build from **coefficients rather than names** — which is the trap that would have bitten us, because the host oracle is SciPy:

  | preset family | nearest SciPy name | `max |Δ|` |
  |---|---|---:|
  | `hann`, `blackman`, `blackman_harris` (→ `blackmanharris`), `flat_top` (→ `flattop`) | matches | **0** |
  | `blackman_nuttall` | `nuttall` | **0** — SciPy's `nuttall` *is* the Blackman–Nuttall set |
  | `nuttall` | *none* | **0.0163** — esp-dsp's Nuttall set is a different window |

  So `get_window(<name>, N, fftbins=True)` is not a safe oracle for one of the six families, and any convention that routes through a *name* rather than through *coefficients* has a silent 0.0163 error in it. Coefficients are the contract.

  **Precision policy.** The table may be built with `double` `cos()` at init — it is a one-off cost of `N` transcendentals, and float `cosf(2πj/N)` at `N = 8192` accumulates ≈ 4×10⁻⁷ per term over up to five terms, which is not comfortably inside the 1×10⁻⁶ tolerance row. `spectral_process()` itself stays float-only, as `-Wdouble-promotion -Werror` already enforces.

  **The table is checksummed.** `spectral_window_fill()`'s output per `(family, N)` is hashed and the digest is a field of the golden manifest, so a window that quietly changes shape fails `verify` rather than shifting every level by a fraction of a dB. *(This adds a field to [`host/golden/manifest.schema.yaml`](../../host/golden/manifest.schema.yaml) — a schema **minor bump**, done when the generator lands, not retroactively.)*

  **2. Normalisation is Heinzel S1/S2, exactly as [`spectral.h`](../../firmware/twatch-s3/components/spectral_core/include/spectral_core/spectral.h) already states it.** Ratified verbatim rather than restated, so there is one text:

  ```
  S1    = Σ w[j]                 S2 = Σ w[j]²         NENBW = N·S2/S1²  [bins]
  PS  [FS²]    = 2·|X[k]|² / S1²          ENBW  = NENBW · fs/N   [Hz]
  PSD [FS²/Hz] = 2·|X[k]|² / (fs·S2)      PS = PSD · ENBW
  factor 2 on k = 1 … N/2−1 only; DC and Nyquist are NOT doubled
  the injected transform is UNNORMALISED (no 1/N, no 1/√N); scaling is spectral_core's
  ```

  Two closed forms make this testable without a reference implementation, and they are why the preset file can carry `enbw_bins` as data. For a **periodic** cosine-sum window and integer `N`, orthogonality gives exactly `S1 = N·a₀` and `S2 = N·(a₀² + Σ_{k≥1} a_k²/2)`, hence

  ```
  NENBW = N·S2/S1² = (a₀² + Σ_{k≥1} a_k²/2) / a₀²
  ```

  which is precisely the `enbw_bins` each preset ships. Verified for all six families on 2026-08-21 (`hann` 1.500000, `blackman` 1.726757, `blackman_harris` 2.004353, `blackman_nuttall` 1.976109, `nuttall` 2.021233, `flat_top` 3.770246 — computed `N·S2/S1²` equals the closed form equals the shipped value to the printed precision). The **symmetric length-`N`** form does not: `hann` gives 1.500366 instead of 1.5. That is the argument for *periodic*, and it is a host test — note it is a different question from the drop-last route above, which produces the periodic window exactly.

  **3. 0 dBFS is a full-scale sine.** `dBFS = 10·log10(PS / 0.5)`. The square case needs stating carefully, because `PS` here is **per bin** and the familiar +3.01 dB is **broadband**, and conflating them is a 0.9 dB error in a test:

  | full-scale signal, hann window, N = 4096 | reads |
  |---|---:|
  | sine on a bin centre — peak bin | **0.00 dBFS** |
  | square — **fundamental (peak) bin** | **+2.10 dBFS** |
  | square — **total power**, `Σ PS / NENBW` | **+3.01 dBFS** |

(Measured 2026-08-21 with the convention exactly as D2 defines it. The fundamental of a square is `4/π` times the sine's amplitude, i.e. `20·log10(4/π) = +2.10 dB`; the +3.01 dB is the square's RMS² of 1 against the sine's 0.5, summed over every harmonic.) **Both rows are asserted in host-tests**, and the pair is the point: a test written from "a full-scale square reads +3.01 dBFS" against a per-bin `PS` fails by 0.92 dB, which is how this document read until the re-audit caught it. PSD is displayed as `10·log10(PSD / 0.5)` labelled **dBFS/Hz** — a different axis with a different unit, never silently mixed with PS on one readout. Floor **−200 dB**. `int16 → float × 1/32768` happens exactly once, at the `audio_source` seam ([ADR 0003](0003-microphone-path.md) d.2); `32768` and not `32767`, and the ~0.00026 dB difference between the two conventions is recorded rather than argued about.

  **4. `fc32` only. `sc16` is rejected, with the arithmetic.** The fixed-point butterfly shifts right by one per stage with no exponent tracking, so a real-`N` transform (complex `N/2`, `log2(N/2)` stages) loses that many bits: **10 bits ≈ 60 dB at real-2048, 12 bits ≈ 72 dB at real-8192**, out of a 16-bit input. Every shipped preset asks for a 90–100 dB display range (`db_floor_dbfs` −90 or −100 under a 0 dBFS ceiling), so the trade is not available. **This is a per-bin argument and not a microphone argument** — the mic's 61.5 dB(A) broadband SNR is *not* a ceiling on the spectrogram, because an `N`-point FFT spreads broadband noise over `N/2` bins. Revisit trigger: a block-floating-point layer with per-stage headroom detection, validated against the float path, which esp-dsp does not provide.

  **5. We write our own `cplx2real`. (OQ4 — closed, on source evidence.)** The real path is complex-`N/2` + bit-reverse + a split step. esp-dsp ships that split step, and using it costs 64 KB and a `double`. Both read from the pinned tree at `firmware/idf-gate/managed_components/espressif__esp-dsp/modules/fft/float/dsps_fft4r_fc32_ansi.c` on 2026-08-21:

  - `dsps_cplx2real_fc32_ansi_()` **refuses to run unless `dsps_fft4r_initialized`** — its first statement is `if (0 == dsps_fft4r_initialized) return ESP_ERR_DSP_UNINITIALIZED;` — *even though it takes a `table` pointer argument*. So using it forces `dsps_fft4r_init_fc32()`, whose table is `malloc(max_fft_size * sizeof(float) * 4)`, i.e. **16 bytes per complex point = 65 536 B at `N_c` = 4096**. Compare `dsps_fft2r_init_fc32`, which allocates `sizeof(float) * table_size` = **4 bytes per point = 16 384 B**, and on the S3 uses a **const ROM table and no heap at all** for `N_c ≤ 1024`.
  - Its inner loop computes `result[k].re = 0.5 * (f1k.re + tw.re)` and three siblings. In C, `0.5` is a **`double`** literal, so every output bin is computed in double and narrowed on assignment — exactly what `-Wdouble-promotion` exists to catch, in the hot loop, on a single-precision FPU.

  Ours needs half-bin angles `cos/sin(πk/N_c)` for `k = 0 … N_c/2`: `4·(N_c+2)` bytes = **16 392 B at `N_c` = 4096**, float-only, ≈ 30 lines from the standard identity (Sorensen 1987; Smith, *SASP*). It also removes the `fft4r` dependency from the radix-2 path entirely, which means one less esp-dsp global with one less owner.

  Net, per real-`N`, tables only:

  Tables only, in bytes. Both routes pay the fft2r twiddles and its bit-reversal copy; the choice is the last column pair.

  | real `N` | `N_c` | fft2r twiddles | fft2r bit-rev | **our split** | **total, ours** | fft4r twiddles | fft4r bit-rev | **total, theirs** |
  |---:|---:|---:|---:|---:|---:|---:|---:|---:|
  | 2048 | 1024 | **0** (const ROM) | 1 984 | **4 104** | **≈ 6 KB** | 16 384 | 1 920 | ≈ 20 KB |
  | 4096 | 2048 | 8 192 | 3 968 | **8 200** | **≈ 20 KB** | *n/a* | *n/a* | *no radix-4 path: `N_c` = 2048 is not `4^k`* |
  | 8192 | 4096 | 16 384 | 8 064 | **16 392** | **≈ 40 KB** | 65 536 | 8 064 | ≈ 96 KB |

  Two things in that table are easy to get wrong and were, in the first draft of this record.
  **The bit-reversal copies are not optional.** `dsps_fft2r_init_fc32` *unconditionally* `malloc`s a RAM copy of the const table — `malloc(2 * dsps_fft2r_rev_tables_fc32_size[log2(N_c)−4] * sizeof(uint16_t))`, with `bitrev2r_table_4096_fc32_size = 2016`, so 8 064 B at `N_c` = 4096 — and no argument supplies it. `dsps_fft4r_init_fc32` does the same with its own table. Omitting both put an earlier draft 8 KB under the figure [ADR 0002](0002-companion-architecture.md) and [ADR 0018](0018-first-reference-project-study.md) already carried.
  **Radix-4 does not exist at real-4096**, the default analysis size: `N_c` = 2048 is not a power of four. So for the preset that matters most, there is no "theirs" — only ours, or `dsps_cplx2real_fc32` dragging in an fft4r table sized for a transform it will never run.

  There is a second, sharper reason. `CONFIG_SPIRAM_MALLOC_ALWAYSINTERNAL=16384` sends anything *strictly larger* to PSRAM first, and esp-dsp allocates with plain `malloc`/`memalign`. The fft2r table at `N_c` = 4096 is 16 384 B and lands internal **by one byte**; the fft4r table at 65 536 B does not. So "use esp-dsp's" does not merely cost 48 KB — it silently puts FFT scratch in PSRAM, which tenet 3 forbids and which the bandwidth numbers say costs 7–13×. **Cost accepted:** ≈ 30 lines of hand-written DSP that must agree with the host reference; the backend-agreement test is what makes that safe, and it is a required deliverable of this record, not an optional one.

  **6. `fft2r` for every size in v1. (OQ3.)** It accepts any power of two; the default analysis size (real-4096 → `N_c` = 2048) is not a power of four and cannot use radix-4 at all, so carrying both kernels buys a faster path for two of six presets at the cost of a second code path, a second set of globals and a second alignment rule. Revisit trigger: an on-target cycle count (roadmap **H13**) showing fft4r wins enough at real-2048/8192 to matter against the 50 Hz budget. **`CONFIG_DSP_MAX_FFT_SIZE` stays 4096** — it bounds `N_c`, not `N_real`, so the default already covers real-8192 on the real path (**OQ2** closed; the correction is owed to [`xiao-edge-audio_notes.md`](../reference-projects/notes/xiao-edge-audio_notes.md) §3, which says it must be raised).

  **7. The DC blocker is the one-pole–one-zero form.** `y[n] = x[n] − x[n−1] + R·y[n−1]`, `R = 1 − 2π·f_c/f_s` (0.996073 at 20 Hz / 32 kHz), one state, float32, applied **before** the window, after the `1/32768` scaling. `R` is recorded per take. An RBJ biquad is rejected: it puts two coefficients within 1.2×10⁻⁷ of the unit circle to place a pole 3.9×10⁻³ away from it, in float32, and it is a second implementation to keep in step with the host. The one-pole form's ≈ +0.3 dB shelf error near `f_c` is accepted and is a tolerance row, not a defect.

  **8. Smoothing, averaging and hold are applied in linear power, never in dB. (OQ8.)** dB-domain averaging of a noise-like bin biases low by ≈ 2.5 dB (the mean of a log is not the log of the mean; Heinzel §9). Not exercised in M0, but fixed now because it is the kind of decision that is made accidentally by whoever writes the display code first.

  **9. Deferred by name, so that nothing is deferred by silence.**
  - **Fast log (OQ7)** — `spectral_to_dbfs()` ships on `log10f` (exact). `spectral_to_dbfs_fast()` (exponent extraction + minimax polynomial on the mantissa) lands only with a measured cycle count and gets its **own tolerance row**, budget `|err| ≤ 0.005 dB (prov.)`, verified exhaustively over the float32 domain in host-tests. Until then the dB stage is not a bottleneck anyone has measured.
  - **Bins → dB count (OQ10)** — whether all `N/2+1` bins or only the ≈ 240 rendered columns are converted couples this stage to the display mapping and to what a take records. Belongs to **ADR 0007**, which is gated on a hardware measurement.
  - **Gaussian window (OQ13, roadmap Q34)** — Praat's convention, not in the enum, not in esp-dsp. Adding it is a schema change and a Praat-comparability argument, both of which need the T7b result first.
  - **f0 estimator (OQ9)** — MPM vs YIN vs dywapitchtrack, lag range, voicing decision, octave guard. **Allocated as ADR 0020**, not folded in here: it is a different kind of decision (an estimator with its own accuracy claim) and folding it in would make this record unreviewable.
  - **Decimation filter (OQ6)** — `dsp/design/decimation-cascade.md`, not an ADR.

- **Alternatives:**

  - **Symmetric windows, matching esp-dsp's `dsps_wind_*_f32` and `scipy.signal.<name>(N, sym=True)`.** Rejected: the DFT of a symmetric window has a discontinuity at the period boundary, `NENBW` no longer equals the closed form the presets ship (1.500366 vs 1.5 for `hann` at N = 4096), and every level readout acquires a small `N`-dependent bias. *Verdict: rejected. Revisit trigger: none — this is a correctness question, not a preference.*
  - **`1/N`-normalised transform** (numpy's `norm="forward"`). Rejected: it makes `PS` depend on the window through `S1/N` rather than `S1`, which is the same information written less legibly, and it disagrees with Heinzel — the reference every level claim in `docs/validation/` is anchored to. *Verdict: rejected.*
  - **Name-based window construction** (`get_window(name, N, fftbins=True)` on the host, enum on the device). Rejected on the 0.0163 measurement above. *Verdict: rejected; the coefficient table is the contract.*
  - **esp-dsp's `dsps_cplx2real_fc32`.** Rejected on the two source facts in D5. *Verdict: rejected. Revisit trigger: an upstream release that drops the `dsps_fft4r_initialized` guard **and** the `0.5` double literal — check at every esp-dsp bump, it is a two-line diff to look for.*
  - **Carry both radix kernels from v1.** Rejected as premature (D6). *Verdict: deferred to an H13 measurement.*
  - **RBJ biquad DC blocker.** Rejected on float32 conditioning and on host-parity cost (D7). *Verdict: rejected. Revisit trigger: a measured need for a steeper roll-off than 6 dB/octave below `f_c`.*
  - **Fold the f0 estimator into this record.** Rejected: unreviewable scope. *Verdict: allocated ADR 0020.*

- **Consequences:**
  - (+) `spectral_core/src/` can be written: every body has a ratified convention and a closed-form test that does not depend on a reference implementation existing first.
  - (+) The host oracle is a direct transcription — `general_cosine(N, a, sym=False)`, the same S1/S2 arithmetic, the same dBFS reference — so the two halves differ only in float width and libm, which is what the tolerance table was designed to absorb.
  - (+) Real-8192 fits internal SRAM with room: **≈ 40 KB** of tables plus `4N` work plus `4N` window = **≈ 104 KB**, against **≈ 160 KB** if esp-dsp's fft4r table were paid for and internal — or a tenet-3 violation if it were not, since 65 536 B exceeds `CONFIG_SPIRAM_MALLOC_ALWAYSINTERNAL` and would be sent to PSRAM. These are the same two figures [ADR 0002](0002-companion-architecture.md) and [ADR 0018](0018-first-reference-project-study.md) already carry, and they agree because all three now count the bit-reversal copy.
  - (+) The window-table digest turns "the window quietly changed" from an undetectable half-dB drift into a red `verify`.
  - (−) ≈ 30 lines of hand-written split-radix unpacking that upstream would otherwise supply. It must agree with `fft_ref.c` bit-for-bit within tolerance, on ANSI and on the S3 SIMD path, and that agreement test is now load-bearing rather than nice to have.
  - (−) The window coefficient table exists in three languages (C, Python, JSON). The preset's `coefficients` field plus rule V8 is what keeps them equal, and V8 is only checked when a preset is *loaded* — a hard-coded table used without a preset would escape it. `spectral_window_fill()` therefore takes the coefficients as an argument; it has no built-in table to drift from.
  - (−) Two decisions here (D5, D7) buy internal SRAM and numeric conditioning with maintenance. Both revisit triggers are measurements, and neither is scheduled.
  - (−) Deciding the smoothing domain (D8) before anything smooths means it is decided on theory. The theory is Heinzel's and it is not controversial, but it has not been demonstrated on this device.
  - (−) The fast-log budget of 0.005 dB is `(prov.)` and was chosen to sit well inside the 0.01 dB golden-file row, not derived from an error analysis of a specific polynomial. It will move when a polynomial exists.

  Reference basis: [05 #1](../bibliography/05-papers.md) (Heinzel, Rüdiger & Schilling 2002 — S1/S2, NENBW, periodic windows, the dB-averaging bias), [05 #2](../bibliography/05-papers.md) (Harris 1978), [05 #3](../bibliography/05-papers.md) (Nuttall 1981 — the coefficient sets), [04 #1](../bibliography/04-books.md) (Smith, *SASP* — the real-FFT `N/2` packing identity and quadratic peak interpolation), [06 #1](../bibliography/06-reference-projects.md) (esp-dsp; read at the pinned managed-component tree for D5's two source facts), [02 #20](../bibliography/02-application-notes.md), [02 #21](../bibliography/02-application-notes.md) (ESP-DSP API reference and benchmarks); [ADR 0003](0003-microphone-path.md) (the `1/32768` seam), [ADR 0009](0009-golden-file-strategy.md) (why every sentence here is two-sided), [ADR 0010](0010-preset-schema.md) (`coefficients` and `enbw_bins` as data), [ADR 0018](0018-first-reference-project-study.md) (esp-dsp's windows are symmetric; its allocations are not capability-aware); [`03-dsp-pipeline.md`](../architecture/03-dsp-pipeline.md) §3, §7.1 and §12 for the questions this record answers, and [`preset-schema.md` §4.3](../../protocols/specs/preset-schema.md) for the coefficient table that is the single source.
