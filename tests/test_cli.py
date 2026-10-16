import shutil
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest

import synthase
from synthase.cli import main


def test_package_version_matches_installed_metadata():
    assert synthase.__version__ == version("synthase-lab")


def test_version_prints_package_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"syn {synthase.__version__}"


def test_help_exits_cleanly_and_names_the_command(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.startswith("usage: syn")


def test_no_arguments_shows_help(capsys):
    assert main([]) == 0
    assert capsys.readouterr().out.startswith("usage: syn")


def test_running_as_module_prints_version():
    result = subprocess.run(
        [sys.executable, "-m", "synthase", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == f"syn {synthase.__version__}"


def test_installed_syn_command_prints_version():
    # The `syn` launcher sits next to the Python that runs the tests
    # (`.venv\Scripts` on Windows, `.venv/bin` elsewhere).
    syn = shutil.which("syn", path=str(Path(sys.executable).parent))
    assert syn is not None, "syn is not installed: run pip install -e .[dev]"
    result = subprocess.run(
        [syn, "--version"], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == f"syn {synthase.__version__}"
