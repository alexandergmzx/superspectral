# Bill of Materials

`bill-of-materials.csv` is the canonical source. Use it for total-cost rollups and procurement. Unlike the swarm BOM it covers **one device under test plus the bench that validates it**: for a metrology project the instruments — and their tolerances — are part of the bill.

Columns:

| Column | Meaning |
|--------|---------|
| `component` | functional role; the first word says which class the row belongs to — `Device under test`, `… (bench)`, `… (bench, optional)`, `Spares and tools` |
| `model` | preferred part / instrument; alternatives separated by ` / ` with the cheaper first |
| `role` | what it does inside the project, with the **spec that matters** (tolerance, range, class) — the number a validation row will cite |
| `interface` | bus / connector / coupling as used in this project |
| `unit_cost_eur_min`, `unit_cost_eur_max` | observed price range (EUR); for a `/` pair, min is the budget option and max the credible one |
| `qty_per_device` | quantity per device under test for DUT rows; for bench rows, the quantity needed for **one validation bench**, shared across units. `0` = optional/excluded from TOTAL |
| `notes` | provenance, gotchas, thresholds that change the plan, links to docs, `(prov.)`/`TBD` flags |

Conventions carried from swarm: min/max **range**, not a point estimate; `—` for N/A; a blank spacer row before `TOTAL`; **the `TOTAL` row carries the justification** (what is counted, what is excluded, and — once proposal §3 names a budget target — any deviation from it).

## Status of the numbers

Every price in the CSV is **(prov.)** — recalled, not quoted — and must be verified before purchase; tolerances and ranges in `role` come from the instrument documents catalogued in [`../../docs/bibliography/01-datasheets.md`](../../docs/bibliography/01-datasheets.md) (B&K 4231 and 4128-C, PPK2 user guide, Otii Arc technical spec, UMIK-1 product brief). Two rows are **thresholds that change the plan**, not shopping choices:

- **Reference microphone class** — a UMIK-1 cannot underwrite a ±1.5 dB absolute target (its disagreement with Earthworks-class mics at HF is of that order); choosing it means restating level metrics as repeatability with a Bland–Altman / ICC analysis or a GUM budget.
- **Calibrator class** — Class 2 caps absolute SPL at ~±2 dB; the research question then loses its absolute-level row, not its f0 rows.

Update this CSV whenever a part or instrument is swapped; record the rationale in an ADR under [`../../docs/adr/`](../../docs/adr/) and adjust the affected rows in [`../../docs/validation/README.md`](../../docs/validation/README.md) in the same commit.
