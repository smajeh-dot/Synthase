"""Saving result tables as CSV, as the roadmap asks of every table.

Where each kind of table is saved is set under [folders] in the workspace
config. The rules are in docs/decisions/0015-table-folders.md.
"""

import csv
from collections.abc import Iterable, Sequence
from pathlib import Path

from synthase.config import FOLDERS_TABLE, WORKSPACE_CONFIG_NAME, Config
from synthase.workspace import code_folder, inside_code_folder

RESULTS_FOLDER = "results"


class TableFolderError(Exception):
    """A place a table can't be saved, with a message for the user."""


def table_folder(workspace: Path, config: Config, area: str) -> Path:
    """The folder ``area``'s tables go in: its [folders] setting, or results."""
    setting = config.folder(area)
    # A full path in the setting replaces the workspace part when joined.
    return workspace / (Path(setting).expanduser() if setting else RESULTS_FOLDER)


def code_folder_problem(path: Path, area: str, config_file: Path) -> str:
    """Why ``path`` can't hold tables, or "" if it isn't in the code folder."""
    if not inside_code_folder(path):
        return ""
    return (
        f"Synthase can't save the table there: {path} is inside Synthase's own "
        f"code folder ({code_folder()}). Tables hold your results. Keeping them "
        "outside the code folder means none of them can be uploaded to GitHub "
        f'by mistake. Choose a folder outside it, or set "{area}" under '
        f"[{FOLDERS_TABLE}] in {config_file}."
    )


def place_table(name: Path, workspace: Path, config: Config, area: str) -> Path:
    """Where a table saved as ``name`` goes, checked before anything is written.

    A file name or relative path goes inside the area's folder; a full path is
    used as typed.
    """
    folder = table_folder(workspace, config, area)
    path = folder / Path(name).expanduser()
    config_file = workspace / WORKSPACE_CONFIG_NAME
    problem = code_folder_problem(path, area, config_file)
    if problem:
        raise TableFolderError(problem)
    if not path.parent.is_dir():
        fix = (
            f'Create it in File Explorer, or change "{area}" under '
            f"[{FOLDERS_TABLE}] in {config_file}."
            if config.folder(area) and path.parent == folder
            else "Create it, or choose another folder."
        )
        raise TableFolderError(
            f"Couldn't save the table: the folder {path.parent} doesn't exist. {fix}"
        )
    return path


def replace_question(path: Path) -> str:
    """The question asked before an existing table is replaced."""
    return f"{path} already exists. Replace it?"


def kept_text(path: Path) -> str:
    return f"Kept the existing {path}. The table was not saved."


def saved_text(path: Path) -> str:
    return f"Saved the table to {path.resolve()}"


def not_saved_text(path: Path, error: OSError) -> str:
    return (
        f"Couldn't save {path}: {error.strerror}. "
        "If it is open in Excel, close it and try again."
    )


def write_csv(
    path: Path, headings: Sequence[str], rows: Iterable[Sequence[str | None]]
) -> None:
    """Save a table as CSV, leaving blank (None) cells empty.

    The file starts with a byte-order mark (utf-8-sig): without it, Excel on
    Windows garbles any letter outside plain English.
    """
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(headings)
        writer.writerows(rows)
