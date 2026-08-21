#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""Account for every unresolved-value marker in the tree, against a baseline.

Why this exists
---------------
On 2026-08-21 a session reported itself finished with four items listed as
"decisions for the owner" that were not decisions at all -- a DOI a registry
would have settled, a licence one API call away, a Python package that installs
in one command. Each had been marked in place and then forgotten, because
nothing counted them. The night before, a correction recorded in an ADR had
survived in eleven other files for the same reason.

The fix is not diligence, it is arithmetic. Every marker in this repository is
either **closed** (it must no longer appear -- a regression guard) or
**allowed** (it legitimately remains, and someone owns it). A marker that is
neither is a failure, so a new one cannot be introduced without editing the
allowlist in the same commit, and an owner cannot be left implicit.

The markers
-----------
``(verify``          a claim that has not been checked against its source
``(prov.)``          a provisional value (CLAUDE.md's sanctioned tag)
``unread`` /         a document or register that has not been read
``unconfirmed``
``TBD (datasheet``   a number that exists on a page nobody has opened

Bare ``TBD`` is deliberately NOT scanned. CLAUDE.md sanctions it for a value
that is genuinely unmeasured, so counting it would drown the signal; the tagged
form ``TBD (datasheet ...)`` is the one that means "someone could just read it".

Usage
-----
    python3 python-scripts/check_markers.py                     # report
    python3 python-scripts/check_markers.py --closed F --allow F  # gate, exit 1 on drift
    python3 python-scripts/check_markers.py --write-allow F     # re-baseline (review the diff!)
    python3 python-scripts/check_markers.py --self-test

File formats, both tab-separated, ``#`` comments and blank lines ignored:

    closed.tsv   <path>\\t<python regex that must NOT match any line>\\t<what closed it>
    allow.tsv    <path>\\t<max count>\\t<owner>

``<owner>`` is free text and is the point of the file: "D4 schematic read",
"Phase 1 measured", "purchase", "owner: taste". A row without one is rejected,
because "allowed" without "whose" is how a marker becomes permanent.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys

MARKERS = re.compile(r"\(verify|\(prov\.\)|\bunread\b|\bunconfirmed\b|TBD \(datasheet")

SCAN_SUFFIXES = (".md", ".yaml", ".yml", ".csv", ".h", ".json", ".toml")
SKIP_PARTS = ("/clones/", "/managed_components/", "/build/", ".ocr")
SKIP_PREFIXES = ("scratch/", "docs/research/")


def repo_root() -> str:
    return subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def tracked_files(root: str) -> list[str]:
    """Tracked *and* untracked-but-not-ignored: a file is accountable the moment
    it is written, not once it is staged (the same reasoning as check_links.py)."""
    out = subprocess.run(
        ["git", "-C", root, "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    keep = []
    for f in sorted(set(out)):
        if not f.endswith(SCAN_SUFFIXES):
            continue
        if any(f.startswith(p) for p in SKIP_PREFIXES):
            continue
        if any(p in "/" + f for p in SKIP_PARTS):
            continue
        keep.append(f)
    return keep


def scan(root: str, files: list[str]) -> dict[str, list[tuple[int, str, str]]]:
    """{path: [(line_no, marker_text, line_excerpt), ...]}"""
    found: dict[str, list[tuple[int, str, str]]] = {}
    for rel in files:
        try:
            text = io.open(os.path.join(root, rel), encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        hits = []
        for n, line in enumerate(text.split("\n"), 1):
            for m in MARKERS.finditer(line):
                hits.append((n, m.group(0), line.strip()[:120]))
        if hits:
            found[rel] = hits
    return found


def read_tsv(path: str, fields: int) -> list[list[str]]:
    rows = []
    for n, line in enumerate(io.open(path, encoding="utf-8"), 1):
        line = line.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < fields:
            raise SystemExit(
                "%s:%d: expected %d tab-separated fields, got %d: %r"
                % (path, n, fields, len(parts), line)
            )
        rows.append([p.strip() for p in parts[:fields]])
    return rows


def check_closed(root: str, spec: str) -> int:
    """Each row names a pattern that must no longer appear in a file."""
    failures = 0
    for path, pattern, why in read_tsv(spec, 3):
        full = os.path.join(root, path)
        if not os.path.exists(full):
            print("REOPENED %s: file is gone, but it was closed by: %s" % (path, why))
            failures += 1
            continue
        rx = re.compile(pattern)
        for n, line in enumerate(io.open(full, encoding="utf-8").read().split("\n"), 1):
            if rx.search(line):
                print("REOPENED %s:%d matches /%s/ — closed by: %s" % (path, n, pattern, why))
                print("         %s" % line.strip()[:150])
                failures += 1
    return failures


def check_allow(found: dict, spec: str) -> int:
    allowed = {}
    for path, count, owner in read_tsv(spec, 3):
        if not owner:
            raise SystemExit("%s: row for %s has no owner" % (spec, path))
        allowed[path] = (int(count), owner)
    failures = 0
    for path, hits in sorted(found.items()):
        if path not in allowed:
            print("UNLISTED %s: %d marker(s), no allowlist row and no owner" % (path, len(hits)))
            for n, mark, line in hits[:3]:
                print("         %s:%d  %s" % (path, n, line[:110]))
            failures += 1
            continue
        cap, owner = allowed[path]
        if len(hits) > cap:
            print("GREW     %s: %d marker(s), allowed %d (owner: %s)" % (path, len(hits), cap, owner))
            failures += 1
    for path, (cap, owner) in sorted(allowed.items()):
        got = len(found.get(path, []))
        if got < cap:
            print("SHRANK   %s: %d marker(s), allowlist still says %d (owner: %s) — lower it"
                  % (path, got, cap, owner))
            failures += 1
    return failures


def write_allow(found: dict, path: str) -> None:
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write("# SPDX-FileCopyrightText: 2026 Alexander Gomez\n")
        fh.write("# SPDX-License-Identifier: Apache-2.0\n#\n")
        fh.write("# Baseline for python-scripts/check_markers.py. THREE tab-separated fields:\n")
        fh.write("#   <path>\\t<max marker count>\\t<owner>\n#\n")
        fh.write("# The owner is the point. Replace every AUTO-GENERATED with a real one, and\n")
        fh.write("# lower a count in the same commit that removes a marker.\n")
        for p, hits in sorted(found.items()):
            fh.write("%s\t%d\tAUTO-GENERATED — needs an owner\n" % (p, len(hits)))
    print("wrote %s with %d rows" % (path, len(found)))


def self_test() -> int:
    """No fixtures: exercise the matcher on strings that have actually bitten us."""
    cases = [
        ("silence 0.09 *(verify: check the OA flag)*", True),
        ("470 mAh `(prov.)` until teardown", True),
        ("the DRV2605L start-up time is unread", True),
        ("reading per the GATECTRL definition — **unconfirmed**", True),
        ("| ALDO3 | `TBD (datasheet)` |", True),
        ("| C_rated | TBD — roadmap Q9 |", False),          # bare TBD is sanctioned
        ("verify the build with idf.py", False),            # prose, not a marker
        ("unreadable file", False),                         # 'unread' must be a whole word
        ("provisional wording without the tag", False),
    ]
    bad = 0
    for text, want in cases:
        got = bool(MARKERS.search(text))
        if got != want:
            print("SELF-TEST FAIL: %r -> %s, expected %s" % (text, got, want))
            bad += 1
    print("self-test: %d/%d cases pass" % (len(cases) - bad, len(cases)))
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--closed", metavar="TSV", help="patterns that must no longer match")
    ap.add_argument("--allow", metavar="TSV", help="per-file marker budget with owners")
    ap.add_argument("--write-allow", metavar="TSV", help="re-baseline the allowlist")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true", help="list every marker")
    args = ap.parse_args(argv)

    if args.self_test:
        return 1 if self_test() else 0

    root = repo_root()
    found = scan(root, tracked_files(root))
    total = sum(len(v) for v in found.values())

    if args.write_allow:
        write_allow(found, args.write_allow)
        return 0

    failures = 0
    if args.closed:
        failures += check_closed(root, args.closed)
    if args.allow:
        failures += check_allow(found, args.allow)

    if not args.closed and not args.allow:
        print("%-62s %s" % ("file", "markers"))
        for p, hits in sorted(found.items(), key=lambda x: -len(x[1])):
            print("%-62s %5d" % (p, len(hits)))
            if args.verbose:
                for n, mark, line in hits:
                    print("      %s:%d  %s" % (p, n, line))
    print("\n%d marker(s) across %d file(s)" % (total, len(found)))
    if args.closed or args.allow:
        print("RESULT: %s" % ("PASS" if failures == 0 else "FAIL (%d)" % failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
