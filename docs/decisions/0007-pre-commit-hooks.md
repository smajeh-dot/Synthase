# 0007: Pre-commit hooks

## Context
CI (decision 0006) catches lint failures and secrets, but only after a push. On a public repo, a secret that has been pushed has already leaked. The checks need to run inside the Claude session, before the commit is made. The owner never commits locally, so the hooks only ever run in Claude sessions.

The owner chose the defaults below during triage of #9 (2026-10-17).

## Decision
- **One file, `.pre-commit-config.yaml`,** run by the `pre-commit` tool. It holds these hooks:
  - `pre-commit-hooks` v6.0.0: `check-added-large-files` at 1024 KB (rule zero's 1 MB limit), `trailing-whitespace` (keeping Markdown's two-space line breaks) and `end-of-file-fixer`.
  - `ruff-pre-commit` v0.17.1: `ruff-check` and `ruff-format`.
  - `gitleaks` v8.30.1, the same version as CI.
- **Versions are pinned to release tags,** not commit IDs. Tags are what `pre-commit autoupdate` manages.
- **`pre-commit` goes in the `dev` extra,** so `pip install -e ".[dev]"` installs it along with pytest and ruff. It is a developer tool only; `syn` doesn't need it to run.
- **Two layers:** the workflow skill says to run `pre-commit run` on the staged files before every commit, and each session also runs `pre-commit install`, so `git commit` runs the hooks too if a session forgets.
- **CI is not changed.** It already runs ruff and gitleaks; running the size and whitespace checks in CI too is a separate issue.

## Consequences
- The first run in a new container takes about a minute: pre-commit downloads the hooks, and gitleaks is built from source with Go.
- The ruff in the `dev` extra is not pinned, but the hook's is. After a ruff release, the hook and CI could disagree. Updating the pin is a deliberate change, the same as for CI's pinned actions.
- Installing `.[dev]` on the Windows laptop also installs pre-commit. The owner never commits locally, so it simply isn't used there.
- Hooks can be skipped with `git commit --no-verify`. The skill forbids that, and CI still runs ruff and gitleaks afterwards.
