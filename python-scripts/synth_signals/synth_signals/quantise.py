# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""float64 ``[-1, 1]`` → int16, stated exactly once.

    s = clip(rint(x * 32768), -32768, 32767)

``32768`` is the scale, not ``32767``: the watch converts the other way with
``int16 → float × 1/32768`` exactly once at the ``audio_source`` seam (ADR 0003
d.2; ADR 0006 D3 records the ~0.00026 dB difference between the two conventions
rather than arguing about it). ``rint`` is round-half-to-even (IEEE 754 default),
so ``0.5 → 0``, ``1.5 → 2``, ``2.5 → 2`` on the 32768 grid.

Consequence, by design: a 0 dBFS sine (amplitude 1.0) produces ``+32768`` at
its positive peaks, which clips to ``+32767``, while its negative peaks reach
``-32768`` exactly. So the full-scale vectors *do* carry samples at the rails —
they are the clipping-flag test vectors for the AOP/clipping row of the
validation plan — and a −1 dBFS sine (amplitude 0.891) never gets within 9 %
of them. The flag threshold below is what the ground truth records per file.

Not a CLI module; used by :mod:`synth_signals.catalogue` and the tests.
"""

from __future__ import annotations

import numpy as np

#: Full-scale float amplitude ↔ int16 scale (ADR 0003 d.2, ADR 0006 D3).
FULL_SCALE = 32768.0

#: |sample| / FULL_SCALE at or above which a sample counts as "at the rail" for
#: the clipping flag recorded in the manifest. 0.99 × 32768 = 32440.32, so the
#: first int16 magnitude that trips it is 32441. The value is the generator's
#: own bookkeeping threshold; the watch's AOP/clipping detector threshold is a
#: validation-plan number and is not fixed by this constant.
CLIP_THRESHOLD = 0.99


def to_int16(x: np.ndarray) -> np.ndarray:
    """Quantise float samples on ``[-1, 1]`` to int16 — the one conversion."""
    x = np.asarray(x, dtype=np.float64)
    if not np.all(np.isfinite(x)):
        raise ValueError("non-finite sample in generator output")
    return np.clip(np.rint(x * FULL_SCALE), -FULL_SCALE, FULL_SCALE - 1.0).astype(np.int16)


def clipped_sample_count(s: np.ndarray, threshold: float = CLIP_THRESHOLD) -> int:
    """Number of int16 samples with ``|s| >= threshold * 32768``."""
    s = np.asarray(s)
    if s.dtype != np.int16:
        raise TypeError(f"expected int16 samples, got {s.dtype}")
    limit = int(np.ceil(threshold * FULL_SCALE))
    return int(np.count_nonzero(np.abs(s.astype(np.int32)) >= limit))
