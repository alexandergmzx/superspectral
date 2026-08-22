# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""Environment tests: the pins that make every golden file mean something (ADR 0009),
and the licence boundary that makes host/ GPL and nothing else (ADR 0004).

No numerics here — B-U3/B-U4 own those. These tests guard the preconditions:
that the installed Praat is the one the manifests will claim, that no Apache-2.0
package can be reached from the GPL environment, and that the skeleton's own
guards (the `--force-regen` refusal, the repo-root fixture) hold.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import conftest
import spectral_host

#: host/pyproject.toml pins praat-parselmouth exactly, because the pin IS the
#: Praat version: every released 0.4.x bundles Praat 6.1.38 (measured 2026-08-21,
#: ADR 0009 amendment). These two strings are what every golden manifest's
#: generator.parselmouth / generator.praat_bundled must equal.
PINNED_PARSELMOUTH = "0.4.7"
PINNED_PRAAT_BUNDLED = "6.1.38"

#: Apache-2.0 modules that live under python-scripts/ (ADR 0004 item 3: nothing
#: inside host/ imports the rest of the repository). synth_signals and
#: golden_compare are B-U2/B-U8 deliverables; check_presets and doc_ocr exist.
APACHE_MODULES = ("synth_signals", "golden_compare", "check_presets", "doc_ocr")


# --- the pin chain ----------------------------------------------------------


def test_installed_praat_is_the_pinned_bundle():
    """A parselmouth bump silently changes the Praat underneath every golden file."""
    parselmouth = importlib.import_module("parselmouth")
    assert parselmouth.VERSION == PINNED_PARSELMOUTH
    assert parselmouth.PRAAT_VERSION == PINNED_PRAAT_BUNDLED


def test_pinned_parselmouth_matches_the_installed_distribution():
    """`parselmouth.VERSION` and the installed dist must agree, or the lock is not what runs."""
    assert importlib.metadata.version("praat-parselmouth") == PINNED_PARSELMOUTH


def test_package_version_matches_installed_metadata():
    """`spectral_host.__version__` and pyproject `version` drift apart unless something checks."""
    assert spectral_host.__version__ == importlib.metadata.version("superspectral-host")


# --- the licence boundary ---------------------------------------------------


@pytest.mark.parametrize("name", APACHE_MODULES)
def test_no_apache_package_is_importable_from_host(name):
    """If an Apache-2.0 module resolves inside host/.venv, the GPL boundary is a directory in name only."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(name)


def test_python_scripts_is_not_on_sys_path(repo_root):
    """The previous test passes vacuously if python-scripts/ is on sys.path and the modules merely failed to load."""
    python_scripts = (repo_root / "python-scripts").resolve()
    on_path = [p for p in sys.path if p and Path(p).resolve() == python_scripts]
    assert on_path == []


def test_spectral_host_is_imported_from_the_src_layout(repo_root):
    """The package must come from host/src (editable) or host/.venv, never from a stray copy elsewhere."""
    location = Path(spectral_host.__file__).resolve()
    assert (repo_root / "host").resolve() in location.parents


# --- the skeleton's own guards ----------------------------------------------


def test_force_regen_is_refused_before_any_test_collects(monkeypatch):
    """ADR 0009 item 4: the one-command silent refresh is a usage error, not a feature."""
    monkeypatch.setattr(sys, "argv", ["pytest", "--force-regen"])
    fake_config = SimpleNamespace(invocation_params=SimpleNamespace(args=()))
    with pytest.raises(pytest.UsageError, match="ADR 0009"):
        conftest.pytest_configure(fake_config)


def test_force_regen_is_refused_when_passed_programmatically(monkeypatch):
    """pytest.main([...]) bypasses sys.argv; invocation_params must catch it too."""
    monkeypatch.setattr(sys, "argv", ["pytest"])
    fake_config = SimpleNamespace(invocation_params=SimpleNamespace(args=("--force-regen",)))
    with pytest.raises(pytest.UsageError, match="ADR 0009"):
        conftest.pytest_configure(fake_config)


def test_force_regen_guard_lets_an_ordinary_invocation_through(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pytest", "-q"])
    fake_config = SimpleNamespace(invocation_params=SimpleNamespace(args=("-q",)))
    conftest.pytest_configure(fake_config)  # must not raise


def test_repo_root_is_the_directory_holding_claude_md(repo_root):
    assert (repo_root / "CLAUDE.md").is_file()
    assert (repo_root / "host" / "pyproject.toml").is_file()


def test_repo_root_search_fails_loudly_outside_a_checkout(tmp_path):
    """A fixture that silently picked `/` would make every path-relative test pass on nothing."""
    with pytest.raises(RuntimeError, match="CLAUDE.md"):
        conftest.find_repo_root(tmp_path)


def test_tier0_dir_is_under_repo_root_datasets(repo_root, tier0_dir):
    assert tier0_dir == repo_root / "datasets" / "tier0-synthetic"


# --- the console script -----------------------------------------------------


@pytest.mark.parametrize("command", ["t7"])  # verify + env landed with B-U5, generate with B-U6; see test_generate_roundtrip.py
def test_unimplemented_subcommand_exits_2_not_0(command):
    """A CI step wired up before its unit lands must fail as a usage error, never read as 'verified clean'."""
    proc = subprocess.run(
        [sys.executable, "-m", "spectral_host.golden.cli", command],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2, proc.stderr
    assert "not implemented" in proc.stderr
    assert proc.stdout == ""


def test_missing_subcommand_is_a_usage_error():
    proc = subprocess.run(
        [sys.executable, "-m", "spectral_host.golden.cli"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "COMMAND is required" in proc.stderr
