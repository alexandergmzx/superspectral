# Daytime session — close what was parked, then re-audit the lot

> **Started 2026-08-21 12:20 CST**, on the operator's return. Branch
> `overnight-2026-08-21` (continued, not forked). `main` untouched, `origin/main`
> still `4468334`, nothing pushed. Same unattended rules as the overnight session
> ([`2026-08-21-overnight-phase0.md`](2026-08-21-overnight-phase0.md)), plus two
> new ones written into the rules section below.

## Why this session exists

The overnight session declared itself finished at 03:55 with four items handed
back as *"decisions for the owner"*. Three of them were not decisions:

| Handed back as | What it actually was |
|---|---|
| "parselmouth is not installed" | one `uv` command, inside the licence boundary |
| "someone has to read the Saarbrücken Terms & Conditions page" | there is no such page; the licence is one Zenodo API call away |
| 05 #23's dead DOI and 05 #44's author order | one CrossRef call each — and the previous pass had already *found* both and chosen to flag rather than fix |

The operator's verdict was that this was laziness, and it was. Worse, closing
them proved the overnight session had not merely *deferred* those three — it had
**got two of them wrong in the other direction**, and one of its own
"corrections" had inverted a true fact. Those are recorded below, because a
session that only reports what it fixed is the same failure again.

## Decisions taken by the operator (12:20)

1. **The firmware gate stays.** CLAUDE.md says firmware beyond stubs is out of
   scope until the Phase-0 DoD is green; four of those boxes are his. Nothing
   under `firmware/` is written beyond comments, and the DoD work I *can* do
   (ADR 0006, the ledger sync) is done instead.
2. **Same branch, merge after the re-audit.**
3. **T7 anchor = raw autocorrelation on Praat 6.1.38, in process.** The only
   reachable option; T7b (praat.org 7.0.01, out of process) is an experiment.
4. **No hardware today.** Hardware units stay recipes.

## Rules in force

Everything from the overnight session, and two additions that come directly from
its failures:

- **Nothing is "verified" by an HTTP 200.** Only a registry or catalogue record,
  a datasheet page, a source line at a pinned revision, or running the code. The
  Disclosure says which.
- **The writer does not grade the work.** Every verification pass is followed by
  an *adversarial* pass that re-fetches the endpoints, and every finding from
  that pass is re-verified before it is applied. This session ran that loop three
  times and it caught something every time — including a "fix" that would have
  put a false denial into a document ADR 0005 depends on.

## Live status

| Unit | State | Notes |
|---|---|---|
| A0 GPL environment | **DONE** | `4cd9926` — `host/pyproject.toml` + `uv.lock` + `REUSE.toml`; `host/.venv` created. **parselmouth 0.4.7 → Praat 6.1.38**, measured. Also the first time `manifest.schema.yaml` was ever loaded by a validator (`check_schema` PASS, worked example 0 errors). |
| A1 T7a + ADR 0009 | **DONE** | `13ab640` — **reverses** the overnight U10 commit `e31df9a`. No released parselmouth can run `To Pitch (filtered autocorrelation)`; the golden pin is `method: raw`. Invariant 6 added. Separately: preset `nuttall` has **no** SciPy name (0.0163 from SciPy's), so the window oracle must build from coefficients, not names. |
| A2 bibliography 05 | **DONE** | `f25539a` — #23's companion is `10.1121/1.4944474`, *JASA* **139(3), 1404–1410** (wrong on DOI, issue *and* pages); #44 is Wang, Müller, Caffier, Caffier; #47 is CC BY-NC-ND 4.0; #6's pages confirmed as cited. |
| A3 Saarbrücken | **DONE** | `e759115` — **CC BY 4.0** (Zenodo 16874898). Quarantine lifted. Counts recomputed from the site's index CSV: 2 225 sessions / 1 853 speakers / 71 labels in 186 combinations. ADR 0005's "1 356 patients" was **sessions**. |
| A4 filed datasheets | **DONE** | `a0f205b` — DRV2605L timings and currents; ALDO3 (and the finding that the **ST7789V3 spec's own current table is `TBD` in every cell**); GATECTRL `E4h` confirmed; ESP32-S3 strapping Table 3-1. A third `TBD` class introduced: `TBD (acquisition)`, for the BMA423 figures Bosch has delisted. |
| D ADR 0006 | **DONE** | `821fb33` — written, `proposed`. Closes the last named ADR line of the DoD. Own `cplx2real` decided on source evidence; OQ1/2/3/4/7/8/9/12/13 closed or routed; ADR 0020 allocated. |
| A5 `(verify)` sweep | **DONE** | `20d14ab`, `0fdc9d0`, `2996ac2` — 4 files swept, then audited, then the audit findings re-verified and applied. **The audit caught a false denial** (FDA #34) and a link that would have sold the operator the withdrawn edition of ISO 9241-112. |
| A7 marker gate | **DONE** | `26cdf93`, `ea2d76c` — `check_markers.py` + closed/allowed lists with **owners**. Mutation-tested both ways. |
| A6 `pre-commit run -a` | **DONE** | `f1e963f` — first full run: 21 hooks, 5 with findings, all addressed. All five local guard hooks passed first try. |
| R re-audit | in progress | 12 lots, claim-by-claim against primary sources, every finding adversarially refuted before it is trusted. |
| Handback | pending | final section of this file. |

## What the loop caught that nobody had flagged

Recorded because these are the ones that argue for the method, not for the
diligence:

1. **The overnight "fix" was backwards.** `e31df9a` changed the golden example's
   thresholds to Praat's *filtered* defaults. Correct against the manual; impossible
   against the library. Only installing parselmouth revealed it.
2. **A false denial, caught by the adversary.** A sweep agent concluded from the
   Federal Register API that FDA's September 2019 revision did not exist. The
   guidance's own cover page names it. Retracted — and since ADR 0005 leans on
   that guidance, the current (2026-01-06) edition was then read in full to
   confirm the constraint survives. It does.
3. **A causal explanation that the bytes disprove.** The registry labels
   `joltwallet/littlefs` 1.22.2+ "Custom"; a sweep explained it as the licence
   text omitting the MIT title line. All five per-version `license.txt` blobs are
   byte-identical (`b6bbf3bd17c2b553…`, 1057 B). Recorded as an anomaly instead.
4. **A behavioural claim carried across from the wrong branch.** `pytest_i2s_record.py`
   at `v6.0.2` is 13 lines of log assertions; the WAV-reconstructing test is on
   `master`. The claim had been stamped with a directory listing, which cannot
   evidence file contents.
5. **A licence deleted as wrong that was right.** Saraga *is* mixed-licence —
   CC BY-NC 4.0 corpus, AGPL-3.0 code, per the project's own `LICENSE.md`. Only
   the Zenodo deposit field says NC-SA.
6. **My own regression guard, matching the wrong thing.** The first five patterns
   in `markers-closed-2026-08-21.tsv` all fired — on the *explanations* of the
   corrections. A regression guard must match the defect, not its obituary.

---

# HANDBACK

*(written at the end of this session; if this section is empty the session was
killed rather than finished, and the branch's commit log is the record)*
