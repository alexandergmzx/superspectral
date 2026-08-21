# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
#
# spectral_fft_backend - binds spectral_core's injected FFT
# (spectral_rfft_fn) to esp-dsp on target/QEMU. The ONLY component that may
# include esp_dsp.h. Managed-component name for REQUIRES is
# "espressif__esp-dsp" (added when src/ appears, so the scaffold configures
# without the registry).
set(_srcs "")
foreach(_f fft_espdsp.c)
    if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/src/${_f}")
        list(APPEND _srcs "src/${_f}")
    endif()
endforeach()

idf_component_register(
    SRCS          ${_srcs}
    INCLUDE_DIRS  "include"
    REQUIRES      spectral_core
    PRIV_REQUIRES heap log)

if(_srcs)
    target_compile_options(${COMPONENT_LIB} PRIVATE
        -Wall -Wextra -Werror
        -Wshadow -Wconversion -Wdouble-promotion
        -Wformat=2 -Wundef -Wvla)
endif()
