# xiao-edge-audio — study notes (D4 reference-project loop)

- **Project:** `clutchitggs/xiao-edge-audio` — "XIAO ESP32-S3 Sense — Real-Time Audio Spectrum Analyzer" ([bibliography 06 #3](../../bibliography/06-reference-projects.md))
- **Studied commit:** `3b8de194f8deb93b5a732185878bbc58bf53abfa` (2026-05-01, "README polish: badges, fix fps inconsistency, tighten perf-table footnote"; the shallow clone holds this single commit). Clone: `docs/reference-projects/clones/xiao-edge-audio/` (gitignored).
- **Licence:** **MIT**, confirmed from `LICENSE` ("Copyright (c) 2026 Tal Nagar", standard MIT text). Apache-2.0-compatible ⇒ code may be reused on the firmware link line with attribution in `NOTICE` ([ADR 0004](../../adr/0004-split-licensing.md), accepted). Nothing below is copied verbatim; what transfers is design.
- **Studied:** 2026-08-21, against ESP-IDF v6.0.2 (`~/esp/idf/v6.0.2`, the pinned tree — [ADR 0001](../../adr/0001-toolchain-esp-idf-v6-pinned-environment.md)) and the esp-dsp clone at `3c8ac0f` (master, 2026-05-12; our pin is `~1.8.2`). IDF facts below were read from the v6.0.2 sources, not from the project's README (which targets v5.1+).
- **Feeds:** ADR 0018 (first project-study ADR), ADR 0003 (mic path), ADR 0006 (FFT conventions), components [`audio_source`](../../../firmware/twatch-s3/components/audio_source/README.md) and [`spectral_fft_backend`](../../../firmware/twatch-s3/components/spectral_fft_backend/README.md).

## 1. What it is

A ~700-line pure ESP-IDF C application (no Arduino) for the Seeed XIAO ESP32-S3 Sense: the on-board PDM MEMS microphone is captured on I2S0 at 16 kHz, a 1024-point Hann-windowed FFT runs on the APP CPU, and a 792-byte binary frame (waveform thumbnail + 256 dB bins) is pushed over a WebSocket to a browser page that draws waveform, spectrum bars and a scrolling spectrogram on `<canvas>`. It is the closest *working* precedent for our capture → window → FFT → magnitude chain on the same silicon class (ESP32-S3, octal PSRAM, same esp-dsp library). It has **no on-device display** — the hardest part of our problem (50 Hz waterfall on an ST7789 over SPI, ADR 0007) is outsourced to a browser — and it has no f0 estimation, no recording, no calibration.

Source layout (all under `firmware/`): `main/audio_capture.{c,h}` (I2S PDM RX), `main/dsp_pipeline.{c,h}` (window + FFT + frame serialisation), `main/main.c` (boot + analysis task), `main/wifi_sta.{c,h}`, `main/web_server.{c,h}`, `main/index.html` (embedded via `EMBED_TXTFILES`), `main/Kconfig.projbuild`, `sdkconfig.defaults`, `partitions.csv`, `main/idf_component.yml`.

## 2. Exact pipeline as committed

```
 PDM mic ──► I2S0 PDM RX (DMA ring 6×240 frames) ──► i2s_channel_read(1024 × int16, portMAX_DELAY)
          ──► int16→float ×(1/32768) × Hann[i] → interleaved complex (im = 0)
          ──► dsps_fft2r_fc32(N=1024) → dsps_bit_rev_fc32
          ──► |X[k]| = sqrtf(re²+im²), k = 0..511 ; peak = argmax k≥1
          ──► 20·log10(|X|+1e-9), pair-average 512→256 bins, clamp [−128, 0] → int8
          ──► 24-byte header + 256×int16 wave + 256×int8 spec = 792 B
          ──► httpd_ws_send_frame_async() to ≤4 clients, from the same task
```

### 2.1 Build and configuration

| Item | Value (file) |
|---|---|
| IDF requirement | `idf: ">=5.1"`, `espressif/esp-dsp: "^1.4.0"` (`main/idf_component.yml`) |
| Component deps | `REQUIRES driver esp_wifi esp_event esp_http_server esp_netif nvs_flash esp_psram` (`main/CMakeLists.txt`) — **on v6.0.2 `driver` is a legacy umbrella that no longer requires `esp_driver_i2s`** (`components/driver/CMakeLists.txt` lists only `esp_hal_i2c esp_hal_twai esp_hal_touch_sens`), so `#include "driver/i2s_pdm.h"` would fail to resolve; our `audio_source` already says `PRIV_REQUIRES esp_driver_i2s`. The project has not been built on v6 (badge: "ESP-IDF 5.1+") |
| Kconfig | `CONFIG_AUDIO_SAMPLE_RATE_HZ` default **16000**, `range 8000 48000`; `CONFIG_AUDIO_FFT_SIZE` default **1024**, `range 256 2048`; Wi-Fi SSID/password/retry (`main/Kconfig.projbuild`) |
| sdkconfig.defaults | `SPIRAM=y`, `SPIRAM_MODE_OCT=y`, `SPIRAM_SPEED_80M=y` (explicit — the same trap we document in PLAN §2b), `SPIRAM_USE_MALLOC=y`, `SPIRAM_MALLOC_ALWAYSINTERNAL=16384`, `SPIRAM_TRY_ALLOCATE_WIFI_LWIP=y`; flash 8 MB QIO 80 MHz; `HTTPD_WS_SUPPORT=y`; `ESP_MAIN_TASK_STACK_SIZE=8192`; `FREERTOS_HZ=1000`; `COMPILER_OPTIMIZATION_PERF=y` |
| Partitions | `nvs 0x9000/0x6000`, `phy_init 0xf000/0x1000`, **single `factory` app 2 MB** — no OTA, no rollback (contrast [ADR 0014](../../adr/0014-partition-layout-frozen.md) / [0015](../../adr/0015-anti-brick-policy.md)) |
| Boot | `app_main` allocates two internal buffers, `audio_capture_init()`, `dsp_pipeline_init()`, blocking Wi-Fi join, `web_server_start()`, then spawns the analysis task and returns. No boot guard, no health gate — fine for a board with an exposed BOOT button, not for ours |

### 2.2 PDM capture (`audio_capture.c`)

| Call / field | Value | Note |
|---|---|---|
| `i2s_chan_config_t` | `I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER)`; `dma_desc_num = 6`; `dma_frame_num = 240` | Mono 16-bit ⇒ 2 B/frame (`i2s_get_buf_size()`: `bytes_per_sample × active_slot`) ⇒ **480 B per descriptor, 2 880 B ring = 1 440 samples = 90 ms at 16 kHz**. The in-code comment says "~30 ms" — wrong by 3× (it would hold at 48 kHz). No `MALLOC_CAP_DMA` choice is exposed — the driver allocates its own descriptors and buffers internally |
| `i2s_new_channel(&chan_cfg, NULL, &s_rx_chan)` | RX only | — |
| `clk_cfg` | `I2S_PDM_RX_CLK_DEFAULT_CONFIG(16000)` ⇒ `clk_src = I2S_CLK_SRC_DEFAULT`, `mclk_multiple = 256`, `dn_sample_mode = I2S_PDM_DSR_8S`, (v6.0.2 adds `bclk_div = 8`) | `i2s_pdm_rx_calculate_clock()` (v6.0.2): `bclk = rate × I2S_LL_PDM_BCK_FACTOR(64) × (DSR_16S ? 2 : 1)` ⇒ **PDM clock = 1.024 MHz** at 16 kHz/DSR_8S. For our defaults: 32 kHz/DSR_8S → 2.048 MHz; 48 kHz → 3.072 MHz (the SPM1423's 1.0–3.25 MHz window, [pins doc](../../hw/twatch-s3-pins.md)); 16 kHz/DSR_16S → 2.048 MHz |
| `slot_cfg` | `I2S_PDM_RX_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_MONO)` ⇒ `slot_mask = I2S_PDM_SLOT_LEFT`, `slot_bit_width = AUTO`, `data_fmt = PCM` | In v6.0.2 the macro survives only as a `@cond` alias of `I2S_PDM_RX_SLOT_PCM_FMT_DEFAULT_CONFIG` (PDM2PCM targets); use the explicit PCM-format macro. The `hp_en`/`hp_cut_off_freq_hz` fields exist **only** under `SOC_I2S_SUPPORTS_PDM_RX_HP_FILTER`, which `soc_caps.h` for esp32s3 does not define (it defines `SOC_I2S_SUPPORTS_PDM_RX` and `SOC_I2S_SUPPORTS_PDM2PCM`) — software DC removal confirmed, as ADR 0003 says |
| `gpio_cfg` | `clk = GPIO42`, `din = GPIO41`, `clk_inv = false` | XIAO routing; ours is CLK 44 / DATA 47 |
| `i2s_channel_init_pdm_rx_mode()` → `i2s_channel_enable()` | — | v6.0.2 guards hit on the way: RX handle only; **`controller->id == I2S_NUM_0`** ("PDM is only supported on I2S0"); `clk_src != I2S_CLK_SRC_EXTERNAL` |
| `audio_capture_read()` | `i2s_channel_read(handle, dst, n×2, &bytes_read, timeout)`; short read ⇒ `ESP_ERR_TIMEOUT` | Called with `portMAX_DELAY` from the task — a stalled I2S blocks forever and never trips the task watchdog (only idle tasks are subscribed) |
| Not done | no `i2s_event_callbacks_t` (`on_recv_q_ovf`), so **DMA overruns are silent**; no slot-mask experiment; no `esp_pm` lock reasoning | — |

### 2.3 Window + FFT + magnitude (`dsp_pipeline.c`)

| Step | Call | Detail |
|---|---|---|
| Buffers | `heap_caps_malloc(…, MALLOC_CAP_8BIT \| MALLOC_CAP_INTERNAL)` for `s_window` (N floats, 4 KB), `s_complex` (2N floats, 8 KB), `s_mag` (N/2 floats, 2 KB); `main.c` adds the 1024×int16 block (2 KB) and the 792 B frame | ≈ 17 KB internal heap + 6 KB task stack. No explicit 16-byte alignment — esp-dsp's own `examples/fft` declares its FFT buffers `__attribute__((aligned(16)))` for the S3 PIE (`_aes3`) kernels |
| Window | `dsps_wind_hann_f32(s_window, N)` once at init | **Symmetric** Hann: esp-dsp computes `0.5·(1 − cos(2πi/(N−1)))` (`modules/windows/hann/float/dsps_wind_hann_f32.c`, checked in the clone). ADR 0006 mandates *periodic* windows (Heinzel 2002) — do not call this directly for analysis; generate N+1 and drop the last, or compute our own |
| Twiddles | `dsps_fft2r_init_fc32(NULL, N)` | On `CONFIG_IDF_TARGET_ESP32S3` with `table_size ≤ 1024` esp-dsp points at the **precompiled** `dsps_fft2r_w_table_fc32_1024` (no heap); larger N ⇒ `memalign(16, N×4)` on the internal heap. Max N = `CONFIG_DSP_MAX_FFT_SIZE` (default 4096 — **our real-8192 preset needs this raised**) |
| Pack | `s_complex[2i] = audio[i]·(1/32768)·w[i]; s_complex[2i+1] = 0` | Full complex FFT of a real signal — the README admits the ≈2× waste. No `dsps_cplx2reC_fc32` two-for-one, no `dsps_fft4r`/`dsps_cplx2real_fc32` real-FFT path |
| FFT | `dsps_fft2r_fc32(s_complex, N)` then `dsps_bit_rev_fc32(s_complex, N)` | `dsps_fft2r_fc32` resolves to `dsps_fft2r_fc32_aes3` on the S3 when `dsps_fft2r_fc32_aes3_enabled` (the SIMD path our backend-agreement test must cover) |
| Magnitude | `sqrtf(re²+im²)` per bin `0..N/2−1`; peak = argmax over `k ≥ 1` (DC skipped) | Bin `N/2` (Nyquist) is dropped; no `/N`, no S1/S2 window normalisation, no ×2 one-sided factor |
| dB | `20·log10f(mag + 1e-9)`; pair-average 512→256 bins in *linear* magnitude, then clamp to `[−128, 0]` and `lrintf` to `int8` | The "dB FS" label is **not** dBFS: for a full-scale sine under the symmetric Hann, `|X_peak| ≈ A·S1/2` with `S1 = Σw = (N−1)/2 = 511.5` ⇒ **+48.2 dB**, i.e. everything above **−48 dBFS** clips to the 0 dB ceiling. A calibrated scale needs the S1 (spectrum) / S2 (PSD) normalisation ADR 0006 specifies |
| Peak Hz | `peak_bin × fs/N` — no interpolation | ±7.8 Hz at 16 kHz/1024 — useless for a cents-grade f0 readout; we use time-domain MPM/YIN in `spectral_core` anyway |

### 2.4 Task, buffer and queue design (`main.c`, `web_server.c`)

- **One task, linear loop**: `xTaskCreatePinnedToCore(analysis_task, "analysis", 6144, NULL, 5, NULL, APP_CPU_NUM)` — **core 1**, priority 5, 6 KB stack. The loop is `read 1024 → process → broadcast`, repeated. On a read error it logs and sleeps 10 ms; on a DSP error it `continue`s.
- **No application queue and no ring buffer of its own.** The I2S driver's DMA ring (90 ms) is the only buffering. Frames are **non-overlapping, block-aligned** (hop = N). There is no producer/consumer split, no double buffer, no ISR callback.
- **Network I/O inside the DSP loop**: `web_server_broadcast()` walks a mutex-protected snapshot of ≤4 socket fds and calls `httpd_ws_send_frame_async()` for each *from the analysis task* ("async" here means "outside a request handler"; the send runs in the caller's context). A slow client therefore delays the next `i2s_channel_read()`; with a 90 ms ring and a 64 ms hop the slack before a silent DMA overrun is ≈26 ms.
- Wi-Fi and `esp_http_server` run on their default IDF tasks (Wi-Fi on core 0; httpd `tskNO_AFFINITY` from `HTTPD_DEFAULT_CONFIG()`); no core-0/core-1 contract is stated beyond the one pin.

### 2.5 Frame rate — what it is and what limits it

| Quantity | Value at the defaults (16 kHz, N = 1024) |
|---|---|
| Bin width | 15.625 Hz; band 0–8 kHz |
| Window length = hop (no overlap) | **64 ms** |
| Hard ceiling on frames/s from the code | **fs/N = 15.6 frames/s** |
| DMA read granularity | 15 ms (one 240-frame descriptor) |
| Analysis latency floor | ≥ 64 ms block fill + ≤ 15 ms descriptor wait + FFT (README: <10 % of a core) + Wi-Fi send + browser `requestAnimationFrame` |
| README claim | "~20 fps observed in dashboard" (README §Performance; the last commit changed the intro from 30 to 20 "to match the measured value") |

**The README's 20 fps is not reproducible from the committed code** at 16 kHz/1024: the non-overlapped hop caps delivery at 15.6 frames/s, and the dashboard counter (`frameCount·1000/Δt` over a 500 ms window, `toFixed(0)`) rounds bursty WebSocket delivery of 8–10 frames per window to 16–20. The limit is therefore **the block-synchronous hop — an architectural choice — not the FFT and not primarily the WebSocket**, which corrects the phrasing in [bibliography 06 #3](../../bibliography/06-reference-projects.md) ("a WebSocket/browser limit"). To reach our ≥30 Hz / 50 Hz spectrogram rows (research question, [validation](../../validation/README.md) "Sustained refresh") with a 64–128 ms analysis window, the hop must be decoupled from the window: 32 kHz, N = 4096 (128 ms window, 7.8 Hz bins), hop 640 samples (20 ms) ⇒ 50 rows/s with 84 % overlap.

### 2.6 The browser side (for completeness, not for transfer)

Off-screen `<canvas>` 600 × 256 used as a column ring; one column per frame; linear frequency axis (row → bin by nearest index); dB → RGB through a hand-rolled 4-stop black→blue→magenta→yellow gradient over [−100, 0] dB (`dbToRgb`). None of it addresses RGB565, perceptual uniformity ([ADR 0011](../../adr/0011-spectrogram-colormap.md), proposed: cividis LUT + ordered dither) or hardware scroll (ADR 0007).

## 3. What transfers to Super Spectral

**To `audio_source` (`pdm_mic` back end):**

- (+) The exact v5/v6 I2S driver call sequence is validated end-to-end on the S3: `I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER)` → `i2s_new_channel(…, NULL, &rx)` → `i2s_pdm_rx_config_t{clk_cfg = I2S_PDM_RX_CLK_DEFAULT_CONFIG(fs), slot_cfg = PCM-format 16-bit mono, gpio_cfg}` → `i2s_channel_init_pdm_rx_mode()` → `i2s_channel_enable()` → `i2s_channel_read()`. Our version changes only the pins (44/47), the rate (32 kHz default, ADR 0003), the slot macro name, and adds what §4 lists.
- (+) `dma_desc_num`/`dma_frame_num` as the tuning pair for ring depth, with the arithmetic above (bytes/frame = 2 for mono 16-bit) — we size ours in **milliseconds of hop slack**, documented next to the numbers, not as a magic "~30 ms".
- (+) `int16 → float × (1/32768)` at the capture seam, so everything downstream is `[−1, 1)` — already the `audio_source` contract.
- (+) Confirms on a second codebase that the PDM2PCM output is plain signed 16-bit mono PCM needing no unpacking, and that PDM RX wants I2S0 (now also a hard `ESP_RETURN_ON_FALSE` in v6.0.2).

**To `spectral_fft_backend`:**

- (+) The minimal esp-dsp contract that works: `dsps_fft2r_init_fc32(NULL, N)` once, `dsps_fft2r_fc32` + `dsps_bit_rev_fc32` per frame, interleaved complex `float` in internal SRAM. Our `spectral_rfft_fn` implementation starts from exactly this and then moves to the real-FFT path.
- (+) The precompiled-table fact for N ≤ 1024 on the S3 and the `CONFIG_DSP_MAX_FFT_SIZE` ceiling (4096 default) — a Kconfig line our `sdkconfig.defaults` must carry before the 8192 preset exists.
- (+) A worked example of the ≈2× cost of complex-FFT-of-real-input, which is the argument for `dsps_fft4r_fc32` + `dsps_cplx2real_fc32` (or `fft2r` + `dsps_cplx2reC_fc32`) in our backend — measured, not assumed, in the backend-agreement test.

**To the task model (architecture tenets, [CLAUDE.md](../../../CLAUDE.md)):**

- (+) DSP pinned to core 1 with the radio/UI work on core 0 — the same split we chose; the project demonstrates that a priority-5 DSP task on core 1 coexists with Wi-Fi on core 0 without audible glitches at the README's "<10 % of one core". Our load is higher (4096-pt at 50 Hz plus rendering), so this is a floor, not proof.

## 4. What not to copy, and why

- (−) **Block-synchronous framing (hop = N).** Caps rows/s at fs/N and sets latency ≥ N/fs. We need a PCM ring in internal SRAM (`MALLOC_CAP_INTERNAL | MALLOC_CAP_DMA`) fed by `i2s_channel_read()` with a **real timeout**, a hop counter that triggers an analysis frame every `hop` samples over the last `N` samples, and an `on_recv_q_ovf` callback that increments a dropout counter the validation table reads ("audio dropout" metric). Same ring is where the digital-injection path writes corpus WAV (two-path rule).
- (−) **`portMAX_DELAY` reads and silent overruns.** A hung I2S must become a watchdog panic (ADR 0015 item 6), not a quiet freeze; a DMA overrun must be counted, never ignored.
- (−) **Network/render I/O inside the DSP loop.** The analysis task hands a finished frame to a queue (or a double-buffered spectrogram column in PSRAM) and goes straight back to the ring; the UI task on core 0 drains it. Xiao's coupling is harmless at 15 frames/s over Wi-Fi and fatal at 50 Hz over SPI.
- (−) **`dsps_wind_hann_f32` for analysis windows** — symmetric, not periodic; violates ADR 0006 and breaks S1/S2 bookkeeping against the host. Generate the periodic family ourselves (Hann, Blackman–Harris, flat-top per preset) and checksum the tables in the golden-file manifest.
- (−) **The "dB FS" scale.** No S1 normalisation, no one-sided ×2, clamp at 0 dB ⇒ a −48 dBFS sine already reads full-scale. Our dB axis is defined once in ADR 0006 and shared with the host; clipping to `int8` is a transport choice we do not need on-device (the spectrogram LUT quantises, ADR 0011).
- (−) **Complex FFT of real input, and the dropped Nyquist bin.** Use the real path; keep `N/2 + 1` bins (our `spectral_rfft_fn` contract).
- (−) **Heap buffers without stated alignment.** Use `heap_caps_aligned_alloc(16, …)` (tenet 3) so the `_aes3` kernels never see an unaligned base.
- (−) **Bin-argmax "peak Hz".** Not a pitch estimator; f0 is MPM/YIN in `spectral_core` with ±cents validation.
- (−) **Whole platform layer:** Wi-Fi STA, `esp_http_server`, `nvs_flash` for credentials, single `factory` partition, no boot guard, no rollback, `REQUIRES driver`. ADR 0017 removes the radio stack structurally (`set(COMPONENTS main)`); ADR 0014/0015 and [experiment 0002](../../validation/experiments/0002-rollback-and-boot-guard-race.md) define our boot path; on v6.0.2 the I2S dependency is `esp_driver_i2s`.
- (−) **Linear-frequency, hand-tuned RGB gradient spectrogram.** Not perceptually uniform, not RGB565, not dithered, no log/mel axis option (the README lists a log axis as future work).

## 5. Alternatives considered for the study (input to ADR 0018)

- *Treat xiao-edge-audio as the template and port it file-by-file.* Rejected: its framing, window, dB scale and task coupling are each wrong for a 50 Hz, calibrated, cents-grade instrument (§4); the driver call sequence is the only part worth keeping, and that is ≈40 lines. Revisit trigger: none — the decision is about architecture, not about the project's quality as a demo.
- *Skip it and derive the PDM path from the ESP-IDF `i2s_pdm` example only ([bibliography 06 #2](../../bibliography/06-reference-projects.md)).* Rejected for D4: xiao-edge-audio adds the esp-dsp coupling, a concrete DMA sizing and a measured-in-the-wild CPU figure the example lacks; the IDF example remains the canonical citation for the driver itself.
- *Adopt its 792-byte binary frame as our take/record format.* Rejected: ours is binary too, but versioned, `_Static_assert`-guarded and carries `app_elf_sha256` ([`protocols/specs/`](../../../protocols/specs/README.md)); the xiao frame is a transport thumbnail (256 × int8, clamped), not a record. Revisit trigger: a future live-streaming debug view over USB could borrow the header idea (magic, seq, fs, n) — and nothing else.

## 6. Facts verified outside the project while studying it

| Fact | Where verified |
|---|---|
| `I2S_PDM_RX_CLK_DEFAULT_CONFIG` = `{rate, I2S_CLK_SRC_DEFAULT, I2S_MCLK_MULTIPLE_256, I2S_PDM_DSR_8S, bclk_div = 8}` | `components/esp_driver_i2s/include/driver/i2s_pdm.h`, v6.0.2 |
| PDM clock = `rate × 64 × (DSR_16S ? 2 : 1)`; `mclk = bclk × bclk_div`; `I2S_LL_PDM_BCK_FACTOR = 64` | `i2s_pdm.c` (`i2s_pdm_rx_calculate_clock`), `esp_hal_i2s/esp32s3/include/hal/i2s_ll.h`, v6.0.2 |
| PDM RX on I2S0 only; external clock source rejected; 16-bit per the slot-macro doc comment ("only support 16 bits for PDM mode") | `i2s_pdm.c` `ESP_RETURN_ON_FALSE` guards, `i2s_pdm.h`, v6.0.2 |
| S3: `SOC_I2S_SUPPORTS_PDM_RX`, `SOC_I2S_SUPPORTS_PDM2PCM` defined; `SOC_I2S_SUPPORTS_PDM_RX_HP_FILTER` absent | `components/soc/esp32s3/include/soc/soc_caps.h`, v6.0.2 |
| Legacy `driver` umbrella no longer pulls `esp_driver_i2s` | `components/driver/CMakeLists.txt`, v6.0.2 |
| `dsps_wind_hann_f32` is symmetric (`1/(len−1)`); `dsps_fft2r_init_fc32` uses the precompiled 1024 table on the S3; `CONFIG_DSP_MAX_FFT_SIZE` default 4096; esp-dsp FFT example aligns buffers to 16 B | esp-dsp clone `3c8ac0f` (`modules/windows/hann/float/`, `modules/fft/float/dsps_fft2r_fc32_ansi.c`, `modules/fft/include/dsps_fft2r.h`, `examples/fft/main/dsps_fft_main.c`) — re-check at the `v1.8.2` tag when the backend lands |
| GPIO47 (our PDM DATA) is a 3.3 V pin on this unit (eFuse `VDD_SPI_FORCE = True`) | [ADR 0016](../../adr/0016-backlight-gpio45-vdd-spi-strap.md), [`docs/hw/README.md`](../../hw/README.md), measured 2026-08-20 |

Reference basis: [bibliography 06 #3](../../bibliography/06-reference-projects.md) (the project), [06 #1](../../bibliography/06-reference-projects.md) (esp-dsp), [06 #2](../../bibliography/06-reference-projects.md) (ESP-IDF `i2s_pdm` example); [02 #14](../../bibliography/02-application-notes.md) (I2S driver API reference), [02 #15](../../bibliography/02-application-notes.md) (`i2s_pdm.h` + `i2s_pdm.c` guards), [02 #16](../../bibliography/02-application-notes.md) (`soc_caps.h`), [02 #20](../../bibliography/02-application-notes.md) (ESP-DSP API reference); [05 #1](../../bibliography/05-papers.md) (Heinzel 2002 — S1/S2, periodic windows); [ADR 0016](../../adr/0016-backlight-gpio45-vdd-spi-strap.md) and [ADR 0017](../../adr/0017-no-radio-in-v1-trimmed-component-set.md) for the measured hardware and component-set facts; the clone at `3b8de19` and the pinned IDF v6.0.2 tree for every call and field named above.
