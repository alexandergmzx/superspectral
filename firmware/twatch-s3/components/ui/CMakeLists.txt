# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
#
# ui - LVGL screens, widgets, note ladder, preset chrome. NO hardware access:
# it consumes spectral_frame_t and an esp_lcd_panel_handle_t obtained through
# display_backend. Managed-component names for REQUIRES ("lvgl__lvgl",
# "espressif__esp_lvgl_port") are added when src/ appears so the scaffold
# configures without the registry.
set(_srcs "")
foreach(_f ui.c ui_spectrogram.c ui_spectrum.c ui_note_ladder.c ui_presets.c)
    if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/src/${_f}")
        list(APPEND _srcs "src/${_f}")
    endif()
endforeach()

idf_component_register(
    SRCS          ${_srcs}
    INCLUDE_DIRS  "include"
    REQUIRES      spectral_core display_backend
    PRIV_REQUIRES heap log)

if(_srcs)
    target_compile_options(${COMPONENT_LIB} PRIVATE
        -Wall -Wextra -Werror
        -Wshadow -Wconversion -Wdouble-promotion
        -Wformat=2 -Wvla)   # -Wundef dropped: ESP-IDF headers use `#if CONFIG_X` idioms that trip it (verified on v6.0.2, E1)
endif()
