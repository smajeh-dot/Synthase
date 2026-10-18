"""Headless tests of the full-screen app, driven by Textual's test pilot."""

import asyncio

from synthase import app as app_module
from synthase.app import UNKNOWN, Message, SynthaseApp
from synthase.config import read_template
from synthase.workspace import remember


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
