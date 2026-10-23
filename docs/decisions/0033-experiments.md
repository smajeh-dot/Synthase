# 0033: Experiments: create, open and the one reopened at start

## Context
Decision 0023 gave each project one `data\experiments.toml` and the commands `exp create` and `exp open`. #104 was split on 2026-10-23 into this part and #128 (`exp show`, `exp show all`, `exp edit`), because the two together were about 650 changed lines. The owner approved the layout from a sample file, and every message below, in the #104 triage on 2026-10-23. The owner also asked that the last experiment opened in a folder opens again when Synthase starts there.

## Decision
**The file** (approved from a sample)
- `data\experiments.toml` holds one table per experiment, named by its ID: `title`, `created` (ISO 8601 text with its UTC offset), `x_unit` (written as `s` at creation), then `[E002.values]` with one inline table per value: `value` and `unit`, then `unc` and `note` only if they were typed. Every number is text. A name with symbols is written as a quoted key.
- Synthase writes no `#` lines. A `#` line added in Notepad is kept when the file is rewritten.

**`exp create`** asks three questions:
- `Title:`, needed.
- `Load starting values from a file, or enter them manually? [f/m]:`. `m` goes on. `f` says `✗ Loading values from a file isn't built yet.` and asks again until #108 builds it. Anything else says `✗ Type f or m.`
- Manual entry: the spec's line `Enter one value per line:  name  value  unit  [+/- uncertainty]  [# note]` is shown once, then `Values:` takes one line at a time until an empty line (the hint on the top rule says so, decision 0030). An empty first line gives an experiment with no values.
- Each line is read as in decision 0032. A line missing a name, a value or a unit: `✗ Each line needs a name, a value and a unit.` A name already entered in this run: `✗ m_crude is already entered in this experiment.`
- Nothing is saved until the last answer. The experiment is saved, the counter after it, so Ctrl+C uses no ID. Then: `✓ Created E002 "Recrystallisation trial 2"  ·  2026-10-21 14:32:07  ·  2 values` (`1 value` for one). The new experiment becomes the open one.

**`exp open <ID or title>`**
- An ID wins over a title. Titles are matched exactly, including case. Success: `✓ Opened E002 "Recrystallisation trial 2".`
- Not found, with close matches: `✗ Unknown experiment 'E009'.` then `› Did you mean: E001, E002?` (IDs and titles are both offered). With none close, every ID: `✗ Unknown experiment 'E009'.` then `› Experiments: E001, E002.` With no experiments: `✗ There are no experiments yet.` Two with the same title: `✗ Several experiments are called "Trial": E001, E003. Open one by its ID.` Same titles are allowed at `exp create`.

**The open experiment**
- It is shown in the status line after the project's name: `Aspirin synthesis/E002`.
- `exp create` and `exp open` write its ID to `data\.last-experiment`, a plain text file beside the lock and the up-arrow history. It is not one of the logged data files, so choosing an experiment is not a change in `history.jsonl`.
- When Synthase starts in the folder and holds the lock, the experiment in that file opens by itself and the output says `› Opened E002 "Recrystallisation trial 2" from last session` (the owner's wording). If that experiment is no longer in `experiments.toml`, or the file is missing or unreadable, nothing is opened and nothing is said.

**History** (`data\history.jsonl`)
- `exp create` logs `create_experiment` (`id`, with the title as `new`), then one `add` per value (`id`, `name`, and `new` as the value's stored fields: `value`, `unit`, and `unc` and `note` if typed), then the `issue_id` for the counter. #105's `value history` reads the `add` lines.

**Tab**
- After `exp show ` Tab offers the experiment IDs (decision 0028).

## Consequences
- `exp show`, `exp show all` and `exp edit` still say `isn't built yet.` until #128.
- #105 acts on the open experiment (`SynthaseApp.experiment`) and finds a value's first version in the `add` lines written here.
- #108 makes `f` work, and the file option will skip the manual-entry question.
- A hand-edit to `experiments.toml` is noticed at the next start and logged as one outside edit (decision 0025).
