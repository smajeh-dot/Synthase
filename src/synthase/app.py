"""The full-screen app: type ``synthase`` in PowerShell to open it.

The layout, wording and keys are in docs/decisions/0026-app-shell.md. All
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
from textual.widget import Widget
from textual.widgets import Input, Label, Static

from synthase import __version__, error_log, lock
from synthase.commands import (
    COMMANDS,
    Call,
    Command,
    CommandError,
    help_forms,
    parse,
)
from synthase.startup import Startup, open_folder, status_line
from synthase.storage import FolderState, folder_state, project_folder
from synthase.theme import SYNTHASE

WELCOME = "type 'help' for commands"
PLACEHOLDER = "Type a command, e.g. help"
# Until #118 adds Tab and history, the first-open hint names only Ctrl+D.
FIRST_HINT = " Ctrl+D exits "
SCROLLED = " scrolled up · {count} newer {lines} below · PgDn to go back down "
ANSWERING = "Answering {command}"
ANSWER_HINT = " · Enter means no · Ctrl+C cancels "
ANSWER_PLACEHOLDER = "y or n"
HELP_HINT = "For every form of one command, type help <command>, e.g. help exp."
NOT_BUILT = "{command} isn't built yet."
# The output keeps only the latest messages, so a long session stays quick.
MAX_MESSAGES = 1000
# The symbol each kind of message starts with. Colour and weight are in the TCSS.
GLYPHS = {
    "echo": ">",
    "normal": "",
    "success": "✓",
    "error": "✗",
    "notice": "i",
    "hint": "›",
    "cancel": "‹",
}
USAGES = {c.usage: c for c in COMMANDS}

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
        yield Static(self.body, classes="body")


class Welcome(HorizontalGroup):
    """The first line: ``Synthase 0.2.0  ·  type 'help' for commands``."""

    def __init__(self) -> None:
        super().__init__(classes="msg -welcome")
        self.text = f"Synthase {__version__}  ·  {WELCOME}"

    def compose(self) -> ComposeResult:
        yield Label(f"Synthase {__version__}", classes="lead", markup=False)
        yield Label("  ·  ", classes="sep", markup=False)
        yield Static(WELCOME, classes="body", markup=False)


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
    question = rest.endswith("?")
    names = rest.removesuffix("?").split(", ")
    parts = [Content.styled(f"{label}: ", "$muted")]
    for number, name in enumerate(names):
        if number:
            parts.append(Content.styled(", ", "$muted"))
        parts.append(Content.styled(name, "$accent"))
    if question:
        parts.append(Content.styled("?", "$muted"))
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
        yield Static(self.entry, classes="log", markup=False)


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
        # Until #118, Tab does nothing rather than move the focus off the bar.
        Binding("tab,shift+tab", "nothing", show=False, priority=True),
    ]

    def __init__(self, watch_css: bool = False) -> None:
        super().__init__(watch_css=watch_css)
        # Before the stylesheet is read, so its $tokens resolve.
        self.register_theme(SYNTHASE)
        self.theme = SYNTHASE.name
        self.startup = Startup(project_folder(), FolderState.NO_PROJECT)
        # What each data command does; later issues add theirs (#101 onwards).
        self.handlers: dict[tuple[str, ...], Handler] = {}
        self.failure: Failure | None = None
        self.first_hint = True

    def compose(self) -> ComposeResult:
        yield VerticalScroll(Welcome(), id="output")
        with Vertical(id="bottom"):
            with Vertical(id="bar"):
                with HorizontalGroup(id="line"):
                    yield Label("> ", id="prompt", markup=False)
                    yield Input(placeholder=PLACEHOLDER, id="command", compact=True)
            yield Static(id="status")

    def on_mount(self) -> None:
        output = self.query_one("#output", VerticalScroll)
        self.watch(output, "scroll_y", self.draw_title, init=False)
        self.watch(output, "max_scroll_y", self.draw_title, init=False)
        self.query_one("#command").focus()
        try:
            self.startup = open_folder()
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

    def on_unmount(self) -> None:
        if self.startup.locked:
            lock.release()

    def draw_status(self) -> None:
        status = self.query_one("#status", Static)
        status.update(status_line(self.startup, max(self.size.width - 2, 20)))

    def on_resize(self) -> None:
        self.draw_status()

    def draw_title(self) -> None:
        """The top rule's title: the question, scrolled up, the first hint or none."""
        bar = self.query_one("#bar")
        if self.failure is not None:
            return
        output = self.query_one("#output", VerticalScroll)
        below = round(output.max_scroll_y - output.scroll_y)
        if below > 0:
            lines = "line" if below == 1 else "lines"
            bar.border_title = SCROLLED.format(count=below, lines=lines)
        else:
            bar.border_title = FIRST_HINT if self.first_hint else ""

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

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.failure is not None:
            event.input.clear()
            self.answer_failure(event.value)
            return
        text = event.value.strip()
        event.input.clear()
        if not text:
            return
        self.first_hint = False
        self.draw_title()
        self.say("echo", text)
        try:
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
        bar = self.query_one("#bar")
        bar.add_class("-answering")
        # Textual draws one rule cell before the title; the design has two.
        bar.border_title = Content.assemble(
            ("━ ", "$answer"),
            (ANSWERING.format(command=command), "bold $answer"),
            (ANSWER_HINT, "$muted"),
        )
        self.query_one("#prompt", Label).update(self.failure_question("$answer"))
        self.query_one("#command", Input).placeholder = ANSWER_PLACEHOLDER

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

    def stop_asking(self) -> None:
        self.failure = None
        self.query_one("#bar").remove_class("-answering")
        self.query_one("#prompt", Label).update("> ")
        self.query_one("#command", Input).placeholder = PLACEHOLDER
        self.draw_title()

    def action_clear_line(self) -> None:
        """Ctrl+C clears the line; on the error question it also means no."""
        command = self.query_one("#command", Input)
        if self.failure is not None:
            command.clear()
            self.answer_failure("")
        else:
            command.clear()

    def action_leave(self) -> None:
        if self.failure is None:
            self.exit()

    def action_nothing(self) -> None:
        pass

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
