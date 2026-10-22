"""Opening the folder Synthase was started in, and the status line it gives.

The states, their wording and the order of the checks are in
docs/decisions/0027-app-shell.md.
"""

from dataclasses import dataclass, field
from pathlib import Path

from textual.content import Content

from synthase import history, lock
from synthase.storage import (
    MARKER,
    FolderState,
    StorageError,
    data_folder,
    folder_state,
    project_folder,
    read_toml,
    shown,
)

NO_PROJECT = "No Synthase project here. Type 'project create' to start one."
FOREIGN = (
    "This folder's data\\ folder wasn't made by Synthase, so Synthase won't write "
    "to it. Start Synthase in another folder."
)
# The status line's short form of each refusal.
FOREIGN_FLAG = "data\\ isn't a Synthase folder"
IN_USE_FLAG = "open in another Synthase window"
BROKEN_FLAG = "{file} has a mistake"

ELLIPSIS = "…"
SEPARATOR = " · "


@dataclass
class Startup:
    """What opening the folder found.

    ``refusal`` is the message shown at start-up and repeated for each data
    command, as a (kind, text) pair; ``flag`` is its short form in the status
    line. ``locked`` says whether this window holds the project's lock.
    """

    folder: Path
    state: FolderState
    name: str | None = None
    refusal: tuple[str, str] | None = None
    flag: tuple[str, str] | None = None
    notices: list[str] = field(default_factory=list)
    locked: bool = False


def open_folder() -> Startup:
    """Check the folder, take the lock and log outside edits. Creates no data\\."""
    folder = project_folder()
    state = folder_state()
    if state is FolderState.NO_PROJECT:
        hint = ("hint", NO_PROJECT)
        return Startup(folder, state, refusal=hint, flag=hint)
    if state is FolderState.NOT_SYNTHASE:
        flag = ("error", FOREIGN_FLAG)
        return Startup(folder, state, refusal=("error", FOREIGN), flag=flag)
    broken = _broken_file()
    if broken is not None:
        file, message = broken
        flag = ("error", BROKEN_FLAG.format(file=file))
        return Startup(folder, state, refusal=("error", message), flag=flag)
    name = read_toml(data_folder() / MARKER).get("name")
    name = name if isinstance(name, str) and name else None
    try:
        lock.acquire()
    except StorageError as error:
        flag = ("error", IN_USE_FLAG)
        return Startup(folder, state, name, ("error", str(error)), flag)
    notices = history.check_external_edits()
    return Startup(folder, state, name, notices=notices, locked=True)


def _broken_file() -> tuple[str, str] | None:
    """The first data file Synthase can't read, as it is shown, with its message."""
    for name in history.TRACKED:
        path = data_folder() / name
        try:
            read_toml(path)
        except StorageError as error:
            return shown(path), str(error)
    try:
        history.entries()
    except StorageError as error:
        return shown(data_folder() / history.FILE), str(error)
    return None


def status_line(startup: Startup, width: int, context: str | None = None) -> Content:
    """The status line, its folder shortened to fit ``width`` cells.

    ``context`` is the open experiment's ID, shown after the project's name.
    """
    parts: list[Content] = []
    if startup.name is not None:
        lead = Content.styled(f"{startup.name}/" if context else startup.name, "$muted")
        parts.append(lead + Content.styled(context, "$accent") if context else lead)
    tail = Content()
    if startup.flag is not None:
        kind, text = startup.flag
        if kind == "hint":
            tail = Content.styled(f"› {text}", "$muted")
        else:
            tail = Content.assemble(("✗", "bold $error"), (f" {text}", "$error"))
    fixed = sum(len(p) for p in parts) + len(tail) + len(SEPARATOR) * len(parts)
    if tail:
        fixed += len(SEPARATOR)
    folder = shorten_path(str(startup.folder), width - fixed)
    parts.append(Content.styled(folder, "$muted"))
    if tail:
        parts.append(tail)
    return Content.styled(SEPARATOR, "$faint").join(parts)


def shorten_path(path: str, room: int, home: str | None = None) -> str:
    """``path`` as it is if it fits in ``room`` cells, otherwise shortened.

    First the home folder becomes ``~``, then middle folders become ``…``,
    keeping the first folder and the project's own folder name.
    """
    if len(path) <= room:
        return path
    home = str(Path.home()) if home is None else home
    sep = "\\" if "\\" in path else "/"
    if path.lower().startswith(home.lower() + sep):
        path = "~" + path[len(home) :]
        if len(path) <= room:
            return path
    parts = path.split(sep)
    if len(parts) <= 2:
        return path
    head, middle, last = parts[0], parts[1:-1], parts[-1]
    for keep in range(len(middle) - 1, -1, -1):
        shorter = sep.join([head, *middle[:keep], ELLIPSIS, last])
        if len(shorter) <= room:
            return shorter
    return sep.join([head, ELLIPSIS, last])
