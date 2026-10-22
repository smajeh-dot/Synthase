import pytest
from textual import constants

from synthase import older_console


@pytest.fixture(autouse=True)
def full_console(monkeypatch):
    """Every test draws as Windows Terminal does, whatever runs it: symbols and
    full colour. The older console's tests change this (decision 0029)."""
    monkeypatch.setattr(older_console, "output_encoding", lambda: "utf-8")
    monkeypatch.setenv("WT_SESSION", "invented")
    monkeypatch.setattr(constants, "COLOR_SYSTEM", "truecolor")


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A project folder in a temporary folder, through SYNTHASE_HOME."""
    monkeypatch.setenv("SYNTHASE_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def data(home):
    """An invented project's data folder, recognised by data\\synthase.toml."""
    folder = home / "data"
    folder.mkdir()
    (folder / "synthase.toml").write_text('name = "Invented project"\n')
    return folder
