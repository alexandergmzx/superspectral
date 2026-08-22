# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""The host web application's backend — FastAPI + uvicorn (ADR 0021, roadmap track W).

The founding research document's §B Python half, and the interface the
`analyze/` and `compare/` modules never had. What it is *not* is a view of the
watch: no audio or spectrum ever arrives here from the device (ADR 0002
decision 4 as amended by ADR 0021 decision 5 — "no live link between watch and
host"), and no number this application produces may be quoted for any bound of
proposal §1 (ADR 0021 decision 3).

Module map (W0):

  settings.py  the frozen `Settings` and its refusals — a data directory inside
               the repository, a non-loopback bind without TLS
  extras.py    optional-dependency probing by `importlib.util.find_spec`, never
               by import; `ExtraMissing` is the 501 of `/analyze` and `/separate`
  models.py    the pydantic response models and the ONE error shape
  static.py    the mount of `host/web/dist` — no SPA fallback, `.npy` typed,
               a 501 page when the front end has not been built
  routes/      `/api/health`, `/api/version`, `/api/presets`, `/api/presets/{id}`
  app.py       `create_app(settings)` — the factory the tests and uvicorn share
  cli.py       `spectral-web serve | peak`

W1 adds `GET /api/golden`; W4 adds `/analyze` and `/separate`.
"""

from __future__ import annotations
