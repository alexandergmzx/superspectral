# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional dependencies, probed without importing them — the 501 of `/analyze` and `/separate`.

A default `uv sync` must stay installable without torch (host/README.md,
"Extras keep the heavy dependencies out of the default install"), so three
groups of the host's dependencies are optional: `capture` (the live mode of
`spectral-web peak`), `analyze` and `separate` (W4). Code that needs one calls
`require_extra()` and gets `ExtraMissing` — which `spectral_host.web.app` maps
to **501 Not Implemented** with the install line in the body — instead of an
`ImportError` traceback three frames deep.

**Probed by `importlib.util.find_spec`, never by `import`.** The distinction is
the whole point of this module: `GET /api/version` reports which extras are
installed, and if it learned that by importing, a machine with `separate`
installed would pay a multi-second torch import (and its CUDA probing) to
answer a status route. `host/tests/test_web_meta.py` asserts `"torch" not in
sys.modules` after `/api/version` — the mechanism, not the intent, is what is
tested. `find_spec` reads the import system's finders and stops at the spec; it
executes no module code.

One caveat it does not remove: `find_spec` imports the *parent* package of a
dotted name (that is how the import protocol locates a submodule). Every name
here is therefore top-level, and a dotted name would be a bug, not a
convenience — hence `_check_top_level`.

`installed_extras()` returns the mapping the version route serves:
`{"capture": True, "analyze": False, "separate": False}`. It is a *report*, not
a gate; `require_extra` is the gate.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass


@dataclass(frozen=True)
class Extra:
    """One optional-dependency group of `host/pyproject.toml`."""

    #: The `[project.optional-dependencies]` key — what `--extra` takes.
    name: str
    #: Top-level module names that must all be importable for the group to work.
    modules: tuple[str, ...]
    #: What the group buys, for the 501 body.
    purpose: str
    #: Roadmap milestone the group lands at (W0 today, W4 for the heavy two).
    lands_at: str

    @property
    def install_hint(self) -> str:
        """The exact command that installs this group — printed by the CLI and by the 501 body."""
        return "uv sync --project host --extra %s" % self.name


#: The optional-dependency groups, in the order host/pyproject.toml declares
#: them. `analyze` and `separate` are listed here BEFORE they exist in
#: pyproject.toml on purpose: the roadmap's W4 adds the packages, and until
#: then the routes that need them must answer 501 with a hint that names a real
#: extra rather than 500 with an ImportError (ADR 0021 consequence: "/separate
#: is exercised through its 501 path in CI").
EXTRAS: dict[str, Extra] = {
    "capture": Extra(
        name="capture",
        modules=("sounddevice",),
        purpose="live audio capture from this machine's microphone (`spectral-web peak` without --wav)",
        lands_at="W0",
    ),
    "analyze": Extra(
        name="analyze",
        modules=("librosa",),
        purpose="pYIN, DTW and LTAS behind /api/analyze",
        lands_at="W4",
    ),
    "separate": Extra(
        name="separate",
        modules=("demucs", "torch"),
        purpose="Demucs htdemucs vocals separation behind /api/separate",
        lands_at="W4",
    ),
}


class ExtraMissing(Exception):
    """An optional-dependency group this build does not have. Mapped to HTTP 501 and to CLI exit 2."""

    def __init__(self, extra: str, missing: tuple[str, ...] = (), install_hint: str | None = None) -> None:
        spec = EXTRAS.get(extra)
        self.extra = extra
        self.missing = tuple(missing)
        self.install_hint = install_hint or (spec.install_hint if spec else "uv sync --project host --extra %s" % extra)
        purpose = spec.purpose if spec else "this feature"
        missing_text = ", ".join(self.missing) if self.missing else "its packages"
        super().__init__(
            "the '%s' extra is not installed (%s not importable): %s needs it. Install with: %s"
            % (extra, missing_text, purpose, self.install_hint)
        )
        self.message = str(self)


def _check_top_level(module: str) -> None:
    if "." in module:
        raise ValueError(
            "%r is a dotted name: find_spec() imports the parent package to locate a submodule, which is "
            "exactly the import this module exists to avoid. Probe the top-level package instead." % (module,)
        )


def module_available(module: str) -> bool:
    """True when `module` can be imported, established WITHOUT importing it.

    `find_spec` raises `ModuleNotFoundError` when a *parent* is missing and
    `ValueError` for a module already in `sys.modules` with `__spec__ = None`;
    both mean "not usable from here" and are answered False rather than raised,
    because this function's only caller is a report or a gate.
    """
    _check_top_level(module)
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):  # ModuleNotFoundError is an ImportError
        return False


def missing_modules(name: str) -> tuple[str, ...]:
    """The modules of extra `name` that are not importable, in declaration order."""
    try:
        spec = EXTRAS[name]
    except KeyError:
        raise ValueError("unknown extra %r; known: %s" % (name, sorted(EXTRAS))) from None
    return tuple(m for m in spec.modules if not module_available(m))


def is_installed(name: str) -> bool:
    """True when every module of extra `name` is importable."""
    return not missing_modules(name)


def require_extra(name: str) -> None:
    """Raise `ExtraMissing` unless every module of extra `name` is importable. Imports nothing."""
    missing = missing_modules(name)
    if missing:
        raise ExtraMissing(name, missing)


def installed_extras() -> dict[str, bool]:
    """`{extra: installed}` for every group in `EXTRAS` — what `GET /api/version` reports."""
    return {name: is_installed(name) for name in EXTRAS}


__all__ = [
    "EXTRAS",
    "Extra",
    "ExtraMissing",
    "installed_extras",
    "is_installed",
    "missing_modules",
    "module_available",
    "require_extra",
]
