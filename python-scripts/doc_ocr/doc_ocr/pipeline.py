# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
# Origin: python-scripts/doc_ocr in the author's `swarm` repository (same author, same tool).
"""Orchestration: source document in, sidecar(s) and a ledger row out."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import extract, manifest, outline, sidecar
from .config import Settings
from .discover import Source, sidecar_targets

log = logging.getLogger(__name__)


@dataclass
class Result:
    source: Source
    status: str  # created | refreshed | skipped | reset | failed
    layout: str = ""  # single | split | none
    parts: int = 0
    bytes_written: int = 0
    message: str = ""
    row: manifest.Row | None = None  # ledger row to merge back, None when unchanged


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sidecar_present(source: Path) -> bool:
    single, split = sidecar_targets(source)
    return single.is_file() or (split.is_dir() and (split / "_index.md").is_file())


def _clear_targets(source: Path) -> None:
    single, split = sidecar_targets(source)
    single.unlink(missing_ok=True)
    if split.is_dir() and split.name.endswith(".ocr"):
        shutil.rmtree(split)


def _base_front(src: Source, row: manifest.Row) -> dict[str, object]:
    return {
        "source": src.path.name,
        "source_sha256": src.sha256,
        "pages": src.pages,
        "chars_per_page": row.chars_per_page,
        "extractor": row.extractor,
        "extracted_utc": row.extracted_utc,
        "review": row.review,
        "reviewer": row.reviewer or None,
        "redistributable": row.redistributable,
        "figures": [],  # reserved for v2 (see docs/OCR/README.md)
        "notes": row.notes,
    }


def _plan_layout(
    src: Source, pages_text: list[str], settings: Settings
) -> tuple[str, list[outline.Part]]:
    """Decide single file vs split, and where the splits fall."""
    if src.pages <= settings.split_threshold:
        return "single", []

    entries = outline.read_outline(src.path)
    if entries:
        depth = outline.choose_depth(
            entries, settings.min_outline_entries, settings.max_outline_entries
        )
        if depth is not None:
            at_depth = [e for e in entries if e.depth == depth]
            unresolved = outline.resolve_pages(at_depth, pages_text)
            if unresolved <= max(1, len(at_depth) // 3):
                parts = outline.chapter_parts(entries, depth, src.pages)
                if len(parts) >= 2:
                    return "split", parts
            log.info(
                "%s: outline unusable (%d/%d entries unresolved), using page blocks",
                src.path.name,
                unresolved,
                len(at_depth),
            )
    return "split", outline.block_parts(src.pages, settings.block_pages)


def process(src: Source, settings: Settings, row: manifest.Row | None, force: bool) -> Result:
    """Extract one document unless it is already up to date."""
    present = sidecar_present(src.path)
    changed = row is not None and row.sha256 and row.sha256 != src.sha256
    if row is not None and not changed and present and not force:
        # The flag may have been flipped by editing the sidecar rather than via
        # `doc_ocr check`; fold that back into the ledger, which is the file that
        # actually survives.
        single, split = sidecar_targets(src.path)
        flag = sidecar.read_review_flag(single if single.is_file() else split / "_index.md")
        if flag in manifest.REVIEW_STATES and flag != row.review:
            updated = manifest.Row(**{**vars(row), "review": flag})
            return Result(src, "skipped", row.layout, row.parts, row=updated)
        return Result(src, "skipped", row.layout, row.parts)

    try:
        extractor = ""
        if src.is_pdf:
            pages_text = extract.pdf_pages_text(src.path)
            cpp = extract.chars_per_page(pages_text)
            extractor = f"pdftotext -layout ({extract.poppler_version()})"
            if cpp < settings.ocr_chars_per_page:
                log.info("%s: %d chars/page, falling back to OCR", src.path.name, cpp)
                pages_text = extract.ocr_to_pages(src.path, settings.scratch_dir, settings.ocr_lang)
                cpp = extract.chars_per_page(pages_text)
                extractor = f"ocrmypdf --language {settings.ocr_lang} + {extractor}"
        else:
            pages_text = [extract.docx_to_markdown(src.path)]
            cpp = extract.chars_per_page(pages_text)
            extractor = "docx (zipfile/ElementTree, table-aware)"
    except extract.ExtractionError as exc:
        return Result(src, "failed", message=str(exc))

    fresh = manifest.Row(
        source=src.rel,
        sha256=src.sha256,
        pages=src.pages,
        chars_per_page=cpp,
        extractor=extractor,
        extracted_utc=_utc_now(),
    )
    merged = manifest.merge(row, fresh)

    layout, parts = _plan_layout(src, pages_text, settings)
    _clear_targets(src.path)
    single_target, split_target = sidecar_targets(src.path)
    written = 0

    if layout == "single":
        front = _base_front(src, merged)
        front["chars_per_page"] = cpp
        front["extractor"] = extractor
        front["extracted_utc"] = merged.extracted_utc
        body = (
            sidecar.render_body(pages_text)
            if src.is_pdf
            else pages_text[0]
        )
        written = sidecar.write(
            single_target,
            sidecar.SidecarDoc(
                title=src.path.name,
                front=front,
                body=body,
                intro=f"Machine extraction of [`{src.path.name}`](./{src.path.name}). "
                "Generated file — edits are lost on regeneration; durable notes belong in "
                f"`{src.path.stem}_notes.md`.",
            ),
        )
        merged.layout, merged.parts = "single", 1
    else:
        index_rows: list[tuple[str, str, int, int]] = []
        for part in parts:
            filename = f"{part.slug}.md"
            front = _base_front(src, merged)
            front["chars_per_page"] = cpp
            front["extractor"] = extractor
            front["extracted_utc"] = merged.extracted_utc
            front["part"] = filename
            front["part_title"] = part.title
            front["page_first"] = part.first
            front["page_last"] = part.last
            written += sidecar.write(
                split_target / filename,
                sidecar.SidecarDoc(
                    title=f"{part.title} — {src.path.name}",
                    front=front,
                    body=sidecar.render_body(
                        pages_text[part.first - 1 : part.last], first_page=part.first
                    ),
                    intro=f"Pages {part.first}–{part.last}. Index: [`_index.md`](./_index.md).",
                ),
            )
            index_rows.append((filename, part.title, part.first, part.last))

        front = _base_front(src, merged)
        front["chars_per_page"] = cpp
        front["extractor"] = extractor
        front["extracted_utc"] = merged.extracted_utc
        front["parts"] = len(parts)
        rel_pdf = f"../{src.path.name}"
        written += sidecar.write(
            split_target / "_index.md",
            sidecar.SidecarDoc(
                title=f"{src.path.name} — extraction index",
                front=front,
                body=sidecar.index_table(index_rows),
                intro=f"Machine extraction of [`{src.path.name}`]({rel_pdf}), split into "
                f"{len(parts)} parts across {src.pages} pages.",
            ),
        )
        merged.layout, merged.parts = "split", len(parts)

    status = "reset" if changed else ("refreshed" if row is not None else "created")
    return Result(src, status, merged.layout, merged.parts, written, row=merged)
