# Synthase roadmap

What Synthase will (and will not) do, in build order. The feature spec, [`docs/spec.md`](docs/spec.md), is the full description: every command, rule and example lives there, and this file only points to it. Where the two disagree, the spec wins.

How this file works:
- An item becomes a GitHub issue only when it is scheduled. Each feature has a parent issue with a build plan; the next issue is the first open one in that plan. F1's plan is in #92.
- There are no milestones and no due dates. Work happens whenever there's time.
- Synthase stays at version `v0.2.0` until the owner decides to change it.
- Change this file through a normal pull request, like any other change.

Ground rules every feature follows (spec Sections 1 to 3):
- **AI-free and deterministic.** The same input always gives the same output.
- **The tool is in the repo; the science is not.** Projects, experiments, values and compounds live in a `data\` folder inside whichever folder the owner runs `synthase` in, outside this repo (decision [0023](docs/decisions/0023-command-set-and-project-folder.md)).
- **A databank, not a calculator.** Values are stored exactly as typed and never rounded, converted or recalculated. Synthase only computes what can't be done by hand or on a scientific calculator.
- **It doesn't duplicate the other tools.** No plotting or explanations (Claude), no spreadsheet or table viewer (Excel), no text editor (Word).
- **Windows only.** Every setup and run instruction is for PowerShell, on native ARM64 or x64 Python 3.13.

---

## Clean slate (done)

The old app (v0.2.0) was removed in #93, and the docs and rules were updated in #94 (decision [0020](docs/decisions/0020-clean-slate.md)). The old app is still available under the `v0.2.0` tag.

## F1: the Ledger (spec Section 4, F1)

A plain databank of projects, experiments, values and compounds. Values are stored exactly as typed, with an append-only history, and can be shown, fetched by ID, exported and imported as CSV. Built in three stages (spec 9.2), as the sub-issues of #92:

| Stage | What it builds |
|---|---|
| Shell skeleton | The full-screen app, the single command table, help, suggestions and usage errors |
| Storage layer | The Synthase folder, safe TOML saving, data IDs, the history log and the project lock |
| F1 itself | Projects, experiments, values, the compound library, fetch, export and CSV import, the unit check |

## F3: reaction records (spec Section 4, F3)

Record-only reaction records inside an experiment, using F1's compounds, and a way to find past reactions. Nothing is calculated. Gets its own parent issue once F1 is finished.

## F4: saved fits (spec Section 4, F4)

A stored line-of-best-fit equation from a fixed list of models in the owner-editable `models.toml`, which can be queried later and re-run to confirm an identical result. Gets its own parent issue once F3 is finished.

---

## Parked (spec Section 6A)

Nice to have, not important. **Nothing here is built** unless the owner promotes it into the spec's Section 4.

| Idea | What it would be |
|---|---|
| X1: Stochastic kinetics | Gillespie simulation for systems with few molecules. Depends on X2. |
| X2: Mechanism simulation | What-if kinetics for a reaction mechanism written as elementary steps |

## Cut (spec Section 6)

Recorded so they are not proposed again. The numbers F2, F5, F7 and F8 are never reused.

| Feature | Why it was cut |
|---|---|
| F2: Live Word sync | Typing placeholders in Word is slower than fixing the odd stale number by hand |
| F3, calculator version: reaction table | Rudimentary calculations the owner prefers to do by hand; replaced by record-only F3 |
| F1 calculation features | F1 is a databank only: no derived values, unit conversion, uncertainty propagation or rounding |
| F5: Sequence library | No clear case where a stored sequence would be needed |
| F7: Statistical tests | Overkill |
| F8: Bench clock | A stopwatch and Excel are fine |

Everything the old roadmap listed (calculators, plate design, MIC and FICI analysis, statistics, plots, the lab log and backups) is also out: the spec builds only F1, F3 and F4 (spec 9.1).
