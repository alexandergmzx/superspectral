# ui — LVGL screens and the analyzer canvas

**Decision.** The UI is split in two: LVGL 9.5 (`lvgl/lvgl ~9.5.0` via `espressif/esp_lvgl_port ~2.9.0`) for chrome — presets, readouts, note ladder, settings — and a **raw `esp_lcd` canvas** for the spectrogram/spectrum area, which LVGL is told never to repaint. **Trade-off:** two rendering paths to coordinate (a reserved region and a tick budget), in exchange for the ≥30 Hz spectrogram (50 Hz in the live-singing preset) the research question requires; the LVGL widget path alone measures ≈30 fps on this class of board. The split is provisional until the ST7789 scroll-axis check (ADR 0007).

This component has **no hardware access**: inputs are `spectral_frame_t` (from [`spectral_core`](../spectral_core/README.md)) and a panel handle from [`display_backend`](../display_backend/README.md). That is what lets the widget set run in LVGL's native screenshot harness (`lv_test_screenshot_compare()`, `ref_imgs/`) with no ESP-IDF at all.

## Planned pieces

| Piece | Grounding |
|---|---|
| `ui_spectrogram.c` — scrolling canvas, RGB565 LUT | colormap ADR 0011 (cividis/batlow-class, pre-quantised with dithering); ≤80 ms acoustic-to-photon (proposal §4) |
| `ui_spectrum.c` — instantaneous spectrum, peak marker, band overlays | PS in dBFS per ADR 0006; ring/twang overlay rules ADR 0008 |
| `ui_note_ladder.c` — f0 → note/cents | ±20 cents MAE target (research question) |
| `ui_presets.c` — preset chrome | schema owned by [`protocols/specs/`](../../../../protocols/specs/README.md) (ADR 0010), stored on the `presets` littlefs partition |
| `ui.c` — LVGL task on **core 0**, partial buffers 2 × 240×30 RGB565 in internal RAM | esp_lvgl_port `performance.md`; DSP task is on core 1 |

Interaction model (wrist-raise arm, haptic confirm) is ADR 0012 and does not exist yet.
