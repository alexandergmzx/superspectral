# Changelog

All notable changes to Super Spectral are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project will
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) from its first
tagged release. Firmware versions come from `git describe` on annotated tags
(`PROJECT_VER`, ≤ 31 characters); there is no `version.txt`.

Entries reference architecture decisions by number (`ADR 0001`) and the
documentation roadmap by phase (`D1`, `E1`); see
[`docs/roadmap/documentation-roadmap.md`](docs/roadmap/documentation-roadmap.md).

## [Unreleased]

Phase 0 — Documentation & environment. Nothing is flashed, nothing is installed;
every number not backed by a measurement or an ADR is marked `(prov.)`.

### Added

- Repository constitution: `CLAUDE.md`, a `README.md` in every directory,
  `.gitkeep` for every planned library slot, banner-commented `.gitignore`,
  `.gitattributes` (opaque `dependencies.lock`), `CITATION.cff`, this file (D0).
- Split licensing: Apache-2.0 repository default, `host/` under
  GPL-3.0-or-later with its own `LICENSE`; stated in `NOTICE` and `README.md`,
  ADR 0004 pre-registered.
- Founding research document moved byte-identical to
  `docs/research/00-linux-analyzer-architecture-and-build-guide.md`.
- Documentation roadmap with tracks D0–D6 / E0–E2 and a definition of done per
  phase; routing table for the open questions.
- Proposal skeleton with the provisional research question (§1) and five
  objectives (§2); research statement.
- Bibliography 01–11 as the acquisition list: positional citation addresses,
  ★★★/★★/★ priorities, "Why" cells naming the proposal §, ADR or metric each
  document grounds, `## Acquisition links`, `## Disclosure`; empty
  `acquisition-status.md` ledger (D1).
- ADR index with template and pre-registered backlog 0001–0019; ADR 0001
  (ESP-IDF v6.0.2 native, pinned) drafted as `proposed`.
- Validation plan skeleton: two-path rule, metrics with external anchors,
  equipment with tolerances, golden-file strategy, experiment template.
- Environment specification (E0): committed `.envrc` pin, `sdkconfig.defaults*`,
  `partitions.csv` (16 MB, two 4 MB OTA slots, no factory, LittleFS presets, FAT
  takes, coredump), `idf_component.yml` with tilde pins, `.clangd`,
  `.clang-format`, `.editorconfig`, `.pre-commit-config.yaml`, `docs/devenv/`
  (setup, lock template, upgrade procedure, first-flash checklist, brick
  runbook, backup policy, coredump runbook, pitfalls).
- Firmware skeleton: `firmware/twatch-s3/` with component stubs
  (`spectral_core`, `spectral_fft_backend`, `twatch_bsp`, `audio_source`,
  `display_backend`, `ui`), 3 s boot guard, GPIO19/20 static asserts.
- CI: advisory markdownlint, blocking offline relative-link check (lychee),
  `compileall` + `doc_ocr` tests; firmware job (digest-pinned container,
  idf-build-apps, build-twice sha256 diff, size, SBOM) written and gated
  `if: false` until E1 commits `dependencies.lock`.
- Reference-library extraction tool `python-scripts/doc_ocr/` (carried over
  from the author's `swarm` repository) and the tracked `docs/OCR/manifest.tsv`
  ledger.
- Hardware BOM with bench instruments and tolerances; acoustic-port notes.

*Session of 2026-08-21 (branch `overnight-2026-08-21`, plan in
[`docs/session-plans/2026-08-21-overnight-phase0.md`](docs/session-plans/2026-08-21-overnight-phase0.md)):*

- **ADRs 0002, 0003, 0004, 0005, 0009, 0010, 0013, 0018, 0019 accepted**, and
  0011 (spectrogram colormap) and 0012 (hands-free interaction) written as
  `proposed` — both are perception/UX judgements and are the author's to take.
  The backlog is now 0006, 0007, 0008 only.
- **Preset protocol** (ADR 0010): `protocols/specs/preset-schema.md`,
  `protocols/specs/presets.schema.json` (draft 2020-12) and the six shipped
  presets under `protocols/presets/`, each carrying its window coefficients and
  the ENBW derived from them.
- **Golden-file contract** (ADR 0009): `host/golden/manifest.schema.yaml` —
  every version, setting and hash that a Praat reference output depends on.
- **Reference-project study** (ADR 0018): `docs/reference-projects/notes/` for
  xiao-edge-audio, LilyGoLib/XPowersLib, esp-dsp and SensorLib, read at pinned
  revisions, each with a corrections table against what the project believed.
- **Architecture documents** 01 overview, 02 audio-capture path, 03 DSP
  pipeline, 06 power budget, 12 interaction model.
- **Validation, paper side**: `docs/validation/uncertainty-budget.md` (JCGM 100
  shape, three models) and `datasets/corpora/manifest.yaml` pre-registering
  seven corpora with licences, intended validation rows and quarantine
  consequences.
- **Tooling**: `python-scripts/check_links.py` (relative links and `#anchors`,
  reported as `path:line`), `python-scripts/check_presets.py` (schema + loader
  rules V0–V10 + a 41-case negative suite) and
  `python-scripts/gen_colormap_lut.py`.
- Pre-commit hook `presets-rules`; a CI step running the preset checker.

*Session of 2026-08-21, daytime (same branch; plan in
[`docs/session-plans/2026-08-21-daytime-remediation.md`](docs/session-plans/2026-08-21-daytime-remediation.md)):*

- **[ADR 0006](docs/adr/0006-fft-normalisation-and-window-conventions.md)
  written, then accepted** the same day by Alexander after an independent
  re-audit corrected four of its claims — the last named ADR line of the Phase-0
  definition of done, so **ADRs 0001–0006 are all accepted**. Periodic cosine-sum
  windows built from the preset's own coefficients, Heinzel S1/S2, 0 dBFS =
  full-scale sine, `fc32` only, `fft2r` for every size in v1, and our own
  `cplx2real`. **ADR 0020** allocated for the f0 estimator.
- **The research question's real-time bound restated** (owner's decision):
  *"≥ 30 Hz for the presets whose hop supports it (50 Hz for `live_singing` and
  `diction_consonants`)"* — the previous "≥ 30 Hz for every preset" was refuted
  by three of the five accepted watch presets, whose 40 ms hop yields 25
  analysis frames/s. Byte-identical in the proposal, `CLAUDE.md`, `README.md`
  and `research-statement.md`; the freeze of the RQ itself is still open.
- CI job **`guard-hooks`**: the eight repo-local hooks run `--all-files`, plus
  an independent GPIO19/20 scan that **fails closed** — `CLAUDE.md` Never-rule 1
  had promised CI enforcement that did not exist. New local hook
  **`pdf-redistributable`**: a tracked PDF must carry `redistributable=yes` in
  `docs/OCR/manifest.tsv`. Both `pre-commit` stages are now installed, and the
  commit-msg linter's types match the repo's own subject convention
  (`ADR(0006): …`).
- **The GPL environment exists**: `host/pyproject.toml`, `host/uv.lock`,
  `host/REUSE.toml`, `host/.python-version`. `praat-parselmouth==0.4.7` pinned
  exactly, because the pin is the Praat version.
- `python-scripts/check_markers.py` plus
  [`markers-closed-2026-08-21.tsv`](docs/roadmap/markers-closed-2026-08-21.tsv)
  and [`markers-allowlist.tsv`](docs/roadmap/markers-allowlist.tsv): every
  unresolved-value marker is either a closed correction that must not regress or
  an allowed one with a **named owner**. Wired into pre-commit and CI.
- **★★★ filing closed** (DoD item 1): idf-build-apps v3.0.2, pytest-embedded
  v2.8.1 and praat/praat cloned and pinned by commit; ESP-IDF `SUPPORT_POLICY.md`
  / `ROADMAP.md` (+ `_CN` twins) filed byte-verbatim from the v6.0.2 checkout
  under `docs/reports/espressif-tools/esp-idf-v6.0.2/`; the case drawing (08 D5),
  Hillenbrand 1995 (10 #7, no stated terms) and the tier-0 synthetic set (10 P1,
  code) carry reason tags. `acquisition-status.md` header recomputed from
  `manifest.tsv` (46 rows, 3 466 pages). The research-statement's RQ quotation
  is now byte-identical to the proposal (emphasis removed).
- **Host H0 — the golden-file lane exists and runs.** GPL `host/src/spectral_host/`
  (src layout, `spectral-golden verify | env | generate`): the ADR 0006 reference
  spectrum from §4.3 coefficients (never a SciPy window name), Praat 6.1.38 raw-ac /
  Burg / LTAS wrappers with every parameter recorded, the preset loader, the generator
  and a verifier with 14 rules (S, I1–I8, N1–N4, G1) that never writes. Apache
  `python-scripts/synth_signals/` (Tier-0 synthetic corpus, 21 files, tracked manifest,
  `check` = reproducibility on another libm — closes bibliography 10 P1) and
  `python-scripts/golden_compare/` (masked dB residuals, cents + mir_eval melody
  metrics, window-table digests). First golden set **`tier0-synthetic`** committed
  (848 KB, 33 arrays). Golden-manifest schema **"1.1"**: quoted version, `windows[]`
  float32 digests, `rect` for calibration tones only, `generator.sha256` scoped to the
  numerics-bearing modules (`env.GENERATOR_TREE`) — ADR 0009 amended twice, ADR 0006
  D1/(c) closed and D3 carries the sampled-square note (+2.10 ideal, +2.112 at P = 32).
  CI: new `host` job + uv-pinned python-scripts tests + boundary greps; hooks
  `golden-regen` (outputs and the tolerance table never in one commit) and
  `host-boundary`. Experiments 0003/0004 reserved, 0005 (T7b) pre-registered with
  Praat 7.0's `--FULL-TRUST` handled. 339 + 21 + 111 tests, every unit adversarially
  reviewed with mutation runs.

*Session of 2026-08-22 (branch `web-app`):*

- **[ADR 0021](docs/adr/0021-host-web-application.md) accepted** (owner's
  decision, 2026-08-22): the founding research document's web application
  ([§B](docs/research/00-linux-analyzer-architecture-and-build-guide.md)) is
  built **in full** under `host/` — front end `host/web/` (Vite + TypeScript,
  GPL-3.0-or-later), backend `host/src/spectral_host/web/` (FastAPI). It
  decides: the scope (the founding document's §B live path and offline compare
  mode; its M5 native core stays out); **browser-native live DSP** in
  TypeScript, re-implementing the ADR 0006 conventions and held to the Python
  oracle through the same committed golden set the watch is held to — the
  oracle is the only arbiter, so there is no browser-vs-device row; that the
  web application is **the host's user interface and a second
  digital-injection-path instrument, never a wearable claim**, with its latency
  and refresh **measured and never claimed**; GPL-3.0-or-later for all of
  `host/web/` with a fail-closed npm licence gate (permissive only, **AGPL
  forbidden**); **no live link** between watch and host — the contract stays
  files; the six presets served byte-identical from `protocols/presets/`, the
  32 kHz assertion that refuses to start on a mismatch, the meaning of
  `analysis.smoothing`, and one shared `(prov.)` ring/twang constant; mkcert
  HTTPS with **phone-on-LAN as a requirement**, raw-capture constraints as
  mandatory-and-insufficient, and an XDG data directory that is never inside
  the repository; and milestones **W0–W4** on a new roadmap track.
  It **amends** [ADR 0002](docs/adr/0002-companion-architecture.md) decision 4
  ("no live host view" → "**no live link between watch and host**") and
  decision 3 ("the host never sees live audio" → "the host never sees **the
  watch's** live audio"), and it withdraws the offline-viewer-only position of
  `host/README.md`.
- **Roadmap track W** ([`docs/roadmap/documentation-roadmap.md`](docs/roadmap/documentation-roadmap.md)):
  W0 peak CLI + both skeletons + `/api/presets` · W1 live spectrum against the
  goldens · W2 waterfall + preset switching + injection mode + phone-on-LAN ·
  W3 f0 / ring / F1–F2 overlays · W4 offline compare — each with owner, inputs,
  outputs and a definition of done. Track W needs no hardware and, by the
  owner's ordering decision of the same day, **runs first**, in parallel with
  his own remaining Phase-0 items; firmware stays parked until both are green.
  Routing-table rows **Q48–Q53** give the web application's open questions a
  home (estimator family → ADR 0020; the 32 kHz refusal; the XDG data
  directory; the ring/twang band edges → ADR 0008; the shared colormap LUT →
  ADR 0011; the `requires-python` floor).
- **Validation, web side**: a *Host web application metrics* block in
  [`docs/validation/README.md`](docs/validation/README.md) — spectrum vs the
  Python oracle, window-table digest, peak frequency, browser f0 vs the Praat
  golden in **its own row**, capture-chain linearity, mic-to-pixel latency and
  sustained refresh (both *measured, no claim*), preset byte-identity — and
  three tolerance rows in
  [`docs/validation/golden-files.md`](docs/validation/golden-files.md), each
  saying why it is not tighter and where its measured residual will be
  recorded. Experiments
  [0006](docs/validation/experiments/0006-web-capture-chain-linearity.md)
  (capture-chain linearity per browser and OS — the *unprocessed / processed*
  verdict that travels with every acoustic number) and
  [0007](docs/validation/experiments/0007-web-latency-and-refresh.md)
  (microphone-to-pixel latency and sustained refresh, measured on the watch's
  own phototransistor rig) pre-registered.
- Commit type **`web`** added to the conventional-commit linter's `--types`
  list, so track W's milestone commits have a prefix of their own.

### Changed

- **The host is no longer an offline viewer only.** The position stated in
  `host/README.md` ("not a browser app … if a UI is ever added here, it is an
  offline viewer"), in [ADR 0002](docs/adr/0002-companion-architecture.md)
  decision 4, and in the architecture overview is **withdrawn** by
  [ADR 0021](docs/adr/0021-host-web-application.md) (owner, 2026-08-22).
  Nothing in that chain argued against the web application *as the host's own
  instrument*; it argued against it *as the wearable*, and that argument still
  stands — the four rehearsal-room objections of proposal §1 remain true of the
  web application, which is exactly why it is not the product.
- **The research question's closing clause was reworded** (owner's choice of
  wording, 2026-08-22; every number in the question is untouched). It now reads:
  *"— with all real-time DSP behind these bounds on-device, the host never in
  the watch's live loop, and files the only contract between them?"*, replacing
  *"— with all real-time DSP on-device and the host used only for offline
  analysis of recorded takes?"*, which a live analyzer on the host would have
  made false. The clause now states a **testable property** (the host is absent
  from the watch's loop; the contract is files) instead of a feature
  restriction on the host. Applied byte-identically to
  [`docs/proposal/01-super-spectral-proposal.md`](docs/proposal/01-super-spectral-proposal.md)
  §1, `CLAUDE.md`, `README.md` and
  [`docs/proposal/research-statement.md`](docs/proposal/research-statement.md);
  the **freeze** of the research question is still the author's act and remains
  open.

- ADR 0004's `host/` boundary is one `grep` over *headers*: every file under
  `host/` except `LICENSE` carries the GPL-3.0-or-later header (or is annotated
  by `host/REUSE.toml`), and no file outside it does. The string also appears in
  prose in ADR 0004 and ADR 0009 — the claim is about headers, as the record
  itself says.
- `check_links.py` reports `path:line`, validates `#anchors` against heading
  slugs, and scans `.yaml`/`.yml`/`.json` as well as `.md`.
- The `no-usb-pins` pre-commit hook blanks string literals before matching, so
  the `_Static_assert` that enforces the rule no longer trips it.

### Deprecated / Removed / Fixed / Security

- **The 1.8 V flash claim is retired.** The schematic names a W25Q128JW; the
  shipped die on this unit reads JEDEC `ef 4018`, a 3.3 V JV-class part, and
  `VDD_SPI_FORCE = 1`. GPIO45 is free for backlight PWM (ADR 0016). Corrected
  in fourteen places, including `twatch_pins.h`, the BOM and the hardware
  README.
- **FFT memory figures corrected.** Real-8192 costs ≈ 104 KB of internal SRAM
  with our own `cplx2real` and ≈ 160 KB on esp-dsp's tables — not the 112 KB
  that was in circulation, because `dsps_cplx2real_fc32` pulls in
  `dsps_fft4r_init_fc32`'s `16·N_c` twiddle table even on the radix-2 path.
- **`fft4real` does not exist** in esp-dsp 1.8.2; it is an example directory.
  Corrected in the bibliography, the component README, `spectral.h` and
  `idf_component.yml`.
- **SensorLib 0.4.1 is not an AXP2101 fallback**: `src/pmic/xpowers/` is on
  GitHub master and absent from the registry tarball we pin.
- `sdkconfig.defaults.esp32s3` no longer says FFT scratch goes to PSRAM.
- The `sc16` rejection had its bit-loss inverted (it is ≈ 60 dB at real-2048
  and ≈ 72 dB at real-8192) and rested on the microphone's broadband SNR rather
  than the 90–100 dB per-bin range the presets ask for.
- The golden-file worked example pinned raw-autocorrelation thresholds under
  `method: filtered`; both Praat default sets are now recorded with their
  source URLs and read date.
- `live_singing`'s `enbw_hz` was truncated rather than rounded.
- SPDX headers added to `firmware/idf-gate/{CMakeLists.txt,
  main/CMakeLists.txt, main/idf_component.yml}`.
- **A vendor manual was removed from the branch's history before its first
  push.** `docs/reports/nti-audio/nti-audio_xl2-manual_fw4.93_2026.pdf`
  (11 MB, `redistributable=unknown`, "local only" in four of the repo's own
  records) had been tracked since the branch's second commit. The branch was
  rewritten with `git-filter-repo` in a throwaway clone and verified
  commit-by-commit before the switch; 53 hashes changed and the session records
  quoting them were remapped from the commit-map. The file stays on disk,
  excluded, and `doc_ocr verify` still matches it. The `pdf-redistributable`
  hook exists so this cannot recur.

*Session of 2026-08-21, daytime — corrections, several of them to the night's own work:*

- **The golden-file pitch method was corrected in the wrong direction overnight**
  and is now right. No released `praat-parselmouth` (0.4.0–0.4.7) can run
  `To Pitch (filtered autocorrelation)` — all of them bundle **Praat 6.1.38**,
  which predates the method by two years. Golden sets pin `method: raw`, and
  `host/golden/verify.py` — **planned for D6, not yet written** — carries the
  rule as invariant 6: `filtered` requires `praat_bundled ≥ 6.4.0`.
- **The window oracle must build from coefficients, not names.** Preset
  `nuttall` (esp-dsp's set) has no SciPy equivalent — it is 0.0163 from SciPy's
  `nuttall`, which is in fact the Blackman–Nuttall set.
- **The Saarbrücken corpus is CC BY 4.0** (Zenodo 16874898), not
  `unstated-terms`; the site has no terms page at all. ADR 0005's "1 356
  patients" is 1 356 *sessions*, and "687 healthy" matches nothing in the index.
- **05 #23's companion DOI** was wrong on DOI, issue and pages; **#44's author
  order** put the second author first; **#47** is CC BY-NC-ND 4.0, not paid.
- **An FDA "correction" is retracted**: a pass inferred from the Federal
  Register API that the September 2019 revision did not exist. The guidance's own
  cover page names it. ADR 0005 now cites the edition it means (2026-01-06) and
  quotes §II verbatim.
- Four items parked as "unread" were read from datasheets **already filed in this
  repo** (DRV2605L timings and currents, FT6336U/ST7789 rail currents, ST7789
  `GATECTRL`, ESP32-S3 strapping Table 3-1) — and one of them found that the
  ST7789**V3** spec's own current table is `TBD` in every cell.
- Two `pre-commit` hook revs marked "VERIFY before first use" have now been used;
  `pre-commit run -a` passes 21/21 for the first time.

<!-- Link targets are filled in at the first tagged release. -->
[Unreleased]: ./
