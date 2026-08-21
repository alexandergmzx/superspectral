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

| Subdirectory | Contents |
|--------------|----------|
| [golden/](golden/) | Praat/parselmouth golden-file generator and its manifest (pinned parselmouth → bundled Praat → pitch method → floor/ceiling → sha256) |
| `analyze/` *(planned)* | Take reader + offline analysis: f0 contour, Burg formants F1–F3 with bandwidths, LTAS, SPR (Omori), FHE, H1–H2 with Iseli–Alwan correction, Kreiman spectral-slope vector, CPP/CPPS |
| `compare/` *(planned)* | DTW alignment of a take against a reference stem (librosa), Demucs separation, per-phrase overlays — the `stem_analysis` preset, which is host-only |
| `reports/` *(planned)* | Bland–Altman / ICC agreement reports for the validation plan |

## What the host is not

- Not real-time. The research question binds all real-time DSP to the watch; the host never sees live audio.
- Not a second implementation of the watch's spectrum. The watch's `spectral_core` is regressed against **golden vectors** the host produces, under the conventions in [`../dsp/design/`](../dsp/design/), to a stated tolerance — the host does not replicate the firmware's FFT to compare bit-for-bit.
- Not a browser app. The browser-first live path of the founding document is superseded by the watch; if a UI is ever added here, it is an offline viewer.

## Environment

Own, isolated Python environment (`uv`/`venv`, Python ≥ 3.11), pinned in a lock file in this directory when the first module lands (roadmap D6). parselmouth's version is load-bearing: it bundles a specific Praat whose default pitch method changed from raw to filtered autocorrelation in 2023 — see [`golden/README.md`](golden/README.md).
