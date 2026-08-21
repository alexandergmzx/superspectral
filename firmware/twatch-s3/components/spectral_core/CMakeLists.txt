# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
#
# spectral_core - pure C99 spectral analysis core.
#
# Deliberately depends on NOTHING from ESP-IDF: no esp_err_t, no ESP_LOGx, no
# FreeRTOS, no esp-dsp, no <malloc.h>. That is what makes it buildable by the
# plain-CMake host-tests/ tree (ASan/UBSan/ctest, golden files vs Praat),
# cppcheck-clean and reviewable. Keep it that way: the FFT itself is injected
# through a function pointer (see include/spectral_core/spectral.h), and the
# esp-dsp binding lives in components/spectral_fft_backend.
#
# Sources are listed explicitly (ESP-IDF discourages GLOB) but guarded with
# EXISTS so the scaffold configures before the files land (roadmap E1).
set(_srcs "")
foreach(_f spectral.c window.c peak.c fft_ref.c)
    if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/src/${_f}")
        list(APPEND _srcs "src/${_f}")
    endif()
endforeach()

idf_component_register(
    SRCS          ${_srcs}
    INCLUDE_DIRS  "include"
    REQUIRES      ""          # explicit: no public deps - host-buildable
    PRIV_REQUIRES "")         # explicit: no private deps

# Per-component warning policy (sdkconfig.defaults rationale). Only valid once
# the component has sources (an INTERFACE library rejects PRIVATE options).
# -std=gnu99 pins the dialect the host-tests/ build uses; it is appended after
# the build-wide -std=gnu23 that tools/cmake/build.cmake adds, and GCC honours
# the last -std given. Safe because this component includes no ESP-IDF header.
if(_srcs)
    target_compile_options(${COMPONENT_LIB} PRIVATE
        -std=gnu99
        -Wall -Wextra -Werror
        -Wshadow -Wconversion -Wdouble-promotion
        -Wformat=2 -Wundef -Wvla)
endif()
