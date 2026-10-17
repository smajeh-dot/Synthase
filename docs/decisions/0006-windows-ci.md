# 0006: Windows CI workflow

## Context
Until now, the tests passing in the Claude session (on Linux) stood in for CI. Synthase runs on a Windows laptop, so the checks need to run on Windows, on every PR and on every merge into `main`, and a red result must block the merge.

The repo is public. Anything CI downloads and runs is code that could change under us, so it has to be pinned.

The owner chose the defaults below during triage of #8 (2026-10-17).

## Decision
- **One workflow, `.github/workflows/ci.yml`, with one job named `ci`.** The `protect-main` ruleset requires that one check by name. Renaming the job means updating the ruleset.
- **Triggers:** `pull_request` and `push` to `main` only. Every Claude branch has a PR, so all work is still checked.
- **Runner:** `windows-latest`, Python 3.13 (decision 0002), with `actions/setup-python`'s pip cache keyed on `pyproject.toml`.
- **Steps:** install with `pip install -e ".[dev]"`, then `ruff check`, `ruff format --check`, `pytest`, and gitleaks.
- **gitleaks runs as the program itself, not through `gitleaks-action`.** The workflow downloads a pinned release and checks its SHA-256 checksum before running it. This needs no licence key and no extra third-party action.
- **gitleaks scans only the new commits:** the PR's commits (`base..head`) on a PR, and the pushed commits (`before..after`) on `main`. Older history was scanned when it was new. Secret scanning and push protection on GitHub (owner setup step 4) cover the whole repo.
- **Actions are pinned to full commit IDs,** with the version in a comment. The workflow token is read-only (`contents: read`).
- **If the first Windows run shows a small Windows-only failure** in existing tests, it is fixed on the CI branch. Anything bigger gets its own issue.

## Consequences
- A red `ci` check blocks the merge once the owner adds it to the ruleset (owner setup step 5).
- Pinned versions don't update themselves. Updating an action or gitleaks is a deliberate change: a new commit ID, or a new version and checksum.
- Windows runners are slower to start than Linux ones, about 1 to 2 minutes per run.
- The setup script (#13) will add a step to this same job, so it stays one required check.
- The "local tests stand in for CI" rule is removed from the workflow skill.
