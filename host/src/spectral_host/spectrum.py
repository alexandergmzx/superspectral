# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""The NumPy/SciPy reference spectrum — the host side of ADR 0006, transcribed.

This module is the oracle behind the `analyses.spectrum` block of a golden
manifest (host/golden/manifest.schema.yaml, schema "1.1") and the window-table
and per-bin magnitude rows of docs/validation/golden-files.md. It does not
reproduce the firmware's FFT; it computes what ADR 0006 says the answer *is*,
in float64, so that the device's float32 result can be compared to it under the
tolerance table. Every convention here is a two-sided contract (ADR 0009), so
every number is cited:

  * Windows (ADR 0006 D1): periodic cosine sums built from the COEFFICIENTS in
    protocols/specs/preset-schema.md §4.3 with
    `scipy.signal.windows.general_cosine(N, a, sym=False)` — never from a
    SciPy name (`get_window("nuttall")` is this table's `blackman_nuttall`,
    and this table's `nuttall` has no SciPy name; max |Δ| 0.0163).
  * Scaling (ADR 0006 D2, Heinzel 2002 — bibliography 05 #1):
        S1 = Σ w[j]     S2 = Σ w[j]²     NENBW = N·S2/S1²  [bins]
        PS  [FS²]    = 2·|X[k]|² / S1²        ENBW = NENBW·fs/N  [Hz]
        PSD [FS²/Hz] = 2·|X[k]|² / (fs·S2)    PS = PSD·ENBW
    factor 2 on k = 1 … N/2−1 only; DC and Nyquist are NOT doubled (the
    stricter reading of Heinzel eq. (23), which his text then waives and we do
    not). The transform itself is unnormalised (no 1/N, no 1/√N).
  * dBFS (ADR 0006 D3): a full-scale sine is 0 dBFS, `10·log10(PS/0.5)`; a
    full-scale square reads +2.10 dBFS on its fundamental bin and +3.01 dBFS in
    total power `Σ PS / NENBW`. PSD is a different axis, `10·log10(PSD/0.5)`
    labelled dBFS/Hz, never silently mixed with PS. Floor −200 dB.
    int16 → float is × 1/32768, once (ADR 0003 d.2); 32767 is admitted by the
    schema and differs by 0.00026 dB.
  * Frame grid (golden-files.md, "frame-grid trap"): the device frames from
    sample 0 with a hop; `frames_from_zero()` / `stft_power()` reproduce that
    grid so host and device are compared by time, never by frame index.

The schema enumerates more `normalization` × `scaling` pairs than ADR 0006
ratifies, so that a manifest can *record* whatever convention a set was built
with. `scale()` is therefore total over the enum; the pair the ADR ratifies is
(`S1`, `power_spectrum`) with (`S2`, `power_spectral_density`) as its density
form, and the others are defined here by the one rule stated in `scale()`'s
docstring — recorded conventions, not ratified ones.

Licence boundary (ADR 0004): this file imports only numpy, scipy and the
standard library; nothing from the Apache-2.0 tooling tree is reachable from here.

CLI — the window tables the device lane must reproduce (ADR 0006 D1 digests):

    uv run --project host python -m spectral_host.spectrum 4096 8192
    uv run --project host python -m spectral_host.spectrum --family hann 16

prints, per (family, N): the coefficients, S1, S2, NENBW summed over the float32
table (the device's, so the numbers are the device's) against the closed form,
and the sha256 over the N float32 little-endian samples — the value a
`windows[]` manifest entry carries and `verify.py` invariant 7 recomputes.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import sys
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import scipy.fft
from scipy.signal.windows import general_cosine

# --- the window coefficient table --------------------------------------------
#
# SINGLE SOURCE: protocols/specs/preset-schema.md §4.3, the table headed
# "`name` | a₀…a₄ | coherent_gain | coherent_gain_db | enbw_bins", copied
# digit for digit (ADR 0006 D1: "the coefficient table lives in ONE place").
# `rect` is the seventh family: it is admitted by the golden manifest's
# `$defs/window_family` for calibration tones only (ADR 0009 amendment, schema
# "1.1"; ADR 0006 consequence (c)) and is never a preset family —
# presets.schema.json's `window.name` enum lists six. Order: the six §4.3 rows,
# then `rect`. The host test `test_window_families_equal_the_section_4_3_table`
# parses that table and fails if a digit here drifts from it.
WINDOW_FAMILIES: dict[str, list[float]] = {
    "hann": [0.5, 0.5],
    "blackman": [0.42, 0.5, 0.08],
    "blackman_harris": [0.35875, 0.48829, 0.14128, 0.01168],
    "blackman_nuttall": [0.3635819, 0.4891775, 0.1365995, 0.0106411],
    "nuttall": [0.355768, 0.487396, 0.144232, 0.012604],
    "flat_top": [0.21557895, 0.41663158, 0.277263158, 0.083578947, 0.006947368],
    "rect": [1.0],
}

#: The families a PRESET may name — §4.3's six. `rect` is deliberately absent.
PRESET_WINDOW_FAMILIES: tuple[str, ...] = tuple(f for f in WINDOW_FAMILIES if f != "rect")

# --- the schema enums (manifest.schema.yaml `analyses.spectrum`) -------------
#
# Repeated here so SpectrumConfig can refuse a value the schema would refuse,
# without loading the schema at import time; test_config_keys_equal_schema_required_list
# asserts these tuples equal the schema's enums.
NORMALIZATIONS: tuple[str, ...] = ("none", "1/N", "1/sqrt(N)", "coherent_gain", "S1", "S2")
SCALINGS: tuple[str, ...] = ("power_spectrum", "power_spectral_density", "linear_spectrum", "linear_spectral_density")
DBFS_REFERENCES: tuple[str, ...] = ("sine", "square")
INT16_SCALES: tuple[int, ...] = (32768, 32767)
DTYPES: tuple[str, ...] = ("float32", "float64")

#: The scalings that are per-Hz densities (Heinzel's PSD and LSD).
DENSITY_SCALINGS: frozenset[str] = frozenset({"power_spectral_density", "linear_spectral_density"})

#: Reference power, in FS², of the signal that reads 0 dBFS (ADR 0006 D3 and the
#: schema's `dbfs_reference`): a full-scale sine has mean power A²/2 = 0.5; a
#: full-scale square has mean power 1.0, which puts the sine at −3.01 dBFS.
REFERENCE_POWER: dict[str, float] = {"sine": 0.5, "square": 1.0}

#: ADR 0006 D3: the display floor.
DEFAULT_FLOOR_DB: float = -200.0

#: ADR 0006 D3 / ADR 0003 d.2: the project's int16 seam.
DEFAULT_INT16_SCALE: int = 32768


# --- windows ---------------------------------------------------------------


def window_coefficients(family: str) -> list[float]:
    """The §4.3 coefficients of `family`, as a fresh list (the table itself is never handed out)."""
    try:
        return list(WINDOW_FAMILIES[family])
    except KeyError:
        raise ValueError(f"unknown window family {family!r}; expected one of {list(WINDOW_FAMILIES)}") from None


def _check_window_length(n: int) -> None:
    # manifest.schema.yaml: `windows[].n` and `window_length_samples` have minimum 2.
    if not isinstance(n, (int, np.integer)) or isinstance(n, bool) or n < 2:
        raise ValueError(f"window length must be an integer >= 2 (manifest schema), got {n!r}")


def window_float64(family: str, n: int) -> np.ndarray:
    """The periodic window in float64: `general_cosine(n, a, sym=False)` (ADR 0006 D1).

    This is the window the float64 reference spectrum multiplies by. `window_table()`
    is its float32 rounding — what the device stores and what the digest hashes.
    """
    _check_window_length(n)
    return np.asarray(general_cosine(int(n), window_coefficients(family), sym=False), dtype=np.float64)


def window_table(family: str, n: int) -> np.ndarray:
    """The float32 little-endian window table for (family, n) — the digest's input.

    Identical to the float64 window rounded once to float32, which is the
    representation the device holds in memory (`spectral_window_fill()`); the
    manifest schema's `windows[]` description fixes this as the hashed form.
    """
    return window_float64(family, n).astype("<f4")


def window_table_sha256(family: str, n: int) -> str:
    """sha256 hex over the N float32 little-endian samples of the periodic window.

    The recipe of manifest.schema.yaml `windows[].sha256` and of
    docs/validation/golden-files.md's "exact" digest row, verbatim:
    `hashlib.sha256(np.asarray(w, dtype="<f4").tobytes()).hexdigest()`.
    """
    return hashlib.sha256(window_table(family, n).tobytes()).hexdigest()


def window_sums(w: np.ndarray) -> tuple[float, float, float]:
    """(S1, S2, NENBW) of a window, in float64: S1 = Σw, S2 = Σw², NENBW = N·S2/S1² [bins] (Heinzel 2002)."""
    w64 = np.asarray(w, dtype=np.float64)
    if w64.ndim != 1 or w64.size < 1:
        raise ValueError("window must be a non-empty 1-D array")
    s1 = float(np.sum(w64))
    s2 = float(np.sum(w64 * w64))
    if s1 == 0.0:
        raise ValueError("window sums to zero; NENBW is undefined")
    nenbw = w64.size * s2 / (s1 * s1)
    return s1, s2, nenbw


def nenbw_closed_form(coefficients: Sequence[float]) -> float:
    """NENBW of a PERIODIC cosine-sum window from its coefficients alone.

    ADR 0006 D2: orthogonality gives S1 = N·a₀ and S2 = N·(a₀² + Σ_{k≥1} a_k²/2)
    exactly, hence NENBW = (a₀² + Σ_{k≥1} a_k²/2)/a₀² — the `enbw_bins` each
    preset ships (preset-schema.md §4.3). The symmetric form does not satisfy
    this (hann at N = 4096 gives 1.500366, not 1.5).
    """
    a = [float(c) for c in coefficients]
    if not a or a[0] == 0.0:
        raise ValueError("a cosine-sum window needs a non-zero a0")
    return (a[0] ** 2 + sum(c * c for c in a[1:]) / 2.0) / a[0] ** 2


def enbw_hz(nenbw: float, fs: float, n: int) -> float:
    """Equivalent noise bandwidth in Hz: ENBW = NENBW · fs / N (ADR 0006 D2; preset-schema.md §4.4 `enbw_hz`)."""
    if fs <= 0 or n <= 0:
        raise ValueError("fs and n must be positive")
    return float(nenbw) * float(fs) / float(n)


# --- the configuration block --------------------------------------------------


@dataclass(frozen=True)
class SpectrumConfig:
    """The `analyses.spectrum` block of a golden manifest — exactly its nine keys, in schema order.

    Every field is required by the schema (ADR 0009 item 1(a): an unstated
    convention is not a value), so there are no defaults here. Construct it
    from a manifest with `SpectrumConfig(**block)` and write it back with
    `.asdict()`; a key the schema does not list is a TypeError on the way in.
    """

    window: str
    window_length_samples: int
    fftbins: bool
    fft_size: int
    normalization: str
    scaling: str
    dbfs_reference: str
    int16_scale: int
    dtype: str

    def __post_init__(self) -> None:
        if self.window not in WINDOW_FAMILIES:
            raise ValueError(f"window must be a §4.3 family or 'rect', got {self.window!r}")
        _check_window_length(self.window_length_samples)
        if not isinstance(self.fftbins, bool):
            raise ValueError("fftbins must be a bool")
        if not isinstance(self.fft_size, (int, np.integer)) or isinstance(self.fft_size, bool) or self.fft_size < 2:
            raise ValueError(f"fft_size must be an integer >= 2, got {self.fft_size!r}")
        if self.fft_size < self.window_length_samples:
            raise ValueError("fft_size < window_length_samples would truncate the window; only zero-padding is defined")
        if self.fft_size % 2:
            raise ValueError("fft_size must be even: the DC/Nyquist rule of ADR 0006 D2 is stated for an even transform")
        if self.normalization not in NORMALIZATIONS:
            raise ValueError(f"normalization must be one of {NORMALIZATIONS}, got {self.normalization!r}")
        if self.scaling not in SCALINGS:
            raise ValueError(f"scaling must be one of {SCALINGS}, got {self.scaling!r}")
        if self.dbfs_reference not in DBFS_REFERENCES:
            raise ValueError(f"dbfs_reference must be one of {DBFS_REFERENCES}, got {self.dbfs_reference!r}")
        if self.int16_scale not in INT16_SCALES or isinstance(self.int16_scale, bool):
            raise ValueError(f"int16_scale must be one of {INT16_SCALES}, got {self.int16_scale!r}")
        if self.dtype not in DTYPES:
            raise ValueError(f"dtype must be one of {DTYPES}, got {self.dtype!r}")

    def asdict(self) -> dict[str, object]:
        """The block as the manifest writes it: the nine keys in schema order."""
        return dataclasses.asdict(self)

    @property
    def level_unit(self) -> str:
        """The unit of `reference_spectrum()`'s level column under this config (ADR 0006 D3)."""
        return "dBFS/Hz" if self.scaling in DENSITY_SCALINGS else "dBFS"


#: The convention ADR 0006 ratifies, as the worked example of manifest.schema.yaml
#: writes it — the one every tier-0 spectrum reference uses unless a set says otherwise.
ADR_0006_DEFAULT = SpectrumConfig(
    window="hann",
    window_length_samples=4096,
    fftbins=True,
    fft_size=4096,
    normalization="S1",
    scaling="power_spectrum",
    dbfs_reference="sine",
    int16_scale=DEFAULT_INT16_SCALE,
    dtype="float64",
)


# --- the pipeline, one seam per function ----------------------------------------


def int16_to_float(x: np.ndarray, int16_scale: int = DEFAULT_INT16_SCALE) -> np.ndarray:
    """int16 PCM → float64 in [−1, 1): `x / int16_scale`, applied exactly once (ADR 0003 d.2, ADR 0006 D3).

    Refuses anything that is not int16: a float array passed here would be
    scaled twice and read −90.3 dB low, which is the kind of error that looks
    like a microphone problem.
    """
    arr = np.asarray(x)
    if arr.dtype != np.int16:
        raise TypeError(f"int16_to_float expects int16 samples, got dtype {arr.dtype}")
    if int16_scale not in INT16_SCALES:
        raise ValueError(f"int16_scale must be one of {INT16_SCALES}, got {int16_scale!r}")
    return arr.astype(np.float64) / float(int16_scale)


def rfft_unnormalised(xw: np.ndarray, fft_size: int) -> np.ndarray:
    """The one-sided DFT of a windowed frame, UNNORMALISED (no 1/N, no 1/√N) — ADR 0006 D2.

    `scipy.fft.rfft(xw, n=fft_size)` with the default `norm="backward"`. The
    frame is zero-padded when `fft_size` exceeds its length; truncation is
    refused, because `rfft` would otherwise silently drop samples (and the
    window with them).
    """
    xw = np.asarray(xw)
    if xw.ndim != 1:
        raise ValueError("rfft_unnormalised takes one frame; use stft_power for many")
    if fft_size < xw.size:
        raise ValueError(f"fft_size {fft_size} < frame length {xw.size}: truncation is not a convention of ADR 0006")
    if fft_size % 2:
        raise ValueError("fft_size must be even (ADR 0006 D2 states the DC/Nyquist rule for an even transform)")
    return scipy.fft.rfft(xw, n=int(fft_size), norm="backward")


def one_sided_power(X: np.ndarray) -> np.ndarray:
    """|X[k]|² with the factor 2 on bins 1 … N/2−1 only — DC (k = 0) and Nyquist (k = N/2) are NOT doubled.

    ADR 0006 D2's deliberate divergence from Heinzel's waiver: the two edge
    bins have no mirror image in the two-sided spectrum, so doubling them
    overstates their power by 3.01 dB.
    """
    X = np.asarray(X)
    if X.shape[-1] < 2:
        raise ValueError("a one-sided spectrum of an even transform has at least two bins (DC and Nyquist)")
    p = (X.real.astype(np.float64) ** 2) + (X.imag.astype(np.float64) ** 2)
    p[..., 1:-1] *= 2.0
    return p


def scale(
    X: np.ndarray,
    s1: float,
    s2: float,
    fs: float,
    normalization: str,
    scaling: str,
) -> np.ndarray:
    """Turn an unnormalised one-sided DFT into the quantity `scaling` names, under `normalization`.

    `X` has N/2+1 bins of an even-length-N transform (last axis). The two
    stages are:

    1. `normalization` fixes the divisor D² applied to the one-sided power
       2|X|² (DC/Nyquist undoubled):
           none → 1,  1/N → N²,  1/sqrt(N) → N,  coherent_gain → S1²,
           S1 → S1²,  S2 → S2.
       `S1` gives Heinzel's PS = 2|X|²/S1² directly; `S2` gives fs·PSD =
       2|X|²/S2 directly. `coherent_gain` divides by N·a₀, which for a periodic
       cosine-sum window IS S1 (ADR 0006 D2 orthogonality), so it coincides with
       `S1` here — the enum carries both because manifests record the name a
       tool used, not because they differ. `none`, `1/N` and `1/sqrt(N)` leave
       the window's gain in the result (a tone reads a₀² low); they exist so a
       manifest can name an uncalibrated convention, not for use.
    2. `scaling` converts between the power spectrum and the density with
       Heinzel's PS = PSD·ENBW, ENBW = S2·fs/S1² [Hz] (= NENBW·fs/N, the N
       cancelling), and takes the square root for the linear forms:
           power_spectrum → PS,  power_spectral_density → PSD,
           linear_spectrum → √PS,  linear_spectral_density → √PSD.

    So (`S1`, `power_spectrum`) is ADR 0006 D2's PS and (`S2`,
    `power_spectral_density`) its PSD; the two normalisations agree on both
    quantities because the ENBW identity is exact. Units: FS² (PS), FS²/Hz
    (PSD), FS (LS), FS/√Hz (LSD) for an input scaled by `int16_to_float`.
    """
    if normalization not in NORMALIZATIONS:
        raise ValueError(f"normalization must be one of {NORMALIZATIONS}, got {normalization!r}")
    if scaling not in SCALINGS:
        raise ValueError(f"scaling must be one of {SCALINGS}, got {scaling!r}")
    if s1 <= 0 or s2 <= 0 or fs <= 0:
        raise ValueError("S1, S2 and fs must be positive")
    p2 = one_sided_power(X)
    n = 2 * (p2.shape[-1] - 1)
    divisor_sq = {
        "none": 1.0,
        "1/N": float(n) ** 2,
        "1/sqrt(N)": float(n),
        "coherent_gain": s1 * s1,
        "S1": s1 * s1,
        "S2": s2,
    }[normalization]
    p = p2 / divisor_sq
    enbw = s2 * fs / (s1 * s1)
    if normalization == "S2":
        psd = p / fs
        ps = psd * enbw
    else:
        ps = p
        psd = ps / enbw
    if scaling == "power_spectrum":
        return ps
    if scaling == "power_spectral_density":
        return psd
    if scaling == "linear_spectrum":
        return np.sqrt(ps)
    return np.sqrt(psd)


def _db_of_ratio(power_ratio: np.ndarray, floor_db: float) -> np.ndarray:
    with np.errstate(divide="ignore"):
        db = 10.0 * np.log10(np.asarray(power_ratio, dtype=np.float64))
    return np.maximum(db, float(floor_db))


def to_dbfs(
    v: np.ndarray,
    dbfs_reference: str,
    scaling: str,
    enbw_hz: float | None = None,
    floor_db: float = DEFAULT_FLOOR_DB,
) -> np.ndarray:
    """Level in dBFS — dB re the POWER of a full-scale sine (0.5 FS²) or square (1.0 FS²): `10·log10(PS/ref)`.

    ADR 0006 D3. `v` is whatever `scaling` says it is. A spectrum (PS or its
    square root) is converted directly; a DENSITY is first brought onto the
    PS axis with Heinzel's PS = PSD·ENBW, which is why `enbw_hz` is REQUIRED
    for the two density scalings and REFUSED for the two spectrum scalings —
    passing it where it does nothing is the "silently mixed" case D3 forbids.
    For the density axis itself (dBFS/Hz) use `to_dbfs_per_hz()`.

    Bins at or below `10^(floor_db/10)·ref` (including exact zeros) read
    `floor_db`; D3's floor is −200 dB.
    """
    if dbfs_reference not in REFERENCE_POWER:
        raise ValueError(f"dbfs_reference must be one of {DBFS_REFERENCES}, got {dbfs_reference!r}")
    if scaling not in SCALINGS:
        raise ValueError(f"scaling must be one of {SCALINGS}, got {scaling!r}")
    v = np.asarray(v, dtype=np.float64)
    if scaling in DENSITY_SCALINGS:
        if enbw_hz is None or enbw_hz <= 0:
            raise ValueError(f"{scaling} is per Hz: to_dbfs needs enbw_hz > 0 to reach the PS axis (PS = PSD·ENBW)")
        ps = (v if scaling == "power_spectral_density" else v * v) * float(enbw_hz)
    else:
        if enbw_hz is not None:
            raise ValueError(f"{scaling} is not a density; enbw_hz must be None (ADR 0006 D3: axes are never mixed)")
        ps = v if scaling == "power_spectrum" else v * v
    return _db_of_ratio(ps / REFERENCE_POWER[dbfs_reference], floor_db)


def to_dbfs_per_hz(
    v: np.ndarray,
    dbfs_reference: str,
    scaling: str,
    floor_db: float = DEFAULT_FLOOR_DB,
) -> np.ndarray:
    """The PSD display axis of ADR 0006 D3: `10·log10(PSD/ref)`, labelled dBFS/Hz.

    Density scalings only. A full-scale sine does NOT read 0 here — its peak
    bin reads `10·log10(1/ENBW_Hz)` — which is the point: this is a different
    axis with a different unit, and it is never shown on the same readout as
    dBFS. The floor is the same −200 dB.
    """
    if dbfs_reference not in REFERENCE_POWER:
        raise ValueError(f"dbfs_reference must be one of {DBFS_REFERENCES}, got {dbfs_reference!r}")
    if scaling not in DENSITY_SCALINGS:
        raise ValueError(f"to_dbfs_per_hz is for the density scalings {sorted(DENSITY_SCALINGS)}, got {scaling!r}")
    v = np.asarray(v, dtype=np.float64)
    psd = v if scaling == "power_spectral_density" else v * v
    return _db_of_ratio(psd / REFERENCE_POWER[dbfs_reference], floor_db)


# --- the reference spectrum -------------------------------------------------------


def _window_for(cfg: SpectrumConfig) -> np.ndarray:
    if not cfg.fftbins:
        raise ValueError(
            "fftbins=false asks for a symmetric window; ADR 0006 D1 rejects that form outright "
            "(NENBW no longer equals the closed form) and this oracle does not build it"
        )
    w = window_float64(cfg.window, cfg.window_length_samples)
    return w.astype(np.float32) if cfg.dtype == "float32" else w


def _frame_to_power(frame: np.ndarray, w: np.ndarray, s1: float, s2: float, fs: float, cfg: SpectrumConfig) -> np.ndarray:
    """One float frame (already /int16_scale) → linear `cfg.scaling` values, accumulated in `cfg.dtype`."""
    acc = np.float32 if cfg.dtype == "float32" else np.float64
    xw = frame.astype(acc) * w.astype(acc)
    X = rfft_unnormalised(xw, cfg.fft_size)
    return scale(X, s1, s2, fs, cfg.normalization, cfg.scaling)


def reference_frequencies(fs: float, fft_size: int) -> np.ndarray:
    """Bin centre frequencies k·fs/N for k = 0 … N/2, float64."""
    return scipy.fft.rfftfreq(int(fft_size), d=1.0 / float(fs)).astype(np.float64)


def reference_spectrum(samples_int16: np.ndarray, fs: float, cfg: SpectrumConfig) -> np.ndarray:
    """The golden `spectrum` array: shape [N/2+1, 2], float64, columns [frequency_hz, level].

    Computed on samples [0, N) with N = `cfg.window_length_samples` — the first
    device frame, from sample 0 (the frame-grid trap). Fewer samples than N is
    an error, not a zero-pad: a golden file of a padded frame would pin a
    different signal than its input sha256 names.

    The level column is dBFS (`to_dbfs`) for the spectrum scalings and dBFS/Hz
    (`to_dbfs_per_hz`) for the density scalings — `cfg.level_unit` says which,
    and the manifest's `units` must carry it (ADR 0006 D3: two axes, never
    mixed). The reference `int16_scale`, window, normalisation and accumulation
    width are all `cfg`'s; nothing here has a default the schema does not state.
    """
    n = cfg.window_length_samples
    samples = np.asarray(samples_int16)
    if samples.ndim != 1:
        raise ValueError("reference_spectrum takes one mono channel")
    if samples.size < n:
        raise ValueError(f"need at least window_length_samples = {n} samples, got {samples.size}")
    x = int16_to_float(samples[:n], cfg.int16_scale)
    w = _window_for(cfg)
    s1, s2, nenbw = window_sums(w)
    power = _frame_to_power(x, w, s1, s2, fs, cfg)
    if cfg.scaling in DENSITY_SCALINGS:
        level = to_dbfs_per_hz(power, cfg.dbfs_reference, cfg.scaling)
    else:
        level = to_dbfs(power, cfg.dbfs_reference, cfg.scaling)
    out = np.empty((cfg.fft_size // 2 + 1, 2), dtype=np.float64)
    out[:, 0] = reference_frequencies(fs, cfg.fft_size)
    out[:, 1] = level
    return out


# --- the device frame grid ------------------------------------------------------


def frames_from_zero(x: np.ndarray, n: int, hop: int) -> np.ndarray:
    """Frames of length `n` starting at sample 0, `hop` samples apart, as a [n_frames, n] array.

    The device's grid (golden-files.md "frame-grid trap"): no centring, no
    padding — frame k covers samples [k·hop, k·hop + n), and a trailing partial
    frame is dropped, never zero-padded. Frame k's START time is k·hop/fs
    (`frame_start_times`); compare by time, never by index.
    """
    x = np.asarray(x)
    if x.ndim != 1:
        raise ValueError("frames_from_zero takes one channel")
    _check_window_length(n)
    if not isinstance(hop, (int, np.integer)) or isinstance(hop, bool) or hop < 1:
        raise ValueError(f"hop must be an integer >= 1, got {hop!r}")
    n_frames = 0 if x.size < n else 1 + (x.size - n) // hop
    starts = np.arange(n_frames) * hop
    idx = starts[:, None] + np.arange(n)[None, :]
    return x[idx] if n_frames else np.empty((0, n), dtype=x.dtype)


def frame_start_times(n_frames: int, hop: int, fs: float) -> np.ndarray:
    """Start time in seconds of each frame on the device grid: k·hop/fs."""
    return np.arange(int(n_frames), dtype=np.float64) * (float(hop) / float(fs))


def stft_power(
    samples_int16: np.ndarray,
    fs: float,
    cfg: SpectrumConfig,
    hop: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-frame LINEAR `cfg.scaling` values on the device grid: (frame_start_s, frequency_hz, power[n_frames, N/2+1]).

    Linear, not dB, on purpose: anything that averages or smooths across
    frames does so in PS/PSD (ADR 0006 D8, Heinzel §10) — the log-domain mean
    of a noise bin is 2.51 dB low. Convert with `to_dbfs` / `to_dbfs_per_hz`
    afterwards. Frame k covers samples [k·hop, k·hop + N); see `frames_from_zero`.
    """
    frames = frames_from_zero(np.asarray(samples_int16), cfg.window_length_samples, hop)
    w = _window_for(cfg)
    s1, s2, _nenbw = window_sums(w)
    power = np.empty((frames.shape[0], cfg.fft_size // 2 + 1), dtype=np.float64)
    for k in range(frames.shape[0]):
        x = int16_to_float(frames[k], cfg.int16_scale)
        power[k] = _frame_to_power(x, w, s1, s2, fs, cfg)
    return frame_start_times(frames.shape[0], hop, fs), reference_frequencies(fs, cfg.fft_size), power


# --- CLI -------------------------------------------------------------------------


def _format_row(family: str, n: int) -> str:
    w = window_table(family, n)
    s1, s2, nenbw = window_sums(w)
    closed = nenbw_closed_form(WINDOW_FAMILIES[family])
    coeffs = ", ".join(repr(c) for c in WINDOW_FAMILIES[family])
    return (
        f"{family:<17} N={n:<6} a=[{coeffs}]\n"
        f"{'':<17} float32 table: S1={s1:.10g} S2={s2:.10g} NENBW={nenbw:.9f} (closed form {closed:.9f})\n"
        f"{'':<17} sha256={window_table_sha256(family, n)}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m spectral_host.spectrum",
        description="Print the periodic window tables of ADR 0006 D1: coefficients, S1/S2/NENBW and the float32 sha256 digest.",
    )
    parser.add_argument("sizes", metavar="N", type=int, nargs="+", help="window length(s) in samples")
    parser.add_argument(
        "--family",
        action="append",
        choices=list(WINDOW_FAMILIES),
        help="restrict to one family (repeatable); default: all seven",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    families = args.family or list(WINDOW_FAMILIES)
    try:
        for n in args.sizes:
            for family in families:
                print(_format_row(family, n))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
