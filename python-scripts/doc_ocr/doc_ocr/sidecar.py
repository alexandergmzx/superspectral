# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
# Origin: python-scripts/doc_ocr in the author's `swarm` repository (same author, same tool).
"""Rendering and reading the markdown sidecars.

Body text goes inside a fenced block so column-aligned tables survive, with
`=== p.N ===` markers between pages. The markers are the point: Alexander cites
datasheet pages when arguing for a design choice, so a grep hit has to say which
page of the PDF to open.

YAML front matter is deliberately hand-rolled — the tool has no third-party
dependencies, and these files are gitignored generated artefacts, so introducing
front matter here sets no precedent for the curated docs (which use none).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

PAGE_MARKER = "=== p.{n} ==="
_MARKER_RE = re.compile(r"^=== p\.(\d+) ===$", re.MULTILINE)
_BACKTICKS = re.compile(r"`+")


def _fence_for(text: str) -> str:
    """A fence longer than any backtick run in the body, so nothing is mangled."""
    longest = max((len(m.group(0)) for m in _BACKTICKS.finditer(text)), default=0)
    return "`" * max(3, longest + 1)


def render_front_matter(fields: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, int):
            lines.append(f"{key}: {value}")
        elif isinstance(value, (list, tuple)):
            lines.append(f"{key}: []" if not value else f"{key}: {list(value)}")
        else:
            text = str(value).replace('"', "'")
            lines.append(f'{key}: "{text}"')
    lines.append("---")
    return "\n".join(lines)


def parse_front_matter(text: str) -> dict[str, str]:
    """Scalar front-matter fields of an existing sidecar.

    Only used to notice a review flag a human flipped by hand in the file rather
    than through the CLI.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fields: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip('"')
    return fields


def read_review_flag(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4096]
    except OSError:
        return None
    return parse_front_matter(head).get("review")


def render_body(pages: list[str], first_page: int = 1) -> str:
    """Page-marked text inside one fence."""
    chunks: list[str] = []
    for offset, page in enumerate(pages):
        chunks.append(PAGE_MARKER.format(n=first_page + offset))
        chunks.append(page.rstrip("\n"))
    text = "\n".join(chunks).strip("\n")
    fence = _fence_for(text)
    return f"{fence}text\n{text}\n{fence}\n"


@dataclass
class SidecarDoc:
    title: str
    front: dict[str, object]
    body: str
    intro: str = ""

    def render(self) -> str:
        parts = [render_front_matter(self.front), "", f"# {self.title}", ""]
        if self.intro:
            parts += [self.intro, ""]
        parts.append(self.body)
        return "\n".join(parts)


def write(path: Path, doc: SidecarDoc) -> int:
    """Write a sidecar, refusing to clobber human-owned files."""
    if path.name.endswith("_notes.md"):
        raise ValueError(f"refusing to write human-owned notes file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = doc.render()
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def index_table(parts: list[tuple[str, str, int, int]]) -> str:
    """TOC for a split document: (filename, title, first page, last page)."""
    rows = ["| Part | Pages | Section |", "|---|---|---|"]
    for filename, title, first, last in parts:
        safe = title.replace("|", "\\|")
        rows.append(f"| [`{filename}`](./{filename}) | {first}–{last} | {safe} |")
    return "\n".join(rows)
