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
| U3 D5 engineering ADRs (0009, 0010, 0011, 0012) | pending | |
| U4 D6 validation freeze (paper side) | **DONE** 01:58 | `d5f15e0` — GUM uncertainty budget (3 models; the sample-rate term is row 1 and the reference-mic term is what blocks an accuracy claim) + `datasets/corpora/manifest.yaml` pre-registering 6 corpora with quarantine consequences. Experiment 0001 was already at full recipe quality, so it needed no work. |
| U5 D3 acquisition follow-ups | **DONE** 02:05 | `fc41e7d` — both quarantines resolved (mir_eval was the wrong paper, now correct and committed; XL2 re-fetched whole). YIN + Sundberg 1994: 5xx twice each, paths closed. Added `python-scripts/check_links.py` as the commit gate. |
| U6 bibliography live-verification | **DONE** 02:21 | `3677960` — 430 URLs, 24 min of the 90-min box. 16 dead links replaced; **one cited DOI does not exist** (05 #23) and one author list is wrong (05 #44), both flagged without touching the numbers. Knowles and Bosch have delisted parts we depend on. |
| U7 D2 proposal prose (DRAFT) | **DONE** 02:21 | `44cb4e8` — §1–§7 filled, 199→370 lines, 12 synthesis claims corrected against measured facts, 150 citations verified, RQ byte-identical in all three places (independently checked). Also fixed `architecture/README.md`, which said FFT scratch goes to PSRAM. |
| U8 handback | pending | mandatory, starts 07:00 at the latest |

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
# link checker (stdlib; the docs/OCR/README.md code-span example is its one known
# false positive, which CI's lychee does not share)
python3 - <<'PY'
import re, os, urllib.parse
tracked = os.popen("git ls-files '*.md'").read().split()
bad = 0
for f in tracked:
    for m in re.finditer(r'(?<!`)\]\(([^)\s]+)\)', open(f, encoding='utf-8').read()):
        t = m.group(1)
        if re.match(r'https?:|mailto:|#', t):
            continue
        t = urllib.parse.unquote(t.split('#')[0])
        if t and not os.path.exists(os.path.join(os.path.dirname(f), t)):
            bad += 1
            print('BROKEN', f, '->', t)
print('broken:', bad)
PY
python3 -m compileall -q python-scripts
(cd python-scripts/doc_ocr && python3 -m pytest -q)
```

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

*(written in U8; if this section is missing, the session was killed rather than
finished, and the branch's commit log is the record)*
