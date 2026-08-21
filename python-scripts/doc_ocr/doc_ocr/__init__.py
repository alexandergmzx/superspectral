# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
# Origin: python-scripts/doc_ocr in the author's `swarm` repository (same author, same tool).
"""Reference-library extractor.

Turns the PDFs under docs/ into grep-able markdown sidecars carrying a human
review flag. 79 of 81 documents in the library already have a text layer, so the
main path is extraction (pdftotext -layout), not OCR; OCR is a fallback for the
rare scanned document.

Sidecars are gitignored — some source PDFs are not freely redistributable and the
extracted text inherits that restriction. The durable record is the tracked,
content-free ledger at docs/OCR/manifest.tsv, which also holds the review flag
keyed by source sha256 so verification survives regenerating a sidecar.
"""

__version__ = "0.1.0"
