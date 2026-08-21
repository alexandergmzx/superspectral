#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""Generate the spectrogram colormap LUT for `display_backend` (ADR 0011).

The panel is driven RGB565 (5/6/5 bits) while every published perceptually
uniform colormap is defined in 8-bit sRGB. Rounding each channel independently
is the obvious conversion and the wrong one: it minimises per-channel error, not
perceptual error, and it does not know that the map has to stay
luminance-monotone. A smooth dB ramp then collapses into flat runs of identical
RGB565 words whose boundaries read as contour lines - spurious structure in a
spectrogram, which is the one artefact a measurement instrument must not invent.

This script instead *designs the ramp in RGB565*: it chooses the sequence of
representable words that minimises total CIE76 dE to the published map subject
to a hard non-decreasing L* constraint (a shortest-path problem, solved exactly
by dynamic programming over the candidate words at each index), and reports the
residual banding as numbers instead of an opinion.

    # emit the default map to stdout
    python3 python-scripts/gen_colormap_lut.py --map cividis

    # with the ordered-dither helper, into the firmware component
    python3 python-scripts/gen_colormap_lut.py --map cividis --dither \
        -o firmware/twatch-s3/components/display_backend/include/spectral_cmap_cividis.h

    # the numbers ADR 0011 quotes, for every vendored map (what CI runs)
    python3 python-scripts/gen_colormap_lut.py --self-test

Standard library only, on purpose: this repository's Python has NumPy, the
ESP-IDF venv does not, and a LUT generator a reviewer cannot run in a bare
container is a LUT nobody re-derives. The whole job is 256 x 27 x 27 candidate
transitions and runs in well under a second; NumPy would buy nothing measurable.

Exit status: 0 when the self-test passes (or a header was written), 1 otherwise.

Colour science implemented here: sRGB (IEC 61966-2-1 transfer function) ->
linear -> CIE XYZ (D65) -> CIELAB -> CIE76 dE. CIE76 is the "-ish" in "dE-ish":
it over-weights chroma differences at high chroma relative to CAM02-UCS, the
space viridis and cividis were designed in (bibliography 05 #78). It is used
here to rank candidate words a few quantisation steps apart, where every colour
difference metric agrees on the ordering, and as a reported step size that
should be read as a relative magnitude, not as a JND count.
"""

from __future__ import annotations

import argparse
import math
import re
import sys

# --------------------------------------------------------------------------
# Control points.
#
# Source: matplotlib 3.6.3 `matplotlib/_cm_listed.py` (`_cividis_data`,
# `_viridis_data`, `_magma_data`), Ubuntu package python3-matplotlib
# 3.6.3-1ubuntu5, read 2026-08-21. matplotlib is BSD-style/PSF-derived licensed
# (bibliography 06 #37). Upstream of that:
#   cividis  - Nunez, Anderton & Renslow (2018), PLOS ONE 13(7):e0199239
#              (bibliography 05 #76). CVD-optimised, linear luminance, 2 hues.
#   viridis  - Smith & van der Walt (2015), CAM02-UCS derivation
#              (bibliography 05 #78).
#   magma    - same derivation, dark-background variant.
#   batlow   - Crameri et al. (bibliography 05 #77; tables via 06 #37) is NOT
#              vendored here: its table is not in this repository yet, and
#              inventing one is worse than not shipping it. See MISSING_MAPS.
#
# Transformation applied to the upstream tables, so that this file is
# reproducible from them: every 4th entry of the 256-entry table plus the last
# (65 control points), each channel rounded to 8 bits as round(255*v). Verified
# 2026-08-21 by parsing `_cm_listed.py` with `ast`: 65 points at indices
# 0, 4, ..., 252, 255, and 0 of 195 channels differ from round(255*v).
#
# Cost of the compression, RE-MEASURED 2026-08-21 for the reconstruction this
# file actually performs -- `ramp8()`, i.e. linear interpolation between the
# *8-bit* control points above, rounded to 8 bits -- against the full 256-entry
# float table, for cividis / viridis / magma:
#
#   max |delta| = 3.08 / 1.23 / 1.01 of 255      max CIE76 dE = 1.14 / 1.12 / 0.93
#
# An earlier version of this comment quoted 2.50 / 0.41 / 0.46 and dE 0.375 /
# 0.072 / 0.152. Those figures are real but describe a different computation:
# float control points interpolated in float, i.e. the compression alone with
# the 8-bit rounding of the control points removed. They understate the shipped
# error by up to 15x (viridis). ADR 0011 quotes the 0.375 figure and needs the
# same correction.
#
# Read the true figure against the LUT's own worst fidelity error (dE 2.91 for
# cividis, 2.56 viridis, 3.56 magma, self-test 2026-08-21): the control-point
# compression is roughly a third of the RGB565 quantisation error, not an order
# below it. It is still the smaller term, and the alternative -- vendoring three
# 256-entry tables -- is 4x the table for a third of the error. Reproduce with:
# parse `_cividis_data` / `_viridis_data` / `_magma_data` out of
# `/usr/lib/python3/dist-packages/matplotlib/_cm_listed.py` with `ast`, compare
# `ramp8(name)` against `[tuple(255*c) for c in table]` channel-wise and in
# CIE76.
#
# LICENCE ITEM (ADR 0011, open): the numeric tables travel with matplotlib's
# licence here; the cividis table originates in a CC BY 4.0 paper and the
# viridis family was released CC0 by its authors. Confirm the exact terms and
# record them in NOTICE before a generated header is committed into firmware
# (ADR 0004 admits MIT/BSD/Apache-2.0/CC0 on the link line).
#
# Format: (index, r8, g8, b8) with index in [0, 255].
# --------------------------------------------------------------------------

CONTROL_POINTS: dict[str, tuple[tuple[int, int, int, int], ...]] = {
    "cividis": (
        (0, 0, 34, 78), (4, 0, 37, 84), (8, 0, 40, 91), (12, 0, 43, 98), (16, 0, 46, 106),
        (20, 0, 48, 112), (24, 5, 51, 113), (28, 18, 53, 112), (32, 26, 56, 111),
        (36, 33, 59, 110), (40, 39, 62, 110), (44, 45, 65, 109), (48, 50, 67, 109),
        (52, 54, 70, 108), (56, 59, 73, 108), (60, 63, 76, 108), (64, 67, 78, 108),
        (68, 71, 81, 108), (72, 75, 84, 108), (76, 79, 87, 108), (80, 83, 90, 109),
        (84, 86, 92, 109), (88, 90, 95, 110), (92, 94, 98, 110), (96, 97, 101, 111),
        (100, 101, 104, 112), (104, 104, 106, 113), (108, 108, 109, 114), (112, 111, 112, 115),
        (116, 114, 115, 116), (120, 118, 118, 118), (124, 121, 121, 119), (128, 125, 124, 120),
        (132, 128, 127, 120), (136, 132, 130, 121), (140, 136, 133, 120), (144, 140, 136, 120),
        (148, 144, 139, 120), (152, 147, 142, 120), (156, 151, 145, 119), (160, 155, 148, 118),
        (164, 159, 151, 117), (168, 163, 154, 116), (172, 167, 157, 115), (176, 171, 160, 114),
        (180, 175, 164, 113), (184, 180, 167, 111), (188, 184, 170, 110), (192, 188, 174, 108),
        (196, 192, 177, 106), (200, 196, 180, 104), (204, 200, 184, 102), (208, 205, 187, 99),
        (212, 209, 191, 97), (216, 213, 194, 94), (220, 218, 198, 91), (224, 222, 201, 88),
        (228, 226, 205, 84), (232, 231, 209, 80), (236, 235, 212, 75), (240, 240, 216, 70),
        (244, 245, 220, 65), (248, 249, 224, 58), (252, 254, 228, 52), (255, 254, 232, 56)
    ),
    "viridis": (
        (0, 68, 1, 84), (4, 70, 7, 90), (8, 71, 13, 96), (12, 71, 19, 101), (16, 72, 24, 106),
        (20, 72, 29, 111), (24, 72, 35, 116), (28, 72, 40, 120), (32, 71, 45, 123),
        (36, 70, 50, 126), (40, 69, 55, 129), (44, 68, 59, 132), (48, 66, 64, 134),
        (52, 64, 69, 136), (56, 62, 73, 137), (60, 61, 78, 138), (64, 59, 82, 139),
        (68, 57, 86, 140), (72, 55, 91, 141), (76, 53, 95, 141), (80, 51, 99, 141),
        (84, 49, 103, 142), (88, 47, 107, 142), (92, 46, 111, 142), (96, 44, 114, 142),
        (100, 42, 118, 142), (104, 41, 122, 142), (108, 39, 126, 142), (112, 38, 130, 142),
        (116, 37, 133, 142), (120, 35, 137, 142), (124, 34, 141, 141), (128, 33, 145, 140),
        (132, 31, 148, 140), (136, 31, 152, 139), (140, 30, 156, 137), (144, 31, 160, 136),
        (148, 32, 163, 134), (152, 34, 167, 133), (156, 37, 171, 130), (160, 40, 174, 128),
        (164, 45, 178, 125), (168, 50, 182, 122), (172, 56, 185, 119), (176, 63, 188, 115),
        (180, 70, 192, 111), (184, 78, 195, 107), (188, 86, 198, 103), (192, 94, 201, 98),
        (196, 103, 204, 92), (200, 112, 207, 87), (204, 122, 209, 81), (208, 132, 212, 75),
        (212, 142, 214, 69), (216, 152, 216, 62), (220, 162, 218, 55), (224, 173, 220, 48),
        (228, 184, 222, 41), (232, 194, 223, 35), (236, 205, 225, 29), (240, 216, 226, 25),
        (244, 226, 228, 24), (248, 236, 229, 27), (252, 246, 230, 32), (255, 253, 231, 37)
    ),
    "magma": (
        (0, 0, 0, 4), (4, 2, 1, 9), (8, 3, 3, 18), (12, 6, 5, 26), (16, 10, 8, 34),
        (20, 14, 11, 43), (24, 19, 13, 52), (28, 24, 15, 61), (32, 29, 17, 71),
        (36, 34, 17, 80), (40, 41, 17, 90), (44, 47, 17, 99), (48, 54, 16, 107),
        (52, 61, 15, 113), (56, 68, 15, 118), (60, 74, 16, 121), (64, 81, 18, 124),
        (68, 87, 21, 126), (72, 93, 23, 127), (76, 100, 26, 128), (80, 106, 28, 129),
        (84, 112, 31, 129), (88, 118, 33, 129), (92, 124, 35, 130), (96, 131, 38, 129),
        (100, 137, 40, 129), (104, 144, 42, 129), (108, 150, 44, 128), (112, 156, 46, 127),
        (116, 163, 48, 126), (120, 170, 51, 125), (124, 176, 53, 123), (128, 183, 55, 121),
        (132, 189, 57, 119), (136, 196, 60, 117), (140, 202, 62, 114), (144, 208, 65, 111),
        (148, 214, 69, 108), (152, 220, 72, 105), (156, 226, 77, 102), (160, 231, 82, 99),
        (164, 235, 87, 96), (168, 239, 93, 94), (172, 242, 100, 92), (176, 245, 107, 92),
        (180, 247, 114, 92), (184, 249, 121, 93), (188, 250, 129, 95), (192, 252, 137, 97),
        (196, 252, 144, 101), (200, 253, 152, 105), (204, 254, 159, 109), (208, 254, 167, 114),
        (212, 254, 174, 119), (216, 254, 182, 124), (220, 254, 189, 130), (224, 254, 196, 136),
        (228, 254, 204, 143), (232, 254, 211, 149), (236, 253, 218, 156), (240, 253, 226, 163),
        (244, 253, 233, 170), (248, 252, 240, 178), (252, 252, 247, 185), (255, 252, 253, 191)
    ),
}

# Maps named in ADR 0011 whose tables are deliberately absent, with the reason.
MISSING_MAPS = {
    "batlow": (
        "batlow's table is not vendored in this repository. Fetch the Scientific "
        "Colour Maps release (bibliography 06 #37, MIT) into a vendor directory, "
        "add its 65 control points to CONTROL_POINTS with the release version in "
        "the comment, and re-run. Do not hand-tune an approximation."
    ),
}

# Ordered-dither threshold matrix: the classic 4x4 recursive Bayer matrix
# (M_1 = [[0,2],[3,1]], M_{n+1} = 4*M_n + M_1 applied blockwise), a permutation
# of 0..15 whose spatial spectrum is as close to blue noise as a 4x4 periodic
# tile gets. Reference: B. E. Bayer, "An optimum method for two-level rendition
# of continuous-tone pictures", IEEE International Conference on Communications,
# 1973, 26-11..26-15. NOTE (ADR 0011 open item): that paper has no bibliography
# row yet; add one under 05 `colormaps-visualization` when the ADR is accepted.
BAYER_4X4 = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)

LUT_LEN = 256

# (red bits, green bits, blue bits). RGB565 is the panel default; RGB666 is what
# ST7789 `COLMOD (3Ah) = 06h` would give, at 3 bytes/pixel on the SPI bus - it is
# computed here only so ADR 0011's escape hatch has a number attached to it.
RGB565 = (5, 6, 5)
RGB666 = (6, 6, 6)

# --------------------------------------------------------------------------
# Colour science (stdlib)
# --------------------------------------------------------------------------


def srgb_to_linear(c8: float) -> float:
    """8-bit sRGB channel -> linear light, IEC 61966-2-1 transfer function."""
    c = c8 / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb_to_lab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """8-bit sRGB -> CIELAB (D65 white point, the sRGB reference white)."""
    r, g, b = (srgb_to_linear(c) for c in rgb)
    # sRGB D65 primaries (IEC 61966-2-1).
    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b
    xn, yn, zn = 0.95047, 1.00000, 1.08883
    delta = 6.0 / 29.0

    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > delta ** 3 else t / (3 * delta * delta) + 4.0 / 29.0

    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def de76(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    """CIE76 dE*ab between two 8-bit sRGB triples."""
    return math.dist(rgb_to_lab(a), rgb_to_lab(b))


def lstar(rgb: tuple[int, int, int]) -> float:
    return rgb_to_lab(rgb)[0]


# --------------------------------------------------------------------------
# Quantised colour space
# --------------------------------------------------------------------------


def pack(chan: tuple[int, int, int], fmt: tuple[int, int, int]) -> int:
    """Channel codes -> one packed word, red in the high bits (RGB565 order)."""
    rb, gb, bb = fmt
    r, g, b = chan
    return (r << (gb + bb)) | (g << bb) | b


def unpack(word: int, fmt: tuple[int, int, int]) -> tuple[int, int, int]:
    rb, gb, bb = fmt
    return ((word >> (gb + bb)) & ((1 << rb) - 1),
            (word >> bb) & ((1 << gb) - 1),
            word & ((1 << bb) - 1))


def expand(word: int, fmt: tuple[int, int, int]) -> tuple[int, int, int]:
    """Packed word -> the 8-bit sRGB colour the panel actually shows.

    Bit replication (r8 = r5<<3 | r5>>2) is the convention that maps code 0 to 0
    and the top code to 255; it is what LVGL, esp_lcd and every screenshot
    comparison assume. The panel's own 5->6-bit expansion into frame memory is a
    separate register choice - ST7789 `RAMCTRL (B0h)` EPF[1:0], see ADR 0011.
    """
    out = []
    for code, bits in zip(unpack(word, fmt), fmt):
        shift = 8 - bits
        out.append((code << shift) | (code >> (bits - shift)) if shift else code)
    return (out[0], out[1], out[2])


def quantise_round(rgb: tuple[int, int, int], fmt: tuple[int, int, int]) -> int:
    """Naive conversion: round each channel independently. The thing we reject."""
    codes = tuple(round(c * ((1 << bits) - 1) / 255) for c, bits in zip(rgb, fmt))
    return pack(codes, fmt)


def candidates(rgb: tuple[int, int, int], fmt: tuple[int, int, int],
               radius: int = 1) -> list[int]:
    """Representable words near `rgb`: the rounded codes +/- `radius` steps per
    channel.

    radius=1 gives **up to** 27 words -- fewer where a channel code clamps at
    the ends of the gamut: across the three vendored ramps the set sizes are 27
    (657 of the 768 indices), 18 (102), 12 (8) and 8 (1), measured 2026-08-21.

    The neighbourhood IS binding, if marginally. Re-measured 2026-08-21 with the
    radius forced (radius=1 reproduces `build_lut` bit for bit, so the harness is
    faithful): radius=2 moves exactly one index in each of the three maps, at a
    strictly lower objective -- cividis 463.103 -> 462.856, magma 441.879 ->
    441.626, viridis 407.817 -> 407.745; radius=3 moves three indices in viridis
    (407.621). An earlier version of this docstring claimed radius=2 "returns the
    same LUT", which is wrong.

    The default stays 1: 0.25 of ~450 total dE units, spread over 256 entries,
    is not a visible improvement, and widening it would change the shipped LUT
    and every number ADR 0011 quotes for it. `build_lut` already widens to 2 and
    3 on its own when no L*-monotone path exists at radius 1.
    """
    base = [round(c * ((1 << bits) - 1) / 255) for c, bits in zip(rgb, fmt)]
    tops = [(1 << bits) - 1 for bits in fmt]
    out = set()
    for dr in range(-radius, radius + 1):
        r = min(tops[0], max(0, base[0] + dr))
        for dg in range(-radius, radius + 1):
            g = min(tops[1], max(0, base[1] + dg))
            for db in range(-radius, radius + 1):
                b = min(tops[2], max(0, base[2] + db))
                out.add(pack((r, g, b), fmt))
    return sorted(out)


# --------------------------------------------------------------------------
# LUT construction
# --------------------------------------------------------------------------


def ramp8(name: str) -> list[tuple[int, int, int]]:
    """The map's 256 target colours in 8-bit sRGB, piecewise linear between the
    embedded control points."""
    pts = CONTROL_POINTS[name]
    out: list[tuple[int, int, int]] = []
    seg = 0
    for i in range(LUT_LEN):
        while seg + 2 < len(pts) and pts[seg + 1][0] < i:
            seg += 1
        i0, r0, g0, b0 = pts[seg]
        i1, r1, g1, b1 = pts[seg + 1]
        f = 0.0 if i1 == i0 else (i - i0) / (i1 - i0)
        out.append((round(r0 + (r1 - r0) * f),
                    round(g0 + (g1 - g0) * f),
                    round(b0 + (b1 - b0) * f)))
    return out


def build_lut(name: str, mode: str = "optimal", fmt: tuple[int, int, int] = RGB565,
              repeat_penalty: float = 0.5) -> list[int]:
    """256 packed words for `name`.

    mode="round"   : per-channel rounding, kept so the header and the self-test
                     can quote what the naive conversion would have cost.
    mode="optimal" : the sequence of representable words minimising

                         sum_i dE76(target_i, word_i)
                         + repeat_penalty * #{i : word_i == word_{i-1}}

                     subject to L*(word_i) >= L*(word_{i-1}) for every i. Solved
                     exactly by dynamic programming over the candidate words at
                     each index (no greedy ratchet: a greedy nearest-dE pass that
                     overshoots L* early is then forbidden from coming back down,
                     which was measured to cost ~20 % of the distinct words and
                     ~25 % of the fidelity).

    The luminance constraint is the whole reason a sequential map survives colour
    vision deficiency, greyscale printing and a sunlit panel (bibliography 05 #76,
    05 #82); it is enforced, not hoped for. The repeat penalty (in dE units, per
    repeated index) is the one aesthetic knob: it says "accept up to this much
    extra colour error to break a flat run", and 0.5 dE is below the point where
    the map's colours are distinguishable from the published ones.
    """
    targets = ramp8(name)
    if mode == "round":
        return [quantise_round(t, fmt) for t in targets]
    if mode != "optimal":
        raise ValueError("unknown mode %r" % mode)

    inf = float("inf")
    for radius in (1, 2, 3):
        table = []
        for t in targets:
            rows = []
            for w in candidates(t, fmt, radius):
                shown = expand(w, fmt)
                rows.append((lstar(shown), de76(t, shown), w))
            rows.sort()                      # ascending L*
            table.append(rows)

        cost = [row[1] for row in table[0]]
        back: list[list[int]] = []
        for i in range(1, LUT_LEN):
            prev = table[i - 1]
            cur, bk = [], []
            for lc, d, w in table[i]:
                best, arg = inf, -1
                for j, (pl, _, pw) in enumerate(prev):
                    if pl > lc + 1e-9 or cost[j] == inf:
                        continue             # would lower L*, or is unreachable
                    c = cost[j] + (repeat_penalty if pw == w else 0.0)
                    if c < best:
                        best, arg = c, j
                cur.append(inf if arg < 0 else best + d)
                bk.append(arg)
            back.append(bk)
            cost = cur
        if min(cost) == inf:
            continue                         # no monotone path: widen and retry
        j = min(range(len(cost)), key=lambda k: cost[k])
        lut = [0] * LUT_LEN
        for i in range(LUT_LEN - 1, -1, -1):
            lut[i] = table[i][j][2]
            if i:
                j = back[i - 1][j]
        return lut
    raise RuntimeError("%s: no L*-monotone path exists in this pixel format" % name)


def run_lengths(lut: list[int]) -> list[int]:
    """For every index, the length of the flat run of identical words it belongs
    to. This is the dither amplitude: a run of 1 needs no dithering, a run of 8
    needs the index perturbed across 8 indices to hide the run's edges."""
    out = [1] * len(lut)
    i = 0
    while i < len(lut):
        j = i
        while j + 1 < len(lut) and lut[j + 1] == lut[i]:
            j += 1
        for k in range(i, j + 1):
            out[k] = j - i + 1
        i = j + 1
    return out


def metrics(name: str, lut: list[int],
            fmt: tuple[int, int, int] = RGB565) -> dict[str, float | int | bool]:
    """The banding report. Every number here is measured from `lut`."""
    targets = ramp8(name)
    shown = [expand(w, fmt) for w in lut]
    ls = [lstar(s) for s in shown]
    steps = [de76(shown[i - 1], shown[i]) for i in range(1, len(shown))]
    fidelity = [de76(targets[i], shown[i]) for i in range(len(lut))]
    drops = [ls[i - 1] - ls[i] for i in range(1, len(ls)) if ls[i] < ls[i - 1] - 1e-9]
    return {
        "entries": len(lut),
        "distinct": len(set(lut)),
        "max_step_de76": max(steps),
        "mean_step_de76": sum(steps) / len(steps),
        "max_fidelity_de76": max(fidelity),
        "mean_fidelity_de76": sum(fidelity) / len(fidelity),
        "max_run": max(run_lengths(lut)),
        "lstar_min": min(ls),
        "lstar_max": max(ls),
        "lstar_drops": len(drops),
        "lstar_worst_drop": max(drops) if drops else 0.0,
        "lstar_monotone": not drops,
    }


# --------------------------------------------------------------------------
# Header emission
# --------------------------------------------------------------------------


def emit_header(name: str, lut: list[int], mode: str, dither: bool,
                swap_bytes: bool, argv: list[str]) -> str:
    ident = re.sub(r"[^a-z0-9]", "_", name.lower())
    upper = ident.upper()
    guard = "SPECTRAL_CMAP_%s_H_" % upper
    m = metrics(name, lut)
    naive = metrics(name, build_lut(name, "round"))
    words = [((w & 0xFF) << 8) | (w >> 8) if swap_bytes else w for w in lut]
    runs = run_lengths(lut)

    lines: list[str] = []
    a = lines.append
    a("/* SPDX-FileCopyrightText: 2026 Alexander Gomez")
    a(" * SPDX-License-Identifier: Apache-2.0")
    a(" *")
    a(" * GENERATED FILE - do not edit. Regenerate with:")
    a(" *   python3 python-scripts/gen_colormap_lut.py %s" % " ".join(argv))
    a(" *")
    a(" * Spectrogram colormap '%s', %d entries, designed in RGB565 (ADR 0011)."
      % (name, len(lut)))
    a(" * Control points, their upstream version and their licence status: see the")
    a(" * generator's CONTROL_POINTS comment (ADR 0004 open item).")
    a(" *")
    a(" * Quantisation: %s" % mode)
    a(" * Word order:   %s" % ("byte-swapped, big-endian on the wire (ST7789 over SPI "
                               "with esp_lcd swap_color_bytes off)" if swap_bytes
                               else "native uint16 (host order)"))
    a(" *")
    a(" * Measured at generation time (CIE76 dE over sRGB -> CIELAB, D65):")
    a(" *   distinct RGB565 words     : %3d / %d   (naive per-channel rounding: %d)"
      % (m["distinct"], m["entries"], naive["distinct"]))
    a(" *   longest flat run          : %3d indices          (naive: %d)"
      % (m["max_run"], naive["max_run"]))
    a(" *   worst step between entries: dE %5.2f            (naive: %.2f)"
      % (m["max_step_de76"], naive["max_step_de76"]))
    a(" *   mean step                 : dE %5.3f" % m["mean_step_de76"])
    a(" *   worst error vs the 8-bit map: dE %5.2f          (naive: %.2f)"
      % (m["max_fidelity_de76"], naive["max_fidelity_de76"]))
    a(" *   mean error                : dE %5.3f            (naive: %.3f)"
      % (m["mean_fidelity_de76"], naive["mean_fidelity_de76"]))
    a(" *   L*                        : %.1f .. %.1f, non-decreasing: %s"
      % (m["lstar_min"], m["lstar_max"], "yes" if m["lstar_monotone"] else "NO"))
    a(" *")
    a(" * The worst-step figure is the banding metric: it is the perceptual size of")
    a(" * the edge between two adjacent LUT entries, i.e. of the contour a smooth dB")
    a(" * ramp will draw across the spectrogram. Ordered dithering trades that edge")
    a(" * for spatial noise; 18-bit COLMOD (ST7789 3Ah=06h) removes it at 1.5x the")
    a(" * pixel bytes on the SPI bus (ADR 0011).")
    a(" */")
    a("")
    a("#ifndef %s" % guard)
    a("#define %s" % guard)
    a("")
    a("#include <stdint.h>")
    a("")
    a("#define SPECTRAL_CMAP_%s_LEN %d" % (upper, len(lut)))
    a("#define SPECTRAL_CMAP_%s_DISTINCT %d" % (upper, m["distinct"]))
    a("#define SPECTRAL_CMAP_%s_MAX_RUN %d" % (upper, m["max_run"]))
    a("")
    a("static const uint16_t spectral_cmap_%s565[SPECTRAL_CMAP_%s_LEN] = {"
      % (ident, upper))
    for i in range(0, len(words), 8):
        a("    " + " ".join("0x%04X," % w for w in words[i:i + 8])
          + "  /* %3d..%3d */" % (i, min(i + 7, len(words) - 1)))
    a("};")
    if dither:
        a("")
        a("/* Ordered (Bayer) dithering.")
        a(" *")
        a(" * Why the index and not the colour: after quantisation the LUT contains")
        a(" * flat runs of identical words (longest here: %d indices). Perturbing the"
          % m["max_run"])
        a(" * colour would leave the map, so the *index* is perturbed instead, by up")
        a(" * to half the run it lands in. That spreads one hard run boundary over the")
        a(" * width of the run and lets the eye integrate it. Where the run is 1 the")
        a(" * amplitude is 0 and the pixel is untouched: dithering acts exactly where")
        a(" * the LUT is flat and nowhere else.")
        a(" *")
        a(" * Threshold matrix: the classic 4x4 recursive Bayer matrix, a permutation")
        a(" * of 0..15 (Bayer, ICC 1973). Row = y & 3, column = x & 3:")
        a(" *")
        a(" *      x&3:   0   1   2   3")
        for yy in range(4):
            a(" *   y&3=%d:  %2d  %2d  %2d  %2d" % (yy, *BAYER_4X4[yy]))
        a(" *")
        a(" * The value is mapped to 2*v - 15, i.e. -15..+15 with mean exactly 0, and")
        a(" * scaled by run/32: a plain `v - 8` would have mean -0.5 and would shift")
        a(" * the whole image down by run/32 of an index. C integer division truncates")
        a(" * toward zero, so the +/- halves stay symmetric.")
        a(" *")
        a(" * Cost: two table reads, one multiply, one shift per pixel. The 4x4 tile is")
        a(" * fixed in screen space, so a scrolling waterfall must dither against the")
        a(" * PANEL y (the ST7789 scroll address), not the buffer row, or the pattern")
        a(" * crawls with the scroll (ADR 0007, ADR 0011).")
        a(" */")
        a("static const uint8_t spectral_cmap_%s_damp[SPECTRAL_CMAP_%s_LEN] = {"
          % (ident, upper))
        for i in range(0, len(runs), 16):
            a("    " + " ".join("%2d," % r for r in runs[i:i + 16]))
        a("};")
        a("")
        # The matrix is the same for every map, so it is the one symbol here that
        # is NOT namespaced -- and two dithered headers in one translation unit
        # therefore failed to compile ("redefinition of 'spectral_cmap_bayer4x4'",
        # gcc -std=c99, measured 2026-08-21). ADR 0011 decision 2 ships viridis
        # and magma selectable alongside cividis, so that is a configuration the
        # firmware is meant to have. Its own include guard keeps one definition
        # and lets any number of headers carry it.
        a("#ifndef SPECTRAL_CMAP_BAYER4X4_H_")
        a("#define SPECTRAL_CMAP_BAYER4X4_H_")
        a("static const uint8_t spectral_cmap_bayer4x4[4][4] = {")
        for yy in range(4):
            a("    { %2d, %2d, %2d, %2d }," % BAYER_4X4[yy])
        a("};")
        a("#endif /* SPECTRAL_CMAP_BAYER4X4_H_ */")
        a("")
        a("/* idx: LUT index 0..%d. x, y: pixel position in PANEL coordinates. */"
          % (len(lut) - 1))
        a("static inline uint16_t spectral_cmap_%s_dithered(uint8_t idx, int x, int y)"
          % ident)
        a("{")
        a("    int t = 2 * (int)spectral_cmap_bayer4x4[y & 3][x & 3] - 15; /* -15..+15 */")
        a("    int j = (int)idx + (t * (int)spectral_cmap_%s_damp[idx]) / 32;" % ident)
        a("    if (j < 0) {")
        a("        j = 0;")
        a("    } else if (j > %d) {" % (len(lut) - 1))
        a("        j = %d;" % (len(lut) - 1))
        a("    }")
        a("    return spectral_cmap_%s565[j];" % ident)
        a("}")
    a("")
    a("#endif /* %s */" % guard)
    a("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------


def self_test() -> int:
    """Assert the invariants a spectrogram LUT must have, and print the numbers
    ADR 0011 quotes: monotone luminance, the worst dE step between neighbouring
    entries, and the count of distinct RGB565 words (the banding metric)."""
    failures: list[str] = []
    checks = 0

    def check(cond: bool, msg: str) -> None:
        nonlocal checks
        checks += 1
        if not cond:
            failures.append(msg)

    # A biased threshold matrix would shift the whole image, not just dither it.
    flat = [v for row in BAYER_4X4 for v in row]
    check(len(BAYER_4X4) == 4 and all(len(r) == 4 for r in BAYER_4X4),
          "BAYER_4X4 is not 4x4")
    check(sorted(flat) == list(range(16)), "BAYER_4X4 is not a permutation of 0..15")

    # Packing round trip and the ends of the quantised space.
    for fmt in (RGB565, RGB666):
        top = tuple((1 << b) - 1 for b in fmt)
        check(expand(pack((0, 0, 0), fmt), fmt) == (0, 0, 0),
              "%s: black does not expand to (0,0,0)" % (fmt, ))
        check(expand(pack(top, fmt), fmt) == (255, 255, 255),
              "%s: full scale does not expand to (255,255,255)" % (fmt, ))
        check(unpack(pack((1, 2, 3), fmt), fmt) == (1, 2, 3),
              "%s: pack/unpack does not round trip" % (fmt, ))

    hdr = ("%-8s %-8s %5s %8s %6s %8s %8s %7s %7s %6s" %
           ("map", "mode", "n", "distinct", "maxrun", "maxstep", "meanstep",
            "maxerr", "meanerr", "monoL*"))
    print(hdr)
    print("-" * len(hdr))

    for name in sorted(CONTROL_POINTS):
        pts = CONTROL_POINTS[name]
        check(pts[0][0] == 0 and pts[-1][0] == LUT_LEN - 1,
              "%s: control points do not span 0..%d" % (name, LUT_LEN - 1))
        check(all(pts[i][0] < pts[i + 1][0] for i in range(len(pts) - 1)),
              "%s: control-point indices are not strictly increasing" % name)
        check(all(0 <= c <= 255 for p in pts for c in p[1:]),
              "%s: a control-point channel is outside 0..255" % name)
        ramp = ramp8(name)
        check(all(ramp[i] == (r, g, b) for i, r, g, b in pts),
              "%s: the interpolated ramp does not reproduce its control points" % name)

        lut = build_lut(name, "optimal")
        m = metrics(name, lut)
        naive = metrics(name, build_lut(name, "round"))
        wide = metrics(name, build_lut(name, "optimal", RGB666), RGB666)

        for label, mm in (("optimal", m), ("round", naive), ("18-bit", wide)):
            print("%-8s %-8s %5d %8d %6d %8.2f %8.3f %7.2f %7.3f %6s" %
                  (name, label, mm["entries"], mm["distinct"], mm["max_run"],
                   mm["max_step_de76"], mm["mean_step_de76"],
                   mm["max_fidelity_de76"], mm["mean_fidelity_de76"],
                   "yes" if mm["lstar_monotone"] else "no"))

        # 1. The headline invariant: a sequential map that is not luminance
        #    monotone is not a sequential map.
        check(bool(m["lstar_monotone"]),
              "%s: L* is not non-decreasing after RGB565 quantisation "
              "(%d drops, worst %.2f)" % (name, m["lstar_drops"], m["lstar_worst_drop"]))
        check(bool(wide["lstar_monotone"]),
              "%s: L* is not non-decreasing in RGB666" % name)
        # 2. Enough lightness range to be readable in daylight at all.
        check(m["lstar_max"] - m["lstar_min"] > 60.0,
              "%s: L* range is only %.1f - too flat to read in sunlight"
              % (name, m["lstar_max"] - m["lstar_min"]))
        # 3. Still the published map: quantisation may not move a colour more
        #    than a couple of 565 steps away from it.
        check(m["max_fidelity_de76"] < 4.0,
              "%s: worst error vs the 8-bit map is dE %.2f (>= 4)"
              % (name, m["max_fidelity_de76"]))
        # 4. Designing in RGB565 must beat converting to it on the two numbers
        #    the design exists for: the worst visible edge, and mean fidelity.
        check(m["max_step_de76"] < naive["max_step_de76"],
              "%s: worst step dE %.2f is not better than naive rounding's %.2f"
              % (name, m["max_step_de76"], naive["max_step_de76"]))
        check(m["mean_fidelity_de76"] < naive["mean_fidelity_de76"],
              "%s: mean error dE %.3f is not better than naive rounding's %.3f"
              % (name, m["mean_fidelity_de76"], naive["mean_fidelity_de76"]))
        # 5. 18-bit COLMOD must actually be the escape hatch it is claimed to be.
        check(wide["max_step_de76"] < m["max_step_de76"],
              "%s: RGB666 does not reduce the worst step (%.2f vs %.2f)"
              % (name, wide["max_step_de76"], m["max_step_de76"]))

        # 6. The dither amplitude table must describe the LUT it ships with.
        runs = run_lengths(lut)
        i, ok = 0, True
        while i < LUT_LEN:
            length = runs[i]
            block = lut[i:i + length]
            ok = ok and len(block) == length and len(set(block)) == 1
            ok = ok and all(runs[k] == length for k in range(i, i + length))
            ok = ok and (i + length == LUT_LEN or lut[i + length] != lut[i])
            i += length
        check(ok, "%s: the dither amplitude table does not match the LUT runs" % name)

        # 7. The emitted header must parse back to exactly the LUT.
        text = emit_header(name, lut, "optimal", True, False, ["--self-test"])
        got = [int(w, 16) for w in re.findall(r"0x([0-9A-F]{4}),", text)]
        check(got == lut, "%s: the emitted header does not round trip to the LUT" % name)
        check(text.count("#ifndef") == text.count("#endif") == 2
              and text.count("#ifndef %s" % ("SPECTRAL_CMAP_%s_H_"
                                             % re.sub(r"[^a-z0-9]", "_",
                                                      name.lower()).upper())) == 1,
              "%s: the emitted header is malformed" % name)
        swapped = emit_header(name, lut, "optimal", False, True, ["--self-test"])
        got = [int(w, 16) for w in re.findall(r"0x([0-9A-F]{4}),", swapped)]
        check(all(((s & 0xFF) << 8) | (s >> 8) == w for s, w in zip(got, lut)),
              "%s: --swap-bytes did not byte-swap the words" % name)

    # 8. Two maps must be able to coexist in one translation unit: ADR 0011
    #    decision 2 ships viridis and magma selectable alongside cividis, and
    #    with --dither every header used to define spectral_cmap_bayer4x4
    #    unguarded, so including two of them did not compile.
    names = sorted(CONTROL_POINTS)
    if len(names) >= 2:
        decls: dict[str, list[str]] = {}
        guards: list[str] = []
        for name in names[:2]:
            text = emit_header(name, build_lut(name, "optimal"), "optimal", True,
                               False, ["--self-test"])
            guards += re.findall(r"#ifndef\s+(\w+)", text)
            body = re.sub(r"#ifndef\s+SPECTRAL_CMAP_BAYER4X4_H_.*?#endif[^\n]*\n",
                          "", text, flags=re.S)
            for sym in re.findall(r"^static (?:const |inline )+\w+ (\w+)",
                                  body, flags=re.M):
                decls.setdefault(sym, []).append(name)
        clashes = {k: v for k, v in decls.items() if len(v) > 1}
        check(not clashes,
              "these symbols are defined by more than one map's header and are "
              "not inside a shared guard: %s" % ", ".join(sorted(clashes)))
        check(guards.count("SPECTRAL_CMAP_BAYER4X4_H_") == 2,
              "the shared Bayer matrix is not wrapped in its own include guard")

    for name, why in MISSING_MAPS.items():
        check(name not in CONTROL_POINTS,
              "%s is both vendored and listed as missing" % name)
        check(bool(why), "%s has no reason recorded" % name)

    if failures:
        print("\nFAIL (%d of %d checks):" % (len(failures), checks), file=sys.stderr)
        for f in failures:
            print("  - " + f, file=sys.stderr)
        return 1
    print("\nself-test OK: %d maps, %d checks. Monotone L*, header round trip, and"
          % (len(CONTROL_POINTS), checks))
    print("designing in RGB565 beats converting to it on worst step and mean error.")
    return 0


# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(
        description="Generate an RGB565 spectrogram colormap LUT (ADR 0011).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Vendored maps: %s. Named in ADR 0011 but not vendored: %s."
               % (", ".join(sorted(CONTROL_POINTS)), ", ".join(sorted(MISSING_MAPS))))
    p.add_argument("--map", default="cividis",
                   help="colormap name (default: cividis, the ADR 0011 proposal)")
    p.add_argument("--quantise", choices=("optimal", "round"), default="optimal",
                   help="optimal: minimise CIE76 dE over the representable words "
                        "under a monotone-L* constraint (default). round: naive "
                        "per-channel rounding, for comparison only.")
    p.add_argument("--repeat-penalty", type=float, default=0.5, metavar="DE",
                   help="extra colour error (dE) accepted to break a flat run "
                        "(default: 0.5; 0 gives the pure fidelity optimum)")
    p.add_argument("--dither", action="store_true",
                   help="also emit the 4x4 Bayer matrix, the per-index dither "
                        "amplitude table and the lookup helper")
    p.add_argument("--swap-bytes", action="store_true",
                   help="emit big-endian words (what the ST7789 wants on the wire "
                        "when esp_lcd's swap_color_bytes / LV_COLOR_16_SWAP is off)")
    p.add_argument("-o", "--out", metavar="PATH",
                   help="write the header here instead of stdout")
    p.add_argument("--metrics", action="store_true",
                   help="print the banding metrics for the map and exit")
    p.add_argument("--self-test", action="store_true",
                   help="check every vendored map and exit non-zero on failure")
    args = p.parse_args(argv)

    if args.self_test:
        return self_test()

    if args.map in MISSING_MAPS:
        print("gen_colormap_lut: %s: %s" % (args.map, MISSING_MAPS[args.map]),
              file=sys.stderr)
        return 1
    if args.map not in CONTROL_POINTS:
        print("gen_colormap_lut: unknown map %r (have: %s)"
              % (args.map, ", ".join(sorted(CONTROL_POINTS))), file=sys.stderr)
        return 1

    lut = build_lut(args.map, args.quantise, RGB565, args.repeat_penalty)

    if args.metrics:
        for key, value in metrics(args.map, lut).items():
            print("%-20s %s" % (key, ("%.3f" % value) if isinstance(value, float)
                                else value))
        return 0

    text = emit_header(args.map, lut, args.quantise, args.dither,
                       args.swap_bytes, argv)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("wrote %s (%d entries, %d distinct RGB565 words)"
              % (args.out, len(lut), len(set(lut))), file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
