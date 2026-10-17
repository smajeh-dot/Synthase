# 0013: Run the pre-commit hooks in CI

## Context
The pre-commit hooks (decision 0007) run only inside Claude sessions. CI (decision 0006) repeated ruff and gitleaks, but not the 1 MB, trailing-whitespace and end-of-file checks. So a session that skipped its hooks could push a file over 1 MB, and nothing would stop it reaching `main` (#22).

While triaging #22, Claude read the source of the 1 MB hook (`check-added-large-files`, pre-commit-hooks v6.0.0). By default it checks only files that are *staged as new*. In CI nothing is staged, so the hook as configured would pass a file of any size.

The owner chose the defaults below during triage of #22 (2026-10-17).

## Decision
- **CI runs `pre-commit run --from-ref <base> --to-ref <head>`** in the existing `ci` job, so it stays one required check. The range is the same one gitleaks scans: the PR's commits, or the commits pushed to `main`.
- **The 1 MB hook gets `--enforce-all`,** so it checks every file it's given. This is the one change to the hooks themselves. In sessions it now also checks staged files that already existed, which is slightly stricter.
- **CI skips only the gitleaks hook** (`SKIP=gitleaks`). Building it compiles Go, which is slow on Windows, and CI already runs a pinned, checksum-checked gitleaks. The ruff hooks run the pinned ruff that sessions use, next to the existing ruff steps, which use the unpinned ruff from the `dev` extra. If the two disagree after a ruff release, CI goes red, and that shows the pin needs updating.
- **The hook installs are cached** with `actions/cache` v6.1.0, pinned to its commit ID. The cache key includes the Python version and a hash of `.pre-commit-config.yaml`.
- **One-time exception for the test:** the session's own hook blocks a commit of a file over 1 MB. To show that CI catches it too, one commit of `ci-size-test.bin` (1.1 MB of zeros, no lab data) was made with `--no-verify` on the #22 branch. The next commit removed it. It never reaches `main`, because the PR is squash-merged. The blob stays reachable by commit ID on GitHub. This exception covers that one test only; the rule against `--no-verify` is unchanged.

## Consequences
- A file over 1 MB, trailing whitespace or a missing final newline in a PR now turns `ci` red, even if the session's hooks were skipped.
- Only files the new commits change are checked. Files already on `main` are not checked again.
- The first run after a hook version change rebuilds the cache, which adds about a minute.
- Updating a hook version is still a deliberate change to `.pre-commit-config.yaml` (decision 0007). It now also refreshes the CI cache.
