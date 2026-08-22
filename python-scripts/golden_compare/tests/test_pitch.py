# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""pitch.py — the frame-grid trap made a test, plus the sentinel and mir_eval rows."""

from __future__ import annotations

import numpy as np
import pytest

from golden_compare import load, pitch
from golden_compare.tolerances import F0_INJECTION_MEDIAN_ABS_CENTS, VOICING_FALSE_ALARM_MAX_PERCENT, VOICING_RECALL_MIN_PERCENT

LIMIT = F0_INJECTION_MEDIAN_ABS_CENTS.value   # 5 cents

# A 6 Hz, ±100 cent vibrato on 220 Hz — the tier-0 `vowel_a_vibrato_220_6hz_100c` shape.
F0, RATE_HZ, DEPTH_CENTS, DUR = 220.0, 6.0, 100.0, 3.0
DT = 0.01


def vibrato(t: np.ndarray) -> np.ndarray:
    return F0 * 2.0 ** (DEPTH_CENTS / 1200.0 * np.sin(2 * np.pi * RATE_HZ * t))


@pytest.fixture
def praat_grid() -> np.ndarray:
    # Praat centres its grid: t1 = (duration − (nFrames − 1)·dt)/2 = 0.025 s for 3.0 s at 10 ms, 296 frames
    n = 296
    t1 = (DUR - (n - 1) * DT) / 2
    return t1 + DT * np.arange(n)


@pytest.fixture
def device_grid(praat_grid) -> np.ndarray:
    # the device frames from sample 0 with a hop: same count, 7 ms earlier than Praat's grid
    return praat_grid - 0.007


def test_cents_of_an_octave_is_1200():
    assert pitch.cents(440.0, 220.0) == pytest.approx(1200.0)
    np.testing.assert_allclose(pitch.cents(np.array([220.0, 440.0]), 220.0), [0.0, 1200.0])


def test_cents_refuses_the_unvoiced_sentinel():
    with pytest.raises(ValueError, match="sentinel"):
        pitch.cents(np.array([220.0, 0.0]), 220.0)
    with pytest.raises(ValueError):
        pitch.cents(-1.0, 220.0)


def test_seven_ms_grid_offset_fails_by_index_and_passes_after_resample(praat_grid, device_grid):
    ref = vibrato(praat_grid)          # what Praat reports, on its grid
    dev = vibrato(device_grid)         # a perfect device, on its own grid

    by_index = pitch.median_abs_cents(ref, dev)            # the trap: compare frame k with frame k
    assert by_index > LIMIT, f"index comparison should fail on a 7 ms offset, got {by_index:.2f} cents"

    ref_on_dev = pitch.resample_to_times(praat_grid, ref, device_grid)
    after = pitch.median_abs_cents(ref_on_dev, dev)
    assert after <= LIMIT, f"resampled comparison should pass, got {after:.2f} cents"
    assert after < by_index / 5


def test_resample_is_linear_in_log_frequency_not_in_hertz():
    t = np.array([0.0, 1.0])
    f = np.array([200.0, 800.0])          # two octaves
    mid = pitch.resample_to_times(t, f, np.array([0.5]))
    assert mid[0] == pytest.approx(400.0)  # geometric midpoint, not 500 Hz


def test_resample_never_crosses_an_unvoiced_gap():
    t = np.arange(6) * 0.01
    f = np.array([220.0, 221.0, 0.0, 0.0, 225.0, 226.0])
    dev_t = np.array([0.005, 0.015, 0.025, 0.035, 0.045])
    out = pitch.resample_to_times(t, f, dev_t)
    assert out[0] > 0                                  # between two voiced frames
    assert out[1] == 0 and out[2] == 0 and out[3] == 0  # touching the gap on either side: sentinel
    assert out[4] > 0


def test_resample_outside_the_reference_range_is_unvoiced():
    t = np.array([0.1, 0.2, 0.3])
    f = np.array([220.0, 220.0, 220.0])
    out = pitch.resample_to_times(t, f, np.array([0.0, 0.05, 0.1, 0.3, 0.31]))
    np.testing.assert_array_equal(out, [0.0, 0.0, 220.0, 220.0, 0.0])


def test_resample_on_an_exact_frame_returns_that_frame_even_beside_a_gap():
    t = np.array([0.0, 0.01, 0.02])
    f = np.array([0.0, 230.0, 0.0])
    out = pitch.resample_to_times(t, f, np.array([0.01, 0.005, 0.015]))
    np.testing.assert_array_equal(out, [230.0, 0.0, 0.0])


def test_resample_keeps_a_non_zero_sentinel():
    t = np.array([0.0, 0.01])
    f = np.array([-1.0, 220.0])
    out = pitch.resample_to_times(t, f, np.array([0.005]), sentinel=-1.0)
    assert out[0] == -1.0


def test_resample_refuses_unsorted_reference_times():
    with pytest.raises(ValueError, match="increasing"):
        pitch.resample_to_times(np.array([0.02, 0.01]), np.array([220.0, 220.0]), np.array([0.015]))


def test_median_abs_cents_uses_jointly_voiced_frames_only():
    ref = np.array([220.0, 0.0, 220.0, 220.0])
    est = np.array([220.0, 220.0, 0.0, 440.0])
    assert pitch.median_abs_cents(ref, est) == pytest.approx(600.0)   # frames 0 and 3: 0 and 1200
    assert int(pitch.jointly_voiced(ref, est).sum()) == 2


def test_median_abs_cents_is_nan_when_nothing_is_jointly_voiced():
    assert np.isnan(pitch.median_abs_cents(np.array([220.0, 0.0]), np.array([0.0, 220.0])))


def test_median_abs_cents_refuses_tracks_on_different_grids():
    with pytest.raises(ValueError, match="resample_to_times"):
        pitch.median_abs_cents(np.array([220.0, 220.0]), np.array([220.0]))


def test_mir_eval_identical_tracks_score_perfectly(praat_grid):
    f = vibrato(praat_grid)
    m = pitch.mir_eval_melody(praat_grid, f, praat_grid, f)
    assert m["RPA"] == 1.0 and m["RCA"] == 1.0 and m["OA"] == 1.0
    assert m["VR"] == 1.0 and m["VFA"] == 0.0


def test_mir_eval_octave_error_is_visible_as_rca_minus_rpa(praat_grid):
    f = vibrato(praat_grid)
    m = pitch.mir_eval_melody(praat_grid, f, praat_grid, 2 * f)
    assert m["RPA"] == 0.0 and m["RCA"] == 1.0


def test_mir_eval_survives_the_seven_ms_offset_because_it_resamples(praat_grid, device_grid):
    m = pitch.mir_eval_melody(praat_grid, vibrato(praat_grid), device_grid, vibrato(device_grid))
    assert m["RPA"] > 0.99


def test_mir_eval_cent_tolerance_is_honoured(praat_grid):
    f = vibrato(praat_grid)
    shifted = f * 2 ** (30 / 1200)     # +30 cents everywhere
    assert pitch.mir_eval_melody(praat_grid, f, praat_grid, shifted, cent_tolerance=50)["RPA"] == 1.0
    assert pitch.mir_eval_melody(praat_grid, f, praat_grid, shifted, cent_tolerance=25)["RPA"] == 0.0


def test_compare_tracks_reports_the_median_row_and_the_mir_eval_rows(praat_grid, device_grid):
    r = pitch.compare_tracks(praat_grid, vibrato(praat_grid), device_grid, vibrato(device_grid), median_limit_cents=LIMIT)
    assert r.passed
    assert r.n_jointly_voiced > 250
    assert set(r.metrics) == {"RPA", "RCA", "OA", "VR", "VFA"}
    assert "PASS" in r.summary()


def test_real_tier0_pitch_track_against_itself_is_exact(tier0_manifest_path, repo_root):
    manifest = load.load_manifest(tier0_manifest_path)
    entry = next(e for e in manifest["outputs"] if e["analysis"] == "pitch" and "vibrato" in e["path"])
    arr = load.load_array(repo_root / entry["path"], entry)
    t = load.column(arr, entry, "time", 0)
    f = load.column(arr, entry, "f0", 1)
    sentinel = float(entry["unvoiced_sentinel"])
    r = pitch.compare_tracks(t, f, t, f, median_limit_cents=LIMIT, sentinel=sentinel)
    assert r.passed and r.median_abs_cents == 0.0
    assert r.metrics["RPA"] == 1.0


def test_resample_onto_its_own_grid_is_bit_identical(praat_grid):
    f = vibrato(praat_grid)
    f[10:20] = 0.0
    np.testing.assert_array_equal(pitch.resample_to_times(praat_grid, f, praat_grid), f)


def test_an_estimator_that_voices_half_the_frames_accurately_fails_the_voicing_row(praat_grid):
    # the median row alone would pass this (every voiced frame is exact); the table's VR ≥ 90 % row must not
    f = vibrato(praat_grid)
    half = f.copy()
    half[::2] = 0.0                                   # VR = 50 %
    r = pitch.compare_tracks(praat_grid, f, praat_grid, half, median_limit_cents=LIMIT)
    assert r.median_passed and r.median_abs_cents == 0.0
    assert r.metrics["VR"] == pytest.approx(0.5, abs=0.01) and not r.voicing_passed   # mir_eval re-grids; ≈ 148/297
    assert not r.passed and "FAILS" in r.summary()


def test_an_estimator_that_voices_silence_fails_the_vfa_row(praat_grid):
    f = vibrato(praat_grid)
    ref = f.copy()
    ref[:148] = 0.0                                   # the reference is unvoiced for the first half
    r = pitch.compare_tracks(praat_grid, ref, praat_grid, f, median_limit_cents=LIMIT)   # the estimate voices everything
    assert r.median_passed
    assert r.metrics["VR"] == 1.0 and r.metrics["VFA"] == 1.0 and not r.voicing_passed
    assert not r.passed


def test_voicing_limits_default_to_the_table_rows():
    assert pitch.DEFAULT_VR_MIN == VOICING_RECALL_MIN_PERCENT.value / 100 == 0.9
    assert pitch.DEFAULT_VFA_MAX == VOICING_FALSE_ALARM_MAX_PERCENT.value / 100 == 0.1
