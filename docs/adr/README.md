# Architecture Decision Records

Each ADR captures a single non-trivial decision, the alternatives considered, and the consequences. Keep them short — one page is plenty.

Format (per file `NNNN-title.md`):

```markdown
# NNNN — <Decision title>

- **Status:** proposed | accepted | superseded by NNNN
- **Date:** YYYY-MM-DD
- **Context:** what problem are we solving?
- **Decision:** what did we choose?
- **Alternatives:** what else did we consider, and why not?
- **Consequences:** trade-offs we accept (positive and negative).
```

House conventions (carried over from `swarm`): the title is a **claim**, not a topic; consequences are bulleted `(+)` / `(−)` with negatives listed honestly and usually outnumbering positives; each rejected alternative gets an italic name, a verdict, and — where it could be revisited — the trigger that would reopen it; a `Reference basis:` bullet names the bibliography entries (`NN #k`) the decision leans on; a decision that adds a measurable requirement appends a `### <Subsystem> metrics (per ADR NNNN)` block to [`../validation/README.md`](../validation/README.md) and says `Flagged as a validation item.`; amendments are preferred over supersession. Numbers are allocated when a decision is *identified* (the backlog below), not when it is written, so the first ADR written need not be 0001. **Update this index in the same commit as the ADR.**

## Records

- [0001](0001-toolchain-esp-idf-v6-pinned-environment.md) — ESP-IDF v6.0.2 native, pinned: manual clone + per-minor tools root + committed `.envrc`; tilde pins + `dependencies.lock`; no Arduino in any phase; Zephyr rejected; v5.5.5 escape hatch; gate build required. **accepted** (2026-08-20, after the E1 gate passed on hardware)
- [0002](0002-companion-architecture.md) — Companion architecture: the watch is the live path (PDM → FFT → display; all real-time DSP on-device) and the Linux host is the offline path (Praat-grade formants, LTAS/SPR, H1–H2, DTW, Demucs) working on takes transferred over USB; the feature table in the record is normative for proposal §3. **accepted**
- [0003](0003-microphone-path.md) — The microphone path is fixed by silicon: PDM RX on I2S0 only (16-bit slots, CLK 44 / DATA 47), MAX98357A on I2S1 standard mode; 32 kHz / `DSR_8S` (2.048 MHz) is the default and 48 kHz (3.072 MHz) is gated on a measured tolerance test of the SPM1423's 3.25 MHz ceiling; DC removal in software (the S3 has no hardware PDM high-pass), and no NS/AGC/AEC ever in the analysis path. **accepted**
- [0004](0004-split-licensing.md) — Split licensing: Apache-2.0 is the repository default and `host/` alone is GPL-3.0-or-later (own `LICENSE`) so it may import parselmouth/Praat in-process; no code crosses the `host/` boundary; the firmware link line admits only MIT/BSD/Apache-2.0/CC0 (`NOTICE` + SPDX), GPL/AGPL/LGPL/field-of-use code is read-only reference, and only `redistributable=yes` documents are committed. **accepted**
- [0005](0005-no-clinical-claim.md) — No clinical claim: Super Spectral is a practice and measurement instrument for singers; pathology corpora (PVQD, Saarbrücken) are acoustic material only and their labels are never targets; wording rules bind the UI and the docs. **accepted**
- [0013](0013-native-linux-simulator-target.md) — The native-Linux simulator is a first-class target: `spectral_core` and `ui` build on the host (plain CMake, LVGL over SDL) with QEMU as the in-between lane; seams `audio_source` (pdm_mic | file_blob | synthetic) and `display_backend` (st7789_spi | qemu_rgb | sdl) are normative; hardware still owns every metric. **accepted**
- [0014](0014-partition-layout-frozen.md) — The 16 MB partition layout is frozen: two 4 MB OTA slots, no factory app, `ota_0` is the golden recovery image. **accepted**
- [0015](0015-anti-brick-policy.md) — Anti-brick policy for a USB-Serial-JTAG-only board: the recovery path is sacred and every layer of it is tested. **accepted**
- [0016](0016-backlight-gpio45-vdd-spi-strap.md) — GPIO45 backlight PWM is safe on this unit: VDD_SPI is forced to 3.3 V by eFuse. **accepted**
- [0017](0017-no-radio-in-v1-trimmed-component-set.md) — No radio in v1: the build contains only `main` and what it requires (no Wi-Fi, BT, lwIP, OpenThread). **accepted**
- [0018](0018-first-reference-project-study.md) — What the reference projects supply is a specification, not code: xiao-edge-audio's PDM sequence without its block-synchronous framing; esp-dsp's real-input path with our own internal, aligned buffers and periodic windows; a hand-written AXP2101 driver (SensorLib 0.4.1 ships none) with the BMA423 through SensorLib for its Bosch feature blob; the vendor ST7789 argument list and the `(mirror_y, y_gap)` pairing. **accepted**
- [0019](0019-build-system-v1.md) — Stay on ESP-IDF Build System v1 while v2 (`tools/cmakev2`) is a Technical Preview in v6.0; the migration is a pre-registered three-line change. **accepted**

## Backlog of ADRs to write

Pre-registered from the documentation roadmap ([`../roadmap/documentation-roadmap.md`](../roadmap/documentation-roadmap.md) §3 routes open questions here by number). Filenames follow `NNNN-kebab-title.md`.

- 0006 — FFT normalization and window conventions (power spectrum vs PSD, S1/S2/NENBW, periodic windows, dBFS reference, float32 `fc32` only — no `sc16` without a block-floating-point layer) as a single-source spec shared by watch and host. Grounded by Heinzel 2002, Harris 1978, Nuttall 1981.
- 0007 — The analyzer canvas bypasses LVGL (raw `esp_lcd` + ST7789 hardware vertical scroll); LVGL renders chrome only; partial LVGL buffers in internal SRAM — gated on verifying the scroll axis against `MADCTL` (roadmap threshold T4). Grounded by the ST7789V3 datasheet and `esp_lvgl_port/docs/performance.md`.
- 0008 — Ring/twang readout: FHE (Müller et al. 2022) plus Omori peak-to-peak SPR, reported as relative, within-subject, within-session; fixed bands appear only as overlays. Grounded by thematic file 08.
- 0009 — Golden-file strategy: pinned parselmouth → bundled Praat → method → floor/ceiling manifest with sha256; a tolerance table, not equality; plain-CMake host tests plus a QEMU/target backend-agreement test. Grounded by Jadoul 2018, the Praat manual, the ESP-IDF host-apps guide. Spec: [`../validation/golden-files.md`](../validation/golden-files.md).
- 0010 — Preset JSON schema (with explicit bandwidth/ENBW and a mic-EQ slot) owned by `protocols/specs/`; presets live on the littlefs partition. Grounded by the research doc §B.
- 0011 — Spectrogram colormap: a cividis/batlow-class perceptually uniform map, pre-quantized to an RGB565 LUT with ordered dithering. Grounded by Nuñez et al. 2018, Crameri et al. 2020.
- 0012 — Hands-free interaction model: wrist-raise arming via BMA423, haptic confirmation via DRV2605L; the screen is never touched while singing. Grounded by the watchOS / Wear OS design guidelines.
