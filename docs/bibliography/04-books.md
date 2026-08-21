# 04 — Books and textbooks

The shelf kept within arm's reach while writing `spectral_core`, the preset legends and the validation recipes. Ten titles, deliberately short: the project's literature spine is in the papers ([05](05-papers.md)) and the thematic files; books supply the *derivations* those papers assume. Editions noted are the latest known as of 2026-08-20; verify before purchase. ISBN-13 given where known.

Priority key: ★★★ must-have/blocking · ★★ strongly recommended · ★ useful background (defined in [README](README.md)). ADR numbers refer to [`../adr/README.md`](../adr/README.md); "§n" refers to the [proposal](../proposal/01-super-spectral-proposal.md); metric names are rows of the [validation plan](../validation/README.md).

---

## Spectral analysis and DSP

| # | Title | Author / Edition / ISBN-13 | Priority | Why |
|---|-------|----------------------------|:--------:|-----|
| 1 | **Spectral Audio Signal Processing** | Julius O. Smith III, W3K Publishing (2011); **free online edition** at CCRMA. ISBN 9780974560731 | ★★★ | The bridge between Harris 1978 / Nuttall 1981 ([05](05-papers.md)) and working code: the real-FFT N/2 packing identity that `dsps_cplx2real_fc32` implements, COLA/hop constraints, **quadratic peak interpolation on the log-magnitude spectrum** — the method behind the §4 **peak-frequency ≤ 3 cents (injection)** row at 7.8–11.7 Hz bin spacing — and log-magnitude display conventions. The single source ADR 0006 (FFT normalisation and window conventions) cites for derivations. **Start here before buying anything.** |
| 2 | **Understanding Digital Signal Processing** | Richard G. Lyons, Prentice Hall, 3rd ed. (2010). ISBN 9780137027415 | ★★ | CIC and half-band multirate design for the decimation cascade in `audio_source` (the preset model's "decimation stages" that the objective-4 trade-off study prices in mAh/h); Friture removed a mean-based decimator because it is not an adequate anti-aliasing low-pass — this book is how not to repeat that. Also the cleanest treatment of windowing leakage for the preset guidance notes. |
| 3 | **Discrete-Time Signal Processing** | Alan V. Oppenheim, Ronald W. Schafer, Pearson, 3rd ed. (2009). ISBN 9780131988422 | ★ | The fallback authority for sampling, multirate identities, FIR/IIR design and DFT properties whenever ADR 0006 needs a citation more formal than #1. |
| 4 | **DSP using Arm Cortex-M based Microcontrollers: Theory and Practice** — free sample chapter | Cem Ünsalan, M. Erkin Yücel, H. Deniz Gürhan; Arm Education Media (2018). ISBN 9781911531166 (verify); sample chapter PDF free from Arm | ★ | Q-format fixed-point fundamentals. Relevant only if the `sc16` path of esp-dsp (one bit lost per FFT stage) is ever wrapped in block floating point; ADR 0006 currently mandates float32 `fc32`, so this is the reading that would reopen that decision. Cortex-M specifics do not transfer to Xtensa. |

## Voice science and singing

| # | Title | Author / Edition / ISBN-13 | Priority | Why |
|---|-------|----------------------------|:--------:|-----|
| 5 | **The Science of the Singing Voice** | Johan Sundberg, Northern Illinois University Press (1987). ISBN 9780875801209 (hardcover) / 9780875805429 (paperback) | ★★ | The reference text tying together source–filter theory for singing, the singer's formant cluster (the ≈ 2.5–3.5 kHz "ring" band of ADR 0008), soprano formant tuning, vibrato, registers and the phonetogram. **The book to keep open while writing the overlay legends and per-preset guidance notes** (§3 presets; ADR 0010) and the §1 motivation. |
| 6 | **Principles of Voice Production** | Ingo R. Titze, National Center for Voice and Speech, 2nd printing (2000). ISBN 9780874141221 | ★★ | Glottal-flow source models (Rosenberg, LF) and vocal-tract formant targets for the **Tier-0 synthetic vowels** with known F1–F3 and known f0 ([10](10-datasets-and-ground-truth.md)); the physiological basis of H1–H2 as an open-quotient correlate that the host compare mode (ADR 0002) reports. |
| 7 | **The Acoustic Analysis of Speech** | Ray D. Kent, Charles Read, Singular / Thomson Delmar, 2nd ed. (2002). ISBN 9780769301129 | ★ | Practical formant/LPC methodology **and its failure modes at high f0** — the basis for the §4 **F1/F2 ≤ 5 % or 50 Hz** tolerance and the breathy/creaky degradation caveat in §7. |
| 8 | **Linear Prediction of Speech** | John D. Markel, Augustine H. Gray Jr., Springer (1976). ISBN 9783642662881; DOI 10.1007/978-3-642-66286-7 | ★ | Autocorrelation and Burg LPC, Levinson–Durbin, formant extraction by root-solving — the algorithms behind Praat's `To Formant (burg)` that the host golden files (ADR 0009) are generated with; read if the watch ever gets an on-device LPC preview. |

## Display, perception and psychoacoustics

| # | Title | Author / Edition / ISBN-13 | Priority | Why |
|---|-------|----------------------------|:--------:|-----|
| 9 | **Visible Speech** | Ralph K. Potter, George A. Kopp, Harriet C. Green, Van Nostrand (1947). OCLC 665086 (reprinted Dover 1966) | ★ | The original spectrogram display conventions — grey-scale intensity mapping, time/frequency aspect ratio, how formant bands are *read* — that make a spectrogram legible to a voice professional; the historical anchor for ADR 0011 (colormap) and the 240×240 layout decisions in the `ui`. Pairs with the visual-feedback lineage in [09](09-visual-feedback-for-singing.md). |
| 10 | **Psychoacoustics: Facts and Models** | Hugo Fastl, Eberhard Zwicker, Springer, 3rd ed. (2007). ISBN 9783540231592 (verify); DOI 10.1007/978-3-540-68888-4 | ★ | Loudness, sharpness and critical bands — the models behind ISO 532 / DIN 45692 ([03](03-standards.md) #9) if a psychoacoustic timbre scalar is ever added host-side (§7 future work); also the perceptual argument for the equal-loudness overlay (ISO 226, [03](03-standards.md) #8). |

---

## Suggested reading order (priority + dependency)

1. **Smith, *SASP*** (#1, free) — before writing `spectral_core` or ADR 0006; the peak-interpolation section before the first injection-path measurement.
2. **Sundberg** (#5) — before the preset schema (ADR 0010) and the overlay legends are frozen.
3. **Lyons** (#2) — before the decimation cascade and the first energy-per-preset measurement.
4. **Titze** (#6) — before the Tier-0 synthetic-vowel generator is written.
5. **Kent & Read** (#7) — before the F1/F2 tolerance is defended in §4.
6. The rest as the corresponding decision comes up: #8 with the golden-file manifest, #9 with ADR 0011, #3 as a reference, #4 only if fixed-point is reopened, #10 only for psychoacoustic future work.

## Acquisition links

> **📥 Filed locally (D3 pass, 2026-08-20):** #4 Arm Education Media free sample chapter (Ünsalan, Yücel & Gürhan 2018; 42 pp) → `../books/unsalan2018_dsp-using-arm-cortex-m_sample-chapter.pdf` *(local only; see OCR manifest)* — publisher-sanctioned free download, but its redistribution terms are unstated, so it is filed locally (not committed — redistribution unknown; see [OCR manifest](../OCR/manifest.tsv)).
> Only **author- or publisher-sanctioned free copies** may be placed under [`../books/`](../books/README.md): the Arm sample chapter (#4) qualifies; Smith's *SASP* (#1) is free as an HTML site, not a PDF — archive the chapters you cite with their URLs in `_notes.md` rather than scraping the site. Everything else stays physical or behind institutional access and is tracked in this index only.

| # | Access | Link |
|---|--------|------|
| 1 | free | <https://ccrma.stanford.edu/~jos/sasp/> (full text online; print edition via [W3K Publishing](http://www.w3k.org/books/)) |
| 2 | paid | [Pearson](https://www.pearson.com/) — search ISBN 9780137027415; used copies by ISBN at [bookfinder.com](https://www.bookfinder.com) |
| 3 | paid | [Pearson](https://www.pearson.com/) — search ISBN 9780131988422 |
| 4 | free (sample) / paid | Free sample chapter: <https://www.arm.com/-/media/global/resources/education/textbooks/dsp%20sample%20chapter_01_09_19.pdf> · full book: [Arm Education Media](https://www.arm.com/resources/education/books) |
| 5 | paid | [Northern Illinois University Press / Cornell University Press](https://www.cornellpress.cornell.edu/) — search "Science of the Singing Voice"; widely available used |
| 6 | paid | [National Center for Voice and Speech](https://ncvs.org/) — publications; ISBN 9780874141221 |
| 7 | paid | Out of print at the original publisher; search ISBN 9780769301129 at [bookfinder.com](https://www.bookfinder.com) |
| 8 | paid | <https://doi.org/10.1007/978-3-642-66286-7> (SpringerLink; often in institutional subscriptions) |
| 9 | paid (used or library copy) | Out of print; Dover reprint via used sellers; library lookup by OCLC 665086 at [worldcat.org](https://www.worldcat.org/oclc/665086) |
| 10 | paid | <https://doi.org/10.1007/978-3-540-68888-4> (SpringerLink) |

Institutional SpringerLink access usually covers #8 and #10; check before buying.

## Disclosure

Titles, authors and the ISBNs of #1–#3 and #5–#8 come from the 2026-08-20 research session's domain map (which recorded them from publisher pages and the CCRMA site); #4's full-title/ISBN, #9's OCLC and #10's ISBN/DOI are model-recalled and marked "(verify)" where the number itself matters. Editions and prices reflect the session date and **must be verified before purchase**. Nothing is filed yet (roadmap D3); [`../books/`](../books/README.md) is empty.
