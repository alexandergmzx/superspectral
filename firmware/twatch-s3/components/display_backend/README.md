# display_backend — render seam

**Decision.** The UI asks this component for an `esp_lcd_panel_handle_t` and never knows whether it came from the ST7789V3 over SPI or from QEMU's RGB framebuffer. **Trade-off:** the QEMU path exercises none of the SPI timing, MADCTL or gap-offset behaviour of the real panel (those need hardware or, advisory only, Wokwi) — but it makes the entire LVGL layer and the spectrogram canvas CI-testable at zero hardware cost (ADR 0009).

## Back ends

| Back end | Factory | Notes |
|---|---|---|
| `st7789_spi` | in-tree `esp_lcd_new_panel_st7789()` (`esp_lcd_panel_st7789.h`; v6.0 ships only ST7789 and SSD1306 in-tree) | pixel clock **20 MHz first**, raise only after correctness; `esp_lcd_panel_set_gap()`, `invert_color(true)`, `mirror`/`swap_xy` are empirical — budget tuning time. v6.0 API deltas: GPIO fields are `gpio_num_t`, colour order via `rgb_ele_order`, `esp_lcd_panel_disp_on_off()` replaces `disp_off()`. No `dma_burst_size` on the SPI IO (that field is i80/parallel/RGB only). |
| `qemu_rgb` | `espressif/esp_lcd_qemu_rgb` (registry, added with this source) | full framebuffer; no SPI path |

## Fixed facts

- 240×240 RGB565 = 115,200 B per frame. Full-frame buffers do not fit internal SRAM next to audio and are *slower* in PSRAM (esp_lvgl_port `performance.md`): LVGL gets **two partial buffers of ~1/8 screen (240×30, 14.4 KB each) in internal DMA-capable RAM**; the SPI bounce buffer likewise.
- The 50 Hz live-singing spectrogram target (research question) needs the raw `esp_lcd` path with ST7789 hardware vertical scroll; **scroll axis vs MADCTL is unverified (P0)** — if it fails, the target falls back to ≈30 Hz (ADR 0007).
- Rails: ALDO3 must be up ≥ 10 ms before `esp_lcd_panel_reset()` — into a dead rail it returns `ESP_OK` and does nothing. Backlight (GPIO45, ALDO2) is **not** this component's business until ADR 0016.

Planned sources: `src/display_backend.c`, `src/be_st7789_spi.c` (E2), `src/be_qemu_rgb.c` (E1).
