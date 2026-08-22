# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""The `X-Requested-With` requirement on state-changing methods (`spectral_host.web.app` rule 3).

**W0 has no write endpoint yet**, so every test here registers a throwaway
`POST`/`PUT`/`DELETE` route on a test application built by the same
`create_app()` the server uses. That is deliberate and it is the point of
landing the middleware now: the seam ships with the application, not after the
first upload route exists — a guard added later is a guard that was absent for
every route written in between.

The hazard: this server binds loopback by default and, on the LAN, TLS (ADR
0021 decision 8) — but a page the singer happens to have open in another tab
can POST to `http://localhost:8000` from script or a form. A **custom request
header** cannot be set by a cross-origin form, image or link; only script that
has already passed a CORS preflight can. Requiring one is therefore proof the
request came from this application's own code, with no token round trip and no
session — and it is the layer that survives someone typing
`--allow-insecure-lan`.

Safe methods are untouched: a GET that required a header would break every
`<a href>`, every bookmark and the whole static mount.

Run: `uv run --project host pytest -q host/tests/test_web_csrf.py`
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Mount

from spectral_host.web.app import REQUESTED_WITH_VALUE, UNSAFE_METHODS, create_app


@pytest.fixture
def write_client(web_settings):
    """An application with one throwaway echo route per method — W0 ships no write route of its own.

    The routes are moved AHEAD of the static mount before the client is built.
    `create_app` mounts `/` last on purpose (app.py rule 4) and a mount at the
    root matches everything after it, so a route appended afterwards is
    unreachable — which is itself worth knowing, and is why this fixture
    reorders rather than working around it.
    """
    app = create_app(web_settings)
    before = len(app.router.routes)

    @app.post("/api/_test_echo")
    @app.put("/api/_test_echo")
    @app.patch("/api/_test_echo")
    @app.delete("/api/_test_echo")
    def echo() -> dict[str, str]:
        return {"echoed": "yes"}

    @app.get("/api/_test_echo")
    def echo_get() -> dict[str, str]:
        return {"echoed": "get"}

    added = app.router.routes[before:]
    del app.router.routes[before:]
    mount_at = next(i for i, route in enumerate(app.router.routes) if isinstance(route, Mount))
    app.router.routes[mount_at:mount_at] = added

    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("method", sorted(UNSAFE_METHODS))
def test_a_write_without_the_marker_header_is_403(write_client, method):
    """403, before the handler runs — the body names the header and the value it wants."""
    resp = write_client.request(method, "/api/_test_echo")
    assert resp.status_code == 403
    error = resp.json()["error"]
    assert error["code"] == "requested_with_required"
    assert error["details"]["header"] == "X-Requested-With"
    assert error["details"]["expected"] == REQUESTED_WITH_VALUE


@pytest.mark.parametrize("method", sorted(UNSAFE_METHODS))
def test_a_write_with_the_marker_header_is_allowed(write_client, csrf, method):
    """The `csrf` fixture is exactly what `host/web/src/api/client.ts` sends on every non-GET."""
    resp = write_client.request(method, "/api/_test_echo", headers=csrf)
    assert resp.status_code == 200
    assert resp.json() == {"echoed": "yes"}


def test_get_is_unaffected(write_client, web_client):
    """A header requirement on a safe method would break every link, bookmark and static asset."""
    assert write_client.get("/api/_test_echo").status_code == 200
    assert web_client.get("/api/presets").status_code == 200
    assert web_client.get("/").status_code == 200


def test_the_marker_comparison_is_case_insensitive_on_the_value(write_client):
    """Header NAMES are case-insensitive by HTTP; the value is compared lower-cased so a shouted one still passes."""
    resp = write_client.post("/api/_test_echo", headers={"x-requested-with": "Spectral-Web"})
    assert resp.status_code == 200


def test_a_wrong_marker_value_is_still_403(write_client):
    """The header's PRESENCE is the proof, but a value from some other library is not this application's."""
    resp = write_client.post("/api/_test_echo", headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 403
