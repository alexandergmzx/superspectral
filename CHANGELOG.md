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

### Changed

- Nothing yet.

### Deprecated / Removed / Fixed / Security

- Nothing yet.

<!-- Link targets are filled in at the first tagged release; there is no remote yet. -->
[Unreleased]: ./
