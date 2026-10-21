"""The one command table, and reading a typed line against it.

The table drives `help`, `help <command>`, the `Usage:` lines, the shape check
and Tab completion, so they cannot drift apart (spec C183). The commands and
their wording are the owner's, from
docs/decisions/0023-command-set-and-project-folder.md: change them only there
first. Nothing here prints anything; the app (#100) shows what comes back.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from itertools import groupby

from synthase.suggest import suggestion

# The words that introduce an uncertainty in a value line (spec C168).
PLUS_MINUS = ("+/-", "±")


@dataclass(frozen=True)
class Arg:
    """One part typed after the command words.

    ``name`` is the key in ``Call.args`` and says what the part is, for Tab
    completion. ``read`` is how it is read: one ``word``, the ``rest`` of the
    line, an ``uncertainty`` after ``+/-``, or the ``note`` after ``#``.
    """

    name: str
    placeholder: str
    read: str = "word"

    @property
    def optional(self) -> bool:
        return self.placeholder.startswith("[")


@dataclass(frozen=True)
class Command:
    words: tuple[str, ...]
    group: str
    help: str
    example: str
    args: tuple[Arg, ...] = ()

    @property
    def usage(self) -> str:
        return " ".join([*self.words, *(a.placeholder for a in self.args)])


@dataclass
class Call:
    """A line read as one command, with each part exactly as typed."""

    command: Command
    args: dict[str, str | None] = field(default_factory=dict)


class CommandError(Exception):
    """A line that isn't a command: the message to show instead."""


ID = Arg("id", "<ID>")
VALUE_NAME = Arg("name", "<name>")
VALUE_LINE = (
    VALUE_NAME,
    Arg("value", "<value>"),
    Arg("unit", "<unit>"),
    Arg("uncertainty", "[+/- unc]", "uncertainty"),
    Arg("note", "[# note]", "note"),
)

COMMANDS = (
    Command(
        ("project", "create"),
        "Project",
        "Set up a Synthase project in this folder.",
        "project create",
    ),
    Command(
        ("project", "show"),
        "Project",
        "Show this project's name, folder and contents.",
        "project show",
    ),
    Command(("project", "edit"), "Project", "Rename this project.", "project edit"),
    Command(
        ("exp", "create"),
        "Experiments",
        "Create an experiment and open it.",
        "exp create",
    ),
    Command(
        ("exp", "open"),
        "Experiments",
        "Open an experiment.",
        "exp open E002",
        (Arg("id_or_title", "<ID or title>", "rest"),),
    ),
    Command(
        ("exp", "show"),
        "Experiments",
        "Show the open experiment, another one, or one value from it.",
        "exp show E002 m_crude",
        (Arg("id", "[ID]"), Arg("value_name", "[value name]")),
    ),
    Command(
        ("exp", "show", "all"),
        "Experiments",
        "List every experiment.",
        "exp show all",
    ),
    Command(
        ("exp", "edit"),
        "Experiments",
        "Change the open experiment's title or x unit.",
        "exp edit",
    ),
    Command(
        ("exp", "export"),
        "Experiments",
        "Write the open experiment to the exports folder.",
        "exp export csv",
        (Arg("format", "<csv or json>"),),
    ),
    Command(
        ("value", "add"),
        "Values",
        "Store a new value in the open experiment.",
        "value add m_crude 2.211 g +/- 0.001 # Balance B2",
        VALUE_LINE,
    ),
    Command(
        ("value", "edit"),
        "Values",
        "Replace a value; anything not retyped is cleared.",
        "value edit m_crude 2.215 g",
        VALUE_LINE,
    ),
    Command(
        ("value", "delete"),
        "Values",
        "Delete a value (its history is kept).",
        "value delete m_crude",
        (VALUE_NAME,),
    ),
    Command(
        ("value", "show"),
        "Values",
        "Show one value with its uncertainty and note.",
        "value show m_crude",
        (VALUE_NAME,),
    ),
    Command(
        ("value", "history"),
        "Values",
        "Every version of a value, with times.",
        "value history m_crude",
        (VALUE_NAME,),
    ),
    Command(
        ("compound", "create"),
        "Compounds",
        "Add a compound to the library.",
        "compound create",
    ),
    Command(
        ("compound", "show"),
        "Compounds",
        "Show a compound, or one of its fields.",
        "compound show C001 molar_mass",
        (ID, Arg("field", "[field]")),
    ),
    Command(
        ("compound", "show", "all"),
        "Compounds",
        "List the library.",
        "compound show all",
    ),
    Command(
        ("compound", "edit"),
        "Compounds",
        "Change a compound's fields.",
        "compound edit C001",
        (ID,),
    ),
    Command(
        ("help",),
        "General",
        "List the commands, or every form of one.",
        "help exp",
        (Arg("command", "[command]"),),
    ),
    Command(("exit",), "General", "Leave Synthase (or press Ctrl+D).", "exit"),
)

# The first words, in the order Tab and "Commands:" list them.
COMMAND_WORDS = sorted({c.words[0] for c in COMMANDS})


def _forms(*words: str) -> list[Command]:
    """Every command whose words start with ``words``, in table order."""
    return [c for c in COMMANDS if c.words[: len(words)] == words]


def _usage(commands: list[Command]) -> str:
    return "\n".join(f"Usage: {c.usage}" for c in commands)


def _unknown(typed: str, candidates: list[str]) -> CommandError:
    return CommandError(
        f"Unknown command '{typed}'. " + suggestion(typed, candidates, "Commands")
    )


def _strip_quotes(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] == '"':
        return text[1:-1].strip()
    return text


def _read_args(command: Command, rest: str) -> dict[str, str | None] | None:
    """The parts after the command words, or None if the shape is wrong."""
    args: dict[str, str | None] = {}
    if any(a.read == "note" for a in command.args):
        rest, hash_sign, note = rest.partition("#")
        args["note"] = note.strip() if hash_sign else None
    words = rest.split()
    for arg in command.args:
        if arg.read == "note":
            continue
        if arg.read == "rest":
            text = _strip_quotes(rest.strip())
            args[arg.name] = text or None
            words = []
        elif arg.read == "uncertainty":
            args[arg.name] = None
            if words and words[0] in PLUS_MINUS:
                if len(words) < 2:
                    return None
                args[arg.name] = words[1]
                words = words[2:]
        else:
            args[arg.name] = words.pop(0) if words else None
        if args[arg.name] is None and not arg.optional:
            return None
    if words:
        return None
    return {a.name: args[a.name] for a in command.args}


def parse(line: str) -> Call | None:
    """Read a typed line as one command; None for a blank line.

    Raises CommandError with the message to show when the line isn't a command.
    Names match exactly, including case, and a near miss is never run (D27).
    """
    words = line.split()
    if not words:
        return None
    first = words[0]
    if first not in COMMAND_WORDS:
        raise _unknown(first, COMMAND_WORDS)
    # The longest run of command words that matches what was typed.
    matches = [c for c in _forms(first) if tuple(words[: len(c.words)]) == c.words]
    if not matches:
        if len(words) == 1:
            raise CommandError(_usage(_forms(first)))
        typed = f"{first} {words[1]}"
        seconds = sorted({" ".join(c.words[:2]) for c in _forms(first)})
        raise _unknown(typed, seconds)
    command = max(matches, key=lambda c: len(c.words))
    # Everything after the command words, as typed.
    rest = re.sub(r"^\s*" + r"\s+".join(map(re.escape, command.words)), "", line)
    args = _read_args(command, rest)
    if args is None:
        raise CommandError(_usage(_forms(*command.words[:2])))
    return Call(command, args)


def _help(topic: str | None) -> str:
    if topic is None:
        column = 2 + max(len(c.usage) for c in COMMANDS) + 2
        lines: list[str] = []
        for group, commands in groupby(COMMANDS, key=lambda c: c.group):
            lines.append(group)
            lines += [f"  {c.usage}".ljust(column) + c.help for c in commands]
        return "\n".join(lines)
    if topic not in COMMAND_WORDS:
        raise _unknown(topic, COMMAND_WORDS)
    return "\n\n".join(
        f"Usage: {c.usage}\n{c.help}\nExample: {c.example}" for c in _forms(topic)
    )


Handler = Callable[[Call], str]


def dispatch(line: str, handlers: Mapping[tuple[str, ...], Handler]) -> str:
    """Run a typed line and return what to show.

    ``handlers`` maps a command's words to the function that does its work;
    `help` is answered here from the table.
    """
    try:
        call = parse(line)
        if call is None:
            return ""
        if call.command.words == ("help",):
            return _help(call.args["command"])
        return handlers[call.command.words](call)
    except CommandError as error:
        return str(error)


def complete(line: str) -> list[str]:
    """Command words that could finish the word being typed at the end of ``line``.

    Only command words come from the table; IDs and names come with the
    commands that store them.
    """
    words = line.split()
    if line and not line[-1].isspace():
        typed = words.pop()
    else:
        typed = ""
    if words in ([], ["help"]):
        options = COMMAND_WORDS
    else:
        n = len(words)
        options = sorted({c.words[n] for c in _forms(*words) if len(c.words) > n})
    return [o for o in options if o.startswith(typed)]
