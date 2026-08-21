# Microphone path: PDM mic in-situ characterization through the watch case

**Date:** 2026-08-20 (pre-registered) · **Status:** planned — runs in Phase 1 (weeks 4–7), after E2; it is the experiment that decides roadmap threshold **T2** (host-first pivot) and **T3** (48 kHz vs 32 kHz cap), and it produces the two artefacts every later number depends on: **the mic EQ filter and the measured noise floor**.

## What changed / hypothesis

No analysis feature is involved: the firmware under test is the bare capture path — `driver/i2s_pdm.h` on I2S0 (CLK GPIO44, DATA GPIO47, 16-bit slots), raw PCM streamed over USB-Serial-JTAG to the host and written to WAV — nothing else. The hypothesis is about the **hardware**, not the algorithm.

```sh
# firmware: sdkconfig.ci.analyzer with CONFIG_SPECTRAL_AUDIO_SOURCE_PDM_MIC=y, no DSP, no display
idf.py -p /dev/ttyTWATCH flash
python3 python-scripts/capture/capture.py --port /dev/ttyTWATCH --rate 32000 --seconds 30 --out datasets/phase1/mic/<condition>.wav   # script written in D6; all Python lives under python-scripts/
```

## Provenance

| | |
| --- | --- |
| Inputs | Farina exponential sweep 20 Hz–20 kHz, 10 s, −12 dBFS (sha256 TBD); pink noise 60 s (TBD); 1 kHz calibrator tone 94.0 / 114.0 dB SPL |
| Firmware | commit TBD; capture-only build, `CONFIG_SPECTRAL_BOOT_GUARD_MS=3000`, DC removal **off** (raw PCM is the point) |
| ESP-IDF | `v6.0.2` @ SHA from `env.lock.md` |
| Instruments | reference mic (UMIK-1 s/n TBD with factory cal file, or IEC 61094-4 WS2F class — the class is recorded, see threshold T6); B&K 4231 or Class-2 calibrator s/n TBD; soundcard/monitor TBD; room background measured and recorded |
| Device | T-Watch S3 unit s/n / MAC TBD; schematic revision (V1.4 or 2025-03-24) recorded; `docs/hw/efuse-baseline.json` sha256 |

## Licensing status

| Artefact | Licence | Status |
| --- | --- | --- |
| Tier-0 synthetic signals (generated in-repo) | Apache-2.0 (repo) | ✅ |
| Knowles SPM1423HM4H-B datasheet figures (digitized CSV for the baseline arm) | vendor-published, redistribution unknown | ⚠️ cite, do not redistribute the PDF; the digitized CSV carries its provenance block |
| UMIK-1 factory calibration file | per-serial, miniDSP terms | ⚠️ private to the unit; hash recorded |

**Practical read:** the result is bench evidence for a design decision (EQ or pivot) and a Phase-1 deliverable; it is **not** a claim about the microphone part in general (one unit, one case, one revision) and it is not a calibration of a second watch (open question Q38: per-unit vs per-part-number EQ).

## Scope caveat

A swept sine through a mouth simulator or monitor at a fixed geometry measures the **transfer function of case + port + gasket + microphone + PDM→PCM decimation filter** along one axis. It does not measure wind/motion noise from arm movement, sleeve occlusion during singing, or body-conducted sound — those belong to the Phase-3 wrist-position envelope. It also cannot separate the case resonance from the mic's own response without a second measurement of a bare mic, which this board does not permit; the datasheet curve is the only "bare" reference and it is a raster image until digitized (D3).

## Hypothesis / Setup / Pass–fail

- **Hypothesis (prov.):** through the sealed case on a wrist-like mount at 30 cm / 45° from the source, the in-situ magnitude response from 100 Hz to 8 kHz lies within a **±6 dB (prov.)** envelope that a minimum-phase IIR of order ≤ 8 can flatten to **±1.5 dB**; no resonance exceeds **+6 dB** inside 2.5–5 kHz (the ring/twang band); A-weighted EIN ≤ **35 dB(A) SPL**; capture at **48 kHz / `DSR_8S` (3.072 MHz PDM clock)** is clean (no dropouts, no spurs, noise floor within 1 dB of the 32 kHz / 2.048 MHz capture); the raw-PCM DC offset is bounded and stable.
- **Setup:**
  1. Room background recorded with the reference mic (target ≤ 25 dB(A); else the room is reported per ANSI S12.2 and the EIN row becomes an upper bound — threshold T8).
  2. Geometry per ITU-T P.51 mouth simulator if available, else a reference monitor; watch on a wrist-shaped mount (forearm phantom or the experimenter's wrist, stated) at 15 / 30 / 45 cm and 0° / 45° / 90° relative to the source axis; reference mic co-located at the watch face, 2 cm off-axis.
  3. Signals: Farina sweep ×5 per condition (averaged IR); pink noise 60 s (1/3-octave levels vs reference); calibrator tone at 94.0 dB SPL through the port adapter (absolute sensitivity in dBFS per dB SPL); silence 30 s (EIN).
  4. Capture at 32 kHz / `DSR_8S` **and** 48 kHz / `DSR_8S`, both slot masks tried first (H7: the wrong mask captures silence and looks like a dead mic).
  5. Analysis on the host: deconvolve the sweep (Farina), divide by the reference-mic response, smooth to 1/12 octave; fit the EQ; compute EIN A-weighted; report raw-PCM mean and RMS per condition.
  6. **Baseline arm:** the digitized Knowles free-field curve and the datasheet SNR-derived EIN (≈ 32.5 dB(A)) — the headline is the in-situ deviation from these.
- **Pass:** all five hypothesis clauses hold → commit the EQ coefficients to the preset schema's mic-EQ slot (ADR 0010), record the LF corner and the DC offset in ADR 0003, mark 48 kHz as available.
- **Fail, clause by clause:** envelope or resonance fails → **T2 host-first pivot** is executed (ADR 0002 amendment; timbre metrics move to host-offline); EIN fails → the softest-phonation claim is dropped and the RQ's acoustic bound is re-derived; 3.072 MHz fails → **T3: cap at 32 kHz** (ADR 0003, ADR 0010); DC offset unstable → the software HPF corner is raised and recorded.
- **Repetitions:** each condition ×5 sweeps, 2 sessions on different days; report median and range, not means.

## Evaluation

*(to be filled when the experiment runs; tables keyed by `distance × angle × rate`, headline = max deviation from flat after EQ in 2.5–5 kHz)*

### Baseline (datasheet curve, digitized)

*(to be filled)*

### Wire-path smoke test

Calibrator tone at 94.0 dB SPL → watch capture → host WAV → FFT peak within 3 cents of 1000 Hz after the sample-rate correction; the same file replayed through `file_blob` on the device reproduces the host spectrum within the [golden-file tolerances](../golden-files.md).

## Interpretation and follow-up

*(to be filled)* — at minimum: whether the EQ is per-unit or per-part-number (Q38) cannot be decided from one unit; a second unit or a second board revision is the follow-up.
