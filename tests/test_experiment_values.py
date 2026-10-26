"""Storing, editing, deleting and the history of values (decision 0036).

Every title, name and value is invented.
"""

import tomllib

import pytest

from synthase import experiment_values as values
from synthase import experiments, history
from synthase.experiment_values import ValuesError
from synthase.values import Entry

M_CRUDE = Entry("m_crude", "2.2110", "g", "0.001")
M_SALICYLIC = Entry("m_salicylic", "2.003", "g", "0.001", "Balance B2")


@pytest.fixture
def two(data):
    """E001 and E002, each empty."""
    experiments.create("First", [])
    experiments.create("Second", [])
    return data


def stored(data, experiment="E002"):
    path = data / "experiments.toml"
    return tomllib.loads(path.read_text("utf-8"))[experiment]["values"]


def test_add_stores_the_entry_exactly_and_logs_it(two):
    values.add("E002", [M_CRUDE, M_SALICYLIC])
    assert stored(two) == {
        "m_crude": {"value": "2.2110", "unit": "g", "unc": "0.001"},
        "m_salicylic": {
            "value": "2.003",
            "unit": "g",
            "unc": "0.001",
            "note": "Balance B2",
        },
    }
    adds = [e for e in history.entries() if e["action"] == "add"]
    assert [(e["id"], e["name"], e["new"]["value"]) for e in adds] == [
        ("E002", "m_crude", "2.2110"),
        ("E002", "m_salicylic", "2.003"),
    ]
    assert history.check_external_edits() == []


def test_a_value_belongs_to_one_experiment(two):
    values.add("E001", [Entry("m_crude", "1.0", "g")])
    values.add("E002", [Entry("m_crude", "2.2110", "g")])
    values.edit("E002", Entry("m_crude", "2.215", "g"))
    assert stored(two, "E001")["m_crude"]["value"] == "1.0"
    assert stored(two, "E002")["m_crude"]["value"] == "2.215"
    assert values.names("E001") == ["m_crude"]


def test_add_on_an_existing_name_says_to_use_edit(two):
    values.add("E002", [M_CRUDE])
    with pytest.raises(ValuesError) as refused:
        values.add("E002", [Entry("m_crude", "9", "g")])
    assert refused.value.lines == [
        "m_crude already exists in E002.",
        "Use 'value edit' to change it.",
    ]
    assert stored(two)["m_crude"]["value"] == "2.2110"


def test_a_refused_add_saves_none_of_the_batch(two):
    values.add("E002", [M_CRUDE])
    with pytest.raises(ValuesError):
        values.add("E002", [M_SALICYLIC, M_CRUDE])
    assert values.names("E002") == ["m_crude"]


def test_edit_replaces_the_whole_entry_and_says_what_was_cleared(two):
    values.add("E002", [M_CRUDE, M_SALICYLIC])
    new = Entry("m_crude", "2.215", "g")
    old = values.edit("E002", new)
    assert old == M_CRUDE
    assert stored(two)["m_crude"] == {"value": "2.215", "unit": "g"}
    assert values.removed(old, new) == " (uncertainty removed)"
    both = values.removed(M_SALICYLIC, Entry("m_salicylic", "2", "g"))
    assert both == " (uncertainty and note removed)"
    assert values.removed(old, Entry("m_crude", "2.2", "g", "0.001")) == ""
    assert values.names("E002") == ["m_crude", "m_salicylic"]


def test_edit_on_a_missing_name_suggests_and_points_to_add(two):
    values.add("E002", [M_CRUDE, M_SALICYLIC])
    with pytest.raises(ValuesError) as refused:
        values.edit("E002", Entry("m_crud", "1", "g"))
    assert refused.value.lines == [
        "There is no value 'm_crud' in E002.",
        "Did you mean: m_crude, m_salicylic?",
        "Use 'value add' to store a new one.",
    ]
    with pytest.raises(ValuesError) as refused:
        values.edit("E002", Entry("xyz", "1", "g"))
    assert refused.value.lines[1] == "Values: m_crude, m_salicylic."


def test_a_missing_name_in_an_experiment_with_no_values(two):
    with pytest.raises(ValuesError) as refused:
        values.edit("E002", Entry("m_crude", "1", "g"))
    assert refused.value.lines == [
        "E002 has no values yet.",
        "Use 'value add' to store one.",
    ]


def test_delete_removes_the_value_and_keeps_its_history(two):
    values.add("E002", [M_CRUDE, M_SALICYLIC])
    assert values.delete("E002", "m_crude") == M_CRUDE
    assert values.names("E002") == ["m_salicylic"]
    assert [e["action"] for e in history.entries()][-1] == "delete"
    with pytest.raises(ValuesError) as refused:
        values.read("E002", "m_crude")
    assert refused.value.lines[0] == "There is no value 'm_crude' in E002."
    assert len(values.versions("E002", "m_crude")) == 2


def test_read_gives_the_stored_entry(two):
    values.add("E002", [M_SALICYLIC])
    assert values.read("E002", "m_salicylic") == M_SALICYLIC


def test_history_lists_every_version_with_the_digits_kept(two):
    values.add("E002", [M_CRUDE])
    values.edit("E002", Entry("m_crude", "2.215", "g"))
    values.delete("E002", "m_crude")
    values.add("E002", [Entry("m_crude", "3.0", "g")])
    lines = values.versions("E002", "m_crude")
    assert all(history.shown_time(line[:19]) == line[:19] for line in lines)
    assert [line[19:] for line in lines] == [
        "  added    m_crude  2.2110 g +/- 0.001",
        "  edited   m_crude  2.2110 g +/- 0.001 -> 2.215 g",
        "  deleted  m_crude",
        "  added    m_crude  3.0 g",
    ]


def test_history_is_for_one_experiment_and_one_name(two):
    values.add("E001", [Entry("m_crude", "1.0", "g")])
    values.add("E002", [Entry("m_crude", "2.2110", "g"), M_SALICYLIC])
    assert len(values.versions("E001", "m_crude")) == 1
    assert values.versions("E002", "m_crude")[0].endswith("m_crude  2.2110 g")


def test_history_includes_the_first_version_exp_create_wrote(data):
    experiments.create("First", [M_SALICYLIC])
    assert values.versions("E001", "m_salicylic")[0].endswith(
        "added    m_salicylic  2.003 g +/- 0.001 # Balance B2"
    )


def test_history_of_a_name_never_stored(two):
    values.add("E002", [M_CRUDE])
    with pytest.raises(ValuesError) as refused:
        values.versions("E002", "m_crud")
    assert refused.value.lines == [
        "There is no history for 'm_crud' in E002.",
        "Did you mean: m_crude?",
    ]
    with pytest.raises(ValuesError) as refused:
        values.versions("E001", "m_crude")
    assert refused.value.lines == ["There is no history for 'm_crude' in E001."]


def test_a_failed_save_changes_nothing(two, monkeypatch):
    def held(path, doc):
        raise OSError("held")

    with monkeypatch.context() as patched:
        patched.setattr(values, "save_toml", held)
        with pytest.raises(OSError):
            values.add("E002", [M_CRUDE])
    assert values.names("E002") == []
    assert not [e for e in history.entries() if e["action"] == "add"]
