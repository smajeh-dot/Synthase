"""`syn doctor`: checks the install and the setup, and finds unverified values.

The rules are in docs/decisions/0010-syn-doctor.md.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

from synthase.config import (
    WORKSPACE_CONFIG_NAME,
    Config,
    ConfigError,
    ConfigValue,
    load_config,
)
from synthase.workspace import FOLDERS, WorkspaceError, current_workspace

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


def check_workspace() -> tuple[Check, Path | None]:
    """The workspace check, and the workspace folder if it was found."""
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
            f'run syn init "{path}". It adds what is missing and never touches '
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


def run_checks() -> Report:
    workspace, folder = check_workspace()
    config, loaded = check_config(folder)
    return Report([check_python(), check_rdkit(), workspace, config], loaded)
