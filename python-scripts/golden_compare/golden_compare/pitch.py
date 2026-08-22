# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""f0-track comparison — the cents rows and the `mir_eval` voicing/accuracy rows.

``docs/validation/golden-files.md``: *Device f0 vs Praat — median |Δcents|
over voiced frames — ≤ 5 cents (injection) / ≤ 20 cents (acoustic)*, and
*Device voicing vs Praat — VR / VFA — ≥ 90 % / ≤ 10 %*; the RPA / RCA / OA
rows of ``docs/validation/README.md`` come from ``mir_eval.melody`` directly.
:func:`compare_tracks` applies **both** table rows: its verdict is the median
row *and* the voicing row (``VR ≥ 90 %``, ``VFA ≤ 10 %``), so an estimator
that is accurate on the few frames it chooses to voice does not pass.

**The frame-grid trap is the reason this module exists** (golden-files.md,
"Gotchas"): Praat places its first frame at ``t1 = (duration − (nFrames−1)·dt)/2``
and the device frames from sample 0 with a hop, so the two tracks are never
on the same grid, and comparing them by index turns a constant time offset
into cents error at every note onset and all through a vibrato. *Resample
the host f0 track onto the device's frame times before comparing; never
compare frame indices.* :func:`resample_to_times` does that — linear in
``log2(f)`` (i.e. in cents), over **voiced runs only**: a device time that
falls between two voiced reference frames gets the interpolated value, any
other time gets the unvoiced sentinel. Nothing is ever interpolated across
an unvoiced gap, because the value there is not a frequency.

The sentinel is Praat's ``0`` (``outputs[].unvoiced_sentinel`` in the
manifest) and the same convention mir_eval uses: ``0`` = unvoiced, and a
negative value = unvoiced but pitched. :func:`cents` refuses non-positive
input outright — a ``0`` read as a frequency is the error the manifest field
warns about, and it must fail loudly rather than produce −∞ cents.

CLI (see :mod:`golden_compare.cli`)::

    python -m golden_compare pitch --golden ref.npy --candidate dev.npy --path injection
"""

from __future__ import annotations

from dataclasses import dataclass

import mir_eval.melody
import numpy as np

from .tolerances import VOICING_FALSE_ALARM_MAX_PERCENT, VOICING_RECALL_MIN_PERCENT

#: Praat's and mir_eval's unvoiced marker (manifest `outputs[].unvoiced_sentinel`).
UNVOICED = 0.0

#: The voicing row of the table, as fractions: VR ≥ 0.9, VFA ≤ 0.1 (golden-files.md
#: "Device voicing vs Praat — VR / VFA — ≥ 90 % / ≤ 10 %"; the constants are in %).
DEFAULT_VR_MIN = VOICING_RECALL_MIN_PERCENT.value / 100.0
DEFAULT_VFA_MAX = VOICING_FALSE_ALARM_MAX_PERCENT.value / 100.0

#: The RPA threshold of the research question and of `docs/validation/README.md`
#: ("RPA @ 50 / 25 / 10 cents"); 50 is also `mir_eval.melody`'s own default.
DEFAULT_CENT_TOLERANCE = 50.0


def cents(a: np.ndarray | float, b: np.ndarray | float) -> np.ndarray | float:
    """``1200·log2(a/b)`` — the interval from ``b`` to ``a`` in cents; refuses non-positive input."""
    a64 = np.asarray(a, dtype=np.float64)
    b64 = np.asarray(b, dtype=np.float64)
    if np.any(~(a64 > 0)) or np.any(~(b64 > 0)):
        raise ValueError("cents() takes frequencies > 0 only; the unvoiced sentinel is not a frequency (mask it first)")
    out = 1200.0 * np.log2(a64 / b64)
    return float(out) if out.ndim == 0 else out


def voiced_mask(f0: np.ndarray, sentinel: float = UNVOICED) -> np.ndarray:
    """Frames carrying a frequency: ``f0 > 0`` and ``f0 != sentinel``."""
    f = np.asarray(f0, dtype=np.float64)
    return (f > 0) & (f != float(sentinel))


def _check_track(t: np.ndarray, f0: np.ndarray, name: str) -> tuple[np.ndarray, np.ndarray]:
    t64 = np.asarray(t, dtype=np.float64)
    f64 = np.asarray(f0, dtype=np.float64)
    if t64.ndim != 1 or f64.shape != t64.shape:
        raise ValueError(f"{name}: time and f0 must be 1-D and the same length (got {t64.shape} and {f64.shape})")
    if t64.size and not np.all(np.diff(t64) > 0):
        raise ValueError(f"{name}: frame times must be strictly increasing")
    return t64, f64


def resample_to_times(t_ref: np.ndarray, f0_ref: np.ndarray, t_dev: np.ndarray, sentinel: float = UNVOICED) -> np.ndarray:
    """The reference track at the device's frame times, linear in ``log2(f)``, voiced runs only.

    For each ``t`` in ``t_dev``: if ``t`` lies between two consecutive
    reference frames that are **both** voiced, the value is the log-linear
    interpolation between them (a frame time hit exactly returns that
    frame); otherwise — inside an unvoiced gap, on an unvoiced frame, or
    outside ``[t_ref[0], t_ref[-1]]`` — the value is ``sentinel``. The
    returned array has ``t_dev``'s shape and the sentinel convention of the
    input, so it can go straight into :func:`median_abs_cents`.
    """
    t_ref, f0_ref = _check_track(t_ref, f0_ref, "reference")
    t = np.asarray(t_dev, dtype=np.float64)
    if t.ndim != 1:
        raise ValueError("t_dev must be 1-D")
    out = np.full(t.shape, float(sentinel), dtype=np.float64)
    if t_ref.size == 0 or t.size == 0:
        return out
    voiced = voiced_mask(f0_ref, sentinel)
    if t_ref.size == 1:
        hit = (t == t_ref[0]) & voiced[0]
        out[hit] = f0_ref[0]
        return out
    i = np.clip(np.searchsorted(t_ref, t, side="right") - 1, 0, t_ref.size - 2)
    left, right = t_ref[i], t_ref[i + 1]
    inside = (t >= t_ref[0]) & (t <= t_ref[-1])
    both = voiced[i] & voiced[i + 1]
    with np.errstate(divide="ignore", invalid="ignore"):
        frac = (t - left) / (right - left)
        lf = np.log2(np.where(voiced, f0_ref, 1.0))   # log only where voiced; the rest is never selected
        interp = 2.0 ** (lf[i] + frac * (lf[i + 1] - lf[i]))
    sel = inside & both
    out[sel] = interp[sel]
    # An exact hit on a voiced frame returns that frame's value verbatim — not the
    # log2/2** round trip, which is 1e-13 off — so a track resampled onto its own
    # grid is bit-identical and a golden compared with itself reads 0.000 cents.
    hit_left = inside & (t == left) & voiced[i]
    out[hit_left] = f0_ref[i[hit_left]]
    hit_right = inside & (t == right) & voiced[i + 1]
    out[hit_right] = f0_ref[i[hit_right] + 1]
    return out


def jointly_voiced(f0_ref: np.ndarray, f0_est: np.ndarray, sentinel: float = UNVOICED) -> np.ndarray:
    """Mask of frames voiced on both sides (the frames the median row is taken over)."""
    r = np.asarray(f0_ref, dtype=np.float64)
    e = np.asarray(f0_est, dtype=np.float64)
    if r.shape != e.shape:
        raise ValueError(f"tracks must be on one grid (got {r.shape} and {e.shape}); resample_to_times() first")
    return voiced_mask(r, sentinel) & voiced_mask(e, sentinel)


def median_abs_cents(f0_ref: np.ndarray, f0_est: np.ndarray, sentinel: float = UNVOICED) -> float:
    """Median |cents(est, ref)| over jointly voiced frames of two tracks **on the same grid**; NaN if none.

    Same grid means the caller has already resampled (the frame-grid trap);
    this function refuses tracks of different length rather than guess.
    """
    both = jointly_voiced(f0_ref, f0_est, sentinel)
    if not both.any():
        return float("nan")
    r = np.asarray(f0_ref, dtype=np.float64)[both]
    e = np.asarray(f0_est, dtype=np.float64)[both]
    return float(np.median(np.abs(cents(e, r))))


def mir_eval_melody(
    ref_t: np.ndarray,
    ref_f0: np.ndarray,
    est_t: np.ndarray,
    est_f0: np.ndarray,
    cent_tolerance: float = DEFAULT_CENT_TOLERANCE,
) -> dict[str, float]:
    """``{RPA, RCA, OA, VR, VFA}`` as fractions in ``[0, 1]`` from ``mir_eval.melody.evaluate``.

    mir_eval resamples the estimate onto the reference grid itself (linear in
    cents, zeros held) and scores voiced reference frames; the sentinel
    convention is its own (``0`` unvoiced, negative = unvoiced but pitched).
    ``cent_tolerance`` is the RPA/RCA/OA threshold — 50 cents per the
    research question and the validation README; pass 25 or 10 for the
    finer tiers of that table.
    """
    ref_t, ref_f0 = _check_track(ref_t, ref_f0, "reference")
    est_t, est_f0 = _check_track(est_t, est_f0, "estimate")
    scores = mir_eval.melody.evaluate(ref_t, ref_f0, est_t, est_f0, cent_tolerance=float(cent_tolerance))
    return {
        "RPA": float(scores["Raw Pitch Accuracy"]),
        "RCA": float(scores["Raw Chroma Accuracy"]),
        "OA": float(scores["Overall Accuracy"]),
        "VR": float(scores["Voicing Recall"]),
        "VFA": float(scores["Voicing False Alarm"]),
    }


@dataclass(frozen=True)
class PitchReport:
    """Outcome of :func:`compare_tracks`: the median row plus the mir_eval rows."""

    median_abs_cents: float
    n_jointly_voiced: int
    n_ref_voiced: int
    n_est_voiced: int
    median_limit_cents: float
    metrics: dict[str, float]
    cent_tolerance: float
    vr_min: float = DEFAULT_VR_MIN       #: voicing row: VR ≥ this fraction
    vfa_max: float = DEFAULT_VFA_MAX     #: voicing row: VFA ≤ this fraction

    @property
    def median_passed(self) -> bool:
        """The median row: jointly voiced frames exist and the median |Δcents| is within the limit (NaN fails)."""
        return self.n_jointly_voiced > 0 and bool(np.isfinite(self.median_abs_cents)) and self.median_abs_cents <= self.median_limit_cents

    @property
    def voicing_passed(self) -> bool:
        """The voicing row: ``VR ≥ vr_min`` and ``VFA ≤ vfa_max`` (mir_eval's fractions; NaN fails)."""
        vr, vfa = self.metrics["VR"], self.metrics["VFA"]
        return bool(np.isfinite(vr) and np.isfinite(vfa)) and vr >= self.vr_min and vfa <= self.vfa_max

    @property
    def passed(self) -> bool:
        """True iff **both** rows pass — a track that is accurate on the few frames it voices is not a pass."""
        return self.median_passed and self.voicing_passed

    def summary(self) -> str:
        verdict = "PASS" if self.passed else "FAIL"
        m = self.metrics
        return (
            f"{verdict}: median |Δcents| = {self.median_abs_cents:.3f} (limit {self.median_limit_cents}) over "
            f"{self.n_jointly_voiced} jointly voiced frames (ref {self.n_ref_voiced}, est {self.n_est_voiced})"
            f"{'' if self.median_passed else ' [median row FAILS]'}; "
            f"mir_eval @ {self.cent_tolerance:g} cents: RPA {100 * m['RPA']:.1f} %  RCA {100 * m['RCA']:.1f} %  "
            f"OA {100 * m['OA']:.1f} %  VR {100 * m['VR']:.1f} %  VFA {100 * m['VFA']:.1f} % "
            f"(voicing row: VR ≥ {100 * self.vr_min:g} %, VFA ≤ {100 * self.vfa_max:g} %"
            f"{'' if self.voicing_passed else ' — FAILS'})"
        )


def compare_tracks(
    ref_t: np.ndarray,
    ref_f0: np.ndarray,
    est_t: np.ndarray,
    est_f0: np.ndarray,
    median_limit_cents: float,
    sentinel: float = UNVOICED,
    cent_tolerance: float = DEFAULT_CENT_TOLERANCE,
    vr_min: float = DEFAULT_VR_MIN,
    vfa_max: float = DEFAULT_VFA_MAX,
) -> PitchReport:
    """Resample the reference onto the estimate's grid, take the median row, add the mir_eval rows; the verdict is the median row AND the voicing row."""
    ref_on_est = resample_to_times(ref_t, ref_f0, est_t, sentinel)
    est = np.asarray(est_f0, dtype=np.float64)
    return PitchReport(
        median_abs_cents=median_abs_cents(ref_on_est, est, sentinel),
        n_jointly_voiced=int(jointly_voiced(ref_on_est, est, sentinel).sum()),
        n_ref_voiced=int(voiced_mask(ref_f0, sentinel).sum()),
        n_est_voiced=int(voiced_mask(est, sentinel).sum()),
        median_limit_cents=float(median_limit_cents),
        metrics=mir_eval_melody(ref_t, ref_f0, est_t, est_f0, cent_tolerance),
        cent_tolerance=float(cent_tolerance),
        vr_min=float(vr_min),
        vfa_max=float(vfa_max),
    )
