# Presets

The six preset instances of [ADR 0010](../../docs/adr/0010-preset-schema.md), one JSON file per preset. Field reference and loader rules: [`../specs/preset-schema.md`](../specs/preset-schema.md). Machine-readable schema: [`../specs/presets.schema.json`](../specs/presets.schema.json) (JSON Schema draft 2020-12).

These files are **data, in canonical form** — UTF-8, LF, one trailing newline, keys sorted by code point, two-space indent. The LittleFS `presets` partition stores them byte-for-byte and `TAKE_HEADER` names one by `id` plus the sha256 of exactly these bytes, so reformatting a file orphans every take that referenced it. Edit through the host writer, or edit by hand and re-run the canonical-form check.

| File | Targets | N | Window | Hop | Refresh | ENBW |
|---|---|---:|---|---:|---:|---:|
| [`live_singing.json`](live_singing.json) | watch, host | 4096 | blackman_harris | 20 ms | 50 Hz | 15.659008 Hz |
| [`vowel_formant_study.json`](vowel_formant_study.json) | watch, host | 8192 | hann | 40 ms | 25 Hz | 5.859375 Hz |
| [`sustained_pitch_lab.json`](sustained_pitch_lab.json) | watch, host | 8192 | blackman_harris | 40 ms | 25 Hz | 7.829504 Hz |
| [`diction_consonants.json`](diction_consonants.json) | watch, host | 1024 | hann | 10 ms | 50 Hz | 46.875 Hz |
| [`room_noise_floor.json`](room_noise_floor.json) | watch, host | 8192 | hann | 40 ms | 25 Hz | 5.859375 Hz |
| [`stem_analysis.json`](stem_analysis.json) | **host** | 8192 | hann | 10 ms | — | 8.789062 Hz |

All six run at 32 kHz except `stem_analysis` (48 kHz, host-only — the 48 kHz gate is on the capture path, and the host reads files); all six have `decimations: 0` and `mic_eq: {"mode": "none"}`, because the decimation cascade and the fitted microphone EQ do not exist yet. Fields still `(prov.)` are listed inside each file's own `provisional` array.
