"""The compound library (decision 0037).

Every compound, name and number is invented.
"""

import tomllib

import pytest
from test_app import messages, run, typing

from synthase import compounds, history
from synthase.compounds import CompoundError
from synthase.storage import read_toml
from synthase.values import EntryError


@pytest.fixture
def project(data):
    """An invented project as Synthase left it: its files logged in the history."""
    history.log("create_project", "synthase.toml")
    return data


def stored(data):
    return tomllib.loads((data / "compounds.toml").read_text("utf-8"))


def counter(data):
    return read_toml(data / "synthase.toml")["counters"]["C"]


def test_ids_run_in_order_and_the_counter_follows_the_compound(data):
    first = compounds.create({"name": "Alpha"})
    second = compounds.create({"name": "Beta"})
    assert (first, second) == ("C001", "C002")
    assert counter(data) == 2
    assert [e["action"] for e in history.entries()] == [
        "add_compound",
        "issue_id",
        "add_compound",
        "issue_id",
    ]
    assert history.check_external_edits() == []


def test_unit_fields_are_stored_exactly_as_typed(data):
    fields = compounds.build(
        {
            "name": "Invented acid",
            "formula": "C9H9O9",
            "molar_mass": "138.120 g/mol",
            "density": "1.0800 g/cm^3",
            "purity": "99.50 %",
            "note": "Lot 7",
        }
    )
    compounds.create(fields)
    assert stored(data) == {
        "C001": {
            "name": "Invented acid",
            "formula": "C9H9O9",
            "molar_mass": {"value": "138.120", "unit": "g/mol"},
            "density": {"value": "1.0800", "unit": "g/cm^3"},
            "purity": {"value": "99.50", "unit": "%"},
            "note": "Lot 7",
        }
    }
    assert compounds.get("C001")["molar_mass"] == {"value": "138.120", "unit": "g/mol"}


def test_nothing_is_calculated_or_cross_checked(data):
    fields = compounds.build({"formula": "H2", "molar_mass": "1000 g/mol"})
    compounds.create(fields)
    assert compounds.get("C001") == {
        "formula": "H2",
        "molar_mass": {"value": "1000", "unit": "g/mol"},
    }


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("138.120", compounds.NEEDS_UNIT),
        ("1x8 g/mol", "'1x8' isn't a number."),
        ("138.120 gg", "Unknown unit 'gg'. Did you mean: g, kg?"),
    ],
)
def test_a_bad_unit_field_is_refused(text, reason):
    assert compounds.check_unit_field(text) == reason
    with pytest.raises(EntryError):
        compounds.read_unit_field(text)


def test_a_unit_with_a_space_is_kept(data):
    fields = compounds.build({"molar_mass": "138.120 g mol^-1"})
    assert fields["molar_mass"] == {"value": "138.120", "unit": "g mol^-1"}


def test_an_edit_keeps_clears_and_changes_and_logs_it(data):
    compounds.create(
        compounds.build({"name": "Alpha", "formula": "X", "molar_mass": "10.50 g/mol"})
    )
    old = compounds.get("C001")
    answers = {
        "name": "Alpha",
        "formula": None,
        "molar_mass": "10.50 g/mol",
        "density": "2.0 g/cm^3",
    }
    assert compounds.edit("C001", compounds.build(answers, old))
    assert stored(data)["C001"] == {
        "name": "Alpha",
        "molar_mass": {"value": "10.50", "unit": "g/mol"},
        "density": {"value": "2.0", "unit": "g/cm^3"},
    }
    last = history.entries()[-1]
    assert last["action"] == "edit_compound"
    assert last["old"]["formula"] == "X"
    assert "formula" not in last["new"]


def test_an_edit_that_changes_nothing_saves_and_logs_nothing(data):
    compounds.create({"name": "Alpha"})
    before = (data / "compounds.toml").read_bytes()
    lines = len(history.entries())
    assert not compounds.edit("C001", compounds.build({"name": "Alpha"}))
    assert (data / "compounds.toml").read_bytes() == before
    assert len(history.entries()) == lines


def test_an_edit_leaves_a_hand_added_key_alone(data):
    compounds.create({"name": "Alpha"})
    path = data / "compounds.toml"
    path.write_text(path.read_text("utf-8") + 'extra = "kept"\n', "utf-8")
    compounds.edit("C001", compounds.build({"name": "Beta"}))
    assert stored(data)["C001"] == {"name": "Beta", "extra": "kept"}


def test_find_suggests_the_closest_ids(data):
    for _ in range(3):
        compounds.create({"name": "x"})
    assert compounds.find("C002") == "C002"
    with pytest.raises(CompoundError) as error:
        compounds.find("C010")
    assert error.value.lines == [
        "Unknown compound 'C010'.",
        "Did you mean: C001, C002?",
    ]
    with pytest.raises(CompoundError) as error:
        compounds.find("zzzz")
    assert error.value.lines[1] == "Compounds: C001, C002, C003."


def test_find_with_no_compounds_says_so(data):
    with pytest.raises(CompoundError) as error:
        compounds.find("C001")
    assert error.value.lines == [compounds.NONE_YET, compounds.USE_CREATE]


def test_a_deleted_id_is_never_reused(data):
    compounds.create({"name": "Alpha"})
    compounds.create({"name": "Beta"})
    (data / "compounds.toml").write_text('[C001]\nname = "Alpha"\n', "utf-8")
    assert compounds.create({"name": "Gamma"}) == "C003"


# Through the app


def test_compound_create_asks_each_field_and_adds_the_compound(project):
    async def steps(app, pilot):
        await typing("compound create", "Invented acid", "C9H9O9")(app, pilot)
        assert str(app.query_one("#prompt").render()) == "Molar mass: "
        await typing("138.120 g/mol", "", "", "Lot 7")(app, pilot)
        assert not app.query_one("#bar").has_class("-answering")

    shown = run(steps)
    kinds = messages(shown)
    assert ("normal", compounds.UNIT_FORMAT) in kinds
    assert kinds[-1] == ("success", "Added C001 (Invented acid).")
    assert stored(project)["C001"]["molar_mass"] == {
        "value": "138.120",
        "unit": "g/mol",
    }
    assert "density" not in stored(project)["C001"]


def test_a_unit_field_without_a_unit_asks_again(project):
    async def steps(app, pilot):
        await typing("compound create", "", "", "138.120")(app, pilot)
        assert str(app.query_one("#prompt").render()) == "Molar mass: "
        await typing("138.120 g/mol", "", "", "", "")(app, pilot)

    shown = run(steps)
    assert ("error", compounds.NEEDS_UNIT) in messages(shown)
    assert messages(shown)[-1] == ("success", "Added C001.")


def test_ctrl_c_partway_saves_nothing_and_uses_no_id(project):
    async def steps(app, pilot):
        await typing("compound create", "Invented acid", "C9H9O9")(app, pilot)
        await pilot.press("ctrl+c")
        await pilot.pause()
        await typing("compound create", "Second", "", "", "", "", "")(app, pilot)

    shown = run(steps)
    assert ("cancel", "Cancelled. Nothing was saved.") in messages(shown)
    assert list(stored(project)) == ["C001"]
    assert stored(project)["C001"]["name"] == "Second"
    assert counter(project) == 1


def test_compound_edit_keeps_with_enter_and_clears_with_a_dash(project):
    compounds.create(
        compounds.build({"name": "Alpha", "formula": "X", "molar_mass": "10.5 g/mol"})
    )

    async def steps(app, pilot):
        await typing("compound edit C001")(app, pilot)
        assert app.query_one("#command").placeholder == "Alpha"
        await typing("", "-", "", "", "", "New note")(app, pilot)

    shown = run(steps)
    assert messages(shown)[-1] == ("success", "Updated C001 (Alpha).")
    assert stored(project)["C001"] == {
        "name": "Alpha",
        "molar_mass": {"value": "10.5", "unit": "g/mol"},
        "note": "New note",
    }


def test_compound_edit_with_no_change_says_nothing_was_saved(project):
    compounds.create({"name": "Alpha"})
    before = (project / "compounds.toml").read_bytes()

    async def steps(app, pilot):
        await typing("compound edit C001", "", "", "", "", "", "")(app, pilot)

    shown = run(steps)
    assert messages(shown)[-1] == ("hint", compounds.UNCHANGED)
    assert (project / "compounds.toml").read_bytes() == before


def test_compound_edit_on_a_wrong_id_suggests_ids(project):
    compounds.create({"name": "Alpha"})
    compounds.create({"name": "Beta"})

    async def steps(app, pilot):
        await typing("compound edit C010", "compound edit zzzz")(app, pilot)
        assert not app.query_one("#bar").has_class("-answering")

    shown = run(steps)
    assert messages(shown)[1:] == [
        ("error", "Unknown compound 'C010'."),
        ("hint", "Did you mean: C001, C002?"),
        ("echo", "compound edit zzzz"),
        ("error", "Unknown compound 'zzzz'."),
        ("hint", "Compounds: C001, C002."),
    ]


def test_compound_edit_with_no_compounds(project):
    shown = run(typing("compound edit C001"))
    assert messages(shown)[1:] == [
        ("error", compounds.NONE_YET),
        ("hint", compounds.USE_CREATE),
    ]


def test_compound_show_all_lists_id_name_and_formula(project):
    compounds.create({"name": "Salicylic acid", "formula": "C7H6O3"})
    compounds.create({"name": "Acetic anhydride"})
    compounds.create({"formula": "H2O"})

    shown = run(typing("compound show all"))
    assert messages(shown)[-1] == (
        "normal",
        "C001  Salicylic acid    C7H6O3\n"
        "C002  Acetic anhydride\n"
        "C003                    H2O",
    )


def test_compound_show_all_with_none_stored(project):
    shown = run(typing("compound show all"))
    assert messages(shown)[-1] == ("hint", compounds.NONE_YET)


def test_compound_show_of_one_is_still_not_built(project):
    shown = run(typing("compound show C001"))
    assert messages(shown)[-1] == ("error", "compound show isn't built yet.")


def test_tab_offers_compound_ids_and_fields(project):
    compounds.create({"name": "Alpha"})
    compounds.create({"name": "Beta"})
    from synthase.commands import complete

    app = run().app
    assert complete("compound edit ", app.sources) == ["C001", "C002"]
    assert complete("compound show C001 m", app.sources) == ["molar_mass"]
    assert complete("compound show C001 ", app.sources) == sorted(compounds.FIELDS)
