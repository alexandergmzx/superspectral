# Documentation

Human-facing documents for Super Spectral. `docs/` holds only **cross-cutting material** plus the **reference library** of acquired documents. Subsystem-specific design notes live with their code (`dsp/design/`, `protocols/specs/`, `firmware/twatch-s3/README.md`, `hardware/`).

## Cross-cutting docs

| Subdirectory | Contents |
|--------------|----------|
| [proposal/](proposal/) | Binding research proposal (§1 research question … §7 limitations, References) and the one-page research statement |
| [roadmap/](roadmap/) | The documentation roadmap: tracks D0–D6 (documentation/acquisition) and E0–E2 (environment), each with a definition of done; routing table for the open questions |
| [research/](research/) | The founding Linux-analyzer research document, moved here byte-identical |
| [architecture/](architecture/) | Companion architecture tenets and the planned design documents (audio capture path, DSP pipeline, display render path, host link, power budget, preset schema, memory/task topology) |
| [adr/](adr/) | Architecture Decision Records — one file per non-trivial decision; template, records, and the pre-registered backlog (0001–0019) |
| [validation/](validation/) | Two-path rule, acceptance metrics with external anchors, equipment with tolerances, golden-file strategy, experiment recipes |
| [devenv/](devenv/) | Reproducible ESP-IDF v6.0.2 environment: setup, `env.lock.md`, upgrade procedure, first-flash checklist, brick runbook, backup policy, coredump runbook, pitfall catalogue |
| [hw/](hw/) | Derived board facts: pin map (with attribution), eFuse baseline (read in E2), decoded vendor partition table |
| [bibliography/](bibliography/) | Master reading and acquisition list (index): by type (01–07) and by theme (08–11), plus the `acquisition-status.md` gap ledger |
| [OCR/](OCR/) | Reference-library extraction: workflow, review flags, and the tracked `manifest.tsv` ledger |

## Reference library

Mirrors the bibliography categories. Each directory holds the actual PDFs / files acquired, filed by vendor / body / topic / agency. Empty slots are pre-carved with `.gitkeep` so the acquisition plan is visible before any document arrives.

| Subdirectory | Contents | Index |
|--------------|----------|-------|
| [datasheets/](datasheets/) | Vendor datasheets and reference manuals (ESP32-S3, T-Watch S3 schematics, Knowles SPM1423, ST7789, AXP2101, FT6336U, …, bench instruments) | [01-datasheets.md](bibliography/01-datasheets.md) |
| [app-notes/](app-notes/) | Vendor application notes and API-doc snapshots (ESP-IDF v6.0 guides, esp-dsp, LVGL, MEMS-mic mounting) | [02-application-notes.md](bibliography/02-application-notes.md) |
| [standards/](standards/) | Standards and regulatory documents (IEC, ANSI/ASA, ISO, ITU-T/R, EBU, JCGM, ETSI, EU MDR) | [03-standards.md](bibliography/03-standards.md) |
| [books/](books/) | Free, publisher-sanctioned copies only (e.g. Smith, *Spectral Audio Signal Processing*) | [04-books.md](bibliography/04-books.md) |
| [papers/](papers/) | Academic papers, filed by topic under `by-topic/` | [05-papers.md](bibliography/05-papers.md) |
| [reports/](reports/) | Vendor, tool and community technical reports and page snapshots | [07-technical-reports.md](bibliography/07-technical-reports.md) |
| [reference-projects/](reference-projects/) | Catalogue of open-source projects to study (with **License** and **Apache-2.0-compatible?** columns); `clones/` gitignored, `artifacts/` for self-contained files | [06-reference-projects.md](bibliography/06-reference-projects.md) |

Thematic files [08](bibliography/08-voice-metrology-on-the-wrist.md) (voice metrology on the wrist), [09](bibliography/09-visual-feedback-for-singing.md) (visual feedback for singing), [10](bibliography/10-datasets-and-ground-truth.md) (datasets and ground truth) and [11](bibliography/11-esp-idf-platform-and-toolchain.md) (ESP-IDF platform and toolchain) cut across the by-type directories; their `## Filing` sections say where each entry lands.

## Where to find subsystem docs

| Subsystem | Docs location |
|-----------|---------------|
| DSP (FFT normalization, decimation cascade, pitch, band energy, mic EQ) | [`../dsp/design/`](../dsp/design/) |
| Record format and preset schema | [`../protocols/specs/`](../protocols/specs/) |
| ESP32-S3 firmware (build, components, configuration files) | [`../firmware/twatch-s3/README.md`](../firmware/twatch-s3/README.md) |
| Linux companion and golden-file generator (GPL-3.0-or-later) | [`../host/README.md`](../host/README.md) · [`../host/golden/README.md`](../host/golden/README.md) |
| Host tests for the pure-C DSP core | [`../host-tests/README.md`](../host-tests/README.md) |
| Hardware (BOM, acoustic port, teardown measurements) | [`../hardware/README.md`](../hardware/README.md) |
| Datasets, analysis, tools, tests | [`../datasets/`](../datasets/) · [`../analysis/`](../analysis/) · [`../tools/`](../tools/) · [`../tests/`](../tests/) |

## Conventions

- Markdown for everything new. Vendor-supplied PDFs are kept verbatim; human annotations go in a tracked `<original>_notes.md` next to the PDF.
- English everywhere.
- Cross-link with relative paths so the docs work both on GitHub and offline. ASCII diagrams in fenced blocks; no Mermaid.
- Cite proposal sections (`§1`…`§7`), ADR numbers, datasheet pages, and ESP-IDF symbols/strings — never ESP-IDF line numbers. Unsettled values are `(prov.)` or `TBD`.
- Bibliography entries are addressed positionally (`01 #3`, `05 #12`; letter prefixes S/R/P/D in thematic files). Numbering is append-only.
- When a document from the bibliography is acquired, file it under the matching reference-library subdirectory using that category's filename pattern and add a `📥 Filed locally: <relative path>` blockquote to the bibliography entry so the index and the library stay coupled. Documents whose redistribution terms are unknown are filed locally but not committed; the `_notes.md` with derived facts is.
- After filing a new PDF, run `python3 -m doc_ocr extract` from [`../python-scripts/doc_ocr/`](../python-scripts/doc_ocr/) to generate its grep-able sidecar and register it in [`OCR/manifest.tsv`](OCR/manifest.tsv). For acoustic datasheets, `checked` means the sensitivity/SNR/AOP table and the response curve survived extraction (or were digitized to CSV with provenance).
