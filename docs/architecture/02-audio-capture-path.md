# 02 — Audio capture path: one PDM microphone, one seam, everything linear

**Status:** design note behind [ADR 0003](../adr/0003-microphone-path.md) (**accepted**). It decides nothing; it makes ADR 0003 operational — the call sequence, the arithmetic that turns a preset hop into DMA numbers, and the two traps that cost bring-up time exactly once. Where a number is not yet settled it is `(prov.)` and §11 says who closes it. The 48 kHz row is **gated on roadmap threshold T3** and no part of this note may be read as making it available.

## 1. The decision, and what it costs

**Capture is PDM RX on I2S0, 16-bit, mono, 32 kHz by default, and everything between the microphone and the FFT is linear, fixed and recorded.** Three of those are not preferences: `esp_driver_i2s/i2s_pdm.c` rejects a PDM handle on I2S1, `i2s_pdm_rx_slot_config_t` documents both width fields as *"only support 16 bits for PDM mode"*, and `SOC_I2S_SUPPORTS_PDM_RX_HP_FILTER` is absent from the S3's `soc_caps.h` at the pinned tag, so the high-pass has to be ours ([ADR 0003](../adr/0003-microphone-path.md) context; [02 #15, #16](../bibliography/02-application-notes.md)).

The one thing this note does choose the *shape* of is the **`audio_source` seam** — one indirection per analysis block, in the hot path, on a device with a 240 MHz budget. It buys three things that cannot be bought any other way: the digital-injection validation path (corpus WAV in, microphone bypassed — the only path that may carry a "≤ 5 cents vs Praat" claim, [validation](../validation/README.md) two-path rule), a DSP stack that runs on a lane QEMU can execute (QEMU emulates **no** I²S — [ADR 0013](../adr/0013-native-linux-simulator-target.md)), and a Tier-0 synthetic generator with exact ground truth. The cost is that every downstream component is written against a block-of-floats contract instead of against the driver, and that the microphone is only ever exercised on hardware.

## 2. The chain

```
  acoustic path                                      digital-injection path
  ────────────                                       ──────────────────────
  singer → case/port → SPM1423HM4H-B                 corpus WAV / Tier-0 synth
                       (always-on 3.3 V rail, prov.)              │
             CLK 44 ──►│                                          │
             DAT 47 ◄──┘                                          │
                       │                                          │
        I2S0 PDM RX, master, PDM2PCM decimator, 16-bit mono       │
                       │                                          │
        driver DMA ring  dma_desc_num × dma_frame_num             │
        (MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA, driver-owned)        │
                       │  i2s_channel_read(finite timeout)        │
                       ▼                                          ▼
   ┌───────────────────────────  audio_source seam  ──────────────────────────┐
   │  pdm_mic          int16 → float × 1/32768   →  clipping flag (|s| ≥ 0.99)│
   │  file_blob        (raw mean/RMS logged here for experiment 0001)         │
   │  synthetic        → DC blocker (stateful, streaming, dc_blocker_hz)      │
   └────────────────────────────────┬─────────────────────────────────────────┘
                                    ▼
              PCM ring, float [-1,1), internal SRAM, ≥ N_max + hop_max
                                    │  every hop_samples
                                    ▼
              window → real FFT → |X|² → dB          (03-dsp-pipeline)
                                    │
                take recorder (raw int16 + header naming the filter applied)

  I2S1 std TX ─ BCLK 48 / WS 15 / DOUT 46 ─► MAX98357A ─► calibration tone only
```

## 3. Clock: `sample_rate_hz` × DSR → PDM clock

`i2s_pdm_rx_calculate_clock()` sets `bclk = sample_rate_hz × I2S_LL_PDM_BCK_FACTOR × (dn_sample_mode == I2S_PDM_DSR_16S ? 2 : 1)`, and `I2S_LL_PDM_BCK_FACTOR` is **64** on the S3 (`esp_hal_i2s/esp32s3/include/hal/i2s_ll.h`, v6.0.2). That one line is the whole table. The mic's clock window is **1.0–3.25 MHz** ([01 #9](../bibliography/01-datasheets.md), revision-pinned, read from a raster table).

| `sample_rate_hz` | `dn_sample_mode` | PDM CLK | Nyquist | Against 1.0–3.25 MHz | Status |
|---|---|---|---|---|---|
| 16 000 | `DSR_8S` | 1.024 MHz | 8 kHz | 2.4 % above the floor | not used — 8 kHz Nyquist truncates the 5–8 kHz noise band |
| 16 000 | `DSR_16S` | 2.048 MHz | 8 kHz | mid-window | low-power preset option (ADR 0003 d.4) |
| **32 000** | **`DSR_8S`** | **2.048 MHz** | **16 kHz** | mid-window | **default** — every committed watch preset |
| 32 000 | `DSR_16S` | 4.096 MHz | 16 kHz | 26 % **over** the ceiling | excluded by arithmetic |
| 48 000 | `DSR_8S` | 3.072 MHz | 24 kHz | 178 kHz of headroom — 5.5 % of the 3.25 MHz ceiling, 5.8 % of 3.072 MHz | **gated on T3** — [experiment 0001](../validation/experiments/0001-pdm-mic-in-situ-characterization.md) clause 4 |
| 48 000 | `DSR_16S` | 6.144 MHz | 24 kHz | 89 % **over** the ceiling | excluded by arithmetic |

Two ways reach 2.048 MHz (32 kHz/`DSR_8S` and 16 kHz/`DSR_16S`), which makes the DSR path itself falsifiable during bring-up: the same clock must yield two different PCM rates. The loader refuses `sample_rate_hz: 48000` for a `watch` target until T3 resolves ([ADR 0010](../adr/0010-preset-schema.md) d.3); `stem_analysis` is `["host"]` and names 48 kHz legitimately, because the host reads files, not microphones.

Sample-rate *accuracy* is a separate matter and is not fixed by this table: the S3 has **no APLL**, so the I²S clock comes from PLL/XTAL through a fractional divider and the error is crystal ppm plus divider resolution. That is a measured row (≤ 200 ppm, GPSDO) in the [validation plan](../validation/README.md), and its correction constant lives in the preset, not here.

## 4. Init sequence — the real calls, in order

Preconditions: `twatch_bsp` PMU bring-up has returned (§10.2), and `PRIV_REQUIRES esp_driver_i2s` is declared — on v6.0.2 the legacy `driver` umbrella no longer pulls it in ([xiao-edge-audio notes](../reference-projects/notes/xiao-edge-audio_notes.md) §2.1).

```c
i2s_chan_config_t chan = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
chan.dma_desc_num  = 8;      /* (prov.) - §5 */
chan.dma_frame_num = 320;    /* (prov.) - §5 */
chan.allow_pd      = false;  /* macro default; no sleep gate in v1 (ADR 0015) */
ESP_ERROR_CHECK(i2s_new_channel(&chan, NULL, &s_rx));   /* TX handle NULL: RX-only */

i2s_pdm_rx_config_t cfg = {
    .clk_cfg  = I2S_PDM_RX_CLK_DEFAULT_CONFIG(preset->analysis.sample_rate_hz),
    .slot_cfg = I2S_PDM_RX_SLOT_PCM_FMT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT,
                                                       I2S_SLOT_MODE_MONO),
    .gpio_cfg = { .clk = TWATCH_PIN_PDM_CLK,    /* GPIO44 */
                  .din = TWATCH_PIN_PDM_DATA,   /* GPIO47 */
                  .invert_flags = { .clk_inv = false } },
};
cfg.clk_cfg.dn_sample_mode = I2S_PDM_DSR_8S;   /* explicit; §3 */
cfg.slot_cfg.slot_mask     = s_slot_mask;      /* LEFT or RIGHT - §10.1 */
ESP_ERROR_CHECK(i2s_channel_init_pdm_rx_mode(s_rx, &cfg));

static const i2s_event_callbacks_t cbs = { .on_recv_q_ovf = pdm_ovf_isr };  /* §6 */
ESP_ERROR_CHECK(i2s_channel_register_event_callback(s_rx, &cbs, &s_stats));

i2s_chan_info_t info;                                   /* clock readback, §10.1 */
ESP_ERROR_CHECK(i2s_channel_get_info(s_rx, &info));     /* info.bclk_hz == PDM CLK */

ESP_ERROR_CHECK(i2s_channel_enable(s_rx));
```

Five facts this ordering encodes, each read from the pinned tree:

1. **`I2S_PDM_RX_SLOT_PCM_FMT_DEFAULT_CONFIG`, not `I2S_PDM_RX_SLOT_DEFAULT_CONFIG`** — the latter survives in v6.0.2 only as a `@cond` alias. On a target **without** `SOC_I2S_SUPPORTS_PDM_RX_HP_FILTER` the macro expands without `hp_en` / `hp_cut_off_freq_hz` / `amplify_num`, and those fields do not exist in `i2s_pdm_rx_slot_config_t` either — both the macro and the struct are guarded on that symbol, not on `SOC_I2S_SUPPORTS_PDM2PCM`. `soc/esp32s3/include/soc/soc_caps.h` defines `PDM`, `PDM_TX`, `PDM_RX` and `PDM2PCM` and **not** `PDM_RX_HP_FILTER`, so the S3 has no hardware high-pass — which is why §7's blocker is not optional. (The distinction matters: the ESP32-P4 defines *both* symbols, so on that target the same macro does emit `hp_en = true`, `hp_cut_off_freq_hz = 35.5`, `amplify_num = 1`.)
2. **The macro sets `slot_mask = I2S_PDM_SLOT_LEFT` for mono.** Overwriting it explicitly is the point of §10.1, not decoration.
3. **The callback must be registered before `i2s_channel_enable()`** — `i2s_channel_register_event_callback()` is documented as REGISTERED/READY-only, i.e. before the channel starts.
4. **`i2s_channel_get_info()` returns the achieved `bclk_hz`**, so §3's table is checkable at boot rather than asserted. It says nothing about whether the microphone is answering.
5. **Reads use a finite timeout, never `portMAX_DELAY`.** A stalled I²S must surface as `ESP_ERR_TIMEOUT` that the capture task counts and escalates; blocking forever hides the fault from a task watchdog that only watches idle tasks ([pitfalls D1](../devenv/pitfalls.md), ADR 0003 d.8).

## 5. DMA and ring sizing, derived from the preset hop

Fixed by the driver (v6.0.2, `i2s_common.c`): mono 16-bit PDM ⇒ `bytes_per_frame` = 2 (`i2s_get_buf_size()` = `bytes_per_sample × active_slot`, `active_slot = 1` for `I2S_SLOT_MODE_MONO`); one descriptor is capped at `I2S_DMA_BUFFER_MAX_SIZE` = **4092 B** on the S3 (`SOC_CACHE_INTERNAL_MEM_VIA_L1CACHE` is undefined for esp32s3, so the 4B-aligned constant applies) ⇒ `dma_frame_num ≤ 2046`, above which the driver silently clamps and logs *"dma frame num is out of dma buffer size"*. Descriptors and buffers are allocated by the driver itself with `MALLOC_CAP_INTERNAL | MALLOC_CAP_DMA` — the ADR 0003 d.8 placement rule therefore binds **our** buffers, not the driver's.

The hops come from the committed presets ([`../../protocols/presets/`](../../protocols/presets/live_singing.json), all watch presets at 32 kHz):

| Preset | `interval_ms` | `hop_samples` | `fft_size` |
|---|---|---|---|
| `diction_consonants` | 10 | 320 | 1024 |
| `live_singing` | 20 | 640 | 4096 |
| `sustained_pitch_lab` · `vowel_formant_study` · `room_noise_floor` | 40 | 1280 | 8192 |

Three inequalities, and then arithmetic:

- **C1 — granularity ≤ shortest hop.** `dma_frame_num ≤ min(hop_samples) = 320`. A descriptor longer than the hop makes `interval_ms` unachievable by construction.
- **C2 — granularity divides every hop.** `gcd(320, 640, 1280) = 320`, so any divisor of 320 leaves the read aligned with the hop boundary and never straddles two frames.
- **C3 — ring depth ≥ the worst time the capture task can be away from `i2s_channel_read()`**, which is one analysis frame at the largest N plus scheduling jitter on core 1.

| `dma_desc_num` × `dma_frame_num` | B / descriptor | ring | samples | ring @ 32 kHz | granularity @ 32 kHz |
|---|---|---|---|---|---|
| driver default 6 × 240 | 480 | 2 880 B | 1 440 | 45.0 ms | 7.5 ms |
| **ours (prov.) 8 × 320** | 640 | 5 120 B | 2 560 | **80.0 ms** | **10.0 ms** |
| driver ceiling n × 2046 | 4 092 | — | — | — | 63.9 ms |

80 ms is 8 hops of `diction_consonants`, 4 of `live_singing`, 2 of the 40 ms presets. Against a per-frame DSP cost of ≈ 1.2 ms at N = 4096 and ≈ 1.8 ms at N = 8192 *(prov., derived from the research-synthesis envelope in the gitignored `scratch/research/domainMap.md` — 6.2 % / 8.9 % of one core at 50 Hz; the on-target number is roadmap H13)*, the ring is ~44× the largest frame time. That is slack, not a guarantee: the value that matters is measured, not derived — see §6.

**Our PCM ring** is separate from the driver's and holds `float`: it must carry a full analysis window plus the hop being written, so `ring_samples ≥ N_max + hop_max` = 8192 + 1280 = 9 472 ⇒ **16 384 samples (prov.)**, a power of two so the wrap is a mask — **64 KB as `float`**, and the largest single internal-SRAM allocation in the capture path. It is a `memcpy` destination, not a DMA target, so it needs `MALLOC_CAP_INTERNAL` for bandwidth reasons ([pitfalls D5/D7](../devenv/pitfalls.md)) rather than `MALLOC_CAP_DMA`. Storing `int16` instead would halve it but would move the conversion after the ring, which ADR 0003 d.2 forbids; those 64 KB therefore sit alongside the ≈ 104 KB FFT working set at real-8192 *(prov.* — `fft2r` with our own `cplx2real`, [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md) D5/D6; the earlier 112 KB and 144 KB figures are superseded, [`03-dsp-pipeline.md`](03-dsp-pipeline.md) §4.1*)* in the budget owned by `09-memory-and-task-topology.md`, and the final depth is open (§11 row 1).

Capture's contribution to the ≤ 80 ms acoustic-to-photon bound is `descriptor wait (≤ 10 ms prov.) + hop fill (10–40 ms by preset)`; the rest belongs to `03-dsp-pipeline.md` and `04-display-render-path.md`, and the total is a measured row, not a sum of estimates.

## 6. The overrun callback and the dropped-frame metric

`i2s_event_callbacks_t.on_recv_q_ovf` is **always** registered. The reason is not diagnostics, it is that the [validation plan](../validation/README.md) has a row — *Dropped-frame rate < 1 % over 1 h* — whose only instrument is this counter. An unregistered overrun is a silent one, and a silent one turns a measurable metric into a subjective impression of "it seemed fine". The precedent project registers no callback at all and its DMA overruns are invisible ([xiao-edge-audio notes](../reference-projects/notes/xiao-edge-audio_notes.md) §2.2).

Rules for the ISR: it runs in interrupt context, so it increments a counter in internal SRAM and returns — no logging, no heap, no DSP ([pitfalls D3](../devenv/pitfalls.md)). The counter is exported next to the capture task's own `ESP_ERR_TIMEOUT` count and its short-read count; the three distinguish *producer overran consumer*, *producer stopped* and *consumer asked for more than exists*. Both counters are written into the take header so a recorded take carries its own dropout provenance rather than a claim made afterwards.

One case is worth naming because it is where the counter earns its keep: writing a take to flash disables the cache, and a non-IRAM ISR does not run while it is disabled — the documented cause of dropouts correlated with filesystem writes ([pitfalls D7](../devenv/pitfalls.md)). Whether `CONFIG_I2S_ISR_IRAM_SAFE` should therefore be enabled is **not settled in any ADR** and is recorded as an open question in §11.

## 7. The int16 → float seam, and where the DC blocker sits

The conversion happens **exactly once**, inside `audio_source`, so that every back end delivers one contract to `spectral_core`: mono `float` in `[-1, 1)`, block-aligned to the hop.

```c
s[i] = (float)pcm[i] * (1.0f / 32768.0f);   /* -32768 → -1.0 exactly; +32767 → 0.99997 */
```

Order in the block, and why each step is where it is:

1. **Raw mean and RMS** over the un-converted block. This is the number [experiment 0001](../validation/experiments/0001-pdm-mic-in-situ-characterization.md) needs (roadmap Q23: how much DC the PDM2PCM filter leaves), and it only exists before anything filters it. The characterization build runs with the blocker off entirely — raw PCM is the point of that experiment.
2. **Convert to float.**
3. **Clipping flag**, `|s| ≥ 0.99` FS. Before the blocker, because full scale is a statement about the converter's range and the blocker changes the sample value. Flagged, never tamed — no limiter, no AGC (ADR 0003 d.7).
4. **DC blocker**, a single stateful streaming filter whose state carries across blocks, at the preset's `dc_blocker_hz` (**20 Hz, listed in the preset's own `provisional` array**), below the 65 Hz (C2) f0 floor of the validation plan. It runs here, not per analysis frame, because frames overlap by up to 84 % and re-running a stateful IIR over overlapping windows would not produce the same filter twice.
5. **Into the PCM ring.** The take recorder writes raw `int16`; the take header records which filter was applied, so the host can reproduce or invert exactly what the watch did — the precondition for the "vs Praat" claim.

The filter itself is a `spectral_core` artefact shared with the host, not an esp-dsp call site: `dsps_biquad_gen_hpf_f32(c, f_hz/fs, 0.7071f)` is a correct RBJ high-pass (note `Fs = 1`, so the argument is cycles/sample — 20/32000 = 0.000625), but at that normalised frequency the float32 rounding of `a1` starts to matter, and a first-order blocker or a host/device tolerance agreement is the safer construction ([esp-dsp notes](../reference-projects/notes/esp-dsp_notes.md) §6). Cost is not the issue: the published S3 benchmark is 17 552 cycles per 1024 samples for `dsps_biquad_f32` ⇒ ≈ 0.23 % of one 240 MHz core at 32 kHz. Which form ships is an ADR 0006 question (§11).

No noise suppression, no AGC, no AEC, ever, in the analysis path — non-linear processing destroys exactly what is measured (CLAUDE.md never-rule 8; ADR 0003 d.7).

## 8. The `audio_source` back ends

| Back end | Runs on | Enters the chain at | Ground truth | Cannot measure |
|---|---|---|---|---|
| `pdm_mic` | hardware only | the DMA ring (§4) | none — acoustic path | — |
| `file_blob` | hardware, QEMU | the seam (§7), post-conversion | the take's Praat golden file | sample-rate error, EIN, AOP, case response |
| `synthetic` | hardware, QEMU, host | the seam, generated in `float` | exact by construction (Tier-0, [`datasets/`](../../datasets/README.md)) | same |

The seam exists because two independent constraints demand it and neither is negotiable. **QEMU emulates no I²S** ([ADR 0013](../adr/0013-native-linux-simulator-target.md)), so a lane that runs real Xtensa instructions and real esp-dsp `_aes3` kernels can only be fed from a file or a generator. And the **digital-injection path bypasses the microphone by definition** ([validation](../validation/README.md) two-path rule) — it is what isolates algorithm error from acoustics, and it is the only path on which a "≤ 5 cents vs Praat" claim is legitimate. A capture path written directly against `i2s_channel_read()` forfeits both.

What the injection path skips is precisely the DMA ring, the PDM clock and the microphone, so it can carry no row that depends on them: rate error, noise floor, AOP and every case/port response number are acoustic-path only. The seam is at **block** granularity, one call per hop, not per sample.

## 9. The calibration tone on I2S1

Two independent `i2s_new_channel()` calls with different `i2s_chan_config_t.id`; full duplex on one port is impossible here because PDM RX and standard TX can never agree on one slot/clock configuration ([ADR 0003](../adr/0003-microphone-path.md) alternatives). The MAX98357A is `i2s_channel_init_std_mode()` (Philips), BCLK 48 / WS 15 / DOUT 46, and exists in v1 **only** to validate FFT bin mapping and acoustic-path geometry — not as a playback feature.

Two hardware notes: GPIO46 is a strapping pin (ROM-message / download-mode qualifier with GPIO0), so I2S1 is configured after boot and no external pull-up is ever added — the amp input is high-impedance at reset ([pins doc](../hw/twatch-s3-pins.md) cautions). And the amplifier rail is **DLDO1 (prov.)**, which LilyGoLib never assigns a voltage to (register `0x99` is left at its eFuse default), so enabling it means setting its voltage first ([study notes](../reference-projects/notes/lilygolib-axp2101_notes.md) §5, §6.3). Do not copy the vendor's `initAmplifier()` rate: it passes **160000 Hz**, a digit slip for 16 000 that survives because `playWAV()` overwrites it from the WAV header (roadmap Q19).

## 10. Two bring-up traps

### 10.1 The slot mask — silence is indistinguishable from a dead microphone

`i2s_types.h` defines the mask by the *strap on the microphone's SELECT pin*: `I2S_PDM_SLOT_RIGHT` = `BIT(0)` is *"the PDM device whose 'select' pin is pulled up"*, `I2S_PDM_SLOT_LEFT` = `BIT(1)` is *pulled down*. Which one the SPM1423 is strapped to is **open** (roadmap **H7** / H-slot), and the vendor gives three different answers: `PDM.cpp` uses `I2S_CHANNEL_FMT_ONLY_RIGHT`, `initMicrophone()` uses `I2S_STD_SLOT_LEFT`, and the factory example de-interleaves a mono stream as if it were stereo ([study notes](../reference-projects/notes/lilygolib-axp2101_notes.md) §5.3).

The failure mode is the trap: with the wrong mask the DMA still runs, `i2s_channel_read()` still returns full blocks on time, `i2s_channel_get_info()` still reports the right `bclk_hz`, and the overrun counter still reads zero — the samples are just constant. That is byte-for-byte what a dead rail, a wrong CLK pin or a dead microphone look like. So the clock readback of §4 does **not** discriminate, and the procedure is fixed by [experiment 0001](../validation/experiments/0001-pdm-mic-in-situ-characterization.md) §Setup clause 4: **both masks are captured in the same run, before anyone diagnoses anything else.**

### 10.2 The rail — now closed from the schematic

The *pin-voltage* half is **closed**: `VDD_SPI_FORCE = True`, `VDD_SPI_TIEH = VDD3P3_RTC_IO`, `VDD_SPI_XPD = True` on this unit, so VDD_SPI is eFuse-forced to 3.3 V, GPIO47 (PDM DATA) and GPIO48 (I²S BCLK) sit in the 3.3 V domain, and the 1.8 V-domain concern does not apply here ([ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md); [`../hw/README.md`](../hw/README.md) ledger, read 2026-08-20). The flash on this unit reads JEDEC `ef 4018`, a 3.3 V W25Q128JV-class part, so the schematic's 1.8 V marking is unverified per unit ([pins doc](../hw/twatch-s3-pins.md)).

The *rail-identity* half is **closed**, read directly off sheet 6 of the filed schematic ([01 #6](../bibliography/01-datasheets.md), `lilygo_t-watch-s3_schematic_v1.4.pdf`, read 2026-08-21):

- **The microphone is on `+3V3`.** U18 `SPM1423HM4H-B` pin 6 `VCC` sits on the net `+3V3`, decoupled by C2 100 nF/16 V; R81 (`NC`) is an unpopulated option on that node, not a series element. Tracing `+3V3` back on sheet 1: `+3V3` ← R2 `0R` ← `VDD3V3`, and `VDD3V3` is the **AXP2101 DCDC1** output node (pins 21 `FB1` / 22 `LX1` / 23 `VIN1`, inductor L5003 2.2 µH/1.5 A, C8229 22 µF). Sheet 2 shows the ESP32-S3 supplied from the same `+3V3`. So the microphone is on **DC1 — the SoC's own buck** — which is stronger than the code reading suggested: the mic is not merely *not gated*, it **cannot** be gated without cutting the SoC.
- **DLDO1 is the amplifier rail.** `SPK_VDD` (U27 `MAX98357A` pins 7/8 `VDD`) is fed from `DLDO1` through **R18 `0R`, populated**; the alternative feed from `+3V3` through **R76 is `NC`**. This confirms the two vendor witnesses — LilyGoLib's `RecordWAV` records before `powerControl(POWER_SPEAK, true)`, `initPMU()` has already run `disableDLDO1()`, and TTGO's branch carries `enableDLDO1(); //! Speaker` ([study notes](../reference-projects/notes/lilygolib-axp2101_notes.md) §6.3) — and retires them as *evidence* in favour of the drawing.

Roadmap **Q14 / H2 / H-rail** and open question 6 below are therefore answered from a source already in hand; what remains `TBD` is the mic's **current on this rail**, which belongs to [`06-power-budget.md`](06-power-budget.md), not here.

Three consequences for this component: the firmware does **not** attempt to power-gate the microphone, and now cannot — DC1 is the SoC rail and is never written by firmware ([`06-power-budget.md`](06-power-budget.md) §2); the capture-path term of the power budget is still a `TBD` **current** against the ≥ 3 h autonomy bound; and I2S0 is enabled only after the `twatch_bsp` PMU bring-up sequence has settled. One risk this reading removes for good: disabling DLDO1 at boot is safe and does **not** silence the microphone.

## 11. Open questions this note surfaces

| # | Question | Why it is open | Routed to |
|---|---|---|---|
| 1 | Final `dma_desc_num` / `dma_frame_num` and PCM-ring depth | §5's values satisfy C1–C3 but are derived from a research-estimate frame time, not measured | [validation](../validation/README.md) *Dropped-frame rate* row + roadmap **H13** |
| ~~2~~ | ~~DC blocker **form**~~ — **decided**: the one-pole–one-zero form `y[n] = x[n] − x[n−1] + R·y[n−1]`, `R = 1 − 2π·f_c/f_s` (0.996073 at 20 Hz / 32 kHz), float32, before the window, `R` recorded per take | [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md) **D7**, written 2026-08-21 (`proposed` — acceptance still owed) | ADR 0006 D7 |
| 3 | DC blocker **corner**: 20 Hz `(prov.)`, in every preset's `provisional` array | raised only by measurement of the offset PDM2PCM leaves | [experiment 0001](../validation/experiments/0001-pdm-mic-in-situ-characterization.md) (roadmap Q23) |
| 4 | 48 kHz / `DSR_8S` availability | 178 kHz of datasheet headroom, unmeasured | threshold **T3** — exp 0001 clause 4; [ADR 0003](../adr/0003-microphone-path.md) d.5, [ADR 0010](../adr/0010-preset-schema.md) |
| 5 | PDM slot mask | three contradicting vendor artefacts (§10.1), and the schematic does not break the tie: on sheet 6 the mic's `SELECT` pin 2 reaches **only** R80 (`NC`, to GND) and R81 (`NC`, to `+3V3`), i.e. **neither strap option is populated** and the Knowles sheet specifies V_IH/V_IL but no floating-input default *(prov. — read 2026-08-21; a continuity or logic-level measurement on the pad would settle it)* | roadmap **H7** / H-slot — E2 first capture |
| ~~6~~ | ~~Which AXP2101 rail powers the SPM1423 (and the MAX98357A)~~ — **closed 2026-08-21 from the filed schematic** (§10.2): mic `VCC` → `+3V3` → R2 `0R` → `VDD3V3` = **DC1** (the SoC buck); `SPK_VDD` ← **DLDO1** via R18 `0R` (R76 `NC`) | the drawing, not a measurement; only the mic's *current* on DC1 is still open | [`06-power-budget.md`](06-power-budget.md) §2 / roadmap Q26 |
| 7 | Should the overrun ISR be IRAM-safe (`CONFIG_I2S_ISR_IRAM_SAFE`) so it still counts while a take write has the cache disabled? | **not settled in any ADR**; [pitfalls D7](../devenv/pitfalls.md) says the stall is real, nothing says who owns the answer | new entry for the [ADR backlog](../adr/README.md) (ADR 0006 or a capture-path ADR); measurable under the *Dropped-frame rate* row |
| 8 | Where the "fixed, logged scalar gain" of ADR 0003 d.7 lives | the [preset schema](../../protocols/specs/preset-schema.md) has `dc_blocker_hz` and `mic_eq` but **no capture-gain field**, so a permitted operation has no home and no logged value | [ADR 0010](../adr/0010-preset-schema.md) schema amendment (MINOR bump) or **ADR 0006** — [ADR backlog](../adr/README.md) |

Nothing in this table is decided here. Where a question had no owner (7 and 8), it is written as a backlog entry rather than answered.

Reference basis: [ADR 0003](../adr/0003-microphone-path.md) (the record this note implements), [ADR 0010](../adr/0010-preset-schema.md) (hops, `dc_blocker_hz`, the 48 kHz gate), [ADR 0013](../adr/0013-native-linux-simulator-target.md) (the seams are normative; QEMU has no I²S), [ADR 0015](../adr/0015-anti-brick-policy.md) (watchdog and sleep policy), [ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md) (VDD_SPI forced 3.3 V), [ADR 0018](../adr/0018-first-reference-project-study.md) (reference projects supply a specification, not code), [ADR 0006](../adr/0006-fft-normalisation-and-window-conventions.md) (`proposed` 2026-08-21 — **D7** fixes the DC-blocker form); ESP-IDF v6.0.2 sources read at the pin — `driver/i2s_pdm.h`, `i2s_pdm.c` (`i2s_pdm_rx_calculate_clock`, the two `ESP_RETURN_ON_FALSE` port guards), `i2s_common.c` (`i2s_get_buf_size`, `I2S_DMA_BUFFER_MAX_SIZE`, `I2S_DMA_ALLOC_CAPS`), `hal/i2s_types.h` (slot-mask semantics), `esp_hal_i2s/esp32s3/include/hal/i2s_ll.h` (`I2S_LL_PDM_BCK_FACTOR`), `soc/esp32s3/include/soc/soc_caps.h` ([02 #14, #15, #16](../bibliography/02-application-notes.md)); Knowles SPM1423HM4H-B clock window, sensitivity and AOP ([01 #9](../bibliography/01-datasheets.md)); MAX98357A ([01 #11](../bibliography/01-datasheets.md)); ESP32-S3 datasheet pin-domain table and TRM I²S/PDM chapter ([01 #1, #2](../bibliography/01-datasheets.md)); esp-dsp biquad generators, dispatch and published S3 benchmark ([06 #1](../bibliography/06-reference-projects.md), [study notes](../reference-projects/notes/esp-dsp_notes.md) §6); the xiao-edge-audio capture path read against the pinned tree ([06 #3](../bibliography/06-reference-projects.md), [study notes](../reference-projects/notes/xiao-edge-audio_notes.md)); LilyGoLib/XPowersLib/TTGO rail and slot evidence ([06 #4, #5, #8](../bibliography/06-reference-projects.md), [study notes](../reference-projects/notes/lilygolib-axp2101_notes.md) §5–§6); the filed LilyGO schematic V1.4 sheets 1, 2, 4 and 6 read directly on 2026-08-21 for the mic and amplifier rail identities ([01 #6](../bibliography/01-datasheets.md)); measured hardware in [`../hw/README.md`](../hw/README.md) and [`../hw/twatch-s3-pins.md`](../hw/twatch-s3-pins.md); [`../devenv/pitfalls.md`](../devenv/pitfalls.md) D1/D3/D5/D7; [experiment 0001](../validation/experiments/0001-pdm-mic-in-situ-characterization.md) and the [validation plan](../validation/README.md); component contracts [`audio_source`](../../firmware/twatch-s3/components/audio_source/README.md), [`spectral_core`](../../firmware/twatch-s3/components/spectral_core/README.md), [`twatch_bsp`](../../firmware/twatch-s3/components/twatch_bsp/README.md); the DSP-envelope estimates marked `(prov.)` come from the gitignored research synthesis `scratch/research/domainMap.md` and are replaced by on-target measurement at roadmap H13.
