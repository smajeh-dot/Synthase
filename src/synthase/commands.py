"""The app's one command list, and Tab completion over it.

The list is the ``syn`` tree read from ``build_parser()``, plus the commands only
the app has. A new command or option added to the parser is completed with no
extra work. Like compound_text.py, nothing here prints anything. The details are
in docs/decisions/0016-full-screen-app.md under "Details settled for #53".
"""

import argparse
import os
from dataclasses import dataclass, field

from synthase.cli import build_parser

# Commands only the app has. #54 adds "help".
APP_ONLY = ("quit",)


@dataclass
class Command:
    """One command: its subcommands and its ``--options``."""

    name: str
    subcommands: dict[str, "Command"] = field(default_factory=dict)
    options: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Completion:
    """What Tab gives: the new text, and the choices to list when it can't decide."""

    text: str
    choices: tuple[str, ...] = ()


def _read(name: str, parser: argparse.ArgumentParser) -> Command:
    command = Command(name)
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for sub_name, sub_parser in action.choices.items():
                command.subcommands[sub_name] = _read(sub_name, sub_parser)
        elif not isinstance(action, argparse._HelpAction | argparse._VersionAction):
            # /help is the app's way to get help (#54), so -h and --help aren't offered.
            command.options += [o for o in action.option_strings if o.startswith("--")]
    return command


def command_list() -> Command:
    """Every app command, as a tree under a nameless root."""
    root = _read("", build_parser())
    for name in APP_ONLY:
        root.subcommands[name] = Command(name)
    return root


def find(text: str, root: Command) -> Command | None:
    """The top-level command a line starts with, ignoring spaces and capitals."""
    words = text.strip().lower().split()
    if not words or not words[0].startswith("/"):
        return None
    return root.subcommands.get(words[0][1:])


def complete(text: str, root: Command) -> Completion:
    """Complete the last word of ``text``: a command, a subcommand or an option."""
    if not text.lstrip().startswith("/"):
        return Completion(text)
    words = text.split()
    word = "" if text[-1].isspace() else words.pop()
    # Walk down the tree while the earlier words name subcommands.
    node, walked = root, True
    for earlier in words:
        child = node.subcommands.get(earlier.lower().removeprefix("/"))
        if walked and child is not None:
            node = child
        else:
            walked = False
    if word.startswith("-"):
        candidates = node.options
    elif walked:
        slash = "/" if node is root else ""
        candidates = [slash + name for name in node.subcommands]
    else:
        # A compound ID or a file name: out of scope for #53.
        candidates = []
    matches = sorted(c for c in candidates if c.lower().startswith(word.lower()))
    if not matches:
        return Completion(text)
    start = text[: len(text) - len(word)]
    if len(matches) == 1:
        return Completion(start + matches[0] + " ")
    shared = os.path.commonprefix(matches)
    if len(shared) > len(word):
        return Completion(start + shared)
    return Completion(text, tuple(matches))
