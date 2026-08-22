# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""Serving `host/web/dist` — the built front end — and the four decisions that mount involves.

`npm run build` writes `host/web/dist/`; uvicorn serves it from the same origin
as `/api`, which is what makes phone-on-LAN one URL and one certificate (ADR
0021 decision 8) instead of a CORS problem.

  1. **`.npy` is typed.** W1's golden suite fetches the committed `.npy` arrays
     over this mount. Python 3.12's `mimetypes` has no entry for `.npy`
     (verified on this machine: `mimetypes.guess_type("x.npy") -> (None, None)`),
     and Starlette's fallback for an unknown type is `text/plain`, which a
     browser may sniff and mangle. It is registered as
     `application/octet-stream` here. `.wasm` (`application/wasm`) and `.mjs`
     (`text/javascript`) are ALREADY known to the same stdlib table — verified
     the same way — so they are asserted, not registered: a shim that silently
     stopped being needed is a shim nobody removes.

  2. **No SPA fallback.** An unknown path is a **404**, never `index.html`.
     A rewrite-everything-to-index mount turns a typo, a stale bookmark and a
     renamed asset into a 200 with an empty page, and it turns `/api/golden`
     (misspelled) into HTML that `client.ts` would try to parse as JSON. This
     application has no client-side router; there is nothing a fallback buys.

  3. **Caching follows the name.** `index.html` is `no-cache` (revalidate every
     load — it is the file that names the current hashed bundle);
     everything under `assets/` — Vite's default `assetsDir`, where every name
     carries a content hash — is `immutable, max-age=31536000`. Anything else
     in `dist/` is `no-cache`, because an unhashed name may be overwritten by
     the next build.

  4. **COOP/COEP only on request.** Cross-origin isolation is what
     `SharedArrayBuffer` needs, and the W1 design does not use one: the
     AudioWorklet transfers frames to the Worker over a `MessagePort`. The two
     headers are therefore **off** by default (`Settings.cross_origin_isolation`),
     because turning them on breaks every cross-origin subresource and would be
     a mystery to debug for a capability nothing uses. The flag exists so that
     a W1 profile that wants the shared-memory ring is a command-line change.

And when `dist/` has not been built, the mount answers **501** in plain text,
naming `npm run build` — never a traceback and never a 404, because "the front
end was never built" and "there is no such page" are different problems and the
first one has a fix the reader can type.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import FastAPI
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Receive, Scope, Send

from spectral_host.web.models import error_payload
from spectral_host.web.settings import Settings

#: Registered by `register_mime_types()` — the stdlib table has no `.npy`.
NPY_MEDIA_TYPE = "application/octet-stream"

#: Asserted, not registered: the stdlib already knows these two.
KNOWN_MEDIA_TYPES: dict[str, str] = {".wasm": "application/wasm", ".mjs": "text/javascript"}

#: Vite's default `build.assetsDir`; every file below it carries a content hash.
ASSETS_DIR = "assets"

#: The one document whose name is not content-addressed.
INDEX_NAME = "index.html"

CACHE_IMMUTABLE = "public, max-age=31536000, immutable"
CACHE_REVALIDATE = "no-cache"

#: The prefix the static layer must never answer for; see `_is_api_path`.
API_PREFIX = "api"

NOT_BUILT_MESSAGE = (
    "501 Not Implemented: the front end has not been built.\n"
    "\n"
    "This server mounts host/web/dist/, and there is nothing at\n"
    "    {dist}\n"
    "\n"
    "Build it (Node 20.19+ / npm; ADR 0021 decision 4 — `npm ci` against the committed lockfile\n"
    "is the only install path):\n"
    "\n"
    "    cd host/web\n"
    "    npm ci --ignore-scripts\n"
    "    npm run build\n"
    "\n"
    "The API is unaffected: /api/health, /api/version and /api/presets answer normally.\n"
)


def register_mime_types() -> None:
    """Type `.npy`; assert the two the stdlib already knows. Idempotent, called once per `create_app`."""
    mimetypes.add_type(NPY_MEDIA_TYPE, ".npy")
    for suffix, expected in KNOWN_MEDIA_TYPES.items():
        actual, _encoding = mimetypes.guess_type("probe" + suffix)
        if actual != expected:  # pragma: no cover - a stdlib regression, not a state this code creates
            mimetypes.add_type(expected, suffix)


def _is_api_path(path: str) -> bool:
    """True for the sub-path of a request the API router should have answered.

    The static layer is mounted at `/`, so it is the LAST route tried and it
    receives every `/api/...` path no route matched. Answering those from here
    — 404 from `StaticFiles`, or worse the 501 page — would make a misspelled
    API route indistinguishable from a missing front end. They are separated
    here and answered as a JSON 404 in the one error shape.
    """
    stripped = path.lstrip("/")
    return stripped == API_PREFIX or stripped.startswith(API_PREFIX + "/")


def _unknown_api_route(path: str) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=error_payload(
            "not_found",
            "no such API route: /%s" % path.lstrip("/"),
            path="/" + path.lstrip("/"),
        ),
    )


def _isolation_headers(response: Response, settings: Settings) -> None:
    if settings.cross_origin_isolation:
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"


class DistStaticFiles(StaticFiles):
    """`host/web/dist` with this project's cache policy, no SPA fallback, and the isolation flag.

    `get_response(path, scope)` is overridden rather than `file_response()`:
    it is the narrower, more stable seam (it sees the relative path as a
    string, before the file is opened), and it is the only place where a
    `/api/...` sub-path can be intercepted before `StaticFiles` decides it is
    a missing file.

    `html=False`: with `html=True` Starlette would also serve `index.html` for
    a *directory* request and hunt for a `404.html`; the first is a second way
    to reach the same document and the second is a fallback by another name.
    `/` is handled explicitly below instead.
    """

    def __init__(self, *, directory: Path, settings: Settings) -> None:
        super().__init__(directory=directory, html=False, check_dir=True)
        self._settings = settings

    async def get_response(self, path: str, scope: Scope) -> Response:
        if _is_api_path(path):
            return _unknown_api_route(path)
        # `.` is what Starlette hands down for the mount root: serve the index,
        # the one document whose URL is not its filename.
        relative = INDEX_NAME if path in ("", ".", "/") else path
        response = await super().get_response(relative, scope)
        self._apply_headers(relative, response)
        return response

    def _apply_headers(self, relative: str, response: Response) -> None:
        name = PurePosixName(relative)
        if name.first == ASSETS_DIR and name.depth > 1:
            response.headers["Cache-Control"] = CACHE_IMMUTABLE
        else:
            response.headers["Cache-Control"] = CACHE_REVALIDATE
        _isolation_headers(response, self._settings)


class PurePosixName:
    """The first path segment and the depth of a mount-relative path, without touching the filesystem.

    `Path()` is deliberately not used: on a URL sub-path it would normalise
    separators and resolve `.`/`..` by platform rules, and the cache policy
    must read the URL the client asked for, not a normalised form of it.
    """

    def __init__(self, relative: str) -> None:
        parts = [p for p in relative.replace("\\", "/").split("/") if p not in ("", ".")]
        self.parts = tuple(parts)

    @property
    def first(self) -> str:
        return self.parts[0] if self.parts else ""

    @property
    def depth(self) -> int:
        return len(self.parts)


class FrontEndNotBuilt:
    """The ASGI app mounted at `/` when `dist/` is absent: 501 plain text, `/api` still a JSON 404.

    Plain text, not HTML: the reader of this page is a developer who has just
    started the server, and a paragraph of markup would be one more thing
    between them and the two commands that fix it.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "") or ""
        if _is_api_path(path):
            response: Response = _unknown_api_route(path)
        else:
            response = PlainTextResponse(
                NOT_BUILT_MESSAGE.format(dist=self._settings.dist_dir),
                status_code=501,
                headers={"Cache-Control": CACHE_REVALIDATE},
            )
            _isolation_headers(response, self._settings)
        await response(scope, receive, send)


def dist_is_built(settings: Settings) -> bool:
    """True when `dist_dir` holds an `index.html` — the file the mount is for."""
    return settings.dist_dir.is_dir() and (settings.dist_dir / INDEX_NAME).is_file()


def mount_frontend(app: FastAPI, settings: Settings) -> None:
    """Mount the built front end at `/`, or the 501 page in its place. Called LAST, after the API router.

    Route order is the mechanism: a mount at `/` matches everything, so every
    `/api` route must already be registered when this runs. `create_app`
    enforces the order by calling this at the end.
    """
    register_mime_types()
    if dist_is_built(settings):
        app.mount("/", DistStaticFiles(directory=settings.dist_dir, settings=settings), name="dist")
    else:
        app.mount("/", FrontEndNotBuilt(settings), name="dist-not-built")


__all__ = [
    "ASSETS_DIR",
    "CACHE_IMMUTABLE",
    "CACHE_REVALIDATE",
    "DistStaticFiles",
    "FrontEndNotBuilt",
    "INDEX_NAME",
    "KNOWN_MEDIA_TYPES",
    "NOT_BUILT_MESSAGE",
    "NPY_MEDIA_TYPE",
    "dist_is_built",
    "mount_frontend",
    "register_mime_types",
]
