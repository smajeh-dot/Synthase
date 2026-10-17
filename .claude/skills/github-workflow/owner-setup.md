# Owner setup (one time)

Do these in order, on the GitHub website. You never need git on your laptop: all commits happen in Claude sessions.

## 1. Email privacy
GitHub → your profile picture → **Settings** → **Emails**:
- Tick **Keep my email addresses private**.
- Tick **Block command line pushes that expose my email**.

## 2. Pull request settings
Repo → **Settings** → **General** → **Pull Requests**:
- **Untick** Allow merge commits.
- **Untick** Allow rebase merging.
- Keep **Allow squash merging** ticked, and set its default message to **Pull request title**.
- **Tick** Automatically delete head branches.

## 3. Make the repo public
Repo → **Settings** → **General** → **Danger Zone** → **Change visibility** → **Public**.

Check the repo has nothing in it that rule zero forbids. The email on the initial commit is the one accepted exception.

## 4. Secret scanning
Repo → **Settings** → **Code security** (some accounts show this as **Advanced Security**):
- Turn on **Secret scanning** (also called Secret Protection) and **Push protection**.
- Turn on **Dependabot alerts**.

## 5. Protect `main`
Repo → **Settings** → **Rules** → **Rulesets** → **New ruleset** → **New branch ruleset**:
- **Name:** `protect-main`. **Enforcement:** Active. **Target branches:** Add target → Include default branch.
- **Tick** these rules:
  - Restrict deletions
  - Require linear history
  - Block force pushes
  - Require a pull request before merging, with **Required approvals set to 0**. You can't approve your own PR, so 1 would lock you out.
- Leave the bypass list empty.
- Once the CI workflow (#8) has run at least once, edit the ruleset: tick **Require status checks to pass** → **Add checks** → type `ci` and pick it. GitHub only lists a check after it has run.

## 6. Labels
Repo → **Issues** → **Labels**:
1. Delete every default label (`bug`, `documentation`, `duplicate`, `enhancement`, `good first issue`, `help wanted`, `invalid`, `question`, `wontfix`): **⋯** → **Delete**.
2. Click **New label** for each of these 12. Any colours will do.

| Group | Labels |
|---|---|
| Type | `feature`, `bug`, `test`, `docs`, `infra` |
| Area | `chemistry`, `microbiology`, `interface`, `data` |
| Flag | `blocked`, `needs-verification`, `needs-decision` |

## 7. Milestones
Repo → **Issues** → **Milestones** → **New milestone**, five times. Leave **Due date** blank every time.
1. `M0 Foundations`
2. `M1 First commands`
3. `M2 Terminal interface`
4. `M3 Data pipeline`
5. `M4 Results and record keeping`

## Your part in the routine
| When | What you do |
|---|---|
| A PR is marked ready | Read the PR and its "Files changed" tab, check CI is green, then click **Squash and merge**. The branch deletes itself. |
| End of a milestone | Merge the `chore(release)` PR. Then go to **Releases** → **Draft a new release** → new tag `v0.X.0` on `main` → **Generate release notes** → **Publish release**. |
| Before analysing real data for the write-up | Create a lab tag: **Releases** → **Draft a new release** → new tag `lab-YYYY-MM-DD` on `main` → tick **Set as a pre-release** → **Publish release**. |
| A token or personal information leaked | Revoke the token first, then follow "If something leaked" in `SKILL.md`. |
