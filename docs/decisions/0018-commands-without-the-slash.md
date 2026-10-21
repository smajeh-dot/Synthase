> **Superseded by [0020](0020-clean-slate.md).** It describes the retired app.

# 0018: Commands typed without the leading slash

## Context
Every app command started with `/`, but the slash carried no meaning: the app only used it to tell a command from anything else typed. The owner asked on 2026-10-20 to drop it, so `compound archive SYN-001` works as well as `/compound archive SYN-001` (#82).

## Decision
- **Both forms work.** The first word is matched against the command names after one leading `/` is removed, so `help compound` and `/help compound` do the same thing. Capitals and spaces are still ignored.
- **Everything the app shows uses the bare form:** the placeholder, the welcome line, `help` pages and hints, the status line, error messages, the titles of questions and the README. The text shared with `syn` names `compound ...` and `init` instead of `/compound ...` and `/init`.
- **Anything that isn't a command** says `unknown command, try help`.
- **Tab completes bare words,** including on an empty bar, where it lists every command. A command typed with a slash is completed with its slash, so what the user typed is never rewritten.
- **`quit` now quits.** This replaces the line in decision 0016 that said `quit` without the slash is unknown.
- **History:** lines already saved with a slash still work when stepped back to and run.
- `syn` is unchanged.

## Consequences
- A command word typed on its own line now runs. Nothing destructive is a single bare word, and `compound archive`, `remove-batch` and `unlink` still ask first.
- Old decision records keep their slashes. They describe what was decided at the time; this record is the current rule.
