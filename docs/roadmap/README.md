# Roadmap

The documentation roadmap is the instrument that orders everything else in this repository: what to acquire, why, where to file it, in what sequence, and what "done" means for each phase — **before firmware**.

- [`documentation-roadmap.md`](documentation-roadmap.md) — the roadmap. Two tracks (**D** documentation/acquisition, **E** environment), ten phases (D0 D1 E0 · E1 E2 D2 D3 D4 D5 D6) each with owner, inputs, outputs and a `- [ ]` definition of done; the routing table that gives every open question (47 domain + 18 hardware) a home; the thresholds that change the plan; a one-page timeline.

## How it relates to the rest of `docs/`

| Artefact | Role | Where |
|---|---|---|
| Research question (prov.) | The hypothesis every target traces back to | [`../proposal/01-super-spectral-proposal.md`](../proposal/01-super-spectral-proposal.md) §1 |
| Bibliography | The acquisition list the roadmap's D-track executes | [`../bibliography/README.md`](../bibliography/README.md) |
| ADR backlog | Where the roadmap parks decisions until they are written | [`../adr/README.md`](../adr/README.md) |
| Validation plan | Where the roadmap parks "measure this" items | [`../validation/README.md`](../validation/README.md) |
| Environment spec | The E-track's deliverables | [`../devenv/README.md`](../devenv/README.md) |
| Project-phase table (Phase 0–3, weeks 0–16) | The outward-facing summary of the same timeline | [`../../README.md`](../../README.md) |

The roadmap is a living document: when a phase closes, tick its DoD in the same commit that closes it; when an open question is resolved, move its routing-table row to **closed** with the ADR/experiment that closed it. Do not fork the phase definitions — they are restated (briefly) in [`../../CLAUDE.md`](../../CLAUDE.md) and must stay aligned.
