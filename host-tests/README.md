# Host tests — plain CMake, Apache-2.0

Fast, hardware-free regression tests for the pure-C99 DSP core (`firmware/twatch-s3/components/spectral_core/`): window generation, FFT reference implementation, peak interpolation, dB conversion, decimation cascade, pitch — everything that must agree with the host's golden vectors to a stated tolerance.

| File | Purpose |
|------|---------|
| [`CMakeLists.txt`](CMakeLists.txt) | Builds `spectral_core` with the host compiler under ASan + UBSan and registers one ctest case per `tests/test_*.c`. Configures cleanly today even though the core is a skeleton. |
| `tests/` *(planned)* | `test_window.c`, `test_fft_ref.c`, `test_peak.c`, `test_db.c`, `test_pitch.c` — one executable each, golden-vector driven |

## Why this directory exists (and why it is not under `host/`)

- **esp-dsp will not build on the ESP-IDF `linux` target**: its `CMakeLists.txt` lists Xtensa assembly unconditionally and even its ANSI-C files include `esp_attr.h`/`esp_log.h`. So the DSP core is split in two — `spectral_core` (pure C99, `REQUIRES ""`, zero `esp_*` includes) tested here, and `spectral_fft_backend` (esp-dsp on target, `fft_ref` on host/QEMU) validated by a **backend-agreement test** that pushes the same vectors through both and compares in dB. That second test needs QEMU or hardware and lives under [`../tests/`](../tests/).
- It is **Apache-2.0, deliberately outside [`../host/`](../host/)** (GPL-3.0-or-later). It compiles firmware code; GPL must not touch it. It consumes golden vectors from [`../host/golden/`](../host/golden/) as **data files** only — `fopen()`, never `#include`, never a link.
- Plain CMake, not IDF's `linux` target: seconds to build, gives Valgrind/gcovr/fuzzing for free, and avoids the `--preview set-target linux` API-stability caveat and the non-preemptive FreeRTOS simulator. If an IDF-`linux` lane is ever added, it tests the math, never timing.

## Running

```sh
cmake -S host-tests -B host-tests/build -G Ninja
cmake --build host-tests/build
ctest --test-dir host-tests/build --output-on-failure
```

No ESP-IDF, no `.envrc` activation required; any C99 compiler with sanitizer support (GCC ≥ 12 or Clang ≥ 15) works. `host-tests/build/` is gitignored.

## Conventions

- Warning policy mirrors the firmware components (`-Werror -Wshadow -Wconversion -Wdouble-promotion -Wformat=2 -Wundef -Wvla`); `-fno-fast-math` is explicit because the tolerance table assumes IEEE semantics on both sides.
- Tests assert **tolerances, not equality** — cents for f0, dB for spectra, Hz or % for formants — from [`../docs/validation/golden-files.md`](../docs/validation/golden-files.md). `TEST_ASSERT_FLOAT_WITHIN`-style helpers; no framework dependency beyond `<assert.h>`/`<math.h>` until one is justified by an ADR.
- Each test names the hazard it guards (`test_window_periodic_not_symmetric`, `test_db_reference_is_full_scale_sine`, `test_fft_scaling_matches_heinzel_ps`), mirroring `doc_ocr`'s test style.
- CI job `host-tests` (deferred, see [`../.github/workflows/README.md`](../.github/workflows/README.md)) runs exactly the three commands above and is added the moment the first source file lands in `spectral_core/src/`.
