# Acquisition status — what's filed and what's still missing

Ledger for the bulk-acquisition passes over bibliography files [01](01-datasheets.md)–[11](11-esp-idf-platform-and-toolchain.md). It records **what could not be pulled down automatically and why**, so a human knows exactly what to grab in a browser (or through institutional access) and what is a dead end. The inverse — what *was* filed — is marked with `📥 Filed locally` blockquotes in each source file's *Acquisition links* section; this file never duplicates those.

**Snapshot (2026-08-20, D1 — list complete, nothing acquired):** **0 documents filed**; 0 reference repositories cloned; [`../OCR/manifest.tsv`](../OCR/README.md) holds its header only. The first bulk pass is [roadmap](../roadmap/documentation-roadmap.md) phase **D3** (a follow-up session: it changes the working tree by several hundred megabytes and needs a browser for the CDN-blocked vendors). When D3 runs, replace this paragraph with the pass summary (counts, batches, what the browser batch recovered) and fill the per-file tables below with the *remaining* gaps only — everything filed is removed from them.

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

Filed: none — pending first acquisition pass (roadmap D3).

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| — | *(populated by the D3 pass: list only what remains missing)* | | |

## 02 — Application notes

Filed: none — pending first acquisition pass (roadmap D3).

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| — | *(populated by the D3 pass)* | | |

## 03 — Standards

Filed: none — pending first acquisition pass (roadmap D3).

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| — | *(populated by the D3 pass)* | | |

## 04 — Books

Filed: none — pending first acquisition pass (roadmap D3).

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| — | *(populated by the D3 pass)* | | |

## 05 — Papers

Filed: none — pending first acquisition pass (roadmap D3).

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| — | *(populated by the D3 pass)* | | |

## 06 — Reference projects

Cloned: none — pending first acquisition pass (roadmap D3; `scratch/clone_refs.sh`).

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| — | *(populated by the D3 pass)* | | |

## 07 — Technical reports

Filed: none — pending first acquisition pass (roadmap D3).

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| — | *(populated by the D3 pass)* | | |

## 08 — Voice metrology on the wrist

Filed: none — pending first acquisition pass (roadmap D3). Rows already addressed in 01/03/05 are ledgered there; list only 08-local (`D`/`S`/`R`/`P`) rows here.

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| — | *(populated by the D3 pass)* | | |

## 09 — Visual feedback for singing

Filed: none — pending first acquisition pass (roadmap D3).

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| — | *(populated by the D3 pass)* | | |

## 10 — Datasets and ground truth

Fetched: none — pending first acquisition pass (roadmap D3; corpora go to the gitignored `datasets/corpora/` by manifest, never into git).

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| — | *(populated by the D3 pass)* | | |

## 11 — ESP-IDF platform and toolchain

Filed: none — pending first acquisition pass (roadmap D3). Most rows are Espressif HTML pages whose home is [02](02-application-notes.md); ledger them under 02 and list only 11-local `R`/`P` rows here.

| # | Item | Tag | Where to get it |
|---|------|-----|-----------------|
| — | *(populated by the D3 pass)* | | |

---

## Quick wins — free and scriptable, grab these first

The D3 pass should open with these; they are direct PDFs or stable pages that a scripted `fetch()` (in `scratch/fetch_bibliography.sh`) pulls without a browser, and together they cover every ★★★ hardware and platform document.

- **Espressif primary documents** — ESP32-S3 datasheet, TRM, **errata**, hardware design guidelines PDF ([01](01-datasheets.md) #1–4); ESP-PSRAM64 datasheet ([01](01-datasheets.md) #21 fallback).
- **Both T-Watch S3 schematics** — `T_WATCH_S3.pdf` V1.4 and `T_WATCH-S3 25-03-24.pdf` from the two LilyGO repositories ([01](01-datasheets.md) #6–7) — raw GitHub URLs, scriptable; open locally (WebFetch cannot parse them). Decide the commit-vs-link question at filing time.
- **Knowles SPM1423HM4H-B** from the vendor URL plus the three mirrors ([01](01-datasheets.md) #9) — fetch all four and **record which revision each serves** (the AOP 110-vs-115 dB SPL conflict is a revision question).
- **TI DRV2605L**, **SII MS412FE**, **Everlight IR12-21C** pages ([01](01-datasheets.md) #25, #19, #27); **BMA423** Mouser mirror (#22).
- **Instruments** — B&K 4231 (BP1311) and 4128-C (BP0521) product data, PPK2 user guide (DigiKey-hosted), Otii Arc tech spec (SparkFun-hosted), UMIK-1 product brief ([01](01-datasheets.md) #30–35).
- **ESP-IDF v6.0.2 programme documentation as dated PDF snapshots** — the entire [02](02-application-notes.md) sections A, E, F, G (`…/en/v6.0.2/esp32s3/…` pages; headless-browser print-to-PDF, one command per URL), plus the esp-dsp API/benchmark pages and the esp-bsp `performance.md` (#20–21, #25).
- **Pinned source snapshots** — `i2s_pdm.h`, `i2s_pdm.c`, `soc_caps.h` at tag v6.0.2 ([02](02-application-notes.md) #15–16); `esp_lcd_touch_ft5x06.c` at 1.1.1 (#26); Zephyr `boards/lilygo/twatch_s3/` at a named commit (#53); LilyGoLib `src/` bring-up files (#55).
- **MEMS-mic mounting notes** — TDK AN-1003 and AN-100 (direct PDFs), GORE acoustic-vents portfolio + GAW334 ([02](02-application-notes.md) #62–63, #65).
- **Free standards** — ANSI S1.11-2004 (law.resource.org), ITU-T P.51 / P.56 / P.58 / P.501, ITU-R BS.1770-5 and BT.1359-1, EBU Tech 3253 + SQAM tracks, JCGM 100 (GUM) + JCGM 200 (VIM), WCAG 2.2, EN 301 549 / EN 300 328 / EN 301 489 from `etsi.org/deliver`, RED / MDR / AI Act from EUR-Lex, MDCG 2019-11, FDA General Wellness, the four licence texts + FSF/ASF compatibility pages, FAIR principles ([03](03-standards.md) #1, #10–15, #17, #20, #23–27, #32–40, #42).
- **Free books** — Arm DSP sample chapter ([04](04-books.md) #4); Smith *SASP* is an HTML site — archive only the cited chapters with their URLs.
- **From the other files** (their own ledgers govern): open-access papers in [05](05-papers.md) (arXiv, PLOS, Nature Communications, Frontiers, HAL, NIME proceedings), the LilyGoLib factory firmware binary and the Zephyr board-doc / Espressif support-policy snapshots in [07](07-technical-reports.md), the CC BY corpora manifests in [10](10-datasets-and-ground-truth.md).

**Known browser-only (do not retry with scripts):** Analog Devices (MAX98357A — [01](01-datasheets.md) #11), NXP (PCF8563 — #24), buydisplay (FT6336 family — #16), most Sitronix mirrors are fine but the Sipeed ST7789V3 link may need a browser (#13); ASHA journals and IEEE Xplore for the paywalled papers in [05](05-papers.md); paid IEC/ISO texts ([03](03-standards.md)).

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
