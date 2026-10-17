---
name: issue
description: Use when the owner says "let's work on issue #N", "pick up #N", "triage #N" or "/issue N", or otherwise names a GitHub issue to start work on in this repo.
argument-hint: [issue-number]
allowed-tools: Bash(gh api *) Bash(git fetch *) Bash(git branch *) Bash(git log *) Bash(git status *) Read Grep Glob
---

# Starting work on an issue

The first reply to "let's work on issue #N" is a **triage**, not code. It shows the
owner exactly what the issue contains and which decisions are theirs, so the
autonomous part of the work can then run without stopping.

Issue: `$ARGUMENTS` (if empty, take it from the owner's message).

**REQUIRED:** the `github-workflow` skill's session start still applies. This skill
replaces its step 4 (Read) and decides what the owner sees. Do steps 1 to 3 and the
step 5 baseline as that skill says, and put the baseline result in the triage.

## 1. Gather (read-only)

GraphQL is blocked in Claude sessions, so `gh issue view` and `gh pr list` fail. Use
REST through `gh api`:

```bash
R=repos/smajeh-dot/Synthase
gh api $R/issues/<N> --jq '{title, state, labels: [.labels[].name], milestone: .milestone.title, body}'
gh api $R/issues/<N>/comments --jq '.[] | "--- \(.user.login) \(.created_at)\n\(.body)"'
gh api $R/issues/<N>/timeline --jq '.[] | select(.event=="cross-referenced") | .source.issue | "#\(.number) \(.state) \(if .pull_request then "PR" else "issue" end) \(.title)"'
git fetch origin && git branch -r --list "origin/claude/*/<N>-*"
```

Then:
- For each "Depends on #M" in the issue, check `gh api $R/issues/M --jq .state`.
- If a PR exists for the issue, read its body (`gh api $R/pulls/<P> --jq .body`) to see
  which "Done when" boxes are already ticked.
- For each "Waiting on owner" item in the latest session note, check on GitHub
  whether it has been done.
- Read the `docs/decisions/` entries that touch this work.
- Read the code where the change will land (Grep, Glob, Read). Change nothing.

If the issue is closed or does not exist, say so and stop.

## 2. Output the triage

Produce these sections, in this order:

```markdown
## #N: <title>
<One plain sentence: what this issue delivers.>
**Milestone:** … · **Labels:** … · **Size:** S / M / L (vs the 400-line PR limit) · **Status:** not started / in progress (branch, PR link)

### What it asks for
1. <One requirement per line> [stated] or [inferred: why]

### Done when
<The issue's own checklist, copied word for word, each item marked:>
- ☐ not started / ◐ partly / ☑ met (evidence)
<Add an item only if something checkable is missing, marked [proposed].>

### Context
- Latest session note: next step, and each "waiting on owner" item: done ✓ / still waiting ✗
- Depends on: #M open / closed (open means this issue is blocked)
- Decisions that apply: `docs/decisions/NNNN-…`
- Baseline tests: N passed (quote any failure)

### Where it lands in the code
- `path/to/file.py:line`: what changes there

### 🙋 Needs you
| # | Decision or input | Why it's yours | Needed | Claude's default |
|---|---|---|---|---|

### Risks and out of scope
- …

### Plan
1. <Step>: 🤖 autonomous / 🙋 checkpoint with you

### Suggested /goal
/goal …
```

### What goes in "Needs you"

Anything that depends on the owner's judgement, knowledge or access. Check every
category:

- **Scientific values:** any constant, threshold or range. It goes in the config
  template as an `UNVERIFIED` placeholder; the owner checks it against the
  literature in their own workspace.
- **Real lab file formats:** if the work reads a lab file, ask for a blank-plate
  export or a description of the format. Never ask for real data.
- **Terminal look and wording:** layout, colours, table shape, help text, error
  messages, explanations of jargon. Plan a checkpoint where Claude prints sample
  output in chat for feedback.
- **Scope and behaviour** the issue leaves open, contradictions between the issue,
  comments and code, and anything labelled `needs-decision`.
- **Windows checks:** anything that must be run on the owner's laptop in PowerShell
  (sessions run on Linux).
- **GitHub website steps:** merging, deleting branches, settings, labels.

Give every row a default so the owner can reply "use your defaults". If no
category applies, write *Nothing. This can run autonomously.*

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
- Cover only the 🤖 steps. 🙋 checkpoints happen **before** the goal is set, or
  between two goals. A goal that waits on the owner stalls.
- Never include merging. Merging is the owner's step.
- End with a bound: `or stop after 30 turns`.

Example (for an invented issue):

```
/goal Issue #99 is done: `syn yield` prints theoretical and percentage yield to 3 s.f., and the hand-worked tests in tests/test_yield.py pass; `python -m pytest` exits 0 and `ruff check .` is clean, both with output shown; the work is committed and pushed on claude/feat/99-yield-command; a draft PR closing #99 is open with every "Done when" box ticked and its URL printed; the session note is posted on #99. Or stop after 30 turns.
```

## 3. Stop

End with the github-workflow "Your turn" list, which always includes:

- **Answer the 🙋 items** in chat, or reply "use your defaults". Claude needs these
  before it starts.
- **Start the work:** paste the `/goal` line above, edited if you like, or say
  "go step by step".

Then end the turn. Don't edit, commit or push anything until the owner replies.
