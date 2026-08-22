# Experiments

One file per experiment, numbered `NNNN-kebab-title.md`, append-only. An experiment is anything that produces a number someone might later cite: a bench characterization, a safety test, a model or firmware swap, a regression run. The report exists so that a third party can repeat it and so that the number's *provenance and limits* travel with it.

| # | Experiment | Status | Phase | Produces |
|---|---|---|---|---|
| [0000](0000-template.md) | Template | — | — | the section order below |
| [0001](0001-pdm-mic-in-situ-characterization.md) | PDM microphone in-situ characterization through the watch case | planned | Phase 1 | the mic EQ filter; LF corner; EIN; 3.072 MHz verdict; DC offset; resonance map |
| [0002](0002-rollback-and-boot-guard-race.md) | OTA rollback and boot-guard race | validated 2026-08-21 (window clause open) | E2 week 1 | proof that the recovery path works before any feature code |
| 0003 | ST7789V3 hardware scroll axis vs `MADCTL` (reserved 2026-08-22; hardware, parked until the DoD gate — gates ADR 0007) | reserved | M1 | whether the analyzer canvas may bypass LVGL with the panel's vertical scroll |
| 0004 | M0 bring-up on `ota_1`: PDM capture → FFT → first spectrum frame (reserved 2026-08-22; hardware, parked) | reserved | M0 | the first end-to-end latency and refresh numbers, both `(prov.)` until 0001 |
| [0005](0005-t7b-bundled-praat-vs-praat-org.md) | Golden files: bundled Praat 6.1.38 vs praat.org 7.0.01 (threshold T7b) | planned | H0 *(historical label: host milestones are **W**-numbered since [ADR 0021](../../adr/0021-host-web-application.md) — H-numbers are the roadmap's hardware questions and are not reused)* | version drift and method drift of the Praat reference, measured separately |
| [0006](0006-web-capture-chain-linearity.md) | Host web application: capture-chain linearity per browser and OS | planned | W1 | the **unprocessed / processed** verdict that travels with every acoustic number the web application reports |
| [0007](0007-web-latency-and-refresh.md) | Host web application: microphone-to-pixel latency and sustained refresh | planned | W2 | browser latency and refresh — **measured, never claimed**; reported beside the watch's ≤ 80 ms row, never inside it |

## Section order (generalized from swarm's `detector-smoke-model.md`)

1. **Title line** — `# <Subsystem>: <what was tested>`, then `**Date:** YYYY-MM-DD · **Status:** planned | running | validated on bench | validated in use | failed (see interpretation)`.
2. **What changed / hypothesis** — lead with the invariant ("No firmware code changed: …") or, for planned experiments, the falsifiable hypothesis; then the exact run command.
3. **Provenance** — a keyless two-column `| | |` table: inputs with sha256, firmware commit and `PROJECT_VER`, ESP-IDF tag + SHA, `env.lock.md` hash, instrument serials and calibration dates, corpus manifest hashes.
4. **Licensing status** — every artefact used (corpus, weights, vendor binary, standard) with its licence and a ✅ / ⚠️ verdict, followed by a `**Practical read:**` paragraph stating what the result may and may not be used for.
5. **Scope caveat** — what this experiment cannot see (the analogue of "what a camera can and cannot see").
6. **Evaluation** — result tables whose headings carry the full experimental condition, the headline number bolded, secondary numbers in a `notes` column, every operating point annotated with the system path it models (`injection`, `acoustic`, `live_singing preset`); **a quantified baseline arm is mandatory** (the naive method, the datasheet expectation, the previous firmware — something the new number is compared against).
7. **Wire-path smoke test** — separate from the metric evaluation; input set → path → assertions → latency.
8. **Interpretation and follow-up** — what the number is **not** good for, and the next experiment it motivates.

**Gotchas** are written as bold callouts with their cost and their false-result signature — `**<Name> trap (cost an hour):** … <what the wrong answer looks like> … Any future <X> must pin this.` — and mirrored into the relevant script docstring and subsystem README.

Planned experiments carry a **Hypothesis / Setup / Pass–fail** block in place of sections 6–8 until they run; when they run, the block is kept as the pre-registration and the results are appended below it.
