"""The full-screen app: type ``synthase`` in PowerShell to open it.

The layout, wording and styling rules are in docs/decisions/0016-full-screen-app.md.
All styling is in synthase.tcss and theme.py; nothing here names a colour.
"""

import argparse
import sys
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, HorizontalGroup, Vertical, VerticalScroll
from textual.markup import escape
from textual.widget import Widget
from textual.widgets import Input, Label, Static

from synthase import __version__
from synthase.commands import (
    HELP,
    USAGE_HINT,
    HelpPage,
    UsageError,
    command_list,
    complete,
    find,
    help_page,
    parse_command,
    split_words,
)
from synthase.compound_questions import (
    FIELDS,
    Answers,
    Flow,
    Question,
    add_flow,
    archive_question,
    batch_flow,
    compound_answers,
    confirm_flow,
    confirmed,
    edit_batch_flow,
    edit_flow,
    is_yes,
    remove_batch_question,
    spectrum_flow,
    text_only,
    unlink_flow,
    unlink_question,
)
from synthase.compound_text import (
    EMPTY_REGISTER,
    LABEL_NEEDED,
    NOTHING_ADDED,
    NOTHING_CHANGED,
    NOTHING_LINKED,
    Card,
    Section,
    added_text,
    aligned,
    archived_text,
    batch_added_text,
    batch_cells,
    batch_removed_text,
    batch_saved_text,
    card,
    card_lines,
    field_sections,
    file_needed_text,
    history_rows,
    linked_text,
    list_summary,
    more_details_text,
    restored_text,
    saved_changes_text,
    screen_dates,
    section_lines,
    spectrum_cells,
    still_planned_text,
    unlinked_text,
)
from synthase.compounds import (
    TABLE_HEADINGS,
    Batch,
    Change,
    Compound,
    CompoundError,
    add_batch,
    add_compound,
    archive_compound,
    check_archive,
    compound_history,
    edit_batch,
    edit_compound,
    get_batch,
    get_compound,
    get_spectrum,
    link_spectrum,
    list_compounds,
    parse_batch,
    planned_batch_changes,
    planned_changes,
    remove_batch,
    table_row,
    unlink_spectrum,
)
from synthase.config import ConfigError, ConfigValue, load_config
from synthase.config_edit import (
    Edit,
    plan_folder,
    plan_set,
    plan_source,
    plan_verify,
    save_edit,
)
from synthase.config_text import (
    BACKED_UP,
    CONFIG_HEADINGS,
    EDIT_USAGE,
    EVERY_ENTRY,
    ONE_NAME,
    UNVERIFIED,
    Settings,
    config_entries,
    config_row,
    count_line,
    entry_key,
    entry_rows,
    read_settings,
    settings_heading,
)
from synthase.doctor import Check, ReportText, report_text, run_checks
from synthase.history import History, history_file
from synthase.status import Status, read_status, status_markup
from synthase.tables import (
    TableFolderError,
    kept_text,
    not_saved_text,
    place_table,
    replace_question,
    saved_text,
    write_csv,
)
from synthase.theme import SYNTHASE
from synthase.workspace import (
    WorkspaceError,
    create_workspace,
    current_workspace,
    init_text,
    workspace_target,
)

PLACEHOLDER = "Type a command, e.g. /help"
WELCOME = "Type /quit or press Ctrl+Q to leave."
UNKNOWN = "unknown command, try /help"
NOT_SAVED = "Command history couldn't be saved: {reason}"
QUIT = "quit"
DOCTOR = "doctor"
CONFIG = "config"
INIT = "init"
COMPOUND = "compound"
# The top rule's title while a command is asking questions.
ANSWERING = " Answering {command} · Esc cancels "
CANCELLED = "Cancelled. {nothing}"
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
    "answered": "",
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


class HelpMessage(Message):
    """A /help page: its paragraphs, then names and their help in two columns."""

    def __init__(self, page: HelpPage) -> None:
        rows = "\n".join(f"{name}  {text}" for name, text in page.rows)
        super().__init__("normal", "\n\n".join([*page.paragraphs, rows]).strip())
        self.add_class("-help")
        self.page = page

    def compose(self) -> ComposeResult:
        with Vertical(classes="body"):
            for paragraph in self.page.paragraphs:
                yield Static(paragraph, classes="paragraph", markup=False)
            if self.page.rows:
                with Grid(classes="rows"):
                    for name, text in self.page.rows:
                        yield Label(name, classes="name", markup=False)
                        yield Static(text, classes="text", markup=False)


class DoctorChecks(Message):
    """The /doctor heading, then each check's word and text in two columns.

    With no heading, only the checks, e.g. the folder lines /config shows.
    """

    def __init__(self, heading: str, checks: Iterable[Check]) -> None:
        checks = list(checks)
        lines = [heading, ""] if heading else []
        for check in checks:
            lines.append(f"{check.word:<6}{check.text}")
            if check.fix:
                lines.append(f"      Fix: {check.fix}")
        super().__init__("normal", "\n".join(lines))
        self.add_class("-doctor")
        self.heading = heading
        self.checks = checks

    def compose(self) -> ComposeResult:
        with Vertical(classes="body"):
            if self.heading:
                yield Static(self.heading, classes="heading", markup=False)
            with Grid(classes="rows"):
                for check in self.checks:
                    kind = "-ok" if check.passed else "-fail"
                    yield Label(check.word, classes=f"word {kind}", markup=False)
                    yield Static(check.text, classes=f"text {kind}", markup=False)
                    if check.fix:
                        yield Label("", classes="word")
                        yield Static(f"Fix: {check.fix}", classes="fix", markup=False)


class UnverifiedValues(Message):
    """The /doctor list of unverified values: its title, then key, value and source."""

    def __init__(self, text: ReportText, verified: bool) -> None:
        rows = [f"{key}  {value}\n{source}" for key, value, source in text.unverified]
        kind = "success" if verified else "warning"
        super().__init__(kind, "\n".join([text.unverified_title, *rows]))
        self.add_class("-unverified")
        self.heading = text.unverified_title
        self.rows = text.unverified

    def compose(self) -> ComposeResult:
        yield Label(GLYPHS[self.kind], classes="glyph", markup=False)
        with Vertical(classes="body"):
            yield Static(self.heading, classes="heading", markup=False)
            if self.rows:
                with Grid(classes="rows"):
                    for key, value, source in self.rows:
                        yield Label(key, classes="key", markup=False)
                        yield Static(value, classes="value", markup=False)
                        yield Label("", classes="key")
                        yield Static(source, classes="value", markup=False)


def verified_kind(text: str) -> str:
    """The classes that colour a verified cell; its words carry the meaning."""
    return "verified -no" if text == UNVERIFIED else "verified -yes"


class ConfigTable(Message):
    """The /config heading, then a row per value under a bold heading row."""

    def __init__(self, heading: str, entries: list[ConfigValue]) -> None:
        self.heading = heading
        self.rows = [config_row(entry) for entry in entries]
        lines = [heading, *("  ".join(row) for row in [CONFIG_HEADINGS, *self.rows])]
        super().__init__("normal", "\n".join(lines))
        self.add_class("-config")

    def compose(self) -> ComposeResult:
        with Vertical(classes="body"):
            yield Static(self.heading, classes="title", markup=False)
            with Grid(classes="rows"):
                for heading in CONFIG_HEADINGS:
                    yield Label(heading, classes="heading", markup=False)
                for row in self.rows:
                    *first, verified, source = row
                    for cell in first:
                        yield Label(cell, classes="cell", markup=False)
                    kind = verified_kind(verified)
                    yield Label(verified, classes=f"cell {kind}", markup=False)
                    yield Label(source, classes="cell", markup=False)


class ConfigEntry(Message):
    """One value in full: its key in bold, then each field and what it is."""

    def __init__(self, entry: ConfigValue) -> None:
        self.title = entry.key
        self.rows = entry_rows(entry)
        lines = [self.title, *(f"{name}  {text}" for name, text in self.rows)]
        super().__init__("normal", "\n".join(lines))
        self.add_class("-entry")

    def compose(self) -> ComposeResult:
        with Vertical(classes="body"):
            yield Static(self.title, classes="title", markup=False)
            with Grid(classes="rows"):
                for name, text in self.rows:
                    yield Label(name, classes="name", markup=False)
                    kind = verified_kind(text) if name == "Verified" else ""
                    yield Static(text, classes=f"text {kind}", markup=False)


class Answered(Message):
    """A question and the answer typed, kept in the output as a record."""

    def __init__(self, prompt: str, answer: str) -> None:
        super().__init__("answered", f"{prompt}{answer}")
        self.prompt = prompt
        self.answer = answer

    def compose(self) -> ComposeResult:
        markup = f"[$muted]{escape(self.prompt)}[/][$answer]{escape(self.answer)}[/]"
        yield Static(markup, classes="body")


class Rows(Message):
    """Names and what they are, in two columns, e.g. the folders /init lists."""

    def __init__(self, rows: list[tuple[str, str]]) -> None:
        super().__init__("normal", "\n".join(f"{a}  {b}" for a, b in rows))
        self.add_class("-rows")
        self.rows = rows

    def compose(self) -> ComposeResult:
        with Grid(classes="body rows"):
            for name, text in self.rows:
                yield Label(name, classes="name", markup=False)
                yield Static(text, classes="text", markup=False)


def flagged(line: str) -> tuple[str, str]:
    """A card warning's kind and text: "! …" is a caution, "Warning: …" a warning."""
    if line.startswith("! "):
        return "caution", line[2:]
    return ("warning" if line.startswith("Warning:") else "caution"), line


class Flag(HorizontalGroup):
    """A warning inside a card: its symbol column, then the text."""

    def __init__(self, kind: str, text: str) -> None:
        super().__init__(classes=f"flag -{kind}")
        self.kind = kind
        self.text = text

    def compose(self) -> ComposeResult:
        yield Label(GLYPHS[self.kind], classes="glyph", markup=False)
        yield Static(self.text, classes="text", markup=False)


class CardMessage(Message):
    """A compound's card: the title, each section, then what is still missing.

    Dates are shown DD/MM/YYYY. The text is the card as syn prints it.
    """

    def __init__(self, shown: Card) -> None:
        super().__init__("normal", "\n".join(card_lines(shown)))
        self.add_class("-card")
        self.card = shown

    def compose(self) -> ComposeResult:
        with Vertical(classes="body"):
            yield Static(self.card.title, classes="title", markup=False)
            yield from section_widgets(self.card.sections)
            if self.card.missing:
                yield Flag("hint", "Still missing:")
                for item in self.card.missing:
                    yield Static(item, classes="missing", markup=False)
            else:
                yield Flag("success", "Nothing missing.")


class Fields(Message):
    """A compound's filled fields and details, as shown after adding or editing."""

    def __init__(self, sections: list[Section]) -> None:
        super().__init__("normal", "\n".join(section_lines(sections)))
        self.add_class("-card")
        self.sections = sections

    def compose(self) -> ComposeResult:
        with Vertical(classes="body"):
            yield from section_widgets(self.sections)


def section_widgets(sections: Iterable[Section]) -> Iterator[Widget]:
    """Each section's heading, rows and warnings, laid out as on the card."""
    for section in sections:
        if section.heading is not None:
            yield Static(section.heading, classes="heading", markup=False)
        if section.rows:
            # Batches and Spectra each have their own number of columns.
            kind = section.heading.lower() if section.table else "fields"
            yield row_grid(kind, section.rows)
        for line in section.warnings:
            yield Flag(*flagged(screen_dates(line)))


def screen_rows(rows: Iterable[tuple[str | None, ...]]) -> list[tuple[str, ...]]:
    """``rows`` with - in each blank cell and dates DD/MM/YYYY."""
    return [tuple(screen_dates(cell or "-") for cell in row) for row in rows]


def row_grid(kind: str, rows: Iterable[tuple[str | None, ...]]) -> Grid:
    """``rows`` in the card's columns for ``kind``: fields, batches or spectra."""
    cells = []
    for row in screen_rows(rows):
        *first, last = row
        cells += [Label(cell, classes="name", markup=False) for cell in first]
        # The last column wraps, so a long value stays in it.
        cells.append(Static(last, classes="value", markup=False))
    return Grid(*cells, classes=f"rows -{kind}")


class CardRows(Message):
    """Batches or spectra in the card's columns, e.g. after adding a batch."""

    def __init__(self, kind: str, rows: list[tuple[str | None, ...]]) -> None:
        super().__init__("normal", "\n".join(aligned(screen_rows(rows))))
        self.add_class("-card")
        self.columns = kind
        self.rows = rows

    def compose(self) -> ComposeResult:
        with Vertical(classes="body"):
            yield row_grid(self.columns, self.rows)


class CompoundTable(Message):
    """The compound list: a heading row, then one row per compound."""

    def __init__(self, compounds: list[Compound]) -> None:
        self.compounds = compounds
        self.rows = [table_row(compound) for compound in compounds]
        lines = [
            "  ".join(cell or "-" for cell in row)
            for row in [TABLE_HEADINGS, *self.rows]
        ]
        super().__init__("normal", "\n".join(lines))
        self.add_class("-table")

    def compose(self) -> ComposeResult:
        with Grid(classes="body rows"):
            for heading in TABLE_HEADINGS:
                yield Label(heading, classes="heading", markup=False)
            for compound, row in zip(self.compounds, self.rows, strict=True):
                archived = " -archived" if compound.archived else ""
                for cell in row:
                    yield Label(cell or "-", classes=f"cell{archived}", markup=False)


class ChangeLog(Message):
    """A compound's change log: when, what, then old → new, oldest first."""

    def __init__(self, compound: Compound, changes: list[Change]) -> None:
        self.title = f"History of {compound.id}: {compound.label}"
        self.rows = [
            (screen_dates(when), name, screen_dates(f"{old} → {new}"))
            for when, name, old, new in history_rows(changes)
        ]
        lines = [self.title, *("  ".join(row) for row in self.rows)]
        super().__init__("normal", "\n".join(lines))
        self.add_class("-history")

    def compose(self) -> ComposeResult:
        with Vertical(classes="body"):
            yield Static(self.title, classes="title", markup=False)
            if self.rows:
                with Grid(classes="rows"):
                    for when, name, change in self.rows:
                        yield Label(when, classes="when", markup=False)
                        yield Label(name, classes="name", markup=False)
                        yield Static(change, classes="change", markup=False)


@dataclass
class Asking:
    """A command's open questions: the flow, the answers so far and what's next.

    ``done`` gets the answers once every question is answered. ``nothing`` is
    what cancelling says, e.g. "Nothing was added."
    """

    command: str
    flow: Flow
    done: Callable[[Answers], None]
    nothing: str
    answers: Answers = field(default_factory=dict)
    question: Question | None = None


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
        # Only while a question is open; otherwise the keys work as usual.
        Binding("escape", "cancel", show=False, priority=True),
        Binding("ctrl+c", "cancel", show=False, priority=True),
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
        self.asking: Asking | None = None
        # The config files backed up this session, before their first change.
        self.backed_up: set[Path] = set()

    def compose(self) -> ComposeResult:
        yield VerticalScroll(Welcome(), id="output")
        with Vertical(id="bottom"):
            with Vertical(id="bar"):
                yield Static(id="question", markup=False)
                with HorizontalGroup(id="line"):
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
        self.show(Message(kind, text))

    def show(self, message: Message) -> None:
        """Add a message, following it down unless the user has scrolled up."""
        output = self.query_one("#output")
        following = output.scroll_y >= output.max_scroll_y
        output.mount(message)
        extra = len(output.children) - MAX_MESSAGES
        if extra > 0:
            output.remove_children(output.children[:extra])
        if following:
            output.call_after_refresh(output.scroll_end, animate=False)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.asking is not None:
            event.input.clear()
            self.answer(event.value)
            return
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
        elif command.name == HELP:
            self.show_help(text.split()[1:])
        elif command.name == DOCTOR:
            self.run_doctor()
        elif command.name == CONFIG:
            self.run_config(" ".join(text.split(maxsplit=1)[1:]))
        elif command.name == INIT:
            self.run_init(text.split(maxsplit=1)[1:])
        elif command.name == COMPOUND:
            self.run_compound(text)

    def show_help(self, topic: list[str]) -> None:
        page = help_page(topic, self.commands)
        if page.error:
            self.say("error", page.error)
            return
        # The help is syn's; in the app it names the app's own commands.
        page = replace(
            page,
            paragraphs=tuple(in_app(paragraph) for paragraph in page.paragraphs),
            rows=tuple((name, in_app(text)) for name, text in page.rows),
        )
        self.show(HelpMessage(page))
        if page.hint:
            self.say("hint", page.hint)

    def run_doctor(self) -> None:
        """The self-test, worded as syn doctor words it (decisions 0010 and 0016)."""
        report = run_checks(init="/init")
        text = report_text(report, rerun="/doctor")
        self.show(DoctorChecks(text.heading, report.checks))
        verified = report.config is not None and not text.unverified
        self.show(UnverifiedValues(text, verified))
        last = Message("error" if report.failed else "success", text.last)
        last.add_class("-doctor-last")
        self.show(last)
        self.refresh_status()

    def run_config(self, rest: str) -> None:
        """The settings, or one value in full, checked as syn doctor checks them.

        ``rest`` is everything typed after /config. A first word such as set
        changes a setting instead (decision 0017).
        """
        names = rest.split()
        if names and names[0].lower() in EDIT_USAGE:
            self.edit_config(names[0].lower(), rest.split(maxsplit=1)[1:])
            return
        if len(names) > 1:
            self.say("error", ONE_NAME)
            return
        settings = self.read_config_settings()
        if settings is None:
            return
        config = settings.config
        if names:
            try:
                entry = config.get(entry_key(names[0]))
            except ConfigError as error:
                self.say("error", str(error))
                self.say("hint", EVERY_ENTRY)
                return
            self.show(ConfigEntry(entry))
            if entry.warning:
                self.say("warning", entry.warning)
            return
        entries = config_entries(config)
        self.show(ConfigTable(settings_heading(config), entries))
        unverified = any(not entry.verified for entry in entries)
        self.say("warning" if unverified else "success", count_line(config))
        self.show(DoctorChecks("", settings.folders))

    def read_config_settings(self) -> Settings | None:
        """The checked settings, or None after saying what doctor says is wrong."""
        settings = read_settings(init="/init")
        self.refresh_status()
        if settings.problem is None:
            return settings
        self.say("error", in_app(settings.problem.text))
        if settings.problem.fix:
            self.say("hint", f"Fix: {settings.problem.fix}")
        return None

    def edit_config(self, how: str, rest: list[str]) -> None:
        """Change a setting: ``how`` is set, source, verify or folder."""
        # verify takes one name; the others take a name, then the rest as typed.
        typed = rest[0] if rest else ""
        words = typed.split() if how == "verify" else typed.split(maxsplit=1)
        if len(words) != (1 if how == "verify" else 2):
            self.say("error", EDIT_USAGE[how])
            return
        settings = self.read_config_settings()
        if settings is None:
            return
        workspace = Path(settings.config.path).parent
        plan = {
            "set": plan_set,
            "source": plan_source,
            "verify": plan_verify,
            "folder": plan_folder,
        }[how]
        try:
            edit = plan(workspace, *words)
        except ConfigError as error:
            self.say("error", str(error))
            return
        if edit.new_bytes is None:
            self.say("success", edit.done)
            return
        if edit.note:
            self.say("hint", edit.note)
        folders = how == "folder"
        if not edit.question:
            self.save_config(edit, folders)
            return
        question = Question("change", edit.question, text_only(is_yes))

        def done(answers: Answers) -> None:
            if answers["change"]:
                self.save_config(edit, folders)
            else:
                self.say("cancel", NOTHING_CHANGED)

        self.ask(f"/config {how}", Flow((), (question,)), done, NOTHING_CHANGED)

    def save_config(self, edit: Edit, folders: bool) -> None:
        """Save ``edit``, keeping a backup before the file's first change."""
        first = edit.path not in self.backed_up
        try:
            backup = save_edit(edit, back_up=first)
        except ConfigError as error:
            self.say("error", str(error))
            return
        self.backed_up.add(edit.path)
        self.say("success", edit.done)
        if backup is not None:
            self.say("hint", BACKED_UP.format(name=backup.name))
        if edit.hint:
            self.say("hint", edit.hint)
        settings = self.read_config_settings()
        if folders and settings is not None:
            self.show(DoctorChecks("", settings.folders))

    def run_init(self, rest: list[str]) -> None:
        """Create or find the workspace, as syn init does (decision 0009).

        Everything after /init is the path, with any quotes around it removed.
        """
        typed = rest[0].strip().strip("\"'") if rest else ""
        path = Path(typed) if typed else None
        try:
            target = workspace_target(path)
        except WorkspaceError as error:
            self.say("error", str(error))
            return
        if not target.existing:
            self.finish_init(path, replace=False)
            return
        question = Question("replace", target.question, text_only(is_yes))
        self.ask(
            "/init",
            Flow((), (question,)),
            lambda answers: self.finish_init(path, answers["replace"]),
            "Nothing was changed.",
        )

    def finish_init(self, path: Path | None, replace: bool) -> None:
        try:
            created = create_workspace(path, lambda question: replace)
        except WorkspaceError as error:
            self.say("error", str(error))
            return
        text = init_text(created)
        self.say("success", text.first)
        self.show(Rows(text.rows))
        if text.next is not None:
            self.say("hint", text.next)
        self.say("normal", text.last)
        self.refresh_status()
        # History lives in the workspace, so it follows the new one.
        self.history = History.load(history_file())

    def run_compound(self, text: str) -> None:
        """The /compound commands the app has, read as syn compound reads them."""
        try:
            words = split_words(text)[1:]
        except UsageError as error:
            self.say("error", str(error))
            return
        if not words:
            self.show_help([COMPOUND])
            return
        name = words[0] = words[0].lower()
        if name not in self.commands.subcommands[COMPOUND].subcommands:
            self.say("error", UNKNOWN)
        elif "-h" in words or "--help" in words:
            self.show_help([COMPOUND, name])
        else:
            try:
                args = parse_command([COMPOUND, *words])
            except UsageError as error:
                self.say("error", str(error))
                self.say("hint", USAGE_HINT.format(topic=f"{COMPOUND} {name}"))
                return
            try:
                self.compound_command(args)
            except (WorkspaceError, CompoundError) as error:
                self.say("error", in_app(str(error)))

    def compound_command(self, args: argparse.Namespace) -> None:
        workspace = current_workspace()
        if args.compound_command == "add":
            self.run_add(args, workspace)
        elif args.compound_command == "edit":
            self.run_edit(args, workspace)
        elif args.compound_command == "show":
            self.show(CardMessage(card(get_compound(workspace, args.id), workspace)))
        elif args.compound_command == "history":
            self.show(ChangeLog(*compound_history(workspace, args.id)))
        elif args.compound_command == "archive":
            self.run_archive(args.id, workspace)
        elif args.compound_command == "restore":
            compound = archive_compound(workspace, args.id, archived=False)
            self.say("success", in_app(restored_text(compound)))
        elif args.compound_command == "batch":
            self.run_batch(args, workspace)
        elif args.compound_command == "edit-batch":
            self.run_edit_batch(args, workspace)
        elif args.compound_command == "remove-batch":
            self.run_remove_batch(args, workspace)
        elif args.compound_command == "spectrum":
            self.run_spectrum(args, workspace)
        elif args.compound_command == "unlink":
            self.run_unlink(args, workspace)
        else:
            self.list_compounds(args, workspace)

    def run_add(self, args: argparse.Namespace, workspace: Path) -> None:
        """Add a compound as syn compound add does: from options, or by asking."""
        flags = {field: getattr(args, field) for field in FIELDS}
        if all(flag is None for flag in flags.values()):

            def done(answers: Answers) -> None:
                self.finish_add(workspace, compound_answers(answers))

            self.ask("/compound add", add_flow(workspace), done, NOTHING_ADDED)
        elif args.label is None:
            self.say("error", in_app(LABEL_NEEDED))
        else:
            self.finish_add(workspace, flags)

    def finish_add(self, workspace: Path, values: dict[str, object]) -> None:
        try:
            compound = add_compound(workspace, **values)
        except CompoundError as error:
            self.say("error", in_app(str(error)))
            return
        self.say("success", added_text(compound))
        self.show(Fields(field_sections(compound, workspace)))
        self.say("hint", in_app(more_details_text(compound)))

    def run_edit(self, args: argparse.Namespace, workspace: Path) -> None:
        """Edit a compound as syn compound edit does: from options, or by asking.

        Every confirmation is asked before edit_compound saves anything.
        """
        compound = get_compound(workspace, args.id)
        flags = {field: getattr(args, field) for field in FIELDS}
        if any(flag is not None for flag in flags.values()):
            self.confirm_edit(workspace, args.id, flags)
            return

        def done(answers: Answers) -> None:
            self.confirm_edit(workspace, args.id, compound_answers(answers))

        flow = edit_flow(workspace, compound)
        self.ask("/compound edit", flow, done, NOTHING_CHANGED)

    def confirm_edit(
        self, workspace: Path, text: str, values: dict[str, object]
    ) -> None:
        try:
            changes = planned_changes(workspace, text, **values)
        except (WorkspaceError, CompoundError) as error:
            self.say("error", in_app(str(error)))
            return
        flow = confirm_flow(changes)
        if not flow.questions:
            self.finish_edit(workspace, text, values, set(changes))
            return

        def done(answers: Answers) -> None:
            self.finish_edit(workspace, text, values, confirmed(changes, answers))

        self.ask("/compound edit", flow, done, NOTHING_CHANGED)

    def finish_edit(
        self,
        workspace: Path,
        text: str,
        values: dict[str, object],
        allowed: set[Change],
    ) -> None:
        try:
            compound, changes = edit_compound(
                workspace, text, allowed.__contains__, **values
            )
        except (WorkspaceError, CompoundError) as error:
            self.say("error", in_app(str(error)))
            return
        if not changes:
            self.say("normal", NOTHING_CHANGED)
            return
        self.say("success", saved_changes_text(compound, changes))
        self.show(Fields(field_sections(compound, workspace)))

    def run_archive(self, text: str, workspace: Path) -> None:
        """Archive a compound after a yes, as syn compound archive does."""
        compound = get_compound(workspace, text)
        check_archive(compound)

        def archive() -> None:
            archive_compound(workspace, text)
            self.say("success", in_app(archived_text(compound)))

        self.confirm("/compound archive", archive_question(compound), archive)

    def run_batch(self, args: argparse.Namespace, workspace: Path) -> None:
        """Add a batch as syn compound batch does: from options, or by asking."""
        compound = get_compound(workspace, args.id)
        flags = (args.date, args.mass, args.yield_percent)
        if any(flag is not None for flag in flags):
            self.finish_batch(workspace, args.id, *parse_batch(*flags))
            return

        def done(answers: Answers) -> None:
            self.finish_batch(
                workspace,
                args.id,
                answers["made_on"],
                answers["mass_g"],
                answers["yield_percent"],
            )

        self.ask("/compound batch", batch_flow(compound), done, NOTHING_ADDED)

    def finish_batch(
        self,
        workspace: Path,
        text: str,
        made_on: date,
        mass_g: float | None,
        yield_percent: float | None,
    ) -> None:
        compound, batch = add_batch(workspace, text, made_on, mass_g, yield_percent)
        self.say("success", batch_added_text(compound, batch))
        self.show_batch(batch)
        if planned := still_planned_text(compound):
            self.say("hint", in_app(planned))

    def show_batch(self, batch: Batch) -> None:
        """``batch`` in the card's Batches columns, then any warning about it."""
        self.show(CardRows("batches", [batch_cells(batch)]))
        if batch.warning:
            self.say("caution", batch.warning)

    def run_edit_batch(self, args: argparse.Namespace, workspace: Path) -> None:
        """Correct a batch as syn compound edit-batch does: from options, or by asking.

        Every confirmation is asked before edit_batch saves anything.
        """
        compound, batch = get_batch(workspace, args.id, args.batch)
        flags = {
            "made_on": args.date,
            "mass": args.mass,
            "yield_percent": args.yield_percent,
        }
        if any(flag is not None for flag in flags.values()):
            self.confirm_batch(workspace, args, flags)
            return

        def done(answers: Answers) -> None:
            self.confirm_batch(workspace, args, answers)

        flow = edit_batch_flow(compound, batch)
        self.ask("/compound edit-batch", flow, done, NOTHING_CHANGED)

    def confirm_batch(
        self, workspace: Path, args: argparse.Namespace, values: Answers
    ) -> None:
        changes = planned_batch_changes(workspace, args.id, args.batch, **values)

        def done(answers: Answers) -> None:
            allowed = confirmed(changes, answers)
            compound, batch, saved = edit_batch(
                workspace, args.id, args.batch, allowed.__contains__, **values
            )
            if not saved:
                self.say("normal", NOTHING_CHANGED)
                return
            self.say("success", batch_saved_text(compound, batch, saved))
            self.show_batch(batch)

        flow = confirm_flow(changes)
        if flow.questions:
            self.ask("/compound edit-batch", flow, done, NOTHING_CHANGED)
        else:
            done({})

    def run_remove_batch(self, args: argparse.Namespace, workspace: Path) -> None:
        """Remove a batch after a yes, as syn compound remove-batch does."""
        compound, batch = get_batch(workspace, args.id, args.batch)

        def remove() -> None:
            remove_batch(workspace, args.id, args.batch)
            self.say("success", in_app(batch_removed_text(compound, batch)))

        question = remove_batch_question(compound, batch)
        self.confirm("/compound remove-batch", question, remove)

    def run_spectrum(self, args: argparse.Namespace, workspace: Path) -> None:
        """Link a spectra file as syn compound spectrum does: given, or by asking."""
        compound = get_compound(workspace, args.id)
        if args.file is not None:
            self.finish_link(workspace, args.id, args.file, args.kind)
            return
        if args.kind is not None:
            raise CompoundError(file_needed_text(compound))

        def done(answers: Answers) -> None:
            self.finish_link(workspace, args.id, answers["file"], answers["kind"])

        flow = spectrum_flow(workspace, compound)
        self.ask("/compound spectrum", flow, done, NOTHING_LINKED)

    def finish_link(
        self, workspace: Path, text: str, file: Path, kind: str | None
    ) -> None:
        compound, spectrum = link_spectrum(workspace, text, file, kind)
        self.say("success", linked_text(compound))
        self.show(CardRows("spectra", [spectrum_cells(spectrum, workspace)]))

    def run_unlink(self, args: argparse.Namespace, workspace: Path) -> None:
        """Unlink a spectra file after a yes, as syn compound unlink does.

        With no file, the linked files are listed and the app asks which one.
        """
        compound = get_compound(workspace, args.id)
        if args.file is not None:
            self.confirm_unlink(workspace, args.id, args.file)
            return

        def done(answers: Answers) -> None:
            self.confirm_unlink(workspace, args.id, answers["file"])

        flow = unlink_flow(workspace, compound)
        self.ask("/compound unlink", flow, done, NOTHING_CHANGED)

    def confirm_unlink(self, workspace: Path, text: str, file: str) -> None:
        compound, spectrum = get_spectrum(workspace, text, file)

        def unlink() -> None:
            unlink_spectrum(workspace, text, file)
            self.say("success", unlinked_text(compound, spectrum))

        question = unlink_question(compound, spectrum)
        self.confirm("/compound unlink", question, unlink)

    def confirm(
        self, command: str, question: Question, then: Callable[[], None]
    ) -> None:
        """Ask the [y/N] ``question``, then call ``then`` after a yes.

        Anything else shows the question's kept line, and Esc changes nothing.
        """

        def done(answers: Answers) -> None:
            if answers[question.key]:
                then()

        self.ask(command, Flow((), (question,)), done, NOTHING_CHANGED)

    def list_compounds(self, args: argparse.Namespace, workspace: Path) -> None:
        shown = list_compounds(
            workspace, args.status, args.compound_class, archived=args.all
        )
        everything = list_compounds(workspace, archived=True)
        if not everything:
            self.say("normal", in_app(EMPTY_REGISTER))
            return
        summary = list_summary(
            shown, everything, args.status, args.compound_class, archived=args.all
        )
        if not shown:
            self.say("normal", summary)
            return
        table = CompoundTable(shown)
        self.show(table)
        self.say("normal", summary)
        if args.csv is not None:
            self.save_table(args.csv, workspace, table.rows)

    def save_table(self, name: Path, workspace: Path, rows: list[tuple]) -> None:
        """Save the list as CSV where decision 0015 says, asking before a replace."""
        try:
            path = place_table(name, workspace, load_config(workspace), "compounds")
        except (ConfigError, TableFolderError) as error:
            self.say("error", str(error))
            return
        if not path.exists():
            self.write_table(path, rows)
            return
        question = Question(
            "replace", replace_question(path), text_only(is_yes), yes_no=True
        )

        def done(answers: Answers) -> None:
            if answers["replace"]:
                self.write_table(path, rows)
            else:
                self.say("normal", kept_text(path))

        flow = Flow((), (question,))
        self.ask("/compound list", flow, done, "The table was not saved.")

    def write_table(self, path: Path, rows: list[tuple]) -> None:
        try:
            write_csv(path, TABLE_HEADINGS, rows)
        except OSError as error:
            self.say("error", not_saved_text(path, error))
            return
        self.say("success", saved_text(path))

    def ask(
        self,
        command: str,
        flow: Flow,
        done: Callable[[Answers], None],
        nothing: str,
    ) -> None:
        """Ask ``flow``'s questions in the command bar, then call ``done``.

        Esc or Ctrl+C cancels and says ``nothing``, and ``done`` isn't called.
        """
        for line in flow.opening:
            self.say("normal", asked_text(line))
        self.asking = Asking(command, flow, done, nothing)
        bar = self.query_one("#bar")
        bar.add_class("-answering")
        bar.border_title = ANSWERING.format(command=command)
        self.query_one("#command", Input).placeholder = ""
        self.next_question()

    def next_question(self) -> None:
        asking = self.asking
        asking.question = asking.flow.next_question(asking.answers)
        if asking.question is None:
            self.stop_asking()
            try:
                asking.done(asking.answers)
            except (WorkspaceError, CompoundError) as error:
                self.say("error", in_app(str(error)))
        else:
            prompt = asked_text(asking.question.prompt.rstrip())
            self.query_one("#question", Static).update(prompt)

    def answer(self, text: str) -> None:
        """Check the answer typed; a wrong one is explained and asked again."""
        asking = self.asking
        self.show(Answered(asked_text(asking.question.prompt), text))
        try:
            answer = asking.question.answer(text, asking.answers)
        except CompoundError as error:
            self.say("error", str(error))
            return
        asking.answers[asking.question.key] = answer
        if asking.question.kept is not None and not answer:
            self.say("normal", asked_text(asking.question.kept))
        self.next_question()

    def stop_asking(self) -> None:
        self.asking = None
        bar = self.query_one("#bar")
        bar.remove_class("-answering")
        bar.border_title = ""
        self.query_one("#question", Static).update("")
        self.query_one("#command", Input).placeholder = PLACEHOLDER

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        # Esc and Ctrl+C cancel only while a question is open.
        return action != "cancel" or self.asking is not None

    def action_cancel(self) -> None:
        nothing = self.asking.nothing
        self.stop_asking()
        self.query_one("#command", Input).clear()
        self.say("cancel", CANCELLED.format(nothing=nothing))

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
        if self.asking is not None:
            return
        step = self.history.back() if direction < 0 else self.history.forward()
        if step is not None:
            self.set_command(step)

    def action_complete(self) -> None:
        if self.asking is not None:
            return
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


# Shared messages name syn commands; in the app they name its own.
IN_APP = (
    ('"syn compound ', '"/compound '),
    ('"syn init"', '"/init"'),
)


def in_app(message: str) -> str:
    """A shared message, pointing at the app's own command where it has one."""
    for syn, app in IN_APP:
        message = message.replace(syn, app)
    return message


def asked_text(text: str) -> str:
    """A question, its opening lines or a kept line as the app shows it.

    It names the app's own commands, and its dates are DD/MM/YYYY.
    """
    return screen_dates(in_app(text))


def main(argv: list[str] | None = None) -> int:
    """Open the app. ``synthase --dev`` reloads synthase.tcss whenever it is saved."""
    args = sys.argv[1:] if argv is None else argv
    SynthaseApp(watch_css="--dev" in args).run()
    return 0
