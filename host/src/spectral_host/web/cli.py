# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""`spectral-web` — the host web application's console script (host/pyproject.toml `[project.scripts]`).

Usage:
    spectral-web serve [--host ADDR] [--port N] [--ssl-certfile PEM --ssl-keyfile PEM]
                       [--data-dir DIR] [--presets-dir DIR] [--dist-dir DIR]
                       [--allow-insecure-lan] [--cross-origin-isolation]
                                        # run the FastAPI application under uvicorn; refuses a
                                        # data dir inside the repository and a LAN bind without TLS
    spectral-web peak [--wav FILE | --device NAME] [--preset ID|FILE]
                      [--window W] [--fft-size N] [--rate HZ] [--interval-ms MS]
                      [--min-hz HZ] [--max-hz HZ] [--once] [--frames N] [--reference HZ]
                                        # the founding research document's M0: the interpolated
                                        # peak frequency, one line per interval
    spectral-web --version

Exit status, the same convention as `spectral-golden` (golden/cli.py): **0**
clean; **1** a run that started and failed (no audio, an unreadable file);
**2** the command line asked for something this build cannot do — a usage
error, a refused configuration, or a missing optional-dependency group, whose
message ends in the exact `uv sync --project host --extra ...` line that fixes
it. 2 rather than 1 because "you asked for capture and there is no PortAudio
here" is a statement about the invocation, not about the audio.

Phone-on-LAN (ADR 0021 decision 8) is `serve --host 0.0.0.0` with an mkcert
pair; without `--ssl-certfile` / `--ssl-keyfile` that bind is **refused**,
because `navigator.mediaDevices` is `undefined` on an insecure non-localhost
origin and the live path could not start there anyway. `--allow-insecure-lan`
exists for the offline pane on a trusted network and has to be typed.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from spectral_host import __version__
from spectral_host.capture import peak as peak_mod
from spectral_host.presets import PresetRejected
from spectral_host.wavio import UnsupportedWav
from spectral_host.web.extras import ExtraMissing
from spectral_host.web.settings import Settings, SettingsError, find_repo_root

#: Exit status for "this build cannot do what the command line asked".
EXIT_USAGE = 2

#: Exit status for a run that started and failed.
EXIT_FAILED = 1


def _settings_from_args(args: argparse.Namespace) -> Settings:
    """Build `Settings`, overriding only what was actually passed — defaults stay `settings.py`'s."""
    overrides: dict[str, object] = {
        "host": args.host,
        "port": args.port,
        "cross_origin_isolation": bool(args.cross_origin_isolation),
        "allow_insecure_lan": bool(args.allow_insecure_lan),
    }
    for name in ("data_dir", "presets_dir", "golden_dir", "dist_dir", "ssl_certfile", "ssl_keyfile"):
        value = getattr(args, name, None)
        if value is not None:
            overrides[name] = Path(value)
    if args.max_upload_mb is not None:
        overrides["max_upload_mb"] = int(args.max_upload_mb)
    return Settings(**overrides)  # type: ignore[arg-type]


def _run_serve(args: argparse.Namespace) -> int:
    # Imported here, not at module top: `peak` must run on a machine where
    # uvicorn's own import chain is irrelevant, and an import error in the
    # server must not take the printer down with it.
    import uvicorn

    from spectral_host.web.app import create_app
    from spectral_host.web.static import dist_is_built

    try:
        settings = _settings_from_args(args).validate()
    except SettingsError as exc:
        print("spectral-web serve: %s" % exc, file=sys.stderr)
        return EXIT_USAGE
    scheme = "https" if settings.tls else "http"
    display_host = "127.0.0.1" if settings.host in ("0.0.0.0", "::", "") else settings.host
    print("spectral-web %s serving %s://%s:%d" % (__version__, scheme, display_host, settings.port), file=sys.stderr)
    print("  presets   %s" % settings.presets_dir, file=sys.stderr)
    print("  data dir  %s" % settings.data_dir, file=sys.stderr)
    if dist_is_built(settings):
        print("  front end %s" % settings.dist_dir, file=sys.stderr)
    else:
        # Said once, at startup, rather than only in the 501 body: the person
        # who has to run `npm run build` is the one reading this terminal.
        print("  front end NOT BUILT (%s) — /api works; run `npm run build` in host/web" % settings.dist_dir, file=sys.stderr)
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        ssl_certfile=str(settings.ssl_certfile) if settings.ssl_certfile else None,
        ssl_keyfile=str(settings.ssl_keyfile) if settings.ssl_keyfile else None,
        log_level=args.log_level,
    )
    return 0


def _run_peak(args: argparse.Namespace) -> int:
    presets_dir = None
    root = find_repo_root()
    if root is not None:
        presets_dir = root / "protocols" / "presets"
    try:
        return peak_mod.run_peak(args, presets_dir=presets_dir)
    except ExtraMissing as exc:
        print("spectral-web peak: %s" % exc, file=sys.stderr)
        return EXIT_USAGE
    except PresetRejected as exc:
        print("spectral-web peak: preset rejected: %s" % exc, file=sys.stderr)
        return EXIT_USAGE
    except (UnsupportedWav, ValueError) as exc:
        print("spectral-web peak: %s" % exc, file=sys.stderr)
        return EXIT_USAGE
    except peak_mod.NoAudio as exc:
        print("spectral-web peak: %s" % exc, file=sys.stderr)
        return EXIT_FAILED
    except OSError as exc:
        print("spectral-web peak: %s" % exc, file=sys.stderr)
        return EXIT_FAILED
    except KeyboardInterrupt:
        # A live run ends with Ctrl-C by design; that is a clean exit, not a
        # traceback across the readings the user was watching.
        print("", file=sys.stderr)
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spectral-web",
        description="Super Spectral host web application (GPL-3.0-or-later; ADR 0021). Not a view of the watch.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    serve_help = "run the FastAPI application under uvicorn and serve the built front end"
    serve = subparsers.add_parser("serve", help=serve_help, description=serve_help)
    serve.add_argument("--host", default=Settings.host, help="bind address (default: %(default)s; a non-loopback bind needs TLS)")
    serve.add_argument("--port", type=int, default=Settings.port, help="bind port (default: %(default)s, the port host/web/vite.config.ts proxies to)")
    serve.add_argument("--ssl-certfile", type=Path, default=None, metavar="PEM", help="TLS certificate (mkcert; required for phone-on-LAN)")
    serve.add_argument("--ssl-keyfile", type=Path, default=None, metavar="PEM", help="TLS private key")
    serve.add_argument("--data-dir", type=Path, default=None, metavar="DIR", help="uploads, stems and weights (default: $XDG_DATA_HOME/superspectral; never inside the repository)")
    serve.add_argument("--presets-dir", type=Path, default=None, metavar="DIR", help="the six presets (default: protocols/presets/ of the checkout)")
    serve.add_argument("--golden-dir", type=Path, default=None, metavar="DIR", help="the committed golden sets (default: host/golden/ of the checkout)")
    serve.add_argument("--dist-dir", type=Path, default=None, metavar="DIR", help="the built front end (default: host/web/dist/ of the checkout)")
    serve.add_argument("--max-upload-mb", type=int, default=None, help="upload ceiling in MiB (default: %d, prov.)" % Settings.max_upload_mb)
    serve.add_argument("--allow-insecure-lan", action="store_true", help="permit a non-loopback bind without TLS (the offline pane only)")
    serve.add_argument("--cross-origin-isolation", action="store_true", help="send COOP/COEP; off by default — the design uses MessagePort transfer, not SharedArrayBuffer")
    serve.add_argument("--log-level", default="info", choices=("critical", "error", "warning", "info", "debug", "trace"), help="uvicorn log level (default: %(default)s)")
    serve.set_defaults(func=_run_serve)

    peak_help = "print the interpolated peak frequency per interval (the founding document's M0)"
    peak = subparsers.add_parser("peak", help=peak_help, description=peak_help)
    peak_mod.add_peak_arguments(peak)
    peak.set_defaults(func=_run_peak)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(sys.stderr)
        print("spectral-web: a COMMAND is required (serve | peak)", file=sys.stderr)
        return EXIT_USAGE
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
