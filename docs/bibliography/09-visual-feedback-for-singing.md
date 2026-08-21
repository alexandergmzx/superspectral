# 09 — Visual feedback for singing (efficacy premise, latency, legibility, hands-free interaction, accessibility)

**Purpose.** The entire product premise — *a singer who can see a live spectrogram, f0 trace and ring/twang readout on the wrist sings better, or at least understands the voice better* — is asserted in §1 of the [proposal](../proposal/01-super-spectral-proposal.md) and in the [research doc](../research/00-linux-analyzer-architecture-and-build-guide.md) **without a single citation**. The research benchmarked generic analyzers (Spectroid, REW, Friture) and never named the actual field: thirty years of real-time visual feedback systems built *for singing studios*, with efficacy studies. Five reasons the spine is missing:

1. **The prior-art category was skipped.** WinSingad, Sing&See, VoceVista, Singad, Albert, Madde exist, were evaluated, and were reviewed (Hoppe et al. 2006; a 2022 review; a 2026 survey). Without them the project can state neither its novelty claim nor its efficacy premise.
2. **The ≤ 80 ms acoustic-to-photon target has no anchor.** It was inherited from a desktop tool. Action–sound latency thresholds (≈ 10 ms) and the looser tolerance for visual biofeedback are published; the target must be stated *with* a citation and a reason.
3. **The display is the product and its rendering was not examined.** A 1.3″ 240×240 RGB565 panel in daylight, driven from an 8-bit colormap, bands visibly; spectrogram banding reads as spurious harmonic structure. Perceptually uniform, CVD-safe colormaps and their quantisation are a documented problem with documented solutions.
4. **You cannot touch the watch while singing.** The interaction model must be hands-free (auto-arm, wrist-raise, haptic confirm); the small-screen HIG literature and the hands-busy-context literature were absent.
5. **Accessibility was not framed.** A real-time visual voice display is an assistive technology for deaf and hard-of-hearing singers and for speech training; this is a design constraint and a fundable framing, and it is missing entirely.

This is a **thematic list** (see the numbering note in [08](08-voice-metrology-on-the-wrist.md): `05 #n` rows are cross-references to the by-type index and carry no acquisition link here; local `S`/`R`/`P`/`D` rows are new and get their home address when the parallel indexes freeze). Cite as `09 R1`. Every document has exactly one row; where a second section also rests on it, that section says so in prose under its table rather than repeating the row.

**Downstream of this list:** §1 and §5 get rewritten with inline citations; [ADR 0011](../adr/README.md) (colormap/RGB565 LUT), [ADR 0012](../adr/README.md) (hands-free interaction) and the §4 latency rows cite sections B–D; the six presets are compared against the WinSingad/Sing&See display set in the §5 novelty statement.

## Priority key (same scale as the rest of the bibliography)

| Priority | Meaning |
|----------|---------|
| ★★★ | **Must-have / blocking.** The corresponding claim is indefensible without it. |
| ★★  | **Strongly recommended.** Materially strengthens the design or the evaluation. |
| ★    | **Useful background / breadth.** |

---

## A. The efficacy premise and the prior-art category

Grounds §1 (motivation), the §5 novelty statement ("no wrist-worn, on-device, preset-driven analyzer exists in this lineage"), and the O3 in-use-session design in §4.

| # | Item | Priority | Why |
|---|------|:--------:|-----|
| [05 #68](05-papers.md) | **Howard et al. (2004)** — *WinSingad: a real-time display for the singing studio*, LPV 29(3) | ★★★ | The direct ancestor: real-time narrow-band spectrogram, f0 trace, spectral-ratio (singer's formant) display, for teachers and students. The six presets are compared feature-by-feature against this display set in §5. |
| [05 #70](05-papers.md) | **Hoppe, Sadakata & Desain (2006)** — *Development of real-time visual feedback assistance in singing training: a review*, JCAL 22(4) | ★★★ | Reviews Singad, Albert, Sing&See and WinSingad and the quantitative/qualitative evaluations; concludes real-time visual feedback improves singing ability. The one citation that turns §1's premise into a sourced claim. |
| [05 #69](05-papers.md) | **Welch, Howard, Himonides & Brereton (2005)** — real-time feedback in the singing studio, MER 7(2) | ★★ | Action-research evidence from studio use — how teachers and students actually used the displays, which informs *which* preset is on by default. |
| [05 #71](05-papers.md) | **Wilson, Lee, Callaghan & Thorpe (2008)** — *Learning to sing in tune: does real-time visual feedback help?*, JIMS 2(1–2) | ★★ | Controlled pitch-accuracy study (Sing&See): the efficacy evidence for the f0 display specifically, and a session design the O3 bound (≥ N sessions × M singers) can copy. |
| [05 #72](05-papers.md) | **Leong & Cheng (2014)** — real-time visual feedback and pre-service teachers' singing, JCAL 30(3) | ★ | Non-expert population — closest to a self-practice wrist device; grounds the participant-selection line of the O3 in-use sessions (§4) and the §7 generalisability limitation. |
| [05 #73](05-papers.md) | **Real-time visual feedback in singing pedagogy: current trends and future directions (2022)**, Applied Sciences 12(21) | ★★ | The current review; its "future directions" section is where §7 states the gap this project fills (wearable, on-device, no PC). |
| [05 #74](05-papers.md) | **dos Santos & Masiero (2026)** — 30+ years of automatic singing assessment, arXiv:2601.12153 | ★★ | Maps the field's evolution and names "lack of standardized evaluation frameworks" as a persistent gap — the O5 contribution is positioned against it. |
| R1 | **Sing&See — research index page** (snapshot) — home: [07](07-technical-reports.md) (new agency dir `sing-and-see/`) | ★★ | Curated list of the efficacy studies behind a commercial product (Callaghan, Thorpe, Wilson, van Doorn); the fastest way to find the studies not yet in 05 — a D3 search task that feeds the §1 evidence paragraph. |
| R2 | **VoceVista — product and method pages** (Miller & Schutte lineage; snapshot) — home: [07](07-technical-reports.md) | ★ | The other long-lived singing-studio spectrogram tool; its display conventions (harmonic overlay, EGG pairing) are the second baseline for the §5 comparison. |
| P1 | **Madde** (Svante Granqvist, KTH) voice synthesiser and related KTH teaching tools — home: [06](06-reference-projects.md) | ★ | KTH's pedagogical software line (verify current hosting); background for how the singing-voice-science community visualises source and filter — informs the source/filter wording of the preset legends (ADR 0010) and the §1 motivation; no code is taken. |

The speech-training-aid branch of the same lineage — **Öster (2006)**, [05 #75](05-papers.md) — is listed once, in section E, where it grounds the §5 accessibility framing.

## B. Latency — what "real-time" has to mean on a wrist

Grounds the §4 rows *acoustic-to-photon ≤ 80 ms mean / ≤ 120 ms p99*, *analysis-to-GPIO*, and *sustained refresh ≥ 30 Hz (50 Hz `live_singing`)*, and the §7 statement of what the user can perceive.

| # | Item | Priority | Why |
|---|------|:--------:|-----|
| [05 #83](05-papers.md) | **Jack, Mehrabi, Stockman & McPherson (2018)** — action-sound latency and perceived instrument quality, Music Perception 36(1) | ★★★ | Action–sound tolerance is ≈ 10 ms for musicians; visual biofeedback of one's own voice is a different, looser regime — the 80 ms target of the §4 acoustic-to-photon row is defended *by contrast* with this, not by assertion. |
| [05 #84](05-papers.md) | **McPherson, Jack & Moro (2016)** — *Action-sound latency: are our tools fast enough?*, NIME 2016 | ★★ | The measurement method the §4 test copies (oscilloscope, stimulus on ch1, sensor on ch2 — here a phototransistor taped to the LCD); also the honest finding that most platforms miss their own targets. |
| [05 #85](05-papers.md) | **Schmid et al. (2024)** — JND for audio latency, Audio Mostly 2024 (verify) | ★★ | Recent JND data to bound the §4 acoustic-to-photon p99 (≤ 120 ms) row. |
| S1 | **ITU-R BT.1359-1** — relative timing of sound and vision for broadcasting — free — home: [03](03-standards.md) | ★ | The broadcast AV-sync tolerance window (detectability ≈ +45/−125 ms; acceptability ≈ +90/−185 ms) — the closest *standardised* number for "sound, then picture" perception; cite it as the upper bound the §4 80 ms target sits inside and in the §7 perception statement. |
| — | **Refresh vs perception on a 1.3″ screen** — no source yet; routed to the O4 trade-off study | ★★ | The 50 Hz figure came from a desktop display; on a wrist at arm's length the perceptual return above ≈ 30 Hz is questionable while the display path is the dominant power consumer. Not a document: a measured trade-off (preset × refresh × mAh) with a user-rating arm in the O3 sessions. |

## C. Legibility — colormaps, RGB565 and daylight

Grounds [ADR 0011](../adr/README.md) (cividis/batlow-class, pre-quantised 256-entry RGB565 LUT with ordered dithering, or ST7789 18-bit mode at SPI-bandwidth cost) and the `display_backend` component.

| # | Item | Priority | Why |
|---|------|:--------:|-----|
| [05 #76](05-papers.md) | **Nuñez, Anderton & Renslow (2018)** — cividis, PLOS ONE | ★★★ | CVD-safe, linear-luminance, two-hue, high-contrast: the likely default map of ADR 0011 for a sunlit 1.3″ panel, and the accessibility anchor of section E (§5). |
| [05 #77](05-papers.md) | **Crameri, Shephard & Heron (2020)** — the misuse of colour in science communication, Nat. Commun. | ★★★ | batlow and the written argument against rainbow maps; ADR 0011's justification paragraph. |
| [05 #78](05-papers.md) | **Smith & van der Walt (2015)** — viridis derivation | ★★ | The CAM02-UCS method — how to *re-derive* a map at 5/6/5-bit resolution instead of truncating an 8-bit one; the method of the LUT generator script under `python-scripts/` (ADR 0011). |
| [05 #79](05-papers.md) | **Kovesi (2015)** — good colour maps: how to design them | ★★ | The sine-ramp test pattern = the acceptance test for banding in the RGB565 LUT (a CI screenshot test on the simulator target, ADR 0013). |
| [05 #80](05-papers.md) | **Borland & Taylor (2007)** — rainbow color map (still) considered harmful, IEEE CG&A 27(2) | ★★ | Why the Spectroid-style rainbow spectrogram is rejected — ADR 0011's rejection paragraph and the §3 display description. |
| [05 #81](05-papers.md) | **Liu & Heer (2018)** — empirical assessment of quantitative colormaps, CHI 2018 | ★★ | The task-dependent caveat (peak reading vs texture judgement): ADR 0011 must name the task each preset optimises for, and the O3 sessions include a peak-reading task. |
| [05 #82](05-papers.md) | **Ware (1988)** — color sequences for univariate maps, IEEE CG&A 8(5) | ★ | The founding theory of sequential colour maps — background for ADR 0011's luminance-monotonic requirement. |
| D1 | **Sitronix ST7789V3 datasheet — `COLMOD (3Ah)` and `RAMCTRL` sections** — home: [01](01-datasheets.md) | ★★★ | 16-bit (RGB565) vs 18-bit (RGB666) pixel formats and the SPI-bandwidth cost of the latter; the vertical-scroll registers (`VSCRDEF`/`VSCSAD`) that ADR 0007 depends on. The datasheet decides whether dithering or 18-bit mode is the cheaper fix. |
| P2 | **Scientific Colour Maps** tables + matplotlib `cividis` — home: [06](06-reference-projects.md) #37 | ★★ | The source tables the LUT generator (a script under `python-scripts/`) reads — grounds [ADR 0011](../adr/README.md) (the pre-quantised RGB565 LUT is derived from these tables, not hand-tuned) and [ADR 0004](../adr/README.md) (MIT / BSD-style upstream, so the generated LUT compiled into Apache-2.0 firmware is licence-clean; record the upstream version in the LUT header). |
| — | **Sunlight legibility at the panel's ≈ 450 cd/m²** — no source yet | ★ | Vendor brightness figures are claims; the O3 sessions should include one outdoor condition. Route to §7. |

## D. Glanceable, hands-free interaction

Grounds [ADR 0012](../adr/README.md) (wrist-raise arm via BMA423, haptic confirm via DRV2605L, auto-arm on voice onset) and the `ui` component.

| # | Item | Priority | Why |
|---|------|:--------:|-----|
| R3 | **Apple — Human Interface Guidelines: Designing for watchOS** (snapshot) — home: [07](07-technical-reports.md) | ★★ | Glance duration, minimum touch targets, "interactions should take seconds", complications vs full apps — the vocabulary for a display meant to be read mid-phrase, not operated — grounds ADR 0012's glance-time and target-size rules and the `ui` component's screen budget. |
| R4 | **Google — Wear OS app quality guidelines + design principles** (snapshot) — home: [07](07-technical-reports.md) | ★★ | The Android-side equivalent; its "one-handed / no-handed" guidance is the closest published rule for a singing context — the second source under ADR 0012's auto-arm rule. |
| S2 | **ISO 9241-210:2019** human-centred design · **ISO 9241-112:2017** presentation of information — home: [03](03-standards.md) | ★ | The citable anchor for the UI claims of ADR 0012 and for the §4 O3 session protocol being a *usability evaluation*, not an opinion poll. Paid. |
| — | **Hands-busy / eyes-busy interaction literature** — no specific source yet | ★ | Gap: the singing context is hands-busy (score, instrument), breath-busy (no voice commands) and partially eyes-busy. Route to a search task in D3; until then ADR 0012 rests on R3/R4. |

## E. Accessibility as a feature, not a checkbox

Grounds the §5 practical-significance paragraph, the companion-UI requirements under [`host/`](../../host/README.md), and the CVD-safe default of ADR 0011.

| # | Item | Priority | Why |
|---|------|:--------:|-----|
| [05 #75](05-papers.md) | **Öster (2006)** — visual-feedback speech therapy for profoundly hearing-impaired children (KTH thesis) (verify) | ★ | The assistive-technology lineage: a real-time visual voice display *is* a speech-training aid; frames the deaf/HoH singer as a first-class user — grounds the §5 practical-significance paragraph and the accessibility requirements of the companion UI under [`host/`](../../host/README.md). |
| S3 | **WCAG 2.2** (W3C Recommendation, 2023) — free — home: [03](03-standards.md) | ★★ | Non-colour redundancy (peak markers, numeric readout alongside the spectrogram), contrast minima — applies to the companion web/desktop UI and, by analogy, to the watch `ui`. |
| S4 | **EN 301 549** (ETSI, accessibility requirements for ICT products and services) — free — home: [03](03-standards.md) | ★ | Mandatory framing if any companion UI ships in the EU; cite once in §7. |

The CVD-safe default itself — **cividis**, [05 #76](05-papers.md), row in section C — is the accessibility anchor of ADR 0011; §5 cites it through C.

---

## What transfers from the singing-studio tools to a wrist

| Dimension | Their work (WinSingad, Sing&See, VoceVista) | Our project (Super Spectral on the T-Watch S3) | Transferable? |
|-----------|---------------------------------------------|------------------------------------------------|:-------------:|
| Setting | Studio lesson; teacher interprets the display for the student | Solo practice, rehearsal, anywhere; no interpreter present | Efficacy evidence transfers *with a caveat*: most studies had a teacher in the loop — the O3 sessions must test unassisted use |
| Display | Desktop monitor, many pixels, multiple simultaneous panes | 240×240 at 1.3″, one pane at a time, RGB565, daylight | Display *content* transfers (spectrogram + f0 + formant ratio); *layout* does not → presets are the answer to one-pane-at-a-time |
| Input | Wired condenser mic on a stand, on-axis, fixed distance | PDM MEMS on the wrist, off-axis, moving ([08](08-voice-metrology-on-the-wrist.md)) | Feature definitions transfer; absolute comparisons do not (ADR 0008 relative-only rule) |
| Interaction | Mouse/keyboard between phrases | Hands-free while singing; wrist-raise + haptics (ADR 0012) | Not transferable — the glanceable-wearable HIG literature (D) fills the gap |
| Latency | PC audio path, tens of ms, never stated as a spec | ≤ 80 ms acoustic-to-photon, *measured* with a phototransistor (§4) | Their silence on latency is itself a finding; our measured number is a contribution (§5) |
| Evaluation | Pitch-accuracy gains over weeks with/without feedback | RPA/cents vs Praat (injection and acoustic), then O3 in-use sessions | Their study designs transfer directly to the O3 protocol; their outcome measure (pitch accuracy) is our §4 metric |

Bottom line: the studio literature already shows that *seeing the voice helps*, under teacher supervision and on a big screen. The project's claim is narrower and new: that a **wrist-worn, on-device, hands-free** version can deliver the same displays with a stated fidelity and latency — which is why §5 must cite this file rather than re-argue the premise.

## Minimum set to make the premise defensible (~6 hours)

1. **Hoppe et al. 2006 (05 #70)** — the review that sources the premise.
2. **Howard et al. 2004 (05 #68)** — the display set to compare against.
3. **Wilson et al. 2008 (05 #71)** — one controlled study, for the O3 design.
4. **Jack et al. 2018 (05 #83)** — the latency anchor.
5. **Nuñez et al. 2018 (05 #76)** + **Crameri et al. 2020 (05 #77)** — the colormap decision.
6. **watchOS HIG (R3)** — one evening; then write ADR 0012.

## Filing

- **Papers** (all `05 #` cross-references) → [`../papers/by-topic/visual-feedback-singing/`](../papers/README.md) (#68–#75), `latency-perception/` (#83–#85), `colormaps-visualization/` (#76–#82). Filename `<firstauthor><year>_<short-title>.pdf`.
- **Standards** S1–S4 → [`../standards/<body>/`](../standards/README.md): `itu-r/` (BT.1359-1), `iso/` (9241-210, 9241-112), `etsi/` (EN 301 549); WCAG 2.2 is a W3C Recommendation — file under `iso/` is wrong; create `w3c/` (with `.gitkeep`) when it is filed and list it in the standards README.
- **Reports** R1–R4 → [`../reports/`](../reports/README.md): new agency dirs `sing-and-see/`, `vocevista/`, `apple/`, `google/` created (with `.gitkeep`) at filing time; pattern `<agency>_<short-title>_<YYYY-MM-DD>.pdf` (living pages).
- **Datasheets** D1 → already [01](01-datasheets.md) (`../datasheets/sitronix/`).
- **Projects** P1–P2 → URL-only, [06](06-reference-projects.md).

When a file lands, add `📥 Filed locally: <relative path>` to the entry in its home file and, until the local letters are replaced by home addresses, here too.

## Acquisition links

> **📥 Filed locally:** nothing yet (roadmap D3). Paper links are in [05 — Acquisition links](05-papers.md#acquisition-links); the table below covers the local S/R/P/D entries only.
> **Browser-only:** R1–R4 and S3 are living web pages (print-to-PDF with the capture date in the filename).

Access vocabulary (as in [README](README.md)): `free` · `free (GET)` · `paid` · `mirror` · `free, reg.` · `REPO` · `PORTAL`; qualifiers live in the Link cell.

| # | Access | Link |
|---|--------|------|
| S1 | free | [itu.int/rec/R-REC-BT.1359](https://www.itu.int/rec/R-REC-BT.1359) |
| S2 | paid | [iso.org — ISO 9241-210:2019](https://www.iso.org/standard/77520.html) · [ISO 9241-112:2017](https://www.iso.org/standard/64840.html) (verify record numbers) |
| S3 | free | [w3.org/TR/WCAG22](https://www.w3.org/TR/WCAG22/) (HTML; print-to-PDF) |
| S4 | free (GET) | [etsi.org — EN 301 549](https://www.etsi.org/deliver/etsi_en/301500_301599/301549/) (pick the latest version directory) |
| R1 | free | [singandsee.com/research-visual-feedback](https://www.singandsee.com/research-visual-feedback) (living page — print-to-PDF) |
| R2 | free | [vocevista.com](https://www.vocevista.com/) — product and "method" pages (living page — print-to-PDF; verify current URL) |
| R3 | free | [developer.apple.com — Designing for watchOS](https://developer.apple.com/design/human-interface-guidelines/designing-for-watchos) (living page — print-to-PDF) |
| R4 | free | [developer.android.com — Wear OS quality guidelines](https://developer.android.com/docs/quality-guidelines/wear-app-quality) · [Wear OS design principles](https://developer.android.com/design/ui/wear) (living pages — print-to-PDF) |
| P1 | free | KTH TMH software pages (search "Madde Granqvist"; hosting has moved — verify) |
| P2 | REPO | see [06](06-reference-projects.md) #37 |
| D1 | mirror | see [01](01-datasheets.md) (ST7789V3) |

## Disclosure

Written 2026-08-20. **Live-verified that day:** the WinSingad PDF (imerc.org), the Sing&See research index, Hoppe et al. 2006 (DOI and venue), Wilson et al. 2008 (venue, pages, author PDF), the 2022 Applied Sciences review (DOI), the 2026 arXiv survey, Jack et al. 2018, Nuñez et al. 2018, Crameri et al. 2020, Liu & Heer 2018. **Model-recalled:** the ITU-R BT.1359 tolerance figures quoted in S1 (check the current edition), the ISO record numbers for S2, the VoceVista and Madde URLs, the Öster thesis (existence and year flagged "verify" in 05 #75), the Apple/Google page URLs (they move with each OS release). The gaps marked "—" (refresh-vs-perception on a small screen, sunlight legibility, hands-busy interaction) are genuine: no source was found in this session and none is being invented; they are routed to the O3/O4 studies and to a D3 search task. Nothing in this file has been filed or OCR'd yet.
