#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""Relative-link checker for the tracked text files in this repository.

CI runs `lycheeverse/lychee-action --offline` (.github/workflows/ci.yml); this is
the same check with no install, for use before a commit and in unattended
sessions:

    python3 python-scripts/check_links.py            # every non-ignored file, exit 1 if broken
    python3 python-scripts/check_links.py docs/adr   # limit to a subtree

What it checks, in every `.md`, `.yaml`, `.yml` and `.json` file that git would show
(tracked, or untracked and not ignored):

1. every relative Markdown link and image target resolves to an existing path;
2. every `#anchor` on a link into a Markdown file matches a heading in that file,
   under GitHub's slug rules (lowercase, punctuation dropped, spaces to hyphens,
   `-1`/`-2` suffixes for duplicates) -- a link that resolves to the right file and
   the wrong section is a defect a path check cannot see.

Untracked files are included on purpose: a link check that only sees staged files
passes on a file that was never added. Non-Markdown files are included because the
schemas and manifests carry links too (`host/golden/manifest.schema.yaml` is full of
them) and nothing else checks them. Absolute URLs and `mailto:` are out of scope
(lychee checks those online; we do not, in an unattended session).

Failures are reported as `path:line`, which is what makes them clickable.

Two things it deliberately does NOT flag, because both are correct Markdown that
a naive regex misreads:

* links inside **inline code spans** — `` `![fig](figures/p0027-fig01.png)` `` in
  docs/OCR/README.md is documentation of a planned output format, not a link;
* links inside **fenced code blocks**, for the same reason.

Exit status: 0 when nothing is broken, 1 otherwise (so it can gate a commit).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import urllib.parse

LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
# `[^0-9.x](19|20)` in a YAML-embedded regex is Markdown link syntax by accident.
# A relative link target never contains these.
NOT_A_PATH = re.compile(r"[|^$\\+*?{}]")
FENCE = re.compile(r"^\s*(```|~~~)")
SKIP_SCHEME = re.compile(r"^(https?:|mailto:|ftp:|<)")
ATX = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
SUFFIXES = (".md", ".yaml", ".yml", ".json")
# GitHub's slugger: strip inline markup, drop everything that is not a word
# character, space or hyphen, lowercase, spaces -> hyphens.
SLUG_STRIP = re.compile(r"[^\w\s-]", re.UNICODE)
INLINE_MD = re.compile(r"`([^`]*)`|\*\*([^*]*)\*\*|\*([^*]*)\*|\[([^\]]*)\]\([^)]*\)")


def _strip_code(text: str) -> str:
    """Blank out fenced blocks and inline code spans, preserving line count."""
    out, in_fence = [], False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else re.sub(r"`[^`]*`", "``", line))
    return "\n".join(out)


def slug(heading: str) -> str:
    """GitHub's heading -> anchor transformation."""
    text = INLINE_MD.sub(lambda m: next(g for g in m.groups() if g is not None), heading)
    text = SLUG_STRIP.sub("", text).strip().lower()
    # One hyphen per space, NOT one per run: GitHub turns "A — B" into "a--b"
    # because the em dash is dropped and both surrounding spaces survive.
    return re.sub(r"\s", "-", text)


def anchors_of(path: str) -> set[str]:
    """Every anchor a Markdown file offers: heading slugs (with GitHub's -1/-2
    disambiguation) plus explicit `<a name=>` / `id=` attributes."""
    try:
        text = open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        return set()
    found, seen = set(), {}
    in_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = ATX.match(line)
        if m:
            base = slug(m.group(2))
            if not base:
                continue
            n = seen.get(base, 0)
            seen[base] = n + 1
            found.add(base if n == 0 else f"{base}-{n}")
    for m in re.finditer(r"(?:name|id)=[\"\']([^\"\']+)[\"\']", text):
        found.add(m.group(1))
    return found


def repo_files(root: str, subtree: str | None) -> list[str]:
    """Tracked *and* untracked-but-not-ignored text files, so a file is checked the
    moment it is written rather than only after it is staged."""
    args = ["git", "-C", root, "ls-files", "--cached", "--others", "--exclude-standard"]
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout.split()
    files = sorted({f for f in out if f.endswith(SUFFIXES)})
    if subtree:
        # A second pathspec would UNION with "*.md", not intersect it - filter here.
        prefix = subtree.rstrip("/") + "/"
        files = [f for f in files if f == subtree or f.startswith(prefix)]
    return files


def check(root: str, subtree: str | None = None) -> int:
    broken = 0
    anchor_cache: dict[str, set[str]] = {}
    files = repo_files(root, subtree)
    for rel in files:
        path = os.path.join(root, rel)
        try:
            text = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError) as exc:  # pragma: no cover - unreadable file
            print(f"UNREADABLE {rel}: {exc}")
            broken += 1
            continue
        stripped = _strip_code(text)
        for match in LINK.finditer(stripped):
            raw = match.group(1)
            if SKIP_SCHEME.match(raw) or NOT_A_PATH.search(raw):
                continue
            line_no = stripped.count("\n", 0, match.start()) + 1
            file_part, _, anchor = raw.partition("#")
            file_part = urllib.parse.unquote(file_part)
            anchor = urllib.parse.unquote(anchor)
            resolved = (os.path.join(os.path.dirname(path), file_part)
                        if file_part else path)
            if file_part and not os.path.exists(resolved):
                print(f"BROKEN {rel}:{line_no} -> {raw}")
                broken += 1
                continue
            if anchor and resolved.endswith(".md"):
                key = os.path.realpath(resolved)
                if key not in anchor_cache:
                    anchor_cache[key] = anchors_of(resolved)
                if anchor_cache[key] and anchor not in anchor_cache[key]:
                    print(f"BAD ANCHOR {rel}:{line_no} -> {raw} "
                          f"(no heading slugs to '{anchor}')")
                    broken += 1
    print(f"{len(files)} files checked, {broken} broken")
    return 1 if broken else 0


if __name__ == "__main__":
    repo = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    ).stdout.strip()
    sys.exit(check(repo, sys.argv[1] if len(sys.argv) > 1 else None))
