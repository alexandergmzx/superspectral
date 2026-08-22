/* SPDX-FileCopyrightText: 2026 Alexander Gomez
 * SPDX-License-Identifier: Apache-2.0
 *
 * spectral_core - public API (ADR 0006: FFT normalisation and window
 * conventions, single-source spec shared by the watch and the host).
 * ADR 0006 is WRITTEN as of 2026-08-21 and ratifies the conventions in
 * this header verbatim; where it goes further than the header (own
 * cplx2real, fft2r-only, DC-blocker form, smoothing domain) the record
 * is the authority.
 *
 * STATUS: declarations only. Bodies land in src/ during roadmap E1; the
 * contract below is what host-tests/ and the golden-file manifest
 * (docs/validation/golden-files.md) will be written against.
 *
 * Rules of this header:
 *   - C99, float only. The ESP32-S3 FPU is single precision; a bare `2.0` or
 *     sin() instead of sinf() drops the hot loop into soft-float
 *     (-Wdouble-promotion is -Werror in this component).
 *   - No dynamic allocation inside the processing path. The caller owns every
 *     buffer; sizes are queried first. FFT work areas are never on the stack.
 *   - No ESP-IDF, no esp-dsp, no FreeRTOS. The transform is injected through
 *     spectral_rfft_fn so the same core runs on host (fft_ref.c), QEMU and
 *     target (components/spectral_fft_backend -> esp-dsp).
 */

#ifndef SPECTRAL_CORE_SPECTRAL_H_
#define SPECTRAL_CORE_SPECTRAL_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ------------------------------------------------------------------------
 * Windows
 *
 * Coefficients follow Heinzel, Ruediger & Schilling (2002), "Spectrum and
 * spectral density estimation by the DFT, including a comprehensive list of
 * window functions and some new flat-top windows" (bibliography 05), with
 * Nuttall (1981) coefficients where Harris (1978) is known to be suboptimal.
 * Windows are generated PERIODIC ("DFT-even", length-N period, not the
 * symmetric N-1 form): this matches scipy.signal.get_window(..., fftbins=True)
 * and is the single most common golden-file killer. The enum is the wire
 * value used by preset JSON (protocols/specs) - append only, never renumber.
 * ---------------------------------------------------------------------- */
typedef enum {
    SPECTRAL_WINDOW_RECT = 0, /* NENBW 1.000 bins; calibration tones only */
    SPECTRAL_WINDOW_HANN = 1, /* NENBW 1.500 bins; default for spectrogram */
    SPECTRAL_WINDOW_BLACKMAN = 2,
    SPECTRAL_WINDOW_BLACKMAN_HARRIS = 3, /* 4-term, Nuttall 1981 coefficients */
    SPECTRAL_WINDOW_BLACKMAN_NUTTALL = 4,
    SPECTRAL_WINDOW_NUTTALL = 5,
    SPECTRAL_WINDOW_FLATTOP = 6, /* amplitude-accurate level readouts */
    SPECTRAL_WINDOW_COUNT
} spectral_window_t;

/* ------------------------------------------------------------------------
 * Normalisation (Heinzel 2002 S1/S2 formulation - the ONLY convention used
 * anywhere in this project; host/ golden generators must reproduce it)
 *
 *   S1    = sum_j w[j]                         (window sum)
 *   S2    = sum_j w[j]^2                       (window energy)
 *   NENBW = N * S2 / S1^2                      [bins]  normalised ENBW
 *   ENBW  = NENBW * fs / N                     [Hz]
 *
 *   PS  [FS^2]    = 2 * |X[k]|^2 / S1^2        -> reads the RMS^2 of a sine
 *                                                at bin k, independent of N
 *   PSD [FS^2/Hz] = 2 * |X[k]|^2 / (fs * S2)   -> noise floor independent of N
 *
 *   (factor 2 for the one-sided spectrum, k = 1 .. N/2-1; DC and Nyquist
 *   bins are NOT doubled.)  PS = PSD * ENBW.
 *
 * Rule of thumb that ADR 0006 turns into a test: a tone is read from PS
 * (divide by coherent gain, i.e. S1), a noise floor from PSD (divide by
 * sqrt(ENBW)). Mixing them is the classic "my floor is 2 dB off" bug.
 *
 * dB reference: 0 dBFS = a full-scale SINE (amplitude 1.0 -> RMS^2 = 0.5),
 * i.e. dBFS = 10*log10(PS / 0.5). Mind the square: PS is PER BIN, so a
 * full-scale square's FUNDAMENTAL bin reads +2.10 dBFS (20*log10(4/pi));
 * +3.01 dBFS is its TOTAL power over all harmonics. Both are asserted in
 * host-tests -- a test written from the broadband figure against a per-bin
 * PS fails by 0.92 dB (ADR 0006 D3).
 * The PDM path delivers int16; the backend scales by 1/32768 before the
 * window so "FS" is the 16-bit code range, not the mic's acoustic overload.
 * Absolute dB SPL is a separate, optional calibration offset (validation
 * plan; Knowles sensitivity -22 dBFS @ 94 dB SPL is the nominal seed).
 *
 * Processing gain: an N-point FFT spreads broadband noise over N/2 bins, so
 * a tonal component sits ~10*log10(N/2 / NENBW) dB above the floor that the
 * mic's 61.5 dB(A) SNR suggests (about +30 dB at N = 4096). The mic SNR
 * bounds wideband LEVEL accuracy, not per-bin dynamic range.
 * ---------------------------------------------------------------------- */
typedef enum {
    SPECTRAL_SCALE_PS = 0, /* power spectrum, FS^2     (tones, peaks, f0)   */
    SPECTRAL_SCALE_PSD = 1 /* power spectral density, FS^2/Hz (noise floor) */
} spectral_scale_t;

/* Real-input FFT injected by the integrator.
 *   in      : n real samples (already windowed by spectral_core)
 *   out     : n/2 + 1 complex bins as interleaved {re, im}, out[0] = DC,
 *             out[n/2] = Nyquist (imaginary part 0). Unnormalised forward DFT
 *             (no 1/N, no 1/sqrt(N)); spectral_core applies S1/S2 scaling.
 *   n       : power of two, 256 <= n <= 8192
 * Returns 0 on success. Implementations: fft_ref.c (host, radix-2, float),
 * spectral_fft_backend (esp-dsp dsps_fft2r_fc32 + bit_rev + cplx2real; there
 * is no fft4real API -- see the backend README). The two must
 * agree to the tolerance in docs/validation/golden-files.md, compared in dB. */
typedef int (*spectral_rfft_fn)(void *user, const float *in, float *out, size_t n);

typedef struct {
    uint32_t fft_size;    /* N: power of two, 256..8192            */
    uint32_t hop;         /* samples between frames. NOT N/2: every
                           * shipped preset overlaps 69-94 % (hop is
                           * interval_ms * fs / 1000, ADR 0010 V7). */
    float sample_rate_hz; /* 16000 / 32000 / 48000 (ADR 0003)      */
    spectral_window_t window;
    spectral_scale_t scale;
    spectral_rfft_fn rfft;
    void *rfft_user;
} spectral_config_t;

/* One analysed frame. `bins` is caller-owned, fft_size/2 + 1 floats. */
typedef struct {
    const float *bins;    /* PS or PSD per `scale`, linear (not dB)       */
    uint32_t n_bins;      /* fft_size / 2 + 1                             */
    float bin_hz;         /* fs / N                                       */
    float nenbw_bins;     /* N * S2 / S1^2, for this window                */
    float enbw_hz;        /* nenbw_bins * bin_hz                          */
    float s1;             /* window sum, for PS readback                  */
    float s2;             /* window energy, for PSD readback              */
    uint64_t frame_index; /* monotonically increasing since init          */
    uint64_t t0_samples;  /* sample index of the frame's first sample     */
    uint8_t clipped;      /* 1 if any |x| >= 0.99 FS in this frame         */
} spectral_frame_t;

/* Opaque analysis state; size via spectral_state_size(). */
typedef struct spectral_state spectral_state_t;

/* Bytes the caller must provide for the state + work area of `cfg`
 * (window table, windowed copy, complex FFT output). Place in internal SRAM
 * on target; never on a task stack. */
size_t spectral_state_size(const spectral_config_t *cfg);

/* Initialise state in caller memory. Returns 0 on success, negative on an
 * invalid configuration (non-power-of-two N, unknown window, NULL rfft). */
int spectral_init(spectral_state_t *st, void *mem, size_t mem_bytes, const spectral_config_t *cfg);

/* Analyse exactly cfg->fft_size samples in [-1, 1]. `out_bins` must hold
 * fft_size/2 + 1 floats; `frame` is filled with scaling metadata.
 * Returns 0 on success. Pure function of (state, input): no allocation,
 * no I/O, no time dependence - which is what makes golden files possible. */
int spectral_process(spectral_state_t *st, const float *samples, float *out_bins,
                     spectral_frame_t *frame);

/* Fill `w` with the periodic window of length n; returns S1, S2 and NENBW.
 * Also used by host/golden generators so both sides share one table. */
int spectral_window_fill(spectral_window_t win, float *w, size_t n, float *s1, float *s2,
                         float *nenbw_bins);

/* Convert a PS/PSD value to dB re full-scale sine (see dBFS note above).
 * Floors at -200 dB instead of returning -inf. */
float spectral_to_dbfs(float value, spectral_scale_t scale, float enbw_hz);

#ifdef __cplusplus
}
#endif

#endif /* SPECTRAL_CORE_SPECTRAL_H_ */
