# 0024: Reading and saving data files safely

## Context
Decision 0023 put each project's data in a `data\` folder inside the folder Synthase is started in, one TOML file per kind. The spec wants files that survive a crash (C173), keep the owner's hand-edits and comments (D5), and keep typed numbers exactly as typed (D25). The owner may run Synthase inside a OneDrive folder, where OneDrive can hold a file for a moment while it uploads. The owner chose all the triage defaults for #98 on 2026-10-21.

## Decision
- **The project folder** is the folder Synthase is started in. `SYNTHASE_HOME`, if set, replaces it; it exists for tests and is not advertised.
- **A folder is a project only when `data\synthase.toml` exists.** A `data\` folder without it is reported as not Synthase's. Checking creates nothing.
- **TOML is read and written with `tomlkit`**, pinned to exactly `0.15.2`. It is pure Python (`py3-none-any`), so it installs on ARM64 and x64 alike. Comments and layout survive a save.
- **Typed numbers are stored as text.** A save that contains a TOML number with a decimal point is refused as a programming error, so nothing can be rounded by accident. Whole numbers (such as ID counters) are allowed.
- **Every save goes to a temporary file in the same folder** (`.experiments.toml.tmp`), which then replaces the old file in one step (`os.replace`). A crash leaves either the old file or the new one, never half of one.
- **A held file is retried** 5 times, 0.2 s apart (about a second). Then the save gives up, removes the temporary file, leaves the old file as it was and says: `Couldn't save data\experiments.toml: another program is using it. Nothing was changed. Close that program, then try again.`
- **A broken file is refused**, naming the line: `data\experiments.toml has a mistake on line 3, so Synthase won't load it. Fix it in Notepad, then try again.` A file that isn't UTF-8 is treated the same way. A byte-order mark, which Notepad may add, is accepted.
- **A missing file reads as empty.** Noticing that a file has vanished is the history log's job (#99).

## Consequences
- Lines Synthase adds to a file use plain line feeds, even where the owner's own lines use Windows line endings. Notepad shows both correctly.
- `synthase` now has its first dependency, so the setup script installs `tomlkit` with it.
- Creating `data\` and `synthase.toml` is left to `project create` (#102).
