# 0030: Walk-through questions

## Context
`project create`, `project edit`, `exp create`, `exp edit`, `compound create`, `compound edit` and `value add` typed on its own ask their questions one at a time (decision 0023), and F3 and F4 will too. Decision 0027 built an answer mode for the one y/n question, and said walk-throughs reuse it. The front-end brief's section 5 isn't in the repo, so #101's triage proposed the look and wording from that answer mode. The owner chose every default on 2026-10-22.

## Decision
**Look** (approved)
- A question uses the same answer mode as the error question: heavy blue rules titled **`Answering <command>`** in bold, then a muted hint. The question is the prompt, `Title: `, in the answer colour.
- The hint says what Enter on its own does:
  - an optional question: `· Enter skips · Ctrl+C cancels`
  - a needed question: `· Ctrl+C cancels`
  - an edit: `· Enter keeps · - clears · Ctrl+C cancels`
  - a multi-line question: `· one per line · empty line ends · Ctrl+C cancels`
- In an edit, the stored value is the faint placeholder. A multi-line value shows its lines joined by `; `.
- Each answer goes into the output under the command, as `Title: Aspirin synthesis`, with the question muted and the answer bright. A skipped or cleared question shows only `Notes:`. A multi-line answer's further lines line up under the first.

**Wording** (approved)
- Ctrl+C: `‹ Cancelled. Nothing was saved.`
- An empty answer to a needed question: `✗ An answer is needed.`, then the same question again. Other refusals give the reason from the walk-through's own check (#102 onwards), then the same question again.

**Rules**
- Spaces around an answer are trimmed. A file-path question also strips one pair of surrounding quotes, so a file dragged into the window works (spec Section 2).
- In an edit, Enter on its own keeps the stored value and `-` clears it. A needed value can't be cleared: `-` gets `✗ An answer is needed.`. Outside an edit, `-` is an ordinary answer.
- A multi-line question takes one answer per line until an empty line. In an edit, Enter or `-` on its first line keeps or clears the stored lines; once a line is typed, the new lines replace them.
- Nothing is saved until the last answer. The walk-through's `finish` does the saving and issues any ID, so Ctrl+C saves nothing and uses no ID (C173, decision 0025). An unexpected error while saving asks the error question, as any command does.
- While a question is asked, Tab, Ctrl+D and the pop-up do nothing, as on the error question. Answers are never kept in the up-arrow history (decision 0028).

**Code**
- `synthase/walkthrough.py` holds the rules: `Question`, `Walkthrough` and `Walk`. A command starts one with `SynthaseApp.ask(Walkthrough(...))`. The app draws it.

## Consequences
- #102, #104, #105 and #106 build their walk-throughs as a list of `Question`s with a `finish` that saves, and add only their own checks and refusal reasons.
- `value add` typed on its own is still a usage error until #105 makes it start the multi-line walk-through.
