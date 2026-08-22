<!-- SPDX-FileCopyrightText: 2026 Alexander Gomez -->
<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# Golden files — Praat/parselmouth reference outputs (GPL-3.0-or-later)

Generator and manifest for the reference outputs that the watch's DSP is regressed against: for each input WAV, the f0 contour, formants and spectra that Praat (through parselmouth) computes with **pinned** settings. The firmware's job is to match these to a stated tolerance on the digital-injection path ([`../../docs/validation/README.md`](../../docs/validation/README.md), two-path rule); the strategy is [ADR 0009](../../docs/adr/0009-golden-file-strategy.md) (accepted) and the tolerance table lives in [`../../docs/validation/golden-files.md`](../../docs/validation/golden-files.md).

## Why a manifest, and why it pins what it pins

"Parselmouth is numerically identical to Praat" is true **only for the Praat version parselmouth bundles** — praat.org is at 7.0.01 (Boersma, Weenink & Shchupak — read 2026-08-21) and Praat's default pitch method changed to *filtered autocorrelation* in 2023, while parselmouth's bundled Praat predates that. A golden file without its provenance is therefore not reproducible, and Praat's pitch floor/ceiling change the answer. Every golden set is described by `manifest.yaml`, whose **normative** form is [`manifest.schema.yaml`](manifest.schema.yaml) (JSON Schema draft 2020-12, `additionalProperties: false`). That file's `required:` lists are the single source of truth for what is mandatory — the table below explains *why each pin exists*, naming fields by their schema path, and deliberately does not restate the list (a second list is a second thing to drift):

| Field | Meaning | Example / rule |
|---|---|---|
| `generator.parselmouth` | exact installed parselmouth | from `parselmouth.__version__`; pinned in the host lock file |
| `generator.praat_bundled` | the Praat version **bundled** by that parselmouth | from `parselmouth.PRAAT_VERSION`; never assumed equal to praat.org's current release. (Field renamed 2026-08-21 to match [`manifest.schema.yaml`](manifest.schema.yaml) and [`../../docs/validation/golden-files.md`](../../docs/validation/golden-files.md), which are normative.) |
| `analyses.pitch.method` | `raw` (classic autocorrelation — `To Pitch (ac)...` on the bundled Praat 6.1.38; renamed `To Pitch (raw autocorrelation)...`, synonym `To Pitch (raw ac)...`, from Praat 6.4) or `filtered` (`To Pitch (filtered autocorrelation)...`, Praat ≥ 6.4 only) | must be stated per golden set; `cc` (cross-correlation) only if a set explicitly needs it |
| `analyses.pitch.pitch_floor`, `…pitch_ceiling` | Praat's floor/ceiling for the set | **65 / 1100 Hz** — C2 to just above C6, matching the f0 range the [validation plan](../../docs/validation/README.md) commits to (65 Hz – 1046 Hz) *(prov.)*; a change here is a new golden set, never an edit. (Names and values aligned 2026-08-21 with [`manifest.schema.yaml`](manifest.schema.yaml); this file previously said `pitch_floor_hz`/`pitch_ceiling_hz` and 60/1200.) |
| `analyses.pitch.time_step` | analysis step, in seconds | `0` (Praat auto) or explicit; explicit preferred so hop aligns with the watch's frame rate |
| `analyses.pitch.{silence_threshold, voicing_threshold, octave_cost, octave_jump_cost, voiced_unvoiced_cost}` | the remaining `To Pitch` parameters | recorded even when left at Praat defaults — defaults differ between `raw` and `filtered` |
| `analyses.formant` | `max_formants`, `ceiling_hz`, `window_length`, `preemphasis_from_hz` for `To Formant (burg)` | required when formants are part of the set; Praat's Burg analysis fits **2 × `max_formants`** poles — no `+2`: `Sound_to_Formant_burg()` passes `Melder_iround (2.0 * nFormants)` to `Sound_to_Formant_any()` in `fon/Sound_to_Formant.cpp` (identical at tags `v6.1.38` and `v6.4.27`), and the manual page `Sound: To Formant (burg)...` says the same. `max_formants: 5` ⇒ LPC order **10** |
| `windows[]` | one entry per `(family, N)` the set's spectrum references were built with: `family` (a [`preset-schema.md` §4.3](../../protocols/specs/preset-schema.md) name, or `rect` for calibration tones — admitted here only, never in a preset), `n`, `coefficients` (the cosine-sum *a<sub>k</sub>* the window was built from), `sha256` | sha256 of the **N float32 little-endian samples** of the **periodic** window — `general_cosine(N, a, sym=False)` on the host, `spectral_window_fill()` on the device — per [ADR 0006](../../docs/adr/0006-fft-normalisation-and-window-conventions.md) D1. Required whenever `analyses.spectrum` is present (schema `"1.1"`, [ADR 0009](../../docs/adr/0009-golden-file-strategy.md) amended 2026-08-21); `verify` recomputes every digest and checks the coefficients against §4.3 (invariant 7) and that an entry exists for `(analyses.spectrum.window, window_length_samples)` (invariant 8). The tolerance row is **exact** |
| `inputs[]` | one entry per input WAV: `path` (repository-relative, e.g. `datasets/tier0/sine_440_0dBFS_32k.wav` — the schema says repository-relative, not relative to `datasets/`), `sha256`, sample rate, channels, bit depth, `source` (Tier 0 generator name + parameters, or corpus + licence) | sha256 of the **bytes**, computed after any resampling |
| `outputs[]` | one entry per output array: path, `sha256`, dtype, shape, units (Hz, cents, dB re full-scale sine), column description | written by the generator, verified by `verify` |
| `generated`, `generator.script`, `generator.sha256` | when (UTC, `"YYYY-MM-DD"`, quoted), the generator package `host/src/spectral_host`, and the sorted tree hash of its numerics-bearing modules (`spectral_host.env.GENERATOR_TREE`, recipe `hashing.sha256_files`) | a change to anything that can alter a vector is visible; a change to the CLI or the verifier is not |
| `generator.{python, platform, blas}` | interpreter version, platform string, BLAS vendor | float64 on the host; the watch is float32 — tolerances, not equality. (There is no `host` block: these live under `generator`.) |

Not shown above, and equally mandatory: `schema` (the quoted string `"1.1"` — a reader accepts exactly one value; the integer `1` of the first schema is rejected), `set`, `generator.{script, commit, numpy, scipy, praat_reference}`, `inputs[].source`, `outputs[].{analysis, input, units, columns}`, `tolerances` (a *pointer* to the tolerance table plus the revision it was accepted against) and `regeneration`. Read them off the schema. (Field names aligned with the schema 2026-08-21; this table previously used `parselmouth_version`, `time_step_s`, `formant_settings`/`max_formant_hz`/`window_length_s`, `generated_utc`, `generator_sha256` and `host`, none of which the schema accepts under `additionalProperties: false`.)

A golden set whose manifest does not validate (missing field, sha256 mismatch) is not a golden set; CI refuses it.

## Layout

```
host/golden/                   # DATA and the contract — no code lives here
├── README.md
├── manifest.schema.yaml       # the golden-manifest schema ("1.1")
└── outputs/<set>/             # manifest.yaml + *.npy arrays (ADR 0009: arrays are .npy);
                              #   small sets tracked, large sets regenerated

host/src/spectral_host/golden/ # the CODE (GPL, src layout since H0 unit B-U1)
├── sets.py                    # declarative set definitions (which inputs, which analyses, which parameters)
├── generate.py                # the parselmouth driver: writes outputs/<set>/ and its manifest, then self-verifies
├── verify.py                  # rules S, I1–I8, N1–N4, G1 — recomputes every sha256, checks the pins; never writes
├── manifest.py                # load / validate / dump of a manifest (quoted dates, GPL header lines)
└── cli.py                     # `spectral-golden verify | env | generate | t7`
```

Inputs are **not** stored here: Tier-0 synthetic signals are regenerated by their Apache-2.0 generators under [`../../python-scripts/`](../../python-scripts/) and corpus excerpts are fetched by [`../../datasets/`](../../datasets/) manifests — the golden manifest references them by path and sha256.

## Workflow

1. `uv run --project host spectral-golden verify` against the current environment — if parselmouth or the bundled Praat changed, **regenerate, do not patch**: a new parselmouth produces a new golden set with a new manifest.
2. `uv run --project host spectral-golden generate --set tier0-synthetic --approved-by "<name>" --reason "<why>"` writes outputs and the manifest from a **clean** `host/src` (it refuses a dirty package and an existing set directory); review the diff of the manifest, never the arrays.
3. The watch regression (`host-tests/` for the pure-C core, QEMU/target for the esp-dsp backend) consumes the arrays and compares in the units the tolerance table names (cents for f0, dB for spectra, Hz or % for formants).

## Tolerances, not equality

Xtensa `sinf`/`expf`/`log10f` are not x86 libm; float32 accumulation is not float64; the watch is built without `-ffast-math` precisely so the difference stays bounded and explainable. The acceptance criterion is therefore a per-metric tolerance (`median |Δcents| ≤ 5` vs Praat on injection, F1/F2 within 5 % or 50 Hz, spectra within a dB tolerance per bin class) — defined in [`../../docs/validation/golden-files.md`](../../docs/validation/golden-files.md), never `==`.

> **Measured 2026-08-21 — which Praat this actually is.** `praat-parselmouth==0.4.7`
> (the pin in [`../pyproject.toml`](../pyproject.toml)) bundles **Praat 6.1.38**, released
> 2021-01-02. It exposes `to_pitch`, `to_pitch_ac`, `to_pitch_cc`, `to_pitch_shs` and
> `to_pitch_spinet` — and *not* the filtered method, which Praat added in 6.4 (2023-11-15):
> asking for it returns `PraatError: Command "To Pitch (filtered autocorrelation)" not
> available for given objects.` So `pitch_method` is `raw` for every set generated here,
> with 6.1.38's own defaults (silence 0.03, voicing 0.45, octave cost 0.01), and the
> floor/ceiling widened to 65/1100 Hz for singing `(prov.)`. `verify.py` enforces this as
> invariant 6: `filtered` requires `praat_bundled ≥ 6.4.0`. Sanity check from the same run:
> raw-ac on a synthetic 440 Hz sine gives max |Δ| = **0.0034 cents** over 296 frames, so the
> anchor itself is far inside the ±5-cent bound the research question asks about.

Reference basis: Jadoul, Thompson & de Boer 2018 (parselmouth); Boersma 1993 (autocorrelation pitch) and the Praat manual pages for filtered autocorrelation and `To Formant (burg)`; Hillenbrand et al. 1995 as measured-formant material — all catalogued in [`../../docs/bibliography/05-papers.md`](../../docs/bibliography/05-papers.md) and [`../../docs/bibliography/10-datasets-and-ground-truth.md`](../../docs/bibliography/10-datasets-and-ground-truth.md).
