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
  written** (`proposed`) — the last named ADR line of the Phase-0 definition of
  done. Periodic cosine-sum windows built from the preset's own coefficients,
  Heinzel S1/S2, 0 dBFS = full-scale sine, `fc32` only, `fft2r` for every size in
  v1, and our own `cplx2real`. **ADR 0020** allocated for the f0 estimator.
- **The GPL environment exists**: `host/pyproject.toml`, `host/uv.lock`,
  `host/REUSE.toml`, `host/.python-version`. `praat-parselmouth==0.4.7` pinned
  exactly, because the pin is the Praat version.
- `python-scripts/check_markers.py` plus
  [`markers-closed-2026-08-21.tsv`](docs/roadmap/markers-closed-2026-08-21.tsv)
  and [`markers-allowlist.tsv`](docs/roadmap/markers-allowlist.tsv): every
  unresolved-value marker is either a closed correction that must not regress or
  an allowed one with a **named owner**. Wired into pre-commit and CI.

### Changed

- ADR 0004's `host/` boundary is now literally one `grep`: every file under
  `host/` except `LICENSE` carries the GPL-3.0-or-later header, and no file
  outside it does.
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
