# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""The response models of `/api` — pydantic v2, and the ONE error shape.

Every route returns either a model declared here or `ErrorEnvelope`. One error
shape across the whole surface (including a 404 raised inside the static mount)
is what lets `host/web/src/api/client.ts` decode a failure in one function:
the front end reads `error.code` to decide and `error.message` to show, and
never has to guess whether a body is an envelope, FastAPI's `{"detail": ...}`
or a proxy's HTML.

    {"error": {"code": "preset_rejected",
               "message": "V0: file must end with exactly one trailing newline",
               "details": {"rule": "V0", "id": "live_singing"}}}

`code` is a stable machine token; `message` is for a human; `details` is
free-form and additive — a field added there is not a breaking change, which is
why `PresetRejected`'s rule number travels in it as well as in the message.

W0 declares only what W0 serves. W1's `/api/golden`, W4's `/api/analyze` and
`/api/separate` add their own models here; nothing is declared ahead of its
route, because a model with no endpoint is a contract nobody is holding.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    """Base: extra fields are refused on the way in, so a typo is a 422 and not a silently ignored key."""

    model_config = ConfigDict(extra="forbid")


class PresetSummary(ApiModel):
    """One row of `GET /api/presets` — the identity of a preset file, never its contents.

    `sha256` is over the file's BYTES as read (ADR 0010 decision 6, ADR 0021
    decision 7a): the same digest a TAKE_HEADER carries, so a take recorded by
    the watch and a preset listed here can be matched by value. `bytes` is the
    length of that same subject — a digest with no size is a digest whose
    subject nobody can check.

    `url` is where the byte-identical file itself is served, so the front end
    follows a link instead of assembling a path (`host/web/src/api/client.ts`
    is the only file that knows a route, and this keeps it that way).
    """

    id: str = Field(description="Preset id; equals the file stem under protocols/presets/ (rule V1).")
    name: str = Field(description="The preset's own human-readable `name` (ADR 0010 §4.1).")
    sha256: str = Field(description="sha256 of the canonical file's bytes, lowercase hex.")
    bytes: int = Field(ge=0, description="Size of the canonical file, the digest's subject.")
    targets: list[str] = Field(description='`["watch","host"]` or `["host"]`; "host" covers CLI and web app alike.')
    url: str = Field(description="Route serving the byte-identical file, e.g. /api/presets/live_singing.")


class PresetList(ApiModel):
    """`GET /api/presets`. An object, not a bare array: a top-level JSON array has nowhere to grow.

    The front end accepts either shape (`client.ts::getPresets`); this is the
    one the backend actually sends, and `count` exists so a truncated response
    is detectable without counting rows by hand.
    """

    presets: list[PresetSummary]
    count: int = Field(ge=0)


class Version(ApiModel):
    """`GET /api/version` — the pin chain of the process answering the request.

    Deliberately NOT `git describe`: this route never shells out. A served
    build may be an installed wheel with no checkout, and a subprocess on a
    status route is a hang waiting for a slow filesystem. Everything here comes
    from `importlib.metadata` (which reads installed distribution metadata) and
    from `parselmouth.PRAAT_VERSION` — the one import that is worth its cost,
    because the bundled Praat version IS the golden files' provenance
    (host/README.md: "the pin IS the Praat version").

    `api` is the `/api` contract version, `(prov.)` at "0" while W0–W4 are in
    flight: no consumer outside this repository exists yet, so nothing is
    promised by it.
    """

    version: str = Field(description="spectral_host.__version__ of the serving process.")
    api: str = Field(description='Contract version of /api itself. "0" while track W is in flight (prov.).')
    python: str = Field(description="Interpreter version, e.g. 3.12.3.")
    packages: dict[str, str] = Field(description="Installed distribution versions read from importlib.metadata.")
    praat: str | None = Field(description="parselmouth.PRAAT_VERSION — the bundled Praat; null if unreadable.")
    extras: dict[str, bool] = Field(description="Optional-dependency groups, probed by find_spec, never imported.")


class Health(ApiModel):
    """`GET /api/health` — liveness only. Says nothing about the presets or the front end being present."""

    status: str = Field(description='"ok" when the process is serving.')


class ErrorBody(ApiModel):
    """The inside of the envelope. `code` is the stable token; `details` is additive."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(ApiModel):
    """Every non-2xx body this application produces, including those raised inside the static mount."""

    error: ErrorBody


def error_payload(code: str, message: str, **details: Any) -> dict[str, Any]:
    """Build the envelope as a plain dict — what the exception handlers hand to `JSONResponse`."""
    return ErrorEnvelope(error=ErrorBody(code=code, message=message, details=details)).model_dump()


__all__ = [
    "ApiModel",
    "ErrorBody",
    "ErrorEnvelope",
    "Health",
    "PresetList",
    "PresetSummary",
    "Version",
    "error_payload",
]
