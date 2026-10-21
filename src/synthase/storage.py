"""Where Synthase keeps its files, and reading and saving them safely.

Synthase works in the folder it is started in, with its data in `data\\` there;
the folder is a project only when `data\\synthase.toml` exists. The rules are in
docs/decisions/0023-command-set-and-project-folder.md and
docs/decisions/0024-safe-saving.md. Nothing here creates a project: that is
`project create`.
"""

import os
import time
from enum import Enum
from pathlib import Path

import tomlkit
from tomlkit.exceptions import ParseError
from tomlkit.items import Float
from tomlkit.toml_document import TOMLDocument

DATA = "data"
MARKER = "synthase.toml"
# A save that another program (such as OneDrive) is holding is tried this many
# times, this many seconds apart: about a second in all.
TRIES = 5
WAIT = 0.2

BROKEN = (
    "{file} has a mistake on line {line}, so Synthase won't load it. "
    "Fix it in Notepad, then try again."
)
HELD = (
    "Couldn't save {file}: another program is using it. "
    "Nothing was changed. Close that program, then try again."
)


class StorageError(Exception):
    """A file that can't be read or saved: the message to show."""


class FolderState(Enum):
    PROJECT = "project"
    NO_PROJECT = "no project"
    NOT_SYNTHASE = "a data folder that isn't Synthase's"


def project_folder() -> Path:
    """The folder Synthase was started in, or SYNTHASE_HOME (tests only)."""
    home = os.environ.get("SYNTHASE_HOME")
    return Path(home) if home else Path.cwd()


def data_folder() -> Path:
    return project_folder() / DATA


def folder_state() -> FolderState:
    """Whether the project folder holds a Synthase project. Creates nothing."""
    data = data_folder()
    if (data / MARKER).is_file():
        return FolderState.PROJECT
    if data.exists():
        return FolderState.NOT_SYNTHASE
    return FolderState.NO_PROJECT


def _shown(path: Path) -> str:
    """A file as the owner sees it in File Explorer, e.g. data\\compounds.toml."""
    return f"{path.parent.name}\\{path.name}"


def read_toml(path: Path) -> TOMLDocument:
    """A TOML file with its comments and layout kept; empty if it doesn't exist.

    A file that isn't valid TOML (or UTF-8) is refused, naming the line.
    """
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return tomlkit.document()
    try:
        # Notepad may have saved a byte-order mark.
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        line = raw[: error.start].count(b"\n") + 1
        raise StorageError(BROKEN.format(file=_shown(path), line=line)) from None
    try:
        return tomlkit.parse(text)
    except ParseError as error:
        raise StorageError(BROKEN.format(file=_shown(path), line=error.line)) from None


def _refuse_floats(item: object) -> None:
    """Typed numbers are stored as text, so nothing is rounded (spec D25)."""
    if isinstance(item, Float | float):
        raise TypeError(f"{item!r} must be saved as text, not a number")
    if isinstance(item, dict):
        for value in item.values():
            _refuse_floats(value)
    elif isinstance(item, list):
        for value in item:
            _refuse_floats(value)


def save_toml(path: Path, doc: TOMLDocument) -> None:
    """Save a TOML file so that a crash or a held file never leaves half of it.

    The text goes to a temporary file in the same folder, which then replaces
    the old file in one step. If another program is holding the file, the save
    is retried, then given up with the old file as it was.
    """
    _refuse_floats(doc)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(tomlkit.dumps(doc).encode("utf-8"))
    try:
        for attempt in range(TRIES):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt < TRIES - 1:
                    time.sleep(WAIT)
        raise StorageError(HELD.format(file=_shown(path)))
    finally:
        temporary.unlink(missing_ok=True)
