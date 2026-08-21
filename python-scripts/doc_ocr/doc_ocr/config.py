# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
# Origin: python-scripts/doc_ocr in the author's `swarm` repository (same author, same tool).
"""Runtime configuration for the reference-library extractor.

Defaults come from environment variables (DOC_OCR_* prefix); the CLI in
__main__.py overrides them per invocation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _repo_root() -> Path:
    """Locate the repo root when running from the source tree.

    Layout: <repo>/python-scripts/doc_ocr/doc_ocr/config.py
    """
    return Path(__file__).resolve().parents[3]


def _default_docs_root() -> Path:
    return Path(os.environ.get("DOC_OCR_DOCS", _repo_root() / "docs"))


def _default_manifest() -> Path:
    return Path(os.environ.get("DOC_OCR_MANIFEST", _repo_root() / "docs" / "OCR" / "manifest.tsv"))


def _default_scratch() -> Path:
    # scratch/ is gitignored; OCR needs somewhere to drop its rewritten PDF, which
    # we throw away — the original vendor PDF is never modified.
    return Path(os.environ.get("DOC_OCR_SCRATCH", _repo_root() / "scratch" / "doc_ocr"))


@dataclass
class Settings:
    docs_root: Path = field(default_factory=_default_docs_root)
    manifest_path: Path = field(default_factory=_default_manifest)
    scratch_dir: Path = field(default_factory=_default_scratch)

    # Split documents longer than this into per-chapter parts.
    split_threshold: int = int(os.environ.get("DOC_OCR_SPLIT_PAGES", "250"))
    # Fixed block size when a long document has no usable outline.
    block_pages: int = int(os.environ.get("DOC_OCR_BLOCK_PAGES", "200"))
    # Shallowest outline depth with at least this many entries wins.
    min_outline_entries: int = int(os.environ.get("DOC_OCR_MIN_OUTLINE", "8"))
    max_outline_entries: int = int(os.environ.get("DOC_OCR_MAX_OUTLINE", "500"))
    # Below this many characters per page the text layer is judged inadequate.
    # The corpus separates cleanly: the one image-only document sits at 119
    # chars/page (a thin caption-only layer over scanned artwork) and the next
    # sparsest real text document at 620, so 300 splits them with room either way.
    ocr_chars_per_page: int = int(os.environ.get("DOC_OCR_MIN_CHARS", "300"))
    ocr_lang: str = os.environ.get("DOC_OCR_LANG", "eng")

    # Directories under docs_root that are never scanned.
    skip_dirs: tuple[str, ...] = ("reference-projects", "OCR")
