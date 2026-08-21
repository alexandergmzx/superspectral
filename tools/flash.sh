#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
#
# flash.sh — the only sanctioned way to put a Super Spectral build on the watch.
#
# Policy (ADR 0014 / ADR 0015, critic B2): ota_0 holds a GOLDEN RECOVERY IMAGE and is
# never overwritten by day-to-day flashing. Development builds go to ota_1 only.
# `idf.py flash` is NOT used for the app because it writes the app at the first app
# partition (ota_0 in our table). This wrapper therefore:
#
#   1. writes the app binary to the ota_1 offset read from partitions.csv (never a
#      hard-coded address), using the flash arguments from build/flasher_args.json;
#   2. points otadata at ota_1 with otatool.py switch_ota_partition;
#   3. ARMS ROLLBACK: otatool's switch_ota_partition rewrites only the ota_seq (+0) and
#      crc (+28) fields of the entry it activates and leaves ota_state (+24) as the
#      sector previously held — 0xFFFFFFFF (ESP_OTA_IMG_UNDEFINED) on an erased half, a
#      stale state otherwise (read in components/app_update/otatool.py,
#      switch_ota_partition). The bootloader applies rollback ONLY to an active entry in
#      state ESP_OTA_IMG_NEW (0x0): NEW -> PENDING_VERIFY at boot, PENDING_VERIFY ->
#      ABORTED at the next boot if the app never marked itself valid; VALID/UNDEFINED/
#      ABORTED entries simply boot. Verified in components/bootloader_support/src/
#      bootloader_utility.c (symbols ESP_OTA_IMG_NEW / ESP_OTA_IMG_PENDING_VERIFY /
#      ESP_OTA_IMG_ABORTED) on the v6.0.1 tree, 2026-08-20. So the wrapper patches the
#      freshly activated otadata entry's ota_state explicitly: NEW for dev builds, VALID
#      for the recovery image, UNDEFINED for --no-arm (esptool write-flash erases the
#      sectors, so any value can be written). The app must then call
#      esp_ota_mark_app_valid_cancel_rollback() after its health checks (display +
#      touch + PMU + USB), or the next reset boots ota_0.
#
# Refuses to touch ota_0 unless --recovery-image is given (writes ota_0, marks it VALID).
# Refuses to touch the bootloader or the partition table unless --bootloader / --table.
# Uses esptool v5 hyphenated command names only. Uses ESPPORT / ESPBAUD from .envrc.
# Brick runbook: docs/devenv/brick-runbook.md. First flash: docs/devenv/first-flash-checklist.md.
set -euo pipefail

usage() {
  cat <<USAGE
usage: tools/flash.sh [options]
  (default)           write build app to ota_1, select it, ARM rollback (state NEW)
  --no-arm            select ota_1 and write ota_state UNDEFINED (no rollback — use only
                      while ota_0 is still empty and rollback would have nowhere to go)
  --recovery-image    write build app to ota_0 and mark it VALID (the golden image). Asks
                      for confirmation. Do this only with a build that has passed the
                      week-1 rollback + boot-guard tests (docs/validation/experiments/0002).
  --bootloader        also write the bootloader (offset/file from flasher_args.json)
  --table             also write the partition table (offset/file from flasher_args.json).
                      DANGER: changes the flash map of a device that may hold takes/presets.
  --build-dir DIR     default: firmware/twatch-s3/build
  --port DEV          default: \$ESPPORT (/dev/ttyTWATCH)
  --baud N            default: \$ESPBAUD (460800)
  --monitor           run idf.py monitor afterwards
  --dry-run           print the commands, do nothing
  -h, --help
USAGE
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_DIR="$REPO_ROOT/firmware/twatch-s3"
BUILD_DIR="$PROJECT_DIR/build"
PORT="${ESPPORT:-/dev/ttyTWATCH}"
BAUD="${ESPBAUD:-460800}"
CHIP="esp32s3"
SLOT_NAME="ota_1"
ARM=1
RECOVERY=0
DO_BOOTLOADER=0
DO_TABLE=0
MONITOR=0
DRY=0
# esptool v5 reset strategy over USB-Serial-JTAG. `watchdog-reset` is the recovery
# fallback but it RE-ENUMERATES the port on Linux (critic B7) — keep the default here.
BEFORE="${ESPTOOL_BEFORE:-default-reset}"
AFTER="${ESPTOOL_AFTER:-hard-reset}"

while [ $# -gt 0 ]; do
  case "$1" in
    --no-arm) ARM=0 ;;
    --recovery-image) RECOVERY=1; SLOT_NAME="ota_0" ;;
    --bootloader) DO_BOOTLOADER=1 ;;
    --table) DO_TABLE=1 ;;
    --build-dir) BUILD_DIR="$2"; shift ;;
    --port) PORT="$2"; shift ;;
    --baud) BAUD="$2"; shift ;;
    --monitor) MONITOR=1 ;;
    --dry-run) DRY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

run() { if [ "$DRY" -eq 1 ]; then printf '+'; printf ' %q' "$@"; echo; else "$@"; fi; }
die() { echo "flash.sh: $*" >&2; exit 1; }

[ -n "${IDF_PATH:-}" ] && [ -d "$IDF_PATH" ] || die "IDF_PATH unset — run from the direnv-activated repo shell"
command -v esptool >/dev/null || die "esptool (v5, hyphenated commands) not on PATH"
[ -f "$BUILD_DIR/flasher_args.json" ] || die "no $BUILD_DIR/flasher_args.json — run idf.py build first"
[ -e "$PORT" ] || die "port $PORT not present (udev SYMLINK rule? cable? see docs/devenv/brick-runbook.md)"

PARTITIONS_CSV="$PROJECT_DIR/partitions.csv"
[ -f "$PARTITIONS_CSV" ] || die "missing $PARTITIONS_CSV"

# --- read the flash map from the committed table and the build's flasher_args.json ----
slot_offset() { # slot_offset <name> -> hex offset from partitions.csv
  awk -F, -v want="$1" '
    /^[[:space:]]*#/ || NF < 5 { next }
    { gsub(/[[:space:]]/, "", $1); gsub(/[[:space:]]/, "", $2); gsub(/[[:space:]]/, "", $4) }
    $1 == want && $2 == "app" { print $4; found = 1; exit }
    END { if (!found) exit 1 }' "$PARTITIONS_CSV"
}
SLOT_OFFSET="$(slot_offset "$SLOT_NAME")" || die "partition $SLOT_NAME (type app) not found in partitions.csv"
OTA0_OFFSET="$(slot_offset ota_0)" || die "partition ota_0 not found in partitions.csv"

read -r APP_FILE BOOT_OFFSET BOOT_FILE TABLE_OFFSET TABLE_FILE < <(python3 - "$BUILD_DIR/flasher_args.json" <<'PY'
import json, sys
j = json.load(open(sys.argv[1]))
print(j["app"]["file"], j["bootloader"]["offset"], j["bootloader"]["file"],
      j["partition-table"]["offset"], j["partition-table"]["file"])
PY
)
mapfile -t WRITE_FLASH_ARGS < <(python3 -c 'import json,sys; print("\n".join(json.load(open(sys.argv[1]))["write_flash_args"]))' "$BUILD_DIR/flasher_args.json")
APP_OFFSET_IN_BUILD="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["app"]["offset"])' "$BUILD_DIR/flasher_args.json")"

# --- safety interlocks -----------------------------------------------------------------
if [ "$RECOVERY" -eq 0 ] && [ "$((SLOT_OFFSET))" -eq "$((OTA0_OFFSET))" ]; then
  die "refusing to write ota_0 ($OTA0_OFFSET) without --recovery-image"
fi
if [ "$RECOVERY" -eq 1 ] && [ "$DRY" -eq 0 ]; then
  echo "You are about to OVERWRITE the golden recovery image in ota_0 ($OTA0_OFFSET) on $PORT."
  echo "Only do this with a build that passed experiment 0002 (rollback + boot-guard race)."
  read -r -p "Type 'overwrite ota_0' to continue: " ans
  [ "$ans" = "overwrite ota_0" ] || die "aborted"
fi
if [ "$DO_TABLE" -eq 1 ] && [ "$DRY" -eq 0 ]; then
  echo "Writing the partition table changes the flash map; takes/presets/NVS on the device may become unreadable."
  read -r -p "Type 'rewrite table' to continue: " ans
  [ "$ans" = "rewrite table" ] || die "aborted"
fi
# Never flash the ota_0 image via idf.py semantics by accident: the build's own app offset
# is ota_0; we deliberately do NOT use it unless --recovery-image.
echo "app file        : $BUILD_DIR/$APP_FILE (build's default offset $APP_OFFSET_IN_BUILD — NOT used unless --recovery-image)"
echo "target slot     : $SLOT_NAME @ $SLOT_OFFSET"
echo "port / baud     : $PORT / $BAUD   (before=$BEFORE after=$AFTER)"

ESPTOOL=(esptool --chip "$CHIP" --port "$PORT" --baud "$BAUD" --before "$BEFORE" --after no-reset)

# --- 1. optional bootloader / table ----------------------------------------------------
if [ "$DO_BOOTLOADER" -eq 1 ]; then
  run "${ESPTOOL[@]}" write-flash "${WRITE_FLASH_ARGS[@]}" "$BOOT_OFFSET" "$BUILD_DIR/$BOOT_FILE"
fi
if [ "$DO_TABLE" -eq 1 ]; then
  run "${ESPTOOL[@]}" write-flash "${WRITE_FLASH_ARGS[@]}" "$TABLE_OFFSET" "$BUILD_DIR/$TABLE_FILE"
fi

# --- 2. app -> chosen slot, verified ---------------------------------------------------
run "${ESPTOOL[@]}" write-flash "${WRITE_FLASH_ARGS[@]}" "$SLOT_OFFSET" "$BUILD_DIR/$APP_FILE"
run "${ESPTOOL[@]}" verify-flash "$SLOT_OFFSET" "$BUILD_DIR/$APP_FILE"

# --- 3. point otadata at the slot (otatool computes the next sequence number) ----------
# (--esptool-args is nargs='+', so it must NOT be the last option before the subcommand.)
OTATOOL=(python3 "$IDF_PATH/components/app_update/otatool.py"
         --esptool-args before="$BEFORE" after=no-reset
         --port "$PORT" --baud "$BAUD" --partition-table-file "$PARTITIONS_CSV")
run "${OTATOOL[@]}" switch_ota_partition --name "$SLOT_NAME"

# --- 4. set ota_state: NEW (arm rollback) for dev builds, VALID for the recovery image -
# esp_ota_select_entry_t = { uint32 ota_seq; uint8 seq_label[20]; uint32 ota_state; uint32 crc }
# (components/bootloader_support/include/esp_flash_partitions.h). otadata is two 4 KiB
# copies; the active one is the valid entry with the highest ota_seq. We patch its
# ota_state field (bytes 24..27 of the entry) in place — crc covers ota_seq only.
# --no-arm writes UNDEFINED explicitly rather than trusting what the sector held
# (otatool does not touch ota_state; a stale ABORTED/VALID would mislead
# esp_ota_get_state_partition() even though the bootloader would still boot it).
if [ "$RECOVERY" -eq 1 ]; then STATE_HEX="02000000"; STATE_NAME="ESP_OTA_IMG_VALID"
elif [ "$ARM" -eq 1 ]; then   STATE_HEX="00000000"; STATE_NAME="ESP_OTA_IMG_NEW"
else                          STATE_HEX="FFFFFFFF"; STATE_NAME="ESP_OTA_IMG_UNDEFINED (no rollback)"
fi
if [ -n "$STATE_HEX" ]; then
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  OTADATA_OFFSET="$(awk -F, '/^[[:space:]]*#/ || NF<5 {next} {gsub(/[[:space:]]/,"",$1); gsub(/[[:space:]]/,"",$4)} $1=="otadata" {print $4; exit}' "$PARTITIONS_CSV")"
  [ -n "$OTADATA_OFFSET" ] || die "otadata partition not found in partitions.csv"
  run "${ESPTOOL[@]}" read-flash "$OTADATA_OFFSET" 0x2000 "$TMP/otadata.bin"
  if [ "$DRY" -eq 0 ]; then
    python3 - "$TMP/otadata.bin" "$STATE_HEX" <<'PY'
import struct, sys, zlib
path, state_hex = sys.argv[1], sys.argv[2]
data = bytearray(open(path, "rb").read())
def entry(i):
    base = i * 0x1000
    seq, state, crc = struct.unpack_from("<I", data, base)[0], struct.unpack_from("<I", data, base + 24)[0], struct.unpack_from("<I", data, base + 28)[0]
    valid = seq != 0xFFFFFFFF and crc == (zlib.crc32(struct.pack("<I", seq), 0xFFFFFFFF) & 0xFFFFFFFF)
    return seq, state, valid
entries = [entry(0), entry(1)]
valid = [i for i, e in enumerate(entries) if e[2]]
if not valid:
    sys.exit("no valid otadata entry after switch_ota_partition — refusing to patch")
active = max(valid, key=lambda i: entries[i][0])
new_state = struct.unpack("<I", bytes.fromhex(state_hex))[0]   # little-endian on the wire
struct.pack_into("<I", data, active * 0x1000 + 24, new_state)
open(path, "wb").write(data)
print(f"otadata entry {active}: seq={entries[active][0]} state 0x{entries[active][1]:08x} -> 0x{new_state:08x}")
PY
  fi
  run "${ESPTOOL[@]}" write-flash "$OTADATA_OFFSET" "$TMP/otadata.bin"
fi
echo "ota_state set to: $STATE_NAME"

# --- 5. reset and optionally monitor ---------------------------------------------------
run esptool --chip "$CHIP" --port "$PORT" --before no-reset --after "$AFTER" run
if [ "$ARM" -eq 1 ] && [ "$RECOVERY" -eq 0 ]; then
  echo "Rollback ARMED: if the app does not call esp_ota_mark_app_valid_cancel_rollback() before the"
  echo "next reset, the bootloader marks ota_1 ABORTED and boots ota_0. That is the intended safety net."
fi
if [ "$MONITOR" -eq 1 ]; then
  run idf.py -C "$PROJECT_DIR" -B "$BUILD_DIR" -p "$PORT" monitor
fi
