# 0027: The app shell: Textual, its layout and start-up

## Context
Decision 0020 made Synthase a full-screen app inside the PowerShell window, styled from the owner's design system, and left the library to be chosen when the shell was built (#100). The owner had the F1 screens designed in a Claude Design session on 2026-10-22. The design canvas and its handoff spec are kept outside the repo, as decision 0016's were. This record keeps what the build needs. The owner approved the layout and chose every default in #100's triage on 2026-10-22, including splitting the issue three ways to keep each PR near 400 lines.

## Decision
**Library**
- **Textual** (`textual==8.2.8`) is a run-time dependency, pinned like `tomlkit`. Textual and its six dependencies (Rich, markdown-it-py, mdurl, mdit-py-plugins, linkify-it-py, typing_extensions) are all pure-Python wheels (`py3-none-any`), checked on 2026-10-22, so they install on Windows ARM64 with Python 3.13 and no compiler.
- All colours live in one Textual theme (`synthase/theme.py`), the design system's tokens unchanged from decision 0016. All sizes and styles live in `synthase/synthase.tcss`. Python never names a colour.

**Layout**
- The output fills the window and scrolls, newest at the bottom, keeping the latest 1,000 messages. Under it is the bottom block, always 4 rows: a thin rule, the command bar (`> `), a thin rule, and the status line. No header or footer.
- Below 100 columns the screen has the class `-narrow`: `help` drops to one column.
- The status line leads with the context, then the folder: `Aspirin synthesis · C:\Users\you\Lab\aspirin`, and later `Aspirin synthesis/E002 · …`. A long folder is shortened only when it doesn't fit: the home folder becomes `~`, then middle folders become `…`.
- Every message kind has its own glyph, so no meaning depends on colour alone: `>` echo, `✓` success, `✗` error, `i` notice (new), `›` hint, `‹` cancel. Replies indent 2 cells and wrapped lines hang at 4. (Changed by decision 0034: success and error now both start with `●`, in green or red.)
- An error with suggestions is two lines: `✗ Unknown command 'epx'.`, then `› Did you mean: exp, exit?`. The wording is the command table's, unchanged; only the line break and the styling are added. Several `Usage:` lines hang at 4 under the first.
- `help` lists the commands under their five headings with a rule, the usage in a 52-cell column. Command words are in the accent colour, `<required>` parts plain, `[optional]` parts faint. It closes with `› For every form of one command, type help <command>, e.g. help exp.` `help <command>` shows `Usage:` and `Example:` in a 9-cell label column.

**Wording** (approved by the owner on 2026-10-22)
- Welcome line: `Synthase 0.2.0  ·  type 'help' for commands`. The version comes from the package, so the line never goes out of date. The spacing is the spec's.
- Placeholder: `Type a command, e.g. help`.
- First-open top-rule hint: `Tab completes · ↑ ↓ history · Ctrl+D exits`. Until #118 adds Tab and history, only its `Ctrl+D exits` part is shown, so the hint names no key that does nothing.
- Scrolled up: `scrolled up · 84 newer lines below · PgDn to go back down`.
- Foreign `data\` folder: `This folder's data\ folder wasn't made by Synthase, so Synthase won't write to it. Start Synthase in another folder.`
- Status-line states: `› No Synthase project here. Type 'project create' to start one.`, `✗ data\ isn't a Synthase folder`, `✗ open in another Synthase window`, `✗ data\experiments.toml has a mistake`.
- A data command whose issue isn't built yet: `✗ exp show isn't built yet.`, with the command's own words. Each later issue removes its command from this list.

**Start-up**
- **A project:** the app takes the lock, checks each data file can be read, then shows each outside-edit notice once. A lock held by another window or a broken data file shows its message (decisions 0024, 0025). When a file is broken, the status line shows the folder only, and the lock is not taken.
- **No project:** `› No Synthase project here. Type 'project create' to start one.`
- **A `data\` folder that isn't Synthase's:** the refusal above. Synthase writes nothing there.
- In every refused state, `help` and `exit` still work. A data command repeats the state's message: the no-project message, the refusal, the lock message or the broken-file message.

**Keys**
- Enter runs the line; an empty line does nothing. Ctrl+C clears the line. `exit` or Ctrl+D leaves and releases the lock. PgUp and PgDn scroll the output (new keys, approved).

**Unexpected errors** (owner decision D4)
- The app never shows a Python traceback. An unexpected error asks `Failed. Would you like the error log? [y/n]` in answer mode: a heavy rule titled `Answering <command> · Enter means no · Ctrl+C cancels`, with the placeholder `y or n`.
- `y` or `yes`, in any case, prints the latest log entry under the heading `Error log · data\error.log`, then `› The log stays in data\error.log.` Anything else, Enter and Ctrl+C included, prints nothing more. Either way the app carries on.
- This is the only y/n question in F1, an exception to the spec's "no y/n prompts" (spec Section 9, D27).
- The entry is added to `data\error.log`: a line with the time and the command, a line `Synthase <version> · <system> · Python <version>`, then the traceback. Entries are separated by a blank line.
- When the folder has no project, Synthase writes no log file. `y` still prints the entry, under the heading `Error log` alone, without the closing line.

## Consequences
- Tab completion and up-arrow history are #118, and the older console (ASCII fallback, 16-colour theme) is #119. Until #118, Tab does nothing, rather than moving the focus off the command bar.
- The answer mode built here for the error question is what the walk-throughs (#101) reuse.
- Tests drive the app headless with Textual's own test pilot, so no new dev dependency is needed. Both Windows checks (`ci` and `ci-arm64`) run them.
- CI no longer runs `synthase` itself, because it now opens the full-screen app and would wait for input. It still checks that a new window finds `synthase` on the PATH.
