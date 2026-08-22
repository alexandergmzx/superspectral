# Session plans

One file per **autonomous or long-running session**, named `<date>-<purpose>.md`. The
convention is borrowed from the author's `omniverse_twin` project, whose `CLAUDE.md`
§"Unattended sessions" is the rule set these sessions run under.

A session plan is **written before the work starts** and is **binding** once written:

| Section | Purpose |
|---|---|
| Approved header | Date, wall-clock budget, the "no new unit after" time, and that the plan is binding |
| Live status | One row per unit, updated **after every unit** with its commit hash — the session's own audit trail |
| Context | What is true when the session starts, with file paths; corrections to earlier claims belong here |
| Rules in force | The subset of the unattended rules that binds tonight, restated so nothing depends on memory |
| Unit queue | Ordered units with a time box and a **gate** (what must be true to mark DONE) |
| Verification | The exact commands a unit must pass before its commit |
| Not delegated | What the session may not decide or do — parks to the handback |
| Handback | **Mandatory**, written even when the session fails early: headline, green/red, commits, morning decisions |

Rules that make these files worth reading later:

- The **handback is the deliverable**. A session that produced no code but an honest
  handback is a session that worked.
- Status rows carry commit hashes, so `git show <hash>` is always the next step.
- Negative results are recorded in bold, not deleted. A killed hypothesis is evidence.
- The first action after any context compaction is to re-read the active plan.

## Sessions

| Date | Purpose | Outcome |
|---|---|---|
| [2026-08-21](2026-08-21-overnight-phase0.md) | Overnight Phase-0 documentation session (docs only, branch `overnight-2026-08-21`) | in progress |
