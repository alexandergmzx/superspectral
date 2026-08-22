# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""The H0 Tier-0 catalogue: every named signal, its parameters, and its derived ground truth.

All entries are 3.0 s. Nineteen are at 32 kHz — the watch's default rate
(ADR 0003) and the only rate any shipped preset uses — and two are 48 kHz
**host-only twins** (``sine_440_m20dBFS_48k``, ``vowel_a_f0_220_48k``) that
exercise the host's 48 kHz path; nothing on the watch may depend on 48 kHz
until experiment 0001 clause 4 passes (ADR 0003 decision 5, roadmap T3).

Bin arithmetic is quoted for ``N = 4096`` — the watch's default analysis size
(ADR 0006 D5/D6: "real-4096, the default analysis size") — at 32 kHz, where one
bin is ``32000/4096 = 7.8125 Hz``:

* ``437.5 Hz = 56 × 7.8125`` and ``1000 Hz = 128 × 7.8125`` are **on-bin**;
* ``440 Hz = 56.32 bins`` is **off-bin** (the schema's worked-example input,
  ``sine_440_0dBFS_32k``, keeps its name);
* the two-tone pairs put the second tone ``0.5 / 1 / 2 / 4`` bins above 1000 Hz.

Vowel parameters (``F1–F3 = 700/1220/2600 Hz``, ``BW = 130/70/160 Hz``,
``OQ = 0.6``) are **parameters of this catalogue**, chosen to look like an
/a/-like tract so the estimator rows have something to estimate; they are not
a claim about any speaker or corpus. Levels per family are in
:mod:`synth_signals.signals`'s docstring and repeated per entry below.

Not a CLI module; ``python -m synth_signals list`` prints this table.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from . import quantise, signals, wavio

#: Watch default analysis size the bin truths are quoted for (ADR 0006 D5/D6).
N_REF = 4096
#: The watch default sample rate (ADR 0003) and its 48 kHz host-only twin.
FS_WATCH = 32000
FS_HOST_TWIN = 48000
#: One duration for the whole set.
DUR_S = 3.0
#: −3.01 dB per octave, what 1/f power is in dB per doubling of f.
PINK_SLOPE_DB_PER_OCTAVE = -10.0 * np.log10(2.0)
#: ADR 0006 D3's two square-wave rows: fundamental ``4/π`` over a sine (+2.10 dB), total power +3.01 dB.
SQUARE_FUNDAMENTAL_DB = 20.0 * np.log10(4.0 / np.pi)
SQUARE_TOTAL_POWER_DB = 10.0 * np.log10(2.0)


def bin_hz(fs: int, n: int = N_REF) -> float:
    return fs / n


@dataclass(frozen=True)
class Entry:
    """One catalogue row: what to call, with what, and why it is in the set."""

    name: str
    generator: str
    fs: int
    params: dict[str, Any] = field(default_factory=dict)
    #: Validation rows this file serves (names from datasets/README.md's Tier-0 table
    #: and docs/validation/golden-files.md's tolerance table), injection path only.
    use: tuple[str, ...] = ()
    dur_s: float = DUR_S
    host_only: bool = False
    note: str = ""

    def render(self) -> np.ndarray:
        """Float64 samples on ``[-1, 1]``."""
        fn = getattr(signals, self.generator)
        return fn(fs=self.fs, dur_s=self.dur_s, **self.params)


@dataclass(frozen=True)
class Built:
    """A rendered entry: float samples, int16 samples, WAV bytes, sha256."""

    entry: Entry
    x: np.ndarray
    s: np.ndarray
    data: bytes
    sha256: str

    @property
    def filename(self) -> str:
        return f"{self.entry.name}.wav"


def build(entry: Entry) -> Built:
    x = entry.render()
    s = quantise.to_int16(x)
    data = wavio.wav_bytes(s, entry.fs)
    return Built(entry, x, s, data, hashlib.sha256(data).hexdigest())


# --- the list ---------------------------------------------------------------


def _sine(name: str, f_hz: float, level_dbfs: float, fs: int = FS_WATCH, **kw: Any) -> Entry:
    return Entry(
        name,
        "sine",
        fs,
        {"f_hz": f_hz, "level_dbfs": level_dbfs, "phase_rad": 0.0},
        use=("peak bin and interpolated peak (≤ 3 cents)", "leakage shape per window", "dBFS reference"),
        **kw,
    )


def _two_tone(delta_bins: float) -> Entry:
    tag = str(delta_bins).replace(".", "p").removesuffix("p0")
    f1 = 1000.0
    return Entry(
        f"twotone_1000_d{tag}bin_32k",
        "two_tone",
        FS_WATCH,
        {"f1_hz": f1, "f2_hz": f1 + delta_bins * bin_hz(FS_WATCH), "level_dbfs": -20.0, "phase_rad": 0.0},
        use=("two-tone resolution vs window (Harris 1978, 05 #2)",),
        note=f"Δf = {delta_bins} bins at N = {N_REF}",
    )


_VOWEL = {
    "f0_hz": 220.0,
    "formants_hz": (700.0, 1220.0, 2600.0),
    "bandwidths_hz": (130.0, 70.0, 160.0),
    "open_quotient": 0.6,
    "rise_fraction": 2.0 / 3.0,
    "level_dbfs": -20.0,
}

CATALOGUE: tuple[Entry, ...] = (
    _sine("sine_437p5_m20dBFS_32k", 437.5, -20.0, note="on-bin: 56 × 7.8125 Hz"),
    _sine("sine_440_0dBFS_32k", 440.0, 0.0, note="off-bin; full scale — clipping-flag vector by design; schema worked-example input"),
    _sine("sine_440_m1dBFS_32k", 440.0, -1.0, note="off-bin; 1 dB under full scale — must NOT trip the clipping flag"),
    _sine("sine_440_m20dBFS_32k", 440.0, -20.0, note="off-bin"),
    _sine("sine_440_m60dBFS_32k", 440.0, -60.0, note="off-bin; 32.8 LSB amplitude — quantisation noise floor visible"),
    _sine("sine_1000_m20dBFS_32k", 1000.0, -20.0, note="on-bin: 128 × 7.8125 Hz"),
    Entry(
        "square_1000_0dBFS_32k",
        "square",
        FS_WATCH,
        {"f_hz": 1000.0, "level_dbfs": 0.0, "phase_rad": 0.0},
        use=("dBFS reference: square vs sine (ADR 0006 D3 +2.10 dB per-bin / +3.01 dB total)", "clipping flag"),
        note="on-bin fundamental; every sample at a rail — clipping-flag vector by design",
    ),
    _two_tone(0.5),
    _two_tone(1.0),
    _two_tone(2.0),
    _two_tone(4.0),
    Entry(
        "white_m20dBFS_seed1_32k",
        "white_noise",
        FS_WATCH,
        {"level_dbfs": -20.0, "seed": 1},
        use=("flat PS vs PSD under the stated normalisation",),
    ),
    Entry(
        "pink_m20dBFS_seed1_32k",
        "pink_noise",
        FS_WATCH,
        {"level_dbfs": -20.0, "seed": 1},
        use=("−3 dB/oct PSD under the stated normalisation (PS vs PSD trap)",),
    ),
    Entry(
        "sweep_lin_20_16000_32k",
        "sweep_linear",
        FS_WATCH,
        {"f_start_hz": 20.0, "f_end_hz": 16000.0, "level_dbfs": -20.0, "phase_rad": 0.0},
        use=("tracked peak follows the sweep",),
    ),
    Entry(
        "sweep_exp_20_16000_32k",
        "sweep_exponential",
        FS_WATCH,
        {"f_start_hz": 20.0, "f_end_hz": 16000.0, "level_dbfs": -20.0, "phase_rad": 0.0},
        use=("tracked peak follows the sweep", "in-situ transfer-function instrument (Farina 2000, 05 #88; experiment 0001)"),
    ),
    Entry(
        "vowel_a_f0_220_32k",
        "glottal_vowel",
        FS_WATCH,
        dict(_VOWEL),
        use=("f0 estimator vs exact f0", "F1/F2 estimator vs exact resonator frequencies"),
    ),
    Entry(
        "vowel_a_vibrato_220_6hz_100c_32k",
        "glottal_vowel",
        FS_WATCH,
        {**_VOWEL, "vibrato_rate_hz": 6.0, "vibrato_extent_cents": 100.0},
        use=("vibrato rate/extent readout (±1 semitone at 6 Hz)", "f0 tracking under FM"),
    ),
    Entry(
        "dc_0p1_plus_sine_440_m20dBFS_32k",
        "dc_plus_sine",
        FS_WATCH,
        {"dc_offset": 0.1, "f_hz": 440.0, "level_dbfs": -20.0, "phase_rad": 0.0},
        use=("software DC removal (ADR 0006 D7)",),
    ),
    Entry("silence_32k", "silence", FS_WATCH, {}, use=("noise floor in dBFS (−200 dB floor, ADR 0006 D3)",)),
    _sine("sine_440_m20dBFS_48k", 440.0, -20.0, fs=FS_HOST_TWIN, host_only=True, note="host-only twin (T3 gate)"),
    Entry(
        "vowel_a_f0_220_48k",
        "glottal_vowel",
        FS_HOST_TWIN,
        dict(_VOWEL),
        use=("f0 estimator vs exact f0", "F1/F2 estimator vs exact resonator frequencies"),
        host_only=True,
        note="host-only twin (T3 gate)",
    ),
)

NAMES: tuple[str, ...] = tuple(e.name for e in CATALOGUE)
_BY_NAME = {e.name: e for e in CATALOGUE}
if len(_BY_NAME) != len(CATALOGUE):  # pragma: no cover — a duplicate name is a programming error
    raise RuntimeError("duplicate catalogue names")


def by_name(name: str) -> Entry:
    try:
        return _BY_NAME[name]
    except KeyError:
        raise KeyError(f"no catalogue entry {name!r}; see `python -m synth_signals list`") from None


# --- ground truth -----------------------------------------------------------


def _plain(v: Any) -> Any:
    """YAML-friendly scalars/lists (tuples → lists, numpy → Python)."""
    if isinstance(v, (tuple, list)):
        return [_plain(i) for i in v]
    if isinstance(v, np.generic):
        return v.item()
    return v


def ground_truth(built: Built) -> dict[str, Any]:
    """Exact parameters plus the derived values a test can assert, for one built entry."""
    e = built.entry
    p = {k: _plain(v) for k, v in e.params.items()}
    truth: dict[str, Any] = {
        "generator": f"synth_signals.signals.{e.generator}",
        "parameters": p,
        "samples": int(built.s.size),
        "host_only": e.host_only,
        "clip_samples": quantise.clipped_sample_count(built.s),
        "clip_threshold": quantise.CLIP_THRESHOLD,
        "int16_min": int(built.s.min()),
        "int16_max": int(built.s.max()),
    }
    truth["clip_flag"] = truth["clip_samples"] > 0
    derived: dict[str, Any] = {}
    g = e.generator
    bw = bin_hz(e.fs)
    if g in ("sine", "dc_plus_sine"):
        derived["level_convention"] = "amplitude"
        derived["amplitude"] = signals.amplitude(p["level_dbfs"])
        derived["bin_n4096"] = p["f_hz"] / bw
        derived["on_bin_n4096"] = float(p["f_hz"] / bw).is_integer()
        derived["peak_bin_dbfs_expected"] = p["level_dbfs"]
    if g == "square":
        derived["level_convention"] = "amplitude"
        derived["bin_n4096"] = p["f_hz"] / bw
        derived["on_bin_n4096"] = float(p["f_hz"] / bw).is_integer()
        # The ideal square's fundamental is 4/π (+2.10 dB, ADR 0006 D3). A square
        # *sampled* with an integer period P = fs/f and no band-limiting has its
        # above-Nyquist odd harmonics folded back, and its exact DFT fundamental is
        # 4/(P·sin(π/P)) — 1.2752 for P = 32 (+2.11 dB), against 4/π = 1.2732. The
        # file is the sampled one, so the sampled value is its truth; the ideal is
        # recorded beside it because that is the number the ADR table quotes.
        period = e.fs / p["f_hz"]
        derived["samples_per_period"] = period
        derived["fundamental_amplitude_ideal"] = float(4.0 / np.pi) * signals.amplitude(p["level_dbfs"])
        derived["fundamental_bin_dbfs_ideal"] = p["level_dbfs"] + float(SQUARE_FUNDAMENTAL_DB)
        if float(period).is_integer() and int(period) % 2 == 0:
            a1 = 4.0 / (period * np.sin(np.pi / period))
            derived["fundamental_amplitude_sampled"] = float(a1) * signals.amplitude(p["level_dbfs"])
            derived["fundamental_bin_dbfs_expected"] = p["level_dbfs"] + float(20.0 * np.log10(a1))
        derived["total_power_dbfs_expected"] = p["level_dbfs"] + float(SQUARE_TOTAL_POWER_DB)
    if g == "two_tone":
        derived["level_convention"] = "envelope amplitude; each component −6.02 dB"
        derived["component_amplitude"] = signals.amplitude(p["level_dbfs"]) / 2.0
        derived["delta_hz"] = p["f2_hz"] - p["f1_hz"]
        derived["delta_bins_n4096"] = (p["f2_hz"] - p["f1_hz"]) / bw
        derived["bins_n4096"] = [p["f1_hz"] / bw, p["f2_hz"] / bw]
    if g in ("white_noise", "pink_noise"):
        derived["level_convention"] = "RMS equal to a sine at level_dbfs"
        derived["rms"] = float(signals.rms_of_sine(p["level_dbfs"]))
        derived["rng"] = "numpy.random.default_rng(seed) (PCG64)"
        derived["psd_slope_db_per_octave"] = 0.0 if g == "white_noise" else float(PINK_SLOPE_DB_PER_OCTAVE)
    if g == "sweep_linear":
        derived["level_convention"] = "amplitude"
        derived["instantaneous_frequency_hz"] = "f_start + (f_end - f_start) * t / T"
    if g == "sweep_exponential":
        derived["level_convention"] = "amplitude"
        derived["instantaneous_frequency_hz"] = "f_start * exp(t * ln(f_end / f_start) / T)"
        derived["octaves"] = float(np.log2(p["f_end_hz"] / p["f_start_hz"]))
    if g == "glottal_vowel":
        derived["level_convention"] = "peak after the tract"
        derived["source"] = "Rosenberg (1971) trigonometric pulse, phase-accumulator driven (f0 exact)"
        derived["radiation"] = "first difference (Klatt 1980)"
        derived["tract"] = "cascade of Klatt (1980) resonators, coefficients from (F, BW, fs)"
        derived["harmonics_hz_below_4k"] = [p["f0_hz"] * k for k in range(1, int(4000 // p["f0_hz"]) + 1)]
        # Two truths per formant, both exact: the pole (what Burg/LPC estimates —
        # Praat `To Formant`, the F1/F2 row) is at F itself; the |H| peak of the
        # resonator alone sits slightly below it (signals.klatt_resonator_peak_hz).
        derived["formant_poles_hz"] = list(p["formants_hz"])
        derived["formant_bandwidths_hz"] = list(p["bandwidths_hz"])
        derived["resonator_response_peaks_hz"] = [
            signals.klatt_resonator_peak_hz(f, b, e.fs) for f, b in zip(p["formants_hz"], p["bandwidths_hz"], strict=True)
        ]
        if p.get("vibrato_rate_hz", 0.0) > 0.0:
            ext = p["vibrato_extent_cents"]
            derived["f0_min_hz"] = p["f0_hz"] * 2.0 ** (-ext / 1200.0)
            derived["f0_max_hz"] = p["f0_hz"] * 2.0 ** (ext / 1200.0)
            derived["vibrato_extent_is"] = "peak deviation (±), i.e. half the peak-to-peak"
    if g == "silence":
        derived["level_convention"] = "none (all zeros)"
    if derived:
        truth["derived"] = derived
    if e.note:
        truth["note"] = e.note
    if e.use:
        truth["use"] = list(e.use)
    return truth
