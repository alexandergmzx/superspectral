# Standards and normative documents

Acquired copies of the standards, regulations, licence texts and normative guidance that the project's measurements cite or whose boundaries the project chooses not to cross. Acquisition list and rationale: [`../bibliography/03-standards.md`](../bibliography/03-standards.md) (sectioned by the claim each document grounds; this directory is by issuing body). Nothing is filed yet; the directories are pre-carved with `.gitkeep` for the first bulk pass ([roadmap](../roadmap/documentation-roadmap.md) D3).

**Paid texts are never committed.** IEC, ISO, current ANSI/ASA and DIN standards are sold under single-user licences: file them here locally, keep them out of git, and represent them by their `_notes.md` (derived facts, section numbers) and the sha256-keyed row in [`../OCR/manifest.tsv`](../OCR/manifest.tsv). Free texts (ITU, BIPM, EBU, EUR-Lex, FDA, W3C, ETSI deliverables, licence texts, the ANSI S1.11-2004 public copy) are committed verbatim.

## Layout

Organised by issuing body:

```
standards/
├── ansi-asa/     # ANSI S1.11-2004 (free public copy), ANSI/ASA S1.4 / S1.11 (2014 adoptions, paid), S12.2 room noise
├── iec/          # IEC 61672-1/-2/-3, 61260-1/-3, 60942, 61094-4, 62479, 62133-2, 62368-1 (all paid)
├── iso/          # ISO 226, 532-1/-2, 16, 26101-1 / 3745, 7250-1, 9241-210/-112 (paid); DIN 45692 may share the dir
├── itu-t/        # P.51 artificial mouth, P.56 active speech level, P.58 HATS, P.501 test signals (free)
├── itu-r/        # BS.1770-5 loudness, BT.1359-1 AV timing (free)
├── ebu/          # Tech 3253 SQAM document (+ tracks under datasets/, not here)
├── bipm-jcgm/    # JCGM 100:2008 GUM, JCGM 200:2012 VIM (free)
├── etsi/         # EN 301 549 accessibility, EN 300 328, EN 301 489-1/-17 (free deliverables)
└── eu-mdr/       # MDR 2017/745 (Annex VIII Rule 11), MDCG 2019-11, RED 2014/53/EU, AI Act 2024/1689 (EUR-Lex, free);
                  # FDA General Wellness guidance and the licence texts (Apache-2.0, GPL-3.0, LGPL-2.1, FSF/ASF pages)
                  # go in new `fda/` and `licenses/` directories created with a README when first filed
```

## Filing convention

- Filename pattern: `<body>_<doc-id>_<short-title>_<version-or-year>.pdf` — for example `ansi-asa_s1-11_octave-band-filters_2004.pdf`, `iec_61672-1_sound-level-meters_2013.pdf`, `itu-t_p-58_head-and-torso-simulator_2013.pdf`, `bipm-jcgm_100_gum_2008.pdf`, `etsi_en-301-549_ict-accessibility_v3-2-1.pdf`, `eu_mdcg-2019-11_software-qualification_2019.pdf`, `fsf_lgpl-2-1_1999.pdf`.
- Lowercase, hyphens or underscores, no spaces. **Always stamp the edition year or version** — a superseded edition filed without its year is indistinguishable from the current one, and several "(verify)" flags in the bibliography are exactly about edition years.
- Where a document is paid but a free preview, summary or superseded-but-readable edition exists (ANSI S1.11-2004 for IEC 61260-1), file the free version with `_public` or `_superseded` appended and say which clauses differ in `_notes.md`.
- Keep originals unmodified; hand-written notes alongside as `<original>_notes.md` (tracked); generated `<original>.ocr.md` sidecars are gitignored — see [`../OCR/README.md`](../OCR/README.md). For paid texts the sidecar is the *only* machine-readable form and it must stay gitignored too.

## How this couples to the bibliography

Each entry in [`../bibliography/03-standards.md`](../bibliography/03-standards.md) names the metric row, ADR or proposal section it grounds (e.g. IEC 60942 → the absolute-SPL row's calibrator class; MDR Rule 11 → ADR 0005; LGPL-2.1 §6a → ADR 0004), and the thematic files [08](../bibliography/08-voice-metrology-on-the-wrist.md), [09](../bibliography/09-visual-feedback-for-singing.md) and [10](../bibliography/10-datasets-and-ground-truth.md) re-list the same standards under their `S` numbers (cross-map at the end of 03). When a document lands here, add a `📥 Filed locally: <relative path>` blockquote to its entry in 03 (for paid texts: "filed locally, not committed"), remove it from the gap table in [`acquisition-status.md`](../bibliography/acquisition-status.md), and let the [validation plan](../validation/README.md) cite the entry address (`03 #6`) in its Anchor column.
