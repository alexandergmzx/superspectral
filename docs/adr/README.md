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
- [0016](0016-backlight-gpio45-vdd-spi-strap.md) — GPIO45 backlight PWM is safe on this unit: VDD_SPI is forced to 3.3 V by eFuse. **accepted**
- [0017](0017-no-radio-in-v1-trimmed-component-set.md) — No radio in v1: the build contains only `main` and what it requires (no Wi-Fi, BT, lwIP, OpenThread). **accepted**

## Backlog of ADRs to write

Pre-registered from the documentation roadmap ([`../roadmap/documentation-roadmap.md`](../roadmap/documentation-roadmap.md) §3 routes open questions here by number). Filenames follow `NNNN-kebab-title.md`; 0004 is already named by `NOTICE` as `0004-split-licensing.md`.

- 0002 — Companion architecture: the watch is the live path (capture, real-time spectrum/spectrogram/f0/band energy, take recording); the Linux host is the offline path (Praat-grade formants, LTAS/SPR over takes, H1–H2 with Iseli–Alwan correction, DTW, Demucs); the on-device vs host feature table is normative for proposal §3. Grounded by the research doc §B and the DSP envelope.
- 0003 — Microphone path: PDM RX on I2S0 only (CLK GPIO44 / DATA GPIO47, 16-bit slots), MAX98357A on I2S1; 32 kHz / `DSR_8S` default; 48 kHz gated on a measured 3.072 MHz clock; DC removal in software (no hardware PDM high-pass on the S3 in the pinned IDF); no NS/AGC/AEC ever in the analysis path. Grounded by the Knowles datasheet, `driver/i2s_pdm.h`, the `i2s_pdm.c` guards.
- 0004 — **Split licensing**: Apache-2.0 for repo/firmware/docs/tooling; `host/` GPL-3.0-or-later with its own `LICENSE` so it may import parselmouth in-process; the firmware link line admits only MIT/BSD/Apache code (`NOTICE` + SPDX headers); GPL/AGPL/LGPL/field-of-use code is reference-only on the watch; no code crosses the `host/` boundary in either direction. Grounded by LGPL-2.1 §6, the FSF Apache↔GPL compatibility statement (one-way), Parselmouth GPLv3. Filename: `0004-split-licensing.md`.
- 0005 — No clinical claim: Super Spectral is not a medical device; pathology corpora (PVQD, Saarbrücken) are used only as acoustic material. Grounded by MDR 2017/745 Annex VIII Rule 11, MDCG 2019-11, FDA *General Wellness* policy.
- 0006 — FFT normalization and window conventions (power spectrum vs PSD, S1/S2/NENBW, periodic windows, dBFS reference, float32 `fc32` only — no `sc16` without a block-floating-point layer) as a single-source spec shared by watch and host. Grounded by Heinzel 2002, Harris 1978, Nuttall 1981.
- 0007 — The analyzer canvas bypasses LVGL (raw `esp_lcd` + ST7789 hardware vertical scroll); LVGL renders chrome only; partial LVGL buffers in internal SRAM — gated on verifying the scroll axis against `MADCTL` (roadmap threshold T4). Grounded by the ST7789V3 datasheet and `esp_lvgl_port/docs/performance.md`.
- 0008 — Ring/twang readout: FHE (Müller et al. 2022) plus Omori peak-to-peak SPR, reported as relative, within-subject, within-session; fixed bands appear only as overlays. Grounded by thematic file 08.
- 0009 — Golden-file strategy: pinned parselmouth → bundled Praat → method → floor/ceiling manifest with sha256; a tolerance table, not equality; plain-CMake host tests plus a QEMU/target backend-agreement test. Grounded by Jadoul 2018, the Praat manual, the ESP-IDF host-apps guide. Spec: [`../validation/golden-files.md`](../validation/golden-files.md).
- 0010 — Preset JSON schema (with explicit bandwidth/ENBW and a mic-EQ slot) owned by `protocols/specs/`; presets live on the littlefs partition. Grounded by the research doc §B.
- 0011 — Spectrogram colormap: a cividis/batlow-class perceptually uniform map, pre-quantized to an RGB565 LUT with ordered dithering. Grounded by Nuñez et al. 2018, Crameri et al. 2020.
- 0012 — Hands-free interaction model: wrist-raise arming via BMA423, haptic confirmation via DRV2605L; the screen is never touched while singing. Grounded by the watchOS / Wear OS design guidelines.
- 0013 — Native-Linux simulator target (LVGL simulator + the DSP core on host) as the UI design loop and golden-file harness. Idea only from My-TTGO-Watch (GPL-2.0, no code).
- 0014 — **Partition layout frozen**: `ota_0`/`ota_1` 4 MB each, no factory partition, `presets` littlefs 1 MB, `takes` FAT, `coredump` 60 K, `nvs_keys`, `phy_init` retained; `ota_0` holds the golden recovery image and development builds flash to `ota_1` only; changing offsets breaks every fielded unit. Grounded by the partition-tables guide and the devenv critique (B2).
- 0015 — **Anti-brick policy**: 3 s unconditional boot guard, `_Static_assert` on every pin ≠ 19/20 plus a CI grep, rollback with mark-valid only after display + touch + PMU + USB are confirmed, sleep gating, console permanently on USB-Serial-JTAG, eFuses read-only for life, a deliberate decision on the AXP2101 4 s PMU watchdog. Grounded by the USB-Serial-JTAG console guide and the espefuse docs.
- 0018 — First reference-project study ADR: takeaways from xiao-edge-audio, LilyGoLib register sequences, SensorLib. Grounded by bibliography file 06.
- 0019 — Build System v1 now (`project.cmake`); migrate to Build System v2 when it leaves Technical Preview. Grounded by the build-system-v2 guide.
