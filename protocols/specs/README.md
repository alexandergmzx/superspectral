# Protocol specifications

Human-readable specifications of the formats that cross the watch ↔ host boundary. Implementations live in [`../../firmware/`](../../firmware/) (writer, C99) and [`../../host/`](../../host/) (reader, Python); the preset schema is machine-readable and lives here ([`presets.schema.json`](presets.schema.json)); take test vectors and the `take_record.h` reference header will live next to this directory under `../schemas/` (planned). The record-kind table in [`../README.md`](../README.md) is the single source of truth for kinds and sizes.

Written:

- [`preset-schema.md`](preset-schema.md) — the preset JSON ([ADR 0010](../../docs/adr/0010-preset-schema.md)): every field, the canonical form and the sha256 a take manifest points at, the loader rules V0–V10, and the reason `enbw_hz` is mandatory. Machine-readable form: [`presets.schema.json`](presets.schema.json) (JSON Schema draft 2020-12); the six instances live in [`../presets/`](../presets/).
- *(the take format and the take-transfer procedure are still to be written — roadmap D5/D6, before any firmware writes a take)*

Planned documents:

- `take-format.md` — the on-flash take: physical layer (FAT partition, file naming `YYYYMMDD-HHMMSS-<preset>.take`, block alignment to the DMA frame) → record framing (kind, length, CRC-16/32, `_Static_assert`ed sizes) → `TAKE_HEADER` / `PCM_BLOCK` / `FEATURE_FRAME` / `EVENT` / `TAKE_FOOTER` byte-level layouts → versioning and forward-compatibility rules (unknown kinds are skipped, never fatal) → error handling (truncated take after brownout: footer missing ⇒ recover from header + block CRCs) → `## Verification hooks`: a round-trip test (writer → reader), a truncation test, and the injection-path replay test that proves `PCM_BLOCK` is bit-exact.
- `take-transfer.md` — how takes and presets move between watch and host: the candidate mechanisms (USB mass-storage class exposing the FAT partition; serial dump over the USB-Serial-JTAG console; later BLE is out of scope, ADR 0017), their interaction with the anti-brick rules (the USB-Serial-JTAG console must remain available — ADR 0015), integrity (sha256 per take, manifest file), and the host-side import procedure into [`../../datasets/`](../../datasets/). Decision is **(prov.), ADR-gated**.
- `feature-frame-semantics.md` — what each `FEATURE_FRAME` field means and how the host recomputes it from the `PCM_BLOCK`s for frame-by-frame agreement: f0 in Hz and cents re A4 = 440 Hz, voicing flag, SPR (Omori peak-to-peak), FHE, band energies in dB re full-scale sine, uncorrected and post-EQ variants. This is the document that makes the watch's displayed numbers auditable.

Each spec ends with `## Verification hooks` tying it to a validation row in [`../../docs/validation/README.md`](../../docs/validation/README.md) and to the host-tests / QEMU tests that exercise it.

## Background reading

Storage and platform constraints: ESP-IDF partition tables, FATFS/wear levelling, `joltwallet/littlefs`, `esp_app_desc` (`app_elf_sha256`) in [`../../docs/bibliography/02-application-notes.md`](../../docs/bibliography/02-application-notes.md) and [`11-esp-idf-platform-and-toolchain.md`](../../docs/bibliography/11-esp-idf-platform-and-toolchain.md). Level normalisation for injected corpora: ITU-T P.56 in [`03-standards.md`](../../docs/bibliography/03-standards.md). Preset origins: [`../../docs/research/00-linux-analyzer-architecture-and-build-guide.md`](../../docs/research/00-linux-analyzer-architecture-and-build-guide.md).
