# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
#
# Super Spectral firmware - LilyGO T-Watch S3 (ESP32-S3-R8).
# ESP-IDF Build System v1 (ADR 0019: v2 is a Technical Preview in v6.0;
# migrate only when it leaves preview). Toolchain pin: ADR 0001.
#
# Build:   idf.py set-target esp32s3 && idf.py build
# Config:  sdkconfig.defaults (+ sdkconfig.defaults.esp32s3, auto-loaded by
#          tools/cmake/kconfig.cmake for every entry in SDKCONFIG_DEFAULTS
#          when "<file>.<idf_target>" exists - do NOT list it explicitly).
#          CI overlays: idf.py -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.ci.qemu"

cmake_minimum_required(VERSION 3.22)   # ESP-IDF v6.0 floor (tools/cmake/project.cmake)

# ---- Firmware version -------------------------------------------------------
# PROJECT_VER must be set BEFORE include(project.cmake); precedence there is
# CONFIG_APP_PROJECT_VER_FROM_CONFIG > PROJECT_VER > version.txt > project(VERSION)
# > git describe > "1". Never create version.txt, never enable
# APP_PROJECT_VER_FROM_CONFIG: both sit ABOVE git describe in that chain and
# would silently replace the commit-derived version with a hand-maintained one
# (a reproducibility/precedence hazard, not a length one).
#
# Why 31 characters: esp_app_desc_t.version is char[32] (esp_app_desc.h).
# ESP-IDF's components/esp_app_format/CMakeLists.txt cuts PROJECT_VER from ANY
# source to 31 characters at configure time (string(SUBSTRING ... 0 31
# PROJECT_VER_CUT)) before it becomes the compile definition, so an over-long
# describe string is a SILENT TRUNCATION; the _Static_assert in esp_app_desc.c
# is a belt-and-braces guard that cannot trip on length alone. Our own
# SUBSTRING makes the cut explicit, and the message(STATUS) below logs the FULL
# describe string next to the cut one so a truncated version is never a
# surprise. A describe such as "v0.1.0-12-gabcdef1-dirty" is 24 chars; keep
# annotated tags short: v0.1.0, v1.2.3.
execute_process(
    COMMAND git describe --tags --always --dirty --match "v[0-9]*"
    WORKING_DIRECTORY "${CMAKE_CURRENT_LIST_DIR}"
    OUTPUT_VARIABLE  _git_desc
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET)
if(NOT _git_desc)
    set(_git_desc "0.0.0-nogit")   # no repo, or CI forgot fetch-depth: 0
endif()
string(SUBSTRING "${_git_desc}" 0 31 PROJECT_VER)
message(STATUS "Super Spectral firmware version: ${PROJECT_VER} (git: ${_git_desc})")

# ---- Build system v1 --------------------------------------------------------
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(superspectral)

# Every build log states which IDF built it (docs/devenv/env.lock.md cross-check).
idf_build_get_property(_idf_ver IDF_VER)
message(STATUS "ESP-IDF ${_idf_ver} from $ENV{IDF_PATH} (pin: ADR 0001, .envrc)")
