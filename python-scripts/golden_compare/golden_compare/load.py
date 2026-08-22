# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""Read a golden manifest and its arrays — as data, and only after they agree.

A golden file is its manifest (ADR 0009): an ``.npy`` is trusted only once its
bytes, dtype and shape match the ``outputs[]`` entry that names it. This
module is the Apache side of that contract. It reads what ``host/golden/``
(GPL-3.0-or-later) wrote **as files** — YAML and ``.npy`` — and never imports
from it; reading a file is not linking (ADR 0004, ADR 0009 decision 3).

Three refusals, each a hazard the tests name:

* ``allow_pickle=False`` on every ``np.load``: a pickled ``.npy`` executes
  code on load, and a golden array is numbers, never objects.
* dtype and shape are cross-checked against the manifest entry, and the
  sha256 of the file's bytes against ``entry["sha256"]``; a mismatch raises
  :class:`ManifestMismatch` rather than returning an array that is not the
  one the manifest describes.
* the manifest's ``schema`` must be exactly :data:`SCHEMA_VERSION`; a reader
  accepts one value and refuses the rest (ADR 0009, schema ``"1.1"``) — the
  integer ``1`` of schema 1 is rejected, not coerced.

CLI: none directly; ``python -m golden_compare spectrum|pitch --manifest …``
goes through :func:`load_manifest` and :func:`load_array`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
import yaml

#: The one manifest schema version this reader accepts (manifest.schema.yaml
#: `schema: const "1.1"`; ADR 0009 amendment of 2026-08-21).
SCHEMA_VERSION = "1.1"


class ManifestMismatch(ValueError):
    """The file on disk is not the array (or manifest) its entry describes."""


def sha256_of_file(path: str | Path) -> str:
    """sha256 hex digest of a file's bytes, streamed."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Parse ``manifest.yaml`` with ``yaml.safe_load`` and refuse any schema but :data:`SCHEMA_VERSION`.

    This is a reader, not a validator: the JSON-Schema pass and invariants
    1–8 belong to the GPL side's ``verify.py``. What is checked here is the
    minimum a consumer needs in order not to misread the file — that it is a
    mapping, and that its ``schema`` is the string this code was written for.
    """
    with open(path, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    if not isinstance(doc, Mapping):
        raise ManifestMismatch(f"{path}: manifest is not a mapping")
    version = doc.get("schema")
    if not isinstance(version, str) or version != SCHEMA_VERSION:
        raise ManifestMismatch(
            f"{path}: schema {version!r} is not {SCHEMA_VERSION!r} "
            "(a reader accepts exactly one value; the integer 1 is rejected, never coerced — ADR 0009)"
        )
    return dict(doc)


def find_output(manifest: Mapping[str, Any], path: str | Path) -> dict[str, Any]:
    """The ``outputs[]`` entry whose ``path`` names ``path``.

    Manifest paths are repository-relative (``host/golden/outputs/<set>/x.npy``);
    the caller's path may be absolute or relative to anywhere, so the match is
    on the trailing components: the entry whose ``path`` ends with the caller's
    basename *and* whose components are a suffix of the caller's resolved path.
    Exactly one entry must match.
    """
    wanted = Path(path).resolve()
    hits = []
    for entry in manifest.get("outputs", ()):
        parts = Path(entry["path"]).parts
        if len(parts) <= len(wanted.parts) and wanted.parts[-len(parts):] == parts:
            hits.append(entry)
    if len(hits) != 1:
        raise ManifestMismatch(f"{path}: {len(hits)} outputs[] entries match (need exactly 1)")
    return dict(hits[0])


def find_window(manifest: Mapping[str, Any], family: str, n: int) -> dict[str, Any]:
    """The ``windows[]`` entry for ``(family, n)``; exactly one must exist (invariant 8's lookup)."""
    hits = [w for w in manifest.get("windows", ()) if w.get("family") == family and int(w.get("n", -1)) == int(n)]
    if len(hits) != 1:
        raise ManifestMismatch(f"windows[]: {len(hits)} entries for ({family!r}, {n}) (need exactly 1)")
    return dict(hits[0])


def load_array(path: str | Path, entry: Mapping[str, Any] | None = None, check_sha256: bool = True) -> np.ndarray:
    """``np.load(path, allow_pickle=False)``, cross-checked against a manifest entry when one is given.

    With ``entry`` (an ``outputs[]`` item), the array's dtype and shape must
    equal ``entry["dtype"]`` / ``entry["shape"]`` and — unless ``check_sha256``
    is ``False`` — the file's sha256 must equal ``entry["sha256"]``. Any
    disagreement is :class:`ManifestMismatch`. Without ``entry`` (a device
    dump, a host-tests result) only the pickle refusal applies; the caller
    compares shapes when it compares values.
    """
    path = Path(path)
    if entry is not None and check_sha256:
        want = str(entry["sha256"]).lower()
        got = sha256_of_file(path)
        if got != want:
            raise ManifestMismatch(f"{path}: sha256 {got} != manifest {want}")
    loaded = np.load(path, allow_pickle=False)
    if not isinstance(loaded, np.ndarray):
        raise ManifestMismatch(f"{path}: not a single array (.npz archives are not golden files)")
    if entry is not None:
        want_dtype = np.dtype(str(entry["dtype"]))
        if loaded.dtype != want_dtype:
            raise ManifestMismatch(f"{path}: dtype {loaded.dtype} != manifest {want_dtype}")
        want_shape = tuple(int(s) for s in entry["shape"])
        if loaded.shape != want_shape:
            raise ManifestMismatch(f"{path}: shape {loaded.shape} != manifest {want_shape}")
    return loaded


def column(array: np.ndarray, entry: Mapping[str, Any] | None, name: str, default_index: int) -> np.ndarray:
    """Column ``name`` of a ``[n, k]`` array, located through the entry's ``columns`` list.

    The manifest names every column (``units`` and ``columns`` are required
    fields because "an array of numbers with no unit is the single most
    common way a golden file lies"); with an entry the name is looked up,
    without one ``default_index`` is used — the layout the golden side
    documents for that analysis. A 1-D array is returned as is.
    """
    if array.ndim == 1:
        return array
    if array.ndim != 2:
        raise ValueError(f"expected a 1-D or [n, k] array, got shape {array.shape}")
    if entry is not None:
        names = list(entry.get("columns", ()))
        if name not in names:
            raise ManifestMismatch(f"manifest columns {names} carry no {name!r}")
        return array[:, names.index(name)]
    return array[:, default_index]
