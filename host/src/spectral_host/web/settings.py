# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""Where the web application reads from, where it writes to, and the two binds it refuses.

`Settings` is frozen: it is built once, on the command line or in a fixture,
handed to `create_app()`, and stored on `app.state` — a request never changes
it. `validate()` is separate from construction so that a test can build an
invalid one and assert the refusal.

The two refusals are both ADR 0021 decision 8:

  * **A data directory inside the repository is refused.** Uploads, separated
    stems, Demucs weights and ingested takes are *data*: hundreds of megabytes
    of it, never committed, and the failure mode of a default that landed in
    the checkout is a `git status` nobody can read and a model file in a
    commit. The check walks up from the resolved `data_dir` looking for
    `CLAUDE.md` — the same marker `host/tests/conftest.py::find_repo_root`
    uses, chosen because it exists exactly once, at the root.
  * **A non-loopback bind without TLS is refused** unless `allow_insecure_lan`
    is set explicitly. `navigator.mediaDevices` is `undefined` on an insecure
    origin that is not `localhost`, so an unencrypted LAN bind cannot serve the
    live path anyway; refusing it makes that a startup error with a mkcert
    recipe rather than a browser mystery on the phone. The escape hatch exists
    for serving the *offline* pane over a trusted network and has to be typed.

Defaults. `data_dir` is `$XDG_DATA_HOME/superspectral` when `XDG_DATA_HOME` is
set, else `~/.local/share/superspectral` (`(prov.)`, ADR 0021 decision 8).
`presets_dir`, `golden_dir` and `dist_dir` come from the repository root when
this package is running inside a checkout, and from `data_dir` when it is not —
an installed copy with no checkout has no `protocols/presets/`, and saying so
at `validate()` beats a 404 per preset.

`max_upload_mb` is 256 `(prov.)` — nobody has measured what a take weighs;
the owner sets the real number when `take-format.md` exists.

`cross_origin_isolation` defaults **False**. Cross-origin isolation (COOP +
COEP) is what `SharedArrayBuffer` needs, and the W1 design does not use one:
the AudioWorklet hands frames to the Worker by `MessagePort` transfer. The
flag exists so that turning the two headers on is a command-line change and
not a code change, should a W1 profile ever want the shared-memory ring.
"""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field, replace
from pathlib import Path

#: The repository-root marker, shared with `host/tests/conftest.py`.
REPO_MARKER = "CLAUDE.md"

#: The application name, used for the XDG data directory.
APP_NAME = "superspectral"

DEFAULT_HOST = "127.0.0.1"

#: 8000, because `host/web/vite.config.ts` (committed, W0-FE) proxies /api to
#: 127.0.0.1:8000 in `npm run dev`. Two files have to agree on this number and
#: only one of them is read by a browser, so the server moves to the front end
#: rather than the other way round.
DEFAULT_PORT = 8000

#: `(prov.)` — owner's to set when the take format exists (ADR 0021 decision 8).
DEFAULT_MAX_UPLOAD_MB = 256

#: Host strings that are loopback without being IP literals.
LOOPBACK_NAMES = frozenset({"localhost", "localhost.localdomain"})


class SettingsError(ValueError):
    """A configuration this server refuses to start with."""


def find_repo_root(start: Path | None = None) -> Path | None:
    """The directory holding `CLAUDE.md` at or above `start`, or None.

    Tried in order: `start` (default, the working directory) and then this
    file's own location. The working directory comes first because that is
    what a developer means by "the checkout" when running `spectral-web serve`
    from it; the package location is the fallback for an editable install whose
    working directory is elsewhere. A non-editable install in `site-packages`
    finds neither, and every repository-derived default then falls back to
    `data_dir` — which `validate()` reports as a missing presets directory
    rather than as an empty list of presets.
    """
    candidates = [start if start is not None else Path.cwd(), Path(__file__).resolve().parent]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:  # pragma: no cover - unreadable cwd
            continue
        for directory in (resolved, *resolved.parents):
            if (directory / REPO_MARKER).is_file():
                return directory
    return None


def default_data_dir() -> Path:
    """`$XDG_DATA_HOME/superspectral`, else `~/.local/share/superspectral` (ADR 0021 decision 8)."""
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / APP_NAME


def _repo_relative(*parts: str, fallback: str) -> Path:
    root = find_repo_root()
    if root is not None:
        return root.joinpath(*parts)
    return default_data_dir() / fallback


def default_presets_dir() -> Path:
    """`protocols/presets/` — the six presets, the single source of truth (ADR 0021 decision 7)."""
    return _repo_relative("protocols", "presets", fallback="presets")


def default_golden_dir() -> Path:
    """`host/golden/` — the committed golden sets W1's `/api/golden` will serve."""
    return _repo_relative("host", "golden", fallback="golden")


def default_dist_dir() -> Path:
    """`host/web/dist/` — what `npm run build` writes; absent until it has been run."""
    return _repo_relative("host", "web", "dist", fallback="web-dist")


def is_loopback(host: str) -> bool:
    """True for `localhost` and for any address in a loopback network; False for `0.0.0.0`, `::` and a LAN address.

    An empty host, a hostname that is not a loopback name, and any non-loopback
    literal are all False — the conservative reading, because the failure this
    guards is "the analyzer was reachable on the LAN without TLS".
    """
    name = host.strip().strip("[]").lower()
    if not name:
        return False
    if name in LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


def is_inside(path: Path, directory: Path) -> bool:
    """True when `path` resolves at or below `directory` (both resolved first)."""
    try:
        return path.resolve() == directory.resolve() or directory.resolve() in path.resolve().parents
    except OSError:  # pragma: no cover - unresolvable path
        return False


@dataclass(frozen=True)
class Settings:
    """Everything the application reads from the outside world, resolved once.

    Frozen, so `app.state.settings` cannot drift between requests; use
    `replace(settings, ...)` (re-exported here) to derive a variant in a test.
    """

    data_dir: Path = field(default_factory=default_data_dir)
    presets_dir: Path = field(default_factory=default_presets_dir)
    golden_dir: Path = field(default_factory=default_golden_dir)
    dist_dir: Path = field(default_factory=default_dist_dir)
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    ssl_certfile: Path | None = None
    ssl_keyfile: Path | None = None
    max_upload_mb: int = DEFAULT_MAX_UPLOAD_MB
    cross_origin_isolation: bool = False
    allow_insecure_lan: bool = False

    @property
    def tls(self) -> bool:
        """True when both TLS files are configured — the mkcert pair of ADR 0021 decision 8."""
        return self.ssl_certfile is not None and self.ssl_keyfile is not None

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb) * 1024 * 1024

    def validate(self) -> Settings:
        """Refuse a configuration that cannot be served; return self so a caller can chain.

        Raises `SettingsError` with the reason and, where there is one, the fix.
        """
        repo_root = find_repo_root()
        if repo_root is not None and is_inside(self.data_dir, repo_root):
            raise SettingsError(
                "data_dir %s is inside the repository (%s): uploads, separated stems and model weights "
                "are data and are never committed (ADR 0021 decision 8). Pass --data-dir with a path "
                "outside the checkout, or leave it at the default %s."
                % (self.data_dir, repo_root, default_data_dir())
            )
        if not self.presets_dir.is_dir():
            raise SettingsError(
                "presets_dir %s is not a directory: the six presets are the single source of truth and are "
                "served from protocols/presets/ (ADR 0021 decision 7). Pass --presets-dir, or run from a checkout."
                % (self.presets_dir,)
            )
        if (self.ssl_certfile is None) != (self.ssl_keyfile is None):
            raise SettingsError("TLS needs both --ssl-certfile and --ssl-keyfile, or neither")
        for label, path in (("ssl_certfile", self.ssl_certfile), ("ssl_keyfile", self.ssl_keyfile)):
            if path is not None and not path.is_file():
                raise SettingsError("%s %s does not exist" % (label, path))
        if not is_loopback(self.host) and not self.tls and not self.allow_insecure_lan:
            raise SettingsError(
                "refusing to bind %s without TLS: navigator.mediaDevices is undefined on an insecure origin "
                "that is not localhost, so the live path could not start there anyway (ADR 0021 decision 8). "
                "Mint a certificate — `mkcert <lan-ip> localhost 127.0.0.1 ::1` — and pass --ssl-certfile / "
                "--ssl-keyfile, or pass --allow-insecure-lan for the offline pane on a trusted network."
                % (self.host,)
            )
        if self.max_upload_mb <= 0:
            raise SettingsError("max_upload_mb must be positive, got %r" % (self.max_upload_mb,))
        if not 1 <= int(self.port) <= 65535:
            raise SettingsError("port must be 1 … 65535, got %r" % (self.port,))
        return self

    def ensure_data_dir(self) -> Path:
        """Create `data_dir` (parents included) and return it. Called once, from the lifespan."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir


__all__ = [
    "APP_NAME",
    "DEFAULT_HOST",
    "DEFAULT_MAX_UPLOAD_MB",
    "DEFAULT_PORT",
    "LOOPBACK_NAMES",
    "REPO_MARKER",
    "Settings",
    "SettingsError",
    "default_data_dir",
    "default_dist_dir",
    "default_golden_dir",
    "default_presets_dir",
    "find_repo_root",
    "is_inside",
    "is_loopback",
    "replace",
]
