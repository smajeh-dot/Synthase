"""The compound register, with invented compounds only."""

import sqlite3
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

import pytest

from synthase import compounds
from synthase.compounds import (
    REGISTER_NAME,
    SCHEMA_VERSION,
    Batch,
    Change,
    Compound,
    CompoundError,
    MeltingRange,
    Stock,
    add_batch,
    add_compound,
    archive_compound,
    check_label,
    compound_batches,
    compound_history,
    compound_spectra,
    edit_batch,
    edit_compound,
    get_batch,
    get_compound,
    link_spectrum,
    list_compounds,
    missing_fields,
    parse_batch,
    parse_batch_date,
    parse_class,
    parse_id,
    parse_mass,
    parse_melting_point,
    parse_rf,
    parse_risk_assessment,
    parse_spectrum_kind,
    parse_status,
    parse_stock,
    parse_yes_no,
    parse_yield,
    planned_batch_changes,
    planned_changes,
    purity_warnings,
    read_smiles,
    remove_batch,
    unlink_spectrum,
)
from synthase.config import Config, ConfigValue
from synthase.numbers import sig_figs


def rows(workspace, sql):
    # Closed straight away, so Windows can delete the temporary folder.
    with closing(sqlite3.connect(workspace / REGISTER_NAME)) as db, db:
        return db.execute(sql).fetchall()


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (46.069, "46.1"),
        (106.124, "106"),
        (1234.5, "1230"),
        (0.012345, "0.0123"),
        (99.96, "100"),
        (46.0, "46.0"),
        (2.345, "2.35"),
    ],
)
def test_sig_figs_gives_three_significant_figures(value, text):
    assert sig_figs(value) == text


def test_smiles_gives_formula_and_molar_mass():
    # Worked by hand for C2H6O: 2 x 12.011 + 6 x 1.008 + 15.999 = 46.069 g/mol.
    formula, molar_mass = read_smiles("CCO")
    assert formula == "C2H6O"
    assert molar_mass == pytest.approx(46.069, abs=0.001)


@pytest.mark.parametrize("smiles", ["C1CC", "CC(=O", "Xyz"])
def test_unreadable_smiles_is_refused(smiles):
    with pytest.raises(CompoundError, match="RDKit can't read the SMILES"):
        read_smiles(smiles)


def test_smiles_with_a_space_is_refused():
    with pytest.raises(CompoundError, match="space"):
        read_smiles("CCO ethanol")


def test_unreadable_smiles_prints_nothing_from_rdkit(capfd):
    with pytest.raises(CompoundError):
        read_smiles("C1CC")
    assert capfd.readouterr() == ("", "")


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("Schiff base", "Schiff base"),
        ("schiff-base", "Schiff base"),
        ("SCHIFF_BASE", "Schiff base"),
        ("Chalcone", "chalcone"),
        ("starting  material", "starting material"),
        ("other", "other"),
        ("", None),
    ],
)
def test_class_ignores_capitals_and_hyphens(text, name):
    assert parse_class(text) == name


def test_unknown_class_lists_the_choices():
    with pytest.raises(CompoundError) as error:
        parse_class("ketone")
    assert "Schiff base, chalcone, starting material, other" in str(error.value)


def test_status_defaults_to_planned_and_rejects_unknowns():
    assert parse_status("") == "planned"
    assert parse_status("Synthesised") == "synthesised"
    with pytest.raises(CompoundError, match="planned, synthesised, purified"):
        parse_status("finished")


def test_first_compound_creates_the_register_with_every_table(tmp_path):
    compound = add_compound(tmp_path, "Test compound A")
    assert compound.id == "SYN-001"
    assert (tmp_path / REGISTER_NAME).is_file()
    tables = {name for (name,) in rows(tmp_path, "SELECT name FROM sqlite_master")}
    assert {"compounds", "batches", "spectra", "changes"} <= tables
    assert rows(tmp_path, "PRAGMA user_version") == [(SCHEMA_VERSION,)]


def test_ids_count_up_and_are_never_reused(tmp_path):
    assert add_compound(tmp_path, "Test compound A").id == "SYN-001"
    assert add_compound(tmp_path, "Test compound B").id == "SYN-002"
    rows(tmp_path, "DELETE FROM compounds WHERE id = 2")
    assert add_compound(tmp_path, "Test compound C").id == "SYN-003"


def test_compound_keeps_every_field(tmp_path):
    compound = add_compound(
        tmp_path,
        "  Test compound A ",
        compound_class="chalcone",
        smiles="CCO",
        status="purified",
        notes="invented for a test",
    )
    assert compound.label == "Test compound A"
    assert compound.compound_class == "chalcone"
    assert compound.smiles == "CCO"
    assert compound.formula == "C2H6O"
    assert compound.molar_mass == pytest.approx(46.069, abs=0.001)
    assert compound.status == "purified"
    assert compound.notes == "invented for a test"
    assert rows(
        tmp_path, "SELECT label, class, smiles, formula, status, notes FROM compounds"
    ) == [
        (
            "Test compound A",
            "chalcone",
            "CCO",
            "C2H6O",
            "purified",
            "invented for a test",
        )
    ]


def test_only_the_label_is_needed(tmp_path):
    compound = add_compound(tmp_path, "Test compound A")
    assert compound.status == "planned"
    assert compound.smiles is compound.formula is compound.molar_mass is None
    assert compound.compound_class is compound.notes is None


def test_invalid_smiles_saves_nothing(tmp_path):
    add_compound(tmp_path, "Test compound A")
    with pytest.raises(CompoundError):
        add_compound(tmp_path, "Test compound B", smiles="C1CC")
    assert rows(tmp_path, "SELECT label FROM compounds") == [("Test compound A",)]
    assert add_compound(tmp_path, "Test compound B").id == "SYN-002"


def test_blank_label_is_refused(tmp_path):
    with pytest.raises(CompoundError, match="needs a label"):
        add_compound(tmp_path, "   ")


def test_repeated_label_is_refused_ignoring_capitals(tmp_path):
    add_compound(tmp_path, "Test compound A")
    with pytest.raises(CompoundError) as error:
        add_compound(tmp_path, " test COMPOUND a")
    assert str(error.value) == (
        '"Test compound A" is already SYN-001. Choose another label.'
    )
    with pytest.raises(CompoundError):
        check_label(tmp_path, "TEST COMPOUND A")


def test_check_label_works_before_the_register_exists(tmp_path):
    assert check_label(tmp_path, " Test compound A ") == "Test compound A"
    assert not (tmp_path / REGISTER_NAME).exists()


def test_new_compound_is_in_the_change_log(tmp_path, monkeypatch):
    monkeypatch.setattr(compounds, "_now", lambda: "2026-01-02T03:04:05")
    add_compound(tmp_path, "Test compound A", smiles="CCO")
    assert rows(
        tmp_path, "SELECT compound_id, changed, field, old, new FROM changes"
    ) == [
        (1, "2026-01-02T03:04:05", "label", None, "Test compound A"),
        (1, "2026-01-02T03:04:05", "smiles", None, "CCO"),
        (1, "2026-01-02T03:04:05", "status", None, "planned"),
    ]


def test_register_from_a_newer_synthase_is_refused(tmp_path):
    add_compound(tmp_path, "Test compound A")
    rows(tmp_path, f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    with pytest.raises(CompoundError, match="newer version of Synthase"):
        add_compound(tmp_path, "Test compound B")


def test_file_that_is_not_a_register_is_refused(tmp_path):
    (tmp_path / REGISTER_NAME).write_text("invented, not a database", encoding="utf-8")
    with pytest.raises(CompoundError, match="isn't a compound register"):
        add_compound(tmp_path, "Test compound A")


# --- Reading the register (#33) ---


def add_three(workspace):
    add_compound(workspace, "Test compound A", "chalcone", "CCO", "purified")
    add_compound(workspace, "Test compound B", "Schiff base")
    add_compound(workspace, "Test compound C", "chalcone", notes="invented")


@pytest.mark.parametrize("text", ["SYN-001", "syn-1", " 1 ", "Syn-0001"])
def test_id_can_be_typed_in_several_forms(text):
    assert parse_id(text) == 1


@pytest.mark.parametrize("text", ["abc", "SYN-", "SYN 1", "-1", "SYN-1a", ""])
def test_text_that_is_not_an_id_is_refused(text):
    with pytest.raises(CompoundError, match="isn't a compound ID. IDs look like"):
        parse_id(text)


def test_get_compound_gives_every_saved_field(tmp_path):
    added = add_compound(tmp_path, "Test compound A", "chalcone", "CCO", notes="x")
    assert get_compound(tmp_path, "syn-1") == added


def test_unknown_id_names_the_id_and_the_list_command(tmp_path):
    add_compound(tmp_path, "Test compound A")
    with pytest.raises(CompoundError) as error:
        get_compound(tmp_path, "42")
    assert str(error.value) == (
        "There's no compound SYN-042 in the register. "
        'Run "syn compound list" to see every ID.'
    )


def test_reading_never_creates_the_register(tmp_path):
    with pytest.raises(CompoundError, match="no compound SYN-001"):
        get_compound(tmp_path, "SYN-001")
    assert list_compounds(tmp_path) == []
    assert not (tmp_path / REGISTER_NAME).exists()


def test_list_gives_every_compound_in_id_order(tmp_path):
    add_three(tmp_path)
    assert [c.id for c in list_compounds(tmp_path)] == ["SYN-001", "SYN-002", "SYN-003"]


@pytest.mark.parametrize(
    ("status", "compound_class", "labels"),
    [
        ("planned", None, ["Test compound B", "Test compound C"]),
        ("PURIFIED", None, ["Test compound A"]),
        (None, "chalcone", ["Test compound A", "Test compound C"]),
        (None, "schiff-base", ["Test compound B"]),
        ("planned", "Chalcone", ["Test compound C"]),
        ("tested", None, []),
    ],
)
def test_each_filter_keeps_the_right_rows(tmp_path, status, compound_class, labels):
    add_three(tmp_path)
    found = list_compounds(tmp_path, status, compound_class)
    assert [compound.label for compound in found] == labels


@pytest.mark.parametrize(
    ("status", "compound_class", "message"),
    [("finished", None, "isn't a status"), (None, "ketone", "isn't a compound class")],
)
def test_unknown_filter_value_is_refused(tmp_path, status, compound_class, message):
    with pytest.raises(CompoundError, match=message):
        list_compounds(tmp_path, status, compound_class)


def test_reading_a_register_from_a_newer_synthase_is_refused(tmp_path):
    add_compound(tmp_path, "Test compound A")
    rows(tmp_path, f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    with pytest.raises(CompoundError, match="newer version of Synthase"):
        list_compounds(tmp_path)


def test_missing_fields_names_every_blank_one():
    assert missing_fields(Compound(1, "Test compound A")) == [
        "no class yet",
        "no SMILES yet, so no formula or molar mass",
        "no notes yet",
        "no melting point yet",
        "no Rf value yet",
        "no appearance yet",
        "not recorded whether it is coloured",
        "no solubility yet",
        "no DMSO stock concentration yet",
        "no storage conditions yet",
        "no risk assessment recorded",
        "no hazard notes yet",
    ]


def test_nothing_missing_once_every_field_is_filled(tmp_path, invented_details):
    full = add_compound(
        tmp_path, "Test compound A", "chalcone", "CCO", notes="x", **invented_details
    )
    assert missing_fields(full) == []


def test_a_risk_assessment_not_done_is_still_missing():
    compound = Compound(1, "Test compound A", risk_assessment="no")
    assert "risk assessment not done yet" in missing_fields(compound)
    assert "no risk assessment recorded" not in missing_fields(compound)


# --- Editing and archiving (#34) ---


def say(reply):
    """A confirm function that answers ``reply`` and records each question."""
    asked = []

    def confirm(change):
        asked.append(change)
        return reply

    confirm.asked = asked
    return confirm


def test_edit_to_a_blank_field_needs_no_confirmation(tmp_path):
    add_compound(tmp_path, "Test compound A")
    confirm = say(False)
    compound, changes = edit_compound(tmp_path, "1", confirm, notes="invented")
    assert confirm.asked == []
    assert changes == [Change("notes", None, "invented")]
    assert get_compound(tmp_path, "1").notes == compound.notes == "invented"


def test_edit_to_a_set_field_is_refused_without_a_yes(tmp_path):
    add_compound(tmp_path, "Test compound A", smiles="CCO")
    confirm = say(False)
    compound, changes = edit_compound(tmp_path, "1", confirm, smiles="CCN")
    assert confirm.asked == [Change("smiles", "CCO", "CCN")]
    assert changes == []
    assert get_compound(tmp_path, "1").smiles == compound.smiles == "CCO"
    assert len(rows(tmp_path, "SELECT * FROM changes")) == 3


def test_edit_to_a_set_field_is_applied_with_a_yes(tmp_path):
    add_compound(tmp_path, "Test compound A", smiles="CCO")
    compound, changes = edit_compound(tmp_path, "1", say(True), smiles="CCN")
    assert changes == [Change("smiles", "CCO", "CCN")]
    assert get_compound(tmp_path, "1") == compound
    assert compound.smiles == "CCN"


def test_a_new_smiles_updates_formula_and_molar_mass(tmp_path):
    add_compound(tmp_path, "Test compound A", smiles="CCO")
    compound, _ = edit_compound(tmp_path, "1", say(True), smiles="CCN")
    # Worked by hand for C2H7N: 2 x 12.011 + 7 x 1.008 + 14.007 = 45.085 g/mol.
    assert compound.formula == "C2H7N"
    assert compound.molar_mass == pytest.approx(45.085, abs=0.001)
    cleared, _ = edit_compound(tmp_path, "1", say(True), smiles="-")
    assert cleared.smiles is cleared.formula is cleared.molar_mass is None
    assert get_compound(tmp_path, "1") == cleared


def test_planned_changes_match_the_edit_and_save_nothing(tmp_path):
    add_compound(tmp_path, "Test compound A", smiles="CCO", notes="invented note")
    given = {"smiles": "CCN", "notes": "-", "status": "planned", "storage": "fridge"}
    planned = planned_changes(tmp_path, "SYN-001", **given)
    assert planned == [
        Change("smiles", "CCO", "CCN"),
        Change("notes", "invented note", None),
        Change("storage", None, "fridge"),
    ]
    # Adding logged label, SMILES, status and notes; planning logs nothing.
    assert len(rows(tmp_path, "SELECT * FROM changes")) == 4
    confirm = say(True)
    _, changes = edit_compound(tmp_path, "1", confirm, **given)
    assert changes == planned
    assert confirm.asked == planned[:2]


def test_planned_changes_refuse_what_the_edit_refuses(tmp_path):
    add_compound(tmp_path, "Test compound A")
    with pytest.raises(CompoundError, match="solvent system"):
        planned_changes(tmp_path, "1", rf="0.4")
    with pytest.raises(CompoundError, match="SYN-002"):
        planned_changes(tmp_path, "2", notes="invented")


def test_planned_batch_changes_match_the_edit_and_save_nothing(tmp_path):
    add_compound(tmp_path, "Test compound A")
    add_batch(tmp_path, "1", date(2026, 10, 18), 0.152)
    given = {"made_on": "18/10/2026", "mass": "125 mg", "yield_percent": "64.2"}
    planned = planned_batch_changes(tmp_path, "SYN-001", "1", **given)
    assert planned == [
        Change("batch 1 mass", "152 mg", "125 mg"),
        Change("batch 1 yield", None, "64.2%"),
    ]
    # Adding logged the label, the status and the batch; planning logs nothing.
    assert len(rows(tmp_path, "SELECT * FROM changes")) == 3
    confirm = say(True)
    *_, changes = edit_batch(tmp_path, "1", "1", confirm, **given)
    assert changes == planned
    assert confirm.asked == planned[:1]


def test_planned_batch_changes_refuse_what_the_edit_refuses(tmp_path):
    add_compound(tmp_path, "Test compound A")
    add_batch(tmp_path, "1", date(2026, 10, 18), 0.152)
    with pytest.raises(CompoundError, match="its mass made, its yield or both"):
        planned_batch_changes(tmp_path, "1", "1", mass="-")
    with pytest.raises(CompoundError, match="has no batch 2"):
        planned_batch_changes(tmp_path, "1", "2", mass="1 g")
    with pytest.raises(CompoundError, match="can't be cleared"):
        planned_batch_changes(tmp_path, "1", "1", made_on="-")


def test_parse_batch_reads_typed_options():
    assert parse_batch("18/10/2026", "152 mg", "64.2%") == (
        date(2026, 10, 18),
        pytest.approx(0.152),
        64.2,
    )
    assert parse_batch(None, None, "50") == (date.today(), None, 50.0)
    with pytest.raises(CompoundError, match="isn't a mass"):
        parse_batch(None, "lots", None)


def test_only_confirmed_changes_are_made(tmp_path):
    add_compound(tmp_path, "Test compound A", "chalcone", status="planned")
    replies = iter([True, False])
    compound, changes = edit_compound(
        tmp_path,
        "1",
        lambda change: next(replies),
        compound_class="other",
        status="synthesised",
        notes="invented",
    )
    assert changes == [
        Change("class", "chalcone", "other"),
        Change("notes", None, "invented"),
    ]
    assert (compound.compound_class, compound.status) == ("other", "planned")


def test_each_change_appears_in_the_log_with_old_and_new_values(tmp_path, monkeypatch):
    monkeypatch.setattr(compounds, "_now", lambda: "2026-01-02T03:04:05")
    add_compound(tmp_path, "Test compound A", smiles="CCO")
    monkeypatch.setattr(compounds, "_now", lambda: "2026-01-03T10:00:00")
    edit_compound(tmp_path, "1", say(True), smiles="CCN", notes="invented")
    compound, history = compound_history(tmp_path, "SYN-001")
    assert compound.label == "Test compound A"
    assert history == [
        Change("label", None, "Test compound A", "2026-01-02T03:04:05"),
        Change("smiles", None, "CCO", "2026-01-02T03:04:05"),
        Change("status", None, "planned", "2026-01-02T03:04:05"),
        Change("smiles", "CCO", "CCN", "2026-01-03T10:00:00"),
        Change("notes", None, "invented", "2026-01-03T10:00:00"),
    ]


def test_unchanged_values_are_not_asked_about_or_logged(tmp_path):
    add_compound(tmp_path, "Test compound A", "chalcone")
    confirm = say(True)
    _, changes = edit_compound(
        tmp_path, "1", confirm, label="Test compound A", compound_class="Chalcone"
    )
    assert confirm.asked == changes == []
    assert len(compound_history(tmp_path, "1")[1]) == 3


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        ({"smiles": "C1CC"}, "RDKit can't read the SMILES"),
        ({"compound_class": "ketone"}, "isn't a compound class"),
        ({"label": "-"}, "always has a label, so it can't be cleared"),
        ({"status": "-"}, "always has a status, so it can't be cleared"),
        ({"label": "test compound b"}, '"Test compound B" is already SYN-002.'),
    ],
)
def test_a_refused_value_saves_nothing(tmp_path, flags, message):
    add_compound(tmp_path, "Test compound A", "chalcone")
    add_compound(tmp_path, "Test compound B")
    with pytest.raises(CompoundError, match=message):
        edit_compound(tmp_path, "1", say(True), notes="invented", **flags)
    assert get_compound(tmp_path, "1").notes is None


def test_a_compound_may_change_the_capitals_of_its_own_label(tmp_path):
    add_compound(tmp_path, "Test compound A")
    compound, _ = edit_compound(tmp_path, "1", say(True), label="Test Compound A")
    assert compound.label == "Test Compound A"


def test_archived_compound_is_hidden_from_list_and_found_by_get(tmp_path):
    add_three(tmp_path)
    archived = archive_compound(tmp_path, "SYN-002")
    assert archived.archived
    assert get_compound(tmp_path, "2") == archived
    assert [c.id for c in list_compounds(tmp_path)] == ["SYN-001", "SYN-003"]
    every = list_compounds(tmp_path, archived=True)
    assert [c.id for c in every] == ["SYN-001", "SYN-002", "SYN-003"]
    assert rows(tmp_path, "SELECT COUNT(*) FROM compounds") == [(3,)]


def test_archive_and_restore_are_logged_and_checked(tmp_path):
    add_compound(tmp_path, "Test compound A")
    archive_compound(tmp_path, "1")
    with pytest.raises(CompoundError, match="SYN-001 is already archived."):
        archive_compound(tmp_path, "1")
    restored = archive_compound(tmp_path, "1", archived=False)
    assert not restored.archived
    with pytest.raises(CompoundError, match="isn't archived, so there's nothing"):
        archive_compound(tmp_path, "1", archived=False)
    logged = [(c.name, c.old, c.new) for c in compound_history(tmp_path, "1")[1]]
    assert logged[-2:] == [("archived", "no", "yes"), ("archived", "yes", "no")]


def test_archived_compound_keeps_its_label_and_can_be_edited(tmp_path):
    add_compound(tmp_path, "Test compound A")
    archive_compound(tmp_path, "1")
    with pytest.raises(CompoundError, match="is already SYN-001"):
        add_compound(tmp_path, "Test compound A")
    compound, _ = edit_compound(tmp_path, "1", say(True), notes="abandoned")
    assert compound.archived and compound.notes == "abandoned"


# --- Characterisation, handling and safety (#35) ---


@pytest.mark.parametrize(
    ("text", "low", "high"),
    [
        ("455-457", 455, 457),
        ("455.5 – 457", 455.5, 457),
        ("455 K to 457 K", 455, 457),
        ("456", 456, 456),
        ("456k", 456, 456),
    ],
)
def test_melting_range_is_read_in_kelvin(text, low, high):
    assert parse_melting_point(text) == MeltingRange(low, high)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("457-455", r"runs from high to low \(457 to 455 K\)"),
        ("0", "always above 0 K"),
        ("hot", "isn't a melting range. Type it in kelvin"),
        ("455-", "isn't a melting range"),
    ],
)
def test_impossible_melting_range_is_refused(text, message):
    with pytest.raises(CompoundError, match=message):
        parse_melting_point(text)


def test_melting_range_is_shown_in_kelvin():
    assert str(MeltingRange(455.5, 457)) == "455.5–457 K"
    assert str(MeltingRange(456, 456)) == "456 K"


@pytest.mark.parametrize(
    ("text", "rf"), [("0.45", 0.45), (".3", 0.3), ("0", 0), ("1", 1)]
)
def test_rf_from_0_to_1_is_accepted(text, rf):
    assert parse_rf(text) == rf


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("1.3", r'between 0 and 1\. "1\.3" isn\'t'),
        ("-0.2", r'between 0 and 1\. "-0\.2" isn\'t'),
        ("nan", "isn't an Rf value"),
        ("far", "isn't an Rf value"),
    ],
)
def test_rf_outside_0_to_1_is_refused(text, message):
    with pytest.raises(CompoundError, match=message):
        parse_rf(text)


def test_yes_no_answers():
    assert parse_yes_no(" Yes ") is True
    assert parse_yes_no("n") is False
    with pytest.raises(CompoundError, match="Answer yes or no"):
        parse_yes_no("maybe")


@pytest.mark.parametrize(
    ("text", "stock"),
    [
        ("10 mg/mL", Stock(10, "mg/mL")),
        ("2.5mM", Stock(2.5, "mM")),
        ("500 ug/ml", Stock(500, "µg/mL")),
    ],
)
def test_dmso_stock_needs_a_number_and_a_known_unit(text, stock):
    assert parse_stock(text) == stock


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("10", "Give the unit as well"),
        ("10 g/L", '"g/L" isn\'t a unit Synthase knows'),
        ("0 mg/mL", "must be above zero"),
        ("lots", "isn't a concentration"),
    ],
)
def test_unusable_dmso_stock_is_refused(text, message):
    with pytest.raises(CompoundError, match=message):
        parse_stock(text)


@pytest.mark.parametrize(
    ("text", "saved"),
    [("2020-01-31", "2020-01-31"), ("31/1/2020", "2020-01-31"), ("No", "no")],
)
def test_risk_assessment_is_a_date_or_no(text, saved):
    assert parse_risk_assessment(text) == saved


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("31/02/2026", '"31/02/2026" isn\'t a real date'),
        ("2026-13-01", "isn't a real date"),
        ("2999-01-01", "2999-01-01 is in the future"),
        ("yes", "instead of yes"),
        ("last week", "isn't a date"),
    ],
)
def test_impossible_risk_assessment_date_is_refused(text, message):
    with pytest.raises(CompoundError, match=message):
        parse_risk_assessment(text)


def test_details_are_saved_and_read_back(tmp_path, invented_details):
    added = add_compound(tmp_path, "Test compound A", **invented_details)
    assert added == get_compound(tmp_path, "1")
    assert added.melting_point == MeltingRange(455, 457)
    assert added.rf == 0.45
    assert added.dmso_stock == Stock(10, "mg/mL")
    assert added.risk_assessment == "2020-01-31"


def test_coloured_is_saved_where_plate_design_can_read_it(tmp_path):
    add_compound(tmp_path, "Test compound A", coloured="yes")
    add_compound(tmp_path, "Test compound B", coloured="no")
    add_compound(tmp_path, "Test compound C")
    assert [c.coloured for c in list_compounds(tmp_path)] == [True, False, None]


def test_rf_without_its_solvent_system_is_refused(tmp_path):
    with pytest.raises(CompoundError, match="needs the solvent system"):
        add_compound(tmp_path, "Test compound A", rf="0.45")
    add_compound(tmp_path, "Test compound A", rf="0.45", rf_solvent="invented 3:1")
    with pytest.raises(CompoundError, match="needs the solvent system"):
        edit_compound(tmp_path, "1", say(True), rf_solvent="-")
    assert get_compound(tmp_path, "1").rf_solvent == "invented 3:1"


def test_detail_edits_ask_and_log_as_text(tmp_path, monkeypatch):
    add_compound(tmp_path, "Test compound A", melting_point="455-457", coloured="no")
    confirm = say(True)
    compound, changes = edit_compound(
        tmp_path, "1", confirm, melting_point="455-456", coloured="yes", hazards="x"
    )
    assert compound.melting_point == MeltingRange(455, 456)
    assert compound.coloured is True
    assert [(c.name, c.old, c.new) for c in confirm.asked] == [
        ("melting point", "455–457 K", "455–456 K"),
        ("coloured", "no", "yes"),
    ]
    assert [(c.name, c.old, c.new) for c in changes][-1] == ("hazard notes", None, "x")
    logged = [(c.name, c.new) for c in compound_history(tmp_path, "1")[1]]
    assert ("melting point", "455–456 K") in logged


def test_a_detail_can_be_cleared(tmp_path):
    add_compound(tmp_path, "Test compound A", dmso_stock="10 mM")
    compound, _ = edit_compound(tmp_path, "1", say(True), dmso_stock="-")
    assert compound.dmso_stock is None
    assert get_compound(tmp_path, "1").dmso_stock is None


def purity_config(limit, verified):
    rule = ConfigValue(
        "melting_point.purity_range",
        "melting-point purity rule",
        limit,
        "K",
        "invented for a test",
        verified,
    )
    return Config({rule.key: rule}, "invented")


# Hand-worked against an invented 3 K limit: 451.2 to 454.2 K is 3.0 K wide
# (inside the rule, though the computer makes it 2.9999...); 454.3 makes it
# 3.1 K, just over.
@pytest.mark.parametrize(
    ("melting_point", "flagged"),
    [("451.2-454.1", False), ("451.2-454.2", False), ("451.2-454.3", True)],
)
def test_melting_range_wider_than_the_purity_rule_is_flagged(melting_point, flagged):
    compound = Compound(
        1, "Test compound A", melting_point=parse_melting_point(melting_point)
    )
    lines = purity_warnings(compound, purity_config(3.0, verified=True))
    if flagged:
        assert lines == [
            "! The melting range is 3.1 K wide, wider than the melting-point purity "
            "rule (3 K), so the sample may not be pure."
        ]
    else:
        assert lines == []


def test_purity_flag_carries_the_unverified_warning():
    compound = Compound(1, "Test compound A", melting_point=MeltingRange(450, 455))
    flag, warning = purity_warnings(compound, purity_config(3.0, verified=False))
    assert flag.startswith("! The melting range is 5 K wide")
    assert warning.startswith("Warning: melting-point purity rule (3 K) has not")


def test_no_melting_point_means_no_flag():
    compound = Compound(1, "Test compound A")
    assert purity_warnings(compound, purity_config(3.0, verified=False)) == []


def test_version_1_register_is_read_without_change_then_upgraded(tmp_path):
    with closing(sqlite3.connect(tmp_path / REGISTER_NAME)) as db:
        db.executescript(compounds.SCHEMA + "PRAGMA user_version = 1;")
        db.execute(
            "INSERT INTO compounds (label, smiles, status, notes) "
            "VALUES ('Test compound A', 'CCO', 'planned', 'invented')"
        )
        db.execute(
            "INSERT INTO changes (compound_id, changed, field, old, new) "
            "VALUES (1, '2026-01-01T09:00:00', 'label', NULL, 'Test compound A')"
        )
        db.commit()
    before = (tmp_path / REGISTER_NAME).read_bytes()
    compound = get_compound(tmp_path, "1")
    assert (compound.label, compound.notes, compound.melting_point) == (
        "Test compound A",
        "invented",
        None,
    )
    assert (tmp_path / REGISTER_NAME).read_bytes() == before

    edit_compound(tmp_path, "1", say(True), melting_point="455-457")
    assert rows(tmp_path, "PRAGMA user_version") == [(SCHEMA_VERSION,)]
    upgraded = get_compound(tmp_path, "1")
    assert (upgraded.smiles, upgraded.notes) == ("CCO", "invented")
    assert upgraded.melting_point == MeltingRange(455, 457)
    history = compound_history(tmp_path, "1")[1]
    assert [(c.field, c.new) for c in history] == [
        ("label", "Test compound A"),
        ("melting_point", "455–457 K"),
    ]


# --- Batches and spectra (#36) ---


def test_new_register_has_the_spectrum_kind_column(tmp_path):
    add_compound(tmp_path, "Test compound A")
    columns = [row[1] for row in rows(tmp_path, "PRAGMA table_info(spectra)")]
    assert columns == ["id", "compound_id", "path", "added", "kind", "removed"]


@pytest.mark.parametrize(
    ("text", "grams"),
    [("152 mg", 0.152), ("1.5g", 1.5), ("0.2 G", 0.2), ("2500 MG", 2.5)],
)
def test_mass_is_read_in_grams(text, grams):
    assert parse_mass(text) == pytest.approx(grams)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("152", "Give the unit as well, mg or g"),
        ("1 kg", '"kg" isn\'t a unit Synthase knows. Use mg or g.'),
        ("heavy", "isn't a mass"),
    ],
)
def test_unusable_mass_is_refused(text, message):
    with pytest.raises(CompoundError, match=message):
        parse_mass(text)


def test_yield_and_batch_date_are_read():
    assert parse_yield("64.2%") == 64.2
    with pytest.raises(CompoundError, match="can't be below 0%"):
        parse_yield("-3")
    with pytest.raises(CompoundError, match="must be above zero"):
        parse_mass("0 mg")
    with pytest.raises(CompoundError, match="isn't a yield. Type a percentage"):
        parse_yield("good")
    assert parse_batch_date("") == date.today()
    assert parse_batch_date("31/1/2020") == date(2020, 1, 31)
    with pytest.raises(CompoundError, match="Type the date the batch was made"):
        parse_batch_date("yesterday")
    with pytest.raises(CompoundError, match="isn't a real date"):
        parse_batch_date("30/02/2020")


def test_spectrum_kind_ignores_capitals_and_hyphens():
    assert parse_spectrum_kind("uv vis") == "UV-vis"
    assert parse_spectrum_kind("1h-nmr") == "1H NMR"
    assert parse_spectrum_kind("") is None
    with pytest.raises(CompoundError, match="isn't a kind of spectrum"):
        parse_spectrum_kind("Raman")


# Invented masses and yields; mass shows in mg below 1 g, in g from 1 g up.
@pytest.mark.parametrize(
    ("batch", "text"),
    [
        (Batch(1, "2020-01-31", 0.152, 64.23), "1: 2020-01-31, 152 mg, 64.2%"),
        (Batch(2, "2020-02-01", 1.2345), "2: 2020-02-01, 1.23 g"),
        (Batch(3, "2020-02-02", yield_percent=71), "3: 2020-02-02, 71.0%"),
    ],
)
def test_batch_shows_mass_and_yield_to_3_sf(batch, text):
    assert str(batch) == text


def test_batches_are_numbered_per_compound_and_logged(tmp_path):
    add_compound(tmp_path, "Test compound A")
    add_compound(tmp_path, "Test compound B")
    _, first = add_batch(tmp_path, "1", date(2020, 1, 31), 0.152, 64.2)
    _, other = add_batch(tmp_path, "2", date(2020, 2, 1), yield_percent=50)
    _, second = add_batch(tmp_path, "1", mass_g=0.2)
    assert (first.number, other.number, second.number) == (1, 1, 2)
    assert second.made_on == date.today().isoformat()
    compound = get_compound(tmp_path, "1")
    assert compound_batches(tmp_path, compound) == [first, second]
    logged = [(c.name, c.old, c.new) for c in compound_history(tmp_path, "1")[1]]
    assert logged[-2:] == [
        ("batch", None, "1: 2020-01-31, 152 mg, 64.2%"),
        ("batch", None, f"2: {date.today().isoformat()}, 200 mg"),
    ]


@pytest.mark.parametrize(
    ("given", "message"),
    [
        ({}, "needs its mass made, its yield or both"),
        ({"mass_g": 0}, "mass made must be above zero"),
        ({"yield_percent": -1}, "can't be below 0%"),
        (
            {"made_on": date.today() + timedelta(days=1), "mass_g": 0.1},
            "is in the future",
        ),
    ],
)
def test_impossible_batch_saves_nothing(tmp_path, given, message):
    add_compound(tmp_path, "Test compound A")
    with pytest.raises(CompoundError, match=message):
        add_batch(tmp_path, "1", **given)
    assert compound_batches(tmp_path, get_compound(tmp_path, "1")) == []


def test_yield_over_100_percent_is_saved_with_a_warning(tmp_path):
    add_compound(tmp_path, "Test compound A")
    _, batch = add_batch(tmp_path, "1", yield_percent=104)
    assert batch.warning.startswith("A yield over 100% usually means")
    assert Batch(1, "2020-01-31", yield_percent=100).warning == ""


def spectra_file(workspace, name="spectra/invented IR.csv"):
    path = workspace / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("invented", encoding="utf-8")
    return path


def test_spectrum_is_linked_relative_to_the_workspace_and_logged(tmp_path):
    add_compound(tmp_path, "Test compound A")
    _, spectrum = link_spectrum(tmp_path, "1", spectra_file(tmp_path), "ir")
    assert (spectrum.path, spectrum.kind) == ("spectra/invented IR.csv", "IR")
    compound = get_compound(tmp_path, "1")
    assert compound_spectra(tmp_path, compound) == [spectrum]
    logged = compound_history(tmp_path, "1")[1][-1]
    assert (logged.name, logged.new) == ("spectrum", "IR spectra/invented IR.csv")


def test_relative_spectra_path_counts_from_the_current_folder_then_the_workspace(
    tmp_path, monkeypatch
):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    add_compound(workspace, "Test compound A")
    spectra_file(workspace)
    monkeypatch.chdir(workspace / "spectra")
    _, here = link_spectrum(workspace, "1", Path("invented IR.csv"))
    monkeypatch.chdir(tmp_path)
    spectra_file(workspace, "nmr/invented.txt")
    _, there = link_spectrum(workspace, "1", Path("nmr/invented.txt"))
    assert (here.path, there.path) == ("spectra/invented IR.csv", "nmr/invented.txt")


def test_unusable_spectra_file_is_refused(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    add_compound(workspace, "Test compound A")
    with pytest.raises(CompoundError, match="There's no file at"):
        link_spectrum(workspace, "1", workspace / "missing.csv")
    with pytest.raises(CompoundError, match="is a folder, not a file"):
        link_spectrum(workspace, "1", workspace)
    outside = spectra_file(tmp_path, "elsewhere.csv")
    with pytest.raises(CompoundError, match="must be inside the workspace"):
        link_spectrum(workspace, "1", outside)
    link_spectrum(workspace, "1", spectra_file(workspace))
    with pytest.raises(CompoundError, match="is already linked to SYN-001"):
        link_spectrum(workspace, "1", workspace / "spectra" / "invented IR.csv")
    assert len(compound_spectra(workspace, get_compound(workspace, "1"))) == 1


def test_missing_fields_names_no_batches_or_spectra_only_when_checked(tmp_path):
    compound = Compound(1, "Test compound A")
    assert "no batches yet" not in missing_fields(compound)
    assert missing_fields(compound, [], [])[-2:] == [
        "no batches yet",
        "no spectra linked yet",
    ]
    assert missing_fields(compound, [Batch(1, "2020-01-31", 0.1)], [])[-1] == (
        "no spectra linked yet"
    )


def test_version_2_register_upgrades_to_version_3(tmp_path):
    with closing(sqlite3.connect(tmp_path / REGISTER_NAME)) as db:
        db.executescript(
            compounds.SCHEMA + compounds.DETAILS_SCHEMA + "PRAGMA user_version = 2;"
        )
        db.execute(
            "INSERT INTO compounds (label, status, mp_low, mp_high) "
            "VALUES ('Test compound A', 'planned', 455, 457)"
        )
        db.commit()
    assert compound_spectra(tmp_path, get_compound(tmp_path, "1")) == []
    link_spectrum(tmp_path, "1", spectra_file(tmp_path), "IR")
    assert rows(tmp_path, "PRAGMA user_version") == [(SCHEMA_VERSION,)]
    compound = get_compound(tmp_path, "1")
    assert compound.melting_point == MeltingRange(455, 457)
    assert compound_spectra(tmp_path, compound)[0].kind == "IR"


# --- Correcting and removing batches and spectra links (#46) ---


def three_batches(workspace):
    """An invented compound with batches of 152 mg, 140 mg and 0.1 g."""
    add_compound(workspace, "Test compound A")
    add_batch(workspace, "1", date(2020, 1, 31), 0.152, 64.2)
    add_batch(workspace, "1", date(2020, 2, 1), 0.140, 50)
    add_batch(workspace, "1", date(2020, 2, 2), 0.1)


def test_correcting_batch_1_mass_asks_and_shows_in_the_history(tmp_path):
    three_batches(tmp_path)
    confirm = say(True)
    _, batch, changes = edit_batch(tmp_path, "1", "1", confirm, mass="125 mg")
    assert confirm.asked == changes == [Change("batch 1 mass", "152 mg", "125 mg")]
    assert batch == Batch(1, "2020-01-31", 0.125, 64.2)
    compound = get_compound(tmp_path, "1")
    assert compound_batches(tmp_path, compound)[0] == batch
    logged = compound_history(tmp_path, "1")[1][-1]
    assert (logged.name, logged.old, logged.new) == ("batch 1 mass", "152 mg", "125 mg")


def test_batch_correction_is_refused_without_a_yes(tmp_path):
    three_batches(tmp_path)
    _, batch, changes = edit_batch(tmp_path, "1", "1", say(False), mass="125 mg")
    assert changes == []
    assert batch.mass_g == 0.152
    assert get_batch(tmp_path, "1", "1")[1].mass_g == 0.152
    assert compound_history(tmp_path, "1")[1][-1].name == "batch"


def test_batch_date_and_yield_are_corrected_and_a_blank_filled_without_asking(
    tmp_path,
):
    three_batches(tmp_path)
    confirm = say(True)
    _, batch, changes = edit_batch(
        tmp_path, "1", "3", confirm, made_on="1/2/2020", yield_percent="71"
    )
    assert confirm.asked == [Change("batch 3 date", "2020-02-02", "2020-02-01")]
    assert changes == [*confirm.asked, Change("batch 3 yield", None, "71.0%")]
    assert batch == Batch(3, "2020-02-01", 0.1, 71)


def test_unchanged_batch_values_are_not_asked_about(tmp_path):
    three_batches(tmp_path)
    confirm = say(True)
    _, _, changes = edit_batch(
        tmp_path, "1", "1", confirm, made_on="2020-01-31", mass="0.152 g"
    )
    assert confirm.asked == changes == []


@pytest.mark.parametrize(
    ("given", "message"),
    [
        ({"made_on": "-"}, "A batch always has a date, so it can't be cleared."),
        ({"mass": "-"}, "A batch needs its mass made, its yield or both."),
        ({"mass": "152"}, "Give the unit as well"),
        ({"yield_percent": "-4"}, "can't be below 0%"),
        (
            {"made_on": (date.today() + timedelta(days=1)).isoformat()},
            "is in the future",
        ),
    ],
)
def test_impossible_batch_correction_saves_nothing(tmp_path, given, message):
    three_batches(tmp_path)
    confirm = say(True)
    with pytest.raises(CompoundError, match=message):
        edit_batch(tmp_path, "1", "3", confirm, **given)
    assert confirm.asked == []
    assert get_batch(tmp_path, "1", "3")[1] == Batch(3, "2020-02-02", 0.1)


def test_a_mass_or_yield_can_be_cleared_while_the_other_stays(tmp_path):
    three_batches(tmp_path)
    _, batch, changes = edit_batch(tmp_path, "1", "1", say(True), yield_percent="-")
    assert changes == [Change("batch 1 yield", "64.2%", None)]
    assert batch == Batch(1, "2020-01-31", 0.152)


def test_removing_batch_2_keeps_batch_3_numbered_3(tmp_path):
    three_batches(tmp_path)
    _, removed = remove_batch(tmp_path, "1", "2")
    assert removed == Batch(2, "2020-02-01", 0.14, 50)
    compound = get_compound(tmp_path, "1")
    assert [b.number for b in compound_batches(tmp_path, compound)] == [1, 3]
    assert len(rows(tmp_path, "SELECT * FROM batches")) == 3
    logged = compound_history(tmp_path, "1")[1][-1]
    assert (logged.name, logged.old, logged.new) == (
        "batch",
        "2: 2020-02-01, 140 mg, 50.0%",
        "removed",
    )
    _, added = add_batch(tmp_path, "1", mass_g=0.2)
    assert added.number == 4
    assert [b.number for b in compound_batches(tmp_path, compound)] == [1, 3, 4]


def test_a_removed_or_unknown_batch_is_refused(tmp_path):
    three_batches(tmp_path)
    remove_batch(tmp_path, "1", "2")
    today = date.today().isoformat()
    for action in (
        lambda: remove_batch(tmp_path, "1", "2"),
        lambda: edit_batch(tmp_path, "1", "2", say(True), mass="1 g"),
    ):
        with pytest.raises(
            CompoundError, match=f"Batch 2 of SYN-001 was removed on {today}."
        ):
            action()
    with pytest.raises(
        CompoundError, match="SYN-001 has no batch 4. Its batches are 1 and 3."
    ):
        get_batch(tmp_path, "1", "4")
    with pytest.raises(CompoundError, match='"two" isn\'t a batch number.'):
        get_batch(tmp_path, "1", "two")
    add_compound(tmp_path, "Test compound B")
    with pytest.raises(
        CompoundError, match="SYN-002 has no batch 1. It has no batches."
    ):
        remove_batch(tmp_path, "2", "1")


def test_unlinking_hides_the_link_keeps_the_file_and_logs_it(tmp_path):
    add_compound(tmp_path, "Test compound A")
    file = spectra_file(tmp_path)
    link_spectrum(tmp_path, "1", file, "IR")
    _, spectrum = unlink_spectrum(tmp_path, "1", "SPECTRA\\invented ir.csv")
    assert spectrum.path == "spectra/invented IR.csv"
    assert file.is_file()
    assert compound_spectra(tmp_path, get_compound(tmp_path, "1")) == []
    assert len(rows(tmp_path, "SELECT * FROM spectra")) == 1
    logged = compound_history(tmp_path, "1")[1][-1]
    assert (logged.name, logged.old, logged.new) == (
        "spectrum",
        "IR spectra/invented IR.csv",
        "removed",
    )


def test_an_unlinked_file_can_be_linked_again(tmp_path):
    add_compound(tmp_path, "Test compound A")
    link_spectrum(tmp_path, "1", spectra_file(tmp_path), "ir")
    unlink_spectrum(tmp_path, "1", "spectra/invented IR.csv")
    _, again = link_spectrum(tmp_path, "1", spectra_file(tmp_path), "UV-vis")
    compound = get_compound(tmp_path, "1")
    assert compound_spectra(tmp_path, compound) == [again]
    assert again.kind == "UV-vis"


def test_a_moved_file_can_still_be_unlinked(tmp_path):
    add_compound(tmp_path, "Test compound A")
    file = spectra_file(tmp_path)
    link_spectrum(tmp_path, "1", file)
    file.unlink()
    unlink_spectrum(tmp_path, "1", "spectra/invented IR.csv")
    assert compound_spectra(tmp_path, get_compound(tmp_path, "1")) == []


def test_unlinking_a_file_not_linked_is_refused(tmp_path):
    add_compound(tmp_path, "Test compound A")
    with pytest.raises(CompoundError, match="SYN-001 has no spectra linked."):
        unlink_spectrum(tmp_path, "1", "spectra/invented IR.csv")
    link_spectrum(tmp_path, "1", spectra_file(tmp_path))
    with pytest.raises(CompoundError, match="isn't linked to SYN-001. Its linked"):
        unlink_spectrum(tmp_path, "1", "spectra/other.csv")


def test_version_3_register_upgrades_to_version_4_keeping_batches(tmp_path):
    with closing(sqlite3.connect(tmp_path / REGISTER_NAME)) as db:
        db.executescript(
            compounds.SCHEMA
            + compounds.DETAILS_SCHEMA
            + compounds.SPECTRA_SCHEMA
            + "PRAGMA user_version = 3;"
        )
        db.execute("INSERT INTO compounds (label, status) VALUES ('Test A', 'planned')")
        db.execute(
            "INSERT INTO batches (compound_id, made_on, mass_g) "
            "VALUES (1, '2020-01-31', 0.152)"
        )
        db.commit()
    compound = get_compound(tmp_path, "1")
    assert compound_batches(tmp_path, compound) == [Batch(1, "2020-01-31", 0.152)]
    remove_batch(tmp_path, "1", "1")
    assert rows(tmp_path, "PRAGMA user_version") == [(SCHEMA_VERSION,)]
    assert compound_batches(tmp_path, compound) == []
