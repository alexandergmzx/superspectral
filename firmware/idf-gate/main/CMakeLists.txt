# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
#
idf_component_register(SRCS "gate_main.c" INCLUDE_DIRS "." REQUIRES esp_driver_i2s esp_driver_i2c esp_driver_spi esp_driver_ledc esp_driver_gpio esp_lcd esp_timer app_update esp_app_format)
