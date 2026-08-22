# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: Apache-2.0
"""Tests for the Tier-0 generator — each named for the hazard it guards.

Spectral assertions use the ADR 0006 convention directly (periodic cosine-sum
window from coefficients, S1 scaling, factor 2 on the interior bins, 0 dBFS =
full-scale sine) so that a test here is also a first reading of the convention
against known signals. No WAV fixtures: everything is regenerated, which is
the property under test.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
import yaml
from scipy.signal import hilbert, lfilter, welch
from scipy.signal.windows import general_cosine

from synth_signals import catalogue, cli, manifest, quantise, signals, wavio

FS = catalogue.FS_WATCH
N = catalogue.N_REF  # 4096 — the watch default analysis size
BIN = FS / N  # 7.8125 Hz

HANN = [0.5, 0.5]  # preset-schema.md §4.3 coefficients, periodic form (ADR 0006 D1)


def _ps_dbfs(x: np.ndarray, coefficients: list[float], n: int = N) -> np.ndarray:
    """Power spectrum in dBFS per ADR 0006 D2/D3 on the first ``n`` samples."""
    w = general_cosine(n, coefficients, sym=False)
    s1 = w.sum()
    spec = np.fft.rfft(x[:n] * w)
    ps = np.abs(spec) ** 2 / s1**2
    ps[1:-1] *= 2.0  # factor 2 on k = 1 … N/2−1 only; DC and Nyquist not doubled
    return 10.0 * np.log10(np.maximum(ps / 0.5, 1e-20))


# --- spectral truths --------------------------------------------------------


def test_on_bin_sine_puts_all_energy_in_one_bin_under_rect():
    """437.5 Hz is 56 × 7.8125: under a rectangular window the periodogram is one line."""
    x = catalogue.by_name("sine_437p5_m20dBFS_32k").render()
    power = np.abs(np.fft.rfft(x[:N])) ** 2
    assert np.argmax(power) == 56
    assert power[56] / power.sum() > 1.0 - 1e-12
    # and the discriminating half: 440 Hz (56.32 bins) leaks, so the test is not vacuous
    x_off = catalogue.by_name("sine_440_m20dBFS_32k").render()
    power_off = np.abs(np.fft.rfft(x_off[:N])) ** 2
    assert power_off.max() / power_off.sum() < 0.9


def test_full_scale_sine_reads_0_dbfs_and_full_scale_square_reads_plus_2p1_per_bin_under_hann():
    """ADR 0006 D3's two rows: peak bin 0.00 dBFS for the sine, +2.10 dB (sampled: +2.11) for the square's fundamental."""
    sine = _ps_dbfs(signals.sine(1000.0, FS, 1.0, 0.0), HANN)
    assert sine[128] == pytest.approx(0.0, abs=1e-9)
    built = catalogue.build(catalogue.by_name("square_1000_0dBFS_32k"))
    truth = catalogue.ground_truth(built)["derived"]
    square = _ps_dbfs(built.x, HANN)
    assert square[128] == pytest.approx(truth["fundamental_bin_dbfs_expected"], abs=1e-6)
    assert truth["fundamental_bin_dbfs_expected"] == pytest.approx(2.112, abs=1e-3)
    assert truth["fundamental_bin_dbfs_ideal"] == pytest.approx(2.098, abs=1e-3)
    # total power: Σ PS / NENBW = +3.01 dBFS (NENBW = 1.5 for periodic hann, ADR 0006 D2 closed form)
    w = general_cosine(N, HANN, sym=False)
    ps = np.abs(np.fft.rfft(built.x[:N] * w)) ** 2 / w.sum() ** 2
    ps[1:-1] *= 2.0
    nenbw = N * np.sum(w * w) / w.sum() ** 2
    assert nenbw == pytest.approx(1.5, abs=1e-9)
    assert 10 * np.log10(ps.sum() / nenbw / 0.5) == pytest.approx(truth["total_power_dbfs_expected"], abs=1e-6)


def test_two_tone_components_sit_exactly_delta_bins_apart_at_n4096():
    """The resolution vectors must be 0.5/1/2/4 bins apart, not 'about'; Δf is a catalogue parameter."""
    for delta, name in ((0.5, "twotone_1000_d0p5bin_32k"), (1.0, "twotone_1000_d1bin_32k"), (2.0, "twotone_1000_d2bin_32k"), (4.0, "twotone_1000_d4bin_32k")):
        e = catalogue.by_name(name)
        assert (e.params["f2_hz"] - e.params["f1_hz"]) / BIN == pytest.approx(delta, abs=1e-12)
    # the 4-bin pair resolves under hann into two separate peaks at bins 128 and 132
    x = catalogue.by_name("twotone_1000_d4bin_32k").render()
    db = _ps_dbfs(x, HANN)
    assert db[128] > db[130] + 20 and db[132] > db[130] + 20
    # each component carries level_dbfs − 6.02 dB (envelope convention): the on-bin 1000 Hz
    # component of a −20 dBFS pair must read −26.02 dBFS, not −20 (mutation that dropped the
    # /2 passed every test until 2026-08-21)
    assert db[128] == pytest.approx(-20.0 + 20.0 * np.log10(0.5), abs=1e-6)
    assert catalogue.ground_truth(catalogue.build(catalogue.by_name("twotone_1000_d4bin_32k")))["derived"][
        "component_amplitude"
    ] == pytest.approx(0.05, rel=1e-12)


def test_dc_bin_is_not_doubled_and_reads_the_offset_exactly():
    """ADR 0006 D2's stricter-than-Heinzel rule: the factor 2 is for k = 1 … N/2−1 only. A 0.1 DC offset
    is PS = 0.01 at k = 0 → −16.99 dBFS; a helper that doubled DC would read −13.98 (the 3.01 dB row)."""
    x = catalogue.by_name("dc_0p1_plus_sine_440_m20dBFS_32k").render()
    db = _ps_dbfs(x, HANN)
    # 1e-4: the off-bin 440 Hz sine leaks ≈ −112 dB (hann, 56 bins away) into k = 0 → ≈ 1e-5 dB
    assert db[0] == pytest.approx(10.0 * np.log10(0.1**2 / 0.5), abs=1e-4)
    assert db[0] != pytest.approx(10.0 * np.log10(2 * 0.1**2 / 0.5), abs=1.0)
    # Nyquist likewise: a full-scale alternating sequence is PS = 1 at k = N/2 → +3.01 dBFS undoubled
    alt = np.where(np.arange(N) % 2 == 0, 1.0, -1.0)
    assert _ps_dbfs(alt, HANN)[-1] == pytest.approx(10.0 * np.log10(1.0 / 0.5), abs=1e-6)


def test_pink_noise_falls_3_db_per_octave_between_100_and_8000_hz():
    """The PS-vs-PSD trap: a pink PSD must measure −3.01 ± 0.3 dB/oct with an independent (Welch) estimator."""
    x = catalogue.by_name("pink_m20dBFS_seed1_32k").render()
    f, pxx = welch(x, FS, nperseg=N, window="hann")
    band = (f >= 100.0) & (f <= 8000.0)
    slope = np.polyfit(np.log2(f[band]), 10.0 * np.log10(pxx[band]), 1)[0]
    assert slope == pytest.approx(catalogue.PINK_SLOPE_DB_PER_OCTAVE, abs=0.3)
    # white, same estimator: flat to within the same bound
    w = catalogue.by_name("white_m20dBFS_seed1_32k").render()
    f, pxx = welch(w, FS, nperseg=N, window="hann")
    slope_w = np.polyfit(np.log2(f[band]), 10.0 * np.log10(pxx[band]), 1)[0]
    assert slope_w == pytest.approx(0.0, abs=0.3)


def test_noise_rms_equals_that_of_a_sine_at_the_same_dbfs():
    """The level convention for noise is RMS, referenced to the full-scale sine (ADR 0006 D3)."""
    # literal, not signals.rms_of_sine: comparing against the function under test is circular
    # (a mutation that returned the amplitude instead of amplitude/sqrt(2) passed this test until 2026-08-21)
    expected = 10.0 ** (-20.0 / 20.0) / np.sqrt(2.0)  # 0.070711
    assert signals.rms_of_sine(-20.0) == pytest.approx(expected, rel=1e-15)
    for name in ("white_m20dBFS_seed1_32k", "pink_m20dBFS_seed1_32k"):
        x = catalogue.by_name(name).render()
        assert np.sqrt(np.mean(x * x)) == pytest.approx(expected, rel=1e-12)
        assert np.abs(x).max() < 1.0


def _zero_crossing_frequency(x: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    """Instantaneous frequency from positive-going zero crossings: (centre times, 1/period)."""
    idx = np.flatnonzero((x[:-1] < 0.0) & (x[1:] >= 0.0))
    t_cross = (idx + (-x[idx]) / (x[idx + 1] - x[idx])) / fs  # linear interpolation
    return 0.5 * (t_cross[1:] + t_cross[:-1]), 1.0 / np.diff(t_cross)


def test_sweeps_follow_their_frequency_law_and_carry_the_exact_cycle_count():
    """A sweep whose instantaneous frequency is off anywhere mis-anchors every tracked-peak row; the cycle count is the integral check."""
    cases = (
        ("sweep_lin_20_16000_32k", lambda t: 20.0 + (16000.0 - 20.0) * t / 3.0, (20.0 + 16000.0) / 2.0 * 3.0),
        ("sweep_exp_20_16000_32k", lambda t: 20.0 * np.exp(t * np.log(800.0) / 3.0), 20.0 * 3.0 / np.log(800.0) * (800.0 - 1.0)),
    )
    for name, law, cycles in cases:
        x = catalogue.by_name(name).render()
        t_mid, f_zc = _zero_crossing_frequency(x, FS)
        below_4k = law(t_mid) < 4000.0  # ≥ 8 samples per period: linear-interpolated crossings are good to < 1 %
        rel = np.abs(f_zc[below_4k] - law(t_mid[below_4k])) / law(t_mid[below_4k])
        assert np.max(rel) < 0.01, (name, np.max(rel))
        n_crossings = np.count_nonzero((x[:-1] < 0.0) & (x[1:] >= 0.0))
        assert abs(n_crossings - cycles) <= 1.0, (name, n_crossings, cycles)


def test_vibrato_instantaneous_frequency_spans_plus_minus_extent_cents():
    """100 cents is ±1 semitone peak deviation, not peak-to-peak: f0 must reach 220·2^(±1/12)."""
    x = signals.vibrato_tone(220.0, 6.0, 100.0, FS, 3.0, -20.0)
    f_inst = np.diff(np.unwrap(np.angle(hilbert(x)))) * FS / (2 * np.pi)
    core = f_inst[FS // 2 : -FS // 2]
    assert core.min() == pytest.approx(220.0 * 2 ** (-100 / 1200), abs=0.5)
    assert core.max() == pytest.approx(220.0 * 2 ** (100 / 1200), abs=0.5)


# --- vowel: what is exact and what is not --------------------------------------


def test_klatt_resonator_poles_sit_exactly_at_the_formant_frequency_and_bandwidth():
    """Burg/LPC estimates poles; the pole angle and radius must encode F and BW exactly, not 'near'."""
    for f_hz, bw_hz in ((700.0, 130.0), (1220.0, 70.0), (2600.0, 160.0)):
        _, a = signals.klatt_resonator(f_hz, bw_hz, FS)
        pole = np.roots(a)[0]
        assert abs(np.angle(pole)) * FS / (2 * np.pi) == pytest.approx(f_hz, abs=1e-9)
        assert -FS * np.log(abs(pole)) / np.pi == pytest.approx(bw_hz, abs=1e-9)
        # unity gain at DC by construction of A = 1 − B − C
        b, _ = signals.klatt_resonator(f_hz, bw_hz, FS)
        assert b[0] / a.sum() == pytest.approx(1.0, abs=1e-12)


def test_each_resonator_response_peaks_within_one_bin_of_its_closed_form_peak_at_n8192():
    """A peak picker on |H| lands below F (conjugate-pole pull); the manifest must record that peak, exactly, not F."""
    n = 8192
    imp = np.r_[1.0, np.zeros(n - 1)]
    for f_hz, bw_hz in ((700.0, 130.0), (1220.0, 70.0), (2600.0, 160.0)):
        b, a = signals.klatt_resonator(f_hz, bw_hz, FS)
        mag = np.abs(np.fft.rfft(lfilter(b, a, imp)))
        f_peak_bin = np.argmax(mag) * FS / n
        f_peak_closed = signals.klatt_resonator_peak_hz(f_hz, bw_hz, FS)
        assert abs(f_peak_bin - f_peak_closed) <= FS / n
        assert f_peak_closed < f_hz  # the pull is toward DC, always
    truth = catalogue.ground_truth(catalogue.build(catalogue.by_name("vowel_a_f0_220_32k")))["derived"]
    assert truth["formant_poles_hz"] == [700.0, 1220.0, 2600.0]
    assert truth["resonator_response_peaks_hz"][0] == pytest.approx(696.99, abs=0.01)


def test_vowel_harmonics_sit_at_exact_multiples_of_f0():
    """f0 is driven by a phase accumulator, not an integer period: every harmonic below 2 kHz must land within one bin (N = 8192) of k·220."""
    x = catalogue.by_name("vowel_a_f0_220_32k").render()
    n = 8192
    w = general_cosine(n, HANN, sym=False)
    mag = np.abs(np.fft.rfft(x[:n] * w))
    freqs = np.fft.rfftfreq(n, 1.0 / FS)
    for k in range(1, 10):
        f_k = 220.0 * k
        window = (freqs > f_k - 100.0) & (freqs < f_k + 100.0)
        f_found = freqs[np.argmax(np.where(window, mag, 0.0))]
        assert abs(f_found - f_k) <= FS / n, (k, f_found)


def test_rosenberg_pulse_is_continuous_and_bounded_on_the_open_phase():
    """A discontinuity at Tp would add a second excitation per cycle; the pulse must rise to exactly 1 once and close to 0."""
    phi = np.linspace(0.0, 1.0, 200001, endpoint=False)
    u = signals.rosenberg_pulse(phi, open_quotient=0.6, rise_fraction=2.0 / 3.0)
    assert u.max() == pytest.approx(1.0, abs=1e-9)
    assert u.min() == 0.0
    assert np.all(u[phi >= 0.6] == 0.0)
    assert np.abs(np.diff(u)).max() < 1e-3  # no jump anywhere at this resolution (the closure corner is a slope break)


# --- quantisation ----------------------------------------------------------------


def test_quantisation_rounds_half_to_even_and_saturates_at_the_int16_rails():
    """rint is half-to-even; the scale is 32768; +1.0 must clip to 32767 and −1.0 must be exactly −32768."""
    lsb = 1.0 / quantise.FULL_SCALE
    x = np.array([0.5 * lsb, 1.5 * lsb, 2.5 * lsb, -0.5 * lsb, 1.0, -1.0, -1.5, 2.0])
    s = quantise.to_int16(x)
    assert s.dtype == np.int16
    assert s.tolist() == [0, 2, 2, 0, 32767, -32768, -32768, 32767]
    with pytest.raises(ValueError):
        quantise.to_int16(np.array([0.0, np.nan]))


def test_0_dbfs_sine_reaches_32767_and_minus_1_dbfs_never_does():
    """The full-scale vectors carry rail samples BY DESIGN (clipping-flag vectors); −1 dBFS must not."""
    full = catalogue.build(catalogue.by_name("sine_440_0dBFS_32k"))
    assert full.s.max() == 32767 and full.s.min() == -32768
    assert quantise.clipped_sample_count(full.s) > 0
    assert catalogue.ground_truth(full)["clip_flag"] is True
    under = catalogue.build(catalogue.by_name("sine_440_m1dBFS_32k"))
    assert under.s.max() == 29205 and under.s.min() == -29205
    assert quantise.clipped_sample_count(under.s) == 0
    assert catalogue.ground_truth(under)["clip_flag"] is False
    square = catalogue.build(catalogue.by_name("square_1000_0dBFS_32k"))
    assert quantise.clipped_sample_count(square.s) == square.s.size


# --- determinism and the manifest -------------------------------------------------


def test_seeded_noise_is_byte_identical_across_runs_and_differs_across_seeds():
    """Reproducibility is the whole point of the manifest sha256; a seed that does not pin the draw voids it."""
    a = catalogue.build(catalogue.by_name("white_m20dBFS_seed1_32k"))
    b = catalogue.build(catalogue.by_name("white_m20dBFS_seed1_32k"))
    assert a.sha256 == b.sha256 and a.data == b.data
    other = quantise.to_int16(signals.white_noise(FS, 3.0, -20.0, seed=2))
    assert hashlib.sha256(other.tobytes()).hexdigest() != hashlib.sha256(a.s.tobytes()).hexdigest()
    p1 = catalogue.build(catalogue.by_name("pink_m20dBFS_seed1_32k"))
    p2 = catalogue.build(catalogue.by_name("pink_m20dBFS_seed1_32k"))
    assert p1.sha256 == p2.sha256


def test_no_sample_sits_within_1e_9_lsb_of_a_rounding_boundary():
    """The libm risk (package docstring): a sample within 1e-9 LSB of a half-integer could quantise differently on another CPU."""
    for e in catalogue.CATALOGUE:
        scaled = e.render() * quantise.FULL_SCALE
        inside = scaled[np.abs(scaled) < quantise.FULL_SCALE + 0.5]  # past the rails the clip decides, not rint
        distance = np.abs(np.mod(inside, 1.0) - 0.5)
        assert distance.min() > 1e-9, (e.name, distance.min())


def test_catalogue_names_are_unique_three_seconds_and_include_the_schema_worked_example_input():
    """host/golden's worked example names sine_440_0dBFS_32k; renaming it silently breaks B-U6."""
    assert len(set(catalogue.NAMES)) == len(catalogue.NAMES) == 21
    assert "sine_440_0dBFS_32k" in catalogue.NAMES
    assert all(e.dur_s == 3.0 for e in catalogue.CATALOGUE)
    assert {e.fs for e in catalogue.CATALOGUE if e.host_only} == {48000}
    assert {e.fs for e in catalogue.CATALOGUE if not e.host_only} == {32000}


def test_wav_bytes_round_trip_through_the_stdlib_reader(tmp_path: Path):
    """What the sha256 covers is the WAV file, header included; the header must say 16-bit mono at fs."""
    built = catalogue.build(catalogue.by_name("sine_440_m20dBFS_48k"))
    assert len(built.data) == 44 + 2 * built.s.size
    path = tmp_path / built.filename
    assert wavio.write_wav(path, built.s, 48000) == built.data
    s, fs = wavio.read_wav(path)
    assert fs == 48000 and np.array_equal(s, built.s)
    with pytest.raises(TypeError):
        wavio.wav_bytes(built.x, 48000)  # float64 must never reach the writer unquantised


def test_manifest_sha256_matches_the_bytes_on_disk_and_check_detects_drift(tmp_path: Path):
    """generate → manifest sha256 == sha256(file on disk) for every file; a corrupted file and a wrong recorded hash both fail check."""
    out = tmp_path / "tier0"
    assert cli.main(["generate", "--out", str(out)]) == 0
    data = yaml.safe_load((out / manifest.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert data["clinical_claim"] == "no" and data["tier"] == 0 and data["name"] == "tier0-synthetic"
    assert data["preprocessing"] == "none" and data["restrictions"] == "none"
    assert len(data["files"]) == 21
    for f in data["files"]:
        p = out / f["path"]
        assert p.exists(), f["path"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == f["sha256"]
        assert f["bit_depth"] == 16 and f["channels"] == 1 and f["duration"] == 3.0
        s, fs = wavio.read_wav(p)
        assert fs == f["sample_rate"] and s.size == round(3.0 * fs)
    assert set(data["ground_truth"]["files"]) == set(catalogue.NAMES)
    assert (out / manifest.MANIFEST_NAME).read_text(encoding="utf-8").startswith("# SPDX-FileCopyrightText")
    # clean: check passes
    assert cli.main(["check", "--out", str(out)]) == 0
    # disk corruption: one byte flipped in the payload
    victim = out / "silence_32k.wav"
    raw = bytearray(victim.read_bytes())
    raw[100] ^= 0x01
    victim.write_bytes(bytes(raw))
    assert cli.main(["check", "--out", str(out)]) == 1
    victim.unlink()  # absent is not a failure: the WAVs are gitignored
    assert cli.main(["check", "--out", str(out)]) == 0
    # generator drift, simulated as a wrong recorded hash
    data["files"][0]["sha256"] = "0" * 64
    (out / manifest.MANIFEST_NAME).write_text(manifest.dump(data), encoding="utf-8")
    findings = manifest.check(out)
    assert any(f.kind == "drift" for f in findings)
    assert cli.main(["check", "--out", str(out)]) == 1


def test_generate_only_writes_a_subset_but_keeps_the_manifest_complete(tmp_path: Path):
    """A partial regeneration must not leave a manifest that describes only the files it wrote."""
    out = tmp_path / "tier0"
    assert cli.main(["generate", "--out", str(out), "--only", "silence_32k"]) == 0
    assert sorted(p.name for p in out.glob("*.wav")) == ["silence_32k.wav"]
    data = yaml.safe_load((out / manifest.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert len(data["files"]) == 21
    with pytest.raises(SystemExit):
        cli.main(["generate", "--out", str(out), "--only", "no_such_entry"])


def test_manifest_with_the_wrong_clinical_claim_is_refused(tmp_path: Path):
    """ADR 0005 rule 4: clinical_claim is the quoted string "no" or the manifest is not ours."""
    out = tmp_path / "tier0"
    assert cli.main(["generate", "--out", str(out)]) == 0
    data = yaml.safe_load((out / manifest.MANIFEST_NAME).read_text(encoding="utf-8"))
    data["clinical_claim"] = "yes"
    (out / manifest.MANIFEST_NAME).write_text(manifest.dump(data), encoding="utf-8")
    assert cli.main(["check", "--out", str(out)]) == 2
