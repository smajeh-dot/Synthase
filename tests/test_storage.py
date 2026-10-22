import pytest
import tomlkit

from synthase import storage
from synthase.storage import FolderState, StorageError


def test_the_project_folder_is_synthase_home(home):
    assert storage.project_folder() == home
    assert storage.data_folder() == home / "data"


def test_without_synthase_home_it_is_the_current_folder(tmp_path, monkeypatch):
    monkeypatch.delenv("SYNTHASE_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    assert storage.project_folder() == tmp_path


def test_a_folder_without_data_is_not_a_project(home):
    assert storage.folder_state() is FolderState.NO_PROJECT


def test_a_data_folder_without_synthase_toml_is_not_synthases(home):
    (home / "data").mkdir()
    (home / "data" / "results.csv").write_text("a,b\n")
    assert storage.folder_state() is FolderState.NOT_SYNTHASE


def test_a_data_folder_with_synthase_toml_is_a_project(data):
    assert storage.folder_state() is FolderState.PROJECT


def test_checking_the_folder_creates_nothing(home):
    storage.folder_state()
    assert list(home.iterdir()) == []


def test_typed_numbers_are_kept_exactly(data):
    path = data / "experiments.toml"
    doc = tomlkit.document()
    doc["E001"] = {"values": {"m_crude": {"value": "2.100", "unit": "g"}}}
    storage.save_toml(path, doc)
    assert storage.read_toml(path)["E001"]["values"]["m_crude"]["value"] == "2.100"
    assert 'value = "2.100"' in path.read_text()


def test_a_number_that_is_not_text_is_never_saved(data):
    doc = tomlkit.document()
    doc["E001"] = {"values": {"m_crude": {"value": 2.100, "unit": "g"}}}
    with pytest.raises(TypeError):
        storage.save_toml(data / "experiments.toml", doc)
    assert not (data / "experiments.toml").exists()


def test_a_hand_added_comment_survives_a_save(data):
    path = data / "compounds.toml"
    path.write_text(
        '# Bought in October\n[C001]\nname = "Invented acid"  # check the label\n'
    )
    doc = storage.read_toml(path)
    doc["C001"]["formula"] = "C7H6O3"
    storage.save_toml(path, doc)
    text = path.read_text()
    assert text.startswith("# Bought in October\n")
    assert 'name = "Invented acid"  # check the label' in text
    assert 'formula = "C7H6O3"' in text


def test_a_missing_file_reads_as_empty(data):
    assert storage.read_toml(data / "compounds.toml") == {}


def test_a_file_saved_with_a_byte_order_mark_still_reads(data):
    path = data / "compounds.toml"
    path.write_bytes('﻿[C001]\nname = "Invented acid"\n'.encode())
    assert storage.read_toml(path)["C001"]["name"] == "Invented acid"


def test_an_invalid_file_names_its_line(data):
    path = data / "experiments.toml"
    path.write_text('[E001]\ntitle = "Trial"\nnote = \n')
    with pytest.raises(StorageError) as raised:
        storage.read_toml(path)
    assert str(raised.value) == (
        "data\\experiments.toml has a mistake on line 3, so Synthase won't load it. "
        "Fix it in Notepad, then try again."
    )


def test_a_file_that_is_not_utf8_names_its_line(data):
    path = data / "experiments.toml"
    path.write_bytes(b'[E001]\ntitle = "Tri\xe9l"\n')
    with pytest.raises(StorageError) as raised:
        storage.read_toml(path)
    assert "line 2," in str(raised.value)


def held(fails):
    """An os.replace that is refused ``fails`` times, then works."""
    real = storage.os.replace
    calls = []

    def replace(src, dst):
        calls.append(dst)
        if len(calls) <= fails:
            raise PermissionError("in use")
        real(src, dst)

    return replace, calls


def test_a_briefly_held_file_is_saved_on_a_retry(data, monkeypatch):
    replace, calls = held(fails=2)
    monkeypatch.setattr(storage.os, "replace", replace)
    sleeps = []
    monkeypatch.setattr(storage.time, "sleep", sleeps.append)
    path = data / "experiments.toml"
    storage.save_toml(path, tomlkit.parse('[E001]\ntitle = "Trial"\n'))
    assert len(calls) == 3
    assert sleeps == [0.2, 0.2]
    assert storage.read_toml(path)["E001"]["title"] == "Trial"


def test_a_held_file_gives_up_and_keeps_the_old_file(data, monkeypatch):
    path = data / "experiments.toml"
    path.write_text('title = "Old"\n')
    replace, calls = held(fails=99)
    monkeypatch.setattr(storage.os, "replace", replace)
    monkeypatch.setattr(storage.time, "sleep", lambda seconds: None)
    with pytest.raises(StorageError) as raised:
        storage.save_toml(path, tomlkit.parse('title = "New"\n'))
    assert str(raised.value) == (
        "Couldn't save data\\experiments.toml: another program is using it. "
        "Nothing was changed. Close that program, then try again."
    )
    assert len(calls) == 5
    assert path.read_text() == 'title = "Old"\n'
    assert sorted(p.name for p in data.iterdir()) == [
        "experiments.toml",
        "synthase.toml",
    ]


def test_a_save_leaves_no_temporary_file(data):
    storage.save_toml(data / "compounds.toml", tomlkit.parse('[C001]\nname = "A"\n'))
    assert sorted(p.name for p in data.iterdir()) == [
        "compounds.toml",
        "synthase.toml",
    ]
