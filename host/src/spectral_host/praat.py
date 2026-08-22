# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""Praat through parselmouth: the four analysis blocks of a golden manifest, each driven by its own config.

This is the GPL half's reason to exist (ADR 0004): parselmouth embeds Praat and
is imported in-process here, and nothing outside host/ ever imports this file.
Every function takes a `parselmouth.Sound` and a frozen config dataclass whose
field set is EXACTLY the required key list of the matching `analyses.<block>`
of host/golden/manifest.schema.yaml — pinned by
`test_config_asdict_keys_equal_schema_required_lists` — so that a manifest can
be written with `cfg.asdict()` and read back with `PitchConfig(**block)`, and
"left at a Praat default" can never happen (ADR 0009 item 1(a): the defaults
differ between pitch methods, so an unstated parameter is not a value).

What is pinned, and where each number comes from:

  * `sound_from_int16()` is the ONE decode path. int16 → float is
    `x / int16_scale` (32768 by ADR 0003 d.2 / ADR 0006 D3; 32767 admitted by
    the schema), applied once, here, so that Praat sees the same float the
    spectrum oracle sees. Praat reads a sample value of 1.0 as 1 Pa, which is
    why its LTAS levels are dB SPL re 2·10⁻⁵ Pa (see `ltas`).
  * `pitch_track()` — `method: raw` calls `Sound.to_pitch_ac` with all eleven
    parameters; that binding is Praat 6.1.38's `To Pitch (ac)...`, the only
    autocorrelation command the pinned bundle registers (praat-parselmouth
    0.4.7; ADR 0009 amendment, measured 2026-08-21). `cc` is `to_pitch_cc`.
    `filtered` raises `UnsupportedPitchMethod` unless the bundled Praat is
    ≥ 6.4 (the release that introduced it, 2023-11-15); on such a bundle it
    issues `praat.call(snd, "To Pitch (filtered autocorrelation)", …)` in the
    argument order of `fon/praat_Sound.cpp`
    (`CONVERT_EACH_TO_ONE__Sound_to_Pitch_filteredAutocorrelation`, read in
    the praat/praat clone on 2026-08-21 — bibliography 06 #31): time step,
    floor, TOP, candidates, very accurate, ATTENUATION AT TOP, silence,
    voicing, octave, octave-jump, voiced/unvoiced. The schema has no field for
    the attenuation (ADR 0009: a filtered set is schema "1.2"), so this path
    passes Praat's own default `FILTERED_AC_ATTENUATION_AT_TOP` and maps
    `pitch_ceiling` onto "top"; it has never executed on the pinned bundle
    and is `(prov.)` until a parselmouth release reaches Praat 6.4.
    Output: `[n, 2]` float64, columns `time` (Praat's frame centres, `t1 +
    i·dt` — compare by TIME, never by index: golden-files.md "frame-grid
    trap") and `f0` in Hz with `0` for unvoiced (`unvoiced_sentinel: 0`,
    Praat's own convention via `Pitch.selected_array["frequency"]`).
  * `formant_track()` — `Sound.to_formant_burg` with the five schema fields.
    Praat fits `round(2·max_formants)` poles (`Sound_to_Formant_burg` →
    `Melder_iround (2.0 * nFormants)`) and creates `(poles + 1) // 2` formant
    slots (`Sound_to_Formant_any_inplace`, "e.g. 11 poles -> maximally 6
    formants"; both in `fon/Sound_to_Formant.cpp`), so the array has
    `1 + 2·slots` columns: `time, F1, B1, F2, B2, …`, NaN where Praat has no
    value (its `undefined`, which parselmouth returns as NaN).
  * `ltas()` — `praat.call(snd, "To Ltas", bandwidth_hz)` then `"To Matrix"`
    to read the band values out (parselmouth 0.4.7 has no Ltas class, so the
    object comes back as opaque `parselmouth.Data`). Columns `frequency`
    (band centre, `x1 + k·dx`) and `level`: Praat's
    `10·log10(power density / 4·10⁻¹⁰)` — dB/Hz re (2·10⁻⁵ Pa)², with 1.0 =
    1 Pa, empty bands at −300 (`Spectrum_to_Ltas` / `Sound_to_Ltas` in
    `fon/Ltas.cpp`). A half-scale sine therefore reports a total SPL of
    84.95 dB (RMS 0.354 Pa re 2·10⁻⁵; measured 2026-08-21). This is Praat's
    axis, not ADR 0006's dBFS; the LTAS tolerance row is in dB per band,
    which is invariant to the reference.
  * `spectrogram()` — `Sound.to_spectrogram` with the five schema fields
    (`window_shape` mapped onto `parselmouth.SpectralAnalysisWindowShape`).
    Implemented so the block has a driver; NOT used by any H0 set (roadmap
    H1). Returns `(times, frequencies, values[n_freq, n_time])` with Praat's
    values, a power spectral density in Pa²/Hz.

Praat's defaults for the raw method are recorded in `RAW_AC_PRAAT_DEFAULTS`
and asserted against the bundle's own signature by the test-suite, so the
numbers ADR 0009 cites cannot drift from the code that runs.

CLI — a quick look at what the pinned Praat says about one 16-bit WAV:

    uv run --project host python -m spectral_host.praat pitch FILE.wav [--floor 65 --ceiling 1100 ...]
    uv run --project host python -m spectral_host.praat formant FILE.wav
    uv run --project host python -m spectral_host.praat ltas FILE.wav [--bandwidth 100]

Option defaults are Praat 6.1.38's own (`RAW_AC_PRAAT_DEFAULTS`, and
`to_formant_burg` / golden-files.md's `To Ltas` bandwidth for the other two);
the golden sets pin their values in their manifests, not here.
"""

from __future__ import annotations

import argparse
import dataclasses
import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import parselmouth
from parselmouth.praat import call

from spectral_host.spectrum import INT16_SCALES, DEFAULT_INT16_SCALE
from spectral_host.wavio import read_wav

# --- enums and constants (manifest.schema.yaml `analyses.*`) -----------------

PITCH_METHODS: tuple[str, ...] = ("raw", "filtered", "cc")
FORMANT_METHODS: tuple[str, ...] = ("burg",)
SPECTROGRAM_WINDOW_SHAPES: tuple[str, ...] = ("square", "hamming", "bartlett", "welch", "hanning", "gaussian")

#: Praat release that introduced `To Pitch (filtered autocorrelation)...`
#: (6.4, 2023-11-15; ADR 0009 amendment). Compared as a tuple against
#: `praat_version_tuple(parselmouth.PRAAT_VERSION)`.
FILTERED_AC_MIN_PRAAT: tuple[int, int] = (6, 4)

#: Praat's default "Attenuation at top" of the filtered method (`fon/praat_Sound.cpp`,
#: `POSITIVE (attenuationAtTop, U"Attenuation at top", U"0.03")`). The schema
#: has no field for it until "1.2"; this is what the unreachable path passes. (prov.)
FILTERED_AC_ATTENUATION_AT_TOP: float = 0.03

#: Praat 6.1.38's defaults for `To Pitch (ac)...`, as parselmouth 0.4.7's
#: `Sound.to_pitch_ac` signature carries them (read 2026-08-21) and as ADR 0009's
#: amendment records them: floor 75, ceiling 600, 15 candidates, very accurate
#: off, silence 0.03, voicing 0.45, octave 0.01, octave-jump 0.35, voiced/unvoiced
#: 0.14. `time_step` 0.0 is Praat's "auto" (parselmouth: `None`). Reference data
#: only — a golden set states every value in its manifest.
RAW_AC_PRAAT_DEFAULTS: dict[str, object] = {
    "method": "raw",
    "time_step": 0.0,
    "pitch_floor": 75.0,
    "pitch_ceiling": 600.0,
    "silence_threshold": 0.03,
    "voicing_threshold": 0.45,
    "octave_cost": 0.01,
    "octave_jump_cost": 0.35,
    "voiced_unvoiced_cost": 0.14,
    "max_candidates": 15,
    "very_accurate": False,
}

#: Praat's unvoiced marker in a pitch track (manifest `outputs[].unvoiced_sentinel`).
UNVOICED_SENTINEL: float = 0.0


class UnsupportedPitchMethod(RuntimeError):
    """The requested pitch method does not exist in the Praat parselmouth bundles."""


def praat_version_tuple(version: str) -> tuple[int, ...]:
    """`"6.1.38"` → `(6, 1, 38)`; `"7.0.01"` → `(7, 0, 1)`. Refuses anything that is not dotted integers."""
    parts = str(version).strip().split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        raise ValueError(f"not a dotted-integer Praat version: {version!r}") from None


# --- validation helpers ----------------------------------------------------------


def _is_int(v: object) -> bool:
    return isinstance(v, (int, np.integer)) and not isinstance(v, bool)


def _is_number(v: object) -> bool:
    return isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool)


def _require_number(name: str, v: object, *, minimum: float | None = None, exclusive: bool = False) -> None:
    if not _is_number(v) or not math.isfinite(float(v)):
        raise ValueError(f"{name} must be a finite number, got {v!r}")
    if minimum is not None:
        if exclusive and float(v) <= minimum:
            raise ValueError(f"{name} must be > {minimum}, got {v!r}")
        if not exclusive and float(v) < minimum:
            raise ValueError(f"{name} must be >= {minimum}, got {v!r}")


# --- the configuration blocks ------------------------------------------------------


@dataclass(frozen=True)
class PitchConfig:
    """`analyses.pitch` — exactly its eleven required keys, in schema order, no defaults.

    Cross-field rule checked here and by verify.py invariant 1:
    `pitch_floor < pitch_ceiling`. `time_step == 0` is Praat's automatic step
    (passed to parselmouth as `None`); explicit is preferred (schema).
    """

    method: str
    time_step: float
    pitch_floor: float
    pitch_ceiling: float
    silence_threshold: float
    voicing_threshold: float
    octave_cost: float
    octave_jump_cost: float
    voiced_unvoiced_cost: float
    max_candidates: int
    very_accurate: bool

    def __post_init__(self) -> None:
        if self.method not in PITCH_METHODS:
            raise ValueError(f"method must be one of {PITCH_METHODS}, got {self.method!r}")
        _require_number("time_step", self.time_step, minimum=0.0)
        _require_number("pitch_floor", self.pitch_floor, minimum=0.0, exclusive=True)
        _require_number("pitch_ceiling", self.pitch_ceiling, minimum=0.0, exclusive=True)
        if not self.pitch_floor < self.pitch_ceiling:
            raise ValueError(
                f"pitch_floor ({self.pitch_floor}) must be below pitch_ceiling ({self.pitch_ceiling}) — verify.py invariant 1"
            )
        for name in ("silence_threshold", "voicing_threshold", "octave_cost", "octave_jump_cost", "voiced_unvoiced_cost"):
            _require_number(name, getattr(self, name), minimum=0.0)
        if not _is_int(self.max_candidates) or self.max_candidates < 2:
            raise ValueError(f"max_candidates must be an integer >= 2 (schema; Praat requires > 1), got {self.max_candidates!r}")
        if not isinstance(self.very_accurate, bool):
            raise ValueError(f"very_accurate must be a bool, got {self.very_accurate!r}")

    def asdict(self) -> dict[str, object]:
        """The block as the manifest writes it: the eleven keys in schema order."""
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class FormantConfig:
    """`analyses.formant` — exactly its six required keys, in schema order.

    `max_formants` is a number, not an integer, because Praat accepts
    multiples of 0.5: it fits `round(2·max_formants)` poles (LPC order 10 for
    5 — there is no "+2"; schema block description, `fon/Sound_to_Formant.cpp`).
    """

    method: str
    time_step: float
    max_formants: float
    ceiling_hz: float
    window_length: float
    preemphasis_from_hz: float

    def __post_init__(self) -> None:
        if self.method not in FORMANT_METHODS:
            raise ValueError(f"method must be one of {FORMANT_METHODS}, got {self.method!r}")
        _require_number("time_step", self.time_step, minimum=0.0)
        _require_number("max_formants", self.max_formants, minimum=0.0, exclusive=True)
        _require_number("ceiling_hz", self.ceiling_hz, minimum=0.0, exclusive=True)
        _require_number("window_length", self.window_length, minimum=0.0, exclusive=True)
        _require_number("preemphasis_from_hz", self.preemphasis_from_hz, minimum=0.0)

    def asdict(self) -> dict[str, object]:
        return dataclasses.asdict(self)

    @property
    def lpc_order(self) -> int:
        """The pole count Praat actually fits: `Melder_iround (2.0 * nFormants)` (round half away from zero)."""
        return int(math.floor(2.0 * float(self.max_formants) + 0.5))

    @property
    def formant_slots(self) -> int:
        """Formant slots Praat allocates per frame: `(numberOfPoles + 1) / 2` in integer arithmetic."""
        return (self.lpc_order + 1) // 2


@dataclass(frozen=True)
class SpectrogramConfig:
    """`analyses.spectrogram` — exactly its five required keys, in schema order (Praat's `To Spectrogram...`)."""

    window_shape: str
    window_length: float
    time_step: float
    frequency_step: float
    max_frequency: float

    def __post_init__(self) -> None:
        if self.window_shape not in SPECTROGRAM_WINDOW_SHAPES:
            raise ValueError(f"window_shape must be one of {SPECTROGRAM_WINDOW_SHAPES}, got {self.window_shape!r}")
        for name in ("window_length", "time_step", "frequency_step", "max_frequency"):
            _require_number(name, getattr(self, name), minimum=0.0, exclusive=True)

    def asdict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class LtasConfig:
    """`analyses.ltas` — its one required key (Praat's `To Ltas...` bandwidth in Hz)."""

    bandwidth_hz: float

    def __post_init__(self) -> None:
        _require_number("bandwidth_hz", self.bandwidth_hz, minimum=0.0, exclusive=True)

    def asdict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


# --- the one decode path -------------------------------------------------------------


def sound_from_int16(x: np.ndarray, fs: float, int16_scale: int = DEFAULT_INT16_SCALE) -> parselmouth.Sound:
    """int16 mono samples → `parselmouth.Sound` at `fs`, scaled by `1 / int16_scale` exactly once.

    Refuses non-int16 input (a float array would be scaled twice and read
    90.3 dB low — the same guard as `spectrum.int16_to_float`) and anything
    that is not one channel (Praat would read a `[n, 2]` array as two
    channels of n samples, or as n channels of 2 samples, depending on
    orientation; neither is a take).
    """
    arr = np.asarray(x)
    if arr.dtype != np.int16:
        raise TypeError(f"sound_from_int16 expects int16 samples, got dtype {arr.dtype}")
    if arr.ndim != 1 or arr.size == 0:
        raise ValueError(f"sound_from_int16 takes one non-empty mono channel, got shape {arr.shape}")
    if int16_scale not in INT16_SCALES:
        raise ValueError(f"int16_scale must be one of {INT16_SCALES}, got {int16_scale!r}")
    if not _is_number(fs) or fs <= 0:
        raise ValueError(f"fs must be a positive number, got {fs!r}")
    values = arr.astype(np.float64) / float(int16_scale)
    return parselmouth.Sound(values, sampling_frequency=float(fs), start_time=0.0)


# --- pitch ------------------------------------------------------------------------------


def _praat_time_step(time_step: float) -> float | None:
    # Schema: 0 = Praat's automatic step; parselmouth spells that `None`.
    return None if float(time_step) == 0.0 else float(time_step)


def pitch_track(snd: parselmouth.Sound, cfg: PitchConfig, praat_version: str | None = None) -> np.ndarray:
    """f0 track as `[n, 2]` float64: columns `time` (s, Praat frame centres) and `f0` (Hz, 0 = unvoiced).

    `praat_version` defaults to the installed `parselmouth.PRAAT_VERSION`; it
    is a parameter so the `filtered` gate can be tested against a version
    string without monkeypatching a compiled module.
    """
    if not isinstance(cfg, PitchConfig):
        raise TypeError("pitch_track needs a PitchConfig")
    if cfg.method == "filtered":
        bundled = parselmouth.PRAAT_VERSION if praat_version is None else praat_version
        if praat_version_tuple(bundled) < FILTERED_AC_MIN_PRAAT:
            raise UnsupportedPitchMethod(
                f"method 'filtered' needs Praat >= {'.'.join(map(str, FILTERED_AC_MIN_PRAAT))} "
                f"(To Pitch (filtered autocorrelation)..., 2023-11-15); the bundled Praat is {bundled} "
                "(ADR 0009 amendment, verify.py invariant 6)"
            )
        pitch = call(
            snd,
            "To Pitch (filtered autocorrelation)",
            float(cfg.time_step),  # Praat's own 0.0 = auto; no None here, this is the script form
            float(cfg.pitch_floor),
            float(cfg.pitch_ceiling),  # "top" in the filtered dialogue
            int(cfg.max_candidates),
            bool(cfg.very_accurate),
            float(FILTERED_AC_ATTENUATION_AT_TOP),
            float(cfg.silence_threshold),
            float(cfg.voicing_threshold),
            float(cfg.octave_cost),
            float(cfg.octave_jump_cost),
            float(cfg.voiced_unvoiced_cost),
        )
    else:
        method = snd.to_pitch_ac if cfg.method == "raw" else snd.to_pitch_cc
        pitch = method(
            time_step=_praat_time_step(cfg.time_step),
            pitch_floor=float(cfg.pitch_floor),
            max_number_of_candidates=int(cfg.max_candidates),
            very_accurate=bool(cfg.very_accurate),
            silence_threshold=float(cfg.silence_threshold),
            voicing_threshold=float(cfg.voicing_threshold),
            octave_cost=float(cfg.octave_cost),
            octave_jump_cost=float(cfg.octave_jump_cost),
            voiced_unvoiced_cost=float(cfg.voiced_unvoiced_cost),
            pitch_ceiling=float(cfg.pitch_ceiling),
        )
    times = np.asarray(pitch.xs(), dtype=np.float64)
    f0 = np.asarray(pitch.selected_array["frequency"], dtype=np.float64)
    # Praat marks unvoiced frames with 0; NaN never appears in its output, and
    # a NaN here would break every cents comparison downstream, so say so.
    if np.isnan(f0).any():
        raise RuntimeError("Praat returned NaN in a pitch track; unvoiced frames are expected as 0")
    out = np.empty((f0.size, 2), dtype=np.float64)
    out[:, 0] = times
    out[:, 1] = f0
    return out


# --- formants ----------------------------------------------------------------------------


def formant_track(snd: parselmouth.Sound, cfg: FormantConfig) -> np.ndarray:
    """Formant track as `[n, 1 + 2·slots]` float64: `time, F1, B1, F2, B2, …`, NaN where Praat has none.

    `slots = cfg.formant_slots` (5 for `max_formants: 5`). Values and bandwidths
    are read with `Formant.get_value_at_time` / `get_bandwidth_at_time` at the
    object's own frame centres (`xs()`), unit Hertz, linear interpolation at an
    exact frame centre returns the frame's value.
    """
    if not isinstance(cfg, FormantConfig):
        raise TypeError("formant_track needs a FormantConfig")
    formant = snd.to_formant_burg(
        time_step=_praat_time_step(cfg.time_step),
        max_number_of_formants=float(cfg.max_formants),
        maximum_formant=float(cfg.ceiling_hz),
        window_length=float(cfg.window_length),
        pre_emphasis_from=float(cfg.preemphasis_from_hz),
    )
    times = np.asarray(formant.xs(), dtype=np.float64)
    slots = cfg.formant_slots
    out = np.full((times.size, 1 + 2 * slots), np.nan, dtype=np.float64)
    out[:, 0] = times
    for i, t in enumerate(times):
        for k in range(1, slots + 1):
            out[i, 2 * k - 1] = formant.get_value_at_time(k, float(t))
            out[i, 2 * k] = formant.get_bandwidth_at_time(k, float(t))
    return out


# --- LTAS ---------------------------------------------------------------------------------


def ltas(snd: parselmouth.Sound, cfg: LtasConfig) -> np.ndarray:
    """Long-term average spectrum as `[n_bands, 2]` float64: `frequency` (band centre, Hz), `level` (Praat's dB/Hz).

    `praat.call(snd, "To Ltas", bandwidth_hz)` — Praat's `Sound_to_Ltas`, the
    whole-sound spectrum binned into `bandwidth_hz`-wide bands — read out via
    `"To Matrix"`, whose `x1`/`dx` are the first band centre and the band
    width. The level is `10·log10(P / 4·10⁻¹⁰)` per band (see module docstring).
    """
    if not isinstance(cfg, LtasConfig):
        raise TypeError("ltas needs an LtasConfig")
    ltas_obj = call(snd, "To Ltas", float(cfg.bandwidth_hz))
    matrix = call(ltas_obj, "To Matrix")
    values = np.asarray(matrix.values, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] != 1:
        raise RuntimeError(f"Ltas → Matrix gave shape {values.shape}; expected one row of bands")
    n_bands = values.shape[1]
    out = np.empty((n_bands, 2), dtype=np.float64)
    out[:, 0] = float(matrix.x1) + float(matrix.dx) * np.arange(n_bands, dtype=np.float64)
    out[:, 1] = values[0]
    return out


# --- spectrogram (implemented, unused in H0) ---------------------------------------------


def spectrogram(snd: parselmouth.Sound, cfg: SpectrogramConfig) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Praat's `To Spectrogram...` as `(times[n_time], frequencies[n_freq], values[n_freq, n_time])`, float64.

    `values` is what `parselmouth.Spectrogram.values` holds — Praat's power
    spectral density in Pa²/Hz, linear, not dB — so that any later dB
    conversion states its own reference (ADR 0006 D3 never mixes axes). Not
    consumed by any H0 golden set; roadmap H1 owns the spectrogram goldens.
    """
    if not isinstance(cfg, SpectrogramConfig):
        raise TypeError("spectrogram needs a SpectrogramConfig")
    shape = getattr(parselmouth.SpectralAnalysisWindowShape, cfg.window_shape.upper())
    sg = snd.to_spectrogram(
        window_length=float(cfg.window_length),
        maximum_frequency=float(cfg.max_frequency),
        time_step=float(cfg.time_step),
        frequency_step=float(cfg.frequency_step),
        window_shape=shape,
    )
    times = np.asarray(sg.xs(), dtype=np.float64)
    frequencies = np.asarray(sg.ys(), dtype=np.float64)
    values = np.asarray(sg.values, dtype=np.float64)
    return times, frequencies, values


# --- CLI ---------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    d = RAW_AC_PRAAT_DEFAULTS
    parser = argparse.ArgumentParser(
        prog="python -m spectral_host.praat",
        description="Run the pinned Praat (via parselmouth) over one 16-bit WAV and summarise the result.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    p = sub.add_parser("pitch", help="f0 track; options default to Praat 6.1.38's raw-ac defaults")
    p.add_argument("wav")
    p.add_argument("--method", choices=PITCH_METHODS, default="raw")
    p.add_argument("--time-step", type=float, default=d["time_step"], help="s; 0 = Praat auto")
    p.add_argument("--floor", type=float, default=d["pitch_floor"], help="Hz")
    p.add_argument("--ceiling", type=float, default=d["pitch_ceiling"], help="Hz")
    p.add_argument("--silence", type=float, default=d["silence_threshold"])
    p.add_argument("--voicing", type=float, default=d["voicing_threshold"])
    p.add_argument("--octave-cost", type=float, default=d["octave_cost"])
    p.add_argument("--octave-jump-cost", type=float, default=d["octave_jump_cost"])
    p.add_argument("--vuv-cost", type=float, default=d["voiced_unvoiced_cost"])
    p.add_argument("--candidates", type=int, default=d["max_candidates"])
    p.add_argument("--very-accurate", action="store_true")

    f = sub.add_parser("formant", help="Burg formants; options default to parselmouth's to_formant_burg defaults")
    f.add_argument("wav")
    f.add_argument("--time-step", type=float, default=0.0, help="s; 0 = Praat auto")
    f.add_argument("--max-formants", type=float, default=5.0)
    f.add_argument("--ceiling", type=float, default=5500.0, help="Hz")
    f.add_argument("--window-length", type=float, default=0.025, help="s")
    f.add_argument("--preemphasis-from", type=float, default=50.0, help="Hz")

    lt = sub.add_parser("ltas", help="long-term average spectrum; bandwidth defaults to golden-files.md's 100 Hz")
    lt.add_argument("wav")
    lt.add_argument("--bandwidth", type=float, default=100.0, help="Hz")
    return parser


def _load(path: str) -> parselmouth.Sound:
    wav = read_wav(path)
    return sound_from_int16(wav.mono, wav.sample_rate)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        snd = _load(args.wav)
        if args.command == "pitch":
            cfg = PitchConfig(
                method=args.method,
                time_step=args.time_step,
                pitch_floor=args.floor,
                pitch_ceiling=args.ceiling,
                silence_threshold=args.silence,
                voicing_threshold=args.voicing,
                octave_cost=args.octave_cost,
                octave_jump_cost=args.octave_jump_cost,
                voiced_unvoiced_cost=args.vuv_cost,
                max_candidates=args.candidates,
                very_accurate=args.very_accurate,
            )
            track = pitch_track(snd, cfg)
            voiced = track[track[:, 1] > 0, 1]
            print(f"praat {parselmouth.PRAAT_VERSION} (parselmouth {parselmouth.VERSION}) method={cfg.method}")
            print(f"frames={track.shape[0]} t1={track[0, 0]:.6g} dt={(track[1, 0] - track[0, 0]) if track.shape[0] > 1 else float('nan'):.6g}")
            print(f"voiced={voiced.size} median_f0_hz={np.median(voiced) if voiced.size else float('nan'):.6g}")
        elif args.command == "formant":
            cfg = FormantConfig(
                method="burg",
                time_step=args.time_step,
                max_formants=args.max_formants,
                ceiling_hz=args.ceiling,
                window_length=args.window_length,
                preemphasis_from_hz=args.preemphasis_from,
            )
            track = formant_track(snd, cfg)
            print(f"frames={track.shape[0]} slots={cfg.formant_slots} lpc_order={cfg.lpc_order}")
            for k in range(1, cfg.formant_slots + 1):
                col = track[:, 2 * k - 1]
                defined = col[~np.isnan(col)]
                median = f"{np.median(defined):.6g}" if defined.size else "nan"
                print(f"F{k}: median_hz={median} defined={defined.size}/{col.size}")
        else:
            out = ltas(snd, LtasConfig(bandwidth_hz=args.bandwidth))
            print(f"bands={out.shape[0]} first_centre_hz={out[0, 0]:.6g} width_hz={args.bandwidth:.6g}")
            peak = int(np.argmax(out[:, 1]))
            print(f"peak band centre_hz={out[peak, 0]:.6g} level_db={out[peak, 1]:.4f} (Praat dB/Hz re 2e-5 Pa)")
    except (OSError, ValueError, TypeError, UnsupportedPitchMethod, parselmouth.PraatError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
