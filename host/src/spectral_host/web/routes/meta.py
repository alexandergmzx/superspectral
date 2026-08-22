# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""`GET /api/health` and `GET /api/version` — liveness, and the pin chain of the serving process.

`/api/health` says the process is answering and nothing else. It does not touch
the presets directory or the front-end bundle: a health check that fails
because `npm run build` has not been run would be a health check nobody trusts.

`/api/version` is the provenance route, and it is built out of two deliberate
refusals:

  * **It never shells out.** No `git describe`, no `subprocess`. A served build
    may be an installed wheel with no checkout above it, and a subprocess on a
    status route is a hang waiting for a slow or absent filesystem. Versions
    come from `importlib.metadata`, which reads the installed distributions'
    own metadata.
  * **It never imports an optional dependency.** Which extras are installed is
    answered by `extras.installed_extras()` — `importlib.util.find_spec` only.
    `host/tests/test_web_meta.py` asserts `"torch" not in sys.modules` after a
    call, because a status route that costs a torch import (and its CUDA
    probing) is a status route that times out on the machine that has the
    `separate` extra.

`parselmouth` IS imported, and that is the one import worth its cost:
`parselmouth.PRAAT_VERSION` is the bundled Praat, and the bundled Praat is the
provenance of every golden file this project measures against
(`host/README.md`: "the pin IS the Praat version"). It is imported inside the
handler, not at module import, so a broken parselmouth cannot stop the
application from starting and serving `/api/presets`.
"""

from __future__ import annotations

import importlib.metadata
import platform

from fastapi import APIRouter

from spectral_host import __version__
from spectral_host.web import extras
from spectral_host.web.models import Health, Version

router = APIRouter()

#: The `/api` contract version. `(prov.)` at "0" while track W is in flight:
#: no consumer outside this repository exists, so nothing is promised by it.
API_CONTRACT_VERSION = "0"

#: Distributions reported by `/api/version`, in dependency order: this package,
#: the server, then the numerics whose versions a golden manifest pins
#: (ADR 0009 rule I5 checks numpy and scipy against the manifest — the same two
#: names, so a mismatch can be read off this route without opening the YAML).
REPORTED_DISTRIBUTIONS: tuple[str, ...] = (
    "superspectral-host",
    "fastapi",
    "starlette",
    "uvicorn",
    "pydantic",
    "numpy",
    "scipy",
    "praat-parselmouth",
    "pyyaml",
    "jsonschema",
)


def installed_versions() -> dict[str, str]:
    """`{distribution: version}` for the reported set; a distribution that is absent is omitted, never guessed."""
    found: dict[str, str] = {}
    for name in REPORTED_DISTRIBUTIONS:
        try:
            found[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return found


def bundled_praat_version() -> str | None:
    """`parselmouth.PRAAT_VERSION`, or None if parselmouth cannot be imported or does not carry it.

    None is a fact ("this process cannot tell you"), not a default — the
    alternative would be a version string nobody measured.
    """
    try:
        import parselmouth
    except Exception:  # pragma: no cover - a broken install, not a state under test
        return None
    version = getattr(parselmouth, "PRAAT_VERSION", None)
    return str(version) if version is not None else None


@router.get("/health", response_model=Health, summary="Liveness only")
def health() -> Health:
    return Health(status="ok")


@router.get("/version", response_model=Version, summary="The pin chain of the serving process")
def version() -> Version:
    return Version(
        version=__version__,
        api=API_CONTRACT_VERSION,
        python=platform.python_version(),
        packages=installed_versions(),
        praat=bundled_praat_version(),
        extras=extras.installed_extras(),
    )


__all__ = ["API_CONTRACT_VERSION", "REPORTED_DISTRIBUTIONS", "bundled_praat_version", "installed_versions", "router"]
