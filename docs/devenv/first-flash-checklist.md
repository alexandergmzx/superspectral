# First-flash checklist — Phase 0, before any custom image touches the watch

**Decision:** the first session with the hardware writes **nothing** to it. It records the chip, backs up all 16 MB, reads the eFuses, decodes the vendor partition table, proves the backup restores, and only then (optionally) re-flashes the vendor factory image. Every later flash goes through [`tools/flash.sh`](../../tools/flash.sh) to `ota_1`. (Critic B1; roadmap phase **E2**; ADR 0015.)

**Why a signed-off checklist and not a bullet:** the first flash of our `partitions.csv` overwrites the vendor `nvs`, which on LilyGO boards can carry calibration and BLE identity; the first backlight write can, on a `VDD_SPI_FORCE == 0` part, put 3.3 V on a 1.8 V flash. Both are irreversible, both are cheap to make safe, and the recipe they come from scheduled the safety checks *after* the risky steps. This document fixes the order.

> **NEVER BURN EFUSES.** `espefuse` is a read-only tool for the life of this project: `summary` and `dump` only. Never `burn-efuse`, `burn-key`, `burn-bit`, `burn-block-data`, `set-flash-voltage`, never `--do-not-confirm`, never enable Secure Boot or Flash Encryption (both pinned `=n` in `sdkconfig.defaults` and asserted by pre-commit). Burning is one-way (0 → 1). `set-flash-voltage 3.3V` destroys the 1.8 V W25Q128JW; `DIS_USB_JTAG`/`DIS_USB_SERIAL_JTAG` remove the only debug probe and the only recovery path on a board with zero exposed GPIO ([pitfalls](pitfalls.md) F1–F3).

## Preconditions

- [ ] E1 done: `idf.py --version` = v6.0.2 in the repo shell; `esptool version` is 5.x (all commands below use esptool v5 **hyphenated** names — `read-flash`, `write-flash`, `flash-id`; the `_` forms and `.py` scripts are deprecated).
- [ ] udev symlink present: `ls -l /dev/ttyTWATCH` ([setup.md §4](setup.md#4-udev--a-stable-device-name-nothing-else)). `export ESPPORT=/dev/ttyTWATCH` (done by `.envrc`).
- [ ] Battery charged; short known-good cable; **no hub**; no other `idf.py monitor` holding the port.
- [ ] Off-repo storage ready for a 16 MB file (external drive or private object store — not git, not git-LFS in this repo; [backup-policy.md](backup-policy.md)).
- [ ] `lsusb -d 303a:` shows `303a:821b` (shipped Arduino firmware). Record it.

Convenience variables for the session:

```bash
export ESPPORT=/dev/ttyTWATCH
ET="esptool --chip esp32s3 --port $ESPPORT --baud 460800"
EF="espefuse --chip esp32s3 --port $ESPPORT"
STAMP=$(date -u +%Y%m%d)
```

## Step 1 — Identify the chip and the flash (read-only)

```bash
$ET chip-id
$ET flash-id          # expect 16 MB; manufacturer/device ID of the W25Q128JW (Winbond 0xEF) — record verbatim
$ET read-mac
$ET get-security-info
```

- [ ] Record chip revision, flash manufacturer/device ID, detected size, MAC, security-info output in [`../hw/README.md`](../hw/README.md) ("Factory baseline ledger").
- [ ] Flash size **must** read 16 MB; if it does not, stop — `sdkconfig.defaults.esp32s3` and `partitions.csv` assume it ([pitfalls](pitfalls.md) B4/B5).

## Step 2 — Full-flash backup, hashed, stored off-repo

```bash
$ET read-flash 0 0x1000000 twatch-s3-factory-backup-$STAMP.bin
sha256sum twatch-s3-factory-backup-$STAMP.bin | tee twatch-s3-factory-backup-$STAMP.sha256
$ET verify-flash 0 twatch-s3-factory-backup-$STAMP.bin     # read-back consistency: must report OK
```

- [ ] Two copies of the `.bin` in two off-repo locations; the `.sha256` line copied into the ledger in `docs/hw/README.md`.
- [ ] `verify-flash` passed (a read that changes between passes means a bad cable or an unstable 3.3 V — fix before continuing).

## Step 3 — eFuse baseline, committed

```bash
$EF summary
$EF summary --format json --file docs/hw/efuse-baseline.json
$EF summary VDD_SPI_FORCE VDD_SPI_TIEH VDD_SPI_XPD DIS_USB_JTAG DIS_USB_SERIAL_JTAG FLASH_TYPE SPI_BOOT_CRYPT_CNT SECURE_BOOT_EN
# (or: idf.py efuse-summary from firmware/twatch-s3)
```

- [ ] `docs/hw/efuse-baseline.json` replaced (it ships as a placeholder) and committed — it is an irreplaceable, free record.
- [ ] `DIS_USB_JTAG == False` and `DIS_USB_SERIAL_JTAG == False`. If either is `True` the recovery model of the whole project changes — stop and record.
- [ ] `SPI_BOOT_CRYPT_CNT == 0` and `SECURE_BOOT_EN == False` (a previous owner's firmware could have burned them; the pre-commit grep only guards *our* config — critic B12).
- [ ] `FLASH_TYPE` consistent with the quad-flash assumption in `sdkconfig.defaults.esp32s3`.
- [ ] **`VDD_SPI_FORCE` recorded** → decision table below.

### The GPIO45 / VDD_SPI decision (ADR 0016)

GPIO45 is simultaneously the display backlight and the VDD_SPI strapping pin (MTDI). With a 1.8 V flash, GPIO45 must read HIGH at reset to select 1.8 V — unless the eFuses force it.

| `VDD_SPI_FORCE` | Meaning | Consequence for firmware |
|---|---|---|
| `1` | VDD_SPI fixed by `VDD_SPI_TIEH`/`VDD_SPI_XPD`; GPIO45 ignored at reset | GPIO45 is free — LEDC backlight PWM without constraints. Record `TIEH`/`XPD` too |
| `0` | GPIO45 level at reset selects VDD_SPI: low/floating → **3.3 V**, high → 1.8 V | **Hardware-destruction risk.** Before any backlight code: confirm the external pull-up on the schematic; mandate LEDC idle-**high** and an explicit release-to-input of GPIO45 inside a single `spectral_reboot()` wrapper that is the only permitted path to `esp_restart()`/deep sleep; add a `_Static_assert`-style review gate in `twatch_bsp`. Never drive GPIO45 low across a reset boundary |

Also settle on paper, from the ESP32-S3 datasheet pin table + schematic, before debugging audio: GPIO47 (PDM DATA) and GPIO48 (I²S BCLK) are in the VDD_SPI domain on R8V parts — see [`../hw/twatch-s3-pins.md`](../hw/twatch-s3-pins.md).

## Step 4 — Vendor partition table, decoded and committed

```bash
$ET read-flash 0x8000 0x1000 vendor-parttable-$STAMP.bin
python3 "$IDF_PATH/components/partition_table/gen_esp32part.py" vendor-parttable-$STAMP.bin   # binary → CSV on stdout
```

- [ ] Paste the decoded CSV into [`../hw/vendor-partition-table.md`](../hw/vendor-partition-table.md) (replacing the placeholder) with the date, the backup's sha256 and the `gen_esp32part.py` version (`git -C $IDF_PATH describe`).
- [ ] From the decoded table, carve the vendor `nvs` (and any `phy_init`/calibration) regions out of the full backup by offset, e.g. `dd if=twatch-s3-factory-backup-$STAMP.bin of=vendor-nvs-$STAMP.bin bs=4096 skip=$((OFF/4096)) count=$((SIZE/4096))`, hash them, store them with the backup. This is what lets you restore identity/calibration selectively after our table is flashed.

## Step 5 — Prove the backup restores (scratch region first)

Never test a restore by re-writing 16 MB over a working device. Pick a **scratch region**: a data partition from the decoded vendor table that is demonstrably unused (all `0xFF` in the backup — check with `od -An -tx1 -j OFF -N SIZE file | sort -u`), or the tail of the flash beyond the last vendor partition.

```bash
OFF=0x...; SIZE=0x...                                   # from step 4, 4 KiB-aligned
dd if=twatch-s3-factory-backup-$STAMP.bin of=slice.bin bs=4096 skip=$((OFF/4096)) count=$((SIZE/4096))
$ET erase-region $OFF $SIZE
$ET write-flash $OFF slice.bin
$ET verify-flash $OFF slice.bin                          # write path proven
$ET --after hard-reset run                               # device still boots the vendor firmware
```

- [ ] Erase → write → verify succeeded on the scratch region; the watch still boots and enumerates as `303a:821b`.
- [ ] Write down the exact restore command for the full image: `esptool --chip esp32s3 --port $ESPPORT --baud 460800 write-flash --flash-size 16MB 0 twatch-s3-factory-backup-$STAMP.bin` (the `.bin` read from offset 0 already contains the bootloader header with the correct flash parameters; `--flash-mode keep` is the default).

## Step 6 (optional) — Vendor factory image, once

LilyGoLib publishes `firmware/factory.twatchs3.sx1262.<date>.bin`. Flashing it once proves display/touch/PMU/radio are alive with zero source-tree or licence involvement — this is the *only* sanctioned use of LilyGoLib's drivers (ADR 0001, ADR 0004). It is optional because the watch already ships with equivalent firmware; use it only if the shipped image is suspect.

```bash
# offset per LilyGoLib's README for merged factory images — confirm there before running (verify)
$ET write-flash --flash-size 16MB 0x0 factory.twatchs3.sx1262.<date>.bin
```

- [ ] If done: the file's sha256 and source URL recorded in the ledger; the watch enumerates as `303a:821b` again.

## Sign-off

| Step | Done (date / initials) | Artefact |
|---|---|---|
| 1 chip / flash ID | | ledger row in `docs/hw/README.md` |
| 2 full backup + sha256 + verify | | two off-repo copies; hash in ledger |
| 3 eFuse JSON + `VDD_SPI_FORCE` decision | | `docs/hw/efuse-baseline.json`; ADR 0016 status |
| 4 vendor table decoded; nvs slice saved | | `docs/hw/vendor-partition-table.md` |
| 5 restore proven on a scratch region | | ledger note |
| 6 vendor factory image (optional) | | ledger note |

Only after every row is signed: first build flashed with `tools/flash.sh --no-arm` to `ota_1` (ota_0 still empty), then the week-1 tests — [experiment 0002](../validation/experiments/) (rollback + boot-guard race) — and only then a `--recovery-image` into ota_0 and the switch to the default `tools/flash.sh` (rollback armed). [brick-runbook.md](brick-runbook.md) stays open in another window.
