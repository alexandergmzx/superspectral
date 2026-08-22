// SPDX-FileCopyrightText: 2026 Alexander Gomez
// SPDX-License-Identifier: GPL-3.0-or-later
//
// Vitest configuration (ADR 0021 decision 2; roadmap W0/W1).
//
// Two projects, because they answer different questions and fail for different
// reasons:
//
//   unit   -- pure logic that needs nothing on disk: the licence evaluator, the
//             API client, and from W1 the DSP module's own invariants. Runs in
//             CI on every push.
//   golden -- the agreement suite of ADR 0021 decision 2: the TypeScript
//             implementation of the ADR 0006 conventions against the committed
//             `host/golden/outputs/tier0-synthetic` set, over the Tier-0 WAVs.
//
// THE GOLDEN PROJECT MUST FAIL LOUDLY WHEN THE TIER-0 WAVs ARE MISSING.
// datasets/tier0-synthetic/*.wav is gitignored (root .gitignore, "--- Datasets")
// and regenerated with:
//     cd python-scripts/synth_signals && \
//       uv run python -m synth_signals generate --out ../../datasets/tier0-synthetic
// A `describe.skipIf(!exists)` there would turn "the oracle disagrees" into a
// green run on any machine that had not regenerated the corpus -- which is
// exactly the failure mode ADR 0009 item 4 exists to prevent. The W1 helper
// therefore THROWS with the regeneration command in the message; it never skips.
// (Not implemented in W0: W0 ships no DSP. tests/golden/ holds only its README
// until W1, so `npm run test:golden` reports no test files rather than passing.)
// ----------------------------------------------------------------------------

import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    projects: [
      {
        test: {
          name: 'unit',
          // node, not jsdom: nothing under test touches the DOM yet. The DOM
          // suites arrive with the canvas work (W1/W2) and get their own
          // project rather than an environment flag flipped under these.
          environment: 'node',
          include: ['tests/unit/**/*.test.ts'],
        },
      },
      {
        test: {
          name: 'golden',
          environment: 'node',
          include: ['tests/golden/**/*.test.ts'],
        },
      },
    ],
  },
});
