# 0014 — The 16 MB partition layout is frozen: two 4 MB OTA slots, no factory app, `ota_0` is the golden recovery image

- **Status:** accepted
- **Date:** 2026-08-21
- **Context:** The T-Watch S3 has 16 MB of flash and **no externally reachable BOOT button** — recovery from a bad image must not depend on a human reaching the internal PCB ([ADR 0015](0015-anti-brick-policy.md)). ESP-IDF's default tables assume 2 MB flash and a 1 MB app; the vendor's own table (`app0`/`app1` 6400 K at `0x10000`/`0x650000`, SPIFFS, 64 K coredump — [`docs/hw/vendor-partition-table.md`](../hw/vendor-partition-table.md)) has no room for a wear-levelled preset store and uses SPIFFS, which is effectively unmaintained. App partition offsets are part of the OTA contract: once units are in the field, moving them invalidates every OTA image and every documented recovery command.
- **Decision:** [`firmware/twatch-s3/partitions.csv`](../../firmware/twatch-s3/partitions.csv), applied with `CONFIG_PARTITION_TABLE_CUSTOM=y` **and** `CONFIG_ESPTOOLPY_FLASHSIZE_16MB=y` (both knobs are needed — a correct table flashed with a 2 MB size header still fails):

  | Name | Type/Sub | Offset | Size | Role |
  |---|---|---|---|---|
  | `nvs` | data/nvs | `0x9000` | 24 K | settings |
  | `otadata` | data/ota | `0xF000` | 8 K | two redundant records; rollback state lives here |
  | `phy_init` | data/phy | `0x11000` | 4 K | kept empty for a future radio ([ADR 0017](0017-no-radio-in-v1-trimmed-component-set.md)) |
  | `ota_0` | app/ota_0 | `0x20000` | 4 MB | **golden recovery image** — written only with `tools/flash.sh --recovery-image` |
  | `ota_1` | app/ota_1 | `0x420000` | 4 MB | every development build (`tools/flash.sh`, rollback armed) |
  | `nvs_keys` | data/nvs_keys | `0x820000` | 4 K | reserved so NVS encryption needs no repartition |
  | `presets` | data/littlefs | `0x821000` | 1 MB | preset JSON store (wear-levelled, power-fail safe) |
  | `takes` | data/fat | `0x921000` | ~6.8 MB | recorded takes (sequential files; USB MSC-exposable) |
  | `coredump` | data/coredump | `0xFF1000` | 60 K | the only post-mortem on a sealed device |

  The table ends at exactly `0x1000000`; app partitions are 64 KB-aligned (the 56 KB gap at `0x12000`–`0x20000` is that alignment, decided in the scaffold review). **No factory partition**: a factory image still needs something to *decide* to boot it, and on this board that decider would be the button inside the case; automatic rollback to `ota_0` needs no human. The golden image in `ota_0` is the one that has passed the gate ([`firmware/idf-gate/`](../../firmware/idf-gate/README.md), sha256 in [experiment 0002](../validation/experiments/0002-rollback-and-boot-guard-race.md)); it is replaced only by a build that has itself passed experiment 0002.

  **Changing any app offset after the first fielded unit is a new ADR, not an edit.** The `takes`/`presets` split may be rebalanced only before shipping and only from the end of the table backwards.
- **Alternatives:**
  - *ESP-IDF built-in `partitions_two_ota.csv` (3 × 1 MB).* Rejected: LVGL + esp-dsp builds exceed 1 MB quickly and 14 MB would go unused.
  - *Keep the vendor layout.* Rejected: SPIFFS for the preset store; no coredump headroom policy; and it would test the wrong thing — our firmware's contract is our table.
  - *Factory + two OTA slots.* Rejected: 4 MB for an image that needs the internal button to be selected.
  - *SPIFFS for `presets`.* Rejected: unmaintained, not power-fail safe; LittleFS (`joltwallet/littlefs`, subtype 0x83) is.
- **Consequences:**
  - (+) Exercised on hardware 2026-08-21: golden image in `ota_0`, four armed flashes to `ota_1`, four automatic rollbacks, stable `trying OTA 0` afterwards ([experiment 0002](../validation/experiments/0002-rollback-and-boot-guard-race.md)).
  - (+) `tools/flash.sh` reads the offsets from this file, so the script and the table cannot drift.
  - (−) `idf.py flash` would overwrite `ota_0`; the only sanctioned path for development builds is `tools/flash.sh` — a rule, enforced by habit and the README, not by the toolchain.
  - (−) 4 MB per slot is generous; if `takes` ever needs more, the rebalance must happen before any unit leaves the bench.
  - (−) Restoring the vendor firmware is a whole-flash operation (different table), documented in [`docs/hw/vendor-partition-table.md`](../hw/vendor-partition-table.md).

  Reference basis: ESP-IDF Partition Tables guide and OTA/app_update reference ([bibliography 02](../bibliography/02-application-notes.md)); devenv critique B2; `gen_esp32part.py` round-trip in CI (`partitions-arithmetic` hook).
