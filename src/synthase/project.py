"""Projects: one folder is one project, with its name in `data\\synthase.toml`.

`project create` makes `data\\` and `synthase.toml`; `project edit` renames the
project in that file only, never the folder. The rules and wording are in
docs/decisions/0031-projects.md.
"""

import shutil

import tomlkit

from synthase import history
from synthase.ids import KIND_FILES, id_number
from synthase.startup import FOREIGN
from synthase.storage import (
    MARKER,
    FolderState,
    StorageError,
    data_folder,
    folder_state,
    project_folder,
    read_toml,
    save_toml,
)

CREATED = 'Created project "{name}" in the folder path: {folder}'
ALREADY = (
    'This folder is already the Synthase project "{name}". '
    "To start another, run synthase in another folder."
)
RENAMED = 'Renamed project "{old}" to "{new}".'
KEPT = "Name kept. Nothing was saved."
# `project show`'s labels, in the column they are drawn in.
LABEL_WIDTH = 13


def name() -> str:
    """The project's name as stored, or "" if it has none."""
    stored = read_toml(data_folder() / MARKER).get("name")
    return stored if isinstance(stored, str) else ""


def create(new_name: str) -> None:
    """Create `data\\` and `synthase.toml` holding the name, and log it.

    Refuses if the folder became a project, or gained a `data\\` folder, since
    the question was asked. If saving fails, `data\\` is removed again.
    """
    state = folder_state()
    if state is FolderState.PROJECT:
        raise StorageError(ALREADY.format(name=name()))
    if state is FolderState.NOT_SYNTHASE:
        raise StorageError(FOREIGN)
    data = data_folder()
    data.mkdir()
    try:
        doc = tomlkit.document()
        doc["name"] = new_name
        doc["created"] = history.now()
        save_toml(data / MARKER, doc)
        history.log("create_project", MARKER, new=new_name)
    except BaseException:
        shutil.rmtree(data, ignore_errors=True)
        raise


def details() -> list[tuple[str, str]]:
    """What `project show` prints: each label with its value."""
    created = read_toml(data_folder() / MARKER).get("created")
    counts = {
        letter: sum(
            id_number(key, letter) is not None
            for key in read_toml(data_folder() / file)
        )
        for letter, file in KIND_FILES.items()
    }
    return [
        ("Name", name()),
        ("Created", _shown_time(created)),
        ("Folder", str(project_folder())),
        ("Experiments", str(counts["E"])),
        ("Compounds", str(counts["C"])),
    ]


def _shown_time(stamp: object) -> str:
    """A stored time as shown; one mistyped in Notepad is shown as it is."""
    try:
        return history.shown_time(str(stamp))
    except ValueError:
        return "" if stamp is None else str(stamp)


def rename(new_name: str) -> str:
    """Save the new name, keeping the rest of the file, and log it.

    Returns the old name.
    """
    path = data_folder() / MARKER
    doc = read_toml(path)
    old = name()
    doc["name"] = new_name
    save_toml(path, doc)
    history.log("edit_project", MARKER, old=old, new=new_name)
    return old
