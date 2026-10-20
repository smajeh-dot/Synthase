# Manual: fit check

`fit check` looks at a file of measurements and tells you whether a curve can sensibly be fitted to it. It is the first step of the planned `fit` feature.

**What it does not do.** It fits nothing, saves nothing, removes no points and never says your data is good or bad. It counts what it finds and lists what you should look at. Choosing the curve shape and judging the result stay with you.

All the numbers in this manual are invented. Your own data stays in your workspace, never in the Synthase code folder.

## 1. Before you start

You need Synthase set up (see the README). Open PowerShell and check:

```powershell
syn --version
```

### Your data file

`fit check` reads a CSV file: one header row, then one row per measurement, with commas between values. A minimal file:

```
dose (µM),growth
1,0.90
2,0.80
4,0.60
8,0.35
16,0.20
```

- **x** is what you chose to vary (a dose, a time, a concentration). **y** is what you measured.
- Put the unit in brackets at the end of the column name, as in `dose (µM)`. `fit check` then picks the unit up on its own.
- A file may hold more than two columns (a well name, a note, another measurement). You choose which two to use.
- If several y values share one x, they are treated as repeats of one measurement (you can say they are not).
- Leave out units, notes and symbols inside number cells. A cell such as `n/a` or `0.5 mm` is not a number and fails check A3.

### Saving the file from Excel

Use **File → Save As → CSV UTF-8 (Comma delimited) (\*.csv)**. Plain "CSV (Comma delimited)" can save the µ symbol wrongly, and some Windows regional settings save semicolons instead of commas. Synthase reads commas only, and refuses a file that is not UTF-8 or that uses semicolons, with a message saying what to change.

## 2. Running it in the app (the guided way)

Open the app and type the command on its own:

```powershell
synthase
```

```
fit check
```

The app asks one question at a time. Press Enter to send each answer. Esc cancels at any point, and nothing is checked.

| Question | What to type |
|---|---|
| `Which file? Type its path, or drag it in:` | The path to your CSV. You can drag the file from File Explorer into the window; the quotes it adds are fine. A wrong path prints what is wrong and asks again. |
| *(a preview appears)* | Nothing to type. It shows the file's name, the number of rows and columns, the column names and the first 6 rows, so you can see the file was read as you expect. |
| `Which column is x (…):` | A column name from the list. Capitals do not matter, and you can leave out the unit: `dose` works for `dose (µM)`. |
| `Which column is y (…):` | A column name from the columns left (x is no longer listed). |
| `Unit of dose [µM]:` | Enter keeps the unit shown in the brackets. Type another unit to replace it. |
| `Unit of growth (Enter to skip):` | The column name has no unit, so type one, or press Enter to skip (see check A10). |
| `Are growth values at the same dose repeats of one measurement? [Y/n]` | Only asked if some x values appear more than once. Enter means yes. Type `n` if they are separate points, not repeats. |

If the file has only two columns, the app skips the x and y questions, takes the first column as x, and says so (`Using dose as x and growth as y.`).

Then the report appears (section 4).

## 3. Running it in PowerShell (one line)

```powershell
syn fit check "C:\Users\you\Documents\growth.csv" --x dose --y growth
```

Put the path in quotes if it has spaces. This gives the same report as the app, with the same words.

| Option | Meaning |
|---|---|
| `FILE` | The CSV file. Required. |
| `--x COLUMN` | The column of x values. Needed if the file has more than two columns. |
| `--y COLUMN` | The column of y values. Needed if the file has more than two columns. |
| `--x-unit UNIT` | The unit of x, if the column name has none in brackets. |
| `--y-unit UNIT` | The unit of y, likewise. |
| `--repeats` / `--no-repeats` | Whether y values that share an x are repeats of one measurement. The default is yes. |
| `--model SHAPE` | Check against one curve shape instead of any shape. One of: `line`, `exponential`, `s-curve`, `growth`, `michaelis-menten`, `arrhenius`. |

You can also type the same options in the app, for example `fit check growth.csv --x dose --y growth`, and it skips the questions. In the app, the guided questions never ask about the shape. To check against a shape, use `--model`.

`syn fit check` needs a file. `syn fit check` on its own shows an error, not questions.

`syn help fit check` (or `help fit check` in the app) lists the options as they are installed on your laptop.

**Exit code.** `syn fit check` finishes with code 1 if any check FAILS, and 0 otherwise. Flags do not change it. In PowerShell you can see it with `$LASTEXITCODE`.

## 4. Reading the report

```
Checking doses.csv: dose (µM) against response, any shape (up to 4 settings)

  ✓ ok    A1   30 points for 4 settings, 7.50 per setting.
  ...
  ! flag  A10  No unit given for response. Tables show it without one.
  · info  A11  10 dose values with 3 repeats each.

Checks: 11 run, 10 passed, 1 flagged.
```

The first line names the file, the two columns and the shape. "Any shape (up to 4 settings)" means no shape was chosen, so the checks are strict enough for the most demanding shape.

Each row has a word, a code and a sentence. The word carries the meaning, and the colour only adds to it:

| Word | Meaning | What to do |
|---|---|---|
| `✓ ok` | The check passed. | Nothing. |
| `! flag` | Worth a look. The data can still be used. | Read the sentence, and decide whether it matters for your experiment. |
| `✗ FAIL` | A curve cannot be fitted to this data as it is. | Follow the `› Fix:` line under it, then run the check again. |
| `· info` | A fact about the file. It is counted as passed. | Nothing. |

The last line counts the checks and never grades the data. "Passed" means no flag and no failure, and it does not mean the experiment was good.

### Settings

A shape has a number of **settings**, the numbers its equation needs to find. A line has 2 (slope and intercept). The checks compare your data with that number, because you cannot find more settings than the data can support.

| Shape | Settings |
|---|---|
| `line` | 2 |
| `exponential` | 3 |
| `s-curve` | 4 |
| `growth` | 4 |
| `michaelis-menten` | 2 |
| `arrhenius` | 2 |

With no shape chosen, the checks use 4, the largest.

## 5. The 11 checks

A **point** is a row with a number in both the x and the y column.

| Code | What it checks | When it flags or fails |
|---|---|---|
| A1 | Points against settings | FAIL if there are no more points than settings. Flag if fewer than the limit per setting (5 by default). |
| A2 | Different x values | FAIL if fewer different x values than settings. |
| A3 | Every x and y cell is a number | FAIL, naming the lines and what was written there. |
| A4 | The y values vary | FAIL if every y is the same, or there are none. Usually the wrong column was chosen for y. |
| A5 | Both columns are filled in, and no row repeats exactly | FAIL if x and y have different numbers of values (lines are named). Flag if a whole row appears twice, which can mean it was pasted twice. Two equal readings in different wells are not flagged. |
| A6 | Whether x can be on a log scale | A dose of 0 gives a flag (an untreated control, left out of the log scale). An x below 0 is a FAIL for the s-curve and a flag if no shape was chosen. Other shapes accept any sign. |
| A7 | Enough different x values | Flag if fewer than the limit (5 by default), or exactly as many as there are settings (the curve would pass through every point and leave nothing to check it against). |
| A8 | Coverage across the range | The x range is cut into thirds, on a log scale when the shape needs it. Flag if a third holds less than the limit of the points (20% by default). |
| A9 | Suspect repeats | Only where there are at least 3 repeats at one x. A point far from the rest is listed as suspect. It is kept, never removed. Check it against your notes. |
| A10 | Units | Flag if x or y has no unit. Tables then show the value without one. |
| A11 | A summary of the repeats | Info only, for example `10 dose values with 3 repeats each.` |

### Suspect points (A9)

A9 measures how far each repeat is from the middle of its group, using the median and the median absolute deviation (a robust spread that one odd point cannot distort). Above the limit, the point is listed. If most repeats at an x agree exactly, there is no spread to measure against, so that x is skipped. With `--no-repeats`, A9 does not run, because values sharing an x are not repeats.

## 6. The warning about unverified values

Four limits in the checks live in your workspace `config.toml`, never in the code:

| Setting | Name in the config | Default | Used by |
|---|---|---|---|
| Points per setting | `fit.min_points_per_setting` | 5 | A1 |
| Fewest different x values | `fit.min_distinct_x` | 5 | A7 |
| Least share of points in each third | `fit.coverage_min_fraction` | 0.2 | A8 |
| Suspect-point limit | `fit.outlier_flag` | 3.5 | A9 |

These are **placeholders, marked UNVERIFIED**. Until you check each against the literature or your supervisor's guidance, the report ends with a warning that the results are provisional. `syn doctor` lists them. The `config` commands below work in the app only. To see these four values, type:

```
config fit
```

To change a value, then mark it as checked (the warning stays until you do):

```
config set fit.min_distinct_x 6
config verify fit.min_distinct_x
```

`config source` records where a value came from. See `help config` for the options.

## 7. When it refuses the file

These stop the check, with a message saying what to change. Nothing is guessed.

| Message says | What to do |
|---|---|
| There's no file at … / is a folder | Check the path. Drag the file in to avoid typos. |
| isn't saved as UTF-8 text | Re-save from Excel as CSV UTF-8. |
| seems to use semicolons | Re-save as CSV UTF-8 (Comma delimited). |
| has only one column | The file needs an x column and a y column. |
| is empty, or has column names but no rows | Add your measurements. |
| Column N has no name / Two columns are called … | Give every column its own name. |
| Line N has more values than there are column names | A row has an extra comma. Check the line named. |
| There's no column called … | Use a name from the list shown. |
| The x and y columns must be different | Choose two different columns. |
| says which to use with --x and --y | The file has more than two columns, so name them. |

## 8. Worked example

Save this as `growth.csv` (an invented example):

```
dose (µM),growth,note
1,0.90,a
2,0.80,b
4,0.60,c
8,0.35,d
16,0.20,e
```

In the app, type `fit check`, then answer: the file's path, `dose`, `growth`, Enter (keep `µM`), Enter (skip the unit of growth). The report will show:

- A1 as a flag: 5 points for 4 settings is 1.25 per setting, fewer than 5. (With `--model line` it reads: 5 points for 2 settings is 2.50 per setting, fewer than 5. The default limit is 5 points per setting.)
- A2 as ok: 5 different dose values.
- A7 as ok: 5 different dose values, at least the 5 needed.
- A9 as ok: Too few repeats to compare. Suspect points are checked after fitting. (Each dose appears once.)
- A10 as a flag: No unit given for growth.

What this tells you: with the default limit, 5 points are too few even for a line. Measuring at more doses is the usual fix, and repeats at each dose help too. The limit is a placeholder you can change (section 6). The decision is yours, and Synthase only shows you the count.

The same check on one line of PowerShell:

```powershell
syn fit check growth.csv --x dose --y growth --model line
```

## 9. What comes next

Choosing a shape and fitting it are later steps, not built yet. They are listed in `ROADMAP.md`. This manual will grow with them.
