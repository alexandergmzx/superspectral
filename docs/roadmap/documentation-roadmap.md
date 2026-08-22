# Documentation roadmap — Super Spectral

**Compiled 2026-08-20** from the research session that produced [`../bibliography/`](../bibliography/README.md) (26 agents, two workflows; syntheses kept in the gitignored `scratch/research/`). Provisional values carry `(prov.)`; unsettled values carry `TBD`. Owner of the whole roadmap: Alexander Gomez; Claude acts as scientific assistant and executes the passes marked *this pass*.

The roadmap answers one question for every artefact in this repo: **in what order, and what does "done" look like?** It has two tracks — **D** (documentation and acquisition) and **E** (development environment) — because the user's stated risk ("the environment may cause a lot of troubles later if not done correctly") is real on this host and has its own irreversible steps (a 19 GB cleanup, a first custom flash, a first backlight write). The two tracks interleave: **D0 D1 E0** are this pass; **E1 E2 D2 D3 D4 D5 D6** are follow-up sessions, each a named phase with its own DoD.

---

## 0. Why documentation first — the evidence from `swarm`

`../swarm/` (same author, 32 commits over 77 days, 194 of 292 tracked files under `docs/`, docs:firmware commit ratio ≈ 3.2:1) is the model. Its git chronology, not its README, is the method:

| Step | swarm commit | What happened | What it proves for Super Spectral |
|---|---|---|---|
| 0 | `241c090` | `LICENSE` + a two-line README, nothing else | Licence is decided before any content exists (here: Apache-2.0 root, GPL-3.0-or-later `host/` — [ADR 0004](../adr/0004-split-licensing.md)) |
| 1 | `514846d` | The **whole skeleton in one commit**: `CLAUDE.md` before any code, a README in every directory, `.gitkeep` for planned dirs, proposal filed, CI with markdownlint | "Constitution first" — D0 |
| 2 | `67fc75b` | `docs/bibliography/` the **same day, before implementation**, framed as "the acquisition list" | The bibliography is a procurement instrument, not a reading list — D1 |
| 3 | `6a58924` | Index (`bibliography/`) split from library (`docs/{datasheets,…}`), vendor dirs pre-carved, R100 renames | Index mirrors library; `📥 Filed locally` couples them — D3 |
| 4 | `d9feec5`… | First ADRs numbered **0008** because 0001–0006 were pre-registered in `docs/adr/README.md` "Backlog" | ADR numbers are allocated when a decision is *identified* — D5, and the routing table below |
| 5 | `30922df` `89bdf42` `8bd305a` | Proposal → Markdown; inline citations; per-entry **Acquisition links** | Bidirectional traceability: "Why" cell ↔ § / ADR — D2 |
| 6 | `30bfc59` `3958a07` | **One bulk acquisition pass** (75 PDFs) + `acquisition-status.md` gap ledger + `📥` stamps; ebooks + `reference-projects/` | Acquire in one pass, ledger the gaps — D3 |
| 7 | **swarm** ADR 0015 (not this repo's 0015, which is the anti-brick policy) | `docs/OCR/` + `python-scripts/doc_ocr/` once the library passed ~80 PDFs | Extraction layer after the library is large — D3 (tooling already copied in D0) |
| 8 | `docs/validation/README.md`, `docs/architecture/README.md` | Metrics anchored to standards in the bibliography; tenets + planned-docs manifest | "Validation is part of the design" — D6 |

Two things swarm specified and never did are done here deliberately: the **reference-project study loop** (0 project-ADRs, 0 `_notes.md` in swarm → D4 here) and the **per-experiment validation report** beyond a single worked example (→ `validation/experiments/`).

### The companion decision

Super Spectral is a **companion** to the Linux analyzer in [`../research/00-linux-analyzer-architecture-and-build-guide.md`](../research/00-linux-analyzer-architecture-and-build-guide.md): the watch is the live-capture and real-time-display front end (spectrum, spectrogram, f0, band energy, take recording); the host keeps the heavy science (Praat-grade Burg formants with FormantPath, LTAS/SPR over whole takes, H1–H2 with Iseli–Alwan correction, DTW, Demucs). This is the decision that makes the research question answerable on a 61.5 dB(A) microphone and a 470 mAh (prov.) cell; it is fixed by [ADR 0002](../adr/0002-companion-architecture.md) (accepted 2026-08-20) and by proposal §3.

### The three conventions every phase enforces

1. **Index ↔ library coupling.** `docs/bibliography/NN-*.md` is the index; `docs/{datasheets,app-notes,standards,papers,reports,books}/` is the library. When a document is filed, its index entry gets a `📥 Filed locally: <relative path>` blockquote in the same commit. The index shows the *current gap*; the stamp is the authoritative per-entry state.
2. **Bidirectional traceability.** Every bibliography "Why" cell names what it grounds (a proposal §, an ADR number, a validation metric, a roadmap phase, or a firmware component). Every ADR names its literature in a `Reference basis:` bullet. A claim with no literature spine spawns a thematic bibliography file (08, 09, 10, 11 already exist for exactly this reason).
3. **ADR per decision, numbers allocated at identification.** One non-trivial decision per file; the backlog in [`../adr/README.md`](../adr/README.md) is pre-registered (0001–0019); each ADR ships as a multi-file ripple commit (ADR + proposal § + bibliography "Why" cells + validation rows + README/CLAUDE.md realignment) and the index is updated in that same commit.

---

## 1. The two tracks

```
   Track D — documentation & acquisition          Track E — environment
   ──────────────────────────────────────          ─────────────────────────────────────
   D0  Constitution ............... this pass      E0  Environment specification .. this pass
   D1  Acquisition list ........... this pass          (.envrc, sdkconfig, partitions,
                                                        idf_component.yml, docs/devenv, ADR 0001)
                                                   E1  Install + 30-min gate build   ← user present
   D2  Binding proposal (prose)                    E2  First contact with hardware   ← needs watch
   D3  Bulk acquisition pass                 ┐
   D4  Reference-project study loop +        │  hardware facts from E2 feed D4
       hardware-fact closure             ◄───┘
   D5  ADRs 0002–0019 (ripple commits)      ◄──── ADR 0001 flips to accepted at E1;
   D6  Validation plan frozen                      0014/0015/0016 need E2 data
       = gate to firmware milestone M0
```

The E-track is short and front-loaded on purpose: everything irreversible on the host (cleanup) and on the device (first custom flash, first backlight write) is sequenced *after* the check that makes it safe.

---

## 2. Phases

Each phase lists **Owner** (who must be present), **Inputs** (what must exist first), **Outputs** (files), and a **Definition of done** as `- [ ]` items to be ticked in the closing commit.

### D0 — Constitution *(this pass)*

- **Owner:** Claude (docs pass); Alexander reviews.
- **Inputs:** commit 1 (`LICENSE`, `NOTICE`, `host/LICENSE`, 2-line README); `scratch/research/{PLAN,BRIEF,methodology,domainMap,critic,devenv_synth,devenv_critic}.md`; the swarm tree as template.
- **Outputs:** `CLAUDE.md`; `README.md`; `.gitignore`, `.gitattributes`, `.editorconfig`, `.codespellrc`; `.github/workflows/ci.yml` (docs jobs live, firmware job `if: false`); a `README.md` in **every** directory and `.gitkeep` in every empty planned directory (layout table in [`../../README.md`](../../README.md)); `docs/research/00-linux-analyzer-architecture-and-build-guide.md` moved byte-identically; `python-scripts/doc_ocr/` copied from swarm with only `Settings.skip_dirs` adjusted; `docs/OCR/manifest.tsv` (header only); this roadmap.
- **Definition of done**
  - [ ] Every directory has a `README.md` (a `find`-loop prints no `MISSING`); every empty planned directory has `.gitkeep`.
  - [ ] CI docs jobs green: markdownlint (advisory), relative-link check (blocking), `python3 -m compileall -q python-scripts`.
  - [ ] `CLAUDE.md` quotes the provisional research question **verbatim** (see [`../proposal/01-super-spectral-proposal.md`](../proposal/01-super-spectral-proposal.md) §1) and its Quick-reference links resolve.
  - [ ] `git log --oneline` shows the swarm commit order: licence → skeleton → bibliography → roadmap/ADR/validation/architecture → devenv spec → `doc_ocr`.
  - [ ] Research doc is an R100 rename (`git log --follow` works).

### D1 — Acquisition list *(this pass)*

- **Owner:** Claude; Alexander reviews priorities.
- **Inputs:** D0; domainMap §4 (96 deduplicated documents), critic §C–G (~35 additions), devenv_synth §9 (~60 platform documents).
- **Outputs:** [`../bibliography/`](../bibliography/README.md) files `01-datasheets` … `07-technical-reports` (by type) and the thematic files `08-voice-metrology-on-the-wrist`, `09-visual-feedback-for-singing`, `10-datasets-and-ground-truth`, `11-esp-idf-platform-and-toolchain`; `acquisition-status.md` (empty ledger with the 10-tag legend); ≈190 entries total (prov.).
- **Every row carries:** identifier (DOI / ISBN / document number / URL), priority (★★★ must-have/blocking · ★★ strongly recommended · ★ useful background — research P0→★★★, P1→★★, P2→★), and a **"Why" that names what it grounds** (proposal §, ADR NNNN, validation metric, roadmap phase, or firmware component). Every file ends with `## Acquisition links` (Access ∈ free · paid · mirror · free, reg. · free (GET) · REPO · PORTAL) and `## Disclosure` (which entries were live-verified on 2026-08-20 vs model-recalled; low-confidence rows flagged inline "(verify)").
- **Reading set with a time budget** (the "if you can only read these before writing code" list, ≈20 h; lives in the bibliography README and is restated here so the D-track has a first work item):
  1. Heinzel, Rüdiger & Schilling 2002 — PS/PSD/NENBW normalization; prevents a silently wrong dBFS axis (grounds [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md), accepted).
  2. Smith, *Spectral Audio Signal Processing* — real-FFT packing, quadratic peak interpolation, COLA (grounds [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md), accepted, and the peak-frequency metric).
  3. Harris 1978 (+ Nuttall 1981 coefficients) — the six windows esp-dsp ships, coherent gain, ENBW, scalloping loss.
  4. Boersma 1993 — the algorithm behind the Praat golden files (grounds [ADR 0009](../adr/0009-golden-file-strategy.md)).
  5. McLeod & Wyvill 2005 — MPM; the pitch estimator that fits a 20 ms budget.
  6. Omori et al. 1996 — the *peak-to-peak* definition of SPR (grounds [ADR 0008](../adr/README.md)).
  7. Müller et al. 2022 — FHE; the open replacement for per-voice-type fixed bands.
  8. Švec & Granqvist 2010 — microphone admissibility for voice research (decides whether the SPM1423 is admissible at all).
  9. ESP-IDF v6.0 migration guides (peripherals, system, build system) — what every 5.x example gets wrong on 6.0.
  10. USB-Serial-JTAG console guide — the five ways to lose the only port on a sealed device.
- **Definition of done**
  - [ ] Files 01–11 + `acquisition-status.md` exist; README index counts match the files.
  - [ ] Every row has identifier + priority + a "Why" naming a § / ADR / metric / phase / component (no descriptive-only "Why" cells).
  - [ ] Every file ends with `## Acquisition links` and `## Disclosure`.
  - [ ] No research-workflow IDs (the two-letter-dash-number scheme of the scratch syntheses) appear anywhere in the repo; citation addresses are positional (`01 #3`, `05 #12`, `08 #S2`).
  - [ ] The 15 corrected claims (PLAN §2) do not appear in any "Why" cell.

### E0 — Environment specification *(this pass)*

- **Owner:** Claude; Alexander reviews before E1.
- **Inputs:** D0; devenv_synth (2,230 lines) + devenv_critic corrections (A1–A9, gaps B1–B12); read-only spot checks against the host's `~/.espressif/v6.0.1/esp-idf` tree.
- **Outputs:** `.envrc` (committed IDF pin; `direnv allow` is a user step); `firmware/twatch-s3/{CMakeLists.txt, partitions.csv, sdkconfig.defaults, sdkconfig.defaults.esp32s3, sdkconfig.ci.{qemu,release,analyzer}, main/{CMakeLists.txt, idf_component.yml, Kconfig.projbuild, app_main.c}}` and component stubs; `.clangd`, `.clang-format`, `.pre-commit-config.yaml`; [`../devenv/`](../devenv/README.md) — `setup.md`, `env.lock.md` (template), `upgrade-procedure.md`, `first-flash-checklist.md`, `brick-runbook.md`, `backup-policy.md`, `coredump-runbook.md`, `pitfalls.md`; [`../hw/`](../hw/README.md) — `twatch-s3-pins.md`, `efuse-baseline.json` (placeholder "not yet read"), `vendor-partition-table.md` (placeholder); [ADR 0001](../adr/0001-toolchain-esp-idf-v6-pinned-environment.md) **Status: proposed** at the time of this output, **accepted 2026-08-20** once the E1 gate passed on hardware; `tools/env-lock.sh`, `tools/flash.sh` stubs.
- **Definition of done**
  - [ ] Every `CONFIG_*` symbol named in `sdkconfig.defaults*` resolves to a Kconfig definition in the v6.0.x tree (grep against the read-only local tree; symbol names only, never line numbers).
  - [ ] `partitions.csv` offsets + sizes sum to exactly `0x1000000`; app partitions are 64 KB-aligned; `gen_esp32part.py` dry-run accepts it.
  - [ ] `idf_component.yml` and `.pre-commit-config.yaml` parse as YAML; `.envrc` passes `bash -n`.
  - [ ] No line-number citations into ESP-IDF sources anywhere under `docs/devenv/` (symbol/string citations only).
  - [ ] `.gitattributes` marks `dependencies.lock` `merge=binary` and `*.pdf` binary.
  - [ ] The pre-commit config asserts `SECURE_BOOT=n`, `SECURE_FLASH_ENC_ENABLED=n`, `ESP_WIFI_ENABLED=n`, `BT_ENABLED=n`, and greps for GPIO `19`/`20` literals reaching any GPIO API.

### E1 — Environment install + gate *(next session; Alexander present)*

- **Owner:** Alexander (changes host state); Claude drives.
- **Inputs:** E0 files; network; ~4 GB free for one tools root (and ~19 GB reclaimed at the end).
- **Outputs:** `~/esp/idf/v6.0.2` (full recursive clone at the tag) + `~/esp/tools/v6.0.2` (`IDF_TOOLS_PATH`); `firmware/twatch-s3/dependencies.lock` committed; `docs/devenv/env.lock.md` filled by `tools/env-lock.sh`; ADR 0001 flipped to **accepted**; CI firmware job un-`if: false`d; udev `SYMLINK+="ttyTWATCH"` rule (**only** a symlink — `60-openocd.rules` and `99-platformio-udev.rules` already set `MODE`/`GROUP` for `303a:1001`); host cleanup.
- **Procedure (ordered; details in [`../devenv/setup.md`](../devenv/setup.md))**
  1. `git clone -b v6.0.2 --recursive` (never shallow); `export IDF_TOOLS_PATH=~/esp/tools/v6.0.2`; `unset PYTHONPATH CMAKE_PREFIX_PATH LD_LIBRARY_PATH AMENT_PREFIX_PATH`; `PATH=/usr/bin:$PATH ./install.sh esp32s3`. Record `git rev-parse HEAD`.
  2. `direnv allow` in the repo; `env | grep -i IDF_COMPONENT` must print nothing (H17).
  3. **The 30-minute gate build**: throwaway project on v6.0.2 with `espressif/esp-dsp==1.8.2`, `lvgl/lvgl==9.5.0`, `espressif/esp_lvgl_port==2.9.0`, `espressif/esp_lcd_touch_ft5x06==1.1.1` and a TU including `driver/i2s_pdm.h`, `esp_lcd_panel_vendor.h`, `esp_dsp.h`, `lvgl.h`. Builds → continue. Fails → record the exact failure text in ADR 0001, fall back to v5.5.5 in its own tools root (see §4).
  4. `idf.py set-target esp32s3 && idf.py build` on the skeleton; commit `dependencies.lock`; cross-check resolved versions against components.espressif.com (a local mirror short-circuit shows up as lvgl 9.4.0); fill `env.lock.md`; flip ADR 0001; enable the CI firmware job; re-derive the container digest before first CI use.
  5. Add the udev symlink rule for both `303a:821b` (vendor Arduino TinyUSB PID) and `303a:1001` (native USB-Serial-JTAG).
  6. **Only after 4 succeeds twice:** repoint/delete the `get_idf` alias (`~/.bashrc`), guard the unconditional ROS 2 Jazzy `source` behind a function, and remove `~/.espressif`, `~/esp/esp-idf`, `~/esp/v5.4.1`, `~/esp/ESP8266_RTOS_SDK`, `~/esp/xtensa-lx106-elf` (~19 GB) — confirming each deletion with Alexander; follow [`../devenv/backup-policy.md`](../devenv/backup-policy.md) for what *not* to carry forward (the `components/` mirror, the stale 2025 constraints file, any venv).
- **Definition of done**
  - [x] `idf.py --version` prints v6.0.2 from a **fresh shell** in the repo (direnv, no alias, no manual `export.sh`). *(2026-08-20: verified by sourcing `.envrc` in a clean subshell; `direnv allow` itself is still the owner's step.)*
  - [x] Gate build passed; result recorded in ADR 0001; ADR 0001 **accepted** and the index updated in the same commit. *(2026-08-20: stage 1 compile + stage 2 running LVGL frame on the watch.)*
  - [x] `firmware/twatch-s3/dependencies.lock` committed; `env.lock.md` filled (IDF tag + SHA, `idf_tools.py list`, interpreter path, container digest, distro, cmake/ninja/ccache). *(2026-08-20)*
  - [x] Skeleton builds **twice** with identical `.bin` sha256 (`CONFIG_APP_REPRODUCIBLE_BUILD=y`). *(2026-08-20: identical after `fullclean`; note that `PROJECT_VER` is captured at configure time, so a build from a stale configure differs only in the version stamp — reconfigure before comparing.)*
  - [x] CI firmware job green on the digest-pinned container. *(2026-08-21: workflow run **#18** on `4468334` — all four configs `default`, `release`, `qemu`, `analyzer` green in `espressif/idf:v6.0.2@sha256:0d8c9773…cb67`, alongside the link-check, markdown-lint and python-scripts jobs. The guard-hooks, `check_markers.py` and `check_presets.py` steps were added **after** `4468334` and have not yet run on the remote.)*
  - [ ] Old trees gone; `~/.bashrc` no longer sources ROS unconditionally; `env | grep -i IDF_COMPONENT` empty. *(2026-08-20 partial: the `get_idf` alias to the dev snapshot is retired (`get_idf54` → v5.4.1, kept by owner's choice); `~/esp/esp-idf` and the half-installed `~/esp/idf/v5.5.5` + `~/esp/tools/v5.5.5` are scheduled for the owner to delete; `~/.espressif` (EIM v6.0.1) is untouched — its activation script must never be sourced in a Super Spectral shell (it sets `IDF_COMPONENT_LOCAL_STORAGE_URL`, which `.envrc` unsets defensively). ROS sourcing in `~/.bashrc` is still unconditional; `.envrc` scrubs it per project.)*

### E2 — First contact with hardware *(after E1; needs the watch)*

- **Owner:** Alexander (hands on the device); Claude drives the checklist.
- **Inputs:** E1 complete; the T-Watch S3, a known-good cable, no hub, charged battery; [`../devenv/first-flash-checklist.md`](../devenv/first-flash-checklist.md) and [`../devenv/brick-runbook.md`](../devenv/brick-runbook.md) open.
- **Phase-0 checklist (signed off in order; nothing writes to the device before step 5 is verified)**
  1. `esptool -c esp32s3 -p /dev/ttyTWATCH chip-id` and `flash-id` → record chip revision, flash JEDEC ID, size, MAC.
  2. `read-flash 0 0x1000000 factory-backup.bin` → `sha256sum` → store **off-repo** (16 MB; external drive).
  3. `espefuse -c esp32s3 summary --format json --file docs/hw/efuse-baseline.json` → commit. Read `VDD_SPI_FORCE`, `VDD_SPI_TIEH`, `VDD_SPI_XPD`, `DIS_USB_JTAG`, `DIS_USB_SERIAL_JTAG`, `FLASH_TYPE`, `SPI_BOOT_CRYPT_CNT`.
  4. `read-flash 0x8000 0x1000` → `gen_esp32part.py` → commit the decoded **vendor partition table** as text in `docs/hw/vendor-partition-table.md` (vendor NVS may carry calibration / BLE identity).
  5. Verify the backup **restores** on a scratch region before trusting it.
  6. Flash the vendor factory `.bin` once (LilyGoLib `factory.twatchs3.sx1262.*.bin`, a read-only artefact) to prove display/touch/PMU are alive; then restore.
  7. Observe the USB PID before/after the first native-IDF flash (`303a:821b` → `303a:1001`) and confirm the symlink follows.
  8. **Week-1 safety tests**, before any feature code: [experiment 0002](../validation/experiments/0002-rollback-and-boot-guard-race.md) — OTA rollback to `ota_0` without human intervention, and `idf.py flash` winning the boot-guard race 10/10.
  9. Unblock the paper-first decisions: `VDD_SPI_FORCE` → [ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md) (GPIO45 backlight); schematic + S3 datasheet pin table → which rail powers the SPM1423 (GPIO47, VDD_SPI domain on R8V) and the MAX98357A (GPIO48) → [ADR 0003](../adr/0003-microphone-path.md) / [ADR 0015](../adr/0015-anti-brick-policy.md).
  10. Golden recovery image resident in `ota_0` from this point on; all development builds flash to `ota_1` only.
- **Definition of done**
  - [x] `docs/hw/efuse-baseline.json` and `docs/hw/vendor-partition-table.md` committed; factory backup sha256 recorded (in `docs/hw/README.md` ledger and `vendor-partition-table.md`; `backup-policy.md` points there). *(2026-08-20)*
  - [x] Recovery path demonstrated: rollback and boot-guard race both pass (experiment 0002 Status → validated). *(2026-08-21: rollback 4/4, race 10/10 + 5/5.)*
  - [x] `VDD_SPI_FORCE` value recorded (`1`, TIEH = 3.3 V → GPIO45 free); ADR 0016 branch = "free PWM" ([ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md), accepted 2026-08-20); backlight code was written only after this read. *(2026-08-20)*
  - [ ] Mic/amp rail question (H2/Q14) answered on paper and recorded in `architecture/06-power-budget.md` rail map.
  - [x] `ota_0` holds the golden image (gate stage-2b build, sha256 in experiment 0002); `tools/flash.sh` refuses to target `ota_0` without `--recovery-image` and was the only flashing path used in 0002. *(2026-08-21)*

### D2 — Binding proposal *(skeleton this pass; prose next session)*

- **Owner:** Alexander (the proposal is his voice); Claude drafts.
- **Inputs:** D1 (so every claim has a citation address); the RQ (prov.) from `CLAUDE.md`; the 15 corrections.
- **Outputs:** [`../proposal/01-super-spectral-proposal.md`](../proposal/01-super-spectral-proposal.md) with §1 Motivation & research question · §2 Objectives (exactly five) · §3 Technical approach (companion split table, pipeline, BOM pointer) · §4 Validation plan & experimental methodology (two-path rule, factorial matrix, metrics table) · §5 Expected contributions · §6 16-week timeline · §7 Limitations & future work · References; [`../proposal/research-statement.md`](../proposal/research-statement.md) in swarm's 5-paragraph shape.
- **Definition of done**
  - [ ] RQ **frozen** (the `(prov.)` tag comes off) and quoted verbatim in `README.md`, `CLAUDE.md`, research statement.
  - [ ] Every bibliography "Why" cell that names a § resolves to an existing § of the proposal.
  - [ ] §4 metrics table is the same table as [`../validation/README.md`](../validation/README.md) (one source; the proposal links, it does not fork).
  - [ ] Every `(prov.)` / `TBD` remaining in §1–§7 is listed in §7.1 as a known limitation or in the routing table below.
  - [ ] References section lists citation addresses (`NN #k`) that all resolve.

### D3 — Bulk acquisition pass *(next session)*

- **Owner:** Alexander (purchases, portal logins, browser batch); Claude scripts and files.
- **Inputs:** D1; `scratch/fetch_bibliography.sh` (swarm's `fetch()` byte-for-byte, new URL list) and `scratch/clone_refs.sh`; `python-scripts/doc_ocr/`.
- **Outputs:** ≈70 open-access PDFs filed under the library by the filing convention (`<vendor>_<part>_<doctype>_<version>.pdf` etc., lowercase, version/year-stamped); **all ESP-IDF/Espressif docs as PDF snapshots** (they track `stable` and drift); Tier-0 clones under `docs/reference-projects/clones/` (gitignored): esp-dsp, esp-idf, esp-bsp, LilyGoLib, TTGO_TWatch_Library (`t-watch-s3`), SensorLib, XPowersLib, circuitpython, zephyr (`boards/lilygo`), xiao-edge-audio, mir_eval, mirdata, Parselmouth, friture; manual browser batch (ADI MAX98357A, FocalTech FT6336U, ST7789V3, Knowles); purchase decision list (IEC 61672-1, IEC 61260-1, IEC 60942, ISO 226 — none strictly required for relative measurement; see Q39); board-reference capture (product page → PDF, schematic V1.4 **and** 2025-03-24, Zephyr board-doc snapshot); `doc_ocr extract` sidecars + `docs/OCR/manifest.tsv` rows; `acquisition-status.md` populated; `📥 Filed locally` stamps; **figure digitization** of the Knowles raster tables (sensitivity/SNR/AOP table and the free-field response curve → CSV with a provenance block, via WebPlotDigitizer).
- **Definition of done**
  - [x] Every ★★★ document is filed + `📥` stamped, or ledgered in `acquisition-status.md` with a reason tag *(2026-08-21: scripted recount = 0 unresolved in all eleven files; last closures were 06 #52/#53/#31-praat clones, 07 #16 filed verbatim, 08 D5 and 10 #7 ledgered, 10 P1 ledgered as code → `python-scripts/synth_signals/`)*.
  - [~] `doc_ocr` manifest covers 100 % of filed PDFs *(46/46 as of 2026-08-21; `doc_ocr verify` clean)*; the `checked` review flags are still 0/46 — the human read of Knowles SPM1423, ST7789V3, ESP32-S3 datasheet + TRM, HW Design Guidelines (VDD_SPI table), both schematics marked `checked` — where `checked` for the Knowles sheet means "the acoustic table and the response curve survived extraction or were digitized".
  - [ ] Schematic 2025-03-24 compared with V1.4 for a mic second-source (Q12) and the result written into `01-datasheets.md`.
  - [x] Clone shortlist cloned *(16 of 17; `dywapitchtrack` 404 — the GitHub repo is gone, ledgered)*; licence column confirmed from each repo's `LICENSE` file, not from memory *(2026-08-20; `esp-bsp` and `lvgl` carry `LICENCE.txt`/per-component SPDX rather than a root `LICENSE`, recorded in the clone log)*.
  - [x] No paywalled PDF under `docs/books/`; purchased standards filed only if their licence permits a private copy *(2026-08-21: nothing purchased; the one book PDF is a free vendor sample chapter, `redistributable=unknown`, local only)*.

### D4 — Reference-project study loop + hardware-fact closure

- **Owner:** Claude (reading, notes); Alexander (decisions).
- **Inputs:** D3 clones and filed datasheets; E2 eFuse and rail facts.
- **Outputs:** `_notes.md` per studied project; the first project-ADR ([ADR 0018](../adr/0018-first-reference-project-study.md): xiao-edge-audio / LilyGoLib register sequences / SensorLib takeaways); `architecture/06-power-budget.md` rail map filled (DC1 = SoC, ALDO2 = backlight, ALDO3 = display+touch, ALDO4 = LoRa, BLDO2 = haptic, VBACKUP = RTC, **mic and amp rails from the schematic**); `hardware/bom/bill-of-materials.csv` complete; hardware questions closed on paper: R8 vs R8V, mic/amp rails, ST7789 revision, 470 vs 400 mAh, FT6336U vs FT5336, DIO3/TCXO, `ULC0511C`, speaker transducer (request filed with LilyGO).
- **Definition of done**
  - [ ] `architecture/06-power-budget.md` rail map has no `TBD` rail for any powered part on the BOM.
  - [ ] BOM complete with min/max cost and a TOTAL row carrying any deviation justification.
  - [x] ADR 0018 written; at least two `_notes.md` exist — four do (`xiao-edge-audio`, `lilygolib-axp2101`, `esp-dsp`, `sensorlib`). *(2026-08-21)*
  - [ ] Q8–Q20 rows in the routing table moved to **closed** or explicitly **deferred (ADR 0017)**.

### D5 — ADRs

- **Owner:** Alexander decides; Claude drafts ripple commits.
- **Inputs:** D2 §3/§4 prose; D3 documents; D4 facts; E2 measurements for 0014/0015/0016.
- **Outputs:** the backlog in [`../adr/README.md`](../adr/README.md) written as multi-file ripple commits (ADR + proposal § + bibliography "Why" + validation rows + README/CLAUDE.md); thematic bibliography files spawned for any claim still without a literature spine.
- **Definition of done**
  - [x] ADRs 0001–0006 **accepted** (0001 toolchain+env, 0002 companion split, 0003 mic path, 0004 split licensing, 0005 no-clinical-claim, 0006 FFT conventions — 0006 accepted 2026-08-21).
  - [ ] `docs/adr/README.md` Records index updated **in the same commit** as each ADR (swarm's stale-index habit is not copied).
  - [ ] Every ADR has a `Reference basis:` bullet whose citation addresses resolve.
  - [ ] Every accepted ADR that adds a requirement appended a `### <Subsystem> metrics (per ADR NNNN)` block to the validation README rather than editing the base table.

### D6 — Validation plan frozen → gate to firmware milestone M0

- **Owner:** Alexander.
- **Inputs:** D2–D5; E1–E2.
- **Outputs:** [`../validation/README.md`](../validation/README.md) with every target externally anchored and a measurement method; equipment list with tolerances; corpora manifests (`datasets/<corpus>/manifest.yaml` with sha256 + licence); [`../validation/golden-files.md`](../validation/golden-files.md) manifest + tolerance table; GUM uncertainty-budget skeleton for the level metrics; first experiment recipes ([0001](../validation/experiments/0001-pdm-mic-in-situ-characterization.md), [0002](../validation/experiments/0002-rollback-and-boot-guard-race.md)).
- **Documentation-phase definition of done (the gate to M0)**
  - [x] Every ★★★ document filed + 📥 stamped, or ledgered with a reason tag *(closed 2026-08-21 — see D3)*.
  - [ ] `doc_ocr` manifest covers 100 % of filed PDFs; the gating docs `checked`.
  - [ ] Proposal RQ frozen; `CLAUDE.md` and `research-statement.md` quote it verbatim. **Blocking contradiction resolved 2026-08-21** — the real-time bound now reads "≥ 30 Hz for the presets whose hop supports it" ([proposal §1](../proposal/01-super-spectral-proposal.md)), owner's decision. The freeze itself — the author's voice over the rest of the document — is still open.
  - [x] ADRs 0001 (toolchain+env, accepted after gate), 0002 (companion split), 0003 (mic path), 0004 (split licensing), 0005 (no-clinical-claim), 0006 (FFT conventions, accepted 2026-08-21) accepted.
  - [~] E1 complete: `dependencies.lock` committed, `env.lock.md` filled, CI firmware job green *(2026-08-21)*; **old installs partially removed 2026-08-21** — the v5.5.5 tools root and the `~/esp/esp-idf` master snapshot are gone (the `get_idf` alias is already retired). `~/.espressif` (the EIM tree, incl. v6.0.1) is still present; `~/esp/v5.4.1` is a deliberate keep and not in scope of this gate.
  - [x] E2 complete: eFuse baseline + vendor partition table committed; rollback + boot guard tested *(2026-08-21, experiment 0002: rollback 4/4, race 10/10 + 5/5)*.
  - [x] Validation metrics table: every target has an external anchor and a measurement method *(and, since 2026-08-21, the [uncertainty budget](../validation/uncertainty-budget.md) that says what each ± actually means)*.
  - [x] First reference-project ADR written ([ADR 0018](../adr/0018-first-reference-project-study.md), accepted 2026-08-21, on four `_notes.md` studies); first experiment recipe written ([0001](../validation/experiments/0001-pdm-mic-in-situ-characterization.md), and [0002](../validation/experiments/0002-rollback-and-boot-guard-race.md) executed and `validated 2026-08-21`).
  - [x] CI link-check green *(and reproducible locally without an install: `python3 python-scripts/check_links.py`)*.

---

## 3. Routing table — every open question has a home

The research left 47 domain questions (domainMap §7, **Q1–Q47**) and 18 hardware questions (devenv_synth §10, **H1–H18**) as flat lists. swarm's discipline converts each into one of four homes: an **ADR** number (a decision to write), a **validation row** (a number to measure), an **acquisition line** (a document to obtain), or the **E2 checklist** (a fact to read off the device). Nothing stays unowned. Route abbreviations: `ADR NNNN` → [`../adr/README.md`](../adr/README.md); `metric:` → a row of [`../validation/README.md`](../validation/README.md); `exp 000N` → [`../validation/experiments/`](../validation/experiments/README.md); `acq NN` → a bibliography file; `E2 #n` → the checklist step above; `D4` → hardware-fact closure.

### 3.1 Domain questions Q1–Q47

| ID | Question (short) | Route | Lands in | Closes when |
|---|---|---|---|---|
| Q1 | Is the device acoustically capable at all — in-situ response through the sealed case on a wrist; any resonance in 2.5–5 kHz? | **exp 0001** + metric: peak-amplitude accuracy, wrist-position envelope; threshold §4 | `validation/experiments/0001-…md`; the mic-EQ artefact | exp 0001 Status → validated; EQ filter committed or host-first pivot recorded |
| Q2 | Clock accuracy — measured PCM-rate error over temperature; calibrate once or track? | metric: sample-rate error ≤ 200 ppm; metric: thermal drift | `validation/README.md`; clock-correction constant in the preset schema (ADR 0010) | Phase 1 measurement against a GPSDO-referenced tone (justification is crystal ppm + fractional divider — the S3 has no APLL) |
| Q3 | Does the SPM1423 tolerate 3.072 MHz (48 kHz via DSR_8S; 178 kHz of margin, 5.5 % of the 3.25 MHz max)? | ADR 0003 (48 kHz gated) + acq 01 (Knowles DS, pinned revision) + threshold §4 | `adr/0003`; `01-datasheets.md` | Phase 1 measurement at 3.072 MHz; fails → cap at 32 kHz |
| Q4 | Mic passband at bass fundamentals (82–110 Hz) — harmonic-based f0 needed? Is H1–H2 trustworthy? | exp 0001 (swept sine, digitized datasheet curve) + metric: f0 range 65–1046 Hz | `validation/experiments/0001`; `01-datasheets.md` digitized CSV | Measured LF corner recorded (a plot starting at 100 Hz is not a −3 dB corner) |
| Q5 | Toolchain: ESP-IDF now vs Zephyr now (and which Zephyr PDM strategy)? | **ADR 0001** (decided: ESP-IDF v6.0.2 native; Zephyr rejected) | `adr/0001` | E1 gate build passes → accepted |
| Q6 | Scope of on-watch analysis — where is the line? | **ADR 0002** (decided: companion; feature table in proposal §3) | `adr/0002`; proposal §3 | ADR 0002 accepted in D5 |
| Q7 | Which path is the headline number — injection (±5 c) or acoustic (±20 c)? | validation two-path rule; proposal §1 states both | `validation/README.md` §"Two paths"; proposal §1, §4 | D2: RQ frozen with both bounds |
| Q8 | ESP32-S3 R8 vs R8V — is VDD_SPI 1.8 V? | **E2 #3** (eFuse) + acq 01 (S3 DS Table 1-1; HW Design Guidelines VDD_SPI table; schematic 25-03-24) | `docs/hw/efuse-baseline.json`; `01-datasheets.md` | E2 DoD |
| Q9 | Battery 470 vs 400 mAh | D4 + metric: autonomy (target restated against the confirmed cell) + acq 07 (LilyGoLib hardware doc / product page) | `hardware/bom`; `validation/README.md` | D4 DoD (cell confirmed from the shipped unit) |
| Q10 | Display 1.3″ vs 1.54″; ST7789V vs V3 (T_SCYCW 66 ns vs 16 ns → 4× frame-rate ceiling) | acq 01 (ST7789V3 spec, panel module) + ADR 0007 + H8 | `01-datasheets.md`; `adr/0007` | D3 filing + E2 H8 measurement |
| Q11 | Touch FT6336U vs FT5336; multi-touch for pinch-zoom? | acq 01 (FT6336U DS) + D4; driver choice recorded in `firmware/twatch-s3/components/twatch_bsp/README.md` | `01-datasheets.md`; BSP README | D4 DoD |
| Q12 | Was the obsolete SPM1423HM4H-B second-sourced in the 2025 board revision? | acq 01 (schematic 25-03-24 vs V1.4 diff) | `01-datasheets.md`; `acquisition-status.md` | D3 DoD |
| Q13 | SPM1423 AOP 110 (Rev A, page-verified) vs 115 dB SPL (Rev D)? | acq 01 (pin one revision; digitize the raster table) + metric: AOP/clipping flag | `01-datasheets.md`; `validation/README.md` | D3 `checked` on the Knowles sheet |
| Q14 | Which AXP2101 rail powers the microphone? | **E2 #9** (paper first: schematic + S3 pin table) + ADR 0003 / ADR 0015 + `architecture/06-power-budget.md` | rail map | E2 DoD |
| Q15 | Speaker transducer — Z, P, Fs, SPL undocumented | acq 01 (request from LilyGO; entry kept open in the ledger) + D4 BOM | `01-datasheets.md`; `hardware/bom` | D4 (request filed; "unknown" recorded in BOM if unanswered) |
| Q16 | SX1262 TCXO on DIO3 (GPIO6)? Why omitted from LilyGoLib's pin table? | **ADR 0017** (no radio in v1: SX1262 held in reset, ALDO4 off) — deferred | `adr/0017` | ADR 0017 accepted; revisit only if radio enters scope |
| Q17 | `ULC0511C` — unidentified part near USB/power | acq 01 (schematic 25-03-24 text layer + a vendor part search, ledgered `OPEN-TODO` until identified) + D4 BOM closure | `01-datasheets.md`; `acquisition-status.md`; `hardware/bom` | D4 DoD (part identified, or recorded as unknown in the BOM with the ledger tag) |
| Q18 | Button count / IP rating / USB-C on any S3 revision? | acq 07 (product page + retail manual snapshots) | `07-technical-reports.md` | D3 filing |
| Q19 | LilyGoLib `initAmplifier()` passes 160000 Hz — real bug? | **ADR 0018** / LilyGoLib `_notes.md` (reference-project study) | `reference-projects/` notes | D4 DoD |
| Q20 | I2S allocation — simultaneous PDM RX (I2S0-only) and standard TX (I2S1) for a calibration tone? | ADR 0003 (I2S0 RX / I2S1 TX) + **E2 H6** | `adr/0003` | H6 verified on the pinned tree |
| Q21 | Cycle counts of `dsps_bit_rev2r/4r_fc32` + `dsps_cplx2real_fc32` on S3 (not in the benchmark table) | metric: analysis-to-GPIO latency + **H13** (on-target `dsp_get_cpu_cycle_count()`, trended in CI) | `validation/README.md` | Phase 1 measurement logged via `log_performance()` |
| Q22 | Is the S3 hardware PDM→PCM decimation-filter response documented (SINC order, ripple, stopband)? | acq 01 (TRM Ch. 28 I2S) + exp 0001 (swept sine measures it above ~0.4·f_s) | `01-datasheets.md`; exp 0001 | exp 0001 |
| Q23 | Does PDM2PCM leave a DC offset large enough to swamp low bins (no HW HPF, no `amplify_num` on S3)? | ADR 0003 (software DC removal mandated) + exp 0001 (raw mean/RMS at known SPL) | `adr/0003`; exp 0001 | exp 0001 sizes the HPF and gain |
| Q24 | Should the analyzer canvas bypass LVGL (raw `esp_lcd` + ST7789 `VSCRDEF`/`VSCSAD`)? Does the driver expose the scroll commands? Scroll axis vs `MADCTL`? | **ADR 0007** (gated on scroll-axis verification) + H8/H9 + threshold §4 | `adr/0007` | E2 scroll-axis test; fails → ~30 Hz target via full-frame blits |
| Q25 | Block-floating-point wrapper around `dsps_fft2r_sc16` (6.3× faster, −1 bit/stage, +25.5 mA)? | **ADR 0006** (float32 `fc32` mandated; `sc16` a rejected alternative with a revisit trigger) + metric: two-tone resolution | `adr/0006` | ADR 0006 accepted |
| Q26 | Octal PSRAM active current; backlight current at usable brightness — the two largest unquantified power terms | metric: autonomy, energy per preset (AXP2101 E-Gauge vs PPK2/Otii) + acq 01 (APS6408, panel module DS) + D4 power budget | `validation/README.md`; `architecture/06-power-budget.md` | Phase 1 per-rail measurement |
| Q27 | PSRAM under Zephyr (zephyr#98137 alloc hang)? | ADR 0001 — **closed** (Zephyr rejected) | `adr/0001` Alternatives | closed |
| Q28 | Does Wi-Fi fit the power/core budget (RX 88–91 mA, TX to 340 mA, stack on core 0)? | **ADR 0017** (`WIFI_ENABLED=n`, `BT_ENABLED=n` asserted by pre-commit; `phy_init` retained) | `adr/0017` | ADR 0017 accepted |
| Q29 | Display throughput under Zephyr's 20 MHz DT cap? | ADR 0001 — **closed** for Zephyr; the `esp_lcd` side is **H8** | `adr/0001`; E2 | H8 |
| Q30 | Is 50 Hz the right refresh target for a 1.3″ wrist screen, or would 25–30 Hz halve power for imperceptible loss? | metric: sustained refresh (per-preset target — 50 Hz `live_singing`/`diction_consonants`, 25 Hz the other three, restated 2026-08-21) + ADR 0007 + proposal objective 4 (preset × refresh × mAh trade-off) | `validation/README.md`; proposal §2 (4) | Phase 2/3 trade-off study |
| Q31 | Sundberg 2001 per-voice-type centre frequencies unverified (2420/2550/2840/~3000 Hz) vs Müller 2022 FHE (2384/2454/2705/3092 Hz) | **ADR 0008** (FHE readout) + acq 05 (Sundberg 2001; KTH QPSR crawl, Q47) | `adr/0008`; `05-papers.md` | ADR 0008 accepted; Sundberg 2001 filed or ledgered |
| Q32 | SPR defined inconsistently — Omori peak-to-peak vs band-energy ratio | **ADR 0008** (Omori peak-to-peak is SPR; "ring ratio" is a separate, uncorrected overlay) | `adr/0008` | ADR 0008 accepted |
| Q33 | Ring/twang band edges (2.5–3.5 / 3.5–5 kHz vs Omori 2–4 kHz vs Bloothooft & Plomp 1/3-oct 2.5 / 3.16 kHz) | **ADR 0008** (FHE over any fixed band; fixed bands as overlays only) | `adr/0008`; preset schema (ADR 0010) | ADR 0008 + 0010 accepted |
| Q34 | Which spectrogram bandwidth convention do presets encode (300/45 Hz analog vs Praat Gaussian 260 Hz @ 5 ms / 43 Hz @ 30 ms)? Add Gaussian window? | **ADR 0010** (preset schema carries explicit bandwidth/ENBW) + ADR 0006 | `adr/0010`; `protocols/specs/` | ADR 0010 accepted |
| Q35 | Report Kreiman's four-parameter spectral-slope vector instead of lone H1–H2 in the offline compare mode? | **ADR 0002** (host-side feature table) — host scope | `adr/0002`; `host/README.md` | ADR 0002 accepted (host feature, out of watch scope) |
| Q36 | LPC order / pre-emphasis to match parselmouth `To Formant (burg)` defaults | **ADR 0009** (golden-file manifest pins formant settings) + metric: F1/F2 error | `adr/0009`; `validation/golden-files.md` | ADR 0009 accepted; manifest committed |
| Q37 | Praat version pin — 7.0.01 vs parselmouth's bundled Praat; raw vs filtered autocorrelation default | **ADR 0009** + [`../validation/golden-files.md`](../validation/golden-files.md) manifest (parselmouth → bundled Praat → method → floor/ceiling → sha256) | `validation/golden-files.md` | **Half answered 2026-08-21:** the pin is Praat 6.1.38 and the method is `raw`, because nothing else is reachable (T7a). What remains is not a lookup: whether the RQ's "≤ 5 cents vs Praat" is allowed to mean 2021-era raw autocorrelation, or the out-of-process route ADR 0009 rejected is reopened — **owner's decision**, informed by T7b |
| Q38 | Does the mic's HF rise require a fitted EQ, and is it per-unit or per-part-number? | exp 0001 + metric: 1/3-oct level (post-EQ **and** uncorrected reported) + ADR 0010 (mic-EQ slot in the preset schema) | exp 0001; `adr/0010` | exp 0001 on ≥ 2 units, or "per-unit, calibration step required" recorded in §7.1 |
| Q39 | Standards budget — buy IEC 61672-1 / 61260-1 / 60942 / ISO 226, or rely on free ANSI S1.11-2004 + published formulas and skip absolute-SPL claims? | acq 03 (purchase decision list in D3; none strictly required for relative measurement) | `03-standards.md`; `acquisition-status.md` (`PAID-STD` tags) | D3 decision recorded |
| Q40 | Absolute SPL calibration — Class-1 or Class-2 calibrator? | validation equipment (B&K 4231 Class 1, ±0.2 dB; Class 2 fallback caps SPL accuracy at ≈ ±2 dB) + metric: absolute SPL | `validation/README.md` §Equipment | Equipment acquired or the absolute-SPL row marked "not claimed" |
| Q41 | Own corpus (EGG + ethics) or CC BY 4.0 corpora only? | validation corpora tiers + **ADR 0005** (no clinical claim) + D6 corpora manifests | `validation/README.md` §Corpora; `10-datasets-and-ground-truth.md` | **Licence half closed 2026-08-21:** every Tier-1/2/3 corpus in the manifest now has a read licence, and Saarbrücken — the last unstated one — is CC BY 4.0 (Zenodo 16874898), so "CC BY 4.0 corpora only" is achievable without an own corpus. The open half is the ethics call: whether clinician-labelled pathology audio feeds a headline metric at all. **Owner's decision.** |
| Q42 | Test room ≤ 25 dB(A) available? Fallback? | validation equipment (room row; ISO 26101 / ANSI S12.2 to report the room you have) + metric: EIN | `validation/README.md` | Phase 1 room measurement recorded |
| Q43 | Licence split — deliberate? | **ADR 0004** (decided: Apache-2.0 root, GPL-3.0-or-later `host/`) | `adr/0004`; `NOTICE` | ADR 0004 accepted |
| Q44 | Adopt Zephyr `twatch_s3` board maintainership? | ADR 0001 — **closed** (argument for staying on ESP-IDF) | `adr/0001` | closed |
| Q45 | Shared upstream work with swarm (`lilygo_tbeam_s3_supreme` board, `dmic_esp32.c`)? | ADR 0001 Consequences — **deferred**, off the critical path of both projects | `adr/0001` | revisit only if a Zephyr end-state is reopened |
| Q46 | Trivia: VocalSet gender split; Koenig 1946 page range; pYIN DOI and PDF liveness | acq 05 / acq 10 rows flagged "(verify)" | `05-papers.md`; `10-datasets-and-ground-truth.md` | D3 verification on acquisition |
| Q47 | Highest-yield acquisition action: crawl the KTH STL-QPSR archive for Sundberg's open PDFs | acq 05 (D3 work item) | `05-papers.md` Acquisition links; `acquisition-status.md` Quick wins | D3 |

### 3.2 Hardware questions H1–H18

| ID | Question (short) | Route | Lands in | Closes when |
|---|---|---|---|---|
| H1 | eFuse baseline — `VDD_SPI_FORCE`? (★ was blocking: GPIO45 = backlight = VDD_SPI strap, *if* the flash were the 1.8 V W25Q128JW the schematic names) | **E2 #3** + **ADR 0016** | `docs/hw/efuse-baseline.json`; `adr/0016` | **Retired 2026-08-20.** `VDD_SPI_FORCE = 1` (TIEH, 3.3 V) and the shipped die reads `ef 4018`, a 3.3 V JV-class part — GPIO45 is free for PWM. [ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md), accepted |
| H2 | Which rail powers the SPM1423 and the MAX98357A (GPIO47/48 are VDD_SPI-domain on R8V)? | **E2 #9** (paper first) + ADR 0003 + `architecture/06-power-budget.md` | rail map | E2 DoD |
| H3 | Does the go/no-go gate build pass on v6.0.2? | **E1 step 3** → ADR 0001 accepted / v5.5.5 fallback | `adr/0001` | E1 DoD |
| H4 | What does the device enumerate as after the first native-IDF flash (`303a:821b` → `303a:1001`)? | **E2 #7** + E1 step 5 (symlink rule covers both PIDs) | `docs/devenv/setup.md` | E2 |
| H5 | Does JTAG attach, and at what OpenOCD version? | **E2** smoke step — answered on paper: host OpenOCD `v0.12.0-esp32-20260304` already clears the `20251215` thread-awareness floor; confirm `openocd -f board/esp32s3-builtin.cfg` attaches and `program_esp_bins` works as the second escape hatch | `docs/devenv/brick-runbook.md` | E2 |
| H6 | Confirm PDM RX is I2S0-only on the pinned tree (`i2s_channel_init_pdm_rx_mode()` on an I2S1 handle → `ESP_ERR_INVALID_ARG`) | **E2** + ADR 0003 | `adr/0003` | E2 |
| H7 | PDM slot mask — which channel is the SPM1423 strapped to? (wrong mask = silence = looks like a dead mic) | **E2** (first capture) + exp 0001 setup + ADR 0003 | exp 0001 §Setup | exp 0001 |
| H8 | What SPI pixel clock does the ST7789V3 actually tolerate (20 → 40 → 60 → 80 MHz, bench **and** on-wrist)? | **E2** + ADR 0007 + metric: sustained refresh | `adr/0007`; BSP README | E2 measurement |
| H9 | Real `set_gap`, invert, mirror, `swap_xy` values; touch transform | **E2** checklist item (1-px border + asymmetric pattern; crosshair at touch point) | `firmware/twatch-s3/components/twatch_bsp/README.md` | E2 |
| H10 | Does PSRAM come up at 8 MB, 80 MHz, octal (Kconfig default is 40 M)? | **E2** (boot log + `esp_psram_get_size()` assert + `grep SPIRAM_SPEED build/config/sdkconfig.h`) | `docs/devenv/first-flash-checklist.md` | E2 |
| H11 | Flash read/write/verify at QIO 80 MHz with the 1.9 V VDDSDIO boost, under backlight + DSP load on battery | **E2 #1–#2, #5** + Phase 1 stress (multi-MB write to `takes` under load) | `first-flash-checklist.md` | E2 + Phase 1 |
| H12 | Does esp-dsp's `_aes3` SIMD path produce correct results in QEMU (2026-04 QEMU extended S3 TIE/PIE)? | **validation** — backend-agreement test in [`../validation/golden-files.md`](../validation/golden-files.md) (QEMU lane `CONFIG_DSP_OPTIMIZED=y` vs ANSI; fresh `idf_tools.py install qemu-xtensa` first — the on-disk QEMU is 2024) | `validation/golden-files.md`; CI `sdkconfig.ci.qemu` | first CI run of the QEMU lane |
| H13 | Real FFT frame time; does the pipeline hit its deadline with LVGL rendering concurrently? `-Wdouble-promotion` clean? | metric: analysis-to-GPIO latency; dropped-frame rate (trended via `log_performance()` / `check_performance()`) | `validation/README.md` | Phase 1 |
| H14 | Actual current draw; does the brownout (`SEL_7`, 2.44 V) hold at low battery with backlight + PSRAM bursts + DSP? Charge current < 130 mA? | metric: autonomy + **E2** (reset-reason histogram; `esp_reset_reason()` never `ESP_RST_BROWNOUT`) | `validation/README.md`; `06-power-budget.md` | Phase 1 |
| H15 | Does OTA rollback work end to end (image in `ota_1` that never marks valid → bootloader reverts to `ota_0`)? | **E2 #8** = **exp 0002** | `validation/experiments/0002` | E2 DoD |
| H16 | Does the 3 s boot guard win the race against an image that crashes right after it (10/10 recoveries)? | **E2 #8** = **exp 0002**; `CONFIG_SPECTRAL_BOOT_GUARD_MS` raised if not | `validation/experiments/0002` | E2 DoD |
| H17 | Is `IDF_COMPONENT_LOCAL_STORAGE_URL` leaking into the build (local mirror resolves lvgl 9.4.0 instead of 9.5.0)? | **E1 step 2/4** + ADR 0001 (`.envrc` unsets it; CI, which has no mirror, is the arbiter of `dependencies.lock`) | `.envrc`; `adr/0001` | E1 DoD |
| H18 | Does AXP2101 bring-up order matter as predicted (`esp_lcd_panel_init()` returns `ESP_OK` into a dead panel if ALDO3 is off)? | **E2** deliberate negative test + rail-status assertion in `twatch_bsp` | `twatch_bsp/README.md`; `06-power-budget.md` | E2 |

**Count check:** 47 + 18 = 65 rows; every row names a route from the four-home set. When a row closes, keep it and change its "Closes when" cell to `closed — <ADR/experiment/commit>`.

---

## 4. Thresholds that change the plan

Each is a measurable outcome with a pre-committed consequence, so the plan changes by rule rather than by argument on the day.

| # | Threshold (measured where) | If it trips | Consequence (pre-committed) | Recorded in |
|---|---|---|---|---|
| T1 | **E1 gate build** (`esp-dsp==1.8.2` + `lvgl==9.5.0` + `esp_lvgl_port==2.9.0` + `esp_lcd_touch_ft5x06==1.1.1` + `driver/i2s_pdm.h` under v6.0.2) | does not build | Fall back to **v5.5.5** in its own tools root (`~/esp/idf/v5.5.5`, `~/esp/tools/v5.5.5`); accept EOL 2028-01-21; schedule the v6.x migration for 2027 via `upgrade-procedure.md`; `CONFIG_COMPILER_DISABLE_DEFAULT_ERRORS=y` only as a crutch while fixing a single component, then removed | **Retired 2026-08-20:** the gate built under v6.0.2 and ran on the watch, so no fallback was needed and [ADR 0001](../adr/0001-toolchain-esp-idf-v6-pinned-environment.md) is accepted |
| T2 | **Mic acoustically capable through the case** (exp 0001: in-situ response vs reference mic; resonance in 2.5–5 kHz; EIN) | response deviates beyond the fittable-EQ envelope, or a case resonance corrupts the ring/twang band, or EIN fails the Švec & Granqvist floor | **Host-first pivot**: the watch becomes capture + live preview only; every timbre metric (SPR, FHE, ring ratio) moves to host-offline on takes; RQ restated to f0 + latency + autonomy; proposal §7.1 rewritten | ADR 0002 amendment; proposal §1/§7 |
| T3 | **Mic clocks at 3.072 MHz** (Phase 1: capture at 48 kHz / DSR_8S, check for dropouts, noise-floor rise, clock-related spurs) | fails or is marginal | **Cap at 32 kHz / DSR_8S** (2.048 MHz); 16 kHz Nyquist still covers ring (2.5–3.5 kHz), twang (3.5–5 kHz) and the 5–8 kHz noise band; preset schema loses the 48 kHz option | ADR 0003; ADR 0010 |
| T4 | **ST7789 hardware vertical scroll axis** (E2: `VSCRDEF`/`VSCSAD` vs `MADCTL` rotation; the fixed spectrum strip must fall in TFA/BFA) | the time axis does not align with the native scroll axis, or the driver cannot issue the commands even via `esp_lcd_panel_io_tx_param()` | Analyzer canvas reverts to full-frame blits; refresh target becomes **~30 Hz** for all presets (50 Hz `live_singing` dropped from the RQ); power budget re-derived | ADR 0007; RQ refresh bound |
| T5 | **`VDD_SPI_FORCE` eFuse** (E2 #3) | `== 0` | GPIO45 (backlight) may never be driven low across a reset: LEDC idle-high, release-to-input in a single `spectral_reboot()` wrapper that is the **only permitted reboot path**, enforced by grep; no backlight code before the wrapper exists | ADR 0016; ADR 0015 |
| T6 | **Reference-microphone class** (equipment: UMIK-1 vs IEC 61094-4 WS2F / Earthworks class) | only a UMIK-1-class reference is available (> 2 dB HF disagreement reported vs Earthworks-class — inside the ±1.5 dB target) | The 1/3-octave level metric is **restated as within-session repeatability** (Bland–Altman limits of agreement / ICC) with a GUM budget; no absolute ±1.5 dB accuracy claim | validation README metric row; proposal §7.1 |
| ~~T7a~~ | **Which Praat does parselmouth bundle?** | — | **CLOSED 2026-08-21 by measurement.** `praat-parselmouth==0.4.7` → **Praat 6.1.38** (2021-01-02), and every 0.4.x is the same. It registers `To Pitch (ac)`/`(cc)` only; the filtered method (Praat 6.4, 2023-11-15) raises `PraatError: Command "To Pitch (filtered autocorrelation)" not available for given objects.` Golden sets pin `method: raw`, and `host/golden/verify.py` — **planned for D6, not yet written** — carries the rule as invariant 6: `filtered` requires `praat_bundled ≥ 6.4.0`. | [ADR 0009](../adr/0009-golden-file-strategy.md) amendment; `golden-files.md`; `host/pyproject.toml` |
| T7b | **Bundled Praat 6.1.38 vs praat.org 7.0.01** (one WAV through both — *version* drift and *method* drift measured separately) | outputs differ beyond the tolerance table | Golden files already pin the bundled version and method explicitly; the "≡ Praat" claim is dropped from the proposal and the RQ names the version it means; tolerance table widened only with a recorded reason. **Open** — needs a praat.org binary run out of process, and Praat 7.0's script full-trust checking handled for a script that writes files. | golden-files.md manifest; ADR 0009 |
| T8 | **Test-room background** (Phase 1: ≤ 25 dB(A)) | room is louder | EIN metric reports the room (ISO 26101 / ANSI S12.2 framing), the device EIN becomes an upper bound only; fallback = small treated enclosure or night measurement, recorded | validation README equipment row |
| T9 | **Battery capacity** (D4: shipped cell marking) | 400 mAh, not 470 | Autonomy target ≥ 3 h stands; the energy budget in `06-power-budget.md` is re-derived and the margin statement in proposal §3 changes | BOM; proposal §3 |
| T10 | **Third-party component uses the legacy I²C driver on IDF 6** (E1 gate: grep `esp_lcd_touch_ft5x06` for `driver/i2c.h` vs `driver/i2c_master.h`) | legacy | Pin an older compatible release if one exists, else write the ~80-line `esp_lcd_touch`-compatible FT6336U shim in `twatch_bsp`; record in ADR 0001 review debt | ADR 0001 Consequences |

---

## 5. Timeline (one page, all weeks provisional)

Project phases follow the README table: **Phase 0 Documentation & environment (weeks 0–3) · Phase 1 Component characterization (4–7) · Phase 2 Bench validation (8–11) · Phase 3 In-use validation & release (12–16)**. The D/E phases of this roadmap are the internal structure of Phase 0; D-track items that depend on hardware facts spill into Phase 1 by design.

```
week    0       1       2       3       │  4 … 7      │  8 … 11     │ 12 … 16
        ├───────┼───────┼───────┼───────┤             │             │
PHASE   │ Phase 0 — documentation & env  │ Phase 1     │ Phase 2     │ Phase 3
        │                                │ component   │ bench       │ in-use
        │                                │ character.  │ validation  │ + release
TRACK D │                                │             │             │
  D0    ██ constitution ─────────┤ this pass           │             │
  D1    ██ acquisition list ─────┤ this pass           │             │
  D2    │  ░░░░ proposal prose ──┤ RQ frozen           │             │
  D3    │      ░░░░░ bulk acquisition ┤ ★★★ filed/ledgered          │
  D4    │            ░░░░░ ref-project loop + HW-fact closure ┤ E2 facts
  D5    │               ░░░░░░░ ADRs 0002–0019 ────────┤ 0001–0006 accepted
  D6    │                        ░░░ validation frozen ═╣ GATE → M0
TRACK E │                                │             │             │
  E0    ██ env spec ─────────────┤ this pass; ADR 0001 accepted      │
  E1    │  ░░ install + 30-min gate ┤ ADR 0001 accepted · lock · cleanup
  E2    │      ░░░ first contact ───┤ eFuse JSON · vendor table · exp 0002
FIRMWARE (gated on the D6 gate)          │ M0 PDM→FFT  │ M1 canvas   │ M2 presets
                                         │   →USJ dump │   30/50 Hz  │   + takes
VALIDATION                               │ exp 0001    │ 108-trial   │ singers on
                                         │ clock const │   matrix    │   the wrist
                                         │ cycle counts│ golden-file │ autonomy/preset
                                         │ per-rail mA │   CI lanes  │ wrist envelope
                                         │             │             │ release guide

legend  ██ done in this pass   ░░ scheduled   ┤ DoD ticked   ═╣ gate
```

Dependencies worth stating once: **E1 before E2** (no flashing from an unpinned environment); **E2 before any backlight or audio-rail code** (T5, H2); **D6 before firmware M0** (the validation plan is what M0 is measured against); **exp 0002 before feature code** (an untested safety net is not a safety net); **exp 0001 before the preset schema freezes** (ADR 0010 needs the EQ slot's answer).

---

## 6. Maintenance of this document

- Tick DoD boxes in the commit that closes them; never in a separate "docs" sweep.
- When a routing-table row closes, keep it and write `closed — ADR NNNN` / `closed — exp 000N` / `closed — <commit>` in the last cell; rows are never deleted (they are the audit trail of the 65 questions).
- A new open question gets a new row (Q48…, H19…) and one of the four homes before the commit that raises it is merged.
- A threshold that trips gets its consequence executed as written and the row annotated with the date; if the consequence is *not* executed, that is an ADR, not an edit to this table.
