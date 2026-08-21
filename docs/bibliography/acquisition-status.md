# Acquisition status — what's filed and what's still missing

Ledger for the bulk-acquisition passes over bibliography files [01](01-datasheets.md)–[11](11-esp-idf-platform-and-toolchain.md). It records **what could not be pulled down automatically and why**, so a human knows exactly what to grab in a browser (or through institutional access) and what is a dead end. The inverse — what *was* filed — is marked with `📥 Filed locally` blockquotes in each source file's *Acquisition links* section; this file never duplicates those.

**Snapshot (updated 2026-08-21, overnight session U5): 46 documents filed / 16 fetch failures outstanding, both quarantined downloads resolved; 16 reference repositories cloned (1 failed).** `scratch/fetch_bibliography.sh` attempted 65 direct URLs (the scriptable quick-wins subset): 47 returned a PDF, 18 failed (log: `scratch/fetch_results.tsv`). Of the 47, one was a byte-identical mirror (ESP32-S3 datasheet v2.2, dropped), one was the **wrong document** (ISMIR 2014 `000308` is Lartillot's motivic-analysis paper, not mir_eval) and one arrived **truncated** (NTi XL2 manual) — both quarantined under `scratch/d3-quarantine/` and **both resolved on 2026-08-21** (mir_eval re-fetched from Zenodo and committed; XL2 re-fetched complete and filed locally). Two further retries that night (YIN, Sundberg 1994) hit the same 5xx twice and are closed per the bounded-retry rule. Every filed PDF was renamed to the library convention with the revision read from inside the file (`scratch/d3-renames.tsv`), extracted with `doc_ocr` and registered in [`../OCR/manifest.tsv`](../OCR/README.md): 44 rows, 3 100 pages, 4 split sidecars (TRM 1531 pp, three ST7789 specs), all `unchecked`; `redistributable` = yes 11 · unknown 25 · no 8 — only the 11 `yes` rows (Espressif ×3, LilyGO schematics ×2, ANSI S1.11-2004, ISMIR papers ×5) are committed, the rest stay local and are represented by their manifest row. **Not attempted this pass** (no browser, no headless Chromium): the Espressif HTML-page snapshots ([02](02-application-notes.md) sections A/E/F/G, [11](11-esp-idf-platform-and-toolchain.md)), the free ITU / BIPM / EUR-Lex / ETSI / W3C standards ([03](03-standards.md)), the report-page captures ([07](07-technical-reports.md), [09](09-visual-feedback-for-singing.md)), the remaining free (GET) papers, and every PORTAL / REG / request item — all **OPEN-TODO**, listed once per file below rather than row by row. The tables list the *remaining* gaps only; everything filed is stamped `📥` in its home file.

**About the links:** each row's **Where to get it** column is a live link to the best available source — a direct PDF where one exists (works in a browser even when it is `CDN-BLOCK`ed to scripts), otherwise the portal, DOI, or repository. For paywalled papers the link is the `doi.org` resolver; open it through institutional access.

## Why an item is missing — reason legend

| Tag | Meaning | Can a human get it? |
|-----|---------|---------------------|
| **PAYWALL** | Behind a publisher paywall (IEEE, Elsevier, Springer, Wiley, ACS, Nature, ACM, T&F). | Yes, via institutional access / DOI / author email. |
| **CDN-BLOCK** | Vendor CDN / Cloudflare serves a bot-challenge or resets the connection to scripted fetches; a real browser downloads fine. | Yes — open the link in a browser. |
| **PORTAL** | No stable direct-PDF URL: the file sits behind a "Documents" tab, search box, or resource hub. | Yes, with a click or two. |
| **REG** | Free but requires registration / login / click-through license. | Yes, after signup. |
| **HTML-ONLY** | Published as a living web page; no canonical PDF exists. | It's already "readable"; archive the page if needed. |
| **PAID-STD** | Standards body sells the text (ISO/IEEE/NMEA). | Yes, by purchase. |
| **PHYSICAL** | Print/paid book, no sanctioned free copy. | Buy / library. |
| **REPO** | A git repository or dataset, not a document — cloned/downloaded on demand. | `git clone` / dataset portal. |
| **LOST** | Pre-digital or the original host has lapsed; genuinely hard. | Cite the secondary source. |
| **OPEN-TODO** | Legitimately free and scriptable — simply not attempted this pass. **Fetchable on request.** | Yes, trivially. |

Project-specific reading of two tags: **HTML-ONLY** pages that the bibliography needs as *evidence* (Espressif programme docs, the LilyGO wiki, the Zephyr board doc) are not left as links — they are captured as **dated PDF snapshots** and filed; the tag then only means "no vendor PDF exists, ours is a capture". **PAID-STD** texts, once bought, are filed locally but **never committed** (see [README — Acquisition tips](README.md#acquisition-tips)).

---

## 01 — Datasheets

Filed (18 files, 16 entries): #1, #2, #4, #6, #7, #9 (Rev A + Rev D), #13, #14 (V + VW), #16, #17, #25, #30, #31, #33, #34, #35 — see the `📥` block in [01 — Acquisition links](01-datasheets.md#acquisition-links). Remaining:

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| 3 | ESP32-S3 Series Chip Errata — the `espressif.com/sites/default/files/documentation/` URL now returns an HTML page (HTTP 200, `text/html`) | PORTAL | [documentation.espressif.com/esp32-s3_errata_en.pdf](https://documentation.espressif.com/esp32-s3_errata_en.pdf) (the host that served the datasheet and TRM; verify) · [technical-documents portal](https://www.espressif.com/en/support/documents/technical-documents?keys=esp32-s3+errata) |
| 9 | Knowles SPM1423HM4H-B — **vendor original** (knowles.com returns 404 with a JavaScript body) and the **Mouser** mirror (bot challenge). *Rev A and Rev D are filed from the M5Stack and DigiKey mirrors; the vendor copy is wanted only to learn which revision Knowles considers current.* | LOST / CDN-BLOCK | [knowles.com model downloads](https://www.knowles.com/docs/default-source/model-downloads/spm1423hm4h-b.pdf) (try in a browser; else the [product search](https://www.knowles.com/subdepartment/dpt-microphones/subdpt-sisonic-surface-mount-mems)) · [Mouser PDF](https://www.mouser.com/datasheet/2/218/SPM1423HM4H-B-876897.pdf) |
| 11 | MAX98357A/B datasheet — analog.com resets scripted connections (HTTP 000) | CDN-BLOCK | [MAX98357A-MAX98357B.pdf](https://www.analog.com/media/en/technical-documentation/data-sheets/MAX98357A-MAX98357B.pdf) (browser) · [product page](https://www.analog.com/en/products/max98357a.html) |
| 14 | ST7789V2 datasheet (Mouser mirror, bot challenge). *V (V1.3) and VW (V1.0) are filed; V2 completes the `T_SCYCW` comparison set.* | CDN-BLOCK | [Mouser PDF](https://www.mouser.com/datasheet/2/744/ST7789V2-3314280.pdf) (browser) |
| 16 | FT6336 mirrors at displayfuture (serves HTML at the old path) and focuslcds (403). *Redundant — the buydisplay family datasheet V0.3 is filed; listed so nobody retries them.* | LOST / CDN-BLOCK | [focuslcds FT6236.pdf](https://focuslcds.com/wp-content/uploads/Drivers/FT6236.pdf) (browser) — or skip |
| 21 | ESP-PSRAM64 / 64H datasheet — the `espressif.com/sites/default/files/…` URL returns an HTML page | PORTAL | [technical-documents portal, search "PSRAM64"](https://www.espressif.com/en/support/documents/technical-documents?keys=psram64) · try [documentation.espressif.com/esp-psram64_esp-psram64h_datasheet_en.pdf](https://documentation.espressif.com/esp-psram64_esp-psram64h_datasheet_en.pdf) (verify) |
| 22 | Bosch BMA423 datasheet — Mouser bot challenge; Bosch product page is a portal | CDN-BLOCK | [Mouser PDF](https://www.mouser.com/datasheet/2/783/BSCH_S_A0010021471_1-2525113.pdf) (browser) · [bosch-sensortec.com BMA423](https://www.bosch-sensortec.com/products/motion-sensors/accelerometers/bma423/) → Documents |
| 24 | NXP PCF8563 datasheet — `nxp.com/docs/en/data-sheet/PCF8563.pdf` is a 404 (path moved) | LOST | [NXP PCF8563 product page](https://www.nxp.com/products/PCF8563) → Documentation tab (browser; NXP's CDN also blocks scripts) |
| 5, 8, 10, 12, 15, 18–20, 23, 26–29, 32, 36 | Not attempted: PORTAL (Cadence, TDK T3902, Winbond, AP Memory, Panasonic, Earthworks/GRAS), REPO (#8 esp-bsp — cloned, see 06; #23 BMA423-Sensor-API — not in the clone list yet), request (#12 speaker, #15 panel), n/a (#18 cell, #29 `ULC0511C`, #36 counter), free pages not fetched (#19 MS412FE, #27 IR12-21C, #26 SX1262) | OPEN-TODO / PORTAL | links in [01 — Acquisition links](01-datasheets.md#acquisition-links) |

## 02 — Application notes

Filed (3 files, 2 entries): #60 Knowles selection guide R5, #65 GORE portfolio + GAW334 — see [02 — Acquisition links](02-application-notes.md#acquisition-links). Remaining:

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| 63 | TDK InvenSense AN-100 v1.3 — the 2016 `wp-content/uploads` URL is a 404; TDK moved its notes behind the documentation portal | LOST | [TDK InvenSense documentation](https://invensense.tdk.com/developers/documentation/) (search "AN-100") · the sibling [AN-1003 download page](https://invensense.tdk.com/download-pdf/an-1003-recommendations-for-mounting-and-connecting-invensense-mems-microphones/) |
| 62 | TDK AN-1003 mounting and connecting — download page, not a direct PDF; not attempted | PORTAL | [download page](https://invensense.tdk.com/download-pdf/an-1003-recommendations-for-mounting-and-connecting-invensense-mems-microphones/) (one click) |
| 1–59, 61, 64, 66+ | Espressif ESP-IDF v6.0.2 pages, esp-dsp, esp-bsp `performance.md`, LVGL 9, Zephyr board files, pinned source snapshots, Infineon MEMS housing note — living pages or repository files; need headless Chromium or a `git show` at the pinned tag | HTML-ONLY / REPO / OPEN-TODO | `chromium --headless --print-to-pdf=<file> <url>` over the URLs in [02 — Acquisition links](02-application-notes.md#acquisition-links); name them `espressif_esp-idf-v6.0.2_<slug>_2026-MM-DD.pdf` |

## 03 — Standards

Filed (1 file): #1 ANSI S1.11-2004 (law.resource.org) — committed. Remaining:

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| 10–15, 17, 20, 23–27, 32–40, 42 | ITU-T P.51 / P.56 / P.58 / P.501, ITU-R BS.1770-5 / BT.1359-1, EBU Tech 3253 + SQAM, JCGM 100 (GUM) + JCGM 200 (VIM), WCAG 2.2, ETSI EN 301 549 / 300 328 / 301 489, RED / MDR / AI Act (EUR-Lex), MDCG 2019-11, FDA General Wellness, licence texts, FAIR — free and scriptable, **not attempted** | OPEN-TODO | direct links in [03 — Acquisition links](03-standards.md#acquisition-links); ITU PDFs need the `!!PDF-E` suffix, EUR-Lex the `/TXT/PDF/` form |
| 2–9, 16, 18–19, 21–22, 28–31, 41 | IEC 61672 / 61260 / 60942 / 61094-4, ISO 226 / 532 / 3745 / 26101 / 9241, IEC 62133-2, current ANSI/ASA texts | PAID-STD | store links in [03](03-standards.md); buy only what changes an absolute number (see README — Acquisition tips) |

## 04 — Books

Filed (1 file): #4 Arm sample chapter (Ünsalan et al. 2018) — local only (terms unstated). Remaining:

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| 1 | Smith, *Spectral Audio Signal Processing* — HTML book; archive only the cited chapters with their URLs in `_notes.md` | HTML-ONLY | [ccrma.stanford.edu/~jos/sasp](https://ccrma.stanford.edu/~jos/sasp/) |
| 2, 3, 5–10 | Lyons; Oppenheim & Schafer; Sundberg; Titze; Kent & Read; Markel & Gray; Potter/Kopp/Green; Fastl & Zwicker | PHYSICAL | ISBNs in [04](04-books.md); library / institutional SpringerLink-Wiley access |

## 05 — Papers

Filed (21 files, 20 entries + one [10](10-datasets-and-ground-truth.md) paper): #7, #8, #16 (commentary), #17, #20, #21, #23 (companion), #25, #33, #52, #54, #57, #58, #61, #67, #68, #71, #81, #84, #86 — see [05 — Acquisition links](05-papers.md#acquisition-links). Remaining:

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| 1 | Heinzel, Rüdiger & Schilling 2002 — holometer.fnal.gov answers 403 to scripts | CDN-BLOCK | [holometer.fnal.gov/GH_FFT.pdf](https://holometer.fnal.gov/GH_FFT.pdf) (browser) · [MPG PuRe record](https://pure.mpg.de/pubman/faces/ViewItemOverviewPage.jsp?itemId=item_152164) (verify item id) |
| 7 | Boersma 1993 — `fon.hum.uva.nl/archive/1993/Proc17Boersma.pdf` refused the connection (HTTP 000). *The author's `Proceedings_1993.pdf` copy is filed; nothing missing.* | CDN-BLOCK | skip, or [archive copy](https://fon.hum.uva.nl/archive/1993/Proc17Boersma.pdf) in a browser |
| 9 | de Cheveigné & Kawahara 2002 (YIN) — audition.ens.fr returned 503 at fetch time; **retried twice on 2026-08-21, 503 both times** — the host is down, not blocking us; path closed per the bounded-retry rule | CDN-BLOCK | [audition.ens.fr/adc/pdf/2002_JASA_YIN.pdf](http://audition.ens.fr/adc/pdf/2002_JASA_YIN.pdf) (retry; browser) · [doi.org/10.1121/1.1458024](https://doi.org/10.1121/1.1458024) |
| 10 | Mauch & Dixon 2014 (pYIN) — `matthiasmauch.de/_pdf/mauch_pyin_2014.pdf` is a 404 | LOST | [QMUL Research Online](https://qmro.qmul.ac.uk/xmlui/discover?query=pYIN+fundamental+frequency+estimator) (author deposit) · [doi.org/10.1109/ICASSP.2014.6853678](https://doi.org/10.1109/ICASSP.2014.6853678) |
| 14 | Gerhard 2003 TR-CS 2003-06 — `cs.uregina.ca/Research/Techreports/2003-06.pdf` now serves an HTML page | LOST | [University of Regina CS tech reports](https://www.cs.uregina.ca/Research/Techreports/) (browse 2003) · [Semantic Scholar](https://www.semanticscholar.org/search?q=Pitch%20extraction%20and%20fundamental%20frequency%3A%20History%20and%20current%20techniques) |
| 51 | Sundberg 1994 (STL-QPSR 35/2–3) — speech.kth.se answered HTTP 500; **retried twice on 2026-08-21, 500 both times**; path closed per the bounded-retry rule (the QPSR archive index still resolves, so try a different year/file first to tell a dead file from a dead server) | CDN-BLOCK | [speech.kth.se QPSR PDF](https://www.speech.kth.se/prod/publications/files/qpsr/1994/1994_35_2-3_045-068.pdf) (retry; browser) · [QPSR archive index](https://www.speech.kth.se/qpsr/) |
| 53 | Raffel et al. 2014 (mir_eval) — **RESOLVED 2026-08-21**: fetched from Zenodo, first page verified, filed and committed (CC BY 4.0); the wrong link in [05](05-papers.md) #53 is corrected and the Lartillot download stays in `scratch/d3-quarantine/` as the evidence | ~~OPEN-TODO~~ **filed** | [Zenodo 10.5281/zenodo.1416528](https://zenodo.org/records/1416528) → `RaffelMHSNLE14.pdf` (CC BY 4.0; verified 2026-08-20) |
| 59 | Salamon et al. 2017 — `ismir2017/paper/000064.pdf` is a 404 (archive numbering differs from the one recorded) | OPEN-TODO | [ISMIR 2017 proceedings on Zenodo](https://zenodo.org/search?q=%22analysis%2Fsynthesis%20framework%20for%20automatic%20F0%20annotation%22) · [justinsalamon.com/publications](https://www.justinsalamon.com/publications.html) |
| 11, 12, 15, 37, 56, 60, 74, 76, 77, 79, 87–89 | Free (GET) rows not attempted: arXiv (#11, #15, #74, #79), scholarsmine (#12), Nature (#37, #77), ISCA (#56), TISMIR (#60), PLOS (#76), PMC (#87), Farina (#88), SAGE OA (#89) | OPEN-TODO | links in [05 — Acquisition links](05-papers.md#acquisition-links) |
| 30, 44, 45, 66, 73, 92 | Frontiers, MDPI, HAL — Cloudflare / consent shells | CDN-BLOCK | browser; links in [05](05-papers.md) |
| 2–6, 18, 19, 22, 24, 26–29, 31, 32, 34–36, 38–43, 46–50, 55, 62–65, 69, 70, 72, 75, 80, 82, 83, 85, 90, 91 | IEEE, AIP/ASA, ASHA, Elsevier, Wiley, T&F, Springer, SAGE, Karger, ACM | PAYWALL | `https://doi.org/<DOI>` through institutional access; ASHA trio (#63–65) by author e-mail |

## 06 — Reference projects

Cloned (`scratch/clone_refs.sh`, log `scratch/clone.log`, 1.3 GB under the gitignored `../reference-projects/clones/`): esp-dsp, esp-bsp, espp, esp_littlefs, xiao-edge-audio, LilyGoLib, TTGO_TWatch_Library (`t-watch-s3`), SensorLib, XPowersLib, pitch-detection, mir_eval, mirdata, Parselmouth, friture, m5Cardputer_audiospectrum, lvgl (`v9.5.0`) — 16 of 17. Remaining:

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| 17 | antoineschmitt/dywapitchtrack — `git clone` failed (repository gone or renamed) | LOST / REPO | a vendored copy (`dywapitchtrack.c/.h`) is inside the cloned [cyberwisk/m5Cardputer_audiospectrum](https://github.com/cyberwisk/m5Cardputer_audiospectrum) (GPL-3.0 repo — the library itself is MIT; verify the header) · [schmittmachine.com/dywapitchtrack](https://schmittmachine.com/dywapitchtrack/) |
| large / on-demand | circuitpython, zephyr, esp-idf `v6.0.2` study copy (the build copy lives at `~/esp/idf/v6.0.2`) | REPO | commented out in `scratch/clone_refs.sh`; clone when a D4 question needs them |

## 07 — Technical reports

Filed: none. Remaining:

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| 10 | NTi Audio XL2 operating manual — **RESOLVED 2026-08-21**: re-fetched complete (11,204,497 B, firmware V4.93, 360 pp), filed locally as `../reports/nti-audio/nti-audio_xl2-manual_fw4.93_2026.pdf` (`redistributable=unknown`, not committed); the truncated copy stays in `scratch/d3-quarantine/` | ~~OPEN-TODO~~ **filed** | [XL2-Manual.pdf](https://www.nti-audio.com/wp-content/uploads/XL2-Manual.pdf) — re-fetch with `curl -C - -o …` or a browser; file as `../reports/nti-audio/nti-audio_xl2-manual_<year>.pdf` |
| 1–9, 11–15 | LilyGO wiki / product pages, Zephyr board doc, Espressif support-policy / QEMU / EOL pages, REW / Friture help, MIREX wiki, ASHA portal, Spectroid (on-device) — living pages, not attempted | HTML-ONLY | print-to-PDF with the capture date; links in [07 — Acquisition links](07-technical-reports.md#acquisition-links) |

## 08 — Voice metrology on the wrist

Filed via home files: D1 (01 #9), D3 (01 #30), D4 (01 #31), A1 (02 #60), A4 (02 #65), S3-free (03 #1). Remaining 08-local rows:

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| D2 | TDK T3902 datasheet | PORTAL | [invensense.tdk.com/products/digital/t3902](https://invensense.tdk.com/products/digital/t3902/) → Documents |
| A3 | Infineon — PCB and housing design for MEMS microphones | PORTAL / OPEN-TODO | [infineon.com MEMS microphones](https://www.infineon.com/cms/en/product/sensor/mems-microphones/) → Documents |
| S6–S9, ANSUR II / DINED | ITU / BIPM texts and anthropometry tables — free, not attempted | OPEN-TODO | links in [08 — Acquisition links](08-voice-metrology-on-the-wrist.md#acquisition-links) |
| S2–S5, S10 | IEC / ISO / ANSI | PAID-STD | see [03](03-standards.md) |

## 09 — Visual feedback for singing

Filed via home files: D1 (01 #13), papers 05 #68, #71, #81, #84. Remaining 09-local rows:

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| R1–R4 | Sing&See, VoceVista, Apple watchOS HIG, Wear OS guidelines — living pages | HTML-ONLY | print-to-PDF with the capture date; links in [09 — Acquisition links](09-visual-feedback-for-singing.md#acquisition-links) |
| S1, S3 | ITU-R BT.1359-1 (free), WCAG 2.2 (free, HTML) | OPEN-TODO | [ITU-R BT.1359](https://www.itu.int/rec/R-REC-BT.1359/en) · [w3.org/TR/WCAG22](https://www.w3.org/TR/WCAG22/) |
| S2 | ISO 9241-210 / -112 | PAID-STD | ISO store |
| P1, P2 | Madde; Scientific Colour Maps + matplotlib tables | REPO | links in [09](09-visual-feedback-for-singing.md) / [06](06-reference-projects.md) #37 |

## 10 — Datasets and ground truth

Fetched: no corpus (validation phase; manifests to `datasets/corpora/`, never into git). Paper for #6 filed (`dai2023_singstyle111.pdf`). Remaining:

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| all corpora | Tier-0/1 CC BY sets (VocalSet, vocadito, MIR-1K, Dagstuhl ChoirSet, SingStyle111, noise/RIR corpora) | REPO | Zenodo / dataset portals in [10 — Acquisition links](10-datasets-and-ground-truth.md#acquisition-links); fetch by manifest with sha256 |
| 10, 13, 16, 27 | TU Graz, Academia Sinica, NUS, ACE — registration or request | REG | forms linked in [10](10-datasets-and-ground-truth.md) |

## 11 — ESP-IDF platform and toolchain

Filed via home files: 01 #1, #2, #4, #6, #7. Remaining 11-local rows:

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| A-rows, R-rows | Espressif programme docs, component-manager references, espefuse docs, support-policy / QEMU-release / blog pages — living pages at the v6.0.2 rendering | HTML-ONLY / OPEN-TODO | `chromium --headless --print-to-pdf` over the `…/en/v6.0.2/esp32s3/…` URLs in [11](11-esp-idf-platform-and-toolchain.md); R-rows at a named commit |
| P-rows | repositories | REPO | cloned on demand (06) |

---

## Quick wins — what a human can grab in a browser in five minutes

Open these in a normal browser, save the PDF, drop it at the path given, then run `python3 -m doc_ocr extract` and stamp the `📥` block. They are the CDN-blocked and moved items that the scripted pass could not reach; none needs a login.

1. **MAX98357A/B** ([01](01-datasheets.md) #11) — [analog.com PDF](https://www.analog.com/media/en/technical-documentation/data-sheets/MAX98357A-MAX98357B.pdf) → `../datasheets/analog-devices/max98357a/adi_max98357a-b_datasheet_rev<N>.pdf` (read the revision from the footer).
2. **ESP32-S3 errata** ([01](01-datasheets.md) #3) — [documentation.espressif.com/esp32-s3_errata_en.pdf](https://documentation.espressif.com/esp32-s3_errata_en.pdf) or the technical-documents portal → `../datasheets/espressif/esp32-s3/espressif_esp32-s3_errata_v<N>.pdf`.
3. **BMA423** ([01](01-datasheets.md) #22) — [Mouser PDF](https://www.mouser.com/datasheet/2/783/BSCH_S_A0010021471_1-2525113.pdf) → `../datasheets/bosch/bma423/bosch_bma423_datasheet_<rev>.pdf`.
4. **PCF8563** ([01](01-datasheets.md) #24) — [NXP product page](https://www.nxp.com/products/PCF8563) → Documentation → `../datasheets/nxp/pcf8563/nxp_pcf8563_datasheet_rev<N>.pdf`.
5. **ST7789V2** ([01](01-datasheets.md) #14) — [Mouser PDF](https://www.mouser.com/datasheet/2/744/ST7789V2-3314280.pdf) → `../datasheets/sitronix/st7789/sitronix_st7789v2_datasheet_v<N>.pdf`.
6. **ESP-PSRAM64** ([01](01-datasheets.md) #21) — technical-documents portal, search "PSRAM64" → `../datasheets/ap-memory/psram/espressif_esp-psram64h_datasheet_v<N>.pdf`.
7. **Heinzel 2002** ([05](05-papers.md) #1) — [holometer.fnal.gov/GH_FFT.pdf](https://holometer.fnal.gov/GH_FFT.pdf) → `../papers/by-topic/stft-windows-spectral-estimation/heinzel2002_dft-spectrum-estimation.pdf`.
8. **mir_eval** ([05](05-papers.md) #53) — [Zenodo record 1416528](https://zenodo.org/records/1416528) → `../papers/by-topic/mir-evaluation-datasets/raffel2014_mir-eval.pdf` (and fix the `000308` link in 05).
9. **YIN** ([05](05-papers.md) #9) and **Sundberg 1994** (#51) — retry [audition.ens.fr](http://audition.ens.fr/adc/pdf/2002_JASA_YIN.pdf) and [speech.kth.se](https://www.speech.kth.se/prod/publications/files/qpsr/1994/1994_35_2-3_045-068.pdf); both were server errors, not blocks.
10. **NTi XL2 manual** ([07](07-technical-reports.md) #10) — [XL2-Manual.pdf](https://www.nti-audio.com/wp-content/uploads/XL2-Manual.pdf) (the scripted download truncated) → `../reports/nti-audio/nti-audio_xl2-manual_<year>.pdf`.
11. **TDK AN-1003** ([02](02-application-notes.md) #62) — [download page](https://invensense.tdk.com/download-pdf/an-1003-recommendations-for-mounting-and-connecting-invensense-mems-microphones/) → `../app-notes/tdk-invensense/tdk-invensense_an-1003_mounting-and-connecting-mems-microphones.pdf`; AN-100 (#63) from the same documentation portal.

Still scriptable, just not run yet (next `fetch_bibliography.sh` batch): the free standards in [03](03-standards.md), the arXiv / PLOS / Nature / PMC / ISCA papers in [05](05-papers.md), and the Espressif `v6.0.2` page snapshots in [02](02-application-notes.md) via headless Chromium.

**Known browser-only (do not retry with scripts):** Analog Devices (MAX98357A — [01](01-datasheets.md) #11), NXP (PCF8563 — #24), Mouser mirrors (#9, #14, #22), focuslcds (#16), Fermilab holometer (05 #1); ASHA journals and IEEE Xplore for the paywalled papers in [05](05-papers.md); paid IEC/ISO texts ([03](03-standards.md)).

## Method notes (for whoever repeats this)

- **One pass, then ledger.** Run `scratch/fetch_bibliography.sh` (swarm's `fetch()` pattern: URL → target path, browser UA, retries, sha256 logged) over the quick-wins list; `git status` shows what landed; everything else goes into the per-file tables above with a tag. Then the `📥 Filed locally` blockquotes, then `python3 -m doc_ocr extract`, then `python3 -m doc_ocr unchecked` to see the review queue.
- **`wget` vs `curl`.** In the swarm pass ST and Radboud refused `curl` but accepted `wget` (different TLS stack). Try it before declaring a connection reset a `CDN-BLOCK`.
- **Cloudflare 403s are final.** MDPI, NXP's CDN, analog.com, IEEE Xplore, HAL's PDF endpoint and ScienceDirect block every scripted client regardless of headers. Browser or institutional proxy — not a different flag.
- **Espressif HTML → PDF.** Capture the **v6.0.2** rendering (`…/en/v6.0.2/esp32s3/…`), never `stable` or `latest`, with the date in the filename (`espressif_esp-idf-v6.0.2_<slug>_YYYY-MM-DD.pdf`); `chromium --headless --print-to-pdf=<file> <url>` is enough. Re-snapshot only through the [upgrade procedure](../devenv/upgrade-procedure.md).
- **Pin the revision, record the mirror.** Knowles and ST7789 datasheets differ *numerically* between revisions; name the revision in the filename and note in `_notes.md` which mirror served which revision. A mirror whose revision cannot be determined is filed with `_rev-unknown` and flagged in the ledger.
- **Raster tables and curves.** `pdftotext` silently yields nothing for the Knowles acoustic table and response curve; `checked` in the OCR ledger requires a visual read and, for curves, a WebPlotDigitizer CSV committed next to the PDF with a provenance block (source file, revision, page, axes, date, who). See [`../OCR/README.md`](../OCR/README.md).
- **Schematics from GitHub.** Raw URLs are scriptable; WebFetch returns an unreadable stream. Open locally. Record the commit SHA of the repository at fetch time in `_notes.md`.
- **Stores renumber.** IEC/ISO catalogue URLs move; the document identifier + edition is the durable key. Before buying, confirm the edition year against the store listing and update the "(verify)" flags in [03](03-standards.md).
- **Corpora are not documents.** Datasets go to `datasets/corpora/` by manifest with checksums ([10](10-datasets-and-ground-truth.md)); the ledger records the manifest, licence and fetch date, not the files.
- DOIs always resolve at `https://doi.org/<DOI>`; for paywalled items the identifier in each bibliography entry stays authoritative.
