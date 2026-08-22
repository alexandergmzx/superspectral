# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""`spectral-golden` — the host's one console script (host/pyproject.toml `[project.scripts]`).

Usage:
    spectral-golden verify [MANIFEST ...] [--repo-root DIR] [--no-env-check]
                                        # schema + invariants S, I1-I8, N1-N4, G1; exit 1 on any failure; never writes
    spectral-golden env [--repo-root DIR] [--praat-reference VERSION]
                                        # the manifest `generator` block of THIS environment, as JSON
    spectral-golden generate --set NAME --approved-by WHO --reason TEXT [--repo-root DIR] [--allow-dirty]
                                        # write a NEW golden set and verify it; refuses an existing set dir
    spectral-golden t7                  # T7b: one WAV through the bundled Praat and through a praat.org binary
    spectral-golden --version

`verify` (unit B-U5) defaults to every `host/golden/outputs/*/manifest.yaml`
under the repository root found upward from the working directory; with no
manifest present it prints "no manifests" and exits 0, because an empty
outputs directory is not drift. Each failure prints as
`<manifest>: <rule>: <message>`; the rule numbers are documented in
spectral_host/golden/verify.py. `--no-env-check` skips rule I5 only
(installed parselmouth / bundled Praat / numpy / scipy versus the manifest)
and says so in a notice — for a checkout that is not the generating
environment, never for CI.

`env` (unit B-U4's `spectral_host.env.capture`, wired here) prints the eleven
`generator` keys as a JSON object — `praat_reference` is `null` while T7b is
open — so a script can read the pin chain without parsing YAML.

`generate` (unit B-U6, `spectral_host.golden.generate`) writes a NEW set from
its `SetSpec` (`spectral_host.golden.sets`) — chain-of-custody check of every
input WAV against the Tier-0 dataset manifest, arrays, manifest, then its own
`verify`. Exit 0 written and clean; 1 written but red (files left for
inspection); 2 refused — unknown set, existing set directory, missing or
drifted inputs, dirty `host/src/spectral_host` without `--allow-dirty`.

`t7` still prints "not implemented" to stderr and exits 2; its body lands
with unit B-U10. Exit 2 (not 0, not 1) so that a CI step wired up before its
unit lands fails as a usage error rather than reading as "verified clean" or
as "drift detected" (ADR 0009 item 4: a red verify is a decision request, and
this is not one).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from spectral_host import __version__
from spectral_host.golden import generate as generate_mod
from spectral_host.golden import verify as verify_mod

#: Exit status for a subcommand whose unit has not landed. argparse uses 2 for
#: usage errors, which is the right reading: the command line asked for
#: something this build cannot do.
EXIT_NOT_IMPLEMENTED = 2

#: (name, help, roadmap unit) — the subcommands still waiting for their unit.
PENDING_SUBCOMMANDS: tuple[tuple[str, str, str], ...] = (
    ("t7", "threshold T7b: compare the bundled Praat against a praat.org binary on one WAV", "B-U10"),
)


def _not_implemented(args: argparse.Namespace) -> int:
    print(
        f"spectral-golden {args.command}: not implemented (roadmap H0 unit {args.unit})",
        file=sys.stderr,
    )
    return EXIT_NOT_IMPLEMENTED


def _run_verify(args: argparse.Namespace) -> int:
    return verify_mod.run_verify(args.manifests, args.repo_root, args.check_env)


def _run_generate(args: argparse.Namespace) -> int:
    return generate_mod.run_generate(args.set_name, args.approved_by, args.reason, args.repo_root, args.allow_dirty)


def _run_env(args: argparse.Namespace) -> int:
    # Imported here, not at module top: `env` reads git and the package tree,
    # which `verify` does not need, and an import error in one subcommand must
    # not take the other down with it.
    from spectral_host import env as env_mod

    try:
        root = args.repo_root.resolve() if args.repo_root is not None else verify_mod.default_repo_root()
        captured = env_mod.capture(root, praat_reference=args.praat_reference)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(captured.asdict(), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Return the top-level parser. Later units attach arguments to the subparsers they own."""
    parser = argparse.ArgumentParser(
        prog="spectral-golden",
        description="Super Spectral golden-file tooling (GPL-3.0-or-later; ADR 0009).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    verify_help = "recompute digests and re-read the installed pins of a golden set; exit 1 on drift, never writes"
    verify = subparsers.add_parser("verify", help=verify_help, description=verify_help)
    verify_mod.add_verify_arguments(verify)
    verify.set_defaults(func=_run_verify, unit="B-U5")

    env_help = "print the pin chain of the installed environment (the manifest `generator` block) as JSON"
    env = subparsers.add_parser("env", help=env_help, description=env_help)
    env.add_argument("--repo-root", type=Path, default=None, help="repository root (default: search upward from the working directory)")
    env.add_argument("--praat-reference", default=None, help="praat.org release T7b was run against (default: null, T7b open)")
    env.set_defaults(func=_run_env, unit="B-U4")

    # The argument list lives with the generator (imported at module top: its
    # arguments are needed at parse time, and everything it imports, verify
    # already does) so the module CLI and this subcommand cannot drift.
    generate_help = "write a NEW golden set from its SetSpec and verify it; refuses an existing set directory"
    generate = subparsers.add_parser("generate", help=generate_help, description=generate_help)
    generate_mod.add_generate_arguments(generate)
    generate.set_defaults(func=_run_generate, unit="B-U6")

    for name, help_text, unit in PENDING_SUBCOMMANDS:
        sub = subparsers.add_parser(name, help=help_text, description=help_text)
        sub.set_defaults(func=_not_implemented, unit=unit)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(sys.stderr)
        print("spectral-golden: a COMMAND is required", file=sys.stderr)
        return EXIT_NOT_IMPLEMENTED
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
