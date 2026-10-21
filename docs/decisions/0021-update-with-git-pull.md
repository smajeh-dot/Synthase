# 0021: Updating with git pull

## Context
The owner's laptop copy is now a git clone outside OneDrive (#96). Updating took two steps: get the new code, then run `.\scripts\setup.ps1` so any new dependency or command is installed. The owner asked for one `git pull` to do both. Decision 0011 says the setup script never pulls code; that stays true.

The owner chose all the triage defaults below for #96 (2026-10-21).

## Decision
- **A `post-merge` git hook runs the setup script again.** Git runs `post-merge` after a `git pull` that merges or fast-forwards, but not when the copy is already up to date. The hook re-runs setup after every such pull, not only when `pyproject.toml` changes: a run with nothing new takes a few seconds, and the simple rule is easier to trust.
- **The hook lives in the repo as `scripts/post-merge`.** `setup.ps1` copies it to `.git\hooks\post-merge` as a new step 4, right after installing Synthase. It writes the file only when it differs, so running setup again never adds a second copy. It writes no other hook, so the `pre-commit` hook that Claude sessions install stays as it is.
- **A ZIP copy has no `.git` folder,** so setup skips the step and says to update by downloading again and running the script.
- **The hook is plain ASCII with LF line endings.** Git for Windows runs hooks with its `sh`, which reads a CR as part of the command. `.gitattributes` keeps the template LF, and setup writes LF even if the checkout changed it. A test checks the template.
- **The hook runs `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1`.** Windows PowerShell 5.1 is on every Windows laptop, and the script already supports it. `Bypass` applies to that one run only, so a laptop still on the default "Restricted" policy doesn't block the hook without a word. It only ever runs the repo's own setup script.
- **The hook's body sits inside braces,** so `sh` reads all of it before running any of it. A pull can change the template, and setup then rewrites the hook while it is running.
- **The hook always exits 0.** The pull has already finished, so a failed setup changes nothing in git. The hook prints `Synthase: the code is updated, but setup failed. Fix the problem above, then run .\scripts\setup.ps1 again.`
- **CI:** before the setup script runs, CI plants a stand-in `pre-commit` hook. Afterwards it checks that `post-merge` matches the template and the stand-in is unchanged. Then it makes a commit, fast-forwards to it, and checks that the hook ran the setup script to the end.

## Consequences
- The owner's update step is `git pull` in the code folder. The setup must have run once in the clone to install the hook.
- If `synthase` is open in another window during a pull, pip may fail to replace the locked `synthase.exe`. Setup prints its usual FAIL and Fix lines; closing the app and running `.\scripts\setup.ps1` again fixes it.
- A pull that reports "Already up to date" runs nothing.
- The hook is skipped if git is set to look for hooks elsewhere (`core.hooksPath`), or in a git worktree, where `.git` is a file. Neither is used on the owner's laptop.
- Every pull now runs a script from the repo. That is the point of the change, and the repo is the owner's own.
