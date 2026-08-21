#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""Relative-link checker for the tracked Markdown in this repository.

CI runs `lycheeverse/lychee-action --offline` (.github/workflows/ci.yml); this is
the same check with no install, for use before a commit and in unattended
sessions:

    python3 python-scripts/check_links.py            # tracked *.md, exit 1 if broken
    python3 python-scripts/check_links.py docs/adr   # limit to a subtree

What it checks: every relative Markdown link and image target in a tracked `.md`
file resolves to an existing path. Absolute URLs, `mailto:` and pure `#anchor`
links are out of scope (lychee checks those online; we do not, in an unattended
session).

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
FENCE = re.compile(r"^\s*(```|~~~)")
SKIP_SCHEME = re.compile(r"^(https?:|mailto:|ftp:|#|<)")


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


def tracked_markdown(root: str, subtree: str | None) -> list[str]:
    args = ["git", "-C", root, "ls-files", "*.md"]
    if subtree:
        args += ["--", subtree]
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout.split()


def check(root: str, subtree: str | None = None) -> int:
    broken = 0
    files = tracked_markdown(root, subtree)
    for rel in files:
        path = os.path.join(root, rel)
        try:
            text = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError) as exc:  # pragma: no cover - unreadable file
            print(f"UNREADABLE {rel}: {exc}")
            broken += 1
            continue
        for match in LINK.finditer(_strip_code(text)):
            target = match.group(1)
            if SKIP_SCHEME.match(target):
                continue
            target = urllib.parse.unquote(target.split("#")[0])
            if not target:
                continue
            if not os.path.exists(os.path.join(os.path.dirname(path), target)):
                print(f"BROKEN {rel} -> {target}")
                broken += 1
    print(f"{len(files)} files checked, {broken} broken")
    return 1 if broken else 0


if __name__ == "__main__":
    repo = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    ).stdout.strip()
    sys.exit(check(repo, sys.argv[1] if len(sys.argv) > 1 else None))
