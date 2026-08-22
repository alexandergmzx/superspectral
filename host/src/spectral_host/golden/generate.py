# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""`generate` — write a NEW golden set from its `SetSpec`: the arrays, then the manifest that is the golden file.

ADR 0009 decision 4: regeneration is a deliberate, reviewed act with a recorded
reason, never a silent refresh. This module is the only author of a golden
manifest, and it is built so that every way of producing a confidently wrong
one that ADR 0009 names is refused before a byte is written:

  1. **A set is new or nothing.** `host/golden/outputs/<set>/` must not exist.
     A pin change is a new set under a new name; an existing set is never
     edited, re-emitted or patched here (`ExistingSet`).
  2. **Chain of custody on the inputs.** The Tier-0 dataset manifest
     (`<dataset>/manifest.yaml`, written by the Apache-2.0 `synth_signals`
     generator) is read AS DATA with `yaml.safe_load` — this module never
     imports `synth_signals` or anything under python-scripts/ (ADR 0004: the
     boundary is a directory; the halves exchange files). Every input WAV must
     be on disk (`MissingInputs`, whose message says to run `synth_signals
     generate` first) and its bytes must hash to the sha256 that manifest
     records (`InputDigestMismatch`): a golden set of bytes the dataset
     manifest does not describe would pin a signal nobody can regenerate.
     The decoded header (rate, channels, bit depth) must match the manifest
     row too. `inputs[].source.parameters` are copied verbatim from the
     dataset manifest's `ground_truth.files.<stem>.parameters`.
  3. **What ran is what is recorded.** `generator` is `env.capture()` —
     installed parselmouth / bundled Praat / NumPy / SciPy / BLAS, `HEAD`,
     and the GENERATOR_TREE digest of `host/src/spectral_host/` (env.py). A dirty package tree
     (`env.is_dirty`) is refused unless `allow_dirty=True`, because then
     `sha256` describes bytes no commit contains and `commit` is a lie about
     what ran; when it IS allowed, the manifest's `notes` says so
     automatically, so the reviewer cannot miss it.
  4. **One decode.** Each WAV is read once (`wavio.read_wav`, int16 untouched);
     the `1/int16_scale` seam is then applied exactly once per consumer
     (`spectrum.reference_spectrum` for the spectrum block with the block's
     own `int16_scale`; `praat.sound_from_int16` at 32768 — Praat's and the
     project's convention, ADR 0003 d.2 — for the Praat blocks, one
     `parselmouth.Sound` per input shared by pitch/formant/ltas).
  5. **Arrays are plain.** `numpy.save(allow_pickle=False)`, float64,
     C-contiguous, `.npy` format 1.0; `outputs[]` records path, sha256,
     dtype, shape, units, columns, and `unvoiced_sentinel: 0` for pitch
     (Praat's convention; verify.py rule N2).
  6. **Windows for every family.** `windows[]` carries an entry for each of
     the spec's `window_families` (all seven by default: the six §4.3
     families plus `rect`) at every `window_length_samples` the set uses,
     with the §4.3 coefficients and `spectrum.window_table_sha256` (ADR 0006
     D1; schema "1.1").
  7. **The limits are elsewhere.** `tolerances.source` is the schema's
     const, `docs/validation/golden-files.md`; `tolerances.revision` is
     `git log -1 --format=%H -- <that file>` — the last commit that touched
     the table, which is what the set was accepted against.
  8. **It verifies its own output, and fails if red.** After writing, the
     manifest goes through `verify.verify_manifest` with every rule on; any
     Failure raises `VerificationFailed`. The files are left on disk for
     inspection and the message says so — the directory must be removed
     before a retry (rule 1).

`praat_reference` is written as `null`: roadmap threshold T7b is open
(ADR 0009 item 1(c)), and a set carrying `null` there may not back a
"vs Praat" claim outside the project. `regeneration` is written on this, the
first generation, with `previous_manifest_sha256` and `previous_set` `null`
(ADR 0009 decision 4: the block exists on EVERY generation).

Manifest key order is the schema's property order, top to bottom, because a
manifest is reviewed as a diff (ADR 0009 decision 4: "review the manifest
diff, not the arrays").

CLI (wired by `spectral-golden generate`; see cli.py):

    uv run --project host python -m spectral_host.golden.generate \\
        --set tier0-synthetic --approved-by "Alexander Gomez" --reason "initial generation" \\
        [--repo-root DIR] [--allow-dirty]

Exit 0 when the set was written and verifies clean; 1 when it was written
but its own `verify` is red (files left in place); 2 on a refused
precondition — unknown set, existing set directory, missing or drifted
inputs, dirty package tree without `--allow-dirty`, no repository root.
"""

from __future__ import annotations

import argparse
import datetime
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import numpy as np
import parselmouth
import yaml

from spectral_host import env as env_mod
from spectral_host import praat, spectrum
from spectral_host.golden import manifest as manifest_mod
from spectral_host.golden import sets as sets_mod
from spectral_host.golden import verify as verify_mod
from spectral_host.golden.sets import SetSpec
from spectral_host.hashing import sha256_file
from spectral_host.wavio import WavFile, read_wav

#: The file name of a Tier-0 dataset manifest inside its dataset directory.
DATASET_MANIFEST_FILENAME: str = "manifest.yaml"

#: The schema's `tolerances.source` const — the only place a limit is defined (ADR 0009 decision 2).
TOLERANCES_SOURCE: str = "docs/validation/golden-files.md"

#: `inputs[].source.kind` for every input this generator knows how to produce.
SOURCE_KIND: str = "tier0-synthetic"

#: Per analysis: (units, columns) as the manifest records them. Formant columns
#: depend on the config (`FormantConfig.formant_slots`) and are built in place.
PITCH_UNITS, PITCH_COLUMNS = "s, Hz", ("time", "f0")
LTAS_UNITS, LTAS_COLUMNS = "Hz, dB/Hz re (2e-5 Pa)^2 with 1.0 = 1 Pa (Praat To Ltas)", ("frequency", "level")
SPECTRUM_COLUMNS = ("frequency", "level")

#: The hint `MissingInputs` carries: how the Apache side regenerates the WAVs.
SYNTH_SIGNALS_HINT: str = (
    "run synth_signals generate first: "
    "cd python-scripts/synth_signals && uv run python -m synth_signals generate --out ../../datasets/tier0-synthetic"
)


class GenerateError(RuntimeError):
    """A precondition the generator refuses to proceed past (CLI exit 2)."""


class ExistingSet(GenerateError):
    """The set directory exists: a golden set is new or nothing (ADR 0009 decision 4)."""


class MissingInputs(GenerateError):
    """One or more input WAVs are not on disk; the message says how to regenerate them."""


class InputDigestMismatch(GenerateError):
    """A WAV on disk does not hash to what the dataset manifest records (chain of custody broken)."""


class DirtyGenerator(GenerateError):
    """`host/src/spectral_host/` has uncommitted changes and `allow_dirty` is False."""


class VerificationFailed(GenerateError):
    """The set was written but its own `verify` is red (CLI exit 1). Files are left for inspection."""

    def __init__(self, set_dir: Path, failures: list[verify_mod.Failure]) -> None:
        self.set_dir = set_dir
        self.failures = failures
        lines = "\n".join(f"  {f.rule}: {f.message}" for f in failures)
        super().__init__(
            f"{set_dir}: generated set fails its own verify ({len(failures)} failure"
            f"{'s' if len(failures) != 1 else ''}); files left in place for inspection — remove the "
            f"directory before retrying:\n{lines}"
        )


# --- the dataset manifest, read as data ------------------------------------------


@dataclass(frozen=True)
class DatasetEntry:
    """One WAV of a Tier-0 dataset manifest: its `files[]` row joined with its `ground_truth.files` record."""

    stem: str
    relpath: str  # repository-relative path of the WAV
    sha256: str
    sample_rate: int
    channels: int
    bit_depth: int
    generator: str
    parameters: dict
    host_only: bool


def load_dataset_manifest(repo_root: Path, dataset_relpath: str) -> dict[str, DatasetEntry]:
    """Read `<repo_root>/<dataset>/manifest.yaml` with `yaml.safe_load` and index its WAVs by stem.

    The manifest is `synth_signals`' output (python-scripts/synth_signals/synth_signals/manifest.py):
    `files[]` rows carry `path` (relative to the manifest), `sha256`, `sample_rate`,
    `channels`, `bit_depth`; `ground_truth.files.<stem>` carries `generator`,
    `parameters` and `host_only`. Both halves are required for every stem —
    a row without ground truth has no `parameters` to copy, and a ground
    truth without a row has no bytes to hash.
    """
    dataset_dir = PurePosixPath(dataset_relpath)
    path = repo_root / dataset_relpath / DATASET_MANIFEST_FILENAME
    if not path.is_file():
        raise MissingInputs(f"{path} is not on disk; {SYNTH_SIGNALS_HINT}")
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    if not isinstance(doc, dict) or not isinstance(doc.get("files"), list):
        raise GenerateError(f"{path}: not a dataset manifest (no `files` list)")
    truths = doc.get("ground_truth", {}).get("files", {}) if isinstance(doc.get("ground_truth"), dict) else {}
    if not isinstance(truths, dict):
        raise GenerateError(f"{path}: `ground_truth.files` is not a mapping")
    entries: dict[str, DatasetEntry] = {}
    for k, row in enumerate(doc["files"]):
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise GenerateError(f"{path}: files[{k}] has no `path`")
        stem = PurePosixPath(row["path"]).stem
        truth = truths.get(stem)
        if not isinstance(truth, dict):
            raise GenerateError(f"{path}: files[{k}] ({row['path']}) has no ground_truth.files.{stem} record")
        for key in ("sha256", "sample_rate", "channels", "bit_depth"):
            if key not in row:
                raise GenerateError(f"{path}: files[{k}] ({row['path']}) lacks `{key}`")
        if not isinstance(truth.get("generator"), str) or not isinstance(truth.get("parameters"), dict):
            raise GenerateError(f"{path}: ground_truth.files.{stem} lacks `generator` or `parameters`")
        entries[stem] = DatasetEntry(
            stem=stem,
            relpath=(dataset_dir / row["path"]).as_posix(),
            sha256=str(row["sha256"]),
            sample_rate=int(row["sample_rate"]),
            channels=int(row["channels"]),
            bit_depth=int(row["bit_depth"]),
            generator=truth["generator"],
            parameters=dict(truth["parameters"]),
            host_only=bool(truth.get("host_only", False)),
        )
    return entries


def resolve_inputs(repo_root: Path, spec: SetSpec) -> list[DatasetEntry]:
    """The spec's inputs as dataset entries, every WAV present and hashing to its manifest row."""
    entries = load_dataset_manifest(repo_root, spec.dataset)
    unknown = [s for s in spec.inputs if s not in entries]
    if unknown:
        raise GenerateError(f"set {spec.name!r} names inputs the dataset manifest does not list: {unknown}")
    chosen = [entries[s] for s in spec.inputs]
    missing = [e.relpath for e in chosen if not (repo_root / e.relpath).is_file()]
    if missing:
        raise MissingInputs(f"{len(missing)} input WAV(s) not on disk under {repo_root} (first: {missing[0]}); {SYNTH_SIGNALS_HINT}")
    for entry in chosen:
        actual = sha256_file(repo_root / entry.relpath)
        if actual != entry.sha256:
            raise InputDigestMismatch(
                f"{entry.relpath}: sha256 on disk is {actual}, the dataset manifest records {entry.sha256} — "
                "the WAV is not the one the manifest describes; regenerate the dataset (synth_signals generate) "
                "or fix its manifest, never the golden set"
            )
    return chosen


# --- running the analyses --------------------------------------------------------------


@dataclass
class DecodedInput:
    """One input, decoded once; the parselmouth Sound is built lazily and shared by the Praat blocks."""

    entry: DatasetEntry
    wav: WavFile
    _sound: parselmouth.Sound | None = None

    @property
    def sound(self) -> parselmouth.Sound:
        if self._sound is None:
            self._sound = praat.sound_from_int16(self.wav.mono, self.wav.sample_rate, spectrum.DEFAULT_INT16_SCALE)
        return self._sound


def decode_input(repo_root: Path, entry: DatasetEntry) -> DecodedInput:
    """`wavio.read_wav` of the input, checked against the dataset manifest's header fields."""
    wav = read_wav(repo_root / entry.relpath)
    for name, recorded, actual in (
        ("sample_rate", entry.sample_rate, wav.sample_rate),
        ("channels", entry.channels, wav.channels),
        ("bit_depth", entry.bit_depth, wav.bit_depth),
    ):
        if recorded != actual:
            raise InputDigestMismatch(f"{entry.relpath}: decoded {name} is {actual}, the dataset manifest records {recorded}")
    return DecodedInput(entry=entry, wav=wav)


def formant_columns(cfg: praat.FormantConfig) -> tuple[str, ...]:
    """`time, F1, B1, …, F<slots>, B<slots>` — the layout `praat.formant_track` returns."""
    cols = ["time"]
    for k in range(1, cfg.formant_slots + 1):
        cols.extend((f"F{k}", f"B{k}"))
    return tuple(cols)


def run_analysis(analysis: str, cfg: object, decoded: DecodedInput) -> tuple[np.ndarray, str, tuple[str, ...]]:
    """Run one analysis block on one input → (float64 C-order array, units, columns)."""
    if analysis == "spectrum":
        assert isinstance(cfg, spectrum.SpectrumConfig)
        arr = spectrum.reference_spectrum(decoded.wav.mono, decoded.wav.sample_rate, cfg)
        units = f"Hz, dB re full-scale {cfg.dbfs_reference}" + (" per Hz" if cfg.level_unit.endswith("/Hz") else "")
        return np.ascontiguousarray(arr, dtype=np.float64), units, SPECTRUM_COLUMNS
    if analysis == "pitch":
        assert isinstance(cfg, praat.PitchConfig)
        arr = praat.pitch_track(decoded.sound, cfg)
        return np.ascontiguousarray(arr, dtype=np.float64), PITCH_UNITS, PITCH_COLUMNS
    if analysis == "formant":
        assert isinstance(cfg, praat.FormantConfig)
        arr = praat.formant_track(decoded.sound, cfg)
        cols = formant_columns(cfg)
        return np.ascontiguousarray(arr, dtype=np.float64), "s" + ", Hz" * (len(cols) - 1), cols
    if analysis == "ltas":
        assert isinstance(cfg, praat.LtasConfig)
        arr = praat.ltas(decoded.sound, cfg)
        return np.ascontiguousarray(arr, dtype=np.float64), LTAS_UNITS, LTAS_COLUMNS
    raise GenerateError(f"analysis {analysis!r} has no generator (spectrogram goldens are roadmap H1)")


def output_filename(analysis: str, stem: str) -> str:
    return f"{analysis}_{stem}.npy"


def save_array(path: Path, arr: np.ndarray) -> None:
    """`numpy.save(allow_pickle=False)` of a float64 C-order array — `.npy` format 1.0 for these shapes."""
    arr = np.ascontiguousarray(arr, dtype=np.float64)
    if arr.ndim == 0 or arr.size == 0:
        raise GenerateError(f"{path}: refusing to write an empty array ({arr.shape})")
    with open(path, "wb") as fh:
        np.save(fh, arr, allow_pickle=False)


# --- the manifest -----------------------------------------------------------------------


def tolerances_revision(repo_root: Path) -> str:
    """`git log -1 --format=%H -- docs/validation/golden-files.md`: the last commit that touched the tolerance table."""
    proc = subprocess.run(
        ["git", "-C", os.fspath(repo_root), "log", "-1", "--format=%H", "--", TOLERANCES_SOURCE],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GenerateError(f"git log for {TOLERANCES_SOURCE} failed in {repo_root}: {proc.stderr.strip()}")
    sha = proc.stdout.strip()
    if len(sha) != 40:
        raise GenerateError(f"{TOLERANCES_SOURCE} has no commit in {repo_root}; the tolerance table must be committed before a set is accepted against it")
    return sha


def windows_block(spec: SetSpec) -> list[dict[str, object]]:
    """One `windows[]` entry per (family, N): coefficients from the §4.3 table, digest per ADR 0006 D1."""
    block = []
    for n in spec.window_sizes:
        for family in spec.window_families:
            block.append(
                {
                    "family": family,
                    "n": int(n),
                    "coefficients": spectrum.window_coefficients(family),
                    "sha256": spectrum.window_table_sha256(family, int(n)),
                }
            )
    return block


def input_entry(decoded: DecodedInput) -> dict[str, object]:
    e, wav = decoded.entry, decoded.wav
    return {
        "path": e.relpath,
        "sha256": e.sha256,
        "sample_rate": int(wav.sample_rate),
        "bit_depth": int(wav.bit_depth),
        "channels": int(wav.channels),
        "duration_s": wav.duration_s,
        "source": {"kind": SOURCE_KIND, "name": e.generator, "parameters": e.parameters},
    }


def utc_today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


# --- the generator ------------------------------------------------------------------------


def generate_set(
    name: str,
    repo_root: str | os.PathLike[str],
    approved_by: str,
    reason: str,
    allow_dirty: bool = False,
    *,
    log: object = None,
) -> Path:
    """Write the golden set `name` under `<repo_root>/host/golden/outputs/<name>/` and return its manifest path.

    Refuses (raising a `GenerateError` subclass, nothing written) an unknown
    set, an existing set directory, missing or drifted inputs, and a dirty
    package tree unless `allow_dirty`. After writing, runs every `verify`
    rule on the result and raises `VerificationFailed` if any fires.
    `log`, if given, is a callable taking one line of progress text.
    """
    say = log if callable(log) else (lambda _line: None)
    root = Path(repo_root).resolve()
    if not approved_by.strip() or not reason.strip():
        raise GenerateError("approved_by and reason are required, in prose a reviewer can disagree with (ADR 0009 decision 4)")
    try:
        spec = sets_mod.get_set(name)
    except KeyError as exc:
        raise GenerateError(str(exc)) from None

    set_dir = root / manifest_mod.OUTPUTS_RELPATH / spec.name
    if set_dir.exists():
        raise ExistingSet(
            f"{set_dir} exists: a golden set is never edited or re-emitted in place — a pin change is a NEW set "
            "under a new name (ADR 0009 decision 4); remove the directory deliberately if this is a do-over"
        )

    # 2. chain of custody before anything else is touched
    entries = resolve_inputs(root, spec)
    say(f"{len(entries)} inputs verified against {spec.dataset}/{DATASET_MANIFEST_FILENAME}")

    # 3. what ran
    dirty = env_mod.is_dirty(root, [env_mod.PACKAGE_RELPATH])
    if dirty and not allow_dirty:
        raise DirtyGenerator(
            f"{env_mod.PACKAGE_RELPATH} has uncommitted changes: generator.sha256 would describe bytes no commit "
            "contains and generator.commit would misstate what ran; commit first, or pass allow_dirty=True "
            "and say why in --reason"
        )
    generator = env_mod.capture(root, praat_reference=None)
    revision = tolerances_revision(root)

    # 4. decode once
    decoded = [decode_input(root, e) for e in entries]

    # 5. arrays
    set_dir.mkdir(parents=True, exist_ok=False)
    by_stem = {d.entry.stem: d for d in decoded}
    outputs: list[dict[str, object]] = []
    for analysis, stem in spec.planned_outputs():
        arr, units, columns = run_analysis(analysis, spec.analyses[analysis], by_stem[stem])
        path = set_dir / output_filename(analysis, stem)
        save_array(path, arr)
        entry: dict[str, object] = {
            "path": (PurePosixPath(manifest_mod.OUTPUTS_RELPATH) / spec.name / path.name).as_posix(),
            "sha256": sha256_file(path),
            "analysis": analysis,
            "input": by_stem[stem].entry.relpath,
            "dtype": str(arr.dtype),
            "shape": [int(s) for s in arr.shape],
            "units": units,
            "columns": list(columns),
        }
        if analysis == "pitch":
            entry["unvoiced_sentinel"] = int(praat.UNVOICED_SENTINEL)
        outputs.append(entry)
        say(f"wrote {path.name} {list(arr.shape)}")

    notes = spec.notes
    if dirty:
        notes = (notes + " " if notes else "") + (
            f"GENERATED FROM A DIRTY {env_mod.PACKAGE_RELPATH}: generator.sha256 is the GENERATOR_TREE on disk at generation "
            "time; generator.commit is HEAD and does not contain it (allow_dirty was passed; see regeneration.reason)."
        )

    # 7./8. the manifest, in schema order
    today = utc_today()
    doc: dict[str, object] = {
        "schema": manifest_mod.SCHEMA_VERSION,
        "set": spec.name,
        "generated": today,
        "generator": generator.asdict(),
        "inputs": [input_entry(d) for d in decoded],
        "analyses": spec.analyses_asdict(),
    }
    windows = windows_block(spec)
    if windows:
        doc["windows"] = windows
    doc["outputs"] = outputs
    doc["tolerances"] = {"source": TOLERANCES_SOURCE, "revision": revision}
    doc["regeneration"] = {
        "date": today,
        "reason": reason,
        "approved_by": approved_by,
        "previous_manifest_sha256": None,
        "previous_set": None,
    }
    if notes:
        doc["notes"] = notes

    manifest_path = manifest_mod.manifest_path(root, spec.name)
    manifest_path.write_bytes(manifest_mod.dump(doc))
    say(f"wrote {manifest_path.relative_to(root)}")

    notices: list[str] = []
    failures = verify_mod.verify_manifest(manifest_path, root, check_env=True, notices=notices)
    for note in notices:
        say(f"notice: {note}")
    if failures:
        raise VerificationFailed(set_dir, failures)
    say(f"verify: ok ({len(verify_mod.RULES)} rules)")
    return manifest_path


# --- CLI -------------------------------------------------------------------


def add_generate_arguments(parser: argparse.ArgumentParser) -> None:
    """The `generate` arguments, shared by this module's CLI and `spectral-golden generate`."""
    parser.add_argument("--set", dest="set_name", required=True, metavar="NAME", help=f"one of {sorted(sets_mod.SETS)}")
    parser.add_argument("--approved-by", required=True, metavar="WHO", help="the human who reviews the manifest diff")
    parser.add_argument("--reason", required=True, help='why, in prose ("initial generation" for a first set)')
    parser.add_argument("--repo-root", type=Path, default=None, help="repository root (default: search upward from the working directory)")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help=f"proceed although {env_mod.PACKAGE_RELPATH} has uncommitted changes (recorded in the manifest notes)",
    )


def run_generate(set_name: str, approved_by: str, reason: str, repo_root: Path | None, allow_dirty: bool) -> int:
    """The body of `spectral-golden generate`: 0 written and verified, 1 written but red, 2 refused."""
    try:
        root = repo_root.resolve() if repo_root is not None else verify_mod.default_repo_root()
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        manifest_path = generate_set(set_name, root, approved_by, reason, allow_dirty, log=print)
    except VerificationFailed as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (GenerateError, OSError, ValueError, TypeError, parselmouth.PraatError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"{manifest_path}: ok")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m spectral_host.golden.generate",
        description="Write a NEW golden set (arrays + manifest) and verify it. Refuses an existing set directory.",
    )
    add_generate_arguments(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_generate(args.set_name, args.approved_by, args.reason, args.repo_root, args.allow_dirty)


if __name__ == "__main__":
    sys.exit(main())
