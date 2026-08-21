# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
# Origin: python-scripts/doc_ocr in the author's `swarm` repository (same author, same tool).
"""Find source documents under docs/ and describe them.

Nothing here writes: discovery is pure inspection, so `scan` can report on the
corpus without touching a byte.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

SOURCE_SUFFIXES = (".pdf", ".docx")


@dataclass
class Source:
    """A document in the reference library."""

    path: Path
    rel: str  # repo-relative, the manifest key
    sha256: str
    size: int
    pages: int  # 0 when unknown (docx, or a PDF pdfinfo could not read)

    @property
    def is_pdf(self) -> bool:
        return self.path.suffix.lower() == ".pdf"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def page_count(pdf: Path) -> int:
    """Page count via pdfinfo, 0 if it cannot be determined."""
    try:
        out = subprocess.run(
            ["pdfinfo", str(pdf)], capture_output=True, text=True, errors="replace"
        ).stdout
    except FileNotFoundError:
        return 0
    for line in out.splitlines():
        if line.startswith("Pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return 0
    return 0


def discover(docs_root: Path, skip_dirs: tuple[str, ...] = ()) -> list[Source]:
    """Every source document under docs_root, sorted by path."""
    sources: list[Source] = []
    repo_root = docs_root.parent
    for path in sorted(docs_root.rglob("*")):
        if path.suffix.lower() not in SOURCE_SUFFIXES or not path.is_file():
            continue
        rel_parts = path.relative_to(docs_root).parts
        if rel_parts and rel_parts[0] in skip_dirs:
            continue
        sources.append(
            Source(
                path=path,
                rel=str(path.relative_to(repo_root)),
                sha256=sha256_of(path),
                size=path.stat().st_size,
                pages=page_count(path) if path.suffix.lower() == ".pdf" else 0,
            )
        )
    return sources


def sidecar_targets(source: Path) -> tuple[Path, Path]:
    """Where this source's output goes: (single-file sidecar, split directory).

    Only one of the two is ever created. Both sit next to the source, so a
    document gains exactly one sibling entry either way.
    """
    return (source.with_suffix(".ocr.md"), source.with_suffix(".ocr"))
