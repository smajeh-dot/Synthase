# 0014: The compound register and `syn compound add`

## Context
The compound register is the first real command (M1, decision 0012). #32 builds its storage and `syn compound add`. Showing, editing, the extra fields and batches follow in #33 to #36. The issue left open where the register is saved, where the atomic weights for the molar mass come from, the prompt wording, and what happens with duplicate labels, wrong answers and invalid SMILES.

The owner chose all the triage defaults below for #32 (2026-10-17).

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
- **Wording:** after adding, `syn compound add` prints `Added SYN-001: <label>`, each filled field, and `Add more details later with "syn compound edit SYN-001".` That command arrives in #34.

## Consequences
- The register is a single file, so backing up or moving the workspace takes it along.
- SQLite files can't be read in a text editor. `syn compound show` and `list` (#33) are the way to read the register.
- Molar masses follow the atomic weights of the installed RDKit version, which may change slightly between versions.
- The tests read the register file directly with `sqlite3` until #33 adds functions for reading it.
