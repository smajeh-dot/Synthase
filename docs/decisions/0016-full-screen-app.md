# 0016: The full-screen app, its look and the `synthase` command

## Context
M2 adds a full-screen terminal app on top of the shared command layer (decision 0012). #52 builds the frame that every later M2 issue fills in: an output area, a command bar and a status line. The issue left open how the app opens and whether testing it needs a new dev dependency. A bare `syn` printing the help was settled in decision 0014.

The owner answered the triage on 2026-10-18 and then had the look designed in a separate design session. The design canvas and its handoff spec are kept outside the repo. This record keeps what the build needs. The owner approved the design and answered its open questions on 2026-10-18.

## Decision
- **Textual** (`textual>=8.2.8,<9`) becomes a run-time dependency, under the rule in decision 0003, because the app needs it. It is pure Python with pure-Python dependencies (Rich and a few small libraries), so it installs on Windows with Python 3.13 with no compiler. Windows CI installs it on every PR.
- **Opening the app:** typing `synthase` in PowerShell, from any folder, opens it. The setup script puts `synthase.cmd` next to `syn.cmd`. The plain command line (`syn`, `syn compound ...`, `syn doctor`, `syn init`) is unchanged. `/quit` or Ctrl+Q closes the app, and Textual's alternate screen puts the PowerShell prompt back as it was.
- **Tests:** no new dev dependency. The pilot tests run with `asyncio.run(...)`.
- **Layout,** from top to bottom: the output area fills the window and scrolls. Then comes the bottom block of 4 rows: a rule, the command bar, a rule, and the status line on its own plain row. That leaves 26 output rows at 120 × 30 and 20 at 80 × 24. There is no header and no footer. The rules are `#767676` with no side borders. A short key hint, `Ctrl+Q quits`, sits in the top rule until the first command (#53 adds `↑ ↓ history` and `Tab completes` to it).
- **Commands:** spaces around a command and capitals are ignored. An empty line does nothing. `quit` without the slash is unknown. Each line is echoed as `> what you typed`, with a blank row above, and anything that isn't a command prints `✗ unknown command, try /help`.
- **Message kinds:** every kind has its own symbol, so no meaning depends on colour alone. The symbols are `>` for echoed input, `✓` success, `›` hint, `!` caution about the sample, `?` for a `Warning:` about an unverified config value, `✗` error, and `‹` cancel. Replies are indented 2 cells, and wrapped lines hang under the text, not the symbol.
- **Status line:**
  - `Workspace: <folder> · ? 2 config values unverified` (`1 config value`; `✓ all config values verified`)
  - `› No workspace yet. Type /init to create one.`
  - `! Workspace not found. Type /init to choose it.`
  - `Workspace: <folder> · ✗ config.toml has a problem, run /doctor` (the owner chose `/doctor` over `syn doctor`)
  - A path that doesn't fit is shortened, and only then: first the home folder becomes `~` (approved), then middle folders become `…`, and finally only `~\…\<last folder>` is left. The count is never cut.
- **Look:** the app paints its own background, `#0C0C0C`, the same as Windows Terminal's default Campbell scheme. That way every contrast ratio can be checked, and screenshots match the real app. All colours live in one Textual theme (`synthase/theme.py`) and all sizes and styles in one stylesheet (`synthase/synthase.tcss`). Python never names a colour. The tokens and their contrast on `#0C0C0C`:
  - text `#CCCCCC` (12.2:1)
  - echo and headings `#F2F2F2` (17.5:1)
  - muted `#A0A0A0` (7.5:1)
  - faint `#858585` (5.3:1)
  - rule `#767676` (4.3:1, lines only)
  - line `#626262` (3.2:1, lines only)
  - accent and answer `#6CB6FF` (9.1:1)
  - success `#42D55D` (10.2:1)
  - caution `#C19C00` (7.5:1)
  - warning `#C297FF` (8.5:1)
  - error `#FC4055` (5.6:1)
- **Changing the look:** `synthase --dev` reloads the stylesheet each time it is saved, using Textual's own file watcher, so no extra tool is needed.
- **Output:** new output follows the end unless the user has scrolled up. PgUp and PgDn scroll it. Only the latest 1,000 messages are kept, so a long session stays quick (owner decision). The command palette is switched off.
- **Settled now for later M2 issues** (owner, 2026-10-18):
  - Command history is kept between sessions, in a file in the workspace (#53; see "Details settled for #53").
  - Cancelling a question says `‹ Cancelled. Nothing was added.` (#56).
  - In answer mode the rules become heavy and blue, the question is the prompt in regular weight, and the `Answering …` title stays bold (#56).
  - The change log uses `→` in place of `->` (#57).
  - Every date shown on screen is DD/MM/YYYY. Dates inside file names stay YYYY-MM-DD, because Windows forbids `/` in file names (#57 onwards).
  - Success green next to error red is fine, because `✓` and `✗` and their words always tell them apart.
- **Details settled for #53** (the owner chose the triage defaults, 2026-10-18):
  - **One command list.** `synthase/commands.py` holds the app's commands: the whole `syn` tree read from `build_parser()` in `cli.py`, plus the commands only the app has (`/quit` now, `/help` from #54). Tab completion walks this list, so a new command or option added to the parser is completed with no extra work. Like `compound_text.py`, the module never prints anything.
  - **The whole tree completes now.** `/compound …`, `/init` and `/doctor` complete before the app can run them (#55 to #59). Until their issue wires them up, running one prints `✗ /compound isn't in the app yet. For now, run syn compound in PowerShell.` (with the command's own name).
  - **How Tab works.** Matching ignores capitals, the same way commands do. A single match is completed with a space after it, ready for the next word. With several, Tab first extends the text as far as every match agrees (`/compound e` becomes `/compound edit`). If that adds nothing and several commands or options still match, one hint line lists them without echoing the command, for example `› --rf  --rf-solvent`. The same list isn't printed twice in a row. The `-h`/`--help` options aren't offered; `/help` is the app's way to get help (#54).
  - **The key hint** in the top rule, shown until the first command, becomes ` ↑ ↓ history · Tab completes · Ctrl+Q quits `.
  - **The history file** is `command-history.txt` at the top of the workspace, one command per line, in UTF-8. It keeps the latest 500 commands. A command typed twice in a row is saved once. Mistyped commands are saved too, so they can be brought back and fixed. History can hold compound labels, so it lives in the workspace and never in the repo.
  - **Up and down.** Up steps back through earlier commands, newest first. Down steps forward again, and Down past the newest empties the bar. A half-typed line is not kept when Up is pressed.
  - **No workspace, or saving fails.** With no workspace yet, history works for that session only and nothing is saved. If the file can't be written (for example while OneDrive has it locked), the app shows `! Command history couldn't be saved: <reason>` once per session and carries on.

- **Details settled for #54** (the owner chose the triage defaults, 2026-10-18):
  - **One source.** `/help` reads the same `build_parser()` as `syn --help`, through the command list in `synthase/commands.py`: each command's one-line `help=`, its `description=`, and its arguments and options with their help. Only `/help` and `/quit` have their text in `commands.py`, because `syn` has no such commands. A new command or option added to the parser shows in `/help` with no extra work.
  - **Two levels.** `/help` lists every command, one line each, then `› Type /help <command> for more, e.g. /help compound.` A command with subcommands (`/help compound`) shows its description and one line per subcommand, then `› For a command's options, type /help compound <command>, e.g. /help compound add.` (the example is its first subcommand). One command (`/help compound batch`) shows a usage line such as `/compound batch ID [--date DATE] [--mass MASS] [--yield PERCENT]`, its description, then its arguments and options. `-h`/`--help` and `--version` are left out.
  - **Two columns.** Names sit in one column and their help in a second, so a long line wraps under its own column. Help uses the normal text colour, with no new colour.
  - **Unknown topics.** `✗ There's no help on "foo". Topics: init, doctor, compound, help, quit.` Below a command it lists that command's subcommands instead. Capitals and a leading slash are ignored, so `/help /Compound` works.
  - **The `syn …` wording stays.** Some descriptions point to `syn compound list` and similar. They're shown unchanged, because those commands only run in PowerShell for now. Each issue that wires a command into the app (#55 to #59) updates the wording.
  - **Tab after `/help`** completes the topics, using the same command list: `/help co` becomes `/help compound`.

- **Details settled for #55** (the owner chose the triage defaults, 2026-10-18):
  - **One source for the words.** `doctor.py` holds the report's wording: the heading, the `ok` and `FAIL` words, the unverified list and the last line. `syn doctor` prints it and `/doctor` shows it, so the two can't drift apart. Like `compound_text.py`, it never prints anything. `syn doctor` prints exactly what it printed before.
  - **The last line says `/doctor`.** In the app it ends `Fix them, then run /doctor again.` Every other line is word for word the same as `syn doctor`. The `Fix:` lines keep `syn init` until `/init` is in the app (#56).
  - **The heading stays:** `Synthase 0.1.0 self-test`, in bold heading white.
  - **The look.** Each check line starts with its word, so the meaning never depends on colour: `ok` in bold success green, or `FAIL` in bold error red with the line's text red too. A `Fix:` line is normal text, under the check's text. Words and text sit in two columns, so a long path wraps under its own column. The unverified list's title starts with the warning `?` (or `✓` when every value is verified), with the keys in muted grey and each value's source on the row below. The last line is `✓ All checks passed.` in green, or the `✗` failure line in red. A blank row separates the parts. No new colour.
  - **Plain text.** Every line is shown as plain text, so `[folders]` in a `Fix:` line and characters such as `cm⁻¹` and `≤` show in full.
  - **Afterwards** the status line reads the workspace and config again, so its unverified count is up to date. Words typed after `/doctor` are ignored, as they are after `/quit`.

- **Details settled for #70** (the owner chose the triage defaults, 2026-10-18):
  - **A missing `config.toml` is a config problem.** When the workspace has no `config.toml`, the status line shows `✗ config.toml has a problem, run /doctor`, the same as a broken one. It never counts the template's values as the workspace's own (decision 0010). `/doctor` names the missing file.

- **Details settled for #56** (the owner chose the triage defaults, 2026-10-18):
  - **Answering mode.** A command asks its questions from the shared question lists (`compound_questions.py`, #51). While a question is open, the top rule becomes heavy and blue with the bold title ` Answering /init · Esc cancels ` on the left. The question wraps on its own rows, in regular weight, just above `> ` and the input. The bar grows to fit them and shrinks back afterwards.
  - **The record.** Each question and its answer are copied into the output as one line, like PowerShell: the question in muted grey, the answer in blue. A wrong answer adds `✗ <reason>` under it, and the same question stays in the bar. Enter is an answer: it skips a question that may be skipped and is explained on one that can't. `[y/N]` questions count only `yes` or `y` as yes.
  - **Cancelling.** Esc or Ctrl+C cancels the whole command and saves nothing. Each command says what wasn't done: `‹ Cancelled. Nothing was changed.` for `/init`, and `‹ Cancelled. Nothing was added.` for the flows that add things. Outside answering mode the two keys work as before.
  - **Keys and history while answering.** Up, Down and Tab do nothing. Answers are not saved to the command history, because the history is for commands and answers can hold compound details. The command that opened the questions is saved as usual.
  - **`/init [path]`.** Everything after `/init` is the path, with any quotes around it removed, so a path with spaces (such as a OneDrive folder) works with or without quotes. `/init` alone uses `Documents\Synthase-data`. It asks decision 0009's replace question word for word, through the same `create_workspace` as `syn init`. Unlike `syn init`, where no input counts as no, cancelling in the app creates no folders and doesn't change `workspace.txt`.
  - **Same words as `syn init`.** `workspace.py` holds `init`'s result lines, so `syn init` prints them and `/init` shows them. `syn init`'s output is unchanged. In the app the first line starts with `✓`, the folders sit in two columns, and `Next: …` is a `›` hint. Afterwards the status line and the command history both follow the new workspace.
  - **`/doctor`'s Fix line** now says `run /init "<path>"` in the app. `syn doctor` keeps `syn init`.

- **Details settled for #57** (the owner chose the triage defaults, 2026-10-19):
  - **Read as `syn` reads them.** `/compound show`, `list` and `history` go through the same `build_parser()` as `syn`, so their options and checks can't drift apart. Words are split as PowerShell splits them: quotes group words and are removed, and backslashes stay as typed, so `/compound list --csv "D:\Lab tables\june.csv"` works. A typing mistake shows argparse's reason as `✗ …`, then `› Type /help compound show to see how it's used.` `/compound` alone shows `/help compound`, and `/compound show -h` shows `/help compound show`. Other subcommands say `✗ /compound add isn't in the app yet. For now, run syn compound add in PowerShell.` until #58 and #59.
  - **The card.** The title is bold. The first fields come as names in muted grey, with values in a second column. Each group (Characterisation, Handling, Safety, Batches, Spectra) has a bold heading with a blank row above it. Batches and Spectra are aligned columns, as in `syn`. The purity flag starts with the caution `!`, and the unverified rule's `Warning:` with `?`. `› Still missing:` lists one item per row, and `✓ Nothing missing.` shows when nothing is missing. A long value wraps under its own column.
  - **The table.** It has a bold heading row with a thin line under it, `-` in blank cells, and archived rows in muted grey (they still say `(archived)`). The count line is the same as `syn`'s and sits below the table. The label column takes most of the spare width and wraps, and at 80 columns the molar-mass heading wraps over two rows.
  - **The change log.** `History of SYN-001: …` is bold. Each row shows the time in muted grey, then the field, then `old → new`, oldest first.
  - **Dates.** Every date the app shows is DD/MM/YYYY: change times, batch dates, risk assessments, the date a spectrum was added, and any date inside a logged value. `syn` keeps YYYY-MM-DD and `->`, so its output is unchanged.
  - **Words naming `syn`.** Shared messages that name a command the app now has point at the app's own: `Run "/compound list" to see every ID.` and `Run "/init" to create one.` The empty-register line keeps `syn compound add` until #58. Every other message is word for word the same as `syn`'s.
  - **Saving with `--csv`.** The file is saved where decision 0015 says, after the table. An existing file brings up `syn`'s question, `<path> already exists. Replace it? [y/N]`, in answering mode. No gives `Kept the existing <path>. The table was not saved.` Esc or Ctrl+C gives `‹ Cancelled. The table was not saved.` Yes, or a new file, gives `✓ Saved the table to <path>`. The wording lives in `tables.py`, shared with `syn`.

- **Details settled for #58** (the owner chose the triage defaults, 2026-10-19):
  - **Same rules as `syn`.** `/compound add` and `/compound edit <ID>` read their options through `build_parser()`. With no options they ask the shared guided questions (decision 0014), group questions included. With options they ask nothing except the confirmations, and `add` without `--label` gives `syn`'s error. `add_compound` and `edit_compound` write the register and change log, as they do for `syn`.
  - **Every confirmation comes first.** The app asks one question at a time, so it can't answer `edit_compound`'s confirm function while the change is being checked. `planned_changes()` in `compounds.py` runs the same checks and returns the changes without saving. The app asks `Change the … from "…" to "…"? [y/N]` for each set value, in field order, then calls `edit_compound` with the answers. A refused value or an Rf without its solvent is shown as `✗ …` before anything is asked. Esc or Ctrl+C at any question gives `‹ Cancelled. Nothing was changed.` (or `Nothing was added.`) and saves nothing.
  - **Kept lines.** Each `Kept the … as "…".` is plain text, shown right after the no, as in `syn`.
  - **After saving.** `✓ Added SYN-001: …` or `✓ Saved 2 changes to SYN-001: …` is followed by the filled fields, in the card's two-column layout with bold group headings and the purity flag. After adding comes `› Add more details later with "/compound edit SYN-001".` `Nothing was changed.` is plain text.
  - **Words naming `syn`.** In the app, `"syn compound add"` and `"syn compound edit …"` in shared messages become `"/compound add"` and `"/compound edit …"`. That covers the empty-register line, the `--label` error and the hint. The words live in `compound_text.py` and `compound_questions.py`, shared with `syn`, whose output is unchanged.

## Consequences
- Synthase gains its second run-time dependency. A new Textual major version needs a deliberate upgrade, because the pin stops at 9.
- `workspace.current_workspace` now raises two kinds of `WorkspaceError`: `NoWorkspace` and `WorkspaceMissing`. The status line can then tell the two apart, and the plain command line's messages don't change.
- Later M2 issues add their own widgets and styles to the same stylesheet and theme, following the design canvas's handoff spec.
