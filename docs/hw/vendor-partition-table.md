# Vendor partition table — as shipped

**Status: placeholder — decoded in phase E2** ([first-flash-checklist.md](../devenv/first-flash-checklist.md) step 4). Until then the only information is LilyGoLib's published layout description, which is a summary, not a table.

**Why this file exists (critic B1):** the first flash of our [`partitions.csv`](../../firmware/twatch-s3/partitions.csv) overwrites the vendor `nvs`, which on LilyGO boards can carry factory calibration and BLE identity. Without the decoded vendor table you cannot carve those regions out of the 16 MB backup, and therefore cannot restore them selectively later. Decoding is free; doing it after the first custom flash is impossible.

## Procedure

Run from the direnv-activated repo shell, before any custom image is flashed:

```bash
export ESPPORT=/dev/ttyTWATCH
ET="esptool --chip esp32s3 --port $ESPPORT --baud 460800"
STAMP=$(date -u +%Y%m%d)

# 1. Read the one-sector table at the default offset 0x8000 (CONFIG_PARTITION_TABLE_OFFSET).
$ET read-flash 0x8000 0x1000 vendor-parttable-$STAMP.bin

# 2. Decode binary -> CSV (gen_esp32part.py auto-detects a binary input; prints CSV to stdout).
python3 "$IDF_PATH/components/partition_table/gen_esp32part.py" vendor-parttable-$STAMP.bin

# 3. If the vendor used a non-default table offset (the decode fails with a magic-byte error),
#    search the backup: python3 - <<'PY'
#    import re; d=open('twatch-s3-factory-backup-YYYYMMDD.bin','rb').read()
#    print([hex(m.start()) for m in re.finditer(b'\xaa\x50', d) if m.start() % 0x1000 == 0][:8])
#    PY
#    and re-run step 2 with `--offset <found>`.

# 4. Carve the data partitions you may want back (repeat per row of the decoded table):
#    dd if=twatch-s3-factory-backup-$STAMP.bin of=vendor-<name>-$STAMP.bin bs=4096 skip=$((OFF/4096)) count=$((SIZE/4096))
#    sha256sum vendor-<name>-$STAMP.bin
```

Then replace the section below with the decoded CSV **verbatim**, plus the provenance line.

## Decoded table

```text
TBD — phase E2.
Provenance to record: date · unit (MAC from esptool read-mac) · backup sha256 · gen_esp32part.py from ESP-IDF <tag> (<commit>)
```

## Expected shape (prov., from LilyGoLib — verify against the decode)

LilyGoLib's hardware document describes the T-Watch S3 flash as 16 MB with a "3 MB APP / 9.9 MB FATFS" Arduino partition scheme. Under the arduino-esp32 `default_16MB`-style layouts that usually means `nvs` at `0x9000`, `otadata` at `0xE000`, two app slots, a `spiffs`/`fat` data partition and a `coredump` partition — but the exact names, subtypes and offsets of *this* firmware build are not known until decoded. Do not design anything on this paragraph; it exists only so that a decode that looks wildly different triggers a second look (a wrong `--offset`, or a unit that was re-flashed before it reached us).

## What changes once it is decoded

- [`README.md`](README.md) ledger rows for the `nvs` slice and the scratch-region restore test.
- [ADR 0014](../adr/) (partition layout frozen) cites this file for what was overwritten and what was preserved.
- The full restore command in the first-flash checklist is confirmed against the real table.
