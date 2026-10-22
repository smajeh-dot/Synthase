# 0028: Tab completion and the up-arrow history

## Context
Decision 0027 left Tab completion and the up-arrow history to #118, with their wording from the F1 design handoff: ghost text and `Tab completes` for one match, a pop-up for several (`N matches`, `n of N`, `▸`, up to 8 rows, `Tab next · Enter chooses · keep typing to narrow`), and `history 2 of 6 · ↑ older · ↓ newer`. The handoff didn't say where the history count starts, what the history keeps, or how several keys behave in the pop-up. The owner chose every default in #118's triage on 2026-10-22. Built together, the two came to about 700 changed lines, so the history was split into #121.

## Decision
**Tab completion** (#118)
- One function in the command table, `commands.completions`, gives what Tab can offer for the word at the end of the line: the next command word, or what a later issue supplies for a part typed after the command words.
- That supply is `SynthaseApp.sources`, keyed by the part's `Arg.name` (`id`, `name`, `value_name`, `field`). Each is a function given the words before it, so the one `id` source tells `exp show` from `compound show` by the first word. Only parts read as one word are completed.
- **One match:** the rest of the word shows as ghost text in `faint`, and the top rule says `Tab completes`. Tab takes it. There is no ghost text on an empty word: Tab still fills the one match.
- **Several matches:** Tab opens the pop-up just above the bar, with `▸` on the first. Each row is the word in the accent colour, then, in muted text, the help line of a whole command, or the help heading of a first word alone (`exp   Experiments`). An ID or name has no text after it.
- **Keys in the pop-up:** Tab moves down and Shift+Tab up, going round from the last row to the first. ↑ and ↓ move through the pop-up while it is open. Typing narrows it, and it closes when nothing matches. Enter fills the line and never runs it. Esc closes the pop-up and keeps the line. Ctrl+C closes it and clears the line.
- **A chosen word** is followed by a space when more can follow (`exp `, `help `, `compound show C001 `), and not when it can't (`exit`, `exp show all`).
- Tab with no match does nothing. Tab on the error question does nothing.
- Until #121 is built, the first-open hint is `Tab completes · Ctrl+D exits`. As in decision 0027, it names no key that does nothing yet.

**Up-arrow history** (#121)
- The first ↑ shows the newest line as `history 1 of 6`, and each ↑ counts up to the oldest. ↓ past the newest gives back the line that was being typed.
- Every non-empty line run at the `>` prompt is kept, mistyped ones included. Answers to questions (`y` or `n`) are not kept. The same line run twice in a row is kept once. Only the latest 1,000 lines are kept, the same limit as the output.
- With a project, the lines go in `data\.history`, plain text, one per line, so they come back next time. Only the window holding the project's lock reads or writes the file. With no project, or with the project open in another window, they last for the session only.

## Consequences
- `commands.complete` stays as the list of words, so the table's existing tests keep working.
- #104, #105 and #106 add their IDs, value names and fields to `SynthaseApp.sources`; their Notes say so.
- #121 carries the history's code and tests, built in #118's session, as a patch in the issue.
- #102: once #121 is built, `project create` also switches the session's history to saving.
- #119's ASCII fallback already maps the pop-up's `▸` and rounded corners, and draws its current row in reverse video.
