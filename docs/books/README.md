# Books

Free, legitimately-redistributable digital copies of the textbooks in the acquisition list. The full bookshelf (including paid and physical titles) and the rationale for each live in [`../bibliography/04-books.md`](../bibliography/04-books.md); only author- or publisher-sanctioned free copies live here. Nothing is filed yet ([roadmap](../roadmap/documentation-roadmap.md) D3).

> **Only free, sanctioned copies belong here.** Everything in this directory must be redistributed by its author or publisher at no cost. Do **not** add paywalled titles, scanned copies, or "library" mirrors — those stay physical or behind institutional access and are tracked in the bibliography only. Books are otherwise "typically physical"; this directory is the small exception the free editions justify.

## Layout

Flat — the shelf is ten titles and at most two of them have free copies:

```
books/
├── README.md
├── (unsalan2018_dsp-using-arm-cortex-m_sample-chapter.pdf)   # Arm Education Media free sample chapter — 04 #4
└── (smith2011_spectral-audio-signal-processing_notes.md)     # SASP is a free HTML site, not a PDF: cited-chapter
                                                              # URLs + derived formulas, tracked as a notes file — 04 #1
```

## What's filed here

| Bib # | Title | Author(s) | Source |
|-------|-------|-----------|--------|
| — | *(nothing yet — pending the D3 pass)* | | |

## Filing convention

- Filename pattern: `<firstauthor><year>_<short-title>.pdf` (e.g. `unsalan2018_dsp-using-arm-cortex-m_sample-chapter.pdf`); vendor- or project-authored guides use `<vendor>_<short-title>_<version>.pdf`.
- Lowercase, hyphens or underscores, no spaces. Stamp the edition/version where the source revises silently.
- Keep the original PDF unmodified; hand-written notes and excerpts go alongside as `<original>_notes.md` (tracked). Generated `<original>.ocr.md` / `<original>.ocr/` extractions are gitignored — see [`../OCR/README.md`](../OCR/README.md).
- A book that is free **online but not as a PDF** (Smith's *Spectral Audio Signal Processing*) is not scraped; its tracked representation is a `_notes.md` listing the chapters cited, their URLs, the access date, and the formulas the firmware or ADRs depend on (peak interpolation, real-FFT packing, NENBW).

## How this couples to the bibliography

When a free edition lands here, add a `📥 Filed locally: <relative path>` blockquote to its entry in [`../bibliography/04-books.md`](../bibliography/04-books.md), add a row to *What's filed here* above, and remove it from the gap table in [`acquisition-status.md`](../bibliography/acquisition-status.md). Paid titles keep only their purchase-channel links in the bibliography; ADRs cite them by entry address (`04 #5`) and chapter, never by a local path.
