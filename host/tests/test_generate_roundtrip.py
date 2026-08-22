# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""`sets.py` + `generate.py` against ADR 0009 decision 4, by hazard (roadmap H0, unit B-U6).

Positive control: a two-input mini set — two sines written in-test, a Tier-0
style dataset manifest describing them, a stand-in generator package and a
stand-in tolerance table committed in a temporary git checkout — generated
into `tmp_path` and verified green with every rule on. Around it, one test
per way the generator could write a confidently wrong manifest: an output
byte flipped (I4), a ceiling below the floor (I1), an existing set directory,
a missing or drifted input WAV, a dirty package tree, a red self-verify.

The real set's declaration is checked against the real dataset manifest
(`test_tier0_set_inputs_are_exactly_the_32k_manifest_entries`) and against
the pins ADR 0009 / ADR 0006 / golden-files.md name, without running Praat
on it — generating `tier0-synthetic` is `spectral-golden generate`'s job,
done once, reviewed, committed.

Run: `uv run --project host pytest -q host/tests/test_generate_roundtrip.py`
"""

from __future__ import annotations

import os
import subprocess
import sys
import wave
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pytest
import yaml

from spectral_host import env as env_mod
from spectral_host import praat, spectrum
from spectral_host.golden import cli, generate, manifest, sets, verify
from spectral_host.hashing import sha256_file

FS = 32000
SECONDS = 1.0
MINI_SET = "mini-roundtrip"
MINI_DATASET = "datasets/tier0-mini"
STEM_440 = "sine_440_m20dBFS_32k"
STEM_1000 = "sine_1000_m20dBFS_32k"
NPY_MAGIC_V1_0 = b"\x93NUMPY\x01\x00"
ONE_MIB = 1 << 20


# --- building the mini repository ------------------------------------------------------


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", os.fspath(root), *args], capture_output=True, text=True, check=True)
    return proc.stdout.strip()


def write_sine_wav(path: Path, f0: float, amplitude: int = 3277) -> None:
    """A 16-bit mono PCM WAV of `SECONDS` of a sine at FS (3277 counts ≈ −20 dBFS: no clipping)."""
    n = int(round(SECONDS * FS))
    x = np.rint(amplitude * np.sin(2 * np.pi * f0 * np.arange(n) / FS)).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(os.fspath(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(FS)
        wf.writeframes(x.tobytes())


def dataset_manifest(root: Path, stems_and_f0: dict[str, float]) -> dict:
    """The `synth_signals` manifest shape — `files[]` plus `ground_truth.files` — for the in-test WAVs."""
    files, truths = [], {}
    for stem, f0 in stems_and_f0.items():
        wav = root / MINI_DATASET / f"{stem}.wav"
        files.append(
            {"path": f"{stem}.wav", "sha256": sha256_file(wav), "sample_rate": FS, "channels": 1, "bit_depth": 16, "duration": SECONDS}
        )
        truths[stem] = {
            "generator": "synth_signals.signals.sine",
            "parameters": {"f_hz": f0, "level_dbfs": -20.0, "phase_rad": 0.0},
            "samples": int(SECONDS * FS),
            "host_only": False,
        }
    return {"name": "tier0-mini", "tier": 0, "ground_truth": {"kind": "exact by construction", "files": truths}, "files": files}


MINI_SPEC = sets.SetSpec(
    name=MINI_SET,
    dataset=MINI_DATASET,
    inputs=(STEM_440, STEM_1000),
    analyses={
        "pitch": sets.TIER0_PITCH,
        "formant": sets.TIER0_FORMANT,
        "ltas": sets.TIER0_LTAS,
        "spectrum": sets.TIER0_SPECTRUM,
    },
    outputs={
        "pitch": (STEM_440, STEM_1000),
        "formant": (STEM_440,),
        "ltas": (STEM_1000,),
        "spectrum": (STEM_440, STEM_1000),
    },
    notes="mini round-trip set for the generator tests",
)


@dataclass
class MiniRepo:
    root: Path
    head: str

    @property
    def set_dir(self) -> Path:
        return self.root / manifest.OUTPUTS_RELPATH / MINI_SET

    @property
    def manifest_path(self) -> Path:
        return manifest.manifest_path(self.root, MINI_SET)

    @property
    def package_dir(self) -> Path:
        return self.root / "host" / "src" / "spectral_host"

    def wav(self, stem: str) -> Path:
        return self.root / MINI_DATASET / f"{stem}.wav"

    def generate(self, allow_dirty: bool = False, reason: str = "initial generation") -> Path:
        return generate.generate_set(MINI_SET, self.root, "host tests", reason, allow_dirty)

    def doc(self) -> dict:
        doc = manifest.load(self.manifest_path)
        assert isinstance(doc, dict)
        return doc

    def rewrite(self, doc: dict) -> None:
        self.manifest_path.write_bytes(manifest.dump(doc))

    def verify(self, notices: list[str] | None = None) -> list[verify.Failure]:
        return verify.verify_manifest(self.manifest_path, self.root, check_env=True, notices=notices)

    def fired(self) -> set[str]:
        return {f.rule for f in self.verify()}


@pytest.fixture
def mini(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MiniRepo:
    """A git checkout with the stand-in package and tolerance table committed, the WAVs and their manifest on disk."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "host tests")
    (root / "CLAUDE.md").write_text("stand-in\n", encoding="utf-8")
    pkg = root / "host" / "src" / "spectral_host"
    (pkg / "golden").mkdir(parents=True)
    (pkg / "__init__.py").write_text("# stand-in generator package\n", encoding="utf-8")
    for rel in env_mod.GENERATOR_TREE:  # I4 digests exactly these; every one must exist in the stand-in
        (pkg / rel).write_text(f"# stand-in {rel}\n", encoding="utf-8")
    tol = root / generate.TOLERANCES_SOURCE
    tol.parent.mkdir(parents=True)
    tol.write_text("# stand-in tolerance table\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "initial")
    head = git(root, "rev-parse", "HEAD")

    stems = {STEM_440: 440.0, STEM_1000: 1000.0}
    for stem, f0 in stems.items():
        write_sine_wav(root / MINI_DATASET / f"{stem}.wav", f0)
    (root / MINI_DATASET / generate.DATASET_MANIFEST_FILENAME).write_text(
        yaml.safe_dump(dataset_manifest(root, stems), sort_keys=False), encoding="utf-8"
    )
    monkeypatch.setitem(sets.SETS, MINI_SET, MINI_SPEC)
    return MiniRepo(root=root, head=head)


# --- positive control -------------------------------------------------------------------


def test_roundtrip_generates_a_set_that_verifies_clean_with_no_notice(mini):
    """The generator's own output passes every rule, with check_env on, in the environment that wrote it."""
    path = mini.generate()
    assert path == mini.manifest_path
    notices: list[str] = []
    assert mini.verify(notices) == []
    assert notices == []
    doc = mini.doc()
    assert doc["set"] == MINI_SET and doc["schema"] == manifest.SCHEMA_VERSION
    assert [o["path"].rsplit("/", 1)[1] for o in doc["outputs"]] == [
        f"pitch_{STEM_440}.npy",
        f"pitch_{STEM_1000}.npy",
        f"formant_{STEM_440}.npy",
        f"ltas_{STEM_1000}.npy",
        f"spectrum_{STEM_440}.npy",
        f"spectrum_{STEM_1000}.npy",
    ]
    assert doc["generator"]["commit"] == mini.head
    assert doc["generator"]["praat_reference"] is None, "T7b is open: praat_reference must be null, never invented"
    assert doc["tolerances"] == {"source": generate.TOLERANCES_SOURCE, "revision": mini.head}
    assert doc["regeneration"]["previous_manifest_sha256"] is None and doc["regeneration"]["previous_set"] is None
    assert doc["regeneration"]["approved_by"] == "host tests"


def test_manifest_keys_follow_schema_order_so_the_diff_reads_top_down(mini):
    mini.generate()
    doc = mini.doc()
    assert list(doc) == ["schema", "set", "generated", "generator", "inputs", "analyses", "windows", "outputs", "tolerances", "regeneration", "notes"]
    assert list(doc["analyses"]) == ["pitch", "formant", "ltas", "spectrum"]
    assert list(doc["generator"]) == list(env_mod.GENERATOR_KEYS)


def test_pitch_outputs_carry_the_unvoiced_sentinel_and_praats_frame_centres(mini):
    mini.generate()
    doc = mini.doc()
    pitch_outputs = [o for o in doc["outputs"] if o["analysis"] == "pitch"]
    assert len(pitch_outputs) == 2
    for out in pitch_outputs:
        assert out["unvoiced_sentinel"] == 0 and out["columns"] == ["time", "f0"] and out["units"] == "s, Hz"
        arr = np.load(mini.root / out["path"], allow_pickle=False)
        assert arr.shape == tuple(out["shape"]) and arr.dtype.name == out["dtype"] == "float64"
        # Praat's grid, not the device's: the first frame centre is > 0, the step is the config's
        assert arr[0, 0] > 0.0 and arr[1, 0] - arr[0, 0] == pytest.approx(sets.TIER0_PITCH.time_step)
    f0 = np.load(mini.root / pitch_outputs[0]["path"], allow_pickle=False)[:, 1]
    assert np.median(f0[f0 > 0]) == pytest.approx(440.0, abs=0.05)


def test_inputs_copy_parameters_verbatim_from_the_dataset_manifest(mini):
    mini.generate()
    doc = mini.doc()
    dataset = yaml.safe_load((mini.root / MINI_DATASET / "manifest.yaml").read_text(encoding="utf-8"))
    assert [i["path"] for i in doc["inputs"]] == [f"{MINI_DATASET}/{STEM_440}.wav", f"{MINI_DATASET}/{STEM_1000}.wav"]
    for inp, stem in zip(doc["inputs"], (STEM_440, STEM_1000)):
        truth = dataset["ground_truth"]["files"][stem]
        assert inp["source"] == {"kind": "tier0-synthetic", "name": truth["generator"], "parameters": truth["parameters"]}
        assert inp["sha256"] == sha256_file(mini.wav(stem))
        assert (inp["sample_rate"], inp["bit_depth"], inp["channels"], inp["duration_s"]) == (FS, 16, 1, SECONDS)


def test_windows_block_carries_all_seven_families_at_each_window_length(mini):
    """ADR 0006 D1 / schema "1.1": the device lane can check every table it can build, not only hann."""
    mini.generate()
    windows = mini.doc()["windows"]
    assert [(w["family"], w["n"]) for w in windows] == [(f, 4096) for f in spectrum.WINDOW_FAMILIES]
    for w in windows:
        assert w["coefficients"] == spectrum.WINDOW_FAMILIES[w["family"]]
        assert w["sha256"] == spectrum.window_table_sha256(w["family"], w["n"])
    assert {w["family"] for w in windows} == set(spectrum.PRESET_WINDOW_FAMILIES) | {"rect"}


def test_every_output_array_is_under_one_megabyte(mini):
    mini.generate()
    for out in mini.doc()["outputs"]:
        assert (mini.root / out["path"]).stat().st_size < ONE_MIB, out["path"]


def test_npy_files_are_format_1_0_float64_c_order_and_load_without_pickle(mini):
    mini.generate()
    for out in mini.doc()["outputs"]:
        path = mini.root / out["path"]
        assert path.read_bytes()[: len(NPY_MAGIC_V1_0)] == NPY_MAGIC_V1_0, f"{path.name}: not .npy format 1.0"
        arr = np.load(path, allow_pickle=False)
        assert arr.dtype == np.float64 and arr.flags["C_CONTIGUOUS"]
        assert list(arr.shape) == out["shape"]


def test_formant_output_has_time_plus_five_value_bandwidth_pairs(mini):
    mini.generate()
    out = next(o for o in mini.doc()["outputs"] if o["analysis"] == "formant")
    assert out["columns"] == ["time", "F1", "B1", "F2", "B2", "F3", "B3", "F4", "B4", "F5", "B5"]
    assert out["units"] == "s" + ", Hz" * 10
    assert out["shape"][1] == 11


# --- the hazards --------------------------------------------------------------------------


def test_flipping_one_byte_of_an_output_is_caught_by_i4(mini):
    mini.generate()
    out = mini.doc()["outputs"][-1]
    path = mini.root / out["path"]
    data = bytearray(path.read_bytes())
    data[-1] ^= 0x01
    path.write_bytes(bytes(data))
    failures = mini.verify()
    assert {f.rule for f in failures} == {"I4"}
    assert any(out["path"] in f.message for f in failures)


def test_pitch_ceiling_below_floor_is_refused_at_spec_time(mini):
    """The generator cannot even build such a spec: PitchConfig refuses it with invariant 1's own words."""
    with pytest.raises(ValueError, match="invariant 1"):
        replace(sets.TIER0_PITCH, pitch_floor=1100, pitch_ceiling=65)


def test_pitch_ceiling_below_floor_in_a_written_manifest_fires_i1(mini):
    mini.generate()
    doc = mini.doc()
    doc["analyses"]["pitch"]["pitch_ceiling"] = 10
    mini.rewrite(doc)
    assert "I1" in mini.fired()


def test_existing_set_directory_is_refused_not_overwritten(mini):
    first = mini.generate()
    before = first.read_bytes()
    with pytest.raises(generate.ExistingSet, match="never edited"):
        mini.generate(reason="second attempt")
    assert first.read_bytes() == before


def test_missing_wavs_say_run_synth_signals_generate_first(mini):
    mini.wav(STEM_1000).unlink()
    with pytest.raises(generate.MissingInputs, match="run synth_signals generate first"):
        mini.generate()
    assert not mini.set_dir.exists(), "nothing may be written when a precondition fails"


def test_drifted_wav_bytes_break_the_chain_of_custody(mini):
    path = mini.wav(STEM_440)
    data = bytearray(path.read_bytes())
    data[-2] ^= 0x01  # one sample, one bit
    path.write_bytes(bytes(data))
    with pytest.raises(generate.InputDigestMismatch, match="dataset manifest records"):
        mini.generate()
    assert not mini.set_dir.exists()


def test_wav_header_disagreeing_with_the_dataset_manifest_is_refused(mini):
    dataset_path = mini.root / MINI_DATASET / "manifest.yaml"
    doc = yaml.safe_load(dataset_path.read_text(encoding="utf-8"))
    doc["files"][0]["sample_rate"] = 48000  # the bytes still hash right; the row lies about the rate
    dataset_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    with pytest.raises(generate.InputDigestMismatch, match="sample_rate"):
        mini.generate()


def test_dirty_package_tree_is_refused_unless_allowed_and_then_recorded_in_notes(mini):
    (mini.package_dir / "scratch.py").write_text("# untracked\n", encoding="utf-8")
    with pytest.raises(generate.DirtyGenerator, match="uncommitted"):
        mini.generate()
    assert not mini.set_dir.exists()
    mini.generate(allow_dirty=True, reason="tests: generated from a dirty stand-in tree on purpose")
    doc = mini.doc()
    assert "DIRTY host/src/spectral_host" in doc["notes"]
    assert doc["generator"]["commit"] == mini.head
    assert mini.verify() == []  # the tree hash is of what is on disk, so I4 still agrees


def test_clean_tree_leaves_no_dirty_note(mini):
    mini.generate()
    assert "DIRTY" not in mini.doc()["notes"]


def test_unknown_set_is_refused_with_the_known_names(mini):
    with pytest.raises(generate.GenerateError, match="tier0-synthetic"):
        generate.generate_set("no-such-set", mini.root, "host tests", "initial generation")


def test_empty_reason_or_approver_is_refused(mini):
    with pytest.raises(generate.GenerateError, match="approved_by and reason"):
        generate.generate_set(MINI_SET, mini.root, " ", "initial generation")
    with pytest.raises(generate.GenerateError, match="approved_by and reason"):
        generate.generate_set(MINI_SET, mini.root, "host tests", "")


def test_red_self_verify_raises_and_leaves_the_files_for_inspection(mini, monkeypatch):
    def red(path, root, check_env=True, *, schema=None, notices=None):
        return [verify.Failure("I4", "injected")]

    monkeypatch.setattr(generate.verify_mod, "verify_manifest", red)
    with pytest.raises(generate.VerificationFailed, match="left in place"):
        mini.generate()
    assert mini.manifest_path.is_file()


def test_praat_blocks_are_fed_through_the_32768_seam_once_per_input(mini, monkeypatch):
    """ADR 0003 d.2 / ADR 0006 D3: the int16 → Sound seam is 1/32768, not 32767, and one Sound serves pitch/formant/ltas.

    Mutation this guards: generate.py building the Sound with 32767 — a 0.00026 dB
    shift that no tolerance row could see, which is exactly why it is asserted
    at the seam instead of measured downstream.
    """
    calls: list[int] = []
    real = praat.sound_from_int16

    def spy(x, fs, int16_scale=spectrum.DEFAULT_INT16_SCALE):
        calls.append(int(int16_scale))
        return real(x, fs, int16_scale)

    monkeypatch.setattr(generate.praat, "sound_from_int16", spy)
    mini.generate()
    assert calls == [32768, 32768], "one Sound per input, each through the 32768 seam"


def test_generator_never_imports_synth_signals(mini):
    """ADR 0004: the dataset manifest is read as data; the Apache generator package is never imported."""
    source = Path(generate.__file__).read_text(encoding="utf-8")
    assert "import synth_signals" not in source and "from synth_signals" not in source
    assert "sys.path" not in source
    mini.generate()
    assert not any(m == "synth_signals" or m.startswith("synth_signals.") for m in sys.modules)


# --- the console script ---------------------------------------------------------------


def test_cli_generate_exit_codes(mini, capsys):
    argv = ["generate", "--set", MINI_SET, "--approved-by", "host tests", "--reason", "initial generation", "--repo-root", str(mini.root)]
    assert cli.main(argv) == 0
    assert "verify: ok" in capsys.readouterr().out
    assert cli.main(argv) == 2  # existing set directory: refused
    assert "never edited" in capsys.readouterr().err
    assert cli.main(["generate", "--set", "nope", "--approved-by", "x", "--reason", "y", "--repo-root", str(mini.root)]) == 2


def test_cli_generate_exits_1_when_its_own_verify_is_red(mini, monkeypatch, capsys):
    monkeypatch.setattr(generate.verify_mod, "verify_manifest", lambda *a, **k: [verify.Failure("N1", "injected")])
    argv = ["generate", "--set", MINI_SET, "--approved-by", "host tests", "--reason", "initial generation", "--repo-root", str(mini.root)]
    assert cli.main(argv) == 1
    assert "N1: injected" in capsys.readouterr().err


def test_cli_generate_is_no_longer_the_not_implemented_stub():
    proc = subprocess.run([sys.executable, "-m", "spectral_host.golden.cli", "generate"], capture_output=True, text=True, check=False)
    assert proc.returncode == 2 and "required" in proc.stderr and "not implemented" not in proc.stderr


# --- SetSpec self-consistency -------------------------------------------------------------


@pytest.mark.parametrize(
    "field, value, match",
    [
        ("outputs", {"pitch": ("not_an_input",)}, "invariant 2"),
        ("outputs", {"ltas": (STEM_440,), "spectrogram": (STEM_440,)}, "analyses.spectrogram"),
        ("outputs", {"pitch": (STEM_440, STEM_440)}, "twice"),
        ("outputs", {}, "at least one output"),
        ("inputs", (STEM_440, STEM_440), "duplicate"),
        ("analyses", {"pitch": sets.TIER0_FORMANT}, "must be a PitchConfig"),
        ("analyses", {}, "at least one analysis"),
        ("window_families", ("hann", "kaiser"), "not a window family"),
    ],
)
def test_set_spec_refuses_a_declaration_that_cannot_verify(field, value, match):
    with pytest.raises(sets.SetSpecError, match=match):
        replace(MINI_SPEC, **{field: value})


def test_planned_outputs_are_schema_ordered_then_input_ordered():
    assert MINI_SPEC.planned_outputs() == (
        ("pitch", STEM_440),
        ("pitch", STEM_1000),
        ("formant", STEM_440),
        ("ltas", STEM_1000),
        ("spectrum", STEM_440),
        ("spectrum", STEM_1000),
    )
    assert MINI_SPEC.window_sizes == (4096,)


# --- the real set's declaration, against the real dataset manifest ------------------------


def test_tier0_set_inputs_are_exactly_the_32k_manifest_entries(repo_root, tier0_dir):
    """The set lists every non-host_only entry of datasets/tier0-synthetic/manifest.yaml, in its order, and nothing else."""
    doc = yaml.safe_load((tier0_dir / "manifest.yaml").read_text(encoding="utf-8"))
    truths = doc["ground_truth"]["files"]
    expected = tuple(Path(row["path"]).stem for row in doc["files"] if not truths[Path(row["path"]).stem]["host_only"])
    spec = sets.SETS["tier0-synthetic"]
    assert spec.inputs == expected
    assert all(row["sample_rate"] == 32000 for row in doc["files"] if Path(row["path"]).stem in spec.inputs)
    assert spec.dataset == os.fspath(tier0_dir.relative_to(repo_root))


def test_tier0_set_pins_are_the_ones_the_records_name():
    """Pitch: Praat 6.1.38 raw defaults except the singing floor/ceiling and the pinned step; spectrum: ADR 0006's."""
    spec = sets.SETS["tier0-synthetic"]
    pitch = spec.analyses["pitch"].asdict()
    for key, value in praat.RAW_AC_PRAAT_DEFAULTS.items():
        if key in ("time_step", "pitch_floor", "pitch_ceiling"):
            continue
        assert pitch[key] == value, key
    assert (pitch["time_step"], pitch["pitch_floor"], pitch["pitch_ceiling"]) == (0.01, 65, 1100)
    assert spec.analyses["spectrum"] == spectrum.ADR_0006_DEFAULT
    assert spec.analyses["formant"].asdict() == {
        "method": "burg",
        "time_step": 0.01,
        "max_formants": 5,
        "ceiling_hz": 5500,
        "window_length": 0.025,
        "preemphasis_from_hz": 50,
    }
    assert spec.analyses["ltas"].asdict() == {"bandwidth_hz": 100}
    assert spec.window_families == tuple(spectrum.WINDOW_FAMILIES) and len(spec.window_families) == 7


def test_tier0_output_plan_covers_pitch_on_tonal_formant_on_vowels_ltas_on_vowels_and_noise_spectrum_on_all():
    spec = sets.SETS["tier0-synthetic"]
    assert spec.outputs["spectrum"] == spec.inputs
    assert set(spec.outputs["formant"]) == {"vowel_a_f0_220_32k", "vowel_a_vibrato_220_6hz_100c_32k"}
    assert set(spec.outputs["ltas"]) == set(spec.outputs["formant"]) | {"white_m20dBFS_seed1_32k", "pink_m20dBFS_seed1_32k"}
    assert set(spec.outputs["pitch"]) == {s for s in spec.inputs if s.startswith("sine_")} | set(spec.outputs["formant"])
    assert len(spec.planned_outputs()) == 19 + 8 + 2 + 4
