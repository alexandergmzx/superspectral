# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""The one WAV reader of the host: stdlib `wave`, 16-bit PCM only, samples returned as int16 untouched.

Why the standard library and not scipy.io.wavfile or soundfile: `wave` reads
PCM WAV and nothing else, which is the format the Tier-0 generator writes and
the watch records (ADR 0002; the take format itself is a separate contract).
A richer reader would happily open a 24-bit or float WAV, convert it, and
hand back int16 — and the manifest's `inputs[].bit_depth: 16` would then
describe a file that was never int16. So:

  * anything but 16-bit PCM is refused (`UnsupportedWav`), never converted;
  * samples come back as the file's own int16, shape `[n_frames, channels]`,
    with no scaling — the int16 → float seam is applied exactly once, later,
    by `spectrum.int16_to_float` / `praat.sound_from_int16` (ADR 0003 d.2,
    ADR 0006 D3), so this module never touches `int16_scale`;
  * a multichannel file is returned as such; `WavFile.mono` refuses to
    down-mix, because summing channels changes the level by a convention
    nobody wrote down. Pick a channel explicitly if that is what you mean.

The sha256 a manifest records for an input is over the file's bytes
(`hashing.sha256_file`), not over this array; they differ by the 44-byte
header, and the bytes are what `verify` can recompute without a reader.

CLI:

    uv run --project host python -m spectral_host.wavio FILE.wav [...]

prints, per file, the sample rate, channels, bit depth, frame count, duration
and the sha256 of the bytes — the fields of a manifest `inputs[]` entry.
"""

from __future__ import annotations

import argparse
import os
import sys
import wave
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from spectral_host.hashing import sha256_file

#: The only sample format this reader admits (manifest `inputs[].bit_depth`).
SUPPORTED_BIT_DEPTH = 16


class UnsupportedWav(ValueError):
    """The file is a WAV this project does not read (not 16-bit PCM, or not PCM at all)."""


@dataclass(frozen=True)
class WavFile:
    """A decoded 16-bit PCM WAV: `samples` is int16 `[n_frames, channels]`, unscaled."""

    samples: np.ndarray
    sample_rate: int
    channels: int
    bit_depth: int

    @property
    def n_frames(self) -> int:
        return int(self.samples.shape[0])

    @property
    def duration_s(self) -> float:
        return self.n_frames / float(self.sample_rate)

    @property
    def mono(self) -> np.ndarray:
        """The single channel as a 1-D int16 array; refuses to down-mix a multichannel file."""
        if self.channels != 1:
            raise ValueError(
                f"file has {self.channels} channels; refusing to down-mix (the level convention would be "
                "unstated) — index samples[:, k] to pick one"
            )
        return self.samples[:, 0]


def read_wav(path: str | os.PathLike[str]) -> WavFile:
    """Read a 16-bit PCM WAV into int16 `[n_frames, channels]`; anything else raises `UnsupportedWav`.

    `wave` itself rejects non-PCM encodings (float, µ-law, ADPCM) with
    `wave.Error`; that is re-raised as `UnsupportedWav` so a caller has one
    exception to catch. 8-, 24- and 32-bit PCM open fine in `wave` and are
    refused here on `sampwidth`.
    """
    try:
        with wave.open(os.fspath(path), "rb") as wf:
            sampwidth = wf.getsampwidth()
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            if sampwidth * 8 != SUPPORTED_BIT_DEPTH:
                raise UnsupportedWav(
                    f"{path}: {sampwidth * 8}-bit PCM; only {SUPPORTED_BIT_DEPTH}-bit PCM is read "
                    "(no conversion, so that inputs[].bit_depth describes the bytes)"
                )
            raw = wf.readframes(n_frames)
    except (wave.Error, EOFError) as exc:
        # `wave` raises EOFError, not wave.Error, for an empty or truncated header.
        raise UnsupportedWav(f"{path}: not a PCM WAV this reader accepts ({exc!r})") from exc
    if channels < 1:
        raise UnsupportedWav(f"{path}: {channels} channels")
    samples = np.frombuffer(raw, dtype="<i2")
    if samples.size != n_frames * channels:
        raise UnsupportedWav(
            f"{path}: header promises {n_frames} frames x {channels} channels, data holds {samples.size} samples"
        )
    samples = samples.reshape(n_frames, channels).astype(np.int16, copy=True)
    return WavFile(samples=samples, sample_rate=int(sample_rate), channels=int(channels), bit_depth=SUPPORTED_BIT_DEPTH)


# --- CLI -------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m spectral_host.wavio",
        description="Describe 16-bit PCM WAV files the way a manifest inputs[] entry does.",
    )
    parser.add_argument("files", metavar="FILE.wav", nargs="+")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    status = 0
    for raw in args.files:
        try:
            wav = read_wav(raw)
        except (OSError, UnsupportedWav) as exc:
            print(f"error: {exc}", file=sys.stderr)
            status = 2
            continue
        print(
            f"{raw}: sample_rate={wav.sample_rate} channels={wav.channels} bit_depth={wav.bit_depth} "
            f"frames={wav.n_frames} duration_s={wav.duration_s:.6g} sha256={sha256_file(Path(raw))}"
        )
    return status


if __name__ == "__main__":
    sys.exit(main())
