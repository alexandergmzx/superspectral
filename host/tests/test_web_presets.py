# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""`/api/presets` against ADR 0021 decision 7(a) and roadmap W0, by hazard.

The gate this file exists for, in the roadmap's own words: "`GET
/api/presets/{id}` returns bytes **identical** to `protocols/presets/<id>.json`
for all six presets (sha256 compared in the test and displayed beside the
preset name), and a deliberately tampered preset **fails loudly with rule V0**
of the loader rather than being served."

Four hazards, one test each:

  * **The bytes drift.** A route that parsed and re-serialised would return
    valid JSON with a different digest, and the sha256 displayed beside the
    name would stop describing what was served. Asserted as
    `resp.content == path.read_bytes()`, byte for byte, plus the ETag.
  * **A bad preset is served, or silently dropped.** Either would let the
    watch and the host disagree about the preset a take names. Asserted
    through a tampered copy (V0) and a renamed copy (V1): 500, and the rule in
    the body.
  * **An id reaches the filesystem.** `presets_dir / preset_id` with
    unvalidated text is the classic traversal. Asserted with `../LICENSE`,
    `%2e%2e` and an absolute id — and by patching `Path.read_bytes` to explode,
    so "decided before the filesystem is touched" is the mechanism under test
    and not a claim about the code.
  * **The list is not the directory.** Six files, six rows, sorted.

Run: `uv run --project host pytest -q host/tests/test_web_presets.py`
"""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from spectral_host.hashing import sha256_bytes
from spectral_host.web.app import create_app

#: The six of ADR 0010 / ADR 0021 decision 7(b), as protocols/presets/ holds them.
EXPECTED_IDS = frozenset(
    {
        "diction_consonants",
        "live_singing",
        "room_noise_floor",
        "stem_analysis",
        "sustained_pitch_lab",
        "vowel_formant_study",
    }
)


def preset_files(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "protocols" / "presets").glob("*.json"))


def client_over(settings, presets_dir: Path) -> TestClient:
    """A client whose application reads `presets_dir` instead of the real one."""
    return TestClient(create_app(replace(settings, presets_dir=presets_dir)))


def copied_presets(repo_root: Path, destination: Path) -> Path:
    """A writable copy of `protocols/presets/` — the mutations below never touch the tracked files."""
    shutil.copytree(repo_root / "protocols" / "presets", destination)
    return destination


# --- the list ---------------------------------------------------------------------


def test_all_six_presets_are_listed_with_the_file_digest(web_client, repo_root):
    """Every preset file appears once, with the sha256 of ITS OWN BYTES and its true size."""
    body = web_client.get("/api/presets").json()
    assert body["count"] == len(body["presets"]) == 6
    rows = {row["id"]: row for row in body["presets"]}
    assert set(rows) == EXPECTED_IDS
    for path in preset_files(repo_root):
        raw = path.read_bytes()
        row = rows[path.stem]
        assert row["sha256"] == sha256_bytes(raw), "%s: the listed digest is not the file's" % path.name
        assert row["bytes"] == len(raw)
        assert row["url"] == "/api/presets/%s" % path.stem
        assert "host" in row["targets"], "ADR 0021 decision 7(b): 'host' covers the CLI and the web app alike"


def test_the_list_is_sorted_so_two_machines_produce_the_same_order(web_client):
    """Directory iteration order is filesystem-defined; a list whose order moves is a diff nobody can read."""
    ids = [row["id"] for row in web_client.get("/api/presets").json()["presets"]]
    assert ids == sorted(ids)


# --- byte identity ----------------------------------------------------------------


def test_each_preset_is_served_byte_identical_with_its_digest_as_the_etag(web_client, repo_root):
    """The W0 gate: `resp.content == path.read_bytes()`, and the ETag is that digest.

    A re-serialised body would still be valid JSON and would still parse — this
    is the assertion that would catch it, and the reason the route returns a
    `Response` of bytes rather than a model.
    """
    for path in preset_files(repo_root):
        raw = path.read_bytes()
        resp = web_client.get("/api/presets/%s" % path.stem)
        assert resp.status_code == 200, path.name
        assert resp.content == raw, "%s: served bytes differ from the file" % path.name
        assert resp.headers["etag"].strip('"') == sha256_bytes(raw)
        assert resp.headers["content-type"].startswith("application/json")


def test_a_preset_body_is_not_a_reserialisation(web_client, repo_root):
    """Belt and braces: the canonical form has two-space indent and sorted keys — a `json.dumps` default would not."""
    path = repo_root / "protocols" / "presets" / "live_singing.json"
    text = web_client.get("/api/presets/live_singing").text
    assert text == path.read_text(encoding="utf-8")
    assert text.endswith("\n") and not text.endswith("\n\n"), "V0: exactly one trailing newline"


# --- a bad preset fails loudly ------------------------------------------------------


def test_a_tampered_preset_fails_the_list_with_rule_v0_and_is_never_silently_omitted(
    web_settings, repo_root, tmp_path
):
    """Appending one newline breaks the canonical form. The list must 500 naming V0, not return five rows."""
    presets = copied_presets(repo_root, tmp_path / "tampered")
    victim = presets / "live_singing.json"
    victim.write_bytes(victim.read_bytes() + b"\n")

    with client_over(web_settings, presets) as client:
        resp = client.get("/api/presets")
    assert resp.status_code == 500
    error = resp.json()["error"]
    assert error["code"] == "preset_rejected"
    assert error["details"]["rule"] == "V0", "the loader's own rule number has to reach the client"
    assert error["details"]["id"] == "live_singing"
    assert "V0" in error["message"]


def test_a_tampered_preset_also_fails_its_own_route(web_settings, repo_root, tmp_path):
    """The single-preset route proves the file too; it must not shortcut straight to `read_bytes`."""
    presets = copied_presets(repo_root, tmp_path / "tampered-one")
    victim = presets / "live_singing.json"
    victim.write_bytes(victim.read_bytes().replace(b'"smoothing": 0.25', b'"smoothing": 0.2500001'))

    with client_over(web_settings, presets) as client:
        resp = client.get("/api/presets/live_singing")
    assert resp.status_code == 500
    assert resp.json()["error"]["details"]["rule"] == "V0", "seven decimals is outside the canonical number grammar"


def test_a_renamed_preset_fails_under_v1(web_settings, repo_root, tmp_path):
    """V1 is `id` == basename. A copy under another name is a second preset with the first one's id."""
    presets = copied_presets(repo_root, tmp_path / "renamed")
    (presets / "live_singing.json").rename(presets / "live_singing_copy.json")

    with client_over(web_settings, presets) as client:
        resp = client.get("/api/presets/live_singing_copy")
    assert resp.status_code == 500
    error = resp.json()["error"]
    assert error["details"]["rule"] == "V1"
    assert "live_singing" in error["message"]


# --- the id never reaches the filesystem ---------------------------------------------


@pytest.mark.parametrize(
    "raw_id",
    [
        "..",
        "%2e%2e",
        "..%2fLICENSE",
        "%2e%2e%2fLICENSE",
        "%2fetc%2fpasswd",
        "Live_Singing",  # uppercase: outside the schema's pattern
        "ab",  # shorter than the pattern's minimum
        "9live",  # must start with a letter
        "live-singing",  # hyphen is not in [a-z0-9_]
    ],
)
def test_an_id_outside_the_schema_pattern_is_404_and_never_becomes_a_path(web_client, raw_id):
    """Every one of these is refused by `^[a-z][a-z0-9_]{2,31}$` before `presets_dir / id` is built."""
    resp = web_client.get("/api/presets/%s" % raw_id)
    assert resp.status_code == 404, raw_id
    assert resp.json()["error"]["code"] in {"invalid_preset_id", "not_found"}
    assert "GNU GENERAL PUBLIC LICENSE" not in resp.text


def test_the_pattern_decides_before_any_file_is_read(web_client, monkeypatch):
    """The mechanism, not the outcome: with `Path.read_bytes` booby-trapped, a bad id still gets a clean 404."""

    def explode(self, *args, **kwargs):  # pragma: no cover - the point is that it is NOT reached
        raise AssertionError("the filesystem was touched for a rejected id: %s" % self)

    monkeypatch.setattr(Path, "read_bytes", explode)
    resp = web_client.get("/api/presets/%2e%2e")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "invalid_preset_id"


def test_an_unknown_but_well_formed_id_is_404_with_its_own_code(web_client):
    """`no_such_preset` matches the pattern; it just does not exist. A different code, so a typo reads differently."""
    resp = web_client.get("/api/presets/no_such_preset")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "unknown_preset"
