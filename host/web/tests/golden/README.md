<!-- SPDX-FileCopyrightText: 2026 Alexander Gomez -->
<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# `tests/golden/` — the agreement suite (arrives at W1)

Empty on purpose in W0: the milestone ships no DSP, so there is nothing to hold
to the oracle yet. `npm run test:golden` therefore reports *no test files*
rather than passing, and the CI `web` job runs `--project unit` only.

At [W1](../../../../docs/roadmap/documentation-roadmap.md) this directory holds
the suite of [ADR 0021](../../../../docs/adr/0021-host-web-application.md)
decision 2: the TypeScript implementation of the
[ADR 0006](../../../../docs/adr/0006-fft-normalisation-and-window-conventions.md)
conventions, run over the Tier-0 WAVs and compared to the committed
`host/golden/outputs/tier0-synthetic` set — window-table digest **exact** per
`(family, N)`, per-bin magnitude within `0.01 dB` `(prov.)` on bins ≥ −80 dBFS,
interpolated peak frequency ≤ 3 cents.

**It must fail loudly when the Tier-0 WAVs are missing.** They are gitignored
and regenerated with

```sh
cd python-scripts/synth_signals
uv run python -m synth_signals generate --out ../../datasets/tier0-synthetic
```

A `describe.skipIf(!exists)` here would turn *the oracle disagrees* into a green
run on any machine that had not regenerated the corpus — the exact failure mode
[ADR 0009](../../../../docs/adr/0009-golden-file-strategy.md) item 4 exists to
prevent. The W1 loader throws with that command in the message; it never skips.
