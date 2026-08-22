# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""load.py — an array is trusted only after it agrees with its manifest entry."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from golden_compare import load


def _entry(path: Path, arr: np.ndarray, **overrides) -> dict:
    e = {
        "path": str(path),
        "sha256": load.sha256_of_file(path),
        "analysis": "spectrum",
        "input": "x.wav",
        "dtype": str(arr.dtype),
        "shape": list(arr.shape),
        "units": "Hz, dB re full-scale sine",
        "columns": ["frequency", "level"],
    }
    e.update(overrides)
    return e


@pytest.fixture
def saved(tmp_path: Path) -> tuple[Path, np.ndarray]:
    arr = np.stack([np.arange(5, dtype=np.float64), np.linspace(-90, 0, 5)], axis=1)
    p = tmp_path / "spectrum_x.npy"
    np.save(p, arr)
    return p, arr


def test_array_that_matches_its_entry_loads(saved):
    p, arr = saved
    out = load.load_array(p, _entry(p, arr))
    np.testing.assert_array_equal(out, arr)


def test_dtype_drift_is_refused_not_cast(saved):
    p, arr = saved
    with pytest.raises(load.ManifestMismatch, match="dtype"):
        load.load_array(p, _entry(p, arr, dtype="float32"))


def test_shape_drift_is_refused(saved):
    p, arr = saved
    with pytest.raises(load.ManifestMismatch, match="shape"):
        load.load_array(p, _entry(p, arr, shape=[5, 3]))


def test_bytes_that_do_not_hash_to_the_manifest_are_refused(saved):
    p, arr = saved
    with pytest.raises(load.ManifestMismatch, match="sha256"):
        load.load_array(p, _entry(p, arr, sha256="0" * 64))


def test_sha256_check_can_be_waived_only_explicitly(saved):
    p, arr = saved
    out = load.load_array(p, _entry(p, arr, sha256="0" * 64), check_sha256=False)
    np.testing.assert_array_equal(out, arr)


def test_pickled_object_array_never_loads(tmp_path):
    p = tmp_path / "evil.npy"
    np.save(p, np.array([{"a": 1}], dtype=object), allow_pickle=True)
    with pytest.raises(ValueError):
        load.load_array(p)


def test_npz_archive_is_not_a_golden_file(tmp_path):
    p = tmp_path / "bundle.npz"
    np.savez(p, a=np.zeros(3))
    with pytest.raises(load.ManifestMismatch, match="npz"):
        load.load_array(p)


def test_manifest_schema_1_1_string_is_accepted(tmp_path):
    m = tmp_path / "manifest.yaml"
    m.write_text(yaml.safe_dump({"schema": "1.1", "set": "x", "outputs": []}))
    assert load.load_manifest(m)["schema"] == "1.1"


@pytest.mark.parametrize("version", [1, 1.1, "1", "1.0", "1.2", None])
def test_any_other_schema_version_is_refused_never_coerced(tmp_path, version):
    m = tmp_path / "manifest.yaml"
    m.write_text(yaml.safe_dump({"schema": version, "set": "x"}))
    with pytest.raises(load.ManifestMismatch, match="schema"):
        load.load_manifest(m)


def test_find_output_matches_on_the_repository_relative_suffix(tmp_path):
    target = tmp_path / "host" / "golden" / "outputs" / "s" / "a.npy"
    manifest = {"outputs": [
        {"path": "host/golden/outputs/s/a.npy"},
        {"path": "host/golden/outputs/s/b.npy"},
    ]}
    assert load.find_output(manifest, target)["path"] == "host/golden/outputs/s/a.npy"


def test_find_output_refuses_a_basename_that_lives_in_another_set(tmp_path):
    target = tmp_path / "host" / "golden" / "outputs" / "other" / "a.npy"
    manifest = {"outputs": [{"path": "host/golden/outputs/s/a.npy"}]}
    with pytest.raises(load.ManifestMismatch, match="0 outputs"):
        load.find_output(manifest, target)


def test_find_window_needs_exactly_one_family_n_pair():
    manifest = {"windows": [{"family": "hann", "n": 4096}, {"family": "hann", "n": 8192}]}
    assert load.find_window(manifest, "hann", 8192)["n"] == 8192
    with pytest.raises(load.ManifestMismatch):
        load.find_window(manifest, "rect", 4096)


def test_column_is_found_by_manifest_name_not_by_position():
    arr = np.array([[1.0, 2.0], [3.0, 4.0]])
    entry = {"columns": ["level", "frequency"]}   # swapped on purpose
    np.testing.assert_array_equal(load.column(arr, entry, "level", 1), [1.0, 3.0])
    with pytest.raises(load.ManifestMismatch, match="no 'f0'"):
        load.column(arr, entry, "f0", 1)


def test_real_tier0_arrays_load_against_their_entries(tier0_manifest_path, repo_root):
    manifest = load.load_manifest(tier0_manifest_path)
    n = 0
    for entry in manifest["outputs"]:
        arr = load.load_array(repo_root / entry["path"], entry)
        assert tuple(arr.shape) == tuple(entry["shape"])
        n += 1
    assert n >= 1
