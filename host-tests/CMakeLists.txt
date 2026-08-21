# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
#
# Plain-CMake host tests for the pure-C99 DSP core. No ESP-IDF involved at
# all: esp-dsp cannot build on the IDF `linux` target (unconditional Xtensa
# assembly in its CMakeLists, esp_attr.h/esp_log.h includes), so spectral_core
# is kept free of esp_* includes (`REQUIRES ""` on the IDF side) and tested
# here with the host compiler, AddressSanitizer + UndefinedBehaviorSanitizer,
# and ctest. The esp-dsp fast path is validated separately by the
# backend-agreement test on QEMU/target (tests/README.md).
#
#   cmake -S host-tests -B host-tests/build -G Ninja
#   cmake --build host-tests/build
#   ctest --test-dir host-tests/build --output-on-failure
#
# Apache-2.0 on purpose: this tree is NOT under host/ (GPL-3.0-or-later) and
# must never import anything from it. Golden vectors produced by host/golden/
# are consumed as data files only.

cmake_minimum_required(VERSION 3.22)
project(spectral_core_host_tests C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Debug CACHE STRING "Build type" FORCE)
endif()

# Same warning policy as the firmware components, so a warning that would
# break the -Werror target build is caught here first. The S3 FPU is
# single-precision: -Wdouble-promotion is the high-value flag.
add_compile_options(
  -Wall -Wextra -Werror
  -Wshadow -Wconversion -Wdouble-promotion -Wformat=2 -Wundef -Wvla
  -fno-fast-math
  -g -O1
  -fsanitize=address,undefined -fno-omit-frame-pointer
)
add_link_options(-fsanitize=address,undefined)

set(SPECTRAL_CORE_DIR
    "${CMAKE_CURRENT_LIST_DIR}/../firmware/twatch-s3/components/spectral_core")
set(SPECTRAL_CORE_INCLUDE "${SPECTRAL_CORE_DIR}/include")
set(GOLDEN_DIR "${CMAKE_CURRENT_LIST_DIR}/../host/golden/outputs")

file(GLOB SPECTRAL_CORE_SRC CONFIGURE_DEPENDS "${SPECTRAL_CORE_DIR}/src/*.c")
file(GLOB SPECTRAL_TEST_SRC CONFIGURE_DEPENDS "${CMAKE_CURRENT_LIST_DIR}/tests/test_*.c")

enable_testing()

if(NOT SPECTRAL_CORE_SRC)
  # Phase 0: the component exists as a skeleton (include/ and src/ hold
  # .gitkeep only). Configuring must still succeed so CI can add the
  # host-tests job the moment the first source file lands.
  message(STATUS "spectral_core has no sources yet - nothing to build (Phase 0 skeleton)")
  return()
endif()

add_library(spectral_core STATIC ${SPECTRAL_CORE_SRC})
target_include_directories(spectral_core PUBLIC "${SPECTRAL_CORE_INCLUDE}")
target_compile_definitions(spectral_core PRIVATE SPECTRAL_HOST_BUILD=1)
target_link_libraries(spectral_core PUBLIC m)

# One executable per tests/test_<block>.c; each registers as a ctest case and
# receives the golden-vector directory so it can fopen() the arrays that
# host/golden/ produced. Tolerances live in docs/validation/golden-files.md.
foreach(test_src IN LISTS SPECTRAL_TEST_SRC)
  get_filename_component(test_name "${test_src}" NAME_WE)
  add_executable(${test_name} "${test_src}")
  target_link_libraries(${test_name} PRIVATE spectral_core)
  target_compile_definitions(${test_name} PRIVATE
    SPECTRAL_GOLDEN_DIR="${GOLDEN_DIR}")
  add_test(NAME ${test_name} COMMAND ${test_name})
  set_tests_properties(${test_name} PROPERTIES
    ENVIRONMENT "ASAN_OPTIONS=detect_leaks=1:strict_string_checks=1;UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1")
endforeach()
