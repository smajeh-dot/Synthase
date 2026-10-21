# 0023: The command set and the project folder

## Context
The spec's F1 command table mixes verb-first commands of one, two and three words (`create project`, `add`, `add compound`, `list compounds`, `fetch`, `export --csv`). While triaging #97, the owner judged it messy and redesigned it set by set (2026-10-21). In the same conversation the owner described how Synthase should live on the laptop: run `synthase` in any folder and it works in a `data\` folder there, like a tent, instead of one central `Documents\Synthase\` folder holding many projects (spec Section 3, C172).

## Decision
**Commands are noun first.** The first word names the thing, the second says what to do with it. This replaces the spec's F1 command table, `help` and `exit` aside.

| Usage line | One-line help | Example |
|---|---|---|
| `project create` | Set up a Synthase project in this folder. | `project create` |
| `project show` | Show this project's name, folder and contents. | `project show` |
| `project edit` | Rename this project. | `project edit` |
| `exp create` | Create an experiment and open it. | `exp create` |
| `exp open <ID or title>` | Open an experiment. | `exp open E002` |
| `exp show [ID] [value name]` | Show the open experiment, another one, or one value from it. | `exp show E002 m_crude` |
| `exp show all` | List every experiment. | `exp show all` |
| `exp edit` | Change the open experiment's title or x unit. | `exp edit` |
| `exp export <csv or json>` | Write the open experiment to the exports folder. | `exp export csv` |
| `value add <name> <value> <unit> [+/- unc] [# note]` | Store a new value in the open experiment. | `value add m_crude 2.211 g +/- 0.001 # Balance B2` |
| `value edit <name> <value> <unit> [+/- unc] [# note]` | Replace a value; anything not retyped is cleared. | `value edit m_crude 2.215 g` |
| `value delete <name>` | Delete a value (its history is kept). | `value delete m_crude` |
| `value show <name>` | Show one value with its uncertainty and note. | `value show m_crude` |
| `value history <name>` | Every version of a value, with times. | `value history m_crude` |
| `compound create` | Add a compound to the library. | `compound create` |
| `compound show <ID> [field]` | Show a compound, or one of its fields. | `compound show C001 molar_mass` |
| `compound show all` | List the library. | `compound show all` |
| `compound edit <ID>` | Change a compound's fields. | `compound edit C001` |
| `help [command]` | List the commands, or every form of one. | `help exp` |
| `exit` | Leave Synthase (or press Ctrl+D). | `exit` |

How they behave, as agreed set by set:
- **Projects.** A project has only a name. `project create` asks `Name:`; `project edit` renames the project. `project show` prints the name, the date created, the folder and how many experiments and compounds it holds.
- **Experiments.** `exp create` asks for the title, then the spec's "load values from a file, or enter them manually" question. `exp show` prints the ID, title, date created and x unit, then the table of values; it replaces the spec's bare `show`. `exp show all` prints one line per experiment: ID, title, date created. `exp edit` asks for the title and the x unit in turn, Enter keeping each; the file keeps its original title, so the ID stays the reliable handle.
- **Values belong to one experiment.** Every `value` command works on the open experiment only. The same name in two experiments is two separate values that never affect each other. With no experiment open, a `value` command prints `No experiment is open.` `value add` with nothing after it takes one value per line until a blank line. `value edit` replaces the whole entry (spec C164); the old entry stays in `value history`.
- **Compounds** are one library per project. `compound create` asks for the spec's fields in turn (name, formula, molar mass, density, purity, note), Enter skipping each, and takes the next free C ID. `compound edit <ID>` shows each field's current value: Enter keeps it and `-` clears it. `compound show all` prints ID, name and formula. There is no `compound delete`, as in the spec.
- **`fetch` is folded into `show`.** `exp show E002 m_crude` and `compound show C001 molar_mass` print only the value and unit (`2.2110 g`), so it pastes cleanly into Word. `exp show <ID>` shows an experiment without opening it.
- **Export.** `exp export csv` and `exp export json` write the open experiment to `exports\E002.csv` or `.json` in the project folder, next to `data\`. A repeat export overwrites the file and prints the path. The CSV has the columns the file import reads. No command uses dashes.
- **`help`** groups the commands as Project, Experiments, Values, Compounds and General. `help <command>` takes the first word only (`help exp`) and prints every form of it, each with its usage line, help and example.

**Messages.**
- A mistyped command word: `Unknown command 'epx'. Did you mean: exp, exit?` A mistyped second word: `Unknown command 'exp shwo'. Did you mean: exp show, exp open?` When nothing is close, every command is listed: `Unknown command 'xyz'. Commands: compound, exit, exp, help, project, value`.
- A mistyped ID, field or value name keeps the spec's wording: `Unknown field 'molarmass' for C001. Closest: molar_mass, formula`, or the full list when nothing is close.
- A missing or extra part prints `Usage: …`, one line for each form of the command typed.
- `No Synthase project here. Type 'project create' to start one.`

**"Close" (D27).** Suggestions use Python's `difflib` similarity score. If any candidate scores at least 0.6, the two highest-scoring candidates are shown, even if the second scores less; equal scores keep the list's order. If none reaches 0.6, everything of that kind is listed. Plain `difflib.get_close_matches` would show only `molar_mass` for `molarmass` and put `C011` before `C001`, so it can't reproduce the spec's own examples.

**One folder is one project (the tent).**
- `synthase` works in the folder it is run from. Its data lives in `data\` there: `synthase.toml` (the project name and ID counters), `experiments.toml` (every experiment and its values), `compounds.toml` (the compound library) and `history.jsonl` (every change). The up-arrow history, the error log and the lock file go in `data\` too.
- The tent holds data only. Synthase and its libraries are installed once by `setup.ps1`.
- Running `synthase` in a folder without a project creates nothing: it says `No Synthase project here. Type 'project create' to start one.` Only the current folder counts; Synthase never looks in parent folders.
- A `data\` folder counts only if it holds `data\synthase.toml`. `project create` refuses to write into a `data\` folder that lacks it.
- Switching projects means running `synthase` in another folder, so there is no `project open` or list of projects. `Documents\Synthase\` and `settings.toml` are dropped. `SYNTHASE_HOME` stays, only so tests can point at a temporary folder.

## Consequences
- `docs/spec.md` lists this record among the owner's later decisions. Where the spec's F1 command table, Section 3 folder layout, Section 3 examples, C166 (no renaming), C168 (rest-of-line commands), C170 (export paths) and C172 (file locations) disagree with it, this record wins.
- The spec's Section 3 suggestion examples are tested through `compound show` instead of `fetch`, with the same messages.
- The only command that takes the rest of the line is `exp open`, because a title can contain spaces.
- Value names can't clash with command words, because every value command starts with `value`. A value may be called `compound` or `all`.
- One file per kind means a broken hand-edit to `experiments.toml` blocks every experiment until it is fixed; Synthase still refuses to load it and names the line.
- Later issues in #92's build plan were written for the spec's commands and folder. Each is brought in line with this record when it is picked up; #98 (the Synthase folder) changes most.
- Where F3 and F4 commands (`create reaction`, `fit`, `predict`) go is decided when those features are built, and `models.toml`'s home with F4.
