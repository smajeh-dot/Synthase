"""The compound register's text, with invented compounds only."""

from datetime import date

import pytest

from synthase.compound_text import (
    Section,
    card,
    card_lines,
    field_sections,
    history_lines,
    history_rows,
    list_summary,
    section_lines,
)
from synthase.compounds import (
    add_batch,
    add_compound,
    archive_compound,
    compound_history,
    edit_compound,
    get_compound,
    link_spectrum,
    list_compounds,
    table_row,
)
from synthase.workspace import create_workspace


@pytest.fixture
def workspace(tmp_path):
    """A new workspace, with the config template's placeholder values."""
    return create_workspace(tmp_path / "ws", lambda question: False).path


def invented_compound(workspace):
    """CCO, melting at 455-457 K, with batch 1: 2026-10-18, 152 mg, 64.2%."""
    add_compound(workspace, "Test compound A", smiles="CCO", melting_point="455-457")
    add_batch(workspace, "1", date(2026, 10, 18), 0.152, 64.2)
    return get_compound(workspace, "1")


def test_card_lines_for_an_invented_compound(workspace):
    compound = invented_compound(workspace)
    assert card_lines(card(compound, workspace)) == [
        "SYN-001: Test compound A",
        "  SMILES       CCO",
        "  formula      C2H6O",
        "  molar mass   46.1 g/mol",
        "  status       planned",
        "Characterisation",
        "  melting point       455–457 K",
        "Batches",
        "  1  2026-10-18  152 mg  64.2%",
        "",
        "Still missing:",
        "  no class yet",
        "  no notes yet",
        "  no Rf value yet",
        "  no appearance yet",
        "  not recorded whether it is coloured",
        "  no solubility yet",
        "  no DMSO stock concentration yet",
        "  no storage conditions yet",
        "  no risk assessment recorded",
        "  no hazard notes yet",
        "  no spectra linked yet",
    ]


def test_card_gives_the_app_its_rows(workspace):
    compound = invented_compound(workspace)
    shown = card(compound, workspace)
    assert shown.title == "SYN-001: Test compound A"
    assert shown.sections == (
        Section(
            None,
            (
                ("SMILES", "CCO"),
                ("formula", "C2H6O"),
                ("molar mass", "46.1 g/mol"),
                ("status", "planned"),
            ),
        ),
        Section("Characterisation", (("melting point", "455–457 K"),)),
        Section("Batches", (("1", "2026-10-18", "152 mg", "64.2%"),), table=True),
    )
    assert "no batches yet" not in shown.missing


def test_table_row_for_an_invented_compound(workspace):
    compound = invented_compound(workspace)
    assert table_row(compound) == (
        "SYN-001",
        "Test compound A",
        None,
        "planned",
        "C2H6O",
        "46.1",
    )


def test_field_sections_are_what_add_and_edit_print(workspace):
    compound = invented_compound(workspace)
    assert section_lines(field_sections(compound, workspace)) == [
        "  SMILES       CCO",
        "  formula      C2H6O",
        "  molar mass   46.1 g/mol",
        "  status       planned",
        "Characterisation",
        "  melting point       455–457 K",
    ]


def test_wide_melting_range_warns_under_characterisation(workspace):
    add_compound(workspace, "Test compound A", melting_point="400-410")
    compound = get_compound(workspace, "1")
    characterisation = field_sections(compound, workspace)[1]
    assert characterisation.heading == "Characterisation"
    flag, unverified = characterisation.warnings
    assert flag.startswith("! The melting range is 10 K wide")
    assert unverified.startswith("Warning: melting-point purity rule (2 K)")


def test_card_flags_a_high_yield_and_a_missing_spectra_file(workspace):
    add_compound(workspace, "Test compound A")
    add_batch(workspace, "1", date(2020, 1, 31), yield_percent=104)
    (workspace / "invented IR.csv").write_text("x", encoding="utf-8")
    link_spectrum(workspace, "1", workspace / "invented IR.csv", "ir")
    (workspace / "invented IR.csv").unlink()
    lines = card_lines(card(get_compound(workspace, "1"), workspace))
    added = date.today().isoformat()
    assert (
        "Batches\n"
        "  1  2020-01-31  -  104%\n"
        "  ! Batch 1: A yield over 100% usually means the product is still wet "
        "or impure.\n"
        "Spectra\n"
        f"  IR  invented IR.csv  (added {added})  (file not found)\n"
        "\n"
    ) in "\n".join(lines)


def test_card_says_when_nothing_is_missing(workspace, invented_details):
    add_compound(
        workspace,
        "Test compound A",
        "chalcone",
        "CCO",
        notes="invented note",
        **invented_details,
    )
    add_batch(workspace, "1", date(2020, 1, 31), 0.152)
    (workspace / "invented IR.csv").write_text("x", encoding="utf-8")
    link_spectrum(workspace, "1", workspace / "invented IR.csv")
    lines = card_lines(card(get_compound(workspace, "1"), workspace))
    assert lines[-2:] == ["", "Nothing missing."]


def test_archived_compound_title(workspace):
    add_compound(workspace, "Test compound A")
    compound = archive_compound(workspace, "1")
    assert card(compound, workspace).title == "SYN-001: Test compound A (archived)"


def test_history_rows_and_lines(workspace):
    invented_compound(workspace)
    edit_compound(workspace, "1", lambda change: True, notes="invented note")
    compound, changes = compound_history(workspace, "1")
    rows = history_rows(changes)
    assert [row[1:] for row in rows] == [
        ("label", "(blank)", "Test compound A"),
        ("SMILES", "(blank)", "CCO"),
        ("status", "(blank)", "planned"),
        ("melting point", "(blank)", "455–457 K"),
        ("batch", "(blank)", "1: 2026-10-18, 152 mg, 64.2%"),
        ("notes", "(blank)", "invented note"),
    ]
    when = rows[0][0]
    assert len(when) == 16 and when[10] == " "
    lines = history_lines(compound, changes)
    assert lines[0] == "History of SYN-001: Test compound A"
    assert lines[1:] == [
        f"  {rows[0][0]}  label          (blank) -> Test compound A",
        f"  {rows[1][0]}  SMILES         (blank) -> CCO",
        f"  {rows[2][0]}  status         (blank) -> planned",
        f"  {rows[3][0]}  melting point  (blank) -> 455–457 K",
        f"  {rows[4][0]}  batch          (blank) -> 1: 2026-10-18, 152 mg, 64.2%",
        f"  {rows[5][0]}  notes          (blank) -> invented note",
    ]


@pytest.fixture
def three_compounds(workspace):
    """Two invented chalcones, one of them archived, and one Schiff base."""
    add_compound(workspace, "Test compound A", "chalcone", status="synthesised")
    add_compound(workspace, "Test compound B", "chalcone")
    add_compound(workspace, "Test compound C", "Schiff base")
    archive_compound(workspace, "2")
    return workspace


@pytest.mark.parametrize(
    ("filters", "summary"),
    [
        ({}, "2 compounds (1 archived, hidden; add --all to see it)."),
        ({"archived": True}, "3 compounds."),
        (
            {"compound_class": "chalcone"},
            "1 of 2 compounds (class: chalcone; 1 archived, hidden; "
            "add --all to see it).",
        ),
        (
            {"compound_class": "chalcone", "archived": True},
            "2 of 3 compounds (class: chalcone).",
        ),
        ({"status": "purified"}, "No compounds match (status: purified)."),
    ],
)
def test_list_summary(three_compounds, filters, summary):
    shown = list_compounds(three_compounds, **filters)
    everything = list_compounds(three_compounds, archived=True)
    assert list_summary(shown, everything, **filters) == summary


def test_list_summary_when_every_compound_is_archived(workspace):
    add_compound(workspace, "Test compound A")
    archive_compound(workspace, "1")
    everything = list_compounds(workspace, archived=True)
    assert list_summary([], everything) == (
        "Every compound is archived. Add --all to see them."
    )


def test_nothing_is_printed(workspace, capsys):
    compound = invented_compound(workspace)
    card_lines(card(compound, workspace))
    history_lines(*compound_history(workspace, "1"))
    everything = list_compounds(workspace, archived=True)
    list_summary(everything, everything)
    assert capsys.readouterr() == ("", "")
