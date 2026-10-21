import pytest

from synthase import history, ids, storage


def write(data, name, text):
    (data / name).write_text(text)


def counters(data):
    return dict(storage.read_toml(data / "synthase.toml").get("counters", {}))


def test_a_new_project_starts_at_001(data):
    assert ids.next_id("E") == "E001"
    assert ids.next_id("C") == "C001"


def test_the_next_id_follows_the_counter(data):
    write(data, "synthase.toml", 'name = "P"\n[counters]\nE = 3\n')
    write(data, "experiments.toml", '[E001]\ntitle = "A"\n[E003]\ntitle = "B"\n')
    assert ids.next_id("E") == "E004"


def test_a_deleted_id_is_never_reused(data):
    # E003 was the last issued, then removed from the file in Notepad.
    write(data, "synthase.toml", 'name = "P"\n[counters]\nE = 3\n')
    write(data, "experiments.toml", '[E001]\ntitle = "A"\n')
    assert ids.next_id("E") == "E004"


def test_never_lower_than_the_highest_id_in_the_file(data):
    # E007 was added in Notepad, past the counter.
    write(data, "synthase.toml", 'name = "P"\n[counters]\nC = 2\n')
    write(data, "compounds.toml", '[C001]\nname = "A"\n[C007]\nname = "B"\n')
    assert ids.next_id("C") == "C008"


def test_after_999_the_number_grows_to_four_digits(data):
    write(data, "synthase.toml", 'name = "P"\n[counters]\nE = 999\n')
    assert ids.next_id("E") == "E1000"
    write(data, "experiments.toml", '[E1000]\ntitle = "A"\n')
    assert ids.next_id("E") == "E1001"


def test_ids_are_per_project(tmp_path, monkeypatch):
    for name, last in (("one", 4), ("two", 1)):
        folder = tmp_path / name / "data"
        folder.mkdir(parents=True)
        write(folder, "synthase.toml", f'name = "{name}"\n[counters]\nC = {last}\n')
    monkeypatch.setenv("SYNTHASE_HOME", str(tmp_path / "one"))
    assert ids.next_id("C") == "C005"
    monkeypatch.setenv("SYNTHASE_HOME", str(tmp_path / "two"))
    assert ids.next_id("C") == "C002"


def test_other_letters_and_odd_keys_are_ignored(data):
    write(
        data, "experiments.toml", '[E002]\nx = "1"\n[e009]\nx = "1"\n[E09]\nx = "1"\n'
    )
    assert ids.next_id("E") == "E003"


@pytest.mark.parametrize(
    ("text", "number"),
    [("E001", 1), ("E999", 999), ("E1000", 1000), ("C001", None), ("e001", None)],
)
def test_reading_an_id(text, number):
    assert ids.id_number(text, "E") == number


def test_recording_an_id_moves_the_counter_up_only(data):
    ids.record_id("E004")
    assert counters(data) == {"E": 4}
    ids.record_id("E002")
    assert counters(data) == {"E": 4}
    assert storage.read_toml(data / "synthase.toml")["name"] == "Invented project"


def test_recording_an_id_is_logged_so_it_is_not_an_outside_edit(data):
    history.log("create_experiment", "synthase.toml")
    ids.record_id("E001")
    assert history.entries()[-1]["action"] == "issue_id"
    assert history.entries()[-1]["id"] == "E001"
    assert history.check_external_edits() == []
