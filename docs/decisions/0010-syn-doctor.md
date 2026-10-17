# 0010: `syn doctor` and the RDKit dependency

## Context
`syn doctor` (#12) is a self-test: one command that says whether Synthase is installed and set up correctly, and lists every config value still unverified. It checks the Python version, RDKit, the workspace and the config. Until now Synthase had no run-time dependencies (decision 0003), so the RDKit check could never pass. The issue also left open whether unverified values count as a failure, what counts as a valid workspace, and what happens to the config check when there is no workspace.

The owner chose all the triage defaults below for #12 (2026-10-17).

## Decision
- **RDKit is Synthase's first run-time dependency:** `rdkit>=2026.9.1` in `pyproject.toml`. Decision 0003 adds a dependency only when a feature needs one, and doctor needs it. The compound register (M1) needs it next. Decision 0002 already checked that it has Windows wheels for Python 3.13.
- **The four checks:**
  - **Python:** the running Python is 3.13, the version pinned in decision 0002.
  - **RDKit:** `rdkit` imports and reads the SMILES `CCO` (ethanol).
  - **Workspace:** `current_workspace()` (decision 0009) finds the folder, and it has `raw\`, `maps\`, `results\`, `notebook\` and `config.toml`. A missing `config.toml` fails with the fix "run `syn init` again". It is never silently replaced by the template.
  - **Config:** `load_config()` (decision 0008) reads the workspace's `config.toml` without errors. When there is no workspace or no `config.toml`, the config shows as "not checked" with the fix "get the workspace check passing first", and counts as a failure.
- **Unverified values don't fail doctor.** They are listed with their name, value, unit and source, but the exit code stays 0. Otherwise doctor would fail until every value had been checked against the literature.
- **Exit code:** 0 when every check passes, 1 when any fails.
- **Wording:** each check prints one line starting with `ok` or `FAIL`. For Synthase's own checks, a `Fix:` line follows each failure. Errors from the workspace and config code (decisions 0008 and 0009) already end with their fix, so doctor shows them as written and the wording stays in one place. The last line is either `All checks passed.` or `N check(s) failed. Fix it/them, then run "syn doctor" again.`
- **Text Synthase can't write is replaced, not fatal.** The config contains characters such as `cm⁻¹` and `≤`. When output is saved to a file in PowerShell, Windows Python writes in the old Windows character set, which lacks them, and would crash. `syn` now writes `?` in their place instead. This applies to every command.

## Consequences
- Installing Synthase downloads RDKit, about 30 MB, and CI takes a little longer.
- The setup script (#13) can run `syn doctor` and use its exit code.
- A wrong Python version can only be faked in the tests, because CI and the venv both run 3.13.
