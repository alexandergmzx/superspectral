# esp-dsp — study notes (D4 reference-project loop)

- **Project:** `espressif/esp-dsp` — "the official DSP library for Espressif SoCs" ([bibliography 06 #1](../../bibliography/06-reference-projects.md)). This is the library our `spectral_fft_backend` is built on; the pin is `espressif/esp-dsp: "~1.8.2"` in [`firmware/twatch-s3/main/idf_component.yml`](../../../firmware/twatch-s3/main/idf_component.yml).
- **Studied commit:** `3c8ac0fdfec83740b783e200862c8d0c056de0ad` (master, 2026-05-12, "Merge branch 'bugfix/dp_int8' into 'master'"). The shallow clone carries no tags, but this commit's `CHANGELOG.md` opens with `## [1.8.2] 2026-05-11 — Fixed: Row dot product calculation for int8`, and the merged branch is that fix, so `3c8ac0f` **is** the v1.8.2 content. `idf_component.yml` has no `version:` key (the release procedure in `CONTRIBUTING.md` adds it on the release branch). Clone: `docs/reference-projects/clones/esp-dsp/` (gitignored).
- **Licence:** **Apache-2.0**, confirmed from `LICENSE` (the plain, unfilled Apache-2.0 text). Copyright is asserted per file — `// Copyright 2018-2019 Espressif Systems (Shanghai) PTE LTD` on the older files, `SPDX-FileCopyrightText: <year> Espressif Systems (Shanghai) CO LTD` + `SPDX-License-Identifier: Apache-2.0` on files added from 2022 on. **There is no `NOTICE` file**, so Apache-2.0 §4(d) imposes nothing beyond §4(a)–(c); our own `NOTICE` row is the attribution. Apache-2.0-compatible with the firmware link line ([ADR 0004](../../adr/0004-split-licensing.md)).
- **Studied:** 2026-08-21, against ESP-IDF v6.0.2 (`~/esp/idf/v6.0.2`, the pinned tree — [ADR 0001](../../adr/0001-toolchain-esp-idf-v6-pinned-environment.md)) and this unit's measured hardware facts ([`docs/hw/README.md`](../../hw/README.md): ESP32-S3 rev v0.2, 240 MHz, 40 MHz crystal, 8 MB octal PSRAM). Claims marked *(verified)* were reproduced by compiling esp-dsp's own ANSI sources standalone on the host; claims marked *(prov.)* are extrapolations from the published benchmark table.
- **Feeds:** [ADR 0006](../../adr/README.md) (FFT normalisation and window conventions), component [`spectral_fft_backend`](../../../firmware/twatch-s3/components/spectral_fft_backend/README.md), the backend-agreement test in [`docs/validation/golden-files.md`](../../validation/golden-files.md), and the upstream-issue action already promised in [ADR 0017](../../adr/0017-no-radio-in-v1-trimmed-component-set.md).

## 1. Scope of this study

Read in full: `modules/fft/` (float + fixed), `modules/windows/`, `modules/iir/`, `modules/support/{snr,mem,misc}`, `modules/common/`, `Kconfig`, `CMakeLists.txt`, `docs/en/esp-dsp-benchmarks.rst`, `test/`, `test_app/`, `examples/{fft,fft4real,fft_window}`, `applications/spectrum_box_lite`. Not read: `modules/{dotprod,matrix,conv,dct,kalman}` beyond their build entries, the P4/S31 (`_arp4`) assembly.

## 2. `modules/fft` — what actually exists

### 2.1 The three families, and the one that does not exist

| Family | Files | Data type | Length constraint | S3 dispatch |
|---|---|---|---|---|
| **fft2r** — complex radix-2 | `float/dsps_fft2r_fc32_{ansi.c,ae32_.S,aes3_.S}` | `fc32` (interleaved `float` re/im) | any power of two ≤ `CONFIG_DSP_MAX_FFT_SIZE` | `dsps_fft2r_fc32` → `dsps_fft2r_fc32_aes3` |
| **fft2r sc16** — complex radix-2 fixed point | `fixed/dsps_fft2r_sc16_{ansi.c,ae32.S,aes3.S}` | `sc16` (interleaved Q15 re/im) | same | `dsps_fft2r_sc16` → `dsps_fft2r_sc16_aes3` |
| **fft4r** — complex radix-4 | `float/dsps_fft4r_fc32_{ansi.c,ae32_.S,aes3_.S}` | `fc32` only | **N = 4^k only** — `if ((log2N & 0x01) != 0) return ESP_ERR_DSP_INVALID_LENGTH;` in `dsps_fft4r_fc32_ansi_` | `dsps_fft4r_fc32` → `dsps_fft4r_fc32_aes3` |
| ~~**fft4real**~~ | — | — | — | **does not exist as an API** |

**`fft4real` is an example directory, not a function.** `examples/fft4real/` composes `fft2r`/`fft4r` + bit-reverse + `dsps_cplx2real_fc32` to do a real-input FFT. There is no `dsps_fft4real_*` symbol anywhere in the tree. Correction owed to [bibliography 06 #1](../../bibliography/06-reference-projects.md) ("`dsps_fft2r/fft4r/fft4real`"), to the `main/idf_component.yml` comment, and to the [`spectral_fft_backend` README](../../../firmware/twatch-s3/components/spectral_fft_backend/README.md) ("the `fft4real` path").

Also declared-but-never-defined (link error if called): `dsps_cplx2real256_fc32_ansi`, `dsps_snr_fc32`, and the whole radix-4 fixed-point surface — `dsps_fft4r_sc16` (the `#define` in `dsps_fft4r.h` resolves to `dsps_fft4r_sc16_ae32` / `_ansi`, neither of which exists), plus `dsps_fft4r_w_table_sc16`, `dsps_fft4r_w_table_sc16_size`, `dsps_fft4r_sc16_initialized`. **There is no radix-4 fixed-point FFT.**

### 2.2 Init and twiddle-table allocation

Both inits take an optional caller buffer and are **global, one-shot, and silently idempotent**:

```c
esp_err_t dsps_fft2r_init_fc32(float *fft_table_buff, int table_size);   /* table_size = N_complex     */
esp_err_t dsps_fft4r_init_fc32(float *fft_table_buff, int max_fft_size); /* max_fft_size = N_complex   */
```

| Behaviour | fft2r (`dsps_fft2r_fc32_ansi.c`) | fft4r (`dsps_fft4r_fc32_ansi.c`) |
|---|---|---|
| Already initialised | `if (dsps_fft2r_initialized != 0) return ESP_OK;` — **a second init with a different size is silently ignored and returns success** | same (`dsps_fft4r_initialized`) |
| Range check | `table_size > CONFIG_DSP_MAX_FFT_SIZE` → `ESP_ERR_DSP_PARAM_OUTOFRANGE` (applies even to a caller-supplied buffer) | same |
| Bytes written into the table | `table_size × 4` (`dsps_gen_w_r2_fc32` fills `table_size>>1` cos/sin pairs) | **`max_fft_size × 16`** — the buffer is `4 × max_fft_size` floats, four times what the parameter name suggests. The doxygen says only "pointer to floating point buffer"; **passing `max_fft_size` floats overflows by 4×** |
| Internal allocation | S3: `table_size ≤ 1024` → ROM table (below); else `memalign(16, 4 × table_size)`. Non-S3: `malloc` | always `malloc(16 × max_fft_size)` — **no `memalign`, no alignment guarantee** |
| NULL check on the allocation | yes | yes |
| Extra allocation | copies the const bit-reversal table into RAM: `malloc(4 × dsps_fft2r_rev_tables_fc32_size[log2(N)−4])`, then **overwrites the global `dsps_fft2r_rev_tables_fc32[log2(N)−4]`** to point at the copy. Only for `16 ≤ table_size ≤ 4096` | same, `dsps_fft4r_rev_tables_fc32[(log2(N)>>1)−2]`, only for `16 ≤ max ≤ 4096` |
| Post-init transform | `dsps_gen_w_r2_fc32` then `dsps_bit_rev_fc32_ansi(w, table_size>>1)` — the table is stored **bit-reversed** | plain `cosf/sinf` sweep over `2×max_fft_size` angles, **not** bit-reversed |
| Leak on a late error | if `dsps_gen_w_r2_fc32` fails after the bit-rev table was malloc'd, init returns without freeing and leaves `initialized = 0` — the next call re-mallocs | same shape |

**A table generated for M works for any FFT of N ≤ M; a table smaller than N is a silent buffer over-read and wrong output.** *(verified: esp-dsp's ANSI `dsps_gen_w_r2_fc32` + `dsps_bit_rev_fc32_ansi` + `dsps_fft2r_fc32_ansi_` compiled standalone; N = 1024 with M ∈ {1024, 2048, 4096} all put the tone at bin 7 with |X| = 512 and peak/total = 0.5, while M = 512 moves the peak to bin 1017 and M = 256 to bin 519, with no error returned.)* This is why every esp-dsp example calls `dsps_fft2r_init_fc32(NULL, CONFIG_DSP_MAX_FFT_SIZE)` and why we must do the same: **initialise once, at boot, with the maximum**, because any later library call (`dsps_snr_f32` does exactly this) will otherwise be capped by whatever size we registered first.

### 2.3 The ESP32-S3 ROM-table special case

```c
#ifdef CONFIG_IDF_TARGET_ESP32S3
extern float *dsps_fft2r_w_table_fc32_1024;
#endif
...
#if CONFIG_IDF_TARGET_ESP32S3
    if (table_size <= 1024) {
        dsps_fft_w_table_fc32 = dsps_fft2r_w_table_fc32_1024;
    } else {
        dsps_fft_w_table_fc32 = (float *)memalign(16, sizeof(float) * table_size);
    }
#endif
```

- The symbol is resolved by the **ROM linker script**, not by esp-dsp: `dsps_fft2r_w_table_fc32_1024 = 0x3fcefff8;` under `Group esp-dsp` in `components/esp_rom/esp32s3/ld/esp32s3.rom.ld` (ESP-IDF v6.0.2). It is a *data* symbol — a 4-byte pointer variable in the ROM's DRAM data area (`SOC_DRAM_HIGH = 0x3FD00000`; the app's `dram0_0_seg` is documented in `esp_system/ld/esp32s3/memory.ld.in` as "shared data RAM, **excluding** memory reserved for ROM bss/data/stack"), so the declaration as `float *` is type-correct and the region it points at is RAM the application never allocates.
- Consequence: for `N_complex ≤ 1024` on the S3 the twiddle table costs **zero heap**. For `N_complex > 1024` it is a `memalign(16, …)` on the ordinary heap.
- `dsps_fft2r_init_fc32` still *regenerates* the table into that memory (`dsps_gen_w_r2_fc32` + `dsps_bit_rev_fc32_ansi`); it is a scratch buffer, not a read-only constant. It is therefore **not safe to assume the ROM contents survive** — and two components that both init at ≤ 1024 share the same physical buffer.
- `dsps_fft2r_deinit_fc32` guards the free with `if (dsps_fft_w_table_fc32 != dsps_fft2r_w_table_fc32_1024)`, so the ROM buffer is never passed to `free()`. Correct, but it means `dsps_fft2r_mem_allocated` is set to 1 for an allocation that never happened.
- There is **no equivalent for fft4r and none for sc16** — those always allocate.

### 2.4 Bit-reversal

| Symbol | What it is | Notes |
|---|---|---|
| `dsps_bit_rev_fc32` | `#define`d to `dsps_bit_rev_fc32_ansi` in **both** branches of `dsps_fft2r.h` | the generic swap loop; **there is no optimised version** — do not use it in the hot path |
| `dsps_bit_rev2r_fc32(data, N)` | table-driven radix-2 reorder | lookup tables for N ∈ {16 … 4096}; **any other N falls through to `dsps_bit_rev_fc32`**. Dispatches to `dsps_bit_rev_lookup_fc32` → `_aes3` on the S3 |
| `dsps_bit_rev4r_fc32(data, N)` | table-driven radix-4 reorder | tables for N ∈ {16, 64, 256, 1024, 4096}; otherwise `dsps_bit_rev4r_direct_fc32_ansi` |
| `dsps_bit_rev_lookup_fc32_{ansi,ae32,aes3}` | the swap engine | table entries are `uint16_t` byte offsets, used as `>> 2`; the aes3 file uses only `lsx`/`ssx`, no PIE |

The RAM copy made by init exists so the swap engine reads the table from DRAM rather than from flash-mapped `.rodata`. Cost at `N_complex = 4096`: 8 064 B for fft2r, 8 064 B for fft4r.

Fragility worth knowing: `dsps_fft4r.h` ends with `#define dsps_bit_rev4r_fc32 dsps_bit_rev4r_fc32_ae32` under `CONFIG_DSP_OPTIMIZED`, and `dsps_bit_rev4r_fc32_ae32` **is not implemented anywhere**. It links only because the *definition* in `dsps_fft4r_fc32_ansi.c` also passes through the header and is renamed by the same macro. Any translation unit that declares the prototype itself gets an undefined reference.

### 2.5 `cplx2real` vs `cplx2reC` — two different tricks

| Function | Header | Purpose | Requires |
|---|---|---|---|
| `dsps_cplx2real_fc32(data, N)` | `dsps_fft4r.h` | **one real signal of 2N samples** → its spectrum, from an N-point complex FFT | `dsps_fft4r_init_fc32()` — returns `ESP_ERR_DSP_UNINITIALIZED` otherwise, **even when the FFT itself was radix-2** |
| `dsps_cplx2reC_fc32(data, N)` | `dsps_fft2r.h` | **two real signals of N samples each** (one in re, one in im) → two spectra of N/2 bins, side by side | only `dsps_fft2r_init_fc32()`; `#define`d to `_ansi` on every target |
| `dsps_cplx2reC_sc16`, `dsps_cplx2real_sc16_ansi` | `dsps_fft2r.h` | Q15 counterparts | `dsps_fft2r_init_sc16()` |

`dsps_cplx2real_fc32` is a macro that resolves to **`dsps_cplx2real_fc32_ae32`** on the S3 (`dsps_cplx2real_fc32_ae32_enabled` is set for any Xtensa core with FP + zero-overhead loops). There is no `_aes3` variant — the S3 runs the ESP32 scalar-FPU assembly.

**Output packing of `dsps_cplx2real_fc32(data, N_c)` for `N_real = 2·N_c` real input samples** *(verified against a naive DFT: `N_real = 64`, `x[n] = cos(2π·5n/64) + 0.5·cos(2π·13n/64 + 0.7) + 0.25`)*:

| Slot | Holds | Value in the test |
|---|---|---|
| `slot[0].re` | `X[0]` (DC, real) | 16.0000 = 0.25 × 64 ✔ |
| `slot[0].im` | `X[N_c]` = `X[N_real/2]` (Nyquist, real) — **packed into bin 0's imaginary part** | 0.0000 ✔ |
| `slot[k]`, `1 ≤ k ≤ N_c−1` | `X[k]`, complex | \|slot[5]\| = 32.0000 = 1.0 × 64/2 ✔; \|slot[13]\| = 16.0000 = 0.5 × 64/2 ✔ |

So `N_real/2 + 1` unique bins live in `N_real/2` complex slots, in place, and the transform is the **unnormalised forward DFT**: `X[0] = N_real · mean`, and a real cosine of amplitude A at bin k gives `|X[k]| = A · N_real/2`. Two traps follow:

1. `sqrt(slot[0].re² + slot[0].im²)` is **not** the DC magnitude — it mixes DC and Nyquist. esp-dsp's own `examples/fft4real` computes exactly this wrong value for bin 0. Our `spectral_rfft_fn` must unpack slot 0 into two real bins and emit `N/2 + 1` bins, as its [contract](../../../firmware/twatch-s3/components/spectral_fft_backend/README.md) already says.
2. DC and Nyquist scale with `N`, every other bin with `N/2`. ADR 0006 has to state the one-sided ×2 factor as applying to bins `1 … N/2−1` only.

## 3. The exact API sequence for a real-input FFT on the ESP32-S3

Target: `N_real` real samples (power of two), Hann or Blackman–Harris window, `N_real/2 + 1` magnitude bins. `N_c = N_real/2`.

```c
#include "esp_dsp.h"          /* note: does NOT pull in dsps_mem.h */

/* ---- once, at boot, on the DSP task's core ------------------------------ */
/* Both inits are needed: fft2r (or fft4r) for the transform, fft4r for the
   twiddles that dsps_cplx2real_fc32() reads.  Always init with the maximum
   N_c the app will ever use -- a later, smaller init is silently ignored,
   and a table smaller than N is a silent over-read (see §2.2).             */
ESP_ERROR_CHECK(dsps_fft2r_init_fc32(fft2r_tbl, N_C_MAX));  /* 4*N_C_MAX bytes  */
ESP_ERROR_CHECK(dsps_fft4r_init_fc32(fft4r_tbl, N_C_MAX));  /* 16*N_C_MAX bytes */

/* Window, generated ONCE.  esp-dsp's dsps_wind_*_f32 are SYMMETRIC
   (1/(len-1)); ADR 0006 mandates periodic.  Generate len+1 and drop the
   last sample, or compute the cosine sum ourselves (§5).                   */
dsps_wind_hann_f32(win_tmp, N_REAL + 1);           /* then use win_tmp[0..N_REAL-1] */
/* or dsps_wind_blackman_harris_f32(win_tmp, N_REAL + 1); */

/* ---- per analysis frame ------------------------------------------------- */
/* 1. window in place into the work buffer.  No packing step is needed: the
      real array IS the complex array -- even samples become re, odd become
      im.  (dsps_mul_f32 can do this, or a plain loop.)                      */
for (int i = 0; i < N_REAL; i++) work[i] = pcm[i] * win[i];

/* 2. complex FFT of N_c points, in place.
      fft4r is ~1.5x faster but only accepts N_c = 4^k (64, 256, 1024, 4096),
      i.e. real 128 / 512 / 2048 / 8192.  Everything else uses fft2r.        */
#if (N_C == 64 || N_C == 256 || N_C == 1024 || N_C == 4096)
    ESP_ERROR_CHECK(dsps_fft4r_fc32(work, N_C));
    ESP_ERROR_CHECK(dsps_bit_rev4r_fc32(work, N_C));
#else
    ESP_ERROR_CHECK(dsps_fft2r_fc32(work, N_C));
    ESP_ERROR_CHECK(dsps_bit_rev2r_fc32(work, N_C));   /* NOT dsps_bit_rev_fc32 */
#endif

/* 3. unpack the real spectrum in place: N_c complex slots, slot0 = {DC, Nyq} */
ESP_ERROR_CHECK(dsps_cplx2real_fc32(work, N_C));

/* 4. magnitudes: N_REAL/2 + 1 bins, unnormalised                            */
mag[0]        = fabsf(work[0]);                     /* DC       = X[0]       */
mag[N_C]      = fabsf(work[1]);                     /* Nyquist  = X[N_c]     */
for (int k = 1; k < N_C; k++)
    mag[k] = sqrtf(work[2*k]*work[2*k] + work[2*k+1]*work[2*k+1]);
/* 5. S1/S2 normalisation, one-sided x2 on bins 1..N_C-1, dB -> ADR 0006,
      in spectral_core.  esp-dsp does none of it.                            */
```

Deviations from esp-dsp's own `examples/fft4real/main/dsps_fft4real_main.c` (which is otherwise the reference for this sequence): it calls `dsps_wind_hann_f32(wind, N)` (symmetric), it uses `dsps_bit_rev2r_fc32` for the radix-2 path and `dsps_bit_rev4r_fc32` for the radix-4 path but does not say why, it ignores every return code, and its dB loop `10·log10((re²+im²)/N)` normalises by `N` (not `N²`, not `S1²`) and treats slot 0 as an ordinary bin.

**Which radix for our presets** (`N_c = N_real/2`):

| Preset `N_real` | `N_c` | fft4r usable? | Path |
|---|---|:---:|---|
| 1024 | 512 | no (2⁹) | fft2r + `bit_rev2r` |
| 2048 | 1024 | **yes** (4⁵) | fft4r + `bit_rev4r`; fft2r twiddles come free from ROM |
| 4096 | 2048 | no (2¹¹) | fft2r + `bit_rev2r` |
| 8192 | 4096 | **yes** (4⁶) | fft4r + `bit_rev4r` |

So the roadmap's headline sizes fall on opposite sides of the radix-4 constraint. `real-4096` — the default analysis size — **cannot** use the radix-4 kernel.

## 4. Memory and alignment

### 4.1 Where the bytes go

`fc32` real-input pipeline, in place, everything in bytes:

| Item | Formula | real-2048 | real-4096 | real-8192 |
|---|---|---:|---:|---:|
| Work buffer (in place, = the windowed PCM) | `4·N_real` | 8 192 | 16 384 | 32 768 |
| Window table (full length) | `4·N_real` | 8 192 | 16 384 | 32 768 |
| fft2r twiddles | `4·N_c` | **0** (S3 ROM) | 8 192 | 16 384 |
| fft2r RAM bit-rev copy | `4·size[log2 N_c−4]` | 1 984 | 3 968 | 8 064 |
| fft4r twiddles (**needed by `cplx2real` even on the fft2r path**) | `16·N_c` | 16 384 | 32 768 | **65 536** |
| fft4r RAM bit-rev copy | `4·size4r` | 1 920 | 1 920 | 8 064 |
| **Total** | | **≈ 35.8 KB** | **≈ 77.8 KB** | **≈ 159.8 KB** |

The 112 KB figure for real-8192 quoted in the gitignored `scratch/research/PLAN.md` §2 and in [bibliography 02 #21](../../bibliography/02-application-notes.md) does not include the 64 KB radix-4 twiddle table. Two ways under it:

- **Write our own `cplx2real`.** It needs only `cos/sin(πk/N_c)` for `k = 0 … N_c/2`, i.e. `4·(N_c+2)` bytes (16 392 B at `N_c = 4096`) instead of 65 536, and it removes the `dsps_fft4r_init_fc32` dependency from the radix-2 path entirely. Total for real-8192 drops to **≈ 104 KB**. (The fft2r twiddle table cannot be reused: it holds `cos/sin(2πi/N_c)` and is stored bit-reversed; `cplx2real` wants half-bin angles in natural order.)
- Store the window at half length and mirror it, or evaluate the cosine sum per frame: another 16 KB at real-8192.

`CONFIG_DSP_MAX_FFT_SIZE` bounds `N_c`, **not** `N_real`. The Kconfig default `4096` is therefore exactly enough for a real-8192 FFT on the real path — the note in [`xiao-edge-audio_notes.md`](xiao-edge-audio_notes.md) §3 that "our real-8192 preset needs this raised" is only true for a complex FFT of 8192 zero-padded real samples, which we are not doing. **No `sdkconfig.defaults` change is needed.**

### 4.2 The PSRAM trap

esp-dsp's internal allocations are **not capability-aware**: `malloc()` for the fft4r table, `memalign()` for the fft2r table, `malloc()` for both bit-rev copies. On ESP-IDF, `memalign` → `heap_caps_aligned_alloc_default` and `malloc` → `heap_caps_malloc_default` (`components/esp_libc/src/heap.c`), and both send any request **strictly larger than `CONFIG_SPIRAM_MALLOC_ALWAYSINTERNAL`** to PSRAM first (`components/heap/heap_caps.c`). Our committed [`sdkconfig.defaults.esp32s3`](../../../firmware/twatch-s3/sdkconfig.defaults.esp32s3) sets `CONFIG_SPIRAM_USE_MALLOC=y` and `CONFIG_SPIRAM_MALLOC_ALWAYSINTERNAL=16384`, so:

| Allocation | Size | Lands in |
|---|---:|---|
| fft2r twiddles, `N_c = 4096` | 16 384 | internal (`≤` limit, by one byte) |
| fft2r/fft4r bit-rev copies | ≤ 8 064 | internal |
| **fft4r twiddles, `N_c = 2048`** | 32 768 | **PSRAM** |
| **fft4r twiddles, `N_c = 4096`** | 65 536 | **PSRAM** |

A twiddle table in PSRAM violates architecture tenet 3 ("FFT working buffers are internal") and costs on every butterfly. **Therefore `spectral_fft_backend` must always pass its own buffers** to `dsps_fft2r_init_fc32` / `dsps_fft4r_init_fc32`, allocated with `heap_caps_aligned_alloc(16, n, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT)` — never `NULL`. (Passing a buffer also skips the S3 ROM shortcut, which is a small loss at `N_c ≤ 1024` and irrelevant above it.)

The two bit-rev RAM copies are still made internally by esp-dsp and cannot be supplied; they are small and internal, so they are fine.

### 4.3 Alignment

| Path | Instructions used | Required alignment | Checked at runtime? |
|---|---|---|---|
| `dsps_fft2r_fc32_aes3_`, `dsps_fft4r_fc32_aes3_` | `ee.ldf.64.ip` / `ee.stf.64.ip` only | **8 bytes** (esp-dsp's own examples use 16) | **no** — a misaligned buffer is a `LoadStoreAlignment` panic, not an error code |
| `dsps_fft2r_sc16_aes3_` | `ee.vld.128.ip`, `ee.vst.128.ip`, `ee.cmul.s16`, `ee.vzip.32`, … | **16 bytes** | **no** |
| `dsps_bit_rev_lookup_fc32_aes3` | `lsx`/`ssx` (scalar FP indexed) | 4 bytes | n/a |
| `dsps_cplx2real_fc32_ae32_` | `lsi`/`ssi` (scalar FP) | 4 bytes | n/a |
| `dsps_fir_init_f32`, `dsps_fird_init_s16` | — | 16 bytes on S3 | **yes** — `ESP_ERR_DSP_ARRAY_NOT_ALIGNED` |
| `dsps_biquad_f32_*` | plain FPU (no PIE) | 4 bytes | n/a |

So the FFT is the one place where alignment matters and is *not* validated. Every buffer the backend hands to esp-dsp — work array, both twiddle tables, the window — gets `heap_caps_aligned_alloc(16, …)` or `__attribute__((aligned(16)))`, and a `_Static_assert`/`assert` on the pointer at init.

`dsps_memcpy_aes3` / `dsps_memset_aes3` (`modules/support/mem/esp32s3/`) are the exception: their headers document, and `modules/support/mem/test/` exercises, all four aligned/unaligned combinations. They are only reachable through `dsps_memcpy` / `dsps_memset`, which `esp_dsp.h` does **not** include — `#include "dsps_mem.h"` explicitly. On a non-optimized or non-S3 build the macros fall back to `memcpy`/`memset` without including `<string.h>`.

## 5. `modules/windows` — six windows, all symmetric

All six are `void dsps_wind_<name>_f32(float *window, int len)` and all six use `len_mult = 1/(float)(len − 1)` — **symmetric (DFT-even is what we need, and this is not it)**. Cosine-sum coefficients as committed, with the coherent gain and NENBW that follow from them *(computed from the source coefficients under the periodic convention; they match Harris 1978 and Heinzel 2002 to the digits shown)*:

| esp-dsp function | a0 | a1 | a2 | a3 | a4 | CG = a0 | CG (dB) | NENBW (bins) |
|---|---|---|---|---|---|---:|---:|---:|
| `dsps_wind_hann_f32` | 0.5 | 0.5 | — | — | — | 0.5000 | −6.02 | 1.5000 |
| `dsps_wind_blackman_f32` | 0.42 | 0.5 | 0.08 | — | — | 0.4200 | −7.54 | 1.7268 |
| `dsps_wind_blackman_harris_f32` | 0.35875 | 0.48829 | 0.14128 | 0.01168 | — | 0.3588 | −8.90 | 2.0044 |
| `dsps_wind_blackman_nuttall_f32` | 0.3635819 | 0.4891775 | 0.1365995 | 0.0106411 | — | 0.3636 | −8.79 | 1.9761 |
| `dsps_wind_nuttall_f32` | 0.355768 | 0.487396 | 0.144232 | 0.012604 | — | 0.3558 | −8.98 | 2.0212 |
| `dsps_wind_flat_top_f32` | 0.21557895 | 0.41663158 | 0.277263158 | 0.083578947 | 0.006947368 | 0.2156 | −13.33 | 3.7702 |

Notes for ADR 0006:

- The Blackman–Harris set is the standard 4-term −92 dB one and the Nuttall set is Nuttall 1981's minimum-4-term-with-continuous-first-derivative — i.e. **esp-dsp already agrees with SciPy/Praat coefficient-for-coefficient**, which is what [bibliography 05 #3](../../bibliography/05-papers.md) asks us to pin. The *only* discrepancy against a periodic reference is the `1/(len−1)` denominator.
- Two ways to get the periodic window: call the esp-dsp function with `len + 1` and use the first `len` samples, or compute the sum ourselves. Either way the table is checksummed into the golden-file manifest ([`docs/validation/golden-files.md`](../../validation/golden-files.md)).
- Every one of the six evaluates `i * 2 * M_PI * len_mult` where `M_PI` is a `double` — a soft-float double multiply per sample per term on a single-precision FPU. Irrelevant at init time, fatal if a window were ever regenerated per frame; it is also exactly what our `-Wdouble-promotion` CI flag exists to catch, and it is one reason to generate the window ourselves.
- There is **no `dsps_wind_*_s16`**: a Q15 window has to be built by hand (`applications/spectrum_box_lite/main/main.c` does `(int16_t)(w[i] * 32767)`).

## 6. `modules/iir` — biquads

- **Runtime**: `dsps_biquad_f32(input, output, len, coef, w)` — transposed direct-form II, `coef[5] = {b0, b1, b2, a1, a2}` with `a0 ≡ 1` and the RBJ sign convention (`d0 = x − a1·w0 − a2·w1`), `w[2]` state. A stereo variant `dsps_biquad_sf32` interleaves L/R with `w[4]`.
- **Dispatch defect on the S3.** `dsps_biquad.h` tests `dsps_biquad_f32_ae32_enabled` **before** `dsps_biquad_f32_aes3_enabled`, and `dsps_biquad_platform.h` sets `_ae32_enabled = 1` for any Xtensa core with FP + loops — which includes the LX7. So on the ESP32-S3 `dsps_biquad_f32` always resolves to `dsps_biquad_f32_ae32` and `dsps_biquad_f32_aes3.S` is dead code. The published benchmark corroborates it: 1024 samples costs **17 552** cycles on the S3 versus **17 442** on the ESP32 — the S3 is marginally *slower*, which cannot happen if a PIE kernel were running. (The same `#elif` ordering appears in `dsps_fft4r.h`, where it is harmless only because `dsps_fft4r_fc32_ae32_enabled` is scoped to `CONFIG_IDF_TARGET_ESP32`.)
- **Coefficient generators** (`dsps_biquad_gen_f32.c`) are the RBJ Audio-EQ-Cookbook forms with **`Fs = 1`**: the `f` argument is normalised frequency in cycles/sample, range 0…0.5, so a 60 Hz high-pass at 32 kHz is `f = 60/32000 = 0.001875`. Available: `lpf`, `hpf`, `bpf`, `bpf0db`, `notch(gain)`, `allpass360`, `allpass180`, `peakingEQ`, `lowShelf(gain)`, `highShelf(gain)`.
- Three of the ten are mislabelled or duplicated:
  - `dsps_biquad_gen_notch_f32(coeffs, f, gain, q)` implements the RBJ **peaking EQ** (`b0 = 1 + α·A`, `b2 = 1 − α·A`), not a notch. It degenerates to a true notch only as `gain → −∞`.
  - `dsps_biquad_gen_peakingEQ_f32(coeffs, f, q)` takes **no gain argument** and is byte-identical to `dsps_biquad_gen_bpf0db_f32`.
  - `dsps_biquad_gen_allpass180_f32` is byte-identical to `dsps_biquad_gen_allpass360_f32`.
  - `notch`, `lowShelf` and `highShelf` compute `sqrtf(pow(10, (double)gain / 20.0))` — a `double` `pow` call, soft-float on the S3.
- **For our HPF (DC/rumble removal, ADR 0003's "software DC removal")**: `dsps_biquad_gen_hpf_f32(c, f_hz/fs, 0.7071f)` is a correct Butterworth-Q RBJ high-pass and is directly usable; at `f = 0.001875` the coefficients are close to 1 and −2 and float32 rounding of `a1` starts to matter — a first-order DC blocker or a cascade in float64-on-host / float32-on-device with an agreed tolerance is the safer construction, and it is a `spectral_core` decision, not an esp-dsp one.
- **For decimation there is no IIR path.** The decimating filters live in `modules/fir`: `dsps_fird_f32` (integer decimation, `dsps_fird_init_f32`), `dsps_firmr_f32` (rational L/M, `dsps_firmr_init_f32`) and the `dsps_resampler_mr_*` wrapper. All of them allocate their delay line with unchecked `memalign`/`malloc` when `delay == NULL` (§8), so pass the delay line in. Published cost: `dsps_fird_f32`, 1024 samples / 256 taps / decimation 4 = **115 499** cycles on the S3.

## 7. `modules/support`

- **`dsps_snr_f32(input, len, use_dc)`** (`snr/float/dsps_snr_f32.cpp`, C++): windows with a **periodic** Hann computed inline (`0.5·(1 − cos(2πi/len))` — note `len`, not `len−1`, i.e. the library's own test helper disagrees with its public window API), runs an ANSI radix-2 FFT, takes the peak bin, sums everything outside a fixed ±7-bin guard band, returns `10·log10(peak/noise) − 2` with the `− 2` documented only as "window correction". Side effects to know about: it calls **`dsps_fft2r_init_fc32(NULL, CONFIG_DSP_MAX_FFT_SIZE)` itself and never deinits**, so merely calling it once claims the global FFT table; it `new[]`s `2·len` floats without a null check; and it returns `0` — indistinguishable from a real 0 dB result — when `len` is not a power of two. Header says "for debug and unit tests only"; treat it as such and compute SNR on the host instead. `dsps_snr_fc32` is declared but never defined.
- **`dsps_sfdr_f32`** — same shape, same caveats.
- **`modules/support/mem`** — `dsps_memcpy_aes3` / `dsps_memset_aes3`, S3-only, 32 B (aligned) or 48 B (unaligned source) per loop for copy, 16 B per loop for set, correct for every alignment combination and covered by `modules/support/mem/test/`. Reachable only via `#include "dsps_mem.h"` (**not** in `esp_dsp.h`) and only under `CONFIG_DSP_OPTIMIZED`; otherwise the macros are plain `memcpy`/`memset`. Candidate for the spectrogram column blit into PSRAM — but measure against `memcpy` first, because the IDF's own `memcpy` is already Xtensa-tuned.
- **`dsps_tone_gen_f32(out, len, A, freq, phase)`** — normalised `freq` (cycles/sample), `phase` in degrees, and it **accumulates phase in float** (`ph += fr` with a `±2π` wrap) using `double sin()`. Fine for a smoke test, not fine for Tier-0 golden signals: the accumulated phase drifts and the wrap introduces a discontinuity in the last ULP. Our synthetic corpus is generated on the host in float64 and shipped as WAV.
- `dsps_view` (ASCII plot), `dsps_d_gen`, `dsps_h_gen`, `dsps_cplx_gen` — debug helpers; `dsps_cplx_gen_init` has two more unchecked `malloc`s.

## 8. `sc16` vs `fc32` — the per-stage scaling, quantified

The fixed-point radix-2 butterfly is four inline helpers in `modules/fft/fixed/dsps_fft2r_sc16_ansi.c`:

```c
static const int add_rount_mult  = 0x7fff;
static const int mult_shift_const = 0x7fff;   /* "Used to shift data << 15" */

static inline int16_t xtfixed_bf_3(int16_t a0, int16_t a1, int16_t a2,
                                   int16_t a3, int16_t a4, int result_shift)
{
    int result = a0 * mult_shift_const;                              /* Q15 -> Q30 */
    result += (int32_t)a1 * (int32_t)a2 + (int32_t)a3 * (int32_t)a4; /* Q15*Q15 = Q30 */
    result += add_rount_mult;                                        /* round */
    result = result >> result_shift;                                 /* called with 16 */
    return (int16_t)result;
}
```

Both operands arrive in Q30 and the result is shifted right by **16**, not 15. That extra bit is a **divide-by-two in every stage**:

| Consequence | Value |
|---|---|
| Scaling per radix-2 stage | 1/2 (−6.02 dB) |
| Total output scaling | **1/N** for an N-point complex FFT |
| Effective bits lost | `log2(N)` — 10 bits at `N_c = 1024`, 12 at `N_c = 4096` |
| Bits left for a low-level bin at `N_c = 4096` from a 16-bit input | ≈ 4 |
| Renormalisation / exponent tracking | **none** — this is fixed scaling, *not* block floating point |

Two more sc16 caveats found while reading:

- **Overflow is reachable in the ANSI butterfly.** `a0 * 0x7fff` reaches ±1.074 × 10⁹ and `|a1·a2 + a3·a4| = |c·re + s·im| · 32767²` reaches 1.52 × 10⁹ for a full-scale input; their sum exceeds `INT32_MAX` (2.147 × 10⁹). There is no saturation, so sc16 input must carry headroom (≈ 3 dB or more below full scale). The `_aes3` assembly uses the saturating `ee.vadds.s16` / `ee.cmul.s16` TIE ops with a `wsr.sar`-configured shift and does not have this failure mode, so **ANSI and aes3 do not agree bit-for-bit near full scale** — which is precisely what a backend-agreement test would flag.
- **`dsps_fft2r_init_sc16` ignores its `table_size`** on the internal path: it always allocates and records `CONFIG_DSP_MAX_FFT_SIZE` entries (8 KB at the default 4096), and it does not check the allocation (§9).

Against the `fc32` path, sc16 buys roughly **6×** on the S3 (1024 complex points: 15 623 vs 97 847 cycles) at the cost of `log2(N)` bits. That trade is not available here, and the binding number is the **per-bin range the display asks for**, not the microphone. Every shipped preset sets `db_floor_dbfs` to −90 or −100 under a 0 dBFS ceiling — a 90–100 dB range — which an `N`-point FFT can reach because it spreads broadband noise over `N/2` bins; reading the mic’s 61.5 dB(A) broadband SNR as a display ceiling is the specific error [the proposal warns against](../../proposal/01-super-spectral-proposal.md) (§3.3). Shedding `log2(N_c)` = 10–12 bits out of a 16-bit word cannot leave that range: **`fc32` only, as [ADR 0006](../../adr/README.md) already pre-registers.** Revisiting sc16 requires a block-floating-point layer (per-stage headroom detection + exponent bookkeeping) that esp-dsp does not provide and that would have to be written and validated against the float path.

## 9. Defects found

### 9.1 The two GCC `-fanalyzer` findings ([ADR 0017](../../adr/0017-no-radio-in-v1-trimmed-component-set.md))

Both were reproduced on the host with `gcc 13.3.0 -O2 -fanalyzer -Wall` on minimal extracts of the upstream sources (the S3 targets are unreachable for the host analyzer, so the extracts keep the control flow and drop the inline assembly).

**(a) `va_start` without `va_end` — `modules/common/misc/aes3_tie_log.c`, function `tie_log()`**

```c
esp_err_t tie_log(int n_regs, ...)
{
#if !TIE_LOG_ENABLED
    return ESP_OK;
#else
    va_list list;
    va_start(list, n_regs);
    ...
    return ESP_OK;      /* no va_end(list) on this path, and it is the only path */
#endif
}
```

`-Wanalyzer-va-list-leak`: *"missing call to 'va_end' to match 'va_start'"*. C17 §7.16.1p3 makes the missing `va_end` undefined behaviour regardless of whether a given ABI's `va_end` is a no-op. The function is a register-dump debug helper, is declared in the public `dsp_common.h`, is listed unconditionally in `CMakeLists.txt`, is guarded by `#if (CONFIG_IDF_TARGET_ESP32S3)` and a `#define TIE_LOG_ENABLED 1` that is never 0, and is **called from nowhere in the tree** — so it compiles into every ESP32-S3 build and is pure analyzer noise. Fix: one `va_end(list);` before the `return`.

**(b) unchecked allocation in `dsps_*_init` — several files**

`-Wanalyzer-possible-null-dereference` [CWE-690]. The pattern is: allocate, do not check, dereference in the same function.

| File | Function | Line-context | Dereferenced by |
|---|---|---|---|
| `modules/fft/fixed/dsps_fft2r_sc16_ansi.c` | `dsps_fft2r_init_sc16` | `memalign(16, CONFIG_DSP_MAX_FFT_SIZE * sizeof(int16_t))` | `dsps_gen_w_r2_sc16(dsps_fft_w_table_sc16, …)` a few lines later |
| `modules/fir/float/dsps_fir_init_f32.c` | `dsps_fir_init_f32` | `memalign(16, (coeffs_len + 4) * sizeof(float))` / `malloc(…)` | `for (…) delay[i] = 0;` |
| `modules/fir/float/dsps_firmr_init_f32.c` | `dsps_firmr_init_f32` | `memalign(16, (fir->delay_size + 4) * sizeof(float))` | `for (…) fir->delay[i] = 0;` |
| `modules/fir/fixed/dsps_fird_init_s16.c` | `dsps_fird_init_s16` | five sites: `aexx_rounding_buff`, `new_delay_buff` (×2), `aes3_delay_buff`, `aes3_coeffs_buff` | all written immediately |
| `modules/fir/fixed/dsps_firmr_init_s16.c` | `dsps_firmr_init_s16` | `memalign(16, (fir->delay_size + 4) * sizeof(int16_t))` | `for (…) fir->delay[i] = 0;` |
| `modules/fir/resampler/dsps_resampler_mr.c` | `dsps_resampler_mr_init` | `malloc(sizeof(fir_f32_t))` / `malloc(sizeof(fir_s16_t))` | passed straight into `dsps_firmr_init_*` |
| `modules/support/cplx_gen/dsps_cplx_gen_init.c` | `dsps_cplx_gen_init` | two `malloc`s for the LUT | LUT fill loop |

The `fc32` FFT inits (`dsps_fft2r_init_fc32`, `dsps_fft4r_init_fc32`) **do** check and return `ESP_ERR_DSP_PARAM_OUTOFRANGE` — those are the ones we use, which is why our backend is unaffected in practice; the analyzer still stops the build.

### 9.2 Found by reading, not by the analyzer

- **`dsps_firmr_init_s16` reads `fir->delay_size` before assigning it.** The allocation at the top of the function sizes the delay line from `fir->delay_size`, but `fir->delay_size = coeffs_len / interp;` happens *after* it. The caller's `fir_s16_t` is normally uninitialised — and `dsps_resampler_mr_init` reaches this path with a freshly `malloc`'d, uninitialised struct — so the size comes from heap garbage, while the zeroing loop at the bottom uses the *correct* `delay_size`. Whenever the garbage value is smaller, that loop writes past the end of the allocation. The float twin `dsps_firmr_init_f32` sets `fir->delay_size` before allocating; the s16 port dropped the ordering. CWE-457 → CWE-787.
- **`dsps_biquad_f32_aes3` is unreachable on the ESP32-S3** (§6): the `#elif` ordering means the LX7 always takes the ESP32 `_ae32` kernel. Costs the S3 whatever the PIE biquad was worth.
- **Dead public API**: `dsps_cplx2real256_fc32_ansi`, `dsps_snr_fc32`, `dsps_bit_rev4r_fc32_ae32`, `dsps_fft4r_sc16` (+ its three `extern` globals) are declared in public headers with no definition anywhere.
- **Doxygen defect**: `dsps_fft4r_init_fc32`'s `fft_table_buff` needs `4 × max_fft_size` floats; nothing says so.
- **Silent no-op re-init**: a second `dsps_fft2r_init_fc32` / `dsps_fft4r_init_fc32` with a *larger* size returns `ESP_OK` and keeps the old, too-small table, which then over-reads (§2.2).

## 10. Proposed upstream issue text

To be filed at <https://github.com/espressif/esp-dsp/issues> using the "Bug report" template (`.github/ISSUE_TEMPLATE/02_bug.yml`; fields: IDF version, module/chip, DSP version, expected, actual, steps). One issue, because both findings come from the same CI configuration and the same one-line-each fix class. No CLA is needed for an issue (only for a PR).

> **Title:** Two GCC `-fanalyzer` findings in v1.8.2: `va_start` without `va_end` in `aes3_tie_log.c`, and unchecked allocations in several `dsps_*_init` functions
>
> **IDF version:** v6.0.2 · **Module or chip used:** ESP32-S3 (chip-down ESP32-S3-R8, 8 MB octal PSRAM) · **DSP version:** v1.8.2 (`3c8ac0f`)
>
> **What is the expected behavior?**
> A project that builds with `-fanalyzer` as a blocking warning (`CONFIG_COMPILER_STATIC_ANALYZER`-style setups, or `-fanalyzer` added per target) should be able to include `espressif/esp-dsp` without disabling the analyzer for the component.
>
> **What is the actual behavior?**
> Building an ESP32-S3 application that depends on `espressif/esp-dsp ~1.8.2` with GCC's static analyzer enabled produces two classes of finding in library code. Both are in code paths that compile into every ESP32-S3 build.
>
> **1. `-Wanalyzer-va-list-leak` — `modules/common/misc/aes3_tie_log.c`, `tie_log()`**
> `va_start(list, n_regs)` has no matching `va_end(list)` on the single return path. C17 §7.16.1p3 makes this undefined behaviour independently of whether `va_end` expands to nothing on Xtensa. The file is listed unconditionally in `CMakeLists.txt`, the body is enabled by `#if (CONFIG_IDF_TARGET_ESP32S3)` together with `#define TIE_LOG_ENABLED 1` (never set to 0), and `tie_log` is declared in the public `dsp_common.h` but is not called anywhere in the repository. Fix: add `va_end(list);` before `return ESP_OK;`.
>
> **2. `-Wanalyzer-possible-null-dereference` (CWE-690) — allocation results used without a NULL check**
> The `fc32` FFT inits check their allocations and return `ESP_ERR_DSP_PARAM_OUTOFRANGE`; the following do not, and dereference the result in the same function:
> - `modules/fft/fixed/dsps_fft2r_sc16_ansi.c` — `dsps_fft2r_init_sc16()`: `memalign(16, CONFIG_DSP_MAX_FFT_SIZE * sizeof(int16_t))`, then `dsps_gen_w_r2_sc16()` writes through it.
> - `modules/fir/float/dsps_fir_init_f32.c` — `dsps_fir_init_f32()`: the `delay == NULL` allocation, then the zeroing loop.
> - `modules/fir/float/dsps_firmr_init_f32.c` — `dsps_firmr_init_f32()`: same shape.
> - `modules/fir/fixed/dsps_fird_init_s16.c` — `dsps_fird_init_s16()`: `aexx_rounding_buff`, `new_delay_buff` (both `#if` branches), `aes3_delay_buff`, `aes3_coeffs_buff`.
> - `modules/fir/fixed/dsps_firmr_init_s16.c` — `dsps_firmr_init_s16()`: the `delay == NULL` allocation.
> - `modules/fir/resampler/dsps_resampler_mr.c` — `dsps_resampler_mr_init()`: `malloc(sizeof(fir_f32_t))` / `malloc(sizeof(fir_s16_t))`, passed straight into `dsps_firmr_init_*`.
> - `modules/support/cplx_gen/dsps_cplx_gen_init.c` — `dsps_cplx_gen_init()`: both LUT allocations.
>
> Returning `ESP_ERR_NO_MEM` (or the existing `ESP_ERR_DSP_PARAM_OUTOFRANGE`, for consistency with `dsps_fft2r_init_fc32`) would match the rest of the library and silence the analyzer.
>
> **While looking at (2), a related defect in the same file family, which the analyzer does not see because the struct comes from the caller:**
> `modules/fir/fixed/dsps_firmr_init_s16.c` sizes the delay line from `fir->delay_size` **before** assigning it — `fir->delay_size = coeffs_len / interp;` is executed after the allocation. Callers normally pass an uninitialised `fir_s16_t` (`dsps_resampler_mr_init()` passes a freshly `malloc`'d one), so the allocation size is indeterminate while the zeroing loop at the end of the function uses the correct `delay_size`, writing out of bounds whenever the indeterminate value was smaller. The float counterpart `dsps_firmr_init_f32()` assigns `fir->delay_size` before allocating; moving the assignment up in the s16 version fixes it.
>
> **Steps to reproduce:** add `espressif/esp-dsp: "~1.8.2"` to an ESP-IDF v6.0.2 ESP32-S3 project and compile the component with `-fanalyzer` (e.g. `target_compile_options(... PRIVATE -fanalyzer)` on the `esp-dsp` target, or `idf.py -DCMAKE_C_FLAGS=-fanalyzer build`). Findings 1 and 2 appear at `-O2` with GCC 13 or newer. Minimal host-side reductions of both patterns reproduce them with `gcc-13.3 -O2 -fanalyzer -Wall`.
>
> **Other items:** none of these affect correct-input, sufficient-memory operation; they matter to projects that gate merges on the analyzer. Happy to open a PR for the `va_end` one-liner and the NULL checks if that is preferred.

Until this lands, [ADR 0017](../../adr/0017-no-radio-in-v1-trimmed-component-set.md)'s scoping stands: `-fanalyzer` is blocking for our code and appended as `-fno-analyzer` for registry components.

## 11. Benchmarks and the test harness

The table in `docs/en/esp-dsp-benchmarks.rst` is generated by the Unity test app, and **`test/linker.lf` maps the whole of `libesp-dsp.a`, `libdsp.a` and `libesp-dsp_test.a` into `noflash` (IRAM)**. Every published cycle count is therefore for IRAM-resident code with no flash-cache misses; a normal application runs esp-dsp from flash through the cache and will be slower. `test_app/sdkconfig.defaults` also sets `CONFIG_COMPILER_OPTIMIZATION_PERF=y` and disables both watchdogs; `test_app/pytest_esp-dsp_unity_tests.py` drives it with `pytest-embedded` (`dut.run_all_single_board_cases()`) over `esp32`, `esp32s3`, `esp32p4`, `esp32s31`. Cycles are taken with `dsp_get_cpu_cycle_count()` inside `dsp_ENTER_CRITICAL`/`dsp_EXIT_CRITICAL` (`test/report.inc`).

Measured, S3, `-O2` (the "O2" column; the header's O2/Os labels are swapped relative to `CONTRIBUTING.md`'s description, so quote the column header):

| Function | 64 | 128 | 256 | 512 | 1024 |
|---|---:|---:|---:|---:|---:|
| `dsps_fft2r_fc32` (complex points) | 3 970 | 8 999 | 20 139 | 44 594 | 97 847 |
| `dsps_fft4r_fc32` | 2 597 | — | 13 213 | — | 64 482 |
| `dsps_fft2r_sc16` | 774 | 1 608 | 3 412 | 7 294 | 15 623 |
| `dsps_biquad_f32` (1024 input samples) | — | — | — | — | 17 552 |
| `dsps_fird_f32` (1024 in, 256 taps, decim 4) | — | — | — | — | 115 499 |

**The table stops at 1024 complex points and contains no row for `dsps_bit_rev*`, `dsps_cplx2real_fc32`, `dsps_cplx2reC_fc32` or any `dsps_wind_*`** — i.e. it covers none of the three stages our real-input path adds. Extrapolating `a·N·log2 N` from the three fft4r and five fft2r points (the coefficient falls slowly: fft2r 10.34 → 9.56 cycles per point·bit from N = 64 to 1024; fft4r 6.76 → 6.30):

| Preset | Transform | Extrapolated FFT | + bit-rev + `cplx2real` (order of magnitude) | Total | at 240 MHz | at 50 frames/s |
|---|---|---:|---:|---:|---:|---:|
| real-4096 | fft2r, `N_c` = 2048 | ≈ 213 k | ≈ 40 k | **≈ 253 k** | ≈ 1.05 ms | **≈ 5 %** of one core |
| real-8192 | fft4r, `N_c` = 4096 | ≈ 305 k | ≈ 80 k | **≈ 385 k** | ≈ 1.6 ms | **≈ 8 %** of one core |
| real-8192 | fft2r, `N_c` = 4096 | ≈ 462 k | ≈ 80 k | ≈ 542 k | ≈ 2.3 ms | ≈ 11 % of one core |

All **(prov.)** — extrapolation from IRAM-resident measurements, one core, no cache pressure, no window multiply, no magnitude/dB stage. It corroborates the "real-4096 @ 50 Hz ≈ 6 % of one core" figure in [bibliography 02 #21](../../bibliography/02-application-notes.md) — and the 6.21 % / 8.89 % column in [proposal §3.3](../../proposal/01-super-spectral-proposal.md), which is that figure scaled per preset. The gap is not a disagreement: this table stops at `cplx2real`, the proposal's column also carries the window multiply, the magnitude and the fast-log, and 6.21/5 ≈ 1.18 and 8.89/8 ≈ 1.11 is the right size for exactly those. Neither replaces a measurement. **Deliverable for Phase 1:** extend the benchmark idea into our own cycle-count harness (`dsp_get_cpu_cycle_count()` around each stage, on target, both `CONFIG_DSP_OPTIMIZED=y` and `=n`, with and without an esp-dsp `linker.lf` IRAM mapping) and publish per-preset numbers in [`docs/validation/README.md`](../../validation/README.md).

## 12. What transfers to `spectral_fft_backend`

- (+) The full real-input call sequence of §3, with the four corrections (periodic window, `bit_rev2r`/`bit_rev4r` rather than `bit_rev`, unpack slot 0, check every return code).
- (+) **Own the memory.** Pass pre-allocated, 16-byte-aligned, `MALLOC_CAP_INTERNAL` buffers to both inits; never pass `NULL` (§4.2). Init once at boot with the largest `N_c` any preset uses.
- (+) The radix table in §3: fft4r for real-2048 and real-8192, fft2r for real-1024 and real-4096. The backend picks per preset; the backend-agreement test covers both kernels because they are genuinely different code.
- (+) `dsps_cplx2reC_fc32` as a **two-for-one**: two overlapping analysis frames (or two channels) through one complex FFT, at the price of packing one into re and one into im. At 50 frames/s with ≥ 50 % overlap this halves the transform cost; the packing loop and the extra buffer are the counterweight. Worth benchmarking before adopting.
- (+) `__attribute__((aligned(16)))` on every static FFT buffer, as esp-dsp's own examples do.
- (+) `dsp_get_cpu_cycle_count()` + `dsp_ENTER_CRITICAL` as the on-target measurement idiom.
- (−) **Do not use `dsps_wind_*_f32` directly for analysis** — symmetric, and double-promoting. Generate the periodic family ourselves and checksum it.
- (−) **Do not use `sc16`** (§8) and do not use `dsps_snr_f32`/`dsps_sfdr_f32` outside a test (§7).
- (−) Do not copy the examples' dB conventions: `10·log10((re²+im²)/N)` with no S1/S2, no one-sided ×2, and slot 0 treated as an ordinary bin.
- (−) Do not rely on `dsps_biquad_f32` being SIMD on the S3 (§6), and do not use `dsps_biquad_gen_notch_f32`, `_peakingEQ_f32` or `_allpass180_f32` under their advertised names.
- (−) Do not let esp-dsp's globals be shared implicitly: `dsps_fft_w_table_fc32`, `dsps_fft4r_w_table_fc32`, `dsps_fft2r_rev_tables_fc32[]` and the `*_initialized` flags are process-wide. One owner (`spectral_fft_backend`), one init, one deinit; the host-side and QEMU tests must not call anything that inits behind our back.

## 13. Corrections owed to other documents

| Document | Says | Should say |
|---|---|---|
| [bibliography 06 #1](../../bibliography/06-reference-projects.md) | "`dsps_fft2r/fft4r/fft4real`" | there is no `fft4real` API; the real path is `fft2r`/`fft4r` + `bit_rev*` + `dsps_cplx2real_fc32`, and `dsps_cplx2real_fc32` needs `dsps_fft4r_init_fc32` even on the radix-2 path |
| [`spectral_fft_backend` README](../../../firmware/twatch-s3/components/spectral_fft_backend/README.md) | "the `fft4real` path"; work area "~32 KB for n = 4096 (prov.)" | same correction; and the real-4096 work area is ≈ 78 KB with esp-dsp's own tables, ≈ 46 KB with our own `cplx2real` |
| `firmware/twatch-s3/main/idf_component.yml` comment | "radix-2/4 complex FFT, fft4real, six windows" | drop `fft4real`; note the six windows are symmetric |
| [`xiao-edge-audio_notes.md`](xiao-edge-audio_notes.md) §2.3, §3 | "`CONFIG_DSP_MAX_FFT_SIZE` ceiling (4096 default) — a Kconfig line our `sdkconfig.defaults` must carry before the 8192 preset exists" | `CONFIG_DSP_MAX_FFT_SIZE` bounds `N_c`, not `N_real`; the default 4096 already covers a real-8192 FFT on the real path. No change needed |
| [bibliography 02 #21](../../bibliography/02-application-notes.md) | "real-8192 fits 112 KB SRAM" | 112 KB holds only if we supply our own `cplx2real` twiddles (≈ 104 KB); esp-dsp's own tables put it at ≈ 160 KB, 64 KB of which lands in PSRAM by default |
| [ADR 0006 backlog entry](../../adr/README.md) | "float32 `fc32` only — no `sc16` without a block-floating-point layer" | confirmed, with the arithmetic: fixed `>>16` per butterfly = 1/2 per stage = 1/N overall, `log2(N)` bits lost, no exponent tracking (§8) |

Reference basis: the esp-dsp clone at `3c8ac0f` (= v1.8.2) — `modules/fft/{float,fixed,include}`, `modules/windows/*`, `modules/iir/*`, `modules/support/{snr,mem,misc,cplx_gen}`, `modules/fir/*`, `modules/common/{include,misc}`, `Kconfig`, `CMakeLists.txt`, `LICENSE`, `CONTRIBUTING.md`, `docs/en/esp-dsp-benchmarks.rst`, `test/`, `test_app/`, `examples/{fft,fft4real}`, `applications/spectrum_box_lite`; ESP-IDF v6.0.2 sources for `dsps_fft2r_w_table_fc32_1024` (`components/esp_rom/esp32s3/ld/esp32s3.rom.ld`), the DRAM/ROM split (`components/esp_system/ld/esp32s3/memory.ld.in`), and the allocator routing (`components/esp_libc/src/heap.c`, `components/heap/heap_caps.c`, `components/esp_psram/Kconfig.spiram.common`); [bibliography 06 #1](../../bibliography/06-reference-projects.md) (the project), [02 #20](../../bibliography/02-application-notes.md) (ESP-DSP API reference) and [02 #21](../../bibliography/02-application-notes.md) (ESP-DSP benchmarks); [04 #1](../../bibliography/04-books.md) (Smith, *SASP* — the real-FFT N/2 packing identity), [05 #1](../../bibliography/05-papers.md) (Heinzel 2002 — S1/S2, NENBW, periodic windows), [05 #2](../../bibliography/05-papers.md) (Harris 1978) and [05 #3](../../bibliography/05-papers.md) (Nuttall 1981) for the window table; [ADR 0017](../../adr/0017-no-radio-in-v1-trimmed-component-set.md) for the analyzer policy that produced the two findings; [`docs/hw/README.md`](../../hw/README.md) for the measured chip revision, clock and PSRAM facts of this unit (2026-08-20); [`firmware/twatch-s3/sdkconfig.defaults.esp32s3`](../../../firmware/twatch-s3/sdkconfig.defaults.esp32s3) for the PSRAM allocator thresholds this note reasons against.
