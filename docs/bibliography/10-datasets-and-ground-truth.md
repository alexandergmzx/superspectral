# 10 — Datasets and ground truth (synthetic generators, corpora, noise, rooms, licences)

**Purpose.** The research question promises numbers — ±20 cents median, ≥ 90 % RPA @ 50 c, ≤ 5 cents vs Praat, ±1.5 dB per 1/3-octave — and every one of them is a comparison *against something*. The [research doc](../research/00-linux-analyzer-architecture-and-build-guide.md) names pYIN, CREPE and a few corpora loosely; nothing in the project yet says which signals, under which licence, with which provenance, will be the ground truth. This file is the acquisition list that fixes that. Five reasons the spine is missing:

1. **No synthetic tier.** The only ground truth that is exact *by construction* (sines on and off bin centres, sweeps, two-tone, glottal-source vowels with known F1–F3, AM/FM tones) was described in one sentence with no generator named and no method citation for the swept sine.
2. **No licence ledger.** Corpus licences range from CC BY 4.0 through CC BY-NC to "not stated" and "request from the lab"; a headline number computed on an NC or unlicensed corpus cannot appear in anything with commercial framing, and the plan did not separate them.
3. **No noise or room axis.** A wrist device is used in rehearsal rooms, yet the metric table had no background-noise or reverberation factor and no corpora to supply one.
4. **Only two measurement paths.** Injection and acoustic. A third — injection ⊛ room impulse response — isolates room effects from microphone effects cheaply, and the RIR databases for it were absent.
5. **Golden-file provenance is stated, not designed.** "Parselmouth ≡ Praat" holds only per bundled version (roadmap correction #6); the manifest that pins version → method → settings → sha256 did not exist.

This is a **thematic list** and the **home index for datasets**: datasets are numbered `1…n` here (there is no by-type dataset file; the library location is the repo-root [`datasets/`](../../datasets/README.md)). Papers are cross-referenced as `05 #n`; generator tools as `P`, signal standards as `S` (home: [03](03-standards.md)). Cite as `10 #5` or `10 P1`. Entry numbers are append-only.

**Downstream of this list:** §4 of the [proposal](../proposal/01-super-spectral-proposal.md) (corpus manifests, two-path rule, the optional third path), [`golden-files.md`](../validation/golden-files.md) and [ADR 0009](../adr/README.md) (golden-file strategy), [ADR 0005](../adr/README.md) (pathology corpora as acoustic material only), the `mirdata` manifests under [`datasets/`](../../datasets/README.md), and the three-ledger rule of ADR 0004 (corpus licences · software licences · golden-file provenance — never conflated).

## Priority key (same scale as the rest of the bibliography)

| Priority | Meaning |
|----------|---------|
| ★★★ | **Must-have / blocking.** The corresponding claim is indefensible without it. |
| ★★  | **Strongly recommended.** Materially strengthens the design or the evaluation. |
| ★    | **Useful background / breadth.** |

**Licence column legend:** CC BY 4.0 = clean for thesis, preprint and any framing · CC BY-SA = clean for research; derived *data* must be shared alike (does not touch firmware) · CC BY-NC = research only; **quarantine from headline metrics** if any commercial framing is contemplated · request/terms = verify before any derived number appears anywhere · not stated = bench-only.

---

## A. Tier 0 — synthetic signals with exact ground truth

Grounds the injection path of the §4 two-path rule (the only path where a "≤ 5 cents vs Praat" claim is legitimate), the peak-frequency and two-tone-resolution rows, the F1/F2 row (known-formant vowels), the vibrato row (AM/FM tones), and the golden-file tolerance tables of ADR 0009. **Must exist before any corpus is touched** — generated in-repo by a script under `python-scripts/`, seeded, with the generator version and parameters written into each WAV's sidecar.

| # | Item | Priority | Why |
|---|------|:--------:|-----|
| P1 | **In-repo generator** (to be written; `python-scripts/`, Apache-2.0): pure sines on/off bin centres · linear and log sweeps · two-tone at Δf = 0.5/1/2/4 bins · white and pink noise (assert flat / −3 dB per octave) · AM/FM tones at 5–7 Hz, ±1 semitone · clipping test tones for the AOP flag | ★★★ | Exact ground truth by construction; every §4 DSP row is first validated here. NumPy/SciPy only; no corpus licence involved. |
| P2 | **`pyworld`** (WORLD vocoder wrapper, MIT; [06](06-reference-projects.md) #35) | ★★ | Glottal source + known spectral envelope → synthetic vowels with exact f0 and F1–F3 for the formant row. Alternative: **Praat `Create KlattGrid`** through Parselmouth ([06](06-reference-projects.md) #31; GPL, host-side only) — a KlattGrid is the more "textbook" source-filter model (Rosenberg / Liljencrants–Fant pulse + formant filters). Grounds the §4 F1/F2 row's Tier-0 material and the formant golden files of ADR 0009. |
| [05 #88](05-papers.md) | **Farina (2000)** — exponential swept sine | ★★★ | The method citation for the sweep: the same signal measures the in-situ transfer function in experiment 0001 and separates distortion from the linear response. |
| S1 | **ITU-T P.501** test signals for telecommunication terminals — free — home: [03](03-standards.md) | ★ | Citable definitions of standard artificial and composite test signals; the CSS/artificial-voice signals are a neutral level-setting stimulus for the §4 acoustic path (level matching between paths; 08 section C). |
| S2 | **ISO 16:1975** (standard tuning frequency, A4 = 440 Hz) — home: [03](03-standards.md) | ★ | The unambiguous Hz ↔ cents ↔ note-name anchor for every f0 display and for the cents conversions in the validation scripts. |
| S3 | **EBU Tech 3253 — Sound Quality Assessment Material (SQAM)** — free — home: [03](03-standards.md) | ★★ | Studio-grade reference recordings including **sung material** (solo voice tracks), with known provenance — a bridge between Tier 0 synthetics and Tier 1 corpora for the acoustic path. |

## B. Tier 1 — clean licence with usable ground truth (the headline corpora)

Grounds the RQ's headline numbers and the §4 matrix. Everything in this tier is CC BY 4.0 (or equivalently permissive) so any derived number may appear anywhere. Loaders: `mirdata` ([06](06-reference-projects.md) #30) where one exists; otherwise a checksummed manifest under [`datasets/`](../../datasets/README.md).

| # | Dataset | Content / ground truth | Licence | Priority | Why |
|---|---------|------------------------|---------|:--------:|-----|
| 1 | **vocadito** — Zenodo [5578807](https://zenodo.org/records/5578807); paper [05 #58](05-papers.md) | 40 solo monophonic excerpts, 7 languages, mixed devices incl. phones; frame-level f0, two note-annotation versions, lyrics | CC BY 4.0 | ★★★ | The corpus the RQ's ±20 c / ≥ 90 % RPA is measured on. Phone-recorded takes are the closest existing analogue to a wrist MEMS. Its inter-annotator agreement is the floor on any cents claim (§4, §7). `mirdata` loader exists. |
| 2 | **Dagstuhl ChoirSet** — Zenodo [4608395](https://zenodo.org/records/4608395); paper [05 #60](05-papers.md) | Amateur ensemble, 55 min 30 s, choir + quartet; F0 per close-up mic, **larynx contact-microphone channel**, beats, aligned score | CC BY 4.0 | ★★★ | The closest thing to EGG ground truth without buying one — the §4 acoustic-path reference for f0. `mirdata` loader exists. |
| 3 | **VocalSet** — Zenodo [1193957](https://zenodo.org/records/1193957); paper [05 #57](05-papers.md) | 10.1 h, 20 professional singers, **17 vocal techniques**, all 5 vowels; no f0 ground truth in the base release | CC BY 4.0 | ★★ | The technique/timbre axis (O4; ADR 0008 ring/twang and FHE across techniques). Settle the 11 M / 9 F vs 11 F / 9 M discrepancy before it lands in a table. |
| 4 | **Annotated-VocalSet** — Zenodo [7061507](https://zenodo.org/records/7061507) | VocalSet + annotations (verify exactly which: f0 / notes / technique labels) | CC BY 4.0 | ★★ | Supplies the f0/technique labels #3 lacks, so VocalSet can serve the §4 RPA rows across techniques (O4) and not only the timbre readouts; verify the annotation type and method before it is admitted as f0 ground truth in the corpus manifest. |
| 5 | **Choral Singing Dataset** (Cuesta, Gómez, Martorell & Loáiciga, 2018) — Zenodo DOI 10.5281/zenodo.1286570 | 16 singers of the Anton Bruckner Choir (Barcelona), 3 a-cappella pieces, individual close-mic tracks + synchronised MIDI per section | CC BY 4.0 | ★★ | Per-singer tracks with score-level reference: a second acoustic-path corpus with a different room for the §4 matrix's room factor, and the material for the §7 ensemble/unison-intonation future-work item. |
| 6 | **SingStyle111** (Dai, Wu, Chen, Huang & Dannenberg, ISMIR 2023) — Zenodo [10265401](https://zenodo.org/records/10265401) · [shuqid.net/singstyle111](https://shuqid.net/singstyle111) | 111 songs, 8 professional singers, 12.8 h, English/Chinese/Italian; styles (bel canto, folk, pop, jazz, children); lyrics, performance MIDI, phoneme alignment, extracted F0 and loudness | CC BY 4.0 | ★★ | Style axis complementary to #3's technique axis; studio-quality stems for the timbre readouts. Its *extracted* F0 is a tool output, not ground truth — record which tracker produced it before using it as reference. Grounds the style factor of the O4 trade-off study and the ADR 0008 ring/twang readouts across styles. |
| 7 | **Hillenbrand et al. (1995) vowel database** — [homepages.wmich.edu/~hillenbr/voweldata.html](https://homepages.wmich.edu/~hillenbr/voweldata.html); paper [05 #18](05-papers.md) | 12 American English vowels × 139 talkers (men, women, children); WAVs + **measured F1–F4 and f0** per token | free for research (site terms — record them) | ★★★ | The only free corpus with *measured* formant ground truth → the golden-file material for the §4 F1/F2 row (ADR 0009). |
| 8 | **CSTR VCTK Corpus 0.92** — [datashare.ed.ac.uk, DOI 10.7488/ds/2645](https://doi.org/10.7488/ds/2645) | 110 English speakers, ≈ 400 sentences each, 48 kHz, two mic channels | CC BY 4.0 | ★ | Speech (not singing) reference for formant regression where singing corpora lack ground truth; its two simultaneous microphones are a ready-made "on-axis vs off-axis" comparison for the §4 F1/F2 row and the wrist-position envelope (08 section B). |
| 9 | **CMU ARCTIC** — [festvox.org/cmu_arctic](http://www.festvox.org/cmu_arctic/) | ≈ 1150 phonetically balanced utterances per speaker; several speakers recorded **with simultaneous EGG** | free (BSD-style festvox licence — record it) | ★★ | Speech with EGG-derived f0 — a clean-licence EGG reference for the §4 f0 rows (RPA, VR/VFA) when PTDB-TUG's terms (#10) are not settled. |

## C. Tier 2 — usable but restricted, non-commercial, or unstated licence

Grounds the §4 secondary comparisons and the §7 limitation on corpus availability. Numbers from this tier are reported in a clearly separated table and **never** as the headline.

| # | Dataset | Ground truth | Licence | Priority | Why |
|---|---------|--------------|---------|:--------:|-----|
| 10 | **PTDB-TUG** (Pirker et al. 2011; [05 #56](05-papers.md)) — [spsc.tugraz.at — PTDB-TUG](https://www.spsc.tugraz.at/databases-and-tools/ptdb-tug-pitch-tracking-database-from-graz-university-of-technology.html) | 4 720 recordings, 20 speakers; reference f0 from **simultaneous laryngograph** via RAPT | TU Graz terms — verify before publishing | ★★ | The most physiologically grounded f0 ground truth available — the laryngograph reference for the §4 RPA @ 10 c and VR/VFA rows on the injection path; speech, not singing (stated in §7). |
| 11 | **MDB-stem-synth** (Salamon et al. 2017; [05 #59](05-papers.md)) — [zenodo.org/records/1481172](https://zenodo.org/records/1481172) (verify record) | 230 stems, 15.56 h; "perfect" f0 by analysis/resynthesis | **CC BY-NC 4.0** | ★★ | The CREPE benchmark set — needed to state the RPA @ 10 c gap to the published ceiling ([05 #11](05-papers.md)). NC: quarantine from headline metrics; its resynthesis artefacts are documented in #59. `mirdata` loader exists. |
| 12 | **MIR-1K** (Hsu & Jang 2010; [05 #62](05-papers.md)) — [mirlab.org — MIR-1K](http://mirlab.org/dataset/public/) | 1 000 clips, manual semitone contours, unvoiced-frame typing, lyrics; voice and accompaniment on separate channels | **not stated** on the download page | ★ | Bench-only until the terms are resolved; the separate-channel layout is handy for the §4 background-noise factor (voice + known accompaniment at set SNR). `mirdata` loader exists. |
| 13 | **iKala** — Academia Sinica (request) | Human-annotated f0; separated channels | request / restricted | ★ | Only if #1/#2 prove insufficient; the request process is itself a §7 limitation to mention. |
| 14 | **Opencpop · ACE-KiSing · M4Singer · OpenSinger** (Mandarin singing-synthesis corpora) | Phoneme / note / syllable timing | **CC BY-NC 4.0** | ★ | Style and language breadth for the §7 generalisability discussion; NC → research tables only (ledger G). |
| 15 | **Erkomaishvili dataset** (AudioLabs Erlangen) — [audiolabs-erlangen.de resources](https://www.audiolabs-erlangen.de/resources/MIR/2017-GeorgianMusic-Erkomaishvili) | F0 + onsets per voice (CSV), sheet music; historic three-voice Georgian chant | AudioLabs terms | ★ | Polyphonic-voice f0 references for the §7 ensemble use-case item; not on the headline path. |
| 16 | **NUS-48E** — request from SMC, NUS | Phone-level durations (25 474), sung **and spoken** lyrics by the same speakers | not published — request | ★ | Sung-vs-spoken pairs for the SPR honesty check ([05 #42](05-papers.md)) in the host compare mode (ADR 0002, ADR 0008). |
| 17 | **Saraga (Carnatic/Hindustani)** — [mtg.github.io/saraga](https://mtg.github.io/saraga/) | Predominant F0, tonic, sections, phrases | CompMusic terms (mixed CC) | ★ | Non-Western vocal styles; breadth for §7. `mirdata` loader exists. |

## D. Tier 3 — voice-quality and pathology corpora (acoustic material only)

Grounds the LTAS / H1–H2 / CPP axis of the host compare mode (ADR 0002) and **ADR 0005**: Super Spectral makes no clinical claim; these corpora are used only as acoustic material with perceptual ratings, never to state anything about a user's health (MDR Rule 11 / MDCG 2019-11 / FDA General Wellness — [03](03-standards.md)).

| # | Dataset | Content | Licence | Priority | Why |
|---|---------|---------|---------|:--------:|-----|
| 18 | **PVQD — Perceptual Voice Qualities Database** — [data.mendeley.com/datasets/9dz247gnyb/4](https://data.mendeley.com/datasets/9dz247gnyb/4) | 296 WAVs, CAPE-V sustained vowels + sentences, expert perceptual ratings | CC BY 4.0 | ★★ | Perceptually rated material to check that CPP/H1–H2/tilt readouts order voices the way listeners do — a *validity* check of the host measures (ADR 0002 compare mode), not a diagnostic use (ADR 0005). |
| 19 | **Saarbrücken Voice Database** — [stimmdb.coli.uni-saarland.de](https://stimmdb.coli.uni-saarland.de/) | > 2 000 speakers (687 healthy, 1 356 patients, 71 pathologies), **audio + EGG** | site terms — verify | ★ | EGG-paired vowels at several pitches for the pitch estimators and the H1–H2 definitions; the pathology labels are *not* used (ADR 0005). |

## E. Noise corpora — the SNR axis

Grounds a background-noise factor the §4 matrix currently lacks, the EIN row ("or you measure the room"), and section F of [08](08-voice-metrology-on-the-wrist.md). Used on the injection path (voice + noise at controlled SNR) and, optionally, replayed in the room on the acoustic path.

| # | Dataset | Content | Licence | Priority | Why |
|---|---------|---------|---------|:--------:|-----|
| 20 | **DEMAND** (Thiemann, Ito & Vincent 2013) — [zenodo.org/records/1227121](https://zenodo.org/records/1227121) · paper [hal-00796707](https://hal.science/hal-00796707) | 18 environments × 16 channels, 5 min each (domestic, office, public, transport, street, nature) | **CC BY-SA 3.0** (per the database notes — verify on the record) | ★★★ | The controlled noise beds for SNR sweeps; the multichannel recordings let one pick a realistic rehearsal-room-like scene. SA applies to derived *recordings*, not to firmware. |
| 21 | **MUSAN** (Snyder, Chen & Povey 2015) — [openslr.org/17](https://www.openslr.org/17/) · [arXiv:1510.08484](https://arxiv.org/abs/1510.08484) | Music, speech and noise partitions (≈ 109 h) | CC BY 4.0 | ★★ | Speech-and-music interference (accompaniment, other singers) — the case DEMAND does not cover; the second noise class of the §4 background-noise factor. |
| 22 | **ESC-50** (Piczak 2015) — [github.com/karolpiczak/ESC-50](https://github.com/karolpiczak/ESC-50) | 2 000 five-second environmental clips, 50 classes | **CC BY-NC 3.0** | ★ | Transient/event noise (doors, coughs, traffic) for the §4 voicing-detection rows (VR/VFA). NC → research tables only (ledger G). |
| 23 | **UrbanSound8K** (Salamon, Jacoby & Bello 2014) — [urbansounddataset.weebly.com](https://urbansounddataset.weebly.com/urbansound8k.html) · [zenodo.org/records/1203745](https://zenodo.org/records/1203745) | 8 732 urban clips, 10 classes | **CC BY-NC 4.0** (verify version) | ★ | Outdoor practice scenario for the §4 background-noise factor; NC → research tables only (ledger G). |

## F. Room impulse responses — the third measurement path

Grounds the optional *injection ⊛ RIR* path of §4: corpus WAV convolved with a measured room response, injected digitally. It isolates room effects from microphone effects at zero hardware cost, and it is what makes the acoustic-path results *interpretable* when the test room is not a free field (08 section F).

| # | Dataset | Content | Licence | Priority | Why |
|---|---------|---------|---------|:--------:|-----|
| 24 | **OpenAIR** (University of York) — [openairlib.net](https://www.openairlib.net/) | Measured RIRs of concert halls, churches, studios, small rooms; B-format and stereo | CC BY 4.0 (per-entry — verify each) | ★★★ | The widest free RIR library; includes small practice-room-class spaces. Pick three (dry room, rehearsal room, church) and pin their entry IDs in the manifest — the room levels of the §4 injection ⊛ RIR path. |
| 25 | **BUT ReverbDB** (Szöke et al. 2019) — [speech.fit.vutbr.cz — BUT ReverbDB](https://speech.fit.vutbr.cz/software/but-speech-fit-reverb-database) | Real RIRs + background noise from several rooms, many mic positions | CC BY 4.0 | ★★ | Room + noise recorded *together*, with position metadata — the closest to "a singer in a rehearsal room with the watch at 30 cm" — the §4 injection ⊛ RIR path's realistic-room level. |
| 26 | **MIT Acoustical Reverberation Scene Statistics Survey** (Traer & McDermott 2016) — [mcdermottlab.mit.edu/Reverb/IR_Survey.html](https://mcdermottlab.mit.edu/Reverb/IR_Survey.html) | 271 everyday-space IRs (kitchens, offices, streets, cars) | free for research (site terms — record them) | ★★ | *Everyday* spaces, which is where a wrist device lives; the distribution of RT60s to sample from for the §4 injection ⊛ RIR path and the §7 field-conditions statement. |
| 27 | **ACE Challenge corpus** (Eaton, Gaubitch, Moore & Naylor 2016) — [acecorpus.ee.ic.ac.uk](http://www.ee.ic.ac.uk/naylor/ACEweb/) | RIRs + noise for several mic configurations; ground-truth T60 and DRR | free, registration (verify terms) | ★ | Ground-truth T60/DRR lets the §4 room factor be reported as a number, not a label. |

---

## G. Licence ledger (the corpus ledger of ADR 0004's three-ledger rule)

Keep this table separate from the software-licence table in [06](06-reference-projects.md) and from the golden-file provenance manifest; never merge them.

| Class | Entries | Terms | Consequence for the project |
|---|---|---|---|
| Synthetic, in-repo | P1, P2 outputs | Apache-2.0 (generated) | Unrestricted; the only tier that can ship in CI fixtures. |
| CC BY 4.0 | #1, #2, #3, #4, #5, #6, #8, #18, #21, #24, #25 | attribution | Clean for thesis, preprint, any framing; attribution lines go into the datasets README and the paper. |
| CC BY-SA | #20 | attribution + share-alike on derived *data* | Clean for research; any redistributed derived recording is CC BY-SA. Never bundled into firmware or CI fixtures. |
| CC BY-NC | #11, #14, #22, #23 | non-commercial | Research tables only; **quarantined from headline metrics** if any commercial framing is contemplated. |
| Site / institutional terms | #7, #9, #10, #15, #17, #19, #26, #27 | varies | Record the terms verbatim in the dataset manifest; verify before a derived number appears in an application or paper. |
| Request-only | #13, #16 | per request | §7 limitation; do not plan the headline around them. |
| Not stated | #12 | all rights reserved by default | Bench-only until resolved. |
| Standards (S1–S3) | ITU-T P.501, ISO 16, EBU SQAM | free (P.501, SQAM) / paid (ISO 16) | Test signals, not corpora; SQAM recordings are free for research use under EBU terms. |

## H. Golden-file provenance (the third ledger)

Grounds ADR 0009 and [`golden-files.md`](../validation/golden-files.md). Not a document to acquire — a manifest to design. Every golden output is keyed by: input WAV sha256 → generator/corpus entry (this file's number) → parselmouth version → **bundled Praat version** → pitch method (`raw` / `filtered` autocorrelation) → floor/ceiling → silence and voicing thresholds → octave-jump cost → output array sha256 → tolerance per metric. Known golden-file killers to record explicitly: periodic vs symmetric windows (`fftbins=True` vs `sym=True`), FFT normalisation convention, dBFS reference (full-scale sine vs square = 3 dB), mel-filterbank norm (`slaney` vs `htk`, librosa 0.8→0.10), float32 vs float64 accumulation, `-ffast-math`/FMA contraction on Xtensa vs x86 libm. Bit-exactness is not achievable; the artifact is a **tolerance table per metric** ([05 #55](05-papers.md); [06](06-reference-projects.md) #31, #36).

---

## What transfers from MIR evaluation practice to this project

| Dimension | Their work (MIREX / mir_eval / CREPE-style evaluation) | Our project (Super Spectral) | Transferable? |
|-----------|---------------------------------------------------------|------------------------------|:-------------:|
| Input | Clean digital audio files, 44.1/16 kHz | Same files injected digitally **and** replayed acoustically into a wrist MEMS through a case | Metrics transfer; the two-path rule is new and must be reported in every table |
| Ground truth | Annotated or resynthesised f0, usually CC BY-NC | Tier 1 CC BY 4.0 first (vocadito, Dagstuhl), NC quarantined | Loader/checksum discipline (`mirdata`) transfers; the licence split is stricter than the field's habit |
| Metrics | RPA/RCA/OA/VR/VFA at 50 cents | Same, plus 25 c and 10 c tiers, plus median \|Δcents\| vs Praat, plus level and timbre agreement | `mir_eval` transfers verbatim; the Praat-relative and Bland–Altman rows are added |
| Reference implementation | A published model (CREPE, pYIN) run on a GPU/PC | A C99 core on an MCU, regressed against Praat goldens | The *gap* to the published ceiling is the reportable quantity, not a pass/fail |
| Noise / room | Rarely varied | SNR and RIR axes (E, F) on the injection path | The controlled-degradation methodology of speech research transfers; MIR practice has little of it |
| Provenance | Dataset version sometimes stated | Three ledgers: corpus licence, software licence, golden-file manifest with sha256 everywhere | Stricter than the field; this is the O5 contribution |

Bottom line: the MIR community supplies the metrics and the corpora; the project adds the acoustic path, the licence discipline, and the provenance manifest — and reports its numbers as a *distance from* the published ceilings rather than as new records.

## Minimum set to make the ground truth defensible (~8 hours, mostly scripting)

1. **Write P1** (the synthetic generator) and run every §4 DSP row against it — before touching a corpus.
2. **Download #1 vocadito and #2 Dagstuhl ChoirSet via `mirdata`**, validate checksums, write the manifest.
3. **Read [05 #58](05-papers.md) (vocadito) and [05 #60](05-papers.md) (Dagstuhl)** for the annotation protocols — they set the floor on the cents claim.
4. **Read [05 #55](05-papers.md) (Parselmouth)** and design the golden-file manifest (H) before generating a single golden file.
5. **Pick three OpenAIR RIRs (#24) and one DEMAND scene (#20)** and pin their IDs — the third path costs an afternoon.
6. **Record the licence of every entry actually used** in the ledger (G) — one line each, verbatim terms.

## Filing

Datasets are **not** filed under `docs/`: they live under the repo-root [`datasets/`](../../datasets/README.md) (raw audio gitignored; tracked: `mirdata` index files or a `manifest.tsv` with URL, version, sha256, licence, terms verbatim, date). Papers (`05 #` cross-references) file under [`../papers/by-topic/mir-evaluation-datasets/`](../papers/README.md) and `formant-lpc/` (#18). Standards S1–S3 → [`../standards/`](../standards/README.md): `itu-t/` (P.501), `iso/` (ISO 16), `ebu/` (Tech 3253). Generator tools P1–P2 → code under `python-scripts/` (P1) and URL-only in [06](06-reference-projects.md) (P2). Golden files → [`host/golden/`](../../host/golden/README.md) outputs, with the manifest tracked and the arrays reproducible from it.

When a dataset is downloaded, add `📥 Downloaded: datasets/<name>/ (manifest sha256 …)` to its row here; datasets are tagged `REPO` in [`acquisition-status.md`](acquisition-status.md).

## Acquisition links

> **📥 Downloaded:** nothing yet (roadmap D3 / validation phase). Paper links are in [05 — Acquisition links](05-papers.md#acquisition-links).
> **Registration or request:** #10 (TU Graz form), #13 (Academia Sinica), #16 (NUS), #27 (ACE registration). **NC:** #11, #14, #22, #23. **Unstated:** #12.

Access vocabulary (as in [README](README.md)): `free` · `free (GET)` · `free, reg.` · `paid` · `REPO`, plus `request` (corpus released on request; also used in [01](01-datasheets.md)) and `n/a` (generated in-repo). Licence qualifiers (NC, unstated, verify terms) are **not** access states — they live in the Link cell and in the licence ledger (section G).

| # | Access | Link |
|---|--------|------|
| P1 | n/a | written in-repo (`python-scripts/`) |
| P2 | REPO | [github.com/JeremyCCHsu/Python-Wrapper-for-World-Vocoder](https://github.com/JeremyCCHsu/Python-Wrapper-for-World-Vocoder) · Praat KlattGrid via [Parselmouth](https://github.com/YannickJadoul/Parselmouth) |
| S1 | free | [itu.int/rec/T-REC-P.501](https://www.itu.int/rec/T-REC-P.501) |
| S2 | paid | [iso.org — ISO 16:1975](https://www.iso.org/standard/3601.html) |
| S3 | free (GET) | [tech.ebu.ch/publications/sqamcd](https://tech.ebu.ch/publications/sqamcd) |
| 1 | free (GET) | [zenodo.org/records/5578807](https://zenodo.org/records/5578807) · `mirdata.initialize("vocadito")` |
| 2 | free (GET) | [zenodo.org/records/4608395](https://zenodo.org/records/4608395) · `mirdata.initialize("dagstuhl_choirset")` |
| 3 | free (GET) | [zenodo.org/records/1193957](https://zenodo.org/records/1193957) · `mirdata.initialize("vocalset")` (verify loader name) |
| 4 | free (GET) | [zenodo.org/records/7061507](https://zenodo.org/records/7061507) |
| 5 | free (GET) | [zenodo.org/records/1286570](https://zenodo.org/records/1286570) (DOI 10.5281/zenodo.1286570) |
| 6 | free (GET) | [zenodo.org/records/10265401](https://zenodo.org/records/10265401) · [shuqid.net/singstyle111](https://shuqid.net/singstyle111) · paper [ISMIR 2023 #91](https://archives.ismir.net/ismir2023/paper/000091.pdf) |
| 7 | free (GET) | [homepages.wmich.edu/~hillenbr/voweldata.html](https://homepages.wmich.edu/~hillenbr/voweldata.html) |
| 8 | free (GET) | [doi.org/10.7488/ds/2645](https://doi.org/10.7488/ds/2645) (Edinburgh DataShare) |
| 9 | free (GET) | [festvox.org/cmu_arctic](http://www.festvox.org/cmu_arctic/) (per-speaker tarballs; EGG in the `_egg` sets — verify availability) |
| 10 | free, reg. | (verify terms) [TU Graz SPSC — PTDB-TUG](https://www.spsc.tugraz.at/databases-and-tools/ptdb-tug-pitch-tracking-database-from-graz-university-of-technology.html) |
| 11 | free (GET) | (CC BY-NC — research tables only) [zenodo.org/records/1481172](https://zenodo.org/records/1481172) (verify record) · `mirdata.initialize("medleydb_pitch")` / `"mdb_stem_synth"` (verify loader) |
| 12 | free | (licence terms unstated — bench-only, ledger G) [mirlab.org/dataset/public](http://mirlab.org/dataset/public/) · `mirdata.initialize("mir1k")` |
| 13 | request | Academia Sinica — request via the iKala dataset page (search "iKala dataset request") |
| 14 | free, reg. | (CC BY-NC — research tables only) Opencpop: [wenet.org.cn/opencpop](https://wenet.org.cn/opencpop/) · ACE-KiSing, M4Singer, OpenSinger: project GitHub pages (search by name) |
| 15 | free | [audiolabs-erlangen.de — Erkomaishvili](https://www.audiolabs-erlangen.de/resources/MIR/2017-GeorgianMusic-Erkomaishvili) |
| 16 | request | SMC Lab, National University of Singapore — request |
| 17 | free (GET) | [mtg.github.io/saraga](https://mtg.github.io/saraga/) · `mirdata.initialize("saraga_carnatic")` |
| 18 | free (GET) | [data.mendeley.com/datasets/9dz247gnyb/4](https://data.mendeley.com/datasets/9dz247gnyb/4) |
| 19 | free, reg. | (verify terms) [stimmdb.coli.uni-saarland.de](https://stimmdb.coli.uni-saarland.de/) |
| 20 | free (GET) | [zenodo.org/records/1227121](https://zenodo.org/records/1227121) |
| 21 | free (GET) | [openslr.org/17](https://www.openslr.org/17/) |
| 22 | free (GET) | (CC BY-NC — research tables only) [github.com/karolpiczak/ESC-50](https://github.com/karolpiczak/ESC-50) |
| 23 | free, reg. | (CC BY-NC — research tables only) [zenodo.org/records/1203745](https://zenodo.org/records/1203745) |
| 24 | free | [openairlib.net](https://www.openairlib.net/) (per-entry download; record the entry ID and its licence line) |
| 25 | free (GET) | [speech.fit.vutbr.cz — BUT ReverbDB](https://speech.fit.vutbr.cz/software/but-speech-fit-reverb-database) |
| 26 | free | [mcdermottlab.mit.edu/Reverb/IR_Survey.html](https://mcdermottlab.mit.edu/Reverb/IR_Survey.html) |
| 27 | free, reg. | [ACE Challenge corpus](http://www.ee.ic.ac.uk/naylor/ACEweb/) |

## Disclosure

Written 2026-08-20. **Live-verified that day:** #5 (title, authors, DOI 10.5281/zenodo.1286570, CC BY 4.0, content), #6 (Zenodo record, CC BY 4.0, content summary), #20 (CC BY-SA licence — the critics' note said "CC BY"; the record says Attribution-ShareAlike 3.0, so SA is recorded here and the derived-data consequence is stated), the Zenodo records for #1–#4 (from the domain research), #18 (Mendeley record and CC BY 4.0). **Model-recalled:** the URLs and record numbers for #8–#12, #15, #17, #19, #21–#27 and the loader names quoted for `mirdata` (verify each against the current `mirdata` index); the NC version numbers for #22/#23; the EGG availability of #9; the per-entry licensing of #24. **Flagged in the rows:** #4's annotation type, #11's Zenodo record, #10/#19/#26/#27 terms. Nothing has been downloaded; the licence ledger describes what the project will do, not what it has done.
