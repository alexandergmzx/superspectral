/* SPDX-FileCopyrightText: 2026 Alexander Gomez
 * SPDX-License-Identifier: Apache-2.0
 *
 * Super Spectral - application entry point (LilyGO T-Watch S3, ESP-IDF v6.0).
 *
 * This file stays tiny on purpose: boot guard, reset-reason log, then the
 * bring-up sequence delegated to components/ in the order fixed by
 * docs/hw/twatch-s3-pins.md and ADR 0015. No hardware is touched here yet.
 */

#include "sdkconfig.h"

#include "esp_log.h"
#include "esp_system.h"
#include "esp_ota_ops.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "superspectral";

void app_main(void)
{
    /* ------------------------------------------------------------------
     * ANTI-BRICK BOOT GUARD - MUST REMAIN THE FIRST STATEMENT (ADR 0015).
     * Zero exposed GPIO, BOOT button inside the case: the only re-flash path
     * is esptool over the native USB-Serial-JTAG controller, which needs
     * ~1 s to enumerate after every reset. This window guarantees
     * `idf.py flash` wins the race even if everything below crash-loops.
     * CONFIG_SPECTRAL_BOOT_GUARD_MS: Kconfig.projbuild, default 3000,
     * range 1000..10000. Never reduce it, never move it, never make it
     * conditional.
     * ------------------------------------------------------------------ */
    ESP_LOGW(TAG, "boot guard: %d ms window - flash now if needed", CONFIG_SPECTRAL_BOOT_GUARD_MS);
    vTaskDelay(pdMS_TO_TICKS(CONFIG_SPECTRAL_BOOT_GUARD_MS));

    /* Why did we get here? ESP_RST_PANIC / ESP_RST_TASK_WDT / ESP_RST_BROWNOUT
     * after a flash is the first thing to read over the USJ console. A boot
     * counter + reset-reason histogram in NVS is the follow-up (ADR 0015). */
    const esp_reset_reason_t reason = esp_reset_reason();
    ESP_LOGI(TAG, "reset reason: %d (esp_reset_reason_t)", (int) reason);

    /* Which slot, which OTA state - the two facts experiment 0002 reads. */
    const esp_partition_t *running = esp_ota_get_running_partition();
    esp_ota_img_states_t ota_state = ESP_OTA_IMG_UNDEFINED;
    (void) esp_ota_get_state_partition(running, &ota_state);
    ESP_LOGI(TAG, "running from %s @0x%lx, ota state %d (0 NEW, 1 PENDING_VERIFY, 2 VALID, 3 INVALID, 4 ABORTED)",
             running->label, (unsigned long) running->address, (int) ota_state);

#if CONFIG_SPECTRAL_TEST_CRASH_AFTER_GUARD
    /* Image B of experiment 0002: deliberate crash loop after the guard window. */
    ESP_LOGE(TAG, "TEST HOOK: SPECTRAL_TEST_CRASH_AFTER_GUARD - aborting now");
    abort();
#endif

    /* ------------------------------------------------------------------
     * Bring-up order - docs/hw/twatch-s3-pins.md, ADR 0003/0007/0015/0016.
     * Each step is a call into components/; none exist yet (roadmap E1/E2).
     *
     * TODO(bsp) 1. twatch_bsp: I2C0 master (SDA 10 / SCL 11) via
     *             driver/i2c_master.h; AXP2101 chip-ID at 0x34.
     * TODO(bsp) 2. twatch_bsp: AXP2101 rails - set voltages, disable every
     *             unused channel (DC2-DC5, ALDO1, BLDO1, CPUSLDO, DLDO1,
     *             DLDO2 - list owned by twatch_pins.h / docs/hw), charge
     *             current <= 130 mA, ALDO4 (LoRa) OFF (ADR 0017).
     * TODO(bsp) 3. twatch_bsp: ALDO3 on (display + touch), settle >= 10 ms,
     *             then the five-address I2C scan gate (0x34 0x19 0x51 0x5A
     *             on I2C0; 0x38 on I2C1 SDA 39 / SCL 40).
     * TODO(bsp) 4. display_backend: ST7789V3 over SPI (CS 12 / MOSI 13 /
     *             SCK 18 / DC 38) with in-tree esp_lcd_new_panel_st7789(),
     *             20 MHz first; set_gap / invert / mirror tuned on hardware.
     * TODO(bsp) 5. twatch_bsp: backlight on GPIO45 ONLY after ADR 0016
     *             resolves VDD_SPI_FORCE from the E2 eFuse read; ALDO2 last,
     *             ramped.
     * TODO(bsp) 6. audio_source: PDM RX on I2S0 (CLK 44 / DIN 47, 16-bit,
     *             internal DMA) -> spectral_fft_backend -> ui, DSP task pinned
     *             to core 1, UI to core 0.
     * TODO(bsp) 7. esp_ota_mark_app_valid_cancel_rollback() ONLY after
     *             display frame rendered + touch responds + PMU rails
     *             confirmed + USB enumerated (ADR 0015). Until then the
     *             bootloader reverts this image on the next reset.
     * TODO(bsp) 8. Sleep entry stays unreachable unless
     *             CONFIG_SPECTRAL_DEV_SLEEP_ARMED and the runtime gate pass.
     * ------------------------------------------------------------------ */
    /* Marker line for pytest-embedded: dut.expect("Super Spectral"). */
    ESP_LOGI(TAG, "Super Spectral scaffold: no peripherals initialised");
}
