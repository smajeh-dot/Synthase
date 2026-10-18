"""`syn doctor`: checks the install and the setup, and finds unverified values.

The rules are in docs/decisions/0010-syn-doctor.md. The report's words are
here too, so `syn doctor` and the app's `/doctor` say the same thing.
Nothing here prints anything.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

from synthase import __version__
from synthase.config import (
    FOLDER_AREAS,
    FOLDERS_TABLE,
    WORKSPACE_CONFIG_NAME,
    Config,
    ConfigError,
    ConfigValue,
    load_config,
)
from synthase.tables import table_folder
from synthase.workspace import (
    FOLDERS,
    WorkspaceError,
    code_folder,
    current_workspace,
    inside_code_folder,
)

# The version pinned in pyproject.toml (decision 0002).
REQUIRED_PYTHON = (3, 13)
TEST_SMILES = "CCO"
TEST_NAME = "ethanol"
REINSTALL = (
    "with the virtual environment switched on, run "
    "python -m pip install -e . in the Synthase folder."
)


@dataclass(frozen=True)
class Check:
    passed: bool
    text: str
    fix: str = ""

    @property
    def word(self) -> str:
        """``ok`` or ``FAIL``, the word each check's line starts with."""
        return "ok" if self.passed else "FAIL"


@dataclass(frozen=True)
class Report:
    checks: list[Check]
    config: Config | None

    @property
    def failed(self) -> int:
        return sum(not check.passed for check in self.checks)

    def unverified(self) -> list[ConfigValue]:
        if self.config is None:
            return []
        entries = (self.config.get(key) for key in self.config.keys())
        return [entry for entry in entries if not entry.verified]


def check_python(version: tuple[int, ...] | None = None) -> Check:
    version = tuple(version or sys.version_info[:3])
    found = ".".join(map(str, version))
    if version[:2] == REQUIRED_PYTHON:
        return Check(True, f"Python {found}")
    needed = ".".join(map(str, REQUIRED_PYTHON))
    return Check(
        False,
        f"Python {found}, but Synthase needs Python {needed}",
        f"install Python {needed}, then make the virtual environment again "
        f"in the Synthase folder: py -{needed} -m venv .venv",
    )


def check_rdkit() -> Check:
    try:
        import rdkit
        from rdkit import Chem
    except ImportError:
        return Check(False, "RDKit is not installed, or it won't load", REINSTALL)
    test = f"a test structure ({TEST_NAME}, {TEST_SMILES})"
    if Chem.MolFromSmiles(TEST_SMILES) is None:
        return Check(
            False, f"RDKit {rdkit.__version__} loads but can't read {test}", REINSTALL
        )
    return Check(True, f"RDKit {rdkit.__version__} reads {test}")


def check_workspace(init: str = "syn init") -> tuple[Check, Path | None]:
    """The workspace check, and the workspace folder if it was found.

    ``init`` is how the Fix line says to run init.
    """
    try:
        path = current_workspace()
    except WorkspaceError as error:
        return Check(False, str(error)), None
    missing = [name for name in FOLDERS if not (path / name).is_dir()]
    if not (path / WORKSPACE_CONFIG_NAME).is_file():
        missing.append(WORKSPACE_CONFIG_NAME)
    if missing:
        return Check(
            False,
            f"The workspace at {path} is missing: {', '.join(missing)}",
            f'run {init} "{path}". It adds what is missing and never touches '
            "your files. If it asks about config.toml, answer no to keep yours.",
        ), path
    return Check(True, f"Workspace found at {path}"), path


def check_config(workspace: Path | None) -> tuple[Check, Config | None]:
    """The config check, and the loaded config if it is valid."""
    if workspace is None or not (workspace / WORKSPACE_CONFIG_NAME).is_file():
        return Check(
            False, "Config not checked", "get the workspace check passing first."
        ), None
    try:
        config = load_config(workspace)
    except ConfigError as error:
        return Check(False, str(error)), None
    return Check(True, f"Config is valid: {config.path}"), config


def check_table_folder(workspace: Path, config: Config, area: str) -> Check:
    """Whether ``area``'s tables can be saved where config.toml says (decision 0015)."""
    label = f"{area.capitalize()} folder"
    folder = table_folder(workspace, config, area)
    if not config.folder(area):
        return Check(True, f"{label}: not set, tables go in {folder}")
    if inside_code_folder(folder):
        return Check(
            False,
            f"{label} {folder} is inside Synthase's own code folder ({code_folder()})",
            f'choose a folder outside it for "{area}" under [{FOLDERS_TABLE}] '
            "in config.toml.",
        )
    if not folder.is_dir():
        return Check(
            False,
            f"{label} {folder} doesn't exist",
            f'create it in File Explorer, or change "{area}" under '
            f"[{FOLDERS_TABLE}] in config.toml.",
        )
    return Check(True, f"{label}: {folder}")


def run_checks(init: str = "syn init") -> Report:
    """Every check. ``init`` is how a Fix line says to run init."""
    workspace, folder = check_workspace(init)
    config, loaded = check_config(folder)
    checks = [check_python(), check_rdkit(), workspace, config]
    if loaded is not None:
        checks += [check_table_folder(folder, loaded, area) for area in FOLDER_AREAS]
    return Report(checks, loaded)


@dataclass(frozen=True)
class ReportText:
    """The words of a report, apart from each check's own line.

    ``unverified`` holds a (key, value, source) row for each unverified value.
    """

    heading: str
    unverified_title: str
    unverified: list[tuple[str, str, str]]
    last: str


def report_text(report: Report, rerun: str) -> ReportText:
    """The report's words. ``rerun`` is how to run doctor again."""
    unverified = report.unverified()
    if report.config is None:
        title = (
            "The unverified config values can't be listed until the config is fixed."
        )
    elif not unverified:
        title = "Every config value has been verified."
    else:
        title = (
            f"Unverified config values ({len(unverified)}). "
            "Results that use them show a warning:"
        )
    rows = [
        (entry.key, f"{entry.name}: {entry.describe()}", f"source: {entry.source}")
        for entry in unverified
    ]
    if not report.failed:
        last = "All checks passed."
    elif report.failed == 1:
        last = f"1 check failed. Fix it, then run {rerun} again."
    else:
        last = f"{report.failed} checks failed. Fix them, then run {rerun} again."
    return ReportText(f"Synthase {__version__} self-test", title, rows, last)
