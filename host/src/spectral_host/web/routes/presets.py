# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""`GET /api/presets` and `GET /api/presets/{id}` — the six presets, proved and then served VERBATIM.

ADR 0021 decision 7(a): the presets under `protocols/presets/` are the single
source of truth, the front end never ships a copy, and the bundler never embeds
one. Two properties make that real, and both are load-bearing:

**The bytes are the answer.** `GET /api/presets/{id}` returns the file's bytes
exactly as they are on disk — `path.read_bytes()`, `media_type
application/json`, no parse-and-re-serialise anywhere on the path. Rule V0 has
just proved those bytes ARE the canonical form (preset-schema.md §3), so
re-serialising could only move away from it; and the sha256 that a TAKE_HEADER
carries is over these bytes, so an object round-tripped through `json.dumps`
with different key order or float formatting would hash differently and the
displayed digest would be a lie. The ETag is that same digest.

**A bad preset fails loudly.** Every file goes through
`spectral_host.presets.load_preset` (V0/V1/V8/V9) before anything is served,
and a `PresetRejected` propagates — `create_app`'s handler turns it into a
**500 naming the rule**. It is deliberately not filtered out of the list: the
roadmap's W0 definition of done says a tampered preset "fails loudly with rule
V0 of the loader rather than being served", and a list that silently omitted it
would show five presets and no error, which is the failure this route exists to
make impossible.

**The id is validated before a path is built.** `PRESET_ID` is the schema's own
`^[a-z][a-z0-9_]{2,31}$` (preset-schema.md §4.1). It runs on the raw path
parameter — after URL decoding, so `%2e%2e` is `..` and is refused by the same
expression — and the handler returns 404 without touching the filesystem.
`Path(presets_dir) / preset_id` with an unvalidated id is the classic traversal
(`../../LICENSE`, and `/etc/passwd` for an absolute id, which `/` joining would
happily accept); refusing at the pattern means no path is ever constructed from
untrusted text.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from spectral_host.presets import Preset, PresetRejected, load_preset
from spectral_host.web.models import PresetList, PresetSummary, error_payload
from spectral_host.web.settings import Settings

router = APIRouter()

#: preset-schema.md §4.1: `id` is `^[a-z][a-z0-9_]{2,31}$` and equals the
#: basename (rule V1). Repeated here rather than imported from the loader
#: because it is applied EARLIER than the loader — to a URL path parameter,
#: before a filesystem path exists to load.
PRESET_ID = re.compile(r"^[a-z][a-z0-9_]{2,31}$")

#: The one media type of this route. Never `text/plain`: the body is JSON, and
#: `client.ts::getPresetSource` reads it as text on purpose (the bytes, not a
#: parsed object) — which is a decision about the reader, not about the type.
PRESET_MEDIA_TYPE = "application/json"


def settings_of(request: Request) -> Settings:
    """The frozen `Settings` stored on `app.state` by `create_app` / the lifespan."""
    return request.app.state.settings


def preset_paths(settings: Settings) -> list[Path]:
    """Every `*.json` under `presets_dir`, sorted by name — the list order the interface shows.

    Sorted, not `glob` order: directory iteration order is filesystem-defined,
    and a list whose order changes between machines is a diff nobody can read.
    `README.md` and any other non-`.json` file is simply not matched.
    """
    return sorted(settings.presets_dir.glob("*.json"))


def _annotate(exc: PresetRejected, path: Path) -> PresetRejected:
    """Attach the file the rejection is about, so the 500 handler can name it. Returns the same exception."""
    exc.preset_path = str(path)  # type: ignore[attr-defined]
    exc.preset_id = path.stem  # type: ignore[attr-defined]
    return exc


def summarise(preset: Preset, raw: bytes) -> PresetSummary:
    """One `PresetSummary` from an accepted preset and the bytes it was proved from."""
    doc: dict[str, Any] = preset.doc
    targets = doc.get("targets", [])
    return PresetSummary(
        id=preset.id,
        name=str(doc.get("name", preset.id)),
        sha256=preset.sha256,
        bytes=len(raw),
        targets=[str(t) for t in targets] if isinstance(targets, list) else [],
        url="/api/presets/%s" % preset.id,
    )


def _load(path: Path) -> tuple[Preset, bytes]:
    """Read and prove one preset file; a rejection is annotated with the file and re-raised."""
    raw = path.read_bytes()
    try:
        return load_preset(path), raw
    except PresetRejected as exc:
        raise _annotate(exc, path) from None


@router.get("/presets", response_model=PresetList, summary="The presets, proved by the loader")
def list_presets(request: Request) -> PresetList:
    """Every preset under `presets_dir`, with the sha256 of its bytes. Any rejection fails the whole list."""
    settings = settings_of(request)
    summaries = [summarise(*_load(path)) for path in preset_paths(settings)]
    return PresetList(presets=summaries, count=len(summaries))


@router.get(
    "/presets/{preset_id}",
    response_class=Response,
    summary="The canonical preset file, byte-identical",
    responses={
        200: {"content": {PRESET_MEDIA_TYPE: {}}, "description": "The file's bytes, unmodified."},
        404: {"description": "No such preset id, or an id outside the schema's pattern."},
        500: {"description": "The file exists and the loader rejected it; the body names the rule."},
    },
)
def get_preset(preset_id: str, request: Request) -> Response:
    """The file's BYTES, with `ETag` = their sha256. Proved by `load_preset` first; never re-serialised."""
    if not PRESET_ID.match(preset_id):
        # Before any path is built (see the module docstring): a traversal
        # attempt and a typo get the same answer, and neither reaches the disk.
        raise HTTPException(
            status_code=404,
            detail=error_payload(
                "invalid_preset_id",
                "preset id %r is not %s (preset-schema.md §4.1)" % (preset_id, PRESET_ID.pattern),
                id=preset_id,
                pattern=PRESET_ID.pattern,
            ),
        )
    settings = settings_of(request)
    path = settings.presets_dir / ("%s.json" % preset_id)
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=error_payload("unknown_preset", "no preset %r" % preset_id, id=preset_id),
        )
    preset, raw = _load(path)
    return Response(
        content=raw,
        media_type=PRESET_MEDIA_TYPE,
        headers={
            # Quoted per RFC 9110 §8.8.3. Strong, because the entity IS the
            # digest's subject: same digest, same bytes, byte for byte.
            "ETag": '"%s"' % preset.sha256,
            # The file on disk is the source of truth and may be edited between
            # requests; a cached copy would be a fork of it by another name.
            "Cache-Control": "no-cache",
            "X-Preset-Sha256": preset.sha256,
        },
    )


__all__ = ["PRESET_ID", "PRESET_MEDIA_TYPE", "get_preset", "list_presets", "preset_paths", "router", "summarise"]
