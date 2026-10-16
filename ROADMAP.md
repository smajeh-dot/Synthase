# Synthase roadmap

What Synthase will (and will not) do, in build order. Numbers in brackets, such as (#6), refer to the original 80-item feature list from planning.

How this file works:
- An item becomes a GitHub issue only when it is scheduled. Only Foundations and Tier 1 items are issues for now.
- Milestones M0 to M4 on GitHub are ordered phases with no due dates. Work follows milestone order, whenever there's time.
- Change this file through a normal pull request, like any other change.

Ground rules every feature follows:
- **AI-free and deterministic.** The same input always gives the same output.
- **Offline first.** Online features are optional, cache their results and say plainly when you are offline.
- **The tool is in the repo; the science is not.** All lab data, results, compounds, notes and real config values live in a local workspace on the user's computer, outside this repo.
- **Every scientific constant lives in the config**, with a source and a verified or unverified status. Every result that uses an unverified value says so.
- **Output conventions:** plain language, jargon defined on first use, SI units, 3 significant figures. Every result table can also be saved as CSV.

---

## Foundations (milestone M0)

Built into everything, not separate lab commands.

| Item | What it does | From |
|---|---|---|
| Windows setup script | PowerShell script: creates the virtual environment, installs dependencies including RDKit, runs the self-test | #72 |
| `syn` entry point | One command-line entry point shared by every tool, with one data format and one config | #73 |
| `syn doctor` | Self-test: checks the install and the config, and lists every config value still marked unverified | #72 + new |
| `syn init` workspace | Creates the local workspace outside the repo (`raw/`, `maps/`, `results/`, `notebook/`, `config`). Synthase never writes into its own code folder. | new |
| Config system | A committed template holds placeholder values marked `UNVERIFIED`. The real config lives in the workspace, and every value records its source and verification status. | new |
| Provenance | Raw files are fingerprinted (hashed) and made read-only when imported. Every output records the code version, input fingerprints and the settings used. | #54 + #55 |
| Continuous integration (CI) | GitHub Actions on Windows: lint plus tests on every pull request and every merge into `main` | #74 |
| Tests | Every calculation has at least one hand-worked example as a test, using invented numbers only | #75 |
| Pre-commit hooks | Formatting, secret scanning (gitleaks) and a large-file block. They run in Claude sessions, and CI repeats the same checks | #79 |

---

## Tier 1: the core loop (very likely)

### M1: first commands (no lab data needed)

Build in this order. `/yield` and `/plate design` both read from the compound register, so the register comes first.

#### 1. `/compound`: compound register (#3, #18, #19)
Add a compound the moment it is only an idea, and fill in its details as the project produces them. Every field except a short label is optional.

| Command | What it does |
|---|---|
| `/compound add` | Creates an entry with the next ID (`SYN-001`, `SYN-002` ...). Prompts for whatever is known; the rest can be left blank. |
| `/compound edit <ID>` | Fills in or changes fields. Asks for confirmation before overwriting a value that is already set. |
| `/compound show <ID>` | A full record card, plus a "still missing" list (for example: no melting point yet, no risk assessment recorded). |
| `/compound list` | A table of all compounds, filterable by status or class. |
| `/compound archive <ID>` | Hides an abandoned compound. Nothing is ever deleted. |

Fields:
- **Identity:** label or name; class (Schiff base, chalcone, starting material, other); SMILES (the text notation for a chemical structure). When a SMILES is entered, RDKit checks it is valid and fills in the molecular formula and the molar mass (g/mol, 3 s.f.).
- **Status:** planned → synthesised → purified → characterised → tested.
- **Batches:** date, mass made and yield. One compound can have several batches, and `/yield` adds them automatically.
- **Characterisation:** melting-point range, flagged by the purity rule in the config; Rf value with the solvent system used; links to spectra files in the workspace.
- **Handling:** appearance and colour; solubility and DMSO stock concentration; storage conditions. A compound recorded as coloured makes `/plate design` remind the user to add a compound-only blank.
- **Safety:** whether a risk assessment has been done (yes or no, with the date); hazard notes.
- **Notes:** free text.

Behaviour:
- Every edit is logged with its date and the old and new values.
- Data is stored in SQLite inside the local workspace, never in the repo.
- Works as guided prompts in the terminal interface, or as flags on the plain command line (for example `syn compound edit SYN-001 --mp "142-144"`).
- Tests use invented compounds only.

#### 2. `/calc`: lab calculator (#1, #43, #45)
- Converts between mass, amount, concentration and molarity.
- Stock solutions and serial dilutions.
- DMSO limit check, using the limit from the config.
- Inoculum preparation from OD600 and a calibration curve.
- Transformation efficiency (CFU per µg DNA).

#### 3. `/yield`: stoichiometry and yield sheet (#2)
- Takes the SMILES of each reagent and gives molar masses, equivalents, masses to weigh, and theoretical and % yield.
- Saves each run as a batch in the compound register.

#### 4. `/plate design` and `/checkerboard design` (#6, #7, #71)
- One shared engine produces 96-well layouts with serial dilutions and all the controls.
- Outputs a plate map file and a printable pipetting sheet.
- Checks the DMSO limit.
- Prints a pre-run checklist (controls, risk assessment, sign-off) before the sheet.

#### 5. Library enumerator (#32)
- Lists every Schiff base or chalcone that can be made from lists of aldehydes and amines (or ketones).
- Chosen compounds can be added straight to the register as "planned".
- Placed late in M1 because the compounds are not yet chosen.

### M2: terminal interface
- Full-screen Textual app: scrolling output area, a fixed command bar, a status line, slash commands with tab completion, history, inline tables and plots, and confirmation before overwriting files.
- `/help [topic]` with fixed help text, and `/config` to show or edit settings.
- Anything that is not a command gives "unknown command, try /help".

### M3: data pipeline
| Command | What it does | From |
|---|---|---|
| Fake data generator | Produces fake plate reads, so the pipeline can be tested without the lab | #76 |
| `/parse` | Reads plate-reader exports into one tidy table. Blocked until a sample export exists; the copy committed for tests must be a blank-plate export or a hand-built file with invented values. | #8 |
| `/clean` | Subtracts blank and compound-only wells and normalises OD600 | #9 |
| `/mic` | Applies the growth threshold from the config, calls the MIC, and flags rows that don't change in one direction and skipped wells | #10 |
| `/fici` | MICs alone and in combination, FIC(A), FIC(B), FICI, the interpretation band from the config, and an isobologram | #11 |
| Figure style | One colour-blind-safe style used by every plot, with poster and slide size exports | #15, #63 |

### M4: results and record keeping
| Command | What it does | From |
|---|---|---|
| `/stats` | Means, SD, and median or modal MIC across biological repeats, worked on log₂ values to respect the two-fold MIC scale | #14, #51 |
| `/log` | Dated lab-notebook entries linked to files and compound IDs, with a mentor sign-off field | #16, #70 |
| `/backup` | Zips the workspace to a chosen location (OneDrive folder or USB) | #78 |
| `syn demo` | Runs the whole analysis loop on fake data | new |

---

## Tier 2: likely, if time allows

| Item | Note | From |
|---|---|---|
| PAINS and reactivity alerts | RDKit has these filters built in. Chalcones will be flagged as Michael acceptors, which is a useful point for the write-up. | #36 |
| SAR table | Activity side by side with descriptors RDKit calculates offline (logP, TPSA, MW, H-bond donors and acceptors). Substituent constants come from the config. | #31 |
| Spectra peak table | Parses IR/NMR exports and compares peaks to the configured expected ranges. Depends on which instrument and export format are available. | #17 |
| Growth-curve fitter | Only useful if the plate reader takes readings over time | #12 |
| Edge-effect and outlier flags | Added to `/mic` | #53 |
| Strain inventory | Flags anything that isn't BSL-1 or isn't on the allowed list | #68 |
| Hazard table drafter (online, cached) | GHS statements for human review | #5 |
| DOI to citation (online, cached) | Via Crossref | #20 |

## Tier 3: only if extension assays happen or the write-up needs them

Nitrocefin assay analyser (#48), time-kill curves (#49), dose-response fitting (#13), FICI vs Bliss/Loewe comparison (#56), uncertainty propagation (#57), mechanism drawings (#35).

---

## Cut

| Reason | Items |
|---|---|
| Writing and content work, not lab maths. It would hold science, so it belongs in local documents, not the tool. | #21, #22, #23, #25, #27, #28, #29, #30, #58, #59, #61, #62, #64, #65, #66, #67 |
| Free existing tools do it better | #41 (plasmid maps), #42 (primers), #60 (Gantt), #80 (docs site; the README plus `/help` is enough) |
| Too few compounds (6 to 8) for the analysis to mean anything | #34, #40, #52 |
| Rough rules of thumb that can't be verified, so they risk giving confident-looking wrong answers | #33 (revisit once the rules are verified), #37, #38 |
| Online, outside the core, low value for this project. RDKit already covers #4 offline. | #4, #24, #26, #39, #46, #47, #50 |
| Hard to make reliable from photos | #44, and the photo part of #18 |
| A second interface on top of the terminal one | #77 |
| Low value | #69 |
