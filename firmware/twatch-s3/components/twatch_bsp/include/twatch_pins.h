/* SPDX-FileCopyrightText: 2026 Alexander Gomez
 * SPDX-License-Identifier: Apache-2.0
 *
 * LilyGO T-Watch S3 (ESP32-S3-R8) - pin and rail map.
 *
 * Provenance. Pin numbers are hardware facts derived from the vendor
 * schematic T_WATCH_S3.pdf V1.4 (text layer; docs/bibliography 01) and
 * cross-checked against LilyGoLib's hardware document and MIT-licensed
 * headers (Xinyuan-LilyGO/LilyGoLib, MIT licence, Copyright (c) 2025
 * Shenzhen Xin Yuan Electronic Technology Co., Ltd) and CircuitPython's
 * boards/lilygo_twatch_s3/pins.c (MIT). Nothing here is copied from
 * arduino-esp32/variants/ (LGPL-2.1) - see ADR 0004. Prose version with the
 * full source matrix: docs/hw/twatch-s3-pins.md. Rows marked (verify) were
 * confirmed by fewer than two independent sources at the time of writing.
 *
 * Every pin carries a _Static_assert that it is neither GPIO19 nor GPIO20:
 * those are USB D-/D+ of the on-chip USB-Serial-JTAG controller, the ONLY
 * console, debug and re-flash path of a board with zero exposed GPIO and the
 * BOOT button inside the case (ADR 0015). A pre-commit grep backs the assert.
 */

#ifndef TWATCH_BSP_TWATCH_PINS_H_
#define TWATCH_BSP_TWATCH_PINS_H_

/* ---- USB-Serial-JTAG: never configured, never referenced as GPIO -------- */
#define TWATCH_PIN_USB_DN 19 /* D-  : reserved, do not use */
#define TWATCH_PIN_USB_DP 20 /* D+  : reserved, do not use */

#define TWATCH_ASSERT_NOT_USJ(pin)             \
    _Static_assert((pin) != 19 && (pin) != 20, \
                   #pin " collides with GPIO19/20 = USB-Serial-JTAG (ADR 0015)")

/* ---- Display: ST7789V3 240x240 over SPI (MISO and RESET not connected) -- */
#define TWATCH_PIN_LCD_CS   12
#define TWATCH_PIN_LCD_MOSI 13
#define TWATCH_PIN_LCD_SCK  18
#define TWATCH_PIN_LCD_DC   38
/* GPIO45 is ALSO the VDD_SPI strapping pin. With a 1.8 V W25Q128JW flash,
 * driving it low across a reset may select 3.3 V for VDD_SPI if the eFuse
 * VDD_SPI_FORCE is 0. No code may touch this pin until ADR 0016 resolves
 * VDD_SPI_FORCE from the E2 eFuse read (docs/hw/efuse-baseline.json). */
#define TWATCH_PIN_LCD_BL   45 /* backlight PWM, HAZARD: see above */
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_LCD_CS);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_LCD_MOSI);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_LCD_SCK);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_LCD_DC);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_LCD_BL);

/* ---- Touch: FocalTech FT6336U on its own I2C bus (addr 0x38) ------------ */
#define TWATCH_PIN_TOUCH_SDA    39
#define TWATCH_PIN_TOUCH_SCL    40
#define TWATCH_PIN_TOUCH_INT    16
#define TWATCH_I2C_ADDR_FT6336U 0x38
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_TOUCH_SDA);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_TOUCH_SCL);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_TOUCH_INT);

/* ---- Main I2C: PMU, accelerometer, RTC, haptic --------------------------- */
#define TWATCH_PIN_I2C_SDA       10
#define TWATCH_PIN_I2C_SCL       11
#define TWATCH_I2C_ADDR_AXP2101  0x34
#define TWATCH_I2C_ADDR_BMA423   0x19
#define TWATCH_I2C_ADDR_PCF8563  0x51
#define TWATCH_I2C_ADDR_DRV2605L 0x5A
#define TWATCH_PIN_PMU_INT       21 /* AXP2101 IRQ */
#define TWATCH_PIN_BMA423_INT    14 /* INT1 */
#define TWATCH_PIN_RTC_INT       17 /* PCF8563 alarm/timer */
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_I2C_SDA);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_I2C_SCL);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_PMU_INT);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_BMA423_INT);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_RTC_INT);

/* ---- Audio in: Knowles SPM1423HM4H-B PDM microphone -> I2S0 ------------- */
/* PDM RX is I2S0-only and 16-bit-only in ESP-IDF (esp_driver_i2s/i2s_pdm.c:
 * "This channel handle is registered on I2S1, but PDM is only supported on
 * I2S0"). Mic clock 1.0-3.25 MHz per the Knowles datasheet: 32 kHz with
 * DSR_8S = 2.048 MHz is comfortable; 48 kHz needs 3.072 MHz (verify, ADR 0003).
 * GPIO47 may sit in the VDD_SPI (1.8 V) I/O domain on R8V parts - rail to be
 * confirmed from the schematic before audio bring-up (docs/hw). */
#define TWATCH_I2S_PORT_MIC 0 /* I2S_NUM_0 - hard requirement */
#define TWATCH_PIN_MIC_CLK  44
#define TWATCH_PIN_MIC_DATA 47
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_MIC_CLK);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_MIC_DATA);

/* ---- Audio out: MAX98357A class-D amp -> I2S1 (standard/Philips) -------- */
/* Cannot share I2S0 with PDM RX (different clock and slot configs). Used for
 * the calibration-tone path only. GPIO48 shares the VDD_SPI-domain question
 * with GPIO47 (MAX98357A V_IH ~ 0.65 x DVDD). */
#define TWATCH_I2S_PORT_AMP  1 /* I2S_NUM_1 */
#define TWATCH_PIN_AMP_BCLK  48
#define TWATCH_PIN_AMP_LRCLK 15
#define TWATCH_PIN_AMP_DIN   46
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_AMP_BCLK);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_AMP_LRCLK);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_AMP_DIN);

/* ---- Radio: Semtech SX1262 on SPI2 - OUT OF SCOPE in v1 (ADR 0017) ------ */
/* Listed so the BSP can hold NRESET low and keep ALDO4 off. Numbers from
 * LilyGoLib utilities.h (MIT); DIO3 (GPIO6) is absent from LilyGoLib's public
 * pin table - (verify) against the schematic. */
#define TWATCH_PIN_LORA_SCK  3 /* (verify) */
#define TWATCH_PIN_LORA_MISO 4 /* (verify) */
#define TWATCH_PIN_LORA_MOSI 1 /* (verify) */
#define TWATCH_PIN_LORA_CS   5 /* (verify) */
#define TWATCH_PIN_LORA_RST  8 /* (verify) held LOW in v1 */
#define TWATCH_PIN_LORA_BUSY 7 /* (verify) */
#define TWATCH_PIN_LORA_DIO1 9 /* (verify) */
#define TWATCH_PIN_LORA_DIO3 6 /* (verify) TCXO control? */
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_LORA_SCK);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_LORA_MISO);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_LORA_MOSI);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_LORA_CS);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_LORA_RST);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_LORA_BUSY);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_LORA_DIO1);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_LORA_DIO3);

/* ---- Misc ---------------------------------------------------------------- */
#define TWATCH_PIN_IR_TX 2 /* IR12-21C via MMBT3904 */
#define TWATCH_PIN_BOOT  0 /* internal PCB button only */
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_IR_TX);
TWATCH_ASSERT_NOT_USJ(TWATCH_PIN_BOOT);

/* ---- AXP2101 rail map (LilyGoLib hardware doc; Zephyr DTS agrees) --------
 *
 *   Rail     | Powers                      | v1 policy
 *   ---------+-----------------------------+----------------------------------
 *   DC1      | ESP32-S3 core               | on (PMU default); never touch
 *   ALDO2    | display backlight           | ON LAST, ramped; gated by ADR 0016
 *   ALDO3    | display + touch (ST7789V3,  | on before any SPI/I2C to them,
 *            | FT6336U)                    | settle >= 10 ms
 *   ALDO4    | SX1262 LoRa                 | OFF (ADR 0017)
 *   BLDO2    | DRV2605L enable (no GPIO)   | on only when haptics are used
 *   VBACKUP  | PCF8563 via MS412FE cell    | charging per RTC retention budget
 *   DC2 DC3 DC4 DC5 ALDO1 BLDO1 CPUSLDO DLDO1 DLDO2 | unused: explicitly OFF
 *
 *   All used rails 3300 mV. Charge current <= 130 mA (LilyGO guidance for
 *   the 400-470 mAh cell; capacity unresolved, hardware/ BOM). The rail that
 *   powers the SPM1423 mic and the MAX98357A amp is NOT documented - open
 *   question for the schematic read (docs/hw/twatch-s3-pins.md).
 * ------------------------------------------------------------------------ */
#define TWATCH_RAIL_MV               3300
#define TWATCH_CHARGE_CURRENT_MAX_MA 130

/* ---- Bus identities ------------------------------------------------------
 * I2C port numbers and the I2S ports above are fixed by the board (two
 * physical I2C buses; PDM RX is I2S0-only). The SPI host numbers are a
 * FIRMWARE allocation, not a board fact: the LCD and the SX1262 sit on
 * separate pin groups, both routed through the GPIO matrix, and either could
 * take SPI2_HOST or SPI3_HOST. Keep them distinct; change them only here. */
#define TWATCH_I2C_PORT_MAIN         0 /* I2C_NUM_0: PMU/IMU/RTC/haptic */
#define TWATCH_I2C_PORT_TOUCH        1 /* I2C_NUM_1: FT6336U            */
#define TWATCH_SPI_HOST_LCD          1 /* SPI2_HOST (allocation)        */
#define TWATCH_SPI_HOST_LORA         2 /* SPI3_HOST (allocation; v1 unused) */

#endif /* TWATCH_BSP_TWATCH_PINS_H_ */
