# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""Audio capture on the HOST machine — this laptop's microphone, never the watch's (ADR 0002, ADR 0021 d.5).

There is no live link between watch and host: no audio or spectrum is ever
transported from the device, and nothing here is in the watch's loop. What this
package captures is the sound in front of the machine running it, which is a
different claim and is labelled as one everywhere it is reported.

W0 ships `peak.py`, the founding research document's **M0**: window, transform,
interpolate, print the peak frequency. `sounddevice` (the `capture` extra) is
imported lazily, inside the function that opens a stream, so that the WAV mode
— the mode the roadmap's ≤ 3 cents gate runs on — needs no PortAudio at all.
"""

from __future__ import annotations
