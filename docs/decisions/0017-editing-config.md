# 0017: Editing the config from the app

## Context
`/config` shows the settings (#60). #61 adds changing them from inside the app: a value, its source, whether it has been checked, and the `[folders]` settings. Everything else in the workspace `config.toml`, its comments included, must stay as it was.

Python's built-in `tomllib` can read TOML but not write it, and decision 0008 said Synthase only reads the file. The issue also left open the commands and their wording, what changes the verified mark, and what to do with an entry that `load_config()` fills in from the template because the workspace file doesn't have it.

The owner chose all the triage defaults below for #61 (2026-10-19).

## Decision
- **`tomlkit` writes the file.** `tomlkit>=0.13,<1` becomes a run-time dependency, under the rule in decision 0003. It is pure Python, MIT-licensed, made by the Poetry team, and has no dependencies of its own. It keeps comments, blank lines and order by design. This replaces "Synthase only reads the file" in decision 0008. `tomllib` still does every check.
- **Only the workspace's own `config.toml` is edited,** never the template in the package.
- **The commands,** in the app only. `syn` gains no `config` command, as with `/config` in #60.
  - `/config set <name> <value>` changes a value.
  - `/config source <name> <text>` sets where it comes from.
  - `/config verify <name>` marks it as checked against that source.
  - `/config folder compounds <path>` sets a `[folders]` setting. `/config folder compounds ""` clears it.
  - Names are matched as `/config <name>` matches them: capitals and `[ ]` around the name are ignored. Entry names always contain a dot, so `set`, `source`, `verify` and `folder` can't clash with one.
- **How a value is typed.** A value keeps its kind, because the features that use it expect that kind. A value of the wrong kind is refused with `[mic.growth_threshold] takes a number, e.g. /config set mic.growth_threshold 0.1.` The example is the entry's current value.
  - Number: `0.2`.
  - Range: `1600 1650` or `1600-1650`.
  - Text, such as a unit: `/config set units.mass g`, without quotes.
  - Bands are typed as `/config` shows them, with `≤` and `>` optional: `/config set fici.bands 0.5 synergy, 4 no interaction, antagonism`.
  - Typing the value the entry already has changes nothing, so it can't reset the verified mark by accident.
- **Every change is checked by `load_config()`'s own rules** before anything is saved, so an edit can never leave a config that won't load. A refused change leaves the file exactly as it was.
- **Changing a value** always asks first, and marks the value unverified:
  `Change growth threshold from 0.1 OD600 to 0.2 OD600? It will be marked unverified until you check it again. Type yes to change it [no]:`
  then `✓ Changed growth threshold to 0.2 OD600. It is now unverified.`
- **Changing a source** asks first only when the value is verified, and then marks it unverified, because "verified" means checked against that source. A source for an unverified value is saved straight away.
- **`/config verify`** asks: `Mark growth threshold (0.2 OD600) as checked against "<source>"? Type yes to mark it verified [no]:`
  - It refuses while the source still starts with `UNVERIFIED`: `Set its source first: /config source mic.growth_threshold <reference>.`
  - A value that is already verified gets `✓ growth threshold is already verified.` and nothing changes.
  - There is no `unverify` command. Changing the value or the source already does it.
- **Folders** are not scientific values, so changing one asks nothing. The path is saved as typed, in single quotes when it can be (as the template comment advises). Afterwards the `/doctor` folder line is shown, so a folder that doesn't exist yet is flagged but not refused.
- **No, Esc or Ctrl+C** gives `‹ Nothing was changed.`
- **An entry only in the template** is copied from the template to the end of `config.toml` first. Before the question, the app says `› [x] isn't in config.toml yet, so it will be copied from the template.` Without this the owner would have to hand-edit for every entry a newer version adds.
- **The backup.** Before the first change in a session (one run of the app), the old file is copied to `config.toml.bak-YYYYMMDD-HHMMSS` next to it, as `syn init` does (decision 0009). Then the app says `› The old file is kept as config.toml.bak-….`
- **Saving.** The new file is written next to the old one and then swapped in, so a failed save leaves the old file whole. The file's line endings (CRLF on Windows) are kept. If `config.toml` changed while a question was being answered, for example because it was saved in Notepad, nothing is written and the app asks for the command again.
- **Afterwards** the status line reads the config again, so its unverified count is up to date.

## Consequences
- An existing install needs `pip install -e ".[dev]"`, or `.\scripts\setup.ps1`, run again to get `tomlkit`.
- A comment on the same line as a changed value is kept. A value that was spread over several lines is written back in the template's layout.
- An entry's `name` and `unit` can still only be changed by hand. They describe what the code expects, so changing them belongs with the features that use them.
