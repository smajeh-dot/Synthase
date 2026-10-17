# 0005: Issue triage skill and /goal

## Context
The owner works through issues one per session and wants each session to open the same way: a clear account of what the issue contains, and a list of what only the owner can supply, such as feedback on the terminal's look, wording preferences and verified scientific values. Without a fixed format, each session summarises the issue differently and owner decisions surface halfway through the work.

Claude Code's `/goal` command keeps a session working until a separate, smaller model judges a completion condition met. That model reads only the conversation and can't run commands. A goal that waits on the owner stalls.

GitHub's GraphQL API is blocked in Claude sessions, so `gh issue view` and `gh pr list` fail. REST calls through `gh api` work.

## Decision
- **A project skill, `.claude/skills/issue/SKILL.md`,** runs when the owner names an issue. It replaces the Read step of the `github-workflow` session start and sets a fixed triage format: what it asks for, done when, context, where it lands in the code, needs you, risks, plan, suggested `/goal`.
- **The triage stops and waits for the owner.** Nothing is edited, committed or pushed until the owner answers the "Needs you" items or replies "use your defaults".
- **`/goal` covers only the steps Claude can finish alone.** Owner checkpoints happen before the goal is set. The condition names each "Done when" item, requires the tests and lint to pass with their output shown, requires a pushed branch, a draft PR and a session note, never includes merging, and ends with a turn limit.
- **The owner starts the goal** by pasting the suggested line. The skill doesn't start it.
- **GitHub is read through `gh api` (REST) only.**

## Consequences
- Every session on an issue opens the same way, and owner decisions come up front.
- The `github-workflow` rules still govern branching, commits, PRs and session notes. The triage skill doesn't repeat them.
- If the `github-workflow` session start changes, check that the triage skill still lines up with it.
- If GraphQL becomes available in sessions, the `gh api` calls still work and need no change.
