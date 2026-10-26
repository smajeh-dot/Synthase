"""The one command table, and reading a typed line against it.

The table drives `help`, `help <command>`, the `Usage:` lines, the shape check
and Tab completion, so they cannot drift apart (spec C183). The commands and
their wording are the owner's, from
docs/decisions/0023-command-set-and-project-folder.md: change them only there
first. Nothing here prints anything; the app (#100) shows what comes back.
"""

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from itertools import groupby

from synthase.suggest import suggestion
from synthase.values import unit_words

# The words that introduce an uncertainty in a value line (spec C168).
PLUS_MINUS = ("+/-", "±")


@dataclass(frozen=True)
class Arg:
    """One part typed after the command words.

    ``name`` is the key in ``Call.args`` and says what the part is, for Tab
    completion. ``read`` is how it is read: one ``word``, the ``rest`` of the
    line, a ``unit`` (two words when they are a listed unit such as
    ``mol dm^-3``, else one), an ``uncertainty`` after ``+/-``, or the ``note``
    after ``#``.
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
    bare: bool = False
    """May be typed with no parts at all; the app then asks for them."""

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
    Arg("unit", "<unit>", "unit"),
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
        bare=True,
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
        elif arg.read == "unit":
            size = unit_words(words)
            args[arg.name] = " ".join(words[:size]) or None
            words = words[size:]
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
    if command.bare and not rest.strip():
        return Call(command, {})
    args = _read_args(command, rest)
    if args is None:
        raise CommandError(_usage(_forms(*command.words[:2])))
    return Call(command, args)


def read_value_line(text: str) -> dict[str, str | None] | None:
    """A typed `name value unit [+/- unc] [# note]` line, read as `value add` reads
    it; None if its shape is wrong. Manual entry reads each line this way."""
    command = next(c for c in COMMANDS if c.words == ("value", "add"))
    return _read_args(command, text)


def _help(topic: str | None) -> str:
    if topic is None:
        column = 2 + max(len(c.usage) for c in COMMANDS) + 2
        lines: list[str] = []
        for group, commands in groupby(COMMANDS, key=lambda c: c.group):
            lines.append(group)
            lines += [f"  {c.usage}".ljust(column) + c.help for c in commands]
        return "\n".join(lines)
    return "\n\n".join(
        f"Usage: {c.usage}\n{c.help}\nExample: {c.example}" for c in help_forms(topic)
    )


def help_forms(topic: str) -> list[Command]:
    """Every form `help <topic>` lists; CommandError if it isn't a first word."""
    if topic not in COMMAND_WORDS:
        raise _unknown(topic, COMMAND_WORDS)
    return _forms(topic)


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


# What Tab can offer for a part typed after the command words, by Arg.name: a
# function given the words before it. Later issues add IDs, value names and
# fields (#104 onwards).
Source = Callable[[tuple[str, ...]], Iterable[str]]


@dataclass(frozen=True)
class Completion:
    """One word Tab can offer: the word, what it is, and whether more can follow.

    ``about`` is a whole command's help line, a first word's help heading, or
    empty for a part such as an ID.
    """

    word: str
    about: str = ""
    more: bool = False


def _word_args(words: tuple[str, ...]) -> list[tuple[Arg, bool]]:
    """The parts that could be typed next, after ``words``, and if more can follow.

    Only parts read as one word count; a value line's ``+/-`` and ``#`` don't.
    """
    found = []
    for command in COMMANDS:
        size = len(command.words)
        if words[:size] != command.words:
            continue
        args = [a for a in command.args if a.read == "word"]
        position = len(words) - size
        if position < len(args):
            more = position < len(command.args) - 1
            found.append((args[position], more))
    return found


def completions(
    line: str, sources: Mapping[str, Source] | None = None
) -> list[Completion]:
    """What could finish the word being typed at the end of ``line``.

    Command words come from the table; IDs and names come from ``sources``,
    which the commands that store them fill in.
    """
    words = line.split()
    if line and not line[-1].isspace():
        typed = words.pop()
    else:
        typed = ""
    found: dict[str, Completion] = {}
    if words in ([], ["help"]):
        for word in COMMAND_WORDS:
            forms = _forms(word)
            whole = [c for c in forms if c.words == (word,)]
            about = whole[0].help if whole else forms[0].group
            more = not words and (len(forms) > 1 or bool(forms[0].args))
            found[word] = Completion(word, about, more)
    else:
        before = tuple(words)
        n = len(before)
        for command in _forms(*before):
            if len(command.words) <= n:
                continue
            full = command.words[: n + 1]
            forms = _forms(*full)
            whole = [c for c in forms if c.words == full]
            about = whole[0].help if whole else ""
            more = len(forms) > 1 or any(c.args for c in whole)
            found.setdefault(full[n], Completion(full[n], about, more))
        for arg, more in _word_args(before):
            source = (sources or {}).get(arg.name)
            for word in source(before) if source else ():
                found.setdefault(word, Completion(word, "", more))
    return [found[w] for w in sorted(found) if w.startswith(typed)]


def complete(line: str, sources: Mapping[str, Source] | None = None) -> list[str]:
    """The words that could finish the word being typed at the end of ``line``."""
    return [c.word for c in completions(line, sources)]
