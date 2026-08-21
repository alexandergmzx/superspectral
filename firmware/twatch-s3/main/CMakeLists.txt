# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
#
# `main` automatically requires every other component in the build
# (build-system guide, "main component"), so REQUIRES here is documentation
# of the intended wiring, not a constraint. Keep main tiny: app_main, the boot
# guard, task creation. Real work lives in components/ so that dependency
# errors surface there, where REQUIRES is enforced.
#
# REQUIRES      = components whose headers main's public headers would include
# PRIV_REQUIRES = components used only from app_main.c
idf_component_register(
    SRCS          "app_main.c"
    INCLUDE_DIRS  "."
    REQUIRES      twatch_bsp ui spectral_core spectral_fft_backend
                  audio_source display_backend
    PRIV_REQUIRES esp_timer nvs_flash esp_app_format app_update espcoredump)   # espcoredump: keep core-dump-to-flash in the trimmed build (ADR 0015, 0017)

# Project-own warning set (ADR-level policy, see sdkconfig.defaults). The S3
# FPU is single precision: -Wdouble-promotion is the high-value one.
target_compile_options(${COMPONENT_LIB} PRIVATE
    -Wall -Wextra -Werror
    -Wshadow -Wconversion -Wdouble-promotion
    -Wformat=2 -Wvla)   # -Wundef dropped: ESP-IDF headers use `#if CONFIG_X` idioms that trip it (verified on v6.0.2, E1)
