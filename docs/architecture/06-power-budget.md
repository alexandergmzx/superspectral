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
   DLDO1   ──► R18 0R ──► SPK_VDD ──► MAX98357A amp ... off in v1; does not silence the mic
   VBACKUP ──► PCF8563 RTC via MS412FE coin cell
   (DC1 again, via R2 0R: VDD3V3 = +3V3) ──► SPM1423 PDM mic ... CANNOT be power-gated
```

Two structural consequences of that picture, before any number:

1. **The PSRAM cannot be isolated by rail measurement.** `VDD_SPI_TIEH` reads *"VDD_SPI connects to VDD3P3_RTC_IO"* on this unit ([ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md)), so the octal PSRAM and the flash draw through the SoC's own 3.3 V supply. Isolating them needs a **differential workload** (same frame rate, PSRAM history on vs off), not a probe on a rail.
2. **The microphone term is fixed cost, and now for a structural reason rather than a policy one.** Sheet 6 of the filed schematic ([01 #6](../bibliography/01-datasheets.md), read 2026-08-21) puts U18 `SPM1423HM4H-B` pin 6 `VCC` on the net `+3V3` (C2 100 nF decoupling; R81 is an unpopulated `NC` option), and sheet 1 traces `+3V3` ← R2 `0R` ← `VDD3V3` = the **AXP2101 DCDC1** output node (pins 21 `FB1` / 22 `LX1` / 23 `VIN1`, L5003 2.2 µH, C8229 22 µF) — the same buck that supplies the ESP32-S3 on sheet 2. The microphone is therefore on **DC1**: firmware does not gate it because it *cannot*, and its current is present in every mode including idle. This confirms and supersedes [ADR 0003](../adr/0003-microphone-path.md) decision 10's "always-on rail `(prov.)`", which rested on two vendor code witnesses.

## 2. Rail-by-rail budget

`Analysis mode` = the `live_singing` preset running continuously: PDM capture at 32 kHz, FFT + f0 on core 1, canvas at 50 Hz, backlight on, radio off. Every current cell is `TBD` on purpose.

**How to read the `TBD`s in this table (added 2026-08-21).** They are not all the same
kind of unknown, and conflating them is how a budget stays unfinished. Two classes:

- **`TBD (datasheet)`** — a number that exists on a page somebody has to read. On
  2026-08-21 every one of these that could be closed from a document **already filed
  under `docs/datasheets/`** was closed: ALDO3 (FT6336U and ST7789) and BLDO2
  (DRV2605L). None remain.
- **`TBD (measured, …)`** — a number that does not exist on any page, because it is a
  property of *this* board running *this* firmware: rail currents in analysis mode,
  backlight draw at usable brightness, usable battery capacity. These wait for the
  instrument, and no amount of reading closes them.

One row is still blocked on a third thing — **acquisition**: the panel-module sheet
([01 #15](../bibliography/01-datasheets.md)) is not filed. The BMA423 row was listed
here for the same reason until 2026-08-21, on the claim that Bosch's delisting made the
datasheet unobtainable. **That claim was wrong** — delisting a product page is not the
same as the document ceasing to exist. `BMA423 – Data Sheet`, document number
`BST-BMA423-DS004-00`, revision 2.0, August 2019, answers HTTP 200 as a 2 619 179-byte
PDF from DigiKey's document host (`mm.digikey.com/.../BMA423_Rev2.0_Aug2019.pdf`,
re-fetched and read 2026-08-21); the Mouser mirror already in [01 #22](../bibliography/01-datasheets.md)
is bot-blocked, which is probably what produced the claim. Filing it under
`docs/datasheets/bosch/bma423/` and running `doc_ocr` is a roadmap **D3/D4** acquisition
action, owned by the session that files documents — not a dead end.

| Rail | Powers | Boot state | v1 policy | Current, analysis mode | Filled by |
|---|---|---|---|---|---|
| **DC1** | ESP32-S3 core, and through VDD_SPI the flash + in-package PSRAM; **also the SPM1423 microphone** — schematic-confirmed 2026-08-21 (sheet 1: `VDD3V3` = DCDC1 output; R2 `0R` → `+3V3`; sheet 2: SoC on `+3V3`; sheet 6: mic `VCC` on `+3V3`) | boot-on | never written by firmware | `TBD` — §3 bounds it from below | Phase 1, differential workload |
| **ALDO2** | display backlight (GPIO45 LEDC, 5 kHz/8-bit) | boot-on | enabled last, duty ramped ([ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md)) | `TBD` — **plausibly the largest single term** | Phase 1, swept duty 0→255 |
| **ALDO3** | ST7789V3 panel + FT6336U touch, 3300 mV | boot-on | enabled first, ≥ 10 ms settle, before any SPI/I²C traffic | **≈ 10 mA typ** for controller + touch, from the filed sheets (read 2026-08-21): FT6336U `Iopr` **4 mA** typ / `Imon` 1.5 mA / `Islp` 50 µA (§DC, VDDA = 2.8 V, MCLK 17.5 MHz); ST7789 `IDD` **6.0 mA** typ / 7.5 mA max in Normal mode with a black image, 5.0/6.0 partial+idle, 0.015/0.03 sleep-in. **Two caveats, both load-bearing:** the **V3** preliminary spec's own Table 3 is literally `TBD` in every cell, so the 6.0 mA is the **ST7789V v1.3** sheet used as a proxy; and its typical is at VDD = 2.75 V while this rail runs at 3.30 V. The LCD **glass/panel module** is a separate term that appears in no filed sheet. `TBD (measured, Phase 1)` for the rail as built. | Phase 1 + acq [01 #15](../bibliography/01-datasheets.md) |
| **ALDO4** | SX1262 LoRa | boot-on | **off** — [ADR 0017](../adr/0017-no-radio-in-v1-trimmed-component-set.md), radio held in reset | 0 by construction (verify the rail is actually off) | E2/Phase 1 check |
| **BLDO2** | DRV2605L enable (the rail *is* the enable — no GPIO) | boot-on | on only while haptics are needed | **≤ 7 µA** in STANDBY, **≤ 0.65 mA** quiescent while driving (SLOS854D §6.5, read 2026-08-21); in-situ `TBD (measured, Phase 1)`. Re-enabling costs ≥ 250 µs to I²C-ready (a MIN, §9.3.1 step 1) + ≈ **1.5 ms typ** to output (§6.7 `t(start)`, EN high → output — the MIN and MAX columns are empty, so this is **not** an upper bound) + a calibration restore (§8.5.6 step 6b), so the rail policy is a latency choice, not a battery one ([12 §8](12-interaction-model.md)) | acq [01 #25](../bibliography/01-datasheets.md) + Phase 1 |
| **DLDO1** | MAX98357A amplifier — **schematic-confirmed** 2026-08-21: `DLDO1` → R18 `0R` (populated) → `SPK_VDD` → U27 `VDD` pins 7/8; the alternative `+3V3` feed through R76 is `NC` ([01 #6](../bibliography/01-datasheets.md) sheet 6). The two vendor witnesses ([study notes](../reference-projects/notes/lilygolib-axp2101_notes.md) §6.3) agree | vendor leaves it off | disabled at boot; safe — it does **not** silence the mic | 0 in v1 (no playback path) | closed — drawing read |
| **VBACKUP** | PCF8563 RTC via MS412FE coin cell (≈ 1 mAh, [01 #19](../bibliography/01-datasheets.md)) | — | backup charge on/off is a decision, not a default | `TBD`; the vendor measures the backup charger at **≈ +200 µA** (code comment, [study notes](../reference-projects/notes/lilygolib-axp2101_notes.md) §3.7) | Phase 1 |
| *(**DC1**, via `+3V3`)* | **SPM1423 PDM mic** — schematic-confirmed, see §1 | on before firmware | **not gateable at all** — same buck as the SoC | I_DD **500 µA typ / 600 µA max** at VDD = 1.8 V, F_CLOCK = 2.4 MHz ([01 #9](../bibliography/01-datasheets.md) Rev D) — our rail is **3.3 V** (schematic) and our clock 2.048 MHz, so this is an indication, not our number; and it is not separable at a rail, so it needs a differential workload like the PSRAM term | Phase 1 |
| *(I²C0 loads)* | BMA423 (feature engine on), PCF8563 | on | wrist-raise is a wake source ([ADR 0012](../adr/0012-hands-free-interaction.md), proposed) | BMA423 electrical table, `BST-BMA423-DS004-00` rev 2.0 (read 2026-08-21, **not yet filed** — see the note above): **I_DD 150 µA** typ in Performance mode, **I_DDlp1 14 µA** typ in Low-power mode @ 50 Hz ODR, **I_DDsum 3.5 µA** typ in Suspend, all at nominal VDD/VDDIO, 25 °C, g_FS 4g; `t_s,up` 1 ms. The sheet gives **no separate feature-engine adder** — the whole document contains four `µA` figures and none is feature-specific — so the *delta* for wrist-raise/step/tilt features stays `TBD (measured, Phase 1)` on the rail ([12 §8](12-interaction-model.md)). PCF8563 is [01 #24](../bibliography/01-datasheets.md), unfiled | file + Phase 1 |
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

**Instrument.** An external analyzer on a battery pigtail — Nordic **PPK2** (200 nA–1 A, 100 kS/s, source mode 0.8–5 V; [01 #33](../bibliography/01-datasheets.md)) or a Qoitech **Otii**. Note what the filed document actually is: [01 #34](../bibliography/01-datasheets.md) is the *Otii **Arc*** product specification (2021), **not** the Arc Pro — 2.5 A max continuous / 5 A max peak on an external 7.5–9 V supply (250 mA on USB), current accuracy **±(0.1 % + 50 nA)** up to 19 mA in auto range and ±(0.1 % + 150 µA) above it, sample rate 4 ksps in the ±19 mA range and 1 ksps in the ±2.7 A / ±5.0 A ranges, analog bandwidth 400 Hz. The string "24-bit" appears nowhere in it, and the "nA–5 A, 24-bit" line that circulated in this project (and in the bibliography title for 01 #34) is **not from this sheet** — a correction owed to [01 #34](../bibliography/01-datasheets.md). Either instrument is preferred over the PPK2 because backlight-on peaks may clip the PPK2's 1 A ceiling; if the **Arc Pro** is the one bought, its own specification must be acquired and re-cited before any tolerance is quoted from it. The watch is sealed: **the pigtail/emulation procedure is itself a deliverable** and is `TBD` ([`../validation/README.md`](../validation/README.md) equipment table, [`../../hardware/bom/bill-of-materials.csv`](../../hardware/bom/bill-of-materials.csv)) — without it the metric is unmeasurable, not merely unmeasured.

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
| ~~P4~~ | ~~Which rail powers the SPM1423 (and confirmation that DLDO1 is the amplifier)~~ — **closed 2026-08-21** from the filed schematic ([01 #6](../bibliography/01-datasheets.md) sheets 1/2/6): mic on **DC1** via `+3V3`; `SPK_VDD` on **DLDO1** via R18 `0R`. Roadmap **Q14 / H2 / H-rail** retire with it; [ADR 0003](../adr/0003-microphone-path.md) decision 10 is owed the amendment | — | closed |
| P5 | BMA423 **feature-engine delta** over the 150 µA Performance-mode typ (the datasheet does not itemise it); DRV2605L start-up time out of BLDO2 (decides "gate BLDO2" vs "leave it on") — both base sheets are now read, [01 #25](../bibliography/01-datasheets.md) filed and [01 #22](../bibliography/01-datasheets.md) retrievable but not yet filed | this table; [12 §8](12-interaction-model.md) | BMA423 filed + Phase 1 rail measurement |
| P6 | Panel + touch split of ALDO3, and the ST7789 revision's effect on it | acq [01 #15](../bibliography/01-datasheets.md), [01 #13](../bibliography/01-datasheets.md); **H-lcd** | Phase 1 + D4 |
| P7 | Battery-pigtail / emulation procedure for a sealed watch | [`../validation/README.md`](../validation/README.md) equipment row; BOM bench line | procedure written and executed once |
| P8 | Is idle-state dimming/sleep in scope for v1 at all, given the [ADR 0015](../adr/0015-anti-brick-policy.md) sleep gate and the take state machine? | [ADR 0012](../adr/0012-hands-free-interaction.md) (proposed) `t_idle`; ADR 0015 item 5 | ADR 0012 accepted |

Reference basis: ESP32-S3 Series Datasheet v2.2 §5.6 Tables 5-7, 5-8, 5-9, 5-10 and §5.7 Tables 5-11, 5-12 — the PSRAM preamble to §5.6.2 and the absent current column being as load-bearing as the values ([01 #1](../bibliography/01-datasheets.md), filed and OCR'd); AXP2101 register map and E-Gauge ([01 #17](../bibliography/01-datasheets.md)); Knowles SPM1423HM4H-B Rev D electrical table, I_DD 500 µA typ / 600 µA max at VDD = 1.8 V, F_CLOCK = 2.4 MHz ([01 #9](../bibliography/01-datasheets.md)); the DRV2605L sheet SLOS854D §6.5/§6.7/§8.5.6/§9.3.1 ([01 #25](../bibliography/01-datasheets.md), filed) and the **BMA423** sheet `BST-BMA423-DS004-00` rev 2.0 §Electrical Specification ([01 #22](../bibliography/01-datasheets.md), read 2026-08-21, filing owed); the **LilyGO T-Watch S3 schematic V1.4 sheets 1, 2 and 6** read directly on 2026-08-21 for the mic and amplifier rail identities ([01 #6](../bibliography/01-datasheets.md), filed); panel-module, PSRAM and cell datasheets as *unacquired* dependencies ([01 #15](../bibliography/01-datasheets.md), [01 #21](../bibliography/01-datasheets.md), [01 #18](../bibliography/01-datasheets.md), [01 #19](../bibliography/01-datasheets.md)); PPK2 and **Otii Arc** (not Arc Pro) specifications ([01 #33](../bibliography/01-datasheets.md), [01 #34](../bibliography/01-datasheets.md)); ESP-IDF power-management and sleep-modes guides for DFS and the frequency locks ([02 #33](../bibliography/02-application-notes.md)); the eFuse baseline of 2026-08-20 and [ADR 0016](../adr/0016-backlight-gpio45-vdd-spi-strap.md) for the VDD_SPI domain; [ADR 0015](../adr/0015-anti-brick-policy.md) (sleep gate, PMU watchdog left unarmed), [ADR 0017](../adr/0017-no-radio-in-v1-trimmed-component-set.md) (radio excluded structurally) and [ADR 0003](../adr/0003-microphone-path.md) (decision 10, whose "always-on rail `(prov.)`" this file now resolves to DC1); charge registers, vendor sleep currents and the 4.35 V CV finding from the [LilyGoLib/XPowersLib study notes](../reference-projects/notes/lilygolib-axp2101_notes.md) §3.3, §3.5, §3.6, §3.7, §4.4, §6.3; rail map and battery conflict from [`../hw/twatch-s3-pins.md`](../hw/twatch-s3-pins.md) and the [`../hw/README.md`](../hw/README.md) ledger; the autonomy / energy-per-preset metric rows and the bench-instrument tolerances from [`../validation/README.md`](../validation/README.md); routing IDs Q9, Q26, Q30, H-batt and threshold T9 (Q14 / H2 / H-rail retire with P4) from the [documentation roadmap](../roadmap/documentation-roadmap.md).
