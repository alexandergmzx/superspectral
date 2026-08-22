# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""Super Spectral host companion — the GPL-3.0-or-later offline path (ADR 0002, ADR 0004).

This package imports parselmouth (which embeds Praat, GPLv3+) in-process; nothing
outside host/ may import it, and nothing in here may import the Apache-2.0 tooling
under python-scripts/. The two halves exchange files on disk only.
"""

__version__ = "0.1.0"
