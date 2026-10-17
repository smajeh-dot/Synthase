# 0009: The workspace and `syn init`

## Context
All lab data, results, notes and the real config live in a local workspace, never in this repo (#11). `syn init` creates that workspace, and later commands need to find it again. The issue left four things open: where the workspace's location is kept, what "Documents" means on a laptop whose Documents folder may be synced to OneDrive, what counts as "inside the repo", and what overwriting an existing workspace does. It also needed the command's wording.

The owner chose all the triage defaults below for #11 (2026-10-17).

## Decision
- **Layout:** `raw\`, `maps\`, `results\`, `notebook\` and `config.toml`, a copy of the template from decision 0008.
- **Default location:** `Synthase-data` in the user's Documents folder. Synthase asks Windows where Documents really is (the "known folder" lookup), so it follows OneDrive when OneDrive has moved Documents. If that lookup fails, or on a system other than Windows, it uses `Documents` in the home folder. Built-in Python only (`ctypes`), no new dependency.
- **Remembering the workspace:** its absolute path is written as one line to `%APPDATA%\Synthase\workspace.txt`, the user's own app-settings folder. That is outside both the repo and the workspace. Running `syn init` again replaces the line. Where `APPDATA` isn't set (not Windows), the file is `~/.config/synthase/workspace.txt`. Later commands read it with `current_workspace()`, which explains what to do if there is no workspace yet or it has moved.
- **Refusing the code folder:** `syn init` refuses any path inside the folder Synthase's code is in. That is the checkout holding Synthase's `pyproject.toml` (which also covers its `.venv`), or the installed package folder when there is no checkout. The message:
  `Synthase can't create the workspace there: <path> is inside Synthase's own code folder (<folder>). The workspace holds your lab data, results and notes. Keeping it outside the code folder means none of it can be uploaded to GitHub by mistake. Choose another folder, or run "syn init" with no path to use Documents\Synthase-data.`
- **An existing workspace:** a folder that already has a `config.toml` counts as an existing workspace. `syn init` asks:
  `A workspace already exists at <path>. Replace its config.toml with a fresh copy of the template? Any values you have checked will be reset (the old file is kept as config.toml.bak-…). Type yes to replace it [no]:`
  - **No** is the default. Pressing Enter, typing anything other than `yes` or `y`, or having no input at all counts as no. The config is kept as it is, and the workspace is remembered. This is how a workspace is found again after reinstalling Synthase.
  - **Yes** first saves the old file as `config.toml.bak-YYYYMMDD-HHMMSS` next to it, then copies in a fresh template.
  - Either way, the four data folders and everything in them are never changed or deleted. Any that are missing are created.
- **Wording:** the help text says the default location and that a Documents folder synced to OneDrive backs the workspace up automatically. After creating the workspace, `syn init` lists each folder with one line on what goes in it, then says: `Next: open config.toml and check each value against the literature.`

## Consequences
- Tests point `APPDATA` and the Documents folder at a temporary folder, so they never touch the real ones.
- The Windows known-folder lookup can only run on Windows, so only Windows CI tests it.
- Moving the workspace by hand breaks the saved path. Running `syn init <new path>` fixes it without touching the files or the config.
- A workspace inside another git repository is not refused. Only Synthase's own code folder is.
