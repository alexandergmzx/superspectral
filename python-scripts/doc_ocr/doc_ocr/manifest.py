# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
# Origin: python-scripts/doc_ocr in the author's `swarm` repository (same author, same tool).
"""The tracked ledger: docs/OCR/manifest.tsv.

This file is committed; the sidecars it describes are not. It records *that* a
document exists and was processed — never its content — and it owns the review
flag, keyed by source sha256. That key is what lets a human's "I checked this"
survive deleting and regenerating a gitignored sidecar, and what turns a changed
PDF into a loud warning instead of a silent desync.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from pathlib import Path

COLUMNS = (
    "source",
    "sha256",
    "pages",
    "chars_per_page",
    "extractor",
    "extracted_utc",
    "layout",
    "parts",
    "review",
    "reviewer",
    "redistributable",
    "notes",
)

REVIEW_STATES = ("unchecked", "checked", "needs-work")


@dataclass
class Row:
    source: str
    sha256: str = ""
    pages: int = 0
    chars_per_page: int = 0
    extractor: str = ""
    extracted_utc: str = ""
    layout: str = ""  # single | split | none
    parts: int = 0
    review: str = "unchecked"
    reviewer: str = ""
    redistributable: str = "unknown"
    notes: str = ""


def _clean(value: str) -> str:
    """TSV cells must not contain tabs or newlines."""
    return str(value).replace("\t", " ").replace("\n", " ").strip()


def load(path: Path) -> dict[str, Row]:
    """Manifest rows keyed by source path. Missing file means an empty ledger."""
    if not path.is_file():
        return {}
    rows: dict[str, Row] = {}
    int_fields = {f.name for f in fields(Row) if f.type == "int"}
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        if not line.strip() or line.startswith("#"):
            continue
        cells = line.split("\t")
        if cells[0] == "source":  # header
            continue
        cells += [""] * (len(COLUMNS) - len(cells))
        values: dict[str, object] = {}
        for name, cell in zip(COLUMNS, cells):
            if name in int_fields:
                try:
                    values[name] = int(cell or 0)
                except ValueError:
                    values[name] = 0
            else:
                values[name] = cell
        row = Row(**values)  # type: ignore[arg-type]
        rows[row.source] = row
    return rows


def save(path: Path, rows: dict[str, Row]) -> None:
    """Write the ledger sorted by source path so diffs stay readable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    out = ["\t".join(COLUMNS)]
    for source in sorted(rows):
        row = asdict(rows[source])
        out.append("\t".join(_clean(row[name]) for name in COLUMNS))
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def merge(existing: Row | None, fresh: Row) -> Row:
    """Fold a fresh extraction into the ledger, preserving human-owned fields.

    The review flag carries over only while the source bytes are unchanged. A
    different sha256 means the vendor silently revised the document, so the
    extraction is no longer the thing anybody verified and the flag resets.
    """
    if existing is None:
        return fresh
    if existing.sha256 and existing.sha256 != fresh.sha256:
        fresh.review = "unchecked"
        fresh.reviewer = ""
        fresh.notes = existing.notes
        fresh.redistributable = existing.redistributable
        return fresh
    fresh.review = existing.review or fresh.review
    fresh.reviewer = existing.reviewer
    fresh.notes = existing.notes
    fresh.redistributable = existing.redistributable or "unknown"
    return fresh
