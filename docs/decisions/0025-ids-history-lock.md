# 0025: Data IDs, the history log and the project lock

## Context
Every data command needs the same three things: the next free ID (spec C80–C84, C167), a record of every change with a way to notice hand-edits (C171), and a guard against two Synthase windows changing one project at once (C173). Decision 0023 put each project's data in `data\`, one file per kind, with the counters in `data\synthase.toml`. The owner chose all the triage defaults for #99 on 2026-10-21.

## Decision
**IDs**
- An ID is one capital letter and at least three digits: `E001`, `C014`, and `E1000` after `E999`. Experiments live in `experiments.toml`, compounds in `compounds.toml`; analysis records (A) come with F4.
- `data\synthase.toml` holds `[counters]`, the last number issued per letter. The next ID is the counter + 1, or the highest ID found in that kind's file + 1, whichever is higher, so an entry added in Notepad is never overwritten.
- Counters only go up, so an ID whose entry was deleted in Notepad is never reused.
- The counter is saved only after the entry that used it, when the walk-through has finished. A walk-through cancelled with Ctrl+C uses no ID. If Synthase stops between the two saves, the "highest found" rule still prevents reuse.

**History**
- `data\history.jsonl` gets one JSON line per change, with `ts`, `action`, `id`, `name`, `old`, `new`, `file` and `sha256` (the hash of `file` after the change, or `null` if it is gone). It is only ever added to. Symbols such as `µ` are written as they are, so the file stays readable in Notepad.
- **Issuing an ID is logged** with the action `issue_id`, because saving the counter changes `synthase.toml`. Without it, the next start would report `synthase.toml` as changed outside Synthase. This adds one action to the spec's list in C171; the owner approved it on 2026-10-22.
- On start, each data file (`synthase.toml`, `experiments.toml`, `compounds.toml`) is compared with the last hash logged for it. A file that differs, is new or has gone is logged as `external_edit` and reported once:
  - `data\experiments.toml was changed outside Synthase. The change is noted in the history.`
  - `data\compounds.toml was deleted outside Synthase. The deletion is noted in the history.`
- A broken line in `history.jsonl` is refused with decision 0024's message, naming the line.
- Times are stored as ISO 8601 with the UTC offset (`2026-10-21T14:32:07+01:00`) and shown as `2026-10-21 14:32:07`.

**Lock**
- While a project is open, `data\.synthase.lock` holds the window's process ID. Another window refuses: `This project is already open in another Synthase window. Close it there first. If no other window is open, delete data\.synthase.lock and try again.`
- A lock whose process has stopped, or that can't be read, is cleared and taken. On Windows, whether a process is running is asked of Windows itself: Python's usual check (`os.kill(pid, 0)`) would end that process on Windows.
- A window only ever removes its own lock.

## Consequences
- Because each kind is one file, a hand-edit to `experiments.toml` is logged as one change to the whole file, not per experiment.
- Windows can give a closed window's process ID to a new, unrelated program, which could make a leftover lock look live. The message says how to clear it.
- Taking the lock when the app opens a project, and showing the hand-edit messages, are the app's job (#100).
