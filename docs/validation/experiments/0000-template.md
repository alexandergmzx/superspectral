# <Subsystem>: <what was tested>

**Date:** YYYY-MM-DD · **Status:** planned | running | validated on bench | validated in use | failed (see interpretation)

## What changed / hypothesis

Lead with the invariant ("No firmware code changed: the …") or, for a planned experiment, the falsifiable hypothesis in one sentence with its numeric threshold. Then the exact run command:

```sh
# from the repo root, inside `direnv`
…
```

## Provenance

| | |
| --- | --- |
| Inputs | `<path>` (sha256 `<64 hex>`), … |
| Firmware | commit `<sha>`, `PROJECT_VER` `<git describe>`, `sdkconfig.ci.<variant>` |
| ESP-IDF | `v6.0.2` @ `<sha>`; `env.lock.md` sha256 `<…>` |
| Instruments | `<model> s/n <…>`, calibration `<date>` |
| Corpus manifests | `datasets/<corpus>/manifest.yaml` sha256 `<…>` |

## Licensing status (read before citing the result)

| Artefact | Licence | Status |
| --- | --- | --- |
| `<corpus / weights / binary / standard>` | `<SPDX or terms>` | ✅ clean · ⚠️ restricted / unverified |

**Practical read:** what this result may be used for (bench evidence, a design decision) and what it may **not** be used for (a headline figure, a claim in an application) — and why.

## Scope caveat

What this experiment cannot observe, in one paragraph.

## Hypothesis / Setup / Pass–fail *(planned experiments; keep as pre-registration once run)*

- **Hypothesis:** …
- **Setup:** geometry, signals, instruments, firmware configuration, number of repetitions.
- **Pass:** … **Fail:** … **If it fails:** the pre-committed consequence (roadmap §4 threshold, ADR amendment, or target restatement).

## Evaluation

### `<condition>` — `<N>` trials / `<instrument>` / `<path>`

| factor | metric | value | notes |
| --- | --- | --- | --- |
| … | … | **headline** | `injection` / `acoustic` / preset · secondary metrics separated by ` · ` |

### Baseline (`<naive method / datasheet expectation / previous firmware>`)

The quantified arm the headline is compared against. Mandatory.

### Wire-path smoke test

Input set → path → assertions → latency, as a short paragraph.

## Interpretation and follow-up

- What the number is **not** good for.
- Which roadmap row / ADR / metric this closes or moves.
- The next experiment it motivates.
