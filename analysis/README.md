# Analysis

Post-experiment data analysis. This is where takes, bench captures and corpus runs turn into the figures, tables and statistics of the validation plan — and eventually the paper.

| Subdirectory | Contents |
|--------------|----------|
| `notebooks/` *(planned)* | Jupyter notebooks for exploratory analysis and figure generation, one per experiment or validation row |
| `reports/` *(planned)* | Per-phase reports (Markdown) summarising results against the acceptance metrics; figures as PNG/SVG/PDF |

## Conventions

- Notebooks must be **deterministic from the manifests** — no manual mutation. Read from [`../datasets/`](../datasets/) via each dataset's `manifest.yaml` and from the golden manifests; write figures to `reports/`.
- Heavy lifting (take decoding, alignment, metric computation, statistics) belongs in scripts under [`../python-scripts/`](../python-scripts/) (Apache-2.0) or, when it needs parselmouth/Demucs, under [`../host/`](../host/) (GPL-3.0-or-later); notebooks orchestrate and visualize. A notebook that imports from `host/` is itself GPL and lives under `host/`, not here.
- **Two paths, two columns.** Every table reports the digital-injection path and the acoustic path separately; a cell that mixes them is a defect ([`../docs/validation/README.md`](../docs/validation/README.md)).
- Agreement against a reference is a **Bland–Altman** problem (bias, limits of agreement), repeatability is **ICC**, and equivalence claims use TOST — not RMSE or a correlation coefficient alone. Report percentiles of cents error (CEP-style), not just means.
- Every figure states the build (`app_elf_sha256`), the preset id + sha256, the golden-set manifest, the measurement path and the geometry (mouth-to-wrist distance, arm angle, sleeve condition) in its caption or metadata.
- Commit cleared notebooks (no output cells) to keep diffs reviewable; expensive figures land in `reports/`.
- Colormaps for any spectrogram figure follow the same perceptually uniform, colour-vision-deficiency-safe choice the watch uses (cividis / batlow class, ADR 0011); never rainbow/jet.
