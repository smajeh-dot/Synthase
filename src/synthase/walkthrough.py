"""Walk-throughs: questions asked one at a time in the app's answer mode.

This module holds the rules: what each answer means, and what is refused. The
app draws the questions and saves nothing until the walk-through finishes, so
Ctrl+C leaves no trace. The look and wording are in
docs/decisions/0030-walk-throughs.md.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

NEEDED = "An answer is needed."
CANCELLED = "Cancelled. Nothing was saved."
# In an edit, this answer clears the stored value.
CLEAR = "-"

# What a question gives: its text, a multi-line question's lines, or None.
Answer = str | list[str] | None
# Checks one answer (one line of a multi-line one): the reason it's refused,
# or None.
Check = Callable[[str], str | None]


@dataclass
class Question:
    name: str
    """The key of its answer."""
    label: str
    """What the prompt asks, e.g. ``Title``."""
    optional: bool = False
    lines: bool = False
    """One answer per line, until an empty line."""
    path: bool = False
    """A file path: quotes and spaces around it are stripped."""
    check: Check | None = None
    current: Answer = None
    """In an edit, the stored value."""


@dataclass
class Walkthrough:
    command: str
    """The command it belongs to, for the `Answering <command>` title."""
    questions: list[Question]
    finish: Callable[[dict[str, Answer]], None]
    """Given every answer once the last question is answered; it does the saving."""
    edit: bool = False


@dataclass
class Step:
    """What one answer did."""

    refused: str | None = None
    """The reason, when the same question is asked again."""
    shown: list[str] | None = None
    """The answer to record under its question: [] for the question alone,
    None for nothing."""
    more: bool = False
    """A further line of a multi-line answer, recorded under the first."""


def unquote(text: str) -> str:
    """A path with the quotes a dragged-in file brings stripped off."""
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return text


@dataclass
class Walk:
    """Where a walk-through has got to."""

    walkthrough: Walkthrough
    answers: dict[str, Answer] = field(default_factory=dict)
    number: int = 0
    typed: list[str] = field(default_factory=list)
    """A multi-line question's lines so far."""

    @property
    def question(self) -> Question | None:
        questions = self.walkthrough.questions
        return questions[self.number] if self.number < len(questions) else None

    @property
    def keeping(self) -> bool:
        """Whether Enter on its own keeps the stored value."""
        return self.walkthrough.edit and not self.typed

    def answer(self, text: str) -> Step:
        question = self.question
        text = unquote(text) if question.path else text.strip()
        if self.keeping and text == "":
            current = question.current
            shown = current if isinstance(current, list) else [current or ""]
            return self.next(current, [line for line in shown if line])
        if (self.keeping and text == CLEAR) or (not self.typed and text == ""):
            if not question.optional:
                return Step(refused=NEEDED)
            return self.next(None, [])
        if question.lines and text == "":
            lines, self.typed = self.typed, []
            return self.next(lines, None)
        reason = question.check(text) if question.check else None
        if reason is not None:
            return Step(refused=reason)
        if not question.lines:
            return self.next(text, [text])
        self.typed.append(text)
        return Step(shown=[text], more=len(self.typed) > 1)

    def next(self, answer: Answer, shown: list[str] | None) -> Step:
        self.answers[self.question.name] = answer
        self.number += 1
        return Step(shown=shown)
