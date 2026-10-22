"""Projects: creating, showing and renaming one (decision 0031).

Every name and folder is invented.
"""

import tomllib

import pytest

from synthase import history, project
from synthase.startup import FOREIGN
from synthase.storage import StorageError


def test_create_writes_the_name_and_the_time_and_logs_it(home):
    project.create("Invented project")
    saved = tomllib.loads((home / "data" / "synthase.toml").read_text("utf-8"))
    assert saved["name"] == "Invented project"
    assert history.shown_time(saved["created"])
    [entry] = history.entries()
    assert entry["action"] == "create_project"
    assert entry["new"] == "Invented project"
    assert entry["file"] == "synthase.toml"
    # Logged as Synthase left it, so the next start notices nothing.
    assert history.check_external_edits() == []


def test_create_refuses_in_a_project(data):
    with pytest.raises(StorageError) as refused:
        project.create("Another name")
    assert str(refused.value) == (
        'This folder is already the Synthase project "Invented project". '
        "To start another, run synthase in another folder."
    )


def test_create_refuses_a_data_folder_that_isnt_synthases(home):
    (home / "data").mkdir()
    with pytest.raises(StorageError) as refused:
        project.create("Invented project")
    assert str(refused.value) == FOREIGN
    assert list((home / "data").iterdir()) == []


def test_a_failed_save_leaves_the_folder_as_it_was(home, monkeypatch):
    def held(path, doc):
        raise StorageError("held")

    monkeypatch.setattr(project, "save_toml", held)
    with pytest.raises(StorageError):
        project.create("Invented project")
    assert list(home.iterdir()) == []


def test_details_count_experiments_and_compounds(home):
    project.create("Invented project")
    data = home / "data"
    (data / "experiments.toml").write_text('[E001]\ntitle = "a"\n[E002]\n')
    (data / "compounds.toml").write_text('[C001]\nname = "b"\n')
    details = dict(project.details())
    assert list(details) == ["Name", "Created", "Folder", "Experiments", "Compounds"]
    assert details["Name"] == "Invented project"
    assert details["Folder"] == str(home)
    assert details["Experiments"] == "2"
    assert details["Compounds"] == "1"


def test_details_of_a_new_project(home):
    project.create("Invented project")
    details = dict(project.details())
    assert (details["Experiments"], details["Compounds"]) == ("0", "0")


def test_rename_saves_and_logs_old_and_new(home):
    project.create("Invented project")
    path = home / "data" / "synthase.toml"
    path.write_text(path.read_text("utf-8") + "# kept comment\n", "utf-8")
    history.check_external_edits()
    project.rename("Invented project 2")
    text = path.read_text("utf-8")
    assert tomllib.loads(text)["name"] == "Invented project 2"
    assert "# kept comment" in text
    entry = history.entries()[-1]
    assert (entry["action"], entry["old"], entry["new"]) == (
        "edit_project",
        "Invented project",
        "Invented project 2",
    )
    assert history.check_external_edits() == []
