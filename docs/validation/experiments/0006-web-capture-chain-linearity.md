# Host web application: capture-chain linearity per browser and OS

**Date:** 2026-08-22 (pre-registered) · **Status:** planned — owner Alexander (his browsers, his phone, his room). Nothing in this recipe runs on the watch, and no number it produces may be quoted for any bound of [proposal §1](../../proposal/01-super-spectral-proposal.md).

[ADR 0021](../../adr/0021-host-web-application.md) decision 8 states the rule this experiment operationalises: **raw-capture constraints are mandatory and insufficient.** `getUserMedia({audio: {echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1}})` is a *request*; some drivers, OS audio stacks and phone routes process regardless, and `track.getSettings()` reports what the browser *believes*, not what the hardware did. The question here is therefore not "did the browser accept the constraint" — that is one line of JavaScript, and the app already shows it — but **does the chain behave linearly**, which is the property every level, band-ratio and noise-floor readout silently assumes. A single-level measurement cannot see a compressor; two levels 20 dB apart can.

The verdict of this experiment — **unprocessed** or **processed** — is not a pass/fail for the software. It is a label that travels with every acoustic number the web application reports from that browser on that operating system ([`../README.md`](../README.md), *Host web application metrics*).

## What changed / hypothesis

No firmware, no golden set and no tolerance table changes; this experiment reads the browser, not the repository.

**Hypothesis H1 (the digital control arm is exact).** Through the app's **injection mode** — a TypeScript WAV reader feeding the DSP module in a Worker with no audio graph, so no capture chain exists at all — a pair of Tier-0 files 20 dB apart reads a step of **20.00 dB** to within the spectrum row's own tolerance (`atol = 0.01 dB`, [`../golden-files.md`](../golden-files.md)). If this arm is not exact, nothing in the acoustic arm means anything, and the experiment stops here.

**Hypothesis H2 (the acoustic chain is linear).** With the three processing flags read back `false`, a 440 Hz tone reproduced at two amplifier settings **20 dB apart** reads a step of **20 dB within ±0.5 dB** `(prov.)` at the browser's own input, **and** the broadband noise floor measured between bursts does not move with the tone (|Δ floor| ≤ 0.5 dB `(prov.)`). Both conditions must hold: a chain with AGC can reproduce the step while riding the floor, and a chain with noise suppression can hold the floor while compressing the step.

**Hypothesis H3 (the verdict is a property of the browser × OS pair, not of the machine).** Chromium and Firefox on the same laptop, on the same input device, in the same session, give the same verdict. If they do not, the verdict is per browser and the metrics table says so for every figure.

```sh
# from the repo root
# 1. serve the app over HTTPS (phone arm needs it; the laptop arms do not)
uv run --project host spectral-web serve --host 0.0.0.0 --port 8443 \
       --ssl-certfile ~/.local/share/mkcert/lan.pem \
       --ssl-keyfile  ~/.local/share/mkcert/lan-key.pem
# 2. control arm, no capture chain at all: injection mode, two Tier-0 files 20 dB apart
#    datasets/tier0-synthetic/sine_440_0dBFS_32k.wav   and   ..._m20dBFS_32k.wav
# 3. acoustic arm: the SAME -20 dBFS file reproduced at two amplifier settings 20 dB
#    apart, captured live; the app's capture-chain panel writes one JSON per run
#    (getSettings + getCapabilities + the two levels + the two floors) to the
#    data directory of ADR 0021 decision 8.
```

## Provenance

| | |
| --- | --- |
| Inputs | `datasets/tier0-synthetic/sine_440_0dBFS_32k.wav` and `sine_440_m20dBFS_32k.wav` (sha256 from `datasets/tier0-synthetic/manifest.yaml` at the commit named here; `python3 -m synth_signals check` must pass first) |
| Web application | repo commit; `host/web/package-lock.json` sha256; the resolved Node version from `.nvmrc`; the built bundle's sha256 |
| Backend | `uv.lock` sha256; `spectral-web --version`; the served preset sha256 shown in the interface |
| Browsers | full `navigator.userAgent`, the browser's own version string, and — recorded verbatim — `track.getSettings()` **and** `track.getCapabilities()` for the selected input device |
| Operating system | `uname -srm` (laptop) / OS build number (phone); the audio server in use (PipeWire / PulseAudio / CoreAudio / Android AudioFlinger) and its version |
| Input device | device label and `deviceId` group, the OS-level input gain **written down and not touched between arms**, and whether any OS "voice enhancement" toggle exists and is off |
| Instruments | amplifier and reference monitor with the setting used for each level; a reference microphone if one is present (optional here — this experiment measures a *ratio*, not an absolute level) |
| Room | background dB(A) if a sound level meter is available, else a one-line description; the same room for both levels |

## Licensing status

| Artefact | Licence | Status |
| --- | --- | --- |
| Tier-0 synthetic WAVs | Apache-2.0 (generated by `python-scripts/synth_signals/`) | ✅ |
| `host/web/` and `host/src/spectral_host/web/` | GPL-3.0-or-later ([ADR 0004](../../adr/0004-split-licensing.md), [ADR 0021](../../adr/0021-host-web-application.md) decision 4) | ✅ |
| npm dependencies | the permissive allowlist of ADR 0021 decision 4; AGPL forbidden, gate fails closed | ✅ (the gate is the evidence, not this table) |
| Browsers, OS, audio server | vendor terms; used as instruments, never redistributed | ✅ |

**Practical read:** the result may be quoted as "the capture chain of *this browser* on *this OS* with *this input device* was linear (or was not) over a 20 dB step at 440 Hz". It says nothing about the watch, nothing about a different phone, and nothing about absolute level — no calibrator is in this loop. It is the precondition that decides whether the web application's **acoustic** numbers from that pair are reportable at all.

## Scope caveat

This experiment sees one tone at one frequency over one 20 dB step. It cannot see: frequency-dependent processing (a de-esser or a high-pass that is flat at 440 Hz), processing with a time constant longer than the burst (slow AGC that has not yet moved), processing that only engages on speech-like material (a voice-activity-gated suppressor that a steady tone never triggers), or anything at all below the reproduction chain's own distortion. A **unprocessed** verdict is therefore "linear under this test", not "raw" — and the honest place for that sentence is beside every number the verdict travels with.

## Hypothesis / Setup / Pass–fail

- **Setup.** Tier-0 set regenerated and `check`-clean. The app served over HTTPS from the laptop. Per browser × OS pair, in one uninterrupted session, with the OS input gain fixed at the start and never touched: **(a)** the injection control arm on the two Tier-0 files; **(b)** the acoustic arm — the −20 dBFS 440 Hz file reproduced through amplifier + monitor at a comfortable level (call it **L**), then at **L − 20 dB**, five bursts of 3 s at each level, alternating high/low/high/low/… so that drift and a slow AGC separate; **(c)** between bursts, 3 s of silence with the source muted, for the noise floor. Levels are read from the app's own band-limited RMS around 440 Hz; the floor from the broadband RMS excluding a ±50 Hz notch at the tone. The three processing flags are read back from `getSettings()` **before and after** every arm — a browser may change them when the route changes.
- **Repetitions.** 5 bursts per level per arm; the whole arm repeated once after a page reload (a fresh `AudioContext` is a fresh negotiation). Median over bursts; the spread reported, never hidden.
- **Pass H1:** the injection step reads 20.00 dB within the spectrum row's `atol`; the two files' spectra also pass the golden rows. **Fail H1:** stop — the TypeScript level path is wrong and this is a W1 bug, not a browser finding.
- **Pass H2 (verdict *unprocessed*):** median acoustic step within **20 ± 0.5 dB** `(prov.)` **and** |Δ noise floor between tone-present and tone-absent| ≤ 0.5 dB `(prov.)`, with the three flags `false` at both reads.
- **Fail H2 (verdict *processed*):** recorded as a **finding about that browser × OS × device**, not as a defect. Consequence, pre-committed: the pair's row in the *Host web application metrics* block carries **processed**, every acoustic number from it is reported with that word attached, and none of them is used for a comparison against the watch. The injection-path rows are unaffected — they never touched the capture chain.
- **Pass H3:** both browsers agree. **Fail H3:** the verdict is recorded per browser and the metrics block gains a per-browser column; no averaging across browsers, ever.
- **If the flags cannot be set `false` at all** (a phone browser that refuses): that is a *processed* verdict by default, recorded with the exact refusal, and the phone arm of [experiment 0007](0007-web-latency-and-refresh.md) still runs — latency is measurable on a processed chain, linearity is not.

## Gotchas (pre-registered)

- **Chrome AGC trap.** In Chromium, automatic gain control is only reliably off when **`echoCancellation` is also false**: the AEC module and the gain control share a processing graph, and asking for `autoGainControl: false` alone can leave the graph — and its gain — in place. *Signature:* `getSettings()` reports `autoGainControl: false`, and the 20 dB step still reads 12–16 dB. *Pin:* all three flags false in the same constraint object, and both `getSettings()` and `getCapabilities()` recorded — capabilities show whether the browser could have honoured the request at all.
- **Driver-processes-anyway trap.** Some laptop audio drivers and OS "voice clarity" features process below the browser, where no constraint reaches. *Signature:* Chromium and Firefox agree with each other and both disagree with the amplifier — the step is short by the same amount in both. *Pin:* this is exactly what H3 is for; record the audio server and any OS enhancement toggle in Provenance, and re-run with it toggled if one exists.
- **Phone route-switch trap.** A phone may switch input route mid-session (speakerphone ↔ earpiece ↔ headset, or a notification grabbing the mic) and come back with a **different sample rate** and different processing. *Signature:* the second half of an arm disagrees with the first, and `AudioContext.sampleRate` or `getSettings().sampleRate` has changed since the first read. *Pin:* read the flags and the rate before *and* after every arm; a change invalidates the arm rather than being averaged into it — and the sample-rate assertion of [ADR 0021](../../adr/0021-host-web-application.md) decision 7(c) refuses to start on a mismatch in the first place.
- **Reproduction-chain trap.** A 20 dB step at the amplifier is not a 20 dB step at the microphone unless the amplifier is linear over that range and the monitor is not compressing. *Signature:* every browser on every OS reports the same wrong step. *Pin:* verify the step once with a reference microphone or a sound level meter before believing any browser; if neither is available, say so — the experiment then bounds *relative* browser behaviour only, which is still the question it was written to answer.
- **Gain-touched trap (cost: the whole session).** Changing the OS input slider between the two levels destroys the measurement and looks exactly like a linear chain. *Signature:* a suspiciously perfect 20.0 dB step on a chain whose flags could not be set. *Pin:* the gain is written into Provenance at the start of the session and read again at the end; if the two differ, the session is discarded.
