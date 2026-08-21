# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
#
# audio_source - the capture seam: pdm_mic | file_blob | synthetic.
# One interface, three implementations selected by Kconfig (symbols are
# defined here when the first implementation lands, so sdkconfig.ci.qemu can
# reference them without kconfgen warnings). QEMU emulates no I2S, so every
# test above "frames arrive" goes through file_blob or synthetic.
set(_srcs "")
foreach(_f audio_source.c src_pdm_mic.c src_file_blob.c src_synthetic.c)
    if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/src/${_f}")
        list(APPEND _srcs "src/${_f}")
    endif()
endforeach()

idf_component_register(
    SRCS          ${_srcs}
    INCLUDE_DIRS  "include"
    REQUIRES      twatch_bsp
    PRIV_REQUIRES esp_driver_i2s heap log)

if(_srcs)
    target_compile_options(${COMPONENT_LIB} PRIVATE
        -Wall -Wextra -Werror
        -Wshadow -Wconversion -Wdouble-promotion
        -Wformat=2 -Wundef -Wvla)
endif()
