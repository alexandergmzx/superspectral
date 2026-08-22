# Host web application: microphone-to-pixel latency and sustained refresh

**Date:** 2026-08-22 (pre-registered) · **Status:** planned — owner Alexander; needs **the same phototransistor rig as the watch's acoustic-to-photon latency row** (oscilloscope, ch1 = drive signal, ch2 = phototransistor on the screen). Nothing in this recipe runs on the watch.

Read this first, because it is the whole point of the experiment's shape: **these numbers are measured, never claimed.** [ADR 0021](../../adr/0021-host-web-application.md) decision 3 says so, the *Host web application metrics* block of [`../README.md`](../README.md) carries `measured, no claim` in the target cell of both rows, and neither row has an external anchor — deliberately, because a browser's audio graph, compositor and display pipeline are not this project's design. The watch's **≤ 80 ms** acoustic-to-photon bound and its per-preset refresh targets belong to [proposal §1](../../proposal/01-super-spectral-proposal.md) and are properties of the firmware alone. The results of this experiment are reported **beside** that row, never inside it, and no figure produced here may be quoted for any research-question bound.

What the experiment is *for*, then: knowing whether the browser analyzer is usable as a rehearsal-room instrument at all, and on which machine — and having the number written down instead of guessed at, so that a future decision (move f0 server-side; drop a preset's refresh in the browser; prefer one browser in the setup guide) is taken against a measurement.

## What changed / hypothesis

No firmware and no golden set changes.

**Hypothesis H1 (the reported latencies are incomplete).** `AudioContext.baseLatency + AudioContext.outputLatency` under-reports the true microphone-to-pixel delay, because it accounts for the audio graph and not for the worker hop, the canvas draw, the compositor or the panel. Prediction: the phototransistor number exceeds the reported sum by a margin that is **not constant across browsers**. The reported values are recorded in every run — they are cheap, they are useful for attributing a change, and they are **not trusted alone**.

**Hypothesis H2 (refresh is preset-bound, not machine-bound, until it is not).** For the presets whose hop admits it, achieved waterfall columns per second track the preset's analysis hop; the first thing to break as load rises is **dropped columns**, not the frame rate — the page keeps compositing while the worker falls behind. Prediction: dropped columns rise before achieved columns fall, so a frame-rate counter alone would report health while data is being lost.

**Hypothesis H3 (the phone is a different instrument).** The phone's numbers differ from the laptop's by more than the two laptop browsers differ from each other. Consequence either way: the table is reported **per browser × OS × device**, never averaged.

```sh
# from the repo root
# 1. serve over HTTPS so the phone arm can run at all (mkcert; ADR 0021 decision 8)
uv run --project host spectral-web serve --host 0.0.0.0 --port 8443 \
       --ssl-certfile ~/.local/share/mkcert/lan.pem \
       --ssl-keyfile  ~/.local/share/mkcert/lan-key.pem
# 2. latency arm: the same rig as the watch's row -- signal generator drives the
#    monitor (ch1) and a phototransistor is taped over the region of the canvas
#    that a 1 kHz burst lights up (ch2). 100 bursts per preset per browser.
# 3. refresh arm: the app's own counters over 60 s per preset -- columns drawn
#    (page) and columns dropped (worker) -- written to one JSON per run in the
#    data directory of ADR 0021 decision 8, alongside baseLatency/outputLatency.
```

## Provenance

| | |
| --- | --- |
| Inputs | `datasets/tier0-synthetic/sine_1000_m20dBFS_32k.wav` for the burst source (sha256 from `datasets/tier0-synthetic/manifest.yaml`); the six presets, sha256 as served |
| Web application | repo commit; `host/web/package-lock.json` sha256; Node version from `.nvmrc`; built-bundle sha256; **whether the build is the production bundle or the dev server** — they are not the same instrument |
| Backend | `uv.lock` sha256; `spectral-web --version` |
| Browsers | full `navigator.userAgent`; `AudioContext.baseLatency` and `outputLatency` at the start of each run; `track.getSettings()` |
| Devices | laptop model, CPU, GPU and whether WebGL is hardware-accelerated (`WEBGL_debug_renderer_info`, recorded — a software rasteriser is a different experiment); phone model and OS build |
| Display | panel refresh rate as reported by the OS and as measured (`requestAnimationFrame` deltas over 5 s); external monitor or internal panel; any compositor VSync setting |
| Instruments | oscilloscope model + s/n, phototransistor part, the exact screen region it covers; signal generator / soundcard with its stated clock accuracy |
| Load state | what else was running; power profile / battery vs mains (a laptop on battery throttles, and that is a finding, not a nuisance) |

## Licensing status

| Artefact | Licence | Status |
| --- | --- | --- |
| Tier-0 synthetic WAV | Apache-2.0 (`python-scripts/synth_signals/`) | ✅ |
| `host/web/` and `host/src/spectral_host/web/` | GPL-3.0-or-later ([ADR 0004](../../adr/0004-split-licensing.md)) | ✅ |
| Browsers, OS, GPU drivers | vendor terms; instruments, never redistributed | ✅ |

**Practical read:** the numbers may be quoted as "*this* build of the web application, in *this* browser on *this* machine, took N ms from acoustic onset to first pixel change, and sustained M columns per second on preset P". They may **not** be compared with the watch's ≤ 80 ms bound, folded into it, or used to argue anything about the firmware — different device, different display, different pipeline, and a bound the web application was never held to ([ADR 0021](../../adr/0021-host-web-application.md) decision 3).

## Scope caveat

The rig sees photons leaving one region of one screen. It cannot separate the contributions inside the chain — capture buffer, worklet hop, worker transform, canvas draw, compositor, panel scan-out — and a change in any of them moves one number. It cannot see what the user perceives (a jittery 50 Hz reads worse than a steady 30 Hz, and neither counter says so). It cannot see the phone's behaviour under a real rehearsal-room thermal load unless the phone is actually hot when measured. And it measures *this* build: a dev-server build with a source map and no minification is a different instrument from the production bundle, which is why Provenance records which one ran.

## Hypothesis / Setup / Pass–fail

- **Setup.** Production bundle served over HTTPS. Per browser × OS × device, per preset: the phototransistor taped over the canvas region the burst lights, the oscilloscope triggered on ch1, **100 bursts** with randomised inter-burst intervals (a fixed interval can phase-lock to the frame clock and quietly measure the frame period instead of the latency). Then the refresh arm: 60 s of continuous capture per preset with the counters running, once on mains and once on battery for the laptop, once cool and once after 10 minutes of continuous use for the phone.
- **Reported per run, always together:** median and p99 of the ch1→ch2 delay; achieved columns/s (median over 1 s windows) and dropped columns (absolute count and % of expected); `baseLatency` and `outputLatency`; the measured display refresh; the preset id and its analysis hop.
- **There is no pass and no fail.** Both rows read *measured, no claim*, so the acceptance criterion is on the **reporting**, not on the number: a run is complete when every cell of the Provenance table is filled, the three quantities above are present for every preset, and the result is filed per browser × OS × device with no averaging across them.
- **What the numbers may change (pre-committed).** If browser f0 cannot hold the founding document's 50 Hz on the owner's phone, that is the founding document's own pre-registered threshold and the [ADR 0021](../../adr/0021-host-web-application.md) revisit trigger: **f0 alone moves server-side**, and its golden row is annotated with the date and the measurement that moved it. If dropped columns exceed achieved columns on a preset, that preset is marked *not usable live in this browser* in the interface — a fact shown to the user, not a target quietly lowered.
- **What they may never change:** the watch's ≤ 80 ms row, its per-preset refresh targets, and any wording of the research question.

## Gotchas (pre-registered)

- **`baseLatency` + `outputLatency` trap (the reason this experiment exists).** Both are *estimates the browser reports about its own audio graph*; neither includes the worker hop, the draw, the compositor or the panel, and `outputLatency` is about **output**, which a capture-to-pixel path does not even traverse. *Signature:* a confident sub-20 ms figure in the console and a 60–100 ms trace on the scope. *Pin:* record them, never quote them alone; the phototransistor is the measurement.
- **Frame-lock trap.** Bursts at a fixed interval can phase-lock to `requestAnimationFrame`, so every measurement lands at the same point in the frame and the spread collapses to zero. *Signature:* a p99 suspiciously equal to the median, and a median suspiciously close to a multiple of the frame period. *Pin:* randomise the inter-burst interval; report the spread, and be suspicious of a small one.
- **Counter-lies trap.** A frames-per-second counter driven by `requestAnimationFrame` reports the *compositor*, which keeps running when the analysis worker falls behind: the waterfall scrolls smoothly while showing stale or skipped columns. *Signature:* 60 fps reported, and a spectrogram whose event timing does not match the audio. *Pin:* count **columns actually drawn** in the page and **columns dropped** in the worker, and report both — the pair, never either alone. This is the browser twin of the watch's rule that a firmware frame counter is cross-checked with a phototransistor on a blinking corner ([`../README.md`](../README.md), sustained-refresh row).
- **Software-rasteriser trap.** A browser that falls back to a software WebGL implementation renders the waterfall an order of magnitude slower, and nothing in the interface says so. *Signature:* one browser on the same machine is dramatically worse on the refresh arm only. *Pin:* `WEBGL_debug_renderer_info` recorded in Provenance for every run.
- **Thermal and power trap.** A laptop on battery and a phone after ten minutes of continuous WebGL are different machines from the ones that ran the first minute. *Signature:* the numbers degrade monotonically through the session. *Pin:* the cool/warm and mains/battery arms are part of the setup, not a re-run when the result looks odd.
- **Screen-region trap.** Taping the phototransistor over a region the burst does not light — or over one that a smoothing setting fades in slowly — measures the smoothing constant, not the latency. *Signature:* a latency that changes when `analysis.smoothing` changes. *Pin:* record the region and set smoothing to 0 for the latency arm; smoothing is the weight of the previous frame ([ADR 0021](../../adr/0021-host-web-application.md) decision 7(d)), so a non-zero value is a deliberate delay.
