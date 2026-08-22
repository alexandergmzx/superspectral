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
| A0 GPL environment | **DONE** | `376727e` — `host/pyproject.toml` + `uv.lock` + `REUSE.toml`; `host/.venv` created. **parselmouth 0.4.7 → Praat 6.1.38**, measured. Also the first time `manifest.schema.yaml` was ever loaded by a validator (`check_schema` PASS, worked example 0 errors). |
| A1 T7a + ADR 0009 | **DONE** | `69b7b41` — **reverses** the overnight U10 commit `fab6121`. No released parselmouth can run `To Pitch (filtered autocorrelation)`; the golden pin is `method: raw`. Invariant 6 added. Separately: preset `nuttall` has **no** SciPy name (0.0163 from SciPy's), so the window oracle must build from coefficients, not names. |
| A2 bibliography 05 | **DONE** | `1784749` — #23's companion is `10.1121/1.4944474`, *JASA* **139(3), 1404–1410** (wrong on DOI, issue *and* pages); #44 is Wang, Müller, Caffier, Caffier; #47 is CC BY-NC-ND 4.0; #6's pages confirmed as cited. |
| A3 Saarbrücken | **DONE** | `cffd679` — **CC BY 4.0** (Zenodo 16874898). Quarantine lifted. Counts recomputed from the site's index CSV: 2 225 sessions / 1 853 speakers / 71 labels in 186 combinations. ADR 0005's "1 356 patients" was **sessions**. |
| A4 filed datasheets | **DONE** | `c53c120` — DRV2605L timings and currents; ALDO3 (and the finding that the **ST7789V3 spec's own current table is `TBD` in every cell**); GATECTRL `E4h` confirmed; ESP32-S3 strapping Table 3-1. A third `TBD` class introduced: `TBD (acquisition)`, for the BMA423 figures Bosch has delisted. |
| D ADR 0006 | **DONE** | `15102dd` — written, `proposed`. Closes the last named ADR line of the DoD. Own `cplx2real` decided on source evidence; OQ1/2/3/4/7/8/9/12/13 closed or routed; ADR 0020 allocated. |
| A5 `(verify)` sweep | **DONE** | `3cb2323`, `555f763`, `61695fc` — 4 files swept, then audited, then the audit findings re-verified and applied. **The audit caught a false denial** (FDA #34) and a link that would have sold the operator the withdrawn edition of ISO 9241-112. |
| A7 marker gate | **DONE** | `f24023c`, `6f351a1` — `check_markers.py` + closed/allowed lists with **owners**. Mutation-tested both ways. |
| A6 `pre-commit run -a` | **DONE** | `e7e6c2d` — first full run: 21 hooks, 5 with findings, all addressed. All five local guard hooks passed first try. |
| R re-audit | **DONE** | 12 lots, **1 943 claims checked, 1 711 confirmed (88 %)**, 177 findings; 155 went to skeptics told to defend the repository — **86 confirmed, 50 partial, 19 refuted**. Applied in `69168ff`, `1e0cf71`, `3aeca46`, `c87bd26` across 46 files. |
| Handback | **DONE** | final section of this file. |

## What the loop caught that nobody had flagged

Recorded because these are the ones that argue for the method, not for the
diligence:

1. **The overnight "fix" was backwards.** `fab6121` changed the golden example's
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

**Written 2026-08-21, end of the daytime session.** Branch
`overnight-2026-08-21`: **52 commits ahead of `main`**, 18 of them today.
`main` untouched, `origin/main` still `4468334`, **nothing pushed**,
`git status` clean.

## Headline

The three items I handed back overnight as *"decisions for the owner"* were
lookups, and closing them showed the overnight session had also got two of them
**wrong in the other direction**. So the day became: close them, then audit
everything on the branch claim by claim.

**The audit checked 1 943 claims against primary sources. 1 711 confirmed
(88 %). It produced 177 findings — 6 blockers, 73 majors, 98 minors — and
every one of the 155 that went to a skeptic was defended before it was
believed: 86 confirmed, 50 partial, 19 refuted outright.**

Five of the six blockers are fixed. The sixth is yours and is below.

## The one thing to read first — **resolved 2026-08-21, by the operator**

> Restated as *"≥ 30 Hz for the presets whose hop supports it — 50 Hz for
> `live_singing` and `diction_consonants`"* ([proposal §1](../proposal/01-super-spectral-proposal.md),
> real-time bound). ADR 0006 accepted the same session; the old IDF 5.5.5 tree removed.
> Session record below is left as written — it is what the handback said at the time.

## The one thing to read first — as handed back

> **The research question refutes three of its own presets, and D2 is about to
> freeze it.**
>
> The RQ requires *"a spectrogram refreshed at ≥ 30 Hz for every preset"*.
> `vowel_formant_study`, `sustained_pitch_lab` and `room_noise_floor` all have
> `interval_ms: 40` — 25 analysis frames per second — and `refresh_hz_target: 25`.
> They cannot produce 30 new columns per second whatever the display does; the
> hop is the limit. [ADR 0010](../adr/0010-preset-schema.md) is **accepted**, so
> these are not drafts.
>
> Two ways out, and it is a research-scope choice, not an editorial one:
> **(a)** restate the bound as *"≥ 30 Hz for the presets whose hop supports it
> — 50 Hz for `live_singing` and `diction_consonants`"*, reopening the RQ before
> the freeze; or **(b)** shorten the three 40 ms hops to ≤ 33 ms — an ADR 0010
> amendment, three JSON edits, every derived constant recomputed, and it changes
> what `room_noise_floor` measures, since its slow hop is deliberate.
>
> Recorded at [proposal §1](../proposal/01-super-spectral-proposal.md) (real-time
> bound), in the roadmap's D6 checklist and in `CLAUDE.md`'s DoD, so the freeze
> cannot be ticked past it.

## The other five blockers, all fixed

| # | What it was | Why it mattered |
|---|---|---|
| 1 | **`datasets/corpora/manifest.yaml` had never been committed.** `.gitignore` ignored the *directory*, contradicting its own comment ("Only manifests … are tracked"). Four commit messages claim to edit it; git never saw it. | It also made two of my own gates lie: `check_links.py` resolves with `os.path.exists()` and passed locally while failing on a clean clone, and `check_markers.py` treats a missing closed-row file as a reopened correction — the marker gate passed *only* because an ignored file happened to be on disk. Fixed by ignoring the payload, not the directory. |
| 2 | **`CLAUDE.md` Never-rule 1 promised "CI greps for the literals". CI did not.** Four jobs, none grepping sources; the grep lived in a local hook that `pre-commit install` had never enabled. | GPIO19/20 are the *only* flash and debug path on a sealed board. I wrote the CI job rather than weakening the sentence: new `guard-hooks` job runs all seven repo-local hooks over `--all-files` plus an **independent** grep, negative-tested by injecting `gpio_set_level(GPIO_NUM_19, 1)`. |
| 3 | **ADR 0006 — four errors in a record I wrote at 13:03 today.** "+3.01 dBFS for a full-scale square" is *broadband*; per-bin it is **+2.10**. My stated reason for choosing coefficient-generation was **false** — both routes are byte-identical (`max\|Δ\| = 0`, all six sets). The real-2048 row was copied from the row below. And the memory table omitted esp-dsp's *unconditional* bit-reversal copies, putting it 8 KB under ADR 0002/0018. | A host test written from the square sentence fails by 0.92 dB. Totals now reconcile at 104 KB / 160 KB across all three records. |
| 4 | **Praat has none of our windows.** `Sound_multiplyByWindow`'s complete set is rectangular, triangular, parabolic, Hanning, Hamming, Gaussian, Kaiser. The schema claimed "watch, host, SciPy **and Praat** agree coefficient-for-coefficient" for six families. | Also: SciPy's `nuttall` **is** our `blackman_nuttall`, and our `nuttall` has no SciPy name — 0.0163 apart. The trap is now a `$comment` in the schema JSON itself, where a host implementer will hit it. |
| 5 | **The esp-dsp ROM twiddle claim** described a scratch buffer; the ROM ELF shows a 4-byte pointer to a 4096-byte read-only table in Internal ROM 1 `.rodata`. | Read from `esp32s3_rev0_rom.elf` with `readelf`/`objdump`. |

## Green, re-verified at handback

| Check | Result |
|---|---|
| `pre-commit run -a` | **21/21 Passed, 0 Failed** (exit 0) |
| the seven repo-local guard hooks, `--all-files` | all Passed |
| `check_links.py` | **127 files, 0 broken**, 1 skipped (named) |
| `check_presets.py` | **6/6 accepted, 41/41 rejected, 14/14 regression guards held** |
| `check_markers.py` | self-test **19/19**; gate **PASS**, 271 markers across 66 files, every one owned |
| `gen_colormap_lut.py --self-test` | OK — 3 maps, 57 checks |
| `doc_ocr` pytest | 25 passed |
| `idf.py build` · analyzer config · `idf-gate` | exit 0, **zero warnings** each |
| `git rev-parse origin/main` | `4468334` — nothing pushed |

## What is yours

1. **The RQ refresh bound** — above. Blocks the D2 freeze.
2. **Accept or reject [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md)** (`proposed`). It is the last named ADR line of the Phase-0 DoD. The engineering is evidenced and now audited; two decisions (D5 own `cplx2real`, D7 DC-blocker form) trade internal SRAM against maintenance, and tenet 3 makes SRAM binding.
3. **ADR 0011 and 0012** stay `proposed` — perception and UX judgements.
4. **`doc_ocr check`** on the gating datasheets — the flag records a *human* read, so an assistant must not set it.
5. **Remove the old IDF trees** — `rm -rf ~/esp/esp-idf ~/esp/idf/v5.5.5 ~/esp/tools/v5.5.5`. Your shell.
6. **`pre-commit install`** (writes `.git/hooks`), and the `conventional-precommit-linter` decision: its default type list and `--summary-uppercase` reject this repo's own documented subjects (`ADR 0005: …`, `docs: …`). Either extend `--types` and drop the uppercase rule, or change the convention in `CLAUDE.md`. I did not touch either.
7. **Q41** — whether a clinician-labelled pathology corpus feeds a headline metric. The *licence* half is closed (Saarbrücken is CC BY 4.0); the ethics half is yours.
8. **The proposal's voice**, and the merge and push.

## Before you push

```sh
git log --oneline main..overnight-2026-08-21          # 52 commits
git diff --stat main..overnight-2026-08-21            # 124 files, +10 079 / −601
git diff main..overnight-2026-08-21 -- docs/proposal/ # the draft, and the RQ blocker
pipx install pre-commit && pre-commit install && pre-commit run -a
```

Then, once the RQ question is settled:

```sh
git switch main
git merge --no-ff overnight-2026-08-21 -m "Phase 0 documentation: ADRs, preset protocol, golden-file contract, reference-project study, and two audits of the lot"
git push origin main
```

Nothing on this branch depends on being merged today. `main` is exactly where
you left it, and every commit says what it repairs — including the ones that
repair the commits before them.
