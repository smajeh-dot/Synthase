import hashlib
import json
from datetime import datetime

import pytest

from synthase import history
from synthase.storage import StorageError


def logged(data):
    return [
        json.loads(line)
        for line in (data / "history.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def test_a_change_is_one_json_line_with_every_key(data):
    (data / "experiments.toml").write_text('[E001]\ntitle = "Trial"\n')
    history.log(
        "edit",
        "experiments.toml",
        id="E001",
        name="m_crude",
        old={"value": "2.2110", "unit": "g"},
        new={"value": "2.215", "unit": "g"},
    )
    (entry,) = logged(data)
    assert list(entry) == [
        "ts",
        "action",
        "id",
        "name",
        "old",
        "new",
        "file",
        "sha256",
    ]
    assert entry["action"] == "edit"
    assert entry["new"] == {"value": "2.215", "unit": "g"}
    assert entry["file"] == "experiments.toml"
    expected = hashlib.sha256((data / "experiments.toml").read_bytes()).hexdigest()
    assert entry["sha256"] == expected


def test_the_log_is_only_ever_added_to(data):
    history.log("add", "synthase.toml", name="a")
    first = (data / "history.jsonl").read_text()
    history.log("add", "synthase.toml", name="b")
    assert (data / "history.jsonl").read_text().startswith(first)
    assert [e["name"] for e in history.entries()] == ["a", "b"]


def test_symbols_stay_readable_in_notepad(data):
    history.log("add", "synthase.toml", new={"value": "5", "unit": "µL"})
    assert "µL" in (data / "history.jsonl").read_text(encoding="utf-8")


def test_times_are_stored_with_their_offset():
    stamp = history.now()
    assert datetime.fromisoformat(stamp).utcoffset() is not None
    assert len(stamp) == len("2026-10-21T14:32:07+01:00")


def test_times_are_shown_without_the_offset():
    assert history.shown_time("2026-10-21T14:32:07+01:00") == "2026-10-21 14:32:07"


def test_files_nobody_touched_are_not_reported(data):
    history.log("create_project", "synthase.toml")
    assert history.check_external_edits() == []


def test_a_hand_edit_is_logged_and_reported_once(data):
    (data / "compounds.toml").write_text('[C001]\nname = "Invented acid"\n')
    history.log("add_compound", "compounds.toml", id="C001")
    history.log("create_project", "synthase.toml")
    (data / "compounds.toml").write_text('[C001]\nname = "Invented base"\n')
    assert history.check_external_edits() == [
        "data\\compounds.toml was changed outside Synthase. "
        "The change is noted in the history."
    ]
    entry = history.entries()[-1]
    assert entry["action"] == "external_edit"
    assert entry["file"] == "compounds.toml"
    assert entry["sha256"] == history.file_hash(data / "compounds.toml")
    assert history.check_external_edits() == []


def test_a_new_file_never_logged_counts_as_a_change(data):
    (data / "experiments.toml").write_text('[E001]\ntitle = "Made in Notepad"\n')
    messages = history.check_external_edits()
    assert "data\\experiments.toml was changed outside Synthase." in messages[-1]


def test_a_deleted_file_is_logged_and_reported_once(data):
    (data / "compounds.toml").write_text('[C001]\nname = "Invented acid"\n')
    history.log("add_compound", "compounds.toml", id="C001")
    history.log("create_project", "synthase.toml")
    (data / "compounds.toml").unlink()
    assert history.check_external_edits() == [
        "data\\compounds.toml was deleted outside Synthase. "
        "The deletion is noted in the history."
    ]
    assert history.entries()[-1]["sha256"] is None
    assert history.check_external_edits() == []


def test_a_broken_history_line_is_refused(data):
    history.log("create_project", "synthase.toml")
    with open(data / "history.jsonl", "a", encoding="utf-8") as file:
        file.write("{not json\n")
    with pytest.raises(StorageError) as raised:
        history.entries()
    assert str(raised.value) == (
        "data\\history.jsonl has a mistake on line 2, so Synthase won't load it. "
        "Fix it in Notepad, then try again."
    )


def test_no_history_yet_is_empty(data):
    assert history.entries() == []
