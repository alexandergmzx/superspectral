# 01 — Overview: the watch is the instrument, the host is the arbiter

**Decision.** One line splits the system, and [ADR 0002](../adr/0002-companion-architecture.md) draws it once: a feature runs **on the watch** if and only if its value depends on being live *and* it can be computed honestly from a single-microphone, uncalibrated, 16-bit capture inside the SRAM and latency budget; everything else runs **on the host**, offline, on recorded takes. The contract between the halves is **files, not a link** — take records and preset JSON owned by [`../../protocols/specs/`](../../protocols/specs/README.md). **Trade-off:** two implementations of one shared front end (window, normalisation, dB reference) that must agree to a stated tolerance forever. The entire golden-file apparatus ([ADR 0009](../adr/0009-golden-file-strategy.md)) and the FFT-conventions ADR ([0006](../adr/0006-fft-normalisation-and-window-conventions.md), `proposed` 2026-08-21) exist *only* to pay that bill.

**Status:** this document synthesises decisions already recorded; it decides nothing. Where a decision is missing it is listed in §7 with the ADR number or roadmap row that owns it. Every unsettled quantity carries `(prov.)` or `TBD`.

---

## 1. System block diagram

```
┌─ T-WATCH S3 — LIVE PATH ─────────────── all real-time DSP on-device (ADR 0002) ──┐
│                                                                                  │
│  SPM1423HM4H-B PDM mic      ┌─────────────── core 1 — DSP task ────────────────┐ │
│  CLK 44 / DATA 47           │  int16 → float × 1/32768                         │ │
│  I2S0 PDM RX, 16-bit  ─────►│  software DC removal (no HW PDM HPF on the S3)   │ │
│  32 kHz / DSR_8S (prov.)    │  window → esp-dsp fc32 real FFT (internal SRAM,  │ │
│        ▲                    │    16-byte aligned) → |X|² → dB                  │ │
│        │ audio_source seam  │  MPM/YIN f0 · band energy · decimation cascade   │ │
│  file_blob · synthetic      └──────────────────────┬───────────────────────────┘ │
│  (QEMU · host · CI)                                │ frame handed over by        │
│  = the injection path                              │ pointer, double-buffered    │
│    (ADR 0013)                                      ▼                             │
│                             ┌─────────────── core 0 — UI task ─────────────────┐ │
│  presets (littlefs) ─JSON──►│  analyzer canvas: raw esp_lcd (+ ST7789 scroll,  │ │
│                             │    gated on T4) · LVGL chrome · touch · PMU      │ │
│  takes (FAT) ◄──binary──────│  take recorder · spectrogram history → PSRAM     │ │
│                             └──────────────────────┬───────────────────────────┘ │
│                                display_backend seam│                             │
│                                ST7789V3 240×240 ◄──┘ SPI                         │
└────────────────────────────────────┬─────────────────────────────────────────────┘
                                     │  the contract is files, not a link:
                                     │  takes + presets over the USB cable that is
                                     ▼  also the only recovery path (ADR 0015)
┌─ LINUX HOST — OFFLINE PATH (host/, GPL-3.0-or-later) ────────────────────────────┐
│  parselmouth/Praat Burg formants + FormantPath · pYIN f0 golden files            │
│  LTAS / SPR / FHE over whole takes · H1–H2 · DTW vs a Demucs-separated stem      │
│  mir_eval corpus evaluation · golden-file generation (host/golden/)              │
│  Never real-time · never linked into firmware · reads takes, writes reports      │
└──────────────────────────────────────────────────────────────────────────────────┘
```

Pins and ports are the measured board facts of [`../hw/twatch-s3-pins.md`](../hw/twatch-s3-pins.md); the capture configuration is fixed by silicon, not preference ([ADR 0003](../adr/0003-microphone-path.md)). The figure is the root [`README.md`](../../README.md) diagram reduced to the split — that file carries the full pin-level version.

---

## 2. Responsibilities — and the explicit *not*

The normative feature-by-feature assignment is the table in [ADR 0002](../adr/0002-companion-architecture.md) and is not duplicated here. What follows is the boundary in prose, because a boundary is defined as much by its exclusions.

| The watch **is** | The watch **is not** |
|---|---|
| The only capture device: one PDM mic, I2S0, 16-bit, 32 kHz default `(prov.)` | Not a second microphone away from the wrist — every acoustic number is a *path* response through this case on this arm |
| The whole real-time chain: capture → DC removal → window → FFT → magnitude / spectrogram / f0 / band energy → pixels | Not a place for non-linear pre-processing. No AFE, NS, AGC, AEC, compressor or limiter, ever — clipping is *flagged* (`\|s\| ≥ 0.99` FS), never tamed ([ADR 0003](../adr/0003-microphone-path.md) decision 7) |
| The owner of every research-question bound: latency, refresh, autonomy, and the acoustic-path f0 error are properties of the firmware alone | Not the arbiter of its own numbers — the reported value is checked against the host's recomputation from the same bytes ([ADR 0009](../adr/0009-golden-file-strategy.md)) |
| Self-sufficient: useful with no phone, no PC, no radio ([ADR 0017](../adr/0017-no-radio-in-v1-trimmed-component-set.md)) | Not a networked device. No Wi-Fi, BT, lwIP or OpenThread in the build at all — the exclusion is structural (`set(COMPONENTS main)`), not a Kconfig wish |
| A recorder of **takes** — a phrase, to the frozen FAT partition ([ADR 0014](../adr/0014-partition-layout-frozen.md)) | Not a session recorder: 6.81 MiB ÷ 64 KB/s ≈ **112 s at 32 kHz** before FAT overhead and before feature records share the file (ADR 0002) |
| A relative instrument: dBFS levels, within-subject/within-session timbre readouts | Not a calibrated sound level meter, and never a formant analyser of record — low-order LPC is a marginal overlay, not the reported number |
| A practice and measurement instrument for singers | Not a clinical device ([ADR 0005](../adr/0005-no-clinical-claim.md)) |

| The host **is** | The host **is not** |
|---|---|
| The reference implementation: Praat-grade formants, pYIN, LTAS/SPR/FHE over whole takes, H1–H2, DTW, Demucs | Not a second implementation of the firmware's FFT — it does not reimplement to compare bit-for-bit; it generates goldens the watch is regressed against |
| The offline depth the wrist cannot honestly provide (metrics needing an SPL co-report, formant bandwidths, or a whole take) | Never in the live loop. It never sees live audio, only takes — so no host latency ever enters a research-question number |
| A directory-shaped licence boundary: [`host/`](../../host/README.md) is GPL-3.0-or-later so it may import parselmouth/Praat in-process ([ADR 0004](../adr/0004-split-licensing.md)) | Not importable by anything outside `host/`, and it imports nothing from outside except files on disk |
| A file consumer: takes in, reports and golden vectors out | Not an RPC peer, a streaming sink, or a live viewer — there is no second transport (ADR 0002 decision 4) |

---

## 3. Data flow

Three flows exist, and only the first is real-time.

**A — the live loop (every hop, forever).** `pdm_mic` fills a DMA ring in `MALLOC_CAP_INTERNAL | MALLOC_CAP_DMA`; the DSP task on core 1 blocks on `i2s_channel_read()` with a finite timeout, converts to `float` in `[-1, 1]` at the [`audio_source`](../../firmware/twatch-s3/components/audio_source/README.md) seam, removes DC, windows, calls the injected `spectral_rfft_fn`, and produces a `spectral_frame_t`. The frame is handed to core 0 **by pointer, double-buffered** — never copied, and the renderer is never given a buffer the DSP task is still writing ([architecture tenet 1](README.md)). Core 0 blits the analyzer canvas through [`display_backend`](../../firmware/twatch-s3/components/display_backend/README.md) and lets LVGL repaint chrome only. Budget shape `(prov.)`: real N = 1024…8192 at 50 frames/s costs ≈ 1.3–8.9 % of one core *(prov.* — research estimates from the gitignored `scratch/research/domainMap.md` §2, **not** from esp-dsp's published benchmark, which stops at 1024 complex points and has no row for the bit-reversal, `cplx2real` or window stages our real path adds; see [`03-dsp-pipeline.md`](03-dsp-pipeline.md) §11*)*; the binding resource is internal SRAM, where a real-8192 `fc32` pipeline measures ≈ 160 KB with stock esp-dsp and ≈ 104 KB with our own `cplx2real` ([esp-dsp study notes §4](../reference-projects/notes/esp-dsp_notes.md)). PSRAM holds spectrogram history — ≈ 10 min of 256-bin columns (ADR 0002) — and is never a DMA endpoint.

**B — the take loop (deliberately rare).** In `RECORDING`, core 0 appends binary records to the FAT `takes` partition: a `TAKE_HEADER` that makes a host recomputation *comparable* (preset id + sha256 of the preset JSON, mic-EQ id, nominal rate and its ppm correction once measured, bit depth, RTC start, device id, writing build's `app_elf_sha256`), `PCM_BLOCK`s that are raw 16-bit and **bit-exact**, and `FEATURE_FRAME`s recording *what was displayed*. Transfer to the host is manual, cable-bound and slow: the only USB-Serial-JTAG throughput measured on this unit is the 16 MB factory read-back at ≈ 10 KB/s ([`../hw/README.md`](../hw/README.md)), a floor rather than the CDC bulk rate, at which a full `takes` partition (0x6D0000 = 7 143 424 B) is ≈ 12 min. The state machine that decides when a take starts and stops is [`12-interaction-model.md`](12-interaction-model.md).

**C — the injection loop (how the two halves are compared).** The same corpus WAV is replayed through `file_blob` into the PCM ring with the microphone bypassed, and analysed by the host from the identical file. Bit-exact `PCM_BLOCK`s are what make "the host recomputes what the watch displayed" testable rather than rhetorical. This is the only path on which a "vs Praat" claim is legitimate ([`../validation/README.md`](../validation/README.md), two-path rule).

---

## 4. Component boundaries

The seams below are normative ([ADR 0013](../adr/0013-native-linux-simulator-target.md)); each component's own README is the contract.

| Component | Owns | Must never | Runs on |
|---|---|---|---|
| [`spectral_core`](../../firmware/twatch-s3/components/spectral_core/README.md) | windows, S1/S2 normalisation, peak picking, f0 front end; `REQUIRES ""` | contain `esp_*`, FreeRTOS, esp-dsp, or allocate in `spectral_process()` | host · QEMU · target |
| [`spectral_fft_backend`](../../firmware/twatch-s3/components/spectral_fft_backend/README.md) | the one place esp-dsp is included; implements `spectral_rfft_fn` | apply scaling (that is `spectral_core`'s job) or put work areas in PSRAM or on a stack | QEMU · target |
| [`audio_source`](../../firmware/twatch-s3/components/audio_source/README.md) | `pdm_mic` \| `file_blob` \| `synthetic`; int16→float once, here | do NS/AGC/AEC; call `i2s_channel_read()` with `portMAX_DELAY` | target (mic) · all (others) |
| [`display_backend`](../../firmware/twatch-s3/components/display_backend/README.md) | `st7789_spi` \| `qemu_rgb` \| `sdl`; hands the UI a panel handle | own the backlight (that is `twatch_bsp`, [ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md)) | per back end |
| [`twatch_bsp`](../../firmware/twatch-s3/components/twatch_bsp/README.md) | every board fact: pins, I²C addresses, AXP2101 rail order, I²S port allocation | let application code name a GPIO; reference GPIO19/20 (`_Static_assert` + CI grep) | target |
| [`ui`](../../firmware/twatch-s3/components/ui/README.md) | LVGL chrome + the raw `esp_lcd` analyzer canvas | touch a register — it sees a `spectral_frame_t` and a panel handle | host (SDL) · QEMU · target |

`spectral_core` being host-buildable is what makes [`host-tests/`](../../host-tests/README.md) (plain CMake, ASan/UBSan, Apache-2.0 — *not* the GPL `host/` tree) possible, and that in turn is the precondition for golden-file validation.

---

## 5. Milestone map

Three firmware milestones are recorded — in this directory's [planned-documents row](README.md), in the roadmap's firmware lane ([`../roadmap/documentation-roadmap.md`](../roadmap/documentation-roadmap.md) §5) and in [proposal §6](../proposal/01-super-spectral-proposal.md). They are gated, not scheduled: **D6 freezes the validation plan before M0 starts**, because the validation plan is what M0 is measured against.

| Milestone | Deliverable | Entry gate | Measured by | Status |
|---|---|---|---|---|
| **M0** — PDM → FFT → USJ dump | Live capture through the real path, FFT on target, spectrum dumped over the USB-Serial-JTAG console. No canvas. | roadmap **D6** (validation plan frozen) + E2 done | sample-rate error, EIN, AOP/clipping flag, dropped-frame rate; [experiment 0001](../validation/experiments/0001-pdm-mic-in-situ-characterization.md) runs alongside | **not started** |
| **M1** — analyzer canvas at 30/50 Hz | Spectrogram + spectrum on the panel; raw `esp_lcd` canvas with LVGL chrome around it | M0; **ADR 0007** written and threshold **T4** resolved | sustained refresh (counter *and* phototransistor), acoustic-to-photon latency ≤ 80 ms mean | **not started** |
| **M2** — presets + takes | The six presets loaded from littlefs, takes written to FAT, host ingestion round-trip | M1; `take-format.md` + `take-transfer.md` written | median \|Δcents\| vs Praat on the injection path; watch↔host agreement rows | **not started** |

**What is reached today** is everything *before* M0 — the environment and the recovery path, both on hardware:

| Reached | Evidence |
|---|---|
| E1 gate: the pinned component set builds **and runs** on ESP-IDF v6.0.2 | [`../../firmware/idf-gate/`](../../firmware/idf-gate/README.md), passed 2026-08-20 — stage 1 zero warnings; stage 2 PMU rails, `AXP2101 IC_TYPE=0x4A`, I²C0 `0x19 0x34 0x51 0x5A`, I²C1 `0x38`, ST7789 at 20 MHz, an LVGL frame on the panel. ADR 0001 accepted on that basis |
| Reproducible build; `dependencies.lock` committed | [ADR 0001](../adr/0001-toolchain-esp-idf-v6-pinned-environment.md); `firmware/twatch-s3/dependencies.lock` |
| Factory flash backup, eFuse baseline, decoded vendor partition table | [`../hw/README.md`](../hw/README.md) ledger (2026-08-20) |
| GPIO45 / VDD_SPI hazard closed by measurement | [ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md) |
| Partition layout frozen; radio removed from the build | [ADR 0014](../adr/0014-partition-layout-frozen.md), [ADR 0017](../adr/0017-no-radio-in-v1-trimmed-component-set.md) |
| Recovery path demonstrated on the watch | [experiment 0002](../validation/experiments/0002-rollback-and-boot-guard-race.md), 2026-08-21: rollback 4/4 PASS, boot-guard race 10/10 (`--before default-reset`) + 5/5 (`--before usb-reset`) |

Everything past that — M0, M1, M2 and all of Phase 1–3 — is **not started**. No feature firmware exists: the tree carries configuration, component contracts, the boot guard, the pin table and an API sketch, and nothing else ([`../../firmware/twatch-s3/README.md`](../../firmware/twatch-s3/README.md)).

---

## 6. Open questions this document could not close

None of these is decided here; each names its home.

| # | Question | Home |
|---|---|---|
| 1 | **M3 and M4 do not exist.** The architecture [planned-documents row](README.md), the roadmap firmware lane (§5) and [proposal §6](../proposal/01-super-spectral-proposal.md) all stop at M2. Whether release hardening, host ingestion or an autonomy milestone get numbers — or whether M2 is the last — is unrouted | roadmap §5 timeline / §6 maintenance |
| 2 | **M1's 50 Hz clause is conditional on unverified silicon.** ADR 0007 is unwritten and threshold **T4** (ST7789 scroll axis vs `MADCTL`) is unmeasured; if T4 trips, the canvas reverts to full-frame blits and 50 Hz leaves the research question | [ADR backlog 0007](../adr/README.md); roadmap T4 |
| 3 | **FFT normalisation and window conventions are now specified but not ratified.** ADR 0006 is **written** (`proposed`, 2026-08-21, nine decisions D1–D9); what is still owed is *acceptance*, and the watch↔host agreement tolerance depends on it | [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md); [`../../dsp/design/`](../../dsp/design/README.md) |
| 4 | **M2 has no format to write.** `take-format.md`, `take-transfer.md` and `feature-frame-semantics.md` are planned, not written; ADR 0002 states the constraints on them but not the layout, and the transport (USB MSC vs console dump) is ADR-gated | [`../../protocols/specs/`](../../protocols/specs/README.md); roadmap D5/D6 |
| 5 | **The sample rate is two-valued.** 48 kHz stays gated on experiment 0001 clause 4 / threshold **T3**; until it runs, the preset schema, bin-mapping tables and window tables must tolerate both 32 kHz and 48 kHz | [ADR 0003](../adr/0003-microphone-path.md); roadmap T3 |
| 6 | **The capture-path power term is `TBD`.** The *rail identity* is now closed from the schematic (sheet 6 of [01 #6](../bibliography/01-datasheets.md): mic VCC on `+3V3`, which is AXP2101 **DC1** — the SoC's own buck — so the microphone is not power-gateable at all); what remains `TBD` is its **current** on this board, which the ≥ 3 h autonomy bound still carries as an unbudgeted term | [`06-power-budget.md`](06-power-budget.md) §2; roadmap Q26 |
| 7 | **§2's responsibility split is provisional in one direction.** If threshold **T2** trips, every timbre and level metric moves host-offline as an *amendment to ADR 0002*, and this document's tables follow it | [ADR 0002](../adr/0002-companion-architecture.md) T2 clause; [experiment 0001](../validation/experiments/0001-pdm-mic-in-situ-characterization.md) |
| 8 | **The hands-free interaction model that decides take boundaries is `proposed`.** Gesture set, timings and the voice-onset question are the author's calls | [ADR 0012](../adr/0012-hands-free-interaction.md); [`12-interaction-model.md`](12-interaction-model.md) §8 |

---

Reference basis: [ADR 0002](../adr/0002-companion-architecture.md) for the split, the normative feature table, the take-format constraints and the T2 pivot; [ADR 0003](../adr/0003-microphone-path.md) for the capture path (I2S0-only PDM RX, 16-bit slots, 32 kHz/`DSR_8S`, software DC removal, no NS/AGC/AEC), grounded in `driver/i2s_pdm.h` + `i2s_pdm.c` ([02 #15](../bibliography/02-application-notes.md)), `soc_caps.h` for esp32s3 ([02 #16](../bibliography/02-application-notes.md)) and the Knowles SPM1423HM4H-B spec ([01 #9](../bibliography/01-datasheets.md)); [ADR 0013](../adr/0013-native-linux-simulator-target.md) for the `audio_source`/`display_backend` seams and the three lanes; [ADR 0009](../adr/0009-golden-file-strategy.md) and parselmouth ([05 #55](../bibliography/05-papers.md)) for the host-as-arbiter role; [ADR 0014](../adr/0014-partition-layout-frozen.md), [0015](../adr/0015-anti-brick-policy.md), [0017](../adr/0017-no-radio-in-v1-trimmed-component-set.md) for the storage, recovery and radio boundaries; [ADR 0004](../adr/0004-split-licensing.md) and [0005](../adr/0005-no-clinical-claim.md) for the licence and claim boundaries; esp-dsp ([06 #1](../bibliography/06-reference-projects.md)) with its published benchmarks ([02 #21](../bibliography/02-application-notes.md)) and our own [esp-dsp study notes](../reference-projects/notes/esp-dsp_notes.md) for the compute and SRAM envelope; MPM ([05 #8](../bibliography/05-papers.md)) for the on-device f0 choice; the founding [research document](../research/00-linux-analyzer-architecture-and-build-guide.md) for the six presets and the live/offline ancestry. Measured on this unit: [`../hw/README.md`](../hw/README.md) (eFuse baseline, flash identity, USB-Serial-JTAG read rate), [`../../firmware/idf-gate/`](../../firmware/idf-gate/README.md) (E1 gate, 2026-08-20) and [experiment 0002](../validation/experiments/0002-rollback-and-boot-guard-race.md) (rollback and boot-guard race, 2026-08-21).
