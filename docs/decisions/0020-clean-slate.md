# 0020: Clean slate for the feature spec

## Context
The owner wrote a new feature spec in a separate Claude session (#92). It describes Synthase as a plain databank of projects, experiments, values and compounds (F1, the Ledger), with record-only reaction records (F3) and saved curve fits (F4). Where the spec and the existing app clash, the spec wins. Nearly every part of v0.2.0 clashes with it: the SQLite compound register with RDKit-computed values, the workspace and config of scientific constants, `doctor`, `fit check`, the `syn` command line, rounding to 3 significant figures, y/N questions and lenient name matching. The conflict table is in #92.

The owner considered starting a new repository. They chose on 2026-10-21 to wipe the app in place instead: the repo's groundwork (CI, hooks, templates, skills, the setup script and the GitHub settings) fits the spec as it is, and the old app stays available under the `v0.2.0` tag.

## Decision
- **The old app is retired.** All of its code, tests, the fit manual and its design files (`theme.py`, `synthase.tcss`) are deleted (#93). No compounds are migrated; the owner's old workspace folder stays on their laptop untouched.
- **The feature spec replaces the roadmap.** The Ledger is built first, then reaction records, then saved fits (#92, #94).
- **A full-screen layout, not a line prompt.** The app runs full screen inside the PowerShell window, styled from the owner's design system. This replaces the spec's line prompt (spec 1.3); the spec's prompt context (`Project/E002`) is shown inside the layout. The library is chosen when the app shell is built.
- **`synthase` is the only command.** It opens the app. There is no `syn` and no one-shot command typed in PowerShell (spec D15). Commands inside the app have no leading `/`.
- **Native Python on every laptop.** RDKit was the only reason for the x64 Python on an ARM laptop. Without it, the setup script wants Python 3.13 built for the laptop's own processor (still exactly 3.13, decision 0002), and CI runs a second check, `ci-arm64`, on ARM64 Windows.
- **The setup script** removes the old `syn.cmd`, warns when the code folder is inside OneDrive, and checks that `synthase` in a new window runs its own shim, naming anything that gets in the way.
- **Until the app is rebuilt,** `synthase` prints one line saying so.

## Consequences
- About 430 tests leave with the code. The hygiene, setup-script and placeholder tests remain.
- The SQLite lines leave `.gitignore`, because nothing in the spec uses a database.
- An ARM laptop with only the x64 Python must install the ARM64 Python 3.13 and rebuild `.venv`; the setup script says how.
- `ci-arm64` is not yet required by the `main` ruleset. The owner adds it after it has run once.
- Decisions 0003, 0008 to 0010, 0012 and 0014 to 0019 describe the retired app. #94 marks them as superseded by this record.
