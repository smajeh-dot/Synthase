"""Command history for the app, kept in the workspace between sessions.

History can hold compound labels, so it lives in the workspace and never in the
repo. Nothing here prints anything. The details are in
docs/decisions/0016-full-screen-app.md under "Details settled for #53".
"""

from pathlib import Path

from synthase.workspace import WorkspaceError, current_workspace

FILE_NAME = "command-history.txt"
# Only the latest commands are kept, so the file stays small.
LIMIT = 500


def history_file() -> Path | None:
    """The history file in the workspace, or None when there is no workspace yet."""
    try:
        return current_workspace() / FILE_NAME
    except WorkspaceError:
        return None


class History:
    """Earlier commands, oldest first, and where Up and Down have stepped to."""

    def __init__(self, path: Path | None, lines: list[str] | None = None) -> None:
        self.path = path
        self.lines = (lines or [])[-LIMIT:]
        # len(lines) means the bar is past the newest command.
        self.position = len(self.lines)

    @classmethod
    def load(cls, path: Path | None) -> "History":
        """Read the file. A missing or unreadable file starts an empty history."""
        lines = []
        if path is not None:
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                pass
        return cls(path, [line for line in lines if line.strip()])

    def add(self, line: str) -> None:
        """Remember a command, unless it repeats the one before. Raises OSError."""
        if not self.lines or self.lines[-1] != line:
            self.lines = [*self.lines, line][-LIMIT:]
        self.position = len(self.lines)
        if self.path is not None:
            self.path.write_text("".join(f"{x}\n" for x in self.lines), "utf-8")

    def back(self) -> str | None:
        """Up: the command before, or None when there is nothing older."""
        if self.position == 0:
            return None
        self.position -= 1
        return self.lines[self.position]

    def forward(self) -> str | None:
        """Down: the next command, "" past the newest, None when already there."""
        if self.position == len(self.lines):
            return None
        self.position += 1
        return self.lines[self.position] if self.position < len(self.lines) else ""
