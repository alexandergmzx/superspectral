# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""The tolerance table of ``docs/validation/golden-files.md``, as constants.

**The document is the only definition; this module is a copy.** ADR 0009
decision 2: the limits live in exactly one Apache-licensed file on the
validation side, and a limit is widened only with a recorded reason in that
table *and* in the commit message. Code cannot be that file, so every
constant here carries the row it was copied from and the literal text the
number appears as, and ``tests/test_tolerances_match_golden_files_md.py``
greps the document for each one: a number edited here without the table
moving — or in the table without this module moving — fails the suite. Every
value is ``(prov.)`` exactly as the table says it is.

The constants are reached by name::

    from golden_compare.tolerances import SPECTRUM_ATOL_DB, SPECTRUM_FLOOR_DBFS

or by row through :data:`TABLE`, which the test iterates. Nothing here is a
default a caller may silently inherit: the CLI prints the tolerance it
applied next to the result, every time.

CLI: none — ``python -m golden_compare`` prints the table under ``tolerances``::

    python -m golden_compare tolerances
"""

from __future__ import annotations

from dataclasses import dataclass

#: The document this module copies. Repository-relative, like the manifest's
#: own ``tolerances.source`` pointer (manifest.schema.yaml, `const`).
SOURCE = "docs/validation/golden-files.md"


@dataclass(frozen=True)
class Tolerance:
    """One limit, bound to the line of the table it was copied from.

    ``row`` is a substring that identifies exactly one table row of the
    document (the test asserts the "exactly one"); ``doc_text`` is the literal
    the number appears as in that row, Unicode minus and all, so the grep is
    for the text a reviewer reads and not for a regex of it. ``value`` is
    ``None`` only for the digest row, whose tolerance is the word *exact*.
    """

    name: str
    value: float | None
    unit: str
    row: str
    doc_text: str


# -- the table, row by row, in the document's order ---------------------------

F0_INJECTION_MEDIAN_ABS_CENTS = Tolerance(
    "F0_INJECTION_MEDIAN_ABS_CENTS", 5.0, "cents",
    row="Device f0 vs Praat, injection path", doc_text="≤ 5 cents",
)
F0_ACOUSTIC_MEDIAN_ABS_CENTS = Tolerance(
    "F0_ACOUSTIC_MEDIAN_ABS_CENTS", 20.0, "cents",
    row="Device f0 vs Praat, acoustic path", doc_text="≤ 20 cents",
)
VOICING_RECALL_MIN_PERCENT = Tolerance(
    "VOICING_RECALL_MIN_PERCENT", 90.0, "%",
    row="Device voicing vs Praat", doc_text="≥ 90 %",
)
VOICING_FALSE_ALARM_MAX_PERCENT = Tolerance(
    "VOICING_FALSE_ALARM_MAX_PERCENT", 10.0, "%",
    row="Device voicing vs Praat", doc_text="≤ 10 %",
)
WINDOW_DIGEST_EXACT = Tolerance(
    "WINDOW_DIGEST_EXACT", None, "sha256",
    row="window **table digest** per `(family, N)`", doc_text="**exact**",
)
FAST_LOG_MAX_ABS_DB = Tolerance(
    "FAST_LOG_MAX_ABS_DB", 0.005, "dB",
    row="`spectral_to_dbfs_fast()` vs `log10()` in double", doc_text="**≤ 0.005 dB**",
)
WINDOW_COEFFICIENTS_ATOL = Tolerance(
    "WINDOW_COEFFICIENTS_ATOL", 1e-6, "(window sample, float32)",
    row="window coefficients vs `scipy.signal.windows.general_cosine", doc_text="`atol = 1e-6`",
)
WINDOW_COEFFICIENTS_RTOL = Tolerance(
    "WINDOW_COEFFICIENTS_RTOL", 0.0, "relative",
    row="window coefficients vs `scipy.signal.windows.general_cosine", doc_text="`rtol = 0`",
)
SPECTRUM_ATOL_DB = Tolerance(
    "SPECTRUM_ATOL_DB", 0.01, "dB",
    row="magnitude spectrum vs `numpy.fft.rfft`", doc_text="`atol = 0.01 dB`",
)
SPECTRUM_FLOOR_DBFS = Tolerance(
    "SPECTRUM_FLOOR_DBFS", -80.0, "dBFS",
    row="magnitude spectrum vs `numpy.fft.rfft`", doc_text="−80 dBFS",
)
BACKEND_AGREEMENT_RTOL = Tolerance(
    "BACKEND_AGREEMENT_RTOL", 1e-4, "relative, linear magnitude",
    row="backend agreement", doc_text="`rtol = 1e-4`",
)
PEAK_INTERPOLATION_MAX_CENTS = Tolerance(
    "PEAK_INTERPOLATION_MAX_CENTS", 3.0, "cents",
    row="Interpolated peak frequency vs known synthetic tone", doc_text="≤ 3 cents",
)
FORMANT_MAX_PERCENT = Tolerance(
    "FORMANT_MAX_PERCENT", 5.0, "%",
    row="Device F1/F2 vs Praat Burg", doc_text="≤ 5 %",
)
FORMANT_MAX_HZ = Tolerance(
    "FORMANT_MAX_HZ", 50.0, "Hz",
    row="Device F1/F2 vs Praat Burg", doc_text="or 50 Hz",
)
LTAS_BAND_MAX_DB = Tolerance(
    "LTAS_BAND_MAX_DB", 0.2, "dB per band",
    row="Device LTAS band levels vs Praat `To Ltas`", doc_text="≤ 0.2 dB",
)
FHE_MAX_HZ = Tolerance(
    "FHE_MAX_HZ", 50.0, "Hz",
    row="Device FHE / SPR vs host", doc_text="≤ 50 Hz",
)
SPR_MAX_DB = Tolerance(
    "SPR_MAX_DB", 0.5, "dB",
    row="Device FHE / SPR vs host", doc_text="≤ 0.5 dB",
)

#: Every constant above, in table order. The grep test walks this tuple, so a
#: constant that is not listed here is not guarded — add it to both places.
TABLE: tuple[Tolerance, ...] = (
    F0_INJECTION_MEDIAN_ABS_CENTS,
    F0_ACOUSTIC_MEDIAN_ABS_CENTS,
    VOICING_RECALL_MIN_PERCENT,
    VOICING_FALSE_ALARM_MAX_PERCENT,
    WINDOW_DIGEST_EXACT,
    FAST_LOG_MAX_ABS_DB,
    WINDOW_COEFFICIENTS_ATOL,
    WINDOW_COEFFICIENTS_RTOL,
    SPECTRUM_ATOL_DB,
    SPECTRUM_FLOOR_DBFS,
    BACKEND_AGREEMENT_RTOL,
    PEAK_INTERPOLATION_MAX_CENTS,
    FORMANT_MAX_PERCENT,
    FORMANT_MAX_HZ,
    LTAS_BAND_MAX_DB,
    FHE_MAX_HZ,
    SPR_MAX_DB,
)

#: Which f0 row applies to which measurement path (validation README, two-path
#: rule): only the injection path may carry a "vs Praat" claim.
F0_MEDIAN_ABS_CENTS_BY_PATH: dict[str, Tolerance] = {
    "injection": F0_INJECTION_MEDIAN_ABS_CENTS,
    "acoustic": F0_ACOUSTIC_MEDIAN_ABS_CENTS,
}


def format_table() -> str:
    """The table as text, one constant per line, for the CLI."""
    width = max(len(t.name) for t in TABLE)
    lines = [f"source: {SOURCE}  (the only definition; every value is (prov.))"]
    for t in TABLE:
        value = "exact" if t.value is None else repr(t.value)
        lines.append(f"{t.name:<{width}}  {value:>8} {t.unit:<30}  row: {t.row}")
    return "\n".join(lines)
