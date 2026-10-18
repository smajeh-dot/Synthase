# 0014: The compound register, `syn compound add`, `show` and `list`

## Context
The compound register is the first real command (M1, decision 0012). #32 builds its storage and the shared code that adds a compound. The `syn compound add` command that asks the questions is #37, split from #32 to keep each PR under the 400-line limit. Showing, editing, the extra fields and batches follow in #33 to #36. The issue left open where the register is saved, where the atomic weights for the molar mass come from, the prompt wording, and what happens with duplicate labels, wrong answers and invalid SMILES.

The owner chose all the triage defaults below for #32 (2026-10-17). The prompt and flag rules below are built in #37.

## Decision
- **Storage:** one SQLite file, `compounds.sqlite`, in the workspace next to `config.toml`. SQLite is built into Python, so there is no new dependency. The file is created the first time a compound is added.
- **Tables:** `compounds`, `batches`, `spectra` and `changes` (the change log) are all created at once. The schema version is kept in SQLite's `user_version`, starting at 1, so a later version of Synthase can upgrade the file. A file with a newer version than Synthase knows is refused with "update Synthase". #35 adds the characterisation, handling and safety columns as an upgrade to version 2. #36 may change the `batches` and `spectra` columns before anything is saved in them.
- **IDs:** `SYN-` and the row number, zero-padded to three digits (`SYN-001`). SQLite's `AUTOINCREMENT` makes sure a number is never used twice, even if a row were removed by hand. After `SYN-999` comes `SYN-1000`.
- **Shared command layer:** `synthase/compounds.py` does the work and raises `CompoundError` with a plain-language message. It never prints or asks anything. `synthase/cli.py` asks the questions and prints the results. The M2 app will call the same functions.
- **One quick write per command:** each command opens the file, writes everything in one transaction and closes it again. That reduces the chance of OneDrive syncing a half-written file. `/backup` (M5) is the proper safety net.
- **Molar mass uses RDKit's built-in standard atomic weights.** This is an exception to the rule that every scientific constant lives in the config: copying 118 atomic weights into the config would add nothing that can be checked better there. The formula comes from RDKit too. The full value is saved and shown to 3 s.f. (`CCO` gives C2H6O, 46.1 g/mol).
- **SMILES:** saved exactly as typed. A SMILES RDKit can't read is refused, and so is one with a space in it, because RDKit would silently ignore everything after the space. There is no check for the same structure entered twice under different labels.
- **Labels:** required, and unique when capitals and surrounding spaces are ignored. A repeat is refused: `"Test compound A" is already SYN-001. Choose another label.`
- **Class and status:** fixed lists from the roadmap. Capitals, hyphens and underscores are ignored, so `schiff-base` gives "Schiff base". Status defaults to planned.
- **Wrong answers:** guided prompts explain and ask again. Flags fail with the message and exit code 1, and nothing is saved.
- **Prompts and flags:** `syn compound add` with no flags asks for each field, and Enter skips any question except the label. With any flag it asks nothing, and `--label` is required. Running out of input (for example a closed pipe) cancels with "Nothing was added."
- **Change log:** adding a compound logs one row for each field filled in, with the date and time, an empty old value and the new value. Edits in #34 use the same table.
- **Details settled for #37** (the owner chose the triage defaults, 2026-10-17):
  - A repeated label is caught straight after it is typed, before the other questions.
  - A wrong answer in the prompts prints the message on its own line, then asks the same question again.
  - Ctrl+C partway through is treated like running out of input: `Nothing was added.`, exit code 1.
  - Flags without `--label` fail with: `Give the label with --label, or run "syn compound add" with no flags to be asked for each field.`
  - `syn compound` on its own shows the `compound` help, as a bare `syn` does.
  - Help text: `syn --help` lists `compound` as "keep track of the project's compounds, from idea to tested". `syn compound add --help` says: "Add a compound to the register. With no options, Synthase asks for each detail; press Enter to skip any but the label. With options, it asks nothing."
- **Details settled for #33** (the owner chose the triage defaults, 2026-10-18). The owner noted that the app in M2 gets its own interface, so this plain command-line look is not designed further now.
  - `syn compound show <ID>` prints the same field lines as `add`, leaving out blank fields, then a "Still missing:" list: `no class yet`, `no SMILES yet, so no formula or molar mass`, `no notes yet`. With nothing blank it prints `Nothing missing.` The #35 fields join the list when they arrive.
  - An ID can be typed as `SYN-001`, `syn-1` or `1`. Anything else gives `"abc" isn't a compound ID. IDs look like SYN-001.` An unknown ID gives `There's no compound SYN-042 in the register. Run "syn compound list" to see every ID.` Both exit with code 1.
  - `syn compound list` prints aligned columns (ID, Label, Class, Status, Formula, Molar mass (g/mol)) in ID order, with `-` in blank cells and labels never cut short. A count follows: `2 compounds.`, or `1 of 3 compounds (status: planned).` when filtered.
  - `--status` and `--class` take one value each, in the same forgiving forms as `add`. Together, a compound must match both. A value not on the list gives the same message as `add` and exit code 1.
  - An empty register prints `The register is empty. Add a compound with "syn compound add".` A filter that matches nothing prints `No compounds match (status: tested).` Both exit with code 0, and nothing is saved as CSV.
  - `--csv <file>` saves the same columns and values as the table, molar mass to 3 s.f., with blank cells left empty. The file is UTF-8 with a byte-order mark (`utf-8-sig`), so Excel on Windows shows every letter correctly. The path is taken as typed, relative to the current folder. (Replaced by decision 0015: a file name now goes in the folder set under `[folders]` in `config.toml`, or the workspace `results\` folder.) An existing file is replaced only after a yes to `<file> already exists. Replace it? [y/N]`. A file that can't be written, for example because Excel has it open, gives a plain message and exit code 1.
  - Reading never creates the register: `show` and `list` open it read-only, and only if it exists.
- **Wording:** after adding, `syn compound add` prints `Added SYN-001: <label>`, each filled field, and `Add more details later with "syn compound edit SYN-001".` That command arrives in #34.

## Consequences
- The register is a single file, so backing up or moving the workspace takes it along.
- SQLite files can't be read in a text editor. `syn compound show` and `list` (#33) are the way to read the register.
- Molar masses follow the atomic weights of the installed RDKit version, which may change slightly between versions.
- The command-line tests read the register through `list_compounds` (#33). The register tests still read the file with `sqlite3`, because they check the tables and the change log themselves.
