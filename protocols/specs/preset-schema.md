# Preset schema

**Status:** normative, bound by [ADR 0010](../../docs/adr/0010-preset-schema.md). **Owner:** this directory. **Machine-readable form:** [`presets.schema.json`](presets.schema.json) (JSON Schema draft 2020-12). **Shipped instances:** [`../presets/`](../presets/) — six files, one per preset of the founding research document ([`00-linux-analyzer-architecture-and-build-guide.md`](../../docs/research/00-linux-analyzer-architecture-and-build-guide.md) §B).

A preset is the only thing a user changes that changes what the numbers *mean*. It is therefore the one place where every convention that could silently differ between the watch and the host — window, its coherent gain, its noise bandwidth, the dB reference, the microphone correction — is written down in the file itself rather than assumed. This document defines every field, the rules a loader enforces, and the identity a take manifest points at.

This spec does **not** define the DSP conventions. Normalisation (`1/N` vs `1/√N`, S1/S2 sums, power spectrum vs PSD scaling) is [ADR 0006](../../docs/adr/0006-fft-normalisation-and-window-conventions.md) and `dsp/design/fft-normalization.md` (**planned**); the decimation cascade is `dsp/design/decimation-cascade.md` (**planned**); the ring/twang readout is [ADR 0008](../../docs/adr/README.md). See [`../../dsp/design/README.md`](../../dsp/design/README.md).

## 1. Where presets live

```
LittleFS `presets` partition — 1 MB at 0x821000, subtype 0x83 (ADR 0014)
│
├── presets/
│   ├── live_singing.json           ─┐
│   ├── vowel_formant_study.json     │  the six shipped presets, 1.48–1.62 kB each
│   ├── sustained_pitch_lab.json     │  stored byte-for-byte as committed under
│   ├── diction_consonants.json      │  protocols/presets/ (canonical form, §3)
│   ├── room_noise_floor.json        │
│   └── stem_analysis.json          ─┘  present, but never offered by the watch UI
│
├── eq/
│   └── <eq_id>.json                    filed microphone-EQ curves — none exist until
│                                       validation experiment 0001 fits one
└── index.json                          id → { file, sha256, bytes }; written by the host,
                                        read by the watch, never edited on the watch
```

The whole shipped set is 9,323 bytes, so LittleFS's 4 KB block granularity — not the content — decides the footprint, and the partition is oversized on purpose: the store is wear-levelled and power-fail safe precisely so that a preset edit interrupted by a flat battery cannot leave a half-written file where a valid one used to be ([ADR 0014](../../docs/adr/0014-partition-layout-frozen.md)).

Takes are a different partition and a different format: binary, fixed-layout, no JSON ([`../README.md`](../README.md)). Presets are JSON because the host edits them and because the schema is the thing a user reasons about.

## 2. Anatomy

```
preset.json
├── schema_version   "1.0.0"          the loader accepts major 1 and rejects everything else
├── id               live_singing     == the file's basename (rule V1)
├── name             "Live singing"   the preset picker's label
├── description      one paragraph
├── targets          ["watch","host"] which half may run it (ADR 0002)
├── analysis ────────────────────────────────────────────────────────────────┐
│   ├── sample_rate_hz  fft_size  interval_ms  decimations                   │
│   ├── window       { name, form, coefficients, coherent_gain,              │  everything
│   │                  coherent_gain_db, enbw_bins }                         │  the host
│   ├── resolution   { bin_width_hz, window_duration_ms,                     │  must repeat
│   │                  enbw_hz, hop_samples }                                │  exactly
│   ├── spectrum_type  db_reference  weighting  dc_blocker_hz                │
│   └── averaging  averaging_frames  smoothing  hold ───────────────────────┘
├── mic_eq           { mode: none | ref | inline, … }
├── display          { freq_scale, freq_min_hz, freq_max_hz, db_floor_dbfs,
│                      db_ceiling_dbfs, refresh_hz_target, colormap_id, overlays[] }
├── host             { reference, separation, align }   host-target presets only
├── guidance         environment rules of thumb, shown once on selection
└── provisional      JSON Pointers to fields that are still `(prov.)`
```

## 3. Identity: `id`, `schema_version`, canonical form, sha256

A take is written with a preset, and months later the host has to know *exactly* which preset that was — not its name, its bytes. `TAKE_HEADER` therefore carries the preset `id` **and** the sha256 of the preset file ([`../README.md`](../README.md), record kind `0x01`).

**Canonical form (rule V0).** The file on disk *is* the canonical form; the hash is over its bytes, so nothing on the watch has to re-serialise JSON to verify a hash.

| Property | Rule |
|---|---|
| Encoding | UTF-8, no BOM |
| Line ending | LF, exactly one trailing newline, no trailing whitespace |
| Object members | sorted by Unicode code point, one per line |
| Indent | two spaces per level |
| Separators | `,` at end of line, `": "` between key and value |
| Arrays | one element per line; array **order is significant** and is never sorted (`overlays` is display order) |
| Numbers | decimal only — no exponent, no leading `+`, no trailing `.`; **rounded** (half-even) to at most 6 decimal places, never truncated. Truncation is what makes a derived value miss the V9 tolerance from the correct side: `live_singing`'s `enbw_hz` is 15.6590078125 exactly, and the truncated `15.659007` is 8.1×10⁻⁷ away — inside V9's 1×10⁻⁶ but outside the 5×10⁻⁷ the rule below promises |

The number rule is what makes this portable: the schema constrains every numeric field to a range in which the shortest round-trip decimal is identical in Python's `repr`, in ECMAScript's `Number::toString` and in a C `printf("%.17g")` round-trip, so the sorted-keys/indent form above is unambiguous without importing a full canonicalisation scheme (RFC 8785 JCS is the fallback if the schema ever admits a field where they could differ; it is not a bibliography entry yet).

`python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(json.dumps(d,sort_keys=True,indent=2,ensure_ascii=False))"` reproduces the file exactly, minus the trailing newline. That equality is rule V0 and is what a pre-commit hook checks.

**Versioning.** `schema_version` is `MAJOR.MINOR.PATCH`. MINOR adds optional fields; PATCH is editorial. A loader accepts MAJOR 1 and **rejects** anything else — it never coerces, never fills a default for a field it does not recognise, and never drops an unknown field silently (`additionalProperties: false` makes an unknown field a hard error). Changing MAJOR is an ADR and coordinated commits across firmware, host, validation and these files.

**Hash chain.**

```
preset file bytes ──sha256──────────────► preset_sha256 ──┐
eq/<eq_id>.json  ──sha256──────────────► eq_sha256 ──┐    │
                                                     ▼    ▼
firmware image ──esp_app_desc──► app_elf_sha256 ──► TAKE_HEADER (kind 0x01)
                                                          │
                                                          ▼
                     the host can reconstruct the exact analysis that produced the take
```

## 4. Field reference

Unless stated otherwise every field is **required**. `additionalProperties` is `false` at every level.

### 4.1 Top level

| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | `^1\.N\.N$` |
| `id` | string | `^[a-z][a-z0-9_]{2,31}$`, equals the basename |
| `name` | string ≤ 40 | preset-picker label |
| `description` | string ≤ 400 | optional |
| `targets` | array of `watch` \| `host` | 1–2 entries, unique. A host-only preset is never offered by the watch UI and can never be named by a take |
| `analysis` | object | §4.2 |
| `mic_eq` | object | §4.5 |
| `display` | object | §4.6 |
| `host` | object | optional; §4.7; permitted only when `targets` contains `host` |
| `guidance` | string ≤ 600 | optional; the "environment rules of thumb" the founding document asks for — distance, expected floor, clipping headroom |
| `provisional` | array of JSON Pointer | optional; the repository's `(prov.)` marker made machine-readable. Every pointer must resolve (rule V10) |

### 4.2 `analysis`

| Field | Type | Notes |
|---|---|---|
| `sample_rate_hz` | 16000 \| 32000 \| **48000 (reserved)** | 32 kHz is the default ([ADR 0003](../../docs/adr/0003-microphone-path.md) decision 4). **48000 is present in the enum but rejected by the watch loader** until [experiment 0001](../../docs/validation/experiments/0001-pdm-mic-in-situ-characterization.md) clause 4 shows the SPM1423 tolerates a 3.072 MHz PDM clock; if that test fails, 48000 leaves the enum in a MAJOR bump. A **host-only** preset may use 48000 today — the gate is on the capture path, and the host reads files, not microphones |
| `fft_size` | 512 … 16384 | real transform length N. **16384 is host-only.** On the path [ADR 0006](../../docs/adr/0006-fft-normalisation-and-window-conventions.md) chose (**accepted** 2026-08-21) — our own `cplx2real` (decision 5) on the `fft2r` kernel for every size (decision 6) — the real-8192 working set is ≈ 104 KB of internal SRAM, against ≈ 160 KB if esp-dsp's own `fft4r` table were paid for (ADR 0006, *Consequences*). Real-16384 is ≈ 192–224 KB on the two pre-D5 itemisations, which do not agree with each other ([03-dsp-pipeline §4.1](../../docs/architecture/03-dsp-pipeline.md), and §7 below for the per-size breakdown). All figures `(prov.)` and unmeasured — roadmap **H13** measures them, and the internal-SRAM budget they are weighed against (I²S DMA, LVGL partial buffers, SPI bounce buffer) is itself unmeasured |
| `window` | object | §4.3 |
| `resolution` | object | §4.4 |
| `interval_ms` | integer 1–1000 | analysis hop. `interval_ms × sample_rate_hz` must be a multiple of 1000 (rule V7 clause 1 — **vacuous under the present enum**, since 16000, 32000 and 48000 are each a multiple of 1000 and `interval_ms` is an integer; it is kept as the guard a non-1000-divisible rate would need, e.g. 44100) |
| `decimations` | integer 0–4 | Spectroid-style cascade depth; stage *k* analyses at `sample_rate_hz / 2^k`. A real IIR low-pass, never decimate-by-averaging — the mistake Friture's maintainer removed from its FFT path. **0 in every shipped preset**: the cascade is designed in `dsp/design/decimation-cascade.md`, which is **planned, not written** ([`../../dsp/design/README.md`](../../dsp/design/README.md)) |
| `spectrum_type` | `power_spectrum` \| `psd` | what the dB axis shows. PSD divides by the ENBW and is correct for noise; power spectrum is correct for tones. ADR 0006 fixes the constants — the preset only names which of the two it displays |
| `db_reference` | const `dbfs_sine` | dBFS referenced to a full-scale **sine**. A full-scale square reference is the same axis shifted by 3.01 dB, and that constant is the classic "it goes away if someone edits a number" bug ([`golden-files.md`](../../docs/validation/golden-files.md)) |
| `averaging` | `none` \| `exponential` \| `linear` | linear averaging is Welch's method |
| `averaging_frames` | integer 2–1000 | required iff `averaging == "linear"`, forbidden otherwise |
| `smoothing` | number 0–0.95 | exponential coefficient; must be > 0 iff `averaging == "exponential"`, and exactly 0 otherwise. The 0.95 ceiling is `(prov.)` — recalled from Spectroid, not read from it, until the manual capture of [07 #9](../../docs/bibliography/07-technical-reports.md) (roadmap D3) settles the enumerated values (§9) |
| `hold` | `none` \| `peak` \| `min` | |
| `weighting` | `Z` \| `A` \| `C` | applies to **level readouts only**, never to the displayed spectrum. Relative dBFS in every case: no calibrator is in the chain, so no reading is dB SPL |
| `dc_blocker_hz` | number 0–100 | corner of the software DC blocker in the capture path. The ESP32-S3 has no hardware PDM high-pass, so this filter always exists and the host must reproduce it ([ADR 0003](../../docs/adr/0003-microphone-path.md) decision 6) |

### 4.3 `analysis.window` — properties of the window alone

| Field | Type | Notes |
|---|---|---|
| `name` | `hann` \| `blackman` \| `blackman_harris` \| `blackman_nuttall` \| `nuttall` \| `flat_top` | the six families esp-dsp ships, so a preset never asks for a window the firmware cannot build |
| `form` | const `periodic` | DFT-even. esp-dsp's own `dsps_wind_*_f32` are **symmetric** (`1/(len−1)`); the firmware generates the periodic family itself ([ADR 0018](../../docs/adr/0018-first-reference-project-study.md)) |
| `coefficients` | array of 2–5 numbers | the cosine-sum *a<sub>k</sub>*, exactly as committed in esp-dsp — the Blackman–Harris set is the standard 4-term −92 dB one and the Nuttall set is Nuttall 1981's 4-term window with **continuous first derivative**, *not* his minimum-sidelobe 4-term — that one is the set this table names `blackman_nuttall`, which is also what SciPy's docstring calls "a minimum 4-term Blackman-Harris window according to Nuttall" and Heinzel's "Nuttall4c" (`(prov.)` on the paper: Nuttall 1981 is [05 #3](../../docs/bibliography/05-papers.md) and is **not filed**, so the attribution rests on the coefficient sets in [`esp-dsp_notes.md`](../../docs/reference-projects/notes/esp-dsp_notes.md) §5 and in SciPy 1.18, not on the paper). **Two name traps, both measured 2026-08-21 and both able to cost a silent fraction of a dB:** (a) `scipy.signal.windows.nuttall` is the **Blackman–Nuttall** set `[0.3635819, 0.4891775, 0.1365995, 0.0106411]` — i.e. SciPy's `nuttall` is this schema's `blackman_nuttall`, and this schema's `nuttall` `[0.355768, 0.487396, 0.144232, 0.012604]` **has no SciPy name at all** (`grep 0.355768` over the installed package finds nothing); (b) **Praat has none of these windows.** `Sound_multiplyByWindow` enumerates its complete set — rectangular, triangular, parabolic, Hanning, Hamming, Gaussian 1–5, Kaiser — so five of the six families here cannot be compared with Praat at all, and only `hann` can. Windows are therefore built from the **coefficients** in the table below, never from a library's name for them ([ADR 0006](../../docs/adr/0006-fft-normalisation-and-window-conventions.md) D1) ([`esp-dsp_notes.md`](../../docs/reference-projects/notes/esp-dsp_notes.md) §5) |
| `coherent_gain` | number | *a<sub>0</sub>*. Divide a **tone's** magnitude by this |
| `coherent_gain_db` | number | 20·log₁₀(*a<sub>0</sub>*), for the UI |
| `enbw_bins` | number 1–8 | normalised equivalent noise bandwidth, in bins (Heinzel 2002's NENBW). Divide a **noise** power by this. `enbw_bins = (a₀² + Σ_{k≥1} a_k²/2) / a₀²` |

Carrying the coefficients *and* the two derived constants is deliberate redundancy, and rule V8 is what keeps it honest: a loader recomputes both from `coefficients` and rejects the file if either disagrees by more than 1×10⁻⁶. The alternative — a hard-coded table in two languages — is exactly the kind of duplication that produces a 2 dB noise-floor error nobody can find.

| `name` | *a₀…a₄* | `coherent_gain` | `coherent_gain_db` | `enbw_bins` |
|---|---|---:|---:|---:|
| `hann` | 0.5, 0.5 | 0.5 | −6.0206 | 1.5 |
| `blackman` | 0.42, 0.5, 0.08 | 0.42 | −7.535014 | 1.726757 |
| `blackman_harris` | 0.35875, 0.48829, 0.14128, 0.01168 | 0.35875 | −8.904162 | 2.004353 |
| `blackman_nuttall` | 0.3635819, 0.4891775, 0.1365995, 0.0106411 | 0.3635819 | −8.787955 | 1.976109 |
| `nuttall` | 0.355768, 0.487396, 0.144232, 0.012604 | 0.355768 | −8.976662 | 2.021233 |
| `flat_top` | 0.21557895, 0.41663158, 0.277263158, 0.083578947, 0.006947368 | 0.21557895 | −13.327873 | 3.770246 |

Gaussian is **not** in the enum. Praat uses it for its zero sidelobes and its bandwidth convention is defined for it; adding it is an ADR 0006 question (open question 34 of the domain map), not a schema edit — and esp-dsp does not ship it.

### 4.4 `analysis.resolution` — what the (window, N, f<sub>s</sub>) triple buys

Every field here is derived, and every field here is re-derived and re-checked on load (rule V9). It is stored anyway, because a take manifest that names an ENBW is self-describing and one that names only `"window": "hann"` is not.

| Field | Definition |
|---|---|
| `bin_width_hz` | `sample_rate_hz / fft_size` |
| `window_duration_ms` | `1000 × fft_size / sample_rate_hz` |
| `enbw_hz` | `enbw_bins × bin_width_hz` — **the analysis bandwidth of this preset** |
| `hop_samples` | `interval_ms × sample_rate_hz / 1000`, an integer |

### 4.5 `mic_eq` — the microphone-correction slot

One of exactly three shapes ([ADR 0003](../../docs/adr/0003-microphone-path.md) decision 7: the only conditioning ever permitted in the analysis path is linear and declared).

```
{ "mode": "none" }                                    no correction — the state today

{ "mode": "ref",    "eq_id": "…", "sha256": "…" }     the curve lives at eq/<eq_id>.json
                                                      on the same partition; the sha256
                                                      makes the reference exact

{ "mode": "inline", "eq_id": "…",                     the curve travels with the preset
  "design_sample_rate_hz": 32000,
  "scope": "part_number" | "unit",
  "biquads": [ { "b0","b1","b2","a1","a2" }, … ] }    ≤ 8 sections, RBJ sign convention,
                                                      a0 ≡ 1 (esp-dsp dsps_biquad_f32 order)
```

`design_sample_rate_hz` must equal `analysis.sample_rate_hz` (rule V6b): a biquad cascade fitted at 32 kHz is a different filter at 48 kHz.

`scope` records the open question the EQ itself raises — whether the correction is a per-part-number constant or a per-unit calibration. A per-unit EQ makes every band ratio non-reproducible on a second watch without a calibration step. The schema records the answer; it does not choose it (`dsp/design/mic-eq.md` — **planned**; the content lives today in [ADR 0003](../../docs/adr/0003-microphone-path.md) decision 7 and [experiment 0001](../../docs/validation/experiments/0001-pdm-mic-in-situ-characterization.md); roadmap Q38).

All six shipped presets are `{"mode": "none"}` because no EQ has been fitted: experiment 0001 produces the first one. Every band-energy readout is therefore uncorrected today, and the validation plan reports uncorrected and post-EQ values separately for exactly this reason.

### 4.6 `display`

| Field | Type | Notes |
|---|---|---|
| `freq_scale` | `log` \| `linear` | `log` requires `freq_min_hz > 0` (rule V4) |
| `freq_min_hz`, `freq_max_hz` | number | `0 ≤ min < max ≤ sample_rate_hz / 2` (rule V9) |
| `db_floor_dbfs`, `db_ceiling_dbfs` | number | the visible dB window |
| `refresh_hz_target` | integer 1–50 | **required for a watch preset.** 50 Hz is the `(prov.)` **target** ceiling of the hardware-scrolled analyzer canvas — ADR 0007 is pre-registered, not written, and the *Sustained refresh* row of [`../../docs/validation/README.md`](../../docs/validation/README.md) is a target with a measurement method, not a measurement; `1000 / interval_ms` must be an integer multiple of it (rule V7), i.e. a whole number of spectrogram columns per rendered frame |
| `colormap_id` | string | optional, and deliberately **not** an enum: [ADR 0011](../../docs/adr/README.md) fixes the map and the RGB565 LUT. Absent means "the firmware default". No shipped preset sets it |
| `overlays` | array, ≤ 8, unique | `f0`, `peak_markers`, `f1f2`, `spectrum_envelope`, `vibrato_rate`, `ring_band`, `twang_band`, `fhe`, `spr`, `ltas`, `leq`, `clipping`, `stem_f0`, `dtw_path`. `stem_f0` and `dtw_path` are **host-only** and are rejected on a watch preset (rule V2) |

`db_floor_dbfs` in the shipped presets is derived, not chosen: the per-bin noise floor of a tonal component sits roughly `10·log₁₀((N/2) / enbw_bins)` below the microphone's broadband SNR, so `floor = −10·round((SNR_A + processing gain)/10)` with SNR<sub>A</sub> = 61.5 dB(A) from the SPM1423 datasheet. That is a datasheet-derived expectation, so `/display/db_floor_dbfs` is listed in `provisional` in every preset until experiment 0001 measures the real floor.

`freq_max_hz` is capped at 12800 Hz (0.4·f<sub>s</sub>) in the two presets that would otherwise run to Nyquist: the ESP32-S3's PDM→PCM decimation filter response is undocumented above roughly 0.4·f<sub>s</sub> — the TRM gives only `f_sampling = f_PDM / DSR`, with no SINC order, passband ripple or stopband figure — so displaying to Nyquist would draw a curve whose shape is the filter's, not the room's. Also `provisional`, pending the swept-sine measurement in experiment 0001.

### 4.7 `host`

| Field | Type | Notes |
|---|---|---|
| `reference` | `none` \| `stem` \| `take` | what the take is compared against |
| `separation` | `none` \| `demucs_htdemucs` \| `demucs_htdemucs_ft` | local stem separation; `htdemucs_ft` is the fine-tuned model |
| `align` | `none` \| `dtw_chroma` \| `dtw_mfcc` | DTW feature for time alignment when the two performances differ in tempo |

## 5. Bandwidth: why `enbw_hz` is mandatory

The founding document's presets state an FFT size and a window and nothing else. That is not enough to say what a spectrogram *shows*, and it is the reason two people can look at the same picture and disagree about whether it is "wideband" or "narrowband":

| Convention | Wideband | Narrowband | Source |
|---|---|---|---|
| Classical sound spectrograph | 300 Hz | 45 Hz | Koenig, Dunn & Lacy 1946 |
| Praat (Gaussian, bandwidth = 1.2982804 / window length) | 260 Hz at 5 ms | 43 Hz at 30 ms | Praat manual |

Neither is a property of "8192-point Hann". Both are bandwidths. So the schema requires the bandwidth — `enbw_hz`, on Heinzel's NENBW definition, which is the one that also makes the dB axis correct — and the words "wideband" and "narrowband" **do not appear in a preset file at all**. The UI prints `enbw_hz` and `window_duration_ms`; a reader who wants the classical vocabulary can place the number against the table above.

Doing this immediately surfaces something the presets had hidden. At 32 kHz a Hann window reaches Koenig's 300 Hz wideband only at N ≈ 160, and his 45 Hz narrowband at N ≈ 1067:

| Preset | N | window | `window_duration_ms` | `enbw_hz` | Against the classical pair |
|---|---:|---|---:|---:|---|
| `diction_consonants` | 1024 | hann | 32.0 | **46.875** | ≈ Koenig **narrowband** (45 Hz) |
| `live_singing` | 4096 | blackman_harris | 128.0 | 15.659008 | 3× narrower than narrowband |
| `stem_analysis` | 8192 | hann | 170.666667 | 8.789062 | |
| `sustained_pitch_lab` | 8192 | blackman_harris | 256.0 | 7.829504 | |
| `room_noise_floor` | 8192 | hann | 256.0 | 5.859375 | |
| `vowel_formant_study` | 8192 | hann | 256.0 | 5.859375 | 8× narrower than narrowband |

**Every one of the six is a narrowband analysis**, and the one named for consonants — transients, where a wideband window is the classical tool — is the *closest* to narrowband's 45 Hz rather than to wideband's 300 Hz. The schema does not fix that; it makes it visible and puts a number on it. Whether the set gains a genuinely wideband preset (N ≈ 128–256) is an ADR 0006 / preset-content question, routed there, not decided here.

## 6. Loader rules

The watch **validates and rejects**; it never coerces, never clamps, never substitutes a default for a malformed value. A preset that fails any rule is not loaded, the previous preset stays active, and the failure is logged with the rule number. Silent coercion is how a take ends up recorded under an analysis nobody can reconstruct.

| Rule | Statement | Enforced by |
|---|---|---|
| V0 | The file's bytes are exactly its canonical form (§3) | pre-commit hook / host writer |
| V1 | `id` equals the file's basename without `.json` | loader |
| V2 | A `watch` preset: `fft_size ≤ 8192`, `sample_rate_hz ≠ 48000` (until the gate opens), `refresh_hz_target` present, no host-only overlay | schema + loader — all four are in the schema's V2 branch since 2026-08-21; the loader repeats them because a preset can also arrive over the wire |
| V3 | A `host` block implies `host ∈ targets` | schema |
| V4 | `freq_scale == "log"` implies `freq_min_hz > 0` | schema |
| V5 | `smoothing > 0` iff `averaging == "exponential"`; otherwise exactly 0 | schema |
| V6 | `averaging_frames` present iff `averaging == "linear"` | schema |
| V6b | `mic_eq.design_sample_rate_hz == analysis.sample_rate_hz` when `mode == "inline"` | loader |
| V7 | `interval_ms × sample_rate_hz` is a multiple of 1000 (vacuous under the present `sample_rate_hz` enum — §4.2); `1000 / interval_ms` is an integer multiple of `refresh_hz_target` | loader |
| V8 | `coefficients` match the named family, and `coherent_gain`, `coherent_gain_db`, `enbw_bins` are recomputed from them (tolerance 1×10⁻⁶) | loader |
| V9 | every `resolution` field recomputed from `sample_rate_hz`, `fft_size`, `interval_ms`, `enbw_bins` (tolerance 1×10⁻⁶); `0 ≤ freq_min_hz < freq_max_hz ≤ sample_rate_hz / 2` | loader |
| V10 | every pointer in `provisional` resolves to an existing field | loader |

The 1×10⁻⁶ tolerance is exactly what the canonical-form number rule guarantees: **rounding** to 6 places moves a value by at most 5×10⁻⁷, so a correctly written file sits at half the tolerance and the other half absorbs the float arithmetic. Truncating instead of rounding spends the margin: it can move a value by up to 1×10⁻⁶, i.e. the whole budget.

## 7. The six presets as shipped

Sample rate 32 kHz everywhere except the host-only preset ([ADR 0003](../../docs/adr/0003-microphone-path.md)); `decimations` 0 everywhere; `mic_eq` `none` everywhere.

| id | targets | N | window | hop | refresh | `enbw_hz` | averaging / hold | overlays | CPU (one core) *(prov.)* |
|---|---|---:|---|---:|---:|---:|---|---|---|
| `live_singing` | watch, host | 4096 | blackman_harris | 20 ms | 50 Hz | 15.659008 | exp 0.25 / — | f0, peaks, ring, clipping | ≈ 6.2 % |
| `vowel_formant_study` | watch, host | 8192 | hann | 40 ms | 25 Hz | 5.859375 | none | f1f2, envelope, peaks | ≈ 4.5 % (derived) |
| `sustained_pitch_lab` | watch, host | 8192 | blackman_harris | 40 ms | 25 Hz | 7.829504 | exp 0.15 / — | f0, vibrato, peaks | ≈ 4.5 % |
| `diction_consonants` | watch, host | 1024 | hann | 10 ms | 50 Hz | 46.875 | none | peaks, clipping | ≈ 2.6 % |
| `room_noise_floor` | watch, host | 8192 | hann | 40 ms | 25 Hz | 5.859375 | linear ×25 / min | leq | ≈ 4.5 % (derived) |
| `stem_analysis` | **host** | 8192 | hann | 10 ms | — | 8.789062 | none | stem f0, dtw, ltas, spr | n/a |

CPU figures are `(prov.)` throughout — preset-feasibility *estimates*, restated from [03-dsp-pipeline §11](../../docs/architecture/03-dsp-pipeline.md), which gives three reasons none of them may be quoted as a result (the published esp-dsp benchmark stops at 1024 complex points, has no row for `bit_rev*` / `cplx2real` / any window, and is IRAM-resident). They scale real N at the stated frame rate, +40 % for window, bit-reversal, `cplx2real`, magnitude and fast-log; "derived" marks a figure scaled from a published rate to this preset's frame rate rather than quoted directly. Every one is re-measured on target in Phase 1 with `dsp_get_cpu_cycle_count()`. Internal-SRAM **FFT working set**, computed from esp-dsp's own allocation sites ([esp-dsp notes §4.1](../../docs/reference-projects/notes/esp-dsp_notes.md)): about 22 KB at real N = 2048, 52 KB at 4096 and 104 KB at 8192 if we supply our own `cplx2real`; about 36 / 78 / 160 KB on esp-dsp's own tables, the difference being the `16*N_c` radix-4 twiddle table that `dsps_cplx2real_fc32` pulls in even on the radix-2 path. The int16 input ring (`2*N`) and the column buffers sit on top of that.

`diction_consonants` is the preset that makes `refresh_hz_target` earn its place: a 10 ms hop is 100 analysis frames per second, which the DSP can do and the panel cannot. The analyzer canvas is scrolled by hardware, so the renderer pushes **two spectrogram columns per rendered frame** at 50 Hz. Analysis rate and display rate are separate fields because they are separate limits.

## 8. What the schema deliberately does not contain

- **Capture-path constants that must not vary between presets** — the int16→float divisor (32768), the clipping threshold (|s| ≥ 0.99 FS), the PDM slot mask, the DMA descriptor sizing. These are firmware constants; a preset that could change them could change what "0 dBFS" means mid-session.
- **Normalisation constants.** ADR 0006 owns `1/N` vs `1/√N` and the S1/S2 bookkeeping. The preset names `spectrum_type` and supplies the two window constants that scaling needs; it does not restate the formula.
- **Band edges for ring/twang/SPR.** They are unsettled in the literature (2.5–3.5 kHz vs Omori's 2–4 kHz vs Bloothooft & Plomp's 1/3-octave bands) and they belong to ADR 0008. `overlays` names *which* readout is drawn, not where its edges are.
- **The colormap.** ADR 0011. `colormap_id` is an open string until it lands.
- **Anything about takes.** A preset does not know it is being recorded.
- **User state** — last-selected preset, brightness, volume. That is NVS, not the preset store.

## 9. Background reading

Windows, coherent gain and ENBW: Harris 1978, Nuttall 1981 and Heinzel, Rüdiger & Schilling 2002 in [`../../docs/bibliography/05-papers.md`](../../docs/bibliography/05-papers.md); Welch 1967 for the linear-averaging preset; Koenig, Dunn & Lacy 1946 for the 300/45 Hz pair. The committed esp-dsp coefficients and the symmetric-window defect are in [`../../docs/reference-projects/notes/esp-dsp_notes.md`](../../docs/reference-projects/notes/esp-dsp_notes.md) §5. Storage: the ESP-IDF partition-table guide and the `joltwallet/littlefs` README in [`../../docs/bibliography/02-application-notes.md`](../../docs/bibliography/02-application-notes.md). Prior art for the preset model: Spectroid ([`../../docs/bibliography/07-technical-reports.md`](../../docs/bibliography/07-technical-reports.md) #9 — still a manual capture task; until it is done the enumerated values here are reconstructed from the founding document, not from the app) and Friture ([`../../docs/bibliography/06-reference-projects.md`](../../docs/bibliography/06-reference-projects.md) #32).

## 10. Verification hooks

| Hook | What it proves | Where |
|---|---|---|
| Schema validation of `protocols/presets/*.json` | every shipped preset is loadable | [`python-scripts/check_presets.py`](../../python-scripts/check_presets.py), the pre-commit `presets-rules` hook and the `python-scripts` CI job. `jsonschema` 4.10.3 `Draft202012Validator`; **6/6 accepted** (2026-08-21) |
| Negative-case suite | the loader *rejects* every malformed preset. **41 mutations, 41/41 rejected** (2026-08-21) — 28 by the schema (unknown top-level or `analysis` field, off-enum window / `spectrum_type` / `weighting`, symmetric window `form`, `schema_version` 2.x or non-semver, missing `enbw_hz` / `id` / `targets`, empty `targets`, `db_floor` above its permitted **maximum** (the suite names this case "db_floor above db_ceiling", but the schema bounds the two independently — `db_floor_dbfs` ≤ −10, `db_ceiling_dbfs` ≥ −20 — and **no rule anywhere enforces `db_floor_dbfs < db_ceiling_dbfs`**: an inversion inside the overlapping [−20, −10] window is accepted today. Open item for the loader, tracked here until a V-numbered rule and a real negative case exist), negative `dc_blocker_hz`, `smoothing` > 1, `fft_size` not a power of two, a one-coefficient window, `mic_eq` `ref` without a sha256, and — because the schema encodes those conditionals too — V2's N = 16384, its 48 kHz ban and its missing `refresh_hz_target`, V3, V4, V5 and V6; plus the **V6b** mutation, which the schema rejects only because it is *also* structurally malformed — it omits `eq_id` and writes `biquads: [{b, a}]` instead of `b0…a2`, so `mic_eq`'s `oneOf` fails on shape, not on the design rate. **V6b itself is loader-only**, as §6's *Enforced by* column says: a well-formed inline EQ carrying `design_sample_rate_hz: 48000` against `analysis.sample_rate_hz: 32000` validates clean (verified 2026-08-21), because nothing in the schema relates the two subtrees. Encoding it would take root-level `if/then` branches over the three `sample_rate_hz` values; that is a schema change and an ADR 0010 amendment, not an editorial fix) and **13 only by the rules** (V1 `id` ≠ filename; V7 an analysis rate `1000 / interval_ms` that is not an integer and one that is not an integer multiple of `refresh_hz_target`; V8 a mutated coefficient, another family's coefficients under this name, a stale `coherent_gain_db` or `enbw_bins`; V9 a stale `enbw_hz`, `bin_width_hz` or `hop_samples` and `freq_max_hz` above Nyquist; V10 a dangling pointer and an out-of-range array index). Every case also asserts that **the rule that owns it fires**, so a rule the schema happens to shadow is still exercised: coverage spans V1–V10 and V6b | same script; run `--verbose` to list each case and what caught it |
| Rules V0–V10 recomputation | the derived constants in the file agree with the coefficients and with `(N, f_s, interval_ms)` to 1×10⁻⁶, and the bytes are the canonical form | same script (V0 is checked against the file's bytes, so it runs on the shipped presets only); also a `spectral_core` host test **(planned)**, because the C loader must reject the same files |
| Round-trip through the store | a preset written by the host, mounted on LittleFS and read by the watch hashes to the same sha256 | QEMU/target test (planned), with the take-transfer spec |
| Frame-rate feasibility | the `refresh_hz_target` of every watch preset is actually sustained | *Sustained refresh* and *Dropped-frame rate* rows of [`../../docs/validation/README.md`](../../docs/validation/README.md) — the phototransistor cross-check, not the firmware counter alone |
| `db_floor_dbfs` and `freq_max_hz` | the two provisional display numbers | [experiment 0001](../../docs/validation/experiments/0001-pdm-mic-in-situ-characterization.md); until it runs both stay in `provisional` |
