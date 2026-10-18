"""The full-screen app: type ``synthase`` in PowerShell to open it.

The layout, wording and styling rules are in docs/decisions/0016-full-screen-app.md.
All styling is in synthase.tcss and theme.py; nothing here names a colour.
"""

import sys

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalGroup, Vertical, VerticalScroll
from textual.widgets import Input, Label, Static

from synthase import __version__
from synthase.commands import command_list, complete, find
from synthase.history import History, history_file
from synthase.status import Status, read_status, status_markup
from synthase.theme import SYNTHASE

PLACEHOLDER = "Type a command, e.g. /help"
WELCOME = "Type /quit or press Ctrl+Q to leave."
UNKNOWN = "unknown command, try /help"
# For a syn command whose app version hasn't been built yet (#55 to #59).
NOT_YET = "/{name} isn't in the app yet. For now, run syn {name} in PowerShell."
NOT_SAVED = "Command history couldn't be saved: {reason}"
QUIT = "quit"
# The output keeps only the latest messages, so a long session stays quick.
MAX_MESSAGES = 1000
# Shown in the top rule until the first command.
FIRST_HINT = " ↑ ↓ history · Tab completes · Ctrl+Q quits "
# The symbol each kind of message starts with. Colour and weight are in the TCSS.
GLYPHS = {
    "echo": ">",
    "normal": "",
    "success": "✓",
    "hint": "›",
    "caution": "!",
    "warning": "?",
    "error": "✗",
    "cancel": "‹",
}


class Message(HorizontalGroup):
    """One message in the output: a symbol column, then the text."""

    def __init__(self, kind: str, text: str) -> None:
        reply = "" if kind == "echo" else " -reply"
        super().__init__(classes=f"msg -{kind}{reply}")
        self.kind = kind
        self.text = text

    def compose(self) -> ComposeResult:
        if GLYPHS[self.kind]:
            yield Label(GLYPHS[self.kind], classes="glyph", markup=False)
        yield Static(self.text, classes="body", markup=False)


class Welcome(HorizontalGroup):
    """The first line: ``Synthase 0.1.0. Type /quit or press Ctrl+Q to leave.``"""

    def __init__(self) -> None:
        super().__init__(classes="msg -welcome")

    def compose(self) -> ComposeResult:
        yield Label(f"Synthase {__version__}.", classes="lead", markup=False)
        yield Static(f" {WELCOME}", classes="body", markup=False)


class SynthaseApp(App):
    CSS_PATH = "synthase.tcss"
    TITLE = "Synthase"
    ENABLE_COMMAND_PALETTE = False
    # The input keeps the focus, so the output scrolls through app keys.
    BINDINGS = [
        Binding("pageup", "scroll_output(-1)", show=False),
        Binding("pagedown", "scroll_output(1)", show=False),
        Binding("up", "step_history(-1)", show=False),
        Binding("down", "step_history(1)", show=False),
        # Before Textual's own Tab, which would move the focus off the bar.
        Binding("tab", "complete", show=False, priority=True),
    ]

    def __init__(self, watch_css: bool = False) -> None:
        super().__init__(watch_css=watch_css)
        # Before the stylesheet is read, so its $tokens resolve.
        self.register_theme(SYNTHASE)
        self.theme = SYNTHASE.name
        self.status = Status("none")
        self.commands = command_list()
        self.history = History(None)
        self.history_warned = False
        # The last choices Tab listed, so the same list isn't printed twice in a row.
        self.listed: tuple[str, ...] = ()

    def compose(self) -> ComposeResult:
        yield VerticalScroll(Welcome(), id="output")
        with Vertical(id="bottom"):
            with HorizontalGroup(id="bar"):
                yield Label("> ", id="prompt", markup=False)
                yield Input(placeholder=PLACEHOLDER, id="command", compact=True)
            yield Static(id="status")

    def on_mount(self) -> None:
        self.query_one("#bar").border_title = FIRST_HINT
        self.refresh_status()
        self.history = History.load(history_file())
        self.query_one("#command").focus()

    def refresh_status(self) -> None:
        """Read the workspace and config again, then redraw the status line."""
        self.status = read_status()
        self.draw_status()

    def draw_status(self) -> None:
        status = self.query_one("#status", Static)
        room = max(self.size.width - 2, 20)
        status.update(status_markup(self.status, room))

    def on_resize(self) -> None:
        self.draw_status()

    def say(self, kind: str, text: str) -> None:
        """Add a message, following it down unless the user has scrolled up."""
        output = self.query_one("#output")
        following = output.scroll_y >= output.max_scroll_y
        output.mount(Message(kind, text))
        extra = len(output.children) - MAX_MESSAGES
        if extra > 0:
            output.remove_children(output.children[:extra])
        if following:
            output.call_after_refresh(output.scroll_end, animate=False)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.clear()
        if not text:
            return
        self.query_one("#bar").border_title = ""
        self.listed = ()
        self.say("echo", text)
        self.remember(text)
        command = find(text, self.commands)
        if command is None:
            self.say("error", UNKNOWN)
        elif command.name == QUIT:
            self.exit()
        else:
            self.say("error", NOT_YET.format(name=command.name))

    def remember(self, text: str) -> None:
        """Add a command to the history, saying once if the file can't be saved."""
        try:
            self.history.add(text)
        except OSError as error:
            if not self.history_warned:
                self.history_warned = True
                self.say("caution", NOT_SAVED.format(reason=error.strerror or error))

    def set_command(self, text: str) -> None:
        bar = self.query_one("#command", Input)
        bar.value = text
        bar.cursor_position = len(text)

    def action_step_history(self, direction: int) -> None:
        step = self.history.back() if direction < 0 else self.history.forward()
        if step is not None:
            self.set_command(step)

    def action_complete(self) -> None:
        text = self.query_one("#command", Input).value
        result = complete(text, self.commands)
        if result.text != text:
            self.set_command(result.text)
        elif result.choices and result.choices != self.listed:
            self.say("hint", "  ".join(result.choices))
        self.listed = result.choices

    def action_scroll_output(self, direction: int) -> None:
        output = self.query_one("#output")
        if direction < 0:
            output.scroll_page_up()
        else:
            output.scroll_page_down()


def main(argv: list[str] | None = None) -> int:
    """Open the app. ``synthase --dev`` reloads synthase.tcss whenever it is saved."""
    args = sys.argv[1:] if argv is None else argv
    SynthaseApp(watch_css="--dev" in args).run()
    return 0
