# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""Per-bin level comparison — the magnitude-spectrum row of the tolerance table.

``docs/validation/golden-files.md``: *`spectral_core` magnitude spectrum vs
`numpy.fft.rfft` — per-bin level in dB — `atol = 0.01 dB` for bins ≥ −80 dBFS;
bins below are masked — float32 accumulation across 11 radix-2 stages.* Both
sides are already in dBFS under ADR 0006 D2/D3 (the golden ``spectrum`` arrays
are ``[N/2+1, 2]`` of ``[frequency, level]``; a device dump is the same
``level`` column); this module subtracts them bin by bin, masks the bins the
**golden** puts below the floor, and reports the largest remaining
|residual| against the atol.

Two rules, both deliberate:

* **The mask never widens the tolerance.** A bin below the floor is excluded
  from the comparison; a bin above it is compared at the full atol, whatever
  its level. The floor exists because relative float32 error grows in deep
  nulls (the "why not tighter" column), not to forgive near-floor bins.
* **The reference decides what is masked.** The golden is the definition of
  the signal; masking on the candidate would let a candidate hide a bin by
  under-reporting it. ``Report.n_candidate_above_floor_in_mask`` counts the
  bins where the candidate shows energy the golden does not — visible in the
  report, not a pass/fail criterion of this row.

A comparison with **no** bin above the floor (a silence golden) does not
pass: ``Report.passed`` requires ``n_compared > 0``, because "nothing was
compared" is not agreement.

CLI (see :mod:`golden_compare.cli`)::

    python -m golden_compare spectrum --golden A.npy --candidate B.npy [--atol-db 0.01] [--floor -80]
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.ma as ma


def residual_db(golden: np.ndarray, candidate: np.ndarray, floor_dbfs: float) -> ma.MaskedArray:
    """``candidate − golden`` per bin, in dB, masked wherever ``golden < floor_dbfs``.

    Both inputs are 1-D level arrays in dBFS on the same bin grid (same
    ``fs``, same ``N``); a length mismatch is a grid error and raises — it is
    never resolved by interpolation, because the row compares *bins*. The
    result is a :class:`numpy.ma.MaskedArray` in float64 whose mask is the
    golden's below-floor set; ``NaN`` on either side in a compared bin is a
    failure, not a masked value.
    """
    g = np.asarray(golden, dtype=np.float64)
    c = np.asarray(candidate, dtype=np.float64)
    if g.ndim != 1 or c.ndim != 1:
        raise ValueError(f"levels must be 1-D (got shapes {g.shape} and {c.shape}); pass the level column")
    if g.shape != c.shape:
        raise ValueError(f"bin grids differ: golden has {g.size} bins, candidate {c.size}; the row compares bins, not frequencies")
    mask = g < float(floor_dbfs)
    return ma.masked_array(c - g, mask=mask)


@dataclass(frozen=True)
class Report:
    """Outcome of :func:`check`: the largest compared |residual| against the atol."""

    max_abs: float                 #: largest |residual| over compared bins (NaN when none compared)
    worst_bin: int                 #: index of that bin (−1 when none compared)
    n_compared: int
    n_masked: int
    atol_db: float
    floor_dbfs: float
    n_candidate_above_floor_in_mask: int = 0   #: candidate bins ≥ floor where the golden is < floor (informational)

    @property
    def passed(self) -> bool:
        """True iff at least one bin was compared and every compared |residual| ≤ ``atol_db`` (NaN fails)."""
        return self.n_compared > 0 and bool(np.isfinite(self.max_abs)) and self.max_abs <= self.atol_db

    def summary(self) -> str:
        verdict = "PASS" if self.passed else "FAIL"
        if self.n_compared == 0:
            detail = "no bin above the floor was compared"
        else:
            detail = f"max |Δ| = {self.max_abs:.6f} dB at bin {self.worst_bin}"
        return (
            f"{verdict}: {detail}; atol = {self.atol_db} dB; "
            f"{self.n_compared} bins compared, {self.n_masked} masked below {self.floor_dbfs} dBFS"
            + (f"; {self.n_candidate_above_floor_in_mask} masked bins where the candidate is above the floor"
               if self.n_candidate_above_floor_in_mask else "")
        )


def check(residual: ma.MaskedArray, atol_db: float, candidate: np.ndarray | None = None, floor_dbfs: float | None = None) -> Report:
    """Apply the atol to a :func:`residual_db` result.

    ``candidate`` and ``floor_dbfs`` are optional and only feed the
    informational ``n_candidate_above_floor_in_mask`` count; the verdict is
    the compared bins against ``atol_db`` and nothing else.
    """
    r = ma.asarray(residual, dtype=np.float64)
    mask = ma.getmaskarray(r)
    n_masked = int(mask.sum())
    n_compared = int(r.size - n_masked)
    if n_compared:
        absr = np.abs(np.asarray(r.filled(np.nan), dtype=np.float64))
        absr[mask] = -np.inf
        if np.isnan(absr[~mask]).any():
            worst = int(np.flatnonzero(np.isnan(absr))[0])
            max_abs = float("nan")
        else:
            worst = int(np.argmax(absr))
            max_abs = float(absr[worst])
    else:
        worst, max_abs = -1, float("nan")
    spurious = 0
    if candidate is not None and floor_dbfs is not None and n_masked:
        c = np.asarray(candidate, dtype=np.float64)
        spurious = int(np.count_nonzero(c[mask] >= float(floor_dbfs)))
    return Report(
        max_abs=max_abs,
        worst_bin=worst,
        n_compared=n_compared,
        n_masked=n_masked,
        atol_db=float(atol_db),
        floor_dbfs=float(floor_dbfs) if floor_dbfs is not None else float("nan"),
        n_candidate_above_floor_in_mask=spurious,
    )


def compare(golden: np.ndarray, candidate: np.ndarray, atol_db: float, floor_dbfs: float) -> Report:
    """``check(residual_db(golden, candidate, floor), atol)`` in one call."""
    return check(residual_db(golden, candidate, floor_dbfs), atol_db, candidate=candidate, floor_dbfs=floor_dbfs)
