# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""The golden sets, declared: which inputs, which analysis settings, which outputs — and where every number comes from.

A golden set is its manifest (ADR 0009 decision 1), and a manifest is too
verbose for a human to author (ADR 0009 consequence: "the generator is the
only practical author"). This module is the human-sized form: one `SetSpec`
per set, read by `generate.py`, stating the input list, the analysis
configuration blocks and which analysis runs on which input. It is data, not
code that runs anything — a reviewer reads it the way they would read the
manifest diff, and a change here is a new set under a new name, never an edit
of an existing one (ADR 0009 decision 4).

`SETS["tier0-synthetic"]` — the first set (roadmap H0, unit B-U6)
--------------------------------------------------------------------

**Inputs**: the nineteen 32 kHz files of `datasets/tier0-synthetic/manifest.yaml`
(the tracked half of the Tier-0 dataset, written by the Apache-2.0 generator
`python-scripts/synth_signals`; bibliography 10 P1), in that manifest's own
order. The two 48 kHz twins (`host_only: true` there) are deliberately absent:
32 kHz is the watch's default rate and the only rate any shipped preset uses
(ADR 0003), and nothing may depend on 48 kHz on the watch until experiment
0001 clause 4 passes (ADR 0003 decision 5, roadmap threshold T3) — a golden
set that exists only at 48 kHz would never regress the path the device runs.
`test_tier0_set_inputs_are_exactly_the_32k_manifest_entries` holds this list
equal to the dataset manifest's non-`host_only` entries. The generator reads
that manifest as DATA (never imports `synth_signals`: the licence boundary of
ADR 0004 is a directory, and the halves exchange files only).

**Analyses** — every number below is traced; the floor/ceiling pair marked
`(prov.)` is the only choice rather than a record:

  * `pitch` — `PitchConfig(method="raw", time_step=0.01, pitch_floor=65,
    pitch_ceiling=1100, silence_threshold=0.03, voicing_threshold=0.45,
    octave_cost=0.01, octave_jump_cost=0.35, voiced_unvoiced_cost=0.14,
    max_candidates=15, very_accurate=False)`.
      - `raw`: the only autocorrelation method the pinned bundle registers —
        praat-parselmouth 0.4.7 bundles Praat 6.1.38, which has `To Pitch
        (ac)...` and not the filtered method Praat introduced in 6.4
        (ADR 0009 amendment of 2026-08-21, measured; verify.py invariant 6).
      - `time_step: 0.01` s — pinned rather than Praat's auto `0.0`, so the
        hop relates to the watch's frame rate (docs/validation/golden-files.md
        manifest sketch: "pinned; Praat's own default is 0.0 (auto)").
      - `pitch_floor: 65` Hz (C2) and `pitch_ceiling: 1100` Hz (above C6) —
        widened for singing from the raw defaults 75 / 600 `(prov.)`
        (golden-files.md sketch; host/golden/README.md: "C2 to just above
        C6, matching the f0 range the validation plan commits to").
      - silence 0.03, voicing 0.45, octave 0.01, octave-jump 0.35,
        voiced/unvoiced 0.14, 15 candidates, very accurate off — Praat
        6.1.38's own defaults for `To Pitch (ac)...` (ADR 0009 amendment;
        `praat.RAW_AC_PRAAT_DEFAULTS`, asserted against the bundle's
        signature by `test_raw_ac_praat_defaults_match_the_bundled_signature`).
        Recorded even though they are defaults: ADR 0009 item 1(a), "unstated
        is not a value", because the defaults differ between methods.
  * `formant` — `FormantConfig(method="burg", time_step=0.01, max_formants=5,
    ceiling_hz=5500, window_length=0.025, preemphasis_from_hz=50)`: the
    golden-files.md sketch, verbatim. `max_formants: 5` is LPC order 10, not
    12 (Praat fits `2 × max_formants` poles — manifest.schema.yaml `formant`
    description, `fon/Sound_to_Formant.cpp`); 5500 Hz is Praat's own ceiling
    ("~5000 male / 5500 female" — the sketch); 0.025 s and 50 Hz are Praat's
    `To Formant (burg)...` defaults; `time_step` 0.01 matches `pitch` so the
    two tracks share a grid.
  * `ltas` — `LtasConfig(bandwidth_hz=100)`: the golden-files.md sketch
    (`ltas: bandwidth_hz: 100`); the LTAS tolerance row is "dB per band at
    the same bandwidth", so the bandwidth is the contract.
  * `spectrum` — `SpectrumConfig(window="hann", window_length_samples=4096,
    fftbins=True, fft_size=4096, normalization="S1", scaling="power_spectrum",
    dbfs_reference="sine", int16_scale=32768, dtype="float64")`, which is
    `spectrum.ADR_0006_DEFAULT`: periodic cosine-sum window from the §4.3
    coefficients (ADR 0006 D1; `fftbins: true`), Heinzel S1 power spectrum
    with DC/Nyquist undoubled (D2), 0 dBFS = full-scale sine (D3), the
    `1/32768` seam (D3, ADR 0003 d.2), float64 because the host is the
    float64 reference and the watch the float32 subject (ADR 0009 context).
    N = 4096 is the default analysis size (ADR 0006 D6, "real-4096 → N_c =
    2048"); `hann` is the family the schema's worked example and
    golden-files.md sketch both pin.

**Outputs** (`<analysis>_<input-stem>.npy`, float64, C-order):
  * `pitch` on the six sines, the vowel and the vibrato vowel — the signals
    with a defined f0 (the dataset manifest's `use:` lists "f0 estimator vs
    exact f0" / "peak bin and interpolated peak"); the f0 tolerance rows of
    golden-files.md are about these.
  * `formant` on the two vowels — the only inputs with known resonators
    (`formant_poles_hz` in the dataset manifest; the F1/F2 row).
  * `ltas` on the two vowels and the two noises — the LTAS / SPR / FHE rows
    read band levels off vowels, and a flat (white) and a −3 dB/octave (pink)
    PSD are the "PS vs PSD trap" controls the dataset manifest names.
  * `spectrum` on every input — the per-bin magnitude row applies to all of
    them (on-/off-bin sines, the square's +2.10 dB fundamental, two-tone
    resolution, the sweeps' first frame, DC + sine before the blocker, the
    silence floor at −200 dB).

**Windows**: `generate.py` emits a `windows[]` entry for ALL SEVEN families
(`spectrum.WINDOW_FAMILIES`: the six §4.3 families plus `rect`) at every
`window_length_samples` the set's spectrum block uses — 4096 here — so the
device lane can check every table it can build against the set, not only the
one the spectrum reference happened to use (ADR 0006 D1; schema "1.1"
`windows` description: "a set may carry the digests of every family at the
sizes it generates").

CLI:

    uv run --project host python -m spectral_host.golden.sets            # list the sets
    uv run --project host python -m spectral_host.golden.sets tier0-synthetic   # describe one

`describe` prints the inputs, the analysis blocks (as the manifest will carry
them) and the output plan; nothing is read from disk, nothing is written.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from spectral_host import spectrum
from spectral_host.praat import FormantConfig, LtasConfig, PitchConfig, SpectrogramConfig

#: The `analyses` blocks in manifest.schema.yaml's property order — the order a
#: generated manifest writes them in, because a manifest is reviewed as a diff.
ANALYSIS_ORDER: tuple[str, ...] = ("pitch", "formant", "spectrogram", "ltas", "spectrum")

#: What each `analyses.<block>` is configured by. `spectrum` is the NumPy/SciPy
#: oracle's block (ADR 0009 item 1(b)); the other four are Praat's.
ANALYSIS_CONFIG_TYPES: Mapping[str, type] = {
    "pitch": PitchConfig,
    "formant": FormantConfig,
    "spectrogram": SpectrogramConfig,
    "ltas": LtasConfig,
    "spectrum": spectrum.SpectrumConfig,
}

AnalysisConfig = PitchConfig | FormantConfig | SpectrogramConfig | LtasConfig | spectrum.SpectrumConfig


class SetSpecError(ValueError):
    """A `SetSpec` that contradicts itself (an output naming an input or analysis the set does not have)."""


@dataclass(frozen=True)
class SetSpec:
    """One golden set, declared: inputs, analysis blocks, and which analysis runs on which input.

    `dataset` is the repository-relative directory holding the Tier-0
    `manifest.yaml` and its WAVs; `inputs` are that manifest's file stems (the
    WAV name without `.wav`), in the order the manifest is to list them;
    `analyses` maps a schema block name to its config; `outputs` maps a block
    name to the input stems it runs on. `notes` becomes the manifest's
    free-form `notes` field.
    """

    name: str
    dataset: str
    inputs: tuple[str, ...]
    analyses: Mapping[str, AnalysisConfig]
    outputs: Mapping[str, tuple[str, ...]]
    notes: str = ""
    #: Families whose window tables are emitted at every N the set uses.
    window_families: tuple[str, ...] = field(default=tuple(spectrum.WINDOW_FAMILIES))

    def __post_init__(self) -> None:
        if not self.name or not self.inputs:
            raise SetSpecError(f"set {self.name!r}: a set needs a name and at least one input")
        if len(set(self.inputs)) != len(self.inputs):
            raise SetSpecError(f"set {self.name!r}: duplicate input stems in {self.inputs}")
        for analysis, cfg in self.analyses.items():
            expected = ANALYSIS_CONFIG_TYPES.get(analysis)
            if expected is None:
                raise SetSpecError(f"set {self.name!r}: {analysis!r} is not a schema analysis block {ANALYSIS_ORDER}")
            if not isinstance(cfg, expected):
                raise SetSpecError(f"set {self.name!r}: analyses.{analysis} must be a {expected.__name__}, got {type(cfg).__name__}")
        if not self.analyses:
            raise SetSpecError(f"set {self.name!r}: a set needs at least one analysis block (schema: analyses minProperties 1)")
        for analysis, stems in self.outputs.items():
            if analysis not in self.analyses:
                raise SetSpecError(f"set {self.name!r}: outputs.{analysis} has no analyses.{analysis} block (verify.py invariant 3)")
            if analysis == "spectrogram":
                raise SetSpecError(f"set {self.name!r}: spectrogram outputs are roadmap H1, not H0; the block may be recorded but not emitted")
            unknown = [s for s in stems if s not in self.inputs]
            if unknown:
                raise SetSpecError(f"set {self.name!r}: outputs.{analysis} names inputs not in the set: {unknown} (verify.py invariant 2)")
            if len(set(stems)) != len(stems):
                raise SetSpecError(f"set {self.name!r}: outputs.{analysis} lists an input twice: {stems}")
        if not any(self.outputs.values()):
            raise SetSpecError(f"set {self.name!r}: a set needs at least one output (schema: outputs minItems 1)")
        for family in self.window_families:
            if family not in spectrum.WINDOW_FAMILIES:
                raise SetSpecError(f"set {self.name!r}: {family!r} is not a window family {list(spectrum.WINDOW_FAMILIES)}")

    @property
    def ordered_analyses(self) -> tuple[str, ...]:
        """The set's analysis blocks in schema order."""
        return tuple(a for a in ANALYSIS_ORDER if a in self.analyses)

    @property
    def window_sizes(self) -> tuple[int, ...]:
        """Every `window_length_samples` the set's spectrum block(s) use, sorted; `()` without a spectrum block."""
        sizes = {cfg.window_length_samples for a, cfg in self.analyses.items() if a == "spectrum"}
        return tuple(sorted(int(n) for n in sizes))

    def analyses_asdict(self) -> dict[str, dict[str, object]]:
        """The manifest's `analyses` mapping: each block's `asdict()`, in schema order."""
        return {a: self.analyses[a].asdict() for a in self.ordered_analyses}

    def planned_outputs(self) -> tuple[tuple[str, str], ...]:
        """`(analysis, input_stem)` pairs in emission order: analyses in schema order, inputs in set order."""
        plan = []
        for analysis in self.ordered_analyses:
            wanted = set(self.outputs.get(analysis, ()))
            plan.extend((analysis, stem) for stem in self.inputs if stem in wanted)
        return tuple(plan)


# --- tier0-synthetic ----------------------------------------------------------------

#: The nineteen 32 kHz stems of datasets/tier0-synthetic/manifest.yaml, in its order.
TIER0_32K_INPUTS: tuple[str, ...] = (
    "sine_437p5_m20dBFS_32k",
    "sine_440_0dBFS_32k",
    "sine_440_m1dBFS_32k",
    "sine_440_m20dBFS_32k",
    "sine_440_m60dBFS_32k",
    "sine_1000_m20dBFS_32k",
    "square_1000_0dBFS_32k",
    "twotone_1000_d0p5bin_32k",
    "twotone_1000_d1bin_32k",
    "twotone_1000_d2bin_32k",
    "twotone_1000_d4bin_32k",
    "white_m20dBFS_seed1_32k",
    "pink_m20dBFS_seed1_32k",
    "sweep_lin_20_16000_32k",
    "sweep_exp_20_16000_32k",
    "vowel_a_f0_220_32k",
    "vowel_a_vibrato_220_6hz_100c_32k",
    "dc_0p1_plus_sine_440_m20dBFS_32k",
    "silence_32k",
)

_TIER0_SINES: tuple[str, ...] = tuple(s for s in TIER0_32K_INPUTS if s.startswith("sine_"))
_TIER0_VOWELS: tuple[str, ...] = ("vowel_a_f0_220_32k", "vowel_a_vibrato_220_6hz_100c_32k")
_TIER0_NOISES: tuple[str, ...] = ("white_m20dBFS_seed1_32k", "pink_m20dBFS_seed1_32k")

TIER0_PITCH = PitchConfig(
    method="raw",
    time_step=0.01,
    pitch_floor=65,
    pitch_ceiling=1100,
    silence_threshold=0.03,
    voicing_threshold=0.45,
    octave_cost=0.01,
    octave_jump_cost=0.35,
    voiced_unvoiced_cost=0.14,
    max_candidates=15,
    very_accurate=False,
)

TIER0_FORMANT = FormantConfig(
    method="burg",
    time_step=0.01,
    max_formants=5,
    ceiling_hz=5500,
    window_length=0.025,
    preemphasis_from_hz=50,
)

TIER0_LTAS = LtasConfig(bandwidth_hz=100)

TIER0_SPECTRUM = spectrum.ADR_0006_DEFAULT

TIER0_NOTES: str = (
    "spectrum = the first device frame, samples [0, N) of the int16 file scaled by 1/32768, "
    "BEFORE the DC blocker (ADR 0006 D7 is not applied here; the dc_0p1 input exists to test it "
    "on the device). Pitch/formant times are Praat's frame centres: compare by time, never by "
    "index (golden-files.md frame-grid trap). LTAS levels are Praat's dB/Hz re (2e-5 Pa)^2 with "
    "1.0 = 1 Pa, not dBFS; the LTAS tolerance row is per band and reference-invariant. "
    "Formant columns F1..F5/B1..B5 are NaN where Praat has no value."
)

SETS: dict[str, SetSpec] = {
    "tier0-synthetic": SetSpec(
        name="tier0-synthetic",
        dataset="datasets/tier0-synthetic",
        inputs=TIER0_32K_INPUTS,
        analyses={
            "pitch": TIER0_PITCH,
            "formant": TIER0_FORMANT,
            "ltas": TIER0_LTAS,
            "spectrum": TIER0_SPECTRUM,
        },
        outputs={
            "pitch": _TIER0_SINES + _TIER0_VOWELS,
            "formant": _TIER0_VOWELS,
            "ltas": _TIER0_VOWELS + _TIER0_NOISES,
            "spectrum": TIER0_32K_INPUTS,
        },
        notes=TIER0_NOTES,
    ),
}


def get_set(name: str) -> SetSpec:
    """`SETS[name]`, with a message listing what exists."""
    try:
        return SETS[name]
    except KeyError:
        raise KeyError(f"no golden set named {name!r}; known sets: {sorted(SETS)}") from None


# --- CLI -------------------------------------------------------------------


def describe(spec: SetSpec) -> str:
    lines = [f"set: {spec.name}", f"dataset: {spec.dataset}", f"inputs ({len(spec.inputs)}):"]
    lines.extend(f"  - {stem}" for stem in spec.inputs)
    lines.append("analyses:")
    for analysis, block in spec.analyses_asdict().items():
        lines.append(f"  {analysis}:")
        lines.extend(f"    {k}: {v}" for k, v in block.items())
    lines.append(f"windows: {list(spec.window_families)} at N in {list(spec.window_sizes)}")
    plan = spec.planned_outputs()
    lines.append(f"outputs ({len(plan)}):")
    lines.extend(f"  - {analysis}_{stem}.npy" for analysis, stem in plan)
    if spec.notes:
        lines.append(f"notes: {spec.notes}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m spectral_host.golden.sets",
        description="List the declared golden sets, or describe one (inputs, analysis blocks, output plan).",
    )
    parser.add_argument("name", nargs="?", help="set to describe (default: list the names)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.name is None:
        for name, spec in SETS.items():
            print(f"{name}: {len(spec.inputs)} inputs, {len(spec.planned_outputs())} outputs, analyses {list(spec.ordered_analyses)}")
        return 0
    try:
        print(describe(get_set(args.name)))
    except KeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
