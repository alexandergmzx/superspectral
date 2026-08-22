# 08 — Voice metrology on the wrist (microphone admissibility, placement, calibration, uncertainty)

**Purpose.** The acoustic-path half of the research question — ±20 cents median error and ≥ 90 % RPA through the watch case, ±1.5 dB 1/3-octave level, an EIN figure, a "wrist-position envelope" — is, so far, **engineering intuition transplanted from desktop and handheld analyzers without a literature spine**. The digital-injection path is well anchored (mir_eval, Praat, Heinzel — [05](05-papers.md)); the part that makes this a *wearable* result is not. This file is the acquisition list that fixes that. Six reasons the spine is missing:

1. **Admissibility was never assessed.** No document in the research asked whether a −22 dBFS, 61.5 dB(A)-SNR PDM MEMS microphone behind a sealed case meets the criteria the voice-science community already published for research microphones (Švec & Granqvist 2010).
2. **Placement and directivity were treated as nuisance, not as the dominant confound.** A wrist is ≈ 30 cm from the mouth at 45–90° off-axis. The high-frequency directivity of the singing voice makes that position *systematically* different from an on-axis studio mic in exactly the 2.5–5 kHz band the ring/twang readouts live in — and that cell has already been measured (Titze & Winholtz 1993; Katz & d'Alessandro 2007).
3. **The calibration chain is circular.** The ±1.5 dB target was set against a UMIK-1-class reference whose own HF disagreement with Class-1 mics exceeds 2 dB (roadmap correction #8). Either the chain is upgraded, the target widened, or the claim restated as repeatability.
4. **There is no uncertainty budget.** Every threshold is a point number; nothing says what the measurement's combined standard uncertainty is (JCGM 100).
5. **The protocol anchor was declared absent when it exists.** The voice field has two instrumental-assessment protocols (ASHA 2018, ELS 2001) — the analogue of swarm's EPA Performance Targets — and they name microphone, distance, SPL and calibration requirements.
6. **The acoustic port is undocumented.** Port diameter, channel length, cavity volume, gasket and any vent membrane determine the in-situ response more than the transducer does (roadmap correction #9); the relevant vendor application notes were not on the list.

This is a **thematic list**: 01–07 are organised by document *type*; this file is organised by the *claim each document must support*, because wrist metrology cuts across papers, standards, datasheets and app notes at once. Acquired items still file into the by-type library exactly like everything else — see [Filing](#filing).

**How this file numbers things.** Thematic tables are four columns wide — `| # | Item | Priority | Why |` — the **Identifier** column of the by-type files is deliberately absent because the identifier (DOI, document number, revision) lives in the home entry and the Item cell here carries only what is needed to recognise the document. A row whose `#` is an address like `05 #63` is already indexed in a by-type file — that entry is authoritative and carries the acquisition link; it is repeated here only so the claim→evidence map is complete. Rows with a *local* letter-prefixed number (`S1` standards, `D1` datasheets, `A1` app notes, `R1` reports, `P1` projects) are listed here first because their by-type home ([01](01-datasheets.md)/[02](02-application-notes.md)/[03](03-standards.md)/[07](07-technical-reports.md)) was authored in parallel and its entry numbers were not yet fixed; they get their home address when the indexes freeze (roadmap D3). Local numbers are append-only. Cite as `08 S4`. A `#` cell that begins with `→` is a **cross-reference** to a row numbered elsewhere (another section of this file, or another file) — it is not a citation address of its own, so every local number appears exactly once.

**Downstream of this list:** the §4 validation section of the [proposal](../proposal/01-super-spectral-proposal.md) gets rewritten with these citations; [ADR 0003](../adr/0003-microphone-path.md) (microphone path) and the first experiment recipe ([`0001` PDM mic in-situ characterisation](../validation/experiments/README.md)) cite sections A–C; the validation README's "where the thresholds come from" note (07 #15) cites section E.

## Priority key (same scale as the rest of the bibliography)

| Priority | Meaning |
|----------|---------|
| ★★★ | **Must-have / blocking.** The corresponding claim is indefensible without it. |
| ★★  | **Strongly recommended.** Materially strengthens the design or the evaluation. |
| ★    | **Useful background / breadth.** |

Each row's **Why** names the proposal claim, ADR or metric it grounds, so this doubles as a traceability map from §4 back to prior art.

---

## A. Is the microphone admissible at all?

Grounds ADR 0003 (microphone path), experiment 0001, and the §7 limitation that states the answer honestly. The question is prior to every acoustic-path number: if the SPM1423 through the case fails the community's admissibility criteria, the acoustic path is reported as a *characterisation* of a consumer device, not as a voice measurement.

| # | Item | Priority | Why |
|---|------|:--------:|-----|
| [05 #63](05-papers.md) | **Švec & Granqvist (2010)** — *Guidelines for selecting microphones for human voice production research*, AJSLP 19(4). DOI 10.1044/1058-0360(2010/09-0091) | ★★★ | The admissibility criteria: flat within ±2 dB over the band of interest; equivalent noise level ≥ 15 dB below the softest phonation to be measured; omnidirectional to avoid proximity effect. Experiment 0001 tests each criterion *in situ* and §7 reports which are met. |
| D1 | **Knowles SPM1423HM4H-B datasheet** (obsolete part; pin the revision — AOP 110 dB SPL in Rev A vs 115 in Rev D) — home: [01](01-datasheets.md) | ★★★ | Sensitivity −22 dBFS, SNR 61.5 dB(A), PDM clock window 1.0–3.25 MHz, supply range (the GPIO47 1.8 V-domain question). The free-field response and the acoustic table are **raster images** — `pdftotext` yields nothing; digitise with WebPlotDigitizer ([06](06-reference-projects.md) #38) into a CSV with provenance before any "+5 dB by 10 kHz" statement is repeated (roadmap correction #2). |
| D2 | **TDK/InvenSense T3902 datasheet** — home: [01](01-datasheets.md) | ★★ | The likely second source if the 2025 board revision replaced the obsolete SPM1423; every quoted SNR/AOP number is invalid if the part changed. Read the part marking in E2 before trusting D1. |
| A1 | **Knowles — MEMS microphone specifications explained / mic selection guide** (`mic-selection-guide-r5.pdf`) — home: [02](02-application-notes.md) | ★★ | Translates datasheet numbers into what may honestly be displayed: what dBFS means for this part, where AOP caps loud singing, how sleep-vs-normal PDM clock modes move the noise floor. Decides whether an absolute-SPL readout is defensible (section C) — grounds the dBFS→SPL labelling rule of ADR 0006 and the §4 absolute-SPL / AOP rows. |
| [05 #1](05-papers.md) | **Heinzel et al. (2002)** — spectrum estimation by the DFT | ★★★ | The correction that the mic's SNR bounds *wideband level* accuracy, not per-bin spectral dynamic range (processing gain ≈ 30 dB at N = 4096). Without it the admissibility argument is made against the wrong number — grounds the §4 EIN row and roadmap correction #1. |

## B. Placement, distance and directivity — the wrist-position envelope

Grounds the §4 wrist-position row (reported as an envelope, not pass/fail), the 3 distances × 3 arm angles × 2 sleeve factors of the (prov.) 108-trial matrix, and the ADR 0008 rule that ring/twang numbers are relative and within-session only.

| # | Item | Priority | Why |
|---|------|:--------:|-----|
| [05 #64](05-papers.md) | **Švec & Granqvist (2018)** — *Tutorial and guidelines on measurement of SPL in voice and speech*, JSLHR 61(3) | ★★★ | SPL vs distance, weighting, background noise and calibration for head/body-mounted microphones; "always report mouth-to-mic distance". The §4 wrist row and every SPL number in a take record ([`protocols/specs/`](../../protocols/specs/README.md)) must carry the distance estimate. |
| [05 #65](05-papers.md) | **Titze & Winholtz (1993)** — microphone type and placement vs perturbation measures, JSHR 36(6) | ★★★ | Degradation measured at 4 cm / 30 cm / 1 m × 0° / 45° / 90°. The wrist cell is in the table; cite it for the expected loss before measuring it — grounds the expected range of the §4 wrist-position-envelope row. |
| [05 #66](05-papers.md) | **Katz & d'Alessandro (2007)** — directivity of the singing voice, ICA 2007 | ★★ | HF directivity of the *singing* voice — the reason an off-axis wrist mic under-reads 2.5–5 kHz systematically; grounds the angle factor of the §4 matrix and the ADR 0008 relative-only rule. |
| [05 #67](05-papers.md) | **Pörschmann & Arend (2020)** — phoneme-dependent voice directivity, DAGA 2020 | ★★ | Directivity varies by phoneme → a vowel × angle interaction; keeps three angles (not one) in the §4 acoustic-path matrix. |
| S1 | **ISO 7250-1** (basic human body measurements) · **ANSUR II** public anthropometric tables · **DINED** database — home: [03](03-standards.md) | ★★ | The wrist-to-mouth distance *distribution* for a raised arm, replacing the made-up 15/30/45 cm levels with percentiles (5th/50th/95th) — the §4 distance factor becomes population-grounded. ANSUR II and DINED are free; ISO 7250-1 is paid and needed only for the measurement definitions. |
| [05 #36](05-papers.md) | **Nordenberg & Sundberg (2004)** — effect of vocal loudness on LTAS, LPV 29(4) | ★★★ | Up to 4 kHz, LTAS level tracks loudness strongly and non-uniformly — more than any between-singer difference; together with B's directivity papers it is why ADR 0008 forbids absolute ring/SPR comparisons across sessions or people, and why every §4 ring/SPR row carries an SPL estimate. |
| [05 #38](05-papers.md) | **Bloothooft & Plomp (1986)** — sound level of the singer's formant, JASA 79(6) | ★★ | Vowel (16 dB) and f0 (9–14 dB) outrank between-singer differences (4 dB) in singer's-formant level; grounds the vowel factor of the §4 acoustic-path matrix and the ADR 0008 within-session rule. |
| — | **Wind and motion noise from arm movement** — no source yet; listed as a gap | ★ | A wrist-worn mic moves with the gesture; there is no document on this in the list. Route to experiment 0001 as a measured condition (arm still vs conducting-style motion) and to §7. |

## C. Calibration chain — from a 94 dB calibrator to a number on the wrist

Grounds the §4 level rows (1/3-oct ±1.5 dB *as repeatability or with a GUM budget*, absolute SPL ±1.5 dB @ 1 kHz, EIN, AOP), the mic-EQ slot of ADR 0010, and the instrument list in the validation plan. The chain is: calibrator → reference microphone → playback geometry → in-situ transfer function → EQ filter → readout. Each link has a standard or a method paper; the UMIK-1-vs-Class-1 question decides whether the ±1.5 dB claim survives.

| # | Item | Priority | Why |
|---|------|:--------:|-----|
| S2 | **IEC 61672-1:2013** (sound level meters — Part 1: specifications) — home: [03](03-standards.md) #2 | ★★ | Normative A/C/Z weighting, Fast/Slow, class 1/2 tolerances — the definitions behind the §4 absolute-SPL row and the `spectral_core` weighting filters; lets A-weighting be implemented from the spec instead of from a GPL coefficient table ([06](06-reference-projects.md) #40). Paid; [03](03-standards.md) routes the free ANSI S1.11-2004 as the read-first alternative for bands. |
| [03 #3](03-standards.md) | **IEC 61672-2:2013** (pattern evaluation tests) · **IEC 61672-3:2013** (periodic tests) — one entry in 03 | ★ | Part 1 alone states tolerances; without Parts 2–3 the phrase "class-2 reference" in §4 is not a conformance claim (roadmap correction on the RQ wording). Needed only if the reference chain is ever described as *conformant* rather than as a class-2 instrument. |
| S3 | **IEC 61260-1:2014** (= ANSI/ASA S1.11-2014 Part 1) octave-band filters · **ANSI S1.11-2004** (superseded, freely readable) — home: [03](03-standards.md) | ★★ | The class 1/2 masks that turn "my 1/3-octave bank looks right" into a numeric pass/fail; the §4 1/3-oct row is measured against a compliant reference analysis. Buy only one of IEC/ANSI 2014 (identical); read the free 2004 text first. |
| S4 | **IEC 60942:2017** sound calibrators — home: [03](03-standards.md) | ★★ | Class LS/1/2 calibrator tolerances; ties the B&K 4231 (D3) to a Class-1 chain. A class-2 calibrator caps absolute SPL at ≈ ±2 dB, which is already outside the target. |
| S5 | **IEC 61094-4** working-standard microphones (WS2F/WS3) — home: [03](03-standards.md) | ★★ | Decides whether a UMIK-1-class or a GRAS/B&K-class reference is defensible for ±1.5 dB — the reference-mic class *is* a threshold that changes the plan. |
| D3 | **Brüel & Kjær Type 4231 sound calibrator** product data (94.0/114.0 dB @ 1 kHz, ±0.2 dB, IEC 60942 Class 1) — home: [01](01-datasheets.md) | ★★★ | The level reference for the §4 absolute-SPL row; needs a documented custom port adapter for the watch case (experiment 0001). |
| D4 | **miniDSP UMIK-1** (per-serial factory calibration file) · **Earthworks M23R** / GRAS 46AE class references — home: [01](01-datasheets.md) | ★★★ | The budget vs credible reference-mic options; the > 2 dB HF disagreement between them is the same order as the target — state which class was used in every table; grounds the reference-microphone line of the §4 equipment table and the reference-mic term of the GUM budget (section D). |
| S6 | **ITU-T P.58** (head and torso simulator) · **ITU-T P.51** (artificial mouth) — free — home: [03](03-standards.md) | ★★ | Makes corpus playback *repeatable in geometry* — the difference between "we played the corpus at the watch" and an experiment; the acoustic-path matrix assumes a P.51/P.58 mouth or a documented monitor substitute. |
| S7 | **ITU-T P.56** active speech level — free — home: [03](03-standards.md) | ★★ | The citable way to normalise corpus level on the injection path so injection and acoustic paths are compared at matched level — grounds the level-matching rule of the §4 two-path comparison and the `host/golden/` level-normalisation step. |
| S8 | **ITU-R BS.1770-5** loudness (LKFS) — free — home: [03](03-standards.md) | ★ | A defensible *relative* level readout for the `ui` when no calibrator is present — the project's likely field reality. |
| [05 #88](05-papers.md) | **Farina (2000)** — exponential swept sine | ★★★ | The in-situ transfer-function instrument of experiment 0001; separates linear response from harmonic distortion so the EQ fit and the AOP reading are not confounded. |
| [05 #92](05-papers.md) | **Välimäki & Reiss (2016)** — audio equalisation | ★★ | How the measured curve becomes the biquad cascade in the mic-EQ slot (`dsps_biquad_gen_*`). Open question routed from the roadmap: is the EQ a per-part-number constant or a per-unit calibration? Per-unit makes the ring/twang metric non-reproducible on a second watch. |
| A2 | **TDK/InvenSense AN-1003** *Recommendations for mounting and connecting MEMS microphones* · **AN-100** handling and assembly guide — home: [02](02-application-notes.md) | ★★★ | Port ≥ 0.25 mm, gasket sealing, front-cavity (Helmholtz) resonance — the physical model that predicts whether a resonance lands in 2.5–5 kHz; grounds the geometry section of experiment 0001 and the mic-EQ slot of ADR 0010 (section G). |

## D. Uncertainty, agreement and repeatability — how the numbers are reported

Grounds the statistics column of the §4 table (roadmap correction #8) and the reproducibility objective O5.

| # | Item | Priority | Why |
|---|------|:--------:|-----|
| S9 | **JCGM 100:2008 — Guide to the Expression of Uncertainty in Measurement (GUM)** + **JCGM 200 (VIM)** — free (BIPM) — home: [03](03-standards.md) | ★★★ | The missing methodological spine: every ±X target becomes a combined standard uncertainty with a budget (calibrator ±0.2 dB, reference mic class, geometry, temperature, clock ppm). Without it the ±1.5 dB claim is a wish. |
| [05 #86](05-papers.md) | **Bland & Altman (1986)** | ★★★ | Agreement against a reference → bias + limits of agreement, not Pearson's r (the "r ≥ 0.9" SPR target is exactly the error B&A was written to correct) — grounds the statistics column of the §4 table and the SPR/FHE agreement metric (ADR 0008). |
| [05 #87](05-papers.md) | **Koo & Li (2016)** — ICC selection | ★★ | Within-session / within-subject repeatability (the only mode in which ADR 0008 allows ring/SPR numbers) reported as the correct ICC form. |
| [05 #89](05-papers.md) | **Lakens (2017)** — TOST equivalence | ★ | Equivalence testing for the ±1.5 dB claims and the power analysis the (prov.) 108-trial matrix lacks. |
| — | **Sample-rate error** — no APLL on the S3: crystal ppm + fractional divider (roadmap correction #4) | ★★ | Not a document: a budget line for the §4 sample-rate-error row. ≤ 200 ppm is 1200 · log₂(1 + 200 × 10⁻⁶) ≈ 0.35 cent of pure additive bias on every cents number — negligible against the ±20 cents target, but *systematic*, so it is entered into the GUM budget as a Type B term rather than waved away; measured once against a GPSDO / ≤ 1 ppm counter ([01](01-datasheets.md) #36, validation equipment list) and carried as the clock-correction constant. |

## E. Protocol anchors — the field's "performance targets"

Grounds the §4 preamble and the validation README's threshold-provenance note ([07](07-technical-reports.md) #15). The research stated there was no EPA-equivalent anchor; for voice there are two, and they name microphone, distance, SPL and calibration requirements directly.

| # | Item | Priority | Why |
|---|------|:--------:|-----|
| [05 #31](05-papers.md) | **Patel et al. (2018)** — ASHA recommended protocols for instrumental assessment of voice | ★★★ | Names the recording distance, microphone class, calibration and analysis settings a voice measurement is expected to follow; the §4 protocol cites it rather than inventing one. |
| [05 #32](05-papers.md) | **Dejonckere et al. (2001)** — ELS basic protocol | ★★★ | The European counterpart; sustained-vowel, SPL and perturbation conventions. Both are cited as *measurement* protocols only — ADR 0005 forbids any clinical reading of the results. |
| R1 | **ASHA Practice Portal — Voice Disorders (assessment section)** snapshot — home: [07](07-technical-reports.md) #14 | ★ | Practitioner wording of the same protocol; useful for the §4 text. |
| [05 #46](05-papers.md) | **Ternström, Pabon & Södersten (2016)** — the Voice Range Profile | ★★ | The canonical singing measurement that *requires* the calibration chain of section C; it is the §7 future-work feature that would justify buying the calibrator. |

## F. Room, background noise and environment

Grounds the §4 EIN row ("requires a room below 25 dB(A) or you measure the room") and the availability-risk line in the equipment list.

| # | Item | Priority | Why |
|---|------|:--------:|-----|
| S10 | **ISO 26101-1** (qualification of free-field environments) and/or **ISO 3745 Annex A** · **ANSI/ASA S12.2** (room noise criteria) — home: [03](03-standards.md) | ★★ | Justifies the "≤ 25 dB(A) room" requirement instead of asserting it, and gives the vocabulary (NC/NCB curves) to *report the room actually used* when the requirement is not met — grounds the §4 EIN row's room requirement and the room-report line of experiment 0001. |
| → [10](10-datasets-and-ground-truth.md) | **Noise corpora (DEMAND, MUSAN, ESC-50, UrbanSound8K)** and **RIR databases (OpenAIR, BUT ReverbDB, MIT IR Survey, ACE)** | ★★ | The SNR and reverberation axes — a rehearsal room is not a free field. Indexed in the datasets file; cited here because they are the *controlled* substitute for a quiet room on the injection ⊛ RIR third path of §4. |

## G. The acoustic port, case and gasket — the largest hardware-documentation gap

Grounds [`hardware/acoustic-port/`](../../hardware/acoustic-port/README.md), experiment 0001's geometry section, and the roadmap's "mic not acoustically capable through the case → host-first pivot" threshold. The speaker is optional; the port bounds the headline measurement.

| # | Item | Priority | Why |
|---|------|:--------:|-----|
| → A2 | **TDK AN-1003 / AN-100** — cross-reference to A2 in section C (one entry, one number) | ★★★ | Port and cavity design rules; the Helmholtz model of the port channel makes the 2.5–5 kHz resonance question partly *calculable* before it is measured — grounds the geometry section of experiment 0001 and the port drawing under [`hardware/acoustic-port/`](../../hardware/acoustic-port/README.md). |
| A3 | **Infineon — PCB and housing design for MEMS microphones** application note — home: [02](02-application-notes.md) | ★★ | Housing-side rules (channel length, gasket compression, membrane placement) independent of the Knowles part — grounds the port drawing under [`hardware/acoustic-port/`](../../hardware/acoustic-port/README.md) and experiment 0001's geometry section. |
| A4 | **GORE acoustic-vent portfolio datasheet** + **GAW334** vent datasheet — home: [02](02-application-notes.md) | ★★ | If the case carries any vent membrane it is a 0.4–4 dB, frequency-dependent insertion loss — a first-order and currently untracked term in the EQ fit — grounds the mic-EQ slot of ADR 0010 and the vent line of the `hardware/acoustic-port/` drawing. |
| D5 | **LilyGO T-Watch S3 case drawing / STEP, or a teardown-measured port drawing** — home: [01](01-datasheets.md) (request to vendor; fallback: calipers + photo) | ★★★ | Hole diameter, channel length, cavity volume, gasket presence. No vendor file is known to exist; the fallback is a measured drawing committed under `hardware/acoustic-port/` with provenance. |
| [01](01-datasheets.md) | **T-Watch S3 schematic V1.4 / 2025-03-24** | ★★★ | Which AXP2101 rail powers the mic (and whether it is the 1.8 V `IOVDD1_8V` domain that GPIO47 sits in on R8V parts) — settles whether the mic is even powered in a given rail configuration (ADR 0016 adjacency). |

---

## What transfers from the voice-science lab to a wrist

| Dimension | Their work (voice-science protocols: Švec & Granqvist, ASHA, ELS) | Our project (Super Spectral on the T-Watch S3) | Transferable? |
|-----------|-------------------------------------------------------------------|------------------------------------------------|:-------------:|
| Microphone | Calibrated omni condenser, flat ±2 dB, head-mounted or on a stand | Single PDM MEMS (−22 dBFS, 61.5 dB(A)), obsolete part, behind a sealed case port | Criteria transfer; the device is tested *against* them, not assumed to meet them (A) |
| Geometry | Fixed 30 cm (or 4–10 cm head-mounted), on-axis, reported with every SPL | ≈ 30 cm at 45–90°, moving with the arm, sleeve-occluded at times | Distance rule transfers; angle/motion are new factors → envelope, not pass/fail (B) |
| Level reference | Class-1 calibrator + Class-1 chain, SPL in every table | Calibrator optional; likely UMIK-1 reference; absolute SPL ±1.5 dB is inside the reference's own uncertainty | Chain design transfers; the *claim* must be restated as repeatability or carry a GUM budget (C, D) |
| Analysis | Sustained vowels, LTAS, CPP, jitter/shimmer on a PC, clinician present | Live f0, spectrogram, FHE/SPR on-device; Praat-grade analysis offline on the host (ADR 0002) | The on-device subset is a *front end* to the same analyses; ADR 0005 forbids the clinical reading |
| Environment | Sound-treated room, background ≤ 25–30 dB(A) | Rehearsal rooms, practice corners, outdoors | Room qualification transfers as a *report the room* rule; the injection ⊛ RIR path (10) simulates what cannot be controlled |
| Statistics | Bland–Altman, ICC, reported uncertainty | Currently r and ±X point targets | Transfers directly; this is the cheapest fix in the whole plan (D) |

Bottom line: the voice-science community has already specified how to measure a voice with a microphone at 30 cm; the project's contribution is to **characterise how far a wrist-worn MEMS through a case falls from that specification and to report the residual honestly** — not to claim the specification is met.

## Minimum set to make the acoustic path defensible (~10 hours)

1. **Švec & Granqvist 2010 (05 #63)** — the admissibility criteria.
2. **Švec & Granqvist 2018 (05 #64)** — SPL from body-mounted mics, report the distance.
3. **Titze & Winholtz 1993 (05 #65)** — the 30 cm / 45–90° cell.
4. **Patel et al. 2018 (05 #31)** — the protocol anchor.
5. **JCGM 100 (S9)** — chapters 4–5 only: the budget skeleton.
6. **Bland & Altman 1986 (05 #86)** — how agreement is reported.
7. **Farina 2000 (05 #88)** + **TDK AN-1003 (A2)** — how experiment 0001 measures the case, and what geometry to expect.
8. **Knowles datasheet (D1)** — with the response curve *digitised*, not eyeballed.

## Filing

Acquired items go into the by-type reference library, same as 01–07:

- **Papers** (all `05 #` cross-references) → [`../papers/by-topic/microphone-placement-voice/`](../papers/README.md) (#63–#67), `metrology-statistics/` (#86–#89), `spectral-tilt-voice-quality/` (#31, #32), `singers-formant-ltas/` (#36, #38, #46), `embedded-audio-dsp/` (#92), `stft-windows-spectral-estimation/` (#1). Filename `<firstauthor><year>_<short-title>.pdf`.
- **Standards** S1–S10 → [`../standards/<body>/`](../standards/README.md): `iso/` (7250-1, 26101-1, 3745), `iec/` (61672-1, 61672-2/-3 via [03](03-standards.md) #3, 61260-1, 60942, 61094-4), `ansi-asa/` (S1.11-2004, S12.2), `itu-t/` (P.51, P.58, P.56), `itu-r/` (BS.1770-5), `bipm-jcgm/` (JCGM 100, 200). Pattern `<body>_<doc-id>_<short-title>_<version-or-year>.pdf`.
- **Datasheets** D1–D5 → [`../datasheets/<vendor>/<part>/`](../datasheets/README.md): `knowles/spm1423hm4h-b/`, `tdk-invensense/t3902/`, `instruments/bk-4231/`, `instruments/minidsp-umik-1/`, `lilygo/t-watch-s3/` (case drawing). Digitised curves as `<original>_response.csv` next to the PDF with a provenance header.
- **App notes** A1–A4 → [`../app-notes/<vendor>/`](../app-notes/README.md): `knowles/`, `tdk-invensense/`, `infineon/`, `gore/`.
- **Reports** R1 → [`../reports/asha-els/`](../reports/README.md).
- **Projects** (WebPlotDigitizer) → URL-only, [06](06-reference-projects.md) #38.

When a file lands, add the `📥 Filed locally: <relative path>` blockquote to the entry in its **home** file (01/02/03/05/07) and, until the local letters here are replaced by home addresses, to the row here as well.

## Acquisition links

> **📥 Filed locally (D3 pass, 2026-08-20)** — by home file: D1 Knowles SPM1423HM4H-B Rev A + Rev D, D3 B&K 4231 BP1311, D4 UMIK-1 product brief → [01 — Acquisition links](01-datasheets.md#acquisition-links) (#9, #30, #31); A1 Knowles selection guide R5, A4 GORE portfolio + GAW334 → [02](02-application-notes.md#acquisition-links) (#60, #65); S3's free half, ANSI S1.11-2004 → [03](03-standards.md#acquisition-links) (#1); Bland & Altman 1986 and Pörschmann & Arend 2020 → [05](05-papers.md#acquisition-links) (#86, #67). Paper links live in [05 — Acquisition links](05-papers.md#acquisition-links) under the numbers cross-referenced above; the table below covers only the local S/D/A/R entries.
> **Paid standards:** S2–S5, S10 (IEC/ISO/ANSI stores; none strictly required for a *relative* measurement tool — roadmap open question on the standards budget). **Free:** S6–S9 (ITU, BIPM), ANSI S1.11-2004 (law.resource.org), ANSUR II / DINED.

Access vocabulary (as in [README](README.md)): `free` · `free (GET)` · `paid` · `mirror` · `free, reg.` · `REPO` · `PORTAL`, plus `request` (vendor/author request; also used in [01](01-datasheets.md)). Several tokens joined by ` / ` mean several routes; qualifiers live in the Link cell, except **(CDN-BLOCK)**, which sits in the Access cell and means the host answered a scripted fetch with 403 or a bot challenge on 2026-08-21 and must be opened in a browser (legend in [`acquisition-status.md`](acquisition-status.md)).

| # | Access | Link |
|---|--------|------|
| S1 | paid (CDN-BLOCK) / free | ISO 7250-1 paid; ANSUR II and DINED free — [iso.org — ISO 7250-1](https://www.iso.org/standard/65246.html) (verify current edition) · ANSUR II: [openlab.psu.edu/ansur2](https://www.openlab.psu.edu/ansur2/) · DINED: [dined.io.tudelft.nl](https://dined.io.tudelft.nl/) |
| S2 | paid (CDN-BLOCK) | [webstore.iec.ch — IEC 61672-1:2013](https://webstore.iec.ch/en/publication/5708) · ANSI/ASA S1.4-2014 adoption: [webstore.ansi.org](https://webstore.ansi.org/) (free preview) · Parts 2/3: see [03](03-standards.md) #3 |
| S3 | free (GET) / paid (CDN-BLOCK) | ANSI S1.11-2004 (free, incorporated by reference): [law.resource.org — ansi.s1.11.2004.pdf](https://law.resource.org/pub/us/cfr/ibr/002/ansi.s1.11.2004.pdf) · IEC 61260-1:2014: [webstore.iec.ch](https://webstore.iec.ch/) · ANSI/ASA S1.11-2014 Part 1: [webstore.ansi.org](https://webstore.ansi.org/) |
| S4 | paid | [webstore.iec.ch — IEC 60942:2017](https://webstore.iec.ch/en/publication/30045) |
| S5 | paid | [webstore.iec.ch](https://webstore.iec.ch/) — search "IEC 61094-4" |
| S6 | free | [itu.int/rec/T-REC-P.58](https://www.itu.int/rec/T-REC-P.58) · [itu.int/rec/T-REC-P.51](https://www.itu.int/rec/T-REC-P.51) |
| S7 | free | [itu.int/rec/T-REC-P.56](https://www.itu.int/rec/T-REC-P.56) |
| S8 | free | [itu.int/rec/R-REC-BS.1770](https://www.itu.int/rec/R-REC-BS.1770) |
| S9 | free (GET) | [bipm.org — JCGM publications](https://www.bipm.org/en/committees/jc/jcgm/publications) (JCGM 100:2008, JCGM 200:2012) |
| S10 | paid (CDN-BLOCK) | [iso.org — ISO 26101-1](https://www.iso.org/standard/79355.html) (verify) · [ISO 3745](https://www.iso.org/standard/45362.html) (verify) · ANSI/ASA S12.2: [webstore.ansi.org](https://webstore.ansi.org/) |
| D1 | mirror | [Mouser mirror (Rev. D)](https://www.mouser.com/datasheet/2/218/SPM1423HM4H-B-876897.pdf) *(link replaced 2026-08-21: `knowles.com/docs/default-source/model-downloads/spm1423hm4h-b.pdf` is 404, the Knowles SiSonic sub-department page is 404, and the Wayback Machine has no snapshot of the vendor PDF — the part appears delisted)* · further mirrors in the LilyGoLib repo — verify which revision each serves |
| D2 | free | [invensense.tdk.com — T3902 product page](https://invensense.tdk.com/products/digital/t3902/) (datasheet under "Documentation") |
| D3 | free | [bksv.com — Type 4231](https://www.bksv.com/en/transducers/acoustic/calibrators/sound-calibrator-4231) (product data PDF under "Downloads") |
| D4 | free (GET) / free, reg. (CDN-BLOCK) | [minidsp.com — UMIK-1](https://www.minidsp.com/products/acoustic-measurement/umik-1) (403 to scripts — browser; per-serial cal file by serial number) · [earthworksaudio.com — M23R](https://earthworksaudio.com/measurement-microphones/m23r/) · [grasacoustics.com — 46AE](https://www.grasacoustics.com/products/measurement-microphone-sets/constant-current-power-ccp/product/140-46ae) *(link replaced 2026-08-21: GRAS renumbered the product id `143-46ae` → `140-46ae`; the old path is 404, and the host bot-blocks a bare `HEAD`)* |
| D5 | request | Vendor request via [LilyGO support](https://lilygo.cc/pages/contact) *(link replaced 2026-08-21: the slug lost its `-us`; `/pages/contact-us` is 404)* (no known public STEP); fallback: measured drawing committed under [`hardware/acoustic-port/`](../../hardware/acoustic-port/README.md) |
| A1 | free (GET) | [knowles.com — mic-selection-guide-r5.pdf](https://www.knowles.com/docs/default-source/default-document-library/mic-selection-guide-r5.pdf) |
| A2 | free (GET) | [TDK AN-1003](https://invensense.tdk.com/download-pdf/an-1003-recommendations-for-mounting-and-connecting-invensense-mems-microphones/) (resolves 200 on 2026-08-21, but now lands on a TDK **search-results page**, not the PDF) · [TDK AN-100 v1.3, Wayback copy (2022-11-08)](https://web.archive.org/web/20221108202016/https://invensense.tdk.com/wp-content/uploads/2016/03/AN-100-00-MEMS-Microphone-Handling-and-Assembly-Guide-v1.3.pdf) *(link replaced 2026-08-21: TDK's `en-us` redirect target for the live path is 404)* |
| A3 | PORTAL | [infineon.com — MEMS microphones documents](https://www.infineon.com/cms/en/product/sensor/mems-microphones/) (search "PCB and housing design") |
| A4 | free (GET) / mirror | [GORE acoustic vents portfolio datasheet](https://www.gore.com/sites/default/files/resources/pdf/2025-07/gore-acoustic-vents-portfolio-datasheet-en.pdf) · [GAW334 datasheet (GroupGets mirror)](https://groupgets-files.s3.amazonaws.com/AudioMoth/GORE-Acoustic-Vent-GAW334-Datasheet-en.pdf) |
| R1 | free | [asha.org — Voice Disorders practice portal](https://www.asha.org/practice-portal/clinical-topics/voice-disorders/) (browser) |

## Disclosure

Written 2026-08-20 from the research syntheses and the critics' review, not from the documents themselves. **Live-verified that day:** Švec & Granqvist 2010/2018, Titze & Winholtz 1993, Katz & d'Alessandro (HAL record), Pörschmann DAGA 2020 PDF, TDK AN-1003 and AN-100 URLs, both GORE datasheets, the free ANSI S1.11-2004 copy, the JCGM publications page. **Model-recalled:** the ISO store URLs for S1 and S10 (edition numbers flagged "verify"), the product-page URLs for D2–D4 (vendors move these), the Infineon document title (A3), and the claim that no public case STEP exists (D5 — a vendor request is the way to find out). The anthropometric percentiles, the ≈ 30 cm wrist distance and the 45–90° angle are *assumptions* this file asks the literature and experiment 0001 to replace, not facts it asserts. Nothing in this file has been filed or OCR'd yet.

**Link layer re-checked live on 2026-08-21** (HTTP status only — no PDF was downloaded, and no distance, angle, percentile, edition year or priority was changed). Resolving normally: S3's free ANSI S1.11-2004 copy at law.resource.org, S2/S4/S5's `webstore.iec.ch` pages (including both deep links), S1's ANSUR II and DINED links, S6–S8 (itu.int), S9 (bipm.org), D2 (the TDK T3902 product page, now redirecting to `www.invensense.tdk.com/en-us/products/microphone/t3902`), D3 (bksv.com), D4's Earthworks page, A1 (the Knowles selection guide — note this Knowles path still works even though D1's did not), A3 (infineon.com), A4 (both GORE datasheets), R1 (asha.org). **Dead links replaced, no claim touched:** D1 (Knowles vendor PDF 404 with no snapshot → the Mouser Rev. D mirror), D4's GRAS 46AE (product id renumbered `143-` → `140-`), D5 (LilyGO's contact slug lost its `-us`), A2's AN-100 v1.3 (TDK's live path 404s → a 2022-11-08 Wayback copy). **CDN-blocked** (403 to scripts — URLs left as-is, Access cells now say **(CDN-BLOCK)**): S1, S10 (iso.org), S2, S3, S10 (webstore.ansi.org), D4's minidsp page. **Observed but not acted on:** A2's AN-1003 link returns 200 yet now lands on a TDK search-results page instead of the PDF — the URL is kept because it is the vendor's own redirect, with the behaviour recorded in the row. Everything listed as model-recalled above stays model-recalled: the S1/S10 edition numbers (a 403 store page cannot confirm them), the Infineon document title, and the no-public-STEP claim — D5's link now reaches a working contact page, which is where that question gets answered, not evidence about the answer.
