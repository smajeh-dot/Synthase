# 0004: Issue and PR templates

## Context
The issue and PR formats were written out in the workflow skill. Issue #7 turns them into GitHub templates. Keeping the section lists in both places would let them drift apart, and a later session could follow the out-of-date copy.

GitHub applies templates only on its website. Issues and PRs created through the API, which is how Claude sessions create them, get no template, and `blank_issues_enabled: false` doesn't stop them either.

## Decision
- **The templates are the only definition of the formats:** `.github/ISSUE_TEMPLATE/task.md` and `.github/pull_request_template.md`. The workflow skill points to them and holds only the behaviour around them (labels, milestones, title style, size limit, when a PR is ready). It tells Claude to read the template file and copy its headings when creating an issue or PR through the API.
- **Markdown templates, not YAML issue forms.** Markdown gives the same `##` headings as the existing issues, and Claude can copy it directly. The forms' required fields only work on the website, so they wouldn't cover Claude's issues anyway.
- **PRs carry a "Done when" section.** The PR copies the issue's checklist and the boxes are ticked there, so the owner checks one page before merging and the PR list shows progress. Issue #7 listed five PR sections; this is the sixth.
- **Both templates start with a hidden reminder** that the repo is public, so no lab data, results, real names, the school's name or keys go into an issue or PR.
- **No automated test checks the templates.** The owner judged it unnecessary for a personal tool.
- **Template changes are tested after merging.** GitHub reads templates only from `main`, so the website test can't happen on the PR's branch. A template PR says `Part of #N` rather than `Closes #N`, so the issue stays open until the owner's test passes, and only then is it closed as completed.

## Consequences
- Changing a format means editing the template file in a normal PR. The skill needs no change.
- The issue's own "Done when" boxes stay unticked. The issue closes when its PR is merged.
- Nothing catches a damaged template automatically. The first sign would be a wrong-looking issue or PR.
