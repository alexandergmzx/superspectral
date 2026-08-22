# Datasets

Audio material and ground truth for the validation plan. **Corpus payload is git-ignored, manifests are tracked** (`datasets/corpora/**` with `*.yaml` / `*.yml` / `*.md` / `LICENCE*` re-included, plus `datasets/raw/` and `datasets/**/*.wav` — see [`.gitignore`](../.gitignore)): corpora carry their own licences and Tier-0 signals are regenerated. (Corrected 2026-08-21: the ignore rule used to name the *directory* `datasets/corpora/`, which silently ignored the manifest inside it too; it now ignores the payload only, and this sentence and the table row below were brought into line.) What is tracked is the **manifest** that describes each dataset, the generators, and the licence ledger.

| Subdirectory | Tier | Description |
|--------------|------|-------------|
| [`tier0-synthetic/`](tier0-synthetic/) *(manifest tracked, WAVs regenerated)* | 0 | Generated in-repo by [`../python-scripts/synth_signals/`](../python-scripts/synth_signals/) — 21 files, 3.0 s, 32 kHz plus two 48 kHz host-only twins; ground truth exact by construction, recorded per file in [`tier0-synthetic/manifest.yaml`](tier0-synthetic/manifest.yaml) with the sha256 of each WAV. `python -m synth_signals check` regenerates and fails on drift |
| `corpora/` *(payload gitignored, manifest tracked)* | 1–3, N | Fetched by manifest (mirdata where available): singing corpora with f0 ground truth, technique/timbre corpora, voice-quality corpora, noise and RIR corpora |
| `takes/` *(planned)* | — | Takes recorded by the watch and imported through the take-transfer procedure ([`../protocols/specs/`](../protocols/specs/)); raw audio gitignored, manifests tracked |
| `reference/` *(planned)* | — | Reference-mic captures aligned with takes on the acoustic path; calibrator recordings |

Currently on disk: [`corpora/manifest.yaml`](corpora/manifest.yaml) — the Tier-1/2/3
corpora **pre-registered** (vocadito, Dagstuhl ChoirSet, VocalSet, PVQD, the Saarbrücken
Voice Database, MDB-stem-synth, DEMAND) with their licences, intended validation rows and quarantine consequences, and
empty `files:` blocks. Nothing is downloaded yet: the checksums are what the fetch adds,
and a manifest whose `files:` list is empty is honest about that.

## `manifest.yaml` — the contract

Every dataset carries a `manifest.yaml`; any analysis reads configuration from it and never hardcodes.

**Shape is unsettled `(prov.)`, 2026-08-21.** Three places describe it and they do not agree. What is on disk is *one aggregate* manifest — [`corpora/manifest.yaml`](corpora/manifest.yaml), holding all seven pre-registered corpora as entries of a `datasets:` list. The D6 output line of the [roadmap](../docs/roadmap/documentation-roadmap.md) names the *per-corpus* form, `datasets/<corpus>/manifest.yaml`, and so does the layout block at the end of this file. No per-dataset directory exists. Picking one shape — and editing all three places in the same commit — is a D6 item; **owner: Alexander**. Nothing depends on the choice yet because nothing is downloaded. Required fields, either shape:

| Field | Meaning |
|---|---|
| `name`, `tier`, `version` | identity; `version` is the upstream release (Zenodo record version) or the generator's git describe |
| `source` | upstream URL / DOI / Zenodo record, or the generator script path + parameters |
| `licence` | SPDX identifier or the literal terms (`CC-BY-4.0`, `CC-BY-NC-4.0`, `request-only`, `unstated`), plus the URL where the terms were read and the date |
| `ground_truth` | what exists (frame-level f0, note annotations, EGG/laryngograph-derived f0, formants, perceptual ratings) and its format |
| `files[]` | per file: relative path, `sha256`, sample rate, channels, bit depth, duration; for corpora, the subset actually used |
| `preprocessing` | resampling to the watch's rate, level normalisation (ITU-T P.56 active speech level for injection), channel selection — recorded so the injection path is reproducible |
| `use` | which validation rows and which measurement path (injection / acoustic / injection⊛RIR) this dataset serves |
| `restrictions` | NC / request-only / unstated flags and the consequence (quarantined from headline metrics, bench-only) |
| `clinical_claim` | always the quoted string `"no"`. Not a licence field: it records that the corpus's **audio** is acoustic material while its **labels are never used as targets**, and that no sensitivity, specificity, ROC or AUC against those labels is computed or published ([ADR 0005](../docs/adr/0005-no-clinical-claim.md) rule 4). No other value is permitted; a corpus that cannot carry it does not enter the manifest. |

A take's manifest additionally records the preset id + sha256, firmware `app_elf_sha256`, device id, RTC time, mic-EQ id, and the reference-mic capture it pairs with.

## Tier 0 — synthetic (must exist before any corpus is touched)

Generated, deterministic, checked into [`tier0-synthetic/manifest.yaml`](tier0-synthetic/manifest.yaml) with parameters and sha256; the audio is regenerated, not stored. *(Written 2026-08-21 as unit B-U2; the manifest is the first per-dataset `manifest.yaml` on disk — `datasets/<dataset-id>/manifest.yaml`, the per-dataset shape — while the corpora still share the aggregate file, so the shape note above stays open.)* What exists versus this table: every row below has at least one file; the vowel rows use the in-repo Rosenberg → Klatt cascade rather than `pyworld` or a KlattGrid, and the manifest records **two** formant truths per file — the resonator poles (what Burg/LPC estimates: exactly F) and the |H| peak of each resonator alone (what a peak picker finds: 3.0 Hz below F1 for the catalogue's bandwidths, closed form in `signals.klatt_resonator_peak_hz`) — and notes that the cascade's envelope shifts further under the neighbouring skirts (its F3 peak reads 14 Hz, 3.6 bins at N = 8192, below the pole), because a row that compares a peak picker against the poles fails for the wrong reason. The 0 dBFS sine and square reach the int16 rails through `rint(x·32768)` by design: they are the clipping-flag vectors, and the −1 dBFS sine is the one that must not trip it.

| Signal | Asserts |
|---|---|
| Pure sines on bin centres and between bins (catalogue today: 437.5 Hz on-bin, 1000 Hz on-bin, 440 Hz off-bin at 0 / −1 / −20 / −60 dBFS; the 80 Hz – 8 kHz span is still owed) | peak bin, interpolated peak within the tolerance table (≤ 3 cents injection); leakage shape per window |
| Linear and exponential (Farina) sweeps | tracked peak follows; the exponential sweep is also the in-situ transfer-function instrument for the mic-EQ fit |
| Two-tone at Δf = 0.5 / 1 / 2 / 4 bins | resolution vs window (Hann vs Blackman-Harris per Harris 1978) |
| White and pink noise | flat / −3 dB per octave under the stated normalization (PS vs PSD — the classic trap) |
| Synthetic glottal-source vowels (Rosenberg / Liljencrants-Fant source + known F1–F3 vocal tract; `pyworld` or Praat `Create KlattGrid` as reference implementation) | f0 and formant estimators against exact ground truth |
| AM/FM tones at 5–7 Hz, ±1 semitone | vibrato rate/extent readout |
| Silence and DC offset | software DC removal (the S3 has no hardware PDM high-pass); noise floor in dBFS |
| Full-scale sine vs full-scale square | dBFS reference sanity — **per bin** the square's fundamental reads +2.10 dB over the sine (4/π; the sampled P = 32 square in the catalogue reads +2.11, recorded in the manifest), **broadband** (Σ PS / NENBW) +3.01 dB; the two are not interchangeable (ADR 0006 D3). *(This row read "3 dB apart by definition" until 2026-08-21 — the per-bin/broadband conflation ADR 0006 D3 names.)* |

## Licence ledger

Kept as `LICENCES.md` in this directory (planned) — one row per dataset, separate from the software-licence ledger (`NOTICE`) and from golden-file provenance (`host/golden/manifest.yaml`); the three are never conflated.

| Column | Meaning |
|---|---|
| `dataset` | name and version |
| `tier` | 0 synthetic · 1 clean licence + f0 ground truth · 2 restricted or non-commercial · 3 voice quality / pathology · N noise / RIR |
| `licence` | SPDX id or literal terms |
| `verified_on`, `verified_where` | date and URL the terms were read |
| `ground_truth` | f0 / notes / EGG / formants / ratings / none |
| `allowed_use` | thesis · preprint · headline metric · bench-only · none |
| `restriction` | NC ⇒ quarantined from any commercial framing; request-only ⇒ no derived number in an application until confirmed; unstated ⇒ bench-only |
| `clinical_claim` | always `no` — pathology corpora (Tier 3) are acoustic material only (ADR 0005, no clinical claim) |

Candidate corpora and their licences are catalogued in [`../docs/bibliography/10-datasets-and-ground-truth.md`](../docs/bibliography/10-datasets-and-ground-truth.md) (Tier 1 CC BY 4.0: vocadito, Dagstuhl ChoirSet, VocalSet, Annotated-VocalSet; Tier 2 restricted: PTDB-TUG, MDB-stem-synth (NC), MIR-1K (unstated), …; Tier 3 CC BY 4.0, acoustic material only: PVQD, the Saarbrücken Voice Database; noise: DEMAND, MUSAN; RIR: OpenAIR, BUT ReverbDB, ACE). Nothing is downloaded in Phase 0.

*PVQD moved from the Tier-1 clause to Tier 3 on 2026-08-21.* It is entry #18 under "Tier 3 — voice-quality and pathology corpora (acoustic material only)" in that bibliography file, and `tier: 3` in [`corpora/manifest.yaml`](corpora/manifest.yaml); listing it as Tier 1 here put a pathology corpus in the tier that feeds headline metrics. The same correction is still owed in [`../docs/validation/README.md`](../docs/validation/README.md), whose corpora table lists PVQD in **both** its Tier-1 row and its Tier-3 row — owner: Alexander (that file is not edited from here).

## Layout convention per dataset

*(Planned, not current — see the shape note above: today all seven corpora share the single aggregate [`corpora/manifest.yaml`](corpora/manifest.yaml).)*

```
<tier-or-kind>/<dataset-id>/
  ├── manifest.yaml        # the contract above — tracked
  ├── audio/               # *.wav (git-ignored; fetched or regenerated)
  ├── ground-truth/        # upstream annotations as shipped (tracked only if the licence allows redistribution)
  └── derived/             # resampled / normalised copies for the injection path (git-ignored; reproducible from manifest)
```
