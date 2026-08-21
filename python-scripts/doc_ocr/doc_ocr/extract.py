# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
# Origin: python-scripts/doc_ocr in the author's `swarm` repository (same author, same tool).
"""Getting text out of a source document.

The corpus survey that motivated this tool found 79 of 81 PDFs already carry a
text layer, so `pdftotext -layout` is the main path and it is very good: it
reproduces the BME280 memory map with its columns intact, which is the whole
point for register maps and pin tables. OCR is a fallback for the one genuine
scan, and it runs by OCR-ing into a throwaway copy in scratch/ and then reading
that copy with the same code path — the vendor PDF is never modified.
"""

from __future__ import annotations

import logging
import subprocess
import zipfile
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree

log = logging.getLogger(__name__)

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class ExtractionError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def poppler_version() -> str:
    try:
        proc = subprocess.run(
            ["pdftotext", "-v"], capture_output=True, text=True, errors="replace"
        )
    except FileNotFoundError as exc:  # pragma: no cover - environment problem
        raise ExtractionError("pdftotext not found; install poppler-utils") from exc
    first = (proc.stderr or proc.stdout).splitlines()[0] if (proc.stderr or proc.stdout) else ""
    return first.replace("pdftotext version ", "poppler ").strip() or "poppler"


def pdf_pages_text(pdf: Path) -> list[str]:
    """Per-page text for the whole document, one pdftotext call.

    Pages come back form-feed separated; splitting once here means chapter
    slicing later is free.
    """
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", "-q", str(pdf), "-"],
            capture_output=True,
            text=True,
            errors="replace",
        )
    except FileNotFoundError as exc:  # pragma: no cover - environment problem
        raise ExtractionError("pdftotext not found; install poppler-utils") from exc
    pages = proc.stdout.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def chars_per_page(pages: list[str]) -> int:
    """Average non-whitespace characters per page.

    Measured across the whole document on purpose. Sampling the first few pages
    misreports title/cover pages as scans — it flagged the FreeRTOS book, which
    has a perfectly good text layer starting a few pages in.
    """
    if not pages:
        return 0
    total = sum(len("".join(p.split())) for p in pages)
    return total // len(pages)


def ocr_to_pages(pdf: Path, scratch_dir: Path, lang: str = "eng") -> list[str]:
    """OCR a scanned PDF and return its per-page text.

    Writes the OCR'd PDF into scratch/ and reads that; the original is untouched.
    """
    scratch_dir.mkdir(parents=True, exist_ok=True)
    tmp_pdf = scratch_dir / (pdf.stem + ".ocr.pdf")
    # --force-ocr, not --skip-text: we only get here because the existing text
    # layer was judged inadequate, and --skip-text would honour that bad layer and
    # OCR nothing. --force-ocr rasterizes and replaces it.
    cmd = [
        "ocrmypdf",
        "--quiet",
        "--force-ocr",
        "--language",
        lang,
        str(pdf),
        str(tmp_pdf),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    except FileNotFoundError as exc:
        raise ExtractionError("ocrmypdf not found; install ocrmypdf + tesseract") from exc
    if proc.returncode != 0 or not tmp_pdf.is_file():
        raise ExtractionError(f"ocrmypdf failed for {pdf.name}: {proc.stderr.strip()[:400]}")
    try:
        return pdf_pages_text(tmp_pdf)
    finally:
        tmp_pdf.unlink(missing_ok=True)


def _cell_text(cell: ElementTree.Element) -> str:
    parts = []
    for para in cell.iter(f"{W_NS}p"):
        parts.append("".join(t.text or "" for t in para.iter(f"{W_NS}t")))
    return " ".join(p.strip() for p in parts if p.strip())


def docx_to_markdown(path: Path) -> str:
    """Flatten a .docx to markdown, keeping tables as tables.

    python-scripts/extract_docx.py collapses every table cell onto its own line,
    which destroyed the T-Beam pin map that ADR 0014 depends on. Walking the body
    in document order and emitting <w:tbl> as a markdown table fixes that.
    """
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    body = root.find(f"{W_NS}body")
    if body is None:
        return ""

    out: list[str] = []
    for node in body:
        if node.tag == f"{W_NS}p":
            text = "".join(t.text or "" for t in node.iter(f"{W_NS}t")).strip()
            if text:
                out.append(text)
                out.append("")
        elif node.tag == f"{W_NS}tbl":
            rows = [
                [_cell_text(tc) for tc in tr.findall(f"{W_NS}tc")]
                for tr in node.findall(f"{W_NS}tr")
            ]
            rows = [r for r in rows if any(c for c in r)]
            if not rows:
                continue
            width = max(len(r) for r in rows)
            rows = [r + [""] * (width - len(r)) for r in rows]
            header, *rest = rows
            out.append("| " + " | ".join(c.replace("|", "\\|") for c in header) + " |")
            out.append("|" + "|".join(["---"] * width) + "|")
            for row in rest:
                out.append("| " + " | ".join(c.replace("|", "\\|") for c in row) + " |")
            out.append("")
    return "\n".join(out).strip() + "\n"
