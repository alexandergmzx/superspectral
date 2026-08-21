# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
# Origin: python-scripts/doc_ocr in the author's `swarm` repository (same author, same tool).
"""Reference-library extractor: PDFs under docs/ -> reviewable markdown sidecars.

Usage:
    python3 -m doc_ocr scan                       # status report, writes nothing
    python3 -m doc_ocr extract                    # generate/refresh stale sidecars
    python3 -m doc_ocr extract docs/datasheets/bosch --force
    python3 -m doc_ocr check docs/.../bme280.pdf --reviewer AG --note "tables ok"
    python3 -m doc_ocr unchecked                  # what still needs human review
    python3 -m doc_ocr verify                     # PDFs that changed since extraction

Sidecars are gitignored; the tracked ledger is docs/OCR/manifest.tsv.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import manifest, pipeline
from .config import Settings
from .discover import discover, sidecar_targets


def _select(sources, paths: list[Path]):
    """Filter discovered sources to those under any of the given paths."""
    if not paths:
        return sources
    resolved = [p.resolve() for p in paths]
    picked = []
    for src in sources:
        s = src.path.resolve()
        if any(s == r or r in s.parents for r in resolved):
            picked.append(src)
    return picked


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return str(n)


def cmd_scan(args, settings: Settings) -> int:
    sources = _select(discover(settings.docs_root, settings.skip_dirs), args.paths)
    rows = manifest.load(settings.manifest_path)
    n_split = n_stale = n_missing = 0
    print(f"{'PAGES':>6} {'STATE':<10} {'REVIEW':<10} FILE")
    for src in sources:
        row = rows.get(src.rel)
        if row is None:
            state, n_missing = "new", n_missing + 1
        elif row.sha256 != src.sha256:
            state, n_stale = "CHANGED", n_stale + 1
        elif not pipeline.sidecar_present(src.path):
            state, n_missing = "missing", n_missing + 1
        else:
            state = "ok"
        if src.pages > settings.split_threshold:
            n_split += 1
        review = row.review if row else "-"
        if args.all or state != "ok":
            print(f"{src.pages:>6} {state:<10} {review:<10} {src.rel}")
    print(
        f"\n{len(sources)} documents · {n_missing} need extraction · {n_stale} changed "
        f"· {n_split} over {settings.split_threshold} pages"
    )
    return 0


def cmd_extract(args, settings: Settings) -> int:
    sources = _select(discover(settings.docs_root, settings.skip_dirs), args.paths)
    rows = manifest.load(settings.manifest_path)
    counts: dict[str, int] = {}
    total_bytes = 0
    failures: list[pipeline.Result] = []

    for src in sources:
        result = pipeline.process(src, settings, rows.get(src.rel), args.force)
        counts[result.status] = counts.get(result.status, 0) + 1
        total_bytes += result.bytes_written
        if result.row is not None:
            rows[src.rel] = result.row
        if result.status == "failed":
            failures.append(result)
            print(f"  FAILED  {src.rel}: {result.message}", file=sys.stderr)
        elif result.status == "reset":
            print(
                f"  CHANGED {src.rel}: source bytes differ from the verified extraction; "
                f"review flag reset to unchecked",
                file=sys.stderr,
            )
        elif result.status != "skipped":
            layout = f"{result.layout}/{result.parts}" if result.layout == "split" else "single"
            print(f"  {result.status:<10}{src.rel}  [{layout}] {_human(result.bytes_written)}")

    manifest.save(settings.manifest_path, rows)
    summary = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    print(f"\n{summary} · {_human(total_bytes)} written · ledger {settings.manifest_path}")
    return 1 if failures else 0


def cmd_check(args, settings: Settings) -> int:
    sources = _select(discover(settings.docs_root, settings.skip_dirs), args.paths)
    if not sources:
        sys.exit("no source documents matched")
    rows = manifest.load(settings.manifest_path)
    for src in sources:
        row = rows.get(src.rel)
        if row is None:
            print(f"  not extracted yet, skipping: {src.rel}", file=sys.stderr)
            continue
        row.review = args.state
        if args.reviewer:
            row.reviewer = args.reviewer
        if args.note:
            row.notes = args.note
        if args.redistributable:
            row.redistributable = args.redistributable
        rows[src.rel] = row
        print(f"  {args.state:<10}{src.rel}")
    manifest.save(settings.manifest_path, rows)
    return 0


def cmd_unchecked(args, settings: Settings) -> int:
    rows = manifest.load(settings.manifest_path)
    pending = [r for r in rows.values() if r.review != "checked"]
    for row in sorted(pending, key=lambda r: -r.pages):
        print(f"{row.pages:>6} {row.review:<10} {row.source}")
    print(f"\n{len(pending)} of {len(rows)} documents awaiting review")
    return 0


def cmd_verify(args, settings: Settings) -> int:
    sources = _select(discover(settings.docs_root, settings.skip_dirs), args.paths)
    rows = manifest.load(settings.manifest_path)
    drift = 0
    for src in sources:
        row = rows.get(src.rel)
        if row is None:
            continue
        if row.sha256 != src.sha256:
            drift += 1
            print(f"  CHANGED  {src.rel} (was {row.sha256[:12]}, now {src.sha256[:12]})")
        elif not pipeline.sidecar_present(src.path):
            single, _ = sidecar_targets(src.path)
            print(f"  MISSING  {src.rel} -> {single.name} (regenerate with `extract`)")
    print(f"\n{drift} source document(s) changed since extraction")
    return 1 if drift else 0


def build_parser(defaults: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doc_ocr",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--docs", type=Path, default=defaults.docs_root,
                        help="reference library root (default: %(default)s)")
    parser.add_argument("--manifest", type=Path, default=defaults.manifest_path,
                        help="tracked ledger (default: %(default)s)")
    parser.add_argument("--split-pages", type=int, default=defaults.split_threshold,
                        help="split documents longer than this (default: %(default)s)")
    parser.add_argument("--lang", default=defaults.ocr_lang,
                        help="tesseract language for scanned PDFs (default: %(default)s)")
    parser.add_argument("-v", "--verbose", action="store_true", help="log extraction decisions")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scan", help="report corpus status without writing")
    p.add_argument("paths", nargs="*", type=Path)
    p.add_argument("--all", action="store_true", help="list up-to-date documents too")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("extract", help="generate or refresh sidecars")
    p.add_argument("paths", nargs="*", type=Path)
    p.add_argument("--force", action="store_true", help="re-extract even if up to date")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("check", help="record human review of an extraction")
    p.add_argument("paths", nargs="+", type=Path)
    p.add_argument("--state", choices=manifest.REVIEW_STATES, default="checked")
    p.add_argument("--reviewer", default="", help="who reviewed it")
    p.add_argument("--note", default="", help="one-line note for the ledger")
    p.add_argument("--redistributable", choices=("yes", "no", "unknown"), default="")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("unchecked", help="list documents awaiting review")
    p.set_defaults(func=cmd_unchecked)

    p = sub.add_parser("verify", help="detect sources that changed since extraction")
    p.add_argument("paths", nargs="*", type=Path)
    p.set_defaults(func=cmd_verify)
    return parser


def main() -> int:
    defaults = Settings()
    args = build_parser(defaults).parse_args()
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    settings = Settings(
        docs_root=args.docs,
        manifest_path=args.manifest,
        split_threshold=args.split_pages,
        ocr_lang=args.lang,
    )
    if not settings.docs_root.is_dir():
        sys.exit(f"docs root not found: {settings.docs_root}")
    return args.func(args, settings)


if __name__ == "__main__":
    sys.exit(main())
