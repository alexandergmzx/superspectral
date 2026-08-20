# Architecture & Build Guide: A Preset-Driven Singing-Voice Spectral Analyzer for Linux

## TL;DR
- **Build a Python-orchestrated app with a hard architectural seam between a swappable "DSP core" and everything else, and split the two paths by physics: do the real-time spectrum/spectrogram entirely in the browser (getUserMedia + AudioWorklet, WASM later), and do the heavy offline vocal analysis (formants, f0, H1–H2, ring ratio, stem comparison) in a Python/FastAPI backend using parselmouth + librosa.** This gives you the "open it from your phone" property for free on the live path and keeps the accurate, non-real-time science in Python where the mature libraries live.
- **Your six Spectroid presets map 1:1 onto JSON preset files** (FFT size, window, hop/interval, smoothing, decimations), so the app stays preset-driven, not knob-heavy — and the presets are literally the same DSP parameters you already understand.
- **Do NOT rewrite DSP in C/C++/Rust yet.** NumPy/scipy FFT is already compiled C; the realistic hot loops (feature/glue loops, multi-resolution cascade) should be *profiled first* and only ported (PyO3+maturin or Cython) if a benchmark demands it. Friture — the closest prior-art app — is pure Python + NumPy rfft with only four small Cython modules, and it hits 50+ Hz displays fine.

## Key Findings

**The closest existing app to what you want is Friture, and it validates your whole plan.** Friture is a real-time audio analyzer (spectrum, 2D spectrogram, octave analyzer) written in Python, GPLv3, by Timothée Lecomte. It captures audio through PortAudio via `sounddevice` (plus `rtmixer` for allocation-free callbacks), computes its FFT with NumPy `rfft` + a Hann window, and has migrated its rendering to PyQt5 + QML on the GPU (it dropped its old PyOpenGL dependency). Critically for your "port later" question: Friture is *not* mostly C. It ships exactly four Cython `.pyx` hot-loop modules in a `friture_extensions/` package — `exp_smoothing_conv` (exponential smoothing), `lfilter` (IIR filter), `lookup_table`, and `linear_interp` — and leaves everything else in Python/NumPy. That is the exact "profile, then port only the proven-hot loops" discipline you should copy.

**Friture also already implements Spectroid's "decimations."** Its fraction-of-octave analyzer (1/1, 1/3, 1/6, 1/12, 1/24 bands/octave) uses a cascaded-decimation elliptic-IIR filter bank: a low-pass decimation filter halves the sample rate per octave and the band-pass filters are re-applied at each decimated rate. That is precisely the multi-rate scheme Spectroid calls "decimations" (finer resolution at low frequencies, at the cost of time resolution there). Note a useful nuance: Friture's *FFT/spectrogram* path once had a separate crude decimation and its maintainer **removed** it because a naive mean isn't a good enough anti-aliasing low-pass — the lesson being that if you replicate Spectroid's decimation on the FFT path, you must use a real low-pass filter, not decimate-by-averaging.

**For voice-specific science, parselmouth (Praat-in-Python) is the spine.** It directly wraps Praat's C/C++ code so its formant (Burg/LPC), pitch (autocorrelation), intensity, harmonicity, and spectrogram outputs are numerically identical to Praat. This is your source of truth for formants and for golden-file tests. It is GPLv3 (it embeds Praat, which is GPLv3+), which has real licensing consequences (below).

**The singer's-formant / "ring" region you care about (2.5–3.5 kHz) is a well-established, measurable target.** Johan Sundberg (KTH Stockholm) described the singer's formant in 1974 as formants F3, F4 and F5 "clustered in a wide band around 3 kHz," where the orchestra has little energy; its center frequency varies by voice type — per Sundberg (2001), roughly 2,420 Hz for basses, 2,550 Hz baritones, 2,840 Hz tenors, ~3,000 Hz contraltos, while sopranos typically form no pronounced cluster in their upper range and use formant tuning instead. It shows up clearly on a Long-Term Average Spectrum (LTAS) and is commonly quantified by the Singing Power Ratio (SPR) read from LTAS. Several browser tools already visualize a "ring band" at 2.5–4 kHz and a "twang band" at 3.5–5 kHz with live F1/F2 overlays — proof your feature set is buildable and useful.

**For source separation, use Demucs locally instead of depending on Moises.** Demucs (Meta, htdemucs / htdemucs_ft) is MIT-licensed, runs locally, is `pip install demucs`, has a Python API (`apply_model`), and a `--two-stems=vocals` karaoke mode; its fine-tuned htdemucs_ft model reaches 9.20 dB SDR on MUSDB HQ (SOTA-class among public models, per Rouard, Massa & Défossez, "Hybrid Transformers for Music Source Separation," ICASSP 2023). Ultimate Vocal Remover (UVR) is a GUI front-end over the same models. This lets your offline "compare against the isolated vocal stem" feature run entirely on your machine.

## Details

### A. Prior art (fork/learn/borrow)

| Project | What it is | What to take | License |
|---|---|---|---|
| **Friture** (tlecomte/friture) | Python real-time analyzer: spectrum, 2D spectrogram, octave, generators | Overall architecture; NumPy rfft path; Cython hot-loop pattern; cascaded-decimation octave filter bank; sounddevice+rtmixer capture | GPLv3 |
| **parselmouth** (YannickJadoul/Parselmouth) | Pythonic bindings to Praat internals | Formants (Burg/LPC), pitch, intensity, harmonicity, spectrogram; golden reference | GPLv3 |
| **Praat** | The reference voice-analysis app | Algorithm definitions; validation target | GPLv3+ |
| **librosa** | MIR toolkit | `pyin` f0, VQT/CQT, `sequence.dtw` alignment, LTAS building blocks, `set_fftlib` (swap in pyFFTW) | ISC (permissive) |
| **CREPE** (marl/crepe) | CNN pitch tracker, state-of-the-art 2018 | Optional high-accuracy offline f0; note TensorFlow dependency | MIT |
| **aubio** | Clean C pitch/onset library (YIN etc.) | Reference implementations; fast pitch/onset | GPLv3 |
| **TarsosDSP** | Java DSP teaching library: YIN, MPM/McLeod, AMDF | Algorithm reference (YIN, MPM), synthetic-signal test ideas | GPLv3 |
| **Sonic Visualiser + Vamp** | Feature-extraction app with out-of-process plugin model (Piper/Cap'n Proto) | Plugin-isolation architecture idea; batch analysis via sonic-annotator | GPLv2+ |
| **audioMotion-analyzer** | High-res dependency-free JS spectrum analyzer (Web Audio) | Front-end spectrum rendering reference | AGPLv3 |
| **WebAudioSpectrum** (deftio) | Pure-JS mic spectrum + spectrogram | Minimal AnalyserNode + Canvas starting point | MIT (verify) |
| **Chrome/voice-science/PhonaLab spectrograms** | Browser voice spectrograms with ring/twang bands, F1/F2 overlays | UX/feature model for your live vocal presets | proprietary (inspiration only) |
| **Demucs** (facebookresearch/demucs) | Local neural stem separation (htdemucs) | Local vocal-stem extraction to replace Moises | MIT |
| **Ultimate Vocal Remover (UVR)** | GUI over Demucs/MDX models | UX reference for stem step | MIT |

**Pitch algorithms, honestly compared.** pYIN (librosa `pyin`) is a robust probabilistic autocorrelation tracker and is the pragmatic default: pure-Python-stack, no GPU, good on clean monophonic vocals — it exploits temporal smoothness via an HMM, which helps stability. CREPE is more accurate (over 90% raw pitch accuracy within a 10-cent threshold on MDB-stem-synth, ~100% on RWC-synth per Kim, Salamon, Li & Bello, ICASSP 2018, arXiv:1802.06182) and beat pYIN and SWIPE across noise conditions except low-frequency brown noise — but it pulls in TensorFlow, is heavier, and (unlike pYIN) estimates each frame independently with no temporal tracking, so raw CREPE output can jitter. Keep CREPE as an optional "high accuracy" offline backend. Praat/parselmouth pitch (autocorrelation) is your validation reference. For the live path, the browser's own AnalyserNode gives you a spectrum immediately, but for live f0 you'll want a lightweight YIN/MPM in an AudioWorklet (later WASM) — this is exactly the Rust-in-WASM pitch-detector pattern the Toptal tutorial demonstrates.

### B. Architecture recommendation (opinionated)

**Split by physics, not by convenience:**

```
        ┌───────────────────────── BROWSER (phone or laptop) ─────────────────────────┐
        │  LIVE PATH (low latency, 50 Hz)          OFFLINE PATH (upload/record)         │
        │  getUserMedia{echoCancellation:false,    file  ──►  POST /analyze             │
        │   noiseSuppression:false,                              │                       │
        │   autoGainControl:false}                               │ results (JSON+PNG)    │
        │        │                                               ▼                       │
        │   AudioWorklet ── ring buffer ── FFT (WASM/JS) ── features                    │
        │        │                                        │                              │
        │   WebGL waterfall  +  Canvas2D spectrum  ◄───────┘  overlays (f0/F1/F2/ring)   │
        └───────────────▲───────────────────────────────────────────▲──────────────────┘
                        │ (optional) binary WS frames                 │ HTTPS/WSS
        ┌───────────────┴─────────────────────────────────────────────┴────────────────┐
        │                      PYTHON BACKEND (FastAPI + uvicorn)                        │
        │  /presets (JSON)   /analyze (parselmouth+librosa)   /separate (Demucs)         │
        │                                                                                │
        │   ┌──────────────── DSP CORE (stable interface) ────────────────┐             │
        │   │  spectrum(frame,preset) · f0(sig) · formants(sig) · h1h2 ·   │             │
        │   │  ring_ratio · ltas · dtw_align   ── NumPy/scipy today,       │             │
        │   │                                     C/Rust later behind SAME │             │
        │   │                                     function signatures      │             │
        │   └──────────────────────────────────────────────────────────────┘           │
        └────────────────────────────────────────────────────────────────────────────────┘
```

**Why browser-first for live.** A pure-browser real-time path (getUserMedia → AudioWorklet → WASM) is genuinely the better engineering choice for *your* live requirement, and it gives "open it from a phone on the LAN" essentially for free. Round-tripping raw mic audio to a Python server over WebSocket at 50 Hz adds latency and a serialization tax for no analytical benefit — the FFT is trivial and the browser already exposes it via AnalyserNode. Reserve the Python backend for what browsers can't do well: parselmouth/Praat formants, Demucs separation, DTW alignment, LTAS over whole takes. Mozilla's own AudioWorklet writeup confirms pro-audio DSP compiled to WASM runs on the real-time audio thread and is the intended path for heavy in-browser processing.

**When you'd still stream to Python.** If you decide you want the *exact same* DSP core producing both live and offline results (single source of truth, easier golden-file testing), then stream audio to the backend and push binary Float32 frames back over WebSocket to a Canvas/WebGL renderer (the FastAPI+WebSocket+Canvas pattern is well-trodden; e.g. Honghe/demo_fastapi_websocket, which also notes you need HTTPS to use getUserMedia cross-host). Be honest about the tradeoff: you gain consistency, you lose latency and the trivial phone-deploy story. Recommended: browser-first live, Python offline, and share *algorithms* by keeping the math identical (same window, same normalization) rather than sharing the *process*.

**Audio capture on Linux (2026).** PipeWire is the default on current mainstream distros and exposes both PulseAudio and JACK APIs, so you rarely talk to ALSA directly. Use **python-sounddevice** (PortAudio, CFFI) — it's what Friture uses, its callback runs in C without the GIL, and PortAudio 19.7.x fixed earlier PipeWire crashes. Open an input-only callback stream, keep the callback allocation-free (no Python object churn, no file/network I/O — the sounddevice docs explicitly warn against extensive computation, waiting on threads, or I/O in the callback), and hand samples to a lock-free ring buffer. The Android "Unprocessed source" lesson translates directly: on Linux, make sure PipeWire's `module-echo-cancel` / AGC filters aren't in your capture chain (pick the raw device, not a filtered virtual source), and in the browser set `echoCancellation:false, noiseSuppression:false, autoGainControl:false` — note that on Chrome, AGC is only reliably disabled by turning `echoCancellation` off, and some mic drivers apply their own processing regardless.

**Processing pipeline.** ring buffer → window (Blackman-Harris / Hann per preset) → `numpy.fft.rfft` (or `scipy.fft`, which is better-maintained than numpy's per SciPy's own guidance; or pyFFTW via `librosa.set_fftlib` if you ever need it) → optional multi-resolution (replicate Spectroid decimations with a *proper* elliptic IIR low-pass before decimating, like Friture's octave bank; or use librosa VQT/CQT for log-frequency resolution that's musically natural for vibrato) → feature extractors → exponential smoothing → serialize (binary Float32Array over WS, or JSON for offline) → render.

**Rendering.** For the scrolling waterfall use **WebGL** (upload each new column into a texture and scroll via texture coordinates, or a single-row texture blitted into a ring); Canvas2D `getImageData`/`putImageData` works for a first pass but gets expensive at high frame rates. `regl` or plain WebGL textures are the pragmatic choices; PixiJS if you want a scene graph. For the instantaneous spectrum line, Canvas2D is fine.

**Frame rates & budgets (your language).** Target 50 Hz display updates. Live singing/vibrato visibility wants short windows (~20–45 ms; at 48 kHz, 4096 samples ≈ 85 ms is already long, 2048 ≈ 43 ms, 1024 ≈ 21 ms) — the Δf·Δt floor means a 1024-pt window at 48 kHz gives ~47 Hz bins and ~21 ms response (Friture states exactly this: 1024/48000 = 21.3 ms). Formant/vowel study wants longer windows (8192 ≈ 170 ms) for fine harmonic resolution where you don't need time precision. This is the uncertainty-principle tradeoff you already reason about; the presets just encode chosen operating points on that curve.

**Process/threading model.** Audio callback thread (C, GIL-free) → lock-free queue → DSP worker thread (NumPy releases the GIL during FFT and vectorized ops, so a worker thread genuinely runs in parallel with asyncio) → asyncio broadcast over FastAPI/uvicorn WebSocket. This breaks down if you do heavy *Python-level* per-sample loops (they hold the GIL and starve the event loop) — which is exactly the signal to vectorize or port that specific loop. Measure with `py-spy record` (flamegraph) before optimizing; the top 1–3 CPU functions are your only legitimate port candidates.

**Preset system (maps 1:1 to your Spectroid setups).** JSON files, one per preset, e.g.:

```json
// live_singing.json
{ "name": "Live singing", "fft_size": 4096, "decimations": 0,
  "window": "blackman-harris", "interval_ms": 20, "smoothing": 0.25,
  "overlays": ["f0"], "freq_scale": "log" }
// vowel_formant_study.json  { "fft_size": 8192, "decimations": 0, "window": "hann",
//   "overlays": ["f1f2","spectrum_envelope"] }
// sustained_pitch_lab.json  { "fft_size": 8192, "window": "blackman-harris",
//   "interval_ms": 40, "overlays": ["f0","vibrato_rate"] }
// diction_consonants.json   { "fft_size": 1024, "window": "hann",
//   "interval_ms": 10, "smoothing": 0.0 }
// stem_analysis.json        { "mode": "offline", "reference": "stem",
//   "overlays": ["f0_overlay","ltas","ring_ratio"], "align": "dtw" }
// room_noise_floor.json     { "fft_size": 8192, "window": "hann",
//   "averaging": "linear", "hold": "min" }
```

Ship an "environment rules of thumb" note per preset (mic distance, expected noise floor, clipping headroom).

**Offline compare mode.** Browser uploads/records a take → backend runs parselmouth (f0 contour, F1/F2/F3, intensity) + librosa (LTAS, VQT) on *both* the user take and the Demucs-isolated reference stem → align in time with `librosa.sequence.dtw` on chroma or MFCC features (handles the two performances differing in tempo) → return aligned overlays: f0 contour overlay, LTAS comparison, ring-region energy ratio (SPR), per-phrase segmentation. H1–H2 (first-minus-second-harmonic amplitude, a spectral-tilt / open-quotient correlate) and singer's-formant ratio are computed per voiced frame. Flag that H1–H2 is noisy when f0 is irregular (creak), so smooth/aggregate over stable voiced regions.

**C/C++/Rust migration path.** Keep the DSP core behind stable function signatures (`spectrum(frame, preset) -> mags`, `f0(sig, sr) -> contour`, etc.) so the implementation can change without touching the app. Order of porting *if profiling demands it*: (1) any per-sample Python loop in the multi-resolution decimation cascade; (2) exponential smoothing / windowing glue (Friture chose exactly these for Cython); (3) a custom FFT — almost never worth it, since numpy/scipy FFT is FFTW/pocketfft-class C already. Tooling: **PyO3 + maturin** (Rust) is the modern recommendation — memory-safe, zero-copy NumPy interop, releases the GIL, ships a pip-installable wheel; benchmarks put Rust/PyO3 and Cython within roughly x12-of-Python and roughly equal to each other, so choose by ergonomics (Rust if you want to learn it and get safety; Cython if you want to sprinkle types on existing Python with least friction; nanobind/pybind11 if wrapping existing C++). Be honest with yourself: for a single-user learning tool, **the port may never be needed.**

### C. Build roadmap (one person, learning project)

- **M0 — CLI peak-frequency printer.** sounddevice input stream → NumPy rfft → print argmax bin as Hz. *Teaches:* capture, windowing, bin↔Hz mapping, leakage.
- **M1 — Live spectrum to browser.** Minimal browser path: getUserMedia (raw constraints) → AnalyserNode → Canvas2D line. *Teaches:* Web Audio, secure-context requirement, dBFS.
- **M2 — Waterfall + preset system.** WebGL scrolling spectrogram; load the six JSON presets; window/FFT-size switching. *Teaches:* STFT, Δf·Δt tradeoff, GPU textures, exponential smoothing.
- **M3 — Pitch/formant overlays (live).** YIN/MPM f0 in AudioWorklet; ring-band (2.5–3.5 kHz) energy meter; optional F1/F2. *Teaches:* time-domain pitch detection, band energy ratios.
- **M4 — Offline compare mode.** FastAPI `/analyze` with parselmouth + librosa; Demucs `/separate`; DTW alignment; LTAS + SPR + H1–H2 + f0 overlay vs stem. *Teaches:* LPC/Burg formants, probabilistic pitch, DTW, LTAS.
- **M5 — (optional) native DSP core.** Profile with py-spy; port only the proven hot loop to Rust/PyO3 behind the existing interface; benchmark before/after. *Teaches:* profiling discipline, FFI, GIL.

**Testing.** Use synthetic signals as unit tests — exactly your Spectroid test-signal habit: pure sines (assert peak bin ± tolerance), linear/log sweeps (assert tracked peak follows), white/pink noise (assert flat/−3 dB-oct spectrum), two-tone (assert resolution vs window). Golden-file tests: run parselmouth on fixed WAVs and snapshot formant/f0 arrays so refactors and any future native port must match Praat to tolerance. This is your regression safety net for the migration path.

### Library choices (2026), maturity, licenses
- **sounddevice** (PortAudio, CFFI) — capture; mature, ~0.5.x, widely used, MIT.
- **numpy / scipy.fft** — FFT and vectorized DSP; use scipy.fft over numpy.fft (better maintained). BSD.
- **librosa** — pyin, VQT/CQT, dtw, LTAS building blocks; ISC (permissive). Can swap FFT backend via `set_fftlib`.
- **parselmouth** (praat-parselmouth) — formants/pitch/harmonicity; **GPLv3**. Actively maintained (0.4.x).
- **crepe** — optional neural f0; MIT (but TensorFlow dep).
- **demucs** — local stem separation; **MIT**.
- **FastAPI + uvicorn** — backend + WebSocket; MIT/BSD.
- **pyFFTW** — optional FFT acceleration; BSD-licensed wrapper around FFTW, which is GPL — note the copyleft reach if you distribute.
- **PyO3 + maturin** — optional native core; Apache-2.0/MIT.
- Front-end: plain WebGL / **regl** (MIT) / **PixiJS** (MIT); **audioMotion-analyzer** is **AGPLv3** (viral even over network — avoid embedding unless you accept AGPL).

### License notes (this matters)
- **parselmouth and Praat are GPLv3.** If your app imports parselmouth in the same process, the combined work is a GPLv3 derivative — fine for a personal project or an open-source release under GPLv3, but it means you can't ship it as closed source. If you ever want a permissive core, isolate parselmouth behind a **separate process** (CLI subprocess or its own microservice) and talk to it over a pipe/socket — the Sonic Visualiser/Vamp out-of-process (Piper) model is the precedent, and a GPLv3 issue thread on the Parselmouth repo confirms server-side "internal use" without conveying the binary is generally treated as not triggering distribution obligations. For a solo learning tool, simplest is to just license the whole thing **GPLv3**.
- **Friture is GPLv3** (confirmed in every source-file header, "GNU General Public License version 3," Copyright 2009 Timothée Lecomte) — you may fork/borrow code, but your derivative must be GPLv3.
- **Demucs (MIT) and librosa (ISC) are permissive** — no copyleft obligations.
- **aubio and TarsosDSP are GPLv3** — reference their algorithms/papers freely, but copying code pulls in GPL.
- **audioMotion-analyzer is AGPLv3** — the network-copyleft clause can reach a served web app; prefer MIT front-end libs.
- **FFTW is GPL**; pyFFTW wrapping it means distribution triggers GPL. numpy/scipy FFT (pocketfft, BSD) avoids this.

## Recommendations

1. **Start M0–M2 browser-first.** Prove the live spectrum + waterfall + presets purely in the browser (getUserMedia raw + AudioWorklet + WebGL). Don't build the Python live-streaming path unless M3 shows you truly need shared DSP. Benchmark that changes the decision: if browser-side WASM f0 can't hold 50 Hz with acceptable accuracy on your phone, then move f0 server-side.
2. **Stand up the Python backend only for offline (M4).** FastAPI + parselmouth + librosa + Demucs. This is where your engineering-learning payoff is highest (LPC, DTW, LTAS) and where Python's libraries are unbeatable.
3. **Encode the six presets as JSON from day one** and make every widget read from the active preset — this is what keeps it "easy to use," and it forces the clean DSP-core interface you'll want for a future native port.
4. **Set raw-audio constraints everywhere** (`echoCancellation/noiseSuppression/autoGainControl:false` in the browser; raw PipeWire device on Linux) and add a **clipping detector** (flag any |sample| ≥ ~0.99 full-scale) — you just learned this risk on Android; make the app surface it.
5. **For phone-on-LAN, solve HTTPS early**: getUserMedia only works in a secure context (HTTPS or localhost; on insecure origins `navigator.mediaDevices` is `undefined`). Use **mkcert** to mint a locally trusted cert for your laptop's LAN IP and serve uvicorn with `--ssl-keyfile/--ssl-certfile`; the Chrome `--unsafely-treat-insecure-origin-as-secure` flag is a dev-only fallback.
6. **Defer the native port until py-spy says otherwise.** Write the golden-file tests first; only when a specific loop dominates a flamegraph do you port it (Rust/PyO3), and the tests prove you didn't change the numbers.
7. **License GPLv3** for simplicity given parselmouth/Praat, or isolate parselmouth in a subprocess if you ever want a permissive core.

**Thresholds that change the plan:** if live browser f0 accuracy/latency is inadequate → move f0 to the Python backend over WS. If offline Demucs is too slow on CPU → on an NVIDIA RTX 3060 Ti a 6 min 24 s FLAC took 15.6 s with htdemucs vs 187.8 s CPU-only (~12× slower, per LinuxLinks' benchmark), so add optional CUDA or fall back to a cloud stem for long sessions. If a profiled Python loop exceeds your ~20 ms live budget → port that loop only.

## Caveats
- **The "singer's formant" framing is classical/operatic.** "Mentira" by La Ley is rock/pop; the 2.5–3.5 kHz ring band still meaningfully indicates brightness/projection, but don't expect a textbook operatic F3–F5 cluster in a pop-rock vocal. Treat SPR/ring-ratio as a *relative* self-comparison metric (your take vs the reference stem, or your progress over time) under consistent recording conditions, not an absolute score — the literature stresses SPR is only meaningful for the same voice under consistent conditions.
- **Demucs vocal stems have artifacts**, especially on heavily processed or live source material; f0/formant tracking on a separated stem inherits those artifacts. Validate against the full mix where possible.
- **H1–H2 and formant estimates degrade** on breathy/creaky/irregular phonation and near f0 extremes (Praat returns NaN at frame edges) — aggregate over stable voiced regions.
- **Browser audio constraints are inconsistent across browsers/OSes** (Safari behaves differently with `echoCancellation:false`; some drivers process regardless), so verify with a known test tone that what you capture is actually unprocessed.
- **Friture source specifics** (exact octave-filter code) were confirmed via its setup.py, feature page, changelog, and maintainer PR discussion rather than a line-by-line read of every DSP file; the DSP *behavior* is well-corroborated but treat any single file-level claim as "as documented by the project."
- Some cited tutorials/tools are secondary sources (Medium, DEV, vendor blogs); the primary specs (MDN getUserMedia, librosa/parselmouth docs, Demucs repo, W3C, the CREPE and Demucs papers) are authoritative and were prioritized where they conflict.