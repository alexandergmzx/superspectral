# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""tolerances.py is a copy; docs/validation/golden-files.md is the definition. Drift fails here.

Three directions are checked: every constant's row exists exactly once in
the document and carries the literal text the constant was copied from;
the number in that literal parses to the constant's value; and every row
of the document's table is covered by at least one constant, so a row
added to the table without a constant is caught too.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from golden_compare import tolerances
from golden_compare.tolerances import TABLE, Tolerance

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:e-?\d+)?")


def _table_lines(doc: Path) -> list[str]:
    """The rows of the tolerance table: 4-cell lines between its heading and the gotchas."""
    text = doc.read_text(encoding="utf-8")
    start = text.index("## Tolerance table")
    end = text.index("## Gotchas", start)
    rows = []
    for line in text[start:end].splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.replace(r"\|", "\x00").strip().strip("|").split("|")]
        if len(cells) != 4 or set(cells[0]) <= {"-"} or cells[0] == "Comparison":
            continue   # separator, header, or the 3-cell SciPy-name mini-table
        rows.append(line)
    return rows


def _number_in(doc_text: str) -> float:
    cleaned = doc_text.replace("−", "-").replace("`", "").replace("*", "")
    m = _NUMBER.search(cleaned)
    assert m, f"no number in {doc_text!r}"
    return float(m.group(0))


@pytest.mark.parametrize("tol", TABLE, ids=[t.name for t in TABLE])
def test_each_constant_is_copied_from_exactly_one_row_verbatim(golden_files_md: Path, tol: Tolerance):
    rows = [r for r in _table_lines(golden_files_md) if tol.row in r]
    assert len(rows) == 1, f"{tol.name}: row key {tol.row!r} matches {len(rows)} rows"
    assert tol.doc_text in rows[0], f"{tol.name}: {tol.doc_text!r} not in the row:\n{rows[0]}"


@pytest.mark.parametrize("tol", [t for t in TABLE if t.value is not None], ids=[t.name for t in TABLE if t.value is not None])
def test_the_literal_in_the_document_parses_to_the_constant(tol: Tolerance):
    assert _number_in(tol.doc_text) == tol.value, f"{tol.name}: doc says {tol.doc_text!r}, constant is {tol.value!r}"


def test_the_exact_row_has_no_number_to_copy():
    assert tolerances.WINDOW_DIGEST_EXACT.value is None
    assert not _NUMBER.search(tolerances.WINDOW_DIGEST_EXACT.doc_text.replace("*", ""))


def test_every_row_of_the_document_table_is_covered_by_a_constant(golden_files_md: Path):
    uncovered = [r for r in _table_lines(golden_files_md) if not any(t.row in r for t in TABLE)]
    assert not uncovered, "rows in golden-files.md with no constant in tolerances.py:\n" + "\n".join(uncovered)


def test_the_table_has_the_rows_this_package_applies(golden_files_md: Path):
    # a sanity floor on the parser itself: the rows the three comparators consume must be found
    rows = _table_lines(golden_files_md)
    assert len(rows) >= 12
    for key in ("injection path", "table digest", "numpy.fft.rfft", "general_cosine"):
        assert any(key in r for r in rows), key


def test_source_pointer_matches_the_manifest_schema_constant(repo_root: Path):
    schema = (repo_root / "host" / "golden" / "manifest.schema.yaml").read_text(encoding="utf-8")
    assert f'const: "{tolerances.SOURCE}"' in schema


def test_every_constant_is_in_the_table_tuple():
    named = {v.name for v in vars(tolerances).values() if isinstance(v, Tolerance)}
    assert named == {t.name for t in TABLE}
    assert all(getattr(tolerances, t.name) is t for t in TABLE)
