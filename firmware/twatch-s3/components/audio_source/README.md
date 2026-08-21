# audio_source — capture seam

**Decision.** Everything downstream of "a block of `int16` samples arrived" is written against one `audio_source` interface with three back ends: `pdm_mic` (I2S0 PDM RX on the watch), `file_blob` (a WAV/raw take embedded in flash or read from the `takes` partition), and `synthetic` (sine / two-tone / chirp / pink-noise generator with exact ground truth). **Trade-off:** one more abstraction in the hot path, for a DSP and UI stack that is testable on QEMU — which emulates no I²S, I²C or GP-SPI — and a digital-injection validation path that bypasses the microphone entirely (the research question's "≤5 cents vs Praat" leg, proposal §4).

## Back ends

| Back end | Where it runs | Ground truth | Selected by (planned Kconfig) |
|---|---|---|---|
| `pdm_mic` | target only | none — acoustic path | `CONFIG_SPECTRAL_AUDIO_SOURCE_PDM_MIC` |
| `file_blob` | target, QEMU | the take's sidecar (Praat golden file) | `CONFIG_SPECTRAL_AUDIO_SOURCE_FILE_BLOB` |
| `synthetic` | target, QEMU, host | exact by construction (Tier-0 corpus, [`datasets/`](../../../../datasets/README.md)) | `CONFIG_SPECTRAL_AUDIO_SOURCE_SYNTHETIC` |

## Fixed facts for `pdm_mic` (ADR 0003)

- I2S0 only, 16-bit only (`i2s_channel_init_pdm_rx_mode()`; `i2s_pdm.c` rejects I2S1 and `I2S_CLK_SRC_EXTERNAL`).
- Default 32 kHz with `I2S_PDM_DSR_8S` (mic clock 2.048 MHz); 48 kHz (3.072 MHz) gated on measuring the SPM1423's 3.25 MHz ceiling in situ.
- `slot_mask` must match the mic's L/R strap — the wrong side captures silence and looks like a dead mic.
- DMA descriptors and ring buffer in `MALLOC_CAP_INTERNAL | MALLOC_CAP_DMA`; conversion to `float` (`1/32768`) happens here so `spectral_core` sees `[-1, 1]`.
- No hardware PDM high-pass on the S3 (`SOC_I2S_SUPPORTS_PDM_RX_HP_FILTER` absent in v6.0.x): software DC removal lives in this component; no noise suppression, AGC or AEC ever.
- The DSP task blocks on `i2s_channel_read()` with a real timeout; ISRs enqueue a buffer index and nothing else. Pinned to core 1 (UI on core 0).

Planned sources: `src/audio_source.c`, `src/src_pdm_mic.c`, `src/src_file_blob.c`, `src/src_synthetic.c` (E1 for synthetic/file_blob, E2 for the mic).
