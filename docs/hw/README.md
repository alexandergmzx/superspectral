# Hardware facts — LilyGO T-Watch S3

The hardware facts the firmware configuration depends on, kept **next to the evidence that produced them**. This directory holds derived tables and device-specific records; the vendor PDFs themselves live in the reference library ([`../datasheets/lilygo/t-watch-s3/`](../datasheets/lilygo/t-watch-s3/), acquired and filed in phase D3 on 2026-08-20) and are indexed in [bibliography 01](../bibliography/01-datasheets.md). The rail-by-rail power budget is a planned architecture document (`docs/architecture/06-power-budget.md`); the BOM is [`../../hardware/bom/bill-of-materials.csv`](../../hardware/bom/bill-of-materials.csv).

| File | Contents | Status |
|---|---|---|
| [twatch-s3-pins.md](twatch-s3-pins.md) | Pin map, AXP2101 rail map, I²S allocation, strapping-pin cautions (GPIO45/VDD_SPI, GPIO47/48 domain) — derived from the LilyGO schematic and the LilyGoLib MIT hardware document, **not** from arduino-esp32's LGPL `variants/` | **Schematic filed** (D3, 2026-08-20 — both PDFs are committed) and **eFuses read** (E2, 2026-08-20). The file's own provenance paragraph still carries the pre-D3/E2 `(prov.)` wording and is owed the same correction; individual rows that remain unmeasured say so. |
| [efuse-baseline.json](efuse-baseline.json) | `espefuse summary --format json` of *this* unit (112 fields, read 2026-08-20 with esptool 5.3.dev3 over `/dev/ttyACM0`) | **recorded** — human-readable copy in the off-repo backup folder |
| [vendor-partition-table.md](vendor-partition-table.md) | The shipped partition table, decoded with `gen_esp32part.py`; shipped firmware = Arduino on ESP-IDF v4.4.4 | **recorded** 2026-08-20 |

## Factory baseline ledger (filled in E2)

| Item | Value | Recorded |
|---|---|---|
| `esptool chip-id` (chip revision) | ESP32-S3 (QFN56) **revision v0.2**; features: Wi-Fi, BT 5 LE, dual core + LP core, 240 MHz, **embedded PSRAM 8 MB (AP_3v3)**; crystal 40 MHz; USB mode USB-Serial/JTAG | 2026-08-20 |
| `esptool flash-id` (manufacturer / device ID / size) | manufacturer `ef` (Winbond), device `4018` → **W25Q128JV-class, 3.3 V** (a JW 1.8 V part would read `6018`); detected **16 MB**; eFuse flash type quad; *"Flash voltage set by eFuse: 3.3V"* | 2026-08-20 |
| `esptool read-mac` | `48:27:e2:e9:b0:8c` | 2026-08-20 |
| `esptool get-security-info` | TBD | |
| `lsusb -d 303a:` before any custom flash | `303a:1001 Espressif USB JTAG/serial debug unit` on `/dev/ttyACM0` — the shipped firmware already uses the native USB-Serial-JTAG console, not TinyUSB (so the `821b` expectation was wrong for this unit) | 2026-08-20 |
| Full-flash backup file name | `twatch-s3_factory-backup_48-27-e2-e9-b0-8c.bin` in `~/superspectral-backups/2026-08-20/` + `scratch/hw-backup/` (off-git; third copy to external storage still owed — [backup-policy.md](../devenv/backup-policy.md)) | 2026-08-20 |
| Full-flash backup sha256 | `1b6f26d7bbb3ffae30de3765706e4be39007a6b41491d59c76d1d9b6027bee22` (16 777 216 bytes; read over USB-Serial-JTAG at ≈ 10 KB/s — budget 30 min) | 2026-08-20 |
| Vendor `nvs` slice (offset, size, sha256) | `0x9000`, `0x5000`, `f77bc3860d050d144329f5ee4d5390025abcc5ae9be6a70775193a9d7ff219de` | 2026-08-20 |
| Scratch-region restore test (offset, size, result) | read-back comparison instead of a write: regions `0x0` and `0x9000` (64 KB each) re-read and byte-compared → **MATCH**; a write-restore test is deferred until the first custom flash (it is then a whole-flash restore, see [vendor-partition-table.md](vendor-partition-table.md)) | 2026-08-20 |
| Vendor factory image flashed (optional): file, sha256, source URL | TBD | |
| `VDD_SPI_FORCE` / `VDD_SPI_TIEH` / `VDD_SPI_XPD` | **`True` / VDD_SPI connects to VDD3P3_RTC_IO (3.3 V) / `True`** → VDD_SPI is forced to 3.3 V by eFuse; GPIO45 is **not** sampled as a strap → backlight PWM is safe; GPIO47/48 are in the 3.3 V domain → ADR 0016 resolves to "free PWM" | 2026-08-20 |
| `DIS_USB_JTAG` / `DIS_USB_SERIAL_JTAG` | `False` / `False` ✅ (also `DIS_DOWNLOAD_MODE=False`, `DIS_USB_SERIAL_JTAG_DOWNLOAD_MODE=False`, `DIS_PAD_JTAG=False`) — recovery path intact | 2026-08-20 |
| `SPI_BOOT_CRYPT_CNT` / `SECURE_BOOT_EN` | `Disable (0b000)` / `False` ✅; `WR_DIS=0`, `RD_DIS=0`, all key purposes `USER` (unused) | 2026-08-20 |

## Rules

- **eFuses are read-only for the life of the project.** This directory records them; nothing in this repository ever writes them.
- Pin numbers in firmware come from `twatch_bsp/include/twatch_pins.h`, which is derived from [twatch-s3-pins.md](twatch-s3-pins.md) and carries a `_Static_assert` per pin against 19/20. When the schematic is filed and disagrees with this table, the schematic wins and both files change in the same commit.
- **The two LilyGO schematic PDFs are committed** — `lilygo_t-watch-s3_schematic_v1.4.pdf` and `lilygo_t-watch-s3_schematic_2025-03-24.pdf`, both tracked under [`../datasheets/lilygo/t-watch-s3/`](../datasheets/lilygo/t-watch-s3/). The question critic B11 deferred ("linked, not committed") was answered at filing time in D3: both come from MIT-licensed LilyGO repositories (`TTGO_TWatch_Library`, `LilyGoLib`), so they are `redistributable=yes` in the [OCR manifest](../OCR/manifest.tsv) and are committed verbatim under the [ADR 0004](../adr/0004-split-licensing.md) rule. Every *other* vendor PDF whose redistribution terms are unstated stays **local only**, represented by its `_notes.md` and its manifest row — see [`../datasheets/README.md`](../datasheets/README.md) and [bibliography 01](../bibliography/01-datasheets.md) *Redistribution*.

## Open hardware questions routed here

R8 vs R8V marking (VDD_SPI domain), which rail feeds the SPM1423 and the MAX98357A, ST7789 revision (`T_SCYCW` 66 ns vs 16 ns), FT6336U vs FT5336, 470 vs 400 mAh, `ULC0511C` identity, SX1262 DIO3/TCXO — tracked in the roadmap routing table ([`../roadmap/documentation-roadmap.md`](../roadmap/documentation-roadmap.md)) and closed on paper in phase D4 or on the bench in E2.
