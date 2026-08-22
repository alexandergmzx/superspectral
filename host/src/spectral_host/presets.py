# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""The host preset loader — identity, canonical bytes and the window arithmetic of a preset (ADR 0010).

A preset is the one file the watch and the host must read identically: a take
names its preset by `id` AND by the sha256 of the preset file's bytes
(protocols/specs/preset-schema.md §3, TAKE_HEADER kind 0x01), and every level
the host later computes for that take depends on the window constants the
preset carries. This module is what the GPL half uses to turn a preset file
into (a) an identity it can match against a take and (b) a `SpectrumConfig`
for `spectrum.reference_spectrum()`.

Rule numbers are SHARED. V0, V1, V8 and V9 below carry the numbers of
protocols/specs/preset-schema.md §6 — the same numbers python-scripts/
check_presets.py (Apache-2.0) and the C loader in `spectral_core` use — so a
rejection reads the same in every log. The division of labour is deliberate:

  * The FULL V-suite (schema validation, V2–V7, V10, the negative cases and
    the coverage assertion) is the Apache checker's job, in the `python-scripts`
    CI job and the `presets-rules` pre-commit hook. It is the validator of
    record; nothing here replaces it.
  * This module RE-IMPLEMENTS — never imports — the four rules the host's own
    correctness rests on. ADR 0004 item 3: nothing under host/ imports anything
    from python-scripts/, and the two exchange files on disk only. The preset
    JSON IS that file. A reviewer can diff the two implementations; they must
    agree, and host/tests/test_presets.py checks this one against the shipped
    six and against the same byte-level mutations the checker's regression
    guards use.

The four rules, as enforced here (`load_preset` raises `PresetRejected(rule,
message)` on the first one that fails, in this order):

  V0  the file's bytes are exactly the canonical form of §3: UTF-8 without a
      BOM, LF line endings, no trailing whitespace, exactly one trailing
      newline, and byte-equal to
      `json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\\n"`;
      every JSON number is decimal, no exponent, no leading `+`, no trailing
      `.`, at most six decimal places. A file that does not parse as JSON is
      reported under V0 too — it cannot be its own canonical form. The sha256
      is over these bytes and nothing is re-serialised to compute it (ADR 0010
      decision 6).
  V1  `id` equals the file's basename without `.json`.
  V8  `window.name` is one of the six §4.3 preset families (`rect` is a golden-
      manifest family only — ADR 0006 consequence (c) — and is rejected here as
      the C loader rejects wire value 0); `window.coefficients` equal
      `spectrum.WINDOW_FAMILIES[name]` term for term; and `coherent_gain`,
      `coherent_gain_db`, `enbw_bins` are RECOMPUTED to 1×10⁻⁶ from the
      periodic window itself — `spectrum.window_sums(spectrum.window_float64(
      name, fft_size))`, i.e. S1/N, 20·log10(S1/N) and N·S2/S1² — not from the
      closed form. ONE TABLE, BOTH USES: the array whose sums are checked here
      is the array `spectrum.reference_spectrum()` multiplies by, so a preset
      accepted by V8 is a preset whose constants describe the window the host
      will actually use. (ADR 0006 D2 proves the sums equal the closed form
      `(a₀² + Σ a_k²/2)/a₀²` for the periodic form; the tests assert both.)
      `window.form` must be `periodic` — the schema's `const` owns that, but
      the recomputation presupposes it, so a symmetric form is refused here
      under V8 rather than mapped to a window the oracle would then refuse.
  V9  every `resolution` field recomputed from (`sample_rate_hz`, `fft_size`,
      `interval_ms`, `enbw_bins`) to 1×10⁻⁶ — `bin_width_hz = fs/N`,
      `window_duration_ms = 1000·N/fs`, `enbw_hz = enbw_bins·fs/N`
      (`spectrum.enbw_hz`), `hop_samples = interval_ms·fs/1000` an integer —
      and `0 ≤ freq_min_hz < freq_max_hz ≤ fs/2` when the display band is
      present.

The window length of a preset is `fft_size`: §4.4 defines
`window_duration_ms = 1000 × fft_size / sample_rate_hz`, and the preset has no
separate window-length field, so `window_length_samples == fft_size` and the
transform is never zero-padded on the preset path.

`spectrum_config_from_preset()` is the mapping onto the nine keys of the golden
manifest's `analyses.spectrum` block (ADR 0009), each with its source:
`window` / `window_length_samples` / `fft_size` from `analysis`; `fftbins`
True because `form` is `periodic`; (`normalization`, `scaling`) =
(`S1`, `power_spectrum`) for `spectrum_type: power_spectrum` and
(`S2`, `power_spectral_density`) for `psd` — the pair ADR 0006 D2 ratifies and
its density form; `dbfs_reference: sine` from `db_reference: dbfs_sine` (the
schema's only value; ADR 0006 D3); `int16_scale` 32768 (ADR 0003 d.2 — a
firmware constant the preset deliberately cannot change, preset-schema.md §8);
`dtype` float64, the oracle's accumulation width, overridable by argument for a
float32 twin of the device.

`dump_preset(doc)` is the canonical writer — the same bytes V0 checks — and it
REFUSES a number with more than six decimals (or a non-finite one) rather than
rounding it: the spec's "rounded half-even, never truncated" is an instruction
to whoever derives the value, and a writer that rounds silently would change
a value a loader is about to recompute. Round first, then dump.

CLI (read-only; prints, never writes a preset):

    uv run --project host python -m spectral_host.presets protocols/presets/*.json
    uv run --project host python -m spectral_host.presets --canonical PRESET.json

Per file: `<id>  sha256=<digest>  <window> N=<fft_size> fs=<rate> -> <normalization>/<scaling>`,
or `<path>: <rule>: <message>` on rejection. `--canonical` prints the
canonical bytes of an accepted preset to stdout instead (byte-identical to the
file, by V0). Exit 0 when every file is accepted, 1 on any rejection, 2 on a
usage error.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from spectral_host import spectrum
from spectral_host.hashing import sha256_bytes

#: preset-schema.md §6: "The 1×10⁻⁶ tolerance is exactly what the canonical-form
#: number rule guarantees" — rounding to six places moves a value by at most
#: 5×10⁻⁷, the other half absorbs the float arithmetic.
TOL: float = 1e-6

#: The tolerance on the COEFFICIENTS themselves (V8 first clause). The
#: coefficients are the contract (ADR 0006 D1) and they round-trip exactly
#: through JSON, so this is effectively equality; 1e-9 is what the Apache
#: checker uses and it is kept identical here so the two cannot disagree on a
#: value one calls the table's and the other does not.
COEFFICIENT_TOL: float = 1e-9

#: preset-schema.md §4.2: `fft_size` is 512 … 16384 (16384 host-only). The
#: loader builds a window of `fft_size` samples under V8, so the bound is
#: repeated here — the schema is the Apache checker's, and a file that skips it
#: must still not make this module allocate a window the size of a typo.
MIN_FFT_SIZE: int = 512
MAX_FFT_SIZE: int = 16384

#: ADR 0003 d.2 / preset-schema.md §8: the int16 → float divisor is a firmware
#: constant, not a preset field — the same value `spectrum.DEFAULT_INT16_SCALE`.
PRESET_INT16_SCALE: int = spectrum.DEFAULT_INT16_SCALE

#: `analysis.spectrum_type` → the (normalization, scaling) pair of the golden
#: manifest. ADR 0006 D2 ratifies (`S1`, `power_spectrum`) and names
#: (`S2`, `power_spectral_density`) as its density form; preset-schema.md §4.2:
#: "PSD divides by the ENBW and is correct for noise; power spectrum is correct
#: for tones. ADR 0006 fixes the constants — the preset only names which of the
#: two it displays."
SPECTRUM_TYPE_TO_SCALING: dict[str, tuple[str, str]] = {
    "power_spectrum": ("S1", "power_spectrum"),
    "psd": ("S2", "power_spectral_density"),
}

#: `analysis.db_reference` → the manifest's `dbfs_reference`. The schema makes
#: `dbfs_sine` a const (preset-schema.md §4.2): a square reference "is the same
#: axis shifted by 3.01 dB, and that constant is the classic 'it goes away if
#: someone edits a number' bug".
DB_REFERENCE_TO_DBFS: dict[str, str] = {"dbfs_sine": "sine"}

#: A JSON number as the canonical form permits it (preset-schema.md §3, Numbers
#: row): decimal only, no exponent, no leading '+', no trailing '.', at most six
#: decimal places. Matched against the NUMERIC LEAVES of the parsed document —
#: never against the serialised text, so a decimal inside a free-text
#: `description` is not a JSON number and is not rejected by a rule about JSON
#: numbers. Exact because it runs only after the bytes have been proved equal
#: to `json.dumps(doc, sort_keys=True, indent=2)`, so each leaf's shortest
#: round-trip repr IS the token on disk. Same expression as the Apache checker's.
CANONICAL_NUMBER = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,6})?$")

_BOM = b"\xef\xbb\xbf"


class PresetRejected(Exception):
    """A rule violation. `rule` is the V-number that owns it (V0, V1, V8, V9) — the same shape as check_presets' `Failure`."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(message)
        self.rule = rule
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - formatting only
        return "%s: %s" % (self.rule, self.message)


@dataclass(frozen=True)
class Preset:
    """A loaded, accepted preset.

    `id` is the document's `id` (== basename, V1); `sha256` is over the file's
    bytes exactly as read — the identity a TAKE_HEADER carries (preset-schema.md
    §3); `doc` is the parsed document, handed out as the `dict` `json.loads`
    produced (treat it as read-only: a mutated copy is a different preset with
    a different sha256, and `dump_preset` is how one is written); `path` is
    where it was read from. Equality and hashing use `id`, `sha256` and `path`
    — `doc` is excluded because a dict cannot be hashed and because the sha256
    already identifies it.
    """

    id: str
    sha256: str
    doc: dict[str, Any] = field(compare=False, hash=False, repr=False)
    path: Path

    @property
    def analysis(self) -> dict[str, Any]:
        """The `analysis` block (preset-schema.md §4.2)."""
        return self.doc["analysis"]


# --- canonical bytes (V0) --------------------------------------------------------


def canonical_text(doc: Any) -> str:
    """The canonical serialisation of `doc` as text, with its single trailing newline (preset-schema.md §3).

    `allow_nan=False`: the canonical number grammar has no NaN/Infinity tokens,
    so `json.dumps` must raise rather than emit them.
    """
    return json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def number_leaves(node: Any, pointer: str = "") -> Iterator[tuple[str, str]]:
    """Yield `(json_pointer, serialised_number)` for every numeric leaf of `node`.

    `bool` is excluded: it is a JSON boolean even though Python makes it an
    `int` subclass. The pointer uses RFC 6901 escaping so a message can name
    the leaf exactly.
    """
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        yield pointer, json.dumps(node)
    elif isinstance(node, dict):
        for key, value in node.items():
            token = str(key).replace("~", "~0").replace("/", "~1")
            yield from number_leaves(value, pointer + "/" + token)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from number_leaves(value, pointer + "/%d" % index)


def _check_number_leaves(doc: Any) -> None:
    for pointer, token in number_leaves(doc):
        if not CANONICAL_NUMBER.match(token):
            raise PresetRejected(
                "V0",
                "number %r at %s is not in canonical decimal form (decimal, no exponent, <= 6 places)"
                % (token, pointer or "/"),
            )


def check_v0_canonical(raw_bytes: bytes) -> dict[str, Any]:
    """V0 — prove `raw_bytes` is exactly its own canonical form; return the parsed document.

    Byte checks first (BOM, CR), then the parse, then the serialisation
    equality, then the number grammar on the parsed leaves — the order in
    which each check's precondition is established.
    """
    if raw_bytes.startswith(_BOM):
        raise PresetRejected("V0", "file starts with a UTF-8 BOM")
    if b"\r" in raw_bytes:
        raise PresetRejected("V0", "file contains CR; line endings must be LF")
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PresetRejected("V0", "file is not valid UTF-8: %s" % exc) from None
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise PresetRejected("V0", "file must end with exactly one trailing newline")
    for i, line in enumerate(text.split("\n")[:-1], 1):
        if line != line.rstrip():
            raise PresetRejected("V0", "trailing whitespace on line %d" % i)
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PresetRejected("V0", "file is not JSON (%s) and so cannot be its canonical form" % exc) from None
    if not isinstance(doc, dict):
        raise PresetRejected("V0", "top level is %s, not an object" % type(doc).__name__)
    expected = canonical_text(doc)
    if text != expected:
        for i, (a, b) in enumerate(zip(text.split("\n"), expected.split("\n")), 1):
            if a != b:
                raise PresetRejected(
                    "V0", "not canonical at line %d: %r, canonical form has %r" % (i, a, b)
                )
        raise PresetRejected("V0", "not canonical (length differs from the canonical form)")
    _check_number_leaves(doc)
    return doc


def dump_preset(doc: dict[str, Any]) -> bytes:
    """The canonical bytes of `doc` (preset-schema.md §3) — what `load_preset` will accept under V0.

    Refuses, under V0, a document whose serialisation is not in the canonical
    number grammar (more than six decimals, an exponent form, NaN/Infinity)
    instead of rounding: the writer does not change values. The result is
    byte-identical to a shipped preset file (`test_dump_then_load_is_byte_identical`).
    """
    if not isinstance(doc, dict):
        raise PresetRejected("V0", "a preset document is a JSON object, got %s" % type(doc).__name__)
    try:
        text = canonical_text(doc)
    except ValueError as exc:  # allow_nan=False: NaN / Infinity
        raise PresetRejected("V0", "document cannot be written canonically: %s" % exc) from None
    _check_number_leaves(doc)
    return text.encode("utf-8")


# --- the rules (V1, V8, V9) --------------------------------------------------------


def _close(actual: Any, expected: float, tol: float = TOL) -> bool:
    return isinstance(actual, (int, float)) and not isinstance(actual, bool) and abs(float(actual) - expected) <= tol


def check_v1_id(doc: dict[str, Any], basename: str) -> None:
    """V1 — `id` equals the file's basename without `.json`."""
    if doc.get("id") != basename:
        raise PresetRejected("V1", "id %r != file basename %r" % (doc.get("id"), basename))


def recompute_window_constants(name: str, n: int) -> tuple[float, float, float]:
    """(coherent_gain, coherent_gain_db, enbw_bins) of the periodic `name` window at length `n`, from the window itself.

    `spectrum.window_sums(spectrum.window_float64(name, n))` — the same array
    the oracle multiplies by — gives S1, S2 and NENBW = N·S2/S1²; the coherent
    gain is S1/N, which for the periodic form is exactly a₀ (ADR 0006 D2).
    """
    w = spectrum.window_float64(name, n)
    s1, _s2, nenbw = spectrum.window_sums(w)
    coherent_gain = s1 / float(n)
    return coherent_gain, 20.0 * math.log10(coherent_gain), nenbw


def check_v8_window(doc: dict[str, Any]) -> None:
    """V8 — the window block describes the §4.3 family it names, recomputed from the window (docstring above)."""
    analysis = doc["analysis"]
    w = analysis["window"]
    name, coeffs = w.get("name"), w.get("coefficients")
    if name not in spectrum.PRESET_WINDOW_FAMILIES:
        raise PresetRejected(
            "V8",
            "window family %r is not one of the six preset families %s"
            % (name, list(spectrum.PRESET_WINDOW_FAMILIES))
            + (" (`rect` is a golden-manifest family only — ADR 0006 consequence (c))" if name == "rect" else ""),
        )
    known = spectrum.window_coefficients(name)
    if not isinstance(coeffs, list) or len(coeffs) != len(known) or any(
        not _close(c, k, COEFFICIENT_TOL) for c, k in zip(coeffs, known)
    ):
        raise PresetRejected("V8", "coefficients %r are not the committed %r set %r" % (coeffs, name, known))
    if w.get("form") != "periodic":
        raise PresetRejected(
            "V8",
            "window form %r: the recomputation below holds for the periodic form only (ADR 0006 D1/D2); "
            "the schema's `const` owns this field" % (w.get("form"),),
        )
    n = analysis["fft_size"]
    if not isinstance(n, int) or isinstance(n, bool) or not MIN_FFT_SIZE <= n <= MAX_FFT_SIZE:
        # The schema bounds fft_size (§4.2); repeated here so the window is
        # built only for a length a preset may name — a rejection, never an
        # allocation the size of a bogus number.
        raise PresetRejected(
            "V8", "fft_size %r is outside the schema's %d … %d; no preset window of that length exists" % (n, MIN_FFT_SIZE, MAX_FFT_SIZE)
        )
    coherent_gain, coherent_gain_db, enbw_bins = recompute_window_constants(name, n)
    if not _close(w.get("coherent_gain"), coherent_gain):
        raise PresetRejected(
            "V8", "coherent_gain %r != S1/N = %.9f" % (w.get("coherent_gain"), coherent_gain)
        )
    if not _close(w.get("coherent_gain_db"), coherent_gain_db):
        raise PresetRejected(
            "V8",
            "coherent_gain_db %r != 20*log10(S1/N) = %.9f" % (w.get("coherent_gain_db"), coherent_gain_db),
        )
    if not _close(w.get("enbw_bins"), enbw_bins):
        raise PresetRejected(
            "V8",
            "enbw_bins %r != N*S2/S1^2 of the periodic %s window at N = %d = %.9f"
            % (w.get("enbw_bins"), name, n, enbw_bins),
        )


def check_v9_resolution(doc: dict[str, Any]) -> None:
    """V9 — every `resolution` field re-derived (preset-schema.md §4.4), and the display band inside Nyquist."""
    analysis = doc["analysis"]
    r, fs, n = analysis["resolution"], analysis["sample_rate_hz"], analysis["fft_size"]
    interval_ms = analysis["interval_ms"]
    if not isinstance(fs, int) or fs <= 0 or not isinstance(n, int) or n <= 0:
        raise PresetRejected("V9", "sample_rate_hz %r / fft_size %r are not positive integers" % (fs, n))
    bin_width = float(fs) / n
    expected = {
        "bin_width_hz": bin_width,
        "window_duration_ms": 1000.0 * n / fs,
        "enbw_hz": spectrum.enbw_hz(analysis["window"]["enbw_bins"], fs, n),
        "hop_samples": interval_ms * fs / 1000.0,
    }
    for key, want in expected.items():
        if not _close(r.get(key), want):
            raise PresetRejected("V9", "%s = %r, recomputed %.9f" % (key, r.get(key), want))
    if float(r["hop_samples"]) != round(float(r["hop_samples"])):
        raise PresetRejected("V9", "hop_samples %r is not an integer" % (r["hop_samples"],))
    d = doc.get("display", {})
    lo, hi = d.get("freq_min_hz"), d.get("freq_max_hz")
    if lo is None or hi is None:
        return
    if not 0 <= lo < hi <= fs / 2.0:
        raise PresetRejected(
            "V9", "band [%s, %s] Hz violates 0 <= min < max <= Nyquist (%g)" % (lo, hi, fs / 2.0)
        )


# --- loading --------------------------------------------------------------------------


def _basename_of(path: Path) -> str:
    name = path.name
    if not name.endswith(".json"):
        raise PresetRejected("V1", "preset file %r is not named <id>.json" % name)
    return name[: -len(".json")]


def load_preset_bytes(raw_bytes: bytes, path: str | os.PathLike[str]) -> Preset:
    """Apply V0, V1, V8, V9 to `raw_bytes` read from `path`; return the `Preset` or raise `PresetRejected`.

    Split from `load_preset` so a test can feed mutated bytes under a chosen
    name without touching disk. `path` supplies the basename V1 compares
    against and is recorded as given.
    """
    path = Path(path)
    basename = _basename_of(path)
    doc = check_v0_canonical(raw_bytes)
    check_v1_id(doc, basename)
    try:
        check_v8_window(doc)
        check_v9_resolution(doc)
    except PresetRejected:
        raise
    except (KeyError, TypeError, IndexError, ValueError, ZeroDivisionError) as exc:
        # A structurally malformed document (a missing block, a string where a
        # number belongs) is the schema's to describe; here it is reported as a
        # rejection rather than escaping as a traceback, the way the Apache
        # checker's `V?` does.
        raise PresetRejected("V?", "rule raised %s: %s" % (type(exc).__name__, exc)) from None
    return Preset(id=doc["id"], sha256=sha256_bytes(raw_bytes), doc=doc, path=path)


def load_preset(path: str | os.PathLike[str]) -> Preset:
    """Read a preset file, enforce V0/V1/V8/V9, and return its identity and document.

    Raises `PresetRejected(rule, message)` on the first failing rule; `OSError`
    if the file cannot be read. Never writes.
    """
    path = Path(path)
    return load_preset_bytes(path.read_bytes(), path)


# --- the mapping onto the golden manifest ----------------------------------------


def spectrum_config_from_preset(preset: Preset, dtype: str = "float64") -> spectrum.SpectrumConfig:
    """The `analyses.spectrum` block (nine keys, ADR 0009) that computes what this preset displays.

    See the module docstring for the source of each key. `dtype` defaults to
    the oracle's float64; pass "float32" for a twin of the device's width.
    `spectrum_type` and `db_reference` values outside the schema's enums are
    refused with a `ValueError` naming the field — this function maps, it
    never guesses.
    """
    a = preset.analysis
    try:
        normalization, scaling = SPECTRUM_TYPE_TO_SCALING[a["spectrum_type"]]
    except KeyError:
        raise ValueError(
            "spectrum_type %r is not one of %s" % (a.get("spectrum_type"), list(SPECTRUM_TYPE_TO_SCALING))
        ) from None
    try:
        dbfs_reference = DB_REFERENCE_TO_DBFS[a["db_reference"]]
    except KeyError:
        raise ValueError(
            "db_reference %r is not one of %s" % (a.get("db_reference"), list(DB_REFERENCE_TO_DBFS))
        ) from None
    return spectrum.SpectrumConfig(
        window=a["window"]["name"],
        window_length_samples=a["fft_size"],
        fftbins=True,  # V8 proved form == "periodic"
        fft_size=a["fft_size"],
        normalization=normalization,
        scaling=scaling,
        dbfs_reference=dbfs_reference,
        int16_scale=PRESET_INT16_SCALE,
        dtype=dtype,
    )


# --- CLI ---------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m spectral_host.presets",
        description="Load preset files under rules V0/V1/V8/V9 and print their identity and spectrum mapping. Read-only.",
    )
    parser.add_argument("presets", metavar="PRESET", nargs="+", help="preset JSON file(s)")
    parser.add_argument(
        "--canonical",
        action="store_true",
        help="print the canonical bytes of each accepted preset to stdout instead of the summary line",
    )
    return parser


def _summary_line(preset: Preset) -> str:
    cfg = spectrum_config_from_preset(preset)
    a = preset.analysis
    return "%-20s sha256=%s  %s N=%d fs=%d -> %s/%s" % (
        preset.id,
        preset.sha256,
        cfg.window,
        cfg.fft_size,
        a["sample_rate_hz"],
        cfg.normalization,
        cfg.scaling,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    status = 0
    for raw in args.presets:
        try:
            preset = load_preset(raw)
        except PresetRejected as exc:
            print("%s: %s" % (raw, exc), file=sys.stderr)
            status = 1
            continue
        except OSError as exc:
            print("%s: %s" % (raw, exc), file=sys.stderr)
            status = 2
            continue
        if args.canonical:
            sys.stdout.buffer.write(dump_preset(preset.doc))
            sys.stdout.flush()
        else:
            print(_summary_line(preset))
    return status


if __name__ == "__main__":
    sys.exit(main())
