"""The command history: the lines ↑ and ↓ step back through.

With a project, the lines run are kept in `data\\.history`, plain text, one per
line, so they come back next time; only the window holding the project's lock
reads or writes it. With no project they last for the session. The rules are
in docs/decisions/0028-tab-and-history.md.
"""

import os
from pathlib import Path

from synthase.storage import data_folder

FILE = ".history"
# Only the latest lines are kept, as in the output.
MAX_LINES = 1000


def path() -> Path:
    return data_folder() / FILE


def load() -> list[str]:
    """The kept lines, oldest first; empty if there are none yet.

    A file grown past MAX_LINES is cut back to the latest ones.
    """
    try:
        text = path().read_text(encoding="utf-8-sig", errors="replace")
    except FileNotFoundError:
        return []
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) > MAX_LINES:
        lines = lines[-MAX_LINES:]
        temporary = path().with_name(f"{FILE}.tmp")
        temporary.write_text("".join(f"{line}\n" for line in lines), "utf-8")
        os.replace(temporary, path())
    return lines


class CommandHistory:
    """The lines run so far, and where ↑ and ↓ have stepped to.

    ``saved`` says whether each new line is also added to `data\\.history`.
    """

    def __init__(self, lines: list[str] | None = None, saved: bool = False) -> None:
        self.lines = list(lines or [])
        self.saved = saved
        # How many steps back from the newest; None when not stepping.
        self.step: int | None = None
        self.draft = ""

    def add(self, line: str) -> None:
        """Keep a line just run; the same line twice in a row is kept once."""
        self.stop()
        if self.lines and self.lines[-1] == line:
            return
        self.lines = [*self.lines, line][-MAX_LINES:]
        if self.saved:
            with path().open("a", encoding="utf-8", newline="\n") as file:
                file.write(f"{line}\n")

    def older(self, draft: str) -> str | None:
        """The line one step back, or None if there is none.

        ``draft`` is the line being typed, given back by ``newer`` at the end.
        """
        if not self.lines:
            return None
        if self.step is None:
            self.draft = draft
            self.step = 1
        elif self.step < len(self.lines):
            self.step += 1
        return self.lines[-self.step]

    def newer(self) -> str | None:
        """The line one step forward, the draft after the newest, or None."""
        if self.step is None:
            return None
        if self.step == 1:
            self.stop()
            return self.draft
        self.step -= 1
        return self.lines[-self.step]

    def stop(self) -> None:
        self.step = None
