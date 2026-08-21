# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
# Origin: python-scripts/doc_ocr in the author's `swarm` repository (same author, same tool).
"""Unit tests for the reference-library extractor.

No PDF fixtures: the interesting logic is parsing, and the right unit boundary is
the captured output of pdftotext/mutool as text. The two mutool samples below are
real output from the corpus — RM0456 (page destinations, chapters at depth 1) and
the ESP32-S3 TRM (named destinations, chapters at depth 2 under parts), which are
the two shapes the outline parser has to handle.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from doc_ocr import extract, manifest, outline, sidecar

# --- fixtures: captured `mutool show <pdf> outline` -------------------------

RM0456_OUTLINE = (
    '|\t"Contents"\t#page=2&zoom=nan,67,87\n'
    '|\t"List of tables"\t#page=91&zoom=nan,67,87\n'
    '+\t"1 Documentation conventions"\t#page=127&zoom=nan,67,87\n'
    '|\t\t"1.1 General information"\t#page=127&zoom=nan,67,128\n'
    '+\t"2 Memory and bus architecture"\t#page=129&zoom=nan,67,87\n'
    '|\t\t"2.1 System architecture"\t#page=131&zoom=nan,67,128\n'
    '+\t"3 Flash"\t#page=200&zoom=nan,67,87\n'
)

TRM_OUTLINE = (
    '-\t"I Microprocessor and Master"\t#nameddest=part.1\n'
    '-\t\t"1 Processor Instruction Extensions (PIE)"\t#nameddest=chapter.1\n'
    '|\t\t\t"1.1 Overview"\t#nameddest=section.1.1\n'
    '-\t\t"2 ULP Coprocessor (ULP-FSM, ULP-RISC-V)"\t#nameddest=chapter.2\n'
    '|\t\t"3 GDMA Controller (GDMA)"\t#nameddest=chapter.3\n'
)


def parse(text: str) -> list[outline.Entry]:
    """Run the line parser over captured output without touching a PDF."""
    entries = []
    for line in text.splitlines():
        m = outline._LINE.match(line)
        assert m, f"unparsed outline line: {line!r}"
        _marker, tabs, title, dest = m.groups()
        page = None
        if pm := outline._PAGE_DEST.search(dest):
            page = int(pm.group(1))
        entries.append(outline.Entry(len(tabs), title.strip(), dest, page))
    return entries


# --- outline parsing --------------------------------------------------------


def test_parses_page_destinations():
    entries = parse(RM0456_OUTLINE)
    top = [e for e in entries if e.depth == 1]
    assert [e.title for e in top][:3] == ["Contents", "List of tables", "1 Documentation conventions"]
    assert [e.page for e in top] == [2, 91, 127, 129, 200]


def test_parses_all_three_marker_characters():
    """`|`, `+` and `-` all appear in the corpus; none may be dropped."""
    entries = parse(TRM_OUTLINE)
    assert len(entries) == 5
    assert entries[0].depth == 1 and entries[1].depth == 2


def test_named_destinations_carry_no_page():
    entries = parse(TRM_OUTLINE)
    assert all(e.page is None for e in entries)


# --- adaptive depth ---------------------------------------------------------


def test_choose_depth_picks_chapters_not_parts():
    """The TRM nests chapters under 6 parts; depth 1 would give 6 huge files."""
    entries = [outline.Entry(1, f"part {i}", "") for i in range(6)]
    entries += [outline.Entry(2, f"chapter {i}", "") for i in range(44)]
    assert outline.choose_depth(entries, min_entries=8, max_entries=500) == 2


def test_choose_depth_returns_none_when_outline_is_too_thin():
    entries = [outline.Entry(1, f"c{i}", "") for i in range(3)]
    assert outline.choose_depth(entries, min_entries=8, max_entries=500) is None


# --- page resolution via the running-header band ----------------------------


def test_resolve_pages_ignores_the_table_of_contents():
    """The TOC lists every chapter title; naive matching sends them all to page 2."""
    toc = "Contents\n\n1 Alpha Chapter .... 10\n2 Beta Chapter .... 20\n"
    pages = [
        "Cover",
        toc,
        "Chapter 1 Alpha Chapter\n\nbody text about alpha",
        "Chapter 1 Alpha Chapter\n\nmore alpha",
        "Chapter 2 Beta Chapter\n\nbody text about beta",
    ]
    entries = [
        outline.Entry(1, "1 Alpha Chapter", "#nameddest=chapter.1"),
        outline.Entry(1, "2 Beta Chapter", "#nameddest=chapter.2"),
    ]
    assert outline.resolve_pages(entries, pages) == 0
    assert [e.page for e in entries] == [3, 5]


def test_resolve_pages_reports_unresolved():
    entries = [outline.Entry(1, "Nowhere To Be Found", "#nameddest=x")]
    assert outline.resolve_pages(entries, ["a", "b"]) == 1
    assert entries[0].page is None


def test_header_zone_only_reads_the_top_of_the_page():
    page = "Running Header\n\nbody\n" + "\n".join(f"line {i}" for i in range(40))
    zone = outline.header_zone(page)
    assert "running header" in zone
    assert "line 30" not in zone


# --- splitting --------------------------------------------------------------


def test_chapter_parts_tile_the_document_with_no_gaps():
    entries = [
        outline.Entry(1, "One", "", page=10),
        outline.Entry(1, "Two", "", page=20),
        outline.Entry(1, "Three", "", page=30),
    ]
    parts = outline.chapter_parts(entries, depth=1, pages=45)
    assert [(p.first, p.last) for p in parts] == [(1, 9), (10, 19), (20, 29), (30, 45)]
    assert parts[0].title == "Front matter"  # pages before chapter 1 are not dropped


def test_chapter_parts_merges_entries_sharing_a_start_page():
    entries = [
        outline.Entry(1, "One", "", page=1),
        outline.Entry(1, "Also One", "", page=1),
        outline.Entry(1, "Two", "", page=5),
    ]
    parts = outline.chapter_parts(entries, depth=1, pages=9)
    assert len(parts) == 2
    assert parts[0].title == "One · Also One"
    assert (parts[0].first, parts[0].last) == (1, 4)


def test_block_parts_cover_every_page():
    parts = outline.block_parts(pages=450, block=200)
    assert [(p.first, p.last) for p in parts] == [(1, 200), (201, 400), (401, 450)]


def test_slugify():
    assert outline.slugify("2 ULP Coprocessor (ULP-FSM, ULP-RISC-V)") == "2-ulp-coprocessor-ulp-fsm-ulp-risc-v"
    assert outline.slugify("!!!") == "part"


# --- extraction heuristics --------------------------------------------------


def test_chars_per_page_averages_over_the_whole_document():
    """Empty cover pages must not drag a good document below the OCR threshold."""
    pages = ["", "", ""] + ["x" * 3000 for _ in range(97)]
    assert extract.chars_per_page(pages) == pytest.approx(2910, abs=5)


def test_chars_per_page_of_nothing_is_zero():
    assert extract.chars_per_page([]) == 0


# --- sidecar rendering ------------------------------------------------------


def test_front_matter_round_trip():
    fields = {"source": "a.pdf", "pages": 60, "reviewer": None, "figures": []}
    parsed = sidecar.parse_front_matter(sidecar.render_front_matter(fields) + "\nbody")
    assert parsed["source"] == "a.pdf"
    assert parsed["pages"] == "60"
    assert parsed["reviewer"] == "null"


def test_render_body_marks_pages_with_their_real_numbers():
    body = sidecar.render_body(["first", "second"], first_page=27)
    assert "=== p.27 ===" in body
    assert "=== p.28 ===" in body


def test_fence_grows_past_backticks_in_the_source_text():
    body = sidecar.render_body(["a ``` b ```` c"])
    assert body.startswith("`````text")


def test_write_refuses_to_clobber_human_notes(tmp_path):
    doc = sidecar.SidecarDoc(title="t", front={}, body="b")
    with pytest.raises(ValueError, match="human-owned"):
        sidecar.write(tmp_path / "thing_notes.md", doc)


def test_read_review_flag(tmp_path):
    path = tmp_path / "x.ocr.md"
    sidecar.write(path, sidecar.SidecarDoc(title="t", front={"review": "checked"}, body="b"))
    assert sidecar.read_review_flag(path) == "checked"
    assert sidecar.read_review_flag(tmp_path / "absent.ocr.md") is None


# --- the ledger -------------------------------------------------------------


def test_manifest_round_trip(tmp_path):
    path = tmp_path / "manifest.tsv"
    rows = {
        "docs/a.pdf": manifest.Row(source="docs/a.pdf", sha256="aa", pages=10, review="checked"),
        "docs/b.pdf": manifest.Row(source="docs/b.pdf", sha256="bb", pages=20),
    }
    manifest.save(path, rows)
    back = manifest.load(path)
    assert back["docs/a.pdf"].review == "checked"
    assert back["docs/a.pdf"].pages == 10
    assert back["docs/b.pdf"].review == "unchecked"


def test_manifest_strips_tabs_that_would_corrupt_a_row(tmp_path):
    path = tmp_path / "manifest.tsv"
    manifest.save(path, {"a": manifest.Row(source="a", notes="has\ttab\nand newline")})
    assert len(manifest.load(path)) == 1
    assert manifest.load(path)["a"].notes == "has tab and newline"


def test_review_flag_survives_regeneration_of_an_unchanged_source():
    existing = manifest.Row(source="a", sha256="aa", review="checked", reviewer="AG")
    fresh = manifest.Row(source="a", sha256="aa", extracted_utc="now")
    merged = manifest.merge(existing, fresh)
    assert merged.review == "checked"
    assert merged.reviewer == "AG"
    assert merged.extracted_utc == "now"


def test_changed_source_resets_the_review_flag():
    """A silently revised vendor PDF must not keep somebody's old verification."""
    existing = manifest.Row(source="a", sha256="aa", review="checked", reviewer="AG", notes="keep")
    fresh = manifest.Row(source="a", sha256="bb")
    merged = manifest.merge(existing, fresh)
    assert merged.review == "unchecked"
    assert merged.reviewer == ""
    assert merged.notes == "keep"


def test_merge_with_no_existing_row_is_the_fresh_row():
    fresh = manifest.Row(source="a", sha256="aa")
    assert manifest.merge(None, fresh) is fresh


# --- docx path --------------------------------------------------------------

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _docx(tmp_path: Path) -> Path:
    """A minimal .docx with one paragraph and one 2x2 table."""
    def cell(text):
        return f'<w:tc><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:tc>'

    xml = (
        f'<w:document xmlns:w="{W}"><w:body>'
        "<w:p><w:r><w:t>Pin assignments</w:t></w:r></w:p>"
        "<w:tbl>"
        f"<w:tr>{cell('Signal')}{cell('GPIO')}</w:tr>"
        f"<w:tr>{cell('LORA_SCK')}{cell('IO12')}</w:tr>"
        "</w:tbl>"
        "</w:body></w:document>"
    )
    path = tmp_path / "sample.docx"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", xml)
    return path


def test_docx_tables_stay_tables(tmp_path):
    """extract_docx.py flattened cells one per line, destroying the T-Beam pin map."""
    md = extract.docx_to_markdown(_docx(tmp_path))
    assert "Pin assignments" in md
    assert "| Signal | GPIO |" in md
    assert "|---|---|" in md
    assert "| LORA_SCK | IO12 |" in md
