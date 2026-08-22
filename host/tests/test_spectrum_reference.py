# SPDX-FileCopyrightText: 2026 Alexander Gomez
# SPDX-License-Identifier: GPL-3.0-or-later
"""The reference-spectrum oracle against ADR 0006, by hazard (roadmap H0, unit B-U3).

Each test is named for the silent mismatch it guards — the ones enumerated in
docs/validation/golden-files.md and measured in ADR 0006: symmetric-for-periodic
windows, the name-based SciPy oracle (0.0163), the NENBW closed form, the 0 dBFS
sine reference, the per-bin +2.10 vs broadband +3.01 square readings, the
doubled DC/Nyquist bins, PS vs PSD under a change of N, ÷32767 vs ÷32768, the
manifest's nine keys, the pinned window digests and `rect`'s non-preset status.

Signals are synthesised here, in int16, with no generator import: the Apache
`synth_signals` package is on the other side of the licence boundary and must
stay unimportable from this environment (test_env.py checks that it is).

Run: `uv run --project host pytest -q host/tests/test_spectrum_reference.py`
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pytest
import yaml
from scipy.signal.windows import general_cosine, get_window

from spectral_host import spectrum as sp

FS = 32000
N = 4096

#: Pinned digests of ADR 0006 D1's recipe. Recomputed 2026-08-21 on x86-64,
#: NumPy 2.5.2 / SciPy 1.18.0, before they were written here; both matched the
#: values the unit brief carried. (rect, 16) is also a closed form: sixteen
#: float32 ones, little-endian, i.e. sha256(b"\x00\x00\x80\x3f" * 16).
PINNED_DIGESTS = {
    ("rect", 16): "9628e545ed3ac074e5a6cbf542a642b62482fbfca9b4cb3ea4743a1874256e37",
    ("hann", 4): "0903e88d2ff9e0e5509ba475628fc865fa0cbab57b49c02bff937c9dc5ae7607",
}

#: ADR 0006 D1: the four families whose nearest SciPy name reproduces them exactly.
SCIPY_NAME_MATCHES = {
    "hann": "hann",
    "blackman": "blackman",
    "blackman_harris": "blackmanharris",
    "flat_top": "flattop",
}


# --- signal helpers (int16, in-file) ------------------------------------------


def full_scale_sine_int16(bin_index: int, n: int = N, amplitude: int = 32767) -> np.ndarray:
    """A sine on bin centre `bin_index` of an n-point transform at FS, peak `amplitude` LSB, phase 0."""
    t = np.arange(n) / FS
    f = bin_index * FS / n
    return np.rint(amplitude * np.sin(2 * np.pi * f * t)).astype(np.int16)


def full_scale_square_int16(period: int, n: int = N, amplitude: int = 32767) -> np.ndarray:
    """A ±amplitude square with an even integer period in samples (50 % duty), so its fundamental is on-bin."""
    assert period % 2 == 0 and n % period == 0
    return np.where((np.arange(n) % period) < period // 2, amplitude, -amplitude).astype(np.int16)


def config(**overrides) -> sp.SpectrumConfig:
    """ADR_0006_DEFAULT with fields replaced — always through the validating constructor."""
    return sp.SpectrumConfig(**{**sp.ADR_0006_DEFAULT.asdict(), **overrides})


# --- fixtures -------------------------------------------------------------------


@pytest.fixture(scope="module")
def section_4_3_table(repo_root: Path) -> dict[str, dict]:
    """The §4.3 coefficient table of preset-schema.md, parsed: name -> {coefficients, enbw_bins}.

    Parsed from the prose, not from the preset JSON files, because §4.3 is the
    single source ADR 0006 D1 names; the presets are checked against it by V8.
    """
    text = (repo_root / "protocols" / "specs" / "preset-schema.md").read_text(encoding="utf-8")
    start = text.index("### 4.3")
    end = text.index("### 4.4", start)
    rows: dict[str, dict] = {}
    for line in text[start:end].splitlines():
        m = re.match(r"^\| `([a-z_]+)` \| ([0-9., ]+) \| [^|]+ \| [^|]+ \| ([0-9.]+) \|$", line)
        if m:
            rows[m.group(1)] = {
                "coefficients": [float(c) for c in m.group(2).split(",")],
                "enbw_bins": float(m.group(3)),
            }
    assert len(rows) == 6, f"expected the six §4.3 rows, parsed {sorted(rows)}"
    return rows


@pytest.fixture(scope="module")
def manifest_schema(repo_root: Path) -> dict:
    return yaml.safe_load((repo_root / "host" / "golden" / "manifest.schema.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def presets_schema(repo_root: Path) -> dict:
    return json.loads((repo_root / "protocols" / "specs" / "presets.schema.json").read_text(encoding="utf-8"))


# --- windows: periodic, from coefficients, not from names ------------------------


def test_window_families_equal_the_section_4_3_table(section_4_3_table):
    """WINDOW_FAMILIES claims to be §4.3 digit for digit; a retyped coefficient would pass every other test."""
    for family, row in section_4_3_table.items():
        assert sp.WINDOW_FAMILIES[family] == row["coefficients"], family
    assert set(sp.WINDOW_FAMILIES) == set(section_4_3_table) | {"rect"}
    assert sp.WINDOW_FAMILIES["rect"] == [1.0]
    assert sp.PRESET_WINDOW_FAMILIES == tuple(section_4_3_table)


def test_window_is_periodic_not_symmetric():
    """The symmetric form is the ADR 0006 rejected alternative; the name-based oracle is the 0.0163 trap."""
    for family, scipy_name in SCIPY_NAME_MATCHES.items():
        periodic = get_window(scipy_name, N, fftbins=True)
        symmetric = get_window(scipy_name, N, fftbins=False)
        assert np.array_equal(sp.window_float64(family, N), periodic), family
        assert np.array_equal(sp.window_table(family, N), periodic.astype("<f4")), family
        assert not np.array_equal(sp.window_float64(family, N), symmetric), family
    # Trap (a): SciPy's `nuttall` is this table's `blackman_nuttall` ...
    assert np.array_equal(sp.window_float64("blackman_nuttall", N), get_window("nuttall", N, fftbins=True))
    # ... and this table's `nuttall` is a different window by ~0.0163 (ADR 0006 D1, measured).
    delta = np.max(np.abs(sp.window_float64("nuttall", N) - get_window("nuttall", N, fftbins=True)))
    assert delta == pytest.approx(0.0163, abs=5e-4)
    # The periodic window does not end where it began: w[0] = Σ(−1)^k a_k, and w[N−1] ≠ w[0] for every cosine-sum.
    for family in sp.PRESET_WINDOW_FAMILIES:
        w = sp.window_float64(family, N)
        assert w[0] == pytest.approx(sum((-1) ** k * a for k, a in enumerate(sp.WINDOW_FAMILIES[family])), abs=1e-15)
        assert w[-1] != w[0]


def test_window_table_is_float32_little_endian():
    """The digest is over `<f4` bytes; a float64 or big-endian table hashes to something else."""
    w = sp.window_table("hann", N)
    assert w.dtype == np.dtype("<f4")
    assert w.nbytes == 4 * N
    assert w.tobytes() == w.astype("<f4").tobytes()


def test_periodic_nenbw_equals_closed_form_and_preset_table(section_4_3_table):
    """ADR 0006 D2: N·S2/S1² = (a₀² + Σ a_k²/2)/a₀² = the shipped enbw_bins, to 1e-6 — for the PERIODIC form only."""
    for family, row in section_4_3_table.items():
        a = sp.WINDOW_FAMILIES[family]
        for n in (512, 2048, N, 8192):
            _s1, _s2, nenbw = sp.window_sums(sp.window_float64(family, n))
            assert nenbw == pytest.approx(sp.nenbw_closed_form(a), abs=1e-6), (family, n)
            assert nenbw == pytest.approx(row["enbw_bins"], abs=1e-6), (family, n)
    # The symmetric hann at N = 4096 gives 1.500366, not 1.5 (ADR 0006 D2) — the number the rejection rests on.
    _s1, _s2, nenbw_sym = sp.window_sums(general_cosine(N, [0.5, 0.5], sym=True))
    assert nenbw_sym == pytest.approx(1.500366, abs=1e-6)
    assert abs(nenbw_sym - 1.5) > 1e-4
    # rect: S1 = S2 = N, NENBW = 1 exactly.
    assert sp.window_sums(sp.window_float64("rect", N)) == (float(N), float(N), 1.0)


def test_enbw_hz_is_nenbw_times_bin_width():
    """preset-schema.md §4.4: enbw_hz = enbw_bins × sample_rate_hz / fft_size."""
    assert sp.enbw_hz(1.5, FS, N) == pytest.approx(1.5 * FS / N)
    assert sp.enbw_hz(1.5, FS, N) == pytest.approx(11.71875)


# --- levels: ADR 0006 D3 ------------------------------------------------------------


def test_full_scale_on_bin_sine_reads_0_dbfs_under_ps_s1():
    """0 dBFS = a full-scale sine's PS = 0.5, hann window, peak bin (ADR 0006 D3 row 1)."""
    k = 56  # 437.5 Hz, a bin centre
    out = sp.reference_spectrum(full_scale_sine_int16(k), FS, sp.ADR_0006_DEFAULT)
    assert out.shape == (N // 2 + 1, 2) and out.dtype == np.float64
    assert out[k, 0] == pytest.approx(k * FS / N)
    # The int16 peak is 32767/32768 of full scale under the ÷32768 seam: −0.000265 dB is the exact expectation,
    # and the quantisation of a rounded sine accounts for the last 1e-5 dB.
    assert out[k, 1] == pytest.approx(20 * np.log10(32767 / 32768), abs=2e-5)
    assert out[k, 1] == pytest.approx(0.0, abs=1e-3)
    assert np.argmax(out[:, 1]) == k
    # The hann sidelobes: the adjacent bins are the −6.02 dB skirt of a periodic hann on-bin, nothing else leaks.
    assert out[k - 1, 1] == pytest.approx(out[k, 1] - 6.0206, abs=1e-3)
    assert out[k + 1, 1] == pytest.approx(out[k, 1] - 6.0206, abs=1e-3)
    assert np.max(out[: k - 1, 1]) < -90 and np.max(out[k + 2 :, 1]) < -90


def test_full_scale_square_fundamental_bin_reads_plus_2p10_and_total_plus_3p01():
    """ADR 0006 D3 rows 2 and 3 — BOTH numbers; a test written from +3.01 against a per-bin PS fails by 0.92 dB."""
    period = 64  # 500 Hz = bin 64 of a 4096-point transform at 32 kHz
    square = full_scale_square_int16(period)
    cfg = sp.ADR_0006_DEFAULT
    out = sp.reference_spectrum(square, FS, cfg)
    fundamental = out[N // period, 1]
    # Per-bin: the fundamental of a square is 4/π × the sine's amplitude → +2.10 dB (the sampled square's
    # fundamental is 4/(P·sin(π/P)) ≈ 1.00038 × 4/π, +0.003 dB, which is why the tolerance is not tighter).
    assert fundamental == pytest.approx(20 * np.log10(4 / np.pi) + 20 * np.log10(32767 / 32768), abs=0.005)
    assert round(fundamental, 2) == 2.10
    # Broadband: Σ PS / NENBW is the mean power 1.0 of a ±1 square against the sine's 0.5 → +3.01 dB.
    w = sp.window_float64(cfg.window, cfg.window_length_samples)
    s1, s2, nenbw = sp.window_sums(w)
    ps = sp.scale(sp.rfft_unnormalised(sp.int16_to_float(square) * w, cfg.fft_size), s1, s2, FS, "S1", "power_spectrum")
    total = 10 * np.log10(ps.sum() / nenbw / sp.REFERENCE_POWER["sine"])
    assert total == pytest.approx(10 * np.log10(2.0) + 20 * np.log10(32767 / 32768), abs=0.001)
    assert round(total, 2) == 3.01
    # And the pair is the point: the two readings differ by 0.91 dB, so neither is a substitute for the other.
    assert total - fundamental == pytest.approx(10 * np.log10(2.0) - 20 * np.log10(4 / np.pi), abs=0.005)


def test_dc_and_nyquist_are_not_doubled():
    """ADR 0006 D2's divergence from Heinzel's waiver: DC and Nyquist have no mirror bin; doubling them is +3.01 dB."""
    s1, s2 = 4.0, 2.0
    X = np.ones(N // 2 + 1, dtype=complex)
    ps = sp.scale(X, s1, s2, FS, "S1", "power_spectrum")
    assert ps[0] == pytest.approx(1 / s1**2)
    assert ps[-1] == pytest.approx(1 / s1**2)
    assert np.all(ps[1:-1] == pytest.approx(2 / s1**2))
    # End to end with a rect window, whose Nyquist response is not zero (a hann's is, by orthogonality):
    # a constant 0.5 FS and an alternating ±0.5 FS each carry power 0.25 FS² in one bin → −3.01 dBFS, not 0.
    cfg = config(window="rect")
    dc = np.full(N, 16384, dtype=np.int16)
    nyquist = np.where(np.arange(N) % 2 == 0, 16384, -16384).astype(np.int16)
    assert sp.reference_spectrum(dc, FS, cfg)[0, 1] == pytest.approx(10 * np.log10(0.25 / 0.5), abs=1e-9)
    assert sp.reference_spectrum(nyquist, FS, cfg)[-1, 1] == pytest.approx(10 * np.log10(0.25 / 0.5), abs=1e-9)
    # Under the hann default the DC bin reads the same −3.01 dBFS: S1 normalisation makes a constant window-independent.
    assert sp.reference_spectrum(dc, FS, sp.ADR_0006_DEFAULT)[0, 1] == pytest.approx(-3.0103, abs=1e-3)


def test_white_noise_psd_independent_of_n_and_ps_scales_with_enbw():
    """Heinzel 2002: a noise floor in PSD is the same at every N; in PS it moves with ENBW (the 'noise floor is 2 dB off' trap)."""
    rng = np.random.default_rng(20260821)
    sigma_lsb = 3276.8  # 0.1 FS: quantisation noise (1/12 LSB²) is 1e-8 of the signal power
    x = np.clip(np.rint(rng.normal(0.0, sigma_lsb, 3 * FS)), -32768, 32767).astype(np.int16)
    variance = float(np.mean(sp.int16_to_float(x) ** 2))  # the realised σ², so the generator's own spread is not in the tolerance
    expected_psd = 2 * variance / FS  # one-sided, FS²/Hz
    means = {}
    for n in (1024, 4096):
        cfg = config(window_length_samples=n, fft_size=n, scaling="power_spectral_density", normalization="S2")
        _t, _f, psd = sp.stft_power(x, FS, cfg, hop=n)
        cfg_ps = config(window_length_samples=n, fft_size=n)
        _t, _f, ps = sp.stft_power(x, FS, cfg_ps, hop=n)
        s1, s2, nenbw = sp.window_sums(sp.window_float64("hann", n))
        means[n] = (float(np.mean(psd[:, 1:-1])), float(np.mean(ps[:, 1:-1])), sp.enbw_hz(nenbw, FS, n))
        # PS = PSD·ENBW holds bin for bin, not only on average (ADR 0006 D2's identity).
        np.testing.assert_allclose(ps, psd * sp.enbw_hz(nenbw, FS, n), rtol=1e-12)
    for n, (psd_mean, ps_mean, enbw) in means.items():
        assert psd_mean == pytest.approx(expected_psd, rel=0.03), n  # ≈ 47 000 exponential bin estimates → ≈ 0.5 % rel. std
        assert ps_mean == pytest.approx(expected_psd * enbw, rel=0.03), n
    # PSD is flat across N; PS drops by the ENBW ratio (4× here: same NENBW, a quarter of the bin width → −6.02 dB).
    assert means[4096][0] / means[1024][0] == pytest.approx(1.0, rel=0.03)
    assert means[4096][1] / means[1024][1] == pytest.approx(means[4096][2] / means[1024][2], rel=0.03)
    assert means[4096][2] / means[1024][2] == pytest.approx(0.25)


def test_int16_scale_32767_differs_by_0p00026_db():
    """The schema admits both divisors; the difference is 20·log10(32768/32767) = 0.000265 dB, recorded not argued."""
    k = 56
    sine = full_scale_sine_int16(k)
    at_32768 = sp.reference_spectrum(sine, FS, sp.ADR_0006_DEFAULT)[k, 1]
    at_32767 = sp.reference_spectrum(sine, FS, config(int16_scale=32767))[k, 1]
    assert at_32767 - at_32768 == pytest.approx(20 * np.log10(32768 / 32767), abs=1e-9)
    assert at_32767 - at_32768 == pytest.approx(0.00026, abs=1e-5)
    assert at_32767 > at_32768


def test_int16_to_float_refuses_non_int16():
    """A float array scaled here would be divided by 32768 twice and read −90.3 dB low, like a dead microphone."""
    with pytest.raises(TypeError, match="int16"):
        sp.int16_to_float(np.zeros(8, dtype=np.float32))
    with pytest.raises(TypeError, match="int16"):
        sp.int16_to_float(np.zeros(8, dtype=np.int32))
    assert sp.int16_to_float(np.array([-32768, 32767], dtype=np.int16)).tolist() == [-1.0, 32767 / 32768]


def test_dbfs_reference_square_puts_the_sine_at_minus_3p01():
    """The schema's `square` reference: the same array, the axis shifted by the classic 3.01 dB constant."""
    ps = np.array([0.5, 1.0, 0.25])
    sine_axis = sp.to_dbfs(ps, "sine", "power_spectrum")
    square_axis = sp.to_dbfs(ps, "square", "power_spectrum")
    np.testing.assert_allclose(sine_axis - square_axis, 10 * np.log10(2.0))
    assert sine_axis[0] == 0.0 and square_axis[1] == 0.0


def test_to_dbfs_floor_and_density_axis_are_explicit():
    """ADR 0006 D3: zeros read the −200 dB floor; PSD needs ENBW to reach dBFS and has its own dBFS/Hz axis."""
    assert sp.to_dbfs(np.array([0.0, 0.5]), "sine", "power_spectrum").tolist() == [-200.0, 0.0]
    assert sp.to_dbfs(np.array([0.0]), "sine", "power_spectrum", floor_db=-120.0).tolist() == [-120.0]
    enbw = sp.enbw_hz(1.5, FS, N)
    psd_of_full_scale_sine_peak = 0.5 / enbw
    assert sp.to_dbfs(np.array([psd_of_full_scale_sine_peak]), "sine", "power_spectral_density", enbw_hz=enbw)[0] == pytest.approx(0.0)
    assert sp.to_dbfs_per_hz(np.array([psd_of_full_scale_sine_peak]), "sine", "power_spectral_density")[0] == pytest.approx(
        -10 * np.log10(enbw)
    )
    # Linear forms: 20·log10, the same axis.
    assert sp.to_dbfs(np.array([np.sqrt(0.5)]), "sine", "linear_spectrum")[0] == pytest.approx(0.0)
    # Mixing the axes is refused in both directions.
    with pytest.raises(ValueError, match="enbw_hz"):
        sp.to_dbfs(np.array([1.0]), "sine", "power_spectral_density")
    with pytest.raises(ValueError, match="not a density"):
        sp.to_dbfs(np.array([1.0]), "sine", "power_spectrum", enbw_hz=enbw)
    with pytest.raises(ValueError, match="density"):
        sp.to_dbfs_per_hz(np.array([1.0]), "sine", "power_spectrum")


def test_s1_and_s2_normalisations_agree_on_both_ps_and_psd():
    """ADR 0006 D2: PS = PSD·ENBW exactly, so the two ratified routes must give the same arrays (not merely close)."""
    rng = np.random.default_rng(7)
    X = rng.normal(size=N // 2 + 1) + 1j * rng.normal(size=N // 2 + 1)
    s1, s2, _ = sp.window_sums(sp.window_float64("blackman_harris", N))
    for scaling in sp.SCALINGS:
        via_s1 = sp.scale(X, s1, s2, FS, "S1", scaling)
        via_s2 = sp.scale(X, s1, s2, FS, "S2", scaling)
        np.testing.assert_allclose(via_s1, via_s2, rtol=1e-12)
    # coherent_gain is S1 for a periodic cosine sum (S1 = N·a₀); none / 1/N / 1/√N keep the window gain.
    np.testing.assert_array_equal(sp.scale(X, s1, s2, FS, "coherent_gain", "power_spectrum"), sp.scale(X, s1, s2, FS, "S1", "power_spectrum"))
    raw = sp.scale(X, s1, s2, FS, "none", "power_spectrum")
    np.testing.assert_allclose(sp.scale(X, s1, s2, FS, "1/N", "power_spectrum"), raw / N**2)
    np.testing.assert_allclose(sp.scale(X, s1, s2, FS, "1/sqrt(N)", "power_spectrum"), raw / N)


# --- the configuration block against the schema -----------------------------------------


def test_config_keys_equal_schema_required_list(manifest_schema):
    """The dataclass IS the schema's `analyses.spectrum` block: same nine keys, same order, same enums."""
    block = manifest_schema["properties"]["analyses"]["properties"]["spectrum"]
    required = block["required"]
    assert len(required) == 9
    assert required == list(block["properties"])
    assert [f.name for f in sp.SpectrumConfig.__dataclass_fields__.values()] == required
    assert list(sp.ADR_0006_DEFAULT.asdict()) == required
    assert block["additionalProperties"] is False
    props = block["properties"]
    assert tuple(props["normalization"]["enum"]) == sp.NORMALIZATIONS
    assert tuple(props["scaling"]["enum"]) == sp.SCALINGS
    assert tuple(props["dbfs_reference"]["enum"]) == sp.DBFS_REFERENCES
    assert tuple(props["int16_scale"]["enum"]) == sp.INT16_SCALES
    assert tuple(props["dtype"]["enum"]) == sp.DTYPES
    assert props["window"]["$ref"] == "#/$defs/window_family"
    assert props["window_length_samples"]["minimum"] == 2 and props["fft_size"]["minimum"] == 2


def test_config_round_trips_the_schema_worked_example(manifest_schema):
    """`SpectrumConfig(**block).asdict() == block` for the worked example's values — the generator's write path."""
    block = sp.ADR_0006_DEFAULT.asdict()
    assert sp.SpectrumConfig(**block) == sp.ADR_0006_DEFAULT
    assert sp.SpectrumConfig(**block).asdict() == block
    assert block == {
        "window": "hann",
        "window_length_samples": 4096,
        "fftbins": True,
        "fft_size": 4096,
        "normalization": "S1",
        "scaling": "power_spectrum",
        "dbfs_reference": "sine",
        "int16_scale": 32768,
        "dtype": "float64",
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {"window": "nuttall4"},
        {"window": "hanning"},
        {"window_length_samples": 1},
        {"fft_size": 2048},  # < window length: truncation
        {"fft_size": 4095},  # odd: no Nyquist bin, the DC/Nyquist rule is undefined
        {"normalization": "forward"},
        {"scaling": "psd"},
        {"dbfs_reference": "rms"},
        {"int16_scale": 32000},
        {"dtype": "float16"},
        {"fftbins": 1},
    ],
)
def test_config_refuses_values_the_schema_refuses(overrides):
    with pytest.raises(ValueError):
        config(**overrides)


def test_config_refuses_a_tenth_key():
    """additionalProperties: false on the schema side; a TypeError here, so a misspelt key cannot be silently dropped."""
    with pytest.raises(TypeError):
        sp.SpectrumConfig(**sp.ADR_0006_DEFAULT.asdict(), fft_bins=True)


def test_symmetric_window_request_is_refused_not_approximated():
    """fftbins=false names the form ADR 0006 rejects; the oracle must not build a periodic window and call it symmetric."""
    with pytest.raises(ValueError, match="symmetric"):
        sp.reference_spectrum(full_scale_sine_int16(56), FS, config(fftbins=False))


# --- the digests ---------------------------------------------------------------------


def test_window_table_sha256_pinned():
    """ADR 0006 D1's digest recipe, pinned at two tiny sizes so a recipe change (dtype, endianness, form) is one diff."""
    assert sp.window_table_sha256("rect", 16) == PINNED_DIGESTS[("rect", 16)]
    assert sp.window_table_sha256("hann", 4) == PINNED_DIGESTS[("hann", 4)]
    # Closed forms: rect is N float32 ones; the periodic hann at N = 4 is exactly [0, 0.5, 1, 0.5].
    assert PINNED_DIGESTS[("rect", 16)] == hashlib.sha256(b"\x00\x00\x80\x3f" * 16).hexdigest()
    assert sp.window_table("hann", 4).tolist() == [0.0, 0.5, 1.0, 0.5]
    assert PINNED_DIGESTS[("hann", 4)] == hashlib.sha256(np.array([0.0, 0.5, 1.0, 0.5], dtype="<f4").tobytes()).hexdigest()
    # The recipe agrees with test_manifest_schema.py's independent transcription at the sizes the worked example pins.
    assert sp.window_table_sha256("hann", 4096) == "3ce6c7c870b60fc2425689b96f2ccf1cecff9b071766a48ae3d25a0ca8f3d304"
    assert sp.window_table_sha256("rect", 4096) == "3035aac5fb87474c303702f9030301b4e6bb7aee93be3710b8ab8dcea201db70"


def test_window_table_sha256_distinguishes_form_and_width():
    """Symmetric samples or float64 bytes must never collide with the pinned periodic-float32 digest."""
    sym = general_cosine(4, [0.5, 0.5], sym=True).astype("<f4")
    assert hashlib.sha256(sym.tobytes()).hexdigest() != PINNED_DIGESTS[("hann", 4)]
    assert hashlib.sha256(sp.window_float64("hann", 4).tobytes()).hexdigest() != PINNED_DIGESTS[("hann", 4)]
    assert hashlib.sha256(sp.window_table("hann", 4).astype(">f4").tobytes()).hexdigest() != PINNED_DIGESTS[("hann", 4)]


# --- rect is a calibration window, never a preset ------------------------------------------


def test_rect_is_never_a_preset_family(presets_schema, manifest_schema):
    """ADR 0006 consequence (c) / ADR 0009 amendment: `rect` lives in the golden manifest's enum only."""
    preset_enum = presets_schema["$defs"]["window"]["properties"]["name"]["enum"]
    manifest_enum = manifest_schema["$defs"]["window_family"]["enum"]
    assert "rect" not in preset_enum
    assert "rect" in manifest_enum
    assert set(manifest_enum) == set(sp.WINDOW_FAMILIES)
    assert set(preset_enum) == set(sp.PRESET_WINDOW_FAMILIES)
    assert "rect" not in sp.PRESET_WINDOW_FAMILIES
    with pytest.raises(ValueError, match="unknown window family"):
        sp.window_table("rectangular", 16)


# --- the device frame grid ----------------------------------------------------------------


def test_frames_from_zero_start_at_sample_zero_and_drop_the_partial_tail():
    """The frame-grid trap: no centring pad, no zero-padded last frame; frame k starts at k·hop."""
    x = np.arange(20, dtype=np.int16)
    frames = sp.frames_from_zero(x, n=8, hop=4)
    assert frames.shape == (4, 8)  # starts 0, 4, 8, 12; a frame at 16 would need samples 16..23
    assert frames[0].tolist() == list(range(0, 8))
    assert frames[-1].tolist() == list(range(12, 20))
    assert sp.frames_from_zero(x[:7], n=8, hop=4).shape == (0, 8)
    assert sp.frame_start_times(4, 4, FS).tolist() == [0.0, 4 / FS, 8 / FS, 12 / FS]


def test_stft_first_frame_equals_reference_spectrum():
    """`reference_spectrum` is frame 0 of the grid — the two paths must not drift apart."""
    sine = full_scale_sine_int16(56, n=3 * N)
    cfg = sp.ADR_0006_DEFAULT
    times, freqs, power = sp.stft_power(sine, FS, cfg, hop=N // 2)
    assert times[0] == 0.0 and power.shape == (5, N // 2 + 1)
    np.testing.assert_array_equal(freqs, sp.reference_spectrum(sine, FS, cfg)[:, 0])
    np.testing.assert_array_equal(sp.to_dbfs(power[0], cfg.dbfs_reference, cfg.scaling), sp.reference_spectrum(sine, FS, cfg)[:, 1])


def test_reference_spectrum_refuses_a_short_input_rather_than_padding():
    with pytest.raises(ValueError, match="window_length_samples"):
        sp.reference_spectrum(full_scale_sine_int16(56)[: N - 1], FS, sp.ADR_0006_DEFAULT)


def test_rfft_is_unnormalised_and_refuses_truncation():
    """ADR 0006 D2: no 1/N, no 1/√N in the transform; zero-padding is allowed, truncation is not."""
    x = np.ones(8)
    assert sp.rfft_unnormalised(x, 8)[0] == pytest.approx(8.0)  # Σx, not 1 and not √8
    assert sp.rfft_unnormalised(x, 16).shape == (9,)
    with pytest.raises(ValueError, match="truncation"):
        sp.rfft_unnormalised(x, 4)


def test_float32_accumulation_stays_inside_the_magnitude_tolerance_row():
    """dtype=float32 is the device's width; golden-files.md allows 0.01 dB above −80 dBFS against the float64 reference."""
    sine = full_scale_sine_int16(56)
    ref = sp.reference_spectrum(sine, FS, sp.ADR_0006_DEFAULT)[:, 1]
    f32 = sp.reference_spectrum(sine, FS, config(dtype="float32"))[:, 1]
    mask = ref >= -80.0
    assert np.max(np.abs(f32[mask] - ref[mask])) < 0.01


# --- the CLI -----------------------------------------------------------------------------


def test_cli_prints_the_pinned_digest(capsys):
    assert sp.main(["--family", "hann", "4"]) == 0
    out = capsys.readouterr().out
    assert PINNED_DIGESTS[("hann", 4)] in out
    assert "NENBW=1.500000000" in out


def test_cli_rejects_a_window_length_below_the_schema_minimum(capsys):
    assert sp.main(["--family", "rect", "1"]) == 2
    assert "window length" in capsys.readouterr().err
