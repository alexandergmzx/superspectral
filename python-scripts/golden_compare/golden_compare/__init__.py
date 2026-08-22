# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""golden_compare — the Apache-2.0 consumer of the golden files.

Reads what ``host/golden/`` (GPL-3.0-or-later) wrote — ``manifest.yaml`` and
the ``.npy`` arrays — **as data**, and applies the tolerance table of
``docs/validation/golden-files.md`` to a candidate: a device dump, a
``host-tests`` result, an esp-dsp backend's output. Nothing here imports
``spectral_host`` and nothing under ``host/`` imports this; the licence
boundary is a directory boundary and the contract is files on disk
(ADR 0004, ADR 0009 decision 3).

Modules
-------
:mod:`golden_compare.load`
    ``load_manifest`` (schema ``"1.1"`` only) and ``load_array``
    (``allow_pickle=False``; sha256, dtype and shape cross-checked against the
    manifest entry).
:mod:`golden_compare.spectrum`
    ``residual_db`` (bins below the floor masked — the mask never widens the
    atol) and ``check`` → ``Report(max_abs, n_compared, n_masked, passed)``.
:mod:`golden_compare.pitch`
    ``cents``, ``resample_to_times`` (voiced-only, linear in log f — the
    frame-grid trap), ``median_abs_cents``, ``mir_eval_melody`` →
    ``{RPA, RCA, OA, VR, VFA}``.
:mod:`golden_compare.windows`
    sha256 of a raw little-endian float32 window-table dump and
    ``compare_window_digest`` against a manifest ``windows[]`` entry — the
    device lane's hasher (the C side carries no sha256).
:mod:`golden_compare.tolerances`
    the table's constants, each bound to the row it was copied from; the
    document stays the only definition and a test greps it.

CLI (run from ``python-scripts/golden_compare/``; see ``pyproject.toml``)::

    uv run python -m golden_compare spectrum --golden A.npy --candidate B.npy [--atol-db 0.01 --floor -80]
    uv run python -m golden_compare pitch    --golden ref.npy --candidate dev.npy --path injection
    uv run python -m golden_compare window   --raw table.f32 --manifest manifest.yaml --family hann --n 4096
    uv run python -m golden_compare tolerances
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
