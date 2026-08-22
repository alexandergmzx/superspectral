# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""Tier-0 synthetic signals — ground truth exact by construction.

The generator behind ``datasets/tier0-synthetic/`` (bibliography 10 P1). Every
signal is computed in float64 on ``[-1, 1]``, quantised to 16-bit once
(:mod:`synth_signals.quantise`), written as a mono RIFF/WAVE file
(:mod:`synth_signals.wavio`) and described — parameters, derived truths and the
sha256 of the bytes — in a tracked ``manifest.yaml`` (:mod:`synth_signals.manifest`).
The WAVs themselves are gitignored (``datasets/**/*.wav``) and regenerated.

CLI (run from ``python-scripts/synth_signals/``; see ``pyproject.toml``)::

    uv run python -m synth_signals list
    uv run python -m synth_signals generate --out ../../datasets/tier0-synthetic [--only NAME ...]
    uv run python -m synth_signals check    --out ../../datasets/tier0-synthetic

``generate`` writes every catalogue entry and the manifest. ``check`` is the
reproducibility test: it regenerates every entry **in memory**, compares the
sha256 of the bytes it would write against the tracked manifest, and — when the
file is on disk — against the bytes on disk too; any drift is exit status 1.

Conventions (ADR 0006, accepted 2026-08-21)
-------------------------------------------
* 0 dBFS is a full-scale sine: amplitude 1.0 in float, which quantises to
  ``rint(32768 * x)`` clipped to ``[-32768, 32767]`` — ``32768`` and not ``32767``,
  the same seam the watch uses in reverse (ADR 0003 d.2, ADR 0006 D3). A 0 dBFS
  sine therefore *does* reach 32767 (through the clip), which is the deliberate
  clipping-flag vector; see :mod:`synth_signals.quantise`.
* For noise, ``level_dbfs`` sets the RMS to that of a sine at the same dBFS
  (``10**(L/20) / sqrt(2)``), so a −20 dBFS white noise and a −20 dBFS sine carry
  the same total power under the S1/S2 scaling of ADR 0006 D2.
* Bin centres are quoted for the watch default ``N = 4096`` at 32 kHz
  (``fs / N = 7.8125 Hz``): 437.5 Hz is bin 56, 1000 Hz is bin 128, 440 Hz is
  bin 56.32 (off-bin). The bin index is recorded per file as ground truth.

Reproducibility — the libm risk
-------------------------------
The signals go through ``numpy.sin``/``cos``/``exp`` in float64, ``numpy.fft``
(pink noise) and ``scipy.signal.lfilter`` (the vowel). Those are not
bit-reproducible across CPUs, NumPy builds (SIMD dispatch: AVX2 vs AVX-512 vs
scalar) or libm versions. The int16 quantisation absorbs that: a float64
difference flips ``rint`` only when ``x·32768`` sits closer to a half-integer
than the difference itself. Measured 2026-08-21 over all 21 files (numpy 2.5.2,
scipy 1.18.1, x86_64): the nearest any sample comes to a rounding boundary is
4.7×10⁻⁸ LSB (pink noise), while a last-ULP float64 error at that magnitude is
~4×10⁻¹³ LSB — a libm would have to disagree by ~10⁵ ULP to change one byte.
The test ``test_no_sample_sits_within_1e_9_lsb_of_a_rounding_boundary`` keeps
that margin from eroding when the catalogue grows. It is a margin, not a
proof: if ``check`` reports drift on another machine with an unchanged
generator, the first suspects are ``numpy``/``scipy`` versions (the manifest
records them) and the CPU; the fix is to pin, not to widen the comparison.
``numpy.random.default_rng`` (PCG64) output is stable across NumPy versions by
policy, so the *noise draws* are not part of this risk; their FFT shaping is.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
