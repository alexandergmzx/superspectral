# Overnight Phase-0 session — documentation only

> **APPROVED 2026-08-21 01:48 CST.** Budget 5 h 42 m — ends **07:30**, no new unit
> starts after **07:00**. Binding; the status table is updated after every unit;
> this file is the first thing re-read after any context compaction; the handback
> is its final section and is written even if the session fails early.
>
> **Operator is asleep.** `git push` does not exist tonight. Work happens on
> `overnight-2026-08-21`; `main` is not touched; `origin/main` must still be
> `4468334` at handback.

## Live status

| Unit | State | Notes |
|---|---|---|
| U0 session setup | **DONE** 02:20 | `06a4f74` — branch + this plan. **Correction:** workflow `w9e08cb66` did not survive the interrupt at 01:41:33 — three of its four study agents died mid-tool-call and the ADR phase never began. It was resumed as `wipguewn1` (the finished study replayed from cache). Absorbed: `22e425a` four D4 study notes (1,180 lines; the AXP2101 register table is the `twatch_bsp` driver specification) and `8015184` seven ADRs. The index now holds 12 records, backlog down to 0006–0012. Corrected one factual error in ADR 0004 while reviewing (it claimed the D3 history rewrite was cheap "because there is no remote yet"). |
| U3 D5 engineering ADRs (0009, 0010, 0011, 0012) | **DONE** 02:47 | `163592a`, `+1` — schema negative-tested (6/6 invalid presets rejected), every preset's ENBW/coherent gain recomputed from its own coefficients to 6e-8, colormap self-test runs. 0011/0012 **proposed**. |
| U4 D6 validation freeze (paper side) | **DONE** 01:58 | `d5f15e0` — GUM uncertainty budget (3 models; the sample-rate term is row 1 and the reference-mic term is what blocks an accuracy claim) + `datasets/corpora/manifest.yaml` pre-registering 6 corpora with quarantine consequences. Experiment 0001 was already at full recipe quality, so it needed no work. |
| U5 D3 acquisition follow-ups | **DONE** 02:05 | `fc41e7d` — both quarantines resolved (mir_eval was the wrong paper, now correct and committed; XL2 re-fetched whole). YIN + Sundberg 1994: 5xx twice each, paths closed. Added `python-scripts/check_links.py` as the commit gate. |
| U6 bibliography live-verification | **DONE** 02:21 | `3677960` — 430 URLs, 24 min of the 90-min box. 16 dead links replaced; **one cited DOI does not exist** (05 #23) and one author list is wrong (05 #44), both flagged without touching the numbers. Knowles and Bosch have delisted parts we depend on. |
| U7 D2 proposal prose (DRAFT) | **DONE** 02:21 | `44cb4e8` — §1–§7 filled, 199→370 lines, 12 synthesis claims corrected against measured facts, 150 citations verified, RQ byte-identical in all three places (independently checked). Also fixed `architecture/README.md`, which said FFT scratch goes to PSRAM. |
| U8 handback | **DONE** 03:55 | this file's final section. Written 3 h 5 m before the deadline because the queue emptied, not because it was rushed. |

**Queue extended 02:50.** All eight approved units closed four hours inside the
budget, so the following stretch units were added under the same rules. They are
additions, not substitutions: nothing in the approved queue was skipped to reach
them, and each is documentation of a decision already taken or a verification of
work already committed — no new science, no new scope.

| Unit | State | Notes |
|---|---|---|
| U9 architecture documents (01 overview, 02 audio capture, 03 DSP pipeline, 06 power budget) | **DONE** 03:07 | `dd9939b` — 773 lines. Pure synthesis of accepted ADRs and measured facts; every open question carries an `OQ` number and an owner. |
| U10 self-review sweep | **DONE** 03:55 | `a75b0ca` … `bd3c5b1` (11 commits). An adversarial re-read of everything committed tonight produced **4 blockers, 12 majors, 14 minors and 5 nits**; every one is fixed, none deferred. The two worst were factual: the 1.8 V flash correction had survived in eleven files, and the real-8192 FFT figure was wrong because `dsps_cplx2real_fc32` drags in the radix-4 twiddle table. Two findings were repairs to the gates themselves — a pre-commit hook that could never pass, and a spec reporting results from a script that did not exist. |

**Out of scope by the operator's decision (01:55):** U1 (promote the gate's bring-up
into `twatch_bsp`) and U2 (`spectral_core` v0 + host golden tests). No firmware
source is written tonight. Both are the first engineering units in the morning.

## Context

Phase 0 stands at: scaffold + bibliography (D0/D1), ESP-IDF v6.0.2 environment with
the gate passed on hardware (E1), first contact with the watch (E2), experiment 0002
validated, ADRs 0001 and 0014–0017 accepted, D3 first acquisition pass filed. CI is
green on `4468334` (docs, links, python, and the three gating firmware configs plus
the analyzer, which became blocking once [ADR 0017](../adr/0017-no-radio-in-v1-trimmed-component-set.md)
trimmed the component set).

Two facts constrain tonight:

1. **The watch is connected and powered but is not touched.** Unattended rule: no
   `esptool`, `espefuse`, `idf.py flash`/`monitor`, `tools/flash.sh`, serial opens or
   OpenOCD. The gate firmware currently in `ota_0` stays as it is.
2. **A workflow was already running when the session began** — `w9e08cb66`, writing
   D4 reference-project study notes and seven ADRs (0002, 0003, 0004, 0005, 0013,
   0018, 0019) into the working tree. It was launched against `main`'s tree; its
   output is absorbed on this branch in U0. It must be allowed to finish, not
   restarted.

## Rules in force tonight

- **git is local-only.** No push, no PR, no remote branch, no fetch-and-merge.
- **Append-only history.** One concern per commit, `[Un]` in the subject. Never
  amend, rebase, `reset --hard`, `clean -fd`, or delete a branch. A wrong commit is
  repaired by a new commit that says it repairs it.
- **A commit is a green checkpoint or it doesn't happen.** Green tonight:
  link checker → 0 broken; `compileall` over `python-scripts/`; `doc_ocr` pytest;
  and, if anything under `firmware/` is touched, `idf.py build` **and** the analyzer
  configuration both clean plus the four local hook scripts. Work that cannot reach
  green stays uncommitted and is named in the handback.
- **No hardware.** See Context #1.
- **Bounded retries.** The same command failing twice for the same reason closes that
  path: record it, move on.
- **Park, don't decide.** Science and preference calls are drafted `proposed` or
  listed under "Morning decisions" — never silently accepted.
- **Subagents** may write files; they are told *no git, no hardware, no network
  writes*. The orchestrator alone commits.
- `date` between units; no new unit after 07:00.

## Unit queue

| # | Unit | Box | Gate |
|---|---|---|---|
| U0 | **Session setup.** Branch, `docs/session-plans/` + this plan; wait out workflow `w9e08cb66`, run its verifier's findings through a fix pass, commit its output. | 45 m | ADR index lists each new record once, sorted; link check 0 broken; plan committed. |
| U3 | **D5 engineering ADRs.** 0009 golden-file strategy (+ `host/golden/manifest.schema.yaml`), 0010 preset schema (+ `protocols/specs/preset-schema.md`, `presets.schema.json`, the six presets as JSON), 0011 colormap (+ `python-scripts/gen_colormap_lut.py`, ADR `proposed`), 0012 hands-free interaction (design note, ADR `proposed`). | 75 m | Presets validate against the schema; index updated; links resolve. |
| U4 | **D6 validation freeze, paper side.** Experiment 0001 to full recipe; `docs/validation/uncertainty-budget.md` (JCGM 100 shape); `datasets/manifest.yaml` for the Tier-1 CC BY corpora. | 60 m | Files lint; manifest parses; links resolve. |
| U5 | **D3 follow-ups (network reads only).** The two quarantined items re-fetched correctly, the two transient failures retried ×2; file, extract, stamp, ledger. | 30 m | Each item OK or ledgered with its final tag; `doc_ocr verify` clean. |
| U6 | **Bibliography live-verification** (agent, hard 90-minute box). Every "(verify)" or model-recalled DOI/URL in 01–11 checked by fetching the page (never a PDF); dead links fixed; Disclosure wording flipped recalled → verified where true. | 90 m | Disclosures say what was verified tonight and when; 0 broken links; no content claim changed without a source. |
| U7 | **D2 proposal prose — DRAFT.** §1–§7 filled from the syntheses and the measured facts; every unsettled number `(prov.)`; header says DRAFT. | 45 m | RQ verbatim unchanged; links resolve. |
| U8 | **Handback.** | 30 m | Written even if everything above is partial. |

Skip-edges: U5 and U6 are network-bound and run as background agents alongside U3
and U4. U7 is last because it is the least verifiable. If a unit blocks, it is
parked with its reason rather than retried past the bounded-retry rule.

## Verification

```sh
python3 python-scripts/check_links.py      # relative links + #anchors, path:line, exit 1 if broken
python3 python-scripts/check_presets.py    # schema + loader rules V0-V10 + the negative suite
python3 -m compileall -q python-scripts
(cd python-scripts/doc_ocr && python3 -m pytest -q)
```

*(The inline heredoc this section originally carried was superseded in U5 by
`check_links.py` and improved again in U10; it only ever saw tracked `.md` and
had a known false positive on `docs/OCR/README.md`'s code-span example, which the
committed tool does not.)*

At handback: `git log --oneline main..overnight-2026-08-21`, `git status`, and
`git rev-parse origin/main` (must still be `4468334`).

## Not delegated — parks to the handback

- `git push`, PRs, merging into `main`, any history rewrite.
- **Firmware source**: U1 (gate bring-up → `twatch_bsp`) and U2 (`spectral_core` +
  host golden tests), by the operator's scope decision.
- Touching the watch: first flash of promoted firmware (to `ota_1` via
  `tools/flash.sh`, with the operator present), experiment 0001 on hardware, the
  ST7789 scroll-axis check (ADR 0007), the 48 kHz PDM clock tolerance test
  (ADR 0003 trigger).
- The operator's shell: deleting the legacy IDF trees, `direnv allow`, the udev rule.
- Science and product decisions: FFT conventions (0006), ring/twang metric (0008),
  colormap (0011), interaction model (0012), proposal claims, metric targets —
  drafted `proposed`, decided in the morning.
- Anything paid or requiring an account.

---

# HANDBACK

**Written 2026-08-21 03:55 CST.** Ten units done — the eight approved plus two
stretch units — 3 h 35 m inside the budget. Nothing was pushed. `main` is
untouched, `origin/main` is still `4468334`, and `git status` is clean.

## Headline

**Phase 0's documentation is complete, and then it was audited.** Thirty-four
commits on `overnight-2026-08-21`: 99 files, +7,306 / −353. Eleven ADRs written
(nine accepted, two `proposed` because they are yours to decide), the preset
protocol and the golden-file contract specified, four reference projects read at
pinned revisions, five architecture documents written, and the bibliography's
430 URLs verified live.

Then U10 re-read all of it adversarially and found **35 defects** — 4 blockers,
12 majors, 14 minors, 5 nits. All 35 are fixed on this branch. That number is
the honest headline: the writing was good and the checking found real errors in
it anyway, including two that had already been "corrected" once and had survived
the correction.

## Green

Every commit is a green checkpoint. Re-verified at handback:

| Check | Result |
|---|---|
| `python3 python-scripts/check_links.py` | **124 files, 0 broken** (was 110 files before U10 widened it) |
| `python3 python-scripts/check_presets.py` | **PASS** — 6/6 presets accepted, 41/41 negative cases rejected |
| `python3 -m compileall -q python-scripts` | clean |
| `doc_ocr` pytest | **25 passed** |
| `idf.py build` (twatch-s3, default) | exit 0, **zero warnings** |
| analyzer configuration | exit 0, **zero warnings** |
| `idf.py build` (idf-gate) | exit 0, zero warnings |
| `no-usb-pins`, `pins-h`, `sdkconfig-invariants`, `partitions-arithmetic`, `spdx-header` | all rc=0, run by hand over the whole tree |
| `git rev-parse origin/main` | `4468334` — nothing pushed |

## Red

Nothing is red. Two things are *unfinished rather than broken*, and both were
out of scope by your 01:55 decision:

- **U1** — promote the E1 gate's bring-up code into `twatch_bsp`.
- **U2** — `spectral_core` v0 plus the host golden tests.

They are the first engineering units of the morning. No firmware source was
written tonight; the only files touched under `firmware/` are comments, SPDX
headers and one `sdkconfig` comment, and all three builds were run to prove it.

Three things could not be done here and are yours:

1. ~~**parselmouth is not installed**~~ — **closed 2026-08-21, and it should not have
   been listed here.** `uv` and `pipx` were already on the machine; installing into
   `host/.venv` was one command inside the licence boundary. Doing it showed the
   handback's own premise was wrong: parselmouth 0.4.7 bundles **Praat 6.1.38**, which
   has no filtered autocorrelation at all, so U10's "correction" of the golden example
   to `method: filtered` (commit `e31df9a`) moved it *away* from what any generator can
   produce. Reversed; ADR 0009 amended; T7 split into T7a (closed) and T7b (open, needs
   an out-of-process praat.org binary).
2. ~~**`pre-commit` is not installed**~~ — **closed 2026-08-21** (`pipx install pre-commit`,
   4.6.2). `pre-commit install`, which writes `.git/hooks`, is still the operator's call.
3. **The watch was not touched**, per the unattended rule. It is still running
   the E1 gate firmware in `ota_0`.

## Commits

| Unit | Commit | What |
|---|---|---|
| U0 | `06a4f74` | the session plan |
| U0 | `22e425a` | D4 study notes ×4 (1,180 lines) |
| U0 | `bd44ec3` | plan: notes absorbed |
| U0 | `8015184` | ADRs 0002, 0003, 0004, 0005, 0013, 0018, 0019 accepted |
| U0 | `36d0f0a` | three committed claims the study proved wrong |
| U0 | `efd5127` | plan: U0/U6/U7 done |
| U5 | `fc41e7d` | both quarantined acquisitions resolved; two 5xx paths closed |
| U5 | `279fadd` | plan: the pre-session workflow died at the interrupt |
| U4 | `d5f15e0` | GUM uncertainty budget + pre-registered corpus manifest |
| U4 | `2656156` | plan: status after U4 |
| U4 | `e271470` | the calibrator row cites the instrument certificate, not a recalled standard |
| U4 | `9a2fd52` | roadmap ticked to what actually closed |
| U7 | `44cb4e8` | proposal §1–§7 drafted (199 → 370 lines) |
| U6 | `3677960` | 430 URLs verified live; 16 dead links replaced; one DOI found not to exist |
| U3 | `3211ed6` | plan: U3 started |
| U3 | `163592a` | ADRs 0009–0012 with their artefacts |
| U3 | `28efd79` | LVGL screenshot harness needs the direct call |
| U3 | `97b9e7f` | plan: queue extended with U9 and U10 |
| U3 | `f7337c9` | `host/golden/README.md` aligned with the normative schema |
| U9 | `dd9939b` | architecture 01, 02, 03, 06 (773 lines) |
| U10 | `a75b0ca` | the 1.8 V correction swept into eleven files |
| U10 | `96b3639` | FFT memory figures corrected from esp-dsp's allocation sites |
| U10 | `f59c551` | seven findings: SRAM table, sc16 arithmetic, `fft4real`, `clinical_claim` |
| U10 | `25edf38` | status hygiene: accepted ADRs stop being called "backlog" |
| U10 | `701db47` | `check_presets.py` written, so the spec stops reporting a script that did not exist |
| U10 | `e31df9a` | the golden example pinned *raw* thresholds under `method: filtered` |
| U10 | `20f9669` | firmware comment corrections + two pre-commit hooks that could never pass |
| U10 | `7e49a4c` | `enbw_hz` rounded not truncated; V2's 48 kHz ban moved into the schema |
| U10 | `8f2b945` | six minors, including a licence boundary that was not quite one `grep` |
| U10 | `8aed606` | 43 ADR links repointed; Saarbrücken corpus pre-registered |
| U10 | `055779a` | five citation minors: every number under an address that carries it |
| U10 | `82fddc5` | five nits, and a link checker that reports *where* |
| U10 | `bd3c5b1` | the last three 1.8 V stragglers; OQ11 closed |
| U8 | *this commit* | CHANGELOG entry + handback |

## The five findings worth your attention

1. **The 1.8 V flash correction did not take the first time.** ADR 0016 recorded
   it on 2026-08-20; eleven files still asserted the old claim, and three more
   turned up in the final sweep — including `twatch_pins.h`, which was still
   telling an implementer that *no code may touch GPIO45*. A correction is not
   done when the record is written; it is done when the sweep is clean. Related:
   `BOOTLOADER_VDDSDIO_BOOST_1_9V` is **inert** on this unit — IDF's own Kconfig
   says it has no effect when VDD_SPI is 3.3 V.
2. **Real-8192 does not cost 112 KB.** `dsps_cplx2real_fc32` requires
   `dsps_fft4r_init_fc32`, whose table is `16·N_c` bytes, **even on the radix-2
   path**. So it is ≈ 160 KB on esp-dsp's tables, or ≈ 104 KB if we write our own
   `cplx2real` (which needs `4·(N_c+2)` bytes instead of 65,536). That is a real
   architectural choice and it belongs to ADR 0006.
3. **Two gates were decorative.** `check_presets.py` did not exist, yet the spec
   reported its results as measurements; and the `no-usb-pins` pre-commit hook
   flagged the `_Static_assert` that enforces the rule, so the tree could never
   be committed clean. Both are now real: the checker is written and wired into
   CI, and the hook reads code instead of message text. Recorded as pitfalls G20
   and G21.
4. **The `sc16` rejection was argued backwards.** "N = 2048 loses ≈30 dB and
   N = 8192 ≈18 dB" — a larger FFT cannot lose *less* under one-bit-per-stage. It
   is ≈ 60 dB and ≈ 72 dB, and the case should be made against the 90–100 dB
   per-bin range the presets ask for, not the microphone's 61.5 dB(A) SNR. The
   corrected argument is *stronger*.
5. **The golden-file example was the trap ADR 0009 exists to close.** It pinned
   `method: filtered` next to `silence 0.03 / voicing 0.45 / octave 0.01` — the
   *raw* defaults. Both sets are now recorded with their source URLs and read
   date.

## Morning decisions — yours, not mine

| # | Decision | Where it is parked |
|---|---|---|
| 1 | **ADR 0011 — spectrogram colormap.** cividis vs viridis vs a custom map; whether ordered dithering is on. A perception judgement, and the panel has never been photometered. | [ADR 0011](../adr/0011-spectrogram-colormap.md), `proposed` |
| 2 | **ADR 0012 — hands-free interaction.** The take state machine and where touch is refused. A UX judgement. | [ADR 0012](../adr/0012-hands-free-interaction.md), `proposed` |
| 3 | **ADR 0006 — FFT conventions.** Now has a concrete sub-question: do we pay esp-dsp's 64 KB radix-4 twiddle table, or write our own `cplx2real` and save `6·N`? | backlog; [03-dsp-pipeline §4.1](../architecture/03-dsp-pipeline.md) |
| 4 | **ADR 0007 — display path** and **ADR 0008 — ring/twang metric.** Untouched tonight. | backlog |
| 5 | **The proposal is a DRAFT and says so.** §1–§7 are filled and every claim is cited, but the voice is mine, not yours. | [`docs/proposal/01-…`](../proposal/01-super-spectral-proposal.md) |
| 6 | **05 #23's DOI does not exist** and 05 #44's author list is wrong. Flagged, not silently changed — a bibliography entry is a claim about the record. | [05-papers](../bibliography/05-papers.md) |
| 7 | **The Saarbrücken corpus is quarantined** on `unstated-terms`. Someone has to read its Terms & Conditions page before anything from it reaches a number. | [`datasets/corpora/manifest.yaml`](../../datasets/corpora/manifest.yaml) |

## Before you push

1. Read this file and the two `proposed` ADRs (0011, 0012).
2. Skim the proposal draft — it is the only artefact written in a voice that
   should be yours.
3. Spot-check three of U10's factual corrections against their sources: the
   `ef 4018` JEDEC read, the esp-dsp allocation sizes, the Praat defaults.
4. `pip install pre-commit && pre-commit install && pre-commit run -a`. The
   hooks have never run under `pre-commit` itself; two were repaired tonight by
   running them by hand, and `pre-commit run -a` is the first real test of the
   rest.
5. Then, and only then:

```sh
git switch main
git merge --no-ff overnight-2026-08-21 -m "Phase 0 documentation: ADRs, preset protocol, golden-file contract, reference-project study, and the audit that followed"
git push origin main
```

If you would rather review it as a diff first:

```sh
git log --oneline main..overnight-2026-08-21
git diff --stat main..overnight-2026-08-21
git diff main..overnight-2026-08-21 -- docs/proposal/
```

Nothing on this branch depends on being merged tonight. The branch is
self-contained, `main` is exactly where you left it, and every commit says what
it repairs.
