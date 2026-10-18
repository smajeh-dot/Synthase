"""The compound register, with invented compounds only."""

import sqlite3
from contextlib import closing

import pytest

from synthase import compounds
from synthase.compounds import (
    REGISTER_NAME,
    SCHEMA_VERSION,
    Compound,
    CompoundError,
    add_compound,
    check_label,
    get_compound,
    list_compounds,
    missing_fields,
    parse_class,
    parse_id,
    parse_status,
    read_smiles,
)
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
    ]


def test_nothing_missing_once_every_field_is_filled(tmp_path):
    full = add_compound(tmp_path, "Test compound A", "chalcone", "CCO", notes="x")
    assert missing_fields(full) == []
