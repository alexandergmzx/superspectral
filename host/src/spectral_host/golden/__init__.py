# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""Golden-file generator and verifier (ADR 0009).

The manifest is the golden file; the arrays are its payload. Modules land per
roadmap H0 unit: `cli` (B-U1), `manifest` + `verify` (B-U5), `sets` + `generate`
(B-U6). The schema they validate against is host/golden/manifest.schema.yaml.
"""
