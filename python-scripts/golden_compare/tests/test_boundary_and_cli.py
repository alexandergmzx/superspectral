# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""The licence boundary (ADR 0004) and the CLI's exit codes."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest
import yaml

from golden_compare import cli, windows

PACKAGE = Path(__file__).resolve().parents[1]
SOURCES = sorted(PACKAGE.glob("golden_compare/*.py")) + sorted(PACKAGE.glob("tests/*.py"))


def test_package_never_imports_the_gpl_side_or_edits_the_import_path():
    bad = re.compile(r"^\s*(from|import)\s+spectral_host\b|sys\.path", re.M)
    offenders = [p for p in SOURCES if bad.search(p.read_text(encoding="utf-8"))]
    assert not offenders, f"GPL boundary crossed in {offenders}"


def test_every_source_carries_the_apache_spdx_header():
    for p in SOURCES:
        head = p.read_text(encoding="utf-8").splitlines()[:2]
        assert head == ["# SPDX-FileCopyrightText: 2026 Alexander Gomez", "# SPDX-License-Identifier: Apache-2.0"], p


def test_every_module_documents_its_cli():
    for p in PACKAGE.glob("golden_compare/*.py"):
        text = p.read_text(encoding="utf-8")
        assert '"""' in text and "python -m golden_compare" in text, f"{p.name} lacks a docstring naming the CLI"


@pytest.fixture
def spectra(tmp_path: Path) -> dict[str, Path]:
    freq = np.arange(2049, dtype=np.float64) * (32000 / 4096)
    level = np.full(2049, -120.0)
    level[56] = 0.0
    golden = np.stack([freq, level], axis=1)
    paths = {}
    for name, delta in (("golden", 0.0), ("near", 0.005), ("far", 0.02)):
        arr = golden.copy()
        arr[:, 1] += delta
        p = tmp_path / f"{name}.npy"
        np.save(p, arr)
        paths[name] = p
    return paths


def test_cli_spectrum_exit_codes_follow_the_atol(spectra, capsys):
    assert cli.main(["spectrum", "--golden", str(spectra["golden"]), "--candidate", str(spectra["golden"])]) == 0
    assert "max |Δ| = 0.000000 dB" in capsys.readouterr().out
    assert cli.main(["spectrum", "--golden", str(spectra["golden"]), "--candidate", str(spectra["near"])]) == 0
    assert cli.main(["spectrum", "--golden", str(spectra["golden"]), "--candidate", str(spectra["far"])]) == 1
    assert cli.main(["spectrum", "--golden", str(spectra["golden"]), "--candidate", str(spectra["far"]), "--atol-db", "0.05"]) == 0
    assert "overridden" in capsys.readouterr().out


def test_cli_spectrum_with_manifest_refuses_a_golden_whose_bytes_moved(spectra, tmp_path, capsys):
    g = spectra["golden"]
    manifest = {
        "schema": "1.1",
        "outputs": [{
            "path": str(g.relative_to(tmp_path)), "sha256": "0" * 64, "analysis": "spectrum", "input": "x.wav",
            "dtype": "float64", "shape": [2049, 2], "units": "Hz, dB re full-scale sine", "columns": ["frequency", "level"],
        }],
    }
    m = tmp_path / "manifest.yaml"
    m.write_text(yaml.safe_dump(manifest))
    assert cli.main(["spectrum", "--golden", str(g), "--candidate", str(g), "--manifest", str(m)]) == 2
    assert "sha256" in capsys.readouterr().err


def test_cli_pitch_selects_the_limit_by_path(tmp_path, capsys):
    t = 0.025 + 0.01 * np.arange(296)
    f = 220.0 * 2 ** (100 / 1200 * np.sin(2 * np.pi * 6 * t))
    ref = tmp_path / "ref.npy"
    np.save(ref, np.stack([t, f], axis=1))
    dev = tmp_path / "dev.npy"
    np.save(dev, np.stack([t, f * 2 ** (12 / 1200)], axis=1))     # +12 cents everywhere
    assert cli.main(["pitch", "--golden", str(ref), "--candidate", str(dev), "--path", "injection"]) == 1
    assert "F0_INJECTION_MEDIAN_ABS_CENTS = 5.0" in capsys.readouterr().out
    assert cli.main(["pitch", "--golden", str(ref), "--candidate", str(dev), "--path", "acoustic"]) == 0
    assert "F0_ACOUSTIC_MEDIAN_ABS_CENTS = 20.0" in capsys.readouterr().out
    half = tmp_path / "half.npy"
    fh = f.copy()
    fh[::2] = 0.0                                                  # exact pitch on half the frames: VR = 50 %
    np.save(half, np.stack([t, fh], axis=1))
    assert cli.main(["pitch", "--golden", str(ref), "--candidate", str(half), "--path", "acoustic"]) == 1
    assert "VOICING_RECALL_MIN_PERCENT = 90.0" in capsys.readouterr().out
    assert cli.main(["pitch", "--golden", str(ref), "--candidate", str(half), "--path", "acoustic", "--vr-min", "0.4"]) == 0
    assert "voicing limits overridden" in capsys.readouterr().out


def test_cli_window_against_manifest_and_against_a_bare_digest(tmp_path, capsys):
    table = windows.window_table([0.5, 0.5], 4096)
    raw = tmp_path / "hann_4096.f32"
    raw.write_bytes(table.tobytes())
    digest = windows.table_sha256(table)
    m = tmp_path / "manifest.yaml"
    m.write_text(yaml.safe_dump({"schema": "1.1", "windows": [{"family": "hann", "n": 4096, "coefficients": [0.5, 0.5], "sha256": digest}]}))
    assert cli.main(["window", "--raw", str(raw), "--manifest", str(m), "--family", "hann", "--n", "4096"]) == 0
    assert cli.main(["window", "--raw", str(raw), "--manifest", str(m), "--family", "hann", "--n", "8192"]) == 2
    assert cli.main(["window", "--raw", str(raw), "--sha256", digest]) == 0
    assert cli.main(["window", "--raw", str(raw), "--sha256", "0" * 64]) == 1
    capsys.readouterr()


def test_cli_tolerances_prints_every_constant(capsys):
    assert cli.main(["tolerances"]) == 0
    out = capsys.readouterr().out
    assert "SPECTRUM_ATOL_DB" in out and "docs/validation/golden-files.md" in out
