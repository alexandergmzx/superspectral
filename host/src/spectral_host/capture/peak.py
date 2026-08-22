# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""The founding research document's **M0**: print the interpolated peak frequency, per interval.

Behind `spectral-web peak` (ADR 0021 decision 1). Two input modes, one
numerical path:

    spectral-web peak --wav datasets/tier0-synthetic/sine_1000_m20dBFS_32k.wav --once
    spectral-web peak --preset live_singing            # this machine's microphone

Both end in `spectral_host.spectrum` and in nothing else. There is no second
window function here, no second normalisation and no second dB reference: the
window comes from the family's **coefficients** through
`spectrum.window_float64` (ADR 0006 D1 — never a SciPy window *by name*, because
`scipy.signal.get_window("hann")` is the symmetric form and its NENBW is
1.500366, not 1.5), the level is S1 / power-spectrum / full-scale-sine
(ADR 0006 D2, D3), and the int16 → float division by 32768 happens exactly once,
inside `spectrum.int16_to_float`, where every other consumer's does
(ADR 0003 d.2). The gate this module exists to pass —
`sine_1000_m20dBFS_32k.wav` read within **≤ 3 cents** (roadmap W0, the
peak-frequency row of docs/validation/README.md) — is a gate on those
conventions as much as on the interpolation.

**Interpolation.** The peak bin of a windowed sinusoid is not the sinusoid's
frequency: at N = 4096 and fs = 32 kHz a bin is 7.8125 Hz, so a raw `argmax`
can be half a bin — 3.90625 Hz — from the truth. That is **6.75 cents at
1 kHz** and **66 cents at 100 Hz**, because a fixed frequency error is a
widening interval as the note falls; both are outside the ≤ 3 cents gate, and
the low end of a bass's range is where the raw bin is worst. (This line read
"68 cents at 1 kHz" until 2026-08-22: 68 cents is the 100 Hz figure, and at
1 kHz the true worst case is 6.75. The conclusion — interpolate — is
unchanged; the number was not.) A parabola fitted through
the peak bin and its two neighbours **in dB** (Smith, *Spectral Audio Signal
Processing*, "Quadratic Interpolation of Spectral Peaks") gives

    d = 0.5·(a − g) / (a − 2b + g),     f = (k + d)·fs/N,     ŷ = b − 0.25·(a − g)·d

with a, b, g the levels at k−1, k, k+1. In dB, not in linear power: a Gaussian
window's log-magnitude main lobe IS a parabola, and for the cosine-sum families
the dB fit is the better approximation of the two — the same choice the
TypeScript module will make at W1, where the two are held to the same row.

**Live capture.** `sounddevice` is imported lazily, inside the function that
opens the stream, so the WAV mode needs no PortAudio and the gate above runs in
CI on a machine with no sound card. The stream is opened with `dtype="int16"`
— PortAudio's own conversion to float would apply a scaling this project has
not stated, and the seam has to stay single. The callback does exactly one
thing: copy the block into a **preallocated** ring (`SampleRing.push`). No
allocation, no I/O, no Python-level per-sample loop, no printing — the
sounddevice manual's own rule for the callback, and the reason the FFT runs on
the main thread.

Live readings are *(prov.)* as measurements: the ring is read without a lock
(a torn read is possible, though the ring is sized several frames deep), and
this machine's capture chain is not characterised. ADR 0021 decision 3 — no
number from the web application, this printer included, may be quoted for any
bound of proposal §1.
"""

from __future__ import annotations

import argparse
import math
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from spectral_host import spectrum, wavio
from spectral_host.presets import load_preset, spectrum_config_from_preset
from spectral_host.web.extras import require_extra

#: Default transform when no preset is named: the convention ADR 0006 ratifies.
DEFAULT_WINDOW = "hann"
DEFAULT_FFT_SIZE = 4096

#: `(prov.)` — the presets say 32 kHz (ADR 0003), and a live device that cannot
#: give it makes `bin_width_hz` fiction, so the rate is asserted, never resampled.
DEFAULT_SAMPLE_RATE = 32000

#: `(prov.)` — ten readings a second is legible in a terminal. The presets'
#: own `interval_ms` (20 ms live, ADR 0010) overrides it when `--preset` is used.
DEFAULT_INTERVAL_MS = 100.0

#: Ring depth, in analysis frames. Four is enough that the writer is nowhere
#: near the samples the reader is copying at any plausible block size `(prov.)`.
RING_FRAMES = 4

#: Seconds to wait for the first full frame before giving up on a live stream.
DEFAULT_TIMEOUT_S = 10.0

#: A4 = 440 Hz — the only place a musical constant enters this module, and only
#: for the `--reference` cents readout the ≤ 3 cents gate is expressed in.
CENTS_PER_OCTAVE = 1200.0


class NoAudio(RuntimeError):
    """A live stream produced no full analysis frame before the timeout."""


def cents(f: float, reference: float) -> float:
    """Interval from `reference` to `f`, in cents: 1200·log2(f/ref). The unit every f0 row of this project uses."""
    if f <= 0 or reference <= 0:
        raise ValueError("cents are defined for positive frequencies only, got %r and %r" % (f, reference))
    return CENTS_PER_OCTAVE * math.log2(f / reference)


@dataclass(frozen=True)
class PeakReading:
    """One interval's answer: the interpolated peak, the bin it grew out of, and its level."""

    #: Interpolated peak frequency, Hz.
    frequency_hz: float
    #: The bin `argmax` chose, before interpolation.
    bin_index: int
    #: Sub-bin offset `d` from the interpolation, in bins; |d| ≤ 0.5 for a true peak.
    delta_bins: float
    #: Interpolated level at the peak, dBFS (0 dBFS = a full-scale sine, ADR 0006 D3).
    level_dbfs: float
    #: Start sample of the frame this reading came from, in the source.
    frame_start: int

    def format(self) -> str:
        """The printed line: `<f> Hz  (bin k, <level> dBFS)` — the founding document's M0 output."""
        return "%.3f Hz  (bin %d, %.2f dBFS)" % (self.frequency_hz, self.bin_index, self.level_dbfs)


def interpolate_peak(levels_db: np.ndarray, k: int) -> tuple[float, float]:
    """Parabolic interpolation on the dB values around bin `k` → `(delta_bins, level_db)`.

    `d = 0.5(a − g)/(a − 2b + g)` and `ŷ = b − 0.25(a − g)d`. Returns `(0.0,
    b)` unchanged when `k` is an edge bin (no two neighbours) or when the
    denominator is not a downward parabola — a flat or rising triple is not a
    peak, and extrapolating from one would move the answer away from the data.
    """
    levels = np.asarray(levels_db, dtype=np.float64)
    if k <= 0 or k >= levels.size - 1:
        return 0.0, float(levels[k])
    a, b, g = float(levels[k - 1]), float(levels[k]), float(levels[k + 1])
    denominator = a - 2.0 * b + g
    if denominator >= 0.0 or not math.isfinite(denominator):
        return 0.0, b
    d = 0.5 * (a - g) / denominator
    if not math.isfinite(d) or abs(d) > 1.0:
        return 0.0, b
    return d, b - 0.25 * (a - g) * d


def _search_bounds(fs: float, fft_size: int, min_hz: float | None, max_hz: float | None) -> tuple[int, int]:
    """Inclusive bin range to search, always inside `1 … N/2−1` so interpolation has both neighbours.

    DC and Nyquist are excluded on purpose: neither has two neighbours, and DC
    is where an uncorrected offset lives — the peak of a signal with a DC
    offset is a fact about the ADC, not about the note being sung.
    """
    n_bins = fft_size // 2 + 1
    lo, hi = 1, n_bins - 2
    bin_width = float(fs) / float(fft_size)
    if min_hz is not None:
        lo = max(lo, int(math.ceil(min_hz / bin_width)))
    if max_hz is not None:
        hi = min(hi, int(math.floor(max_hz / bin_width)))
    if lo > hi:
        raise ValueError(
            "search band [%s, %s] Hz holds no interpolable bin at fs = %g, N = %d (bin width %g Hz)"
            % (min_hz, max_hz, fs, fft_size, bin_width)
        )
    return lo, hi


def peak_of_frame(
    frame_int16: np.ndarray,
    fs: float,
    cfg: spectrum.SpectrumConfig,
    min_hz: float | None = None,
    max_hz: float | None = None,
    frame_start: int = 0,
) -> PeakReading:
    """One frame of int16 PCM → its interpolated peak, through `spectrum.reference_spectrum` and nothing else.

    `reference_spectrum` is the whole numerical path: `int16_to_float` (the one
    1/32768), the periodic window from coefficients, the unnormalised rfft, the
    S1 power spectrum with the factor 2 on bins 1 … N/2−1 only, and dBFS
    against a full-scale sine. This function only picks a bin out of its
    second column and fits a parabola through three of them.
    """
    spec = spectrum.reference_spectrum(np.asarray(frame_int16), fs, cfg)
    levels = spec[:, 1]
    lo, hi = _search_bounds(fs, cfg.fft_size, min_hz, max_hz)
    k = int(lo + int(np.argmax(levels[lo : hi + 1])))
    delta, level = interpolate_peak(levels, k)
    return PeakReading(
        frequency_hz=(k + delta) * float(fs) / float(cfg.fft_size),
        bin_index=k,
        delta_bins=delta,
        level_dbfs=level,
        frame_start=int(frame_start),
    )


# --- WAV mode ----------------------------------------------------------------------


def wav_peaks(
    path: Path,
    cfg: spectrum.SpectrumConfig,
    hop: int,
    min_hz: float | None = None,
    max_hz: float | None = None,
    limit: int | None = None,
    channel: int = 0,
) -> Iterator[PeakReading]:
    """Peaks of a 16-bit PCM WAV on the device frame grid — `read_wav` then `wav_peaks_of`.

    `read_wav` refuses anything but 16-bit PCM (`UnsupportedWav`); no
    conversion happens anywhere on this path.
    """
    return wav_peaks_of(wavio.read_wav(path), cfg, hop, min_hz, max_hz, limit=limit, channel=channel, label=str(path))


def wav_peaks_of(
    wav: wavio.WavFile,
    cfg: spectrum.SpectrumConfig,
    hop: int,
    min_hz: float | None = None,
    max_hz: float | None = None,
    limit: int | None = None,
    channel: int = 0,
    label: str = "<wav>",
) -> Iterator[PeakReading]:
    """Peaks of an already-read WAV on the device frame grid: frame k covers `[k·hop, k·hop + N)`.

    `spectrum.frames_from_zero`'s grid — no centring, no padding, first frame
    from sample 0 (golden-files.md's "frame-grid trap"), so a reading here and
    a golden spectrum of the same file describe the same samples. A file
    shorter than one frame is an error from `reference_spectrum`, not a
    zero-padded reading of a signal that was never there.

    Takes the `WavFile` rather than the path so that `run_peak` can state the
    file's OWN rate in its header line without reading the file twice — the
    rate the transform uses is `wav.sample_rate` and nothing else.
    """
    samples = wav.samples[:, channel] if wav.channels > 1 else wav.mono
    n = cfg.window_length_samples
    if samples.size < n:
        raise ValueError(
            "%s holds %d samples; one analysis frame is %d (fft_size). Choose a smaller --fft-size or a longer file."
            % (label, samples.size, n)
        )
    emitted = 0
    for start in range(0, samples.size - n + 1, hop):
        yield peak_of_frame(samples[start : start + n], wav.sample_rate, cfg, min_hz, max_hz, frame_start=start)
        emitted += 1
        if limit is not None and emitted >= limit:
            return


# --- live mode ---------------------------------------------------------------------


class SampleRing:
    """A preallocated int16 ring the audio callback copies into, and nothing else.

    The callback's rule (sounddevice's own): no allocation, no I/O, no locks,
    no Python-level per-sample loop. `push` therefore does slice assignment
    through `np.copyto` into a buffer allocated once in `__init__` — the
    buffer object never changes identity and never grows.
    `host/tests/test_web_peak.py` asserts both: that no numpy array constructor
    is called during a callback, and that the buffer's memory address is the
    same before and after.
    """

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("ring capacity must be positive, got %r" % (capacity,))
        self.buffer = np.zeros(int(capacity), dtype=np.int16)
        self.write = 0
        #: Total samples ever written — the main thread's clock for "a new frame is due".
        self.written = 0
        #: Blocks larger than the ring; a real one means the reader is too slow.
        self.overruns = 0

    @property
    def capacity(self) -> int:
        return int(self.buffer.shape[0])

    def push(self, block: np.ndarray) -> None:
        """Copy `block` (1-D int16, a view is fine) into the ring. Called from the audio thread."""
        cap = self.capacity
        n = int(block.shape[0])
        if n <= 0:
            return
        if n >= cap:
            np.copyto(self.buffer, block[n - cap :])
            self.write = 0
            self.written += n
            self.overruns += 1
            return
        end = self.write + n
        if end <= cap:
            np.copyto(self.buffer[self.write : end], block)
        else:
            first = cap - self.write
            np.copyto(self.buffer[self.write :], block[:first])
            np.copyto(self.buffer[: n - first], block[first:])
        self.write = end % cap
        self.written += n

    def latest(self, n: int) -> np.ndarray | None:
        """A COPY of the `n` most recent samples, or None while fewer than `n` have arrived. Main thread only.

        Read without a lock. A block boundary crossing the copy would tear one
        frame; the ring is `RING_FRAMES` frames deep so the writer is far from
        the samples being read, and a live reading is `(prov.)` in any case —
        the injection path is where this project's numbers come from.
        """
        cap = self.capacity
        if n > cap or self.written < n:
            return None
        start = (self.write - n) % cap
        if start + n <= cap:
            return self.buffer[start : start + n].copy()
        out = np.empty(n, dtype=np.int16)
        first = cap - start
        out[:first] = self.buffer[start:]
        out[first:] = self.buffer[: n - first]
        return out


def make_callback(ring: SampleRing, channel: int = 0) -> Any:
    """The sounddevice callback: one slice-assignment into `ring`. Closes over nothing else."""

    def callback(indata: np.ndarray, frames: int, time_info: Any, status: Any) -> None:
        # `indata[:, channel]` is a VIEW — no copy, no allocation; `push`
        # writes through it into the preallocated buffer. `status` is
        # deliberately not printed: printing from the audio thread is I/O in
        # the callback, and overruns are counted by the ring instead.
        ring.push(indata[:, channel])

    return callback


def live_peaks(
    cfg: spectrum.SpectrumConfig,
    fs: int,
    hop: int,
    block: int,
    device: str | int | None = None,
    min_hz: float | None = None,
    max_hz: float | None = None,
    limit: int | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    sleep: Any = time.sleep,
) -> Iterator[PeakReading]:
    """Open an input stream and yield one reading per `hop` samples of new audio.

    `sounddevice` is imported HERE: `require_extra("capture")` raises
    `ExtraMissing` (CLI exit 2, HTTP 501) before the import is attempted, so a
    machine without PortAudio gets the install line and not an `OSError` from
    a shared library.

    The device's own sample rate is asserted against `fs` rather than
    resampled — the rule ADR 0021 decision 7(c) states for the browser, applied
    here for the same reason: a silent resampler makes `bin_width_hz` fiction.
    """
    require_extra("capture")
    import sounddevice  # noqa: PLC0415 — lazy by design; see the docstring

    n = cfg.window_length_samples
    ring = SampleRing(max(RING_FRAMES * n, n + block))
    stream = sounddevice.InputStream(
        samplerate=fs,
        channels=1,
        dtype="int16",  # the 1/32768 seam stays single (ADR 0003 d.2)
        blocksize=block,
        device=device,
        callback=make_callback(ring),
    )
    with stream:
        actual = int(getattr(stream, "samplerate", fs) or fs)
        if actual != int(fs):
            raise ValueError(
                "device opened at %d Hz, not the requested %d Hz. Nothing here resamples (ADR 0021 decision 7c): "
                "pass --rate %d, or choose another --device." % (actual, fs, actual)
            )
        deadline = time.monotonic() + float(timeout_s)
        emitted = 0
        next_due = n
        while True:
            if ring.written >= next_due:
                frame = ring.latest(n)
                if frame is not None:
                    yield peak_of_frame(frame, fs, cfg, min_hz, max_hz, frame_start=ring.written - n)
                    emitted += 1
                    if limit is not None and emitted >= limit:
                        return
                    next_due = ring.written + hop
                    deadline = time.monotonic() + float(timeout_s)
                    continue
            if time.monotonic() > deadline:
                raise NoAudio(
                    "no full analysis frame in %.1f s (%d samples of %d arrived). Is --device right, and is "
                    "anything reaching the input?" % (timeout_s, ring.written, n)
                )
            sleep(0.005)


# --- configuration ------------------------------------------------------------------


@dataclass(frozen=True)
class PeakConfig:
    """Everything `run_peak` needs, resolved once from the command line and/or a preset."""

    cfg: spectrum.SpectrumConfig
    sample_rate_hz: int
    hop: int
    source: str


def _resolve_preset(reference: str, presets_dir: Path | None) -> Any:
    """`--preset` takes a path or a bare id; an id is resolved against `protocols/presets/`."""
    candidate = Path(reference)
    if candidate.suffix == ".json" or candidate.exists():
        return load_preset(candidate)
    if presets_dir is None:
        raise ValueError("--preset %r is not a file and no presets directory was found" % (reference,))
    return load_preset(presets_dir / ("%s.json" % reference))


def resolve_config(args: argparse.Namespace, presets_dir: Path | None = None) -> PeakConfig:
    """Turn the parsed arguments into a `SpectrumConfig`, a rate and a hop.

    A preset supplies all three (ADR 0021 decision 7: the preset is the
    contract, and the CLI reads the same file the browser fetches). Without
    one, the ADR 0006 default convention is used at `--fft-size` / `--window`.
    `--rate` and `--interval-ms` are refused ALONGSIDE `--preset` rather than
    silently overriding it: a reading taken at a rate the preset does not name
    is not that preset's reading. Both therefore default to **None** rather
    than to `DEFAULT_SAMPLE_RATE` / `DEFAULT_INTERVAL_MS`, because argparse
    cannot otherwise tell a typed value from a default and the refusal would
    fire on every `--preset` run.
    """
    if args.preset:
        conflicting = [
            flag
            for flag, value in (("--rate", args.rate), ("--interval-ms", args.interval_ms))
            if value is not None
        ]
        if conflicting:
            raise ValueError(
                "%s cannot be combined with --preset: the preset states its own sample_rate_hz and interval_ms "
                "(ADR 0010 decision 4), and a reading taken at a rate the preset does not name is not that "
                "preset's reading. Drop %s, or drop --preset."
                % (" and ".join(conflicting), " and ".join(conflicting))
            )
        preset = _resolve_preset(args.preset, presets_dir)
        cfg = spectrum_config_from_preset(preset)
        analysis = preset.analysis
        fs = int(analysis["sample_rate_hz"])
        hop = int(round(float(analysis["resolution"]["hop_samples"])))
        return PeakConfig(cfg=cfg, sample_rate_hz=fs, hop=hop, source="preset %s (%s)" % (preset.id, preset.sha256[:12]))
    n = int(args.fft_size)
    interval_ms = DEFAULT_INTERVAL_MS if args.interval_ms is None else float(args.interval_ms)
    cfg = spectrum.SpectrumConfig(
        window=args.window,
        window_length_samples=n,
        fftbins=True,
        fft_size=n,
        normalization="S1",
        scaling="power_spectrum",
        dbfs_reference="sine",
        int16_scale=spectrum.DEFAULT_INT16_SCALE,
        dtype="float64",
    )
    fs = DEFAULT_SAMPLE_RATE if args.rate is None else int(args.rate)
    hop = max(1, int(round(interval_ms * fs / 1000.0)))
    return PeakConfig(cfg=cfg, sample_rate_hz=fs, hop=hop, source="%s N=%d (ADR 0006 default convention)" % (args.window, n))


def add_peak_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Attach `peak`'s arguments. Lives here so the subcommand and the module cannot drift."""
    source = parser.add_argument_group("input")
    source.add_argument("--wav", type=Path, default=None, metavar="FILE", help="read a 16-bit PCM WAV instead of capturing live")
    source.add_argument("--device", default=None, help="input device name or index (live mode; sounddevice's own naming)")
    source.add_argument("--channel", type=int, default=0, help="channel index of a multichannel source (default: 0)")

    analysis = parser.add_argument_group("analysis")
    analysis.add_argument("--preset", default=None, metavar="ID|FILE", help="take window, fft_size, rate and interval from a preset (ADR 0010)")
    analysis.add_argument("--window", default=DEFAULT_WINDOW, choices=sorted(spectrum.WINDOW_FAMILIES), help="window family, built from its coefficients (default: %(default)s)")
    analysis.add_argument("--fft-size", type=int, default=DEFAULT_FFT_SIZE, help="transform length in samples (default: %(default)s)")
    analysis.add_argument("--rate", type=int, default=None, help="live capture rate in Hz; asserted, never resampled (default: %d; refused with --preset)" % DEFAULT_SAMPLE_RATE)
    analysis.add_argument("--interval-ms", type=float, default=None, help="hop between readings in ms (default: %g; refused with --preset)" % DEFAULT_INTERVAL_MS)
    analysis.add_argument("--min-hz", type=float, default=None, help="lower edge of the search band (default: the first interpolable bin)")
    analysis.add_argument("--max-hz", type=float, default=None, help="upper edge of the search band (default: just below Nyquist)")

    output = parser.add_argument_group("output")
    output.add_argument("--once", action="store_true", help="print one reading and exit")
    output.add_argument("--frames", type=int, default=None, metavar="N", help="stop after N readings (default: the whole file / until interrupted)")
    output.add_argument("--reference", type=float, default=None, metavar="HZ", help="also print the error from HZ in cents — the ≤ 3 cents gate's readout")
    output.add_argument("--block", type=int, default=None, metavar="SAMPLES", help="live capture block size (default: the hop)")
    output.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="seconds to wait for live audio before giving up (default: %(default)s)")
    return parser


def run_peak(args: argparse.Namespace, presets_dir: Path | None = None, stream: Any = None) -> int:
    """Print one line per interval. Exit 0 on a clean run; the caller maps exceptions to statuses.

    The configuration line goes to **stderr** and the readings to **stdout**,
    so `spectral-web peak --wav ... | awk '{print $1}'` is a column of
    frequencies and nothing else.
    """
    import sys

    out = sys.stdout if stream is None else stream
    resolved = resolve_config(args, presets_dir)
    limit = 1 if args.once else args.frames
    wav = None
    fs, hop = resolved.sample_rate_hz, resolved.hop
    if args.wav is not None:
        # Read the header BEFORE the configuration line is printed. In WAV mode
        # the rate that reaches `reference_spectrum` is the FILE's — nothing
        # here resamples — so a header quoting `--rate` (or a preset's rate)
        # would state a bin width the transform never used.
        wav = wavio.read_wav(args.wav)
        fs = int(wav.sample_rate)
        if args.preset and fs != resolved.sample_rate_hz:
            # ADR 0021 decision 7(c), applied to the file path exactly as
            # `live_peaks` applies it to the device: validate and reject, and
            # name both rates. Silently analysing a 48 kHz file on a 32 kHz
            # preset's hop would attribute a reading to a preset that does not
            # describe it (ADR 0010 decision 7: reject, never coerce).
            raise ValueError(
                "%s is %d Hz and %s states sample_rate_hz = %d. Nothing here resamples "
                "(ADR 0021 decision 7c): drop --preset, or use a file at the preset's rate."
                % (args.wav, fs, resolved.source, resolved.sample_rate_hz)
            )
        if not args.preset:
            # `--interval-ms` is a duration, so its hop follows the file's rate.
            interval_ms = DEFAULT_INTERVAL_MS if args.interval_ms is None else float(args.interval_ms)
            hop = max(1, int(round(interval_ms * fs / 1000.0)))
    print(
        "# %s  fs=%d Hz  N=%d  hop=%d  bin=%.6g Hz  %s"
        % (
            resolved.source,
            fs,
            resolved.cfg.fft_size,
            hop,
            fs / resolved.cfg.fft_size,
            "wav=%s" % args.wav if args.wav else "live",
        ),
        file=sys.stderr,
    )
    if wav is not None:
        readings: Iterator[PeakReading] = wav_peaks_of(
            wav, resolved.cfg, hop, args.min_hz, args.max_hz, limit=limit, channel=args.channel, label=str(args.wav)
        )
    else:
        block = int(args.block) if args.block else resolved.hop
        readings = live_peaks(
            resolved.cfg,
            resolved.sample_rate_hz,
            resolved.hop,
            block,
            device=args.device,
            min_hz=args.min_hz,
            max_hz=args.max_hz,
            limit=limit,
            timeout_s=args.timeout,
        )
    for reading in readings:
        line = reading.format()
        if args.reference:
            line += "  (%+.2f cents re %g Hz)" % (cents(reading.frequency_hz, args.reference), args.reference)
        print(line, file=out, flush=True)
    return 0


__all__ = [
    "CENTS_PER_OCTAVE",
    "DEFAULT_FFT_SIZE",
    "DEFAULT_INTERVAL_MS",
    "DEFAULT_SAMPLE_RATE",
    "DEFAULT_TIMEOUT_S",
    "DEFAULT_WINDOW",
    "NoAudio",
    "PeakConfig",
    "PeakReading",
    "RING_FRAMES",
    "SampleRing",
    "add_peak_arguments",
    "cents",
    "interpolate_peak",
    "live_peaks",
    "make_callback",
    "peak_of_frame",
    "resolve_config",
    "run_peak",
    "wav_peaks",
    "wav_peaks_of",
]
