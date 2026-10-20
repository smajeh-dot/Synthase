# 0019: fit check, and the groundwork for fit

## Context
`fit` is the planned curve-fitting engine. The user chooses a shape, such as a line or an S-curve, and Synthase finds the best settings for it. Every result shows a range and a list of checks. Synthase never grades a fit or picks the shape. The design is the `fit` build handoff (design pass 1, 20/10/2026). As with decision 0016, it is kept outside the repo, and this record keeps what the build needs.

Step 1 of the 8-step build is `fit check` (#84). It reads a CSV of measurements and runs the group A checks (A1 to A11), which say whether the data can have a curve fitted to it. At triage the whole step came to about 1,500 lines, far over the 400-line limit for one PR. The owner chose all the triage defaults below (2026-10-20).

## Decision
- **Three issues, three PRs, in this order:**
  - #85 is the groundwork:
    - whole-line colours for cautions and warnings
    - the four `fit.*` config entries
    - the shapes table
    - `config GROUP`
    - this record
  - #84 covers:
    - the group A checks
    - the wording module, which never prints
    - `syn fit check` with flags
    - the report in the app
  - #86 covers the guided questions and the data preview in the app.
- **The colour rule.** A caution (`!`) or warning (`?`) is drawn in its own colour across the whole line, from the symbol to the end of the text, as an error (`✗`) already is. The symbol stays bold. This applies to caution and warning messages and to the flags on a compound card. It replaces the part of decision 0016 that drew only the symbol in colour and left the text in the normal foreground. The symbols still carry the meaning, so nothing depends on colour alone. The status line is not a message, so it keeps its look.
- **Four thresholds go in the config template,** each marked `UNVERIFIED` with the usual placeholder source:
  - `fit.min_points_per_setting = 5`: below this many points per setting, A1 flags the data.
  - `fit.min_distinct_x = 5`: below this many different x values, A7 flags the data.
  - `fit.coverage_min_fraction = 0.2`: the smallest share of the points each third of the log x range should hold (A8).
  - `fit.outlier_flag = 3.5`: the robust z-score, worked out from the median and the median absolute deviation, above which A9 lists a point as suspect. Points are listed, never removed.

  The owner checks the real values against the literature in their own workspace. A workspace made before these entries existed gets them from the template, unverified, so `doctor` lists them and the status line counts them with no action needed.
- **The shapes table lives in code** (`fit_shapes.py`), not in the config:
  - line 2
  - exponential 3
  - s-curve 4
  - growth 4
  - michaelis-menten 2
  - arrhenius 2

  A settings count belongs to a shape's equation, not to a measurement, so it isn't a scientific value to verify. With no shape chosen, the checks use the largest count, 4.
- **`config GROUP`** lists every entry whose key starts with that group and a dot, in the usual config table, under `fit settings in <path>`. It ends with the group's own count line, such as `? 4 of 4 values are still unverified.` The `[folders]` checks are left out. `config fit` is what the report's `› See them with config fit.` hint names. Capitals and `[ ]` are ignored, as for one value. A full entry name still shows that one value.
- **Settled for #84 and #86,** to be built in those PRs:
  - **Group A follows Claude's reading of the design.** The owner sees a full sample report before tests are written. The checks:
    - A3: values that aren't numbers
    - A4: no spread in y
    - A6: x ≤ 0 on a log range
    - A7: distinct x values below `fit.min_distinct_x`
    - A11: a summary of the repeats
  - **CSV:**
    - commas only, with the header row first
    - UTF-8, with or without Excel's BOM (Excel's "CSV UTF-8" save)
    - anything else is refused with a plain reason
  - **Flags:** `syn fit check FILE --x COL --y COL --x-unit U --y-unit U --repeats/--no-repeats --model NAME`.
  - **A10's wording for a skipped unit:** `! flag  No unit given for response. Tables show it without one.`
  - **The invented `doses-a.csv`:**
    - 10 doses doubling from 0.5 to 256 µM, with 3 repeats each
    - y comes from a fixed invented S-curve with no randomness
    - generated in the test, never committed
    - each third of the log range includes its lower edge, and the top third includes 256, so the thirds hold 9, 9 and 12 points
  - **Commands are named without the slash** (decision 0018): `fit check`, `config fit`.

## Consequences
- Every caution and warning on screen changes colour on purpose: card flags, the `config` count line, doctor's unverified list and the history-save message. A test checks the colours.
- The template now has 17 entries, so a new workspace starts with 17 unverified values.
- `count_line()` now takes a list of entries rather than the whole config, so a group can be counted on its own.
- #84 and #86 depend on this PR, and each records any further details here.
