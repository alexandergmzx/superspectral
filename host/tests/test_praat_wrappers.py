# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""The Praat wrappers, environment capture and I/O of roadmap H0 unit B-U4, by hazard.

Covers spectral_host.praat, .env, .hashing and .wavio. Each test is named for
the silent failure it guards: a config block that drifts from the schema's
required list, a `filtered` track claimed on a Praat that cannot produce one,
NaN where Praat writes 0 for unvoiced, a generator digest that does not move
when the generator does, a WAV reader that converts instead of refusing.

The pin itself — parselmouth 0.4.7 bundling Praat 6.1.38 — is asserted once,
in test_env.py::test_installed_praat_is_the_pinned_bundle; it is not repeated
here. Signals are synthesised in-file in int16 (no Apache generator import;
test_env.py checks none is reachable).

Run: `uv run --project host pytest -q host/tests/test_praat_wrappers.py`
"""

from __future__ import annotations

import dataclasses
import re
import shutil
import wave
from pathlib import Path

import jsonschema
import numpy as np
import parselmouth
import pytest
import yaml

from spectral_host import env as envmod
from spectral_host import hashing, praat, wavio

FS = 32000

#: The provisional pitch block of docs/validation/golden-files.md and the schema's
#: worked example: Praat 6.1.38 raw-ac defaults with floor/ceiling widened for
#: singing to 65 / 1100 Hz (prov.) and the step pinned at 10 ms.
PITCH_PROV = praat.PitchConfig(
    method="raw",
    time_step=0.01,
    pitch_floor=65,
    pitch_ceiling=1100,
    silence_threshold=0.03,
    voicing_threshold=0.45,
    octave_cost=0.01,
    octave_jump_cost=0.35,
    voiced_unvoiced_cost=0.14,
    max_candidates=15,
    very_accurate=False,
)

#: golden-files.md's formant block (Praat's own defaults; LPC order 10).
FORMANT_PROV = praat.FormantConfig(
    method="burg", time_step=0.01, max_formants=5, ceiling_hz=5500, window_length=0.025, preemphasis_from_hz=50
)

#: The four config classes against their `analyses.<block>` names.
CONFIG_BLOCKS = {
    "pitch": praat.PitchConfig,
    "formant": praat.FormantConfig,
    "spectrogram": praat.SpectrogramConfig,
    "ltas": praat.LtasConfig,
}


# --- signal helpers (int16, in-file) ------------------------------------------


def sine_int16(freq_hz: float, seconds: float, amplitude: int = 16383, fs: int = FS) -> np.ndarray:
    t = np.arange(int(round(seconds * fs))) / fs
    return np.rint(amplitude * np.sin(2 * np.pi * freq_hz * t)).astype(np.int16)


def silence_int16(seconds: float, fs: int = FS) -> np.ndarray:
    return np.zeros(int(round(seconds * fs)), dtype=np.int16)


def cents(f: np.ndarray, ref_hz: float) -> np.ndarray:
    return 1200.0 * np.log2(np.asarray(f, dtype=np.float64) / ref_hz)


def write_wav(path: Path, samples: np.ndarray, fs: int, sampwidth: int = 2, channels: int = 1) -> Path:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(fs)
        wf.writeframes(samples.tobytes())
    return path


# --- fixtures -------------------------------------------------------------------


@pytest.fixture(scope="module")
def schema(repo_root: Path) -> dict:
    return yaml.safe_load((repo_root / "host" / "golden" / "manifest.schema.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sine_440() -> parselmouth.Sound:
    return praat.sound_from_int16(sine_int16(440.0, 3.0), FS)


# --- configs vs the schema -------------------------------------------------------


@pytest.mark.parametrize("block", sorted(CONFIG_BLOCKS))
def test_config_asdict_keys_equal_schema_required_lists(schema, block):
    """A field the schema requires but the dataclass lacks is a manifest that never validates; the reverse is a key the generator writes that `additionalProperties: false` rejects."""
    required = schema["properties"]["analyses"]["properties"][block]["required"]
    fields = [f.name for f in dataclasses.fields(CONFIG_BLOCKS[block])]
    assert fields == required, f"{block}: dataclass fields {fields} != schema required {required}"
    # The schema lists every property it requires and requires every property it lists.
    assert sorted(schema["properties"]["analyses"]["properties"][block]["properties"]) == sorted(required)


def test_generator_env_keys_equal_schema_required_list(schema):
    """Same hazard for the `generator` block: `GeneratorEnv` must be exactly the schema's key set, in order."""
    required = schema["properties"]["generator"]["required"]
    assert [f.name for f in dataclasses.fields(envmod.GeneratorEnv)] == required
    assert envmod.GENERATOR_KEYS == tuple(required)


def test_config_enums_equal_schema_enums(schema):
    """The wrappers refuse what the schema refuses, without loading the schema at run time — so the copies must agree."""
    analyses = schema["properties"]["analyses"]["properties"]
    assert tuple(analyses["pitch"]["properties"]["method"]["enum"]) == praat.PITCH_METHODS
    assert tuple(analyses["formant"]["properties"]["method"]["enum"]) == praat.FORMANT_METHODS
    assert tuple(analyses["spectrogram"]["properties"]["window_shape"]["enum"]) == praat.SPECTROGRAM_WINDOW_SHAPES


@pytest.mark.parametrize(
    "block, cfg",
    [
        ("pitch", PITCH_PROV),
        ("formant", FORMANT_PROV),
        ("spectrogram", praat.SpectrogramConfig(window_shape="gaussian", window_length=0.005, time_step=0.002, frequency_step=20, max_frequency=8000)),
        ("ltas", praat.LtasConfig(bandwidth_hz=100)),
    ],
)
def test_config_round_trips_through_asdict_and_validates(schema, block, cfg):
    """`Config(**block)` ← `cfg.asdict()` is how manifests are read and written; the schema's sub-block must accept the dict."""
    d = cfg.asdict()
    assert type(cfg)(**d) == cfg
    sub_schema = {**schema["properties"]["analyses"]["properties"][block], "$defs": schema["$defs"]}
    assert list(jsonschema.Draft202012Validator(sub_schema).iter_errors(d)) == []


def pybind_defaults(method) -> dict[str, str]:
    """`name: type = default` pairs from a pybind11 method's first docstring line (it has no `__text_signature__`)."""
    first_line = method.__doc__.splitlines()[0]
    return dict(re.findall(r"(\w+): [^=,()]+(?:\[[^\]]*\])* = ([^,)]+)", first_line))


def test_raw_ac_praat_defaults_match_the_bundled_signature():
    """ADR 0009's amendment records 6.1.38's raw defaults; if parselmouth's own signature disagrees, the record is wrong."""
    sig = pybind_defaults(parselmouth.Sound.to_pitch_ac)
    d = praat.RAW_AC_PRAAT_DEFAULTS
    assert float(sig["pitch_floor"]) == d["pitch_floor"]
    assert float(sig["pitch_ceiling"]) == d["pitch_ceiling"]
    assert int(sig["max_number_of_candidates"]) == d["max_candidates"]
    assert sig["very_accurate"] == "False" and d["very_accurate"] is False
    assert float(sig["silence_threshold"]) == d["silence_threshold"]
    assert float(sig["voicing_threshold"]) == d["voicing_threshold"]
    assert float(sig["octave_cost"]) == d["octave_cost"]
    assert float(sig["octave_jump_cost"]) == d["octave_jump_cost"]
    assert float(sig["voiced_unvoiced_cost"]) == d["voiced_unvoiced_cost"]
    assert sig["time_step"] == "None"  # Praat's 0.0 = auto
    praat.PitchConfig(**praat.RAW_AC_PRAAT_DEFAULTS)  # the recorded defaults form a valid block


@pytest.mark.parametrize(
    "override, match",
    [
        ({"pitch_floor": 1100, "pitch_ceiling": 65}, "invariant 1"),
        ({"pitch_floor": 600, "pitch_ceiling": 600}, "invariant 1"),
        ({"method": "yin"}, "method"),
        ({"max_candidates": 1}, "max_candidates"),
        ({"max_candidates": 15.0}, "max_candidates"),
        ({"very_accurate": 0}, "very_accurate"),
        ({"time_step": -0.01}, "time_step"),
    ],
)
def test_pitch_config_refuses_what_verify_invariant_1_and_the_schema_refuse(override, match):
    """A config that Praat would accept but the schema would not must fail here, before any vector is computed."""
    with pytest.raises(ValueError, match=match):
        praat.PitchConfig(**{**PITCH_PROV.asdict(), **override})


def test_pitch_config_rejects_a_key_the_schema_does_not_list():
    with pytest.raises(TypeError):
        praat.PitchConfig(**{**PITCH_PROV.asdict(), "attenuation_at_top": 0.03})


@pytest.mark.parametrize("max_formants, lpc_order, slots", [(5, 10, 5), (5.5, 11, 6), (4, 8, 4), (4.5, 9, 5)])
def test_formant_lpc_order_is_twice_max_formants_with_no_plus_two(max_formants, lpc_order, slots):
    """`max_formants: 5` is LPC order 10, not 12 (schema block description, fon/Sound_to_Formant.cpp)."""
    cfg = praat.FormantConfig(**{**FORMANT_PROV.asdict(), "max_formants": max_formants})
    assert cfg.lpc_order == lpc_order
    assert cfg.formant_slots == slots


# --- the decode path ---------------------------------------------------------------


def test_sound_from_int16_divides_by_32768_exactly_once():
    """Praat must see the same float the spectrum oracle sees: full-scale −32768 → −1.0, +32767 → 1 − 2⁻¹⁵."""
    x = np.array([-32768, 0, 32767], dtype=np.int16)
    snd = praat.sound_from_int16(x, FS)
    np.testing.assert_array_equal(snd.values[0], [-1.0, 0.0, 32767 / 32768])
    assert snd.sampling_frequency == FS
    assert snd.values.shape == (1, 3)


def test_sound_from_int16_honours_the_32767_scale_the_schema_admits():
    snd = praat.sound_from_int16(np.array([32767], dtype=np.int16), FS, int16_scale=32767)
    assert snd.values[0, 0] == 1.0


@pytest.mark.parametrize("bad", [np.zeros(8, dtype=np.float32), np.zeros(8, dtype=np.int32), np.zeros((8, 1), dtype=np.int16)])
def test_sound_from_int16_refuses_floats_other_widths_and_2d(bad):
    """A float array would be scaled twice (−90.3 dB); a 2-D array is channels to Praat."""
    with pytest.raises((TypeError, ValueError)):
        praat.sound_from_int16(bad, FS)


# --- pitch ------------------------------------------------------------------------------


def test_raw_ac_on_pure_440_sine_is_within_1_cent(sine_440):
    """The anchor of the RQ's '≤ 5 cents vs Praat': Praat itself must land on a synthetic 440 Hz to well inside that."""
    track = praat.pitch_track(sine_440, PITCH_PROV)
    assert track.shape == (296, 2)  # the frame count the schema's worked example measured for this input
    assert track.dtype == np.float64
    f0 = track[:, 1]
    assert np.all(f0 > 0), "a steady full-scale sine has no unvoiced frame"
    assert np.abs(np.median(cents(f0, 440.0))) < 1.0
    assert np.max(np.abs(cents(f0, 440.0))) < 1.0


def test_pitch_times_are_praat_frame_centres_not_device_frames(sine_440):
    """Frame-grid trap: Praat's first frame centre is `t1 = (duration − (n−1)·dt)/2`, not 0 — compare by time, never by index."""
    track = praat.pitch_track(sine_440, PITCH_PROV)
    n, dt = track.shape[0], PITCH_PROV.time_step
    t1 = (sine_440.duration - (n - 1) * dt) / 2
    assert track[0, 0] == pytest.approx(t1, abs=1e-9)
    np.testing.assert_allclose(np.diff(track[:, 0]), dt, atol=1e-9)


def test_unvoiced_frames_are_zero_not_nan():
    """Praat writes 0 for unvoiced (`unvoiced_sentinel: 0`); a NaN would poison every cents comparison downstream."""
    x = np.concatenate([silence_int16(1.0), sine_int16(440.0, 1.0), silence_int16(1.0)])
    track = praat.pitch_track(praat.sound_from_int16(x, FS), PITCH_PROV)
    f0 = track[:, 1]
    assert not np.isnan(f0).any()
    in_silence = (track[:, 0] < 0.9) | (track[:, 0] > 2.1)
    assert np.all(f0[in_silence] == praat.UNVOICED_SENTINEL)
    in_tone = (track[:, 0] > 1.1) & (track[:, 0] < 1.9)
    assert np.all(f0[in_tone] > 0)
    assert np.abs(np.median(cents(f0[in_tone], 440.0))) < 1.0


def test_filtered_method_is_refused_below_praat_6_4(sine_440):
    """Invariant 6 in code: a `filtered` track cannot come from the pinned bundle, and the gate must say so before Praat is asked."""
    cfg = praat.PitchConfig(**{**PITCH_PROV.asdict(), "method": "filtered"})
    with pytest.raises(praat.UnsupportedPitchMethod, match="6.4"):
        praat.pitch_track(sine_440, cfg)  # the installed bundle (6.1.38 by test_env.py)
    with pytest.raises(praat.UnsupportedPitchMethod):
        praat.pitch_track(sine_440, cfg, praat_version="6.1.38")
    with pytest.raises(praat.UnsupportedPitchMethod):
        praat.pitch_track(sine_440, cfg, praat_version="6.3.99")


def test_filtered_gate_is_the_only_guard_before_praat(sine_440):
    """If the version gate is told 6.4, the call reaches Praat — which on 6.1.38 refuses the command itself.

    This proves the gate is the one thing standing between the config and the
    command, so a future bundle that registers it will run it with no further
    code change (the argument order is the 6.4 dialogue's).
    """
    cfg = praat.PitchConfig(**{**PITCH_PROV.asdict(), "method": "filtered"})
    with pytest.raises(parselmouth.PraatError, match="not available"):
        praat.pitch_track(sine_440, cfg, praat_version="6.4.0")


@pytest.mark.parametrize("version, expected", [("6.1.38", (6, 1, 38)), ("7.0.01", (7, 0, 1)), ("6.4", (6, 4))])
def test_praat_version_tuple_compares_numerically_not_lexically(version, expected):
    """`"6.10" > "6.4"` is false as strings; the gate must compare integers."""
    assert praat.praat_version_tuple(version) == expected
    assert praat.praat_version_tuple("6.10.0") > praat.praat_version_tuple("6.4.0")


def test_praat_version_tuple_refuses_garbage():
    with pytest.raises(ValueError):
        praat.praat_version_tuple("6.1.38-beta")


def test_cc_method_runs_and_tracks_the_sine(sine_440):
    """`cc` is a schema value; a wrapper that only really implemented `raw` would pass every other test."""
    cfg = praat.PitchConfig(**{**PITCH_PROV.asdict(), "method": "cc"})
    track = praat.pitch_track(sine_440, cfg)
    f0 = track[:, 1]
    assert np.abs(np.median(cents(f0[f0 > 0], 440.0))) < 1.0


class _FakePitch:
    def __init__(self, n: int = 3):
        self._n = n

    def xs(self):
        return np.arange(self._n) * 0.01

    @property
    def selected_array(self):
        return {"frequency": np.full(self._n, 440.0)}


class _RecordingSound:
    """Stands in for `parselmouth.Sound`: records the keyword arguments the wrapper hands to Praat."""

    def __init__(self):
        self.calls: dict[str, dict] = {}

    def to_pitch_ac(self, **kwargs):
        self.calls["ac"] = kwargs
        return _FakePitch()

    def to_pitch_cc(self, **kwargs):
        self.calls["cc"] = kwargs
        return _FakePitch()


#: Every value distinct from every other and from Praat's defaults, so a swapped
#: pair or a dropped field cannot hide behind an equal number.
ODD_PITCH = praat.PitchConfig(
    method="raw",
    time_step=0.007,
    pitch_floor=61.0,
    pitch_ceiling=1234.0,
    silence_threshold=0.11,
    voicing_threshold=0.22,
    octave_cost=0.33,
    octave_jump_cost=0.44,
    voiced_unvoiced_cost=0.55,
    max_candidates=7,
    very_accurate=True,
)


@pytest.mark.parametrize("method", ["raw", "cc"])
def test_raw_and_cc_hand_every_parameter_to_its_own_praat_keyword(method):
    """A swapped pair (octave_cost ↔ octave_jump_cost, silence ↔ voicing) survives every signal test on a clean sine; the binding must be checked name by name."""
    cfg = praat.PitchConfig(**{**ODD_PITCH.asdict(), "method": method})
    snd = _RecordingSound()
    praat.pitch_track(snd, cfg, praat_version="6.1.38")
    kwargs = snd.calls[{"raw": "ac", "cc": "cc"}[method]]
    assert kwargs == {
        "time_step": 0.007,
        "pitch_floor": 61.0,
        "max_number_of_candidates": 7,
        "very_accurate": True,
        "silence_threshold": 0.11,
        "voicing_threshold": 0.22,
        "octave_cost": 0.33,
        "octave_jump_cost": 0.44,
        "voiced_unvoiced_cost": 0.55,
        "pitch_ceiling": 1234.0,
    }
    assert isinstance(kwargs["max_number_of_candidates"], int) and isinstance(kwargs["very_accurate"], bool)


def test_time_step_zero_becomes_parselmouths_none_for_auto():
    """Schema `time_step: 0` is Praat's auto step; parselmouth spells that `None`, and `0.0` would be an error."""
    snd = _RecordingSound()
    praat.pitch_track(snd, praat.PitchConfig(**{**ODD_PITCH.asdict(), "time_step": 0}))
    assert snd.calls["ac"]["time_step"] is None


def test_filtered_call_uses_the_6_4_dialogue_argument_order(monkeypatch):
    """The unreachable path is still code: its positional order is `fon/praat_Sound.cpp`'s form — attenuation sits between very-accurate and silence, top is the third number."""
    recorded = {}

    def fake_call(obj, command, *args):
        recorded["command"] = command
        recorded["args"] = args
        return _FakePitch()

    monkeypatch.setattr(praat, "call", fake_call)
    cfg = praat.PitchConfig(**{**ODD_PITCH.asdict(), "method": "filtered"})
    praat.pitch_track(object(), cfg, praat_version="6.4.0")
    assert recorded["command"] == "To Pitch (filtered autocorrelation)"
    assert recorded["args"] == (0.007, 61.0, 1234.0, 7, True, praat.FILTERED_AC_ATTENUATION_AT_TOP, 0.11, 0.22, 0.33, 0.44, 0.55)


def test_raw_ac_wrapper_equals_praats_own_positional_script_form():
    """`Sound.to_pitch_ac(**kw)` and `praat.call(snd, "To Pitch (ac)", …)` are two bindings of one command; on a noisy, gapped, vibrato signal with non-default parameters the tracks must be identical."""
    rng = np.random.default_rng(0)
    t = np.arange(int(2.0 * FS)) / FS
    f0 = 220.0 * 2 ** (0.03 * np.sin(2 * np.pi * 5 * t))
    ph = 2 * np.pi * np.cumsum(f0) / FS
    sig = np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.3 * np.sin(3 * ph)
    envelope = np.ones_like(t)
    envelope[(t > 0.6) & (t < 0.9)] = 0.05
    envelope[(t > 1.4) & (t < 1.5)] = 0.0
    x = np.rint(12000 * envelope * sig + 2500 * rng.standard_normal(t.size)).astype(np.int16)
    snd = praat.sound_from_int16(x, FS)
    cfg = praat.PitchConfig(
        method="raw",
        time_step=0.01,
        pitch_floor=65,
        pitch_ceiling=1100,
        silence_threshold=0.1,
        voicing_threshold=0.3,
        octave_cost=0.1,
        octave_jump_cost=0.1,
        voiced_unvoiced_cost=0.3,
        max_candidates=4,
        very_accurate=True,
    )
    track = praat.pitch_track(snd, cfg)
    oracle = parselmouth.praat.call(snd, "To Pitch (ac)", 0.01, 65.0, 4, True, 0.1, 0.3, 0.1, 0.1, 0.3, 1100.0)
    ref = np.asarray(oracle.selected_array["frequency"], dtype=np.float64)
    np.testing.assert_array_equal(track[:, 1], ref)
    np.testing.assert_array_equal(track[:, 0], np.asarray(oracle.xs()))
    assert 0 < (ref > 0).sum() < ref.size, "the signal must have both voiced and unvoiced frames for the path costs to matter"


# --- formants and LTAS ------------------------------------------------------------------


def test_formant_track_has_time_plus_value_bandwidth_pairs_and_nan_where_praat_has_none(sine_440):
    """Columns `time, F1, B1, …` for every slot Praat allocates; missing formants are NaN, never 0 (0 Hz would be a 'formant')."""
    track = praat.formant_track(sine_440, FORMANT_PROV)
    assert track.shape[1] == 1 + 2 * FORMANT_PROV.formant_slots == 11
    assert track.dtype == np.float64
    np.testing.assert_allclose(np.diff(track[:, 0]), FORMANT_PROV.time_step, atol=1e-9)
    f1 = track[:, 1]
    assert np.all(np.isfinite(f1)) and np.all(f1 > 0)
    b1 = track[:, 2]
    assert np.all(np.isfinite(b1)) and np.all(b1 > 0)
    # Value and bandwidth columns must not be interchangeable: the sine's first
    # pole sits near 440 Hz (Praat 6.1.38 measures ≈ 421 Hz with this config)
    # with a bandwidth of a few Hz; a swap puts ≈ 2.5 in the F1 column.
    assert 400.0 < np.median(f1) < 480.0
    assert np.median(b1) < 10.0
    f5 = track[:, 9]
    assert np.isnan(f5).any(), "a pure sine does not fill five formant slots; Praat's undefined must surface as NaN"
    assert not (track[:, 1:] == 0).any()


def test_ltas_bands_are_centred_on_bandwidth_grid_and_peak_at_the_tone(sine_440):
    """`To Ltas` band k is centred at (k + ½)·bandwidth; a 440 Hz tone must peak in the 400–500 Hz band."""
    out = praat.ltas(sine_440, praat.LtasConfig(bandwidth_hz=100))
    assert out.shape == (FS // 2 // 100, 2) == (160, 2)
    np.testing.assert_allclose(out[:, 0], 50 + 100 * np.arange(160))
    assert out[np.argmax(out[:, 1]), 0] == 450.0


def test_ltas_level_is_praat_db_re_20_micropascal_not_dbfs(sine_440):
    """Praat's axis: 1.0 = 1 Pa, level = 10·log10(P/4e-10). A half-scale sine's peak band sits near 65 dB, nowhere near 0 dBFS."""
    out = praat.ltas(sine_440, praat.LtasConfig(bandwidth_hz=100))
    peak = out[:, 1].max()
    # Measured 2026-08-21 on the pinned bundle: 64.94 dB. A ±1 dB band guards the
    # convention (a dBFS-style reference would read about −6 dB here), not the digit.
    assert 63.0 < peak < 67.0


def test_spectrogram_returns_praat_grid_and_linear_psd(sine_440):
    """Implemented-not-used in H0: the shapes must still agree with Praat's own grid so H1 does not start from a stub."""
    cfg = praat.SpectrogramConfig(window_shape="gaussian", window_length=0.005, time_step=0.002, frequency_step=20, max_frequency=8000)
    times, freqs, values = praat.spectrogram(sine_440, cfg)
    assert values.shape == (freqs.size, times.size)
    assert values.min() >= 0.0, "Praat's Spectrogram values are linear power density, not dB"
    assert freqs[np.argmax(values.mean(axis=1))] == pytest.approx(440.0, abs=cfg.frequency_step)


# --- hashing ------------------------------------------------------------------------------


def _package_copy(repo_root, tmp_path):
    """A relocated copy of the package in a fake repo root, so `generator_sha256` can be computed on an edited tree."""
    fake_root = tmp_path / "repo"
    copy = fake_root / envmod.PACKAGE_RELPATH
    shutil.copytree(repo_root / envmod.PACKAGE_RELPATH, copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return fake_root, copy


def test_generator_digest_changes_when_a_numerics_module_changes(repo_root, tmp_path):
    """`generator.sha256` covers `GENERATOR_TREE`; a one-byte edit to the oracle or a wrapper must move it (ADR 0009: a generator change is visible in the manifest diff)."""
    fake_root, copy = _package_copy(repo_root, tmp_path)
    baseline = envmod.generator_sha256(fake_root)
    assert baseline == envmod.generator_sha256(repo_root), "a relocated identical tree must hash identically (path-independent)"
    for rel in ("praat.py", "spectrum.py", "golden/sets.py"):
        target = copy / rel
        original = target.read_bytes()
        target.write_bytes(original + b"\n# touched\n")
        assert envmod.generator_sha256(fake_root) != baseline, rel
        target.write_bytes(original)
    assert envmod.generator_sha256(fake_root) == baseline


def test_generator_digest_ignores_modules_that_cannot_change_a_vector(repo_root, tmp_path):
    """The CLI, the verifier, the manifest I/O and the preset loader are outside `GENERATOR_TREE`: editing them must NOT turn every committed set red on I4 (the whole-package digest of the first H0 draft did exactly that)."""
    fake_root, copy = _package_copy(repo_root, tmp_path)
    baseline = envmod.generator_sha256(fake_root)
    for rel in ("golden/cli.py", "golden/verify.py", "golden/manifest.py", "presets.py", "__init__.py"):
        target = copy / rel
        target.write_bytes(target.read_bytes() + b"\n# touched\n")
    (copy / "scratch_not_a_module.py").write_text("pass\n")
    assert envmod.generator_sha256(fake_root) == baseline


def test_generator_tree_names_every_module_the_generator_imports_for_numerics(repo_root):
    """Every `spectral_host` module that `generate.py` or `sets.py` imports (transitively, within the package) is either in `GENERATOR_TREE` or in the explicit non-numerics list — a new numerics module cannot be forgotten silently."""
    import ast

    pkg = repo_root / envmod.PACKAGE_RELPATH
    non_numerics = {"golden/cli.py", "golden/verify.py", "golden/manifest.py", "presets.py", "__init__.py", "golden/__init__.py"}

    def imports_of(rel):
        tree = ast.parse((pkg / rel).read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("spectral_host"):
                mod = node.module
                names.add(mod)
                for alias in node.names:
                    names.add(f"{mod}.{alias.name}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("spectral_host"):
                        names.add(alias.name)
        rels = set()
        for name in names:
            rel_candidate = name.removeprefix("spectral_host").lstrip(".").replace(".", "/") + ".py"
            if rel_candidate != ".py" and (pkg / rel_candidate).is_file():
                rels.add(rel_candidate)
        return rels

    seen, todo = set(), {"golden/generate.py", "golden/sets.py"}
    while todo:
        rel = todo.pop()
        seen.add(rel)
        todo |= imports_of(rel) - seen
    for rel in sorted(seen):
        assert rel in envmod.GENERATOR_TREE or rel in non_numerics, f"{rel} is reachable from the generator but listed nowhere"
    for rel in envmod.GENERATOR_TREE:
        assert (pkg / rel).is_file(), rel
    assert all((pkg / rel).is_file() for rel in non_numerics)
    assert not set(envmod.GENERATOR_TREE) & non_numerics


def test_sha256_files_refuses_a_missing_or_duplicate_entry(tmp_path):
    """A listed file that is absent must be an error, never a silently shorter digest; a duplicate would double-count bytes."""
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("y = 2\n")
    both = hashing.sha256_files(tmp_path, ["b.py", "a.py"])
    assert both == hashing.sha256_files(tmp_path, ["a.py", "b.py"]), "the list is sorted by the recipe, not by the caller"
    assert both == hashing.sha256_tree(tmp_path), "over the same files, the explicit and the walked recipe agree"
    with pytest.raises(FileNotFoundError):
        hashing.sha256_files(tmp_path, ["a.py", "missing.py"])
    with pytest.raises(ValueError, match="duplicate"):
        hashing.sha256_files(tmp_path, ["a.py", "a.py"])
    with pytest.raises(ValueError, match="empty"):
        hashing.sha256_files(tmp_path, [])


def test_generator_tree_hash_changes_on_rename_but_not_on_bytecode(tmp_path):
    """The relative path is part of the digest (a rename is a change); __pycache__ is not (a test run is not)."""
    tree = tmp_path / "pkg"
    tree.mkdir()
    (tree / "a.py").write_text("x = 1\n")
    (tree / "b.py").write_text("y = 2\n")
    baseline = hashing.sha256_tree(tree)
    (tree / "__pycache__").mkdir()
    (tree / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"\x00" * 16)
    # CPython writes `<name>.pyc.<pid>` temp files while compiling: not `.pyc`
    # by suffix, so the DIRECTORY exclusion must carry this one on its own.
    (tree / "__pycache__" / "a.cpython-312.pyc.140123").write_bytes(b"\x00" * 16)
    assert hashing.sha256_tree(tree) == baseline
    (tree / "stray.pyc").write_bytes(b"\x00" * 16)
    assert hashing.sha256_tree(tree) == baseline, "a .pyc outside __pycache__ is still interpreter output"
    (tree / "b.py").rename(tree / "c.py")
    assert hashing.sha256_tree(tree) != baseline


def test_tree_hash_is_order_independent_and_length_prefixed(tmp_path):
    """Without the length prefix, `{a: "X", b: "Y"}` and `{a: "Xb\\0Y"}` feed sha256 the identical stream `a\\0Xb\\0Y`.

    The path/data separator alone cannot keep them apart, because a file's
    bytes may contain a NUL followed by another file's name; the length
    prefix is what makes the framing unambiguous. (The earlier form of this
    test, `ab|c` vs `a|bc`, was separated by the NUL already and passed with
    the prefix removed.)
    """
    t1 = tmp_path / "t1"
    t2 = tmp_path / "t2"
    for t in (t1, t2):
        t.mkdir()
    (t1 / "a").write_bytes(b"X")
    (t1 / "b").write_bytes(b"Y")
    (t2 / "a").write_bytes(b"Xb\0Y")
    assert hashing.sha256_tree(t1) != hashing.sha256_tree(t2)
    assert [rel for rel, _ in hashing.tree_files(t1)] == ["a", "b"]


def test_tree_hash_refuses_an_empty_tree(tmp_path):
    with pytest.raises(ValueError, match="empty"):
        hashing.sha256_tree(tmp_path)


def test_sha256_file_equals_sha256_bytes(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(bytes(range(256)) * 3)
    assert hashing.sha256_file(p) == hashing.sha256_bytes(p.read_bytes())


# --- env ---------------------------------------------------------------------------------------


def test_captured_generator_block_validates_against_the_schema(repo_root, schema):
    """What `capture()` returns is what the generator will write; it must pass the schema's `generator` sub-schema as-is."""
    block = envmod.capture(repo_root).asdict()
    generator_schema = {**schema["properties"]["generator"], "$defs": schema["$defs"]}
    assert list(jsonschema.Draft202012Validator(generator_schema).iter_errors(block)) == []
    assert block["praat_reference"] is None  # T7b open: the only value this module writes on its own
    assert block["praat_bundled"] == parselmouth.PRAAT_VERSION
    assert block["parselmouth"] == parselmouth.__version__
    assert block["sha256"] == envmod.generator_sha256(repo_root)
    assert block["sha256"] == hashing.sha256_files(repo_root / envmod.PACKAGE_RELPATH, envmod.GENERATOR_TREE)
    assert block["script"] == envmod.PACKAGE_RELPATH
    assert len(block["commit"]) == 40


def test_blas_string_names_a_vendor_and_a_version():
    """`generator.blas` exists because reduction order differs by vendor; 'unknown unknown' would be recorded, but loudly."""
    s = envmod.blas_string()
    assert s and " " in s
    assert s.split(" ", 1)[0] != ""


def test_is_dirty_sees_an_untracked_file_inside_the_package(tmp_path):
    """The generator refuses a dirty host/src; an untracked file is in the tree hash but in no commit, so it must count."""
    import subprocess

    repo = tmp_path / "repo"
    pkg = repo / envmod.PACKAGE_RELPATH
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init"], check=True
    )
    assert not envmod.is_dirty(repo, [envmod.PACKAGE_RELPATH])
    (pkg / "scratch.py").write_text("pass\n")
    assert envmod.is_dirty(repo, [envmod.PACKAGE_RELPATH])
    (pkg / "scratch.py").unlink()
    (pkg / "__init__.py").write_text("# edited\n")
    assert envmod.is_dirty(repo, [envmod.PACKAGE_RELPATH])
    assert envmod.git_head(repo) == subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def test_format_env_is_valid_yaml_with_null_for_open_t7b(repo_root):
    text = envmod.format_env(envmod.capture(repo_root))
    doc = yaml.safe_load(text)
    assert list(doc) == list(envmod.GENERATOR_KEYS)
    assert doc["praat_reference"] is None
    assert doc == envmod.capture(repo_root).asdict()


def test_format_env_keeps_a_two_part_version_a_string_not_a_yaml_float(repo_root):
    """`praat_reference: 7.0` unquoted is the float 7.0 to every YAML reader; the pin chain is strings or nothing."""
    doc = yaml.safe_load(envmod.format_env(envmod.capture(repo_root, praat_reference="7.0")))
    assert doc["praat_reference"] == "7.0" and isinstance(doc["python"], str)


# --- wavio ---------------------------------------------------------------------------------------


def test_read_wav_returns_the_files_int16_unscaled(tmp_path):
    """No scaling here: the int16 → float seam is applied once, later, by the consumer."""
    x = sine_int16(440.0, 0.1)
    wav = wavio.read_wav(write_wav(tmp_path / "s.wav", x, FS))
    assert wav.sample_rate == FS and wav.channels == 1 and wav.bit_depth == 16
    assert wav.samples.dtype == np.int16 and wav.samples.shape == (x.size, 1)
    np.testing.assert_array_equal(wav.mono, x)
    assert wav.duration_s == pytest.approx(0.1)


@pytest.mark.parametrize("sampwidth", [1, 3, 4])
def test_read_wav_refuses_non_16_bit_pcm_instead_of_converting(tmp_path, sampwidth):
    """`inputs[].bit_depth: 16` must describe the bytes; a reader that converted 24-bit to int16 would make it a lie."""
    n = 100
    raw = np.zeros(n * sampwidth, dtype=np.uint8)
    path = write_wav(tmp_path / f"w{sampwidth}.wav", raw, FS, sampwidth=sampwidth)
    with pytest.raises(wavio.UnsupportedWav, match=f"{8 * sampwidth}-bit"):
        wavio.read_wav(path)


def test_read_wav_refuses_to_downmix_stereo(tmp_path):
    """Summing channels changes the level by an unstated convention; `mono` must refuse, and `samples[:, k]` still works."""
    left = sine_int16(440.0, 0.05)
    right = np.zeros_like(left)
    interleaved = np.empty(2 * left.size, dtype=np.int16)
    interleaved[0::2], interleaved[1::2] = left, right
    wav = wavio.read_wav(write_wav(tmp_path / "st.wav", interleaved, FS, channels=2))
    assert wav.channels == 2 and wav.samples.shape == (left.size, 2)
    np.testing.assert_array_equal(wav.samples[:, 0], left)
    with pytest.raises(ValueError, match="down-mix"):
        _ = wav.mono


@pytest.mark.parametrize("payload", [b"RIFF\x00\x00\x00\x00WAVEjunk", b"", b"RIFF"])
def test_read_wav_refuses_a_non_wav_or_truncated_file(tmp_path, payload):
    """`wave` raises EOFError (not wave.Error) on an empty or truncated header; the caller still sees one exception type."""
    p = tmp_path / "not.wav"
    p.write_bytes(payload)
    with pytest.raises(wavio.UnsupportedWav):
        wavio.read_wav(p)


def test_wav_round_trip_through_sound_from_int16_matches_in_memory_decode(tmp_path):
    """The single decode path: reading a WAV and decoding the array must give Praat the same Sound as the array directly."""
    x = sine_int16(440.0, 0.2)
    wav = wavio.read_wav(write_wav(tmp_path / "rt.wav", x, FS))
    a = praat.sound_from_int16(wav.mono, wav.sample_rate)
    b = praat.sound_from_int16(x, FS)
    np.testing.assert_array_equal(a.values, b.values)
