"""The guided questions, worked through without the terminal, with invented answers."""

from datetime import date

import pytest

from synthase.compound_questions import (
    NEEDS_MASS_OR_YIELD,
    add_flow,
    batch_flow,
    change_question,
    compound_answers,
    confirm_flow,
    confirmed,
    edit_batch_flow,
    edit_flow,
    is_yes,
    kept_message,
    spectrum_flow,
    unlink_flow,
)
from synthase.compounds import (
    Change,
    CompoundError,
    add_batch,
    add_compound,
    edit_compound,
    get_batch,
    get_compound,
    link_spectrum,
)
from synthase.workspace import create_workspace

GROUPS = (
    "characterisation details (melting point, Rf)? [y/N] ",
    "handling details (appearance, colour, solubility, DMSO stock, storage)? [y/N] ",
    "safety details (risk assessment, hazards)? [y/N] ",
)


@pytest.fixture
def workspace(tmp_path):
    """A new workspace, with the config template's placeholder values."""
    return create_workspace(tmp_path / "ws", lambda question: False).path


def run(flow, *replies):
    """Work through ``flow`` with ``replies`` typed in turn, as the app will.

    Returns the answers, and each prompt shown with any refusal after it.
    Every reply must be used.
    """
    answers = {}
    shown = []
    waiting = iter(replies)
    while (question := flow.next_question(answers)) is not None:
        shown.append(question.prompt)
        try:
            answers[question.key] = question.answer(next(waiting), answers)
        except CompoundError as error:
            shown.append(str(error))
    assert list(waiting) == []
    return answers, shown


def test_add_refuses_a_backwards_melting_range_then_takes_it(workspace):
    flow = add_flow(workspace)
    answers, shown = run(
        flow,
        *("Test compound A", "", "CCO", "", ""),
        *("y", "457-455", "455-457", "", "n", "n"),
    )
    assert flow.opening == (
        "New compound. Press Enter to skip any question except the label.",
    )
    assert shown == [
        "Label: ",
        "Class (Schiff base, chalcone, starting material, other): ",
        "SMILES: ",
        "Status [planned]: ",
        "Notes: ",
        f"Add {GROUPS[0]}",
        "Melting range in K (e.g. 455-457): ",
        "The melting range runs from high to low (457 to 455 K). "
        "Type the lower temperature first.",
        "Melting range in K (e.g. 455-457): ",
        "Rf (0 to 1): ",
        f"Add {GROUPS[1]}",
        f"Add {GROUPS[2]}",
    ]
    assert compound_answers(answers) == {
        "label": "Test compound A",
        "compound_class": None,
        "smiles": "CCO",
        "status": "planned",
        "notes": "",
        "melting_point": "455-457",
        "rf": None,
    }
    compound = add_compound(workspace, **compound_answers(answers))
    assert (compound.label, compound.smiles) == ("Test compound A", "CCO")
    assert str(compound.melting_point) == "455–457 K"


def test_add_says_which_questions_can_be_skipped(workspace):
    questions = {question.key: question for question in add_flow(workspace).questions}
    assert not questions["label"].skippable
    assert all(
        question.skippable for key, question in questions.items() if key != "label"
    )
    with pytest.raises(CompoundError, match="A compound needs a label"):
        questions["label"].answer("  ", {})


def test_add_refuses_a_bad_smiles_and_asks_for_the_solvent_after_an_rf(workspace):
    answers, shown = run(
        add_flow(workspace),
        *("Test compound A", "chalcone", "xyz", "CCO", "", "invented note"),
        *("y", "", "0.45", "", "invented solvent 3:1", "", "yes", "", ""),
    )
    assert 'RDKit can\'t read the SMILES "xyz".' in shown[3]
    assert shown[-6:-4] == [
        "An Rf value needs the solvent system it was measured in, such as "
        '"hexane:ethyl acetate 3:1".',
        "Rf solvent system (e.g. hexane:ethyl acetate 3:1): ",
    ]
    assert answers["compound_class"] == "chalcone"
    assert answers["rf_solvent"] == "invented solvent 3:1"
    assert (answers["Handling"], answers["Safety"]) == (False, True)
    assert "appearance" not in answers


@pytest.mark.parametrize("reply", ["", "n", "maybe", "yess"])
def test_anything_but_yes_skips_a_group(workspace, reply):
    answers, shown = run(
        add_flow(workspace), "Test compound A", "", "", "", "", reply, reply, reply
    )
    assert shown[-3:] == [f"Add {group}" for group in GROUPS]
    assert set(compound_answers(answers)) == {
        "label",
        "compound_class",
        "smiles",
        "status",
        "notes",
    }


@pytest.mark.parametrize("reply", ["y", "Y", "yes", " YES "])
def test_only_yes_or_y_counts_as_yes(reply):
    assert is_yes(reply)


def test_edit_shows_current_values_and_enter_keeps_them(workspace):
    add_compound(workspace, "Test compound A", smiles="CCO", melting_point="455-457")
    compound = get_compound(workspace, "1")
    flow = edit_flow(workspace, compound)
    answers, shown = run(
        flow, "", "-", "", "synthesised", "", "y", "456-458", "", "", "n", "n"
    )
    assert flow.opening == (
        "Editing SYN-001: Test compound A. "
        "Press Enter to keep a value, or type - to clear it.",
    )
    assert shown == [
        "Label [Test compound A]: ",
        "Class (Schiff base, chalcone, starting material, other): ",
        "SMILES [CCO]: ",
        "Status (planned, synthesised, purified, characterised, tested) [planned]: ",
        "Notes: ",
        f"Edit {GROUPS[0]}",
        "Melting range in K (e.g. 455-457) [455–457 K]: ",
        "Rf (0 to 1): ",
        "Rf solvent system (e.g. hexane:ethyl acetate 3:1): ",
        f"Edit {GROUPS[1]}",
        f"Edit {GROUPS[2]}",
    ]
    flags = compound_answers(answers)
    assert flags["label"] is None
    assert flags["compound_class"] == "-"
    compound, changes = edit_compound(workspace, "1", lambda change: True, **flags)
    assert [change.name for change in changes] == ["status", "melting point"]


def test_edit_refuses_clearing_the_solvent_of_a_kept_rf(workspace):
    add_compound(
        workspace, "Test compound A", rf="0.45", rf_solvent="invented solvent 3:1"
    )
    answers, shown = run(
        edit_flow(workspace, get_compound(workspace, "1")),
        *("", "", "", "", ""),
        *("y", "", "", "-", "", "n", "n"),
    )
    assert shown[9] == (
        "An Rf value needs the solvent system it was measured in, such as "
        '"hexane:ethyl acetate 3:1".'
    )
    assert answers["rf_solvent"] is None


def test_batch_needs_a_mass_or_a_yield(workspace):
    add_compound(workspace, "Test compound A")
    flow = batch_flow(get_compound(workspace, "1"))
    answers, shown = run(flow, "", "", "", "64.2")
    assert flow.opening == (
        "New batch of SYN-001: Test compound A. Press Enter for today's date, "
        "or to skip the mass or the yield.",
    )
    assert shown == [
        "Date made (e.g. 2026-10-18): ",
        "Mass made (e.g. 152 mg): ",
        "Yield in % (e.g. 64.2): ",
        NEEDS_MASS_OR_YIELD,
        "Yield in % (e.g. 64.2): ",
    ]
    assert answers == {
        "made_on": date.today(),
        "mass_g": None,
        "yield_percent": 64.2,
    }


def test_edit_batch_refuses_clearing_both_the_mass_and_the_yield(workspace):
    add_compound(workspace, "Test compound A")
    add_batch(workspace, "1", date(2026, 10, 1), 0.152, 64.2)
    compound, batch = get_batch(workspace, "1", "1")
    answers, shown = run(edit_batch_flow(compound, batch), "", "-", "-", "")
    assert shown == [
        "Date made [2026-10-01]: ",
        "Mass made [152 mg]: ",
        "Yield in % [64.2%]: ",
        NEEDS_MASS_OR_YIELD,
        "Yield in % [64.2%]: ",
    ]
    assert answers == {"made_on": None, "mass": "-", "yield_percent": None}


def test_spectrum_needs_a_file_and_takes_a_dragged_in_path(workspace):
    (workspace / "spectra").mkdir()
    file = workspace / "spectra" / "invented IR.csv"
    file.write_text("x", encoding="utf-8")
    add_compound(workspace, "Test compound A")
    flow = spectrum_flow(workspace, get_compound(workspace, "1"))
    answers, shown = run(flow, "", f'"{file}"', "ir")
    assert shown[:2] == ["File: ", "Type the file's path, or drag the file in."]
    assert not flow.questions[0].skippable
    assert answers == {"file": file, "kind": "IR"}


def test_unlink_lists_the_files_then_asks_which_one(workspace):
    (workspace / "spectra").mkdir()
    add_compound(workspace, "Test compound A")
    for name in ("invented IR.csv", "invented NMR.csv"):
        (workspace / "spectra" / name).write_text("x", encoding="utf-8")
        link_spectrum(workspace, "1", workspace / "spectra" / name, None)
    flow = unlink_flow(workspace, get_compound(workspace, "1"))
    answers, shown = run(flow, "3", "2")
    assert flow.opening[0] == "Spectra linked to SYN-001: Test compound A"
    assert [line.split()[0] for line in flow.opening[1:]] == ["1", "2"]
    assert shown == [
        "Which one? (1-2): ",
        "Type the number of the file to unlink (1-2).",
        "Which one? (1-2): ",
    ]
    assert answers["file"].endswith("invented NMR.csv")


def test_unlink_with_nothing_linked_is_refused(workspace):
    add_compound(workspace, "Test compound A")
    with pytest.raises(CompoundError, match="SYN-001 has no spectra linked."):
        unlink_flow(workspace, get_compound(workspace, "1"))


@pytest.mark.parametrize(
    ("change", "question", "kept"),
    [
        (
            Change("smiles", "CCO", "CCC"),
            'Change the SMILES from "CCO" to "CCC"? [y/N] ',
            'Kept the SMILES as "CCO".',
        ),
        (
            Change("notes", "invented note", None),
            'Clear the notes ("invented note")? [y/N] ',
            'Kept the notes as "invented note".',
        ),
        (
            Change("batch 2 mass", "152 mg", None),
            'Clear batch 2\'s mass ("152 mg")? [y/N] ',
            'Kept batch 2\'s mass as "152 mg".',
        ),
    ],
)
def test_change_confirmation_wording(change, question, kept):
    assert change_question(change) == question
    assert kept_message(change) == kept


def test_confirm_flow_asks_only_about_set_values():
    changes = [
        Change("smiles", "CCO", "CCN"),
        Change("storage", None, "fridge"),
        Change("notes", "invented note", None),
    ]
    flow = confirm_flow(changes)
    assert flow.opening == ()
    assert [q.prompt for q in flow.questions] == [
        change_question(changes[0]),
        change_question(changes[2]),
    ]
    assert [q.kept for q in flow.questions] == [
        kept_message(changes[0]),
        kept_message(changes[2]),
    ]
    answers = {}
    for question, typed in zip(flow.questions, ["Y", "nope"], strict=True):
        answers[question.key] = question.answer(typed, answers)
    assert flow.next_question(answers) is None
    assert confirmed(changes, answers) == {changes[0], changes[1]}
