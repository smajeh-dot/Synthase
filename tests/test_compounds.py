"""The compound register, with invented compounds only."""

import sqlite3
from contextlib import closing

import pytest

from synthase import compounds
from synthase.compounds import (
    REGISTER_NAME,
    SCHEMA_VERSION,
    CompoundError,
    add_compound,
    check_label,
    parse_class,
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
