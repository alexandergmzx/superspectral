# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""spectrum.py — the per-bin dB row: masked below the floor, never widened."""

from __future__ import annotations

import numpy as np
import pytest

from golden_compare import load, spectrum
from golden_compare.tolerances import SPECTRUM_ATOL_DB, SPECTRUM_FLOOR_DBFS

ATOL = SPECTRUM_ATOL_DB.value       # 0.01 dB
FLOOR = SPECTRUM_FLOOR_DBFS.value   # −80 dBFS


@pytest.fixture
def golden() -> np.ndarray:
    # a peak at 0 dBFS, a skirt, and a floor well below −80 — the shape of a sine's spectrum
    levels = np.full(2049, -120.0)
    levels[100:110] = np.linspace(-60, 0, 10)
    levels[110:120] = np.linspace(0, -60, 10)
    levels[500] = -79.999   # just above the floor: compared
    levels[501] = -80.001   # just below: masked
    return levels


def test_golden_against_itself_has_zero_residual(golden):
    r = spectrum.compare(golden, golden.copy(), ATOL, FLOOR)
    assert r.max_abs == 0.0
    assert r.passed


def test_plus_0_005_db_passes_at_atol_0_01(golden):
    r = spectrum.compare(golden, golden + 0.005, ATOL, FLOOR)
    assert r.max_abs == pytest.approx(0.005)
    assert r.passed


def test_a_residual_of_exactly_the_atol_passes_the_limit_is_inclusive(golden):
    # 0.0 + 0.01 is exact in float64 at the peak bin; `<=` not `<` (assert_allclose semantics)
    cand = golden.copy()
    cand[109] = golden[109] + ATOL
    r = spectrum.compare(golden, cand, ATOL, FLOOR)
    assert r.max_abs == ATOL and r.worst_bin == 109
    assert r.passed


def test_plus_0_02_db_fails_at_atol_0_01(golden):
    r = spectrum.compare(golden, golden + 0.02, ATOL, FLOOR)
    assert r.max_abs == pytest.approx(0.02)
    assert not r.passed
    assert r.worst_bin in range(golden.size)


def test_bins_below_the_floor_are_masked_and_counted(golden):
    r = spectrum.compare(golden, golden, ATOL, FLOOR)
    below = int((golden < FLOOR).sum())
    assert r.n_masked == below
    assert r.n_compared == golden.size - below
    assert 501 in np.flatnonzero(np.ma.getmaskarray(spectrum.residual_db(golden, golden, FLOOR)))
    assert 500 not in np.flatnonzero(np.ma.getmaskarray(spectrum.residual_db(golden, golden, FLOOR)))


def test_a_gross_error_in_a_masked_bin_does_not_fail(golden):
    cand = golden.copy()
    cand[501] += 30.0             # masked by the golden
    r = spectrum.compare(golden, cand, ATOL, FLOOR)
    assert r.passed
    assert r.n_candidate_above_floor_in_mask == 1   # but it is reported


def test_the_same_error_one_bin_above_the_floor_fails_at_the_full_atol(golden):
    cand = golden.copy()
    cand[500] += 0.02             # −79.999 is compared, at the same 0.01 dB as the peak
    r = spectrum.compare(golden, cand, ATOL, FLOOR)
    assert not r.passed
    assert r.worst_bin == 500


def test_the_mask_follows_the_golden_not_the_candidate(golden):
    cand = golden.copy()
    cand[105] = -150.0            # candidate under-reports a compared bin: still compared, fails
    r = spectrum.compare(golden, cand, ATOL, FLOOR)
    assert not r.passed
    assert r.worst_bin == 105


def test_nothing_compared_is_not_a_pass():
    silence = np.full(2049, -200.0)
    r = spectrum.compare(silence, silence, ATOL, FLOOR)
    assert r.n_compared == 0
    assert not r.passed
    assert "no bin" in r.summary()


def test_nan_in_a_compared_bin_fails(golden):
    cand = golden.copy()
    cand[105] = np.nan
    r = spectrum.compare(golden, cand, ATOL, FLOOR)
    assert not r.passed
    assert r.worst_bin == 105


def test_bin_grid_mismatch_raises_instead_of_interpolating(golden):
    with pytest.raises(ValueError, match="bins"):
        spectrum.residual_db(golden, golden[:-1], FLOOR)


def test_two_d_arrays_are_refused_until_the_level_column_is_chosen(golden):
    two_d = np.stack([np.arange(golden.size, dtype=float), golden], axis=1)
    with pytest.raises(ValueError, match="1-D"):
        spectrum.residual_db(two_d, two_d, FLOOR)


def test_real_tier0_spectrum_against_itself_is_zero(tier0_manifest_path, repo_root):
    manifest = load.load_manifest(tier0_manifest_path)
    entry = next(e for e in manifest["outputs"] if e["analysis"] == "spectrum" and "sine_440_0dBFS" in e["path"])
    arr = load.load_array(repo_root / entry["path"], entry)
    level = load.column(arr, entry, "level", 1)
    r = spectrum.compare(level, level.copy(), ATOL, FLOOR)
    assert r.passed and r.max_abs == 0.0
    assert r.n_compared > 0 and r.n_masked > 0   # a sine has a skirt and a floor
