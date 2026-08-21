# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
# Origin: python-scripts/doc_ocr in the author's `swarm` repository (same author, same tool).
"""Bookmark outlines, and turning them into page ranges.

`mutool show <pdf> outline` emits one line per bookmark:

    |\t"Contents"\t#page=2&zoom=nan,67,87
    +\t"2 Memory and bus architecture"\t#page=129&zoom=nan,67,87
    -\t\t"1 Processor Instruction Extensions (PIE)"\t#nameddest=chapter.1

Three things vary across the corpus and all three matter:

* the leading marker is `|`, `+` or `-` (leaf / has-children / open);
* depth is the number of tabs before the title;
* the destination is either `#page=N` or `#nameddest=...`, which carries no page
  number at all. The ESP32-S3 technical reference manual — the most important
  datasheet in the project — uses nameddest, so a `#page=` only parser silently
  fails on it.

It also nests chapters under six roman-numeral *parts*, so splitting at depth 1
would produce six enormous files. Hence choose_depth(): take the shallowest depth
that actually looks like a chapter list.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

# marker, tabs (depth), quoted title, destination
_LINE = re.compile(r'^([|+\-])(\t+)"(.*)"\t([^\t]*)$')
_PAGE_DEST = re.compile(r"#page=(\d+)")
_WS = re.compile(r"\s+")

# How many non-blank lines at the top of a page count as the running header.
HEADER_LINES = 3
# "1 Alpha Chapter ......... 10" — a contents entry, never a running header. On a
# long manual the TOC sits well below the header band anyway, but a short contents
# page would otherwise land inside it.
_TOC_LINE = re.compile(r"\.{2,}\s*\d+\s*$")


@dataclass
class Entry:
    depth: int
    title: str
    dest: str
    page: int | None = None


def read_outline(pdf: Path) -> list[Entry]:
    """Parse `mutool show ... outline`. Empty list when there are no bookmarks."""
    try:
        proc = subprocess.run(
            ["mutool", "show", str(pdf), "outline"],
            capture_output=True,
            text=True,
            errors="replace",
        )
    except FileNotFoundError:
        return []
    entries: list[Entry] = []
    for line in proc.stdout.splitlines():
        m = _LINE.match(line)
        if not m:
            continue
        _marker, tabs, title, dest = m.groups()
        page = None
        if pm := _PAGE_DEST.search(dest):
            page = int(pm.group(1))
        entries.append(Entry(depth=len(tabs), title=title.strip(), dest=dest, page=page))
    return entries


def choose_depth(entries: list[Entry], min_entries: int, max_entries: int) -> int | None:
    """Shallowest depth holding a plausible chapter list, or None.

    RM0456 resolves to depth 1 (82 chapters). The ESP32-S3 TRM resolves to depth 2,
    because depth 1 is only its six parts.
    """
    counts = Counter(e.depth for e in entries)
    for depth in sorted(counts):
        if min_entries <= counts[depth] <= max_entries:
            return depth
    return None


def normalize(text: str) -> str:
    return _WS.sub(" ", text).strip().lower()


def header_zone(page: str, lines: int = HEADER_LINES) -> str:
    """The running-header band at the top of a page, normalized."""
    kept = [
        line
        for line in page.splitlines()
        if line.strip() and not _TOC_LINE.search(line)
    ][:lines]
    return normalize(" \n ".join(kept))


def resolve_pages(entries: list[Entry], pages_text: list[str]) -> int:
    """Fill in .page for entries that only had a named destination.

    Returns the number still unresolved. The obvious approach — search the page
    text for the outline title — fails badly: the table of contents lists every
    chapter title, so first-match sends all 44 chapters of the ESP32-S3 TRM to
    pages 4-10. Searching only the running-header band fixes it, because a
    typeset manual repeats "Chapter 3 GDMA Controller (GDMA)" at the top of every
    page of that chapter while contents pages carry their own header. That takes
    the TRM from 5/44 resolved to 44/44.
    """
    targets = [e for e in entries if e.page is None]
    if not targets:
        return 0

    zones = [header_zone(p) for p in pages_text]

    # Anchor to whatever the #page= entries already established, then only ever
    # move forward: chapters do not go backwards.
    known = [e.page for e in entries if e.page is not None]
    cursor = max(0, min(known) - 1) if known else 0

    unresolved = 0
    for entry in targets:
        title = normalize(entry.title)
        found = None
        if title:
            for i in range(cursor, len(zones)):
                if title in zones[i]:
                    found = i
                    break
        if found is None:
            unresolved += 1
            continue
        entry.page = found + 1  # pages are 1-based
        cursor = found
    return unresolved


def slugify(title: str, fallback: str = "part") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return (slug or fallback)[:60]


@dataclass
class Part:
    """One output file of a split document."""

    title: str
    slug: str
    first: int  # 1-based, inclusive
    last: int  # 1-based, inclusive


def chapter_parts(entries: list[Entry], depth: int, pages: int) -> list[Part]:
    """Page ranges for every entry at `depth`, each running to the next one.

    Every page of the document lands in exactly one part. Two details keep that
    true: entries sharing a start page are merged rather than dropped (dropping
    them would leave a hole), and anything before the first chapter — cover, TOC,
    release notes — becomes a leading "Front matter" part instead of vanishing.
    """
    chosen = [e for e in entries if e.depth == depth and e.page]
    chosen.sort(key=lambda e: e.page or 0)
    if not chosen:
        return []

    # Merge entries that start on the same page into one titled part.
    merged: list[tuple[int, str]] = []
    for entry in chosen:
        page = entry.page or 1
        if merged and merged[-1][0] == page:
            merged[-1] = (page, f"{merged[-1][1]} · {entry.title}")
        else:
            merged.append((page, entry.title))

    spans: list[tuple[str, int, int]] = []
    if merged[0][0] > 1:
        spans.append(("Front matter", 1, merged[0][0] - 1))
    for i, (page, title) in enumerate(merged):
        last = merged[i + 1][0] - 1 if i + 1 < len(merged) else pages
        if last >= page:
            spans.append((title, page, min(last, pages)))

    return [
        Part(title=title, slug=f"{i + 1:02d}-{slugify(title)}", first=first, last=last)
        for i, (title, first, last) in enumerate(spans)
    ]


def block_parts(pages: int, block: int) -> list[Part]:
    """Fixed-size page blocks, for long documents with no usable outline."""
    parts: list[Part] = []
    for first in range(1, pages + 1, block):
        last = min(first + block - 1, pages)
        parts.append(
            Part(
                title=f"Pages {first}–{last}",
                slug=f"{len(parts) + 1:02d}-p{first:04d}-{last:04d}",
                first=first,
                last=last,
            )
        )
    return parts
