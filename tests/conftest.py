import pytest


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
