# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""The pin chain, captured: the `generator` block of a golden manifest, read from the installed environment.

ADR 0009 decision 1 makes `generator.*` the reason the manifest exists —
"parselmouth is numerically identical to Praat" holds only within one bundled
Praat version, and every number in a golden set is conditioned on the
parselmouth, Praat, NumPy, SciPy, BLAS and interpreter that ran. This module
READS those values; it never assumes them. `GeneratorEnv` has exactly the
schema's eleven required keys (manifest.schema.yaml `generator.required`,
pinned by `test_generator_env_keys_equal_schema_required_list`), and
`capture()` fills each one from its source of truth:

  * `script`    — `PACKAGE_RELPATH`, `host/src/spectral_host`: the generator
                  is a package (praat.py, spectrum.py, the golden/ modules …),
                  not one script, so the path names the package the digest
                  covers. The schema's original example (`host/golden/generate.py`)
                  predates the src layout of unit B-U1.
  * `sha256`    — `generator_sha256(repo_root)` = `hashing.sha256_files` over
                  `GENERATOR_TREE`: the sorted tree hash (relative path + size
                  + bytes per file) of the NUMERICS-BEARING modules only —
                  the oracle, the Praat wrappers, the decoder, the set
                  definitions, the generator and the two modules that define
                  this digest. A change to any of them is a manifest diff
                  (regenerate — ADR 0009 decision 4); a change to the CLI,
                  the verifier, the manifest I/O or the preset loader is not,
                  because none of them can alter a vector. Hashing the whole
                  package (the first H0 draft) made every host commit a
                  regeneration and was dropped on 2026-08-22 (ADR 0009
                  amendment). If `GENERATOR_TREE` itself changes, every
                  existing set re-verifies red on I4 and is re-emitted with
                  that reason — which is the intended reading.
  * `commit`    — `git rev-parse HEAD` in `repo_root` (40 hex; the schema's
                  `$defs/git_sha` refuses a short sha).
  * `python`    — `platform.python_version()` (`3.12.3`).
  * `numpy` / `scipy` / `parselmouth` — each package's `__version__`.
  * `praat_bundled` — `parselmouth.PRAAT_VERSION`, the version the numbers
                  come from; never praat.org's current release.
  * `praat_reference` — the praat.org release T7b was run against; `None`
                  while T7b is open (ADR 0009 item 1(c)), which is the only
                  value this module will ever write on its own.
  * `platform`  — `platform.platform()`.
  * `blas`      — NumPy's BLAS name and version from
                  `numpy.show_config(mode="dicts")["Build Dependencies"]["blas"]`,
                  as `"<name> <version>"` (e.g. `scipy-openblas 0.3.34.0.0`).
                  Recorded because reduction order differs between vendors.

`is_dirty(repo_root, paths)` asks `git status --porcelain` whether anything
under `paths` is modified or untracked — the generator (unit B-U6) refuses to
run from a dirty `host/src`, because `sha256` would then describe bytes no
commit contains and `commit` would be a lie about what ran.

CLI (the body of `spectral-golden env`; the subcommand itself is wired by unit B-U5):

    uv run --project host python -m spectral_host.env [--repo-root DIR] [--praat-reference VERSION]

prints the captured block as `key: value` lines in schema order and exits 0,
or exits 2 if the repository root cannot be found or git is unavailable.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import platform
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy
import parselmouth
import scipy

from spectral_host.hashing import sha256_files

#: Repository-relative path of the generator package — what `script` names.
PACKAGE_RELPATH: str = "host/src/spectral_host"

#: The numerics-bearing modules of the package, relative to `PACKAGE_RELPATH`:
#: exactly the files whose bytes can change a golden vector, plus the two that
#: define this digest. `generator.sha256` is `hashing.sha256_files` over this
#: list (recipe in hashing.py). Adding a module that computes part of a vector
#: means adding it HERE, in the same commit — `test_generator_tree_names_every_
#: module_the_generator_imports_for_numerics` guards the obvious omission.
GENERATOR_TREE: tuple[str, ...] = (
    "env.py",
    "hashing.py",
    "praat.py",
    "spectrum.py",
    "wavio.py",
    "golden/generate.py",
    "golden/sets.py",
)

#: The schema's `generator.required`, in schema order (manifest.schema.yaml).
GENERATOR_KEYS: tuple[str, ...] = (
    "script",
    "sha256",
    "commit",
    "python",
    "numpy",
    "scipy",
    "parselmouth",
    "praat_bundled",
    "praat_reference",
    "platform",
    "blas",
)


@dataclass(frozen=True)
class GeneratorEnv:
    """The `generator` block of a golden manifest — exactly its eleven keys, in schema order."""

    script: str
    sha256: str
    commit: str
    python: str
    numpy: str
    scipy: str
    parselmouth: str
    praat_bundled: str
    praat_reference: str | None
    platform: str
    blas: str

    def asdict(self) -> dict[str, object]:
        """The block as the manifest writes it (`praat_reference` stays `None` → YAML `null`)."""
        return dataclasses.asdict(self)


# --- sources of truth, one function each ---------------------------------------------


def blas_string() -> str:
    """`"<name> <version>"` of NumPy's BLAS from `numpy.show_config(mode="dicts")`.

    Falls back to `"<name> unknown"` / `"unknown"` rather than raising: the
    schema only requires a non-empty string, and an environment whose BLAS
    cannot be identified should still be recordable — as unknown, visibly.
    """
    try:
        info = numpy.show_config(mode="dicts")
    except TypeError:  # NumPy < 1.25 has no `mode`
        return "unknown"
    blas = (info or {}).get("Build Dependencies", {}).get("blas", {}) or {}
    name = str(blas.get("name") or "unknown")
    version = str(blas.get("version") or "unknown")
    return f"{name} {version}"


def git_head(repo_root: str | os.PathLike[str]) -> str:
    """The full 40-hex commit `HEAD` resolves to in `repo_root`."""
    proc = subprocess.run(
        ["git", "-C", os.fspath(repo_root), "rev-parse", "--verify", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git rev-parse HEAD failed in {repo_root}: {proc.stderr.strip()}")
    sha = proc.stdout.strip()
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise RuntimeError(f"git rev-parse HEAD returned {sha!r}, not a 40-hex object name")
    return sha


def is_dirty(repo_root: str | os.PathLike[str], paths: Iterable[str | os.PathLike[str]]) -> bool:
    """True if `git status --porcelain` lists anything (modified, staged or untracked) under `paths`.

    `paths` are repository-relative or absolute; `--untracked-files=all` so an
    untracked file inside an otherwise clean package counts — it is in the
    tree hash but in no commit.
    """
    path_args = [os.fspath(p) for p in paths]
    proc = subprocess.run(
        ["git", "-C", os.fspath(repo_root), "status", "--porcelain", "--untracked-files=all", "--", *path_args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git status failed in {repo_root}: {proc.stderr.strip()}")
    return any(line.strip() for line in proc.stdout.splitlines())


def generator_sha256(repo_root: str | os.PathLike[str]) -> str:
    """`generator.sha256`: the sorted tree hash of `GENERATOR_TREE` under `repo_root / PACKAGE_RELPATH`."""
    return sha256_files(Path(repo_root) / PACKAGE_RELPATH, GENERATOR_TREE)


def capture(repo_root: str | os.PathLike[str], praat_reference: str | None = None) -> GeneratorEnv:
    """Read every `generator` field from the installed environment and the checkout at `repo_root`."""
    root = Path(repo_root)
    if not (root / PACKAGE_RELPATH).is_dir():
        raise FileNotFoundError(f"{root} has no {PACKAGE_RELPATH}; is it the repository root?")
    return GeneratorEnv(
        script=PACKAGE_RELPATH,
        sha256=generator_sha256(root),
        commit=git_head(root),
        python=platform.python_version(),
        numpy=numpy.__version__,
        scipy=scipy.__version__,
        parselmouth=parselmouth.__version__,
        praat_bundled=parselmouth.PRAAT_VERSION,
        praat_reference=praat_reference,
        platform=platform.platform(),
        blas=blas_string(),
    )


def format_env(env: GeneratorEnv) -> str:
    """`key: value` lines in schema order, as valid YAML: strings double-quoted, `None` as `null`.

    Quoting is not cosmetic — a bare `6.4` or `7.0` (a two-part `praat_reference`)
    is a YAML *float*, and an unquoted `3.12` would round-trip as `3.12` the
    number; the schema's `$defs/version` wants strings.
    """
    lines = []
    for key, value in env.asdict().items():
        lines.append(f"{key}: {'null' if value is None else json.dumps(str(value))}")
    return "\n".join(lines)


# --- CLI ---------------------------------------------------------------------------------


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "CLAUDE.md").is_file() and (candidate / PACKAGE_RELPATH).is_dir():
            return candidate
    raise FileNotFoundError(f"no repository root (CLAUDE.md + {PACKAGE_RELPATH}) above {start}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m spectral_host.env",
        description="Print the generator pin chain of the installed environment (manifest `generator` block).",
    )
    parser.add_argument("--repo-root", type=Path, default=None, help="repository root (default: search upward from this file)")
    parser.add_argument("--praat-reference", default=None, help="praat.org release T7b was run against (default: null, T7b open)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root = args.repo_root if args.repo_root is not None else _find_repo_root(Path(__file__).resolve().parent)
        env = capture(root, praat_reference=args.praat_reference)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(format_env(env))
    return 0


if __name__ == "__main__":
    sys.exit(main())
