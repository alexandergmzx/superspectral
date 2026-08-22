# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""Command line for the Tier-0 generator.

::

    python -m synth_signals list
    python -m synth_signals generate --out DIR [--only NAME ...]
    python -m synth_signals check    --out DIR [--only NAME ...]

``generate`` renders the whole catalogue in memory, writes ``DIR/<name>.wav``
for every entry (or only the ``--only`` names) and rewrites ``DIR/manifest.yaml``
from the full render, so the manifest is always complete and consistent with
the generator even after a partial write. ``check`` regenerates in memory and
compares sha256 against the manifest and against whatever is on disk; exit 1
on any drift or mismatch (see :func:`synth_signals.manifest.check`). ``list``
prints the catalogue. Exit 2 on usage or a bad manifest.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import catalogue, manifest


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="synth_signals", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="write the WAVs and manifest.yaml")
    g.add_argument("--out", required=True, type=Path, help="dataset directory (e.g. datasets/tier0-synthetic)")
    g.add_argument("--only", action="append", metavar="NAME", help="write only this entry (repeatable); manifest stays complete")

    c = sub.add_parser("check", help="regenerate in memory and compare sha256 with the manifest (exit 1 on drift)")
    c.add_argument("--out", required=True, type=Path, help="dataset directory holding manifest.yaml")
    c.add_argument("--only", action="append", metavar="NAME", help="check only this entry (repeatable)")

    sub.add_parser("list", help="print the catalogue")
    return p


def _validate_names(names: list[str] | None) -> list[str] | None:
    if names is None:
        return None
    unknown = [n for n in names if n not in catalogue.NAMES]
    if unknown:
        raise SystemExit(f"unknown catalogue name(s): {', '.join(unknown)} (see `list`)")
    return names


def cmd_list() -> int:
    width = max(len(e.name) for e in catalogue.CATALOGUE)
    for e in catalogue.CATALOGUE:
        twin = "  host-only" if e.host_only else ""
        print(f"{e.name:<{width}}  {e.fs:>5} Hz  {e.dur_s:.1f} s  {e.generator}{twin}")
    print(f"{len(catalogue.CATALOGUE)} entries")
    return 0


def cmd_generate(out: Path, only: list[str] | None) -> int:
    out.mkdir(parents=True, exist_ok=True)
    builts = [catalogue.build(e) for e in catalogue.CATALOGUE]
    selected = set(only) if only else set(catalogue.NAMES)
    written = 0
    for b in builts:
        if b.entry.name in selected:
            (out / b.filename).write_bytes(b.data)
            written += 1
            print(f"wrote {out / b.filename}  {b.sha256[:12]}…")
    path = manifest.write(out, manifest.build_manifest(builts))
    print(f"wrote {path}  ({written} WAV(s), {len(builts)} manifest entries)")
    return 0


def cmd_check(out: Path, only: list[str] | None) -> int:
    try:
        findings = manifest.check(out, only)
    except (OSError, ValueError) as exc:
        print(f"check: {exc}", file=sys.stderr)
        return 2
    ok = manifest.print_findings(findings)
    if not ok:
        print("check: DRIFT -- the generator no longer reproduces the tracked manifest (or a file on disk is stale)", file=sys.stderr)
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "list":
        return cmd_list()
    only = _validate_names(args.only)
    if args.command == "generate":
        return cmd_generate(args.out, only)
    if args.command == "check":
        return cmd_check(args.out, only)
    raise SystemExit(2)  # pragma: no cover — argparse enforces the choices
