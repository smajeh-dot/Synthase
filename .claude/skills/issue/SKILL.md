---
name: issue
description: Use when the owner says "let's work on issue #N", "pick up #N", "triage #N" or "/issue N", or otherwise names a GitHub issue to start work on in this repo, and whenever the owner makes a decision that could change issues already open.
argument-hint: [issue-number]
allowed-tools: Bash(gh api *) Bash(git fetch *) Bash(git branch *) Bash(git log *) Bash(git ls-tree *) Bash(git rev-list *) Bash(git status *) Bash(python -m pytest *) Bash(ruff check *) Bash(python -m venv *) Bash(.venv/bin/*) Read Grep Glob
---

# Starting work on an issue

The first reply to "let's work on issue #N" is a **triage**, not code. It shows the
owner exactly what the issue contains and which decisions are theirs, so the
autonomous part of the work can then run without stopping.

Issue: `$ARGUMENTS` (if empty, take it from the owner's message).

**REQUIRED:** the `github-workflow` skill's session start still applies. This skill
replaces its step 4 (Read) and decides what the owner sees. Before the triage, do
step 3 (identity) and step 5 (baseline: `python -m pytest` and `ruff check .`).
Do step 2 (the branch) after the owner replies. Name the branch in the triage.

A fresh session has no test environment. If `python -m pytest` reports
`No module named pytest`, set one up first (`.venv` is gitignored):

```bash
python -m venv .venv && .venv/bin/python -m pip install -q -e ".[dev]"
.venv/bin/pre-commit install
.venv/bin/python -m pytest -q && .venv/bin/ruff check .
```

## 1. Gather (read-only)

GraphQL is blocked in Claude sessions, so `gh issue view` and `gh pr list` fail. Use
REST through `gh api`:

```bash
R=repos/smajeh-dot/Synthase
gh api $R/issues/<N> --jq '{title, state, labels: [.labels[].name], body}'
gh api $R/issues/<N>/comments --jq '.[] | "--- \(.user.login) \(.created_at)\n\(.body)"'
gh api $R/issues/<N>/timeline --jq '.[] | select(.event=="cross-referenced") | .source.issue | "#\(.number) \(.state) \(if .pull_request then "PR" else "issue" end) \(.title)"'
gh api "$R/pulls?state=open" --jq '.[] | "#\(.number) \(.head.ref) \(.title)"'
gh api "$R/issues/comments?sort=created&direction=desc&per_page=30" --jq '.[] | select(.body | contains("Session note")) | "--- \(.issue_url | split("/") | last) \(.created_at)\n\(.body)"'
git fetch origin && git branch -r --list "origin/claude/*/<N>-*"
```

Then:
- For each "Depends on #M" in the issue, check `gh api $R/issues/M --jq .state`.
- If a PR exists for the issue, read its body (`gh api $R/pulls/<P> --jq .body`) to see
  which "Done when" boxes are already ticked.
- Session notes: use the latest note on this issue, or the most recent one in the
  repo if this issue has none. Also scan the older notes from the last command:
  an owner item can drop out of a later note without being done. For each
  "Waiting on owner" item, check on GitHub whether it has been done.
- Open PRs can clash with this work, for example by claiming the next
  `docs/decisions/` number. Note any clash.
- Read the `docs/decisions/` entries that touch this work.
- Read the code where the change will land (Grep, Glob, Read). Change nothing.

If the issue is closed or does not exist, say so and stop.

## 2. Output the triage

Produce these sections, in this order, in plain text with no emojis:

```markdown
## #N: <title>
<One plain sentence: what this issue delivers.>
**Part of:** #parent, step N of its build plan · **Labels:** … · **Size:** S (<100 lines) / M (100–300) / L (300–400; over 400 means split) · **Status:** not started / in progress (branch, PR link) · **Branch:** `claude/<type>/<N>-<short-description>`

### What it asks for
1. <One requirement per line> [stated] or [inferred: why]

### Done when
<The issue's own checklist, copied word for word, each item marked:>
- [ ] <item> (not started)
- [ ] <item> (partly: what's left)
- [x] <item> (met: evidence)
<Add an item only if something checkable is missing: `- [ ] [proposed] …`.>

### Context
- Latest session note: next step, and each "waiting on owner" item: done / still waiting
- Depends on: #M open / closed (open means this issue is blocked)
- Decisions that apply: `docs/decisions/NNNN-…`
- Baseline tests: N passed (quote any failure)

### Where it lands in the code
- `path/to/file.py:line`: what changes there

### Needs you
| # | Decision or input | Why it's yours | Needed | Claude's default |
|---|---|---|---|---|

### Risks and out of scope
- …

### Plan
1. <Step>: autonomous / checkpoint with you

### Suggested /goal
/goal …
```

### What goes in "Needs you"

The table holds the choices the owner makes better than Claude: what Synthase
looks like and says to the person using it, and what only the owner knows or can
reach. Every row is one of these kinds:

- **Wording:** command names, usage lines, prompts, help text, messages and
  explanations of jargon. Wording the spec gives is used word for word and needs
  no row. Anything else, or a spec default the owner hasn't confirmed (C174 to
  C184), gets a row with the proposed wording in it, so the owner can approve it now.
- **Look:** layout, colours, table shape and what the screen shows. Put a sample
  of the output in the row. If the look needs several rounds of feedback, plan a
  checkpoint with the owner before the goal is set.
- **What the user meets** that the spec and the issue leave open: what a command
  does, asks or refuses, described as the user would see it. This includes
  contradictions between the issue, its comments and the code, and anything
  labelled `needs-decision`.
- **Scientific values:** a constant, unit list, threshold or model formula the
  work needs. Synthase has no built-in constants (spec C73), so it comes from the
  spec or the owner, never from Claude's own knowledge.
- **Real lab file formats:** if the work reads a lab file, ask for a blank-plate
  export or a description of the format. Never ask for real data.
- **Windows checks:** anything that must be run on the owner's laptop in PowerShell
  (sessions run on Linux).

Coding decisions are Claude's: how the code is structured, which library to use,
file layout, internal names, how errors are handled inside the code, how it is
tested. Make them, and name any that matter in the Plan.

Keep a row only when both are true: the owner's answer changes what they see or
use (or supplies something only they have), and the owner could reasonably choose
something other than the default. Any other row comes out, and Claude uses its default.

Owner actions on the GitHub website (merging, deleting branches, settings) go in
the "Your turn" list, not in this table.

Give every row a default so the owner can reply "use your defaults". If no row is
left, write *Nothing. This can run autonomously.*

### Writing the `/goal` line

`/goal <condition>` keeps Claude working turn after turn until a separate,
smaller model judges the condition met. That model **reads only the
conversation**. It can't run commands, so the condition must:

- Name each "Done when" item and how its evidence will be shown.
- Require `python -m pytest` to exit 0 and `ruff check .` to be clean, with the
  output shown.
- Require the work committed and pushed on the issue's branch, a draft PR open
  with its "Done when" boxes ticked and its URL printed, and the session note
  posted on the issue.
- Cover only the autonomous steps. Checkpoints with the owner happen **before**
  the goal is set, or between two goals. A goal that waits on the owner stalls.
- Never include merging. Merging is the owner's step.
- End with a bound: `or stop after 30 turns`.

Example (for an invented issue):

```
/goal Issue #99 is done: `add m_crude 2.100 g` stores the value as `2.100` and `show` prints it unchanged, and the hand-worked tests in tests/test_values.py pass; `python -m pytest` exits 0 and `ruff check .` is clean, both with output shown; the work is committed and pushed on claude/feat/99-add-values; a draft PR closing #99 is open with every "Done when" box ticked and its URL printed; the session note is posted on #99. Or stop after 30 turns.
```

## 3. Stop

End with the github-workflow "Your turn" list. It holds every outstanding owner
item found while gathering, and always includes:

- **Answer the "Needs you" items** in chat, or reply "use your defaults". Claude needs these
  before it starts.
- **Start the work:** paste the `/goal` line above, edited if you like, or say
  "go step by step".

Then end the turn. Don't edit, commit or push anything until the owner replies.

## After an owner decision

Whenever the owner decides something, in the triage or later in the session, that
could change an issue already open:

1. Record it in `docs/decisions/` (see the `github-workflow` skill).
2. List the open issues:
   `gh api "$R/issues?state=open&per_page=100" --jq '.[] | select(.pull_request | not) | "#\(.number) \(.title)"'`.
   Read each one the decision could touch: the later steps of the same build plan
   (#92 for F1), issues the decision names, and issues using the same commands,
   files or wording.
3. Edit each affected issue so it matches the decision: its title, "Done when",
   "Out of scope" and Notes. Write the new body to a file in Claude's scratchpad,
   then `gh api -X PATCH $R/issues/<M> -F body=@<file>`.
4. Comment on each edited issue: what changed, and which decision record caused it.
5. Tell the owner which issues changed, one line each, and list them under "Done"
   in the session note.

If the decision changes no open issue, say so in one line.
