# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""The `host/web/dist` mount, by hazard (`spectral_host.web.static`, ADR 0021 decisions 1 and 8).

Four hazards, and each is a way a static mount silently does the wrong thing:

  * **`.npy` served as text.** Python 3.12's `mimetypes` has no `.npy` entry;
    Starlette's fallback is `text/plain`, and a browser may sniff and mangle a
    binary body served that way. W1's golden suite fetches the committed `.npy`
    arrays over this mount, so a mangled one would read as a numerical
    disagreement with the oracle — the hardest possible way to find a MIME bug.
    The same test asserts that `.wasm` and `.mjs` are ALREADY known to the
    stdlib, because a shim for something that no longer needs one is a shim
    nobody removes.
  * **An SPA fallback.** With rewrite-everything-to-index, `/api/goldn`
    (misspelled) becomes a 200 of HTML that the client tries to parse as JSON,
    and every typo becomes an empty page instead of a 404.
  * **A traceback where a build instruction belongs.** `dist/` absent is the
    normal state of a fresh checkout; it must produce a 501 naming
    `npm run build`, and `/api` must keep working while it does.
  * **COOP/COEP by default.** Cross-origin isolation breaks every cross-origin
    subresource; the W1 design does not need it (MessagePort transfer, not
    SharedArrayBuffer), so it is off unless `--cross-origin-isolation` is typed.

Run: `uv run --project host pytest -q host/tests/test_web_static.py`
"""

from __future__ import annotations

import mimetypes
from dataclasses import replace

from fastapi.testclient import TestClient

from spectral_host.web import static
from spectral_host.web.app import create_app


def client_with(settings) -> TestClient:
    return TestClient(create_app(settings))


# --- MIME types -------------------------------------------------------------------


def test_npy_is_typed_and_the_two_the_stdlib_knows_are_not_shimmed(web_client):
    """`.npy` → application/octet-stream, registered by `create_app`; `.wasm`/`.mjs` were already right."""
    assert mimetypes.guess_type("window-hann-4096.npy")[0] == static.NPY_MEDIA_TYPE
    for suffix, expected in static.KNOWN_MEDIA_TYPES.items():
        assert mimetypes.guess_type("probe" + suffix)[0] == expected, (
            "%s stopped being known to the stdlib — static.py's assertion is now a registration" % suffix
        )
    resp = web_client.get("/assets/window-hann-4096.npy")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(static.NPY_MEDIA_TYPE)


# --- no SPA fallback ----------------------------------------------------------------


def test_an_unknown_api_path_is_a_json_404_and_never_index_html(web_client):
    """The static mount sees every unmatched `/api/...` path; it must answer 404 in the one error shape."""
    resp = web_client.get("/api/goldn")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json()["error"]["code"] == "not_found"
    assert "<!doctype html>" not in resp.text.lower()


def test_an_unknown_page_is_404_not_the_index(web_client):
    """No client-side router exists, so there is nothing a fallback would buy and one page to lose."""
    resp = web_client.get("/no/such/page")
    assert resp.status_code == 404
    assert "fixture" not in resp.text


def test_the_index_is_served_at_the_root(web_client):
    """The one document whose URL is not its filename."""
    resp = web_client.get("/")
    assert resp.status_code == 200
    assert "<!doctype html>" in resp.text.lower()


# --- caching ------------------------------------------------------------------------


def test_the_index_revalidates_and_hashed_assets_are_immutable(web_client):
    """`index.html` names the current bundle, so it revalidates; `assets/` names carry a content hash."""
    assert web_client.get("/").headers["cache-control"] == static.CACHE_REVALIDATE
    assert web_client.get("/assets/index-abc123.js").headers["cache-control"] == static.CACHE_IMMUTABLE
    # Not under assets/: an unhashed name may be overwritten by the next build.
    assert web_client.get("/unhashed.txt").headers["cache-control"] == static.CACHE_REVALIDATE


# --- dist/ absent -------------------------------------------------------------------


def test_a_missing_dist_gives_the_501_page_and_not_a_traceback(web_settings, tmp_path):
    """A fresh checkout has no dist/. The answer names `npm run build`; the API is untouched."""
    settings = replace(web_settings, dist_dir=tmp_path / "never-built")
    with client_with(settings) as client:
        resp = client.get("/")
        assert resp.status_code == 501
        assert resp.headers["content-type"].startswith("text/plain")
        assert "npm run build" in resp.text
        assert "npm ci --ignore-scripts" in resp.text
        assert str(settings.dist_dir) in resp.text
        assert "Traceback" not in resp.text
        # The API is unaffected — that is the sentence the page makes.
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/presets").status_code == 200


def test_a_missing_dist_still_404s_an_unknown_api_path(web_settings, tmp_path):
    """501 must not swallow the API prefix: "not built" and "no such route" are different problems."""
    settings = replace(web_settings, dist_dir=tmp_path / "never-built")
    with client_with(settings) as client:
        resp = client.get("/api/nope")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_dist_is_built_reads_the_index_not_just_the_directory(web_settings, tmp_path):
    """An empty `dist/` left over from a failed build is not a built front end."""
    empty = tmp_path / "empty-dist"
    empty.mkdir()
    assert not static.dist_is_built(replace(web_settings, dist_dir=empty))
    assert static.dist_is_built(web_settings)


# --- cross-origin isolation ----------------------------------------------------------


def test_coop_and_coep_are_absent_by_default(web_client):
    """Off unless asked: the design transfers frames over a MessagePort and needs no SharedArrayBuffer."""
    for path in ("/", "/assets/index-abc123.js"):
        headers = web_client.get(path).headers
        assert "cross-origin-opener-policy" not in headers, path
        assert "cross-origin-embedder-policy" not in headers, path


def test_coop_and_coep_appear_when_the_flag_is_on(web_settings):
    """The flag is a command-line change, so a W1 profile that wants the shared-memory ring needs no code edit."""
    with client_with(replace(web_settings, cross_origin_isolation=True)) as client:
        headers = client.get("/").headers
    assert headers["cross-origin-opener-policy"] == "same-origin"
    assert headers["cross-origin-embedder-policy"] == "require-corp"


def test_the_501_page_also_carries_the_isolation_headers_when_asked(web_settings, tmp_path):
    """Same flag, same answer, whether or not the front end has been built."""
    settings = replace(web_settings, dist_dir=tmp_path / "never-built", cross_origin_isolation=True)
    with client_with(settings) as client:
        headers = client.get("/").headers
    assert headers["cross-origin-opener-policy"] == "same-origin"
