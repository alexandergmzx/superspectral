# Protocols

Definitions of every byte that crosses the boundary between the two halves of Super Spectral: what the watch **writes** (takes, their headers and side-car metadata) and what both halves **load** (preset JSON). This subsystem is **self-contained**: specs live alongside the schemas under [`specs/`](specs/), not under `docs/`.

| Subdirectory | Contents |
|--------------|----------|
| [specs/](specs/) | Human-readable format specifications plus the machine-readable preset schema: [`preset-schema.md`](specs/preset-schema.md) + [`presets.schema.json`](specs/presets.schema.json) (JSON Schema draft 2020-12), and — planned — the take/record format and the take-transfer procedure |
| [presets/](presets/) | The six preset instances, one JSON file per preset, in the canonical form the LittleFS `presets` partition stores byte-for-byte ([ADR 0010](../docs/adr/0010-preset-schema.md)) |
| `schemas/` *(planned)* | Remaining machine-readable artifacts: `take_record.h` reference header, take test vectors |

The C header the firmware compiles against lives in `firmware/twatch-s3/components/spectral_core/include/spectral_core/` (planned `take_record.h`) so `spectral_core` stays host-buildable; the host reads the same layout through a Python reader under [`../host/`](../host/). This directory holds **specifications and schemas**, not source — the header is generated from or checked against the spec, never the other way around.

## Record formats are sacred

The wire-format discipline of the author's earlier `swarm` project applies here to formats **at rest**, because there is no wire: the watch and the host never share a process or a live link.

- **Binary on flash.** Takes are fixed-layout binary records on the FAT `takes` partition; no JSON, no text framing in the take stream. Presets are JSON because the host edits them and because the schema is the thing a user reasons about — and their schema is versioned.
- **A `_Static_assert` guards the on-disk size of every record struct**; do not relax it. Structs are packed explicitly, little-endian, with no implicit padding, and every record carries a `version` field, a CRC, and the `app_elf_sha256` of the writing build so a take can always be matched to the firmware (and coredump ELF) that produced it.
- **Changing a format requires an ADR and coordinated commits** across firmware + host + validation + the test vectors in `schemas/`. Formats freeze in step with the partition layout (ADR 0014): offsets and record layouts are the two things that break fielded units when changed.
- This table is the **single source of truth for record kinds**; do not restate sizes elsewhere. Sizes marked *(prov.)* are provisional until [`specs/take-format.md`](specs/) fixes the byte-level layouts.

| Kind | Name | Size | Purpose |
|------|------|------|---------|
| 0x01 | `TAKE_HEADER` | TBD *(prov.)* | Once per take: format version, preset id + sha256 of the preset JSON, sample rate (nominal and, once measured, corrected ppm), bit depth, start time (PCF8563 RTC), device id, firmware `app_elf_sha256`, mic-EQ id |
| 0x02 | `PCM_BLOCK` | TBD *(prov.)* | Raw 16-bit PCM as delivered by the I2S0 PDM RX path, block-sized to the DMA frame; uncompressed by default so the injection path can replay it bit-exact |
| 0x03 | `FEATURE_FRAME` | TBD *(prov.)* | Per analysis frame: f0 + voicing, band energies / SPR / FHE, peak list, frame counter, dropped-frame flag — what the watch displayed, so host and watch can be compared frame by frame |
| 0x04 | `EVENT` | TBD *(prov.)* | Marker events: preset change, clipping flag, PMU/battery sample (AXP2101 E-Gauge), user mark, reset reason |
| 0x05 | `TAKE_FOOTER` | TBD *(prov.)* | CRC over the take, record counts, duration, end time |
| — | `preset.json` | schema-bound | One file per preset on the LittleFS `presets` partition: FFT size, window, interval, smoothing, decimations, overlays, **explicit bandwidth/ENBW**, **mic-EQ slot**, display options (ADR 0010) |

Optional compressed takes (OPUS via `esp_audio_codec`, measured at ≈ 25 % of a core at 48 kHz) are deferred and ADR-gated; the injection-path rule ("corpus WAV into the PCM ring buffer, bit-exact") is the reason raw PCM is the default.

## Watch ↔ host transfer

| Link | Contract | Spec |
|------|----------|------|
| Takes and presets, watch → host and host → watch | files on the FAT `takes` and LittleFS `presets` partitions | `specs/take-transfer.md` (planned): USB mass-storage exposure of the FAT partition vs a serial dump over USB-Serial-JTAG — **(prov.), ADR-gated**; whichever is chosen must never disable the USB-Serial-JTAG console (anti-brick rule, ADR 0015) |

## Background reading

Partition-table and FAT/LittleFS constraints are catalogued in [`../docs/bibliography/02-application-notes.md`](../docs/bibliography/02-application-notes.md) (ESP-IDF partition tables, `app_update`/OTA, `esp_app_desc`, USB-Serial-JTAG console guide) and [`../docs/bibliography/11-esp-idf-platform-and-toolchain.md`](../docs/bibliography/11-esp-idf-platform-and-toolchain.md); the preset semantics come from the founding research document ([`../docs/research/`](../docs/research/)) and the spectral conventions from [`../dsp/design/`](../dsp/design/).
