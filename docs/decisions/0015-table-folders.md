# 0015: The folder each kind of table is saved to

## Context
`syn compound list --csv <file>` saved the file relative to the current folder (decision 0014). Run from inside the Synthase folder, that put a results table in the code folder, one `git add` away from GitHub (#41). The owner wants to choose, in the workspace `config.toml`, the folder each kind of table is saved to, with one setting per area rather than one folder for every CSV file.

The issue left open how a folder setting fits a config built for scientific values (decision 0008), whether a full path given to `--csv` still wins, whether a missing folder is created, and whether `syn doctor` checks the folders. The owner chose all the triage defaults below for #41 (2026-10-18).

## Decision
- **A `[folders]` table in `config.toml`,** one line per area, starting with `compounds = ""`. These are plain text. Folders are not scientific values, so they have none of the `name`, `value`, `unit`, `source` and `verified` fields from decision 0008.
  - Blank (`""`) means not set. The template leaves every setting blank, and never holds a real path: a real folder path can hold personal information, so it lives only in the owner's workspace `config.toml`.
  - A path without a drive letter counts from the workspace folder.
  - Only known names are allowed, so a typo such as `compunds` is an error, as it is for scientific entries. A setting that isn't text in quotes is an error too.
  - A workspace `config.toml` made before this change has no `[folders]` table. It still loads, and every setting counts as not set until the owner copies the lines across from the template.
  - Windows paths go in single quotes (`'D:\Lab\Compound tables'`), which keep backslashes as they are. A folder name with an apostrophe needs double quotes and forward slashes instead (`"D:/Lab/Sam's tables"`). The template comment explains both.
- **Where `--csv` saves:**
  - A file name, or a relative path such as `june\compounds.csv`, goes inside the area's folder when one is set, and inside the workspace `results\` folder when it isn't. The current folder is never used. This replaces "taken as typed, relative to the current folder" in decision 0014.
  - A full path, such as `D:\Lab\compounds.csv`, is used as typed and wins over the setting.
- **Never in the code folder.** Whatever the path came from, Synthase refuses to save a table inside its own code folder (the same folder `syn init` refuses, decision 0009):
  `Synthase can't save the table there: <path> is inside Synthase's own code folder (<folder>). Tables hold your results. Keeping them outside the code folder means none of them can be uploaded to GitHub by mistake. Choose a folder outside it, or set "compounds" under [folders] in <config path>.`
- **A missing folder is refused, never created.** A typo in a path would otherwise quietly make a new folder somewhere unexpected:
  `Couldn't save the table: the folder <folder> doesn't exist. Create it in File Explorer, or change "compounds" under [folders] in <config path>.`
  When the folder didn't come from the config (the `results\` folder, a full path or a subfolder in the file name), the last sentence is `Create it, or choose another folder.` Both exit with code 1.
- **A folder that can't be written to** gives the message from decision 0014, `Couldn't save <path>: <reason>. If it is open in Excel, close it and try again.`, and exit code 1.
- **`syn doctor` checks each area's folder** once the config is valid, with one line:
  - set and present: `ok  Compounds folder: <path>`
  - not set: `ok  Compounds folder: not set, tables go in <workspace>\results`
  - missing, or inside the code folder: `FAIL`, with a `Fix:` line pointing at `[folders]` in config.toml.

## Consequences
- `--csv` now reads `config.toml`, so a broken entry anywhere in it stops a CSV being saved, with the usual config error. Without `--csv`, nothing changes.
- Each later command that saves a table (plate maps, MIC results, stats) adds its own name to `[folders]` and its own `syn doctor` line when it is built.
- Tests write folder settings that point at temporary folders only.
