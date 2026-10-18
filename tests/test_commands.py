"""Tab completion over the app's one command list."""

import pytest

from synthase.cli import build_parser
from synthase.commands import Command, Completion, command_list, complete, find

ROOT = command_list()


@pytest.mark.parametrize(
    ("typed", "completed"),
    [
        ("/comp", "/compound "),
        ("/COMP", "/compound "),
        ("/q", "/quit "),
        ("/compound sh", "/compound show "),
        ("/Compound SH", "/Compound show "),
        ("/compound list --sta", "/compound list --status "),
        (
            "/compound list --status final --cl",
            "/compound list --status final --class ",
        ),
        ("/compound e", "/compound edit"),
        ("  /doc", "  /doctor "),
    ],
)
def test_one_match_or_a_longer_shared_start_completes(typed, completed):
    assert complete(typed, ROOT) == Completion(completed)


@pytest.mark.parametrize(
    ("typed", "choices"),
    [
        ("/compound edit", ("edit", "edit-batch")),
        ("/compound edit 1 --rf", ("--rf", "--rf-solvent")),
        ("/", ("/compound", "/doctor", "/init", "/quit")),
    ],
)
def test_several_matches_are_listed_and_the_text_is_kept(typed, choices):
    assert complete(typed, ROOT) == Completion(typed, choices)


def test_a_space_after_a_command_lists_its_subcommands():
    result = complete("/compound ", ROOT)
    assert result.text == "/compound "
    assert result.choices[:3] == ("add", "archive", "batch")
    assert "show" in result.choices


@pytest.mark.parametrize(
    "typed",
    [
        "",
        "comp",
        "/zzz",
        "/compound show 1",
        "/compound show SYN-0",
        "/compound list --zzz",
        "/compound list --he",
    ],
)
def test_nothing_to_complete_leaves_the_text_alone(typed):
    assert complete(typed, ROOT) == Completion(typed)


def test_a_new_parser_command_is_completed_with_no_extra_work(monkeypatch):
    def parser_with_a_new_command():
        parser = build_parser()
        commands = next(a for a in parser._actions if a.dest == "command")
        commands.add_parser("plate").add_argument("--wells")
        return parser

    monkeypatch.setattr("synthase.commands.build_parser", parser_with_a_new_command)
    root = command_list()
    assert complete("/pla", root).text == "/plate "
    assert complete("/plate --we", root).text == "/plate --wells "


def test_find_names_the_top_level_command_ignoring_spaces_and_capitals():
    assert find("  /COMPOUND show 1", ROOT).name == "compound"
    assert find("/quit", ROOT).name == "quit"
    assert find("quit", ROOT) is None
    assert find("/zzz", ROOT) is None
    assert find("", ROOT) is None


def test_help_and_version_options_are_not_offered():
    assert "--version" not in ROOT.options
    assert "--help" not in ROOT.subcommands["compound"].subcommands["list"].options
    assert isinstance(ROOT.subcommands["quit"], Command)
