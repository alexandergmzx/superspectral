# Vendor partition table — as shipped on unit `48:27:e2:e9:b0:8c`

Decoded on 2026-08-20 (E2 step 4) from the full-flash backup with
`gen_esp32part.py` (ESP-IDF v6.0.2) on the 4 KB sector at offset `0x8000`.
This is the map needed to interpret the backup and to selectively restore the
vendor `nvs` if it is ever needed. Our own layout ([`../../firmware/twatch-s3/partitions.csv`](../../firmware/twatch-s3/partitions.csv), ADR 0014) is **different** — flashing our firmware overwrites this table.

```csv
# ESP-IDF Partition Table
# Name,     Type, SubType,  Offset,    Size,   Flags
nvs,        data, nvs,      0x9000,    20K,
otadata,    data, ota,      0xe000,    8K,
app0,       app,  ota_0,    0x10000,   6400K,
app1,       app,  ota_1,    0x650000,  6400K,
spiffs,     data, spiffs,   0xc90000,  3456K,
coredump,   data, coredump, 0xff0000,  64K,
```

| Fact | Value |
|---|---|
| Shipped firmware | Arduino core on **ESP-IDF v4.4.4** (`esp-idf: v4.4.4 e8bdaf9198` in the app descriptor) — LilyGO factory image |
| Full-flash backup | `twatch-s3_factory-backup_48-27-e2-e9-b0-8c.bin`, 16 777 216 bytes, sha256 `1b6f26d7bbb3ffae30de3765706e4be39007a6b41491d59c76d1d9b6027bee22`; two copies (`~/superspectral-backups/2026-08-20/` and repo `scratch/hw-backup/`, both off-git per [backup-policy.md](../devenv/backup-policy.md)) — **copy one to external storage** |
| Vendor `nvs` slice | offset `0x9000`, size `0x5000`, sha256 `f77bc3860d050d144329f5ee4d5390025abcc5ae9be6a70775193a9d7ff219de` (extract with `dd if=<backup> bs=4096 skip=9 count=5`) |
| Read-back verification | regions `0x0` and `0x9000` (64 KB each) re-read from the device after the backup and compared byte-for-byte: **MATCH** |
| Restore procedure | `esptool -c esp32s3 -p $ESPPORT write-flash 0x0 <backup>` restores the whole device (table, both apps, spiffs, nvs); `write-flash 0x9000 <nvs-slice>` restores only the vendor NVS into *this* vendor layout |

Note that the vendor `app0`/`app1` slots are 6400 K each and start at `0x10000`, whereas ours are 4 MB at `0x20000`/`0x420000` with LittleFS/FAT data partitions — a restore of the vendor image is therefore a whole-flash operation, not a slot swap.
