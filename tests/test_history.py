"""Command history, with invented commands in a temporary workspace."""

import pytest

from synthase import history as history_module
from synthase.history import FILE_NAME, History, history_file
from synthase.workspace import remember


def invented_workspace(tmp_path):
    folder = tmp_path / "Documents" / "Synthase"
    folder.mkdir(parents=True)
    remember(folder)
    return folder


def test_the_file_is_in_the_workspace(tmp_path):
    folder = invented_workspace(tmp_path)
    assert history_file() == folder / FILE_NAME


def test_with_no_workspace_there_is_no_file():
    assert history_file() is None


def test_up_steps_back_newest_first_and_stops_at_the_oldest():
    history = History(None, ["/one", "/two", "/three"])
    assert [history.back() for _ in range(4)] == ["/three", "/two", "/one", None]


def test_down_steps_forward_then_empties_the_bar_then_does_nothing():
    history = History(None, ["/one", "/two"])
    history.back()
    history.back()
    assert [history.forward() for _ in range(3)] == ["/two", "", None]


def test_an_empty_history_does_nothing():
    history = History(None)
    assert history.back() is None
    assert history.forward() is None


def test_adding_saves_the_file_and_resets_the_steps(tmp_path):
    path = tmp_path / FILE_NAME
    history = History(path)
    history.add("/compound show 1")
    history.back()
    history.add("/zzz")
    assert path.read_text(encoding="utf-8") == "/compound show 1\n/zzz\n"
    assert history.back() == "/zzz"


def test_a_command_typed_twice_in_a_row_is_saved_once(tmp_path):
    history = History(tmp_path / FILE_NAME)
    for line in ("/one", "/one", "/two", "/one"):
        history.add(line)
    assert history.lines == ["/one", "/two", "/one"]


def test_only_the_latest_commands_are_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(history_module, "LIMIT", 3)
    path = tmp_path / FILE_NAME
    history = History(path)
    for number in range(5):
        history.add(f"/word{number}")
    assert path.read_text(encoding="utf-8").splitlines() == [
        "/word2",
        "/word3",
        "/word4",
    ]
    assert History.load(path).lines == ["/word2", "/word3", "/word4"]


def test_load_reads_the_saved_commands_back(tmp_path):
    path = tmp_path / FILE_NAME
    path.write_text("/one\n\n/two\n", encoding="utf-8")
    assert History.load(path).lines == ["/one", "/two"]


def test_load_starts_empty_when_the_file_is_missing_or_unreadable(tmp_path):
    assert History.load(None).lines == []
    assert History.load(tmp_path / FILE_NAME).lines == []
    broken = tmp_path / "broken.txt"
    broken.write_bytes(b"\xff\xfe\xfa")
    assert History.load(broken).lines == []


def test_saving_into_a_missing_folder_raises_but_keeps_the_command(tmp_path):
    history = History(tmp_path / "gone" / FILE_NAME)
    with pytest.raises(OSError):
        history.add("/one")
    assert history.back() == "/one"
