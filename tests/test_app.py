"""Headless tests of the full-screen app, driven by Textual's test pilot.

Every folder, name and value is invented.
"""

import asyncio
import os
import subprocess
import sys
from dataclasses import dataclass, field

import pytest
from textual.content import Content

from synthase import __version__, history
from synthase.app import (
    FIRST_HINT,
    PLACEHOLDER,
    ErrorLog,
    HelpForms,
    HelpList,
    Message,
    SynthaseApp,
    Welcome,
)
from synthase.lock import IN_USE
from synthase.startup import FOREIGN, NO_PROJECT


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
    shown = run(typing("exp show", "project create"), size=(200, 50))
    assert messages(shown) == [
        ("hint", NO_PROJECT),
        ("echo", "exp show"),
        ("hint", NO_PROJECT),
        ("echo", "project create"),
        ("error", "project create isn't built yet."),
    ]
    assert shown.status == f"{home} · › {NO_PROJECT}"
    assert not (home / "data").exists()


def test_a_data_folder_that_isnt_synthases_is_left_alone(home):
    (home / "data").mkdir()
    (home / "data" / "results.csv").write_text("invented\n")
    shown = run(typing("help exp", "exp show"), size=(200, 50))
    assert messages(shown)[0] == ("error", FOREIGN)
    assert len(shown.of(HelpForms)) == 1
    assert messages(shown)[-1] == ("error", FOREIGN)
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
