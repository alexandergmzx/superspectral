# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""The host preset loader against preset-schema.md §3/§6 and ADR 0006, by hazard (roadmap H0, unit B-U7).

Each test is named for the silent failure it guards: a preset whose bytes are
not its hash (V0), a file renamed under another preset's id (V1), window
constants that no longer describe the window the oracle multiplies by (V8),
a resolution block or display band that drifted from (fs, N, hop) (V9), a
writer that silently rounds, a `rect` preset, and the mapping onto the golden
manifest's nine keys.

The six shipped presets are read AS DATA by path from protocols/presets/ —
never through the Apache checker, which is on the other side of the licence
boundary (ADR 0004) and is the validator of record for the full V-suite.
Mutations are built here on the parsed document or on the canonical bytes,
the way python-scripts/check_presets.py's negative cases and regression guards
are, so the two implementations are exercised by the same inputs.

Run: `uv run --project host pytest -q host/tests/test_presets.py`
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

from spectral_host import presets as pr
from spectral_host import spectrum as sp

#: preset-schema.md §1 / §7: the six presets of the founding document, one file each.
SHIPPED = (
    "diction_consonants",
    "live_singing",
    "room_noise_floor",
    "stem_analysis",
    "sustained_pitch_lab",
    "vowel_formant_study",
)


# --- fixtures ---------------------------------------------------------------------


@pytest.fixture(scope="module")
def preset_dir(repo_root: Path) -> Path:
    d = repo_root / "protocols" / "presets"
    found = sorted(p.stem for p in d.glob("*.json"))
    assert found == list(SHIPPED), f"protocols/presets/ holds {found}, not the six of preset-schema.md §7"
    return d


@pytest.fixture(scope="module")
def live_bytes(preset_dir: Path) -> bytes:
    return (preset_dir / "live_singing.json").read_bytes()


@pytest.fixture(scope="module")
def live_doc(live_bytes: bytes) -> dict:
    return json.loads(live_bytes.decode("utf-8"))


def _set(doc: dict, path: list, value) -> dict:
    node = doc
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return doc


def _reject(raw: bytes, name: str = "live_singing.json") -> pr.PresetRejected:
    with pytest.raises(pr.PresetRejected) as info:
        pr.load_preset_bytes(raw, Path(name))
    return info.value


def _reject_doc(doc: dict, name: str = "live_singing.json") -> pr.PresetRejected:
    """Dump `doc` canonically (so V0 passes) and load it under `name`; return the rejection."""
    return _reject(pr.dump_preset(doc), name)


# --- the shipped six ---------------------------------------------------------------


@pytest.mark.parametrize("name", SHIPPED)
def test_each_shipped_preset_is_accepted_with_its_file_sha256(preset_dir: Path, name: str):
    """V0/V1/V8/V9 on the committed files, and the identity is the sha256 of the bytes as read (§3)."""
    path = preset_dir / f"{name}.json"
    p = pr.load_preset(path)
    assert p.id == name
    assert p.path == path
    assert p.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert p.doc["id"] == name
    assert p.analysis is p.doc["analysis"]


def test_preset_identity_is_hashable_and_excludes_the_document(preset_dir: Path):
    """`Preset` is frozen; equality/hash rest on id + sha256 + path, so a dict field does not make it unhashable."""
    a = pr.load_preset(preset_dir / "live_singing.json")
    b = pr.load_preset(preset_dir / "live_singing.json")
    assert a == b and hash(a) == hash(b)
    with pytest.raises(AttributeError):
        a.id = "other"  # type: ignore[misc]


def test_rejection_carries_the_owning_rule_number():
    """`PresetRejected(rule, message)` is the Apache checker's `Failure` shape: rule first, for the log."""
    exc = pr.PresetRejected("V8", "enbw_bins drifted")
    assert (exc.rule, exc.message) == ("V8", "enbw_bins drifted")
    assert str(exc) == "V8: enbw_bins drifted"


# --- V0: the bytes are the canonical form -------------------------------------------


@pytest.mark.parametrize(
    "label, mutate",
    [
        ("utf-8 BOM", lambda good, doc: b"\xef\xbb\xbf" + good),
        ("CRLF line endings", lambda good, doc: good.replace(b"\n", b"\r\n")),
        ("no trailing newline", lambda good, doc: good.rstrip(b"\n")),
        ("duplicated trailing newline", lambda good, doc: good + b"\n"),
        ("trailing whitespace", lambda good, doc: good.replace(b"\n", b" \n", 1)),
        (
            "four-space indent",
            lambda good, doc: (json.dumps(doc, sort_keys=True, indent=4, ensure_ascii=False) + "\n").encode(),
        ),
        (
            "keys not sorted",
            lambda good, doc: (
                json.dumps(dict(reversed(list(doc.items()))), sort_keys=False, indent=2, ensure_ascii=False) + "\n"
            ).encode(),
        ),
        (
            "seven-decimal number",
            lambda good, doc: pr.canonical_text(_set(copy.deepcopy(doc), ["analysis", "dc_blocker_hz"], 0.1234567)).encode(),
        ),
        (
            "exponent-form number",
            lambda good, doc: pr.canonical_text(_set(copy.deepcopy(doc), ["analysis", "dc_blocker_hz"], 1e-7)).encode(),
        ),
        ("not JSON at all", lambda good, doc: b"{ not json\n"),
        ("a JSON array, not an object", lambda good, doc: b"[]\n"),
    ],
)
def test_non_canonical_bytes_are_rejected_by_v0(live_bytes: bytes, live_doc: dict, label: str, mutate):
    """A file that is not byte-for-byte its canonical form has a sha256 no take can reproduce (§3, ADR 0010 d.6)."""
    raw = mutate(live_bytes, live_doc)
    assert raw != live_bytes, label
    exc = _reject(raw)
    assert exc.rule == "V0", f"{label}: rejected by {exc.rule}, not V0: {exc.message}"


def test_a_decimal_inside_a_description_string_is_not_a_v0_number(live_doc: dict):
    """V0 is a rule about JSON numbers, matched on parsed leaves — prose with 0.1234567 in it is accepted."""
    doc = _set(copy.deepcopy(live_doc), ["description"], "matches Spectroid 32768 at 0.1234567 s")
    p = pr.load_preset_bytes(pr.dump_preset(doc), Path("live_singing.json"))
    assert p.doc["description"].endswith("0.1234567 s")


def test_shipped_bytes_equal_json_dumps_sorted_indent_2(preset_dir: Path):
    """The §3 one-liner: `json.dumps(d, sort_keys=True, indent=2, ensure_ascii=False)` reproduces every file minus the newline."""
    for name in SHIPPED:
        raw = (preset_dir / f"{name}.json").read_bytes()
        doc = json.loads(raw.decode("utf-8"))
        assert raw == (json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8"), name


# --- V1: id == basename ---------------------------------------------------------------


def test_id_not_equal_to_basename_is_rejected_by_v1(live_bytes: bytes):
    """The same canonical bytes under another file name: V0 passes, V1 must fire (a take names presets by id)."""
    exc = _reject(live_bytes, "live_singing_v2.json")
    assert exc.rule == "V1"
    assert "live_singing_v2" in exc.message


def test_file_without_json_suffix_is_rejected_by_v1(live_bytes: bytes):
    exc = _reject(live_bytes, "live_singing")
    assert exc.rule == "V1"


# --- V8: the window block describes the window the oracle uses ----------------------------


def test_enbw_mismatch_is_rejected_by_v8(live_doc: dict):
    """`enbw_bins` that is another family's, or off by 2e-6, fails; off by 5e-7 (the rounding budget) passes."""
    truth = live_doc["analysis"]["window"]["enbw_bins"]  # blackman_harris, 2.004353 (§4.3)
    assert truth == 2.004353

    stale = _set(copy.deepcopy(live_doc), ["analysis", "window", "enbw_bins"], 1.5)  # hann's value
    exc = _reject_doc(stale)
    assert exc.rule == "V8" and "enbw_bins" in exc.message

    over = _set(copy.deepcopy(live_doc), ["analysis", "window", "enbw_bins"], 2.004355)  # +2e-6 > TOL
    exc = _reject_doc(over)
    assert exc.rule == "V8" and "enbw_bins" in exc.message

    # 2.0043535 has seven decimals, so it cannot be written canonically at all;
    # the in-budget case is therefore checked on the parsed document directly.
    within = _set(copy.deepcopy(live_doc), ["analysis", "window", "enbw_bins"], truth + 4e-7)
    pr.check_v8_window(within)


@pytest.mark.parametrize(
    "label, path, value",
    [
        ("mutated coefficient", ["analysis", "window", "coefficients"], [0.35875, 0.48829, 0.14128, 0.02168]),
        ("another family's coefficients under this name", ["analysis", "window", "coefficients"], [0.42, 0.5, 0.08]),
        ("stale coherent_gain", ["analysis", "window", "coherent_gain"], 0.5),
        ("stale coherent_gain_db", ["analysis", "window", "coherent_gain_db"], -6.0206),
        ("symmetric form", ["analysis", "window", "form"], "symmetric"),
        ("unknown family", ["analysis", "window", "name"], "gaussian"),
    ],
)
def test_window_block_drift_is_rejected_by_v8(live_doc: dict, label: str, path: list, value):
    exc = _reject_doc(_set(copy.deepcopy(live_doc), path, value))
    assert exc.rule == "V8", f"{label}: {exc}"


def test_rect_is_rejected_as_a_preset_family_by_v8(live_doc: dict):
    """ADR 0006 consequence (c): `rect` is a golden-manifest family only; the loader refuses it as the C loader refuses wire value 0."""
    doc = copy.deepcopy(live_doc)
    w = doc["analysis"]["window"]
    w.update(name="rect", coefficients=[1.0], coherent_gain=1.0, coherent_gain_db=0.0, enbw_bins=1.0)
    doc["analysis"]["resolution"]["enbw_hz"] = 7.8125  # 1.0 bin at 32 kHz / 4096, so only V8 can fire
    exc = _reject_doc(doc)
    assert exc.rule == "V8" and "rect" in exc.message
    assert "rect" in sp.WINDOW_FAMILIES and "rect" not in sp.PRESET_WINDOW_FAMILIES


@pytest.mark.parametrize("name", SHIPPED)
def test_v8_recomputes_from_the_oracle_window_and_matches_the_closed_form(preset_dir: Path, name: str):
    """One table, both uses: the sums of `spectrum.window_float64(name, N)` — the array `reference_spectrum`
    multiplies by — give the shipped constants, and equal the ADR 0006 D2 closed form to far below TOL."""
    p = pr.load_preset(preset_dir / f"{name}.json")
    a = p.analysis
    family, n = a["window"]["name"], a["fft_size"]
    cg, cg_db, nenbw = pr.recompute_window_constants(family, n)
    s1, s2, nenbw_sums = sp.window_sums(sp.window_float64(family, n))
    assert nenbw == nenbw_sums
    assert cg == s1 / n
    closed = sp.nenbw_closed_form(sp.WINDOW_FAMILIES[family])
    assert abs(nenbw - closed) < 1e-12, (family, n, nenbw, closed)
    assert abs(cg - sp.WINDOW_FAMILIES[family][0]) < 1e-12
    assert abs(a["window"]["enbw_bins"] - nenbw) <= 5e-7  # the rounding half of the 1e-6 budget (§6)
    assert abs(a["window"]["coherent_gain"] - cg) <= 5e-7
    assert abs(a["window"]["coherent_gain_db"] - cg_db) <= 5e-7


# --- V9: resolution and the display band -------------------------------------------------


@pytest.mark.parametrize(
    "label, path, value",
    [
        ("stale enbw_hz", ["analysis", "resolution", "enbw_hz"], 15.0),
        ("stale bin_width_hz", ["analysis", "resolution", "bin_width_hz"], 7.8),
        ("stale window_duration_ms", ["analysis", "resolution", "window_duration_ms"], 256.0),
        ("stale hop_samples", ["analysis", "resolution", "hop_samples"], 512),
        ("freq_max above Nyquist", ["display", "freq_max_hz"], 20000),
        ("freq_min not below freq_max", ["display", "freq_min_hz"], 8000),
    ],
)
def test_resolution_or_band_drift_is_rejected_by_v9(live_doc: dict, label: str, path: list, value):
    exc = _reject_doc(_set(copy.deepcopy(live_doc), path, value))
    assert exc.rule == "V9", f"{label}: {exc}"


def test_fractional_hop_is_rejected_by_v9_even_when_it_matches_interval_ms(live_doc: dict):
    """A hop of 640.5 against interval_ms 20 fails the recomputation, not the integer rule — so that case is
    mute. Here interval_ms 20.015625 (exactly representable, six decimals) makes 20.015625 × 32000 / 1000 =
    640.5 the *correct* recomputation, and only the "hop_samples is an integer" clause can fire. (V7 forbids
    such an interval on the Apache side; this loader does not carry V7, so the clause is reachable here.)"""
    doc = copy.deepcopy(live_doc)
    _set(doc, ["analysis", "interval_ms"], 20.015625)
    _set(doc, ["analysis", "resolution", "hop_samples"], 640.5)
    exc = _reject_doc(doc)
    assert exc.rule == "V9" and "not an integer" in exc.message
    # the same interval with the hop rounded: the recomputation clause fires instead, still V9
    _set(doc, ["analysis", "resolution", "hop_samples"], 640)
    exc = _reject_doc(doc)
    assert exc.rule == "V9" and "recomputed" in exc.message


def test_coefficient_off_by_1e6_is_rejected_by_v8_although_the_derived_constants_still_agree(live_doc: dict):
    """The coefficients are the contract (ADR 0006 D1): a₃ of blackman_harris moved by 1×10⁻⁶ shifts NENBW by
    ≈ 1×10⁻⁷ and the coherent gain not at all, so V8's TOL clauses pass — only the 1e-9 coefficient clause
    (shared with the Apache checker) can catch it, and the message must blame the coefficients."""
    doc = copy.deepcopy(live_doc)
    coeffs = list(doc["analysis"]["window"]["coefficients"])
    assert coeffs == sp.WINDOW_FAMILIES["blackman_harris"]
    coeffs[3] = 0.011681  # 0.01168 + 1e-6
    _set(doc, ["analysis", "window", "coefficients"], coeffs)
    assert abs(sp.nenbw_closed_form(coeffs) - sp.nenbw_closed_form(sp.WINDOW_FAMILIES["blackman_harris"])) < pr.TOL
    exc = _reject_doc(doc)
    assert exc.rule == "V8" and "coefficients" in exc.message


def test_fft_size_outside_the_schema_bound_is_rejected_before_a_window_is_built(live_doc: dict):
    """A loader that skipped the schema would otherwise allocate 2**40 floats for a typo; §4.2's bound is repeated under V8."""
    for n in (256, 2**40):
        exc = _reject_doc(_set(copy.deepcopy(live_doc), ["analysis", "fft_size"], n))
        assert exc.rule == "V8" and "fft_size" in exc.message, n


def test_structurally_malformed_document_is_a_rejection_not_a_traceback(live_doc: dict):
    """A missing block is the schema's to describe; here it must still be reported (as `V?`), never escape."""
    doc = copy.deepcopy(live_doc)
    del doc["analysis"]["resolution"]
    exc = _reject_doc(doc)
    assert exc.rule == "V?"


# --- the canonical writer ---------------------------------------------------------------


@pytest.mark.parametrize("name", SHIPPED)
def test_dump_then_load_is_byte_identical(preset_dir: Path, tmp_path: Path, name: str):
    """dump(load(file).doc) == file bytes, and the dump re-loads to the same sha256 — the store round-trip of §10."""
    path = preset_dir / f"{name}.json"
    raw = path.read_bytes()
    p = pr.load_preset(path)
    dumped = pr.dump_preset(p.doc)
    assert dumped == raw
    out = tmp_path / f"{name}.json"
    out.write_bytes(dumped)
    again = pr.load_preset(out)
    assert again.sha256 == p.sha256
    assert again.doc == p.doc


def test_dump_refuses_a_seven_decimal_number_instead_of_rounding(live_doc: dict):
    """§3: values are rounded by whoever derives them; a writer that rounded silently would change a value V8/V9 recompute."""
    doc = _set(copy.deepcopy(live_doc), ["analysis", "dc_blocker_hz"], 0.1234567)
    with pytest.raises(pr.PresetRejected) as info:
        pr.dump_preset(doc)
    assert info.value.rule == "V0"
    doc = _set(copy.deepcopy(live_doc), ["analysis", "dc_blocker_hz"], float("nan"))
    with pytest.raises(pr.PresetRejected) as info:
        pr.dump_preset(doc)
    assert info.value.rule == "V0"


# --- the mapping onto the golden manifest's nine keys ------------------------------------------


def test_stem_analysis_maps_to_hann_8192_s1(preset_dir: Path):
    """The host-only preset: hann, N = 8192 at 48 kHz (accepted here — V2's 48 kHz gate is the WATCH's),
    power spectrum → (`S1`, `power_spectrum`), sine reference, ÷32768, float64 — ADR 0006 D2/D3, ADR 0003 d.2."""
    p = pr.load_preset(preset_dir / "stem_analysis.json")
    assert p.analysis["sample_rate_hz"] == 48000 and p.doc["targets"] == ["host"]
    cfg = pr.spectrum_config_from_preset(p)
    assert cfg == sp.SpectrumConfig(
        window="hann",
        window_length_samples=8192,
        fftbins=True,
        fft_size=8192,
        normalization="S1",
        scaling="power_spectrum",
        dbfs_reference="sine",
        int16_scale=32768,
        dtype="float64",
    )
    assert cfg.level_unit == "dBFS"
    assert pr.spectrum_config_from_preset(p, dtype="float32").dtype == "float32"


def test_room_noise_floor_psd_maps_to_s2_density(preset_dir: Path):
    """`spectrum_type: psd` is ADR 0006 D2's density form (`S2`, `power_spectral_density`), a dBFS/Hz axis."""
    p = pr.load_preset(preset_dir / "room_noise_floor.json")
    assert p.analysis["spectrum_type"] == "psd"
    cfg = pr.spectrum_config_from_preset(p)
    assert (cfg.normalization, cfg.scaling) == ("S2", "power_spectral_density")
    assert cfg.level_unit == "dBFS/Hz"
    assert (cfg.window, cfg.fft_size, cfg.window_length_samples) == ("hann", 8192, 8192)


@pytest.mark.parametrize("name", SHIPPED)
def test_every_shipped_preset_maps_to_a_config_the_oracle_accepts(preset_dir: Path, name: str):
    """The mapping never produces a config `SpectrumConfig.__post_init__` would refuse, for any shipped preset."""
    p = pr.load_preset(preset_dir / f"{name}.json")
    cfg = pr.spectrum_config_from_preset(p)
    assert cfg.window == p.analysis["window"]["name"]
    assert cfg.fft_size == cfg.window_length_samples == p.analysis["fft_size"]
    assert cfg.int16_scale == sp.DEFAULT_INT16_SCALE
    assert cfg.asdict().keys() == sp.ADR_0006_DEFAULT.asdict().keys()


def test_mapping_refuses_an_unmapped_spectrum_type_or_db_reference(preset_dir: Path):
    """The mapping names, never guesses: a value outside its two tables is a ValueError naming the field."""
    p = pr.load_preset(preset_dir / "stem_analysis.json")
    doc = copy.deepcopy(p.doc)
    doc["analysis"]["spectrum_type"] = "cepstrum"
    with pytest.raises(ValueError, match="spectrum_type"):
        pr.spectrum_config_from_preset(pr.Preset(id=p.id, sha256=p.sha256, doc=doc, path=p.path))
    doc = copy.deepcopy(p.doc)
    doc["analysis"]["db_reference"] = "dbfs_square"
    with pytest.raises(ValueError, match="db_reference"):
        pr.spectrum_config_from_preset(pr.Preset(id=p.id, sha256=p.sha256, doc=doc, path=p.path))


# --- the CLI -------------------------------------------------------------------------------


def test_cli_accepts_the_six_and_exits_1_on_a_rejection(preset_dir: Path, tmp_path: Path, capsys):
    paths = [str(preset_dir / f"{n}.json") for n in SHIPPED]
    assert pr.main(paths) == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 6 and out[1].startswith("live_singing") and "blackman_harris N=4096 fs=32000 -> S1/power_spectrum" in out[1]

    bad = tmp_path / "live_singing.json"
    bad.write_bytes((preset_dir / "live_singing.json").read_bytes() + b"\n")
    assert pr.main([str(bad)]) == 1
    assert "V0:" in capsys.readouterr().err


def test_cli_canonical_prints_the_file_bytes_exactly(preset_dir: Path, capsysbinary):
    path = preset_dir / "stem_analysis.json"
    assert pr.main(["--canonical", str(path)]) == 0
    assert capsysbinary.readouterr().out == path.read_bytes()


# --- the licence boundary, from this module's side --------------------------------------------


def test_presets_module_imports_nothing_from_python_scripts(repo_root: Path):
    """ADR 0004 item 3, read off the AST: the loader re-implements the rules; it names check_presets only in prose."""
    src = (repo_root / "host" / "src" / "spectral_host" / "presets.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    top_level = {m.split(".")[0] for m in imported}
    apache = {"check_presets", "synth_signals", "golden_compare", "doc_ocr"}
    assert not top_level & apache, imported
    allowed = set(sys.stdlib_module_names) | {"spectral_host", "numpy", "scipy"}
    assert top_level <= allowed, top_level - allowed
    sys_path = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Attribute) and n.attr == "path"
        and isinstance(n.value, ast.Name) and n.value.id == "sys"
    ]
    assert not sys_path, "presets.py touches the interpreter import path (ADR 0004 item 3)"
