<!-- SPDX-FileCopyrightText: 2026 Alexander Gomez -->
<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# Host — Linux companion (GPL-3.0-or-later)

The **offline path** of the companion architecture ([ADR 0002](../docs/adr/0002-companion-architecture.md), accepted): everything the founding research document assigned to the Python backend — Praat-grade formants, pitch golden files, LTAS/SPR over whole takes, H1–H2, DTW alignment against a Demucs-separated reference stem — runs here, on recorded takes, never in the watch's live loop.

Since [ADR 0021](../docs/adr/0021-host-web-application.md) (accepted 2026-08-22) this directory also carries the founding document's **web application**, in full: a front end under `web/` (Vite + TypeScript) served by a FastAPI backend under `src/spectral_host/web/`. It is two things at once — the **user interface** the `analyze/` and `compare/` modules never had, and a **second digital-injection-path instrument**, an independent TypeScript implementation of the [ADR 0006](../docs/adr/0006-fft-normalisation-and-window-conventions.md) conventions held to the Python oracle by the committed golden set. It is *not* a view of the watch: it analyses **this machine's** microphone, and its own latency and refresh are **measured and reported, never claimed**. Milestones W0–W4 on the [roadmap](../docs/roadmap/documentation-roadmap.md)'s track W.

## The licence boundary

**Everything under this directory is licensed GPL-3.0-or-later** under [`LICENSE`](LICENSE), not Apache-2.0 like the rest of the repository. Reason: the companion imports parselmouth (which embeds Praat, GPLv3+) in-process, and librosa/Demucs/mir_eval sit alongside it. The split is stated in the root [`NOTICE`](../NOTICE) and [`README.md`](../README.md#license) and will be recorded as ADR 0004.

Rules that keep the boundary clean — they are the reason the boundary is a *directory*:

- Nothing outside `host/` imports anything inside `host/`; nothing inside `host/` imports anything outside `host/`. The two halves exchange **files** only: takes and preset JSON written by the watch ([`../protocols/specs/`](../protocols/specs/)), golden vectors and reports written by the host.
- Firmware never links, vendors or generates code from `host/`. The firmware's only relationship with Praat is a tolerance table against files the host produced.
- This is the **sole exception** to the "every Python file lives under `python-scripts/`" rule ([`CLAUDE.md`](../CLAUDE.md#where-python-lives)). Apache-2.0 Python (signal generators, comparators, `doc_ocr`) stays under [`../python-scripts/`](../python-scripts/); anything that needs a GPL import comes here. Do not move Apache-2.0 tooling here for convenience — that would relicense it.
- Every file here carries `SPDX-License-Identifier: GPL-3.0-or-later` — in an HTML comment for the Markdown, on line 2 for everything else. The one exception is `LICENSE`, which *is* the licence text.

## Layout

A src layout (roadmap H0, unit B-U1): the importable package lives under `src/`, so `import spectral_host` resolves only from the installed environment (`host/.venv`) and never by accident from a checkout that happens to have `host/` on `sys.path`. Data that the Apache-2.0 side *reads* — the schema and the golden outputs — stays under [`golden/`](golden/), outside the package, so that the licence boundary and the "files on disk only" contract coincide.

```
host/
├── pyproject.toml              # the GPL environment: exact parselmouth pin, src layout, `spectral-golden` entry point
├── uv.lock · .python-version   # frozen resolution (install with `uv sync --frozen`; the CI `host` job does) · 3.12
├── src/spectral_host/          # the package — GPL-3.0-or-later, imported by nothing outside host/
│   ├── __init__.py             # __version__
│   ├── spectrum.py             # the NumPy/SciPy reference spectrum: ADR 0006 windows from coefficients, S1/S2, dBFS
│   ├── praat.py                # parselmouth wrappers: raw-ac pitch (all eleven parameters), Burg formants, LTAS
│   ├── wavio.py · hashing.py   # 16-bit WAV reader; sha256 of bytes / files / the GENERATOR_TREE
│   ├── env.py                  # the `generator` block: installed pins, HEAD, GENERATOR_TREE digest, BLAS
│   ├── presets.py              # preset loader (V0/V1/V8/V9 re-implemented; the Apache checker is the validator of record)
│   ├── golden/                 # ADR 0009 tooling: sets.py, generate.py, verify.py, manifest.py, cli.py
│   ├── capture/                # planned, W0 — audio.py (host input stream: device, rate, what it actually got)
│   │                           #   + peak.py (`spectral-web peak`, the founding document's M0 printer)
│   └── web/                    # planned, W0 — the FastAPI backend: /api/presets (byte-identical + sha256),
│                               #   /analyze (parselmouth), /separate (Demucs), served by uvicorn (TLS for phone-on-LAN)
├── golden/                     # DATA, not code: manifest.schema.yaml, README, outputs/<set>/manifest.yaml + *.npy
├── tests/                      # pytest; conftest.py refuses --force-regen (ADR 0009 item 4), fixtures repo_root / tier0_dir
└── web/                        # planned, W0–W4 — the front end: Vite + TypeScript, GPL-3.0-or-later per file (ADR 0021 d.4)
    ├── package.json · package-lock.json · tsconfig.json    # annotated by REUSE.toml; `npm ci` is the only install path
    └── src/                    # AudioWorklet ring buffer · the TypeScript DSP module (ADR 0006 re-implemented)
                                #   · WebGL scrolling waterfall · Canvas2D spectrum · the six presets, fetched never bundled
```

| Path | Contents |
|------|----------|
| [src/spectral_host/golden/](src/spectral_host/golden/) | Praat/parselmouth golden-file generator and verifier behind the `spectral-golden` console script (`verify` · `env` · `generate` · `t7`); the manifest it writes pins parselmouth → bundled Praat → pitch method → floor/ceiling → sha256 |
| [golden/](golden/) | The manifest schema, its README (field table, workflow) and the generated sets under `outputs/<set>/` |
| [src/spectral_host/](src/spectral_host/) `spectrum.py` · `praat.py` · `wavio.py` · `hashing.py` · `env.py` · `presets.py` | The numerics the golden sets are made of (ADR 0006 conventions, Praat 6.1.38 raw autocorrelation), the decoder, the digests and the pin capture; `presets.py` loads the six presets under the same rule numbers as `python-scripts/check_presets.py` without importing it |
| [tests/](tests/) | hazard-named pytest suites per module (`test_env.py`: the installed Praat is the pinned bundle and no Apache-2.0 package is importable from here; `test_spectrum_reference.py`: ADR 0006 D1–D3 numbers; `test_manifest_schema.py` / `test_manifest_verify.py`: schema edges and every verify rule, each with a negative case; `test_generate_roundtrip.py`; `test_presets.py`; `test_praat_wrappers.py`) |
| `src/spectral_host/analyze/` *(planned, W4)* | Take reader + offline analysis: f0 contour, Burg formants F1–F3 with bandwidths, LTAS, SPR (Omori), FHE, H1–H2 with Iseli–Alwan correction, Kreiman spectral-slope vector, CPP/CPPS |
| `src/spectral_host/compare/` *(planned, W4)* | DTW alignment of a take against a reference stem (librosa), Demucs separation, per-phrase overlays — the `stem_analysis` preset, which is host-only |
| `src/spectral_host/reports/` *(planned, W4)* | Bland–Altman / ICC agreement reports for the validation plan |
| `src/spectral_host/capture/` *(planned, W0)* | `audio.py` opens a host input stream and records what device and sample rate it actually got; `peak.py` prints the interpolated peak frequency behind `spectral-web peak` — the founding document's M0 milestone, landed as a CLI ([ADR 0021](../docs/adr/0021-host-web-application.md) decision 1) |
| `src/spectral_host/web/` *(planned, W0)* | The FastAPI application: `GET /api/presets/{id}` returns the canonical file from [`../protocols/presets/`](../protocols/presets/) **byte-identical** after `presets.load_preset` has proved it, and reports its sha256; `/analyze` (parselmouth f0 contour, Burg formants, LTAS) and `/separate` (Demucs `htdemucs`, vocals two-stem — exercised through its **501 path** in CI) are the offline-compare endpoints. Served by uvicorn, with `--ssl-certfile` / `--ssl-keyfile` for phone-on-LAN |
| `web/` *(planned, W0–W4)* | The browser-native live path: `getUserMedia` with `echoCancellation`, `noiseSuppression` and `autoGainControl` all **false** → AudioWorklet ring buffer → DC blocker → window → FFT → `\|X\|²` → dBFS in TypeScript → WebGL waterfall + Canvas2D spectrum, peak markers, hold, smoothing, the clipping flag, and the live overlays. **Injection mode** parses int16 PCM itself and never calls `decodeAudioData` (which resamples silently), so *the same Tier-0 files against the same goldens* is literally true |

## What the host is not

- **Not real-time for the watch's audio.** The research question binds the **watch's** real-time DSP to the watch; nothing here ever sees the watch's live audio, and no number produced here enters a latency, refresh or autonomy bound of [proposal §1](../docs/proposal/01-super-spectral-proposal.md). The web application's own live path is live on *this machine's* microphone, which is a different claim and is labelled as one.
- **Not in the watch's live loop.** There is no live link between watch and host — no WebSocket, no stream, no transport of audio or spectra from the device ([ADR 0002](../docs/adr/0002-companion-architecture.md) decision 4 as amended by [ADR 0021](../docs/adr/0021-host-web-application.md) decision 5; it would need the radio [ADR 0017](../docs/adr/0017-no-radio-in-v1-trimmed-component-set.md) excludes). The host sees **takes**: files on disk, read by one reader that both the CLI and the web application's offline-compare mode call. Until `take-format.md` exists, the web application accepts WAV uploads instead.
- **Not a viewer of the watch.** The host web application ([ADR 0021](../docs/adr/0021-host-web-application.md)) is a live analyzer of **this machine's** microphone and the user interface of the offline-compare mode; its mic-to-pixel latency and sustained refresh are **measured and reported per browser and OS, never claimed**. Nothing it shows is the watch's screen — that is `host-sim` ([ADR 0013](../docs/adr/0013-native-linux-simulator-target.md)), an Apache-2.0 LVGL/SDL program that renders the watch's own `ui` component and lives **outside this directory**. Two different programs; neither substitutes for the other.
- **Not a second implementation of the watch's spectrum.** The watch's `spectral_core` is regressed against **golden vectors** the host produces, under the conventions in [`../dsp/design/`](../dsp/design/), to a stated tolerance — the host does not replicate the firmware's FFT to compare bit-for-bit. The web application's TypeScript DSP module is likewise held to **this oracle** and never to `spectral_core` directly, so the agreement matrix stays a star and there is no watch-vs-browser row (ADR 0021 decision 2).

## Environment

Own, isolated Python environment, pinned here and nowhere else:

```sh
cd host && uv sync --extra dev      # creates host/.venv from uv.lock; installs spectral_host editable
uv run --project host python -c "import parselmouth; print(parselmouth.VERSION, parselmouth.PRAAT_VERSION)"
uv run --project host pytest -q host/tests            # from the repository root (or `uv run pytest` from host/)
uv run --project host spectral-golden --help
```

**Extras keep the heavy dependencies out of the default install.** `dev` (pytest) is the only one that exists today; track W adds three more, each entering `pyproject.toml` and `uv.lock` under the licence discipline of [ADR 0021](../docs/adr/0021-host-web-application.md) decision 4:

| Extra | Adds | Lands at |
|---|---|---|
| `capture` | the host input stream behind `spectral-web peak` | W0 |
| `analyze` | librosa (ISC, [06 #34](../docs/bibliography/06-reference-projects.md)) — pYIN, DTW and LTAS behind `/analyze` and the compare mode | W4 |
| `separate` | demucs (MIT, [06 #59](../docs/bibliography/06-reference-projects.md)) and torch (BSD-3-Clause (verify)) — hundreds of megabytes, a model download at first run, and CPU separation an order of magnitude slower than GPU. Weights are **data**: fetched into the data directory, never committed | W4 |

A default `uv sync` must stay installable without torch; `/separate` answers **501** when the extra is absent, and that 501 path is what CI exercises. Where FastAPI and uvicorn ([06 #65](../docs/bibliography/06-reference-projects.md)) land — base dependencies or a fourth extra — is W0's call, unrouted by the ADR; either way they are pinned in `uv.lock` under the same discipline, because the backend is what serves the interface at all.

Run inside `direnv` or with `env -u PYTHONPATH`: this machine's `~/.bashrc` sources ROS 2 Jazzy, whose `PYTHONPATH` lands on `sys.path` ahead of the venv and drags its `launch_testing` pytest plugin into any pytest run ([pitfall A1](../docs/devenv/pitfalls.md#a-host-toolchain-shell)); the repository [`.envrc`](../.envrc) already unsets it.

`praat-parselmouth` is pinned **exactly** (`==0.4.7`), because the pin *is* the
Praat version. Measured from this environment on 2026-08-21:

| | |
|---|---|
| `parselmouth.VERSION` | `0.4.7` |
| `parselmouth.PRAAT_VERSION` | **`6.1.38`** (2021-01-02) |
| pitch methods available | `to_pitch`, `to_pitch_ac`, `to_pitch_cc`, `to_pitch_shs`, `to_pitch_spinet` |
| `To Pitch (filtered autocorrelation)` | **`PraatError: Command "To Pitch (filtered autocorrelation)" not available for given objects.`** |

Praat's default pitch method changed from raw to filtered autocorrelation in
**Praat 6.4 (2023-11-15)**, and *no released parselmouth has reached it* — every
0.4.x bundles 6.1.38. Golden sets therefore pin `method: raw` with 6.1.38's own
defaults; see [`golden/README.md`](golden/README.md) and
[ADR 0009](../docs/adr/0009-golden-file-strategy.md). praat.org itself is at
7.0.01 (read 2026-08-21) — comparing the two is roadmap threshold T7b, and it
needs an out-of-process binary.

### The fourth environment: Node and npm for `web/`

The front end is the first application code in this repository that is neither C nor Python. It gets its **own toolchain and its own lockfile**, and it is never mixed with the Python environments catalogued in [`../docs/devenv/setup.md`](../docs/devenv/setup.md) — no `uv` project installs it, no `.venv` contains it, and `npm` is never run from inside `host/.venv`.

| | |
|---|---|
| Node | `v20.20.2` (read on this machine, 2026-08-22) |
| npm | `10.8.2` (read on this machine, 2026-08-22) |
| Install path | **`npm ci` against the committed `package-lock.json`, with `--ignore-scripts`** — the only install path ([ADR 0021](../docs/adr/0021-host-web-application.md) decision 4). `npm install` is not a substitute: it rewrites the lock |
| Allowed dependency licences | MIT, ISC, 0BSD, BSD-2-Clause, BSD-3-Clause, Apache-2.0, CC0-1.0, Unlicense, BlueOak-1.0.0, Python-2.0, Zlib, CC-BY-4.0 — and nothing else. **AGPL-3.0 is forbidden** (a served web application is exactly the case its network clause reaches); GPL and LGPL packages are refused too, so that the allowlist stays one line a reviewer can check. A licence gate over `package-lock.json` runs in CI and **fails closed** on an unknown or absent licence |

The exact Node and npm pin lands with the `package-lock.json` at W0; until then the versions above are what the machine has, not a decision.

### mkcert: phone-on-LAN is a requirement, not a nicety

`navigator.mediaDevices` is `undefined` on an insecure origin that is not `localhost`, so opening the analyzer on a phone over the LAN needs HTTPS. **W2 is not done until the waterfall runs on the owner's phone through this certificate** (owner's decision, 2026-08-22; [ADR 0021](../docs/adr/0021-host-web-application.md) decision 8). Chrome's insecure-origin flag is a development fallback and is deliberately not documented here as the way in.

```sh
mkcert -install                                   # install the local CA into this machine's trust stores
mkcert <lan-ip> localhost 127.0.0.1 ::1           # one certificate covering the laptop's LAN address
# keep both files OUTSIDE the repository -- they are machine-local secrets, never committed
# the ASGI module path itself lands at W0
uvicorn spectral_host.web.app:app --host 0.0.0.0 \
        --ssl-certfile <path>.pem --ssl-keyfile <path>-key.pem
```

The phone will not trust that certificate until **mkcert's root CA is installed on the phone itself** (`mkcert -CAROOT` names the directory holding `rootCA.pem`; transfer and install it through the phone's own certificate store). Verify on the actual phone, not on the laptop: a laptop browser trusts the CA already and proves nothing about the device the requirement is about. Every third party who builds this mints their own certificate — nothing here is shareable.

The data directory the backend writes — uploads, separated stems, model weights, ingested takes — defaults to `$XDG_DATA_HOME/superspectral/` `(prov.)`, is overridable, and is **never inside the repository**: the server refuses a path that resolves inside it, and nothing under it is ever committed.
