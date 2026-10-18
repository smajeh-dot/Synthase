"""The app's one command list, Tab completion over it, and the /help pages.

The list is the ``syn`` tree read from ``build_parser()``, plus the commands only
the app has. A new command or option added to the parser is completed, and shows
in /help, with no extra work. Like compound_text.py, nothing here prints anything.
The details are in docs/decisions/0016-full-screen-app.md under "Details settled
for #53" and "Details settled for #54".
"""

import argparse
import os
from dataclasses import dataclass, field

from synthase.cli import build_parser

HELP = "help"
# Commands only the app has: name, one-line help, usage and description.
APP_ONLY = (
    (
        HELP,
        "list the commands, or explain one",
        "/help [COMMAND]",
        "List every command, or explain one command and its options, "
        "such as /help compound.",
    ),
    (
        "quit",
        "leave Synthase (or press Ctrl+Q)",
        "/quit",
        "Leave Synthase. Ctrl+Q does the same.",
    ),
)
ROOT_HINT = "Type /help <command> for more, e.g. /help compound."
SUBCOMMANDS_HINT = (
    "For a command's options, type /help {name} <command>, e.g. /help {first}."
)
NO_HELP = 'There\'s no help on "{asked}".'


@dataclass
class Command:
    """One command: its subcommands and ``--options``, and the text /help shows."""

    name: str
    subcommands: dict[str, "Command"] = field(default_factory=dict)
    options: list[str] = field(default_factory=list)
    # How it is typed, such as "/compound batch"; empty for the root.
    path: str = ""
    summary: str = ""
    usage: str = ""
    description: str = ""
    # Its arguments and options, each with its help.
    rows: list[tuple[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class Completion:
    """What Tab gives: the new text, and the choices to list when it can't decide."""

    text: str
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class HelpPage:
    """What /help shows: paragraphs, two-column rows and a hint; or an error."""

    paragraphs: tuple[str, ...] = ()
    rows: tuple[tuple[str, str], ...] = ()
    hint: str = ""
    error: str = ""


def _read(name: str, parser: argparse.ArgumentParser, path: str = "") -> Command:
    command = Command(name, path=path, description=parser.description or "")
    arguments, options, option_rows = [], [], []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            summaries = {a.dest: a.help or "" for a in action._choices_actions}
            for sub_name, sub_parser in action.choices.items():
                sub_path = f"{path} {sub_name}" if path else f"/{sub_name}"
                sub = _read(sub_name, sub_parser, sub_path)
                sub.summary = summaries.get(sub_name, "")
                command.subcommands[sub_name] = sub
        elif isinstance(action, argparse._HelpAction | argparse._VersionAction):
            # /help is the app's way to get help, so -h and --help aren't offered.
            continue
        elif not action.option_strings:
            metavar = action.metavar or action.dest.upper()
            arguments.append(f"[{metavar}]" if action.nargs == "?" else metavar)
            command.rows.append((metavar, action.help or ""))
        else:
            command.options += [o for o in action.option_strings if o.startswith("--")]
            spelled = max(action.option_strings, key=len)
            if action.nargs != 0:
                spelled += " " + (action.metavar or action.dest.upper())
            options.append(spelled if action.required else f"[{spelled}]")
            option_rows.append((spelled, action.help or ""))
    # Arguments first, then options, the same order as syn --help.
    command.rows += option_rows
    command.usage = " ".join([path, *arguments, *options]) if path else ""
    return command


def command_list() -> Command:
    """Every app command, as a tree under a nameless root."""
    root = _read("", build_parser())
    for name, summary, usage, description in APP_ONLY:
        root.subcommands[name] = Command(
            name, path=f"/{name}", summary=summary, usage=usage, description=description
        )
    # Tab after /help completes the topics: every command.
    root.subcommands[HELP].subcommands = root.subcommands
    return root


def _topics(node: Command) -> dict[str, Command]:
    """The commands below ``node`` that have their own help."""
    # /help's subcommands are only there for Tab; they aren't help topics.
    return {} if node.path == f"/{HELP}" else node.subcommands


def help_page(topic: list[str], root: Command) -> HelpPage:
    """The help for ``/help <topic>``, ignoring capitals and a leading slash."""
    node = root
    for word in topic:
        child = _topics(node).get(word.lower().removeprefix("/"))
        if child is None:
            asked = NO_HELP.format(asked=" ".join(topic).removeprefix("/"))
            if _topics(node):
                return HelpPage(error=f"{asked} Topics: {', '.join(_topics(node))}.")
            return HelpPage(error=f"{asked} Try /help {node.path[1:]}.")
        node = child
    rows = tuple((c.path, c.summary) for c in _topics(node).values())
    if node is root:
        return HelpPage(rows=rows, hint=ROOT_HINT)
    if rows:
        first = rows[0][0][1:]
        hint = SUBCOMMANDS_HINT.format(name=node.path[1:], first=first)
        return HelpPage((node.description,), rows, hint)
    paragraphs = tuple(p for p in (node.usage, node.description) if p)
    return HelpPage(paragraphs, tuple(node.rows))


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
