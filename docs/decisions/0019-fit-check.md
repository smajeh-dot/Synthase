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

## Details settled for #84
The owner chose the defaults for the checks' open points on 2026-10-20 after seeing a sample report.

- **Which rows count as points.** Only a row with a number in both the x and the y column is a point. Text such as `n/a` fails A3, and a row with only one of the two values fails A5. A row is a repeat of another (the A5 flag) only if every cell matches, so two equal readings in different wells are not flagged.
- **A dose of 0** never blocks. A6 flags it as an untreated control, and A8 leaves it out of the log scale and says how many points it left out. Only an x below 0 blocks, and only for a shape fitted on log x: today that is the s-curve. With no shape chosen, an x below 0 is a flag. With any other shape, A6 says the shape can use x values of any sign.
- **A8's scale.** A8 uses a log scale when no shape is chosen, or when the shape is fitted on log x, as long as no x is below 0. Otherwise it uses a plain scale. A point exactly on the edge between two thirds goes in the upper one. A flag names how many thirds hold less than `fit.coverage_min_fraction` of the points.
- **A9.**
  - Only an x with at least 3 repeats can be checked. Its points are compared by robust z-score: the distance from the median, divided by the median absolute deviation over 0.6745. 0.6745 is the upper quartile of the standard normal distribution, worked out in code, so it is a mathematical constant, not a lab value.
  - An x whose repeats mostly agree exactly has no spread to measure against, so it is skipped.
  - With fewer than 3 repeats at every x, the row says `Too few repeats to compare. Suspect points are checked after fitting.`
  - With `--no-repeats`, the row says that values sharing an x aren't repeats.
- **A7** also flags when there are exactly as many different x values as settings, because the curve would then pass through every one.
- **Info rows** (`· info`, muted) count as passed, so the count line reads `Checks: 11 run, 10 passed, 1 flagged.` A FAIL adds `, 2 failed`.
- **Words.**
  - Rows name the file's own columns, for example `10 different dose values`.
  - Worked-out numbers are whole or to 3 significant figures. Values from the file are shown as typed.
  - The `syn` report ends with `Run "syn doctor" to see them.` because `syn` has no `config` command. The app ends with `› See them with config fit.` Every other word is shared.
- **Columns.** With two columns, `--x` and `--y` can be left out, and the first column is x. With more than two, both must be named. Names match with or without the unit in brackets, ignoring capitals.
- **`syn fit check`** exits with 1 if any check fails, as `syn doctor` does.

## Details settled for #86
The owner chose the defaults on 2026-10-20.

- **When the questions start.** `fit check` typed on its own in the app asks them. With any option, such as `--x dose` and no file, the usage error shows as before. `syn fit check` always needs a file.
- **The questions, in order**, each shown with the answer typed:
  - `Which file? Type its path, or drag it in:`. A wrong path prints the error and asks again.
  - A preview of the file: `NAME: N rows, N columns`, the column names and the first 6 rows in aligned columns (a cell longer than 16 characters ends in `…`), then `Showing all N rows.` or `Showing the first 6 of N rows.`
  - `Which column is x (…)`, then `Which column is y (…)`, listing only the columns left. A file with two columns skips both, and the preview ends with `Using dose as x and growth as y.`
  - `Unit of dose [µM]:`, pre-filled from the unit in brackets in the column's name, so Enter keeps it. With no unit in the name, `Unit of growth (Enter to skip):`. Skipping gives the A10 flag.
  - `Are growth values at the same dose repeats of one measurement? [Y/n]`, asked only when several y values share an x. Enter means yes, as the `--repeats` default does. Only `n` or `no` means no.
- **No shape question.** The checks allow for any shape, as `syn fit check` does without `--model`.
- **The same report.** The answers become the same options as the flags and go through the same code, so the report has the same words.
- **Cancelling** with Esc says `‹ Cancelled. Nothing was checked.`

## Consequences
- Every caution and warning on screen changes colour on purpose: card flags, the `config` count line, doctor's unverified list and the history-save message. A test checks the colours.
- The template now has 17 entries, so a new workspace starts with 17 unverified values.
- `count_line()` now takes a list of entries rather than the whole config, so a group can be counted on its own.
- #86's details are above. A question can now work out its words and its pre-filled answer from the earlier answers, and can show a line (the preview) after a good answer.
