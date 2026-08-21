# OCR / document extraction

Home of the reference-library extraction system: the workflow, the flag legend, and the tracked
ledger [`manifest.tsv`](manifest.tsv). The **code** lives in
[`../../python-scripts/doc_ocr/`](../../python-scripts/doc_ocr/) — every Python file in this repo
lives under `python-scripts/` ([CLAUDE.md](../../CLAUDE.md#where-python-lives)), so this directory
holds documentation and the ledger only.

The tool and this convention are inherited verbatim from the `swarm` project (same author), where
the rationale and alternatives are recorded in its ADR 0015 *"Markdown sidecars for the reference
library: extract, don't OCR; ignore the text, track the ledger"*. Super Spectral adopts it unchanged;
if the policy ever diverges, write a local ADR.

## What it produces

Each source document in the reference library gets a markdown sidecar **next to it**:

```
docs/datasheets/knowles/spm1423hm4h-b/
├── knowles_spm1423hm4h-b_datasheet_revA.pdf        ← vendor original, never modified
└── knowles_spm1423hm4h-b_datasheet_revA.ocr.md     ← generated, gitignored

docs/datasheets/espressif/esp32-s3/
├── espressif_esp32-s3_trm_v1.8.pdf
└── espressif_esp32-s3_trm_v1.8.ocr/                ← >250 pages, split by chapter
    ├── _index.md                                   ← front matter + linked TOC
    ├── 01-front-matter.md
    └── …
```

Body text sits in a fenced block with `=== p.N ===` page markers, so a grep hit tells you which
page of the PDF to open:

```
$ grep -rn 'VDD_SPI_FORCE' docs/datasheets/espressif/
… EFUSE_VDD_SPI_FORCE   GPIO45   EFUSE_VDD_SPI_TIEH   VDD_SPI voltage …
```

## Three kinds of file, three different rules

| File | Tracked? | Written by | Safe to edit? |
|---|---|---|---|
| `<name>.pdf` / `.docx` | yes (see redistribution note) | the vendor | never modified by anything |
| `<name>.ocr.md`, `<name>.ocr/` | **no** | `doc_ocr` | edits are lost on regeneration |
| `<name>_notes.md` | **yes** | you | the tool refuses to touch this name |
| `manifest.tsv` | **yes** | `doc_ocr` + your `check` calls | edit via the CLI |

Sidecars are gitignored because several source documents are not freely redistributable and their
extracted full text inherits that. **Durable prose belongs in `_notes.md`.**

**Redistribution note (Apache-2.0 repo).** Vendor PDFs whose redistribution terms are unknown or
restrictive are *not* committed either: file them locally, set `redistributable=no|unknown` in the
ledger, and commit only the `_notes.md` with the derived facts (facts are not copyrightable) plus a
link to the upstream source. See [`../bibliography/README.md`](../bibliography/README.md) → Acquisition
tips. Only documents with explicit permissive terms (ITU-T free recommendations, arXiv preprints under
CC licences, vendor docs that state free redistribution) are committed.

## Usage

Run from `python-scripts/doc_ocr/` — stdlib only, no install, no virtualenv:

```sh
cd python-scripts/doc_ocr

python3 -m doc_ocr scan                    # status report, writes nothing
python3 -m doc_ocr extract                 # generate/refresh whatever is stale
python3 -m doc_ocr extract ../../docs/papers --force
python3 -m doc_ocr unchecked               # the review queue, biggest first
python3 -m doc_ocr check ../../docs/datasheets/knowles/spm1423hm4h-b/<file>.pdf \
        --reviewer AG --note "Sensitivity/SNR table and response curve verified against p.3-4"
python3 -m doc_ocr verify                  # did any source PDF change under us?
```

Requires `poppler-utils` and `mupdf-tools` (both present on the development host); `ocrmypdf` +
`tesseract` only for scanned documents.

## Review flags

Every document starts `unchecked`. The flag lives in `manifest.tsv` keyed by the source's sha256,
not in the sidecar — that way it survives deleting and regenerating a gitignored file.

| Flag | Meaning |
|---|---|
| `unchecked` | Machine output, nobody has looked. Do not quote it as authoritative. |
| `checked` | A human read the extraction against the PDF and it is faithful. |
| `needs-work` | Reviewed and found lossy — tables mangled, OCR garbage, pages missing. |

**A changed source PDF resets the flag to `unchecked` and warns.** Vendors revise datasheets
silently; that reset is the tripwire, and `doc_ocr verify` reports it without writing anything.

### What `checked` means for this corpus

For acoustic and electrical datasheets, `checked` specifically means **the numeric tables survived
extraction**: the Knowles SPM1423 sensitivity/SNR/AOP table and free-field response curve, the
ESP32-S3 power tables (5-7 … 5-10), the AXP2101 register map, the ST7789 timing table (T_SCYCW).
Several of these are **raster images** in the PDF and `pdftotext` yields nothing for them — they must
be read visually and, for curves, digitized (WebPlotDigitizer → CSV committed next to the PDF as
`<name>_response.csv` with a provenance block). See roadmap phase D3.

## Not yet done — figures and diagrams (v2)

Sidecars carry an empty `figures: []` front-matter key so adding this is not a format change. The
planned shape: `pdfimages -png` into `<original>.ocr/figures/`, an `![p27 fig1](figures/p0027-fig01.png) <!-- undescribed -->`
marker in the text, and a `doc_ocr describe` queue so a human can write descriptions. For this
project that step matters more than it did for swarm — microphone polar patterns, response curves
and spectrogram examples are the information content of half the library.
