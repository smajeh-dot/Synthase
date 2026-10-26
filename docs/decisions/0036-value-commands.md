# 0036: The value commands

## Context
#105 builds `value add`, `value edit`, `value delete`, `value show` and `value history` (decision 0023). The spec fixes only the `Updated …` line (D8) and the history line shapes (C171); the rest of the wording and look was proposed in the #105 triage on 2026-10-26, and the owner chose "use your defaults" for every row.

## Decision
**Where they act.** Every `value` command works on the open experiment only (`SynthaseApp.experiment`). With none open: `✗ No experiment is open.`

**`value add`**
- `value add <entry>` stores a new value: `✓ Added m_crude: 2.2110 g +/- 0.001` (the note is not repeated).
- On an existing name: `✗ m_crude already exists in E002.` then `› Use 'value edit' to change it.`
- `value add` typed on its own is a walk-through (decision 0030): the spec's format line, then `Values:` takes one entry per line until an empty line. The question is needed, so an empty first line says `✗ An answer is needed.`. Each line is checked as in decision 0032; a name already stored or already typed in this run is refused on its own line, in one line: `m_crude already exists in E002. Use 'value edit' to change it.` Nothing is saved until the empty line, and then all the values are saved together, each logged as an `add`. One `✓ Added …` line is printed for each.
- This is the only value command that may be typed with no parts. A name added again after it was deleted is allowed and is a new `added` line in the same history.

**`value edit <entry>`**
- It replaces the whole entry (C164) and prints `✓ Updated m_crude: 2.2110 g -> 2.215 g`, showing each side's value and unit. When a retyped entry leaves out an earlier uncertainty or note, it adds what was cleared: `(uncertainty and note removed)`, `(uncertainty removed)` or `(note removed)`.
- An identical entry is still saved and logged as an edit.
- On a missing name: `✗ There is no value 'm_crud' in E002.`, then `› Did you mean: m_crude, m_salicylic?` (D27) or, when nothing is close, `› Values: m_crude, m_salicylic.`, then `› Use 'value add' to store a new one.` With no values at all: `✗ E002 has no values yet.` then `› Use 'value add' to store one.`
- `value edit` with no parts stays a usage error. This replaces the line in decision 0030 that lists `value edit` as a walk-through: the issue and decision 0023 give it as one line, and a walk-through would need questions the owner hasn't worded.

**`value delete <name>`** removes the value from `experiments.toml`; its history stays. `✓ Deleted m_crude.` An unknown name gets the same refusal as `value edit` without its last line.

**`value show <name>`** prints `m_crude  2.2110 g +/- 0.001` on one line, then `note: Balance B2` on a second line only when there is a note. An unknown name is refused as for `value delete`.

**`value history <name>`** prints one line for each version, oldest first, in the spec's shape (C171): the time as in `exp create` (`2026-10-21 14:32:07`), the action padded to nine characters, the name, then the text: `added    m_crude  2.2110 g`, `edited   m_crude  2.2110 g +/- 0.001 -> 2.215 g`, `deleted  m_crude`. The text holds the whole entry: value, unit, `+/- uncertainty` and `# note` when present. A deleted name still has a history, ending with `deleted`. A name never stored in this experiment: `✗ There is no history for 'x' in E002.` with the same suggestions, taken from every name the experiment has ever had.

**Stored and logged**
- A value is one inline table in `[E002.values]`, as decision 0033 describes. Each change is saved with `save_toml` and then logged: `add` (`id`, `name`, `new`), `edit` (`old` and `new`) and `delete` (`old`), where each entry is `{value, unit, unc?, note?}`, the same shape `exp create` writes.
- `value history` reads these lines, so a value's first version is the `add` line `exp create` wrote.

**Tab** (decision 0028) offers the open experiment's value names after `value edit`, `value delete`, `value show` and `value history`, and after `exp show`'s ID (that experiment's, when the ID is one). It offers none after `value add`, which needs a new name.

## Consequences
- `value add` with no parts is the one command that the table reads without its parts (`Command.bare`); help still shows the single usage line from decision 0023.
- #107 prints a value's `value unit` only (`exp show E002 m_crude`); #128 prints the table. Neither is changed by this record.
- No open issue needed editing for it.
