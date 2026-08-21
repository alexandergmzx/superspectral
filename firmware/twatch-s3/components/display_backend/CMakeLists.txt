# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
#
# display_backend - the render seam: returns an esp_lcd_panel_handle_t from
# either st7789_spi (watch) or qemu_rgb (espressif/esp_lcd_qemu_rgb, added to
# main/idf_component.yml together with that source). Everything above
# esp_lcd - LVGL chrome and the raw analyzer canvas (ADR 0007) - is backend
# agnostic.
set(_srcs "")
foreach(_f display_backend.c be_st7789_spi.c be_qemu_rgb.c)
    if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/src/${_f}")
        list(APPEND _srcs "src/${_f}")
    endif()
endforeach()

idf_component_register(
    SRCS          ${_srcs}
    INCLUDE_DIRS  "include"
    REQUIRES      esp_lcd twatch_bsp
    PRIV_REQUIRES esp_driver_spi heap log)

if(_srcs)
    target_compile_options(${COMPONENT_LIB} PRIVATE
        -Wall -Wextra -Werror
        -Wshadow -Wconversion -Wdouble-promotion
        -Wformat=2 -Wundef -Wvla)
endif()
