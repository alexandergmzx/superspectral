# spectral_fft_backend — esp-dsp binding

**Decision.** `spectral_core` never sees esp-dsp; this component implements the `spectral_rfft_fn` contract from [`spectral_core/spectral.h`](../spectral_core/include/spectral_core/spectral.h) on top of `espressif/esp-dsp ~1.8.2` (`dsps_fft2r_fc32` / `dsps_fft4r_fc32`, hand-composed with `dsps_bit_rev*` and `dsps_cplx2real_fc32` — **there is no `fft4real` API**, `examples/fft4real/` is a directory, and `dsps_cplx2real_fc32` needs `dsps_fft4r_init_fc32` even on the radix-2 path ([esp-dsp notes §2.1](../../../../docs/reference-projects/notes/esp-dsp_notes.md))). **Trade-off:** a second FFT implementation to keep in agreement (`fft_ref.c` on the host), but that agreement *is* the test that catches esp-dsp misuse — wrong `dsps_fft2r_init_fc32` table size, a forgotten bit-reverse, a missing `/N` — and it is the only place the S3 SIMD (`_aes3`) path gets numeric coverage (QEMU, ADR 0009).

## Contract

| Item | Value |
|---|---|
| Input | `n` windowed real floats, `256 ≤ n ≤ 8192`, power of two |
| Output | `n/2 + 1` interleaved complex bins, unnormalised forward DFT |
| Scaling | none here — `spectral_core` applies Heinzel S1/S2 (ADR 0006) |
| Work area | twiddle table + complex scratch in **internal SRAM** (`heap_caps_malloc`, never PSRAM, never a task stack); ~32 KB for n = 4096 (prov.) |
| Precision | `fc32` float path only; the `sc16` fixed-point FFT loses a bit per stage and is not used |
| Budget | real-4096 at 50 frames/s ≈ 6 % of one core (esp-dsp benchmark tables, prov.) |

## Validation

- **Backend-agreement test** on QEMU and target: same Tier-0 vectors through `fft_ref` and this backend; assert `|dB(esp) − dB(ref)| < tol` with `tol` from [`docs/validation/golden-files.md`](../../../../docs/validation/golden-files.md) (≈1e-4 relative, compared in dB, not linear).
- Run once with `CONFIG_DSP_OPTIMIZED=y` (esp-dsp's own Kconfig) to cover the S3 PIE path, once with the ANSI path.

Planned source: `src/fft_espdsp.c` (E1, after the gate build proves esp-dsp 1.8.2 compiles under v6.0.2's warnings-as-errors + gnu23 default).
