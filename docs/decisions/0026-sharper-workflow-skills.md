# 0026: Sharper workflow skills

## Context
Claude was applying the `github-workflow` and `issue` skills in the wrong places (#116). Three problems came up:
- Nothing said where hand-off or briefing notes for another Claude session belong, so they could end up in the repo. Decisions 0016 and 0019 already kept design hand-offs outside it, but only case by case.
- When the owner made a decision, issues already open that it changed were left describing the old plan until someone picked them up. After decision 0023, the later Ledger issues (#98 onwards) still described the old commands and folder.
- The triage's "Needs you" table filled up with rows the owner didn't need to see: coding choices the owner isn't placed to judge better than Claude, and rows with an obvious answer. The choices the owner is best placed to make, the wording and the look of what they type and see, are the ones Claude gets wrong on its own.

The owner set all three rules on 2026-10-22. In the triage they chose to keep scientific values, lab file formats and Windows checks in "Needs you", and to leave the open issues as they are until the next decision.

## Decision
- **Hand-off and briefing notes never reach the repo.** They are on rule zero's "never commit" list, and are never written inside the repo folder: they stay in the chat or in Claude's scratchpad.
- **Owner decisions reach the open issues.** After recording a decision, Claude reads the open issues it could change, edits each affected one, comments on it naming the decision, and tells the owner which issues changed. The `issue` skill holds the steps; the `github-workflow` session end points to them.
- **"Needs you" holds only what the owner is best placed to decide or supply:** wording, look, behaviour the user meets that the spec leaves open, scientific values, real lab file formats and Windows checks. Coding decisions are Claude's. A row stays only if the owner's answer changes what they see or use (or supplies something only they have) and the owner could reasonably choose something other than the default.

## Consequences
- Triages are shorter, and anything left in "Needs you" is worth the owner's time.
- Claude makes coding choices without asking, and names the ones that matter in the triage's Plan.
- Sessions that record a decision spend extra time reading and editing open issues; each edit is announced on the issue.
- Rows for scientific values, lab formats and Windows checks still appear, but only when an issue needs one.
- Skills load from the branch a session starts on, so the new rules apply only to sessions started after this change merges.
