# Session record — 2026-08-21/22: DoD closure (D′) and host H0 (Phase B)

**Approved by:** Alexander, 2026-08-21 ("do what is needed to push to remote and plan the next steps" → plan accepted: push first, then host H0 + the four free ★★★ fetches in parallel with his own DoD items; firmware stays parked until the Phase-0 DoD is green; no hardware on an unattended day). **Binding rules:** the same set as [2026-08-21-daytime-remediation.md](2026-08-21-daytime-remediation.md) §Rules in force, plus: agents write, the orchestrator alone commits; never force-push; `backup/overnight-2026-08-21-pre-rewrite` stays local; `host/` GPL and `python-scripts/` Apache never import each other.

## Headline

Two branches, both merged `--no-ff` into `main` and pushed, CI green on every job both times:

| Merge | What landed | CI |
|---|---|---|
| `86f0db6` `dod-closure` | ★★★ filing closed (DoD item 1 ticked); RQ quotation byte-identical in all four places | run [32542863239](https://github.com/alexandergmzx/superspectral/actions/runs/32542863239), 8/8 |
| `61a2358` `host-h0` | the golden-file lane exists and runs: `spectral_host` (GPL), `synth_signals` + `golden_compare` (Apache), schema `"1.1"`, the first golden set, a CI `host` job | run [32549170456](https://github.com/alexandergmzx/superspectral/actions/runs/32549170456), **9/9** — first remote run of the `host` job |

The remote `host` job settled two things a local run cannot: the parselmouth wheel installed on `ubuntu-24.04` matches the manifest's pins exactly (verify rule I5; `ok (14 rules)`), and the Tier-0 corpus reproduces byte-for-byte on GitHub's libm (`synth_signals check` 21/21).

## Live status

| Unit | Commit | Gate |
|---|---|---|
| D′ — 4 free fetches (06 #52 idf-build-apps v3.0.2, 06 #53 pytest-embedded v2.8.1, praat/praat `f38ba40b`, 07 #16 ESP-IDF support policy filed verbatim), 2 ledger rows (08 D5, 10 #7), ledger header re-sync (46 / 3 466 pp / 12·26·8) | `0f4fae6` | scripted recount: 0 unresolved ★★★ rows in all eleven files; `check_links` 0; markers PASS; `doc_ocr verify` clean |
| D′ — research-statement RQ bold stripped | `e2923dd` | scripted extraction of the sentence from proposal, CLAUDE.md, README, statement compares equal |
| D′ — DoD tick (CLAUDE.md, roadmap D3 + D6, CHANGELOG) | `0a7bb75` | — |
| B-U9 — CI `host` job, uv-pinned python-scripts tests, `golden-regen` + `host-boundary` hooks | `3ee26bd` | review mutations (GPL header outside host, `import spectral_host` outside host, Apache import under host/tests, `sys.path` in host/src, outputs + tolerance table staged together) all caught; `golden-regen` fails closed on a shallow HEAD (guard-hooks checkout is `fetch-depth: 2` for that reason) |
| B-U1b — ADR 0009 amended ×2: schema `"1.1"` (`windows[]` float32 digests, `rect` for calibration only, quoted version) and the generator digest scoped to `env.GENERATOR_TREE`; ADR 0006 D1/(c) closed, D3 sampled-square note; experiments 0003/0004 reserved, 0005 (T7b) pre-registered | `18fbf22` | `check_schema` PASS; `test_manifest_schema.py` 44; markers PASS |
| B-U2 — `python-scripts/synth_signals/` + tracked `datasets/tier0-synthetic/manifest.yaml` (closes 10 P1) | `835955e` | 21 tests; `generate` then `check` 21/21 |
| B-U1/U3/U4/U5/U6/U7 — `host/src/spectral_host/` (spectrum oracle, Praat wrappers, env, hashing, wavio, presets, golden generate/verify/manifest/cli) | `5601e12` | 339 tests |
| B-U6 — golden set `tier0-synthetic` (33 arrays, 848 KB), generated from the clean tree at `5601e12` | `1946b94` | `spectral-golden verify` ok (14 rules); arrays `cmp`-identical to both earlier uncommitted emissions |
| B-U8 — `python-scripts/golden_compare/` | `1929d2e` | 111 tests; 4 run against the real set |
| merge `main` → `host-h0`, CHANGELOG | `c749ab1`, `adbb64e` | full gate on the merged tree (below) |

Full gate on the merged tree before the push: host 339 · synth 21 + `check` 21/21 · compare 111 · `spectral-golden verify` ok · compileall · `check_links` 135 files 0 broken · `check_presets` PASS · markers PASS (274 markers, 67 files) · `doc_ocr` 25 + verify clean · `pre-commit run -a` 24/24 · boundary greps empty · `firmware/` untouched.

## How the work was done, and what the loop caught

Nine build units, each followed by an adversarial reviewer with licence to fix what it found (mutation runs, independent recomputation with `uv run --project host python`), then a final gate agent; 21 agents, 651 tool calls. The review stage earned its cost:

- **Three test mutations survived the first `synth_signals` suite** (two-tone `/2`, `rms_of_sine` compared against itself, DC-bin doubling in the test helper) — each got a real test. The vibrato docstring's "< 1e-9 cycles" phase error was measured at 7.8 × 10⁻⁸ and corrected.
- **Four of twelve mutants survived the first `praat.py` suite**: the raw/cc parameter plumbing was untested because pure sines are insensitive to `octave_cost ↔ octave_jump_cost` swaps. Fixed with a recording stub that asserts every keyword, plus a test pinning the wrapper against Praat's own positional script form.
- **`verify.py` I6 refused `praat_bundled: "6.4"`** (`(6,4) < (6,4,0)` in Python) — the release that *introduced* the filtered method. Fixed.
- **`golden_compare`'s pitch report passed an estimator exact on half the frames**: the VR/VFA row had constants but no effect on `passed`. Fixed.
- **The `golden-regen` hook would have been permanently red on `main`**: at `fetch-depth: 1`, `git diff-tree --root HEAD` lists the whole tree. Fixed before it ever ran remotely.
- **The first schema unit shipped with zero tests touching the schema** (deleting the `windows[]` conditional left the suite green) — a 44-test suite was added, which also measured the float32-boundary margin the ADR had only asserted (1521 float64 ULP, `nuttall`, N = 2048).
- **The generator digest.** B-U4 hashed the whole `spectral_host` package; by the final gate, edits to `cli.py`/`verify.py`/`presets.py` had turned the freshly generated set red on I4 with all 33 arrays byte-identical. Decision (orchestrator, recorded as an ADR 0009 amendment): `generator.sha256` covers the numerics-bearing modules only (`env.GENERATOR_TREE`), `generator.script` is the package path and the only value verify accepts; `generate` still refuses a dirty package. The set was then regenerated from a clean tree so `generator.commit` names a commit that contains the generator.

Two physics corrections worth knowing: the |H| peak of a Klatt two-pole resonator sits *below* its pole (697.0 Hz for 700/130; the cascade pushes F3's envelope peak 14 Hz low), so the Tier-0 manifest records poles and response peaks separately; and a sampled P = 32 square's fundamental is `4/(P·sin(π/P))` above `4/π` — +2.112 dBFS, not the ideal +2.10 (ADR 0006 D3 now says so; the dataset manifest carries the expected value).

## Findings that are yours

- **Praat Burg on the synthetic vowel reads F1/F2/F3 = 646/1152/1379 Hz against poles 700/1220/2600** (`max_formants = 5`, ceiling 5500 Hz). The golden records what Praat says — the F1/F2 tolerance row is device-vs-Praat — but the reference is ~8 % off the truth on this material. Recorded `(prov.)` in `golden-files.md`; the formant settings for the vowel set deserve a look before H1.
- **Experiment 0005 (T7b)** is pre-registered and is yours to run: a praat.org 7.0.01 binary out of process with `--FULL-TRUST` (read from `sys/praat.cpp` of the pinned clone — without it a script that saves files stops silently after `versions.txt`), raw-ac vs raw-ac for version drift and raw-ac vs the 7.0 filtered defaults (50/800 Hz, 0.03/0.09/0.50/0.055/0.35/0.14, `fon/praat_Sound.cpp`) for method drift, never summed. The `spectral-golden t7` subcommand still exits 2; the recipe's manual steps stand on their own.
- **Ledger facts from D′:** 07 #16's 2027-03-20 / 2028-09-20 dates are *derived* from the 30-month policy plus the real `v6.0` tag date (2026-03-19) — the filed `ROADMAP.md` only carries the *planned* 2026-02-13; two back-cover STEPs exist upstream (`TTGO_TWatch_Library@t-watch-s3 shell/BackCover*.stp`, MIT) though no case-body drawing does; Hillenbrand 1995 states no terms at all (`(c) 1995 James Hillenbrand` only).
- `docs/devenv/env.lock.md` gains the `uv` row on your next `tools/env-lock.sh` run from the IDF shell.
- `markdown-lint` reports MD013/MD060 on the new experiment recipe — advisory, non-blocking, same as every other long-line doc in the tree.

## Not delegated (unchanged)

`doc_ocr check` on the 8 gating docs; the proposal in your voice, the `(prov.)` strip and the RQ freeze; `rm -rf ~/.espressif` (then I re-tense the five docs sentences); ADR 0011/0012; Q41; running experiment 0005; anything on the watch. Firmware Phase C stays parked until the DoD is green — after this session the open DoD items are `doc_ocr` `checked`, the RQ freeze, and E1's `~/.espressif`.

## Before you pull

`main` = `61a2358`. Branches `dod-closure` and `host-h0` are pushed as frozen records; `backup/overnight-2026-08-21-pre-rewrite` is local only and must stay so. The `host-h0` worktree lives in the session scratchpad and can be removed with `git worktree prune` once `/tmp` is cleared. Three Python environments now exist on your machine and never mix: the IDF venv, `python-scripts/<pkg>/.venv` (uv), `host/.venv` (uv); every pytest invocation needs `PYTHONPATH` stripped (the ROS 2 leak, pitfall A1 — `.envrc` does it).
