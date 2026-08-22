#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""Relative-link checker for the tracked text files in this repository.

CI runs `lycheeverse/lychee-action --offline` (.github/workflows/ci.yml); this is
the same check with no install, for use before a commit and in unattended
sessions:

    python3 python-scripts/check_links.py            # every non-ignored file, exit 1 if broken
    python3 python-scripts/check_links.py docs/adr   # limit to a subtree
    python3 python-scripts/check_links.py --verbose  # also name every skipped target
    python3 python-scripts/check_links.py --self-test  # fixtures for the rules above

What it checks, in every `.md`, `.yaml`, `.yml` and `.json` file that git would show
(tracked, or untracked and not ignored):

1. every relative Markdown link and image target resolves to an existing path --
   including the outer target of the badge form `[![alt](img.png)](target.md)`,
   whose label the inline-link regex cannot span, and the target of a
   reference-style definition (`[r1]: some/file.md`);
2. every `#anchor` on a link into a Markdown file matches a heading in that file,
   under GitHub's slug rules (lowercase, punctuation dropped, spaces to hyphens,
   `-1`/`-2` suffixes for duplicates) -- a link that resolves to the right file and
   the wrong section is a defect a path check cannot see. A Markdown file that
   offers *no* anchors makes every anchor into it wrong; only a file this script
   cannot read is exempt.

Untracked files are included on purpose: a link check that only sees staged files
passes on a file that was never added. Non-Markdown files are scanned with the same
Markdown-link regexes, which today finds nothing: measured 2026-08-21, all 2753
relative links in the tree are in `.md` files and the `.yaml`/`.yml`/`.json` files
carry **zero** Markdown links. The paths they do carry -- `host/golden/manifest.
schema.yaml`'s `../../docs/validation/golden-files.md`, `host/golden/generate.py` --
are bare string scalars, and are **not checked**: a bare-path pass over those files
resolves neither against the file's directory nor against the repo root for 48 of
the 93 candidate strings (`idf.py`, `twatch_pins.h`, `$GITHUB_WORKSPACE/...`), so it
would report far more noise than defects. The suffixes stay so that the day a schema
grows a real Markdown link it is covered. Absolute URLs and `mailto:` are out of
scope (lychee checks those online; we do not, in an unattended session).

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
# `[^\]]*` cannot span the label of a badge link, so LINK sees only the inner
# image of `[![alt](img.png)](target.md)`. This second pass takes the outer
# target; the inner one is already covered by LINK, so nothing is checked twice.
NESTED_LINK = re.compile(
    r"\[!?\[[^\]]*\]\([^)\s]+(?:\s+\"[^\"]*\")?\)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)"
)
# A reference-style definition: `[r1]: some/file.md "title"`.
# `[ \t]{0,3}`, not `\s{0,3}`: under re.M `\s` matches newlines, so the match
# would start on a blank line several lines above the definition and every
# failure would be reported at the wrong line number.
REF_DEF = re.compile(r"^[ \t]{0,3}\[[^\]\n]+\]:[ \t]+(\S+)", re.M)
# `[^0-9.x](19|20)` in a YAML-embedded regex is Markdown link syntax by accident.
# Only the characters that actually appear in those embedded regexes are excused:
# `+`, `?`, `*`, `{` and `}` are legal in filenames (a `c++` directory, a query
# string), and excusing them silently accepted broken targets. `--verbose` names
# every target this skips, so the exemption is visible rather than assumed.
NOT_A_PATH = re.compile(r"[|^$\\]")
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


def anchors_of(path: str) -> set[str] | None:
    """Every anchor a Markdown file offers: heading slugs (with GitHub's -1/-2
    disambiguation) plus explicit `<a name=>` / `id=` attributes.

    Returns ``None`` -- not an empty set -- when the file cannot be read, so a
    caller can tell "this file offers no anchors, so every anchor into it is
    wrong" from "this script could not look".  Both halves skip fenced blocks:
    an `<a name="...">` inside an ```html block is a worked example and must not
    validate a link that points at it.  The heading loop tracks fences itself
    rather than reusing ``_strip_code``, which also blanks inline code spans --
    that would turn the heading "The `foo` rule" into the slug `the--rule`
    instead of GitHub's `the-foo-rule`.
    """
    try:
        text = open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        return None
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
    for m in re.finditer(r"""(?:name|id)=["\']([^"\']+)["\']""", _strip_code(text)):
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


def check_text(root, rel, text, anchor_cache, verbose=False):
    """Check one file's text; returns (broken, skipped) counts and prints failures.

    Split out of ``check`` so the self-test can drive it on fixtures without a
    git repository.
    """
    path = os.path.join(root, rel)
    stripped = _strip_code(text)
    broken, skipped = 0, 0
    targets = [(m.start(), m.group(1)) for m in LINK.finditer(stripped)]
    targets += [(m.start(), m.group(1)) for m in NESTED_LINK.finditer(stripped)]
    targets += [(m.start(), m.group(1)) for m in REF_DEF.finditer(stripped)]
    for start, raw in sorted(targets):
        if SKIP_SCHEME.match(raw):
            continue
        line_no = stripped.count("\n", 0, start) + 1
        if NOT_A_PATH.search(raw):
            skipped += 1
            if verbose:
                print(f"SKIPPED {rel}:{line_no} -> {raw} (regex metacharacter)")
            continue
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
            known = anchor_cache[key]
            # `None` means unreadable -- nothing can be said.  An empty set is a
            # statement: the file offers no anchors, so this one is wrong.
            if known is not None and anchor not in known:
                print(f"BAD ANCHOR {rel}:{line_no} -> {raw} "
                      f"(no heading slugs to '{anchor}')")
                broken += 1
    return broken, skipped


def check(root: str, subtree: str | None = None, verbose: bool = False) -> int:
    broken = skipped = 0
    anchor_cache: dict[str, set[str] | None] = {}
    files = repo_files(root, subtree)
    for rel in files:
        path = os.path.join(root, rel)
        try:
            text = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError) as exc:  # pragma: no cover - unreadable file
            print(f"UNREADABLE {rel}: {exc}")
            broken += 1
            continue
        b, s = check_text(root, rel, text, anchor_cache, verbose)
        broken += b
        skipped += s
    tail = f", {skipped} skipped (--verbose to name them)" if skipped else ""
    print(f"{len(files)} files checked, {broken} broken{tail}")
    return 1 if broken else 0


def self_test() -> int:
    """Fixtures for every rule the docstring claims, run in a temp directory.

    Each fixture is a defect this checker once missed; the expected-failure list
    is compared exactly, so a rule cannot quietly stop firing *and* a fixture
    cannot quietly start failing for the wrong reason.
    """
    import io
    import contextlib
    import tempfile

    files = {
        "real.md": "# A Heading\n\n## The `foo` rule\n",
        "empty.md": "no headings here, and no anchors either\n",
        "fenced.md": "```html\n<a name=\"not-a-real-anchor\"></a>\n```\n",
        "weird+name.md": "# W\n",
        "img.png": "",
        "case.md": (
            "[good](real.md)\n"                                 # 1  ok
            "[good anchor](real.md#a-heading)\n"                # 2  ok
            "[code anchor](real.md#the-foo-rule)\n"             # 3  ok
            "[missing](nope.md)\n"                              # 4  BROKEN
            "[bad anchor](real.md#no-such-heading)\n"           # 5  BAD ANCHOR
            "[![badge](img.png)](nope-target.md)\n"             # 6  BROKEN (outer)
            "[anchor into a file with none](empty.md#nope)\n"   # 7  BAD ANCHOR
            "[anchor from inside a fence](fenced.md#not-a-real-anchor)\n"  # 8 BAD ANCHOR
            "[query](real.md?x=1)\n"                            # 9  BROKEN
            "[plus](weird+name.md)\n"                           # 10 ok
            "[plus missing](weird+nope.md)\n"                   # 11 BROKEN
            "[in a code span: `[x](nope-span.md)`](real.md)\n"  # 12 ok
            "\n```\n[fenced](nope-fenced.md)\n```\n"            # 15 ok
            "\n[r1]: nope-ref.md\n"                             # 18 BROKEN
            "[r2]: real.md\n"                                   # 19 ok
        ),
        "regex.yaml": "  - id: pins\n    entry: '[^0-9.x](19|20)'\n",
    }
    expected = [
        "BROKEN case.md:4 -> nope.md",
        "BAD ANCHOR case.md:5 -> real.md#no-such-heading",
        "BROKEN case.md:6 -> nope-target.md",
        "BAD ANCHOR case.md:7 -> empty.md#nope",
        "BAD ANCHOR case.md:8 -> fenced.md#not-a-real-anchor",
        "BROKEN case.md:9 -> real.md?x=1",
        "BROKEN case.md:11 -> weird+nope.md",
        "BROKEN case.md:18 -> nope-ref.md",
    ]
    with tempfile.TemporaryDirectory() as root:
        for name, body in files.items():
            with open(os.path.join(root, name), "w", encoding="utf-8") as fh:
                fh.write(body)
        cache: dict[str, set[str] | None] = {}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            broken, skipped = 0, 0
            for name in ("case.md", "regex.yaml"):
                b, s = check_text(root, name, files[name], cache, verbose=False)
                broken += b
                skipped += s
        got = [ln.split(" (")[0] for ln in buf.getvalue().splitlines()]
    failures = []
    for want in expected:
        if not any(line.startswith(want) for line in got):
            failures.append(f"expected but not reported: {want}")
    for line in got:
        if not any(line.startswith(want) for want in expected):
            failures.append(f"reported but not expected: {line}")
    if skipped != 1:
        failures.append(f"the YAML-embedded regex should be the only skip, got {skipped}")
    for line in failures:
        print("SELF-TEST " + line)
    print("self-test: %d/%d fixtures held" % (len(expected) - len(failures), len(expected)))
    return 1 if failures else 0



if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--self-test" in argv:
        sys.exit(self_test())
    verbose = False
    for flag in ("--verbose", "-v"):
        if flag in argv:
            verbose = True
            argv = [a for a in argv if a != flag]
    repo = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    ).stdout.strip()
    sys.exit(check(repo, argv[0] if argv else None, verbose))
