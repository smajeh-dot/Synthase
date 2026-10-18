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

## Consequences
- Synthase gains its second run-time dependency. A new Textual major version needs a deliberate upgrade, because the pin stops at 9.
- `workspace.current_workspace` now raises two kinds of `WorkspaceError`: `NoWorkspace` and `WorkspaceMissing`. The status line can then tell the two apart, and the plain command line's messages don't change.
- Later M2 issues add their own widgets and styles to the same stylesheet and theme, following the design canvas's handoff spec.
