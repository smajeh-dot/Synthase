# 0022: The workflow rules after the feature spec

## Context
The workflow rules were written for the old app and its roadmap (#94). They had a "config rule" (every scientific constant lives in a committed config template, marked `UNVERIFIED` until checked), milestones M0 to M5 that set the work order and one release each, a lab tag before real data was analysed, and a `microbiology` label. The feature spec (decision 0020) has no config of constants: values are stored exactly as typed and nothing is built in (spec C73, D25). The old roadmap is gone, and on 2026-10-21 the owner chose not to use milestones (#92) and to keep the version at `v0.2.0` until they decide otherwise (#94). The owner also wants total control over the wording of the commands they will type.

## Decision
- **The spec is committed** as `docs/spec.md`, with the owner's name and personal paths removed and the owner's later decisions listed at its top. Every build session works from it. `ROADMAP.md` lists the features in order and points to the spec instead of repeating it.
- **The config rule is retired.** Synthase has no built-in scientific constants. If work seems to need one, a unit list or a model formula, it comes from the spec or the owner, through the triage's "Needs you" table. Rule zero now keeps the owner's Synthase folder out of the repo, and the commit review looks for built-in constants instead of hard-coded ones.
- **No milestones.** Each feature (F1, F3, F4) has a parent issue whose build plan lists its sub-issues in order; the next issue is the first open one. F1's plan is in #92. The issue triage shows "Part of" instead of a milestone.
- **Versions are the owner's call.** Synthase stays at `v0.2.0`. Claude never changes the version or proposes a number unprompted; when the owner asks for a release, Claude prepares the `chore(release)` PR with their number and the owner tags it.
- **No lab tag.**
- **The owner owns the wording.** Command names, usage lines, help text and messages come from the spec or the owner, word for word. Where the spec has a gap or an unconfirmed default (C174 to C184), Claude proposes wording in the triage and builds it only once the owner approves.
- **The `biology` label** replaces `microbiology`, matching the spec's disciplines.
- **The PR template** asks "Spec followed?" instead of "Config template changed?".

## Consequences
- CLAUDE.md, the `github-workflow` skill, `owner-setup.md`, the `issue` skill and the PR template are updated to match.
- Decision 0004 still mentions milestones among the behaviour the workflow skill holds; this record replaces that part.
- The milestones M0 to M5 on GitHub are closed by the owner; old issues keep their milestone as history.
- Issue #110 is still titled `chore(release): v0.3.0`. The owner chose to leave it as it is for now.
- The PR template change can only be checked on the website after it merges, so #94 stays open until the owner has done so.
