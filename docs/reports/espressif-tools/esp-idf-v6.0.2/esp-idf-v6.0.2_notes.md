# ESP-IDF support-policy and roadmap snapshot at tag `v6.0.2` — notes

Bibliography entry: [07 #16](../../../bibliography/07-technical-reports.md) · grounds [ADR 0001](../../../adr/0001-toolchain-esp-idf-v6-pinned-environment.md) and the version-bump rule in [`upgrade-procedure.md`](../../../devenv/upgrade-procedure.md).

## What is in this directory

The four files beside this note are **byte-verbatim copies** of the top-level policy documents of `espressif/esp-idf` at tag `v6.0.2` (commit `7101770dc6db2667b3c477cc31365dd1acd6db4e`), copied on 2026-08-21 from the pinned build checkout `~/esp/idf/v6.0.2` (`git describe --tags --exact-match` → `v6.0.2`). They keep their upstream basenames so that the EN ↔ 中文 cross-links inside them (`./SUPPORT_POLICY_CN.md`, `./ROADMAP_CN.md`, and back) resolve unchanged and so that `cmp` against the tag is a one-liner; the version stamp lives on the directory name instead of the filename.

| File | sha256 at `v6.0.2` | Last upstream change (`git log -1 --`) |
|------|--------------------|-----------------------------------------|
| `SUPPORT_POLICY.md` | `92c2bddc00d371eb3b25a29203b31728d321e0884fe3c16f3a6843bfbc4b1a8c` | `ca57e121` 2022-05-11 |
| `SUPPORT_POLICY_CN.md` | `f580cef988fd7055ae3c9cea0879915a543aa62165d0f592a1885550322c6ff7` | — (companion, filed so the cross-link resolves) |
| `ROADMAP.md` | `9a01247499a8cbad21a115721ea337989db4555e8b8b8c29dc4ede2dec706cd1` | `cb02c76a` 2025-03-19 |
| `ROADMAP_CN.md` | `045619730b24f539c66ffa02da714ebaba1948764ec244b9ba2b9e2332c4469d` | — (companion) |

These are Markdown, not PDFs, so they are **not** registered in [`docs/OCR/manifest.tsv`](../../../OCR/README.md) — `doc_ocr` discovers `.pdf` / `.docx` only (`SOURCE_SUFFIXES` in `python-scripts/doc_ocr/doc_ocr/discover.py`). This note is the ledger for them.

## Licence basis (why they are committed)

- The repository `LICENSE` at `v6.0.2` is the unmodified Apache License 2.0 text (202 lines).
- `docs/en/COPYRIGHT.rst` at the same tag: *"All original source code in this repository is Copyright (C) 2015-2023 Espressif Systems. This source code is licensed under the Apache License 2.0 as described in the file LICENSE."* and *"Where source code headers specify Copyright & License information, this information takes precedence over the summaries made here."* Its *Documentation* subsection names only the Sphinx theme (MIT).
- None of the four files carries a header, SPDX tag, copyright line or licence statement of its own (checked by `grep -i 'licen\|copyright\|SPDX'`), so nothing overrides the repository default.
- Reading: the files are Espressif-original content in an Apache-2.0 repository with no contrary per-file statement → redistributable under Apache-2.0 §4 (copies must carry the licence notice — this note and the repo-wide attribution in `NOTICE`/`LICENSE` do that). **Residual caveat, recorded rather than hidden:** the `COPYRIGHT.rst` grant is worded for "source code"; these are prose files. If Espressif ever publishes a narrower documentation licence, re-decide at the next upgrade.

## What they evidence, and what they do not

- `SUPPORT_POLICY.md` evidences the flat **30-month** policy, split **12 months Service + 18 months Maintenance**, the "In Service is recommended for new projects" rule, that pre-release and "Preview" features carry no support period, and the policy history (September 2019 split; July 2020 unification).
- `ROADMAP.md` is the **2025** roadmap: "Release IDF v5.5 in the middle of 2025", "Release IDF v6.0 at the end of 2025", the MbedTLS 4.x / PSA-crypto migration warning for v6.0, and a release timeline listing `v6.0 : 2026/02/13`, `v5.5 : 2025/08/04`, `v5.5.2 : 2025/11/12`, `v5.1.7 : 2026/01/06`.
- **Neither file states the per-release Service / EOL dates** that 07 #16's Why cell quotes (v6.0 Service-to 2027-03-20 / EOL 2028-09-20, v5.5 EOL 2028-01-21). Those come from the per-release support-period announcements and the versions page, not from these two files — cite them from there. They are, however, consistent with this policy applied to the real release date: the `v6.0` tag is dated **2026-03-19** (`git for-each-ref` on the tag, tagger date; the roadmap's planned `2026/02/13` slipped), and 2026-03-19/20 + 12 months = 2027-03-20 Service end, + 30 months = 2028-09-20 EOL. `v6.0.1` is tagged 2026-04-22 and `v6.0.2` 2026-06-19.

## The support-periods chart (not filed)

`https://dl.espressif.com/dl/esp-idf/support-periods.svg` was fetched on 2026-08-21 for reading only (HTTP 200, `image/svg+xml`, 56 764 B, sha256 `30380788a35b87a4e969699d397b2b6afaa67c36a2d63f4f24364b222288e2ea`). It is a Matplotlib 3.9.4 export dated `2026-08-18T15:27:56`, text rendered as DejaVu Sans glyph outlines; decoding the glyph runs gives the axis `Jul 2024 … Jan 2029`, the rows **v6.0, v5.5, v5.4, v5.3**, and the legend *"Service period (Recommended for new designs)"* / *"Maintenance period"*. Exact dates are bar geometry, not text. The file carries **no licence statement** (the `cc:` namespace in its RDF block is Matplotlib boilerplate with no `cc:license` element) and `dl.espressif.com` publishes no terms for it, so it is ledgered `redistributable=unknown` in [`acquisition-status.md`](../../../bibliography/acquisition-status.md) and kept out of the tree; re-fetch it when needed — it is regenerated (the 2026-08-18 date is three days before this snapshot).
