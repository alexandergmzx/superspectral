# Uncertainty budget — the instrument for every "± x dB" and "± y cents" in this project

**Status:** skeleton, pre-registered 2026-08-21. The rows exist; the numbers arrive
with Phase 1 ([experiment 0001](experiments/0001-pdm-mic-in-situ-characterization.md))
and the reference-chain decision (roadmap threshold **T6**). It is written *before*
the measurements deliberately: a budget assembled after the fact is a rationalisation.

Structure follows **JCGM 100:2008 (GUM)** — [bibliography 03](../bibliography/03-standards.md),
free from BIPM. The vocabulary used here is GUM's: a *Type A* component is evaluated
from the statistics of repeated observations, a *Type B* component from anything else
(a datasheet tolerance, a calibration certificate, a manufacturer's spec, judgement).
Both are expressed as standard uncertainties `u(x)`, combined in quadrature into
`u_c(y)` through the measurement model's sensitivity coefficients, and reported as an
expanded uncertainty `U = k·u_c` with `k = 2` (≈ 95 % for a roughly normal result) and
the coverage factor stated.

## Why this file exists at all

[`README.md`](README.md) sets `≤ ±1.5 dB` on the 1/3-octave band level and
`≤ ±20 cents` on acoustic-path f0. Those numbers are only meaningful with the
uncertainty of the *reference* attached — and the reference chain the project can
currently afford (a UMIK-1-class measurement mic) has a factory calibration whose own
uncertainty is of the same order as the target. The honest consequences, already
recorded in `README.md` and here made computable:

1. A band-level claim of "±1.5 dB **accuracy**" is not defensible with a
   non-IEC-61094-4 reference. What *is* defensible is **within-session
   repeatability** (Bland–Altman limits of agreement, ICC) plus this budget.
2. Any absolute-SPL readout requires the calibrator's own certificate in the
   budget — otherwise the readout is device-relative and must be labelled as such
   in the UI, which is what [`README.md`](README.md) already commits to
   ("claimed only if a Class-1 calibrator is available, else *not claimed*").
3. A cents claim is dominated by a systematic term nobody thinks about — the
   sample-rate error — which is why it is row 1 below.

## Model A — spectral peak frequency (cents)

Measurand: the frequency of a spectral peak as reported by the watch, compared with
the true frequency of the stimulus.

`f̂ = (f_nom + δ_stim) · (1 + ε_clock + ε_drift) + δ_interp + δ_window`, and the
reported quantity is `y = 1200·log₂(f̂ / f_nom)` cents, where `f_nom` is the
frequency the stimulus is *believed* to have. Every row of the table below is a
term of that equation or a Type-A evaluation of `y` itself — a component with no
term is a component that cannot be combined, which is the usual way a budget
quietly stops being computable.

Two kinds of input therefore appear, and they do **not** share a sensitivity
coefficient:

- **relative** terms (`ε_clock`, `ε_drift`, dimensionless, quoted in ppm):
  `c = ∂y/∂ε = 1200/ln2 ≈ 1731` cents per unit relative error, i.e.
  **1 ppm ≈ 0.0017 cents** — frequency-independent, which is why the
  sample-rate row can be stated once for the whole band;
- **absolute** terms (`δ_stim`, `δ_interp`, `δ_window`, in Hz):
  `c = ∂y/∂δ ≈ 1731 / f_nom` cents per Hz — **frequency-dependent**: 3.93 cents/Hz
  at 440 Hz, 0.216 cents/Hz at 8 kHz. A budget for these rows is evaluated per
  stimulus frequency and never quoted once for the band.

Signs are irrelevant in quadrature; magnitudes are not.

| # | Component | Symbol · unit of `u_i` · `c_i` | Type | Source of the estimate | Distribution | Status |
|---|---|---|---|---|---|---|
| A1 | **Sample-rate error** — the PCM rate differs from nominal | `ε_clock` · relative (ppm) · `1731` | B (then A) | Crystal tolerance + the I²S fractional divider's resolution. **Not APLL**: the ESP32-S3 has none, so the mechanism is the 40 MHz crystal's ppm spec and the divider residue. Measured against a GPSDO/counter in Phase 1 | rectangular → `u = a/√3` | **dominant systematic; must be measured and corrected, then re-entered as the residual** |
| A2 | Peak interpolation | `δ_interp` · Hz · `1731/f_nom` | B | Quadratic interpolation on the log-magnitude; bias depends on window and on the peak's bin offset. Bounded by simulation over the Tier-0 on/off-bin sines | rectangular | from Tier-0 |
| A3 | Stimulus frequency — `f_nom` is not the frequency the source actually produced | `δ_stim` · Hz · `1731/f_nom` | B | Signal generator / soundcard clock spec, or the GPSDO reference | rectangular | small if the reference is disciplined |
| A4 | Frame-to-frame scatter | evaluated on `y` directly · cents · `1` | A | s.d. of the mean over repeated frames of a steady tone; it is the Type-A evaluation of the reported quantity, not a term of the model | normal | from data |
| A5 | Thermal drift — the *residual* clock error moves over the session | `ε_drift` · relative (ppm) · `1731` | A | Re-measure the same tone after a 60-minute soak; a crystal's tempco is a ppm quantity, so drift enters where `ε_clock` does, not as an additive Hz offset | rectangular | Phase 1 |
| A6 | Analysis-window effects on a non-stationary source | `δ_window` · Hz (or cents directly) · `1731/f_nom` (or `1`) | B | Vibrato and the window's time extent interact; applies to *singing*, not to the tone rows. Bounded from the vibrato literature (extent ±0.5–1 semitone at 5.5–7 Hz) | rectangular | Phase 3 only |

`u_c(cents) = √(Σ (c_i·u_i)²)`, `U = 2·u_c`. **A1 and A2 are correlated with nothing
else and dominate**; A6 applies only to the acoustic-path singing rows, never to the
injection path. A3 is exactly zero on the injection path — the WAV *is* the stimulus,
so `f_nom` is exact by construction and only the acoustic path carries that row.

## Model B — 1/3-octave band level (dB)

Measurand: band level reported by the watch minus band level from the reference
chain, in dB, over 100 Hz – 8 kHz.

| # | Component | Type | Source of the estimate | Distribution | Status |
|---|---|---|---|---|---|
| B1 | **Reference-microphone response uncertainty** | B | The factory calibration file's stated uncertainty; for a UMIK-1-class unit this is the term that decides whether "±1.5 dB accuracy" can be claimed at all. An IEC 61094-4 WS2F reference replaces this row and shrinks it (threshold T6) | normal (k from the certificate) | **blocks the accuracy claim** |
| B2 | Calibrator | B | The unit's **own** certificate — for a B&K 4231 the product data states ±0.2 dB ([01](../bibliography/01-datasheets.md) #30) — **plus** the port-adapter coupling loss, which is *not* in any certificate (the watch has no standard coupler) and must be bounded by its own measurement. IEC 60942's per-class tolerances are **not quoted here**: the standard is paid and unacquired ([03](../bibliography/03-standards.md) #6), so the class is recorded as a fact about the instrument and the number comes from the certificate, never from a recalled table | normal + rectangular | needs the adapter |
| B3 | Geometry repeatability | A | Re-mount the watch between runs; s.d. of the band level. The single largest Type-A term for a wrist device | normal | Phase 1 |
| B4 | Room / background | B→A | Background level per band; where it is within 10 dB of the signal it biases the band up — corrected or the band is excluded and said so (ANSI S12.2 room report) | — | measured |
| B5 | Mic-EQ fit residual | A | Residual of the fitted IIR against the measured in-situ response, per band | normal | experiment 0001 |
| B6 | Window/normalisation convention | B | Coherent gain and NENBW must be applied correctly per window; a mistake here is a *bias*, not a scatter. Bounded to ≈0 by the golden-file tests, which is what makes them a metrology instrument and not just a regression suite | — | design-controlled |
| B7 | PDM→PCM decimation filter | B | The S3's hardware decimator's passband ripple is undocumented; measured by swept sine in experiment 0001, entered as a per-band bound (matters above ≈0.4·f_s) | rectangular | open question |
| B8 | Quantisation and mic self-noise | B | Only relevant near the noise floor; enters the soft-phonation rows | — | from EIN |

## Model C — SPR / ring-band ratio (dB)

A **ratio** of two band energies from the same capture, so the terms that are common
to both bands cancel to first order: the reference-mic absolute uncertainty (B1) and
the calibrator (B2) drop out, and what remains is the *slope* uncertainty of the
reference across the two bands, the EQ residual difference (B5 evaluated as a
difference), the geometry term (B3, which does **not** cancel — directivity differs
between 0–2 kHz and 2–4 kHz), and the source-level dependence documented in the
LTAS literature. This is the technical reason the project reports SPR as a
**within-subject, within-session relative** quantity: in that form its budget is
small and honest; as an absolute number it inherits every row of Model B twice.

## Reporting rules

- Every headline number carries `± U (k = 2)` and names which model produced it.
- Type A components state their `n`; a component from `n < 6` observations also
  states the effective degrees of freedom (Welch–Satterthwaite) or is reported as a
  range instead of an uncertainty.
- Systematic terms that are **corrected** (A1 after clock calibration) are reported
  as the residual after correction, and the correction itself is recorded in the
  experiment's provenance table — never silently applied.
- A row whose estimate is "TBD" is printed as TBD in the result table. A budget with
  invisible gaps is worse than no budget.
- The budget is re-derived, not reused, when the reference chain changes (T6), when
  the mic EQ is refitted, or when the sample-rate correction changes.

## What this file is not

It is not a calibration certificate and does not make the watch a measuring
instrument in the IEC 61672 sense — [ADR 0005](../adr/0005-no-clinical-claim.md) (no clinical claim, accepted) and
[`README.md`](README.md) both say the readouts are relative unless a calibrator is in the chain.
It is the discipline that keeps the project's own numbers honest.

**Reference basis:** JCGM 100:2008 (GUM) and JCGM 200 (VIM) — [03](../bibliography/03-standards.md);
IEC 60942 (calibrators), IEC 61094-4 (working standard microphones), IEC 61260-1 /
ANSI S1.11-2004 (band filters) — 03; Bland & Altman 1986 and Koo & Li 2016 (agreement
and reliability, the companions to this budget) — [05](../bibliography/05-papers.md);
Švec & Granqvist 2018 (SPL measurement in voice research) — 05.
