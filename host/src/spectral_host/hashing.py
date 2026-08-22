# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""sha256 over bytes, files and whole source trees — the digests a golden manifest carries (ADR 0009).

Three recipes, each stated so that the Apache side can recompute it without
importing this module (the licence boundary of ADR 0004 is a file format, not
an API):

  * `sha256_bytes(b)` / `sha256_file(path)` — `hashlib.sha256` over the raw
    bytes. These are `inputs[].sha256` (the WAV bytes as used) and
    `outputs[].sha256` (the `.npy` bytes) of manifest.schema.yaml.
  * `sha256_files(root, relpaths)` — the SORTED TREE HASH over an EXPLICIT
    list of files: sort the POSIX relative paths, and feed into ONE sha256,
    per file, `relpath + "\\0" + str(size) + "\\0" + bytes`. The relative path
    is part of the input, so a rename changes the digest; the absolute
    location is not, so a checkout elsewhere on disk recomputes the same
    value. The length prefix keeps `("a", b"bc")` and `("ab", b"c")` distinct.
    A listed file that is missing is an error, never silently skipped. This
    is the recipe `generator.sha256` records, over the numerics-bearing
    modules `env.GENERATOR_TREE` enumerates (see env.py for why not the
    whole package).
  * `sha256_tree(root)` — the same recipe over EVERY regular file under
    `root` except bytecode caches (walk, then sort). Used by the CLI and by
    tests; a manifest never records it since the `GENERATOR_TREE` scoping.

Excluded from the tree: `__pycache__/` directories and `*.pyc` — they are
interpreter output, not source, and would make the digest depend on which
tests ran last. Nothing else is excluded: an untracked scratch file inside
the package changes the digest, which is the intended reading ("what ran" is
what was on disk), and `env.is_dirty()` is the guard that refuses to generate
from such a tree.

CLI:

    uv run --project host python -m spectral_host.hashing PATH [PATH ...]

prints `<sha256>  <path>` per argument — the tree recipe for a directory, the
file recipe otherwise — in the two-column form `sha256sum` uses.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path, PurePosixPath

#: Names (directories) and suffixes (files) that `sha256_tree` skips.
TREE_EXCLUDED_DIRS: frozenset[str] = frozenset({"__pycache__"})
TREE_EXCLUDED_SUFFIXES: frozenset[str] = frozenset({".pyc"})

_CHUNK = 1 << 20


def sha256_bytes(data: bytes) -> str:
    """Lowercase hex sha256 of `data` (manifest `$defs/sha256`: 64 hex characters)."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | os.PathLike[str]) -> str:
    """Lowercase hex sha256 of a file's bytes, streamed; the recipe for `inputs[].sha256` and `outputs[].sha256`."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def tree_files(root: str | os.PathLike[str]) -> Iterator[tuple[str, Path]]:
    """(posix relative path, absolute path) of every hashed file under `root`, in sorted order.

    Symlinks are not followed into (a link to a directory is skipped; a link to
    a file is hashed through, as `open` would read it).
    """
    root_path = Path(root)
    if not root_path.is_dir():
        raise NotADirectoryError(f"sha256_tree needs a directory, got {root_path}")
    found: list[tuple[str, Path]] = []
    for dirpath, dirnames, filenames in os.walk(root_path, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in TREE_EXCLUDED_DIRS)
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix in TREE_EXCLUDED_SUFFIXES or not path.is_file():
                continue
            found.append((path.relative_to(root_path).as_posix(), path))
    # Sort on the relative POSIX path, not on os.walk order, so the digest is
    # independent of filesystem enumeration order.
    found.sort(key=lambda item: item[0])
    yield from found


def _digest_listed(pairs: Iterable[tuple[str, Path]], what: str) -> str:
    h = hashlib.sha256()
    count = 0
    for relpath, path in pairs:
        data = path.read_bytes()
        h.update(relpath.encode("utf-8"))
        h.update(b"\0")
        h.update(str(len(data)).encode("ascii"))
        h.update(b"\0")
        h.update(data)
        count += 1
    if count == 0:
        raise ValueError(f"no hashable files in {what}; refusing to digest an empty tree")
    return h.hexdigest()


def sha256_files(root: str | os.PathLike[str], relpaths: Iterable[str]) -> str:
    """The sorted tree hash over the listed files (POSIX paths relative to `root`), lowercase hex.

    The list is sorted here, so callers need not keep it ordered; a duplicate
    entry is an error (it would double-count bytes); a listed path that is not
    a regular file is an error — the digest must describe exactly what the
    list names, or the list is wrong.
    """
    root_path = Path(root)
    names = sorted(relpaths)
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate entries in the file list for {root_path}")
    pairs = []
    for rel in names:
        path = root_path / rel
        if not path.is_file():
            raise FileNotFoundError(f"{rel} (under {root_path}) is listed for digesting but is not a regular file")
        pairs.append((PurePosixPath(rel).as_posix(), path))
    return _digest_listed(pairs, f"the file list under {root_path}")


def sha256_tree(root: str | os.PathLike[str]) -> str:
    """The sorted tree hash over every hashable file under `root`, lowercase hex.

    An empty tree (no hashable file) is refused: a generator digest over
    nothing would validate against the schema and record nothing.
    """
    return _digest_listed(tree_files(root), f"the tree under {Path(root)}")


# --- CLI -------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m spectral_host.hashing",
        description="sha256 of files (bytes) or directories (sorted tree hash, the generator.sha256 recipe).",
    )
    parser.add_argument("paths", metavar="PATH", nargs="+", help="file or directory")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    status = 0
    for raw in args.paths:
        path = Path(raw)
        try:
            digest = sha256_tree(path) if path.is_dir() else sha256_file(path)
        except (OSError, ValueError) as exc:
            print(f"error: {raw}: {exc}", file=sys.stderr)
            status = 2
            continue
        print(f"{digest}  {raw}")
    return status


if __name__ == "__main__":
    sys.exit(main())
