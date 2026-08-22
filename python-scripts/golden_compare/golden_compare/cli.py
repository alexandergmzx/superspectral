# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""Command line for golden_compare.

::

    python -m golden_compare spectrum --golden A.npy --candidate B.npy [--manifest M.yaml]
                                      [--atol-db 0.01] [--floor -80]
    python -m golden_compare pitch    --golden ref.npy --candidate dev.npy [--manifest M.yaml]
                                      --path injection|acoustic [--median-cents X] [--cent-tolerance 50]
                                      [--vr-min 0.9 --vfa-max 0.1]
    python -m golden_compare window   --raw table.f32 (--manifest M.yaml --family F --n N | --sha256 HEX)
    python -m golden_compare tolerances

Defaults for every limit come from :mod:`golden_compare.tolerances` (a copy
of ``docs/validation/golden-files.md``); an override on the command line is
printed next to the result, so a run never silently uses a different limit
than the one it reports. ``--manifest`` cross-checks the golden's sha256,
dtype and shape against its ``outputs[]`` entry before anything is compared
(:mod:`golden_compare.load`); without it the golden is trusted as loaded.

Exit status: 0 pass, 1 fail, 2 usage or a file that could not be read or
did not match its manifest.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import load, pitch, spectrum, tolerances, windows


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="golden_compare", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("spectrum", help="per-bin dB comparison (magnitude-spectrum row)")
    s.add_argument("--golden", required=True, type=Path, help="golden spectrum .npy ([N/2+1, 2] of [frequency, level] or 1-D levels)")
    s.add_argument("--candidate", required=True, type=Path, help="candidate .npy on the same bin grid")
    s.add_argument("--manifest", type=Path, help="manifest.yaml whose outputs[] names the golden (sha256/dtype/shape checked)")
    s.add_argument("--atol-db", type=float, default=tolerances.SPECTRUM_ATOL_DB.value, help=f"default {tolerances.SPECTRUM_ATOL_DB.value} dB")
    s.add_argument("--floor", type=float, default=tolerances.SPECTRUM_FLOOR_DBFS.value, help=f"mask golden bins below this dBFS (default {tolerances.SPECTRUM_FLOOR_DBFS.value})")

    q = sub.add_parser("pitch", help="f0 track comparison (median |Δcents| row + mir_eval rows)")
    q.add_argument("--golden", required=True, type=Path, help="golden pitch .npy ([n, 2] of [time, f0], 0 = unvoiced)")
    q.add_argument("--candidate", required=True, type=Path, help="candidate .npy, same layout, its own frame grid")
    q.add_argument("--manifest", type=Path, help="manifest.yaml whose outputs[] names the golden")
    q.add_argument("--path", choices=sorted(tolerances.F0_MEDIAN_ABS_CENTS_BY_PATH), default="injection", help="measurement path: selects the median |Δcents| limit (default injection)")
    q.add_argument("--median-cents", type=float, help="override the median |Δcents| limit (printed when used)")
    q.add_argument("--cent-tolerance", type=float, default=pitch.DEFAULT_CENT_TOLERANCE, help=f"mir_eval RPA/RCA/OA threshold (default {pitch.DEFAULT_CENT_TOLERANCE:g})")
    q.add_argument("--vr-min", type=float, default=pitch.DEFAULT_VR_MIN, help=f"voicing row: minimum VR as a fraction (default {pitch.DEFAULT_VR_MIN:g}; printed when overridden)")
    q.add_argument("--vfa-max", type=float, default=pitch.DEFAULT_VFA_MAX, help=f"voicing row: maximum VFA as a fraction (default {pitch.DEFAULT_VFA_MAX:g}; printed when overridden)")

    w = sub.add_parser("window", help="hash a raw float32 LE window-table dump and compare it with the manifest (exact row)")
    w.add_argument("--raw", required=True, type=Path, help="raw dump: N float32 little-endian samples, no header")
    w.add_argument("--manifest", type=Path, help="manifest.yaml with the windows[] entry")
    w.add_argument("--family", help="windows[].family to look up (with --manifest)")
    w.add_argument("--n", type=int, help="windows[].n to look up (with --manifest)")
    w.add_argument("--sha256", help="expected digest, instead of a manifest lookup")

    sub.add_parser("tolerances", help="print the tolerance constants and the rows they were copied from")
    return p


def _golden_entry(manifest_path: Path | None, golden: Path) -> dict | None:
    if manifest_path is None:
        return None
    return load.find_output(load.load_manifest(manifest_path), golden)


def cmd_spectrum(args: argparse.Namespace) -> int:
    entry = _golden_entry(args.manifest, args.golden)
    g = load.column(load.load_array(args.golden, entry), entry, "level", 1)
    c = load.column(load.load_array(args.candidate), None, "level", 1)
    report = spectrum.compare(g, c, args.atol_db, args.floor)
    print(report.summary())
    if args.atol_db != tolerances.SPECTRUM_ATOL_DB.value or args.floor != tolerances.SPECTRUM_FLOOR_DBFS.value:
        print(f"note: limits overridden on the command line (table: atol {tolerances.SPECTRUM_ATOL_DB.value} dB, floor {tolerances.SPECTRUM_FLOOR_DBFS.value} dBFS)")
    return 0 if report.passed else 1


def cmd_pitch(args: argparse.Namespace) -> int:
    entry = _golden_entry(args.manifest, args.golden)
    g = load.load_array(args.golden, entry)
    c = load.load_array(args.candidate)
    sentinel = float(entry.get("unvoiced_sentinel", pitch.UNVOICED)) if entry else pitch.UNVOICED
    limit_row = tolerances.F0_MEDIAN_ABS_CENTS_BY_PATH[args.path]
    limit = args.median_cents if args.median_cents is not None else limit_row.value
    report = pitch.compare_tracks(
        load.column(g, entry, "time", 0), load.column(g, entry, "f0", 1),
        load.column(c, None, "time", 0), load.column(c, None, "f0", 1),
        median_limit_cents=limit, sentinel=sentinel, cent_tolerance=args.cent_tolerance,
        vr_min=args.vr_min, vfa_max=args.vfa_max,
    )
    print(f"path: {args.path} ({limit_row.name} = {limit_row.value} cents; "
          f"{tolerances.VOICING_RECALL_MIN_PERCENT.name} = {tolerances.VOICING_RECALL_MIN_PERCENT.value} %, "
          f"{tolerances.VOICING_FALSE_ALARM_MAX_PERCENT.name} = {tolerances.VOICING_FALSE_ALARM_MAX_PERCENT.value} %)")
    print(report.summary())
    if args.median_cents is not None and args.median_cents != limit_row.value:
        print(f"note: median limit overridden on the command line (table: {limit_row.value} cents)")
    if args.vr_min != pitch.DEFAULT_VR_MIN or args.vfa_max != pitch.DEFAULT_VFA_MAX:
        print(f"note: voicing limits overridden on the command line (table: VR ≥ {pitch.DEFAULT_VR_MIN:g}, VFA ≤ {pitch.DEFAULT_VFA_MAX:g})")
    return 0 if report.passed else 1


def cmd_window(args: argparse.Namespace) -> int:
    if args.manifest is not None:
        if args.family is None or args.n is None:
            raise SystemExit("window: --manifest needs --family and --n")
        entry = load.find_window(load.load_manifest(args.manifest), args.family, args.n)
        report = windows.compare_window_digest(args.raw, entry)
        print(report.summary())
        return 0 if report.passed else 1
    if args.sha256 is None:
        raise SystemExit("window: give --manifest/--family/--n or --sha256")
    got = windows.raw_f32_sha256(args.raw)
    ok = got == args.sha256.lower()
    print(f"{'PASS' if ok else 'FAIL'}: dump {got} {'==' if ok else '!='} expected {args.sha256.lower()} ({windows.read_raw_f32(args.raw).size} samples)")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "spectrum":
            return cmd_spectrum(args)
        if args.command == "pitch":
            return cmd_pitch(args)
        if args.command == "window":
            return cmd_window(args)
        if args.command == "tolerances":
            print(tolerances.format_table())
            return 0
    except (OSError, ValueError, KeyError) as exc:   # ManifestMismatch is a ValueError
        print(f"golden_compare {args.command}: {exc}", file=sys.stderr)
        return 2
    raise SystemExit(2)  # pragma: no cover — argparse enforces the choices
