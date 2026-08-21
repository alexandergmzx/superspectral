// SPDX-FileCopyrightText: 2026 Alexander Gomez
// SPDX-License-Identifier: Apache-2.0
// E1 gate, stage 2b: PMU rails -> ST7789 -> LVGL frame on the T-Watch S3 (ESP-IDF v6.0.2).
// Bring-up order per docs/hw/twatch-s3-pins.md: console -> I2C -> AXP2101 chip-ID -> ALDO3 (display+touch)
// -> settle -> panel init -> first frame -> ALDO2 + backlight PWM last, ramped.
#include "sdkconfig.h"
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_check.h"
#include "driver/i2c_master.h"
#include "driver/spi_master.h"
#include "driver/ledc.h"
#include "driver/i2s_pdm.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_vendor.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_touch_ft5x06.h"
#include "esp_dsp.h"
#include "lvgl.h"
#include "esp_lvgl_port.h"
#include "esp_littlefs.h"
#include "esp_ota_ops.h"

static const char *TAG = "gate";

// ---- pins (docs/hw/twatch-s3-pins.md; schematic + LilyGoLib MIT, not arduino-esp32) ----
#define PIN_I2C0_SDA 10
#define PIN_I2C0_SCL 11
#define PIN_I2C1_SDA 39
#define PIN_I2C1_SCL 40
#define PIN_LCD_SCK  18
#define PIN_LCD_MOSI 13
#define PIN_LCD_CS   12
#define PIN_LCD_DC   38
#define PIN_LCD_BL   45   // VDD_SPI strap neutralised on this unit: VDD_SPI_FORCE=1 (efuse-baseline.json)
_Static_assert(PIN_I2C0_SDA != 19 && PIN_I2C0_SCL != 20 && PIN_LCD_DC != 19 && PIN_LCD_BL != 20, "GPIO19/20 are USB-Serial-JTAG");

// ---- AXP2101 (XPowersLib REG/AXP2101Constants.h, MIT) ----
#define AXP_ADDR            0x34
#define AXP_IC_TYPE         0x03   // reads 0x4A
#define AXP_CHIP_ID         0x4A
#define AXP_LDO_ONOFF_CTRL0 0x90   // b0 ALDO1 b1 ALDO2 b2 ALDO3 b3 ALDO4 b4 BLDO1 b5 BLDO2 b6 CPUSLDO b7 DLDO1
#define AXP_ALDO2_VOL       0x93   // low 5 bits = (mV-500)/100
#define AXP_ALDO3_VOL       0x94

static i2c_master_dev_handle_t axp;

static esp_err_t axp_rd(uint8_t reg, uint8_t *v) { return i2c_master_transmit_receive(axp, &reg, 1, v, 1, 100); }
static esp_err_t axp_wr(uint8_t reg, uint8_t v)  { uint8_t b[2] = {reg, v}; return i2c_master_transmit(axp, b, 2, 100); }
static esp_err_t axp_set_ldo_mv(uint8_t reg, int mv) {
    uint8_t cur; ESP_RETURN_ON_ERROR(axp_rd(reg, &cur), TAG, "rd");
    return axp_wr(reg, (uint8_t)((cur & 0xE0) | (uint8_t)((mv - 500) / 100)));
}
static esp_err_t axp_enable_bit(uint8_t bit) {
    uint8_t cur; ESP_RETURN_ON_ERROR(axp_rd(AXP_LDO_ONOFF_CTRL0, &cur), TAG, "rd");
    return axp_wr(AXP_LDO_ONOFF_CTRL0, (uint8_t)(cur | (1u << bit)));
}

static void i2c_scan(i2c_master_bus_handle_t bus, const char *name) {
    char found[96] = ""; int n = 0;
    for (uint8_t a = 0x08; a < 0x78; a++)
        if (i2c_master_probe(bus, a, 20) == ESP_OK) { n += snprintf(found + n, sizeof found - (size_t)n, "0x%02X ", a); }
    ESP_LOGI(TAG, "%s devices: %s", name, found[0] ? found : "(none)");
}

void app_main(void)
{
    ESP_LOGW(TAG, "boot guard: 3000 ms");
    vTaskDelay(pdMS_TO_TICKS(3000));
    const esp_partition_t *run = esp_ota_get_running_partition();
    esp_ota_img_states_t st = ESP_OTA_IMG_UNDEFINED;   // stays UNDEFINED when no otadata record maps to this slot (after a rollback)
    (void)esp_ota_get_state_partition(run, &st);
    ESP_LOGI(TAG, "idf %s, lvgl %d.%d.%d, running %s @0x%lx state %d reset %d", esp_get_idf_version(),
             LVGL_VERSION_MAJOR, LVGL_VERSION_MINOR, LVGL_VERSION_PATCH, run->label, (unsigned long)run->address, (int)st, (int)esp_reset_reason());

    // ---- I2C0: PMU, IMU, RTC, haptics ----
    i2c_master_bus_handle_t bus0, bus1;
    i2c_master_bus_config_t b0 = { .i2c_port = 0, .sda_io_num = PIN_I2C0_SDA, .scl_io_num = PIN_I2C0_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT, .glitch_ignore_cnt = 7, .flags.enable_internal_pullup = true };
    ESP_ERROR_CHECK(i2c_new_master_bus(&b0, &bus0));
    i2c_scan(bus0, "I2C0");
    i2c_device_config_t dc = { .dev_addr_length = I2C_ADDR_BIT_LEN_7, .device_address = AXP_ADDR, .scl_speed_hz = 100000 };
    ESP_ERROR_CHECK(i2c_master_bus_add_device(bus0, &dc, &axp));
    uint8_t id = 0; ESP_ERROR_CHECK(axp_rd(AXP_IC_TYPE, &id));
    ESP_LOGI(TAG, "AXP2101 IC_TYPE=0x%02X (%s)", id, id == AXP_CHIP_ID ? "ok" : "UNEXPECTED");
    if (id != AXP_CHIP_ID) { ESP_LOGE(TAG, "not an AXP2101 - stopping before touching rails"); for (;;) vTaskDelay(1000); }
    uint8_t ldo; axp_rd(AXP_LDO_ONOFF_CTRL0, &ldo); ESP_LOGI(TAG, "LDO_ONOFF_CTRL0 before: 0x%02X", ldo);

    // ---- rails: voltages first, ALDO3 (display+touch) on, settle; ALDO2 (backlight) LAST ----
    ESP_ERROR_CHECK(axp_set_ldo_mv(AXP_ALDO3_VOL, 3300));
    ESP_ERROR_CHECK(axp_set_ldo_mv(AXP_ALDO2_VOL, 3300));
    ESP_ERROR_CHECK(axp_enable_bit(2));          // ALDO3
    vTaskDelay(pdMS_TO_TICKS(20));
    axp_rd(AXP_LDO_ONOFF_CTRL0, &ldo); ESP_LOGI(TAG, "LDO_ONOFF_CTRL0 after ALDO3: 0x%02X", ldo);

    // ---- I2C1: touch (FT6336U @0x38) should now answer ----
    i2c_master_bus_config_t b1 = { .i2c_port = 1, .sda_io_num = PIN_I2C1_SDA, .scl_io_num = PIN_I2C1_SCL,
        .clk_source = I2C_CLK_SRC_DEFAULT, .glitch_ignore_cnt = 7, .flags.enable_internal_pullup = true };
    ESP_ERROR_CHECK(i2c_new_master_bus(&b1, &bus1));
    vTaskDelay(pdMS_TO_TICKS(50));
    i2c_scan(bus1, "I2C1");

    // ---- ST7789 over SPI2 at 20 MHz (raise only after correctness is proven) ----
    spi_bus_config_t spi = { .sclk_io_num = PIN_LCD_SCK, .mosi_io_num = PIN_LCD_MOSI, .miso_io_num = -1,
        .quadwp_io_num = -1, .quadhd_io_num = -1, .max_transfer_sz = 240 * 40 * 2 };
    ESP_ERROR_CHECK(spi_bus_initialize(SPI2_HOST, &spi, SPI_DMA_CH_AUTO));
    esp_lcd_panel_io_handle_t io; esp_lcd_panel_handle_t panel;
    esp_lcd_panel_io_spi_config_t ioc = { .dc_gpio_num = PIN_LCD_DC, .cs_gpio_num = PIN_LCD_CS, .pclk_hz = 20 * 1000 * 1000,
        .lcd_cmd_bits = 8, .lcd_param_bits = 8, .spi_mode = 0, .trans_queue_depth = 10 };
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)SPI2_HOST, &ioc, &io));
    esp_lcd_panel_dev_config_t pc = { .reset_gpio_num = GPIO_NUM_NC, .rgb_ele_order = LCD_RGB_ELEMENT_ORDER_RGB, .bits_per_pixel = 16 };
    ESP_ERROR_CHECK(esp_lcd_new_panel_st7789(io, &pc, &panel));
    ESP_ERROR_CHECK(esp_lcd_panel_reset(panel));
    ESP_ERROR_CHECK(esp_lcd_panel_init(panel));
    ESP_ERROR_CHECK(esp_lcd_panel_invert_color(panel, true));
    ESP_ERROR_CHECK(esp_lcd_panel_set_gap(panel, 0, 0));
    ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel, true));
    ESP_LOGI(TAG, "st7789 init done");

    // ---- LVGL via esp_lvgl_port: partial internal-SRAM buffers, DMA, byte swap for SPI ----
    lvgl_port_cfg_t lc = ESP_LVGL_PORT_INIT_CONFIG();
    ESP_ERROR_CHECK(lvgl_port_init(&lc));
    lvgl_port_display_cfg_t dcfg = { .io_handle = io, .panel_handle = panel, .buffer_size = 240 * 30, .double_buffer = true,
        .hres = 240, .vres = 240, .monochrome = false, .color_format = LV_COLOR_FORMAT_RGB565,
        .rotation = { .swap_xy = false, .mirror_x = false, .mirror_y = false },
        .flags = { .buff_dma = true, .swap_bytes = true } };
    lv_display_t *disp = lvgl_port_add_disp(&dcfg);
    if (!disp) { ESP_LOGE(TAG, "lvgl_port_add_disp failed"); for (;;) vTaskDelay(1000); }

    // ---- the frame ----
    static float x[2048] __attribute__((aligned(16)));
    ESP_ERROR_CHECK(dsps_fft2r_init_fc32(NULL, 1024));
    for (int i = 0; i < 1024; i++) { x[2*i] = (i % 64) < 32 ? 1.0f : -1.0f; x[2*i+1] = 0; }
    dsps_fft2r_fc32(x, 1024); dsps_bit_rev2r_fc32(x, 1024);

    lvgl_port_lock(0);
    lv_obj_t *scr = lv_screen_active();
    lv_obj_set_style_bg_color(scr, lv_color_hex(0x101820), 0);
    lv_obj_t *title = lv_label_create(scr);
    lv_label_set_text(title, "SUPER SPECTRAL\nE1 gate 2b\nESP-IDF v6.0.2 / LVGL 9.5");
    lv_obj_set_style_text_color(title, lv_color_hex(0xE0E0E0), 0);
    lv_obj_set_style_text_align(title, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 16);
    // 48 bars of the square-wave spectrum (odd harmonics visible = FFT is right)
    for (int b = 0; b < 48; b++) {
        float mag = 0; for (int k = b * 2; k < b * 2 + 2 && k < 512; k++) { float re = x[2*k], im = x[2*k+1]; float m = re*re + im*im; if (m > mag) mag = m; }
        int h = (int)(mag > 1 ? (10.0f * __builtin_log10f(mag)) * 2.0f : 0); if (h > 110) h = 110; if (h < 2) h = 2;
        lv_obj_t *bar = lv_obj_create(scr); lv_obj_remove_style_all(bar);
        lv_obj_set_size(bar, 4, h); lv_obj_set_style_bg_opa(bar, LV_OPA_COVER, 0);
        lv_obj_set_style_bg_color(bar, lv_color_hex(h > 60 ? 0x3DDC84 : 0x2A6F97), 0);
        lv_obj_align(bar, LV_ALIGN_BOTTOM_LEFT, 2 + b * 5, -8);
    }
    lvgl_port_unlock();
    vTaskDelay(pdMS_TO_TICKS(100));   // let the first flush land in GRAM before light

    // ---- backlight last: ALDO2 on, then LEDC ramp on GPIO45 ----
    ESP_ERROR_CHECK(axp_enable_bit(1));          // ALDO2
    ledc_timer_config_t lt = { .speed_mode = LEDC_LOW_SPEED_MODE, .duty_resolution = LEDC_TIMER_8_BIT, .timer_num = LEDC_TIMER_0,
        .freq_hz = 5000, .clk_cfg = LEDC_AUTO_CLK };
    ESP_ERROR_CHECK(ledc_timer_config(&lt));
    ledc_channel_config_t lch = { .gpio_num = PIN_LCD_BL, .speed_mode = LEDC_LOW_SPEED_MODE, .channel = LEDC_CHANNEL_0,
        .timer_sel = LEDC_TIMER_0, .duty = 0, .hpoint = 0 };
    ESP_ERROR_CHECK(ledc_channel_config(&lch));
    for (int d = 0; d <= 160; d += 8) { ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, (uint32_t)d); ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0); vTaskDelay(pdMS_TO_TICKS(20)); }
    ESP_LOGI(TAG, "backlight on (ALDO2 + LEDC 160/255)");

    if (st == ESP_OTA_IMG_PENDING_VERIFY) { esp_ota_mark_app_valid_cancel_rollback(); ESP_LOGI(TAG, "marked valid"); }
    (void)i2s_channel_init_pdm_rx_mode; (void)esp_vfs_littlefs_register; (void)esp_lcd_touch_new_i2c_ft5x06;
    ESP_LOGI(TAG, "GATE_STAGE2B_FRAME_SENT");
    for (int i = 0; ; i++) { vTaskDelay(pdMS_TO_TICKS(5000)); ESP_LOGI(TAG, "alive %d", i); }
}
