# spectral_core — pure C99 analysis core

**Decision.** The spectral maths (windowing, S1/S2 normalisation, peak picking, f0 front end) is a dependency-free C99 component with `REQUIRES ""`. The FFT is *injected* through a function pointer; esp-dsp never appears here. **Trade-off:** one extra indirection per frame (negligible against a 4096-point FFT) buys a core that builds and tests on the host in seconds with ASan/UBSan, and that is numerically identical on host, QEMU and target — which is the precondition for the golden-file validation path (proposal §4, ADR 0009).

Conventions are fixed by **ADR 0006** (FFT normalisation and window conventions) and documented in the header itself: Heinzel 2002 `S1`/`S2`, `NENBW = N·S2/S1²`, PS vs PSD, periodic windows, 0 dBFS = full-scale sine. See [`include/spectral_core/spectral.h`](include/spectral_core/spectral.h).

## Layout

```
spectral_core/
├── CMakeLists.txt                  REQUIRES "" - guarded source list
├── include/spectral_core/
│   └── spectral.h                  public API sketch (this pass)
│       window.h, peak.h            planned (E1)
└── src/                            planned (E1): spectral.c, window.c,
                                    peak.c, fft_ref.c (host radix-2 reference)
```

## Rules

| Rule | Why |
|---|---|
| No `esp_*`, no FreeRTOS, no esp-dsp, no `<malloc.h>` | Host-buildable by [`host-tests/`](../../../../host-tests/README.md) (plain CMake, Apache-2.0 — *not* under the GPL `host/` tree) |
| `float` only; `-Wdouble-promotion` is `-Werror` | ESP32-S3 FPU is single precision; a stray `double` is a 5–11× slowdown |
| Caller owns all buffers; no allocation in `spectral_process()` | Deterministic, golden-file-testable; FFT work areas never on a task stack |
| Periodic (DFT-even) windows, Heinzel S1/S2 scaling | Matches `scipy.signal.get_window(..., fftbins=True)`; the host generator uses the same table via `spectral_window_fill()` |
| Window enum values are wire values for the preset schema | [`protocols/specs/`](../../../../protocols/specs/README.md) owns the JSON; append-only, never renumber |

## Validation hooks

- **Backend agreement**: `fft_ref.c` (host) vs `spectral_fft_backend` (esp-dsp) on the same Tier-0 synthetic vectors, compared in dB, tolerance table in [`docs/validation/golden-files.md`](../../../../docs/validation/golden-files.md).
- **Against Praat**: f0 median |Δcents| ≤ 5 c on the digital-injection path (proposal §4, research question) via the pinned parselmouth manifest in [`host/golden/`](../../../../host/golden/README.md).

Design prose lives in [`dsp/design/`](../../../../dsp/design/README.md); this README only states the component contract.
