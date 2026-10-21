import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _in_git_checkout():
    # A ZIP download from GitHub has no .git folder, so these checks can't run.
    if shutil.which("git") is None:
        return False
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and Path(result.stdout.strip()) == REPO_ROOT


pytestmark = pytest.mark.skipif(
    not _in_git_checkout(), reason="needs git and a git checkout of the repo"
)


def is_ignored(path):
    # --no-index checks the rules even if the path is tracked or doesn't exist.
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", path], cwd=REPO_ROOT
    )
    return result.returncode == 0


def attribute(path, name):
    result = subprocess.run(
        ["git", "check-attr", name, "--", path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    # Output looks like "path: name: value".
    return result.stdout.rsplit(": ", 1)[1].strip()


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "data/run.csv",
        ".venv/Scripts/python.exe",
        "src/synthase/__pycache__/app.cpython-313.pyc",
    ],
)
def test_forbidden_files_are_ignored(path):
    assert is_ignored(path)


@pytest.mark.parametrize(
    "path",
    ["data/samples/example.csv", "src/synthase/app.py", "README.md"],
)
def test_tool_files_and_samples_are_not_ignored(path):
    assert not is_ignored(path)


@pytest.mark.parametrize(
    ("path", "eol"),
    [
        ("scripts/setup.ps1", "crlf"),
        ("scripts/post-merge", "lf"),
        ("src/synthase/app.py", "lf"),
    ],
)
def test_line_endings(path, eol):
    assert attribute(path, "eol") == eol


@pytest.mark.parametrize("path", ["docs/figure.png", "register.db"])
def test_binary_files_are_not_treated_as_text(path):
    assert attribute(path, "text") == "unset"
