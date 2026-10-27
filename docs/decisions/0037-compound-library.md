# 0037: The compound library

## Context
#106 builds `compound create`, `compound edit` and `compound show all` (decision 0023). The spec gives the six field names (C72), the `Added C001 (<name>).` line and the stored layout (Section 3). The rest of the wording and look was proposed in the #106 triage on 2026-10-27, and the owner chose "use your defaults" for every row.

## Decision
**`compound create`** is a walk-through (decision 0030) with six optional questions: `Name:`, `Formula:`, `Molar mass:`, `Density:`, `Purity:`, `Note:`. Enter skips a field.
- A unit field takes one line, the value then the unit. Above `Molar mass:` it shows once: `Type the value and its unit, e.g. 138.120 g/mol`.
- The value and unit are checked as in decision 0032 and kept as typed. A line with no unit is refused: `Each needs a value and a unit.`, then the question again.
- It ends `✓ Added C001 (Salicylic acid).`. A compound with every field skipped is allowed and ends `✓ Added C001.`.
- Nothing is saved until the last answer, and the ID is issued by saving, so Ctrl+C saves nothing and uses no ID.

**`compound edit <ID>`** asks the same six questions in the edit look of decision 0030: the stored value is the placeholder, Enter keeps it and `-` clears it. A unit field shows as `138.120 g/mol`.
- It ends `✓ Updated C001 (Salicylic acid).` (`✓ Updated C001.` with no name). When nothing changed it says `Nothing changed. Nothing was saved.` as a muted hint, saves nothing and logs nothing.
- A wrong ID: `✗ Unknown compound 'C010'.` then `› Did you mean: C001, C002?`, or `› Compounds: C001, C002.` when nothing is close. With no compounds: `✗ There are no compounds yet.` then `› Use 'compound create' to add one.`

**`compound show all`** prints one line each, ID bright and then the name and formula in columns, a missing one left blank:
```
C001  Salicylic acid    C7H6O3
C002  Acetic anhydride
```
With none stored: `There are no compounds yet.` (a muted hint).

**Stored and logged**
- `data\compounds.toml` follows spec Section 3: one `[C001]` table per compound, fields in the order name, formula, molar_mass, density, purity, note; the three unit fields are inline tables `{ value, unit }`. A skipped or cleared field is left out. Keys Synthase doesn't know (added in Notepad) are left alone.
- A new compound is saved first and the counter after it (decision 0025). Each change is logged with the spec's action names (C171): `add_compound` (`id`, `new`) and `edit_compound` (`id`, `old`, `new`), where each side is the stored fields.

**Tab** (decision 0028) offers compound IDs after `compound show` and `compound edit` (the `id` source now answers for `exp` and `compound`), and the six field names after `compound show <ID>`.

## Consequences
- `compound show <ID> [field]` is still `isn't built yet.`: it is #107. #107 can reuse `compounds.find` for the wrong-ID wording above, `compounds.get` and `compounds.shown`.
- The spec's `add compound`, `edit compound` and `list compounds` stay superseded by decision 0023.
