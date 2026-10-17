"""The workspace: the folder, outside the repo, for lab data, results and notes.

`syn init` creates it and remembers where it is. The rules are in
docs/decisions/0009-workspace.md.
"""

import os
import sys
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from synthase.config import WORKSPACE_CONFIG_NAME, read_template

FOLDERS = ("raw", "maps", "results", "notebook")
DEFAULT_NAME = "Synthase-data"
POINTER_NAME = "workspace.txt"
PACKAGE_NAME = "synthase-lab"
# Windows' ID for the Documents folder (FOLDERID_Documents).
DOCUMENTS_ID = "FDD39AD0-238F-46AF-ADB4-6C85480369C7"


class WorkspaceError(Exception):
    """A workspace that can't be created or found, with a message for the user."""


@dataclass(frozen=True)
class Created:
    path: Path
    config: str  # "copied", "kept" or "replaced"
    backup: Path | None = None


def documents_folder() -> Path:
    """The user's Documents folder, wherever Windows (or OneDrive) has put it."""
    if sys.platform == "win32":
        try:
            return _windows_documents()
        except OSError:
            pass
    return Path.home() / "Documents"


def _windows_documents() -> Path:
    import ctypes
    import uuid
    from ctypes import wintypes

    shell32 = ctypes.WinDLL("shell32")
    ole32 = ctypes.WinDLL("ole32")
    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.c_char_p,
        wintypes.DWORD,
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]
    # HRESULT raises OSError when Windows reports a failure.
    shell32.SHGetKnownFolderPath.restype = ctypes.HRESULT
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]

    found = ctypes.c_wchar_p()
    folder_id = uuid.UUID(DOCUMENTS_ID).bytes_le
    shell32.SHGetKnownFolderPath(folder_id, 0, None, ctypes.byref(found))
    try:
        return Path(found.value)
    finally:
        ole32.CoTaskMemFree(found)


def default_path() -> Path:
    return documents_folder() / DEFAULT_NAME


def settings_folder() -> Path:
    """Where Synthase keeps its own settings: outside the repo and the workspace."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Synthase"
    return Path.home() / ".config" / "synthase"


def code_folder() -> Path:
    """The folder Synthase's code is in.

    That is the checkout holding Synthase's pyproject.toml, or the installed
    package folder when there is no checkout.
    """
    package = Path(__file__).resolve().parent
    for folder in package.parents:
        if _is_synthase_project(folder / "pyproject.toml"):
            return folder
    return package


def _is_synthase_project(pyproject: Path) -> bool:
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return False
    return data.get("project", {}).get("name") == PACKAGE_NAME


def check_outside_code_folder(path: Path) -> None:
    code = code_folder()
    if Path(path).resolve().is_relative_to(code):
        raise WorkspaceError(
            f"Synthase can't create the workspace there: {path} is inside "
            f"Synthase's own code folder ({code}). The workspace holds your lab "
            "data, results and notes. Keeping it outside the code folder means "
            "none of it can be uploaded to GitHub by mistake. Choose another "
            'folder, or run "syn init" with no path to use '
            f"Documents\\{DEFAULT_NAME}."
        )


def create_workspace(path: Path | None, ask: Callable[[str], bool]) -> Created:
    """Create the workspace at ``path`` (or the default) and remember it.

    ``ask`` is called with a question if the folder already has a config, and
    returns True only if the user agreed to replace it.
    """
    path = (Path(path).expanduser() if path is not None else default_path()).resolve()
    check_outside_code_folder(path)
    if path.exists() and not path.is_dir():
        raise WorkspaceError(
            f"Synthase can't create the workspace there: {path} is a file, "
            "not a folder. Choose a folder instead."
        )

    config = path / WORKSPACE_CONFIG_NAME
    existed = config.exists()
    replace = existed and ask(
        f"A workspace already exists at {path}. Replace its config.toml with a "
        "fresh copy of the template? Any values you have checked will be reset "
        "(the old file is kept as config.toml.bak-…). Type yes to replace it [no]: "
    )

    for name in FOLDERS:
        (path / name).mkdir(parents=True, exist_ok=True)
    backup = _back_up(config) if replace else None
    if replace or not existed:
        config.write_text(read_template(), encoding="utf-8")
    remember(path)

    if replace:
        return Created(path, "replaced", backup)
    return Created(path, "kept" if existed else "copied")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _back_up(config: Path) -> Path:
    """Copy the config to a new ``config.toml.bak-…`` file, never over an old one."""
    stem = f"{config.name}.bak-{_timestamp()}"
    backup = config.with_name(stem)
    number = 1
    while True:
        try:
            with open(backup, "xb") as copy:
                copy.write(config.read_bytes())
            return backup
        except FileExistsError:
            number += 1
            backup = config.with_name(f"{stem}-{number}")


def remember(path: Path) -> None:
    folder = settings_folder()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / POINTER_NAME).write_text(f"{path}\n", encoding="utf-8")


def current_workspace() -> Path:
    """The workspace that `syn init` last created or chose."""
    pointer = settings_folder() / POINTER_NAME
    try:
        text = pointer.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        text = ""
    if not text:
        raise WorkspaceError('There is no workspace yet. Run "syn init" to create one.')
    path = Path(text)
    if not path.is_dir():
        raise WorkspaceError(
            f"The workspace at {path} can't be found. If you moved it, run "
            '"syn init" with its new location. Your files and config there '
            "are kept."
        )
    return path
