# 0032: Value entry: numbers, names and the recognised-unit list

## Context
Spec C168, C165 and C169 say how a value line is read, but leave the unit list open ("v1: not editable", with a few examples) and give no wording for refusals. #103's triage proposed both. The owner chose the list unit by unit on 2026-10-23, and the refusal wording below. The list only catches typos: nothing is converted, compared by dimension or corrected (C70, D22, D25).

## Decision
**Numbers**
- A number is an optional sign, digits with an optional decimal point (`.5` and `5.` too) and an optional exponent. It is kept as text, exactly as typed. The uncertainty follows the same rule.
- A refused number says `'2.1O' isn't a number.` When swapping a comma for the point, or `O`, `o`, `l`, `I` for `0`, `0`, `1`, `1`, makes a number, that reading is added: `'2.1O' isn't a number. Did you mean: 2.10?` Nothing else is added: `'1/2' isn't a number.`

**Names** (C165)
- No spaces, not empty, at most 64 characters, not starting with `#`, not `+/-`, not starting with `rxn_` (kept for F3). Case-sensitive.
- Messages: `A value name can't start with '#'.` · `A value name can't be '+/-'.` · `A value name can be at most 64 characters.` · `Names starting with rxn_ are kept for reaction records.`
- The empty and spaced cases can't come from a typed line, only from a CSV row (#108). Their wording was proposed by Claude and approved by the owner on 2026-10-23: `A value name can't be empty.` · `A value name can't contain spaces.`

**Units**
- A unit is required. It is matched whole and case-sensitive against this list, and stored as typed (`u` is not turned into `µ`):
  - Mass: `g`, `kg`, `mg`, `ug`
  - Volume: `L`, `mL`, `uL`, `cm^3`, `dm^3`
  - Amount: `mol`, `mmol`, `umol`
  - Concentration: `mol/dm^3`, `mol dm^-3`, `M`, `mM` (`mM` is millimolar)
  - Molar mass, density, purity, yield: `g/mol`, `g mol^-1`, `g/cm^3`, `g cm^-3`, `g/dm^3`, `g dm^-3`, `%`
  - Temperature: `K`, `degC`
  - Time: `s`, `min`, `h`
  - Energy: `J`, `kJ`, `J/mol`, `kJ/mol`, `J mol^-1`, `kJ mol^-1`
  - Pressure: `Pa`, `kPa`, `bar`, `atm`
  - Frequency: `Hz`
  - Rate constants: `s^-1`, `min^-1`, `dm^3/mol/s`
  - Dimensionless: `none`
- This replaces C169's piece-by-piece check and its list. Left out on purpose: the biology units (`bp`, `kb`, `U`, `ng/uL`, `rpm`), `nM`, `uM`, `nmol`, `m^3`, `nm`, `ppm` and every other unit. The list is in the code and isn't editable.
- Symbols are not accepted as input (`µg`, `µL`, `°C`): the owner's keyboard has none. Only the ASCII spellings are on the list. `±` as the uncertainty marker is unchanged (#97).
- An unknown unit says `Unknown unit 'gg'. Did you mean: g, kg?` (the two closest). With nothing close it says only `Unknown unit 'xyz'.`, with no list.
- `1/s` and `1/min` are refused. Because `s^-1` and `min^-1` are listed, they are suggested: `Unknown unit '1/s'. Did you mean: s^-1?`
- A unit may hold one space (`mol dm^-3`). The command table reads a second word as part of the unit only when the two together are a listed unit, so a forgotten `+/-` (`value add m_crude 2.211 g 0.001`) still prints the usage line.

## Consequences
- `value add` and `value edit` still say `isn't built yet.` until #105: #103 adds the checker (`src/synthase/values.py`) and the table change, and registers no handlers.
- #104, #105 and #108 call `values.read_entry`, so each refusal is worded once, here.
- The unit list is now the owner's list, not spec C169's. F3's C175 (mass, volume and amount units) and C174 name units that are no longer all accepted (`m^3`, `nmol`); settle that when F3 is scheduled.
- Compound fields use this list too (#106 says so). Whether F4's x and y units do is open.
- Adding a unit later is a one-line change to `UNITS` plus the matching line in `tests/test_values.py`, with the owner's say-so.
