# Technical reports and grey literature

Vendor pages, wiki and board-documentation snapshots, commercial-analyzer manuals, evaluation-campaign pages and platform support policies — the documents that are neither datasheets nor papers but that the design cites. Acquisition list and rationale: [`../bibliography/07-technical-reports.md`](../bibliography/07-technical-reports.md); the thematic files [08](../bibliography/08-voice-metrology-on-the-wrist.md) and [09](../bibliography/09-visual-feedback-for-singing.md) add a few `R`-entries that file here too.

Most of what lands here is a **dated snapshot of a living web page**. The point is provenance: the LilyGO wiki, the Zephyr board doc, the MIREX task page and Espressif's support chart all change without versioning, and a design decision must cite the text as it was when the decision was made.

## Layout

Organised by issuing agency (or product, for analyzers):

```
reports/
├── lilygo/             # product page + wiki snapshots, LilyGoLib hardware docs, retail manuals, Meshtastic device page, Seeed display-fps guide
├── spectroid/          # the manual capture of Spectroid's enumerated settings (Play page + screenshots + transcript)
├── nti-audio/          # XL2 operating manual (commercial handheld feature model)
├── rew/                # Room EQ Wizard help/features (visualisation vocabulary)
├── friture/            # Friture features page (host-side reference numbers)
├── mirex/              # Audio Melody Extraction task page + results archive (the 50-cent convention)
├── asha-els/           # ASHA practice-portal snapshot; ELS/ASHA protocol companions (the papers themselves are in papers/)
├── espressif-tools/    # SUPPORT_POLICY/ROADMAP/support-periods, QEMU peripheral matrix, EOL advisories, developer-blog posts
└── (created at filing time, each with .gitkeep)
    ├── regulatory/     # RED chip-down FAQ, MDR Rule 11 explainer          (07 #21–22)
    ├── sing-and-see/   # Sing&See research index                           (09 R1)
    ├── vocevista/      # VoceVista method pages                             (09 R2)
    ├── apple/          # watchOS Human Interface Guidelines                 (09 R3)
    └── google/         # Wear OS quality guidelines / design principles     (09 R4)
```

The first eight directories exist with `.gitkeep` placeholders. Add a directory only together with the bibliography entry that fills it.

## Filing convention

- Filename pattern: `<agency>_<short-title>_<year>.pdf` for documents with an edition or release date — `nti-audio_xl2-manual_2024.pdf`, `lilygo_t-watch-s3-user-manual_2023.pdf`.
- **Living web pages use the full capture date:** `<agency>_<short-title>_<YYYY-MM-DD>.pdf` — `lilygo_t-watch-s3-product-page_2026-08-20.pdf`, `espressif-tools_support-policy_2026-08-20.pdf`, `mirex_audio-melody-extraction_2026-08-20.pdf`. Print-to-PDF from a browser; keep the URL in the PDF header or in a one-line `<file>_source.md` next to it.
- Repository files (e.g. `SUPPORT_POLICY.md`, LilyGoLib `docs/hardware/*.md`) are rendered to PDF at a pinned commit; record the SHA in the filename or sidecar (`espressif-tools_support-policy_<sha7>.pdf`).
- Lowercase, hyphens, no spaces. Keep the original unmodified; notes go in `<original>_notes.md`; machine extractions (`<original>.ocr.md`) are generated and gitignored — see [`../OCR/README.md`](../OCR/README.md).
- **Binaries are not reports.** The LilyGoLib factory firmware (07 #4) is an *artifact*: its manifest (URL, date, sha256, flash command) lives under [`../reference-projects/artifacts/lilygolib/`](../reference-projects/README.md); the binary itself stays off-repo.
- **The Spectroid capture (07 #9)** is a manual task: `spectroid_play-page_<date>.pdf`, `spectroid_settings-screenshots_<date>.pdf` (one PDF of all screenshots) and `spectroid_settings-transcript_<date>.md` listing every enumerated value verbatim.

## How this couples to the bibliography

Each entry in [`../bibliography/07-technical-reports.md`](../bibliography/07-technical-reports.md) names an agency directory; when a file lands, add a `📥 Filed locally: ../reports/<agency>/<file>` blockquote to the entry and stamp the capture date into its Identifier cell. The highest-leverage documents in this directory are the ones that settle *provenance disputes* (470 vs 400 mAh, 1.3″ vs 1.54″, "Not actively maintained", the v6.0.2 support window) — cite the snapshot, never the live page, in ADRs and in the proposal.
