# Synthase — Feature Specification

> **Copy for the repo.** This is the owner's feature spec, committed so every build session works from the same text (#94). The owner's name and personal paths were removed; nothing else was changed below the line.
>
> **Owner's decisions since the spec was written (2026-10-21, #92).** Where these and the spec disagree, these win:
> 1. **Full-screen layout inside PowerShell.** It replaces the line prompt in 1.3. The prompt context (`Project/E002`) is shown inside the layout.
> 2. **`synthase` is the only command.** It opens the app.
> 3. **No leading `/`.** Commands are typed exactly as in this spec.
> 4. **C164–C173 are accepted as written.** C174–C184 still await the owner's confirmation.
> 5. **Exactly Python 3.13, native ARM64.** This narrows "3.11 or newer" (C184).

---

> **Status:** v1 specification complete. F1, F3 and F4 are `ACCEPTED`. The gap-filling defaults in Section 5.1 (C164–C184) are proposed and await the owner's confirmation. X1 and X2 are parked.
> **Audience:** A Claude Code session that will build Synthase from this spec.
> **Started:** 2026-10-21 · **Last updated:** 2026-10-21 (wrap-up and consistency pass, D39–D40)

---

## 0. How to read this document (for the builder)

- Sections 1–3 are **global rules** that apply to every feature.
- Section 4 holds the **features to build**: F1 (Ledger), F3 (Reaction records) and F4 (Saved fits). All three are `ACCEPTED`. (F2, F5, F7 and F8 were cut and no longer have sections; they are listed in Section 6 so they are not re-proposed. The numbers F2, F5, F7 and F8 are never reused.)
- Section 5 is the **clarifications register**. 5.1 lists the gap-filling defaults still awaiting the owner's confirmation. Treat each default as the plan, but if the owner has changed one, the 5.1 table has been updated and wins. 5.2 holds everything already resolved and binding. **If you find a gap that is not covered anywhere in this document, stop and ask the owner. Do not invent behaviour.**
- Section 6 lists **cut ideas**. Section 6A lists **parked "shiny" ideas** (X1, X2). **Do not build anything in 6 or 6A** unless the owner promotes it into Section 4.
- Section 7 is the **decision log**. If a feature description and the decision log disagree, the most recent decision wins.
- Section 9 holds **hand-off notes**: build order, dependencies, packaging and tests.
- Feature numbers (F1, F3, F4) and parked-idea numbers (X1, X2) are spec labels only. They are unrelated to the data IDs used inside the app (E001, C001, A001).
- Every command in this document is typed **at the Synthase prompt** unless marked `PS>` (typed in plain PowerShell).

---

## 1. Product definition

Synthase is a **Python application, launched from PowerShell on Windows**, that supports a scientist across three phases of work:

1. **During the experiment** — recording what was used and measured.
2. **Interpretation of results** — reproducible heavy computation that can't be done by hand.
3. **Write-up** — a reliable place to look numbers up.

It covers many disciplines, with mandatory depth in:

- **Mathematics**
- **Chemistry** — synthesis, kinetics, yield, reaction-system analysis, etc.
- **Biology** — molecular biology, biochemistry, bioinformatics, genomics

### 1.1 The companion-tool rule

Synthase is used **alongside** three other tools. A Synthase feature is only justified if it does something those tools do badly, slowly, or not at all.

| Tool | What it is good at (Synthase must NOT duplicate) | Its weakness (where Synthase can win) |
|---|---|---|
| **Claude (Claude Science)** | Plotting via matplotlib; explaining concepts; open-ended reasoning | **Not reproducible** — gives a different answer each time; no audit trail of how a number was produced |
| **Excel** | Quick arithmetic; recording results; viewing `.csv` files | Values silently overwritten with no history; hard to search across many files; weak at heavy, domain-specific science computation |
| **Microsoft Word** | Writing the report | Not a store of data |

**Synthase must avoid:** plotting (Claude), concept explanation (Claude), being a spreadsheet/table viewer (Excel), being a text editor (Word), and any calculation a scientific calculator can do (the owner does those).

The owner copies numbers into Word by hand. Automatic Word sync was considered and cut (Section 6).

### 1.2 Synthase's two roles (D21)

1. **Databank (F1, F3).** A plain source of truth. Values are stored exactly as typed, retrieved and searched. **No calculations of any kind are run on stored values**: no derived values, no recalculation, no unit conversion, no uncertainty propagation, no computed molar masses, no rounding.
2. **Heavy computation (F4).** Synthase only computes things that **genuinely cannot be done by hand or on a scientific calculator**: e.g. nonlinear fitting, large linear algebra, Monte Carlo simulation, sequence algorithms. Every feature proposing a calculation must state why it passes this test.

### 1.3 Interaction model

- Synthase runs as an **interactive shell inside the PowerShell window** (not a separate GUI window). The user types `synthase` once in PowerShell; from then on, all commands are typed **without the `synthase` prefix** at Synthase's own prompt (D4).
- **There is no one-shot mode.** Commands are never run from the PowerShell prompt directly (D15).
- **Prompt** shows the active context: `Aspirin synthesis/E002 >` with an experiment open; `Aspirin synthesis >` with only a project open; `>` when nothing is open.
- All examples are written **as typed at the Synthase prompt**, unless marked `PS>` (typed in plain PowerShell).

### 1.4 Data hierarchy

```
Project                     (one Ledger per project)
 ├── Compound library       (C001, C002… project-wide; typed once)
 ├── Analysis records       (A001, A002… saved fits (F4))
 └── Experiment             (E001, E002…; each created with a date+timestamp)
      ├── Reaction record   (optional, one per experiment, record-only — F3)
      └── Value             (named entry: value, unit, optional uncertainty, note, history)
```

---

## 2. Environment and platform constraints

- **OS:** Windows. Owner's primary machine is a **Windows on ARM64 Surface Pro**. WSL2/Linux is **not** available.
- **Shell:** PowerShell. All commands, examples and docs must be written for PowerShell/Windows. No macOS or bash instructions anywhere.
- **Language:** Python, installed as a package with a console entry point so typing `synthase` in PowerShell launches the app.
- **ARM64 dependency rule:** Every dependency must have a Windows ARM64 wheel or be pure Python. If a critical dependency has no ARM64 wheel, the builder must either (a) document running an x64 Python under Windows' x64 emulation, or (b) choose a pure-Python alternative. Flag any such dependency explicitly. *(Builder: verify at build time — do not assume. Especially relevant to `numpy`/`scipy` for F4.)*
- **Console gotchas:**
  - Synthase reads each line itself, so PowerShell's special characters (`$ @ ( ) { } ;`) are not a problem inside the app.
  - Non-ASCII symbols (`±`, `µ`, `°`, `Å`) can be mangled in older consoles (Windows PowerShell 5.1). Each must have an **ASCII alternative** accepted on input (`+/-` for `±`, `u` for `µ`, `degC` for `°C`). Output uses UTF-8 and degrades to ASCII if the console can't render it.
  - Dragging a file into the PowerShell / Windows Terminal window pastes its path wrapped in quotes. Any prompt or command that takes a file path must strip surrounding quotes and whitespace.
- **Determinism:** Same inputs + same Synthase version → the same outputs: bit-identical on the same machine and installation and, for numerical features (F4), equal to within 1e-9 relative on a different machine, because floating-point hardware and maths libraries differ in the last digits. No randomness without an explicit, recorded seed. No network calls in core features.

---

## 3. Global architecture

- **Interactive shell:** a REPL with command history (up-arrow) and tab-completion of command words, IDs, value names and field names. Suggested library: `prompt_toolkit` (pure Python — verify ARM64).
- **Storage format: TOML** (D5), read/written with `tomlkit` (pure Python), which **preserves the user's comments and formatting** when Synthase rewrites a file.
- **Data IDs: `Letter` + `NNN` (D26).** Every stored data object gets an auto-assigned ID: one capital letter for its type, then three digits, no separator. E.g. `E020` (experiment), `C003` (compound). Details: C80–C84.

  | Letter | Data type | Status |
  |---|---|---|
  | `E` | Experiment | Agreed |
  | `C` | Compound | Agreed |
  | `A` | Analysis record (saved fits from F4) | Agreed |

- **Exact values, no rounding (D25).** Every number the user types is stored and shown **exactly as typed**, including trailing zeros (`2.100` stays `2.100`). Builder: store numbers as **text** in TOML (e.g. `value = "2.100"`), because a TOML float would lose trailing zeros. *(Computed F4 results are displayed to 4 s.f.: C103, C180.)*
- **Exact names, with suggestions (D23, D24, D27).** Every name or ID typed in a command must match exactly, including case. If it doesn't, Synthase **suggests the two closest matches** — it never runs a corrected command and never asks y/n. If nothing is close, it **lists everything** of that kind. If a command is missing a part or has too many, it prints the command's **correct usage**. Examples:
  ```text
  > fetch C001 molarmass
  Unknown field 'molarmass' for C001. Closest: molar_mass, formula
  > fetch C010 formula
  Unknown compound 'C010'. Closest: C001, C011
  > fetch C001 boiling
  Unknown field 'boiling' for C001. Fields: name, formula, molar_mass, density, purity, note
  > fetch
  Usage: fetch <ID> [field or value name]
  ```
- **History log:** append-only `history.jsonl` (one JSON object per line) per project. Written only by Synthase; readable in Notepad but not intended for hand-editing.
- **Projects location:** `Documents\Synthase\<Project name>\`, changeable in `Documents\Synthase\settings.toml`. Details: C172.
- **Timestamps:** stored as ISO 8601 with UTC offset (`2026-10-21T14:32:07+01:00`); shown as `2026-10-21 14:32:07`.
- **Folder layout:**
  ```
  Documents\Synthase\
    settings.toml                   <- global settings (projects location, etc.)
    models.toml                     <- F4 model registry, shared by all projects (owner-editable)
    Aspirin synthesis\              <- project folder
      project.toml                  <- project metadata
      compounds.toml                <- project-wide compound library
      history.jsonl                 <- every change, ever
      experiments\
        E001-first-attempt.toml
        E002-recrystallisation-trial-2.toml
      analyses\                     <- F4 saved fits
        A001-exp-decay.toml
        A002-linear.toml
      exports\                      <- files written by export commands
  ```
- **Experiment file:**
  ```toml
  [experiment]
  id = "E002"
  title = "Recrystallisation trial 2"
  created = 2026-10-21T14:32:07+01:00
  x_unit = "s"        # optional; x unit for F4 fits in this experiment (default s)

  [values]
  m_salicylic = { value = "2.003", unit = "g", unc = "0.001", note = "Balance B2" }
  c_HCl       = { value = "0.100", unit = "mol/dm^3" }
  m_crude     = { value = "2.211", unit = "g" }
  ```
- **Compound library file:**
  ```toml
  [C001]
  name = "Salicylic acid"
  formula = "C7H6O3"
  molar_mass = { value = "138.12", unit = "g/mol" }
  purity = { value = "99", unit = "%" }
  note = "Sigma-Aldrich, lot 12345"

  [C002]
  name = "Acetic anhydride"
  formula = "C4H6O3"
  density = { value = "1.08", unit = "g/cm^3" }
  ```
- **Output formats:** human-readable tables in the console; `export --csv` / `export --json` for Excel and other tools (layouts: C170). Exports contain values exactly as stored.

---

## 4. Features

### Discipline coverage tracker

| Discipline | Built by | Notes |
|---|---|---|
| Mathematics | F4 (regression and non-linear least-squares fitting) | Nothing else mathematical is accepted. |
| Chemistry | F1 (compound library), F3 (reaction records), F4 (kinetics, Arrhenius) | Mechanism simulation (X2) and stochastic kinetics (X1) are parked. |
| Biology / biochemistry | F4 (enzyme kinetics, Hill, dose–response) | Enzyme-mechanism simulation (X2) is parked. |
| Molecular biology / bioinformatics / genomics | **Nothing** | F5 (sequence library) was cut. |
| Physics | Nothing | Not required by the brief. |
| All (general) | F1 (databank) | |

**Known gaps (owner is aware).** The brief asked for mathematics, chemistry and biology (molecular biology, bioinformatics, genomics). The accepted features cover chemistry and biochemistry well, mathematics only through curve fitting, and molecular biology / bioinformatics / genomics not at all. Several candidate ideas in those areas were rejected because the owner can already do them by hand, in Excel or in Claude (Section 6). Any future idea in these areas must pass the companion-tool rule (1.1) and the "can't do it by hand" test (1.2), and must not simply store sequences.

---


### F1 — The Ledger: a plain databank of projects, experiments, values and compounds

**Status:** `ACCEPTED` (2026-10-21, D34). Gap-filling defaults C164–C173 (Section 5.1) await confirmation.
**Phase(s):** During experiment · Interpretation · Write-up
**Disciplines:** All

#### Problem it solves
Experimental values end up scattered across Excel files, lab notebooks and chats, and get overwritten with no history. There is no single, trustworthy place to store what was used and measured, and to pull it back out later.

#### Principle
F1 **stores and retrieves only**. It runs no calculations on anything stored (D21, D22). Values are kept exactly as typed (D25).

#### Commands

| Command | Purpose |
|---|---|
| `create project <name>` | Create a project folder and open it. |
| `open project <name>` | Open an existing project. |
| `list projects` | List projects. |
| `create experiment [title]` | Create a date+timestamped experiment with the next free `E` ID; title prompted if omitted; it becomes the active experiment. Then asks: load values from a file, or enter them manually (D6). |
| `open experiment <ID or title>` | Make an experiment active. |
| `list experiments` | List experiments (ID, title, created). |
| `edit experiment <title or x_unit> <value>` | Change the experiment's title (C166), or set the x unit F4 uses for fits in this experiment (default `s`; C107). |
| `add <name> <value> <unit> [+/- unc] [# note]` | Store a new value in the active experiment. |
| `edit <name> <value> <unit> [+/- unc] [# note]` | Change an existing value; the whole entry is replaced (C164). Prints `Updated m_crude: 2.211 g -> 2.215 g` (D8). |
| `delete <name>` | Delete a value (logged in history, not erased). Refused if an F3 reaction record points at it; Synthase names the reaction. |
| `show` | Table of all values in the active experiment. |
| `history <name>` | Every version a value has had, with timestamps. |
| `fetch <ID> <field or value name>` | Print one stored item: `fetch C001 molar_mass` (compound field) or `fetch E002 m_crude` (experiment value). Works from anywhere in the project; no need to open the experiment (C75). Also works on analysis records (`A` IDs, F4). |
| `fetch <ID>` | Print everything stored for that compound or experiment (C75). |
| `export --csv` / `export --json` | Export the active experiment (C170). |
| `add compound` | Add a compound with the next free `C` ID; prompts for each standard field in turn, Enter skips (C78). |
| `edit compound <ID> <field> <value> [unit]` | Fill in or change a compound field; with no value, clears it (C166). |
| `list compounds` / `show compound <ID>` | Inspect the library (list shows ID and name). |
| `help` / `help <command>` | Help, including each command's usage line. |
| `exit` | Leave the app. |

#### Rules
- **Value entry:** `name value unit [+/- unc] [# note]`, e.g. `m_crude 2.211 g +/- 0.001 # Balance B2`. Used by `add`, `edit` and the manual-entry step of `create experiment`.
- **Exact storage:** value, unit and uncertainty stored exactly as typed (D25).
- **Uncertainty** is opt-in (D9): stored and shown only; never used in any calculation.
- **Units:** checked against a list of recognised units to catch typos (e.g. `gg` → suggestions `g`, `kg`), then stored exactly as typed; never converted (C70). Concentration may be typed as `mol/dm^3`, `mol dm^-3` or `M`.
- **Value names** (inside an experiment, e.g. `m_crude`): any characters except spaces; case-sensitive (C76). The `rxn_` prefix is reserved for F3.
- **Data IDs** (`E020`, `C003`): auto-assigned in `Letter NNN` form (D26) — always the next free number (C80). Names of compounds are stored in the `name` field, which may contain spaces. IDs are per project (two projects may each have a `C001`; `find … all` shows the project name beside each ID) (C83). After `999` the number grows to four digits (`E1000`); existing IDs never change (C82). A deleted ID is never reused (C84). Projects have no ID and are opened by name (C81).
- **Compound fields** (C72, C77): `name`, `formula`, `molar_mass`, `density`, `purity`, `note` — all optional, stored exactly as typed. No check that molar mass matches the formula. No custom fields in v1; use `note`.
- **`add`/`edit` misuse:** `add` on an existing name → error suggesting `edit`; `edit` on a missing name → error suggesting `add`, plus the closest names (D27).
- **File import (`create experiment` → file):** `.csv` with header `name,value,unit,uncertainty,note` (uncertainty and note may be blank). Values taken exactly as written in the CSV. *Note for owner: Excel writes to CSV what each cell displays, so set the cell format to show the digits you want kept.*
- **Hand-edits:** if a file was changed in Notepad while Synthase was closed, on next load Synthase logs an "external edit" in history. If the file is invalid, it refuses to load it and prints the line number of the error.
- **Dropped from earlier drafts (D22, C73, C74):** formulas, derived values, built-in physical constants, live links between experiments.

#### Example session (illustrative)
```text
PS> synthase
Synthase 0.1  ·  type 'help' for commands
> create project "Aspirin synthesis"
Created project "Aspirin synthesis"  ->  Documents\Synthase\Aspirin synthesis
Aspirin synthesis > add compound
  Name: Salicylic acid
  Formula: C7H6O3
  Molar mass: 138.12 g/mol
  Density:
  Purity: 99 %
  Note: Sigma-Aldrich, lot 12345
Added C001 (Salicylic acid).
Aspirin synthesis > fetch C001 molar_mass
138.12 g/mol
Aspirin synthesis > fetch C001 molarmass
Unknown field 'molarmass' for C001. Closest: molar_mass, formula
Aspirin synthesis > create experiment "Recrystallisation trial 2"
Load starting values from a file, or enter them manually? [f/m]: m
Enter one value per line:  name  value  unit  [+/- uncertainty]  [# note]
Blank line to finish.
  m_salicylic 2.003 g +/- 0.001 # Balance B2
  m_crude 2.2110 g

Created E002 "Recrystallisation trial 2"  ·  2026-10-21 14:32:07  ·  2 values
Aspirin synthesis/E002 > fetch E002 m_crude
2.2110 g
Aspirin synthesis/E002 > edit m_crude 2.215 g
Updated m_crude: 2.2110 g -> 2.215 g
```

#### Implementation notes (for builder)
- Store all typed numbers as text (D25). Validate that a value is a well-formed number (e.g. `2.1O` with a letter O is rejected, with the closest valid reading suggested) without converting it.
- Suggestions: use a deterministic string-similarity method (e.g. Python's standard `difflib.get_close_matches`) over the relevant set only (compound fields when the error is a field name, compound IDs when it's an ID, etc.). Return at most two.
- Unit recognition can use `pint`'s unit registry purely as a lookup list (no conversion), or a hand-maintained list. Biology units (`bp`, `U`, `ng/uL`) must be included.

#### Clarifications
All earlier items are resolved (Section 5.2). C164–C173 (Section 5.1) are gap-filling defaults awaiting confirmation: `edit` semantics, name rules, deletion and renaming, ID counters, command-line parsing, units, export, the history log, file locations and safe saving.

---

### F3 — Reaction records (an extension of the Ledger, F1)

**Status:** `ACCEPTED` (2026-10-21). Gap-filling defaults C174–C176 (Section 5.1) await confirmation. Uses F1's data IDs (`C` for compounds).
**Phase(s):** During experiment (logging what was done) · Later work (looking up past reactions)
**Disciplines:** Chemistry; also usable for any biochemical reaction

#### Principle (D20, D21)
**Synthase does not calculate anything for reactions** — no balancing, moles, limiting-reagent detection, theoretical yield or atom economy. The owner does those by hand. Synthase **provides fields to record them** and makes past reactions **easy to look up**.

**Logging a reaction is never obligatory.** An experiment is complete without one. `create experiment` never asks about reactions. Every field is optional except the equation.

#### Commands

| Command | Purpose |
|---|---|
| `create reaction` | Walk through the reaction fields for the active experiment; Enter skips any field. One reaction per experiment. |
| `edit reaction <field> <value>` | Fill in or change a field later (C174). Results are typed values only — no formulas. |
| `show reaction [experiment ID]` | Show a reaction record; unfilled fields shown as `—`. Defaults to the active experiment. |
| `list reactions` | All experiments in the project that have a reaction (ID, title, date, equation, % yield if filled). |
| `find <compound ID or formula>` | Experiments whose reaction includes that compound. Current project by default; `find <term> all` searches every project. Output: experiment ID, title, date, role, % yield if filled (C176). |
| `delete reaction` | Delete the active experiment's reaction (logged in history). |

#### Fields
- **Equation** (required): free text, stored exactly as typed. `->` is the arrow (`=` also accepted). It may use compound IDs, names or formulas. It is **not** checked for balance.
- **Reagents**: one line each, `<compound ID or text> <role> [amount] [equiv] [# note]`.
  - Roles: `reactant`, `product`, `catalyst`, `solvent`, `reagent`.
  - A compound ID (e.g. `C001`) links the line to the library, so `find` can locate it. Plain text (e.g. `H2SO4`) is allowed for things not in the library; `find` matches it as exact text.
  - Amount: either an existing value name in the experiment (e.g. `m_salicylic`) or a typed amount (e.g. `4.10 cm^3`). A typed amount becomes a new value named `m_`, `V_` or `n_` + the reagent's ID/text, according to whether its unit is a mass, volume or amount of substance (C175).
- **Conditions:** `temperature`, `time`, `solvent`, `atmosphere`.
- **Results (all hand-calculated by the owner, all optional):** `limiting`, `m_theor`, `m_actual`, `yield_pct` (unit `%`), `atom_economy` (unit `%`).
- **Observations:** free text.
- Numeric fields are stored as experiment values with the reserved `rxn_` prefix (`rxn_m_theor`, `rxn_m_actual`, `rxn_yield_pct`, `rxn_atom_economy`, `rxn_temperature`, `rxn_time`), so `fetch E001 rxn_yield_pct` works. `add rxn_...` by the user is refused.
- `create reaction` ends by reporting how many result fields were left blank.

#### Example session
```text
Aspirin synthesis/E002 > create reaction
Equation: C001 + C002 -> C003 + acetic acid
Reagents — one per line: ID-or-text role [amount] [equiv] [# note]. Blank line to finish.
  C001 reactant m_salicylic 1.0
  C002 reactant 4.10 cm^3 3.0
  H2SO4 catalyst # 3 drops, conc.
  C003 product

Conditions (Enter to skip each):
  Temperature: 85 degC
  Time: 15 min
  Solvent:
  Atmosphere:
Results (Enter to skip each — fill in later with 'edit reaction'):
  Limiting reagent: C001
  Theoretical yield:
  Actual yield: 2.211 g
  % yield:
  Atom economy:
Observations: White needles after recrystallisation from water
Reaction saved to E002. 3 results left blank.

Aspirin synthesis/E002 > edit reaction yield_pct 84.63
Updated rxn_yield_pct: — -> 84.63 %

Aspirin synthesis > find C002
E001  First attempt               2026-10-14  reactant  yield 71.2 %
E002  Recrystallisation trial 2   2026-10-21  reactant  yield 84.63 %
```

#### Storage (inside the experiment's TOML file)
```toml
[reaction]
equation = "C001 + C002 -> C003 + acetic acid"
limiting = "C001"
observations = "White needles after recrystallisation from water"

[reaction.reagents]
C001  = { role = "reactant", amount = "m_salicylic", equiv = "1.0" }
C002  = { role = "reactant", amount = "V_C002", equiv = "3.0" }
H2SO4 = { role = "catalyst", note = "3 drops, conc." }
C003  = { role = "product" }

[reaction.conditions]
temperature = { value = "85", unit = "degC" }
time        = { value = "15", unit = "min" }
```

#### Why not the other tools?
- **Excel:** can hold a table of past reactions, but not linked to each experiment's stored values and history; searching by compound across many sheets is clumsy.
- **Claude:** cannot reliably recall past experiments.
- **Word:** information is locked in prose.

---

### F4 — Saved fits: a stored line-of-best-fit equation you can query later

**Status:** `ACCEPTED` (2026-10-21, D34). Reshaped by owner (D29). Gap-filling defaults C177–C182 await confirmation.
**Phase(s):** Interpretation (also during an experiment, to predict a value before measuring it)
**Disciplines:** Chemistry (kinetics, Arrhenius), biochemistry (enzyme kinetics, dose–response), mathematics (regression), and any field that fits a curve to data.

#### Owner's framing (D29)
Claude Science already fits curves and makes good matplotlib plots, so Synthase must **not** compete on fitting reports or plots. The gap is **keeping the fit**. Synthase takes a table of results, fits the chosen equation, gives R² where appropriate, and **saves the equation as a permanent, named record**. Later, the owner types in an x value (e.g. `t = 10800 s`, 3 hours) and gets the y value back.

#### Why this is underrepresented in the other tools
- **Claude:** the fit lives in a chat. It is not stored anywhere you can query next week, and re-asking produces a fresh fit that may differ.
- **Excel:** a trendline shows the equation on the chart as text. To use it you must copy the coefficients into a formula by hand, usually rounded. Only a few shapes are available. `FORECAST`/`TREND` handle straight lines only.
- **Synthase:** one saved, reproducible equation with full-precision coefficients, which can be queried by ID at any time.

#### Why it passes the "can't do it by hand" test (D21)
Fitting the equation is the hard part. Least-squares fitting of a straight line is tedious by hand, and of any curved model (exponential, Michaelis–Menten, logistic…) it is iterative and impractical on a calculator. Evaluating a saved equation at one x is trivial on its own. It is a convenience built on top of a fit that couldn't have been done by hand, and it uses the stored full-precision coefficients rather than rounded copies.

#### Commands

| Command | Purpose |
|---|---|
| `fit <model>` | Fit a model from `models.toml` to a CSV table and save it as an `A` record. Prompts for the file, the x column, the y column and the y unit. |
| `predict <A-ID> <number>` | y at that x. Bare number only, in the fit's x unit (D32). Extrapolation warning outside the data range. |
| `show fit <A-ID>` | Readable equation at 4 s.f., plus a `Python:` line with full-precision coefficients for pasting into Claude (C104). |
| `show fit <A-ID> exact` | Readable equation with **every coefficient at full precision** (D33). The `Python:` line is still printed. |
| `list fits` | All fit records in the project (ID, model, experiment, date). |
| `rerun <A-ID>` | Repeat the fit from the stored data and confirm the same result (Section 2, Determinism). |
| `list models` / `help model <name>` | Read the model registry. |
| `fetch <A-ID> <item>` | One item from a fit record: a coefficient (e.g. `fetch A001 k`), `r_squared` or `rse`, `n`. (`fetch` is defined in F1.) |

The x unit comes from the experiment's `x_unit` field, set with F1's `edit experiment x_unit <unit>` (C107).

#### What it does
1. `fit <model>` asks for a CSV file (e.g. exported from Excel), which columns are x and y, and the y unit. The x unit comes from the experiment's details (C107). **The owner chooses the model.** Synthase never picks the "best" model by itself (C96).
2. Synthase prints the fitted equation with its coefficients, R² where appropriate (C97), the number of points and the x-range of the data.
3. The fit is saved as a record (`A001`…) holding the equation, full-precision coefficients, units, x-range, a copy of the data and the Synthase version. `rerun A001` repeats the fit and confirms an identical result.
4. `predict A001 10800` returns y at that x. **Only a bare number is accepted**, taken to be in the fit's x unit; no unit is typed and nothing is ever converted (D32). A warning appears if x lies outside the range of the data (C98).
5. **No inverse (`solve`) command** (D31). The owner rearranges the saved equation by hand. **No prediction intervals, no slope-at-a-point command, no `save` argument on `predict`** (C99, C101, C106).
6. **Models live in an editable file, `models.toml`** (D30). It ships with the 12 starting models; the owner adds new ones by hand-editing it, and `fit` can use them immediately (C108–C112).

#### Model registry: `models.toml`

Created on first run at `Documents\Synthase\models.toml`, never overwritten afterwards. The 12 shipped models (C177 gives the full list with equations; the file below shows the format with four of them plus an owner-added example):

```toml
# Synthase model registry. Add a new model by copying an entry and editing it.
# equation: use x for the independent variable; functions: exp, ln, log10, sqrt; powers with ^
# units: write x and y (e.g. "1/x"); parameters without a unit are shown with no unit.

[linear]
description = "Straight line"
equation    = "m * x + c"
parameters  = ["m", "c"]
units       = { m = "y/x", c = "y" }
r_squared   = true
guess       = "auto"            # built-in starting-guess rule (C178)

[exp_decay]
description = "First-order decay"
equation    = "a * exp(-k * x)"
parameters  = ["a", "k"]
units       = { a = "y", k = "1/x" }
r_squared   = false
guess       = "auto"

[arrhenius]
description = "Arrhenius: k against T (x = temperature in K)"
equation    = "A * exp(-Ea / (8.314462618 * x))"   # R written as a number
parameters  = ["A", "Ea"]
units       = { A = "y", Ea = "J/mol" }
r_squared   = false
guess       = "auto"

[my_new_model]                  # example of an owner-added model (not shipped)
description = "Owner-added example"
equation    = "a * x / (b + x) + c"
parameters  = ["a", "b", "c"]
units       = { a = "y", b = "x", c = "y" }
r_squared   = false
initial     = { a = 10, b = 1, c = 0 }   # starting guesses for the fit
```

Required keys: `equation`, `parameters`. Optional: `description`, `units`, `r_squared` (default `false`), `initial`, `guess` (C109).

#### Example session
The numbers below are real results for the reference data in "Reference tests" (SciPy 1.18.1, NumPy 2.5.3, one machine). The last digits of full-precision values can differ on other machines (Section 2).

```text
Iodine clock/E007 > fit exp_decay
Data file: "C:\Users\<you>\Documents\iodine_conc.csv"
Columns found: time_s, conc
x column: time_s       (x unit from E007's details: s)
y column: conc
y unit: mol/dm^3
Fitting y = a * exp(-k * x) to 13 points (x from 0 to 2400 s)...

y = 0.04812 * exp(-0.0001179 * x)
a = 0.04812 mol/dm^3    k = 0.0001179 s^-1
Residual standard error = 5.206e-05 mol/dm^3   n = 13
(No R² for curved models: it can mislead. The residual standard error is the typical size of the misfit, in y units.)
Saved as A001 (linked to E007).

Iodine clock/E007 > predict A001 10800
y = 0.01347 mol/dm^3   (at x = 10800 s)
Warning: x = 10800 s is outside the data range (0 to 2400 s). Extrapolated values may be unreliable.

Iodine clock/E007 > predict A001 3 h
Usage: predict <fit ID> <number>   (x is in s for A001; units are not typed)

Iodine clock/E007 > show fit A001
A001  exp_decay  (E007, 2026-10-21 15:02:11)
y = 0.04812 * exp(-0.0001179 * x)      x in s, y in mol/dm^3, data x from 0 to 2400 s
Python: y = 0.04812289193798728 * np.exp(-0.00011791972604274007 * x)

Iodine clock/E007 > show fit A001 exact
A001  exp_decay  (E007, 2026-10-21 15:02:11)
y = 0.04812289193798728 * exp(-0.00011791972604274007 * x)      x in s, y in mol/dm^3, data x from 0 to 2400 s
Python: y = 0.04812289193798728 * np.exp(-0.00011791972604274007 * x)

Iodine clock/E007 > fetch A001 k
0.0001179 s^-1

Iodine clock/E007 > rerun A001
Reproduced: largest relative difference in any coefficient 0 (limit 1e-9).
```

#### Record file (`analyses\A001-exp-decay.toml`)
Numbers are stored as text (D25) so nothing is rounded or reformatted. C182 gives the rules around this file.

```toml
[analysis]
id = "A001"
type = "fit"
created = 2026-10-21T15:02:11+01:00
experiment = "E007"            # omitted if no experiment was active
synthase_version = "0.1.0"
numpy_version = "2.5.3"
scipy_version = "1.18.1"

[model]                        # copy of the model at the time of the fit
name = "exp_decay"
equation = "a * exp(-k * x)"
parameters = ["a", "k"]
units = { a = "y", k = "1/x" }
r_squared = false

[input]
source_file = "C:\\Users\\<you>\\Documents\\iodine_conc.csv"
sha256 = "<SHA-256 of the CSV file's bytes>"
x_column = "time_s"
y_column = "conc"
x_unit = "s"
y_unit = "mol/dm^3"
x = ["0", "200", "400", "600", "800", "1000", "1200", "1400", "1600", "1800", "2000", "2200", "2400"]
y = ["0.04822", "0.04703", "0.04590", "0.04479", "0.04376", "0.04271", "0.04172", "0.04075", "0.03983", "0.03893", "0.03806", "0.03714", "0.03633"]

[result]
a = "0.04812289193798728"
k = "0.00011791972604274007"
n = 13
x_min = "0"
x_max = "2400"
rse = "5.205657639879802e-05"
# r_squared = "..."            # present only when the model's r_squared flag is true
```

#### Reference tests (the builder must reproduce these)

**Test 1: exp_decay.** `iodine_conc.csv`:

```text
time_s,conc
0,0.04822
200,0.04703
400,0.04590
600,0.04479
800,0.04376
1000,0.04271
1200,0.04172
1400,0.04075
1600,0.03983
1800,0.03893
2000,0.03806
2200,0.03714
2400,0.03633
```

`fit exp_decay` (x = time_s, y = conc, y unit `mol/dm^3`) must give `a = 0.04812289193798728`, `k = 0.00011791972604274007` and `rse = 5.205657639879802e-05`. Tests compare to **1e-6 relative** (the digits shown are from one machine). `predict A001 10800` must give `0.013466766996426852` (4 s.f. display: `0.01347`).

**Test 2: linear, with R².** x = 1, 2, 3, 4, 5 and y = 2.1, 3.9, 6.2, 7.8, 10.1. The least-squares line is `m = 1.99`, `c = 0.05` (checked by hand: Sxy / Sxx = 19.9 / 10), `R² = 0.9973053…`, and `predict` at x = 6 gives `11.99`. Display: `y = 1.990 * x + 0.05000`, `R² = 0.9973`, `n = 5`. Compare to 1e-9 relative.

**Test 3: reproducibility.** `rerun` of each saved fit reports a largest relative difference of at most 1e-9.

#### Implementation notes (for builder)
- Libraries: `numpy` + `scipy.optimize` (`curve_fit`). **Verify Windows ARM64 wheels for both** (Section 2, Section 9.3).
- Determinism: starting guesses come from fixed, documented rules per model (C178). No randomness.
- The record stores a hash (SHA-256) of the data file and a copy of the data, so `rerun` works even if the CSV is moved or edited, and warns if the original file has changed or is no longer there.
- `predict` must use the stored full-precision coefficients, never the rounded display values.
- Coefficient units are written by substituting the fit's x and y unit labels into each model's `units` entry (e.g. `k = "1/x"` with x in `s` → `s^-1`). This is bookkeeping on labels, not unit conversion. `predict` never converts units (D22, D32). Wrap a label in parentheses when it contains `/` and is used as a divisor or power (e.g. `y/(mol/dm^3)`).
- `models.toml` equations are parsed with a **safe expression parser** (restricted AST walker; never raw `eval`). Allowed: `x`, the model's declared parameters, numbers, `+ - * / ^` and unary minus, parentheses, `exp`, `ln`, `log10`, `sqrt`. Parameter names must not be `x`, `y` or a function name. Synthase validates the whole file at start-up and reports any bad entry with its line number, but still starts, with that model unavailable.
- Each fit record stores a **copy of the model's equation** at the time of fitting, so editing or deleting a model in `models.toml` never changes old fits, and `rerun` uses the stored copy.

#### Clarifications
All earlier items are resolved (C95–C112, Section 5.2). C177–C182 (Section 5.1) are gap-filling defaults awaiting confirmation: the 12 model equations, starting guesses, fitting details, display notation, `predict` errors, and the record file.

---

## 5. Clarifications register

### 5.1 Awaiting owner confirmation (gap-filling defaults, C164–C184)

These close gaps a builder would otherwise have to guess at. Each has a proposed default. When the owner says "defaults fine" they become binding and move to 5.2; the owner may change any item by its number. Items C177 (the 12 model equations), C164 (what `edit` does to omitted fields) and C166 (what can be deleted) are the ones most worth a look.

**F1 and general**

| ID | Topic | Proposed default |
|---|---|---|
| C164 | What `edit` does to fields you don't retype. | `edit <name> <value> <unit> [+/- unc] [# note]` **replaces the whole entry**: whatever is not typed is cleared, so `edit m_crude 2.215 g` removes an earlier uncertainty and note. The old entry stays in `history`. The confirmation line shows the change (`Updated m_crude: 2.2110 g -> 2.215 g`) and, when something was cleared, adds `(uncertainty and note removed)`. |
| C165 | Value-name rules. | Any characters except whitespace; not empty; at most 64 characters; must not start with `#` and must not be `+/-` (both are syntax); case-sensitive. The `rxn_` prefix is reserved for F3. Names are written as **quoted TOML keys** so any character is safe (e.g. `"m_crude (2)" = { ... }`). |
| C166 | What can be deleted or renamed. | **Values:** `delete <name>` (F1). **Experiment title:** `edit experiment title <text>` (the file name keeps its original slug; the ID is what matters). **Compound fields:** `edit compound <ID> <field>` with no value clears the field. **Not in v1:** commands to delete or rename projects, experiments or compounds (D31). The owner does that in File Explorer. On the next start Synthase logs a vanished or renamed file as an external edit (C171) and **never reuses its ID** (C167). A compound referenced by an F3 reaction that is removed in Explorer leaves the reagent line showing the bare ID. |
| C167 | ID counters. | `project.toml` holds `[counters]` with the last number issued per letter (`E = 3`, `C = 5`, `A = 2`). The next ID is counter + 1 (never lower than the highest ID found in the folder). Counters only go up, which is what makes "never reused" (C84) hold even after a file is deleted. |
| C168 | How a command line is read. | Split on whitespace. Text after the first `#` is the note. `+/-` (the `±` character is also accepted on input) introduces the uncertainty. A number is: optional sign, digits with an optional decimal point (`.5` and `5.` are accepted), optional exponent (`1.0e-5`, `1.0E5`). Anything else (a comma decimal such as `1,5`, `1/2`) is refused with the closest valid reading suggested. `create project`, `open project`, `create experiment`, `open experiment`, `edit experiment title` and `find` take **the rest of the line** as one argument; surrounding double quotes are optional and stripped. A trailing `all` token on `find` means all projects. Project names must be valid Windows folder names (none of the characters backslash, slash, colon, asterisk, question mark, double quote, less-than, greater-than or vertical bar; no trailing space or dot, not a device name such as `CON`). The experiment file name is `E002-<slug>.toml`; the slug is the title lower-cased, spaces turned into hyphens, other non-alphanumerics removed, at most 40 characters, fixed at creation. |
| C169 | Unit list and unit check. | A unit is required; `none` is accepted for dimensionless values. A unit string is split on `/`, `*`, spaces and `^n` (negative allowed); every piece must be in a recognised-unit list kept in the code (v1: not editable). The list covers SI and common lab units, including biology: `g mg ug kg`, `L mL uL dm^3 cm^3 m^3`, `mol mmol umol nmol`, `M mM uM nM`, `s min h`, `K degC`, `%`, `bp kb`, `U`, `ng/uL`, `J kJ`, `Pa kPa bar atm`, `rpm`, `Hz`. `pint`'s registry may serve as the lookup, with the extras added by hand. An unknown unit is refused with the two closest suggestions (D27). Nothing is converted. |
| C170 | `export`. | `export --csv` writes `exports\<ExperimentID>.csv` with header `name,value,unit,uncertainty,note` (the same layout `create experiment` imports, so it round-trips). `export --json` writes `exports\<ExperimentID>.json`: an object with `id`, `title`, `created`, `x_unit` and a `values` list of `{name, value, unit, uncertainty, note}`, every value as the text stored. UTF-8; the CSV is written with a byte-order mark so Excel reads `µ` and `°` correctly (import accepts either). Rewriting overwrites the previous file. Prints the path written. |
| C171 | `show`, `history` and the history log. | `show` prints a header line (ID, title, created) and a table with columns `name`, `value`, `unit`, `+/-`, `note`; reaction values (`rxn_…`) are included. `history <name>` prints one line per version: `2026-10-21 14:32:07  added    m_crude  2.2110 g`, `…  edited   m_crude  2.2110 g -> 2.215 g`, `…  deleted  m_crude`. **`history.jsonl`:** one JSON object per line with `ts`, `action` (`add`, `edit`, `delete`, `create_experiment`, `create_reaction`, `edit_reaction`, `delete_reaction`, `add_compound`, `edit_compound`, `fit`, `external_edit`), `id`, `name`, `old`, `new`, `file` and `sha256` (the hash of the file after the change). On load, if a file's hash differs from the last one logged for it (or the file is new or missing), Synthase logs an `external_edit` entry and tells the owner. |
| C172 | Where files live. | The Synthase folder is `Documents\Synthase\`, with `Documents` found through the Windows known-folder lookup (so it works when Documents is redirected to OneDrive); fall back to `%USERPROFILE%\Documents`. `settings.toml` is created on first run and holds one key in v1, `projects_dir`. The environment variable `SYNTHASE_HOME`, if set, replaces the whole location. It exists so tests never touch the owner's real data and is not advertised to the owner. `models.toml` is created on first run and never overwritten afterwards, so a new Synthase version does not touch the owner's edits. |
| C173 | Interrupts, safe saving and locking. | Every file is written to a temporary file in the same folder and then swapped in (`os.replace`), so a crash never leaves a half-written file. Walk-throughs (`create experiment`, `add compound`, `create reaction`, `fit`) save only when finished: **Ctrl+C cancels the current line or walk-through and saves nothing** (an ID is not consumed). Ctrl+D or `exit` leaves the app. A project holds a `.synthase.lock` file with the process ID while open; a second Synthase opening the same project refuses and names the lock (a lock from a process that is no longer running is ignored). |

**F3**

| ID | Topic | Proposed default |
|---|---|---|
| C174 | `edit reaction` in detail. | `edit reaction equation <text>`, `observations <text>`, `limiting <ID or text>`, `solvent <text>` and `atmosphere <text>` take free text. `edit reaction m_theor <value> <mass unit>`, `m_actual <value> <mass unit>`, `temperature <value> <unit>` and `time <value> <unit>` need a unit. `edit reaction yield_pct <value>` and `atom_economy <value>` take the unit `%` (typing `%` is also accepted). `edit reaction reagents` shows the current reagent lines, then re-prompts for the whole list (blank line to finish) and **replaces** it. All numeric fields are stored as `rxn_` values and appear in `history`. Confirmation: `Updated rxn_yield_pct: — -> 84.63 %`. |
| C175 | Typed reagent amounts. | A typed amount such as `4.10 cm^3` becomes a new value named `m_<ID or text>`, `V_<ID or text>` or `n_<ID or text>` according to its unit: mass (`g mg ug kg`), volume (`L mL uL dm^3 cm^3 m^3`) or amount of substance (`mol mmol umol nmol`). Any other unit is refused with that list shown. If the name already exists in the experiment, `create reaction` refuses and asks the owner to point at the existing value by name instead. |
| C176 | `find` matching. | The term is matched in the current project against: a compound ID (`C002`), a compound's exact `name`, a compound's exact `formula`, and plain-text reagent entries (all exact, case-sensitive). `find <term> all` searches every project's reactions; in that mode a compound ID is refused ("IDs are per project: search by name or formula"), because `C001` means a different compound in each project. Output rows carry the project name when `all` is used. No matches prints `No reactions found for 'term'.` (and the closest compound names, D27). |

**F4**

| ID | Topic | Proposed default |
|---|---|---|
| C177 | **The 12 shipped models.** `x` is the independent variable. | `linear`: `m * x + c`. `poly2`: `a * x^2 + b * x + c`. `poly3`: `a * x^3 + b * x^2 + c * x + d`. `exp`: `a * exp(b * x)`. `exp_decay`: `a * exp(-k * x)`. `exp_decay_offset`: `a * exp(-k * x) + c`. `power`: `a * x^b`. `log`: `a * ln(x) + b`. `michaelis_menten`: `Vmax * x / (Km + x)`. `hill`: `Vmax * x^n / (K^n + x^n)`. `dose_response`: `bottom + (top - bottom) / (1 + (EC50 / x)^h)` (a four-parameter logistic that **rises** from `bottom` to `top` as x increases when `h` is positive; for a falling curve the fit simply returns a negative `h`). `arrhenius`: `A * exp(-Ea / (8.314462618 * x))` (x in K, `Ea` in J/mol). Units: `m = y/x`, `c = y` (linear); `a = y/x^2`, `b = y/x`, `c = y` (poly2); `a = y/x^3`, `b = y/x^2`, `c = y/x`, `d = y` (poly3); `a = y`, `b = 1/x` (exp); `a = y`, `k = 1/x` (exp_decay); `a = y`, `k = 1/x`, `c = y` (exp_decay_offset); none for `power`, `hill`'s `n` and `dose_response`'s `h` (dimensionless); `a = y`, `b = y` (log); `Vmax = y`, `Km = x` (michaelis_menten); `Vmax = y`, `K = x` (hill); `bottom = y`, `top = y`, `EC50 = x` (dose_response). `r_squared = true` for `linear`, `poly2`, `poly3` only (C97). Each shipped entry gets a one-line `description`. |
| C178 | Starting guesses and direct solves. | **Direct least squares, no starting guess:** `linear`, `poly2`, `poly3` and `log` are linear in their parameters, so they are solved directly with NumPy. **`guess = "auto"` rules** for the others: `exp`, `exp_decay`, `exp_decay_offset`: if all y > 0, regress `ln y` on x for the rate and `a = exp(intercept)`; otherwise `a` = first y and rate = ±1 / (x range); `c` = last y, with `a` = first y minus last y, for the offset model. `power`: if x and y are all > 0, regress `ln y` on `ln x` (`b` = slope, `a = exp(intercept)`); otherwise `a = 1`, `b = 1`. `michaelis_menten`: `Vmax` = largest y, `Km` = median x. `hill`: `Vmax` = largest y, `K` = median x, `n = 1`. `dose_response`: `bottom` = smallest y, `top` = largest y, `EC50` = median x, `h = 1`. `arrhenius`: if x and y are all > 0, regress `ln y` on `1/x` (`Ea` = −slope × 8.314462618, `A = exp(intercept)`); otherwise the fit is refused with the reason. These rules apply to a shipped model **only while its `equation` still equals the shipped text**; if the owner edits it, Synthase falls back to `initial`, or to 1 for every parameter (C110). |
| C179 | Fit procedure and statistics. | CSV: comma-separated, first row is the header, UTF-8 with or without a byte-order mark. Columns are chosen by header name (a wrong name gets suggestions, D27). Rows where x or y is blank are skipped and counted in the output; a non-numeric cell is an error naming the row. Duplicate x values are allowed; NaN or infinite values are refused. The fit needs **more points than parameters** (n > p), or it refuses and says so. Non-linear fits use `scipy.optimize.curve_fit` with `method="lm"`, no bounds, no weights, `maxfev = 10000`. If it fails to converge, nothing is saved and the message suggests adding `initial` values. **Residual standard error** = sqrt(SSE / (n − p)), shown in y units. **R²** = 1 − SSE / SST with SST taken about the mean of y, shown only when the model's `r_squared` flag is true; if all y are equal, R² is shown as `—`. The data are read as floating-point numbers for the fit only; the record keeps the typed text (D25). With no active experiment, `fit` still works (x unit `s`, no experiment link). |
| C180 | Display notation for computed numbers (extends C103). | Four significant figures, trailing zeros kept (`1.990`, `0.05000`). Plain decimal when 0.0001 ≤ abs(v) < 1,000,000; otherwise scientific notation with two exponent digits (`5.206e-05`, `1.234e+07`). The readable equation is the model's equation with each parameter replaced by its value; a **negative value is wrapped in parentheses** (`y = 2.000 * x + (-1.200)`), and `^` is kept as `^`. The `Python:` line uses Python's shortest round-trip form of each coefficient, with `^` written `**`, `exp` → `np.exp`, `ln` → `np.log`, `log10` → `np.log10`, `sqrt` → `np.sqrt`. `exact` uses the same full-precision numbers in the readable line. The data range in `show fit` is printed exactly as typed in the data. |
| C181 | `predict`, `fetch` and `list fits` details. | If the model is undefined at the requested x (e.g. `ln` or a fractional power of x ≤ 0, division by zero) or the result is not finite, `predict` prints `Model <name> is undefined at x = <x>.` and no number. Otherwise it prints `y = <4 s.f.> <y unit>   (at x = <x> <x unit>)`. `fetch <A-ID> <item>` accepts each coefficient name, `r_squared` (or `rse`), and `n`, printed with the same 4 s.f. rule and the coefficient's unit; a wrong item gets suggestions listing the available ones (D27). `list fits` prints `ID  model  experiment  date  n`, one line per fit, most recent last. |
| C182 | The `A` record and `rerun`. | The record file is laid out as in F4 ("Record file"): file name `A001-<model with underscores as hyphens>.toml`, all numbers as text, the model copy and the data copy inside it. `rerun A001` refits from the stored data and stored model copy (never the CSV or the current `models.toml`), compares every coefficient and prints `Reproduced: largest relative difference in any coefficient X (limit 1e-9).` or `NOT reproduced: …` with the differences. It never changes or adds a record. If the original CSV still exists and its hash differs from the stored one, it adds a note saying so. |

**Shell and packaging**

| ID | Topic | Proposed default |
|---|---|---|
| C183 | Help, completion, history and errors. | One command table in the code (name, usage line, one-line help, example, argument types) drives `help`, `help <command>`, usage errors (D27), tab-completion and the command-shape checks, so they cannot drift apart. `help` groups commands by feature. Up-arrow history persists across sessions in `Documents\Synthase\.history` (plain text). The app never prints a Python traceback: an unexpected error prints `Internal error. Details are in Documents\Synthase\error.log` and the prompt carries on. |
| C184 | Python version. | Python 3.11 or newer, installed natively for ARM64 where an ARM64 build exists (the builder verifies the choice at build time; see Section 9.3). |

### 5.2 Resolved (binding)

#### Resolved by accepting defaults (D34)

The "Recommended default" column below is now the binding resolution (as revised where marked).

| ID | Feature | Question | Resolution |
|---|---|---|---|
| C80 | F1 | Compound IDs: auto-assigned (next free `C` number), with the chemical's name in a `name` field? Or does the owner choose the number? | Auto-assigned. Name stored in `name`. |
| C81 | F1 | Do projects also get a `Letter NNN` ID (e.g. `P001`), or keep being opened by name? | Keep projects opened by name. They are folders the owner browses in File Explorer, and there are few of them. |
| C82 | F1 | What happens after `999` (e.g. 1000 experiments in one project)? | The number grows to four digits (`E1000`); existing IDs never change. |
| C83 | F1 | Are IDs per project (two projects can each have a `C001`) or unique across all projects? | Per project, matching the per-project compound library (D14). `find … all` output shows the project name alongside the ID. |
| C84 | F1 | Is the ID of a deleted compound or experiment ever reused? | Never reused. |
| C95 | F4 | Command words. | `fit <model>`, `predict <A-ID> <number>`, `show fit <A-ID>`, `list fits`, `rerun <A-ID>`, `list models`, `help model <name>`. Coefficients via `fetch <A-ID> <coefficient>`. |
| C97 | F4 | When is R² "appropriate"? R² is well-defined for straight-line and polynomial fits, but misleading for curved models such as exponential or Michaelis–Menten. | Controlled by each model's `r_squared` flag in `models.toml`: `true` for `linear`, `poly2`, `poly3`. Other models show the residual standard error (typical size of the misfit, in y's units), with a one-line note explaining why there is no R². |
| C98 | F4 | Predicting outside the data range (extrapolation). | Allowed, but always prints a warning giving the data's x-range. Never refused. |
| C99 | F4 | Uncertainty on a prediction (95% interval on y at the chosen x). | **Revised default (D31, fewer arguments): drop from v1.** |
| C101 | F4 | Slope at a point (e.g. rate from a concentration–time fit). | **Revised default (D31): drop.** Differentiating the saved equation is something the owner can do by hand. |
| C103 | F4 | How computed numbers are displayed (D25 covers only typed values; a fitted coefficient has ~16 digits). | Display 4 s.f.; store full precision; `predict` always uses full precision. |
| C104 | F4 | Hand the equation to Claude, so its plot shows exactly Synthase's saved line. | `show fit A001` always prints two lines: the readable equation (4 s.f.), and a `Python:` line with full-precision coefficients, ready to paste into Claude. **Plus** `show fit A001 exact` prints the readable equation with every coefficient at full precision (D33). |
| C105 | F4 | Record letter and links. | `A` (analysis record), so it can cover future heavy-computation features too. Per project; linked to the experiment active when it was made (or none). |
| C106 | F4 | Are predictions saved? | **Revised default (D31): no `save` argument.** Printed and logged in history only. To keep one, the owner uses `add` as normal. |
| C107 | F4 | **"Assumed to be seconds unless specified otherwise in the experiment's details."** Which details? Not every x is time: Michaelis–Menten uses substrate concentration and Arrhenius uses temperature. | Add an optional `x_unit` field to each experiment's `[experiment]` details (default `s` if not set). `fit` uses it as the x unit and shows it; it can be changed for one experiment with `edit experiment x_unit K`. The fit record stores the x unit, so `predict` always echoes it back. |
| C108 | F4 | Where does `models.toml` live? | One global file, `Documents\Synthase\models.toml`, shared by all projects. Created with the 12 starting models on first run. |
| C109 | F4 | Required fields per model. | `equation`, `parameters` required. Optional: `description`, `units` (written with `x`/`y`, e.g. `"1/x"`; parameters without one are shown with no unit), `r_squared` (default `false`), `initial` (starting guesses). |
| C110 | F4 | Starting guesses for owner-added models. | Use `initial` numbers if given; otherwise start every parameter at 1. If the fit fails to converge, say so and suggest adding `initial` values. Built-in models use documented rules (`guess = "auto"`). |
| C111 | F4 | Adding models: commands, or hand-editing the file only? | Hand-edit only, to keep the command line uncluttered. `list models` and `help model <name>` read the file. |
| C112 | F4 | Can the owner edit or delete the 12 starting models? | Yes, the file is fully theirs. Old fits are unaffected because each fit stores its own copy of the equation. |

#### Resolved earlier

| ID | Question | Resolution | Decision |
|---|---|---|---|
| C1 | App: shell inside PowerShell, or separate window? | Interactive shell inside the PowerShell window. | D18 |
| C2 | One-shot commands from plain PowerShell? | No. | D15 |
| C3 | Prompt text. | `<Project>/<ExperimentID> >`; `<Project> >`; `>`. | D18 |
| C4 | Core command words. | As in F1's command table. | D18, D22 |
| C5 | Adding vs changing a value. | `add` creates; `edit` changes. | D11 |
| C6 | Value entry syntax. | `name value unit [+/- unc] [# note]`. | D18 |
| C7 | Unit spellings. | `mol/dm^3`, `mol dm^-3`, `M` accepted; shown as typed. | D18, D25 |
| C10 | Experiment IDs. | `E001`, `E002`… plus title; open by either. | D18, D26 |
| C11 | `create experiment` title / active. | Title inline or prompted; new experiment becomes active. | D18 |
| C12 | Timestamp format. | ISO 8601 with offset; shown `YYYY-MM-DD HH:MM:SS`. | D18 |
| C13 | Import file format. | CSV `name,value,unit,uncertainty,note`; values taken exactly as written. | D18, D25 |
| C14 | Projects location. | `Documents\Synthase\<Project name>\`, configurable. | D18 |
| C15 | Folder layout and TOML keys. | As in Section 3 (numbers stored as text). | D18, D25 |
| C16 | Hand-edits while closed. | Detect and log "external edit"; invalid file → refuse to load, print line number. | D18 |
| C20 | Deleting a value. | Logged, not erased; refused if a reaction record points at it. | D18, D22 |
| C22 | `add`/`edit` misuse. | `add` on existing → suggest `edit`; `edit` on missing → suggest `add` plus closest names. | D18, D27 |
| C28 | Compound commands. | `add compound`, `edit compound`, `list compounds`, `show compound`; hand-edits allowed. | D18 |
| C55 | Scope of "no calculators". | Applies to F1 as well. F1 is a pure databank. | D21, D22 |
| C56 | Check whether an equation balances? | No. | D21 |
| C57 | F3 command words. | `create reaction`, `edit reaction`, `show reaction`, `list reactions`, `find`, `delete reaction`. | D28 |
| C58 | F3 entry flow. | Walk-through; Enter skips; only equation required; one per experiment. | D28 |
| C59 | F3 equation format. | Free text, `->` (or `=`), stored as typed. | D28 |
| C60 | F3 reagent lines. | `<ID or text> <role> [amount] [equiv] [# note]`; amount is a value name or typed amount. | D28 |
| C61 | F3 field list. | Conditions, results and observations as listed in F3. | D28 |
| C62 | F3 value names. | `rxn_` prefix, reserved. | D28 |
| C63 | F3 results: typed or formula? | Typed only. | D22 |
| C64 | F3 `find` scope. | Current project; `find <term> all` for every project. | D28 |
| C65 | F3 prompt in `create experiment`? | No. | D28 |
| C66 | F3 unfilled fields. | Shown as `—`; count of blanks reported. | D28 |
| C67 | F3 units for yield / atom economy. | `%`. | D28 |
| C68 | What is `C-001`? | A placeholder compound ID; now written `C001` (D26). | D23, D26 |
| C69 | `fetch` matching. | Exact match required; suggestions on mismatch. | D23, D27 |
| C70 | Unit checking. | Check recognised unit (suggest on typo); store as typed; never convert. | D28 |
| C71 | Display rounding of typed values. | None — exactly as typed. | D25 |
| C72 | Compound fields. | `name`, `formula`, `molar_mass`, `density`, `purity`, `note`; all optional; stored as typed. | D28 |
| C73 | Built-in constants. | Dropped from F1. | D28 |
| C74 | Cross-experiment links. | Dropped; replaced by `fetch`. | D28 |
| C75 | `fetch` on experiments; `fetch <ID>` alone. | Yes to both. | D28 |
| C76 | Name characters. | Value names: any characters except spaces, case-sensitive. Data objects use `Letter NNN` IDs. | D26 |
| C77 | Custom compound fields. | Not in v1; use `note`. | D28 |
| C78 | `add compound` entry flow. | Prompts for each field; Enter skips. | D28 |
| C79 | Suggestion behaviour. | No y/n, never auto-run. Show the two closest matches; if none close, list everything of that kind; wrong command shape → usage line. | D27 |
| C96 | F4 models in v1. | Start with the 12: `linear`, `poly2`, `poly3`, `exp`, `exp_decay`, `exp_decay_offset`, `power`, `log`, `michaelis_menten`, `hill`, `dose_response`, `arrhenius`. Owner chooses the model; no automatic best-fit selection. All models live in an owner-editable `models.toml` (C108–C112). | D30 |
| C100 | F4 units in `predict`. | Never convert. Accept only a bare number, assumed to be in seconds unless the experiment's details say otherwise (exact mechanism: C107). | D32 |
| C102 | F4 inverse `solve`. | **No.** The owner can rearrange the equation by hand, and it would clutter the command line. | D31 |

### 5.3 Superseded (no longer apply; kept for traceability)

| ID | Was | Superseded by |
|---|---|---|
| C8 | ± shown on derived values | D22 (no derived values) |
| C9 | Flat 4 s.f. display | D25 (exact values) |
| C17 | Cross-experiment references in formulas | D22, C74. (Compound library part still stands.) |
| C18 | Name rules (identifier-only, for formulas) | C76, D26. Case-sensitivity still stands. |
| C19 | Formula syntax and functions | D22 |
| C21 | Derived values vs `add`/`edit` | D22 |
| C23 | 4 s.f. for uncertainties | D25 |
| C24 | Standard-form display rule | D25 |
| C25 | CSV export precision | D25 (exports are exact) |
| C26 | Molar mass computed from formula | D22, C72 |
| C27 | `aspirin.M` reference in formulas | D22; replaced by `fetch` |
| C29 | Hydrate parsing for molar mass | D22 |
| C30 | Built-in physical constants | D22, C73 |

### 5.4 Withdrawn and moved

- C31–C41 belonged to F2 (Live Word sync), which was cut.
- C42–C54 belonged to the calculator version of F3, which was replaced by the record-only version.
- C85–C94 belonged to the first version of F4 (a full fitting report with standard errors, Monte Carlo and fitted-curve CSVs), which the owner reshaped into saved, queryable fits.
- C113–C124 belonged to F5 (Sequence library), which was cut.
- C139–C150 belonged to F7 (Statistical tests), which was cut.
- C151–C163 belonged to F8 (Bench clock), which was cut.
- C125–C138 belonged to F6 (Mechanism simulation). They are not withdrawn: they moved with the idea to X2 (Section 6A) as proposed defaults, never confirmed.
- C164–C184 are the gap-filling defaults in 5.1.

Withdrawn and superseded IDs are not reused.

---

## 6. Cut ideas

Cut ideas are recorded here with the reason, so they are not re-proposed.

| Feature | Cut on | What it was | Why it was cut |
|---|---|---|---|
| F2 — Live Word sync | 2026-10-21 | User types `{{E002.yield_pct}}` placeholders in Word; Synthase fills them and keeps them updated via Word content controls. | Owner: not worth the trouble; typing placeholder strings is slower than fixing the occasional stale number by hand. **Do not propose any feature that requires typing special markup into Word.** |
| F3 (calculator version) — Reaction table | 2026-10-21 | Auto-balancing, moles, equivalents, limiting reagent, theoretical/% yield, atom economy. | Owner: rudimentary calculations they prefer to do by hand. Replaced by record-only F3. **Do not propose calculators for anything a scientific calculator can do.** |
| F1 calculation features | 2026-10-21 | `calc`, derived values, recalculation, uncertainty propagation, unit conversion, computed molar masses, 4 s.f. rounding. | Owner: F1 is a databank only (D22, D25). |
| F5 — Sequence library | 2026-10-21 | A store of DNA / RNA / protein sequences (`S` IDs), kept letter-perfect, with FASTA import and export. | Owner can't see when a stored sequence would be needed, even in CRISPR work. **Do not propose features whose main purpose is storing sequences.** |
| F7 — Statistical tests | 2026-10-21 | `test <name>`: t-tests, ANOVA with Tukey, Kruskal-Wallis, chi-squared and correlations, with exact p-values saved as `A` records. | Owner: overkill. **Keep new ideas light; do not propose general statistics packages.** |
| F8 — Bench clock | 2026-10-21 | `clock start` / `read`: readings stamped with the elapsed time at the bench and stored as a series. | Owner: pointless; a stopwatch and Excel are fine. **Do not propose features that only record data the owner can already capture easily elsewhere.** |

---

## 6A. Shiny ideas (parked: nice to have, not important)

Ideas that look good and might be fun, but are low priority. **Nothing here is to be built** unless the owner promotes it into Section 4. IDs are `X1`, `X2`… (spec labels only).

### X1 — Stochastic kinetics (Gillespie SSA) for small-molecule-count systems

**Status:** `PARKED` (2026-10-21). Owner: shiny, not that important.
**Origin:** the owner's idea. The owner has already built a standalone tool, `stochastix` (Gillespie Direct Method SSA; parallel Monte Carlo ensembles reporting mean, variance, SD and CV per species over time; JSON models; an interactive wizard). Only its README has been reviewed, not its code.

**Depends on X2:** it cannot be promoted before X2.

#### What it would be
A thin layer on X2. The same mechanism file (`mechanisms.toml`) gives the steps, and the same experiment values give the rate constants. Synthase would run an ensemble of stochastic trajectories and save the result as an `A` record with the seed stored. This would show what the X2 curve cannot: spread, noise, the chance of zero copies, or two different outcomes from the same start.

#### Why it is parked
- It only matters at tens to hundreds of molecules (about 1.7 nM per molecule in a 1 fL bacterial volume). At lab concentrations it reproduces the X2 curve more slowly: 1 uM enzyme in 1 mL is about 6x10^14 molecules.
- The owner already has a working tool for it, so integrating it mainly saves switching between tools.

#### If it is ever promoted
- Reuse X2's mechanism file, experiment inputs and `A` records. Whether Synthase imports `stochastix` as a dependency or copies its engine is undecided.
- Starting amounts would be molecule counts, plus a `volume` value in dm^3 to turn macroscopic rate constants into stochastic ones.
- X2's mechanism syntax would need to allow empty sides (`-> A`, `A ->`) for production and degradation. X2's deterministic simulation would gain this too.
- Results must not depend on how many CPU cores are used (e.g. seed each trajectory separately with NumPy's `SeedSequence.spawn`). The seed is always recorded.
- The SSA picks the next reaction **at random in proportion to each reaction's propensity**, not the most likely one, and draws a random waiting time. Do not implement "most likely next reaction".
- Possible later extra: an exact solution of the chemical master equation for very small systems (finite state projection), as a cross-check on the Monte Carlo.
- Do not absorb the `stochastix` roadmap (SBML parsing, promoter/RBS sweeps, an iGEM platform).

### X2 — Mechanism simulation: what-if kinetics for reaction systems

**Status:** `PARKED` (2026-10-21, D39). Formerly F6. Owner: shiny, not that important. **Do not build.**
**Phase(s) if promoted:** Interpretation, and planning before an experiment ("what should I expect to see?")
**Disciplines:** Chemistry (kinetics, reaction-system analysis), biochemistry (enzyme mechanisms and inhibition), mathematics (systems of differential equations)

The design below is complete and was reviewed with the owner, but the owner chose to park it. The "proposed defaults" at the end were never confirmed. If the owner promotes X2 into Section 4, re-confirm them first. X2 would reuse F1's experiment values, F4's `A` records and F4's `predict` / `rerun` commands, which is why it was parked rather than cut.

#### Why it passes the "can't do it by hand" test (D21)
Each species in a mechanism has its own rate equation, and the equations feed into each other. Only the simplest cases (a single first-order step, or A -> B -> C) have a formula you can solve by hand. Add a reversible step, a second-order step or an enzyme mechanism and no formula exists. The equations must be integrated numerically, in thousands of tiny steps, which is not possible on a scientific calculator.

#### Problem it would solve
- **Claude Science:** can write the integration code and plot it, but writes new code each time. The solver, tolerances, units and even the rate equations can differ between runs, and the simulation isn't kept anywhere, so "the simulation behind figure 3" cannot be reproduced.
- **Excel:** can approximate it with Euler's method, one row per time step. Accuracy depends on the step size, mechanisms with fast and slow steps together (stiff systems) blow up, and the sheet must be rebuilt for every new mechanism.

#### What it would do
1. Mechanisms are defined once, as elementary steps, in an editable `mechanisms.toml` (the same idea as `models.toml` in F4).
2. Rate constants and starting concentrations are stored as ordinary values in the experiment (F1), under the names the mechanism expects. Synthase reads them and never changes them.
3. `simulate <mechanism> <t_end>` solves the system from t = 0 to t_end and saves an analysis record (an `A` ID, linked to the active experiment). It prints every species' concentration at t_end.
4. `predict <A-ID> <t>` prints every species at time t (bare number, same rule as F4, D32).
5. `export sim <A-ID>` writes a CSV of all species against time, so the owner can plot it in Claude or Excel. Synthase does not plot (D1).
6. To explore a what-if, `edit` a rate constant and run `simulate` again. Each run is its own record, so old results never change, and `show sim` states exactly which inputs each one used.

#### Example session (the numbers were computed with the specified solver and double as a reference test case)
```text
Enzyme project/E021 > add k1 1.0e5 dm^3/mol/s # E + S -> ES
Enzyme project/E021 > add k_1 50 s^-1
Enzyme project/E021 > add k2 10 s^-1
Enzyme project/E021 > add E_0 1.0e-6 mol/dm^3
Enzyme project/E021 > add S_0 5.0e-3 mol/dm^3
Enzyme project/E021 > simulate michaelis_menten_full 600
Mechanism michaelis_menten_full:  E + S <-> ES (k1, k_1);  ES -> E + P (k2)
Inputs from E021: k1 = 1.0e5 dm^3/mol/s, k_1 = 50 s^-1, k2 = 10 s^-1,
                  E_0 = 1.0e-6 mol/dm^3, S_0 = 5.0e-3 mol/dm^3  (ES_0, P_0 not set: 0)
Solved 0 to 600 s (LSODA, rtol 1e-8, atol 1e-12).
At t = 600 s (mol/dm^3):  E = 5.727e-07   S = 4.476e-04   ES = 4.273e-07   P = 4.552e-03
Saved as A003 (linked to E021).

Enzyme project/E021 > predict A003 60
At t = 60 s (mol/dm^3):  E = 1.184e-07   S = 4.467e-03   ES = 8.816e-07   P = 5.324e-04

Enzyme project/E021 > export sim A003
Wrote exports\A003_sim.csv  (1001 time points, 5 columns)
```
(After `edit k2 20 s^-1`, running `simulate` again would save a new record, A004; A003 is unchanged.)

#### Proposed `mechanisms.toml` (two of the five starting mechanisms shown)
```toml
# Synthase mechanism registry. Add a mechanism by copying an entry and editing it.
# Rate law is always mass action: rate = k x (product of reactant concentrations).
# "<->" is reversible and needs both k_forward and k_reverse.

[michaelis_menten_full]
description = "Enzyme mechanism with no steady-state assumption"
species     = ["E", "S", "ES", "P"]
steps = [
  { equation = "E + S <-> ES", k_forward = "k1", k_reverse = "k_1" },
  { equation = "ES -> E + P",  k_forward = "k2" },
]

[consecutive_first_order]
description = "A -> B -> C"
species     = ["A", "B", "C"]
steps = [
  { equation = "A -> B", k_forward = "k1" },
  { equation = "B -> C", k_forward = "k2" },
]
```

#### Not in the first version
- Rate laws other than mass action (e.g. a written Michaelis–Menten expression); enzyme mechanisms are written as elementary steps.
- Temperature dependence of rate constants.
- **Fitting rate constants to measured time courses.** This is the natural follow-on and is heavy computation that the other tools do poorly, but it is a feature of its own.
- Steady-state or equilibrium solving, and plotting (D1).

#### Implementation notes (if promoted)
- Build the rate equations from the step list with NumPy; never `eval`. Validate that every species used in a step is declared and vice versa, and report problems with the line number in `mechanisms.toml`.
- Solver: `scipy.integrate.solve_ivp`, `method="LSODA"`, `rtol=1e-8`, `atol=1e-12`.
- Unit checking compares an entered unit with the expected unit by dimension and scale (e.g. via `pint`) purely to accept or refuse it; nothing is converted.
- `predict` and `export` re-solve from the stored inputs (`t_eval`), so no solution table is stored.
- **Reference test case:** k1 = 1.0e5 dm^3/mol/s, k_1 = 50 s^-1, k2 = 10 s^-1, E_0 = 1.0e-6, S_0 = 5.0e-3 mol/dm^3. At 60 s: E = 1.184e-07, S = 4.467e-03, ES = 8.816e-07, P = 5.324e-04. At 600 s: E = 5.727e-07, S = 4.476e-04, ES = 4.273e-07, P = 4.552e-03. These match to at least 4 s.f. (LSODA, SciPy 1.18.1), and E + ES = 1.000e-06 and S + ES + P = 5.000e-03 at every time. A second test: `consecutive_first_order` must match its closed-form solution to within solver tolerance.

#### Proposed defaults if promoted (C125–C138, never confirmed)

| ID | Question | Proposed default |
|---|---|---|
| C125 | Command words. | `simulate <mechanism> <t_end>`, `predict <A-ID> <t>` (shared with F4), `show sim <A-ID>`, `list sims`, `export sim <A-ID>`, `rerun <A-ID>` (shared with F4), `list mechanisms`, `help mechanism <name>`. `fetch <A-ID> <species>` gives that species' concentration at t_end; `fetch <A-ID> <input name>` gives an input that was used. |
| C126 | Starting mechanisms. | Five in the file on first run: `consecutive_first_order` (A -> B -> C), `reversible_first_order` (A <-> B), `michaelis_menten_full` (E + S <-> ES -> E + P), `competitive_inhibition` (the same plus E + I <-> EI), `autocatalysis` (A + B -> 2 B). |
| C127 | Where do mechanisms live? | One global file, `Documents\Synthase\mechanisms.toml`, created on first run and edited by hand (as C111). Each record stores a copy of the mechanism it used, so later edits never change old records (as C112). |
| C128 | Step syntax and rate law. | Each step has an `equation` with `->` or `<->`, whole-number coefficients (`2 A -> B`), and `k_forward` (plus `k_reverse` for `<->`) naming its rate constants. The rate law is always mass action: rate = k x product of reactant concentrations, each raised to its coefficient. Species names: letters, digits and underscore, starting with a letter; case-sensitive. |
| C129 | How do inputs get in? | Read by name from the **active experiment**: rate constants under the names written in the mechanism, starting concentrations as `<species>_0` (e.g. `E_0`). A missing `_0` means 0, and the output says so. A missing rate constant is an error listing every missing name with the closest matches (D27). Nothing is prompted for, and other experiments' values are not read (D31). |
| C130 | Units. | No conversion (D22, D32). Concentrations must be `mol/dm^3` (`M` and `mol dm^-3` also accepted). Rate constants must match the step order and the experiment's x unit: `1/x` for first order, `dm^3/mol/x` for second order (spelling-insensitive, e.g. `s^-1` = `1/s`). Any other unit, such as `mmol/dm^3`, or `min^-1` when x is `s`, is refused with the expected unit named. |
| C131 | Time. | `t_end` and `predict` times are bare numbers in the experiment's x unit (default `s`, C107). `t_end` must be greater than 0. `predict` accepts any t of 0 or more, including beyond the original `t_end`; it is a re-solve rather than an extrapolation, so there is no warning. |
| C132 | Solver settings. | `scipy.integrate.solve_ivp`, method `LSODA` (switches between stiff and non-stiff automatically), `rtol = 1e-8`, `atol = 1e-12`. Fixed in v1, not adjustable, and stored in each record. |
| C133 | `rerun` and reproducibility. | Re-solves from the stored inputs and prints `reproduced (largest relative difference X)`. Passes at 1e-9 relative or better. Identical on the same machine and installation; on a different machine, equal to within the solver tolerance (Section 2). |
| C134 | What `simulate` prints, and number format. | The mechanism, the inputs used (exactly as stored), the solver, then every species at t_end to 4 s.f. (C103), always in scientific notation (e.g. `5.727e-07`, `4.467e-03`), because concentrations span many orders of magnitude. Full precision is stored in the record. |
| C135 | Export CSV. | `exports\<A-ID>_sim.csv`: column `t`, then one column per species (mol/dm^3), 1001 evenly spaced times from 0 to t_end, full precision, with units in the header. A repeat export of the same record overwrites the file. |
| C136 | Automatic mass-balance check (confirming that conserved totals such as E + ES stay constant, as a sanity test)? | Not in v1 (D31); the solver tolerance already controls accuracy. Revisit if wanted. |
| C137 | Failure and sanity warnings. | If the solver fails, or any concentration drops below -1e-10 mol/dm^3 (a sign of numerical failure), print a clear warning and mark the record `unreliable`, rather than silently returning numbers. |
| C138 | What a record stores. | The mechanism copy; every input value exactly as stored (name, value, unit); `t_end`; the x unit; solver settings; Synthase, SciPy and NumPy versions; species concentrations at t_end at full precision; and the experiment link. The solution table is not stored, since `predict` and `export` re-solve. |

---

## 7. Decision log

| # | Date | Decision | Reason |
|---|---|---|---|
| D1 | 2026-10-21 | Synthase must not duplicate plotting, concept explanation, table viewing, or prose editing. | Claude, Excel and Word already do these better. |
| D2 | 2026-10-21 | All examples and docs are PowerShell/Windows-only; Windows ARM64 must be supported. | Owner's environment. |
| D3 | 2026-10-21 | Ideas are proposed one at a time and refined collaboratively before acceptance. | Owner's requested process. |
| D4 | 2026-10-21 | Synthase opens as an app; commands are typed without the `synthase` prefix. | Owner's instruction. |
| D5 | 2026-10-21 | Files must be human-readable. Format: **TOML** (via `tomlkit`). | Easier and safer to hand-edit than JSON (no comments, fussy commas) or YAML (indentation-sensitive, values silently change type). |
| D6 | 2026-10-21 | `create experiment` makes a date+timestamped experiment and asks: load values from a file, or key them in. | Owner's design. |
| D7 | 2026-10-21 | One Ledger per project; each project contains many experiments. | Owner's choice. |
| D8 | 2026-10-21 | `edit` prints a short message naming only the value(s) changed. | Owner's choice. |
| D9 | 2026-10-21 | Uncertainty is optional and only stored when explicitly given. | Owner's choice. |
| D10 | 2026-10-21 | Every feature carries an explicit list of clarifications to resolve before building. | Owner: the builder must not fill gaps by guessing. |
| D11 | 2026-10-21 | `add` creates a new value; `edit` changes an existing value. | Owner's choice. |
| D12 | — | *(number reserved; unused)* | — |
| D13 | 2026-10-21 | ~~Flat 4 s.f. display.~~ **Withdrawn by D25.** | — |
| D14 | 2026-10-21 | Project-wide compound library so repeated compounds are typed once. *(Cross-experiment formula references part superseded by D22.)* | Owner's choice. |
| D15 | 2026-10-21 | No one-shot mode: all commands run inside the app. | Owner's choice. |
| D16 | 2026-10-21 | Case-sensitive names. *(Identifier-only rule superseded by C76/D26.)* | Owner approved. |
| D17 | 2026-10-21 | ~~Formula syntax and function set.~~ **Superseded by D22.** | — |
| D18 | 2026-10-21 | Remaining F1 defaults accepted (first version of F1). | Owner: "defaults fine". |
| D19 | 2026-10-21 | **F2 (Live Word sync) CUT.** | Placeholder markup is more effort than fixing stale numbers by hand. |
| D20 | 2026-10-21 | **F3 is reaction records, not a calculator.** Optional fill-in fields (including % yield and atom economy); past reactions searchable; logging never obligatory. | Owner prefers to do rudimentary calculations by hand. |
| D21 | 2026-10-21 | **Two roles.** (1) Databank: store, retrieve, search; no calculations on stored values. (2) Computation only for what genuinely cannot be done by hand or on a scientific calculator. | Owner's clarification. |
| D22 | 2026-10-21 | **F1 re-opened as a pure databank.** Removed `calc`, derived values, recalculation, uncertainty propagation, unit conversion, computed molar masses. Added `fetch`. | Owner's clarification. |
| D23 | 2026-10-21 | `C-001` was a placeholder compound ID. `fetch` arguments must match stored names exactly. | Owner's answer (C68, C69). |
| D24 | 2026-10-21 | On a mismatched name or syntax error, Synthase suggests corrections. *(Exact behaviour refined by D27.)* | Owner's instruction. |
| D25 | 2026-10-21 | **No rounding of typed values.** Stored and shown exactly as typed. D13 withdrawn. | Owner's instruction. |
| D26 | 2026-10-21 | **Data IDs use `Letter NNN`** (e.g. `C003`, `E020`): `E` = experiment, `C` = compound. Value names inside experiments may use any characters except spaces. | Owner's convention (C76). |
| D27 | 2026-10-21 | **Suggestions, not prompts.** On a mismatch, show the two closest matches; if none are close, list everything of that kind. Never ask y/n, never run a corrected command. Wrong command shape → show its usage line. | Owner's instruction (C79). |
| D28 | 2026-10-21 | Defaults accepted for C57–C62, C64–C67, C70, C72–C75, C77, C78. **F3 ACCEPTED.** | Owner: "defaults are fine". |
| D29 | 2026-10-21 | **F4 reshaped into saved fits.** No full fitting reports or plots (Claude Science does those). Synthase fits a chosen equation to a table, gives R² where appropriate, saves the equation as a record, and returns y for a typed x. | Owner: fitting and plotting already work well in Claude; what's missing is a stored equation to query later. |
| D30 | 2026-10-21 | **Model registry file.** F4 starts with 12 models, stored in an owner-editable `models.toml`; new models are added by editing the file. | Owner wants to add models as they come across them. |
| D31 | 2026-10-21 | **Keep the command line uncluttered.** No `solve`; prefer fewer commands and fewer optional arguments. Anything the owner can do by hand (rearranging, differentiating) is left out. | Owner: too many arguments clutter the command line. |
| D32 | 2026-10-21 | `predict` accepts only a bare number, never a unit, and never converts. Assumed seconds unless the experiment's details say otherwise. | Owner's instruction (C100). |
| D33 | 2026-10-21 | Add `show fit <A-ID> exact`: readable equation with every coefficient at full precision. | Owner's request. |
| D34 | 2026-10-21 | Defaults accepted for C80–C84, C95, C97–C99, C101, C103–C112 (C107 explicitly approved). **F1 and F4 ACCEPTED.** F5 (Sequence library) proposed. | Owner: "defaults are fine". |
| D35 | 2026-10-21 | **F5 (Sequence library) CUT.** | Owner sees no scenario where the stored sequence itself would be needed. |
| D36 | 2026-10-21 | **Section 6A created for "shiny" ideas** (nice to have, not important; never built unless promoted). X1 (stochastic kinetics) parked there. | Owner's instruction. |
| D37 | 2026-10-21 | **F7 (Statistical tests) CUT.** | Owner: overkill. |
| D38 | 2026-10-21 | **F8 (Bench clock) CUT.** | Owner: pointless. |
| D39 | 2026-10-21 | **F6 (Mechanism simulation) parked as X2** in Section 6A, with its defaults (C125–C138) kept as unconfirmed proposals. **Feature brainstorming stopped and the spec was wrapped up** (consistency pass, cut-feature stubs removed, resolved items separated from pending ones, Section 9 hand-off notes added). | Owner chose "Wrap up the spec" and "Park it as a shiny idea" after four ideas in a row were rejected. |
| D40 | 2026-10-21 | **Gap-filling defaults C164–C184 added** (Section 5.1) for details a builder would otherwise guess: `edit` semantics, deletion policy, ID counters, command parsing, units, export, history log, file locations, F3 edit details, the 12 model equations, starting guesses, fit statistics, display notation, the `A` record layout, shell behaviour. Awaiting the owner's confirmation. | Owner's rule (D10): the builder must not fill gaps by guessing. |

---

## 8. Conversation log (summary)

- **2026-10-21 — Session start.** Product brief, companion-tool constraints and environment captured. F1 (The Ledger) proposed.
- **2026-10-21 — F1 refined (rounds 1–2).** App-style prompt, Project → Experiment → Value hierarchy, `create experiment` with file-or-manual entry, TOML, `add`/`edit`, compound library. Clarifications register created at the owner's request.
- **2026-10-21 — F1 first accepted.** Owner accepted defaults. F2 (Live Word sync) proposed.
- **2026-10-21 — F2 cut.** Placeholder typing not worth it. F3 (Reaction table) proposed.
- **2026-10-21 — F3 reshaped.** Calculations too rudimentary; F3 became optional, record-only reaction records with fill-in fields and lookup.
- **2026-10-21 — Scope clarified; F1 re-opened.** "No calculators" means nothing a scientific calculator can do. F1 is just a databank. Synthase computes only what can't be done by hand.
- **2026-10-21 — F1 databank details.** `fetch` with exact names; suggestions on mismatch; no rounding.
- **2026-10-21 — IDs and suggestions settled; F3 accepted; F4 proposed.** `Letter NNN` data IDs (`C003`, `E020`); suggestions show two closest matches with no y/n; `fetch` works on experiments too. All remaining small defaults accepted, so F3 is accepted. Raised C80–C84 (ID details). F4 (Model fitting) proposed with C85–C94.
- **2026-10-21 — F4 reshaped.** Owner: Claude already fits and plots well, but a saved best-fit equation that can be queried later (e.g. y at t = 10800 s) would be useful. F4 became "saved fits". C85–C94 withdrawn; C95–C106 raised. C80–C84 (F1 ID details) still awaiting an answer.
- **2026-10-21 — F4 refined.** Resolved C96 (12 models in an editable `models.toml`), C100 (bare numbers only, no units), C102 (no `solve`). New principle D31: keep the command line uncluttered, so defaults for C99, C101, C104, C106 revised to remove optional arguments. Owner asked what the `python` argument in C104 does. Raised C107–C112.
- **2026-10-21 — F1 and F4 accepted; F5 proposed.** Owner added `show fit <ID> exact`, approved C107 and accepted all remaining defaults. F5 (Sequence library, `S` IDs) proposed with C113–C124 to start biology / bioinformatics coverage.
- **2026-10-21 — F5 cut; F6 proposed.** Owner questioned whether stored sequences would ever be needed, even for CRISPR work, and cut F5 entirely (C113–C124 withdrawn). F6 (Mechanism simulation) proposed with C125–C138. Section 2's determinism wording was tightened: identical on the same machine, equal to within 1e-9 relative across machines.
- **2026-10-21 — Stochastic kinetics parked; F7 proposed.** Before replying to F6, the owner suggested stochastic kinetics (Gillespie SSA) and shared the README of their existing tool. Judged valuable only for small molecule counts, so it was parked as X1 in the new Section 6A. F6 remains `PROPOSED` with C125-C138 still awaiting the owner's answer. F7 (Statistical tests) proposed with C139-C150.
- **2026-10-21 — F7 cut; F8 proposed.** Owner found F7 hard to follow when first explained in technical terms, then judged it overkill (C139–C150 withdrawn). F8 (Bench clock) proposed with C151–C163. F6 remains `PROPOSED` with C125–C138 still awaiting the owner's answer.
- **2026-10-21 — F8 cut.** Owner: pointless. Claude noted it was running short of ideas that clearly beat Excel and Claude, and asked the owner for direction rather than guessing again, and for an answer on F6's defaults (C125–C138).
- **2026-10-21 — Wrap-up.** After four rejected ideas in a row, the owner chose to wrap up the spec rather than keep brainstorming, and to park F6 as a shiny idea (X2; C125–C138 kept there as unconfirmed defaults). The spec was rewritten as a clean builder document: cut-feature stubs removed from Section 4, the F4 command table put in its place, the register split into pending (5.1) and resolved (5.2), gap-filling defaults C164–C184 added (D39, D40), and Section 9 added. Two defects were found and fixed: X2's number-format rule contradicted its own example (species concentrations are now always in scientific notation), and F4's example numbers were invented (they are now real results, with two reference tests).

---

## 9. Hand-off notes for the builder

### 9.1 What to build
F1 (Ledger), F3 (Reaction records) and F4 (Saved fits), plus the global rules in Sections 1–3. Nothing from Section 6 or 6A. Everything that is not a command or a rule in this document is out of scope for v1.

### 9.2 Build order
1. **Shell skeleton.** Package layout, entry point, the single command table (C183), REPL with history and tab-completion, `help`, the suggestion engine (D27, `difflib`), usage errors, the "no traceback" wrapper. Tests first for suggestions, using the examples in Section 3.
2. **Storage layer.** First-run folder creation (C172), `tomlkit` read/write with comments preserved, numbers as text, atomic writes, ID counters (C167), `history.jsonl` with hashes and external-edit detection (C171), project lock (C173).
3. **F1.** Projects, experiments, values, compounds, `fetch`, `export`, CSV import, unit check.
4. **F3.** Reaction records and `find`.
5. **F4.** `models.toml` and its safe parser, `fit`, `predict`, `show fit`, `rerun`, `list`, `fetch` on `A` IDs. Reproduce Reference tests 1–3.

Each stage ends with its tests passing before the next begins.

### 9.3 Dependencies and Windows ARM64
Planned dependencies: `prompt_toolkit`, `tomlkit`, `numpy`, `scipy`, and optionally `pint` (unit lookup only); `pytest` for tests. The owner's machine is a Windows ARM64 Surface Pro, so **verify every wheel before writing code that depends on it** (Section 2). In PowerShell:

```powershell
PS> python -c "import platform; print(platform.machine())"      # ARM64 means a native ARM64 Python
PS> python -m venv .venv
PS> .\.venv\Scripts\Activate.ps1
PS> python -m pip install --upgrade pip
PS> python -m pip install prompt_toolkit tomlkit numpy scipy pytest
PS> python -c "import numpy, scipy; print(numpy.__version__, scipy.__version__)"
```

If `Activate.ps1` is blocked by the execution policy, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once. If NumPy or SciPy has no ARM64 wheel, report it to the owner and use the options in Section 2 rather than choosing silently.

### 9.4 Packaging and running
A `pyproject.toml` with a console entry point named `synthase`. Installing into the active environment with `python -m pip install -e .` makes typing `synthase` in PowerShell launch the app (D4). Write every instruction for PowerShell only (D2).

### 9.5 Tests
Use `pytest`, with every test pointed at a temporary folder through `SYNTHASE_HOME` (C172). At minimum:
- **Exactness:** `2.100` is stored, shown, exported and re-imported as `2.100`; a trailing-zero value survives a history round trip.
- **Suggestions:** every example in Section 3 produces exactly the stated output; two closest matches; the "list everything" and "usage" cases.
- **IDs:** next-free, per-project, never reused after deletion of a file, four digits after 999.
- **F1:** `add`/`edit` misuse, `edit` clearing omitted fields (C164), unit typo refused, `delete` refused when an F3 reaction points at the value, CSV import, `export` round trip.
- **F3:** reaction walk-through, `rxn_` values appear in `fetch`, `find` by ID, name, formula and plain text, `find … all`.
- **F4:** Reference tests 1–3; `models.toml` with a bad entry still starts and reports the line number; the safe parser rejects `__import__('os')`, attribute access and unknown names; editing a model never changes an old fit; `predict` extrapolation warning and undefined-x error; `show fit` and `exact` formatting (C180).
- **Robustness:** invalid TOML refuses to load with a line number; an external edit is logged; Ctrl+C in a walk-through saves nothing; a second instance refuses on the lock.

### 9.6 Rules to keep in mind throughout
No plotting, no calculations on stored values, no unit conversion, no rounding of typed values, no y/n prompts, no auto-corrected commands (D1, D21, D22, D25, D27, D31, D32). Everything is ASCII-safe on input (Section 2). When in doubt, ask the owner.
