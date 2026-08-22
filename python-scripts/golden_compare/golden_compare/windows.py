# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""Window-table digests — the device lane's hasher for the *exact* row of the table.

ADR 0006 D1: the float32 table ``spectral_window_fill()`` leaves in memory is
hashed per ``(family, N)`` and the digest is a field of the golden manifest
(``windows[].sha256``, schema ``"1.1"``), so that a window that quietly
changes shape is a red check and not a fraction-of-a-dB drift in every
level. The C side carries no sha256 (manifest.schema.yaml, ``windows``):
the device or the host-tests lane **dumps the table raw** — ``N`` float32
samples, little-endian, no header — and this module hashes the dump and
compares it with the manifest. The recipe is the schema's, verbatim:
``hashlib.sha256(np.asarray(w, dtype="<f4").tobytes()).hexdigest()``; a raw
little-endian dump *is* those bytes, so the file is hashed as it lies.

Two rows of ``docs/validation/golden-files.md`` are served:

* **table digest per (family, N) — exact**: :func:`compare_window_digest`.
* **window coefficients vs ``general_cosine(N, a, sym=False)`` —
  ``atol = 1e-6``, ``rtol = 0``**: the same report carries ``max_abs_diff``
  between the dumped table and the table recomputed here from the entry's
  ``coefficients``, so a digest mismatch says *how far* the table is off —
  a last-ULP libm difference (10⁻⁷, a finding about the digest recipe) and a
  wrong window (10⁻², a bug) look the same in a hash and different here.

The recomputation evaluates the periodic cosine sum the way SciPy's
``general_cosine(N, a, sym=False)`` does — ``fac = linspace(−π, π, N+1)[:-1]``,
``w = Σ a_k·cos(k·fac)`` — rather than the algebraically identical
``Σ (−1)^k a_k cos(2πkj/N)`` of the schema, so that on the same NumPy the
float64 values are the same bits as the GPL oracle's and the float32
rounding cannot differ; the pinned digests in the tests are the proof
(``(hann, 4096)`` and ``(rect, 4096)`` from golden-files.md). No SciPy is
imported for it: three lines of NumPy, and no ``spectral_host``.

CLI (see :mod:`golden_compare.cli`)::

    python -m golden_compare window --raw hann_4096.f32 --manifest manifest.yaml --family hann --n 4096
    python -m golden_compare window --raw hann_4096.f32 --sha256 3ce6c7c8…
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

#: The hashed representation: float32, little-endian (manifest.schema.yaml `windows`).
TABLE_DTYPE = np.dtype("<f4")


def periodic_cosine_sum(coefficients: Sequence[float], n: int) -> np.ndarray:
    """The periodic cosine-sum window in float64, evaluated as ``general_cosine(n, a, sym=False)`` evaluates it."""
    n = int(n)
    if n < 2:
        raise ValueError(f"window length must be >= 2 (manifest schema `windows[].n`), got {n}")
    a = [float(c) for c in coefficients]
    if not 1 <= len(a) <= 5:
        raise ValueError(f"a cosine-sum window has 1 to 5 terms (manifest schema), got {len(a)}")
    fac = np.linspace(-np.pi, np.pi, n + 1)[:-1]
    w = np.zeros(n, dtype=np.float64)
    for k, ak in enumerate(a):
        w += ak * np.cos(k * fac)
    return w


def window_table(coefficients: Sequence[float], n: int) -> np.ndarray:
    """The float32 little-endian table for ``(coefficients, n)`` — the digest's input and the device's memory image."""
    return periodic_cosine_sum(coefficients, n).astype(TABLE_DTYPE)


def table_sha256(table: np.ndarray) -> str:
    """sha256 over the table's ``<f4`` bytes — the manifest's ``windows[].sha256`` recipe."""
    t = np.asarray(table)
    if t.ndim != 1:
        raise ValueError("a window table is 1-D")
    return hashlib.sha256(np.ascontiguousarray(t, dtype=TABLE_DTYPE).tobytes()).hexdigest()


def read_raw_f32(path: str | Path) -> np.ndarray:
    """A raw little-endian float32 dump as a 1-D array; refuses a size that is not a whole number of samples."""
    data = Path(path).read_bytes()
    if not data or len(data) % TABLE_DTYPE.itemsize:
        raise ValueError(f"{path}: {len(data)} bytes is not a non-empty whole number of float32 samples")
    return np.frombuffer(data, dtype=TABLE_DTYPE)


def raw_f32_sha256(path: str | Path) -> str:
    """sha256 of a raw float32 LE dump, hashed as the bytes lie (the dump is already the recipe's byte string)."""
    data = Path(path).read_bytes()
    if not data or len(data) % TABLE_DTYPE.itemsize:
        raise ValueError(f"{path}: {len(data)} bytes is not a non-empty whole number of float32 samples")
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class WindowReport:
    """Outcome of :func:`compare_window_digest`."""

    family: str
    n: int
    expected_sha256: str          #: the manifest's `windows[].sha256`
    dump_sha256: str              #: sha256 of the raw dump
    recomputed_sha256: str        #: sha256 of the table rebuilt here from `coefficients`
    n_samples: int                #: samples in the dump
    max_abs_diff: float           #: max |dump − recomputed| (NaN when the lengths differ)
    worst_index: int

    @property
    def digest_match(self) -> bool:
        """The exact row: the dump's digest equals the manifest's."""
        return self.dump_sha256 == self.expected_sha256

    @property
    def manifest_self_consistent(self) -> bool:
        """The manifest's digest equals the one recomputed from its own coefficients (verify.py invariant 7, re-checked here)."""
        return self.recomputed_sha256 == self.expected_sha256

    @property
    def passed(self) -> bool:
        return self.digest_match and self.n_samples == self.n

    def within(self, atol: float) -> bool:
        """The coefficients row: every sample within ``atol`` of the recomputed table (rtol = 0)."""
        return bool(np.isfinite(self.max_abs_diff)) and self.max_abs_diff <= atol

    def summary(self) -> str:
        verdict = "PASS" if self.passed else "FAIL"
        lines = [
            f"{verdict}: ({self.family}, {self.n}) digest {'matches' if self.digest_match else 'DIFFERS FROM'} the manifest",
            f"  manifest   {self.expected_sha256}",
            f"  dump       {self.dump_sha256}  ({self.n_samples} samples)",
            f"  recomputed {self.recomputed_sha256}"
            + ("" if self.manifest_self_consistent else "  <- manifest digest does not recompute from its own coefficients"),
        ]
        if np.isfinite(self.max_abs_diff):
            lines.append(f"  max |dump − recomputed| = {self.max_abs_diff:.3e} at j = {self.worst_index}")
        else:
            lines.append(f"  dump has {self.n_samples} samples, entry says n = {self.n}: no per-sample comparison")
        return "\n".join(lines)


def compare_window_digest(raw_f32_path: str | Path, manifest_windows_entry: Mapping[str, Any]) -> WindowReport:
    """Hash a raw float32 dump and compare it with one ``windows[]`` entry of a golden manifest.

    The entry supplies ``family``, ``n``, ``coefficients`` and ``sha256``
    (all four are required by the schema). The dump's digest is compared
    with ``sha256`` for the exact row; the table is also rebuilt from
    ``coefficients`` so the report can say how far a mismatching dump is
    from the window it should be.
    """
    entry = manifest_windows_entry
    family = str(entry["family"])
    n = int(entry["n"])
    coefficients = [float(c) for c in entry["coefficients"]]
    expected = str(entry["sha256"]).lower()
    dump = read_raw_f32(raw_f32_path)
    recomputed = window_table(coefficients, n)
    if dump.size == recomputed.size:
        diff = np.abs(dump.astype(np.float64) - recomputed.astype(np.float64))
        worst = int(np.argmax(diff))
        max_abs = float(diff[worst])
    else:
        worst, max_abs = -1, float("nan")
    return WindowReport(
        family=family,
        n=n,
        expected_sha256=expected,
        dump_sha256=hashlib.sha256(dump.tobytes()).hexdigest(),
        recomputed_sha256=table_sha256(recomputed),
        n_samples=int(dump.size),
        max_abs_diff=max_abs,
        worst_index=worst,
    )
