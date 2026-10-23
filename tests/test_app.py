"""Headless tests of the full-screen app, driven by Textual's test pilot.

Every folder, name and value is invented.
"""

import asyncio
import os
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field

import pytest
from textual import constants
from textual.content import Content

from synthase import __version__, experiments, history, older_console
from synthase.app import (
    FIRST_HINT,
    PLACEHOLDER,
    TAB_HINT,
    ErrorLog,
    HelpForms,
    HelpList,
    Message,
    SynthaseApp,
    Welcome,
)
from synthase.lock import IN_USE
from synthase.startup import FOREIGN, NO_PROJECT
from synthase.walkthrough import Question, Walkthrough


@dataclass
class Shown:
    """What the app showed just before it closed."""

    app: SynthaseApp
    output: list = field(default_factory=list)
    status: str = ""
    title: object = ""

    def of(self, kind):
        return [w for w in self.output if isinstance(w, kind)]


def run(steps=None, size=(120, 30), app=None):
    """Open the app, call ``steps(app, pilot)``, and return what it showed."""
    app = app or SynthaseApp()
    shown = Shown(app)

    async def drive():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            if steps is not None:
                await steps(app, pilot)
            await pilot.pause()
            if app.is_running:
                shown.output = list(app.query_one("#output").children)
                shown.status = app.query_one("#status").render().plain
                shown.title = app.query_one("#bar").border_title

    asyncio.run(drive())
    return shown


def typing(*lines):
    """Steps that type each line in the command bar and press Enter."""

    async def steps(app, pilot):
        for line in lines:
            app.query_one("#command").value = line
            await pilot.press("enter")
            await pilot.pause()

    return steps


def messages(shown):
    return [(m.kind, m.text) for m in shown.of(Message)]


@pytest.fixture
def project(data):
    """An invented project as Synthase left it: its files logged in the history."""
    history.log("create_project", "synthase.toml")
    return data


@pytest.fixture
def other_process():
    """Another running process, as a second Synthase window would be."""
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    yield process.pid
    process.kill()
    process.wait()


def test_help_and_a_typo_run_through_the_app(project):
    shown = run(typing("help", "epx"))
    assert len(shown.of(HelpList)) == 1
    help_text = shown.of(HelpList)[0].text
    assert help_text.startswith("Project\n  project create  Set up a Synthase project")
    assert help_text.endswith(
        "› For every form of one command, type help <command>, e.g. help exp."
    )
    assert messages(shown)[-3:] == [
        ("echo", "epx"),
        ("error", "Unknown command 'epx'."),
        ("hint", "Did you mean: exp, exit?"),
    ]


def test_the_welcome_line_and_the_first_hint(project):
    async def steps(app, pilot):
        assert app.query_one("#bar").border_title == FIRST_HINT
        assert FIRST_HINT == " Tab completes · ↑ ↓ history · Ctrl+D exits "
        assert app.query_one("#command").placeholder == PLACEHOLDER
        await typing("help")(app, pilot)

    shown = run(steps)
    assert shown.of(Welcome)[0].text == (
        f"Synthase {__version__}  ·  type 'help' for commands"
    )
    assert shown.title == ""


def test_a_project_opens_with_its_name_and_takes_the_lock(project):
    seen = {}

    async def steps(app, pilot):
        seen["lock"] = (project / ".synthase.lock").read_text()

    shown = run(steps)
    assert seen["lock"] == str(os.getpid())
    assert shown.status.startswith("Invented project · ")
    assert messages(shown) == []
    # The lock is given back when the app closes.
    assert not (project / ".synthase.lock").exists()


def test_outside_edits_are_noticed_once(project):
    (project / "experiments.toml").write_text("[E001]\n")
    shown = run()
    assert messages(shown) == [
        (
            "notice",
            "data\\experiments.toml was changed outside Synthase. "
            "The change is noted in the history.",
        )
    ]
    assert messages(run()) == []


def test_a_folder_with_no_project(home):
    shown = run(typing("exp show", "project show"), size=(200, 50))
    assert messages(shown) == [
        ("hint", NO_PROJECT),
        ("echo", "exp show"),
        ("hint", NO_PROJECT),
        ("echo", "project show"),
        ("hint", NO_PROJECT),
    ]
    assert shown.status == f"{home} · › {NO_PROJECT}"
    assert not (home / "data").exists()


def test_a_data_folder_that_isnt_synthases_is_left_alone(home):
    (home / "data").mkdir()
    (home / "data" / "results.csv").write_text("invented\n")
    shown = run(typing("help exp", "exp show", "project create"), size=(200, 50))
    assert messages(shown)[0] == ("error", FOREIGN)
    assert len(shown.of(HelpForms)) == 1
    assert messages(shown)[-3:] == [
        ("error", FOREIGN),
        ("echo", "project create"),
        ("error", FOREIGN),
    ]
    assert shown.status == f"{home} · ✗ data\\ isn't a Synthase folder"
    assert [p.name for p in (home / "data").iterdir()] == ["results.csv"]


def test_a_project_open_in_another_window(project, other_process):
    (project / ".synthase.lock").write_text(str(other_process))
    shown = run(typing("exp show"))
    assert messages(shown) == [
        ("error", IN_USE),
        ("echo", "exp show"),
        ("error", IN_USE),
    ]
    assert shown.status.endswith(" · ✗ open in another Synthase window")
    assert shown.status.startswith("Invented project · ")
    # The other window's lock stays.
    assert (project / ".synthase.lock").read_text() == str(other_process)


def test_a_broken_data_file(project):
    (project / "experiments.toml").write_text('[E001]\ntitle = "Invented"\n= 3\n')
    shown = run()
    assert messages(shown) == [
        (
            "error",
            "data\\experiments.toml has a mistake on line 3, so Synthase won't "
            "load it. Fix it in Notepad, then try again.",
        )
    ]
    assert shown.status.endswith(" · ✗ data\\experiments.toml has a mistake")
    assert not shown.status.startswith("Invented project")
    assert not (project / ".synthase.lock").exists()


def test_a_data_command_not_built_yet(project):
    shown = run(typing("exp show all"))
    assert messages(shown)[-1] == ("error", "exp show all isn't built yet.")


def test_usage_errors_hang_under_the_first(project):
    shown = run(typing("exp export", "compound show"))
    assert messages(shown) == [
        ("echo", "exp export"),
        ("error", "Usage: exp export <csv or json>"),
        ("echo", "compound show"),
        ("error", "Usage: compound show <ID> [field]\nUsage: compound show all"),
    ]


def test_help_for_one_command(project):
    shown = run(typing("help value", "help vale"))
    forms = shown.of(HelpForms)[0].text.split("\n\n")
    assert forms[0] == (
        "Usage:   value add <name> <value> <unit> [+/- unc] [# note]\n"
        "         Store a new value in the open experiment.\n"
        "Example: value add m_crude 2.211 g +/- 0.001 # Balance B2"
    )
    assert len(forms) == 5
    assert messages(shown)[-2:] == [
        ("error", "Unknown command 'vale'."),
        ("hint", "Did you mean: value, exp?"),
    ]


def test_ctrl_c_clears_the_line(project):
    async def steps(app, pilot):
        app.query_one("#command").value = "exp sh"
        await pilot.press("ctrl+c")
        assert app.query_one("#command").value == ""

    assert messages(run(steps)) == []


@pytest.mark.parametrize("leave", ["exit", "ctrl+d"])
def test_exit_and_ctrl_d_leave_and_give_back_the_lock(project, leave):
    async def steps(app, pilot):
        if leave == "exit":
            await typing("exit")(app, pilot)
        else:
            await pilot.press("ctrl+d")
        await pilot.pause()
        assert not app.is_running

    shown = run(steps)
    assert shown.app.return_code == 0
    assert not (project / ".synthase.lock").exists()


def test_an_empty_line_does_nothing(project):
    shown = run(typing("", "   "))
    assert messages(shown) == []


def test_narrow_windows_have_the_narrow_class(project):
    async def steps(app, pilot):
        assert app.screen.has_class("-narrow")

    run(steps, size=(80, 24))


def test_scrolling_up_says_how_much_is_below(project):
    async def steps(app, pilot):
        await typing("help", "help", "help")(app, pilot)
        await pilot.press("pageup")
        await pilot.pause()
        title = app.query_one("#bar").border_title
        assert title.startswith(" scrolled up · ")
        assert title.endswith(" newer lines below · PgDn to go back down ")
        await pilot.press("pagedown", "pagedown", "pagedown", "pagedown")
        await pilot.pause()
        assert app.query_one("#bar").border_title == ""

    run(steps)


def failing_app():
    """The app with `exp export` failing as if a bug had been hit."""
    app = SynthaseApp()

    def fail(call):
        raise RuntimeError("an invented failure")

    app.handlers[("exp", "export")] = fail
    return app


def asks_question(app):
    bar = app.query_one("#bar")
    title = Content.from_markup(bar.border_title).plain
    return bar.has_class("-answering") and title == (
        "━ Answering exp export · Enter means no · Ctrl+C cancels "
    )


def test_an_unexpected_error_asks_and_y_shows_the_log(project):
    async def steps(app, pilot):
        await typing("exp export csv")(app, pilot)
        assert asks_question(app)
        assert app.query_one("#command").placeholder == "y or n"
        assert str(app.query_one("#prompt").render()) == (
            "Failed. Would you like the error log? [y/n] "
        )
        await typing("Y")(app, pilot)
        assert not app.query_one("#bar").has_class("-answering")

    shown = run(steps, app=failing_app())
    log = (project / "error.log").read_text(encoding="utf-8")
    assert "  exp export csv\nSynthase " in log
    assert log.endswith("RuntimeError: an invented failure\n\n")
    block = shown.of(ErrorLog)[0]
    assert block.file == "data\\error.log"
    assert log.startswith(block.entry)
    assert messages(shown) == [
        ("echo", "exp export csv"),
        ("error", "Failed. Would you like the error log? [y/n] Y"),
        ("hint", "The log stays in data\\error.log."),
    ]
    # The traceback is shown only inside the log block.
    assert all("Traceback" not in text for _, text in messages(shown))


@pytest.mark.parametrize("answer", ["n", "", "maybe"])
def test_anything_but_yes_shows_nothing_more(project, answer):
    shown = run(typing("exp export csv", answer, "help"), app=failing_app())
    assert len(shown.of(ErrorLog)) == 0
    assert messages(shown)[:2] == [
        ("echo", "exp export csv"),
        ("error", f"Failed. Would you like the error log? [y/n] {answer}"),
    ]
    assert len(shown.of(HelpList)) == 1


def test_ctrl_c_on_the_question_means_no(project):
    async def steps(app, pilot):
        await typing("exp export csv")(app, pilot)
        app.query_one("#command").value = "y"
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert not app.query_one("#bar").has_class("-answering")

    shown = run(steps, app=failing_app())
    assert len(shown.of(ErrorLog)) == 0
    assert messages(shown)[-1] == (
        "error",
        "Failed. Would you like the error log? [y/n] ",
    )


def test_with_no_project_no_log_file_is_written(home):
    app = failing_app()

    async def steps(app, pilot):
        # A data command never runs without a project, so fail `help` instead.
        app.show_help = lambda topic: 1 / 0
        await typing("help", "y")(app, pilot)

    shown = run(steps, app=app)
    block = shown.of(ErrorLog)[0]
    assert block.file is None
    assert "ZeroDivisionError" in block.entry
    assert not (home / "data").exists()
    assert messages(shown)[-1] == (
        "error",
        "Failed. Would you like the error log? [y/n] y",
    )


# Tab completion and up-arrow history (#118, decision 0028)


def bar_value(app):
    return app.query_one("#command").value


def pop_up(app):
    """The pop-up as shown: its top border, its rows and its bottom border."""
    matches = app.query_one("#matches")
    if not matches.has_class("-open"):
        return None
    rows = matches.render().plain.splitlines()
    return (matches.border_title, rows, matches.border_subtitle)


async def type_in(pilot, *keys):
    await pilot.press(*keys)
    await pilot.pause()


def test_tab_with_several_matches_opens_the_pop_up(project):
    async def steps(app, pilot):
        await type_in(pilot, "e", "x", "tab")
        assert pop_up(app) == (
            " 2 matches ",
            ["▸ exit   Leave Synthase (or press Ctrl+D).", "  exp    Experiments"],
            " 1 of 2 ",
        )
        assert app.query_one("#bar").border_title == (
            " Tab next · Enter chooses · keep typing to narrow "
        )
        # Tab cycles round; Shift+Tab, ↑ and ↓ step too. The line is unchanged.
        await type_in(pilot, "tab")
        assert pop_up(app)[1][1] == "▸ exp    Experiments"
        assert pop_up(app)[2] == " 2 of 2 "
        await type_in(pilot, "tab")
        assert pop_up(app)[2] == " 1 of 2 "
        await type_in(pilot, "shift+tab")
        assert pop_up(app)[2] == " 2 of 2 "
        await type_in(pilot, "up")
        assert pop_up(app)[2] == " 1 of 2 "
        await type_in(pilot, "down")
        assert pop_up(app)[2] == " 2 of 2 "
        assert bar_value(app) == "ex"
        # Enter fills the line and never runs it.
        await type_in(pilot, "enter")
        assert pop_up(app) is None
        assert bar_value(app) == "exp "
        assert app.is_running

    assert messages(run(steps)) == []


def test_typing_narrows_the_pop_up(project):
    async def steps(app, pilot):
        await type_in(pilot, "e", "x", "tab", "i")
        assert pop_up(app) == (
            " 1 match ",
            ["▸ exit   Leave Synthase (or press Ctrl+D)."],
            " 1 of 1 ",
        )
        await type_in(pilot, "enter")
        assert bar_value(app) == "exit"
        assert app.is_running

    run(steps)


def test_a_word_that_matches_nothing_closes_the_pop_up(project):
    async def steps(app, pilot):
        await type_in(pilot, "e", "x", "tab", "z")
        assert pop_up(app) is None
        assert bar_value(app) == "exz"
        await type_in(pilot, "tab")
        assert pop_up(app) is None

    run(steps)


def test_ctrl_c_closes_the_pop_up_and_clears_the_line(project):
    async def steps(app, pilot):
        await type_in(pilot, "e", "x", "tab", "ctrl+c")
        assert pop_up(app) is None
        assert bar_value(app) == ""
        await type_in(pilot, "e", "x", "tab", "escape")
        assert pop_up(app) is None
        assert bar_value(app) == "ex"

    assert messages(run(steps)) == []


def test_the_pop_up_shows_eight_rows_at_a_time(project):
    app = SynthaseApp()
    app.sources["id"] = lambda words: [f"C{n:03}" for n in range(1, 13)]

    async def steps(app, pilot):
        app.query_one("#command").value = "compound edit "
        await type_in(pilot, "tab")
        title, rows, place = pop_up(app)
        assert (title, place) == (" 12 matches ", " 1 of 12 ")
        assert rows == ["▸ C001", *(f"  C{n:03}" for n in range(2, 9))]
        await type_in(pilot, *["tab"] * 8)
        title, rows, place = pop_up(app)
        assert place == " 9 of 12 "
        assert rows == [*(f"  C{n:03}" for n in range(2, 9)), "▸ C009"]
        await type_in(pilot, "enter")
        assert bar_value(app) == "compound edit C009"

    run(steps, app=app)


def test_one_match_shows_ghost_text_and_tab_takes_it(project):
    async def steps(app, pilot):
        await type_in(pilot, "h", "e", "l")
        await pilot.pause()
        command = app.query_one("#command")
        assert command.render_line(0).text.startswith("help")
        assert app.query_one("#bar").border_title == TAB_HINT == " Tab completes "
        await type_in(pilot, "tab")
        assert bar_value(app) == "help "
        assert pop_up(app) is None
        assert app.query_one("#bar").border_title == FIRST_HINT

    assert messages(run(steps)) == []


def test_a_command_with_nothing_after_it_gets_no_space(project):
    async def steps(app, pilot):
        await type_in(pilot, "e", "x", "i", "tab")
        assert bar_value(app) == "exit"

    run(steps)


# Walk-through questions (#101, decision 0030)


def walking_app(edit=False, current=None):
    """The app with `exp create` (or `exp edit`) as an invented three-question
    walk-through; ``saved`` gets the answers if it finishes."""
    app = SynthaseApp()
    app.saved = []
    current = current or {}
    questions = [
        Question("title", "Title", current=current.get("title")),
        Question("notes", "Notes", optional=True, current=current.get("notes")),
        Question("file", "File", optional=True, path=True, current=current.get("file")),
    ]
    command = "exp edit" if edit else "exp create"
    walk = Walkthrough(command, questions, app.saved.append, edit=edit)
    app.handlers[tuple(command.split())] = lambda call: app.ask(walk)
    return app


def bar_title(app):
    return Content.from_markup(app.query_one("#bar").border_title).plain


def test_a_walk_through_asks_one_question_at_a_time(project):
    async def steps(app, pilot):
        await typing("exp create")(app, pilot)
        assert app.query_one("#bar").has_class("-answering")
        assert bar_title(app) == "━ Answering exp create · Ctrl+C cancels "
        assert str(app.query_one("#prompt").render()) == "Title: "
        await typing("")(app, pilot)
        await typing("Invented title")(app, pilot)
        assert bar_title(app) == (
            "━ Answering exp create · Enter skips · Ctrl+C cancels "
        )
        assert str(app.query_one("#prompt").render()) == "Notes: "
        await typing("", '  "C:\\Lab\\run 1.csv"  ')(app, pilot)
        assert not app.query_one("#bar").has_class("-answering")
        assert app.query_one("#prompt").render().plain == "> "

    shown = run(steps, app=(app := walking_app()))
    assert app.saved == [
        {"title": "Invented title", "notes": None, "file": "C:\\Lab\\run 1.csv"}
    ]
    assert messages(shown)[1:] == [
        ("error", "An answer is needed."),
        ("normal", "Title: Invented title"),
        ("normal", "Notes:"),
        ("normal", "File: C:\\Lab\\run 1.csv"),
    ]


def test_an_edit_keeps_with_enter_and_clears_with_a_dash(project):
    current = {"title": "Old title", "notes": "Old notes", "file": "C:\\old.csv"}

    async def steps(app, pilot):
        await typing("exp edit")(app, pilot)
        assert bar_title(app) == (
            "━ Answering exp edit · Enter keeps · - clears · Ctrl+C cancels "
        )
        assert app.query_one("#command").placeholder == "Old title"
        await typing("", "-", "C:\\new.csv")(app, pilot)

    shown = run(steps, app=(app := walking_app(edit=True, current=current)))
    assert app.saved == [{"title": "Old title", "notes": None, "file": "C:\\new.csv"}]
    assert messages(shown)[1:] == [
        ("normal", "Title: Old title"),
        ("normal", "Notes:"),
        ("normal", "File: C:\\new.csv"),
    ]


def test_a_multi_line_question_ends_on_an_empty_line(project):
    app = SynthaseApp()
    saved = []
    question = Question("values", "Values", lines=True)
    walk = Walkthrough("exp create", [question], saved.append)
    app.handlers[("exp", "create")] = lambda call: app.ask(walk)

    async def steps(app, pilot):
        await typing("exp create", "mass 2.003 g")(app, pilot)
        assert bar_title(app) == (
            "━ Answering exp create · one per line · empty line ends · Ctrl+C cancels "
        )
        assert app.query_one("#bar").has_class("-answering")
        await typing("volume 5 mL", "")(app, pilot)
        assert not app.query_one("#bar").has_class("-answering")

    shown = run(steps, app=app)
    assert saved == [{"values": ["mass 2.003 g", "volume 5 mL"]}]
    assert messages(shown)[1:] == [
        ("normal", "Values: mass 2.003 g"),
        ("normal", "        volume 5 mL"),
    ]


def test_ctrl_c_cancels_and_saves_nothing(project):
    before = {f.name: f.read_bytes() for f in project.iterdir()}

    async def steps(app, pilot):
        await typing("exp create", "Invented title")(app, pilot)
        app.query_one("#command").value = "half an ans"
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert not app.query_one("#bar").has_class("-answering")
        assert app.walk is None
        assert bar_value(app) == ""

    shown = run(steps, app=(app := walking_app()))
    assert app.saved == []
    assert messages(shown)[-1] == ("cancel", "Cancelled. Nothing was saved.")
    after = {f.name: f.read_bytes() for f in project.iterdir()}
    # The command line is kept in the up-arrow history; nothing else changed.
    assert after.pop(".history") == b"exp create\n"
    assert after == before


def test_tab_and_ctrl_d_do_nothing_in_a_walk_through(project):
    async def steps(app, pilot):
        await typing("exp create")(app, pilot)
        await type_in(pilot, "e", "x", "tab", "ctrl+d")
        assert app.is_running
        assert bar_value(app) == "ex"
        assert pop_up(app) is None

    run(steps, app=walking_app())


def test_the_history_skips_answers_and_waits_in_a_walk_through(project):
    async def steps(app, pilot):
        await typing("help", "exp create")(app, pilot)
        await type_in(pilot, "up")
        assert bar_value(app) == ""
        assert app.history.step is None
        await typing("Invented title", "", "")(app, pilot)
        await type_in(pilot, "up")
        assert bar_value(app) == "exp create"

    run(steps, app=walking_app())
    assert (project / ".history").read_text("utf-8") == "help\nexp create\n"


def test_a_failure_when_saving_asks_about_the_log(project):
    app = SynthaseApp()

    def fail(answers):
        raise RuntimeError("an invented failure")

    walk = Walkthrough("exp create", [Question("title", "Title")], fail)
    app.handlers[("exp", "create")] = lambda call: app.ask(walk)

    async def steps(app, pilot):
        await typing("exp create", "Invented title")(app, pilot)
        assert bar_title(app) == (
            "━ Answering exp create · Enter means no · Ctrl+C cancels "
        )
        assert app.walk is None

    run(steps, app=app)
    assert "RuntimeError: an invented failure" in (project / "error.log").read_text()


def test_a_failing_check_asks_about_the_log(project):
    app = SynthaseApp()
    question = Question("title", "Title", check=lambda text: 1 / 0)
    walk = Walkthrough("exp create", [question], print)
    app.handlers[("exp", "create")] = lambda call: app.ask(walk)

    async def steps(app, pilot):
        await typing("exp create", "Invented title")(app, pilot)
        assert app.walk is None
        assert app.failure is not None

    run(steps, app=app)
    assert "ZeroDivisionError" in (project / "error.log").read_text()


# The older console (#119, decision 0029)


def screen(app):
    """Every line of the screen as drawn, filters included."""
    return [strip.text for strip in app.screen._compositor.render_strips()]


def test_cp437_draws_ascii_and_keeps_the_real_symbols(home, monkeypatch):
    monkeypatch.setattr(older_console, "output_encoding", lambda: "cp437")

    async def steps(app, pilot):
        app.say("success", "Done")
        app.say("normal", "2.003 g ± 0.001")
        await type_in(pilot, "e", "x", "tab")
        drawn = screen(app)
        assert "   + Done" in drawn[2]
        assert "   2.003 g +/- 0.001" in drawn[3]
        assert any("  |> exit   Leave Synthase (or press Ctrl+D)." in r for r in drawn)
        assert drawn[-4].endswith(" Tab next | Enter chooses | keep typing to narrow -")
        assert all(line.isascii() for line in drawn)

    shown = run(steps, size=(80, 14))
    # What was said keeps its symbols; only the drawing changed.
    assert messages(shown)[-1] == ("normal", "2.003 g ± 0.001")


def test_the_old_console_window_draws_ascii_and_windows_terminal_doesnt(
    home, monkeypatch
):
    with monkeypatch.context() as old_window:
        old_window.delenv("WT_SESSION")
        old_window.setattr(older_console.sys, "platform", "win32")
        assert run().app.ascii
    assert not run().app.ascii


def test_16_colours_use_the_synthase_16_theme(home, monkeypatch):
    monkeypatch.setattr(constants, "COLOR_SYSTEM", "standard")

    async def steps(app, pilot):
        assert app.theme == "synthase-16"
        await type_in(pilot, "e", "x", "tab")
        rows = app.query_one("#matches").render()
        current = rows.plain.splitlines()[0]
        reversed_text = [
            rows.plain[s.start : s.end] for s in rows.spans if "reverse" in str(s.style)
        ]
        assert reversed_text == [current]

    run(steps)


def test_full_colour_keeps_the_synthase_theme_and_no_reverse(home):
    async def steps(app, pilot):
        assert app.theme == "synthase"
        await type_in(pilot, "e", "x", "tab")
        rows = app.query_one("#matches").render()
        assert not [s for s in rows.spans if "reverse" in str(s.style)]

    run(steps)


def test_up_and_down_step_through_the_history(home):
    async def steps(app, pilot):
        await typing("help", "exp show all")(app, pilot)
        await type_in(pilot, "e", "x")
        await type_in(pilot, "up")
        assert bar_value(app) == "exp show all"
        assert app.query_one("#bar").border_title == (
            " history 1 of 2 · ↑ older · ↓ newer "
        )
        await type_in(pilot, "up", "up")
        assert bar_value(app) == "help"
        assert app.query_one("#bar").border_title == (
            " history 2 of 2 · ↑ older · ↓ newer "
        )
        await type_in(pilot, "down")
        assert bar_value(app) == "exp show all"
        # Past the newest, the line being typed comes back.
        await type_in(pilot, "down")
        assert bar_value(app) == "ex"
        assert app.query_one("#bar").border_title == ""

    run(steps)
    # With no project, nothing is written.
    assert list(home.iterdir()) == []


def test_typing_over_a_recalled_line_stops_the_stepping(home):
    async def steps(app, pilot):
        await typing("help")(app, pilot)
        await type_in(pilot, "up", "space", "e")
        assert bar_value(app) == "help e"
        assert app.history.step is None
        assert app.query_one("#bar").border_title != FIRST_HINT

    run(steps)


def test_the_history_comes_back_after_a_restart(project):
    run(typing("help", "exp show all", "exp show all", "exit"))
    assert (project / ".history").read_text("utf-8") == ("help\nexp show all\nexit\n")

    async def steps(app, pilot):
        await type_in(pilot, "up", "up")
        assert bar_value(app) == "exp show all"
        await type_in(pilot, "up")
        assert bar_value(app) == "help"
        assert app.query_one("#bar").border_title == (
            " history 3 of 3 · ↑ older · ↓ newer "
        )

    run(steps)


def test_answers_to_the_error_question_are_not_kept(project):
    run(typing("exp export csv", "y"), app=failing_app())
    assert (project / ".history").read_text("utf-8") == "exp export csv\n"


def test_another_windows_project_history_is_left_alone(project, other_process):
    (project / ".synthase.lock").write_text(str(other_process))

    async def steps(app, pilot):
        await typing("help")(app, pilot)
        await type_in(pilot, "up")
        assert bar_value(app) == "help"

    run(steps)
    assert not (project / ".history").exists()


# Projects (#102, decision 0031)


def test_project_create_makes_the_project_and_opens_it(home):
    seen = {}

    async def steps(app, pilot):
        await typing("help", "project create")(app, pilot)
        assert bar_title(app) == "━ Answering project create · Ctrl+C cancels "
        assert str(app.query_one("#prompt").render()) == "Name: "
        assert app.query_one("#command").placeholder == ""
        await typing("", "  Invented project  ")(app, pilot)
        assert not app.query_one("#bar").has_class("-answering")
        seen["lock"] = (home / "data" / ".synthase.lock").read_text()
        await typing("project show", "exp show all")(app, pilot)

    shown = run(steps, size=(200, 50))
    assert seen["lock"] == str(os.getpid())
    assert messages(shown)[3:7] == [
        ("error", "An answer is needed."),
        ("normal", "Name: Invented project"),
        (
            "success",
            f'Created project "Invented project" in the folder path: {home}',
        ),
        ("echo", "project show"),
    ]
    lines = messages(shown)[7][1].split("\n")
    assert lines[0] == "Name         Invented project"
    assert lines[1].startswith("Created      20")
    assert lines[2:] == [
        f"Folder       {home}",
        "Experiments  0",
        "Compounds    0",
    ]
    # The project is open: data commands no longer get the no-project hint.
    assert messages(shown)[-1] == ("error", "exp show all isn't built yet.")
    assert shown.status.startswith("Invented project · ")
    # The lines typed before the project existed are kept too.
    assert (home / "data" / ".history").read_text("utf-8") == (
        "help\nproject create\nproject show\nexp show all\n"
    )
    # Opening it again notices no outside edits.
    again = run()
    assert messages(again) == []
    assert again.status.startswith("Invented project · ")


def test_ctrl_c_during_project_create_leaves_the_folder_empty(home):
    async def steps(app, pilot):
        await typing("project create")(app, pilot)
        await type_in(pilot, "I", "n", "v")
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.walk is None

    shown = run(steps, size=(200, 50))
    assert messages(shown)[-1] == ("cancel", "Cancelled. Nothing was saved.")
    assert list(home.iterdir()) == []
    assert shown.status == f"{home} · › {NO_PROJECT}"


def test_project_create_in_a_project_is_refused(project):
    shown = run(typing("project create"))
    assert messages(shown)[-1] == (
        "error",
        'This folder is already the Synthase project "Invented project". '
        "To start another, run synthase in another folder.",
    )


def test_project_edit_renames_and_enter_keeps_the_name(project):
    async def steps(app, pilot):
        await typing("project edit")(app, pilot)
        assert bar_title(app) == (
            "━ Answering project edit · Enter keeps · - clears · Ctrl+C cancels "
        )
        assert app.query_one("#command").placeholder == "Invented project"
        await typing("-", "Renamed project")(app, pilot)
        await typing("project edit", "")(app, pilot)

    shown = run(steps)
    assert messages(shown) == [
        ("echo", "project edit"),
        ("error", "An answer is needed."),
        ("normal", "Name: Renamed project"),
        ("success", 'Renamed project "Invented project" to "Renamed project".'),
        ("echo", "project edit"),
        ("normal", "Name: Renamed project"),
        ("hint", "Name kept. Nothing was saved."),
    ]
    assert shown.status.startswith("Renamed project · ")
    assert 'name = "Renamed project"' in (project / "synthase.toml").read_text()
    assert [e["action"] for e in history.entries()] == [
        "create_project",
        "edit_project",
    ]
    assert messages(run()) == []


# Experiments (#104, decision 0033)

SOURCE_QUESTION = "Load starting values from a file, or enter them manually? [f/m]: "
FORMAT_LINE = (
    "Enter one value per line:  name  value  unit  [+/- uncertainty]  [# note]"
)


def stored(project):
    return tomllib.loads((project / "experiments.toml").read_text("utf-8"))


def invented_experiments():
    experiments.create("Recrystallisation trial 2", [])
    experiments.create("Second try", [])


def test_exp_create_asks_three_questions_and_opens_the_experiment(project):
    async def steps(app, pilot):
        await typing("exp create")(app, pilot)
        assert bar_title(app) == "━ Answering exp create · Ctrl+C cancels "
        assert str(app.query_one("#prompt").render()) == "Title: "
        await typing("", "Recrystallisation trial 2")(app, pilot)
        assert str(app.query_one("#prompt").render()) == SOURCE_QUESTION
        await typing("f", "x", "m")(app, pilot)
        assert bar_title(app) == (
            "━ Answering exp create · one per line · empty line ends · Ctrl+C cancels "
        )
        assert str(app.query_one("#prompt").render()) == "Values: "
        await typing(
            "m_salicylic 2.003 g +/- 0.001 # Balance B2",
            "m_crude 2.2110",
            "m_crude 2.2110 gg",
            "m_crude 2.2110 g",
            "m_crude 1 g",
            "",
        )(app, pilot)
        assert not app.query_one("#bar").has_class("-answering")
        assert app.experiment == "E001"

    shown = run(steps, size=(200, 50))
    assert messages(shown)[:-1] == [
        ("echo", "exp create"),
        ("error", "An answer is needed."),
        ("normal", "Title: Recrystallisation trial 2"),
        ("error", "Loading values from a file isn't built yet."),
        ("error", "Type f or m."),
        ("normal", SOURCE_QUESTION + "m"),
        ("normal", FORMAT_LINE),
        ("normal", "Values: m_salicylic 2.003 g +/- 0.001 # Balance B2"),
        ("error", "Each line needs a name, a value and a unit."),
        ("error", "Unknown unit 'gg'. Did you mean: g, kg?"),
        ("normal", "        m_crude 2.2110 g"),
        ("error", "m_crude is already entered in this experiment."),
    ]
    kind, text = messages(shown)[-1]
    assert kind == "success"
    assert re.fullmatch(
        r'Created E001 "Recrystallisation trial 2"  ·  '
        r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d  ·  2 values",
        text,
    )
    assert shown.status.startswith("Invented project/E001 · ")
    saved = stored(project)["E001"]
    assert saved["title"] == "Recrystallisation trial 2"
    assert saved["x_unit"] == "s"
    assert saved["values"] == {
        "m_salicylic": {
            "value": "2.003",
            "unit": "g",
            "unc": "0.001",
            "note": "Balance B2",
        },
        "m_crude": {"value": "2.2110", "unit": "g"},
    }
    assert [e["action"] for e in history.entries()] == [
        "create_project",
        "create_experiment",
        "add",
        "add",
        "issue_id",
    ]
    assert (project / ".last-experiment").read_text() == "E001\n"
    # The next start notices no outside edit.
    assert not any(kind == "notice" for kind, _ in messages(run()))


def test_exp_create_with_no_values_and_one_value(project):
    async def steps(app, pilot):
        await typing("exp create", "Empty", "m", "")(app, pilot)
        await typing("exp create", "One", "m", "m_crude 2.2110 g", "")(app, pilot)

    shown = run(steps, size=(200, 50))
    created = [text for kind, text in messages(shown) if kind == "success"]
    assert created[0].endswith("·  0 values")
    assert created[1].endswith("·  1 value")
    saved = stored(project)
    assert saved["E001"]["values"] == {}
    assert list(saved["E002"]["values"]) == ["m_crude"]
    assert shown.status.startswith("Invented project/E002 · ")


def test_ctrl_c_during_exp_create_saves_nothing_and_uses_no_id(project):
    async def steps(app, pilot):
        await typing("exp create", "Cancelled", "m", "m_crude 2.2110 g")(app, pilot)
        await type_in(pilot, "m", "_")
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert app.walk is None
        await typing("exp create", "Kept", "m", "")(app, pilot)

    shown = run(steps, size=(200, 50))
    assert ("cancel", "Cancelled. Nothing was saved.") in messages(shown)
    assert list(stored(project)) == ["E001"]
    assert stored(project)["E001"]["title"] == "Kept"
    assert messages(shown)[-1][1].startswith('Created E001 "Kept"')


def test_exp_open_by_id_or_title_shows_it_in_the_status_line(project):
    invented_experiments()

    async def steps(app, pilot):
        await typing("exp open E002")(app, pilot)
        assert app.experiment == "E002"
        await typing('exp open "Recrystallisation trial 2"')(app, pilot)
        assert app.experiment == "E001"
        await typing("exp open Second try")(app, pilot)

    shown = run(steps, size=(200, 50))
    assert messages(shown) == [
        ("echo", "exp open E002"),
        ("success", 'Opened E002 "Second try".'),
        ("echo", 'exp open "Recrystallisation trial 2"'),
        ("success", 'Opened E001 "Recrystallisation trial 2".'),
        ("echo", "exp open Second try"),
        ("success", 'Opened E002 "Second try".'),
    ]
    assert shown.status.startswith("Invented project/E002 · ")
    assert (project / ".last-experiment").read_text() == "E002\n"


def test_exp_open_refusals(project):
    shown = run(typing("exp open E001"))
    assert messages(shown)[1:] == [("error", "There are no experiments yet.")]
    invented_experiments()
    experiments.create("Second try", [])
    shown = run(
        typing("exp open E009", "exp open zzzzzz", "exp open Second try", "exp open")
    )
    assert messages(shown)[1:] == [
        ("error", "Unknown experiment 'E009'."),
        ("hint", "Did you mean: E001, E002?"),
        ("echo", "exp open zzzzzz"),
        ("error", "Unknown experiment 'zzzzzz'."),
        ("hint", "Experiments: E001, E002, E003."),
        ("echo", "exp open Second try"),
        (
            "error",
            'Several experiments are called "Second try": E002, E003. '
            "Open one by its ID.",
        ),
        ("echo", "exp open"),
        ("error", "Usage: exp open <ID or title>"),
    ]
    assert not shown.status.startswith("Invented project/")


def test_the_last_opened_experiment_opens_again_at_start(project):
    invented_experiments()
    run(typing("exp open E002"))
    again = run()
    assert messages(again) == [("hint", 'Opened E002 "Second try" from last session')]
    assert again.status.startswith("Invented project/E002 · ")


def test_a_deleted_last_experiment_opens_nothing_and_says_nothing(project):
    invented_experiments()
    run(typing("exp open E002"))
    (project / "experiments.toml").write_text("")
    history.log("external_edit", "experiments.toml")
    again = run()
    assert messages(again) == []
    assert again.status.startswith("Invented project · ")


def test_no_experiment_opens_while_another_window_holds_the_project(
    project, other_process
):
    invented_experiments()
    (project / ".last-experiment").write_text("E001\n")
    (project / ".synthase.lock").write_text(str(other_process))
    shown = run()
    assert [kind for kind, _ in messages(shown)] == ["error"]
    assert "/E001" not in shown.status


def test_tab_offers_the_experiment_ids_after_exp_show(project):
    invented_experiments()

    async def steps(app, pilot):
        app.query_one("#command").value = "exp show "
        await type_in(pilot, "tab")
        assert [match.word for match in app.matches] == ["E001", "E002", "all"]

    run(steps)
