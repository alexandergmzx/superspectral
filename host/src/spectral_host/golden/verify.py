# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""`verify` — the invariants a golden manifest must satisfy beyond its schema. Never writes.

ADR 0009 decision 1 ends with "a manifest that validates is a necessary
condition, never a sufficient one", and decision 4 says what happens next:
`verify` runs in CI, recomputes every digest, re-reads the installed pins, and
"any drift → exit 1. It never regenerates. A red verify is a decision request
addressed to a human, not a task for a script." This module is that step. It
opens files for reading only; there is no code path that writes, and
`test_verify_never_writes` checks the bytes it was given are the bytes it left.

Each rule has a number, the way `python-scripts/check_presets.py` numbers the
preset loader's rules V0–V10, and for the same reason: a rule that fires is
reported BY NUMBER so a reviewer can find it here, in the schema's header
comment ("WHAT THIS SCHEMA CANNOT EXPRESS", invariants 1–8) and in ADR 0009,
and the negative suite in host/tests/test_manifest_verify.py asserts, per
mutation, that the OWNING rule fires — even where the schema would also have
caught it. `Failure(rule, message)` is the same shape as check_presets'.

  S   the schema (manifest.schema.yaml, draft 2020-12), AND `schema:` is the
      string "1.1" exactly — a reader accepts one value (ADR 0009 amendment).
  I1  `analyses.pitch.pitch_floor` < `pitch_ceiling`           (schema note 1)
  I2  every `outputs[].input` names an `inputs[].path`          (note 2)
  I3  every `outputs[].analysis` names a key of `analyses`      (note 3)
  I4  every recorded sha256 — `inputs[]`, `outputs[]`, `generator` — equals
      the digest of the bytes on disk, relative to the repository root
      (note 4). For `generator`, `script` must be `env.PACKAGE_RELPATH` and
      the digest is recomputed exactly as the generator computed it:
      `env.generator_sha256` = `hashing.sha256_files` over `env.GENERATOR_TREE`
      (the numerics-bearing modules, not the whole package — see env.py).
      A manifest whose `script` names anything else fails I4: the digest
      would have no stated recipe.
  I5  the INSTALLED `parselmouth`, `parselmouth.PRAAT_VERSION`, `numpy` and
      `scipy` equal the manifest's `generator.*` (note 5). Drift here means
      regenerate, not patch — ADR 0009 decision 4, verbatim. `check_env=False`
      skips this rule only (for a checkout that is not the generating
      environment) and says so in a notice.
  I6  `analyses.pitch.method == "filtered"` requires
      `generator.praat_bundled` ≥ 6.4.0 as a version tuple (note 6; the
      method did not exist before Praat 6.4, 2023-11-15).
  I7  every `windows[].sha256` is RECOMPUTED — sha256 over the N float32
      little-endian samples of the periodic window built from the entry's own
      `coefficients` (`general_cosine(n, a, sym=False)`) — and must match;
      AND `coefficients` equal `spectrum.WINDOW_FAMILIES[family]`, the
      preset-schema §4.3 table, term for term (note 7; ADR 0006 D1). When the
      coefficients are the table's, the recomputed value is by construction
      `spectrum.window_table_sha256(family, n)` and that function is what is
      called; when they are not, the digest is still recomputed from what
      was recorded so the message can say WHICH half drifted.
  I8  an entry of `windows[]` exists for the pair
      (`analyses.spectrum.window`, `window_length_samples`) whenever
      `analyses.spectrum` is present (note 8).
  N1  every `outputs[].path` loads with `numpy.load(allow_pickle=False)` and
      its dtype and shape equal the recorded `dtype` / `shape`. A pickled
      object array is refused by the loader and reported here.
  N2  every `analysis: pitch` output carries `unvoiced_sentinel` — the
      schema leaves it optional because the other analyses have none, and a
      0 silently read as a frequency destroys a cents comparison.
  N3  every `outputs[].path` lives under `host/golden/outputs/<set>/` — the
      set's name is its directory (schema `set` description) and an output
      filed under another set's name would be verified by its manifest too.
  N4  the manifest file begins with the two GPL SPDX lines (ADR 0004: host/
      is GPL as a directory; `manifest.dump` writes them first).
  G1  `tolerances.revision` is an object this checkout has (`git cat-file
      -e`). Outside a git checkout, or in a shallow clone that cannot hold
      the object, the rule is SKIPPED WITH A NOTICE rather than failed: a
      missing `.git` says nothing about the manifest.

Rules run independently, every one of them, whatever S said — a manifest
with a schema error can still tell you its digests are stale, and a rule
that cannot run because a field is absent stays silent (S reported the
absence). A rule that raises anything else is reported as `?` with the
exception, never swallowed.

CLI (wired by `spectral-golden verify`; see cli.py):

    uv run --project host python -m spectral_host.golden.verify [--repo-root DIR] [--no-env-check] [MANIFEST ...]

Default manifests: every `host/golden/outputs/*/manifest.yaml`. Exit 0 when
every rule of every manifest passes, 1 on any Failure, 2 on a usage error
(no repository root). Prints `<manifest>: <rule>: <message>` per failure.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import numpy
import numpy as np
import parselmouth
import scipy
from scipy.signal.windows import general_cosine

from spectral_host import spectrum
from spectral_host.golden import manifest as manifest_mod
from spectral_host import env as env_mod
from spectral_host.hashing import sha256_file
from spectral_host.praat import FILTERED_AC_MIN_PRAAT, praat_version_tuple

#: Praat release that introduced the filtered method — `praat.FILTERED_AC_MIN_PRAAT`,
#: (6, 4). The COMPARISON uses the two-place tuple: Python orders a shorter tuple
#: before its own extension, so `(6, 4) < (6, 4, 0)` is True and a manifest
#: recording `praat_bundled: "6.4"` (the schema's `$defs/version` is deliberately
#: unpatterned) would have been refused by a three-place bound. The message
#: prints the three-place form the schema note states.
FILTERED_MIN_PRAAT_BUNDLED: tuple[int, int, int] = (*FILTERED_AC_MIN_PRAAT, 0)

#: The `generator` fields rule I5 compares against the installed environment,
#: with the reader of each installed value. `praat_bundled` is the one that
#: matters (ADR 0009 context); the other three fix array/reduction behaviour.
ENV_PINS: tuple[tuple[str, Callable[[], str]], ...] = (
    ("parselmouth", lambda: str(parselmouth.__version__)),
    ("praat_bundled", lambda: str(parselmouth.PRAAT_VERSION)),
    ("numpy", lambda: str(numpy.__version__)),
    ("scipy", lambda: str(scipy.__version__)),
)


class Failure(Exception):
    """A rule violation. `rule` is the number that owns it (S, I1–I8, N1–N4, G1)."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(message)
        self.rule = rule
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - formatting only
        return "%s: %s" % (self.rule, self.message)


@dataclass
class Context:
    """What every rule sees: the parsed document, the raw bytes, where it came from, and the switches."""

    doc: object
    raw: bytes
    path: Path
    repo_root: Path
    check_env: bool = True
    schema: dict | None = None
    notices: list[str] = field(default_factory=list)

    def notice(self, text: str) -> None:
        self.notices.append(text)

    def resolve(self, relpath: str) -> Path:
        """A repository-relative manifest path on this disk. Absolute paths are used as given."""
        p = Path(relpath)
        return p if p.is_absolute() else self.repo_root / p


# --- small accessors: a rule that cannot run because a field is absent stays silent ---


def _doc(ctx: Context) -> dict:
    return ctx.doc if isinstance(ctx.doc, dict) else {}


def _list(doc: dict, key: str) -> list[dict]:
    value = doc.get(key)
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _mapping(doc: dict, *keys: str) -> dict:
    node: object = doc
    for key in keys:
        if not isinstance(node, dict):
            return {}
        node = node.get(key)
    return node if isinstance(node, dict) else {}


def _is_number(v: object) -> bool:
    return isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool)


def _is_int(v: object) -> bool:
    return isinstance(v, (int, np.integer)) and not isinstance(v, bool)


def window_digest(coefficients: Sequence[float], n: int) -> str:
    """The schema's `windows[].sha256` recipe from coefficients alone (manifest.schema.yaml `windows`).

    `hashlib.sha256(np.asarray(general_cosine(N, a, sym=False), dtype="<f4").tobytes()).hexdigest()`
    — kept separate from `spectrum.window_table_sha256` (which is keyed by
    family) so rule I7 can recompute a digest from coefficients the table does
    NOT contain and report it as such.
    """
    w = general_cosine(int(n), [float(c) for c in coefficients], sym=False)
    return hashlib.sha256(np.asarray(w, dtype="<f4").tobytes()).hexdigest()


def load_schema_for(repo_root: Path) -> dict:
    """The checkout's schema (`repo_root / host/golden/manifest.schema.yaml`), or the package's own copy if the root has none."""
    candidate = Path(repo_root) / manifest_mod.SCHEMA_RELPATH
    return manifest_mod.load_schema(candidate if candidate.is_file() else None)


# --- the rules -------------------------------------------------------------


def check_s_schema(ctx: Context) -> list[Failure]:
    """S — the schema, and `schema == "1.1"` exactly."""
    failures: list[Failure] = []
    if not isinstance(ctx.doc, dict):
        return [Failure("S", f"manifest is not a mapping (YAML resolved it to {type(ctx.doc).__name__})")]
    version = ctx.doc.get("schema")
    version_ok = isinstance(version, str) and version == manifest_mod.SCHEMA_VERSION
    if not version_ok:
        failures.append(
            Failure(
                "S",
                f"schema is {version!r} ({type(version).__name__}); this reader accepts exactly "
                f"the string {manifest_mod.SCHEMA_VERSION!r} — an integer 1 or another MAJOR.MINOR is refused, never coerced",
            )
        )
    schema = ctx.schema if ctx.schema is not None else load_schema_for(ctx.repo_root)
    for problem in manifest_mod.validate(ctx.doc, schema):
        if not version_ok and problem.startswith("$.schema:"):
            continue  # already reported above, in this rule's own words
        failures.append(Failure("S", problem))
    return failures


def check_i1_floor_below_ceiling(ctx: Context) -> list[Failure]:
    pitch = _mapping(_doc(ctx), "analyses", "pitch")
    floor, ceiling = pitch.get("pitch_floor"), pitch.get("pitch_ceiling")
    if _is_number(floor) and _is_number(ceiling) and not floor < ceiling:
        return [Failure("I1", f"analyses.pitch.pitch_floor {floor} is not below pitch_ceiling {ceiling}")]
    return []


def check_i2_outputs_name_inputs(ctx: Context) -> list[Failure]:
    doc = _doc(ctx)
    known = {i.get("path") for i in _list(doc, "inputs")}
    failures = []
    for k, out in enumerate(_list(doc, "outputs")):
        inp = out.get("input")
        if inp is not None and inp not in known:
            failures.append(Failure("I2", f"outputs[{k}].input {inp!r} is not an inputs[].path"))
    return failures


def check_i3_outputs_name_analyses(ctx: Context) -> list[Failure]:
    doc = _doc(ctx)
    analyses = _mapping(doc, "analyses")
    failures = []
    for k, out in enumerate(_list(doc, "outputs")):
        analysis = out.get("analysis")
        if analysis is not None and analysis not in analyses:
            failures.append(Failure("I3", f"outputs[{k}].analysis {analysis!r} has no analyses.{analysis} block"))
    return failures


def _digest_on_disk(ctx: Context, relpath: str) -> str | None:
    """sha256 of a file's bytes; None if it is not on disk (inputs and outputs are always files)."""
    target = ctx.resolve(relpath)
    if target.is_file():
        return sha256_file(target)
    return None


def _generator_digest_on_disk(ctx: Context) -> str | None:
    """`env.generator_sha256` over the checkout, or None if a listed module is missing."""
    try:
        return env_mod.generator_sha256(ctx.repo_root)
    except FileNotFoundError:
        return None


def check_i4_digests_match_disk(ctx: Context) -> list[Failure]:
    doc = _doc(ctx)
    failures = []
    entries: list[tuple[str, object, object]] = []
    for k, inp in enumerate(_list(doc, "inputs")):
        entries.append((f"inputs[{k}]", inp.get("path"), inp.get("sha256")))
    for k, out in enumerate(_list(doc, "outputs")):
        entries.append((f"outputs[{k}]", out.get("path"), out.get("sha256")))
    generator = _mapping(doc, "generator")
    script, recorded = generator.get("script"), generator.get("sha256")
    if isinstance(script, str) and isinstance(recorded, str):
        if script != env_mod.PACKAGE_RELPATH:
            failures.append(
                Failure(
                    "I4",
                    f"generator.script {script!r} is not {env_mod.PACKAGE_RELPATH!r}: the digest recipe "
                    f"(env.GENERATOR_TREE) is defined for that package only",
                )
            )
        else:
            actual = _generator_digest_on_disk(ctx)
            if actual is None:
                failures.append(Failure("I4", f"generator: a module of env.GENERATOR_TREE is missing under {ctx.repo_root}"))
            elif actual != recorded:
                failures.append(
                    Failure(
                        "I4",
                        f"generator: {env_mod.PACKAGE_RELPATH} GENERATOR_TREE hash is {actual}, manifest records {recorded}",
                    )
                )
    for label, relpath, recorded in entries:
        if not isinstance(relpath, str) or not isinstance(recorded, str):
            continue  # S reports the missing/typed field
        parts = PurePosixPath(relpath).parts
        if PurePosixPath(relpath).is_absolute() or ".." in parts:
            # The schema says "repository-relative" without a pattern; an absolute
            # path would verify on the generating machine and nowhere else.
            failures.append(Failure("I4", f"{label}: {relpath!r} is not a repository-relative path (absolute or contains '..')"))
            continue
        actual = _digest_on_disk(ctx, relpath)
        if actual is None:
            failures.append(Failure("I4", f"{label}: {relpath} is not on disk under {ctx.repo_root}"))
        elif actual != recorded:
            failures.append(Failure("I4", f"{label}: {relpath} sha256 is {actual}, manifest records {recorded}"))
    return failures


def check_i5_installed_pins(ctx: Context) -> list[Failure]:
    if not ctx.check_env:
        ctx.notice("I5 skipped (--no-env-check): installed parselmouth/Praat/numpy/scipy not compared with the manifest")
        return []
    generator = _mapping(_doc(ctx), "generator")
    failures = []
    for key, read_installed in ENV_PINS:
        recorded = generator.get(key)
        if recorded is None:
            continue
        installed = read_installed()
        if str(recorded) != installed:
            failures.append(
                Failure(
                    "I5",
                    f"generator.{key} records {recorded!r} but the installed environment is {installed!r}: "
                    "drift here means regenerate under a new set name, not patch (ADR 0009 decision 4)",
                )
            )
    return failures


def check_i6_filtered_needs_praat_6_4(ctx: Context) -> list[Failure]:
    doc = _doc(ctx)
    method = _mapping(doc, "analyses", "pitch").get("method")
    bundled = _mapping(doc, "generator").get("praat_bundled")
    if method != "filtered" or not isinstance(bundled, str):
        return []
    try:
        version = praat_version_tuple(bundled)
    except ValueError as exc:
        return [Failure("I6", f"analyses.pitch.method is 'filtered' but generator.praat_bundled is unparsable: {exc}")]
    if version < FILTERED_AC_MIN_PRAAT:  # (6, 4): see the note on FILTERED_MIN_PRAAT_BUNDLED
        return [
            Failure(
                "I6",
                f"analyses.pitch.method 'filtered' requires generator.praat_bundled >= "
                f"{'.'.join(map(str, FILTERED_MIN_PRAAT_BUNDLED))}; manifest records {bundled!r} "
                "(To Pitch (filtered autocorrelation) did not exist before Praat 6.4, 2023-11-15)",
            )
        ]
    return []


def check_i7_window_digests(ctx: Context) -> list[Failure]:
    failures = []
    for k, entry in enumerate(_list(_doc(ctx), "windows")):
        family, n, coefficients, recorded = (entry.get(key) for key in ("family", "n", "coefficients", "sha256"))
        if not (isinstance(family, str) and _is_int(n) and n >= 2 and isinstance(coefficients, list) and coefficients):
            continue  # S owns the shape
        if not all(_is_number(c) for c in coefficients):
            continue
        table = spectrum.WINDOW_FAMILIES.get(family)
        coeffs = [float(c) for c in coefficients]
        if table is None:
            failures.append(Failure("I7", f"windows[{k}].family {family!r} is not a §4.3 family (or rect)"))
            continue
        coefficients_match = coeffs == [float(c) for c in table]
        if not coefficients_match:
            failures.append(
                Failure(
                    "I7",
                    f"windows[{k}] ({family}, {n}): coefficients {coeffs} are not the preset-schema §4.3 table "
                    f"for {family}, {list(table)} (ADR 0006 D1: coefficients are the contract)",
                )
            )
        # Recompute. From the table's coefficients the recipe IS spectrum.window_table_sha256;
        # from foreign coefficients it is the same recipe over what was recorded.
        expected = spectrum.window_table_sha256(family, int(n)) if coefficients_match else window_digest(coeffs, int(n))
        if not isinstance(recorded, str) or recorded != expected:
            which = "its own coefficients" if not coefficients_match else f"the §4.3 {family} table"
            failures.append(
                Failure(
                    "I7",
                    f"windows[{k}] ({family}, {n}): sha256 recomputed from {which} is {expected}, "
                    f"manifest records {recorded!r}",
                )
            )
    return failures


def check_i8_spectrum_window_listed(ctx: Context) -> list[Failure]:
    doc = _doc(ctx)
    analyses = _mapping(doc, "analyses")
    if "spectrum" not in analyses:
        return []
    spec = _mapping(analyses, "spectrum")
    family, n = spec.get("window"), spec.get("window_length_samples")
    if not isinstance(family, str) or not _is_int(n):
        return []
    listed = {(w.get("family"), w.get("n")) for w in _list(doc, "windows")}
    if (family, n) not in listed:
        have = sorted(f"({f}, {m})" for f, m in listed if isinstance(f, str))
        return [
            Failure(
                "I8",
                f"analyses.spectrum uses ({family}, {n}) but windows[] has no entry for it"
                + (f"; entries: {', '.join(have)}" if have else "; windows[] is absent or empty"),
            )
        ]
    return []


def check_n1_npy_dtype_shape(ctx: Context) -> list[Failure]:
    failures = []
    for k, out in enumerate(_list(_doc(ctx), "outputs")):
        relpath, dtype, shape = out.get("path"), out.get("dtype"), out.get("shape")
        if not isinstance(relpath, str):
            continue
        target = ctx.resolve(relpath)
        if not target.is_file():
            continue  # I4 owns "not on disk"
        try:
            arr = np.load(target, allow_pickle=False)
        except (OSError, ValueError) as exc:
            failures.append(Failure("N1", f"outputs[{k}]: {relpath} does not load as a plain .npy (allow_pickle=False): {exc}"))
            continue
        if isinstance(dtype, str) and arr.dtype.name != dtype:
            failures.append(Failure("N1", f"outputs[{k}]: {relpath} dtype is {arr.dtype.name}, manifest records {dtype!r}"))
        if isinstance(shape, list) and list(arr.shape) != [int(s) for s in shape if _is_int(s)]:
            failures.append(Failure("N1", f"outputs[{k}]: {relpath} shape is {list(arr.shape)}, manifest records {shape}"))
    return failures


def check_n2_pitch_sentinel(ctx: Context) -> list[Failure]:
    failures = []
    for k, out in enumerate(_list(_doc(ctx), "outputs")):
        if out.get("analysis") == "pitch" and "unvoiced_sentinel" not in out:
            failures.append(
                Failure("N2", f"outputs[{k}] ({out.get('path')}): analysis 'pitch' without unvoiced_sentinel — a 0 would read as 0 Hz")
            )
    return failures


def check_n3_outputs_under_set_dir(ctx: Context) -> list[Failure]:
    doc = _doc(ctx)
    set_name = doc.get("set")
    if not isinstance(set_name, str) or not set_name:
        return []
    expected = PurePosixPath(manifest_mod.OUTPUTS_RELPATH) / set_name
    failures = []
    for k, out in enumerate(_list(doc, "outputs")):
        relpath = out.get("path")
        if not isinstance(relpath, str):
            continue
        p = PurePosixPath(relpath)
        inside = (
            not p.is_absolute()
            and ".." not in p.parts
            and len(p.parts) > len(expected.parts)
            and p.parts[: len(expected.parts)] == expected.parts
        )
        if not inside:
            failures.append(
                Failure("N3", f"outputs[{k}].path {relpath!r} is not under {expected}/ (the set's own output directory)")
            )
    return failures


def check_n4_spdx_lines(ctx: Context) -> list[Failure]:
    try:
        text = ctx.raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [Failure("N4", f"manifest is not UTF-8: {exc}")]
    head = text.splitlines()[:2]
    if head != list(manifest_mod.SPDX_LINES):
        return [
            Failure(
                "N4",
                "manifest does not begin with the two GPL SPDX lines "
                f"{list(manifest_mod.SPDX_LINES)} (ADR 0004: host/ is GPL-3.0-or-later as a directory); first lines: {head}",
            )
        ]
    return []


def _git(ctx: Context, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(["git", "-C", os.fspath(ctx.repo_root), *args], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None


def check_g1_tolerance_revision_resolves(ctx: Context) -> list[Failure]:
    revision = _mapping(_doc(ctx), "tolerances").get("revision")
    if not isinstance(revision, str) or not revision:
        return []
    probe = _git(ctx, "rev-parse", "--is-shallow-repository")
    if probe is None:
        ctx.notice("G1 skipped: git is not installed; tolerances.revision not checked")
        return []
    if probe.returncode != 0:
        ctx.notice(f"G1 skipped: {ctx.repo_root} is not a git checkout; tolerances.revision {revision[:12]} not checked")
        return []
    exists = _git(ctx, "cat-file", "-e", revision)
    if exists is not None and exists.returncode == 0:
        return []
    if probe.stdout.strip() == "true":
        ctx.notice(f"G1 skipped: shallow clone cannot hold tolerances.revision {revision[:12]}; unshallow to check it")
        return []
    return [Failure("G1", f"tolerances.revision {revision} is not an object in this checkout (git cat-file -e failed)")]


#: Every rule, in report order. The negative suite asserts each is reached.
RULES: tuple[tuple[str, Callable[[Context], list[Failure]]], ...] = (
    ("S", check_s_schema),
    ("I1", check_i1_floor_below_ceiling),
    ("I2", check_i2_outputs_name_inputs),
    ("I3", check_i3_outputs_name_analyses),
    ("I4", check_i4_digests_match_disk),
    ("I5", check_i5_installed_pins),
    ("I6", check_i6_filtered_needs_praat_6_4),
    ("I7", check_i7_window_digests),
    ("I8", check_i8_spectrum_window_listed),
    ("N1", check_n1_npy_dtype_shape),
    ("N2", check_n2_pitch_sentinel),
    ("N3", check_n3_outputs_under_set_dir),
    ("N4", check_n4_spdx_lines),
    ("G1", check_g1_tolerance_revision_resolves),
)

RULE_NAMES: tuple[str, ...] = tuple(rule for rule, _ in RULES)


def apply_rules(ctx: Context) -> list[Failure]:
    """Run every rule; a rule that raises something other than Failure is reported as `?`, never swallowed."""
    failures: list[Failure] = []
    for rule, fn in RULES:
        try:
            failures.extend(fn(ctx))
        except Failure as exc:
            failures.append(exc)
        except Exception as exc:  # noqa: BLE001 - a crashing rule is a finding, not a pass
            failures.append(Failure("?", f"rule {rule} raised {type(exc).__name__}: {exc}"))
    return failures


def verify_manifest(
    path: str | os.PathLike[str],
    repo_root: str | os.PathLike[str],
    check_env: bool = True,
    *,
    schema: dict | None = None,
    notices: list[str] | None = None,
) -> list[Failure]:
    """Every rule against the manifest at `path`, paths resolved under `repo_root`. Reads only.

    `schema` defaults to `repo_root / host/golden/manifest.schema.yaml`, falling back to
    the package's own copy (`manifest.default_schema_path`) when the root has none —
    a test fixture that builds a repository layout in a temporary directory does not
    carry the schema. `notices`, if given, collects the skip notices (I5 off, G1
    outside a checkout) so a caller can print them; they are never failures.
    """
    manifest_file = Path(path)
    root = Path(repo_root)
    raw = manifest_file.read_bytes()
    try:
        doc = manifest_mod.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, manifest_mod.ManifestError) as exc:
        return [Failure("S", f"manifest cannot be parsed: {exc}")]
    if schema is None:
        schema = load_schema_for(root)
    ctx = Context(doc=doc, raw=raw, path=manifest_file, repo_root=root, check_env=check_env, schema=schema)
    failures = apply_rules(ctx)
    if notices is not None:
        notices.extend(ctx.notices)
    return failures


# --- CLI -------------------------------------------------------------------


def find_repo_root(start: Path) -> Path:
    """Walk up from `start` to the directory holding CLAUDE.md and the manifest schema."""
    for candidate in (start, *start.parents):
        if (candidate / "CLAUDE.md").is_file() and (candidate / manifest_mod.SCHEMA_RELPATH).is_file():
            return candidate
    raise FileNotFoundError(f"no repository root (CLAUDE.md + {manifest_mod.SCHEMA_RELPATH}) above {start}")


def default_repo_root() -> Path:
    """The checkout: upward from the working directory first, then from this file."""
    try:
        return find_repo_root(Path.cwd().resolve())
    except FileNotFoundError:
        return find_repo_root(Path(__file__).resolve().parent)


def add_verify_arguments(parser: argparse.ArgumentParser) -> None:
    """The `verify` arguments, shared by this module's CLI and `spectral-golden verify`."""
    parser.add_argument(
        "manifests",
        metavar="MANIFEST",
        nargs="*",
        type=Path,
        help=f"manifest files (default: every {manifest_mod.OUTPUTS_RELPATH}/*/{manifest_mod.MANIFEST_FILENAME})",
    )
    parser.add_argument("--repo-root", type=Path, default=None, help="repository root (default: search upward from the working directory)")
    parser.add_argument(
        "--no-env-check",
        dest="check_env",
        action="store_false",
        help="skip rule I5 (installed parselmouth/Praat/numpy/scipy vs the manifest); printed as a notice",
    )


def run_verify(manifests: Sequence[Path], repo_root: Path | None, check_env: bool) -> int:
    """The body of `spectral-golden verify`: 0 clean, 1 on any Failure, 2 on a usage error."""
    try:
        root = repo_root.resolve() if repo_root is not None else default_repo_root()
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    targets = list(manifests) if manifests else manifest_mod.discover_manifests(root)
    if not targets:
        print(f"no manifests under {root / manifest_mod.OUTPUTS_RELPATH}; nothing to verify")
        return 0
    status = 0
    for target in targets:
        notices: list[str] = []
        try:
            failures = verify_manifest(target, root, check_env=check_env, notices=notices)
        except OSError as exc:
            print(f"{target}: error: {exc}")
            status = 1
            continue
        for note in notices:
            print(f"{target}: notice: {note}")
        if failures:
            status = 1
            for failure in failures:
                print(f"{target}: {failure.rule}: {failure.message}")
            print(f"{target}: FAIL ({len(failures)} failure{'s' if len(failures) != 1 else ''})")
        else:
            print(f"{target}: ok ({len(RULES)} rules)")
    return status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m spectral_host.golden.verify",
        description="Verify golden manifests: schema, cross-field invariants, digests on disk, installed pins. Never writes.",
    )
    add_verify_arguments(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_verify(args.manifests, args.repo_root, args.check_env)


if __name__ == "__main__":
    sys.exit(main())
