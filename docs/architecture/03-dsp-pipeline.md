# 03 — DSP pipeline: one chain, one set of conventions, and an FFT that is never the bottleneck

**Status:** design note for **[ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md) — FFT normalisation and window conventions — which is now *written* (`proposed`, 2026-08-21, decisions D1–D9); what is still owed is its acceptance.** Everything here that is already binding comes from an accepted record ([0003](../adr/0003-microphone-path.md) capture, [0010](../adr/0010-preset-schema.md) presets, [0013](../adr/0013-native-linux-simulator-target.md) seams, [0018](../adr/0018-first-reference-project-study.md) what esp-dsp actually supplies) or from a measured file in this repository. Everything that is **not** ratified is stated as an open question in §12 with a pointer to the backlog or to the roadmap's Q/H/T tables — this note deliberately decides nothing.

The decision the chain rests on, stated once: **the transform is cheap and the memory is not.** A real-4096 FFT at 50 frames/s costs ≈ 6 % of one core *(prov.)*, while its working set costs 56 KB of internal SRAM out of 512 KB shared with LVGL, the I²S DMA ring and the SPI bounce buffer (`scratch/research/domainMap.md` §2.2, gitignored working notes — research estimates, not measurements). Every trade-off below is therefore paid in bytes and in bus stalls, not in cycles.

## 1. The chain

```
  audio_source (ADR 0003)                 spectral_core — pure C99, zero esp_*, caller owns every buffer
  ┌───────────────────────┐               ┌──────────────────────────────────────────────────────────────┐
  │ PDM RX I2S0 16-bit    │  float ring   │                                                              │
  │ int16 x (1/32768)     ├──────────────►│  DC blocker ──► window ──► real FFT ──► |X|² ──► dB ──► smooth│
  │ clip flag |s| >= 0.99 │  internal     │  1st-order or   periodic   injected     S1/S2     fast  /hold │
  │ file_blob | synthetic │  DMA-capable  │  RBJ HPF,       cosine     via          scaling    log   per  │
  └───────────────────────┘  SRAM         │  f_c 20 Hz      sum,       spectral_    (ADR              pre-│
                                          │  (prov.)        N taps     rfft_fn      0006)             set │
                                          │      │                         │                           │  │
                                          │      │ time-domain branch      │                           ▼  │
                                          │      ▼                         │                     bins to  │
                                          │  f0 (MPM / YIN / dywa —        │                     render   │
                                          │  §9, no ADR number yet)        │                           │  │
                                          │      │                         │                           │  │
                                          │      │  band energy / FHE / SPR (ADR 0008, backlog) ◄───────┤  │
                                          └──────┼─────────────────────────┼───────────────────────────┼──┘
                                                 │                         │ spectral_rfft_fn          │
                                                 │             ┌───────────┴───────────┐               │
                                                 │             ▼                       ▼               │
                                                 │   spectral_fft_backend        fft_ref.c             │
                                                 │   esp-dsp fc32, target        host + QEMU            │
                                                 │   (§6)                        radix-2 float          │
                                                 ▼                                                     ▼
                                          spectral_frame_t  ──── double-buffered, queue of pointers ──► renderer
                                                                                            (ADR 0007 / 0011, core 0)
```

Three properties of that picture are contracts, not drawing conventions:

- **The transform is injected.** `spectral_core` never links esp-dsp; it calls a `spectral_rfft_fn` function pointer ([`spectral.h`](../../firmware/twatch-s3/components/spectral_core/include/spectral_core/spectral.h)). That is what lets the identical arithmetic run under ASan/UBSan on a laptop ([`host-tests/`](../../host-tests/README.md)), inside QEMU and on the watch — the precondition for the golden-file lane ([ADR 0009](../adr/0009-golden-file-strategy.md)).
- **The DC blocker sits in the capture path, before the window, and is declared.** The ESP32-S3 has no hardware PDM high-pass (`SOC_I2S_SUPPORTS_PDM_RX_HP_FILTER` is absent for this target), so this filter always exists and the host must reproduce it bit-for-bit-within-tolerance ([ADR 0003](../adr/0003-microphone-path.md) decision 6). Corner **20 Hz (prov.)** in all six shipped presets, listed in each preset's `provisional` array.
- **The only operations permitted between the microphone and `|X|²` are linear and logged** — DC removal, the mic EQ slot, the window, and a fixed logged gain ([ADR 0003](../adr/0003-microphone-path.md) decision 7). No NS, no AGC, no AEC, ever ([CLAUDE.md](../../CLAUDE.md) never-rule 8).

## 2. Where each stage lives

| Stage | Component | Lane it runs in |
|---|---|---|
| `int16 → float`, clipping flag, ring buffer | [`audio_source`](../../firmware/twatch-s3/components/audio_source/README.md) | target (`pdm_mic`); target/QEMU/host (`file_blob`, `synthetic`) |
| DC blocker, window, S1/S2 scaling, dB, smoothing/hold, peak picking, f0 front end | [`spectral_core`](../../firmware/twatch-s3/components/spectral_core/README.md) | everywhere — pure C99, `REQUIRES ""` |
| The real FFT itself | [`spectral_fft_backend`](../../firmware/twatch-s3/components/spectral_fft_backend/README.md) (esp-dsp) · `spectral_core/src/fft_ref.c` (host) | target/QEMU · host |
| Bins → columns, colormap, scroll | `ui` + the display path | ADR 0007 / [0011](../adr/0011-spectrogram-colormap.md) — **not this document** |

The split is not stylistic: esp-dsp cannot build on the ESP-IDF `linux` target (Xtensa `.S` files registered unconditionally, ANSI sources including `esp_attr.h`), which is why `spectral_core` is the piece that must stay dependency-free ([ADR 0013](../adr/0013-native-linux-simulator-target.md), [`host-tests/README.md`](../../host-tests/README.md)).

## 3. Conventions: what is fixed

> **ADR 0006 is written** ([`0006-fft-normalisation-and-window-conventions.md`](../adr/0006-fft-normalisation-and-window-conventions.md), `proposed` 2026-08-21). Everything this section used to list as "still owed" now has an answer; the table below is unchanged because ADR 0006 ratified it verbatim rather than restating it.

Fixed today, because an accepted ADR or a committed header says so:

| Convention | Value | Source |
|---|---|---|
| Sample format into the chain | `int16 → float × 1/32768`, once, at the `audio_source` seam | [ADR 0003](../adr/0003-microphone-path.md) decision 2 |
| Precision | `fc32` (float32) only; `sc16` rejected — fixed `>>16` per butterfly is 1/2 per stage, 1/N overall, `log2 N` bits lost, no exponent tracking | [esp-dsp notes](../reference-projects/notes/esp-dsp_notes.md) §8; [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md) D4 |
| Window families | the six esp-dsp ships, coefficients carried **in the preset file** | [preset schema](../../protocols/specs/preset-schema.md) §4.3 |
| Window form | `form` is a `const "periodic"` in the schema | [preset schema](../../protocols/specs/preset-schema.md) §4.3 — **but see §7.1** |
| Normalisation | Heinzel S1/S2: `NENBW = N·S2/S1²`, `PS = 2·\|X\|²/S1²`, `PSD = 2·\|X\|²/(f_s·S2)`, factor 2 on bins `1 … N/2−1` only | [`spectral.h`](../../firmware/twatch-s3/components/spectral_core/include/spectral_core/spectral.h); 05 #1 |
| dB reference | `dbfs_sine` — 0 dBFS is a full-scale **sine**; a full-scale square reads +3.01 dBFS | [preset schema](../../protocols/specs/preset-schema.md) §4.2 |
| Bandwidth | `enbw_hz` is mandatory per preset; the words "wideband"/"narrowband" are banned from preset files | [ADR 0010](../adr/0010-preset-schema.md) decision 2 |
| Analysis bandwidth ≠ display rate | `interval_ms` is the hop; `display.refresh_hz_target` is frames pushed | [ADR 0010](../adr/0010-preset-schema.md) decision 4 |

Settled by [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md) on 2026-08-21, each with its decision number there:

| Was owed | Now |
|---|---|
| periodic-window construction (§7.1) | **D1** — cosine sum from the preset's own `coefficients`, never `dsps_wind_*`; table checksummed into the golden manifest. The deciding measurement: preset `nuttall` differs from SciPy's `nuttall` by 0.0163, so name-based construction is unsafe |
| the `1/N` vs `1/√N` bookkeeping `spectral.h` sketches | **D2** — ratified verbatim; the transform is unnormalised and `spectral_core` applies S1/S2. Closed forms `S1 = N·a₀`, `S2 = N(a₀² + Σa_k²/2)` make it testable without a reference |
| fast-log error budget (§10) | **D9** — its own tolerance row, `≤ 0.005 dB (prov.)`, exhaustively verified; M0 ships `log10f` |
| smoothing/hold domain (§12 OQ8) | **D8** — linear power, never dB (dB-domain averaging biases ≈ 2.5 dB low) |
| Gaussian window (roadmap Q34) | **D9 deferred by name** — needs the T7b Praat-comparability result first |

One correction this note must carry rather than repeat: **the microphone's 61.5 dB(A) SNR does not cap the displayed spectral dynamic range.** An N-point FFT spreads broadband noise over N/2 bins, so a tonal component sits roughly `10·log10((N/2)/NENBW)` above the floor the broadband figure suggests — about +30 dB at N = 4096. The mic SNR bounds *wideband level* accuracy ([`spectral.h`](../../firmware/twatch-s3/components/spectral_core/include/spectral_core/spectral.h) header note; [validation README](../validation/README.md) "Displayed spectral dynamic range"; 05 #1).

## 4. N per preset, and the arithmetic that follows from it

Straight from the six committed files in [`../../protocols/presets/`](../../protocols/presets/README.md) — every column here is either read from the JSON or recomputed from it by the loader's rules V8/V9:

| Preset | N | window | f_s | hop (samples) | overlap | frames/s | render Hz | `enbw_hz` | window (ms) |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `diction_consonants` | 1024 | hann | 32 k | 320 | 69 % | 100 | 50 (2 cols/frame) | 46.875 | 32.0 |
| `live_singing` | 4096 | blackman_harris | 32 k | 640 | 84 % | 50 | 50 | 15.659008 | 128.0 |
| `sustained_pitch_lab` | 8192 | blackman_harris | 32 k | 1280 | 84 % | 25 | 25 | 7.829504 | 256.0 |
| `vowel_formant_study` | 8192 | hann | 32 k | 1280 | 84 % | 25 | 25 | 5.859375 | 256.0 |
| `room_noise_floor` | 8192 | hann | 32 k | 1280 | 84 % | 25 | 25 | 5.859375 | 256.0 |
| `stem_analysis` (**host**) | 8192 | hann | 48 k | 480 | 94 % | 100 | — | 8.789062 | 170.666667 |

Two consequences worth stating out loud. **All six are narrowband analyses** against Koenig's 300/45 Hz pair, and the one named for consonants is the *closest* to narrowband — [ADR 0010](../adr/0010-preset-schema.md) made that visible and explicitly declined to fix it; a genuinely wideband preset (N ≈ 128–256) is an ADR 0006 / preset-content question. And **no shipped preset uses `hop = N/2`**. `spectral_config_t.hop` in [`spectral.h`](../../firmware/twatch-s3/components/spectral_core/include/spectral_core/spectral.h) once documented itself as "`N/2` = 50 %"; that comment was corrected in the ADR 0006 commit and now reads "NOT `N/2`: every shipped preset overlaps 69-94 %" (§12 OQ12, closed).

### 4.1 SRAM arithmetic — two itemisations that do not agree yet

The research estimate, `≈ 10·N` bytes per real-FFT size, **all figures (prov.)** (`scratch/research/domainMap.md` §2.2 — research estimates, never measured on this unit):

| Real N | workspace | twiddle | window | input ring | total |
|---:|---:|---:|---:|---:|---:|
| 2048 | 8 KB | **0** (S3 ROM table) | 8 KB | 8 KB | **24 KB** |
| 4096 | 16 KB | 8 KB | 16 KB | 16 KB | **56 KB** |
| 8192 | 32 KB | 16 KB | 32 KB | 32 KB | **112 KB** — the comfortable ceiling |
| 16384 | 64 KB | 32 KB | 64 KB | 64 KB | **224 KB** — hard ceiling, host-only in the schema |

That table is the source of the `≤ 112 KB` figure in [CLAUDE.md](../../CLAUDE.md) tenet 3 and in [ADR 0010](../adr/0010-preset-schema.md)'s `fft_size` clause; the [architecture README](README.md)'s row for this file and [`02-audio-capture-path.md`](02-audio-capture-path.md) §5 were moved to the post-[ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md) ≈ 104 KB on 2026-08-21, and the two remaining sites are corrections owed. Two honest caveats travel with the table:

1. **The rule of thumb undercounts its own table.** The itemisation sums to `14·N` bytes (112 KB = 14 × 8192), not `10·N`; the prose "int16 input ring 2N" and the table's `4N` input-ring column disagree. Nothing downstream uses `10·N`, so this is a wording defect in the research note, but it is the reason no document should quote the rule of thumb without the table.
2. **Reading esp-dsp's actual allocations gives a different number.** The [esp-dsp study notes](../reference-projects/notes/esp-dsp_notes.md) §4.1 itemise the real-input `fc32` pipeline byte by byte and land at **≈ 159.8 KB** for real-8192 — because `dsps_cplx2real_fc32` requires `dsps_fft4r_init_fc32`'s **64 KB** twiddle table *even on the radix-2 path*, and the research estimate does not include it. The same note gives the documented route back under the ceiling: supply our own `cplx2real` half-bin twiddles (`4·(N_c+2)` bytes = 16 392 B instead of 65 536), which drops real-8192 to **≈ 104 KB** and removes the fft4r dependency from the radix-2 path entirely.

3. **A third itemisation, read from the allocation calls, explains *why* the first two disagree — the kernel changes the twiddle cost by 4×.** `dsps_fft4r_init_fc32` allocates `max_fft_size * sizeof(float) * 4` = **16 bytes per complex point**, while `dsps_fft2r_init_fc32` allocates `table_size * sizeof(float)` = **4 bytes per complex point** (both verified in the vendored clone at `modules/fft/float/dsps_fft{2,4}r_fc32_ansi.c`). Radix-4 needs `N_c` to be a power of four, so the kernel a preset can use alternates with N:

   | Real N | N_c | signal buf | twiddle (kernel) | window | magnitudes | total | bytes/N |
   |---:|---:|---:|---:|---:|---:|---:|---:|
   | 1024 | 512 | 4 KB | 2 KB (fft2r) | 4 KB | 2 KB | **12 KB** | 12·N |
   | 2048 | 1024 | 8 KB | 16 KB (fft4r) | 8 KB | 4 KB | **36 KB** | 18·N |
   | 4096 | 2048 | 16 KB | 8 KB (fft2r) | 16 KB | 8 KB | **48 KB** | 12·N |
   | **8192** | 4096 | 32 KB | **64 KB (fft4r)** | 32 KB | 16 KB | **144 KB** | 18·N |
   | 16384 | 8192 | 64 KB | 32 KB (fft2r) | 64 KB | 32 KB | **192 KB** | 12·N |

   Two consequences the earlier estimates hide. **(a)** Real-8192 lands on radix-4, whose table alone is 64 KB, so its true cost is ≈ 144 KB rather than 112 KB — a third of the way past the estimate, against an internal-SRAM budget that also has to hold I²S DMA, the LVGL partial buffers and the SPI bounce buffer. **(b)** Nothing forces radix-4: `fft2r` accepts any power of two, so real-8192 on `fft2r` would pay 16 KB of table instead of 64 KB, trading memory for speed. That is a real design choice, it is not made anywhere yet, and it belongs to **ADR 0006** with a measurement behind it, not to this note.

**Neither figure is measured on target.** Both stay `(prov.)` until the on-target measurement of roadmap **H13** (`dsp_get_cpu_cycle_count()` + a heap census per preset). Reconciling them is open question **OQ4/OQ5** below; the [`spectral_fft_backend` README](../../firmware/twatch-s3/components/spectral_fft_backend/README.md)'s "~32 KB for n = 4096 (prov.)" is already flagged as a correction owed by the study notes §13.

## 5. Why the FFT working buffers are internal SRAM, 16-byte aligned

Three independent reasons, none of them preference:

**(a) The assembly requires alignment and does not check it.** esp-dsp's `dsps_fft2r_fc32_aes3_` and `dsps_fft4r_fc32_aes3_` use only `ee.ldf.64.ip` / `ee.stf.64.ip`, so **8 bytes** is the hard requirement and esp-dsp's own examples use 16; the `sc16` kernels use `ee.vld.128.ip` and need 16. There is **no runtime check on the FFT path** — a misaligned buffer is a `LoadStoreAlignment` panic, not an `ESP_ERR_DSP_ARRAY_NOT_ALIGNED` ([esp-dsp notes](../reference-projects/notes/esp-dsp_notes.md) §4.3). Hence `heap_caps_aligned_alloc(16, …)` or `__attribute__((aligned(16)))` on every buffer handed to the library, plus an assert on the pointer at init.

**(b) PSRAM is bandwidth-bound, and an FFT is a bandwidth workload.** Published measurements on an ESP32-S3 with octal 80 MHz PSRAM, cache flushed (06 #23, **all (prov.)** — a third-party matrix, re-measured on target in Phase 1): IRAM→IRAM `memcpy` **366 MB/s**; IRAM→PSRAM **32.5 MB/s**; PSRAM→IRAM **56.8 MB/s**; PSRAM→PSRAM **21.2 MB/s**, and the PIE path buys *nothing* on the PSRAM legs because they are bus-bound. An in-place radix-2 real-4096 FFT makes 11 passes ≈ 360 KB of traffic ⇒ **6.5–11.3 ms of memory stalls against ≈ 1.05 ms of arithmetic**, a **6–11×** slowdown. *(The arithmetic figure is the whole real path — FFT 213 k + bit-reverse and `cplx2real` 40 k ≈ 253 k cycles ÷ 240 MHz — per [esp-dsp notes §11](../reference-projects/notes/esp-dsp_notes.md). An earlier draft used 0.89 ms here, the transform alone, which is not what the 360 KB of traffic buys and made the ratio look worse than it is; [proposal §3.3](../proposal/01-super-spectral-proposal.md) carries the same 1.05 ms.)* PSRAM holds spectrogram history (256 bins × 1 B × 50 col/s = 12.8 KB/s, ≈ 0.04 % of the write path), fonts and LVGL assets — never a working buffer, never a DMA endpoint.

**(c) esp-dsp's own allocations are capability-blind, so the default lands in the wrong place.** `dsps_fft4r_init_fc32` uses plain `malloc`, `dsps_fft2r_init_fc32` uses `memalign`; on ESP-IDF both route through the default heap, and our committed [`sdkconfig.defaults.esp32s3`](../../firmware/twatch-s3/sdkconfig.defaults.esp32s3) sets `CONFIG_SPIRAM_MALLOC_ALWAYSINTERNAL=16384`, which sends anything *strictly larger* to PSRAM first. Concretely: the fft2r twiddles at `N_c = 4096` are 16 384 B and stay internal by one byte, while the **fft4r twiddles at `N_c = 2048` (32 KB) and `N_c = 4096` (64 KB) land in PSRAM** ([esp-dsp notes](../reference-projects/notes/esp-dsp_notes.md) §4.2). The rule that follows: `spectral_fft_backend` **always passes its own buffers** to both inits — `heap_caps_aligned_alloc(16, n, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT)`, never `NULL`.

> **Correction made (2026-08-21).** The PSRAM comment block in [`sdkconfig.defaults.esp32s3`](../../firmware/twatch-s3/sdkconfig.defaults.esp32s3) used to read *"FFT scratch, spectrogram history and fonts go to PSRAM explicitly via `MALLOC_CAP_SPIRAM`"*, which contradicted [CLAUDE.md](../../CLAUDE.md) tenet 3, [ADR 0018](../adr/0018-first-reference-project-study.md) and (b) above. The comment was wrong, not the Kconfig. It now reads *"Spectrogram history and fonts go to PSRAM explicitly via `MALLOC_CAP_SPIRAM`. … FFT scratch does NOT: it stays in internal SRAM, 16-byte aligned"* and explains why the 16384-byte threshold is load-bearing (§12 OQ11, closed).

## 6. esp-dsp entry points, and the `fft_ref` host seam

There is **no `dsps_fft4real_*` symbol in esp-dsp** — `examples/fft4real/` is a directory, not an API ([esp-dsp notes](../reference-projects/notes/esp-dsp_notes.md) §2.1; a correction owed to 06 #1, to [`main/idf_component.yml`](../../firmware/twatch-s3/main/idf_component.yml) and to the [backend README](../../firmware/twatch-s3/components/spectral_fft_backend/README.md)). The real-input path is composed by hand from four calls, with `N_c = N_real/2`:

```
  once, at boot, on the DSP task's core, with the LARGEST N_c any preset uses
  ├─ dsps_fft2r_init_fc32(our_buf_2r, N_C_MAX)   4 * N_C_MAX bytes, ours, 16 B aligned
  └─ dsps_fft4r_init_fc32(our_buf_4r, N_C_MAX)  16 * N_C_MAX bytes -- FOUR floats per
                                                 entry, which the doxygen does not say
  per frame, in place, the real array IS the complex array (even -> re, odd -> im)
  ├─ window multiply                             our periodic table (§7.1)
  ├─ dsps_fft4r_fc32 + dsps_bit_rev4r_fc32       iff N_c = 4^k
  │  dsps_fft2r_fc32 + dsps_bit_rev2r_fc32       otherwise -- NOT dsps_bit_rev_fc32,
  │                                              which has no optimised version
  ├─ dsps_cplx2real_fc32(work, N_c)              needs the fft4r twiddles even here
  └─ unpack: slot[0].re = X[0] (DC), slot[0].im = X[N_c] (Nyquist)
             |X[k]| for 1 <= k < N_c from slot[k]; emit N/2 + 1 bins
```

Facts this sequence encodes, each verified in the study notes rather than assumed:

- **Init once, with the maximum.** A second init with a *different* size returns `ESP_OK` and silently keeps the old table; a table smaller than N is a silent over-read with wrong output and no error code (§2.2, reproduced on the host).
- **Slot 0 is not an ordinary bin.** `sqrt(re² + im²)` on slot 0 mixes DC with Nyquist — esp-dsp's own `examples/fft4real` computes exactly that wrong value. DC and Nyquist scale with `N`; every other bin with `N/2`; the one-sided ×2 applies to bins `1 … N/2−1` only.
- **Radix availability falls awkwardly across our presets.** `fft4r` accepts only `N_c = 4^k`, so **real-2048 and real-8192 can use the faster kernel and real-1024 and real-4096 cannot** — the default analysis size is on the slow side of the constraint (§2.1, §3 of the notes).
- **The globals are process-wide.** `dsps_fft_w_table_fc32`, `dsps_fft4r_w_table_fc32`, the rev tables and the `*_initialized` flags are shared; `dsps_snr_f32` inits them behind your back. One owner (`spectral_fft_backend`), one init, one deinit.

**The `fft_ref` seam.** `spectral_core/src/fft_ref.c` is a plain radix-2 float32 real FFT on the host side of the same `spectral_rfft_fn` contract: `n` windowed real floats in, `n/2 + 1` interleaved complex bins out, **unnormalised forward DFT** (no `1/N`, no `1/√N`) — `spectral_core` applies the S1/S2 scaling either way. It exists for three jobs: it makes `host-tests/` runnable with no ESP-IDF, it is one half of the **backend-agreement** test that catches esp-dsp misuse (wrong init size, forgotten bit-reverse, slot-0 mishandling), and it is the only lane in which the numerics can be run under ASan/UBSan. The agreement is asserted **in dB against a tolerance table, never as equality** — `rtol = 1e-4` in linear magnitude for esp-dsp `_aes3` vs esp-dsp ANSI, `atol = 0.01 dB` for `spectral_core` vs `numpy.fft.rfft` on bins ≥ −80 dBFS ([`golden-files.md`](../validation/golden-files.md); [ADR 0009](../adr/0009-golden-file-strategy.md)). Bit-exactness is not a goal and cannot be one: float32 Xtensa with newlib/picolibc against float64 x86-64 with glibc.

## 7. Two facts the study notes surfaced that the implementation must resolve

### 7.1 esp-dsp's windows are symmetric; the preset schema declares periodic

All six `dsps_wind_*_f32` compute `len_mult = 1/(float)(len − 1)` — the **symmetric** form. The preset schema fixes `analysis.window.form` as a `const "periodic"` (DFT-even), `spectral_core`'s header states periodic as the rule, and the golden-file tolerance row compares against `scipy.signal.get_window(..., fftbins=True)`. Those cannot both be satisfied by calling the library function as-is. This is a **real mismatch**, not a documentation slip, and it is the classic golden-file killer: at N = 8192 the difference is one sample in the window, worth far less than the 1×10⁻⁶ coefficient tolerance in isolation but enough to shift S1, S2 and therefore the whole dB axis in a way that no test would attribute to the window.

The coefficient *sets* are a **second, independent** problem, and the sentence this note used to carry — that esp-dsp's sets are already identical to SciPy's — is wrong for one family. Measured at `N = 8192`, periodic form, SciPy 1.18.0 (2026-08-21; same numbers as [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md) D1's table):

| preset family | nearest SciPy name | `max \|Δ\|` |
|---|---|---:|
| `hann`, `blackman`, `blackman_harris` (→ `blackmanharris`), `flat_top` (→ `flattop`) | matches | **0** (≤ 4×10⁻¹⁶) |
| `blackman_nuttall` | `nuttall` | **0** — SciPy's `nuttall` *is* the Blackman–Nuttall set |
| `nuttall` | *none* | **0.0163** — esp-dsp's `nuttall` `[0.355768, 0.487396, 0.144232, 0.012604]` (Nuttall 1981's minimum-4-term) is a **different window** from SciPy's `nuttall` `[0.3635819, 0.4891775, 0.1365995, 0.0106411]` |

So the `1/(len−1)` denominator is *not* the only discrepancy, and `get_window(<name>, N, fftbins=True)` is not a safe oracle for one of the six families. Two routes are documented ([esp-dsp notes](../reference-projects/notes/esp-dsp_notes.md) §5): call `dsps_wind_hann_f32(tmp, N+1)` and use the first `N` samples, or compute the cosine sum in `spectral_core` from the coefficients the preset already carries. The second also avoids esp-dsp's per-sample `double` promotion (`i * 2 * M_PI * len_mult` with a `double` `M_PI`), which `-Wdouble-promotion` exists to catch — and only the second is immune to the name trap, which is why D1 chose it. See also [`preset-schema.md` §4.3](../../protocols/specs/preset-schema.md), which carries the coefficient table that is the single source.

**Decided since: [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md) D1** — the cosine sum is computed from the preset's own `coefficients`, `dsps_wind_*` is never called, and the table is checksummed into the golden manifest (§12 OQ1, closed). `spectral_core` already exposes `spectral_window_fill()` precisely so the watch and the host generator share one table.

### 7.2 `CONFIG_DSP_MAX_FFT_SIZE` — the tree contains two answers

The Kconfig default is **4096**, and the symbol bounds **`N_c`, the complex transform length — not `N_real`**. Our real-8192 preset uses `N_c = 4096`, so the default is *exactly* sufficient, with **zero margin**. Two study notes in this repository disagree about what that means:

| Note | Says |
|---|---|
| [`xiao-edge-audio_notes.md`](../reference-projects/notes/xiao-edge-audio_notes.md) §2.3, §3 | "default 4096 — **our real-8192 preset needs this raised**"; a `sdkconfig.defaults` line we must carry |
| [`esp-dsp_notes.md`](../reference-projects/notes/esp-dsp_notes.md) §4.1, §13 | bounds `N_c`, not `N_real`; the default already covers real-8192 on the real path. "**No `sdkconfig.defaults` change is needed.**" The xiao note is listed as a correction owed |

The esp-dsp note is the one written against the library source, and it names the earlier note as the thing to correct — but **no accepted record has ratified either**, and the margin is nil, so the question is live for at least three reasons: a host-target `fft_size: 16384` preset is already legal in the schema; a zero-padded *complex* 8192 transform would need the raise; and `dsps_fft2r_init_sc16` and `dsps_snr_f32` allocate at this symbol regardless of what we ask for. **Decided since: [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md) D6** — `CONFIG_DSP_MAX_FFT_SIZE` stays **4096**, because it bounds `N_c` and the default already covers real-8192 on the real path (§12 OQ2, closed). The correction to the xiao note is still owed. The three reasons above do not disappear; they become revisit triggers rather than blockers.

## 8. The decimation cascade for the octave bank

`analysis.decimations` is an integer 0–4 in the schema; stage *k* analyses at `sample_rate_hz / 2^k`, which is the Spectroid model for buying low-frequency resolution without paying for a longer transform. **It is `0` in every one of the six shipped presets, and the cascade does not exist yet** — it is designed in `dsp/design/decimation-cascade.md` ([`../../dsp/design/README.md`](../../dsp/design/README.md), planned, roadmap D5/D6).

What is already settled and what is not:

- **Settled: a real low-pass, never decimate-by-averaging.** That is the documented trap the Friture maintainer removed from its FFT path (06 #32; [preset schema](../../protocols/specs/preset-schema.md) §4.2). Friture's own octave bank is a cascaded-decimation elliptic-IIR design with a log-constant −3 dB width (07 #12) — the prior art, not a specification we have adopted.
- **Not settled: which filter, and from where.** esp-dsp has **no IIR decimator**: `modules/iir` is single biquads (`dsps_biquad_f32`, transposed direct-form II, RBJ convention, `Fs = 1` normalised frequency in the generators), while the decimating filters live in `modules/fir` (`dsps_fird_f32`, `dsps_firmr_f32`), whose init functions allocate their delay lines with unchecked `memalign`/`malloc` — so the delay line must be passed in ([esp-dsp notes](../reference-projects/notes/esp-dsp_notes.md) §6, §9). The two cost figures in circulation measure different things and neither is ours: a 4-stage **biquad** cascade at ≈ 1.4 % of one core *(prov.*, `domainMap.md` §2.5, assuming ≈ 17 cycles/sample*)*, versus esp-dsp's published **115 499 cycles** for `dsps_fird_f32` at 1024 samples / 256 taps / decimation 4 (02 #21) — an FIR decimator two orders of magnitude more expensive per block.
- **Not settled: group-delay alignment between stages.** A cascade whose stages have different delays draws a spectrogram whose low band is time-shifted against its high band. The design note owes an alignment rule; nothing in the schema expresses one.
- **Explicitly out of scope here:** the octave bank's *class compliance*. ANSI S1.11 / IEC 61260-1 are validation anchors in [`../validation/README.md`](../validation/README.md), **not design targets** ([`../../dsp/design/README.md`](../../dsp/design/README.md)).
- **Also unresolved: `dsps_biquad_f32` is not SIMD on the S3.** The header's `#elif` ordering makes the LX7 always take the ESP32 `_ae32` kernel, leaving `dsps_biquad_f32_aes3.S` dead code — corroborated by the published benchmark, where the S3 is *marginally slower* than the ESP32 at 1024 samples (17 552 vs 17 442 cycles). Any cascade budget built on "the biquad is vectorised" is wrong.

The marginal mAh per decimation stage is a **reportable quantity** of the research question's objective 4, measured in Phase 1 ([`../validation/README.md`](../validation/README.md), "Energy per preset").

## 9. f0: MPM, YIN, dywapitchtrack

f0 is a **time-domain** branch that reads the DC-blocked float stream *before* windowing — it is not derived from the magnitude spectrum. Three candidates are catalogued, all buildable on `dsps_corr_f32`:

| Candidate | Why it is a candidate | Cost |
|---|---|---|
| **MPM / NSDF** (McLeod & Wyvill 2005 — 05 #8) | extracts pitch from **about two periods**, which is the property that lets live f0 fit the 20 ms hop of `live_singing`; named the default in the planned design note | — |
| **YIN / CMNDF** (de Cheveigné & Kawahara 2002 — 05 #9) | the six-step specification with published defaults and no upper frequency limit, which matters for the f0-range row to C6; the fallback | ≈ **6.2 % of one core** at 1024 lags *(prov.)* — `domainMap.md` §2.5, hand-written, never measured on target |
| **dywapitchtrack** (Larson & Maddox 2005 — 05 #13; 06 #17) | MIT, < 0.05 semitone, < 23 ms, already proven on ESP32-S3 | — |

Every one of those numbers is a research estimate. The lag range implied by the validation plan is **65 Hz (C2) to 1046 Hz (C6)** — at 32 kHz that is lags ≈ 31 … 492 samples — and the planned note also owes parabolic peak interpolation, the voicing decision and an octave-error guard ([`../../dsp/design/README.md`](../../dsp/design/README.md), `pitch-mpm-yin.md`). dywapitchtrack additionally hard-codes 44 100 Hz and would have to be adapted to 32/48 kHz.

Two structural facts constrain the choice more than the cycle counts do: the RCA − RPA gap in the validation table **is** the octave-error rate and exists specifically to expose YIN's known failure mode; and pYIN's HMM smoothing (05 #10) is exactly what a frame-independent on-device estimator lacks, which is why the host runs it and the gap between the two is itself a reportable number.

**The f0 estimator choice has its own ADR number since 2026-08-21: [ADR 0020](../adr/README.md), allocated in the backlog** rather than folded into ADR 0006, because an estimator with its own accuracy claim is a separate reviewable decision (§12 OQ9, routed). Until it is written, the planned design note `dsp/design/pitch-mpm-yin.md` is where the argument lives.

## 10. Band energy / FHE / SPR, and the log approximation

**Band readouts are not this document's to define.** [ADR 0008](../adr/README.md) (backlog) owns them: Omori peak-to-peak SPR (greatest harmonic peak 2–4 kHz minus greatest peak 0–2 kHz) and Müller's formant-cluster FHE as the primary readout, with fixed ring (2.5–3.5 kHz) and twang (3.5–5 kHz) bands appearing **only as overlays**. The preset's `overlays` array names *which* readout is drawn and deliberately never where its edges are ([ADR 0010](../adr/0010-preset-schema.md) alternatives). All values are **relative, within-subject, within-session**, and are reported both uncorrected and post-EQ — every shipped preset has `mic_eq: {"mode": "none"}`, the mic's HF rise sits inside the twang band, and no EQ has been fitted until [experiment 0001](../validation/experiments/0001-pdm-mic-in-situ-characterization.md) runs.

**The log approximation.** `10·log10(·)` on every bin of every frame is the one arithmetic stage that can actually cost more than the FFT: `log10f` is ≈ 150 cycles/call, which at 2048 bins × 50 frames/s is **6–8 % of one core** against **0.7 %** for a float-exponent bit-trick log *(both (prov.)*, `domainMap.md` §2.5*)*. Two levers exist; one is now decided, the other is not:

1. **Which approximation, and what is its maximum error?** [ADR 0009](../adr/0009-golden-file-strategy.md) already names this as "a design parameter rather than an accident", and the parameter had no value until 2026-08-21. It is bounded from above by the tolerance table: the `spectral_core` vs `numpy.fft.rfft` row allows `atol = 0.01 dB` for bins ≥ −80 dBFS, so either the approximation's worst-case error fits inside 0.01 dB, or the dB conversion is excluded from that comparison and compared on its own row. **Decided since: [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md) D9** took the second route — the dB stage gets its own tolerance row, `≤ 0.005 dB (prov.)`, exhaustively verified on the host, and M0 ships exact `log10f` (§12 OQ7, closed). The row itself is still owed to [`golden-files.md`](../validation/golden-files.md).
2. **How many bins get converted?** Converting only the ≈ 240 rendered columns instead of all `N/2 + 1` bins is the cheaper option, but it couples the DSP stage to the display's frequency mapping (log vs linear axis, `freq_min_hz`/`freq_max_hz`), which is ADR 0007's territory, and it changes what a *take* records. **OQ10.**

## 11. Cycle budget per preset, and how it stops being an estimate

Everything in this column is `(prov.)`. The preset-schema figures are the domain-map feasibility estimates (real N at the stated frame rate, +40 % for window, bit-reversal, `cplx2real`, magnitude and fast-log); "derived" marks a figure scaled from a published rate rather than quoted.

The esp-dsp column is a least-squares fit of `a·N_c·log2 N_c` to the **`ESP32S3` / `O2`** column of the published benchmark table ([02 #21](../bibliography/02-application-notes.md), `docs/en/esp-dsp-benchmarks.rst`, esp-dsp 1.8.2 — five `dsps_fft2r_fc32` points at 64/128/256/512/1024 complex points, three `dsps_fft4r_fc32` points at 64/256/1024), evaluated at 240 MHz. The fit gives **a = 9.588** cycles (fft2r) and **a = 6.304** (fft4r); an earlier revision of this table quoted the **`ESP32` (LX6)** column by mistake (a = 11.09), which is where its 253 k / 542 k figures came from. [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md) **D6** chose `fft2r` for every size in v1, so the fft2r row is the design number and fft4r is shown only as the rejected alternative.

| Preset | N | `N_c` | frames/s | CPU, one core *(prov.)* | esp-dsp `fft2r` extrapolation, ESP32S3/O2 *(prov.)* |
|---|---:|---:|---:|---:|---|
| `diction_consonants` | 1024 | 512 | 100 | ≈ 2.6 % | ≈ 44 k cycles/frame ≈ 0.18 ms ⇒ ≈ 1.8 % at 100 fps |
| `live_singing` | 4096 | 2048 | 50 | ≈ 6.2 % | ≈ 253 k cycles/frame ≈ **1.05 ms** ⇒ ≈ 5.3 % at 50 fps for the transform path alone; §5(b) budgets the same 1.05 ms, and the ≈ 6.2 % column adds the window multiply, magnitude and log |
| `sustained_pitch_lab` | 8192 | 4096 | 25 | ≈ 4.5 % | ≈ 471 k cycles/frame ≈ 1.96 ms ⇒ ≈ 4.9 % at 25 fps (fft4r would be ≈ 310 k ≈ 1.29 ms, ≈ 3.2 % — not taken, D6) |
| `vowel_formant_study` | 8192 | 4096 | 25 | ≈ 4.5 % (derived) | same |
| `room_noise_floor` | 8192 | 4096 | 25 | ≈ 4.5 % (derived) | same |

Four reasons none of these may be quoted as a result. The fit is an **extrapolation past the last data point** — the largest published transform is `N_c` = 1024, so the 2048 and 4096 rows are outside the measured range, and the fit's own residuals against the published points run to ≈ 7 % at the small end. The published benchmark **stops at 1024 complex points and has no row at all for `dsps_bit_rev*`, `dsps_cplx2real_fc32` or any `dsps_wind_*`** — i.e. it covers none of the three stages our real path adds (roadmap **Q21**). Every published cycle count is for **IRAM-resident** code: esp-dsp's `test/linker.lf` maps the whole library into `noflash`, while a normal application runs it from flash through the cache. And the extrapolation carries no window multiply, no magnitude, no dB stage and no cache pressure from a concurrently rendering core 0.

The measurement that replaces them is already specified: `dsp_get_cpu_cycle_count()` inside `dsp_ENTER_CRITICAL`/`dsp_EXIT_CRITICAL` around each stage, on target, with `CONFIG_DSP_OPTIMIZED` both `y` and `n`, trended in CI through pytest-embedded's `log_performance()` / `check_performance()` (roadmap **H13**; [validation README](../validation/README.md) "Analysis-to-GPIO latency"; 06 #53). The deadline it is measured against is the *Analysis-to-GPIO latency* row — `≤ preset window + 10 ms` — which is the DSP half of the research question's ≤ 80 ms acoustic-to-photon bound. `-Wdouble-promotion` clean is part of the same check: an accidental `double` in the hot loop is a 5–11× slowdown and is [pitfall G15](../devenv/pitfalls.md).

## 12. Open questions

Nothing below is decided in this note. Each row names where the decision belongs.

| # | Question | Routed to |
|---|---|---|
| ~~OQ1~~ | **Closed 2026-08-21 — [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md) D1.** Cosine sum from the preset's `coefficients`; window table checksummed into the golden manifest (schema minor bump when the generator lands). Generating `N+1` and dropping the last sample is **mathematically identical** (measured: `max \|Δ\| = 0` for all six sets — the symmetric length-`N+1` form divides by `N`) and is rejected on cost and clarity, not on numbers. The 0.0163 measurement argues the *separate* point that windows must come from coefficients rather than SciPy **names**, since preset `nuttall` has none. *(was: Periodic window: generate `len+1` and drop the last sample, or compute the cosine sum in `spectral_core` from)* | ADR 0006 D1 |
| ~~OQ2~~ | **Closed — ADR 0006 D6.** `CONFIG_DSP_MAX_FFT_SIZE` stays 4096: it bounds `N_c`, not `N_real`. Correction still owed to `xiao-edge-audio_notes.md` §3. *(was: Raise `CONFIG_DSP_MAX_FFT_SIZE` above 4096 for margin, or accept the exact fit and correct [`xiao-edge-audio_n)* | ADR 0006 D6 |
| ~~OQ3~~ | **Closed — ADR 0006 D6.** `fft2r` for every size in v1; the default real-4096 (`N_c` = 2048) is not a power of four and could never use radix-4. Revisit on an H13 cycle count. *(was: Does the backend carry both radix kernels, and is it worth re-picking preset sizes so the default analysis siz)* | ADR 0006 D6 |
| ~~OQ4~~ | **Closed — ADR 0006 D5, on source evidence.** Our own `cplx2real`: esp-dsp's refuses to run unless `dsps_fft4r_initialized` (its first statement) even though it takes a `table` argument, forcing a 64 KB table that `CONFIG_SPIRAM_MALLOC_ALWAYSINTERNAL=16384` then sends to PSRAM; and it computes every output bin through a `double` `0.5` literal. Ours is `4·(N_c+2)` B, float-only. *(was: Own `cplx2real` half-bin twiddles (≈ 16 KB) or esp-dsp's `dsps_fft4r_init_fc32` table (64 KB, PSRAM by default)* | ADR 0006 D5 |
| OQ5 | *(Half closed by [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md) D5: with our own `cplx2real` the table cost is ≈ 6 / 20 / 40 KB at real-2048 / 4096 / 8192 (including the fft2r bit-reversal RAM copy, which esp-dsp allocates unconditionally), i.e. a **≈ 104 KB** working set at real-8192 against **≈ 160 KB** on esp-dsp's tables, so the 112 KB estimate is superseded rather than reconciled. What remains is the **measurement**.)* Reconcile the 112 KB research estimate with the ≈ 160 KB / ≈ 104 KB itemisation, and correct the `10·N` rule of thumb. (§4.1) | roadmap **H13** measurement; ADR 0006 |
| OQ6 | Which decimating filter (biquad cascade vs `dsps_fird_f32`), and what is the inter-stage group-delay alignment rule? (§8) | `dsp/design/decimation-cascade.md` ([`../../dsp/design/README.md`](../../dsp/design/README.md)) |
| ~~OQ7~~ | **Closed — ADR 0006 D9.** Own tolerance row, `≤ 0.005 dB (prov.)`, exhaustive host verification; M0 ships exact `log10f`. *(was: The fast-log approximation and its **maximum error**, against the 0.01 dB tolerance row. (§10))* | ADR 0006 D9 |
| ~~OQ8~~ | **Closed — ADR 0006 D8.** Linear power, never dB. *(was: Are smoothing, averaging and hold applied in linear power or in dB? Neither the preset schema (§8, "does not r)* | ADR 0006 D8 |
| ~~OQ9~~ | **Routed 2026-08-21 — [ADR 0020 allocated](../adr/README.md)** in the backlog, not folded into 0006: an estimator with its own accuracy claim is a separate reviewable decision. *(was: **No ADR number is allocated for the f0 estimator choice** (MPM vs YIN vs dywapitchtrack, lag range, voicing,)* | ADR 0020 |
| OQ10 | Convert all `N/2 + 1` bins to dB, or only the ≈ 240 rendered columns? Couples the DSP stage to the display mapping and to what a take records. (§10) | ADR 0006 ↔ ADR 0007 |
| ~~OQ11~~ | **Closed 2026-08-21.** [`sdkconfig.defaults.esp32s3`](../../firmware/twatch-s3/sdkconfig.defaults.esp32s3)'s PSRAM comment said FFT scratch goes to PSRAM, contradicting tenet 3 and [ADR 0018](../adr/0018-first-reference-project-study.md). Corrected, and the comment now explains why the 16384-byte `SPIRAM_MALLOC_ALWAYSINTERNAL` threshold is what keeps the fft2r twiddle table internal. (§5) | done |
| ~~OQ12~~ | **Closed — ADR 0006.** `spectral_config_t.hop`'s "`N/2` = 50 %" comment is wrong for every shipped preset (69–94 % overlap); corrected in `spectral.h` in the ADR 0006 commit. *(was: `spectral_config_t.hop`'s doc comment says `N/2 = 50 %`; no shipped preset uses it (69–94 % overlap). Correcti)* | ADR 0006 |
| ~~OQ13~~ | **Deferred by name — ADR 0006 D9.** Gaussian window needs the T7b Praat-comparability result first. *(was: Add a Gaussian window (Praat's convention) and/or a genuinely wideband preset (N ≈ 128–256)? Both were routed)* | ADR 0006 D9 / Q34 |

Thresholds that would rewrite parts of this note if they fire: **T2** (mic not acoustically capable ⇒ host-first pivot, every timbre metric leaves the watch), **T3** (48 kHz fails ⇒ the schema's reserved rate is removed), **T4** (scroll axis fails ⇒ 30 Hz for all presets, which changes every frames/s column in §11). See [`../roadmap/documentation-roadmap.md`](../roadmap/documentation-roadmap.md) §4.

## 13. Where this lives in the tree

| Piece | Home |
|---|---|
| Windowing, S1/S2, dB, smoothing/hold, peak picking, f0 front end | [`spectral_core`](../../firmware/twatch-s3/components/spectral_core/README.md) — pure C99, host-buildable |
| esp-dsp call sequence, aligned internal buffers, one init/deinit | [`spectral_fft_backend`](../../firmware/twatch-s3/components/spectral_fft_backend/README.md) |
| Host reference transform | `spectral_core/src/fft_ref.c` (planned, E1) |
| DC blocker, `int16 → float`, clipping flag, ring | [`audio_source`](../../firmware/twatch-s3/components/audio_source/README.md) |
| The maths prose each block must agree with | [`../../dsp/design/`](../../dsp/design/README.md) — `fft-normalization.md`, `decimation-cascade.md`, `pitch-mpm-yin.md`, `band-energy-and-fhe.md`, `mic-eq.md` (all planned) |
| N, window, ENBW, hop, smoothing, hold per preset | [`../../protocols/specs/preset-schema.md`](../../protocols/specs/preset-schema.md) + [`../../protocols/presets/`](../../protocols/presets/README.md) |
| Tolerances every comparison is asserted against | [`../validation/golden-files.md`](../validation/golden-files.md) |
| Bins → pixels | ADR 0007 / [ADR 0011](../adr/0011-spectrogram-colormap.md); planned `04-display-render-path.md` |

## 14. Background reading

Spectral estimation and the window tables: Heinzel, Rüdiger & Schilling 2002, Harris 1978, Nuttall 1981, Welch 1967, Koenig, Dunn & Lacy 1946 in [`../bibliography/05-papers.md`](../bibliography/05-papers.md); Smith, *SASP* (real-FFT packing, quadratic peak interpolation) in [`../bibliography/04-books.md`](../bibliography/04-books.md). Pitch: McLeod & Wyvill 2005, de Cheveigné & Kawahara 2002, Mauch & Dixon 2014, Larson & Maddox 2005, same file. Library and platform truth: [`../bibliography/06-reference-projects.md`](../bibliography/06-reference-projects.md) (#1 esp-dsp, #3 xiao-edge-audio, #17 dywapitchtrack, #23 the PSRAM bandwidth matrix, #28 kissfft, #32 Friture, #53 pytest-embedded) and [`../bibliography/02-application-notes.md`](../bibliography/02-application-notes.md) (#20 API reference, #21 benchmarks). Prior art for the preset model and the decimation cascade: [`../bibliography/07-technical-reports.md`](../bibliography/07-technical-reports.md) #9 (Spectroid, still an unretrieved primary source) and #12 (Friture).

Reference basis: [ADR 0003](../adr/0003-microphone-path.md) (capture format, software DC removal, linear-only conditioning), [ADR 0009](../adr/0009-golden-file-strategy.md) (tolerance-table comparison, the fast-log error as a design parameter), [ADR 0010](../adr/0010-preset-schema.md) (N, window constants, ENBW, hop vs refresh, the SRAM envelope in the schema), [ADR 0013](../adr/0013-native-linux-simulator-target.md) (the `audio_source` / host lanes the `fft_ref` seam serves), [ADR 0018](../adr/0018-first-reference-project-study.md) (esp-dsp supplies a specification, not code) and **[ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md)** (`proposed` 2026-08-21), which owns every convention §3 lists as owed and closed OQ1–OQ4, OQ7, OQ8, OQ11–OQ13; the [preset schema](../../protocols/specs/preset-schema.md) and the six committed instances for every per-preset number; [`esp-dsp_notes.md`](../reference-projects/notes/esp-dsp_notes.md) §2–§9, §12–§13 (the API sequence, the byte-exact memory itemisation, the alignment and PSRAM traps, the symmetric-window defect, the `CONFIG_DSP_MAX_FFT_SIZE` correction) and [`xiao-edge-audio_notes.md`](../reference-projects/notes/xiao-edge-audio_notes.md) §2.3/§3 (the claim it corrects); [`spectral.h`](../../firmware/twatch-s3/components/spectral_core/include/spectral_core/spectral.h) and [`sdkconfig.defaults.esp32s3`](../../firmware/twatch-s3/sdkconfig.defaults.esp32s3) as committed artefacts; [`golden-files.md`](../validation/golden-files.md) (the 0.01 dB and 1e-4 rows) and [`../validation/README.md`](../validation/README.md) (analysis-to-GPIO latency, displayed spectral dynamic range, energy per preset); roadmap **Q21, Q25, Q34, H13** and thresholds **T2, T3, T4** in [`../roadmap/documentation-roadmap.md`](../roadmap/documentation-roadmap.md); bibliography addresses 02 #20/#21, 04 #1, 05 #1/#2/#3/#5/#6/#8/#9/#10/#13, 06 #1/#3/#17/#23/#28/#32/#53, 07 #9/#12. DSP-envelope figures (cycle percentages, the `10·N` memory rule, the PSRAM bandwidth matrix) come from the gitignored research working notes `scratch/research/domainMap.md` §2 and are **(prov.)** research estimates until Phase 1 measures them on this unit.
