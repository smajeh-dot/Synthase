"""Headless tests of the full-screen app, driven by Textual's test pilot."""

import asyncio

from synthase import __version__
from synthase import app as app_module
from synthase.app import NOT_YET, UNKNOWN, Message, SynthaseApp
from synthase.cli import main
from synthase.commands import ROOT_HINT
from synthase.config import read_template
from synthase.history import FILE_NAME
from synthase.workspace import FOLDERS, remember


def invented_workspace(tmp_path, unverified):
    """A workspace whose config leaves only ``unverified`` values unchecked."""
    folder = tmp_path / "Documents" / "Synthase"
    folder.mkdir(parents=True)
    lines, seen = [], 0
    for line in read_template().splitlines(keepends=True):
        if line.strip() == "verified = false":
            seen += 1
            if seen > unverified:
                line = line.replace("false", "true")
        lines.append(line)
    (folder / "config.toml").write_text("".join(lines), encoding="utf-8")
    remember(folder)
    return folder


def run(steps, size=(120, 30)):
    """Open the app, call ``steps(app, pilot)``, and return the app afterwards."""
    app = SynthaseApp()

    async def drive():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await steps(app, pilot)
            await pilot.pause()

    asyncio.run(drive())
    return app


async def type_line(app, pilot, text):
    app.query_one("#command").value = text
    await pilot.press("enter")
    await pilot.pause()


def messages(app):
    return [(m.kind, m.text) for m in app.query(Message)]


def status_text(app):
    return str(app.query_one("#status").render())


def test_unknown_command_is_echoed_then_refused():
    async def steps(app, pilot):
        await type_line(app, pilot, "hello")
        assert messages(app) == [("echo", "hello"), ("error", UNKNOWN)]

    run(steps)


def test_quit_without_the_slash_is_unknown():
    async def steps(app, pilot):
        await type_line(app, pilot, "quit")
        assert messages(app)[-1] == ("error", UNKNOWN)
        assert app.is_running

    run(steps)


def test_an_empty_line_does_nothing():
    async def steps(app, pilot):
        await type_line(app, pilot, "   ")
        assert messages(app) == []

    run(steps)


def test_quit_closes_the_app_ignoring_spaces_and_capitals():
    async def steps(app, pilot):
        await type_line(app, pilot, " /QUIT ")

    app = run(steps)
    assert not app.is_running
    assert app.return_code == 0


def test_ctrl_q_closes_the_app():
    async def steps(app, pilot):
        await pilot.press("ctrl+q")

    assert not run(steps).is_running


def test_the_key_hint_clears_after_the_first_command():
    async def steps(app, pilot):
        assert app.query_one("#bar").border_title == app_module.FIRST_HINT
        await type_line(app, pilot, "hello")
        assert not app.query_one("#bar").border_title

    run(steps)


def test_status_line_shows_the_workspace_and_two_unverified_values(tmp_path):
    folder = invented_workspace(tmp_path, unverified=2)

    async def steps(app, pilot):
        text = status_text(app)
        assert text == f"Workspace: {folder} · ? 2 config values unverified"

    run(steps, size=(300, 30))


def test_status_line_with_no_workspace_points_to_init():
    async def steps(app, pilot):
        assert status_text(app) == "› No workspace yet. Type /init to create one."

    run(steps)


def test_the_output_keeps_only_the_latest_messages(monkeypatch):
    monkeypatch.setattr(app_module, "MAX_MESSAGES", 5)

    async def steps(app, pilot):
        for number in range(4):
            await type_line(app, pilot, f"word{number}")
        output = app.query_one("#output")
        assert len(output.children) == 5
        assert messages(app)[0] == ("error", UNKNOWN)
        assert messages(app)[-2] == ("echo", "word3")

    run(steps)


def bar(app):
    return app.query_one("#command").value


async def press_tab(app, pilot, text):
    app.query_one("#command").value = text
    await pilot.press("tab")
    await pilot.pause()


def test_up_and_down_step_through_three_commands():
    async def steps(app, pilot):
        for line in ("/one", "/two", "/three"):
            await type_line(app, pilot, line)
        seen = []
        for key in ("up", "up", "up", "up", "down", "down", "down", "down"):
            await pilot.press(key)
            seen.append(bar(app))
        assert seen == ["/three", "/two", "/one", "/one", "/two", "/three", "", ""]

    run(steps)


def test_tab_completes_commands_and_subcommands_and_keeps_the_focus():
    async def steps(app, pilot):
        await press_tab(app, pilot, "/comp")
        assert bar(app) == "/compound "
        await press_tab(app, pilot, "/compound sh")
        assert bar(app) == "/compound show "
        await press_tab(app, pilot, "/compound list --sta")
        assert bar(app) == "/compound list --status "
        assert app.focused is app.query_one("#command")
        assert messages(app) == []

    run(steps)


def test_tab_lists_several_matches_once():
    async def steps(app, pilot):
        await press_tab(app, pilot, "/compound edit")
        await pilot.press("tab")
        await pilot.pause()
        assert bar(app) == "/compound edit"
        assert messages(app) == [("hint", "edit  edit-batch")]

    run(steps)


def test_a_syn_command_not_in_the_app_yet_says_where_to_run_it():
    async def steps(app, pilot):
        await type_line(app, pilot, "/Compound show 1")
        assert messages(app)[-1] == ("error", NOT_YET.format(name="compound"))
        assert NOT_YET.format(name="compound") == (
            "/compound isn't in the app yet. For now, run syn compound in PowerShell."
        )

    run(steps)


def test_history_is_kept_in_the_workspace_between_sessions(tmp_path):
    folder = invented_workspace(tmp_path, unverified=0)

    async def first(app, pilot):
        for line in ("/one", "/two", "/quit"):
            await type_line(app, pilot, line)

    run(first)
    assert (folder / FILE_NAME).read_text(encoding="utf-8") == "/one\n/two\n/quit\n"

    async def second(app, pilot):
        for _ in range(2):
            await pilot.press("up")
        assert bar(app) == "/two"

    run(second)


def test_a_history_file_that_cant_be_saved_is_reported_once(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "history_file", lambda: tmp_path / "gone" / "x")

    async def steps(app, pilot):
        await type_line(app, pilot, "/one")
        await type_line(app, pilot, "/two")
        assert [kind for kind, _ in messages(app)][:3] == ["echo", "caution", "error"]
        cautions = [text for kind, text in messages(app) if kind == "caution"]
        assert len(cautions) == 1
        assert cautions[0].startswith("Command history couldn't be saved: ")
        await pilot.press("up")
        assert bar(app) == "/two"

    run(steps)


def test_help_lists_every_command_then_how_to_get_more():
    async def steps(app, pilot):
        await type_line(app, pilot, "/help")
        echo, rows, hint = messages(app)
        assert echo == ("echo", "/help")
        assert rows[0] == "normal"
        lines = rows[1].splitlines()
        assert [line.split()[0] for line in lines] == [
            "/init",
            "/doctor",
            "/compound",
            "/help",
            "/quit",
        ]
        assert "keep track of the project's compounds" in lines[2]
        assert hint == ("hint", ROOT_HINT)

    run(steps)


def test_help_on_compound_shows_its_description_and_subcommands():
    async def steps(app, pilot):
        await type_line(app, pilot, "/help Compound")
        _, page, hint = messages(app)
        assert page[1].startswith(
            "Keep track of the project's compounds, from idea to tested.\n\n"
        )
        assert "/compound batch  add a batch made of a compound" in page[1]
        assert hint[1].endswith("e.g. /help compound add.")

    run(steps)


def test_help_on_one_command_shows_its_options_and_wraps_at_80_columns():
    async def steps(app, pilot):
        await type_line(app, pilot, "/help compound list")
        _, page = messages(app)
        assert page[1].startswith("/compound list [--status STATUS]")
        assert "--csv FILE  also save the table as a CSV file." in page[1]
        # The help column wraps inside the window, under its own column.
        body = app.query(Message).last().query_one(".body")
        assert body.size.width < 80
        assert body.size.height > len(page[1].splitlines())

    run(steps, size=(80, 24))


def test_an_unknown_help_topic_lists_the_topics():
    async def steps(app, pilot):
        await type_line(app, pilot, "/help foo")
        assert messages(app)[-1] == (
            "error",
            'There\'s no help on "foo". Topics: init, doctor, compound, help, quit.',
        )

    run(steps)


def test_tab_completes_a_help_topic():
    async def steps(app, pilot):
        await press_tab(app, pilot, "/help co")
        assert bar(app) == "/help compound "

    run(steps)


def doctor_workspace(tmp_path, unverified):
    """An invented workspace with every folder doctor checks for."""
    folder = invented_workspace(tmp_path, unverified)
    for name in FOLDERS:
        (folder / name).mkdir()
    return folder


def shown(app, selector):
    """The text each widget matching ``selector`` shows on screen."""
    return [str(widget.render()) for widget in app.query(selector)]


def test_doctor_shows_the_same_lines_as_syn_doctor(tmp_path, capsys):
    folder = doctor_workspace(tmp_path, unverified=2)
    main(["doctor"])
    printed = [line.strip() for line in capsys.readouterr().out.splitlines()]

    async def steps(app, pilot):
        assert status_text(app).endswith("? 2 config values unverified")
        # Five more values to check, including the IR range in cm⁻¹.
        invented_workspace(tmp_path / "again", unverified=5)
        config = tmp_path / "again" / "Documents" / "Synthase" / "config.toml"
        (folder / "config.toml").write_bytes(config.read_bytes())
        remember(folder)
        await type_line(app, pilot, "/doctor")
        echo, checks, unverified, last = messages(app)
        assert echo == ("echo", "/doctor")
        lines = [line.strip() for line in checks[1].splitlines()]
        assert lines == printed[: len(lines)]
        assert lines[0] == f"Synthase {__version__} self-test"
        assert f"ok    Workspace found at {folder}" in lines
        assert shown(app, ".word") == ["ok"] * 5
        assert unverified[0] == "warning"
        assert unverified[1].startswith(
            "Unverified config values (5). Results that use them show a warning:"
        )
        values = shown(app, ".value")
        assert any("≤0.5 synergy" in value for value in values)
        assert any("1600–1650 cm⁻¹" in value for value in values)
        assert last == ("success", "All checks passed.")
        # The status line has read the config again.
        assert status_text(app).endswith("? 5 config values unverified")

    run(steps, size=(300, 40))


def test_doctor_with_config_toml_missing(tmp_path):
    folder = doctor_workspace(tmp_path, unverified=0)
    (folder / "config.toml").unlink()

    async def steps(app, pilot):
        await type_line(app, pilot, "/doctor")
        _, checks, unverified, last = messages(app)
        lines = [line.strip() for line in checks[1].splitlines()]
        assert f"FAIL  The workspace at {folder} is missing: config.toml" in lines
        assert f'Fix: run syn init "{folder}". It adds what is missing' in checks[1]
        assert "FAIL  Config not checked" in lines
        assert "Fix: get the workspace check passing first." in lines
        assert shown(app, ".word.-fail") == ["FAIL", "FAIL"]
        assert unverified == (
            "warning",
            "The unverified config values can't be listed until the config is fixed.",
        )
        assert last == ("error", "2 checks failed. Fix them, then run /doctor again.")

    run(steps)


def test_doctor_shows_fix_lines_as_plain_text(tmp_path):
    folder = doctor_workspace(tmp_path, unverified=0)
    config = folder / "config.toml"
    text = config.read_text(encoding="utf-8")
    config.write_text(
        text.replace('compounds = ""', "compounds = 'no such folder'"), encoding="utf-8"
    )

    async def steps(app, pilot):
        await type_line(app, pilot, "/doctor")
        assert any(
            '"compounds" under [folders] in' in fix for fix in shown(app, ".fix")
        )
        assert messages(app)[-2] == ("success", "Every config value has been verified.")
        assert messages(app)[-1][1].startswith(
            "1 check failed. Fix it, then run /doctor"
        )

    run(steps)
