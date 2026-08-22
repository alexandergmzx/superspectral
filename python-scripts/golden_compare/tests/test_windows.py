# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""windows.py — the device lane's hasher reproduces the manifest's digests, byte for byte."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from golden_compare import load, windows
from golden_compare.tolerances import WINDOW_COEFFICIENTS_ATOL

# Pinned in docs/validation/golden-files.md (`windows[]` example) and host/tests/test_manifest_schema.py.
HANN_4096 = "3ce6c7c870b60fc2425689b96f2ccf1cecff9b071766a48ae3d25a0ca8f3d304"
RECT_4096 = "3035aac5fb87474c303702f9030301b4e6bb7aee93be3710b8ab8dcea201db70"

# preset-schema.md §4.3 (the single source) plus `rect` — copied here only to build dumps for the tests;
# the package itself never carries a table, it reads `coefficients` from the manifest entry.
FAMILIES = {
    "hann": [0.5, 0.5],
    "blackman": [0.42, 0.5, 0.08],
    "blackman_harris": [0.35875, 0.48829, 0.14128, 0.01168],
    "blackman_nuttall": [0.3635819, 0.4891775, 0.1365995, 0.0106411],
    "nuttall": [0.355768, 0.487396, 0.144232, 0.012604],
    "flat_top": [0.21557895, 0.41663158, 0.277263158, 0.083578947, 0.006947368],
    "rect": [1.0],
}


def _dump(tmp_path: Path, table: np.ndarray, name: str = "table.f32") -> Path:
    p = tmp_path / name
    p.write_bytes(np.ascontiguousarray(table, dtype="<f4").tobytes())
    return p


def test_hann_4096_digest_matches_the_value_pinned_in_golden_files_md():
    assert windows.table_sha256(windows.window_table([0.5, 0.5], 4096)) == HANN_4096


def test_rect_4096_digest_is_the_hash_of_4096_float32_ones():
    assert windows.table_sha256(windows.window_table([1.0], 4096)) == RECT_4096
    assert hashlib.sha256(b"\x00\x00\x80\x3f" * 4096).hexdigest() == RECT_4096


def test_periodic_form_not_symmetric_hann_first_sample_is_zero_and_no_sample_is_one_at_the_end():
    w = windows.periodic_cosine_sum([0.5, 0.5], 8)
    assert w[0] == pytest.approx(0.0)
    assert w[4] == pytest.approx(1.0)            # the period's centre, j = N/2
    assert w[-1] == pytest.approx(w[1])          # periodic: w[N−1] == w[1], not 0


def test_periodic_nenbw_equals_the_closed_form_the_presets_ship():
    # ADR 0006 D2: NENBW = (a0² + Σ a_k²/2)/a0² for the PERIODIC form; hann = 1.5 exactly, symmetric gives 1.500366
    for family, a in FAMILIES.items():
        w = windows.periodic_cosine_sum(a, 4096)
        nenbw = 4096 * np.sum(w * w) / np.sum(w) ** 2
        closed = (a[0] ** 2 + sum(c * c for c in a[1:]) / 2) / a[0] ** 2
        assert nenbw == pytest.approx(closed, abs=1e-6), family


def test_raw_dump_of_a_known_table_hashes_to_the_manifest_digest(tmp_path):
    p = _dump(tmp_path, windows.window_table([0.5, 0.5], 4096))
    assert windows.raw_f32_sha256(p) == HANN_4096
    entry = {"family": "hann", "n": 4096, "coefficients": [0.5, 0.5], "sha256": HANN_4096}
    r = windows.compare_window_digest(p, entry)
    assert r.passed and r.digest_match and r.manifest_self_consistent
    assert r.max_abs_diff == 0.0 and r.n_samples == 4096


def test_a_symmetric_table_is_caught_by_the_digest_and_measured_by_the_diff(tmp_path):
    n = 4096
    j = np.arange(n)
    symmetric = (0.5 - 0.5 * np.cos(2 * np.pi * j / (n - 1))).astype("<f4")   # the esp-dsp / sym=True form
    p = _dump(tmp_path, symmetric)
    r = windows.compare_window_digest(p, {"family": "hann", "n": n, "coefficients": [0.5, 0.5], "sha256": HANN_4096})
    assert not r.passed and not r.digest_match
    assert r.manifest_self_consistent                   # the manifest is fine; the dump is the wrong form
    assert r.max_abs_diff > WINDOW_COEFFICIENTS_ATOL.value
    assert not r.within(WINDOW_COEFFICIENTS_ATOL.value)
    assert "DIFFERS" in r.summary()


def test_a_last_ulp_perturbation_fails_the_exact_row_but_sits_inside_the_coefficient_row(tmp_path):
    table = windows.window_table([0.5, 0.5], 4096)
    nudged = table.copy()
    nudged[1000] = np.nextafter(nudged[1000], np.float32(2.0))   # one float32 ULP
    p = _dump(tmp_path, nudged)
    r = windows.compare_window_digest(p, {"family": "hann", "n": 4096, "coefficients": [0.5, 0.5], "sha256": HANN_4096})
    assert not r.digest_match                            # exact means exact
    assert r.within(WINDOW_COEFFICIENTS_ATOL.value)      # and the report says how small the miss is
    assert r.worst_index == 1000


def test_wrong_length_dump_is_a_fail_with_no_per_sample_comparison(tmp_path):
    p = _dump(tmp_path, windows.window_table([0.5, 0.5], 2048))
    r = windows.compare_window_digest(p, {"family": "hann", "n": 4096, "coefficients": [0.5, 0.5], "sha256": HANN_4096})
    assert not r.passed and r.n_samples == 2048 and np.isnan(r.max_abs_diff)


def test_a_dump_that_is_not_whole_float32_samples_is_refused(tmp_path):
    p = tmp_path / "odd.f32"
    p.write_bytes(b"\x00" * 7)
    with pytest.raises(ValueError, match="float32"):
        windows.raw_f32_sha256(p)
    (tmp_path / "empty.f32").write_bytes(b"")
    with pytest.raises(ValueError):
        windows.read_raw_f32(tmp_path / "empty.f32")


def test_manifest_digest_that_does_not_recompute_is_flagged_as_inconsistent(tmp_path):
    p = _dump(tmp_path, windows.window_table([0.5, 0.5], 4096))
    bogus = {"family": "hann", "n": 4096, "coefficients": [0.5, 0.5], "sha256": "f" * 64}
    r = windows.compare_window_digest(p, bogus)
    assert not r.digest_match and not r.manifest_self_consistent
    assert "does not recompute" in r.summary()


def test_every_tier0_window_entry_recomputes_from_its_coefficients_and_hashes_from_a_dump(tmp_path, tier0_manifest_path):
    manifest = load.load_manifest(tier0_manifest_path)
    entries = manifest["windows"]
    assert {e["family"] for e in entries} == set(FAMILIES)
    for e in entries:
        assert e["coefficients"] == FAMILIES[e["family"]], e["family"]
        p = _dump(tmp_path, windows.window_table(e["coefficients"], e["n"]), f"{e['family']}_{e['n']}.f32")
        r = windows.compare_window_digest(p, e)
        assert r.passed and r.manifest_self_consistent, r.summary()
