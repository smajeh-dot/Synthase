from pathlib import Path

import pytest

from synthase.commands import COMMANDS, CommandError, complete, dispatch, parse
from synthase.suggest import suggestion

DECISION = (
    Path(__file__).parents[1]
    / "docs"
    / "decisions"
    / "0023-command-set-and-project-folder.md"
)


def approved() -> list[tuple[str, str, str]]:
    """Decision 0023's command table, word for word: usage, help, example."""
    rows = []
    for line in DECISION.read_text(encoding="utf-8").splitlines():
        if line.startswith("| `"):
            usage, help_text, example = (
                cell.strip() for cell in line.strip("|").split(" | ")
            )
            rows.append((usage.strip("`"), help_text, example.strip("`")))
    return rows


def error(line: str) -> str:
    with pytest.raises(CommandError) as raised:
        parse(line)
    return str(raised.value)


def test_the_table_holds_the_approved_wording_in_order():
    assert [(c.usage, c.help, c.example) for c in COMMANDS] == approved()


@pytest.mark.parametrize("command", COMMANDS, ids=lambda c: c.usage)
def test_every_example_reads_as_its_own_command(command):
    assert parse(command.example).command is command


def test_help_groups_the_commands():
    lines = dispatch("help", {}).splitlines()
    assert [line for line in lines if not line.startswith(" ")] == [
        "Project",
        "Experiments",
        "Values",
        "Compounds",
        "General",
    ]
    assert lines[1].split() == ["project", "create", *COMMANDS[0].help.split()]
    # Indented two spaces, with the help lined up two spaces after the longest
    # usage line.
    column = 2 + max(len(c.usage) for c in COMMANDS) + 2
    commands = [line for line in lines if line.startswith(" ")]
    assert commands == [f"  {c.usage}".ljust(column) + c.help for c in COMMANDS]


def test_help_on_a_command_shows_every_form():
    assert dispatch("help project", {}) == (
        "Usage: project create\n"
        "Set up a Synthase project in this folder.\n"
        "Example: project create\n"
        "\n"
        "Usage: project show\n"
        "Show this project's name, folder and contents.\n"
        "Example: project show\n"
        "\n"
        "Usage: project edit\n"
        "Rename this project.\n"
        "Example: project edit"
    )


def test_help_on_one_form_is_a_usage_error():
    assert dispatch("help exp show", {}) == "Usage: help [command]"


def test_help_on_an_unknown_command():
    assert dispatch("help epx", {}) == (
        "Unknown command 'epx'. Did you mean: exp, exit?"
    )


def test_unknown_command_word():
    assert error("epx") == "Unknown command 'epx'. Did you mean: exp, exit?"


def test_unknown_second_word():
    assert error("exp shwo") == (
        "Unknown command 'exp shwo'. Did you mean: exp show, exp open?"
    )


def test_nothing_close_lists_every_command():
    assert error("xyz") == (
        "Unknown command 'xyz'. Commands: compound, exit, exp, help, project, value"
    )
    assert error("exp xyz") == (
        "Unknown command 'exp xyz'. "
        "Commands: exp create, exp edit, exp export, exp open, exp show"
    )


def test_command_words_are_case_sensitive():
    assert error("Exp show") == "Unknown command 'Exp'. Did you mean: exp, exit?"


def test_a_command_word_alone_prints_every_usage_line():
    assert error("exp") == (
        "Usage: exp create\n"
        "Usage: exp open <ID or title>\n"
        "Usage: exp show [ID] [value name]\n"
        "Usage: exp show all\n"
        "Usage: exp edit\n"
        "Usage: exp export <csv or json>"
    )


def test_missing_and_extra_parts_print_usage():
    assert error("exp export") == "Usage: exp export <csv or json>"
    assert error("exp export csv now") == "Usage: exp export <csv or json>"
    assert error("project create Aspirin") == "Usage: project create"
    assert error("exit now") == "Usage: exit"
    assert error("value add m_crude 2.211") == (
        "Usage: value add <name> <value> <unit> [+/- unc] [# note]"
    )
    assert error("value add m_crude 2.211 g +/-") == (
        "Usage: value add <name> <value> <unit> [+/- unc] [# note]"
    )
    assert error("value add m_crude 2.211 g 0.001") == (
        "Usage: value add <name> <value> <unit> [+/- unc] [# note]"
    )


def test_extra_parts_after_show_all_print_both_show_forms():
    assert error("exp show all E002") == (
        "Usage: exp show [ID] [value name]\nUsage: exp show all"
    )


def test_show_all_and_show_by_id_are_told_apart():
    assert parse("exp show all").command.usage == "exp show all"
    call = parse("exp show E002 m_crude")
    assert call.command.usage == "exp show [ID] [value name]"
    assert call.args == {"id": "E002", "value_name": "m_crude"}
    assert parse("exp show").args == {"id": None, "value_name": None}


def test_a_blank_line_is_nothing():
    assert parse("   ") is None
    assert dispatch("", {}) == ""


def test_exp_open_takes_the_rest_of_the_line():
    assert parse("exp open Recrystallisation trial 2").args == {
        "id_or_title": "Recrystallisation trial 2"
    }


def test_exp_open_strips_one_pair_of_quotes():
    assert parse('exp open "Recrystallisation trial 2"').args == {
        "id_or_title": "Recrystallisation trial 2"
    }
    assert parse('exp open "Recrystallisation').args == {
        "id_or_title": '"Recrystallisation'
    }
    assert error('exp open ""') == "Usage: exp open <ID or title>"


def test_a_value_line_with_uncertainty_and_note():
    call = parse("value add m_crude 2.211 g +/- 0.001 # Balance B2")
    assert call.args == {
        "name": "m_crude",
        "value": "2.211",
        "unit": "g",
        "uncertainty": "0.001",
        "note": "Balance B2",
    }


def test_the_note_is_everything_after_the_first_hash():
    call = parse("value edit m_crude 2.215 g #   from #2 balance, re-weighed")
    assert call.args["note"] == "from #2 balance, re-weighed"
    assert call.args["uncertainty"] is None


def test_the_plus_minus_sign_also_introduces_the_uncertainty():
    assert parse("value add m 2.100 g ± 0.001").args["uncertainty"] == "0.001"


def test_values_are_kept_exactly_as_typed():
    assert parse("value add m_crude 2.100 g").args["value"] == "2.100"


def test_a_corrected_command_is_never_run():
    ran = []
    out = dispatch("exp shwo", {("exp", "show"): lambda call: ran.append(call)})
    assert ran == []
    assert out.startswith("Unknown command 'exp shwo'.")


def test_tab_completes_command_words():
    assert complete("") == ["compound", "exit", "exp", "help", "project", "value"]
    assert complete("e") == ["exit", "exp"]
    assert complete("exp ") == ["create", "edit", "export", "open", "show"]
    assert complete("exp ex") == ["export"]
    assert complete("exp show ") == ["all"]
    assert complete("help p") == ["project"]
    assert complete("value add m_") == []


# Spec Section 3, with `compound show` standing in for `fetch` (decision 0023).
FIELDS = ["name", "formula", "molar_mass", "density", "purity", "note"]
LIBRARY = {
    "C001": {"name": "Salicylic acid", "molar_mass": "138.12 g/mol"},
    "C011": {"name": "Invented compound B"},
    "C123": {"name": "Invented compound C"},
}


def compound_show_stub(call):
    compound_id, field = call.args["id"], call.args["field"]
    if compound_id not in LIBRARY:
        ids = list(LIBRARY)
        return f"Unknown compound '{compound_id}'. " + suggestion(
            compound_id, ids, "Compounds"
        )
    if field not in FIELDS:
        return f"Unknown field '{field}' for {compound_id}. " + suggestion(
            field, FIELDS, "Fields"
        )
    return LIBRARY[compound_id].get(field, "")


@pytest.mark.parametrize(
    ("line", "output"),
    [
        (
            "compound show C001 molarmass",
            "Unknown field 'molarmass' for C001. Closest: molar_mass, formula",
        ),
        (
            "compound show C010 formula",
            "Unknown compound 'C010'. Closest: C001, C011",
        ),
        (
            "compound show C001 boiling",
            "Unknown field 'boiling' for C001. "
            "Fields: name, formula, molar_mass, density, purity, note",
        ),
        (
            "compound show",
            "Usage: compound show <ID> [field]\nUsage: compound show all",
        ),
        ("compound show C001 molar_mass", "138.12 g/mol"),
    ],
)
def test_spec_section_3_examples(line, output):
    handlers = {("compound", "show"): compound_show_stub}
    assert dispatch(line, handlers) == output
