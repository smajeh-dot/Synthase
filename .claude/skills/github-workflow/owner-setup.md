# Owner setup (one time, Windows)

Do these in order. The GitHub steps work the same in any browser. Every command is for PowerShell.

## 1. Email privacy
GitHub → your profile picture → **Settings** → **Emails**:
- Tick **Keep my email addresses private**.
- Tick **Block command line pushes that expose my email**.
- Copy the `…@users.noreply.github.com` address shown on that page. You need it in step 7.

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
- After the CI workflow exists (an M0 issue), edit the ruleset and also tick **Require status checks to pass**, then add the CI check.

## 6. Private word list (names, school, email domains)
Pick the words: your name, your teammate's name, the school's name, the school email domain. Write them as one comma-separated line. Store that same line in three places, and **never in the repo**:
- **CI:** Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**. Name it `SYNTHASE_PRIVATE_WORDS`.
- **Claude cloud sessions:** open the cloud environment menu in the session's title bar → **Edit** → add an environment variable named `SYNTHASE_PRIVATE_WORDS`. New sessions pick it up.
- **Your laptop:** a text file **outside** the repo folder, at `$HOME\.synthase-private-words.txt`. The pre-commit hook (an M0 issue) will read it. Create it in PowerShell:
  ```powershell
  Set-Content -Path "$HOME\.synthase-private-words.txt" -Value "word one, word two"
  ```

## 7. Git on your laptop (only if you'll commit locally)
```powershell
winget install --id Git.Git -e
git config --global user.name "smajeh-dot"
git config --global user.email "PASTE-NOREPLY-ADDRESS-FROM-STEP-1"
```
- Branches you create yourself follow the pattern `laptop/<type>/<issue>-<short-description>`, for example `laptop/feat/12-yield`. The full convention is under "Branch names" in `SKILL.md`.
- The same rules apply as for Claude: one issue per branch, a PR into `main`, squash merge.

## Your part in the routine
| When | What you do |
|---|---|
| A PR is marked ready | Read the PR and its "Files changed" tab, check CI is green, then click **Squash and merge**. The branch deletes itself. |
| End of a milestone | Merge the `chore(release)` PR. Then go to **Releases** → **Draft a new release** → new tag `v0.X.0` on `main` → **Generate release notes** → **Publish**. |
| Before analysing real data for the write-up | Create a lab tag on `main`: `git tag lab-YYYY-MM-DD` then `git push origin lab-YYYY-MM-DD`. Or use a release marked as a pre-release. |
| A token or personal information leaked | Revoke the token first, then follow "If something leaked" in `SKILL.md`. |
