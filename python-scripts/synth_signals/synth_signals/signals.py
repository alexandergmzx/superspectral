# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""Pure float64 signal generators on ``[-1, 1]``.

Every function returns a 1-D ``numpy.float64`` array of ``round(dur_s * fs)``
samples and takes its level as ``level_dbfs`` under ADR 0006 D3 (0 dBFS = a
full-scale sine, amplitude 1.0). Nothing here quantises, windows or writes:
that is :mod:`synth_signals.quantise` / :mod:`synth_signals.wavio`, and the
parameters each catalogue entry passes are the ground truth the manifest records.

Phase is computed in **cycles** (``f·n/fs``) and reduced modulo 1 before the
``sin`` — so an on-bin tone such as 437.5 Hz at 32 kHz (``7n/512``, exact in
binary) is exactly periodic, and a 3 s sweep to 16 kHz never feeds ``sin`` an
argument of 3×10⁵ rad. Sweeps and vibrato integrate their instantaneous
frequency into the same cycle count.

Level conventions per family (also stated in the manifest's ``ground_truth``):

* tones, square, sweeps, vibrato, DC+sine — ``level_dbfs`` is the **amplitude**
  (``10**(L/20)``); for ``two_tone`` it is the amplitude of the **envelope**,
  each component carrying half of it (−6.02 dB);
* noise — ``level_dbfs`` is the **RMS**, equal to that of a sine at the same
  dBFS (``10**(L/20)/sqrt(2)``), so noise and sine at the same level carry the
  same total power under the S1/S2 scaling (ADR 0006 D2);
* vowel — ``level_dbfs`` is the **peak** after the tract; the source-filter
  crest factor is not known a priori, so the peak is what can be set exactly.

References (bibliography positional addresses; the rest by name, ``(prov.)``
because they have no row in ``docs/bibliography/`` yet):

* Heinzel, Rüdiger & Schilling 2002 — 05 #1 — the S1/S2 scaling the levels
  above are defined against (through ADR 0006).
* Harris 1978 — 05 #2 — the two-tone resolution experiment ``two_tone`` feeds.
* Farina 2000 — 05 #88 — the exponential swept sine (``sweep_exponential``).
* Titze, *Principles of Voice Production* — 04 #6 — glottal-flow source models
  (Rosenberg, LF) and vocal-tract formant targets for the Tier-0 vowels.
* Rosenberg, A. E. (1971), "Effect of glottal pulse shape on the quality of
  natural vowels", *JASA* 49(2) — the trigonometric pulse (his model C) used by
  ``rosenberg_pulse``. *(prov.: not yet a bibliography row.)*
* Klatt, D. H. (1980), "Software for a cascade/parallel formant synthesizer",
  *JASA* 67(3) — the second-order resonator ``y[n] = A·x[n] + B·y[n−1] + C·y[n−2]``
  with ``C = −exp(−2πBW/fs)``, ``B = 2·exp(−πBW/fs)·cos(2πF/fs)``, ``A = 1 − B − C``,
  and the first-difference lip radiation. *(prov.: not yet a bibliography row.)*

Not a CLI module; :mod:`synth_signals.catalogue` names the instances.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy.integrate import cumulative_trapezoid
from scipy.signal import lfilter

TWO_PI = 2.0 * np.pi


# --- helpers ----------------------------------------------------------------


def n_samples(fs: int, dur_s: float) -> int:
    """``round(dur_s * fs)`` — the one place the sample count is derived."""
    n = int(round(dur_s * fs))
    if n <= 0:
        raise ValueError(f"duration {dur_s} s at {fs} Hz gives {n} samples")
    return n


def amplitude(level_dbfs: float) -> float:
    """``10**(level_dbfs/20)`` — amplitude of a sine at ``level_dbfs`` (ADR 0006 D3)."""
    return float(10.0 ** (level_dbfs / 20.0))


def rms_of_sine(level_dbfs: float) -> float:
    """RMS of a sine at ``level_dbfs``: ``amplitude / sqrt(2)``."""
    return amplitude(level_dbfs) / np.sqrt(2.0)


def _cycles_constant(f_hz: float, fs: int, n: int) -> np.ndarray:
    return f_hz * np.arange(n, dtype=np.float64) / fs


def _cycles_from_instantaneous(f_inst_hz: np.ndarray, fs: int) -> np.ndarray:
    """Integrate an instantaneous frequency (Hz, one value per sample) into cycles."""
    return cumulative_trapezoid(f_inst_hz, dx=1.0 / fs, initial=0.0)


def _sin_of_cycles(cycles: np.ndarray, phase_rad: float) -> np.ndarray:
    return np.sin(TWO_PI * np.mod(cycles + phase_rad / TWO_PI, 1.0))


def _vibrato_instantaneous_hz(
    f_hz: float, rate_hz: float, extent_cents: float, fs: int, n: int
) -> np.ndarray:
    """``f · 2^((extent/1200)·sin(2π·rate·t))`` — ``extent_cents`` is the **peak**
    deviation (±), so 100 cents = ±1 semitone, 2 semitones peak-to-peak."""
    t = np.arange(n, dtype=np.float64) / fs
    return f_hz * 2.0 ** ((extent_cents / 1200.0) * np.sin(TWO_PI * rate_hz * t))


# --- tones ------------------------------------------------------------------


def sine(f_hz: float, fs: int, dur_s: float, level_dbfs: float = 0.0, phase_rad: float = 0.0) -> np.ndarray:
    """``A · sin(2π f t + φ)`` with ``A = 10**(level_dbfs/20)``."""
    n = n_samples(fs, dur_s)
    return amplitude(level_dbfs) * _sin_of_cycles(_cycles_constant(f_hz, fs, n), phase_rad)


def square(f_hz: float, fs: int, dur_s: float, level_dbfs: float = 0.0, phase_rad: float = 0.0) -> np.ndarray:
    """Ideal (not band-limited) square: ``+A`` on the first half-cycle, ``−A`` on the second.

    Decided on the cycle fraction, not on ``sign(sin)``, so no sample depends on
    ``sin`` rounding at a zero crossing. Its fundamental has amplitude ``4A/π``
    (+2.10 dB over a sine of amplitude ``A``) and its total power is ``A²``
    (+3.01 dB over the sine's ``A²/2``) — the two rows ADR 0006 D3 asserts.
    """
    n = n_samples(fs, dur_s)
    frac = np.mod(_cycles_constant(f_hz, fs, n) + phase_rad / TWO_PI, 1.0)
    a = amplitude(level_dbfs)
    return np.where(frac < 0.5, a, -a).astype(np.float64)


def two_tone(
    f1_hz: float, f2_hz: float, fs: int, dur_s: float, level_dbfs: float = 0.0, phase_rad: float = 0.0
) -> np.ndarray:
    """Two equal-amplitude sines, each at ``level_dbfs − 6.02 dB``, so the envelope peaks at ``level_dbfs``.

    Δf in bins is the caller's business (catalogue: 0.5 / 1 / 2 / 4 bins at
    N = 4096, 32 kHz — Harris 1978's resolution experiment, 05 #2).
    """
    n = n_samples(fs, dur_s)
    a = amplitude(level_dbfs) / 2.0
    return a * _sin_of_cycles(_cycles_constant(f1_hz, fs, n), phase_rad) + a * _sin_of_cycles(
        _cycles_constant(f2_hz, fs, n), phase_rad
    )


def dc_plus_sine(
    dc_offset: float, f_hz: float, fs: int, dur_s: float, level_dbfs: float = 0.0, phase_rad: float = 0.0
) -> np.ndarray:
    """A constant offset plus a sine — the software DC-removal vector (ADR 0006 D7)."""
    return dc_offset + sine(f_hz, fs, dur_s, level_dbfs, phase_rad)


def silence(fs: int, dur_s: float) -> np.ndarray:
    """All zeros — the noise-floor-in-dBFS vector (ADR 0006 D3's −200 dB floor)."""
    return np.zeros(n_samples(fs, dur_s), dtype=np.float64)


# --- noise ------------------------------------------------------------------


def white_noise(fs: int, dur_s: float, level_dbfs: float = -20.0, seed: int = 1) -> np.ndarray:
    """Gaussian white noise, seeded (``numpy.random.default_rng(seed)``), scaled to the RMS of a sine at ``level_dbfs``.

    The RMS is set exactly (divide by the measured RMS, then multiply), so the
    recorded ``rms`` is a property of the file and not of the draw. Clipped to
    ``[-1, 1]`` as a guard; at −20 dBFS (RMS 0.0707) a 6σ peak is 0.42 and the
    guard never fires — the catalogue records the count anyway.
    """
    n = n_samples(fs, dur_s)
    x = np.random.default_rng(seed).standard_normal(n)
    x *= rms_of_sine(level_dbfs) / np.sqrt(np.mean(x * x))
    return np.clip(x, -1.0, 1.0)


def pink_noise(fs: int, dur_s: float, level_dbfs: float = -20.0, seed: int = 1) -> np.ndarray:
    """Pink noise shaped in the frequency domain: ``|X[k]| = 1/sqrt(k)``, seeded uniform phases.

    Built, not filtered: every rfft bin ``k ≥ 1`` of the ``n``-point transform
    gets magnitude ``1/sqrt(f_k)`` (``f_k = k·fs/n``) and a phase drawn from
    ``default_rng(seed).uniform(0, 2π)``; DC and Nyquist are zero. So the
    ``n``-point periodogram falls at exactly −3.01 dB per octave **by
    construction** (PSD ∝ 1/f), which is what the "flat vs −3 dB/oct under PS vs
    PSD" trap in ``datasets/README.md`` needs to be exact. The amplitude
    distribution is not Gaussian (unit-magnitude bins), which is irrelevant to a
    slope test and stated so nobody reads a histogram of it as a bug. RMS set as
    for :func:`white_noise`.
    """
    n = n_samples(fs, dur_s)
    n_bins = n // 2 + 1
    k = np.arange(n_bins, dtype=np.float64)
    mag = np.zeros(n_bins)
    mag[1:] = 1.0 / np.sqrt(k[1:])
    if n % 2 == 0:
        mag[-1] = 0.0  # Nyquist bin must be real; dropping it is one bin in 48 000
    phase = np.random.default_rng(seed).uniform(0.0, TWO_PI, size=n_bins)
    phase[0] = 0.0
    spectrum = mag * np.exp(1j * phase)
    x = np.fft.irfft(spectrum, n=n)
    x *= rms_of_sine(level_dbfs) / np.sqrt(np.mean(x * x))
    return np.clip(x, -1.0, 1.0)


# --- sweeps and modulation --------------------------------------------------


def sweep_linear(
    f_start_hz: float, f_end_hz: float, fs: int, dur_s: float, level_dbfs: float = 0.0, phase_rad: float = 0.0
) -> np.ndarray:
    """Linear chirp: ``f(t) = f_start + (f_end − f_start)·t/T``; cycles ``f_start·t + (f_end − f_start)·t²/(2T)``."""
    n = n_samples(fs, dur_s)
    t = np.arange(n, dtype=np.float64) / fs
    cycles = f_start_hz * t + (f_end_hz - f_start_hz) * t * t / (2.0 * dur_s)
    return amplitude(level_dbfs) * _sin_of_cycles(cycles, phase_rad)


def sweep_exponential(
    f_start_hz: float, f_end_hz: float, fs: int, dur_s: float, level_dbfs: float = 0.0, phase_rad: float = 0.0
) -> np.ndarray:
    """Farina's exponential swept sine (05 #88): ``x(t) = sin(2π·f₁·T/ln(f₂/f₁) · (exp(t·ln(f₂/f₁)/T) − 1))``.

    Instantaneous frequency ``f₁·exp(t·ln(f₂/f₁)/T)`` — a constant number of
    cycles per octave, which is what lets the inverse filter separate harmonic
    distortion from the linear response (experiment 0001's instrument).
    """
    if f_start_hz <= 0.0 or f_end_hz <= 0.0:
        raise ValueError("exponential sweep needs strictly positive end frequencies")
    n = n_samples(fs, dur_s)
    t = np.arange(n, dtype=np.float64) / fs
    log_ratio = np.log(f_end_hz / f_start_hz)
    cycles = (f_start_hz * dur_s / log_ratio) * (np.exp(t * log_ratio / dur_s) - 1.0)
    return amplitude(level_dbfs) * _sin_of_cycles(cycles, phase_rad)


def vibrato_tone(
    f_hz: float,
    rate_hz: float,
    extent_cents: float,
    fs: int,
    dur_s: float,
    level_dbfs: float = 0.0,
    phase_rad: float = 0.0,
) -> np.ndarray:
    """FM tone by phase integral: ``f_inst(t) = f · 2^((extent/1200)·sin(2π·rate·t))``, cycles ``= ∫ f_inst dt``.

    ``extent_cents`` is the **peak** deviation: 100 = ±1 semitone. The integral
    is the trapezoid rule at ``fs`` (``scipy.integrate.cumulative_trapezoid``),
    whose error at 32 kHz for a 6 Hz, ±100 cent modulation of 220 Hz is
    **7.8×10⁻⁸ cycles** max over 3 s (measured 2026-08-21 against the same rule
    at 64×fs; Euler–Maclaurin gives ``h²/12·|f′(t) − f′(0)|`` ≈ 8×10⁻⁸) — a
    phase error of 3×10⁻⁵ degrees, far below anything the vibrato rows resolve.
    """
    n = n_samples(fs, dur_s)
    cycles = _cycles_from_instantaneous(_vibrato_instantaneous_hz(f_hz, rate_hz, extent_cents, fs, n), fs)
    return amplitude(level_dbfs) * _sin_of_cycles(cycles, phase_rad)


# --- glottal source + vocal tract -------------------------------------------


def rosenberg_pulse(period_fraction: np.ndarray, open_quotient: float, rise_fraction: float) -> np.ndarray:
    """Rosenberg (1971) trigonometric glottal-flow pulse (his model C), evaluated on a period fraction ``φ ∈ [0, 1)``.

    ``Tp = OQ·rise_fraction`` (opening, rising flow), ``Tn = OQ·(1 − rise_fraction)``
    (closing)::

        u(φ) = ½(1 − cos(π φ/Tp))          0   ≤ φ < Tp
        u(φ) = cos(π (φ − Tp)/(2 Tn))      Tp  ≤ φ < Tp + Tn
        u(φ) = 0                           otherwise  (closed phase)

    Continuous at ``Tp`` (both branches give 1) and at ``Tp + Tn`` (0); the slope
    discontinuity at closure is the excitation. Flow, not flow derivative — the
    radiation stage differentiates.
    """
    if not 0.0 < open_quotient <= 1.0:
        raise ValueError("open_quotient must be in (0, 1]")
    if not 0.0 < rise_fraction < 1.0:
        raise ValueError("rise_fraction must be in (0, 1)")
    tp = open_quotient * rise_fraction
    tn = open_quotient - tp
    phi = np.asarray(period_fraction, dtype=np.float64)
    u = np.zeros_like(phi)
    opening = phi < tp
    closing = (phi >= tp) & (phi < tp + tn)
    u[opening] = 0.5 * (1.0 - np.cos(np.pi * phi[opening] / tp))
    u[closing] = np.cos(np.pi * (phi[closing] - tp) / (2.0 * tn))
    return u


def klatt_resonator(f_hz: float, bw_hz: float, fs: int) -> tuple[np.ndarray, np.ndarray]:
    """Klatt (1980) digital resonator as ``(b, a)`` for ``scipy.signal.lfilter``.

    ``C = −exp(−2π·BW/fs)``, ``B = 2·exp(−π·BW/fs)·cos(2π·F/fs)``, ``A = 1 − B − C``;
    ``y[n] = A·x[n] + B·y[n−1] + C·y[n−2]`` ⇒ ``b = [A]``, ``a = [1, −B, −C]``.
    Unity gain at DC by construction of ``A``.
    """
    c = -np.exp(-TWO_PI * bw_hz / fs)
    b_coef = 2.0 * np.exp(-np.pi * bw_hz / fs) * np.cos(TWO_PI * f_hz / fs)
    a_coef = 1.0 - b_coef - c
    return np.array([a_coef]), np.array([1.0, -b_coef, -c])


def klatt_resonator_peak_hz(f_hz: float, bw_hz: float, fs: int) -> float:
    """Frequency at which a single Klatt resonator's ``|H(e^{jω})|`` actually peaks.

    The poles sit at ``r·e^{±jθ}`` with ``θ = 2πF/fs`` and ``r = exp(−πBW/fs)``; the
    conjugate pole pulls the magnitude peak toward DC, to ``cos ω = ((1+r²)/2r)·cos θ``.
    For ``F = 700, BW = 130`` at 32 kHz that is 696.9 Hz — 0.8 bins low at ``N = 8192``.
    So a **peak picker** on the response lands here, while a **pole estimator**
    (Burg/LPC — Praat's ``To Formant``) lands on ``F`` itself. Both are exact; the
    manifest records both so the right one is compared with the right row.
    """
    r = np.exp(-np.pi * bw_hz / fs)
    theta = TWO_PI * f_hz / fs
    c = ((1.0 + r * r) / (2.0 * r)) * np.cos(theta)
    if not -1.0 <= c <= 1.0:  # pragma: no cover — only for absurd BW/F combinations
        raise ValueError("resonator has no interior magnitude peak")
    return float(np.arccos(c) * fs / TWO_PI)


def vocal_tract(x: np.ndarray, formants_hz: Sequence[float], bandwidths_hz: Sequence[float], fs: int) -> np.ndarray:
    """Cascade of Klatt resonators, one per ``(F, BW)`` pair, applied in order."""
    if len(formants_hz) != len(bandwidths_hz):
        raise ValueError("one bandwidth per formant")
    y = np.asarray(x, dtype=np.float64)
    for f_hz, bw_hz in zip(formants_hz, bandwidths_hz, strict=True):
        b, a = klatt_resonator(f_hz, bw_hz, fs)
        y = lfilter(b, a, y)
    return y


def glottal_vowel(
    f0_hz: float,
    fs: int,
    dur_s: float,
    formants_hz: Sequence[float] = (700.0, 1220.0, 2600.0),
    bandwidths_hz: Sequence[float] = (130.0, 70.0, 160.0),
    open_quotient: float = 0.6,
    rise_fraction: float = 2.0 / 3.0,
    level_dbfs: float = -20.0,
    vibrato_rate_hz: float = 0.0,
    vibrato_extent_cents: float = 0.0,
) -> np.ndarray:
    """Rosenberg pulse train → first-difference radiation → cascade of Klatt resonators, peak-normalised to ``level_dbfs``.

    The pulse train is driven by a phase accumulator (``f0·n/fs mod 1``, or the
    integral of the vibrato-modulated f0 when ``vibrato_rate_hz > 0``), so f0 is
    exact and not rounded to an integer period (220 Hz at 32 kHz is 145.45
    samples). Because the source is harmonic, the *spectrum of the file* has
    its peaks at multiples of f0 and samples the tract response there; the
    resonator frequencies are the truth for a formant **estimator**, not for a
    peak picker on the WAV. The default F1–F3 / bandwidths are the catalogue's
    parameters for an /a/-like tract, not a claim about any speaker.
    """
    n = n_samples(fs, dur_s)
    if vibrato_rate_hz > 0.0 and vibrato_extent_cents != 0.0:
        cycles = _cycles_from_instantaneous(
            _vibrato_instantaneous_hz(f0_hz, vibrato_rate_hz, vibrato_extent_cents, fs, n), fs
        )
    else:
        cycles = _cycles_constant(f0_hz, fs, n)
    flow = rosenberg_pulse(np.mod(cycles, 1.0), open_quotient, rise_fraction)
    radiated = np.diff(flow, prepend=0.0)  # Klatt 1980 lip radiation: first difference
    y = vocal_tract(radiated, formants_hz, bandwidths_hz, fs)
    peak = float(np.max(np.abs(y)))
    if peak == 0.0:
        raise ValueError("vowel synthesis produced silence")
    return y * (amplitude(level_dbfs) / peak)
