# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""`/api/health` and `/api/version`, by hazard (`spectral_host.web.routes.meta`).

`/api/version` is the provenance route, and its two hazards are both about what
it must NOT do:

  * **Importing an optional dependency to report it.** On a machine with the
    `separate` extra, `import torch` costs seconds and probes CUDA; a status
    route that pays that is a status route that times out. `installed_extras()`
    uses `importlib.util.find_spec` only, and the test asserts the MECHANISM —
    `"torch" not in sys.modules` after the call — rather than the intention.
  * **Shelling out for a version.** No `git describe`: a served build may be an
    installed wheel with no checkout, and a subprocess on a status route is a
    hang waiting for a filesystem. Asserted by booby-trapping
    `subprocess.run`/`Popen`.

And one thing it must do: report the **pinned parselmouth and the Praat it
bundles**. That pair is the provenance of every golden file this project
measures against (`host/README.md`: "the pin IS the Praat version"), so it is
the one fact worth an import on this route.

Run: `uv run --project host pytest -q host/tests/test_web_meta.py`
"""

from __future__ import annotations

import subprocess
import sys

import parselmouth

from spectral_host import __version__
from spectral_host.web import extras


def test_health_is_200_and_says_nothing_else(web_client):
    """Liveness only: it must not depend on the presets or on the front end being built."""
    resp = web_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_version_reports_the_pinned_parselmouth_and_the_praat_it_bundles(web_client):
    """host/pyproject.toml pins `praat-parselmouth==0.4.7`; 0.4.x bundles Praat 6.1.38 (2021-01-02)."""
    body = web_client.get("/api/version").json()
    assert body["version"] == __version__
    assert body["packages"]["praat-parselmouth"] == parselmouth.VERSION
    assert body["praat"] == parselmouth.PRAAT_VERSION
    # numpy and scipy are here because ADR 0009 rule I5 checks those same two
    # names against a golden manifest's `generator` block; a drift is readable
    # off this route without opening the YAML.
    assert set(body["packages"]) >= {"superspectral-host", "numpy", "scipy", "fastapi"}


def test_version_reports_the_extras_it_can_see(web_client):
    """The report is the `find_spec` probe, not a guess: every declared group appears with a boolean."""
    body = web_client.get("/api/version").json()
    assert set(body["extras"]) == set(extras.EXTRAS)
    assert body["extras"] == extras.installed_extras()


def test_version_does_not_import_torch(web_client):
    """A regression sentinel for the day the `separate` extra IS installed here — not the mechanism test.

    On a machine without torch, `"torch" not in sys.modules` holds for ANY
    implementation: `find_spec` and `import_module` alike leave an absent module
    out of `sys.modules`. Verified by mutation (2026-08-22): replacing
    `find_spec` with `importlib.import_module` in `extras.module_available`
    left the whole 419-test suite green. The assertion that actually holds the
    mechanism is `test_the_extras_probe_never_executes_the_module_it_reports_on`
    below, which plants a module that is importable and explodes on import.
    """
    assert "torch" not in sys.modules, "something imported torch before this test ran"
    web_client.get("/api/version")
    assert "torch" not in sys.modules
    assert "librosa" not in sys.modules
    assert "demucs" not in sys.modules


def test_the_extras_probe_never_executes_the_module_it_reports_on(web_client, tmp_path, monkeypatch):
    """The MECHANISM: `find_spec` locates a module without running it, and `/api/version` reports it as present.

    The canary is a real, importable module whose body raises. `find_spec`
    finds its spec and executes nothing, so the probe answers True and
    `sys.modules` stays clean; an implementation that imported to decide would
    raise out of `installed_extras()` and fail this test — which is exactly
    what the torch assertion above cannot do in an environment where torch is
    not installed.
    """
    name = "spectral_extras_probe_canary"
    (tmp_path / (name + ".py")).write_text(
        "raise AssertionError('extras probed by IMPORT, not by find_spec')\n", encoding="utf-8"
    )
    # `monkeypatch.syspath_prepend` is NOT used: it calls
    # `importlib.invalidate_caches()`, which raises `TypeError:
    # MetadataPathFinder.invalidate_caches() missing 1 required positional
    # argument` inside the `_virtualenv._Finder` shim this venv installs on
    # `sys.meta_path`. Prepending directly needs no invalidation — `tmp_path`
    # is a fresh directory, so no `FileFinder` has cached a listing of it.
    monkeypatch.setattr(sys, "path", [str(tmp_path), *sys.path])
    monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setitem(
        extras.EXTRAS,
        "canary",
        extras.Extra(name="canary", modules=(name,), purpose="the probe mechanism test", lands_at="W0"),
    )

    assert extras.module_available(name) is True, "the canary must be findable, or this test proves nothing"
    assert name not in sys.modules

    assert extras.installed_extras()["canary"] is True
    assert name not in sys.modules

    body = web_client.get("/api/version").json()
    assert body["extras"]["canary"] is True
    assert name not in sys.modules, "/api/version executed the module it was only asked to report on"


def test_version_does_not_shell_out(web_client, monkeypatch):
    """No `git describe`, no subprocess of any kind — a served build may have no checkout above it."""

    def explode(*args, **kwargs):  # pragma: no cover - the point is that it is NOT reached
        raise AssertionError("/api/version spawned a subprocess: %r" % (args,))

    monkeypatch.setattr(subprocess, "run", explode)
    monkeypatch.setattr(subprocess, "Popen", explode)
    monkeypatch.setattr(subprocess, "check_output", explode)
    assert web_client.get("/api/version").status_code == 200


def test_a_missing_distribution_is_omitted_rather_than_guessed(web_client, monkeypatch):
    """A version nobody can read is left out; an invented one would be worse than absent."""
    import importlib.metadata

    real = importlib.metadata.version

    def only_some(name: str) -> str:
        if name == "scipy":
            raise importlib.metadata.PackageNotFoundError(name)
        return real(name)

    monkeypatch.setattr(importlib.metadata, "version", only_some)
    body = web_client.get("/api/version").json()
    assert "scipy" not in body["packages"]
    assert "numpy" in body["packages"]


def test_the_extras_probe_refuses_a_dotted_name():
    """`find_spec("a.b")` imports `a` — the very import this module exists to avoid, so it is a ValueError."""
    import pytest

    with pytest.raises(ValueError, match="dotted name"):
        extras.module_available("numpy.linalg")


def test_a_missing_extra_names_the_exact_install_line():
    """The 501 body and the CLI's exit-2 message both end in a command the reader can paste."""
    missing = extras.missing_modules("separate")
    assert missing, "this environment must not have the W4 `separate` extra installed"
    try:
        extras.require_extra("separate")
    except extras.ExtraMissing as exc:
        assert exc.extra == "separate"
        assert exc.install_hint == "uv sync --project host --extra separate"
        assert exc.install_hint in str(exc)
    else:  # pragma: no cover
        raise AssertionError("require_extra did not raise for an absent extra")
