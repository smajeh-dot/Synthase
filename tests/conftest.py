import pytest

from synthase import workspace


@pytest.fixture(autouse=True)
def private_settings(tmp_path, monkeypatch):
    """Keep every test away from the real AppData and Documents folders."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    monkeypatch.setattr(workspace, "documents_folder", lambda: tmp_path / "Documents")
