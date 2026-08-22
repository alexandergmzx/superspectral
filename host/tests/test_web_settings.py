# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""The two configurations the server refuses to start with (`spectral_host.web.settings`, ADR 0021 decision 8).

`Settings` is frozen and `validate()` is separate from construction, so a
negative case here can build an invalid configuration and assert the refusal
without a server ever existing. One test per rule, each named for the hazard it
prevents — the shape of `test_manifest_verify.py`'s negative suite.

  * **A data directory inside the repository.** Uploads, separated stems and
    (at W4) hundreds of megabytes of Demucs weights land there. A default that
    resolved into the checkout would produce a `git status` nobody can read and
    a model file in a commit. The marker is `CLAUDE.md`, the same one
    `conftest.find_repo_root` uses.
  * **A non-loopback bind without TLS.** `navigator.mediaDevices` is
    `undefined` on an insecure origin that is not `localhost`, so the live path
    could not start on a phone over plain HTTP anyway; refusing the bind turns
    that into a startup error with an mkcert recipe instead of a browser
    mystery on the device. `--allow-insecure-lan` is the escape hatch, and it
    has to be typed.

Run: `uv run --project host pytest -q host/tests/test_web_settings.py`
"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest

from spectral_host.web import cli
from spectral_host.web.settings import (
    APP_NAME,
    DEFAULT_PORT,
    REPO_MARKER,
    Settings,
    SettingsError,
    default_data_dir,
    is_loopback,
)


def test_the_repo_marker_is_the_one_the_test_suite_uses(repo_root):
    """`settings.find_repo_root` and `conftest.find_repo_root` must agree, or the refusal guards another tree."""
    assert REPO_MARKER == "CLAUDE.md"
    assert (repo_root / REPO_MARKER).is_file()


def test_a_data_dir_inside_the_repository_is_refused(web_settings, repo_root):
    """Weights and stems are data; a default that landed in the checkout is the failure this rule exists for."""
    with pytest.raises(SettingsError, match="inside the repository"):
        replace(web_settings, data_dir=repo_root / "host" / "scratch").validate()


def test_the_repository_root_itself_is_refused(web_settings, repo_root):
    """The boundary is inclusive: the root is inside the repository too."""
    with pytest.raises(SettingsError, match="inside the repository"):
        replace(web_settings, data_dir=repo_root).validate()


def test_a_data_dir_outside_the_repository_is_accepted(web_settings, tmp_path):
    """Positive control — without it the rule above could be passing for the wrong reason."""
    assert replace(web_settings, data_dir=tmp_path / "elsewhere").validate() is not None


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.42", "spectral.local"])
def test_a_non_loopback_bind_without_tls_is_refused(web_settings, host):
    """Phone-on-LAN needs HTTPS (ADR 0021 decision 8); the message carries the mkcert line."""
    with pytest.raises(SettingsError, match="refusing to bind"):
        replace(web_settings, host=host).validate()


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "127.0.0.5"])
def test_a_loopback_bind_needs_no_tls(web_settings, host):
    """`localhost` is a secure context by specification, which is why the development default is loopback."""
    assert replace(web_settings, host=host).validate() is not None
    assert is_loopback(host)


def test_the_escape_hatch_has_to_be_typed(web_settings):
    """`--allow-insecure-lan` exists for the offline pane on a trusted network, and only when asked for."""
    assert replace(web_settings, host="0.0.0.0", allow_insecure_lan=True).validate() is not None


def test_tls_needs_both_files_or_neither(web_settings, tmp_path):
    """A certificate without its key is a server that starts and then cannot complete a handshake."""
    cert = tmp_path / "cert.pem"
    cert.write_text("not a real certificate\n", encoding="utf-8")
    with pytest.raises(SettingsError, match="both"):
        replace(web_settings, ssl_certfile=cert).validate()
    with pytest.raises(SettingsError, match="does not exist"):
        replace(web_settings, ssl_certfile=cert, ssl_keyfile=tmp_path / "missing-key.pem").validate()


def test_a_missing_presets_dir_is_refused_rather_than_served_as_an_empty_list(web_settings, tmp_path):
    """Six presets or a startup error; "no presets" would look like a working server with nothing to offer."""
    with pytest.raises(SettingsError, match="presets_dir"):
        replace(web_settings, presets_dir=tmp_path / "no-presets").validate()


def test_the_data_dir_default_follows_xdg(monkeypatch, tmp_path):
    """`$XDG_DATA_HOME/superspectral`, else `~/.local/share/superspectral` (ADR 0021 decision 8, prov.)."""
    monkeypatch.setitem(os.environ, "XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert default_data_dir() == tmp_path / "xdg" / APP_NAME
    monkeypatch.delitem(os.environ, "XDG_DATA_HOME", raising=False)
    assert default_data_dir() == Path.home() / ".local" / "share" / APP_NAME


def test_the_default_port_is_the_one_the_front_end_proxies_to(repo_root):
    """Two files have to agree, and only one of them is read by a browser: host/web/vite.config.ts wins."""
    vite = (repo_root / "host" / "web" / "vite.config.ts").read_text(encoding="utf-8")
    assert "127.0.0.1:%d" % DEFAULT_PORT in vite, "settings.DEFAULT_PORT and the vite dev proxy have drifted apart"


def test_the_lifespan_creates_the_data_directory(web_settings, web_client):
    """Created at startup, not at the first upload: a directory the server cannot make is a startup failure."""
    assert web_settings.data_dir.is_dir()
    assert web_client.get("/api/health").status_code == 200


def test_serve_exits_two_on_a_refused_configuration(tmp_path, repo_root, capsys):
    """The CLI turns a `SettingsError` into exit 2 with the reason — never a traceback."""
    status = cli.main(["serve", "--data-dir", str(repo_root / "host"), "--port", "8799"])
    assert status == cli.EXIT_USAGE
    err = capsys.readouterr().err
    assert "inside the repository" in err
    assert "Traceback" not in err


def test_settings_are_frozen(web_settings):
    """`app.state.settings` cannot drift between requests; `replace()` is how a variant is made."""
    with pytest.raises(Exception):
        web_settings.host = "0.0.0.0"  # type: ignore[misc]
