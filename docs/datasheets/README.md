# Datasheets

Acquired datasheets, reference manuals, schematics and bench-instrument specifications for every part on the T-Watch S3 and every instrument in the validation chain. The acquisition list and the rationale for each document live in [`../bibliography/01-datasheets.md`](../bibliography/01-datasheets.md); the actual PDFs live here. Nothing is filed yet — the directories are pre-carved with `.gitkeep` so the acquisition plan is visible before the first bulk pass ([roadmap](../roadmap/documentation-roadmap.md) D3).

## Layout

Organised by vendor, then part; instruments by model under `instruments/`:

```
datasheets/
├── espressif/esp32-s3/            # datasheet, TRM, errata, hardware design guidelines, ESP-PSRAM64 fallback
├── lilygo/t-watch-s3/             # schematics V1.4 (T_WATCH_S3.pdf) and 2025-03-24 revision
├── knowles/spm1423hm4h-b/         # PDM MEMS microphone — pin the revision; digitised response curve CSV lives here
├── tdk-invensense/t3902/          # candidate second-source microphone (T-Watch Ultra)
├── analog-devices/max98357a/      # I²S Class-D amplifier (calibration-tone path)
├── sitronix/st7789/               # ST7789V3 spec + V/VW/V2 comparison set (T_SCYCW)
├── x-powers/axp2101/              # PMU datasheet + register map
├── focaltech/ft6336u/             # touch controller (FT6236/FT6336/FT6436 family)
├── bosch/bma423/                  # accelerometer (wrist-raise arming)
├── nxp/pcf8563/                   # RTC
├── ti/drv2605l/                   # haptic driver
├── semtech/sx1262/                # LoRa transceiver (held in reset in v1, ADR 0017)
├── winbond/w25q128jw/             # serial NOR flash: the schematic says JW (1.8 V),
│                                 # the silicon reads ef 4018 = JV-class 3.3 V (ADR 0016)
├── ap-memory/psram/               # APS6408L octal PSRAM (in-package)
├── seiko/ms412fe/                 # RTC backup coin cell
├── everlight/ir12-21c/            # IR emitter
└── instruments/
    ├── bk-4231/                   # B&K Type 4231 sound calibrator (BP1311); 4128-C HATS (BP0521) may share the dir
    ├── minidsp-umik-1/            # UMIK-1 product brief + per-serial calibration file
    ├── nordic-ppk2/               # Power Profiler Kit II user guide
    └── qoitech-otii/              # Otii Arc Pro technical specification
```

Parts without a directory yet (speaker transducer, display module, battery cell, `ULC0511C`, Panasonic AXK8) get one when a document actually exists; until then they are `TBD` rows in the bibliography.

## Filing convention

- Filename pattern: `<vendor>_<part>_<doctype>_<version>.pdf` — for example `espressif_esp32-s3_datasheet_v2.2.pdf`, `espressif_esp32-s3_trm_v1.8.pdf`, `knowles_spm1423hm4h-b_datasheet_revA.pdf`, `lilygo_t-watch-s3_schematic_v1.4.pdf`, `lilygo_t-watch-s3_schematic_2025-03-24.pdf`, `bk_4231_product-data_bp1311.pdf`.
- Lowercase, hyphens or underscores, no spaces. **Always include the version stamp**: vendors revise datasheets silently, and for this project two of them (Knowles SPM1423, Sitronix ST7789) differ *numerically* between revisions. A mirror whose revision cannot be determined is filed as `_rev-unknown` and flagged in [`../bibliography/acquisition-status.md`](../bibliography/acquisition-status.md).
- Keep the original vendor PDF unmodified. Hand-written excerpts, derived facts and "which mirror served which revision" go alongside as `<original>_notes.md` — tracked in git, never touched by tooling.
- **Digitised figures** (the Knowles free-field response curve, the acoustic table if it must be transcribed) are committed next to the PDF as `<original>_<figure>.csv` with a provenance header block (source file, revision, page, axes and units, digitisation tool and date, who). The OCR ledger's `checked` flag for acoustic datasheets means these exist — see [`../OCR/README.md`](../OCR/README.md).
- Machine extractions are generated, not written by hand: `python3 -m doc_ocr extract` produces `<original>.ocr.md` (or an `<original>.ocr/` directory for documents over 250 pages, e.g. the TRM). These are **gitignored and disposable**; the tracked record is the sha256-keyed row in [`../OCR/manifest.tsv`](../OCR/manifest.tsv).
- Redistribution: Espressif and distributor-hosted datasheets are committed verbatim (`*.pdf binary`); documents with unstated terms (the LilyGO schematics are the open case) may be kept local and represented by their `_notes.md` — decide at filing time and say so in the `📥` blockquote.
- **Directory-README exception (swarm parity).** The vendor level (`espressif/`, `knowles/`, `instruments/`, …) is a pure grouping level: it carries neither a `README.md` nor a `.gitkeep`. This file is the README for the whole `datasheets/` tree, and only the part-level leaves (`espressif/esp32-s3/`, `knowles/spm1423hm4h-b/`, …) hold a `.gitkeep` until their first PDF arrives. This mirrors `swarm/docs/datasheets/<vendor>/<part>/` exactly and is the one place in the library where the "every directory has a README" rule is satisfied by the parent. A vendor-level `_notes.md` is still allowed when a fact spans several parts from the same vendor (e.g. one Sitronix note comparing ST7789V/VW/V3), but never a vendor-level README.

## How this couples to the bibliography

Each entry in [`../bibliography/01-datasheets.md`](../bibliography/01-datasheets.md) names a target part and says which ADR, proposal section, metric or firmware component it grounds. When a datasheet lands here, add a `📥 Filed locally: <relative path>` blockquote to that entry's *Acquisition links* section and remove it from the gap table in [`acquisition-status.md`](../bibliography/acquisition-status.md), so the index and the library stay in sync. Firmware that depends on a specific number (a timing constant in `display_backend`, the PDM clock window in `audio_source`, a register address in `twatch_bsp`) cites the entry address (`01 #13`) and the page in a header comment so the link survives refactors.
