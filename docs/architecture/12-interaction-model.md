# 12 — Interaction model: hands-free while singing, touch only between phrases

**Status:** design note for [ADR 0012](../adr/0012-hands-free-interaction.md), which is **proposed**. Nothing here is settled except the hardware primitives; four questions (gesture set, timings, voice-onset, invariant-vs-default) are open and are stated in §8 as the author's decisions. Every interval in this note is `TBD` on purpose — the numbers come from the objective-3 in-use sessions ([proposal §2, §4.4](../proposal/01-super-spectral-proposal.md)), not from this document.

## 1. The rule, and why it exists

> **You cannot touch the watch while singing.**

The device measures the voice from the wrist, so the wrist is part of the instrument. A finger on the glass mid-phrase moves the microphone inside the wrist-position envelope that [`../validation/README.md`](../validation/README.md) reports as a surface, occludes the acoustic port with a hand, couples a mechanical transient into a PDM MEMS microphone sharing a PCB with the touch panel, and costs the singer the phrase. So the interaction model is not a styling choice layered on the UI; it is a **measurement constraint**, and it determines where the take boundary sits — which is why it reaches into the record format ([`../../protocols/specs/README.md`](../../protocols/specs/README.md)).

The singing context is simultaneously **hands-busy** (score, instrument), **breath-busy** (the voice is the signal under measurement, so it cannot also be the command channel without qualification) and **partially eyes-busy** (conductor, score, room). The bibliography records that no specific published source for that combination was found — [09 §D](../bibliography/09-visual-feedback-for-singing.md) marks "hands-busy / eyes-busy interaction literature" as a genuine gap routed to a search task — so this note rests on the small-screen guidance ([09 R3](../bibliography/09-visual-feedback-for-singing.md) watchOS HIG, [09 R4](../bibliography/09-visual-feedback-for-singing.md) Wear OS quality guidelines) plus the hardware, and says so rather than dressing an opinion as a citation.

## 2. Input inventory — what the board can actually offer

| Input | Part / address | Wiring | Produces | Allowed during a take? |
|---|---|---|---|---|
| **Wrist raise** | BMA423 `0x19` on I²C0 | INT1 → **GPIO14** | `BMA423_TILT` (`0x10`) engine interrupt; `BMA423_TILT_INT` (`0x08`) in the status byte | **Yes** — this is the primary hands-free input |
| **Double tap on the case** | BMA423 `0x19` | same INT1 | `BMA423_WAKEUP` (`0x20`), single/double selectable, sensitivity tunable | **Candidate** (decision D1) |
| **Motion context** | BMA423 `0x19` | same INT1 | `bma423_activity_output()` → `STATIONARY` / `WALKING` / `RUNNING` | Not an input — a **take annotation** (motion-artefact flag) |
| **Haptic confirmation** | DRV2605L `0x5A` on I²C0 | **no GPIO enable** — the AXP2101 **BLDO2** rail *is* the enable | ROM waveform library effects | **Output**, with a guard interval (§5) |
| **Touch** | FT6336U `0x38` on I²C1 | INT → GPIO16; `T_RST` **unpopulated** | up to 2 points, gestures | **No** — setup only |
| **Crown** | AXP2101 PWRKEY | not a GPIO | press / hold; **6 s hold = PMU power-off** | Deferred (decision D1); needs the PMU driver |
| **Voice onset** | SPM1423 → I2S0 PCM ring | — | a level/onset decision read *from* the ring | **Open** (decision D3) |

Board facts: [`../hw/twatch-s3-pins.md`](../hw/twatch-s3-pins.md) (all five I²C addresses answered at the E1 gate). Driver facts and the feature-bit values: our [SensorLib study notes](../reference-projects/notes/sensorlib_notes.md) §4.3, read against the pinned `lewisxhe/sensorlib 0.4.1` tarball.

Two configuration facts are load-bearing and easy to lose:

1. The BMA423 tilt engine does not exist without the **6 144-byte `bma423_config_file` blob** (`BMA423_CONFIG_FILE_SIZE`), which is Bosch microcode and is not derivable from a datasheet. Its licence status is an open question owned by [ADR 0004](../adr/0004-split-licensing.md).
2. **`selectPlatform(Platform::WRISTBAND)` must be called explicitly.** Nothing in `bma423_init()` or `SensorBMA4XX::initImpl()` does it; the untouched default is the *phone* 25-parameter set, and the vendor header's own note says the setting "affects tilt detection". A wrist device running the phone parameter set is the single most likely way for this model to feel wrong on hardware.

## 3. The take state machine

```
                    hands-free inputs only above the line
 ─────────────────────────────────────────────────────────────────────────────────

      wrist raise (BMA423_TILT → INT1 → GPIO14)
                 │
                 │            t_settle (TBD)                start: gesture (D1)
                 ▼                 │                        or voice onset (D3)
   ┌────────┐         ┌────────┐   ▼        ┌────────┐              │   ┌───────────┐
   │  IDLE  │────────►│  LIVE  │───────────►│ ARMED  │──────────────┴──►│ RECORDING │
   │        │         │ analyzer│  auto-arm │ pre-roll│                  │ writing   │
   │ screen │         │ running │           │ from the│                  │ a take    │
   │  dark  │         │ no take │           │ PCM ring│                  │  to FAT   │
   └───┬────┘         └────┬────┘           └────┬────┘                  └─────┬─────┘
       ▲                   │                     │                             │
       │  t_idle (TBD)     │  wrist drop         │  wrist drop + t_holdoff     │ stop (D1/D3)
       └───────────────────┴─────────────────────┴─────────────────────────────┤
                                                                               ▼
 ─────────────────────────────────────────────────────────────────────────── ┌────────┐
      touch (FT6336U) is accepted in IDLE and REVIEW only:                    │ REVIEW │
      presets · settings · frequency-axis pinch · take review                 └────────┘
```

Rules the diagram encodes:

- **Touch never appears above the line.** The state machine consumes no touch event while the state is `LIVE`, `ARMED` or `RECORDING`. Whether that is a hard invariant or a default with an escape hatch is decision **D4**; if it is a default, the take record grows a *touch-during-take* flag so the artefact is visible in the data rather than silent.
- **`ARMED` exists so that the attack is not lost.** The PCM ring is already being filled by the DSP task; arming means "the pre-roll window is now retained", so whatever starts the take — a gesture or a voice onset — does not truncate the onset of the phrase.
- **Every transition is confirmed on two channels** (haptic + visual, §5/§6), never on audio.
- The state machine has **no hardware in it**: it takes an event enum and emits an action enum, so it runs in the native-Linux simulator and in host tests ([ADR 0013](../adr/0013-native-linux-simulator-target.md)) and its whole truth table is testable without a watch.

## 4. Glance zones on a 240×240 panel

Mid-phrase, the singer gets a *glance*, not a *read*. Three things must be legible without interpretation: what note is coming out, whether the input is clipping, and whether a take is being recorded. Everything else is chrome.

```
 240 px
┌─────────────────────────────────────────────┐  ── STATUS STRIP ──────────────
│  ● REC   ARMED   ▲clip        preset name   │  state by SHAPE + WORD, never
├─────────────────────────────────────────────┤  by colour alone (WCAG 2.2)
│                                             │
│                                             │  ── ANALYZER CANVAS ──────────
│        spectrogram / spectrum                │  owned by ADR 0007 (raw esp_lcd
│        (raw esp_lcd; LVGL never repaints)   │  + ST7789 scroll) and ADR 0011
│                                             │  (RGB565 colormap LUT)
│                                             │
├─────────────────────────────────────────────┤  ── GLANCE ZONE ──────────────
│      A4   +7 ¢          −18 dBFS            │  fixed position across ALL
└─────────────────────────────────────────────┘  presets; largest type on the
                                                  screen; numerals, not colour
 band heights: (prov.) — the canvas/chrome split is ADR 0007's, and the LVGL
 partial buffers are 2 × 240×30 RGB565 in internal SRAM (see the `ui` component)
```

Requirements that follow, and their sources:

- **The glance zone never re-flows between presets.** A readout that moves is a readout that must be searched for, and searching is not a glance ([09 R3](../bibliography/09-visual-feedback-for-singing.md)).
- **Sizing targets arm's length**, i.e. the 5th–95th-percentile wrist-to-mouth reach of a raised arm, taken from an anthropometric distribution ([03 #21](../bibliography/03-standards.md): ISO 7250-1 landmarks, ANSUR II / DINED tables) — not from the 15/30/45 cm placeholders that [proposal §4.4](../proposal/01-super-spectral-proposal.md) itself flags as a known defect.
- **No state is colour-only**: `REC`, `ARMED` and the clip warning each carry a shape and a word as well as a colour ([03 #23](../bibliography/03-standards.md) / [09 S3](../bibliography/09-visual-feedback-for-singing.md)). The same argument produces the CVD-safe spectrogram map in [ADR 0011](../adr/0011-spectrogram-colormap.md).
- **Touch targets** for the setup screens follow the small-screen minima ([09 R3](../bibliography/09-visual-feedback-for-singing.md), [09 R4](../bibliography/09-visual-feedback-for-singing.md)); they are irrelevant above the line in §3 because nothing is touched there.
- **Daylight legibility is currently an aspiration, not a requirement with a number.** The panel's luminance has never been measured, and the ≈ 450 cd/m² figure that circulates — in the completeness critique as a small-screen sunlight rule of thumb, in [09 §C](../bibliography/09-visual-feedback-for-singing.md) as this panel's brightness — is **unsourced in both places**. It stays `(prov.)`; the fix is an outdoor illuminance condition in the O3 sessions, which today's factorial does not contain.

## 5. Haptic vocabulary

The DRV2605L is enabled by the AXP2101 **BLDO2** rail — there is no GPIO enable — and the rail policy keeps it off until haptics are needed ([`../hw/twatch-s3-pins.md`](../hw/twatch-s3-pins.md)). Effects come from the part's ROM waveform library ([01 #25](../bibliography/01-datasheets.md)).

| Event | Must feel like | ROM effect | Fires when |
|---|---|---|---|
| Armed | one short pulse | `TBD` | on entering `ARMED` |
| Take started | two pulses, clearly paired | `TBD` | **before** the record window opens (§ guard interval) |
| Take stopped | one long pulse | `TBD` | after the record window closes |
| Take discarded | a distinct rejection pattern | `TBD` | after the window closes |
| Clipping | a repeating tick while clipped | `TBD` | **never during a take** — the clip state is visual only while recording |

Three properties are required of the set, and none of them is a preference:

1. **Distinguishable without looking.** The purpose of the confirmation is that the eyes are elsewhere; a vocabulary that needs the screen to disambiguate it is not a vocabulary.
2. **Never audible-only.** Nothing in this model is confirmed through the MAX98357A; the amp keeps its calibration-tone role ([ADR 0003](../adr/0003-microphone-path.md)) and nothing else. An audio cue is invisible to the deaf/HoH user this design names as first-class (§7).
3. **Outside the take.** A haptic pulse is a mechanical and acoustic event on the same PCB as the measurement microphone. A buzz at the instant a take opens is inside that take. The mitigation is to fire confirmations strictly before the record window opens or after it closes, separated by a **guard interval that has never been measured** — the measurement is a bench task (drive one effect, capture with the mic, find the settling time), and until it is run the guard interval is `TBD`.

Driver note: SensorLib 0.4.1 **does not link** for the DRV2605L — the header resolves but the 46 member definitions live in a `.cpp` outside `SRC_DIRS` ([SensorLib notes](../reference-projects/notes/sensorlib_notes.md) §3). [ADR 0012](../adr/0012-hands-free-interaction.md) decision 7 takes the ≈ 60-line own-driver route over `i2c_master`.

## 6. Timing budget — every row `TBD` by design

| Interval | Meaning | Value | Where the number will come from |
|---|---|---|---|
| `t_live` | INT1 edge → first analyzer frame on the panel | `TBD` | bench (phototransistor rig, GPIO toggle in the ISR) |
| `t_settle` | `LIVE` → `ARMED` | `TBD` | O3 sessions |
| `t_hold` | how long the wrist must stay up before a take may start | `TBD` | O3 sessions |
| `t_holdoff` | wrist drop → auto-disarm | `TBD` | O3 sessions |
| `t_idle` | `LIVE` → `IDLE` with no activity | `TBD` | O3 sessions, then the power budget |
| `t_guard` | haptic pulse → record window may open | `TBD` | bench (mic capture of the pulse) |
| BMA423 init | blob upload + busy-wait, blocking, core 0, before the DSP task | ≈ 350 ms (192 I²C transactions + a 150 ms busy-wait) | measured in the [SensorLib study](../reference-projects/notes/sensorlib_notes.md) |

**This budget is not the latency budget.** The ≤ 80 ms acoustic-to-photon row in [`../validation/README.md`](../validation/README.md) is bounded by what a singer perceives of their own voice ([05 #83–#85](../bibliography/05-papers.md)); those anchors say nothing about how long a *gesture* may take to be acknowledged, and no anchor for that has been found. Do not borrow the 80 ms.

## 7. Accessibility as a design constraint

A real-time visual voice display **is** assistive technology: the speech-training-aid lineage ([05 #75](../bibliography/05-papers.md), Öster 2006) is the same lineage as the singing-studio tools that ground the product premise ([05 #70](../bibliography/05-papers.md), [05 #71](../bibliography/05-papers.md)). That makes the deaf and hard-of-hearing singer a first-class user of this device, not a later audit, and it produces four rules that bind the `ui` component now:

| Rule | Consequence in the model | Source |
|---|---|---|
| No cue is audio-only | every confirmation is haptic **and** visual; the speaker is not in the interaction path at all | [05 #75](../bibliography/05-papers.md) |
| No state is colour-only | `REC` / `ARMED` / clip carry a shape and a word; the spectrogram map is CVD-safe ([ADR 0011](../adr/0011-spectrogram-colormap.md)) | [03 #23](../bibliography/03-standards.md), [03 #24](../bibliography/03-standards.md) |
| Every hands-free gesture has a touch equivalent | reachable between phrases, so limited shoulder range, a prosthesis or a seated arm position never locks a function away | [03 #22](../bibliography/03-standards.md) |
| Voice is never the *only* way to start a take | decision D3 may add voice onset; it may not make it mandatory | [05 #75](../bibliography/05-papers.md) |

The last rule is the reason a spoken keyword is rejected outright rather than deferred — quite apart from CLAUDE.md rule 8 forbidding ESP-SR, a keyword trigger is useless to precisely the user this framing names.

## 8. What is not decided

Four questions belong to the author and are stated in full in [ADR 0012](../adr/0012-hands-free-interaction.md):

- **D1 — the gesture set.** Wrist raise alone; plus double-tap (`BMA423_WAKEUP`); plus the crown (PWRKEY, whose 6 s hold is the PMU power-off). Every extra gesture costs a false-positive rate that must be measured on a wrist.
- **D2 — the timings.** All of §6.
- **D3 — may a take start by voice?** *Never* (deterministic boundary) vs *voice-onset auto-arm* (a detector that **reads** the PCM ring and never gates, ducks or alters it — the instant it touches the audio it violates [ADR 0003](../adr/0003-microphone-path.md) and CLAUDE.md rule 8). A spoken keyword is already excluded. Accessibility argues for onset detection; metrology argues for determinism.
- **D4 — invariant or default?** Whether the state machine *drops* touch above the line, or allows an escape hatch and records a touch-during-take flag.

Engineering questions that are open but are not the author's to decide:

- The BMA423's running current with the feature engine enabled is not yet in the power budget. The **base** figures are now read: `BST-BMA423-DS004-00` rev 2.0 gives **I_DD 150 µA** typ (Performance mode), **14 µA** (Low-power, 50 Hz ODR) and **3.5 µA** (Suspend), at nominal VDD/VDDIO, 25 °C, g_FS 4g. Bosch has delisted its own product page, but the document itself is still freely retrievable (DigiKey's document host answered a 2.6 MB PDF on 2026-08-21) — filing it under `docs/datasheets/bosch/bma423/` and running `doc_ocr` is a D3/D4 acquisition action, not a dead end. What the sheet does **not** give is a feature-engine adder, so the *delta* for wrist-raise still has to be measured on the rail ([`06-power-budget.md`](06-power-budget.md) §2, P5). The ≥ 3 h autonomy claim is not honest until that measurement exists.
- The DRV2605L start-up time out of BLDO2 **has now been read** (datasheet SLOS854D, filed under [`docs/datasheets/ti/drv2605l/`](../datasheets/README.md); §6.5 Electrical Characteristics, §6.7 Switching Characteristics, §8.5.6 Auto Calibration Procedure, §9.3.1 Initialization Procedure). The decision is no longer blocked on a number, only on a preference:

  | | |
  |---|---:|
  | `t(start)`, GO bit or external trigger → output | **0.7 ms** typ — §6.7's MIN and MAX columns are empty |
  | `t(start)`, EN high → output (PWM/analog modes) | **1.5 ms** typ — likewise **no max specified** |
  | I²C accepted after power-up | **≥ 250 µs** (§9.3.1 step 1 — a MIN) |
  | `I(SD)` shutdown, V(EN) = 0 | 4 µA typ / **7 µA max** |
  | `I(standby)` STANDBY = 1 | 4.1 µA typ / **7 µA max** |
  | `I_Q` quiescent, STANDBY = 0, no signal | 0.5 mA typ / **0.65 mA max** |

  On this board BLDO2 *is* the enable — there is no EN GPIO — so "gate the rail" costs a full re-init on every buzz: ≥ 250 µs before the first I²C write, then ≈ 1.5 ms typ to output — a typical, **not** a bound, so a worst-case latency budget cannot be built on it without a bench measurement — **and** the auto-calibration compensation must be restored, because the datasheet says to "repeat the calibration process upon subsequent power ups" or to store the results in host memory and rewrite them (§8.5.6 step 6b). "Leave it on" costs ≤ 7 µA in STANDBY. Against a 470 mAh cell that is ≈ 0.0015 % per hour — i.e. the rail policy is a **latency and complexity** choice, not a battery one. Still [ADR 0012](../adr/0012-hands-free-interaction.md)'s call, now on numbers.
- `t_guard` (§5) needs a bench measurement.

## 9. Interaction with sleep and the anti-brick policy

BMA423 INT1 is a **wake source, never a sleep trigger**. Nothing in this model authorises an unconditional light- or deep-sleep entry: the gate in [ADR 0015](../adr/0015-anti-brick-policy.md) item 5 — uptime ≥ N s **and** no USB host present **and** the development arming flag **and** a timer wake — stands unchanged, and early sleep is one of the documented ways to lose the USB-Serial-JTAG port on a board whose BOOT button is inside the case. Practically: wrist-raise wake is developed and tested with the sleep path **off** and a host attached, and only moves behind the gate once a hardware experiment covers it. A related hazard sits on the touch side, and the board fact behind it is a schematic reading, not a chip-datasheet one — [01 #16](../bibliography/01-datasheets.md) is the FocalTech FT6236/FT6336/FT6436 family spec and cannot say what LilyGO populated. Sheet 4 of [01 #6](../bibliography/01-datasheets.md) (`lilygo_t-watch-s3_schematic_v1.4.pdf`, read 2026-08-21) shows the `T_RST` net reaching the AXP2101's **`EXTEN` = pin 32 `GPIO1/FB5/RTC/LDO2`** through **R41 `0R`, populated**, while the 4K7 pull-up to `AVDD` (R39) and the 1 µF (C65) are both marked `NC`. AXP2101 GPIO1 is **open-drain**, configured by REG `0x1B` bits 3:2 as Hi-Z (POR default) or Low ([01 #17](../bibliography/01-datasheets.md) §6.13.2.17). So touch reset is not absent — it is *assert-only*: the PMU can pull `T_RST` low, and with no pull-up populated the net has **no defined high level** when GPIO1 returns to Hi-Z. Whether the FT6336U supplies an internal pull-up on `RST` is `(prov.)` — unstated in [01 #16](../bibliography/01-datasheets.md) and settled only by a measurement on the pad. The practical rule is unchanged and now better grounded: **use only FT6336U low-power modes recoverable without a reset**, and treat the AXP2101 GPIO1 path as an untested last resort until someone measures the net. (This corrects "`T_RST` is unpopulated" as carried here and in [`../hw/twatch-s3-pins.md`](../hw/twatch-s3-pins.md) — a correction owed to that table.)

## 10. Where this lives in the tree

| Piece | Home |
|---|---|
| Take state machine, glance zones, LVGL chrome | [`ui`](../../firmware/twatch-s3/components/ui/README.md) — hardware-free, so it runs in the simulator |
| BMA423 init, `selectPlatform(WRISTBAND)`, INT1 ISR, C-linkage facade | [`twatch_bsp`](../../firmware/twatch-s3/components/twatch_bsp/README.md) (`src/twatch_imu_bma423.cpp`) |
| DRV2605L driver (≈ 60 lines over `i2c_master`) + BLDO2 sequencing | [`twatch_bsp`](../../firmware/twatch-s3/components/twatch_bsp/README.md) |
| Take boundary, pre-roll length, touch-during-take flag | [`../../protocols/specs/README.md`](../../protocols/specs/README.md) — a record-format contract, so it changes by ADR |
| Interaction metrics | [`../validation/README.md`](../validation/README.md), appended when [ADR 0012](../adr/0012-hands-free-interaction.md) is accepted |

## Background reading

Small-screen and glanceable interaction, the hands-busy gap, the accessibility lineage and the latency anchors are catalogued by claim in [`../bibliography/09-visual-feedback-for-singing.md`](../bibliography/09-visual-feedback-for-singing.md) (sections B, D and E); the human-centred-design, accessibility and anthropometry standards in [`../bibliography/03-standards.md`](../bibliography/03-standards.md) §E; the silicon in [`../bibliography/01-datasheets.md`](../bibliography/01-datasheets.md) (#16 FT6336U, #22 BMA423, #23 Bosch BMA4xx Sensor API, #25 DRV2605L) and [`../bibliography/06-reference-projects.md`](../bibliography/06-reference-projects.md) (#7 SensorLib, #50 the Bosch API upstream, #39 as a read-only UI-layout reference); the driver-level truth in [`../reference-projects/notes/sensorlib_notes.md`](../reference-projects/notes/sensorlib_notes.md) §3 and §4.3.
