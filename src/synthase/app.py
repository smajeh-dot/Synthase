"""The full-screen app: type ``synthase`` in PowerShell to open it.

The layout, wording and keys are in docs/decisions/0027-app-shell.md. All
styling is in synthase.tcss and theme.py; nothing here names a colour.
"""

import sys
from collections.abc import Callable
from dataclasses import dataclass
from itertools import groupby

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, HorizontalGroup, Vertical, VerticalScroll
from textual.content import Content
from textual.suggester import Suggester
from textual.widget import Widget
from textual.widgets import Input, Label, Static

from synthase import (
    __version__,
    command_history,
    error_log,
    experiment_values,
    experiments,
    history,
    lock,
    logo,
    older_console,
    project,
    walkthrough,
)
from synthase.command_history import CommandHistory
from synthase.commands import (
    COMMANDS,
    Call,
    Command,
    CommandError,
    Completion,
    Source,
    completions,
    help_forms,
    parse,
)
from synthase.experiment_values import ValuesError
from synthase.experiments import ExperimentError
from synthase.startup import ELLIPSIS, Startup, open_folder, status_line
from synthase.storage import FolderState, StorageError, folder_state, project_folder
from synthase.theme import SYNTHASE, SYNTHASE_16
from synthase.values import Entry, EntryError, read_entry
from synthase.walkthrough import Answer, Question, Step, Walk, Walkthrough

WELCOME = "type 'help' for commands"
PLACEHOLDER = "Type a command, e.g. help"
FIRST_HINT = " Tab completes · ↑ ↓ history · Ctrl+D exits "
TAB_HINT = " Tab completes "
MATCHES_HINT = " Tab next · Enter chooses · keep typing to narrow "
HISTORY_HINT = " history {step} of {count} · ↑ older · ↓ newer "
MATCH_COUNT = " {count} matches "
ONE_MATCH = " 1 match "
MATCH_PLACE = " {place} of {count} "
# The pop-up shows this many matches at a time.
MATCH_ROWS = 8
SCROLLED = " scrolled up · {count} newer {lines} below · PgDn to go back down "
ANSWERING = "Answering {command}"
ANSWER_HINT = " · Enter means no · Ctrl+C cancels "
ANSWER_PLACEHOLDER = "y or n"
# A walk-through question's hint, by what Enter on its own does (decision 0030).
SKIP_HINT = " · Enter skips · Ctrl+C cancels "
NEEDED_HINT = " · Ctrl+C cancels "
KEEP_HINT = " · Enter keeps · - clears · Ctrl+C cancels "
LINES_HINT = " · one per line · empty line ends · Ctrl+C cancels "
HELP_HINT = "For every form of one command, type help <command>, e.g. help exp."
NOT_BUILT = "{command} isn't built yet."
# The output keeps only the latest messages, so a long session stays quick.
MAX_MESSAGES = 1000
# The symbol each kind of message starts with. Colour and weight are in the TCSS.
GLYPHS = {
    "echo": ">",
    "normal": "",
    "success": "●",
    "error": "●",
    "notice": "i",
    "hint": "›",
    "cancel": "‹",
}
USAGES = {c.usage: c for c in COMMANDS}

# The value commands that take the name of a value already stored.
VALUE_NAME_COMMANDS = {
    ("value", "edit"),
    ("value", "delete"),
    ("value", "show"),
    ("value", "history"),
}

Handler = Callable[[Call], None]


class Message(HorizontalGroup):
    """One message in the output: a symbol column, then the text."""

    def __init__(self, kind: str, text: str | Content) -> None:
        reply = "" if kind == "echo" else " -reply"
        super().__init__(classes=f"msg -{kind}{reply}")
        self.kind = kind
        self.body = text if isinstance(text, Content) else Content(text)
        self.text = self.body.plain

    def compose(self) -> ComposeResult:
        if GLYPHS[self.kind]:
            yield Label(GLYPHS[self.kind], classes="glyph", markup=False)
        yield Static(self.app.drawn(self.body), classes="body")


class Welcome(HorizontalGroup):
    """The first line: ``Synthase 0.2.0  ·  type 'help' for commands``.

    With the start-up logo, the ring comes first and the two parts stack to its
    right, from its top row (decision 0035).
    """

    def __init__(self, logo: Content | None = None) -> None:
        super().__init__(classes="msg -welcome" + (" -logo" if logo else ""))
        self.text = f"Synthase {__version__}  ·  {WELCOME}"
        self.logo = logo

    def compose(self) -> ComposeResult:
        lead = Label(f"Synthase {__version__}", classes="lead", markup=False)
        body = Static(WELCOME, classes="body", markup=False)
        if self.logo is None:
            yield lead
            yield Label("  ·  ", classes="sep", markup=False)
            yield body
            return
        yield Static(self.logo, id="logo")
        with Vertical(classes="info"):
            yield lead
            yield body


class Heading(Widget):
    """A heading, then a rule to the right edge of its block."""

    DEFAULT_CSS = "Heading { height: 1; }"

    def __init__(self, text: str, context: str | None = None) -> None:
        super().__init__(classes="heading")
        self.text = text
        self.context = context

    def render(self) -> Content:
        title = Content.styled(self.text, "bold $heading")
        if self.context:
            title += Content.styled(" · ", "$faint") + Content.styled(
                self.context, "$muted"
            )
        rule = "─" * max(self.size.width - len(title) - 1, 0)
        return title + Content(" ") + Content.styled(rule, "$line")


def usage_content(command: Command) -> Content:
    """A usage line: command words accent, <required> plain, [optional] faint."""
    parts = [Content.styled(" ".join(command.words), "$accent")]
    for arg in command.args:
        style = "$faint" if arg.optional else "$foreground"
        parts.append(Content.styled(arg.placeholder, style))
    return Content(" ").join(parts)


def names_content(text: str) -> Content:
    """``Did you mean: a, b?`` or ``Commands: a, b``, each name in accent."""
    label, _, rest = text.partition(": ")
    end = rest[-1:] if rest[-1:] in ("?", ".") else ""
    names = rest.removesuffix(end).split(", ")
    parts = [Content.styled(f"{label}: ", "$muted")]
    for number, name in enumerate(names):
        if number:
            parts.append(Content.styled(", ", "$muted"))
        parts.append(Content.styled(name, "$accent"))
    if end:
        parts.append(Content.styled(end, "$muted"))
    return Content.assemble(*parts)


class HelpLine(HorizontalGroup):
    """One command in `help`: its usage in a column, then its help line."""

    def __init__(self, command: Command) -> None:
        super().__init__()
        self.command = command

    def compose(self) -> ComposeResult:
        yield Static(usage_content(self.command), classes="usage")
        yield Static(self.command.help, classes="text", markup=False)


class HelpList(Vertical):
    """`help`: the commands under their headings, then how to see every form."""

    def __init__(self) -> None:
        super().__init__(classes="msg -reply")
        lines = []
        for group, commands in groupby(COMMANDS, key=lambda c: c.group):
            lines += [group, *(f"  {c.usage}  {c.help}" for c in commands), ""]
        self.text = "\n".join([*lines, f"› {HELP_HINT}"])

    def compose(self) -> ComposeResult:
        for group, commands in groupby(COMMANDS, key=lambda c: c.group):
            with Vertical(classes="group"):
                yield Heading(group)
                for command in commands:
                    yield HelpLine(command)
        yield Message("hint", HELP_HINT)


class HelpForms(Vertical):
    """`help <command>`: each form's usage, help line and example."""

    def __init__(self, commands: list[Command]) -> None:
        super().__init__(classes="msg -reply")
        self.commands = commands
        self.text = "\n\n".join(
            f"Usage:   {c.usage}\n         {c.help}\nExample: {c.example}"
            for c in commands
        )

    def compose(self) -> ComposeResult:
        for command in self.commands:
            with Grid(classes="form"):
                yield Label("Usage:", classes="key")
                yield Static(usage_content(command))
                yield Label("", classes="key")
                yield Static(command.help, markup=False)
                yield Label("Example:", classes="key")
                yield Static(command.example, classes="example", markup=False)


class ErrorLog(Vertical):
    """The latest error log entry, exactly as written, under its heading."""

    def __init__(self, entry: str, file: str | None) -> None:
        super().__init__(classes="msg -reply -log")
        self.entry = entry
        self.file = file
        self.text = entry

    def compose(self) -> ComposeResult:
        yield Heading(error_log.HEADING, self.file)
        yield Static(self.app.drawn(self.entry), classes="log", markup=False)


class Matches(Static):
    """The pop-up above the bar: the words Tab can offer, ▸ on the current one."""

    def show(self, options: list[Completion], current: int) -> None:
        count = len(options)
        self.border_title = ONE_MATCH if count == 1 else MATCH_COUNT.format(count=count)
        self.border_subtitle = MATCH_PLACE.format(place=current + 1, count=count)
        first = max(current - MATCH_ROWS + 1, 0)
        width = max(len(o.word) for o in options)
        rows = []
        for number, option in enumerate(options[first : first + MATCH_ROWS], first):
            here = number == current
            word = option.word.ljust(width)
            row = Content.assemble(
                ("▸ " if here else "  ", "$accent"),
                (word, "bold $accent" if here else "$accent"),
                (f"   {option.about}" if option.about else "", "$muted"),
            )
            # With 16 colours, bold alone may not show which row is current.
            if here and self.app.sixteen:
                row = row.stylize("reverse")
            rows.append(row)
        self.update(Content("\n").join(rows))
        self.add_class("-open")


class Ghost(Suggester):
    """The faint rest of the word when Tab has exactly one to offer."""

    def __init__(self, app: "SynthaseApp") -> None:
        super().__init__(use_cache=False, case_sensitive=True)
        self.owner = app

    async def get_suggestion(self, value: str) -> str | None:
        return self.owner.ghost(value)


@dataclass
class Failure:
    """An unexpected error waiting for the answer to `Failed. …? [y/n]`."""

    entry: str
    file: str | None


class SynthaseApp(App):
    CSS_PATH = "synthase.tcss"
    TITLE = "Synthase"
    ENABLE_COMMAND_PALETTE = False
    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (100, "-wide")]
    # The input keeps the focus, so these are app keys, before the input's own.
    BINDINGS = [
        Binding("pageup", "scroll_output(-1)", show=False),
        Binding("pagedown", "scroll_output(1)", show=False),
        Binding("ctrl+c", "clear_line", show=False, priority=True),
        Binding("ctrl+d", "leave", show=False, priority=True),
        Binding("tab", "complete(1)", show=False, priority=True),
        Binding("shift+tab", "complete(-1)", show=False, priority=True),
        Binding("up", "step(-1)", show=False),
        Binding("down", "step(1)", show=False),
        Binding("escape", "close_matches", show=False),
    ]

    def __init__(self, watch_css: bool = False) -> None:
        super().__init__(watch_css=watch_css)
        # The older console, decided once (decision 0029).
        self.ascii = older_console.needs_ascii(older_console.output_encoding())
        self.ascii_filter = older_console.Ascii()
        self.sixteen = older_console.has_16_colours(self.console.color_system)
        theme = SYNTHASE_16 if self.sixteen else SYNTHASE
        # Before the stylesheet is read, so its $tokens resolve.
        self.register_theme(theme)
        self.theme = theme.name
        self.startup = Startup(project_folder(), FolderState.NO_PROJECT)
        # What each data command does; later issues add theirs (#104 onwards).
        self.handlers: dict[tuple[str, ...], Handler] = {
            ("project", "create"): self.project_create,
            ("project", "show"): self.project_show,
            ("project", "edit"): self.project_edit,
            ("exp", "create"): self.exp_create,
            ("exp", "open"): self.exp_open,
            ("value", "add"): self.value_add,
            ("value", "edit"): self.value_edit,
            ("value", "delete"): self.value_delete,
            ("value", "show"): self.value_show,
            ("value", "history"): self.value_history,
        }
        # What Tab offers for IDs and names, by Arg.name (#105 onwards).
        self.sources: dict[str, Source] = {
            "id": self.experiment_ids,
            "name": self.value_names,
            "value_name": self.value_names,
        }
        # The ID of the open experiment, shown after the project's name.
        self.experiment: str | None = None
        self.failure: Failure | None = None
        self.walk: Walk | None = None
        self.first_hint = True
        self.history = CommandHistory()
        # The line ↑ or ↓ last put in the bar, until it is typed over.
        self.recalled: str | None = None
        # The pop-up's words and the current one, while it is open.
        self.matches: list[Completion] = []
        self.current = 0

    def compose(self) -> ComposeResult:
        # The logo is drawn once at start-up, never redrawn (decision 0035).
        height = self.size.height
        ring = None
        if height >= logo.MIN_ROWS and not (self.ascii or self.sixteen):
            ring = logo.content(logo.ring(height))
        yield VerticalScroll(Welcome(ring), id="output")
        with Vertical(id="bottom"):
            yield Matches(id="matches")
            with Vertical(id="bar"):
                with HorizontalGroup(id="line"):
                    yield Label("> ", id="prompt", markup=False)
                    yield Input(
                        placeholder=PLACEHOLDER,
                        id="command",
                        compact=True,
                        suggester=Ghost(self),
                    )
            yield Static(id="status")

    def on_mount(self) -> None:
        output = self.query_one("#output", VerticalScroll)
        self.watch(output, "scroll_y", self.draw_title, init=False)
        self.watch(output, "max_scroll_y", self.draw_title, init=False)
        self.query_one("#command").focus()
        try:
            self.startup = open_folder()
            if self.startup.locked:
                self.history = CommandHistory(command_history.load(), saved=True)
        except Exception as error:
            self.startup = Startup(project_folder(), folder_state())
            self.draw_status()
            self.failed("synthase", "synthase", error)
            return
        self.draw_status()
        self.draw_title()
        for notice in self.startup.notices:
            self.say("notice", notice)
        if self.startup.refusal is not None:
            self.say(*self.startup.refusal)
        elif self.startup.locked:
            self.reopen_last()

    def on_unmount(self) -> None:
        if self.startup.locked:
            lock.release()

    def get_line_filters(self):
        """Textual's own filters, then ASCII for each symbol on the older console."""
        filters = list(super().get_line_filters())
        return [*filters, self.ascii_filter] if self.ascii else filters

    def drawn(self, text: str | Content) -> str | Content:
        """Text as this console draws it: on the older console, each symbol longer
        than its ASCII form is spelt out before the text is laid out."""
        if not self.ascii:
            return text
        if isinstance(text, Content):
            return older_console.content(text)
        return older_console.words(text)

    def draw_status(self) -> None:
        status = self.query_one("#status", Static)
        width = max(self.size.width - 2, 20)
        line = status_line(
            self.startup, width, self.experiment, ellipsis=self.drawn(ELLIPSIS)
        )
        status.update(self.drawn(line))

    def on_resize(self) -> None:
        self.draw_status()

    def draw_title(self) -> None:
        """The top rule's title: the question, the pop-up's keys, the history step,
        Tab for one match, scrolled up, the first hint, or none."""
        bar = self.query_one("#bar")
        if self.asking:
            return
        output = self.query_one("#output", VerticalScroll)
        below = round(output.max_scroll_y - output.scroll_y)
        step = self.history.step
        if self.matches:
            title = MATCHES_HINT
        elif step is not None:
            count = len(self.history.lines)
            title = HISTORY_HINT.format(step=step, count=count)
        elif self.ghost(self.query_one("#command", Input).value):
            title = TAB_HINT
        elif below > 0:
            lines = "line" if below == 1 else "lines"
            title = SCROLLED.format(count=below, lines=lines)
        else:
            title = FIRST_HINT if self.first_hint else ""
        bar.border_title = self.drawn(title)

    def say(self, kind: str, text: str | Content) -> None:
        self.show(Message(kind, text))

    def show(self, message: Widget) -> None:
        """Add a message, following it down unless the user has scrolled up."""
        output = self.query_one("#output", VerticalScroll)
        following = output.scroll_y >= output.max_scroll_y
        output.mount(message)
        extra = len(output.children) - MAX_MESSAGES
        if extra > 0:
            output.remove_children(output.children[:extra])
        if following:
            output.call_after_refresh(output.scroll_end, animate=False)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Typing over a recalled line ends the stepping; typing narrows the pop-up."""
        # The bar's value now, not the event's: ↑ pressed twice sends two events.
        value = event.input.value
        if self.recalled is not None and value != self.recalled:
            self.recalled = None
            self.history.stop()
        if self.matches:
            self.matches = completions(value, self.sources)
            self.current = 0
            self.draw_matches()
        self.draw_title()

    @property
    def asking(self) -> bool:
        """Whether the bar is in answer mode: the error question or a walk-through."""
        return self.failure is not None or self.walk is not None

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.failure is not None:
            event.input.clear()
            self.answer_failure(event.value)
            return
        if self.walk is not None:
            event.input.clear()
            self.answer_walk(event.value)
            return
        if self.matches:
            self.fill(self.matches[self.current])
            return
        text = event.value.strip()
        event.input.clear()
        if not text:
            return
        self.first_hint = False
        self.draw_title()
        self.say("echo", text)
        try:
            self.history.add(text)
            self.run_line(text)
        except Exception as error:
            words = text.split()
            self.failed(text, " ".join(words[:2]), error)

    def run_line(self, text: str) -> None:
        try:
            call = parse(text)
        except CommandError as error:
            self.show_error(str(error))
            return
        words = call.command.words
        if words == ("exit",):
            self.exit()
        elif words == ("help",):
            self.show_help(call.args["command"])
        elif self.startup.refusal is not None and not self.makes_project(words):
            self.say(*self.startup.refusal)
        elif words in self.handlers:
            try:
                self.handlers[words](call)
            except Exception as error:
                self.failed(text, " ".join(words), error)
        else:
            self.say("error", NOT_BUILT.format(command=" ".join(words)))

    def makes_project(self, words: tuple[str, ...]) -> bool:
        """`project create` is the one data command a folder with no project runs."""
        return words == ("project", "create") and (
            self.startup.state is FolderState.NO_PROJECT
        )

    def project_create(self, call: Call) -> None:
        if self.startup.state is FolderState.PROJECT:
            self.say("error", project.ALREADY.format(name=project.name()))
            return
        name = Question("name", "Name")
        self.ask(Walkthrough("project create", [name], self.create_project))

    def create_project(self, answers: dict[str, Answer]) -> None:
        """Create the project, then open it as start-up would (decision 0031)."""
        name = answers["name"]
        try:
            project.create(name)
        except StorageError as error:
            self.say("error", str(error))
            return
        self.startup = open_folder()
        if self.startup.locked:
            self.history.keep()
        self.draw_status()
        folder = self.startup.folder
        self.say("success", project.CREATED.format(name=name, folder=folder))
        if self.startup.refusal is not None:
            self.say(*self.startup.refusal)

    def project_show(self, call: Call) -> None:
        """Labels muted, values bright, in one label column."""
        lines = [
            Content.styled(label.ljust(project.LABEL_WIDTH), "$muted")
            + Content.styled(value, "$echo")
            for label, value in project.details()
        ]
        self.say("normal", Content("\n").join(lines))

    def project_edit(self, call: Call) -> None:
        name = Question("name", "Name", current=project.name() or None)
        walk = Walkthrough("project edit", [name], self.rename_project, edit=True)
        self.ask(walk)

    def rename_project(self, answers: dict[str, Answer]) -> None:
        new = answers["name"]
        old = project.name()
        if new is None or new == old:
            self.say("hint", project.KEPT)
            return
        try:
            project.rename(new)
        except StorageError as error:
            self.say("error", str(error))
            return
        self.startup.name = new
        self.draw_status()
        self.say("success", project.RENAMED.format(old=old, new=new))

    def experiment_ids(self, words: tuple[str, ...]) -> list[str]:
        """What Tab offers for an ID: the experiments, after `exp`."""
        if words[:1] != ("exp",):
            return []
        try:
            return experiments.ids()
        except StorageError:
            return []

    def value_names(self, words: tuple[str, ...]) -> list[str]:
        """What Tab offers for a value name: the open experiment's, after the
        commands that take an existing one, and after `exp show`'s ID (0036)."""
        experiment = self.experiment
        try:
            if words[:2] == ("exp", "show"):
                if len(words) > 2 and words[2] in experiments.ids():
                    experiment = words[2]
            elif words[:2] not in VALUE_NAME_COMMANDS:
                return []
            if experiment is None:
                return []
            return experiment_values.names(experiment)
        except StorageError:
            return []

    def open_values(self) -> str | None:
        """The open experiment, or None after saying that none is open."""
        if self.experiment is None:
            self.say("error", experiment_values.NO_EXPERIMENT)
        return self.experiment

    def refuse_value(self, error: ValuesError) -> None:
        """What is wrong, then each suggestion on a › line."""
        first, *rest = error.lines
        self.say("error", first)
        for line in rest:
            names = line.startswith(("Did you mean: ", "Values: "))
            self.say("hint", names_content(line) if names else line)

    def value_add(self, call: Call) -> None:
        experiment = self.open_values()
        if experiment is None:
            return
        if not call.args:
            self.ask_values(experiment)
            return
        try:
            entry = read_entry(call.args)
            experiment_values.add(experiment, [entry])
        except EntryError as error:
            self.show_error(str(error))
            return
        except ValuesError as error:
            self.refuse_value(error)
            return
        except StorageError as error:
            self.say("error", str(error))
            return
        self.say_added(entry)

    def say_added(self, entry: Entry) -> None:
        shown = experiment_values.text(entry, note=False)
        self.say(
            "success", experiment_values.ADDED.format(name=entry.name, entry=shown)
        )

    def ask_values(self, experiment: str) -> None:
        """`value add` on its own: one entry per line until an empty line."""
        try:
            names = set(experiment_values.names(experiment))
        except StorageError as error:
            self.say("error", str(error))
            return

        def check_line(text: str) -> str | None:
            try:
                entry = experiments.read_line(text)
            except EntryError as error:
                return str(error)
            if entry.name in names:
                return " ".join(
                    (
                        experiment_values.exists_message(entry.name, experiment),
                        experiment_values.USE_EDIT,
                    )
                )
            names.add(entry.name)
            return None

        def finish(answers: dict[str, Answer]) -> None:
            entries = [experiments.read_line(line) for line in answers["values"] or []]
            try:
                experiment_values.add(experiment, entries)
            except ValuesError as error:
                self.refuse_value(error)
                return
            except StorageError as error:
                self.say("error", str(error))
                return
            for entry in entries:
                self.say_added(entry)

        questions = [
            Question(
                "values",
                "Values",
                lines=True,
                check=check_line,
                intro=experiments.FORMAT,
            )
        ]
        self.ask(Walkthrough("value add", questions, finish))

    def value_edit(self, call: Call) -> None:
        experiment = self.open_values()
        if experiment is None:
            return
        try:
            entry = read_entry(call.args)
            old = experiment_values.edit(experiment, entry)
        except EntryError as error:
            self.show_error(str(error))
            return
        except ValuesError as error:
            self.refuse_value(error)
            return
        except StorageError as error:
            self.say("error", str(error))
            return
        text = experiment_values.UPDATED.format(
            name=entry.name,
            old=experiment_values.brief(old),
            new=experiment_values.brief(entry),
            removed=experiment_values.removed(old, entry),
        )
        self.say("success", text)

    def value_delete(self, call: Call) -> None:
        experiment = self.open_values()
        if experiment is None:
            return
        name = call.args["name"]
        try:
            experiment_values.delete(experiment, name)
        except ValuesError as error:
            self.refuse_value(error)
            return
        except StorageError as error:
            self.say("error", str(error))
            return
        self.say("success", experiment_values.DELETED.format(name=name))

    def value_show(self, call: Call) -> None:
        experiment = self.open_values()
        if experiment is None:
            return
        name = call.args["name"]
        try:
            entry = experiment_values.read(experiment, name)
        except ValuesError as error:
            self.refuse_value(error)
            return
        except StorageError as error:
            self.say("error", str(error))
            return
        lines = [Content(f"{name}  {experiment_values.text(entry, note=False)}")]
        if entry.note is not None:
            lines.append(Content(f"note: {entry.note}"))
        self.say("normal", Content("\n").join(lines))

    def value_history(self, call: Call) -> None:
        experiment = self.open_values()
        if experiment is None:
            return
        try:
            lines = experiment_values.versions(experiment, call.args["name"])
        except ValuesError as error:
            self.refuse_value(error)
            return
        except StorageError as error:
            self.say("error", str(error))
            return
        self.say("normal", Content("\n").join(Content(line) for line in lines))

    def reopen_last(self) -> None:
        """Open the experiment last opened in this folder, and say which (0033)."""
        try:
            last = experiments.last_opened()
            if last is None:
                return
            text = experiments.AUTO_OPENED.format(
                id=last, title=experiments.title(last)
            )
        except StorageError:
            return
        self.experiment = last
        self.draw_status()
        self.say("hint", text)

    def open_experiment(self, experiment_id: str) -> None:
        """Make an experiment the open one, now and at the next start."""
        self.experiment = experiment_id
        experiments.remember(experiment_id)
        self.draw_status()

    def exp_create(self, call: Call) -> None:
        names: set[str] = set()

        def check_line(text: str) -> str | None:
            try:
                entry = experiments.read_line(text)
            except EntryError as error:
                return str(error)
            if entry.name in names:
                return experiments.DUPLICATE.format(name=entry.name)
            names.add(entry.name)
            return None

        questions = [
            Question("title", "Title"),
            Question("source", experiments.SOURCE, check=experiments.check_source),
            Question(
                "values",
                "Values",
                optional=True,
                lines=True,
                check=check_line,
                intro=experiments.FORMAT,
            ),
        ]
        self.ask(Walkthrough("exp create", questions, self.create_experiment))

    def create_experiment(self, answers: dict[str, Answer]) -> None:
        entries = [experiments.read_line(line) for line in answers["values"] or []]
        try:
            new_id, created = experiments.create(answers["title"], entries)
        except StorageError as error:
            self.say("error", str(error))
            return
        self.open_experiment(new_id)
        text = experiments.CREATED.format(
            id=new_id,
            title=answers["title"],
            created=history.shown_time(created),
            count=experiments.counted(len(entries)),
        )
        self.say("success", text)

    def exp_open(self, call: Call) -> None:
        try:
            found = experiments.find(call.args["id_or_title"])
        except ExperimentError as error:
            self.show_error(str(error))
            return
        self.open_experiment(found)
        text = experiments.OPENED.format(id=found, title=experiments.title(found))
        self.say("success", text)

    def show_help(self, topic: str | None) -> None:
        if topic is None:
            self.show(HelpList())
            return
        try:
            self.show(HelpForms(help_forms(topic)))
        except CommandError as error:
            self.show_error(str(error))

    def show_error(self, text: str) -> None:
        """A command error: what is wrong, then the suggestions on a › line.

        Several `Usage:` lines hang under the first, with no glyph.
        """
        if text.startswith("Usage: "):
            lines = []
            for line in text.splitlines():
                usage = line.removeprefix("Usage: ")
                shown = usage_content(USAGES[usage]) if usage in USAGES else usage
                lines.append(Content.styled("Usage: ", "$error") + shown)
            self.say("error", Content("\n").join(lines))
            return
        what, sep, names = text.partition("'. ")
        if not sep:
            self.say("error", text)
            return
        self.say("error", what + "'.")
        self.say("hint", names_content(names))

    def failed(self, text: str, command: str, error: Exception) -> None:
        """Log an unexpected error and ask whether to show it (owner decision D4)."""
        entry = error_log.entry(text, error)
        has_project = self.startup.state is FolderState.PROJECT
        file = error_log.write(entry) if has_project else None
        self.failure = Failure(entry, file)
        self.start_answering(
            command, ANSWER_HINT, self.failure_question("$answer"), ANSWER_PLACEHOLDER
        )

    def start_answering(
        self, command: str, hint: str, prompt: Content, placeholder: str
    ) -> None:
        """Answer mode: heavy blue rules titled `Answering <command>`, the question
        as the prompt."""
        self.close_matches()
        bar = self.query_one("#bar")
        bar.add_class("-answering")
        # Textual draws one rule cell before the title; the design has two.
        bar.border_title = Content.assemble(
            ("━ ", "$answer"),
            (ANSWERING.format(command=command), "bold $answer"),
            (hint, "$muted"),
        )
        self.query_one("#prompt", Label).update(prompt)
        self.query_one("#command", Input).placeholder = placeholder

    def failure_question(self, style: str) -> Content:
        return Content.assemble(
            (error_log.FAILED, "$error"), (f" {error_log.QUESTION}", style)
        )

    def answer_failure(self, answer: str) -> None:
        failure = self.failure
        self.stop_asking()
        question = self.failure_question("$muted")
        self.say("error", question + Content.styled(answer, "$echo"))
        if error_log.is_yes(answer):
            self.show(ErrorLog(failure.entry, failure.file))
            if failure.file is not None:
                stays = Message("hint", error_log.STAYS.format(file=failure.file))
                stays.add_class("-spaced")
                self.show(stays)

    def ask(self, questions: Walkthrough) -> None:
        """Start a walk-through; nothing is saved until its last answer."""
        self.walk = Walk(questions)
        self.ask_next()

    def ask_next(self) -> None:
        walk = self.walk
        question = walk.question
        if walk.keeping:
            hint = KEEP_HINT
        elif question.lines:
            hint = LINES_HINT
        else:
            hint = SKIP_HINT if question.optional else NEEDED_HINT
        current = question.current if walk.keeping else None
        if isinstance(current, list):
            current = "; ".join(current)
        if question.intro and not walk.typed:
            self.say("normal", Content.styled(question.intro, "$muted"))
        prompt = Content.styled(f"{question.label}: ", "$answer")
        self.start_answering(walk.walkthrough.command, hint, prompt, current or "")

    def answer_walk(self, text: str) -> None:
        """Record an answer and ask the next question, or refuse it and ask again."""
        walk = self.walk
        label = walk.question.label
        try:
            step = walk.answer(text)
        except Exception as error:
            self.walk_failed(error)
            return
        if step.refused is not None:
            self.say("error", step.refused)
            return
        if step.shown is not None:
            self.record(label, step)
        if walk.question is not None:
            self.ask_next()
            return
        try:
            walk.walkthrough.finish(walk.answers)
        except Exception as error:
            self.walk_failed(error)
            return
        self.walk = None
        self.stop_asking()

    def walk_failed(self, error: Exception) -> None:
        """An unexpected error in a walk-through ends it and asks the error question."""
        command = self.walk.walkthrough.command
        self.walk = None
        self.stop_asking()
        self.failed(command, command, error)

    def record(self, label: str, step: Step) -> None:
        """An answer under its question: the question muted, the answer bright,
        a multi-line answer's further lines lined up under the first."""
        lead = f"{label}: "
        if not step.shown:
            self.say("normal", Content.styled(lead.rstrip(), "$muted"))
        for number, line in enumerate(step.shown):
            start = " " * len(lead) if step.more or number else lead
            self.say(
                "normal",
                Content.styled(start, "$muted") + Content.styled(line, "$echo"),
            )

    def cancel_walk(self) -> None:
        """Ctrl+C in a walk-through: it ends, and nothing is saved."""
        self.walk = None
        self.stop_asking()
        self.say("cancel", walkthrough.CANCELLED)

    def stop_asking(self) -> None:
        self.failure = None
        self.query_one("#bar").remove_class("-answering")
        self.query_one("#prompt", Label).update("> ")
        self.query_one("#command", Input).placeholder = PLACEHOLDER
        self.draw_title()

    def action_clear_line(self) -> None:
        """Ctrl+C clears the line and closes the pop-up; on the error question it
        also means no, and in a walk-through it cancels."""
        command = self.query_one("#command", Input)
        self.close_matches()
        command.clear()
        if self.failure is not None:
            self.answer_failure("")
        elif self.walk is not None:
            self.cancel_walk()

    def action_leave(self) -> None:
        if not self.asking:
            self.exit()

    def ghost(self, line: str) -> str | None:
        """The line with the rest of its last word, when Tab has only that to offer."""
        if self.matches or self.asking or not line or line[-1] == " ":
            return None
        options = completions(line, self.sources)
        typed = line.split()[-1]
        if len(options) != 1 or options[0].word == typed:
            return None
        return line + options[0].word.removeprefix(typed)

    def action_complete(self, direction: int) -> None:
        """Tab: one match fills the word, several open the pop-up, which Tab cycles."""
        if self.asking:
            return
        if self.matches:
            self.current = (self.current + direction) % len(self.matches)
            self.draw_matches()
            return
        options = completions(self.query_one("#command", Input).value, self.sources)
        if len(options) == 1:
            self.fill(options[0])
        elif options:
            self.matches = options
            self.current = 0 if direction > 0 else len(options) - 1
            self.draw_matches()
            self.draw_title()

    def fill(self, option: Completion) -> None:
        """Put a word in place of the one being typed; the line is not run."""
        self.close_matches()
        command = self.query_one("#command", Input)
        line = command.value
        if line and not line[-1].isspace():
            line = line[: len(line) - len(line.split()[-1])]
        command.value = line + option.word + (" " if option.more else "")
        command.cursor_position = len(command.value)

    def draw_matches(self) -> None:
        if self.matches:
            self.query_one("#matches", Matches).show(self.matches, self.current)
        else:
            self.close_matches()

    def close_matches(self) -> None:
        self.matches = []
        self.query_one("#matches", Matches).remove_class("-open")
        self.draw_title()

    def action_close_matches(self) -> None:
        self.close_matches()

    def action_step(self, direction: int) -> None:
        """↑ and ↓: move through the pop-up while it is open, else the history."""
        if self.asking:
            return
        if self.matches:
            self.action_complete(direction)
            return
        command = self.query_one("#command", Input)
        if direction < 0:
            line = self.history.older(command.value)
        else:
            line = self.history.newer()
        if line is None:
            return
        self.recalled = line
        command.value = line
        command.cursor_position = len(line)
        self.draw_title()

    def action_scroll_output(self, direction: int) -> None:
        output = self.query_one("#output", VerticalScroll)
        if direction < 0:
            output.scroll_page_up()
        else:
            output.scroll_page_down()


def main(argv: list[str] | None = None) -> int:
    """Open the app. ``synthase --dev`` reloads synthase.tcss whenever it is saved."""
    args = sys.argv[1:] if argv is None else argv
    SynthaseApp(watch_css="--dev" in args).run()
    return 0
