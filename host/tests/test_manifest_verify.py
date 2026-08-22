# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""`manifest.py` + `verify.py` against ADR 0009, by hazard (roadmap H0, unit B-U5).

Positive control: the schema's own worked example, re-created as a real golden
set in a temporary repository — a git checkout with one commit, the 440 Hz
Tier-0 WAV written in-test, the two `.npy` arrays, a generator stand-in — with
every `<placeholder>` replaced by the value measured from those bytes. It must
pass every rule with no notice.

Negative suite, in the shape of `python-scripts/check_presets.py`'s
`negative_cases()`: one mutation per rule, each named for the hazard, each
asserting that the OWNING rule fires — not merely that something did. Where
the schema would also catch a case (a malformed digest, an unquoted date) the
case still names the invariant that owns it, because a rule the schema happens
to shadow today is a rule nobody notices has stopped working tomorrow. A
coverage test asserts every rule in `verify.RULES` is reached by at least one case.

Run: `uv run --project host pytest -q host/tests/test_manifest_verify.py`
"""

from __future__ import annotations

import copy
import datetime
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import parselmouth
import pytest
import scipy
import yaml
from scipy.signal.windows import general_cosine

from spectral_host import spectrum
from spectral_host.golden import cli, manifest, verify
from spectral_host import env as env_mod
from spectral_host.hashing import sha256_bytes, sha256_file

FS = 32000
SET = "tier0-synthetic"
INPUT_RELPATH = "datasets/tier0/sine_440_0dBFS_32k.wav"
GENERATOR_RELPATH = env_mod.PACKAGE_RELPATH  # I4 accepts exactly this `script`; the digest is env.generator_sha256
PITCH_RELPATH = f"host/golden/outputs/{SET}/pitch_sine_440.npy"
SPECTRUM_RELPATH = f"host/golden/outputs/{SET}/spectrum_sine_440.npy"


# --- building the positive control ----------------------------------------------


def worked_example(schema_path: Path) -> dict:
    """The worked example at the foot of the schema, un-commented, placeholders filled with dummies."""
    lines = schema_path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("#   # SPDX-FileCopyrightText"))
    body = "\n".join(line[4:] if line.startswith("#   ") else "" for line in lines[start:] if line.startswith("#"))
    body = re.sub(r"<64 hex[^>]*>", "a" * 64, body)
    body = re.sub(r"<40 hex[^>]*>", "b" * 40, body)
    doc = yaml.safe_load(body)
    assert isinstance(doc, dict) and doc.get("set") == SET, "worked example not found at the foot of the schema"
    return doc


def write_sine_wav(path: Path, seconds: float = 3.0, f0: float = 440.0, amplitude: int = 32767) -> np.ndarray:
    """A 16-bit mono PCM WAV of a sine at FS; returns the int16 samples."""
    n = int(round(seconds * FS))
    x = np.rint(amplitude * np.sin(2 * np.pi * f0 * np.arange(n) / FS)).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(os.fspath(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(FS)
        wf.writeframes(x.tobytes())
    return x


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", os.fspath(root), *args], capture_output=True, text=True, check=True)
    return proc.stdout.strip()


@dataclass
class GoldenRepo:
    """A temporary repository holding one golden set, plus the document that describes it."""

    root: Path
    doc: dict
    head: str

    @property
    def manifest_path(self) -> Path:
        return manifest.manifest_path(self.root, SET)

    def write(self, raw: bytes | None = None) -> Path:
        """Write `self.doc` (or `raw` bytes verbatim) as the set's manifest."""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_bytes(manifest.dump(self.doc) if raw is None else raw)
        return self.manifest_path

    def verify(self, check_env: bool = True, notices: list[str] | None = None) -> list[verify.Failure]:
        return verify.verify_manifest(self.manifest_path, self.root, check_env=check_env, notices=notices)

    def fired(self, check_env: bool = True) -> set[str]:
        return {f.rule for f in self.verify(check_env=check_env)}

    def file(self, relpath: str) -> Path:
        return self.root / relpath

    def output(self, index: int) -> dict:
        return self.doc["outputs"][index]

    def window(self, family: str) -> dict:
        return next(w for w in self.doc["windows"] if w["family"] == family)

    def save_output(self, index: int, arr: np.ndarray, allow_pickle: bool = False) -> None:
        """Replace an output array on disk and re-record its sha256, so only N1 can see the change."""
        path = self.file(self.output(index)["path"])
        np.save(path, arr, allow_pickle=allow_pickle)
        self.output(index)["sha256"] = sha256_file(path)


@pytest.fixture
def golden(tmp_path: Path, repo_root: Path) -> GoldenRepo:
    """The worked example, made real: a git checkout with the set's files and every digest measured."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "host tests")
    (root / "README.md").write_text("golden test repository\n", encoding="utf-8")
    git(root, "add", "README.md")
    git(root, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "initial")
    head = git(root, "rev-parse", "HEAD")

    samples = write_sine_wav(root / INPUT_RELPATH)
    # A stand-in package: every module of env.GENERATOR_TREE present (I4 hashes
    # exactly that list), plus one module outside it, so the tests can show
    # that editing the outsider does not move the digest.
    pkg = root / GENERATOR_RELPATH
    for rel in (*env_mod.GENERATOR_TREE, "golden/cli.py"):
        (pkg / rel).parent.mkdir(parents=True, exist_ok=True)
        (pkg / rel).write_text(f"# {rel}: generator stand-in for the verify tests\n", encoding="utf-8")

    out_dir = root / "host" / "golden" / "outputs" / SET
    out_dir.mkdir(parents=True)
    pitch = np.column_stack([0.025 + 0.01 * np.arange(296), np.full(296, 440.0)])
    np.save(root / PITCH_RELPATH, pitch)
    spec = spectrum.reference_spectrum(samples, FS, spectrum.ADR_0006_DEFAULT)
    np.save(root / SPECTRUM_RELPATH, spec)

    doc = worked_example(repo_root / "host" / "golden" / "manifest.schema.yaml")
    gen = doc["generator"]
    gen.update(
        script=GENERATOR_RELPATH,
        sha256=env_mod.generator_sha256(root),
        commit=head,
        python=platform.python_version(),
        numpy=np.__version__,
        scipy=scipy.__version__,
        parselmouth=parselmouth.__version__,
        praat_bundled=parselmouth.PRAAT_VERSION,
        platform=platform.platform(),
        blas="test-blas 0.0",
    )
    assert [i["path"] for i in doc["inputs"]] == [INPUT_RELPATH]
    doc["inputs"][0]["sha256"] = sha256_file(root / INPUT_RELPATH)
    assert [o["path"] for o in doc["outputs"]] == [PITCH_RELPATH, SPECTRUM_RELPATH]
    assert [o["shape"] for o in doc["outputs"]] == [[296, 2], [2049, 2]]
    for out in doc["outputs"]:
        out["sha256"] = sha256_file(root / out["path"])
    doc["tolerances"]["revision"] = head

    repo = GoldenRepo(root=root, doc=doc, head=head)
    repo.write()
    return repo


# --- positive controls ----------------------------------------------------------


def test_worked_example_made_real_passes_every_rule(golden):
    """The schema's example is the generator author's template; it must verify clean, with no notice."""
    notices: list[str] = []
    assert golden.verify(notices=notices) == []
    assert notices == []


def test_generator_digest_follows_generator_tree_not_the_whole_package(golden):
    """I4 recomputes `env.generator_sha256` (the GENERATOR_TREE modules): editing a module outside the list keeps the set green, editing a listed one turns it red, and bytecode never counts."""
    pkg = golden.root / env_mod.PACKAGE_RELPATH
    (pkg / "__pycache__").mkdir()
    (pkg / "__pycache__" / "x.cpython-312.pyc").write_bytes(b"\0")
    (pkg / "golden" / "cli.py").write_text("# cli edited after generation: not a numerics module\n", encoding="utf-8")
    assert golden.verify() == []
    (pkg / "spectrum.py").write_text("# the oracle changed\n", encoding="utf-8")
    failures = golden.verify()
    assert [f.rule for f in failures] == ["I4"]
    assert "GENERATOR_TREE" in failures[0].message


def test_generator_script_naming_anything_but_the_package_is_rejected_by_i4(golden):
    """The digest recipe is defined for `host/src/spectral_host` only; a file path (the pre-src-layout form) has no recipe and must not verify by accident."""
    (golden.root / "host" / "golden").mkdir(parents=True, exist_ok=True)
    script = golden.root / "host" / "golden" / "generate.py"
    script.write_text("# old single-script form\n", encoding="utf-8")
    golden.doc["generator"]["script"] = "host/golden/generate.py"
    golden.doc["generator"]["sha256"] = sha256_file(script)
    golden.write()
    failures = golden.verify()
    assert [f.rule for f in failures] == ["I4"]
    assert "generator.script" in failures[0].message


def test_failure_has_the_check_presets_shape():
    """`rule` + `message` attributes and `rule: message` str — what the CLI prints and the suite asserts on."""
    failure = verify.Failure("I1", "floor above ceiling")
    assert (failure.rule, failure.message) == ("I1", "floor above ceiling")
    assert str(failure) == "I1: floor above ceiling"
    assert isinstance(failure, Exception)


def test_schema_version_constant_equals_the_schema_const(repo_root):
    schema = manifest.load_schema(repo_root / manifest.SCHEMA_RELPATH)
    assert schema["properties"]["schema"]["const"] == manifest.SCHEMA_VERSION == "1.1"


# --- manifest.py: load / dump round trip --------------------------------------------


def test_dump_keeps_dates_and_the_version_quoted(golden):
    """A bare 2026-08-21 is a datetime.date to YAML; the dump must quote it, or the next load is not a string."""
    text = manifest.dumps(golden.doc)
    assert "generated: '2026-08-21'" in text
    assert "date: '2026-08-21'" in text
    assert "schema: '1.1'" in text
    back = manifest.loads(text)
    assert isinstance(back["generated"], str) and back["generated"] == "2026-08-21"
    assert isinstance(back["regeneration"]["date"], str)
    assert isinstance(back["schema"], str) and back["schema"] == "1.1"
    assert back == golden.doc


def test_dump_begins_with_the_two_spdx_lines_and_keeps_key_order(golden):
    text = manifest.dumps(golden.doc)
    assert text.splitlines()[:2] == list(manifest.SPDX_LINES)
    keys = [line.split(":")[0] for line in text.splitlines()[2:] if re.match(r"[a-z_]", line)]  # `- ` items sit at column 0 too
    assert keys == list(golden.doc.keys())  # sort_keys=False: a manifest is reviewed as a diff
    assert manifest.dump(golden.doc) == text.encode("utf-8")


def test_dump_refuses_a_non_mapping():
    with pytest.raises(TypeError):
        manifest.dump(["not", "a", "manifest"])  # type: ignore[arg-type]


def test_unquoted_date_is_rejected_not_coerced(golden):
    """YAML resolves a bare date to datetime.date; the loader keeps it and the schema refuses it (rule S)."""
    raw = manifest.dump(golden.doc)
    bare = raw.replace(b"generated: '2026-08-21'", b"generated: 2026-08-21")
    assert bare != raw
    path = golden.write(raw=bare)
    loaded = manifest.load(path)
    assert isinstance(loaded["generated"], datetime.date)
    problems = manifest.validate(loaded, manifest.load_schema())
    assert any(p.startswith("$.generated:") for p in problems), problems
    assert "S" in golden.fired()


def test_validate_reports_paths_sorted_and_empty_on_the_example(golden):
    schema = manifest.load_schema()
    assert manifest.validate(golden.doc, schema) == []
    bad = copy.deepcopy(golden.doc)
    bad["set"] = "Has Spaces"
    bad["inputs"][0]["bit_depth"] = 12
    problems = manifest.validate(bad, schema)
    assert [p.split(":")[0] for p in problems] == ["$.inputs[0].bit_depth", "$.set"]


def test_validate_reports_a_non_mapping_instead_of_raising():
    assert manifest.validate(["list"], manifest.load_schema())


def test_load_schema_checks_the_schema_itself(tmp_path):
    """A schema with a broken keyword would validate everything; check_schema must refuse it first."""
    broken = tmp_path / "schema.yaml"
    broken.write_text("type: object\nproperties: 5\n", encoding="utf-8")
    with pytest.raises(Exception):  # jsonschema.SchemaError
        manifest.load_schema(broken)


def test_discover_manifests_lists_only_set_manifests(golden):
    (golden.root / "host" / "golden" / "outputs" / "stray.yaml").write_text("x: 1\n", encoding="utf-8")
    assert manifest.discover_manifests(golden.root) == [golden.manifest_path]
    assert manifest.discover_manifests(golden.root / "nowhere") == []


# --- the negative suite ------------------------------------------------------------------


def _unquote_date(repo: GoldenRepo) -> bytes:
    raw = manifest.dump(repo.doc)
    bare = raw.replace(b"generated: '2026-08-21'", b"generated: 2026-08-21")
    assert bare != raw
    return bare


def _strip_spdx(repo: GoldenRepo) -> bytes:
    raw = manifest.dump(repo.doc)
    return b"\n".join(raw.split(b"\n")[2:])


def _symmetric_hann_digest(n: int = 4096) -> str:
    return hashlib.sha256(np.asarray(general_cosine(n, [0.5, 0.5], sym=True), dtype="<f4").tobytes()).hexdigest()


def _move_output_to_another_set(repo: GoldenRepo) -> None:
    new_rel = "host/golden/outputs/other-set/pitch_sine_440.npy"
    dst = repo.file(new_rel)
    dst.parent.mkdir(parents=True)
    shutil.move(repo.file(repo.output(0)["path"]), dst)
    repo.output(0)["path"] = new_rel  # sha256 unchanged, so I4 stays silent


def _pickled_object_array(repo: GoldenRepo) -> None:
    arr = np.empty((296, 2), dtype=object)
    arr[:] = None
    repo.save_output(0, arr, allow_pickle=True)


def _set_path(path: list, value):
    def mutate(repo: GoldenRepo) -> None:
        node = repo.doc
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return mutate


def _del_path(path: list):
    def mutate(repo: GoldenRepo) -> None:
        node = repo.doc
        for key in path[:-1]:
            node = node[key]
        del node[path[-1]]

    return mutate


def _window(family: str, key: str, value):
    def mutate(repo: GoldenRepo) -> None:
        repo.window(family)[key] = value

    return mutate


def _drifted_hann_with_consistent_digest(repo: GoldenRepo) -> None:
    coeffs = [0.5, 0.5000001]
    repo.window("hann")["coefficients"] = coeffs
    repo.window("hann")["sha256"] = verify.window_digest(coeffs, 4096)


def _remove_hann_entry(repo: GoldenRepo) -> None:
    repo.doc["windows"] = [w for w in repo.doc["windows"] if w["family"] != "hann"]


def _spectrum_at_8192(repo: GoldenRepo) -> None:
    repo.doc["analyses"]["spectrum"]["window_length_samples"] = 8192
    repo.doc["analyses"]["spectrum"]["fft_size"] = 8192


def _append_byte_to_input(repo: GoldenRepo) -> None:
    with open(repo.file(INPUT_RELPATH), "ab") as fh:
        fh.write(b"\0")


def _delete_output(repo: GoldenRepo) -> None:
    repo.file(repo.output(1)["path"]).unlink()


#: (hazard, mutation, owning rule). A mutation may edit `repo.doc`, the files on
#: disk, or return the raw bytes to write instead of `dump(repo.doc)`.
NEGATIVE_CASES: list[tuple[str, Callable[[GoldenRepo], bytes | None], str]] = [
    # --- S: the schema, and exactly one version string ---
    ("schema: 1 (the schema-1 integer)", _set_path(["schema"], 1), "S"),
    ('schema: "1.0"', _set_path(["schema"], "1.0"), "S"),
    ('schema: "1.2" (the filtered bump does not exist yet)', _set_path(["schema"], "1.2"), "S"),
    ("unquoted date resolves to datetime.date", _unquote_date, "S"),
    ("unknown top-level field", _set_path(["colour_scheme"], "viridis"), "S"),
    ("tolerances.source redirected away from the Apache table", _set_path(["tolerances", "source"], "host/golden/limits.md"), "S"),
    # --- I1..I3: cross-field ---
    ("pitch_floor above pitch_ceiling", _set_path(["analyses", "pitch", "pitch_floor"], 1200), "I1"),
    ("pitch_floor equal to pitch_ceiling", _set_path(["analyses", "pitch", "pitch_floor"], 1100), "I1"),
    ("output names an input the manifest does not list", _set_path(["outputs", 0, "input"], "datasets/tier0/missing.wav"), "I2"),
    ("output names an analysis block that is absent", _set_path(["outputs", 0, "analysis"], "ltas"), "I3"),
    # --- I4: digests vs disk ---
    ("input recorded as an absolute path (verifies on one machine only)", lambda r: r.doc["inputs"][0].__setitem__("path", os.fspath(r.file(INPUT_RELPATH))), "I4"),
    ("generator path escaping the checkout with ..", _set_path(["generator", "script"], f"host/../{GENERATOR_RELPATH}"), "I4"),
    ("input bytes changed after the manifest was written", _append_byte_to_input, "I4"),
    ("output digest stale", _set_path(["outputs", 1, "sha256"], "0" * 64), "I4"),
    ("generator digest stale", _set_path(["generator", "sha256"], "0" * 64), "I4"),
    ("output missing from disk", _delete_output, "I4"),
    ("generator script naming a path with no digest recipe", _set_path(["generator", "script"], "host/golden/nope.py"), "I4"),
    ("a GENERATOR_TREE module missing from disk", lambda r: (r.root / env_mod.PACKAGE_RELPATH / "praat.py").unlink(), "I4"),
    # --- I5: installed pins ---
    ("numpy drifted from the installed version", _set_path(["generator", "numpy"], "0.0.0"), "I5"),
    ("praat_bundled claims a Praat the environment does not have", _set_path(["generator", "praat_bundled"], "6.4.27"), "I5"),
    ("parselmouth drifted", _set_path(["generator", "parselmouth"], "0.5.0"), "I5"),
    # --- I6 ---
    ("filtered method on the 6.1.38 bundle", _set_path(["analyses", "pitch", "method"], "filtered"), "I6"),
    # --- I7: window digests and coefficients ---
    ("rect entry carrying hann's coefficients [0.5, 0.5]", _window("rect", "coefficients", [0.5, 0.5]), "I7"),
    ("wrong digest (well-formed)", _window("hann", "sha256", "a" * 64), "I7"),
    ("wrong digest (malformed; the schema also objects)", _window("hann", "sha256", "zz"), "I7"),
    ("digest of the SYMMETRIC hann window", _window("hann", "sha256", _symmetric_hann_digest()), "I7"),
    ("drifted coefficients with a digest consistent with them", _drifted_hann_with_consistent_digest, "I7"),
    (
        "blackman_nuttall coefficients under another family's name (the 0.0163 trap)",
        _window("hann", "coefficients", [0.3635819, 0.4891775, 0.1365995, 0.0106411]),
        "I7",
    ),
    # --- I8 ---
    ("windows[] lacks the entry the spectrum uses", _remove_hann_entry, "I8"),
    ("spectrum at a length windows[] does not carry", _spectrum_at_8192, "I8"),
    # --- N1..N4 ---
    (".npy shape differs from the recorded shape", lambda r: r.save_output(0, np.zeros((295, 2))), "N1"),
    (".npy dtype differs from the recorded dtype", lambda r: r.save_output(0, np.zeros((296, 2), dtype=np.float32)), "N1"),
    ("pickled object array where a float array is recorded", _pickled_object_array, "N1"),
    ("pitch output without unvoiced_sentinel", _del_path(["outputs", 0, "unvoiced_sentinel"]), "N2"),
    ("output filed under another set's directory", _move_output_to_another_set, "N3"),
    ("output path escaping with ..", _set_path(["outputs", 0, "path"], f"host/golden/outputs/{SET}/../{SET}/pitch_sine_440.npy"), "N3"),
    ("manifest without the GPL SPDX lines", _strip_spdx, "N4"),
    # --- G1 ---
    ("tolerances.revision is not an object of this checkout", _set_path(["tolerances", "revision"], "0" * 40), "G1"),
]


@pytest.mark.parametrize(("hazard", "mutate", "owner"), NEGATIVE_CASES, ids=[c[0] for c in NEGATIVE_CASES])
def test_negative_case_is_caught_by_its_owning_rule(golden, hazard, mutate, owner):
    """One mutation, one owner: the rule that owns the hazard must fire, whatever else also does."""
    raw = mutate(golden)
    golden.write(raw=raw)
    failures = golden.verify()
    fired = {f.rule for f in failures}
    assert owner in fired, f"{hazard}: expected {owner} to fire; got {[str(f) for f in failures]}"
    assert "?" not in fired, f"{hazard}: a rule crashed: {[str(f) for f in failures]}"


def test_every_rule_is_reached_by_the_negative_suite():
    """A rule no case reaches is a rule that can stop working unnoticed (check_presets' UNCOVERED check)."""
    owners = {owner for _, _, owner in NEGATIVE_CASES}
    assert set(verify.RULE_NAMES) - owners == set()
    assert owners - set(verify.RULE_NAMES) == set()


def test_schema_catching_a_case_does_not_silence_the_owning_rule(golden):
    """The malformed-digest case: S fires AND I7 fires, because I7 would still have to on a well-formed wrong digest."""
    golden.window("hann")["sha256"] = "zz"
    golden.write()
    fired = golden.fired()
    assert {"S", "I7"} <= fired


def test_i6_accepts_a_two_place_praat_6_4(golden):
    """`"6.4"` parses to (6, 4), which Python orders BELOW (6, 4, 0); the bound must not refuse the release that introduced the method."""
    golden.doc["analyses"]["pitch"]["method"] = "filtered"
    for bundled, expect_i6 in (("6.4", False), ("6.4.0", False), ("6.4.27", False), ("6.3.99", True), ("6.1.38", True)):
        golden.doc["generator"]["praat_bundled"] = bundled
        golden.write()
        fired = golden.fired(check_env=False)  # I5 would fire on every value here; I6 is the rule under test
        assert ("I6" in fired) is expect_i6, (bundled, fired)


def test_window_digest_is_the_periodic_window_pinned_by_the_schema():
    """`window_digest` must reproduce the schema's pinned (hann, 4096) and (rect, 4096) digests and must NOT be the symmetric form.

    The negative suite builds its 'drifted coefficients' digest with `window_digest` itself, so without this
    test a `sym=True` mutation of the recipe would be self-consistent and survive (mutation-tested 2026-08-21).
    """
    hann = verify.window_digest(spectrum.WINDOW_FAMILIES["hann"], 4096)
    assert hann == "3ce6c7c870b60fc2425689b96f2ccf1cecff9b071766a48ae3d25a0ca8f3d304"  # schema worked example
    assert hann == spectrum.window_table_sha256("hann", 4096)
    assert hann != _symmetric_hann_digest(4096)
    assert verify.window_digest([1.0], 4096) == hashlib.sha256(b"\x00\x00\x80\x3f" * 4096).hexdigest()
    # (-1)^k a_k cos(2πkj/N), j = 0 … N-1 — ADR 0006 D1's formula, not SciPy's name for it
    a = spectrum.WINDOW_FAMILIES["blackman_nuttall"]
    j = np.arange(4096)
    w = sum(((-1) ** k) * ak * np.cos(2 * np.pi * k * j / 4096) for k, ak in enumerate(a))
    assert verify.window_digest(a, 4096) == hashlib.sha256(np.asarray(w, dtype="<f4").tobytes()).hexdigest()


# --- switches and notices ----------------------------------------------------------------


def test_no_env_check_skips_i5_only_and_says_so(golden):
    golden.doc["generator"]["numpy"] = "0.0.0"
    golden.write()
    assert "I5" in golden.fired(check_env=True)
    notices: list[str] = []
    assert golden.verify(check_env=False, notices=notices) == []
    assert any("I5" in n for n in notices)


def test_g1_outside_a_checkout_is_a_notice_not_a_failure(golden, tmp_path, monkeypatch):
    """A missing .git says nothing about the manifest; G1 must skip loudly, not fail or pass silently."""
    plain = tmp_path / "plain"
    shutil.copytree(golden.root, plain, ignore=shutil.ignore_patterns(".git"))
    # Stop git from discovering a repository above tmp_path (the pytest temp root is not one, but say so).
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", os.fspath(tmp_path))
    assert subprocess.run(["git", "-C", os.fspath(plain), "rev-parse", "--git-dir"], capture_output=True).returncode != 0
    notices: list[str] = []
    failures = verify.verify_manifest(manifest.manifest_path(plain, SET), plain, notices=notices)
    assert [f.rule for f in failures] == []
    assert any(n.startswith("G1 skipped") for n in notices)


def test_verify_never_writes(golden):
    """ADR 0009 decision 4: verify never regenerates. Every byte and mtime under the repository is untouched, red or green."""
    golden.doc["outputs"][1]["sha256"] = "0" * 64
    golden.window("rect")["coefficients"] = [0.5, 0.5]
    golden.write()

    def snapshot() -> dict[str, tuple[int, str]]:
        return {
            str(p.relative_to(golden.root)): (p.stat().st_mtime_ns, sha256_bytes(p.read_bytes()))
            for p in golden.root.rglob("*")
            if p.is_file() and ".git" not in p.parts
        }

    before = snapshot()
    failures = golden.verify()
    assert {f.rule for f in failures} == {"I4", "I7"}
    assert snapshot() == before


def test_a_crashing_rule_is_reported_not_swallowed(golden, monkeypatch):
    def boom(ctx):
        raise RuntimeError("synthetic")

    monkeypatch.setattr(verify, "RULES", (("I1", boom),))
    failures = golden.verify()
    assert [f.rule for f in failures] == ["?"]
    assert "RuntimeError" in failures[0].message


def test_unparseable_manifest_is_a_rule_s_failure(golden):
    golden.write(raw=b"# SPDX\n: : :\n\t- [")
    failures = golden.verify()
    assert [f.rule for f in failures] == ["S"]


# --- the CLI -----------------------------------------------------------------------------


def test_cli_verify_exits_0_on_a_clean_set_and_1_on_drift(golden, capsys):
    assert cli.main(["verify", str(golden.manifest_path), "--repo-root", str(golden.root)]) == 0
    assert "ok" in capsys.readouterr().out
    golden.doc["analyses"]["pitch"]["pitch_floor"] = 1200
    golden.write()
    assert cli.main(["verify", str(golden.manifest_path), "--repo-root", str(golden.root)]) == 1
    out = capsys.readouterr().out
    assert "I1:" in out and "pitch_floor" in out and "FAIL" in out


def test_cli_verify_discovers_every_set_manifest_by_default(golden, capsys):
    assert cli.main(["verify", "--repo-root", str(golden.root)]) == 0
    assert str(golden.manifest_path) in capsys.readouterr().out


def test_cli_verify_on_an_empty_outputs_dir_exits_0_and_says_no_manifests(tmp_path, capsys):
    """An outputs/ with nothing in it is not drift; but it is not silent either."""
    for root in (tmp_path / "absent", tmp_path / "present"):
        (root / "host" / "golden" / ("outputs" if root.name == "present" else "x")).mkdir(parents=True)
        assert cli.main(["verify", "--repo-root", str(root)]) == 0
        assert "no manifests" in capsys.readouterr().out


def test_cli_verify_no_env_check_prints_the_notice(golden, capsys):
    golden.doc["generator"]["scipy"] = "0.0.0"
    golden.write()
    assert cli.main(["verify", str(golden.manifest_path), "--repo-root", str(golden.root), "--no-env-check"]) == 0
    assert "notice: I5 skipped" in capsys.readouterr().out


def test_cli_env_prints_the_generator_block_as_json(capsys):
    """`spectral-golden env` is the pin chain as data: eleven keys, the bundled Praat the lock pins."""
    assert cli.main(["env"]) == 0
    block = json.loads(capsys.readouterr().out)
    assert list(block) == list(manifest.load_schema()["properties"]["generator"]["required"])
    assert block["praat_bundled"] == "6.1.38"
    assert block["parselmouth"] == "0.4.7"
    assert block["praat_reference"] is None
    assert re.fullmatch(r"[0-9a-f]{40}", block["commit"])


def test_cli_pending_subcommands_still_exit_2(capsys):
    for name in ("t7",):  # `generate` landed with B-U6 (test_generate_roundtrip.py)
        assert cli.main([name]) == cli.EXIT_NOT_IMPLEMENTED
        assert "not implemented" in capsys.readouterr().err


def test_cli_without_a_command_exits_2(capsys):
    assert cli.main([]) == cli.EXIT_NOT_IMPLEMENTED
