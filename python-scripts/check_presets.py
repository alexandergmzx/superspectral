#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""Validate the shipped presets against the schema and the loader rules.

This is the host-side twin of the firmware preset loader described in
``protocols/specs/preset-schema.md`` section 6.  It exists so that a rule the
watch enforces at runtime cannot silently stop being true in the repository:
every rule below has the same number here, in that document, and in the C
loader that will implement it.

Four things run:

  1. **Schema validation** of every ``protocols/presets/*.json`` against
     ``protocols/specs/presets.schema.json`` (JSON Schema draft 2020-12).
     Requires ``jsonschema``; skipped with a loud notice if it is absent.  The
     exit status then reflects only the rules below: the negative cases whose
     owner is the schema are reported as *skipped*, not missed, and the
     rule-coverage assertion is withheld because a partial run cannot make a
     coverage claim.
  2. **Rules V0-V10** re-derived here in Python.  Nothing is coerced: a preset
     either satisfies a rule or is reported with the rule number, exactly as
     the loader must behave.
  3. **A negative-case suite.**  Each case mutates a valid preset in one way
     and names the rule that must catch it.  A case that is *accepted* is a
     failure of this script, not of the preset -- it means the rule is not
     enforced.  Positive controls (the unmutated presets) must be accepted.
  4. **Regression guards.**  One per defect found in this script itself, plus
     the byte-level V0 cases the document suite cannot express.  A guard names
     the rule that must fire *and* the rules that must stay silent, so a rule
     that once fired on the wrong input cannot start doing so again.  Together
     the two suites must exercise V0 and every rule in ``RULES``; a rule no
     case reaches is reported as UNCOVERED and fails the run.

Usage::

    python3 python-scripts/check_presets.py            # from the repo root
    python3 python-scripts/check_presets.py --verbose  # list every case

Exit status is 0 when every preset passes every rule, every negative case is
rejected by the rule that owns it, and every positive control is accepted.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESET_DIR = os.path.join(REPO, "protocols", "presets")
SCHEMA_PATH = os.path.join(REPO, "protocols", "specs", "presets.schema.json")

TOL = 1e-6  # preset-schema.md section 6: the 6-decimal canonical form guarantees it

# preset-schema.md section 4.3.  Coefficients are esp-dsp's own, so watch, host,
# SciPy and Praat agree coefficient-for-coefficient.
#
# UNRESOLVED CONFLICT between V0 and V8, measured 2026-08-21: V0 admits at most
# six decimal places, `blackman_nuttall` needs seven (0.3635819) and `flat_top`
# up to nine (0.277263158), and V8's 1e-9 tolerance forbids rounding them.  A
# canonical preset naming either family is therefore rejected by V0 -- two of
# the six sanctioned families cannot be expressed by any file that passes both
# rules.  No shipped preset uses them, so this is latent.  Resolving it is a
# schema decision (raise the decimal limit for `analysis.window.*`, or drop the
# two families from the enum), owned by preset-schema.md section 3/4.3 and
# protocols/specs/presets.schema.json under ADR 0010; this script must not
# decide it unilaterally.  Until then the conflict is (prov.) unresolved.
WINDOW_FAMILIES = {
    "hann": [0.5, 0.5],
    "blackman": [0.42, 0.5, 0.08],
    "blackman_harris": [0.35875, 0.48829, 0.14128, 0.01168],
    "blackman_nuttall": [0.3635819, 0.4891775, 0.1365995, 0.0106411],
    "nuttall": [0.355768, 0.487396, 0.144232, 0.012604],
    "flat_top": [0.21557895, 0.41663158, 0.277263158, 0.083578947, 0.006947368],
}

# A JSON number as the canonical form permits it: decimal only, no exponent, no
# leading '+', no trailing '.', at most six decimal places.  It is matched
# against the *numeric leaves* of the parsed document, never against the
# serialised text: a decimal inside a free-text `description` is not a JSON
# number and must not be rejected by a rule about JSON numbers.  This is exact
# because the check below runs only after the file's bytes have been proved
# equal to ``json.dumps(doc, sort_keys=True, indent=2)``, so each leaf's
# shortest round-trip repr *is* the token on disk.
CANONICAL_NUMBER = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,6})?$")


class Failure(Exception):
    """A rule violation.  ``rule`` is the V-number that owns it."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(message)
        self.rule = rule
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - formatting only
        return "%s: %s" % (self.rule, self.message)


def close(actual, expected, tol=TOL):
    return isinstance(actual, (int, float)) and abs(float(actual) - float(expected)) <= tol


def resolve_pointer(doc, pointer):
    """Minimal RFC 6901 resolution; returns False if the pointer dangles."""
    if pointer == "":
        return True
    if not pointer.startswith("/"):
        return False
    node = doc
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            if token not in node:
                return False
            node = node[token]
        elif isinstance(node, list):
            if not token.isdigit() or int(token) >= len(node):
                return False
            node = node[int(token)]
        else:
            return False
    return True


# ---------------------------------------------------------------- rules V0-V10


def number_leaves(node, pointer=""):
    """Yield ``(json_pointer, serialised_number)`` for every numeric leaf.

    ``bool`` is excluded: it is a JSON boolean even though Python makes it an
    ``int`` subclass.
    """
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        yield pointer, json.dumps(node)
    elif isinstance(node, dict):
        for key, value in node.items():
            token = str(key).replace("~", "~0").replace("/", "~1")
            for item in number_leaves(value, pointer + "/" + token):
                yield item
    elif isinstance(node, list):
        for index, value in enumerate(node):
            for item in number_leaves(value, pointer + "/%d" % index):
                yield item


def check_v0_canonical(raw_bytes, doc):
    """V0 -- the file's bytes are exactly its canonical form."""
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        raise Failure("V0", "file starts with a UTF-8 BOM")
    if b"\r" in raw_bytes:
        raise Failure("V0", "file contains CR; line endings must be LF")
    text = raw_bytes.decode("utf-8")
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise Failure("V0", "file must end with exactly one trailing newline")
    for i, line in enumerate(text.split("\n")[:-1], 1):
        if line != line.rstrip():
            raise Failure("V0", "trailing whitespace on line %d" % i)
    expected = json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    if text != expected:
        for i, (a, b) in enumerate(zip(text.split("\n"), expected.split("\n")), 1):
            if a != b:
                raise Failure(
                    "V0",
                    "not canonical at line %d: %r, canonical form has %r" % (i, a, b),
                )
        raise Failure("V0", "not canonical (length differs from the canonical form)")
    for pointer, token in number_leaves(doc):
        if not CANONICAL_NUMBER.match(token):
            raise Failure(
                "V0",
                "number %r at %s is not in canonical decimal form"
                % (token, pointer or "/"),
            )


def check_v1_id(doc, basename):
    if doc.get("id") != basename:
        raise Failure("V1", "id %r != file basename %r" % (doc.get("id"), basename))


def check_v2_watch(doc):
    if "watch" not in doc.get("targets", []):
        return
    a = doc["analysis"]
    if a["fft_size"] > 8192:
        raise Failure("V2", "watch preset asks for fft_size %d > 8192" % a["fft_size"])
    if a["sample_rate_hz"] == 48000:
        raise Failure("V2", "watch preset asks for 48000 Hz; the PDM gate is not open")
    if "refresh_hz_target" not in doc.get("display", {}):
        raise Failure("V2", "watch preset has no display.refresh_hz_target")
    # preset-schema.md section 5 (`overlays` row) and the schema's V2 branch:
    # `stem_f0` and `dtw_path` are host-only and are rejected on any preset that
    # targets the watch, whether or not it also targets the host.
    host_only = {"stem_f0", "dtw_path"} & set(doc.get("display", {}).get("overlays", []))
    if host_only:
        raise Failure(
            "V2",
            "watch preset carries host-only overlay(s) %s"
            % ", ".join(sorted(host_only)),
        )


def check_v3_host(doc):
    if "host" in doc and "host" not in doc.get("targets", []):
        raise Failure("V3", "a host block is present but 'host' is not in targets")


def check_v4_log_scale(doc):
    d = doc.get("display", {})
    if d.get("freq_scale") == "log" and not d.get("freq_min_hz", 0) > 0:
        raise Failure("V4", "freq_scale is log but freq_min_hz is %r" % d.get("freq_min_hz"))


def check_v5_smoothing(doc):
    a = doc["analysis"]
    smoothing = a.get("smoothing", 0)
    exponential = a.get("averaging") == "exponential"
    if exponential and not smoothing > 0:
        raise Failure("V5", "exponential averaging with smoothing %r" % smoothing)
    if not exponential and smoothing != 0:
        raise Failure(
            "V5", "smoothing %r with averaging %r" % (smoothing, a.get("averaging"))
        )


def check_v6_frames(doc):
    a = doc["analysis"]
    present = "averaging_frames" in a
    linear = a.get("averaging") == "linear"
    if present != linear:
        raise Failure(
            "V6",
            "averaging_frames %s with averaging %r"
            % ("present" if present else "absent", a.get("averaging")),
        )


def check_v6b_mic_eq(doc):
    eq = doc.get("mic_eq", {})
    if eq.get("mode") != "inline":
        return
    if "design_sample_rate_hz" not in eq:
        raise Failure("V6b", "inline mic_eq without design_sample_rate_hz")
    if eq["design_sample_rate_hz"] != doc["analysis"]["sample_rate_hz"]:
        raise Failure(
            "V6b",
            "inline mic_eq designed at %d Hz, analysis runs at %d Hz"
            % (eq["design_sample_rate_hz"], doc["analysis"]["sample_rate_hz"]),
        )


def check_v7_rates(doc):
    a = doc["analysis"]
    # Clause 1 (preset-schema.md section 4.2 `interval_ms` and section 6 V7) is
    # *vacuous under the current schema*: `sample_rate_hz` is an enum of
    # {16000, 32000, 48000} -- all multiples of 1000 -- and `interval_ms` is an
    # integer, so the product is always a multiple of 1000 (checked
    # exhaustively over the 3 x 1000 admissible pairs on 2026-08-21).  It is
    # kept because the loader must also accept presets that arrive over the
    # wire, and because it is the clause that would bite the day a rate not
    # divisible by 1000 (e.g. 44100) enters the enum.  Nothing in the negative
    # suite can exercise it while the enum stands.
    product = a["interval_ms"] * a["sample_rate_hz"]
    if product % 1000 != 0:
        raise Failure(
            "V7",
            "interval_ms x sample_rate_hz = %s is not a multiple of 1000 (fractional hop)"
            % product,
        )
    refresh = doc.get("display", {}).get("refresh_hz_target")
    if refresh is None:
        return
    frames_per_s = 1000.0 / a["interval_ms"]
    if abs(frames_per_s - round(frames_per_s)) > TOL:
        raise Failure("V7", "1000 / interval_ms = %s is not an integer" % frames_per_s)
    ratio = round(frames_per_s) / float(refresh)
    if abs(ratio - round(ratio)) > TOL or round(ratio) < 1:
        raise Failure(
            "V7",
            "%g analysis frames/s is not an integer multiple of refresh_hz_target %s"
            % (frames_per_s, refresh),
        )


def check_v8_window(doc):
    w = doc["analysis"]["window"]
    name, coeffs = w.get("name"), w.get("coefficients")
    known = WINDOW_FAMILIES.get(name)
    if known is None:
        raise Failure("V8", "unknown window family %r" % name)
    if len(coeffs) != len(known) or any(
        not close(c, k, 1e-9) for c, k in zip(coeffs, known)
    ):
        raise Failure(
            "V8", "coefficients %r are not the committed %r set" % (coeffs, name)
        )
    a0 = coeffs[0]
    if not close(w.get("coherent_gain"), a0):
        raise Failure(
            "V8", "coherent_gain %r != a0 %r" % (w.get("coherent_gain"), a0)
        )
    if not close(w.get("coherent_gain_db"), 20.0 * math.log10(a0)):
        raise Failure(
            "V8",
            "coherent_gain_db %r != 20*log10(a0) = %.9f"
            % (w.get("coherent_gain_db"), 20.0 * math.log10(a0)),
        )
    enbw = (a0 * a0 + sum(c * c / 2.0 for c in coeffs[1:])) / (a0 * a0)
    if not close(w.get("enbw_bins"), enbw):
        raise Failure(
            "V8", "enbw_bins %r != recomputed %.9f" % (w.get("enbw_bins"), enbw)
        )


def check_v9_resolution(doc):
    a = doc["analysis"]
    r, fs, n = a["resolution"], a["sample_rate_hz"], a["fft_size"]
    bin_width = float(fs) / n
    expected = {
        "bin_width_hz": bin_width,
        "window_duration_ms": 1000.0 * n / fs,
        "enbw_hz": a["window"]["enbw_bins"] * bin_width,
        "hop_samples": a["interval_ms"] * fs / 1000.0,
    }
    for key, want in expected.items():
        if not close(r.get(key), want):
            raise Failure(
                "V9", "%s = %r, recomputed %.9f" % (key, r.get(key), want)
            )
    if float(r["hop_samples"]) != round(float(r["hop_samples"])):
        raise Failure("V9", "hop_samples %r is not an integer" % r["hop_samples"])
    d = doc.get("display", {})
    lo, hi = d.get("freq_min_hz"), d.get("freq_max_hz")
    if lo is None or hi is None:
        return
    if not 0 <= lo < hi <= fs / 2.0:
        raise Failure(
            "V9",
            "band [%s, %s] Hz violates 0 <= min < max <= Nyquist (%g)" % (lo, hi, fs / 2.0),
        )


def check_v10_provisional(doc):
    for pointer in doc.get("provisional", []):
        if not resolve_pointer(doc, pointer):
            raise Failure("V10", "provisional pointer %r does not resolve" % pointer)


RULES = [
    ("V1", lambda raw, doc, base: check_v1_id(doc, base)),
    ("V2", lambda raw, doc, base: check_v2_watch(doc)),
    ("V3", lambda raw, doc, base: check_v3_host(doc)),
    ("V4", lambda raw, doc, base: check_v4_log_scale(doc)),
    ("V5", lambda raw, doc, base: check_v5_smoothing(doc)),
    ("V6", lambda raw, doc, base: check_v6_frames(doc)),
    ("V6b", lambda raw, doc, base: check_v6b_mic_eq(doc)),
    ("V7", lambda raw, doc, base: check_v7_rates(doc)),
    ("V8", lambda raw, doc, base: check_v8_window(doc)),
    ("V9", lambda raw, doc, base: check_v9_resolution(doc)),
    ("V10", lambda raw, doc, base: check_v10_provisional(doc)),
]


def apply_rules(doc, basename, raw_bytes=None):
    """Run every rule; returns the list of Failures (empty when the preset loads)."""
    failures = []
    if raw_bytes is not None:
        try:
            check_v0_canonical(raw_bytes, doc)
        except Failure as exc:
            failures.append(exc)
    for _, fn in RULES:
        try:
            fn(raw_bytes, doc, basename)
        except Failure as exc:
            failures.append(exc)
        except (KeyError, TypeError, IndexError, ValueError, ZeroDivisionError) as exc:
            failures.append(
                Failure("V?", "rule raised %s: %s" % (type(exc).__name__, exc))
            )
    return failures


# ------------------------------------------------------------- schema validation


def load_validator():
    try:
        import jsonschema
    except ImportError:
        return None, None
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        schema = json.load(fh)
    return jsonschema.Draft202012Validator(schema), jsonschema.__name__


# ------------------------------------------------------------- negative cases


def _set(doc, path, value):
    node = doc
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return doc


def _del(doc, path):
    node = doc
    for key in path[:-1]:
        node = node[key]
    del node[path[-1]]
    return doc


def negative_cases(presets):
    """(name, basename, mutated document, rule that must catch it).

    Each case changes one thing -- plus, where the mutation invalidates a
    derived field, that field's dependent recomputation, so the case isolates
    the rule it names instead of tripping V9 by accident.  The rule named is
    the one that owns the violation in preset-schema.md section 6; a case
    caught only by the schema is named "schema".

    V0 is *not* exercised here: these cases are documents, and V0 is a rule
    about a file's bytes.  The byte-level V0 guards live in
    ``regression_guards()`` below, and ``main`` asserts that the union of the
    two suites covers every rule.
    """
    live = presets["live_singing"]
    room = presets["room_noise_floor"]
    stem = presets["stem_analysis"]
    vowel = presets["vowel_formant_study"]
    C = copy.deepcopy
    cases = [
        # --- structural / schema ---
        ("unknown top-level field", "live_singing",
         _set(C(live), ["colour_scheme"], "viridis"), "schema"),
        ("unknown analysis field", "live_singing",
         _set(C(live), ["analysis", "overlap_pct"], 75), "schema"),
        ("off-enum window name", "live_singing",
         _set(C(live), ["analysis", "window", "name"], "gaussian"), "schema"),
        ("off-enum spectrum_type", "live_singing",
         _set(C(live), ["analysis", "spectrum_type"], "cepstrum"), "schema"),
        ("off-enum weighting", "live_singing",
         _set(C(live), ["analysis", "weighting"], "ITU-R 468"), "schema"),
        ("window form symmetric", "live_singing",
         _set(C(live), ["analysis", "window", "form"], "symmetric"), "schema"),
        ("schema_version 2.x", "live_singing",
         _set(C(live), ["schema_version"], "2.0.0"), "schema"),
        ("schema_version not semver", "live_singing",
         _set(C(live), ["schema_version"], "1.0"), "schema"),
        ("missing enbw_hz", "live_singing",
         _del(C(live), ["analysis", "resolution", "enbw_hz"]), "schema"),
        ("missing id", "live_singing", _del(C(live), ["id"]), "schema"),
        ("missing targets", "live_singing", _del(C(live), ["targets"]), "schema"),
        ("empty overlays is fine, empty targets is not", "live_singing",
         _set(C(live), ["targets"], []), "schema"),
        ("db_floor above db_ceiling", "live_singing",
         _set(C(live), ["display", "db_floor_dbfs"], 12), "schema"),
        ("negative dc_blocker", "live_singing",
         _set(C(live), ["analysis", "dc_blocker_hz"], -20), "schema"),
        ("smoothing above 1", "live_singing",
         _set(C(live), ["analysis", "smoothing"], 1.5), "schema"),
        ("fft_size not a power of two", "live_singing",
         _set(C(live), ["analysis", "fft_size"], 3000), "schema"),
        ("one-coefficient window", "live_singing",
         _set(C(live), ["analysis", "window", "coefficients"], [1.0]), "schema"),
        ("mic_eq ref without sha256", "live_singing",
         _set(C(live), ["mic_eq"], {"mode": "ref", "ref": "eq/spm1423.json"}), "schema"),
        # --- rules the schema cannot see ---
        ("id does not match filename", "live_singing",
         _set(C(live), ["id"], "live_singing_v2"), "V1"),
        ("watch preset at N = 16384", "live_singing",
         _set(C(live), ["analysis", "fft_size"], 16384), "V2"),
        ("watch preset at 48 kHz", "live_singing",
         _set(C(live), ["analysis", "sample_rate_hz"], 48000), "V2"),
        ("watch preset without refresh_hz_target", "live_singing",
         _del(C(live), ["display", "refresh_hz_target"]), "V2"),
        ("host block without host in targets", "live_singing",
         _set(_set(C(live), ["host"], C(stem["host"])), ["targets"], ["watch"]), "V3"),
        ("log scale from 0 Hz", "live_singing",
         _set(C(live), ["display", "freq_min_hz"], 0), "V4"),
        ("smoothing without exponential averaging", "room_noise_floor",
         _set(C(room), ["analysis", "smoothing"], 0.3), "V5"),
        ("exponential averaging without smoothing", "live_singing",
         _set(C(live), ["analysis", "smoothing"], 0.0), "V5"),
        ("averaging_frames without linear averaging", "live_singing",
         _set(C(live), ["analysis", "averaging_frames"], 25), "V6"),
        ("linear averaging without averaging_frames", "room_noise_floor",
         _del(C(room), ["analysis", "averaging_frames"]), "V6"),
        ("inline mic_eq designed at another rate", "live_singing",
         _set(C(live), ["mic_eq"],
              {"mode": "inline", "design_sample_rate_hz": 48000,
               "biquads": [{"b": [1.0, 0.0, 0.0], "a": [1.0, 0.0, 0.0]}]}), "V6b"),
        # 3 ms x 32000 Hz = 96000 IS a multiple of 1000, so clause 1 does not
        # fire here; what this case tests is clause 2, 1000/3 frames per second.
        ("analysis rate 1000/interval_ms is not an integer", "live_singing",
         _set(C(live), ["analysis", "interval_ms"], 3), "V7"),
        ("analysis rate not a multiple of the refresh rate", "live_singing",
         _set(_set(C(live), ["analysis", "interval_ms"], 25),
              ["analysis", "resolution", "hop_samples"], 800), "V7"),
        ("mutated window coefficient", "live_singing",
         _set(C(live), ["analysis", "window", "coefficients"],
              [0.35875, 0.48829, 0.14128, 0.02168]), "V8"),
        ("coefficients of another family under this name", "live_singing",
         _set(C(live), ["analysis", "window", "coefficients"], [0.42, 0.5, 0.08]), "V8"),
        ("stale coherent_gain_db", "live_singing",
         _set(C(live), ["analysis", "window", "coherent_gain_db"], -6.0206), "V8"),
        ("stale enbw_bins", "live_singing",
         _set(C(live), ["analysis", "window", "enbw_bins"], 1.5), "V8"),
        ("stale enbw_hz", "live_singing",
         _set(C(live), ["analysis", "resolution", "enbw_hz"], 15.0), "V9"),
        ("stale bin_width_hz", "live_singing",
         _set(C(live), ["analysis", "resolution", "bin_width_hz"], 7.8), "V9"),
        ("stale hop_samples", "live_singing",
         _set(C(live), ["analysis", "resolution", "hop_samples"], 512), "V9"),
        ("freq_max above Nyquist", "vowel_formant_study",
         _set(C(vowel), ["display", "freq_max_hz"], 20000), "V9"),
        ("unresolvable provisional pointer", "live_singing",
         _set(C(live), ["provisional"], ["/analysis/overlap_pct"]), "V10"),
        ("provisional pointer into a missing array element", "live_singing",
         _set(C(live), ["provisional"], ["/display/overlays/9"]), "V10"),
    ]
    return cases


def canonical_bytes(doc):
    """The canonical serialisation of ``doc`` (rule V0, preset-schema.md section 3)."""
    return (json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def regression_guards(presets):
    """(label, basename, raw_bytes|None, document, must_fire|None, must_not_fire).

    Guards for defects that were found and fixed in this script, plus the
    byte-level V0 cases the document suite above cannot express.  ``must_fire``
    names the rule that has to appear (``None`` = the input must be accepted by
    every rule); ``must_not_fire`` names rules that must stay silent, which is
    how a rule that once fired on the wrong input is kept honest.
    """
    live = presets["live_singing"]
    stem = presets["stem_analysis"]
    C = copy.deepcopy
    guards = []

    # --- V0: the file's bytes are exactly its canonical form -----------------
    good = canonical_bytes(live)
    guards += [
        ("V0 utf-8 BOM", "live_singing", b"\xef\xbb\xbf" + good, C(live), "V0", ()),
        ("V0 CRLF line endings", "live_singing",
         good.replace(b"\n", b"\r\n"), C(live), "V0", ()),
        ("V0 no trailing newline", "live_singing",
         good.rstrip(b"\n"), C(live), "V0", ()),
        ("V0 duplicated trailing newline", "live_singing",
         good + b"\n", C(live), "V0", ()),
        ("V0 trailing whitespace", "live_singing",
         good.replace(b'"id":', b'"id":  ', 1).replace(b"\n", b" \n", 1),
         C(live), "V0", ()),
        ("V0 four-space indent", "live_singing",
         (json.dumps(live, sort_keys=True, indent=4, ensure_ascii=False) + "\n").encode(
             "utf-8"), C(live), "V0", ()),
    ]
    unsorted = dict(reversed(list(live.items())))
    guards.append((
        "V0 keys not sorted", "live_singing",
        (json.dumps(unsorted, sort_keys=False, indent=2, ensure_ascii=False) + "\n"
         ).encode("utf-8"), C(unsorted), "V0", ()))
    seven = _set(C(live), ["analysis", "dc_blocker_hz"], 0.1234567)
    guards.append(("V0 seven-decimal number", "live_singing",
                   canonical_bytes(seven), seven, "V0", ()))
    # ... and the converse: a decimal inside a free-text string is not a JSON
    # number.  V0 used to regex the serialised text and rejected this preset.
    described = _set(C(live), ["description"], "matches Spectroid 32768 at 0.1234567 s")
    guards.append(("V0 decimal inside a description string", "live_singing",
                   canonical_bytes(described), described, None, ("V0",)))

    # --- V2 clause 4: host-only overlays on a watch preset -------------------
    for overlay in ("stem_f0", "dtw_path"):
        doc = _set(C(live), ["display", "overlays"], ["f0", overlay])
        guards.append(("V2 watch preset with a %s overlay" % overlay, "live_singing",
                       None, doc, "V2", ()))
    # The clause used to test V3's condition instead, so it fired on this input
    # -- a host block, no overlays -- and reported an overlay that was not there.
    host_on_watch = _set(_set(C(live), ["host"], C(stem["host"])), ["targets"], ["watch"])
    guards.append(("V2 stays silent on a host block with no overlay", "live_singing",
                   None, host_on_watch, "V3", ("V2",)))

    # --- rules must report, never crash --------------------------------------
    guards.append(("V? interval_ms 0 does not escape apply_rules", "live_singing",
                   None, _set(C(live), ["analysis", "interval_ms"], 0), "V?", ()))
    guards.append(("V? fft_size 0 does not escape apply_rules", "live_singing",
                   None, _set(C(live), ["analysis", "fft_size"], 0), "V?", ()))
    return guards


# --------------------------------------------------------------------- driver


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verbose", "-v", action="store_true", help="list every case")
    args = ap.parse_args(argv)

    validator, _ = load_validator()
    if validator is None:
        print("NOTE: jsonschema is not installed -- schema validation skipped.")
        print("      Install it (pip install jsonschema) for the full suite.\n")

    names = sorted(
        f[:-5] for f in os.listdir(PRESET_DIR) if f.endswith(".json")
    )
    presets, failed = {}, 0

    print("Positive controls -- %d shipped presets" % len(names))
    for name in names:
        path = os.path.join(PRESET_DIR, name + ".json")
        raw = open(path, "rb").read()
        doc = json.loads(raw.decode("utf-8"))
        presets[name] = doc
        problems = ["%s" % f for f in apply_rules(doc, name, raw)]
        if validator is not None:
            problems += [
                "schema: %s at /%s"
                % (e.message, "/".join(str(p) for p in e.absolute_path))
                for e in validator.iter_errors(doc)
            ]
        if problems:
            failed += 1
            print("  FAIL %-22s %s" % (name, problems[0]))
            for extra in problems[1:]:
                print("       %-22s %s" % ("", extra))
        elif args.verbose:
            print("  ok   %-22s N=%-5d %s @ %d Hz" % (
                name, doc["analysis"]["fft_size"],
                doc["analysis"]["window"]["name"], doc["analysis"]["sample_rate_hz"]))
    print("  %d/%d accepted\n" % (len(names) - failed, len(names)))

    cases = negative_cases(presets)
    print("Negative cases -- %d mutations, each must be rejected" % len(cases))
    caught_by_schema = caught_by_rules = 0
    missed, unowned, skipped = [], [], 0
    owners_seen = set()
    for label, basename, doc, owner in cases:
        if owner == "schema" and validator is None:
            # Without jsonschema there is nothing to run this case against.  It
            # is skipped, not missed: counting it as a failure would make the
            # pre-commit hook block a commit for a reason unrelated to presets.
            skipped += 1
            continue
        rule_failures = apply_rules(doc, basename)
        fired = sorted({f.rule for f in rule_failures})
        owners_seen.update(fired)
        schema_errors = list(validator.iter_errors(doc)) if validator else []
        if schema_errors:
            caught_by_schema += 1
            how = "schema"
        elif rule_failures:
            caught_by_rules += 1
            how = "+".join(fired)
        else:
            missed.append((label, owner))
            how = None
        # The schema catching a case first does not excuse the rule that owns
        # it from firing: the watch runs the rules, and a rule that never fires
        # in this suite is untested.  A V-rule owner must appear in `fired`.
        owner_fired = owner == "schema" or owner in fired
        if not owner_fired:
            unowned.append((label, owner, how))
        if how is None:
            print("  MISSED %-52s (expected %s)" % (label, owner))
        elif not owner_fired:
            print("  RULE   %-52s caught by %s, but %s did not fire"
                  % (label, how, owner))
        elif args.verbose:
            print("  ok     %-52s caught by %s" % (label, how))
    evaluated = len(cases) - skipped
    print("  %d/%d rejected -- %d by the schema, %d only by the rules"
          % (evaluated - len(missed), evaluated, caught_by_schema, caught_by_rules))
    if skipped:
        print("  %d schema-owned cases skipped -- jsonschema is not installed" % skipped)
    owners = sorted({o for _, _, _, o in cases if o != "schema"},
                    key=lambda r: (len(r), r))
    print("  rule coverage: %s\n" % ", ".join(owners))

    guards = regression_guards(presets)
    print("Regression guards -- %d fixed defects, each must stay fixed" % len(guards))
    broken = []
    for label, basename, raw, doc, must_fire, must_not_fire in guards:
        fired = sorted({f.rule for f in apply_rules(doc, basename, raw)})
        why = []
        if must_fire is not None and must_fire not in fired:
            why.append("%s did not fire (fired: %s)"
                       % (must_fire, ", ".join(fired) or "nothing"))
        if must_fire is None and fired:
            why.append("expected acceptance, got %s" % ", ".join(fired))
        for rule in must_not_fire:
            if rule in fired:
                why.append("%s fired and must not" % rule)
        if why:
            broken.append((label, "; ".join(why)))
            print("  BROKEN %-52s %s" % (label, "; ".join(why)))
        elif args.verbose:
            print("  ok     %-52s %s" % (label, ", ".join(fired) or "accepted"))
        owners_seen.update(fired)
    print("  %d/%d held\n" % (len(guards) - len(broken), len(guards)))

    # Arithmetic, not diligence: a rule no case ever fires is an untested rule.
    expected_rules = {"V0"} | {name for name, _ in RULES}
    uncovered = sorted(expected_rules - owners_seen - {o for _, _, _, o in cases},
                       key=lambda r: (len(r), r))
    if skipped:
        uncovered = []  # a partial run cannot make a coverage claim
        print("Rule coverage not asserted -- the run was partial.\n")
    elif uncovered:
        print("UNCOVERED rules -- no case exercises: %s\n" % ", ".join(uncovered))

    ok = failed == 0 and not missed and not unowned and not broken and not uncovered
    print("RESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
