# 0016: The full-screen app, its look and the `synthase` command

## Context
M2 adds a full-screen terminal app on top of the shared command layer (decision 0012). #52 builds the frame that every later M2 issue fills in: an output area, a command bar and a status line. The issue left open how the app opens and whether testing it needs a new dev dependency. A bare `syn` printing the help was settled in decision 0014.

The owner answered the triage on 2026-10-18 and then had the look designed in a separate design session. The design canvas and its handoff spec are kept outside the repo. This record keeps what the build needs. The owner approved the design and answered its open questions on 2026-10-18.

## Decision
- **Textual** (`textual>=8.2.8,<9`) becomes a run-time dependency, under the rule in decision 0003, because the app needs it. It is pure Python with pure-Python dependencies (Rich and a few small libraries), so it installs on Windows with Python 3.13 with no compiler. Windows CI installs it on every PR.
- **Opening the app:** typing `synthase` in PowerShell, from any folder, opens it. The setup script puts `synthase.cmd` next to `syn.cmd`. The plain command line (`syn`, `syn compound ...`, `syn doctor`, `syn init`) is unchanged. `/quit` or Ctrl+Q closes the app, and Textual's alternate screen puts the PowerShell prompt back as it was.
- **Tests:** no new dev dependency. The pilot tests run with `asyncio.run(...)`.
- **Layout,** from top to bottom: the output area fills the window and scrolls. Then comes the bottom block of 4 rows: a rule, the command bar, a rule, and the status line on its own plain row. That leaves 26 output rows at 120 × 30 and 20 at 80 × 24. There is no header and no footer. The rules are `#767676` with no side borders. A short key hint, `Ctrl+Q quits`, sits in the top rule until the first command (#53 adds `↑ ↓ history` to it).
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
  - Command history is kept between sessions, in a file in the workspace (#53).
  - Cancelling a question says `‹ Cancelled. Nothing was added.` (#56).
  - In answer mode the rules become heavy and blue, the question is the prompt in regular weight, and the `Answering …` title stays bold (#56).
  - The change log uses `→` in place of `->` (#57).
  - Every date shown on screen is DD/MM/YYYY. Dates inside file names stay YYYY-MM-DD, because Windows forbids `/` in file names (#57 onwards).
  - Success green next to error red is fine, because `✓` and `✗` and their words always tell them apart.

## Consequences
- Synthase gains its second run-time dependency. A new Textual major version needs a deliberate upgrade, because the pin stops at 9.
- `workspace.current_workspace` now raises two kinds of `WorkspaceError`: `NoWorkspace` and `WorkspaceMissing`. The status line can then tell the two apart, and the plain command line's messages don't change.
- Later M2 issues add their own widgets and styles to the same stylesheet and theme, following the design canvas's handoff spec.
