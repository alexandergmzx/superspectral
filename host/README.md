<!-- SPDX-FileCopyrightText: 2026 Alexander Gomez -->
<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# Host — Linux companion (GPL-3.0-or-later)

The **offline path** of the companion architecture ([ADR 0002](../docs/adr/0002-companion-architecture.md), accepted): everything the founding research document assigned to the Python backend — Praat-grade formants, pitch golden files, LTAS/SPR over whole takes, H1–H2, DTW alignment against a Demucs-separated reference stem — runs here, on recorded takes, never in real time.

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
│   └── golden/                 # ADR 0009 tooling: sets.py, generate.py, verify.py, manifest.py, cli.py
├── golden/                     # DATA, not code: manifest.schema.yaml, README, outputs/<set>/manifest.yaml + *.npy
└── tests/                      # pytest; conftest.py refuses --force-regen (ADR 0009 item 4), fixtures repo_root / tier0_dir
```

| Path | Contents |
|------|----------|
| [src/spectral_host/golden/](src/spectral_host/golden/) | Praat/parselmouth golden-file generator and verifier behind the `spectral-golden` console script (`verify` · `env` · `generate` · `t7`); the manifest it writes pins parselmouth → bundled Praat → pitch method → floor/ceiling → sha256 |
| [golden/](golden/) | The manifest schema, its README (field table, workflow) and the generated sets under `outputs/<set>/` |
| [src/spectral_host/](src/spectral_host/) `spectrum.py` · `praat.py` · `wavio.py` · `hashing.py` · `env.py` · `presets.py` | The numerics the golden sets are made of (ADR 0006 conventions, Praat 6.1.38 raw autocorrelation), the decoder, the digests and the pin capture; `presets.py` loads the six presets under the same rule numbers as `python-scripts/check_presets.py` without importing it |
| [tests/](tests/) | hazard-named pytest suites per module (`test_env.py`: the installed Praat is the pinned bundle and no Apache-2.0 package is importable from here; `test_spectrum_reference.py`: ADR 0006 D1–D3 numbers; `test_manifest_schema.py` / `test_manifest_verify.py`: schema edges and every verify rule, each with a negative case; `test_generate_roundtrip.py`; `test_presets.py`; `test_praat_wrappers.py`) |
| `src/spectral_host/analyze/` *(planned, H3)* | Take reader + offline analysis: f0 contour, Burg formants F1–F3 with bandwidths, LTAS, SPR (Omori), FHE, H1–H2 with Iseli–Alwan correction, Kreiman spectral-slope vector, CPP/CPPS |
| `src/spectral_host/compare/` *(planned, H4)* | DTW alignment of a take against a reference stem (librosa), Demucs separation, per-phrase overlays — the `stem_analysis` preset, which is host-only |
| `src/spectral_host/reports/` *(planned, H4)* | Bland–Altman / ICC agreement reports for the validation plan |

## What the host is not

- Not real-time. The research question binds all real-time DSP to the watch; the host never sees live audio.
- Not a second implementation of the watch's spectrum. The watch's `spectral_core` is regressed against **golden vectors** the host produces, under the conventions in [`../dsp/design/`](../dsp/design/), to a stated tolerance — the host does not replicate the firmware's FFT to compare bit-for-bit.
- Not a browser app. The browser-first live path of the founding document is superseded by the watch; if a UI is ever added here, it is an offline viewer.

## Environment

Own, isolated Python environment, pinned here and nowhere else:

```sh
cd host && uv sync --extra dev      # creates host/.venv from uv.lock; installs spectral_host editable
uv run --project host python -c "import parselmouth; print(parselmouth.VERSION, parselmouth.PRAAT_VERSION)"
uv run --project host pytest -q host/tests            # from the repository root (or `uv run pytest` from host/)
uv run --project host spectral-golden --help
```

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
