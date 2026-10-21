> **Superseded by [0020](0020-clean-slate.md).** It describes the retired app.

# 0008: Config file format

## Context
Every scientific constant Synthase uses needs one home, with its unit, where it came from and whether it has been checked against the literature (#10). The repo holds only a template with placeholder values. The real values live in the config in the owner's local workspace, which `syn init` (#11) creates by copying the template. The owner edits that file by hand when checking a value against a paper, so the format has to be easy to read and edit in a plain text editor.

The owner chose all the triage defaults below for #10 (2026-10-17).

## Decision
- **TOML,** read with Python's built-in `tomllib`. That adds no dependency. Synthase only reads the file, so it doesn't need a TOML writer.
- **The template is `src/synthase/config_template.toml`.** It sits inside the package, so it can still be found after `pip install`. The workspace copy is `config.toml` in the workspace folder.
- **One table per entry, two levels deep:** `[area.entry]`, for example `[mic.growth_threshold]`. Each entry has exactly these fields:

  | Field | Meaning |
  |---|---|
  | `name` | A plain-language label, used in warnings, e.g. `"growth threshold"` |
  | `value` | A number; a text value; a range `[low, high]`; or a list of bands |
  | `unit` | The unit, e.g. `"OD600"` or `"% v/v"`. `""` when the value has no unit, or when the value is itself a unit (the default units) |
  | `source` | Where the value comes from. Every template entry starts with `UNVERIFIED`. |
  | `verified` | `true` only after the owner has checked the value against the source |

  A list of bands is a list of `{ max = …, label = "…" }` tables in increasing order. Each band covers values up to and including its `max`. The last band has no `max` and covers everything above. Any other field is an error, so a typo such as `verifed` is caught instead of being ignored.
- **The template covers:**
  - the growth threshold
  - the FICI interpretation bands
  - the DMSO limit
  - the melting-point purity rule
  - four spectroscopic ranges (IR C=N and C=O stretches, ¹H NMR CH=N and chalcone vinyl protons)
  - default units for mass, volume, concentration, amount and temperature

  Every template value is a round placeholder of a sensible size, with `verified = false`. They are not checked values.
- **Loading:** `load_config(workspace)` reads `<workspace>/config.toml` if it exists, and otherwise the template. Any entry missing from the workspace file is taken from the template; it is still unverified there, so its warning still shows. Finding the workspace folder itself is left to #11.
- **Warnings:** an unverified value carries a warning that results can print:
  `Warning: growth threshold (0.1 OD600) has not been checked against the literature yet. Treat results that use it as provisional.`
- **Errors:** a broken file stops loading with a plain-language message that names the file and the line or the entry:
  `Your config file has a problem: <path>, entry [mic.growth_threshold]: 'verified' must be true or false. Fix that entry, or compare it with the template.`

## Consequences
- Verifying a value means editing the workspace `config.toml`: set the real value, put the reference in `source`, and set `verified = true`. The repo never sees it.
- A new constant added to the template in a later version works straight away in an older workspace. It shows as unverified until the owner copies it across and checks it.
- Python 3.13's `tomllib` errors give the line and column in their message text, but not as separate fields, so syntax errors quote that message as it is.
- Units such as `µL` and `cm⁻¹` are UTF-8 text. `tomllib` always reads UTF-8, whatever the Windows code page.
