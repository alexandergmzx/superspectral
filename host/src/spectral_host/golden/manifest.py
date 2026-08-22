# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""The golden manifest as a document: load it, validate it against the schema, write it back.

A golden file is its manifest (ADR 0009 decision 1). This module is the one
place the host reads and writes that document, and it fixes four behaviours
that `verify.py` (the invariants) and `generate.py` (unit B-U6) both depend on:

  * `load_schema()` reads host/golden/manifest.schema.yaml — JSON Schema
    draft 2020-12 written in YAML — and checks it with
    `Draft202012Validator.check_schema` before handing it out, so a broken
    schema is a crash here and never a manifest that "validates" against
    nothing. The default location is derived from this file (the package is
    installed editable from host/src, so `host/golden/` is three levels up);
    `verify_manifest` passes the checkout's copy explicitly.
  * `validate(doc)` returns the schema's errors as strings, one per error,
    sorted by JSON path so two runs print the same list. An empty list is the
    schema saying yes — which ADR 0009 calls a necessary condition, never a
    sufficient one; the invariants live in `verify.py`.
  * `load(path)` is `yaml.safe_load` and NOTHING ELSE. YAML 1.1 resolves a
    bare `2026-08-21` to `datetime.date`, and this loader lets it: the schema
    types `generated` and `regeneration.date` as strings, so an unquoted date
    arrives as a date object and fails validation instead of being coerced
    back into the string the author probably meant. That is deliberate
    (`$defs/date` in the schema says so): a manifest that is not valid JSON
    data is not a manifest, and a loader that quietly repaired it would hide
    the generator bug that wrote it.
  * `dump(doc)` writes the two GPL SPDX comment lines (host/ is GPL as a
    directory, ADR 0004 — invariant N4 of `verify.py` reads them back) and
    then `yaml.safe_dump(doc, sort_keys=False)`. PyYAML's emitter quotes any
    string its own implicit resolvers would read as another type, so
    `"2026-08-21"` and `"1.1"` come out single-quoted and survive a `load`
    as strings; `test_dump_keeps_dates_and_the_version_quoted` proves it
    rather than trusting it. Key order is the document's (schema order when
    the generator built it), because a manifest is reviewed as a diff.

CLI:

    uv run --project host python -m spectral_host.golden.manifest validate MANIFEST [MANIFEST ...]
    uv run --project host python -m spectral_host.golden.manifest schema-path

`validate` prints each schema error as `<path>: <json-path>: <message>` and
exits 1 if any manifest has one; `schema-path` prints where the schema was
found. Neither writes anything. The invariants are not run here — that is
`spectral-golden verify`.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

import jsonschema
import yaml

#: Repository-relative path of the schema (ADR 0009 decision 1).
SCHEMA_RELPATH: str = "host/golden/manifest.schema.yaml"

#: The one `schema:` value this reader accepts — the schema's `const`, repeated
#: here so `verify.py` rule S can name the version it refused without parsing
#: the schema for it. `test_schema_version_constant_equals_the_schema_const` pins them equal.
SCHEMA_VERSION: str = "1.1"

#: The directory's licence tag (ADR 0004), written first by `dump` and read
#: back by `verify.py` rule N4. Two lines, in this order, no blank line between.
SPDX_LINES: tuple[str, str] = (
    "# SPDX-FileCopyrightText: 2026 Alexander Gomez",
    "# SPDX-License-Identifier: GPL-3.0-or-later",
)

#: Where the default manifest of a set lives: `host/golden/outputs/<set>/manifest.yaml`.
OUTPUTS_RELPATH: str = "host/golden/outputs"
MANIFEST_FILENAME: str = "manifest.yaml"


class ManifestError(ValueError):
    """The file could not be read as a manifest document at all (not YAML, not a mapping)."""


def default_schema_path() -> Path:
    """`host/golden/manifest.schema.yaml` located from this file: host/src/spectral_host/golden/manifest.py → host/."""
    return Path(__file__).resolve().parents[3] / "golden" / "manifest.schema.yaml"


def load_schema(path: str | os.PathLike[str] | None = None) -> dict:
    """Read and check the schema; `path` defaults to `default_schema_path()`.

    `check_schema` runs every time: a schema file with a typo in a keyword
    would otherwise validate every manifest, which is the failure mode with
    the widest blast radius this module can have.
    """
    schema_file = Path(path) if path is not None else default_schema_path()
    with open(schema_file, encoding="utf-8") as fh:
        schema = yaml.safe_load(fh)
    if not isinstance(schema, dict):
        raise ManifestError(f"{schema_file}: schema file is not a mapping")
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


def validator_for(schema: dict) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(schema)


def _json_path(error: jsonschema.ValidationError) -> str:
    if not error.absolute_path:
        return "$"
    parts = []
    for token in error.absolute_path:
        parts.append(f"[{token}]" if isinstance(token, int) else f".{token}")
    return "$" + "".join(parts)


def validate(doc: object, schema: dict | None = None) -> list[str]:
    """Schema errors of `doc` as `"<json-path>: <message>"` strings, sorted by path; `[]` when it validates.

    `doc` may be anything `load` returned — a non-mapping is reported as a
    schema error rather than raised, so the caller sees one kind of result.
    """
    validator = validator_for(schema if schema is not None else load_schema())
    found = []
    for error in validator.iter_errors(doc):
        found.append((_json_path(error), error.message))
    found.sort()
    return [f"{path}: {message}" for path, message in found]


def loads(text: str) -> object:
    """`yaml.safe_load` of manifest text. Returns whatever YAML resolved — see the module docstring on bare dates."""
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ManifestError(f"not YAML: {exc}") from exc


def load(path: str | os.PathLike[str]) -> object:
    """Read a manifest file with `yaml.safe_load`; an unquoted date comes back as `datetime.date`, not a string."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    try:
        return loads(text)
    except ManifestError as exc:
        raise ManifestError(f"{path}: {exc}") from None


def dumps(doc: dict) -> str:
    """The manifest text: the two SPDX lines, then `yaml.safe_dump(doc, sort_keys=False)`."""
    if not isinstance(doc, dict):
        raise TypeError(f"a manifest is a mapping, got {type(doc).__name__}")
    body = yaml.safe_dump(
        doc,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=100,
    )
    return "\n".join(SPDX_LINES) + "\n" + body


def dump(doc: dict) -> bytes:
    """`dumps(doc)` as UTF-8 bytes — what the generator writes and what `inputs`/`previous_manifest_sha256` digest."""
    return dumps(doc).encode("utf-8")


def manifest_path(repo_root: str | os.PathLike[str], set_name: str) -> Path:
    """`<repo_root>/host/golden/outputs/<set>/manifest.yaml`."""
    return Path(repo_root) / OUTPUTS_RELPATH / set_name / MANIFEST_FILENAME


def discover_manifests(repo_root: str | os.PathLike[str]) -> list[Path]:
    """Every `host/golden/outputs/*/manifest.yaml` under `repo_root`, sorted; `[]` if the directory does not exist."""
    outputs = Path(repo_root) / OUTPUTS_RELPATH
    if not outputs.is_dir():
        return []
    return sorted(p for p in outputs.glob(f"*/{MANIFEST_FILENAME}") if p.is_file())


# --- CLI -------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m spectral_host.golden.manifest",
        description="Schema-validate golden manifests (no invariants; see `spectral-golden verify`).",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)
    val = sub.add_parser("validate", help="validate MANIFEST files against the schema; exit 1 on any error")
    val.add_argument("manifests", metavar="MANIFEST", nargs="+", type=Path)
    val.add_argument("--schema", type=Path, default=None, help=f"schema file (default: {SCHEMA_RELPATH} of this checkout)")
    sub.add_parser("schema-path", help="print the default schema location")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "schema-path":
        print(default_schema_path())
        return 0
    try:
        schema = load_schema(args.schema)
    except (OSError, ManifestError, jsonschema.SchemaError) as exc:
        print(f"error: schema: {exc}", file=sys.stderr)
        return 2
    status = 0
    for path in args.manifests:
        try:
            doc = load(path)
        except (OSError, ManifestError) as exc:
            print(f"{path}: error: {exc}")
            status = 1
            continue
        problems = validate(doc, schema)
        if problems:
            status = 1
            for problem in problems:
                print(f"{path}: {problem}")
        else:
            print(f"{path}: ok")
    return status


if __name__ == "__main__":
    sys.exit(main())
