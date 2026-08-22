# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""Golden-manifest schema "1.1" (ADR 0009, amended 2026-08-21; ADR 0006 D1).

The schema is data that the Apache-2.0 harness also reads, so what it accepts
and rejects is a contract. These tests pin the contract's edges — the quoted
version, the `windows[]` conditional, the family enum, the digest recipe — and
run the schema's own worked example through it, so the example cannot rot.
They do not implement verify.py's invariants 7/8 (unit B-U5); they check that
the recipe those invariants will recompute is the one the schema describes.

Run: `uv run --project host pytest -q host/tests/test_manifest_schema.py`
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

import jsonschema
import numpy as np
import pytest
import yaml
from scipy.signal.windows import general_cosine

SCHEMA_VERSION = "1.1"
FAMILIES = ["rect", "hann", "blackman", "blackman_harris", "blackman_nuttall", "nuttall", "flat_top"]

#: The digests the worked example and docs/validation/golden-files.md carry for
#: (hann, 4096) and (rect, 4096). Recipe: sha256 over the N float32 little-endian
#: samples of general_cosine(N, a, sym=False). Computed 2026-08-21 on x86-64,
#: SciPy 1.18.0; the closest any sample comes to a float32 rounding midpoint is
#: 1521 float64 ULP (nuttall, N = 2048), so a last-ULP libm difference cannot move them.
PINNED_DIGESTS = {
    ("hann", 4096): "3ce6c7c870b60fc2425689b96f2ccf1cecff9b071766a48ae3d25a0ca8f3d304",
    ("rect", 4096): "3035aac5fb87474c303702f9030301b4e6bb7aee93be3710b8ab8dcea201db70",
}


def window_digest(coefficients: list[float], n: int) -> str:
    """The schema's `windows[].sha256` recipe, verbatim from its description."""
    w = general_cosine(n, coefficients, sym=False)
    return hashlib.sha256(np.asarray(w, dtype="<f4").tobytes()).hexdigest()


@pytest.fixture(scope="module")
def schema_path(repo_root: Path) -> Path:
    return repo_root / "host" / "golden" / "manifest.schema.yaml"


@pytest.fixture(scope="module")
def schema(schema_path: Path) -> dict:
    return yaml.safe_load(schema_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator(schema: dict) -> jsonschema.Draft202012Validator:
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


@pytest.fixture(scope="module")
def example(schema_path: Path) -> dict:
    """The worked example at the foot of the schema file, un-commented, placeholders filled."""
    lines = schema_path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("#   # SPDX-FileCopyrightText"))
    body = "\n".join(line[4:] if line.startswith("#   ") else "" for line in lines[start:] if line.startswith("#"))
    body = re.sub(r"<64 hex[^>]*>", "a" * 64, body)
    body = re.sub(r"<40 hex[^>]*>", "b" * 40, body)
    doc = yaml.safe_load(body)
    assert isinstance(doc, dict) and "schema" in doc, "worked example not found at the foot of the schema"
    return doc


def errors(validator, doc) -> list[str]:
    return [e.message for e in validator.iter_errors(doc)]


# --- the worked example -----------------------------------------------------


def test_worked_example_validates(validator, example):
    """An example that does not validate teaches the generator author the wrong shape."""
    assert errors(validator, example) == []


def test_worked_example_pins_the_documented_hann_and_rect_digests(example):
    """The example's digests are real values, not placeholders, and they recompute."""
    entries = {(w["family"], w["n"]): w for w in example["windows"]}
    for key, digest in PINNED_DIGESTS.items():
        assert entries[key]["sha256"] == digest
        assert window_digest(entries[key]["coefficients"], key[1]) == digest


# --- the version -----------------------------------------------------------


def test_schema_version_is_the_quoted_string(validator, example):
    assert example["schema"] == SCHEMA_VERSION


@pytest.mark.parametrize("bad", [1, "1", 1.1, "1.0", "1.2", "01.1"])
def test_other_schema_versions_are_refused_not_coerced(validator, example, bad):
    """A reader accepts exactly one value; the schema-1 integer must fail, not round-trip."""
    doc = copy.deepcopy(example)
    doc["schema"] = bad
    assert errors(validator, doc)


def test_schema_id_names_the_version(schema):
    assert schema["$id"].endswith(f":{SCHEMA_VERSION}")


# --- windows[] and the spectrum conditional ----------------------------------


def test_windows_required_when_spectrum_present(validator, example):
    doc = copy.deepcopy(example)
    del doc["windows"]
    assert any("windows" in m for m in errors(validator, doc))


def test_windows_optional_when_spectrum_absent(validator, example):
    """A pitch-only set may omit windows[]; forcing it would make every set carry a digest it never uses."""
    doc = copy.deepcopy(example)
    del doc["windows"]
    del doc["analyses"]["spectrum"]
    assert errors(validator, doc) == []


def test_windows_may_carry_families_the_spectrum_does_not_use(validator, example):
    doc = copy.deepcopy(example)
    doc["windows"].append({"family": "flat_top", "n": 8192, "coefficients": [0.2, 0.4, 0.3, 0.08, 0.007], "sha256": "c" * 64})
    assert errors(validator, doc) == []


def test_empty_windows_is_rejected(validator, example):
    doc = copy.deepcopy(example)
    doc["windows"] = []
    assert errors(validator, doc)


@pytest.mark.parametrize("field", ["family", "n", "coefficients", "sha256"])
def test_windows_entry_requires_every_field(validator, example, field):
    doc = copy.deepcopy(example)
    del doc["windows"][0][field]
    assert errors(validator, doc)


def test_windows_entry_rejects_unknown_fields(validator, example):
    """additionalProperties: false — a misspelt `sha_256` must not validate as 'no digest recorded'."""
    doc = copy.deepcopy(example)
    doc["windows"][0]["sha_256"] = "a" * 64
    assert errors(validator, doc)


@pytest.mark.parametrize("coefficients", [[], [0.1] * 6])
def test_coefficient_count_is_one_to_five(validator, example, coefficients):
    doc = copy.deepcopy(example)
    doc["windows"][0]["coefficients"] = coefficients
    assert errors(validator, doc)


@pytest.mark.parametrize("digest", ["", "A" * 64, "a" * 63, "a" * 65, "g" * 64])
def test_digest_must_be_64_lowercase_hex(validator, example, digest):
    doc = copy.deepcopy(example)
    doc["windows"][0]["sha256"] = digest
    assert errors(validator, doc)


# --- the family enum ---------------------------------------------------------


def test_window_family_enum_is_the_six_preset_families_plus_rect(schema, repo_root):
    """Shared with presets.schema.json: same six names, and only `rect` on top (ADR 0006 consequence (c))."""
    golden = schema["$defs"]["window_family"]["enum"]
    presets = json.loads((repo_root / "protocols" / "specs" / "presets.schema.json").read_text(encoding="utf-8"))
    preset_names = _find_window_name_enum(presets)
    assert set(golden) == set(preset_names) | {"rect"}
    assert "rect" not in preset_names


def _find_window_name_enum(node):
    """Locate the `window.name` enum wherever presets.schema.json nests it."""
    if isinstance(node, dict):
        props = node.get("properties", {})
        if "coefficients" in props and "name" in props and "enum" in props["name"]:
            return props["name"]["enum"]
        for value in node.values():
            found = _find_window_name_enum(value)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_window_name_enum(value)
            if found:
                return found
    return None


@pytest.mark.parametrize("name", ["nuttall4", "hanning", "blackmanharris", "flattop", "gaussian", ""])
def test_scipy_and_foreign_names_are_rejected_as_families(validator, example, name):
    """The name-based oracle is the 0.0163 trap; SciPy spellings must not sneak in as families."""
    doc = copy.deepcopy(example)
    doc["analyses"]["spectrum"]["window"] = name
    assert errors(validator, doc)


@pytest.mark.parametrize("name", FAMILIES)
def test_every_family_is_accepted_in_both_places(validator, example, name):
    doc = copy.deepcopy(example)
    doc["analyses"]["spectrum"]["window"] = name
    doc["windows"][0]["family"] = name
    assert errors(validator, doc) == []


# --- the digest recipe -------------------------------------------------------


def test_rect_digest_is_sha256_of_n_float32_ones_little_endian():
    """Closed form: the recipe must hash exactly N × b'\\x00\\x00\\x80\\x3f' for rect — no libm involved."""
    assert window_digest([1.0], 4096) == hashlib.sha256(b"\x00\x00\x80\x3f" * 4096).hexdigest()
    assert window_digest([1.0], 4096) == PINNED_DIGESTS[("rect", 4096)]


def test_hann_digest_recomputes_to_the_pinned_value():
    assert window_digest([0.5, 0.5], 4096) == PINNED_DIGESTS[("hann", 4096)]


def test_digest_distinguishes_periodic_from_symmetric():
    """Hashing the symmetric form would validate a window ADR 0006 rejects."""
    w_sym = general_cosine(4096, [0.5, 0.5], sym=True)
    assert hashlib.sha256(np.asarray(w_sym, dtype="<f4").tobytes()).hexdigest() != PINNED_DIGESTS[("hann", 4096)]


def test_digest_distinguishes_float64_from_float32_samples():
    w = general_cosine(4096, [0.5, 0.5], sym=False)
    assert hashlib.sha256(w.tobytes()).hexdigest() != PINNED_DIGESTS[("hann", 4096)]
