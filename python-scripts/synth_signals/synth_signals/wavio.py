# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""16-bit mono RIFF/WAVE through the stdlib ``wave`` module — no soundfile, no scipy.io.

The bytes are produced in memory first (:func:`wav_bytes`) so that ``generate``
and ``check`` hash the *same* bytes: what ``check`` regenerates and compares is
exactly what ``generate`` wrote, header included. ``wave`` writes a canonical
44-byte header (RIFF / fmt / data, PCM 16-bit, little-endian), which is what
the sha256 in the manifest covers.

Not a CLI module.
"""

from __future__ import annotations

import io
import wave
from pathlib import Path

import numpy as np

BIT_DEPTH = 16
CHANNELS = 1


def wav_bytes(samples: np.ndarray, fs: int) -> bytes:
    """Encode int16 mono samples at ``fs`` as a complete WAV file, returned as bytes."""
    samples = np.asarray(samples)
    if samples.dtype != np.int16 or samples.ndim != 1:
        raise TypeError(f"expected 1-D int16 samples, got {samples.dtype} ndim={samples.ndim}")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(BIT_DEPTH // 8)
        w.setframerate(int(fs))
        w.writeframes(samples.astype("<i2", copy=False).tobytes())
    return buf.getvalue()


def write_wav(path: Path, samples: np.ndarray, fs: int) -> bytes:
    """Write the WAV and return the bytes written (for hashing)."""
    data = wav_bytes(samples, fs)
    Path(path).write_bytes(data)
    return data


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """Read a 16-bit mono WAV back as ``(int16 samples, fs)``; rejects anything else."""
    with wave.open(str(path), "rb") as w:
        if w.getnchannels() != CHANNELS or w.getsampwidth() != BIT_DEPTH // 8:
            raise ValueError(f"{path}: not 16-bit mono")
        fs = w.getframerate()
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype="<i2").astype(np.int16), fs
