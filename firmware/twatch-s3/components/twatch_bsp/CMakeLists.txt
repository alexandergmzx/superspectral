# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
#
# twatch_bsp - board support for the LilyGO T-Watch S3: pin map, AXP2101
# rail sequencing, I2C buses, ST7789V3 panel + FT6336U touch factories, PDM
# mic / MAX98357A channel factories. Currently header-only (twatch_pins.h);
# sources land during roadmap E2 once the eFuse baseline is read.
#
# REQUIRES are the v6.0 per-peripheral driver components (the legacy
# `driver` umbrella is not used). Managed components (sensorlib,
# esp_lcd_touch_ft5x06) are added to REQUIRES as "lewisxhe__sensorlib" and
# "espressif__esp_lcd_touch_ft5x06" when their first caller appears.
set(_srcs "")
foreach(_f twatch_bsp.c twatch_pmu_axp2101.c twatch_display.c twatch_touch.c twatch_audio.c)
    if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/src/${_f}")
        list(APPEND _srcs "src/${_f}")
    endif()
endforeach()

idf_component_register(
    SRCS          ${_srcs}
    INCLUDE_DIRS  "include"
    REQUIRES      esp_driver_i2c esp_driver_spi esp_driver_i2s esp_driver_gpio
                  esp_driver_ledc esp_lcd
    PRIV_REQUIRES esp_timer log)

if(_srcs)
    target_compile_options(${COMPONENT_LIB} PRIVATE
        -Wall -Wextra -Werror
        -Wshadow -Wconversion -Wdouble-promotion
        -Wformat=2 -Wvla)   # -Wundef dropped: ESP-IDF headers use `#if CONFIG_X` idioms that trip it (verified on v6.0.2, E1)
endif()
