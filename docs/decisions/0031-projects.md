# 0031: Projects: create, show and rename

## Context
Decision 0023 gave a project only a name, set by `project create` and changed by `project edit`, and one project per folder. While the commands were being agreed, the default said renaming would also rename the folder; Windows refuses to rename a folder that PowerShell or Synthase is working in. Spec C168's Windows folder-name rules were written for project names that were folder names. #102's triage proposed the behaviour and wording below; the owner chose every default on 2026-10-22, changing only the message after `project create`.

## Decision
**What a project is**
- The name lives only in `data\synthase.toml`, as `name`. Renaming changes that line; the folder keeps its own name. The Windows folder-name rules in C168 no longer apply to project names: any name that can be typed is accepted, spaces around it trimmed, but not an empty one.
- `synthase.toml` also holds `created`, the time `project create` finished, stored as ISO 8601 with its UTC offset (decision 0025).

**`project create`**
- In a folder with no project, it asks one needed question, `Name:`, with the hint `· Ctrl+C cancels`. It suggests nothing.
- Once answered, it creates `data\` and `synthase.toml`, logs `create_project`, takes the lock and opens the project, so the status line shows the name and the up-arrow history starts saving to `data\.history`, beginning with the lines already typed in that session. It says:
  - `✓ Created project "Aspirin synthesis" in the folder path: C:\Users\you\Lab\aspirin` (approved, with `in the folder path:` in place of the spec's `->`)
- Ctrl+C before the answer creates nothing. If saving fails, whatever was created is removed, so the folder is left as it was.
- In a folder that is already a project: `✗ This folder is already the Synthase project "Aspirin synthesis". To start another, run synthase in another folder.`
- In a folder whose `data\` folder isn't Synthase's, the start-up refusal is repeated word for word (decision 0027). If a project or a `data\` folder appears while `Name:` is being answered, the same refusals are given and nothing is written.

**`project show`**
- Labels muted, values bright, in a 13-cell label column:
  ```
  Name         Aspirin synthesis
  Created      2026-10-22 14:32:07
  Folder       C:\Users\you\Lab\aspirin
  Experiments  0
  Compounds    0
  ```
- Experiments and compounds are counted from the IDs in `experiments.toml` and `compounds.toml`.

**`project edit`**
- It asks `Name:` as an edit (decision 0030): the current name is the placeholder, Enter keeps it, and `-` gets `✗ An answer is needed.`, because a project needs a name.
- A new name is saved safely (decision 0024), logged, and shown in the status line: `✓ Renamed project "Aspirin synthesis" to "Aspirin synthesis 2".`
- Enter, or the same name retyped: `› Name kept. Nothing was saved.`

**History log**
- Two actions join the spec's list in C171: `create_project`, with the name as `new`, and `edit_project`, with the old and new names as `old` and `new`.

## Consequences
- These three commands no longer say `isn't built yet.`
- A project's folder name and its Synthase name can differ. `project show` prints both.
- Deleting a project is still done in File Explorer, by deleting the folder.
