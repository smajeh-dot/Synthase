# Synthase

Before doing anything else in a session, load the `github-workflow` skill (`.claude/skills/github-workflow/SKILL.md`) and follow its session-start checklist. It sets how every change in this repo is branched, committed, tracked and merged.

When the owner names an issue to work on ("let's work on issue #N"), use the `issue` skill: triage the issue first and wait for the owner's reply before changing anything.

- This repo holds the tool only. Lab data, results, compounds, notes and anything from the owner's Synthase folder never go in it.
- Give every setup or run instruction for Windows PowerShell only.
- Synthase is AI-free: never add a model, API key or AI dependency.
- `docs/spec.md` is the feature spec: it defines every command and rule. `ROADMAP.md` lists what gets built and in what order.
- Command names, usage lines, help text and messages come from the spec or the owner, word for word. Never invent or change them.
