---
name: github-workflow
description: Use at the start of every Synthase session and before any git or GitHub action in this repo - branching, staging, committing, pushing, opening or updating pull requests, creating issues, tagging, or when asked to "get it onto main", "carry on", "just delete it", or to commit files that might hold lab data, personal information or secrets.
---

# Synthase GitHub workflow

## Overview
Every change follows one path: **one issue → one branch → one draft PR → the owner squash-merges.** GitHub, not the chat, is the record of what's done, what's in progress and why.

**Breaking the letter of these rules is breaking their spirit.** The owner chose them to stop a previous project from becoming disorganised.

## Rule zero: the repo holds the tool, never the science
| Commit | Never commit |
|---|---|
| Code, tests, help text, docs | Plate reader exports, plate maps for real runs, results, figures |
| **Invented** test data (hand-worked examples, generated fake plates) | The compound register, notebook entries, risk assessments, write-up, literature notes |
| The config **template**, with placeholder values marked `UNVERIFIED` | The real config with verified values |

Also never commit:
- real names, the school's name, email addresses or other personal information
- tokens, keys or `.env` files
- files over 1 MB

GitHub usernames and the Claude attribution lines in commits and PRs are fine. They show who did what.

Any real file the owner shares (for example a plate reader export) is format reference only. A committed copy must be a blank-plate export or hand-built with invented numbers.

## Session start
1. **Know the issue.** If the owner named one, use it. If not, propose the next open issue in the current milestone (the lowest-numbered milestone that still has open issues) and **wait for a yes**. A "next step" in an old session note is not a yes. One session works on one issue. If no issue exists for the work, create it first (template below).
2. **Get onto the issue's branch** (see Branch names). Run `git fetch origin`, then:
   - If the issue's branch is already on GitHub (an earlier session started it), check it out and merge `origin/main` into it.
   - Otherwise create it from `origin/main`: `git checkout -b <name> origin/main`.
   - Claude can't delete branches (GitHub refuses with a 403 error). So after the first push, check the random branch the session started on. If it holds nothing beyond `main` (`git rev-list --count origin/main..origin/<random-branch>` prints 0), add it to the owner's "Your turn" list:
     - delete it at Repo → **Branches** → the bin icon next to it
     - why: it's empty, and leaving it creates branch sprawl
   - If GitHub refuses the push to the readable name, stay on the random branch and tell the owner. The PR title still names the work.
3. **Identity.** `git config user.email` must be a noreply address. If it isn't, stop and tell the owner.
4. **Read.** The issue, including its latest session note, the PR checklist, the latest CI result, and any relevant `docs/decisions/` entries.
   - Check on GitHub whether each "Waiting on owner" item from the last note has been done.
   - Open the session by telling the owner which items are still outstanding (see Working with the owner).
5. **Baseline.** Run the tests before changing anything, so you know what was already broken.

## Branch names
Every branch name says what kind of work it is and which issue it is for. All work happens in Claude sessions; the owner never commits locally.

```
claude/<type>/<issue>-<short-description>
```

| Part | Values |
|---|---|
| type | The same types as commit messages: `feat`, `fix`, `test`, `docs`, `refactor`, `chore` |
| issue | The issue number |
| short-description | 2 to 5 plain words, lowercase, joined by hyphens |

Examples: `claude/feat/6-compound-register`, `claude/fix/14-dmso-check-rounding`, `claude/docs/9-windows-setup`.

- **One branch per issue,** reused by every session that works on it.
- **Always created from `main`.** GitHub deletes it automatically when the PR merges.
- **Follow-up work** after a merge gets a new issue and a new branch.

## During the session
- **Stage by name only:** `git add path/one path/two`. Never `git add .`, `-A`, `-a` or `commit -a`.
- **Before every commit, review the staged changes:** `git diff --staged`, looking for rule-zero material (real names and the school's name included), debug leftovers, hard-coded scientific constants and files outside the issue's scope. Unstage and fix anything you find.
- **Commit messages use Conventional Commits:** `type(scope): description`, in the imperative and under 72 characters.
  - Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`. The scope is the tool or area, e.g. `yield`, `plate`, `ci`.
  - Add a body explaining *why* when that isn't obvious.
  - Banned: `update`, `fix stuff`, `WIP`, `changes`, `misc`.
- **What a commit contains:** one logical step, with its tests passing. Formatting-only or file-move changes go in their own commit.
- **Push after every commit.** The cloud container is temporary.
- **Open a draft PR after the first push.** Base `main`, Conventional title (it becomes the squash commit on `main`), body from the PR template below.
- **Stay in scope.** For a new bug or idea, search the existing issues, then open a new one. Don't fix it on this branch. If you already changed out-of-scope code, revert it from this branch and paste the diff into the new issue so nothing is lost. **Never create a branch for side work.**
- **Follow the config rule.** Every scientific constant lives in the config, never in code.

## Session end
1. Make sure everything is committed and pushed. `git status` should show nothing except untracked files that rule zero keeps out. Name those files to the owner: they exist only in this container, so the owner should keep their own copies.
2. Report the latest test results exactly. If anything fails, quote the failure.
3. Update the PR checklist. Mark the PR **ready for review** only when every "Done when" box is ticked and CI is green. Until the CI workflow exists, the tests passing locally stand in for CI, and you say so in the PR.
4. Post a **session note** on the issue, every session, even when the work is finished:
   ```
   **Session note (YYYY-MM-DD)**
   Done: …
   Not done: …
   Next step: …
   Waiting on owner: … (or "nothing")
   ```
5. Make sure every decision made during the session is recorded in `docs/decisions/NNNN-short-title.md`, with three parts: Context, Decision, Consequences. Write each one when the decision is made, not at the end.
6. Tell the owner in chat: the PR link, then a nudge for every item waiting on them (see Working with the owner).

## Working with the owner
The owner wants to be held accountable for their own steps. Never assume they know what to do, or that they have already done it. Every message that ends with something waiting on the owner closes with a **"Your turn"** list:

```
**Your turn**
- [what to do]: [exact place: a link, or a click path such as Repo → Settings → General]. [Why it matters, in one plain sentence.]
```

- **Check, don't assume.** After the owner says they've done something, check it on GitHub where you can, and report what you found. For example, after a merge, check it was a squash merge and that the branch was deleted.
- **Carry items forward.** Unfinished owner items stay in every session note's "Waiting on owner" line, and are repeated at the start of the next session until they're done.
- **Raise a risky or rule-breaking choice once.** Say plainly what it costs, then respect the owner's decision and record it in `docs/decisions/` if it changes a rule.
- **Keep the tone gentle:** a reminder, not a telling-off. One line per item. Explain any jargon. Steps are for the GitHub website or Windows PowerShell only.

## Merging, releases and tags: the owner's alone
- **Never merge a PR, enable auto-merge, push to `main`, create a tag or create a release.**
- When asked to "get it onto main", make the PR ready, give the link, and say the **Squash and merge** click is the owner's by project rule. The owner can change the rule by editing this skill.
- For a release, prepare a PR titled `chore(release): vX.Y.Z` that bumps the version in `pyproject.toml`.
- Versions and tags:
  - **Milestone release:** M1 = `v0.1.0`, M2 = `v0.2.0`, and so on.
  - **Fix between milestones:** bump the last number, e.g. `v0.1.1`.
  - **Lab tag:** `lab-YYYY-MM-DD` on `main`, before real data is analysed for the write-up. The owner creates it on the GitHub website as a pre-release (see `owner-setup.md`).

## Tracking
- **Issue template.** Title in Conventional style. Body with four headings:
  - `## Goal`: one or two sentences
  - `## Done when`: a checklist, always including a hand-worked test example
  - `## Out of scope`
  - `## Notes`
- **Labels: use only this fixed set; never invent new ones.** Every issue gets one type and any flags. Add an area when the issue touches the app itself.
  - Type: `feature`, `bug`, `test`, `docs`, `infra`
  - Area: `chemistry`, `microbiology`, `interface`, `data`
  - Flags: `blocked`, `needs-verification`, `needs-decision`
- **Milestones:** M0 Foundations, M1 First commands, M2 Terminal interface, M3 Data pipeline, M4 Results and record keeping.
  - Milestones are ordered phases with **no due dates**, because sessions happen whenever the owner has time.
  - Work order comes from milestone order. Never set or suggest deadlines.
- **`ROADMAP.md` holds the full feature list.** An item becomes an issue only when it's scheduled.
- **PR template** (once `.github/pull_request_template.md` exists, use that file instead). Body sections:
  - What and why
  - `Closes #N`
  - How it was tested: the hand-worked examples, plus the test output
  - Config template changed? Values and their verification status
  - Windows check: are the PowerShell setup and run instructions still correct?
- **Size limit:** one task per PR. Split it if it passes about 400 changed lines.

## If something leaked
A delete in a new commit is **not** a fix. History keeps the file, and on a public repo bots scan pushes within minutes. Work through these in order:
1. **Stop.** Tell the owner plainly what leaked and where.
2. **Secrets:** the owner revokes or rotates them first, before any cleanup.
3. **History:** an unmerged branch is rewritten only with the owner's yes, then pushed with `--force-with-lease`. If the material reached `main`, stop and let the owner decide.
4. **Remaining copies:** say plainly that old commits stay reachable by their ID until GitHub Support purges them, and that forks and clones may already hold copies.
5. **Prevention:** add the cause to `.gitignore`, the hooks or CI, in a normal PR.

## Red flags: stop and re-read this skill
| Thought | Reality |
|---|---|
| "The owner said get it on main, so I'll merge it" | Make the PR ready and send the link. The merge click is theirs. |
| "I'll put this side-fix on its own branch so it isn't lost" | Open an issue with the diff in it. Second branches are sprawl. |
| "I'll push it as WIP so it's saved" | Commit only working steps. If time runs out, say exactly what's broken in the session note. |
| "It's tiny, it doesn't need an issue or a PR" | Every change goes issue → PR. No exceptions for size. |
| "`git add .` is fine, I know what changed" | Stage by name. Untracked lab files and `.env` sit in the same folder. |
| "The work is finished, so no session note" | The note goes on the issue every session. |
| "This real file makes a better test fixture" | Fixtures are invented data only. |
| "The value is well known, so I'll hard-code it" | It goes in the config, marked `UNVERIFIED` until the owner verifies it. |
| "The owner said it's done, so it's done" | Check it on GitHub and say what you found. |
| "They probably know they need to click merge" | End with the "Your turn" list anyway. |

The owner's one-time GitHub setup is in `owner-setup.md` in this folder.
