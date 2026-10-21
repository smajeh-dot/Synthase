> **Superseded by [0020](0020-clean-slate.md).** It describes the retired app.

# 0012: Bring the terminal interface forward

## Context
The roadmap built every M1 command (`/compound`, `/calc`, `/yield`, plate designs, library enumerator) before the full-screen terminal interface (M2). Real lab data won't reach Synthase for a while, and the owner wants the full-screen app sooner (#29).

Several roadmap items only matter once lab data arrives:
- **Provenance (#14)** fingerprints raw plate-reader files and records how results were made. Raw files arrive with `/parse`, in the data pipeline.
- **Inline plots** need something to plot. Nothing draws plots until the data pipeline's figure style.

The terminal interface itself only needs some commands to run, and one command layer that both the app and the plain command line use.

The owner chose the recommended order and all the triage defaults for #29 (2026-10-17).

## Decision
- **New milestone order:**
  - **M0 Foundations:** unchanged, except provenance moves to M4.
  - **M1 Compound register:** `/compound` on the plain command line. It is the first real command, and its guided prompts are the first real test of how input should work, before the app's design is fixed.
  - **M2 Terminal interface:** the full-screen Textual app, `/help`, `/config`, and `/compound`, `doctor` and `init` running inside it. Textual is added as a dependency here, when the feature needs it (decision 0003).
  - **M3 Lab calculators and plate design:** `/calc`, `/yield`, `/plate design`, `/checkerboard design`, the library enumerator, and `/log`. `/log` moved here from the old M4, because notebook entries start with synthesis, long before plate readings.
  - **M4 Data pipeline:** as before, plus provenance (#14) and inline plots.
  - **M5 Results and record keeping:** `/stats`, `/backup` and `syn demo`.
- **One shared command layer:** every command does its work once. The plain command line (`syn compound add`) and the app (`/compound add`) both call it. `/compound` is built this way in M1, so moving it into the app in M2 is a small planned change, not a rewrite. Every M3 command works both ways from the start.
- **Milestones on GitHub** are renamed and created to match, by Claude through the GitHub API, because they were empty. #14 moves to M4 Data pipeline.
- **Releases** keep the same rule with one more milestone: M1 = `v0.1.0` up to M5 = `v0.5.0`.

## Consequences
- The full-screen app arrives after one command instead of five.
- `/yield` and the plate designs, in M3, write outputs before provenance exists (M4). Those outputs won't record their code version and inputs until M4 adds it, which will need a small change to each.
- The release numbers no longer match the old milestone contents. For example, v0.3.0 is now the lab calculators, not the data pipeline.
- The skill and `owner-setup.md` list six milestones instead of five.
