# 06 — Power budget: the rail map is known, every current in it is `TBD`

**The decision this document records is what *not* to publish.** The rail map below is settled — from the eFuse read of unit `48:27:e2:e9:b0:8c` ([ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md), [`../hw/efuse-baseline.json`](../hw/efuse-baseline.json)), the vendor register sequence ([study notes](../reference-projects/notes/lilygolib-axp2101_notes.md) §3), and Zephyr's board file as a second witness ([`../hw/twatch-s3-pins.md`](../hw/twatch-s3-pins.md)). The **consumption** is not settled, and the two terms that dominate it — the active current of the in-package octal PSRAM and the backlight at a brightness a singer can actually read — are **unpublished by their vendors**. The trade-off taken here: a complete rail table with `TBD` in every current column and a named measurement behind each one, instead of a plausible-looking total that would then be quoted for a year. The autonomy verdict against the §4 **≥ 3 h** bound is therefore *deferred to a Phase 1 measurement* (roadmap [Q26](../roadmap/documentation-roadmap.md)), not asserted here.

Everything downstream — the ≥ 3 h row in [`../validation/README.md`](../validation/README.md), §3.7 of the [proposal](../proposal/01-super-spectral-proposal.md), the refresh-rate and decimation trade-off study (objective 4) — reads this file, so a fabricated number here would propagate into a published claim.

## 1. The power tree

```
   cell 470 mAh @ 3.8 V (prov.)  |  400 mAh @ 3.7 V (resellers)?   ── roadmap Q9 / T9
        │
        │ VBAT ── slide switch ──►  ┌───────────────────────────────────────────────┐
        │                           │ AXP2101  (I²C0 0x34)                          │
        └── PPK2 / Otii inserted ──►│  charger: CC 125 mA · CV 4.35 V? (POR 4.2 V)  │
            here (pigtail, TBD)     │  14-bit E-Gauge ──► cross-check, not anchor   │
                                    └───┬───────────────────────────────────────────┘
                                        │
   DC1     ──► ESP32-S3 core ──► VDD_SPI (eFuse → VDD3P3_RTC_IO) ──► flash + in-package
                                                                     8 MB octal PSRAM
   ALDO2   ──► display backlight (GPIO45, LEDC 5 kHz / 8-bit)
   ALDO3   ──► ST7789V3 panel + FT6336U touch (3300 mV)
   ALDO4   ──► SX1262 LoRa ............................ OFF in v1 (ADR 0017)
   BLDO2   ──► DRV2605L enable (the rail *is* the enable — no GPIO)
   DLDO1   ──► MAX98357A amplifier (prov.) ............ off in v1; does not silence the mic
   VBACKUP ──► PCF8563 RTC via MS412FE coin cell
   (always-on 3.3 V rail, prov.) ──► SPM1423 PDM mic ... cannot be power-gated
```

Two structural consequences of that picture, before any number:

1. **The PSRAM cannot be isolated by rail measurement.** `VDD_SPI_TIEH` reads *"VDD_SPI connects to VDD3P3_RTC_IO"* on this unit ([ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md)), so the octal PSRAM and the flash draw through the SoC's own 3.3 V supply. Isolating them needs a **differential workload** (same frame rate, PSRAM history on vs off), not a probe on a rail.
2. **The microphone term is fixed cost.** [ADR 0003](../adr/0003-microphone-path.md) decision 10 records that the SPM1423 sits on an always-on rail *(prov., two vendor code witnesses; the schematic closes it in D3/D4, roadmap Q14/H2)*. Firmware does not attempt to gate it, so its current is present in every mode including idle.

## 2. Rail-by-rail budget

`Analysis mode` = the `live_singing` preset running continuously: PDM capture at 32 kHz, FFT + f0 on core 1, canvas at 50 Hz, backlight on, radio off. Every current cell is `TBD` on purpose.

| Rail | Powers | Boot state | v1 policy | Current, analysis mode | Filled by |
|---|---|---|---|---|---|
| **DC1** | ESP32-S3 core, and through VDD_SPI the flash + in-package PSRAM *(prov. — that DC1 feeds the SoC's 3.3 V supplies is the rail map's reading, confirmed against the schematic in D3/D4)* | boot-on | never written by firmware | `TBD` — §3 bounds it from below | Phase 1, differential workload |
| **ALDO2** | display backlight (GPIO45 LEDC, 5 kHz/8-bit) | boot-on | enabled last, duty ramped ([ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md)) | `TBD` — **plausibly the largest single term** | Phase 1, swept duty 0→255 |
| **ALDO3** | ST7789V3 panel + FT6336U touch, 3300 mV | boot-on | enabled first, ≥ 10 ms settle, before any SPI/I²C traffic | `TBD` (panel and touch separately unread: [01 #13](../bibliography/01-datasheets.md), [01 #16](../bibliography/01-datasheets.md)) | Phase 1 + acq [01 #15](../bibliography/01-datasheets.md) |
| **ALDO4** | SX1262 LoRa | boot-on | **off** — [ADR 0017](../adr/0017-no-radio-in-v1-trimmed-component-set.md), radio held in reset | 0 by construction (verify the rail is actually off) | E2/Phase 1 check |
| **BLDO2** | DRV2605L enable (the rail *is* the enable — no GPIO) | boot-on | on only while haptics are needed | `TBD`; the driver's start-up time out of BLDO2 is unread, so "gate the rail" vs "leave it on" is undecidable ([12 §8](12-interaction-model.md)) | acq [01 #25](../bibliography/01-datasheets.md) + Phase 1 |
| **DLDO1** | MAX98357A amplifier *(prov. — two vendor witnesses, [study notes](../reference-projects/notes/lilygolib-axp2101_notes.md) §6.3)* | vendor leaves it off | disabled at boot; safe — it does **not** silence the mic | 0 in v1 (no playback path) | schematic, D3/D4 |
| **VBACKUP** | PCF8563 RTC via MS412FE coin cell (≈ 1 mAh, [01 #19](../bibliography/01-datasheets.md)) | — | backup charge on/off is a decision, not a default | `TBD`; the vendor measures the backup charger at **≈ +200 µA** (code comment, [study notes](../reference-projects/notes/lilygolib-axp2101_notes.md) §3.7) | Phase 1 |
| *(always-on 3.3 V)* | **SPM1423 PDM mic** *(prov.)* | on before firmware | not gateable | I_DD **500 µA typ / 600 µA max** at VDD = 1.8 V, F_CLOCK = 2.4 MHz ([01 #9](../bibliography/01-datasheets.md) Rev D) — our rail is 3.3 V *(prov.)* and our clock 2.048 MHz, so this is an indication, not our number | Phase 1 |
| *(I²C0 loads)* | BMA423 (feature engine on), PCF8563 | on | wrist-raise is a wake source ([ADR 0012](../adr/0012-hands-free-interaction.md), proposed) | `TBD` — [01 #22](../bibliography/01-datasheets.md) has not been read for the feature-engine running current ([12 §8](12-interaction-model.md)) | acq + Phase 1 |
| DC2–DC5, ALDO1, BLDO1, CPUSLDO, DLDO2 | nothing on this board | Zephyr: DC3/ALDO1 boot-on | **explicitly disabled** by our driver — the vendor leaves DC3, DC4 and BLDO1 on ([study notes](../reference-projects/notes/lilygolib-axp2101_notes.md) §3.3) | quiescent only; the saving is itself `TBD` | Phase 1, rails on vs off |

## 3. The one term with a datasheet — and why it is still a floor, not a value

ESP32-S3 datasheet v2.2 Table 5-9, Modem-sleep (RF clock-gated, CPU running — the only block of the table that describes a build with no radio, [ADR 0017](../adr/0017-no-radio-in-v1-trimmed-component-set.md)), 3.3 V, 25 °C ([01 #1](../bibliography/01-datasheets.md); Typ1 = all peripheral clocks disabled, Typ2 = all enabled):

| Mode | Typ1 (mA) | Typ2 (mA) |
|---|---|---|
| 240 MHz, dual core, 32-bit | 66.2 | 81.3 |
| 240 MHz, dual core, 128-bit (PIE) | 91.7 | 107.9 |
| 240 MHz, WAITI (both cores idle) | 32.9 | 47.6 |
| 160 MHz, dual core, 32-bit | 49.6 | 64.1 |
| 80 MHz, dual core, 32-bit | 33.1 | 47.3 |

The table's own preamble disqualifies it as an answer for this part: *"The measurements below are applicable to ESP32-S3 and ESP32-S3FH8. Since ESP32-S3R2 … ESP32-S3R8 … are embedded with PSRAM, their current consumption might be higher."* **We have the R8.** So Table 5-9 is a *lower bound on the SoC term*, with the size of the excess being exactly unknown item (a) of §4.

Same table, footnote 3: *"For a flash rated at 80 Mbit/s, in SPI 2-line mode the consumption is 10 mA."* Our flash runs QIO at 80 MHz, a different operating point — an order-of-magnitude marker only. Table 5-10 (low power): light-sleep **240 µA**, plus **140 µA** for 8 MB 8-line PSRAM at 3.3 V; deep-sleep **8 µA** with RTC memory and peripherals up; power-off **1 µA**. Tables 5-11 and 5-12 (flash and PSRAM specifications) carry **voltage and clock only — there is no current column**, which is the documentary reason the PSRAM term below is a measurement and not a citation.

## 4. The two unknowns that decide the answer

**(a) Octal PSRAM, active.** Espressif publishes the 140 µA light-sleep adder and nothing else; the in-package die (AP Memory APS6408L class, [01 #21](../bibliography/01-datasheets.md)) has no public active-current figure at 80 MHz octal DDR. Its current appears inside the SoC's own 3.3 V supply, so it is measurable only by difference. It is *not* a small term: PSRAM is where the spectrogram history lives, and the history is written every frame.

**(b) Backlight at usable brightness.** The panel-module datasheet ([01 #15](../bibliography/01-datasheets.md)) has no vendor and no copy — it is `TBD` in the bibliography. PWM duty sets the *average* LED current, but perceived brightness is not linear in duty and "usable" on a 1.3″ screen in daylight is a perceptual judgement, not a register value — so the measurement is a duty sweep paired with a legibility call (which belongs with the glance-zone work of [12 §4](12-interaction-model.md)), not a single number.

Both are roadmap **Q26**, routed to a Phase 1 per-rail measurement. Until they land, no total exists.

## 5. Levers, ranked by expected effect

| # | Lever | Expected effect | Status of the number | Cost |
|---|---|---|---|---|
| 1 | **Backlight PWM / auto-dim** (duty, and dimming between phrases) | largest, by §4(b) | `TBD` — the whole point of Q26 | legibility; interacts with the hands-free model, and `setBrightness(0)` must never be allowed to send `SLPIN` ([study notes](../reference-projects/notes/lilygolib-axp2101_notes.md) §4.4) |
| 2 | **240 → 160 MHz** when the preset's N allows | **−16.6 mA (Typ1) / −17.2 mA (Typ2)**, dual-core 32-bit — arithmetic on Table 5-9 | sourced (bound, not value: the PSRAM excess rides on top) | costs a third of the cycle budget, so it is a per-preset choice, not a global one; DFS needs `ESP_PM_*_FREQ_MAX` locks or I²S/SPI clocks move ([02 #33](../bibliography/02-application-notes.md)) |
| 3 | **Float `fc32`, never PIE `sc16`** | avoids **+25.5 mA (Typ1) / +26.6 mA (Typ2)** at 240 MHz — arithmetic on Table 5-9 | sourced | none — the choice is already forced by dynamic range (ADR 0006, [backlog](../adr/README.md)) |
| 4 | **Refresh 50 → 25–30 Hz** on a static signal | display SPI + render CPU + panel; unquantified | `TBD` (roadmap Q30) | the 50 Hz `live_singing` claim in the RQ; a trade-off study, not a default |
| 5 | **Never enabling the radio** ([ADR 0017](../adr/0017-no-radio-in-v1-trimmed-component-set.md)) | structural: Wi-Fi peaks **88/91 mA RX**, **to 340 mA TX**; BLE **93 mA RX**, **to 335 mA TX** (Tables 5-7/5-8, [01 #1](../bibliography/01-datasheets.md)) | sourced (peaks) | already paid — the exclusion is `set(COMPONENTS main)`, not a Kconfig flag |
| 6 | **Disabling the unused rails** (DC2–5, ALDO1, BLDO1, CPUSLDO, DLDO2) | quiescent current of three regulators the vendor leaves on | `TBD` | none; it is our boot policy already |
| — | *Sleep* | not a lever **during** analysis (continuous by definition); it is the idle-state lever | vendor-published, not ours: light sleep **2.38 mA**, deep sleep **530/460 µA** (backup on/off), deep sleep with touch wake **1.08 mA**, power-off **50 µA**; display + touch asleep but powered ≈ **103.4 µA**; leaving ALDO3 off in deep sleep costs an anomalous **+≈ 600 µA** ([study notes](../reference-projects/notes/lilygolib-axp2101_notes.md) §3.7) | every entry stays behind the [ADR 0015](../adr/0015-anti-brick-policy.md) item-5 gate — sleep is one of the documented ways to lose the USB-Serial-JTAG port |

## 6. The battery, and why 470 vs 400 mAh is not a detail

Two sources disagree by ~15 %: **470 mAh @ 3.8 V** (LilyGoLib's `BATTERY_PARAMS_470mAh[]` gauge blob and Zephyr) vs **400 mAh @ 3.7 V** (resellers) — [01 #18](../bibliography/01-datasheets.md), roadmap **Q9**, threshold **T9**, hardware question **H-batt**. It is closed by reading the shipped cell's label at teardown (D4), not by argument.

What it costs, as arithmetic and nothing more:

```
   average-current ceiling for 3 h  =  C_rated / 3 h
        470 mAh  →  156.7 mA          400 mAh  →  133.3 mA
```

Both ceilings assume `C_usable == C_rated`, which is false: usable capacity is the rated capacity times a derating factor `k` for the PMU's cutoff voltage, converter efficiency, cell age and temperature. **`k` is `TBD`** and is measured, not assumed — which is why the honest statement today is a ceiling and a missing factor, not a runtime.

Per threshold T9: if the cell is 400 mAh, the ≥ 3 h target **stands** and this budget is re-derived against the smaller number; the margin statement in proposal §3 changes.

## 7. The charge target — a finding that lands directly on the autonomy metric

Read out of the vendor's register writes ([study notes](../reference-projects/notes/lilygolib-axp2101_notes.md) §3.5, against the AXP2101 datasheet [01 #17](../bibliography/01-datasheets.md)):

| Register | Vendor writes | POR default | Meaning |
|---|---|---|---|
| `0x62` (CC) | 5 → **125 mA** | — | matches LilyGO's own *"use a charging current below 130 mA"* guidance |
| `0x64` (CV) | 4 → **4.35 V**, commented *"T-Watch-S3 uses a high-voltage (4.35 V) battery by default"* | **4.2 V** | a 4.35 V high-voltage cell carries ≈ 5 % more usable charge than the same cell taken to 4.2 V |
| pre-charge / termination | 50 mA / 25 mA | 125 mA | both below the POR default |
| `0x67` safety timers | never written (12 h charge-done, 60 min pre-charge, both enabled) | — | left at defaults |

**The finding:** a `twatch_bsp` that never writes `0x64` inherits the POR default of 4.2 V and silently under-charges the cell by roughly 5 % *(prov. — the 5 % is the cell-chemistry rule of thumb the vendor comment implies, not a measurement on this cell)*. On the 470 mAh figure that is ≈ 23 mAh, ≈ 9 min at the 157 mA ceiling of §6 — i.e. it is spent directly out of the ≥ 3 h metric, by omission.

**This document does not decide it**, because the decision is coupled to an unclosed fact: writing 4.35 V into a cell that is actually a 4.2 V part is a safety question, and which cell is fitted is exactly Q9/T9/H-batt. Recorded as open question **P3** below and routed to the [ADR backlog](../adr/README.md) (the number is allocated when the decision is entered there); whatever is chosen must be an explicit register write, never an inherited default.

## 8. How the numbers get made

**Instrument.** An external analyzer on a battery pigtail — Nordic **PPK2** (200 nA–1 A, 100 kS/s, source mode 0.8–5 V; [01 #33](../bibliography/01-datasheets.md)) or Qoitech **Otii Arc Pro** (nA–5 A, 24-bit, ±(0.1 % + 50 nA) below 19 mA; [01 #34](../bibliography/01-datasheets.md)). Otii is preferred because backlight-on peaks may clip the PPK2's 1 A ceiling. The watch is sealed: **the pigtail/emulation procedure is itself a deliverable** and is `TBD` ([`../validation/README.md`](../validation/README.md) equipment table, [`../../hardware/bom/bill-of-materials.csv`](../../hardware/bom/bill-of-materials.csv)) — without it the metric is unmeasurable, not merely unmeasured.

**Cross-check.** The AXP2101's own 14-bit E-Gauge (coulomb counter; battery %, voltage registers — [01 #17](../bibliography/01-datasheets.md)) is logged over USB-Serial-JTAG for the same run. **Disagreement between the external analyzer and the counter is a finding, not a nuisance** — it is reported, and the external instrument is the anchor. Note what the gauge is: the factory blob in the PMU's own ROM registers, which our firmware deliberately does **not** rewrite (`calibrationPMU()` is a one-way write, ADR-gated — [study notes](../reference-projects/notes/lilygolib-axp2101_notes.md) §3.6). It is a convenience readout, not an instrument.

**Method, per term.**

| Term | Procedure |
|---|---|
| Per-rail split | AXP2101 rails switched individually with the workload held constant; each rail's contribution is a difference of two totals |
| PSRAM active | differential workload at fixed frame rate: spectrogram history on vs off (it is not separable at a rail — §1) |
| Backlight | LEDC duty sweep 0 → 255 at fixed content, paired with a legibility judgement to define "usable" |
| Per preset | the same run segmented by preset — six presets × the refresh options; yields `mAh/h` and `mJ` per analysis frame, plus the marginal `mAh/h` per decimation stage (proposal objective 4) |
| Autonomy | full charge → PMU cutoff, per preset, both instruments logging, room temperature recorded |

The recipe belongs in [`../validation/experiments/`](../validation/experiments/README.md) under the standard template (number allocated when written); the results land in the **Autonomy** and **Energy per preset** rows of [`../validation/README.md`](../validation/README.md), with an uncertainty statement per [`../validation/uncertainty-budget.md`](../validation/uncertainty-budget.md).

## 9. The verdict, and its shape

The document is finished when this line has values in it, per preset:

```
   t_autonomy  =  (C_rated × k_derate) / I_avg          verdict: t_autonomy ≥ 3 h ?

   C_rated   = 470 mAh or 400 mAh          TBD  — roadmap Q9 / T9, read at teardown
   k_derate  = cutoff × efficiency × age   TBD  — measured, never assumed
   I_avg     = per preset, both instruments TBD  — Phase 1, roadmap Q26
```

Until then the autonomy figure is `TBD`, and the *shape* of the answer — a pass/fail per preset against a confirmed capacity, cross-checked by two instruments — is the deliverable this file commits to.

**What must not be quoted.** The research syntheses in `scratch/research/` (not committed) carry an interpolated **"≈ 90–150 mA ⇒ ≈ 3.1–5.2 h"**. That is a **research estimate built on the two unknowns of §4**, not a measurement; it is recorded here only so that it is recognised and replaced when it resurfaces. It may not appear in the proposal, the validation table, or any published figure.

## 10. Open questions this document surfaces

| # | Question | Route | Closes when |
|---|---|---|---|
| P1 | Octal PSRAM active current at 80 MHz octal; backlight current at usable brightness | roadmap **Q26** → metric: autonomy, energy per preset; acq [01 #15](../bibliography/01-datasheets.md), [01 #21](../bibliography/01-datasheets.md) | Phase 1 per-rail measurement |
| P2 | 470 vs 400 mAh; and the derating factor `k` from rated to usable capacity | roadmap **Q9** / threshold **T9** / **H-batt** ([`../hw/twatch-s3-pins.md`](../hw/twatch-s3-pins.md)) | cell label at teardown (D4) + Phase 1 discharge |
| P3 | **Charge target:** write `0x64` = 4.35 V, or leave the POR 4.2 V and accept ≈ 5 %? Coupled to P2 — the safety case depends on which cell is fitted | [ADR backlog](../adr/README.md) — a decision, not a measurement | cell identity known (P2) + ADR accepted |
| P4 | Which rail powers the SPM1423 (and confirmation that DLDO1 is the amplifier) | roadmap **Q14 / H2** → [ADR 0003](../adr/0003-microphone-path.md) decision 10, this rail map | schematic read (D3/D4) |
| P5 | BMA423 running current with the feature engine enabled; DRV2605L start-up time out of BLDO2 (decides "gate BLDO2" vs "leave it on") | acq [01 #22](../bibliography/01-datasheets.md), [01 #25](../bibliography/01-datasheets.md) → this table; [12 §8](12-interaction-model.md) | datasheets read |
| P6 | Panel + touch split of ALDO3, and the ST7789 revision's effect on it | acq [01 #15](../bibliography/01-datasheets.md), [01 #13](../bibliography/01-datasheets.md); **H-lcd** | Phase 1 + D4 |
| P7 | Battery-pigtail / emulation procedure for a sealed watch | [`../validation/README.md`](../validation/README.md) equipment row; BOM bench line | procedure written and executed once |
| P8 | Is idle-state dimming/sleep in scope for v1 at all, given the [ADR 0015](../adr/0015-anti-brick-policy.md) sleep gate and the take state machine? | [ADR 0012](../adr/0012-hands-free-interaction.md) (proposed) `t_idle`; ADR 0015 item 5 | ADR 0012 accepted |

Reference basis: ESP32-S3 Series Datasheet v2.2 §5.6 Tables 5-7, 5-8, 5-9, 5-10 and §5.7 Tables 5-11, 5-12 — the PSRAM preamble to §5.6.2 and the absent current column being as load-bearing as the values ([01 #1](../bibliography/01-datasheets.md), filed and OCR'd); AXP2101 register map and E-Gauge ([01 #17](../bibliography/01-datasheets.md)); Knowles SPM1423HM4H-B Rev D electrical table, I_DD 500 µA typ / 600 µA max at VDD = 1.8 V, F_CLOCK = 2.4 MHz ([01 #9](../bibliography/01-datasheets.md)); panel-module, PSRAM, BMA423, DRV2605L and cell datasheets as *unacquired* dependencies ([01 #15](../bibliography/01-datasheets.md), [01 #21](../bibliography/01-datasheets.md), [01 #22](../bibliography/01-datasheets.md), [01 #25](../bibliography/01-datasheets.md), [01 #18](../bibliography/01-datasheets.md), [01 #19](../bibliography/01-datasheets.md)); PPK2 and Otii Arc Pro specifications ([01 #33](../bibliography/01-datasheets.md), [01 #34](../bibliography/01-datasheets.md)); ESP-IDF power-management and sleep-modes guides for DFS and the frequency locks ([02 #33](../bibliography/02-application-notes.md)); the eFuse baseline of 2026-08-20 and [ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md) for the VDD_SPI domain; [ADR 0015](../adr/0015-anti-brick-policy.md) (sleep gate, PMU watchdog left unarmed), [ADR 0017](../adr/0017-no-radio-in-v1-trimmed-component-set.md) (radio excluded structurally) and [ADR 0003](../adr/0003-microphone-path.md) (mic rail open); charge registers, vendor sleep currents and the 4.35 V CV finding from the [LilyGoLib/XPowersLib study notes](../reference-projects/notes/lilygolib-axp2101_notes.md) §3.3, §3.5, §3.6, §3.7, §4.4, §6.3; rail map and battery conflict from [`../hw/twatch-s3-pins.md`](../hw/twatch-s3-pins.md) and the [`../hw/README.md`](../hw/README.md) ledger; the autonomy / energy-per-preset metric rows and the bench-instrument tolerances from [`../validation/README.md`](../validation/README.md); routing IDs Q9, Q14, Q26, Q30, H2, H-batt and threshold T9 from the [documentation roadmap](../roadmap/documentation-roadmap.md).
