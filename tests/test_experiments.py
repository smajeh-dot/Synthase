"""Experiments: storing, finding and remembering them (decision 0033).

Every title, name and value is invented.
"""

import tomllib

import pytest

from synthase import experiments, history
from synthase.experiments import ExperimentError
from synthase.values import Entry, EntryError

M_CRUDE = Entry("m_crude", "2.2110", "g")
M_SALICYLIC = Entry("m_salicylic", "2.003", "g", "0.001", "Balance B2")


def text(data):
    return (data / "experiments.toml").read_text("utf-8")


def test_create_writes_the_approved_layout(data):
    first, _ = experiments.create("First attempt", [])
    second, created = experiments.create(
        "Recrystallisation trial 2",
        [M_SALICYLIC, Entry("c_HCl", "0.100", "mol/dm^3"), M_CRUDE],
    )
    assert (first, second) == ("E001", "E002")
    assert text(data) == (
        "[E001]\n"
        'title = "First attempt"\n'
        f'created = "{tomllib.loads(text(data))["E001"]["created"]}"\n'
        'x_unit = "s"\n'
        "\n"
        "[E001.values]\n"
        "\n"
        "[E002]\n"
        'title = "Recrystallisation trial 2"\n'
        f'created = "{created}"\n'
        'x_unit = "s"\n'
        "\n"
        "[E002.values]\n"
        'm_salicylic = { value = "2.003", unit = "g", unc = "0.001", '
        'note = "Balance B2" }\n'
        'c_HCl = { value = "0.100", unit = "mol/dm^3" }\n'
        'm_crude = { value = "2.2110", unit = "g" }'
    )
    assert "#" not in text(data)


def test_numbers_are_kept_as_text_and_odd_names_are_quoted(data):
    experiments.create("Invented", [M_CRUDE, Entry("m_crude(2)", "1.95", "g")])
    saved = tomllib.loads(text(data))["E001"]
    assert saved["values"]["m_crude"] == {"value": "2.2110", "unit": "g"}
    assert saved["values"]["m_crude(2)"] == {"value": "1.95", "unit": "g"}
    assert '"m_crude(2)" = ' in text(data)
    assert saved["x_unit"] == "s"
    assert history.shown_time(saved["created"])


def test_create_logs_the_experiment_each_value_and_the_counter(data):
    new_id, _ = experiments.create("Invented", [M_SALICYLIC, M_CRUDE])
    log = history.entries()
    assert [(e["action"], e["id"], e["name"], e["file"]) for e in log] == [
        ("create_experiment", "E001", None, "experiments.toml"),
        ("add", "E001", "m_salicylic", "experiments.toml"),
        ("add", "E001", "m_crude", "experiments.toml"),
        ("issue_id", "E001", None, "synthase.toml"),
    ]
    assert log[0]["new"] == "Invented"
    assert log[1]["new"] == {
        "value": "2.003",
        "unit": "g",
        "unc": "0.001",
        "note": "Balance B2",
    }
    assert log[2]["new"] == {"value": "2.2110", "unit": "g"}
    assert new_id == "E001"
    assert history.check_external_edits() == []


def test_ids_count_up_and_are_never_reused(data):
    assert [experiments.create(t, [])[0] for t in "abc"] == ["E001", "E002", "E003"]
    (data / "experiments.toml").write_text("")
    assert experiments.create("d", [])[0] == "E004"


def test_a_failed_save_uses_no_id(data, monkeypatch):
    def held(path, doc):
        raise OSError("held")

    with monkeypatch.context() as patched:
        patched.setattr(experiments, "save_toml", held)
        with pytest.raises(OSError):
            experiments.create("Invented", [])
    assert experiments.create("Invented", [])[0] == "E001"


def test_ids_are_in_number_order(data):
    for title in "abc":
        experiments.create(title, [])
    assert experiments.ids() == ["E001", "E002", "E003"]
    assert experiments.title("E002") == "b"


def test_find_by_id_or_exact_title(data):
    experiments.create("Recrystallisation trial 2", [])
    experiments.create("Second try", [])
    assert experiments.find("E002") == "E002"
    assert experiments.find("Recrystallisation trial 2") == "E001"


def test_an_id_wins_over_a_title(data):
    experiments.create("E002", [])
    experiments.create("Second try", [])
    assert experiments.find("E002") == "E002"


def test_find_with_no_experiments(data):
    with pytest.raises(ExperimentError) as refused:
        experiments.find("E001")
    assert str(refused.value) == "There are no experiments yet."


def test_find_suggests_the_closest(data):
    experiments.create("Recrystallisation trial 2", [])
    experiments.create("Second try", [])
    with pytest.raises(ExperimentError) as refused:
        experiments.find("E003")
    assert str(refused.value) == "Unknown experiment 'E003'. Did you mean: E001, E002?"
    with pytest.raises(ExperimentError) as refused:
        experiments.find("Recrystalisation trial 2")
    assert str(refused.value).startswith(
        "Unknown experiment 'Recrystalisation trial 2'. Did you mean: "
        "Recrystallisation trial 2"
    )


def test_find_lists_every_id_when_nothing_is_close(data):
    experiments.create("Recrystallisation trial 2", [])
    experiments.create("Second try", [])
    with pytest.raises(ExperimentError) as refused:
        experiments.find("zzzzzz")
    assert str(refused.value) == "Unknown experiment 'zzzzzz'. Experiments: E001, E002."


def test_titles_match_exactly_including_case(data):
    experiments.create("Trial", [])
    with pytest.raises(ExperimentError):
        experiments.find("trial")


def test_two_experiments_with_one_title_are_named(data):
    for _ in range(2):
        experiments.create("Trial", [])
    experiments.create("Other", [])
    with pytest.raises(ExperimentError) as refused:
        experiments.find("Trial")
    assert str(refused.value) == (
        'Several experiments are called "Trial": E001, E002. Open one by its ID.'
    )
    assert experiments.find("E002") == "E002"


def test_the_last_opened_experiment_is_remembered_in_data(data):
    experiments.create("Invented", [])
    experiments.remember("E001")
    assert (data / ".last-experiment").read_text("utf-8") == "E001\n"
    assert experiments.last_opened() == "E001"
    # Not a logged data file: choosing one changes nothing the history tracks.
    assert history.check_external_edits() == []


def test_nothing_is_remembered_if_it_was_deleted_or_unreadable(data):
    assert experiments.last_opened() is None
    experiments.create("Invented", [])
    experiments.remember("E002")
    assert experiments.last_opened() is None
    (data / ".last-experiment").write_bytes(b"\xff\xfe")
    assert experiments.last_opened() is None
    (data / ".last-experiment").write_text("not an id")
    assert experiments.last_opened() is None


def test_the_file_or_manual_question():
    assert experiments.check_source("m") is None
    assert experiments.check_source("f") == (
        "Loading values from a file isn't built yet."
    )
    assert experiments.check_source("x") == "Type f or m."
    assert experiments.check_source("M") == "Type f or m."


def test_a_manual_line_is_read_as_a_value_entry():
    assert experiments.read_line("m_crude 2.2110 g +/- 0.001 # Balance B2") == Entry(
        "m_crude", "2.2110", "g", "0.001", "Balance B2"
    )
    assert experiments.read_line("c_HCl 0.100 mol dm^-3").unit == "mol dm^-3"


@pytest.mark.parametrize("line", ["m_crude", "m_crude 2.2", "m_crude 2.2 g 0.1"])
def test_a_line_with_a_missing_part_is_refused(line):
    with pytest.raises(EntryError) as refused:
        experiments.read_line(line)
    assert str(refused.value) == "Each line needs a name, a value and a unit."


def test_a_bad_unit_is_refused_as_in_0032():
    with pytest.raises(EntryError) as refused:
        experiments.read_line("m_crude 2.2 gg")
    assert str(refused.value) == "Unknown unit 'gg'. Did you mean: g, kg?"


def test_counted():
    assert [experiments.counted(n) for n in (0, 1, 2)] == [
        "0 values",
        "1 value",
        "2 values",
    ]
