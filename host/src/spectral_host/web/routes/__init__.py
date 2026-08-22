# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""The `/api` router — every route this application answers, assembled in one place.

`api_router` is mounted by `spectral_host.web.app.create_app()` at the `/api`
prefix and BEFORE the static mount at `/`, because a mount at the root matches
everything after it (see `static.py`). Splitting the prefix out here means no
module below spells `/api`, and the front end's one route-aware file
(`host/web/src/api/client.ts`) faces one prefix.

W0 serves `meta` (health, version) and `presets` (list, byte-identical file).
W1 adds `golden`; W4 adds `analyze` and `separate`. A router is added here when
its routes exist — never as an empty placeholder, because a registered route
that 501s for a milestone is indistinguishable in a client from one that 501s
for a missing extra.
"""

from __future__ import annotations

from fastapi import APIRouter

from spectral_host.web.routes import meta, presets

#: The prefix every route below is served under.
API_PREFIX = "/api"

api_router = APIRouter()
api_router.include_router(meta.router, tags=["meta"])
api_router.include_router(presets.router, tags=["presets"])

__all__ = ["API_PREFIX", "api_router"]
