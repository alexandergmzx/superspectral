# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""`create_app(settings)` — the FastAPI application, and the four rules that hold for every request.

A **factory**, not a module-level singleton: a test builds an application over
a temporary presets directory, the CLI builds one over the command line's
`Settings`, and neither can disturb the other. `uvicorn
spectral_host.web.app:app` still works (host/README.md documents that string) —
`__getattr__` below builds one on first attribute access, so importing this
module costs nothing and cannot fail on a machine with no checkout.

  1. **One error shape, everywhere.** `{"error": {"code", "message",
     "details"}}` — from a route, from a validation failure, and from the 404
     that `StaticFiles` raises three layers down. `host/web/src/api/client.ts`
     decodes failures in one function; the moment a second shape exists, that
     function starts guessing.

  2. **A tampered preset fails LOUDLY.** `PresetRejected` maps to **500** with
     the loader's rule number in `details.rule` AND in the message. Not 404
     (the file is there), not a filtered-out row (roadmap W0: "fails loudly
     with rule V0 ... rather than being served"). 500 is the honest status: the
     server holds a file it cannot vouch for.

  3. **A write carries `X-Requested-With: spectral-web`.** A custom request
     header cannot be set by a cross-origin form, image or link — only by
     script that has already passed CORS — so requiring one on POST/PUT/PATCH/
     DELETE stops a page the singer happens to have open from driving this
     server, with no token round trip and no session. The server binds
     loopback by default and, on the LAN, TLS (ADR 0021 decision 8); this is
     the third layer, and it is the one that survives someone typing
     `--allow-insecure-lan`. W0 has no write route yet — the middleware lands
     with the seam, not after the first upload endpoint exists.

  4. **The static mount is last.** It matches `/` and therefore everything;
     every `/api` route must be registered before it. The order is fixed here,
     in one function, rather than trusted to whoever adds the next router.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse, Response

from spectral_host import __version__
from spectral_host.presets import PresetRejected
from spectral_host.wavio import UnsupportedWav
from spectral_host.web.extras import ExtraMissing
from spectral_host.web.models import error_payload
from spectral_host.web.routes import API_PREFIX, api_router
from spectral_host.web.settings import Settings
from spectral_host.web.static import mount_frontend

#: The marker header of rule 3. Lower-case: `Headers` lookup is case-insensitive,
#: and comparing a lower-cased value avoids a second normalisation at the call site.
REQUESTED_WITH_HEADER = "x-requested-with"
REQUESTED_WITH_VALUE = "spectral-web"

#: The methods that require it. GET and HEAD are safe by definition; OPTIONS is
#: the CORS preflight, which cannot carry a custom header of its own.
UNSAFE_METHODS: frozenset[str] = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: Status → the `code` used when an `HTTPException` was raised without our envelope
#: (Starlette raises bare ones from inside `StaticFiles`).
_STATUS_CODES: dict[int, str] = {400: "bad_request", 403: "forbidden", 404: "not_found", 405: "method_not_allowed"}

TITLE = "Super Spectral — host web application"
DESCRIPTION = (
    "The founding research document's analyzer, GPL-3.0-or-later (ADR 0021). The host's user interface and a "
    "second digital-injection-path instrument — never a view of the watch, and no number it produces may be "
    "quoted for any bound of proposal §1."
)


def _json_error(status: int, code: str, message: str, **details: object) -> JSONResponse:
    return JSONResponse(status_code=status, content=error_payload(code, message, **details))


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application over `settings` (validated defaults when omitted).

    `settings` is stored on `app.state` twice — at construction and again in
    the lifespan. The first assignment is what makes a route work under a bare
    `TestClient(app)` (no lifespan); the second is the one that matters in
    production, where it is paired with `ensure_data_dir()`. They are the same
    object, so there is nothing to keep in step.
    """
    resolved = Settings().validate() if settings is None else settings

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.settings = resolved
        # Created here, not at import and not per request: the data directory
        # is where uploads and (at W4) model weights land, and a server that
        # cannot create it should fail at startup rather than at the first POST.
        resolved.ensure_data_dir()
        yield

    app = FastAPI(
        title=TITLE,
        description=DESCRIPTION,
        version=__version__,
        lifespan=lifespan,
        # Rule 1 reaches FastAPI's own 422 too; see the handler below.
        responses={422: {"description": "Request validation failed; body is the standard error envelope."}},
    )
    app.state.settings = resolved

    @app.middleware("http")
    async def require_requested_with(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Rule 3 — a state-changing method without the marker header is 403, before any handler runs."""
        if request.method.upper() in UNSAFE_METHODS:
            marker = request.headers.get(REQUESTED_WITH_HEADER, "").strip().lower()
            if marker != REQUESTED_WITH_VALUE:
                return _json_error(
                    403,
                    "requested_with_required",
                    "%s %s requires the header %s: %s — a custom header cannot be set by a cross-origin form, "
                    "which is what makes its presence proof the request came from this application's own script."
                    % (request.method.upper(), request.url.path, "X-Requested-With", REQUESTED_WITH_VALUE),
                    header="X-Requested-With",
                    expected=REQUESTED_WITH_VALUE,
                )
        return await call_next(request)

    @app.exception_handler(PresetRejected)
    async def preset_rejected_handler(request: Request, exc: PresetRejected) -> Response:
        """Rule 2 — 500, with the loader's rule number where a machine can read it."""
        details: dict[str, object] = {"rule": exc.rule}
        preset_id = getattr(exc, "preset_id", None)
        preset_path = getattr(exc, "preset_path", None)
        if preset_id is not None:
            details["id"] = preset_id
        if preset_path is not None:
            details["path"] = preset_path
        return _json_error(
            500,
            "preset_rejected",
            "%s: %s%s"
            % (exc.rule, exc.message, "" if preset_path is None else " (%s)" % preset_path),
            **details,
        )

    @app.exception_handler(UnsupportedWav)
    async def unsupported_wav_handler(request: Request, exc: UnsupportedWav) -> Response:
        """415 — the reader refuses anything but 16-bit PCM, and never converts (wavio's rule)."""
        return _json_error(
            415,
            "unsupported_wav",
            "%s — only 16-bit PCM WAV is read, and no conversion is performed (ADR 0006 D3: the int16 seam is "
            "applied exactly once)" % (exc,),
        )

    @app.exception_handler(ExtraMissing)
    async def extra_missing_handler(request: Request, exc: ExtraMissing) -> Response:
        """501 — the route exists, this build cannot run it, and the body says what to install."""
        return _json_error(
            501,
            "extra_missing",
            str(exc),
            extra=exc.extra,
            missing=list(exc.missing),
            install=exc.install_hint,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> Response:
        """Rule 1 — envelope in, envelope out; a bare `HTTPException` is wrapped rather than leaked."""
        detail = exc.detail
        if isinstance(detail, dict) and isinstance(detail.get("error"), dict):
            return JSONResponse(status_code=exc.status_code, content=detail, headers=exc.headers)
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(code, str(detail), status=exc.status_code),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> Response:
        """FastAPI's 422, in the one shape. `errors` is pydantic's list, passed through, not summarised."""
        return _json_error(
            422,
            "validation_error",
            "request validation failed",
            errors=[{k: v for k, v in err.items() if k != "ctx"} for err in exc.errors()],
        )

    app.include_router(api_router, prefix=API_PREFIX)
    # Rule 4: last, because a mount at "/" matches everything after it.
    mount_frontend(app, resolved)
    return app


def __getattr__(name: str) -> object:
    """`app` on first access — so `uvicorn spectral_host.web.app:app` resolves without a module-level singleton.

    PEP 562. Importing this module (which every test and the CLI do) must not
    read the environment, resolve a repository root or refuse a configuration;
    building the ASGI application by name is exactly when those things should
    happen.
    """
    if name == "app":
        return create_app()
    raise AttributeError("module %r has no attribute %r" % (__name__, name))


__all__ = ["REQUESTED_WITH_HEADER", "REQUESTED_WITH_VALUE", "UNSAFE_METHODS", "create_app"]
