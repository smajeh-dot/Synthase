"""Tab completion over the app's one command list."""

import argparse

import pytest

from synthase.cli import build_parser
from synthase.commands import (
    Command,
    Completion,
    HelpPage,
    command_list,
    complete,
    find,
    help_page,
)

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
        ("/he", "/help "),
        ("/help com", "/help compound "),
        ("/con", "/config "),
        ("/help compound ba", "/help compound batch "),
    ],
)
def test_one_match_or_a_longer_shared_start_completes(typed, completed):
    assert complete(typed, ROOT) == Completion(completed)


@pytest.mark.parametrize(
    ("typed", "choices"),
    [
        ("/compound edit", ("edit", "edit-batch")),
        ("/compound edit 1 --rf", ("--rf", "--rf-solvent")),
        ("/", ("/compound", "/config", "/doctor", "/help", "/init", "/quit")),
        ("/help co", ("compound", "config")),
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


def test_help_lists_every_command_then_how_to_get_more():
    page = help_page([], ROOT)
    assert [name for name, _ in page.rows] == [
        "/init",
        "/doctor",
        "/compound",
        "/config",
        "/help",
        "/quit",
    ]
    assert dict(page.rows)["/quit"] == "leave Synthase (or press Ctrl+Q)"
    assert page.hint == "Type /help <command> for more, e.g. /help compound."
    assert page.paragraphs == ()
    assert page.error == ""


def test_help_on_a_command_lists_its_subcommands():
    page = help_page(["compound"], ROOT)
    assert page.paragraphs == (
        "Keep track of the project's compounds, from idea to tested.",
    )
    assert page.rows[0] == ("/compound add", "add a compound to the register")
    assert ("/compound batch", "add a batch made of a compound") in page.rows
    assert page.hint == (
        "For a command's options, type /help compound <command>, "
        "e.g. /help compound add."
    )


def test_help_on_one_command_shows_its_usage_arguments_and_options():
    page = help_page(["compound", "batch"], ROOT)
    usage, description = page.paragraphs
    assert usage == "/compound batch ID [--date DATE] [--mass MASS] [--yield PERCENT]"
    assert description.startswith("Add a batch made of a compound")
    assert page.rows == (
        ("ID", "its ID, such as SYN-001"),
        ("--date DATE", "the date it was made, such as 2026-10-18 (default: today)"),
        ("--mass MASS", "the mass made, in mg or g, such as 152 mg"),
        ("--yield PERCENT", "the percentage yield, such as 64.2"),
    )
    assert page.hint == ""


@pytest.mark.parametrize(
    ("topic", "usage"),
    [
        (["init"], "/init [PATH]"),
        (["doctor"], "/doctor"),
        (["compound", "unlink"], "/compound unlink ID [FILE]"),
        (
            ["compound", "list"],
            "/compound list [--status STATUS] [--class CLASS] [--all] [--csv FILE]",
        ),
        (["help"], "/help [COMMAND]"),
        (["quit"], "/quit"),
    ],
)
def test_usage_lines(topic, usage):
    assert help_page(topic, ROOT).paragraphs[0] == usage


def test_help_ignores_capitals_and_a_leading_slash():
    assert help_page(["/Compound", "BATCH"], ROOT) == help_page(
        ["compound", "batch"], ROOT
    )


def test_help_and_version_options_are_not_in_the_help():
    names = [name for name, _ in help_page(["compound", "list"], ROOT).rows]
    assert not any("--help" in n or "--version" in n for n in names)


@pytest.mark.parametrize(
    ("topic", "error"),
    [
        (
            ["foo"],
            'There\'s no help on "foo". '
            "Topics: init, doctor, compound, config, help, quit.",
        ),
        (
            ["/compound", "zzz"],
            'There\'s no help on "compound zzz". Topics: add, edit, archive, '
            "restore, history, batch, edit-batch, remove-batch, spectrum, unlink, "
            "show, list.",
        ),
        (
            ["compound", "batch", "1"],
            'There\'s no help on "compound batch 1". Try /help compound batch.',
        ),
        (
            ["help", "compound"],
            'There\'s no help on "help compound". Try /help help.',
        ),
    ],
)
def test_an_unknown_topic_lists_the_topics(topic, error):
    assert help_page(topic, ROOT) == HelpPage(error=error)


def _subparsers(parser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def test_every_help_string_in_the_parser_is_in_the_help():
    """Walk build_parser() itself, so /help and syn --help can't drift apart."""

    def check(parser, topic):
        page = help_page(topic, ROOT)
        if topic:  # /help alone is just the list
            assert (parser.description or "") in page.paragraphs + ("",)
        subparsers = _subparsers(parser)
        if subparsers is None:
            for action in parser._actions:
                if action.help and action.help != argparse.SUPPRESS:
                    if not isinstance(
                        action, argparse._HelpAction | argparse._VersionAction
                    ):
                        assert action.help in dict(page.rows).values()
            return
        summaries = dict(page.rows).values()
        for choice in subparsers._choices_actions:
            assert choice.help in summaries
            check(subparsers.choices[choice.dest], [*topic, choice.dest])

    check(build_parser(), [])


def test_a_new_parser_command_is_in_the_help_with_no_extra_work(monkeypatch):
    def parser_with_a_new_command():
        parser = build_parser()
        commands = _subparsers(parser)
        plate = commands.add_parser("plate", help="design a plate", description="D.")
        plate.add_argument("--wells", help="how many wells")
        return parser

    monkeypatch.setattr("synthase.commands.build_parser", parser_with_a_new_command)
    root = command_list()
    assert ("/plate", "design a plate") in help_page([], root).rows
    assert help_page(["plate"], root) == HelpPage(
        paragraphs=("/plate [--wells WELLS]", "D."),
        rows=(("--wells WELLS", "how many wells"),),
    )
