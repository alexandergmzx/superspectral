# Reference projects

Local landing zone for the open-source projects catalogued in [`../bibliography/06-reference-projects.md`](../bibliography/06-reference-projects.md). That file holds the rationale ("what to take"), the **License** and **Apache-2.0-compatible?** verdicts and the full link table; this directory holds whatever is actually pulled down.

## Policy: catalogue here, clone on demand

Every entry in file 06 is a living repository (esp-dsp, LilyGoLib, SensorLib, Parselmouth, …). The repo-wide convention — stated in [`CLAUDE.md`](../../CLAUDE.md) and repeated in the thematic bibliography files — is **"code repos are cloned on demand, not vendored."** Vendoring would add gigabytes, entangle foreign git history, and — decisive here — drag GPL, AGPL, LGPL and unlicensed code into an Apache-2.0 tree (see the licence table at the top of file 06 and [ADR 0004](../adr/0004-split-licensing.md), accepted).

So the default is a **catalogue**, not a mirror:

- Read the code upstream or in a shallow clone; capture takeaways in a **tracked** note under [`notes/`](notes/README.md) (`<project>_notes.md`, one per project, recording the commit studied and the licence read from the repo's own `LICENSE`), so the findings survive a refreshed or deleted clone; then lift the decisions into an ADR ([0018](../adr/0018-first-reference-project-study.md) is the first).
- When you need a working copy, shallow-clone it into `clones/` with the literal command from the table below.
- Only genuine *self-contained artifacts* are committed, under `artifacts/<project>/` — and for this project that means **manifests**, not binaries: the LilyGoLib factory firmware is recorded as URL + release date + sha256 + flash command in `artifacts/lilygolib/`, while the `.bin` itself (which bundles LGPL and GPL code) stays off-repo next to `factory-backup.bin` per [`backup-policy.md`](../devenv/README.md). A reference-design schematic PDF belongs in [`../datasheets/`](../datasheets/README.md), not here.
- **Never clone into `clones/`** the entries file 06 marks browse-only: `arduino-esp32` (LGPL — the pin map is derived from MIT sources and *compared* afterwards), `T-Watch-Deps` and the unlicensed cluster, the do-not-use entries, and the "Espressif MIT" field-of-use repos.

### `clones/` is gitignored

Shallow clones live in `docs/reference-projects/clones/` and are **not** committed — scratch copies of upstream, refreshed on demand. The repo `.gitignore` carries:

```
docs/reference-projects/clones/
```

`artifacts/` is tracked (it holds small text manifests only).

## Clone-first shortlist (highest overlap with our firmware components)

Clone these before writing the corresponding component. **License** is mandatory; anything not `yes` in the last column is read for ideas and reimplemented from the papers in [05](../bibliography/05-papers.md).

| Bib # | Project | Maps to | License | Apache-2.0-compatible? | Shallow clone |
|-------|---------|---------|---------|:----------------------:|---------------|
| 1 | espressif/esp-dsp | `spectral_fft_backend` — FFT, windows, biquads, correlation; cycle-count harness | Apache-2.0 | yes | `git clone --depth 1 https://github.com/espressif/esp-dsp` |
| 3 | clutchitggs/xiao-edge-audio | `audio_source` → FFT → spectrogram pipeline on the same silicon class (ADR 0018) | MIT | yes | `git clone --depth 1 https://github.com/clutchitggs/xiao-edge-audio` |
| 4 | Xinyuan-LilyGO/LilyGoLib | `twatch_bsp` — rail sequence, display init, PDM slot; schematics; factory firmware | MIT | yes | `git clone --depth 1 https://github.com/Xinyuan-LilyGO/LilyGoLib` |
| 5 | TTGO_TWatch_Library (`t-watch-s3`) | `twatch_bsp` — `utilities.h` (DIO3), board JSON (`qio_opi`, 16 MB), TFT_eSPI setup | MIT | yes | `git clone --depth 1 -b t-watch-s3 https://github.com/Xinyuan-LilyGO/TTGO_TWatch_Library` |
| 6 | adafruit/circuitpython | `audio_source` — `PDMIn.c`; `pins.c`; prebuilt image as the E2 acoustic rig | MIT | yes | `git clone --depth 1 https://github.com/adafruit/circuitpython` |
| 7 | lewisxhe/SensorLib | `twatch_bsp` — BMA423 (mandatory), AXP2101 fallback, Kconfig exclusions | MIT | yes | `git clone --depth 1 https://github.com/lewisxhe/SensorLib` |
| 8 | lewisxhe/XPowersLib | `twatch_bsp` — AXP2101 init order for the hand-written driver; datasheet mirror | MIT | yes | `git clone --depth 1 https://github.com/lewisxhe/XPowersLib` |
| 11 | espressif/esp-bsp | `display_backend`/`ui` — `esp_lvgl_port` (+ `performance.md`), `esp_lcd_touch_ft5x06`, `esp_bsp_generic` | mixed SPDX (Apache-2.0 per component — verify) | yes (per component) | `git clone --depth 1 https://github.com/espressif/esp-bsp` |
| 13 | esp-cpp/espp | `twatch_bsp` structure (T-Deck BSP as template) | MIT | yes | `git clone --depth 1 https://github.com/esp-cpp/espp` |
| 17 | antoineschmitt/dywapitchtrack | `spectral_core` — third f0 candidate | MIT | yes | `git clone --depth 1 https://github.com/antoineschmitt/dywapitchtrack` |
| 18 | sevagh/pitch-detection | `spectral_core` — MPM/YIN references to port to C99 | MIT | yes | `git clone --depth 1 https://github.com/sevagh/pitch-detection` |
| 29 | mir-evaluation/mir_eval | host validation — §4 pitch metrics | MIT | yes | `git clone --depth 1 https://github.com/mir-evaluation/mir_eval` |
| 30 | mir-dataset-loaders/mirdata | host validation — checksummed corpus loaders | BSD-3-Clause | yes | `git clone --depth 1 https://github.com/mir-dataset-loaders/mirdata` |
| 31 | YannickJadoul/Parselmouth | `host/golden/` — golden-file generator (GPL tree only) | GPL-3.0 | **read-only** for firmware; imported under `host/` | `git clone --depth 1 https://github.com/YannickJadoul/Parselmouth` |
| 32 | tlecomte/friture | host reference — decimation trap, octave bank | GPL-3.0 | **read-only** | `git clone --depth 1 https://github.com/tlecomte/friture` |
| 39 | cyberwisk/m5Cardputer_audiospectrum | `ui` ideas — spectrum + tuner on a small S3 screen | GPL-3.0 | **read-only** | `git clone --depth 1 https://github.com/cyberwisk/m5Cardputer_audiospectrum` |
| 9 | zephyrproject-rtos/zephyr (`boards/lilygo/twatch_s3`) | `docs/hw/` cross-check — devicetree of the full pinout; ADR 0001 evidence | Apache-2.0 | yes | `git clone --depth 1 https://github.com/zephyrproject-rtos/zephyr` (large) |

Full list (58 entries), priorities, links and the per-tier licence discussion: [`../bibliography/06-reference-projects.md`](../bibliography/06-reference-projects.md). The one-shot script that clones the Tier-0 set is `scratch/clone_refs.sh` (gitignored working file, roadmap phase D3).

## Layout

```
reference-projects/
├── README.md                 # this catalogue
├── notes/                    # TRACKED per-project study notes (see notes/README.md)
├── clones/                   # shallow clones, gitignored, refreshed on demand
└── artifacts/                # tracked; small self-contained text files only
    └── lilygolib/            # factory-firmware manifest: URL · release date · sha256 · flash command · chip rev tested (binary off-repo)
```
