# Acoustic port, case and gasket

The microphone's **in-situ** response — through the port hole, the channel behind it, any mesh or vent membrane, the gasket and the cavity in front of the MEMS element — is what the watch actually measures. None of it is documented by LilyGO. This is the largest hardware-documentation gap in the project, above the undocumented speaker transducer: the speaker bounds an optional calibration-tone feature; the port bounds the project's headline measurement.

## Why it outranks everything else on the hardware list

- Every acoustic-path metric in the research question (f0 on the acoustic path, band energies, the ring/twang readout, absolute SPL) is measured **through** this geometry. A port resonance or a vent-membrane insertion loss that lands in 2.5–5 kHz is a systematic bias inside exactly the bands the tool reports.
- The mic-EQ fit ([`../../dsp/design/`](../../dsp/design/) `mic-eq.md`) is a fit of *this* geometry plus the MEMS element's own free-field response. Without the geometry, the EQ cannot be separated into a per-part-number term and a per-unit term — which decides whether a second watch needs its own calibration (an open question routed in the roadmap).
- The Knowles datasheet's free-field curve (a raster image; to be digitized) says nothing about the cased response; the only honest statement today is "unknown until measured".
- A Helmholtz estimate from the geometry predicts whether a resonance is *likely* in the band of interest before the first measurement — turning an "unanswerable empirical question" into a partly calculable one.

## Planned teardown measurements (one teardown, shared with the battery-pigtail work)

Recorded here as `teardown-<date>_notes.md` with photos under `images/`, and summarised as a drawing; part numbers go to the BOM spares row.

| Measurement | Symbol | Method | Feeds |
|---|---|---|---|
| Port hole diameter and count | d, n | calipers / photo with scale | Helmholtz neck area; AN-1003 minimum-port rule (≥ 0.25 mm) |
| Port channel length (case wall + any spacer) | L | calipers / depth gauge | Helmholtz neck length (+ end correction ≈ 0.85·d per open end) |
| Front cavity volume between port and MEMS inlet | V | from the measured cavity dimensions; gasket thickness | Helmholtz resonance estimate |
| Gasket material, thickness, compression; whether it seals the mic to the case | — | visual + calipers | leak path ⇒ low-frequency roll-off and a second resonance |
| Mesh / vent membrane present? (type, supplier marking) | — | visual | insertion loss: acoustic vents are typically 0.4–4 dB, frequency-dependent (GORE portfolio datasheet) |
| Mic orientation (top-port SPM1423: port on the package top) and PCB hole alignment to the case hole | — | visual | misalignment ⇒ effective smaller port |
| Distance and path from case hole to the wearer's mouth on the wrist | — | from the wrist-position envelope experiment | geometry term of the validation matrix |
| Back-cover screw head type, gasket part, battery connector | — | visual | BOM spares row; brick runbook last step |

## Helmholtz estimate (placeholder — filled from the teardown)

For a single port of area `A = n·π·(d/2)²`, effective neck length `L' = L + end corrections`, and front-cavity volume `V`, with `c ≈ 343 m/s`:

```
f_H = (c / 2π) · sqrt( A / (V · L') )

d  = TBD mm   n = TBD   L = TBD mm   V = TBD mm³   ⇒   f_H = TBD Hz   (prov.)
```

What the number is for: if `f_H` lands inside 2–5 kHz, the port resonance is a first-order term in the mic EQ and the uncorrected ring/twang readout is biased by design; if it lands well above 8 kHz, the EQ is dominated by the MEMS element's own curve. Either way the estimate is checked against the swept-sine measurement of experiment 0001 (`docs/validation/experiments/`), not trusted on its own. No number is written here until `d`, `L` and `V` are measured.

## Sources

Catalogued in [`../../docs/bibliography/02-application-notes.md`](../../docs/bibliography/02-application-notes.md) (TDK/InvenSense AN-1003 *Recommendations for Mounting and Connecting InvenSense MEMS Microphones* and AN-100 handling guide; Knowles mic selection guide; Infineon *PCB and housing design for MEMS microphones*; GORE acoustic-vent portfolio datasheet) and [`01-datasheets.md`](../../docs/bibliography/01-datasheets.md) (Knowles SPM1423HM4H-B, T-Watch S3 schematics). Measurement method: exponential swept sine per Farina 2000 ([`05-papers.md`](../../docs/bibliography/05-papers.md)); admissibility criteria for the microphone per Švec & Granqvist 2010 ([`08-voice-metrology-on-the-wrist.md`](../../docs/bibliography/08-voice-metrology-on-the-wrist.md)).
