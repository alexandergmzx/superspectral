# 0016 — GPIO45 backlight PWM is safe on this unit: VDD_SPI is forced to 3.3 V by eFuse

- **Status:** accepted
- **Date:** 2026-08-21
- **Context:** On the T-Watch S3 the LCD backlight is driven from **GPIO45**, which is also the ESP32-S3's **VDD_SPI strapping pin** (MTDI): when `EFUSE_VDD_SPI_FORCE == 0` the level of GPIO45 at reset selects the flash/PSRAM I/O voltage (low/floating → 3.3 V, high → 1.8 V). The schematic and the Zephyr board file name the flash as **W25Q128JWPIQ, a 1.8 V part**; had that been true with `FORCE == 0`, any firmware that left GPIO45 low across a reset could bring VDD_SPI up at 3.3 V into a 1.8 V flash — a hardware-destruction risk the roadmap gated all backlight code behind ([pins doc](../hw/twatch-s3-pins.md), [first-flash checklist](../devenv/first-flash-checklist.md) step 3). GPIO47 (PDM mic data) and GPIO48 (I²S BCLK) sit in the same VDD_SPI domain, so the question also decided whether the audio pins were 1.8 V or 3.3 V.
- **Decision:** Resolved **by measurement on unit `48:27:e2:e9:b0:8c`, 2026-08-20** ([`docs/hw/efuse-baseline.json`](../hw/efuse-baseline.json), read with `espefuse summary`, nothing burned):
  - `VDD_SPI_FORCE = True`, `VDD_SPI_XPD = True`, `VDD_SPI_TIEH = "VDD_SPI connects to VDD3P3_RTC_IO"` → **VDD_SPI is forced to 3.3 V by eFuse; GPIO45 is never sampled as a strap.**
  - `esptool flash-id`: JEDEC `ef 4018` → **Winbond W25Q128JV-class, 3.3 V** (the 1.8 V JW part reads `6018`); *"Flash voltage set by eFuse: 3.3V"*. The schematic's JW marking does not describe this unit.
  - Therefore: **GPIO45 is driven as a plain LEDC PWM output** (5 kHz, 8-bit, ramped from 0 after the first frame is in GRAM, ALDO2 enabled first — the order exercised by the gate, [`firmware/idf-gate/`](../../firmware/idf-gate/README.md)). No idle-high rule, no reboot wrapper. GPIO47/48 are 3.3 V-domain pins; the SPM1423 and MAX98357A need no level consideration.
  - The **check stays mandatory for every new unit**: the [`docs/hw/README.md`](../hw/README.md) ledger row `VDD_SPI_FORCE / TIEH / XPD` must be filled from that unit's own eFuse read before its backlight code runs. A unit that reads `FORCE == 0` re-opens this ADR (the idle-high + single-reboot-wrapper branch is written in the pins doc's cautions table).
- **Alternatives:**
  - *Assume the schematic (1.8 V JW) and write the defensive branch unconditionally.* Rejected: the defensive branch costs a wrapper around every reset path and a backlight that cannot be fully off at reset; the eFuse read is a 10-second, zero-risk operation that settles it per unit.
  - *Burn `VDD_SPI_FORCE` ourselves on units where it is 0.* Rejected outright: [ADR 0015](0015-anti-brick-policy.md) — eFuses are read-only for the life of the project; a wrong burn on a 1.8 V part is permanent.
- **Consequences:**
  - (+) Backlight code is ordinary LEDC; the PMU/backlight bring-up order in the gate becomes the `twatch_bsp` reference sequence.
  - (+) One more schematic claim is known to be wrong for shipped units (after the mic's obsolescence): treat LilyGO part markings as "verify per unit", which [bibliography 01](../bibliography/01-datasheets.md) now says.
  - (−) The per-unit eFuse check is a process step, not a code guard; forgetting it on a hypothetical `FORCE == 0` unit is the residual risk. Mitigation: the first-flash checklist and the ledger row.

  Reference basis: ESP32-S3 Hardware Design Guidelines, VDD_SPI voltage-control table ([01 §Espressif](../bibliography/01-datasheets.md)); ESP32-S3 datasheet pin-domain table; `espefuse` summary of 2026-08-20; gate stage 2b log (`ALDO2 + LEDC 160/255`, frame confirmed visually).
