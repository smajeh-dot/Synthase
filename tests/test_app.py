"""Headless tests of the full-screen app, driven by Textual's test pilot."""

import asyncio
import os

from synthase import __version__
from synthase import app as app_module
from synthase.app import NOT_YET, PLACEHOLDER, UNKNOWN, Message, SynthaseApp
from synthase.cli import main
from synthase.commands import ROOT_HINT
from synthase.compound_questions import add_flow
from synthase.config import read_template
from synthase.history import FILE_NAME
from synthase.workspace import FOLDERS, POINTER_NAME, remember, settings_folder


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
        assert f'Fix: run /init "{folder}". It adds what is missing' in checks[1]
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


def bar_question(app):
    return str(app.query_one("#question").render())


def answering(app):
    return app.query_one("#bar").has_class("-answering")


def test_init_in_the_app_creates_then_keeps_replaces_and_cancels(tmp_path):
    folder = (tmp_path / "Lab work" / "Synthase-data").resolve()
    config = folder / "config.toml"
    pointer = settings_folder() / POINTER_NAME
    question = (
        f"A workspace already exists at {folder}. Replace its config.toml with a "
        "fresh copy of the template? Any values you have checked will be reset "
        "(the old file is kept as config.toml.bak-…). Type yes to replace it [no]:"
    )

    async def steps(app, pilot):
        assert status_text(app) == "› No workspace yet. Type /init to create one."

        # A new folder: no question, the same words as syn init.
        await type_line(app, pilot, f'/init "{folder}"')
        assert not answering(app)
        assert messages(app)[1:] == [
            ("success", f"Created the Synthase workspace at {folder}"),
            (
                "normal",
                "raw/  plate reader exports, exactly as saved\n"
                "maps/  plate maps (which compound is in which well)\n"
                "results/  tables and figures Synthase makes\n"
                "notebook/  your notebook entries\n"
                "config.toml  every scientific value Synthase uses, all "
                "unverified for now".replace("/", os.sep),
            ),
            (
                "hint",
                "Next: open config.toml and check each value against the literature.",
            ),
            ("normal", "Synthase will use this workspace from now on."),
        ]
        assert status_text(app).endswith("? 13 config values unverified")
        assert all((folder / name).is_dir() for name in FOLDERS)
        config.write_text("# checked by hand\n" + config.read_text("utf-8"), "utf-8")
        before = config.read_text("utf-8")

        # Again, answering no: the question shows in the bar, the config is kept.
        await type_line(app, pilot, f"/init {folder}")
        assert answering(app)
        assert bar_question(app) == question
        assert app.query_one("#bar").border_title == " Answering /init · Esc cancels "
        await type_line(app, pilot, "no")
        assert not answering(app)
        assert messages(app)[-4][1] == f"{question} no"
        assert messages(app)[-3] == (
            "success",
            f"Using the existing Synthase workspace at {folder}",
        )
        assert messages(app)[-2][1].endswith("config.toml  kept as it was")
        assert config.read_text("utf-8") == before
        assert list(folder.glob("config.toml.bak-*")) == []

        # Again, answering yes: the old config is kept as a .bak copy.
        await type_line(app, pilot, f"/init {folder}")
        await type_line(app, pilot, "yes")
        backups = list(folder.glob("config.toml.bak-*"))
        assert len(backups) == 1
        assert backups[0].read_text("utf-8") == before
        assert config.read_text("utf-8") == read_template()
        assert messages(app)[-3][1].endswith(
            f"the old one is saved as {backups[0].name}"
        )

        # Once more, cancelling with Esc: nothing is saved.
        pointer.write_text("somewhere else\n", encoding="utf-8")
        await type_line(app, pilot, f"/init {folder}")
        await pilot.press("escape")
        await pilot.pause()
        assert not answering(app)
        assert messages(app)[-1] == ("cancel", "Cancelled. Nothing was changed.")
        assert pointer.read_text("utf-8") == "somewhere else\n"
        assert list(folder.glob("config.toml.bak-*")) == backups
        assert config.read_text("utf-8") == read_template()
        assert app.query_one("#command").placeholder == PLACEHOLDER

    run(steps)


def test_init_answers_only_yes_or_y_as_yes(tmp_path):
    folder = tmp_path / "ws"
    main(["init", str(folder)])

    async def steps(app, pilot):
        for reply in ["", "n", "maybe", "yes please"]:
            await type_line(app, pilot, f"/init {folder}")
            await type_line(app, pilot, reply)
        assert list(folder.glob("config.toml.bak-*")) == []
        await type_line(app, pilot, f"/init {folder}")
        await type_line(app, pilot, " Y ")
        assert len(list(folder.glob("config.toml.bak-*"))) == 1

    run(steps)


def test_init_with_no_path_uses_documents(tmp_path):
    async def steps(app, pilot):
        await type_line(app, pilot, "/init")
        folder = (tmp_path / "Documents" / "Synthase-data").resolve()
        assert messages(app)[1] == (
            "success",
            f"Created the Synthase workspace at {folder}",
        )

    run(steps)


def test_init_refusing_the_code_folder_is_an_error():
    async def steps(app, pilot):
        await type_line(app, pilot, "/init .")
        kind, text = messages(app)[-1]
        assert kind == "error"
        assert text.startswith("Synthase can't create the workspace there:")
        assert not answering(app)

    run(steps)


def test_ctrl_c_cancels_a_question(tmp_path):
    folder = tmp_path / "ws"
    main(["init", str(folder)])

    async def steps(app, pilot):
        await type_line(app, pilot, f"/init {folder}")
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert not answering(app)
        assert messages(app)[-1] == ("cancel", "Cancelled. Nothing was changed.")
        assert app.is_running

    run(steps)


def test_answers_are_not_kept_in_history_and_keys_wait(tmp_path):
    folder = invented_workspace(tmp_path, unverified=0)

    async def steps(app, pilot):
        await type_line(app, pilot, f"/init {folder}")
        app.query_one("#command").value = "/he"
        await pilot.press("tab", "up")
        assert app.query_one("#command").value == "/he"
        await type_line(app, pilot, "no")
        assert app.history.lines == [f"/init {folder}"]

    run(steps)


def test_a_shared_question_list_explains_wrong_answers_and_skips(tmp_path):
    folder = invented_workspace(tmp_path, unverified=0)
    done = []

    async def steps(app, pilot):
        app.ask("/compound add", add_flow(folder), done.append, "Nothing was added.")
        await pilot.pause()
        assert messages(app)[-1] == (
            "normal",
            "New compound. Press Enter to skip any question except the label.",
        )
        # The label can't be skipped: Enter is explained and it is asked again.
        await type_line(app, pilot, "")
        assert messages(app)[-1][0] == "error"
        assert bar_question(app) == "Label:"
        await type_line(app, pilot, "invented-1")
        assert bar_question(app).startswith("Class (")
        # A wrong class is explained and asked again; Enter then skips it.
        await type_line(app, pilot, "not a class")
        assert messages(app)[-1][0] == "error"
        assert bar_question(app).startswith("Class (")
        await type_line(app, pilot, "")
        assert bar_question(app) == "SMILES:"
        for _ in range(3):  # SMILES, status, notes
            await type_line(app, pilot, "")
        # [y/N] questions: only yes or y is yes.
        assert bar_question(app).endswith("[y/N]")
        await type_line(app, pilot, "yep")
        await type_line(app, pilot, "n")
        await type_line(app, pilot, "")
        assert not answering(app)

    run(steps)
    (answers,) = done
    assert answers["label"] == "invented-1"
    assert answers["compound_class"] is None
    assert [answers[g] for g in ("Characterisation", "Handling", "Safety")] == [
        False,
        False,
        False,
    ]


def test_answers_with_markup_characters_show_as_typed(tmp_path):
    folder = invented_workspace(tmp_path, unverified=0)

    async def steps(app, pilot):
        app.ask("/compound add", add_flow(folder), lambda answers: None, "x")
        await pilot.pause()
        await type_line(app, pilot, "[b]$x[/b]")
        shown = str(app.query(".-answered .body").last().render())
        assert shown == "Label: [b]$x[/b]"

    run(steps)


def test_esc_and_ctrl_c_do_nothing_without_a_question():
    async def steps(app, pilot):
        app.query_one("#command").value = "/he"
        await pilot.press("escape", "ctrl+c")
        await pilot.pause()
        assert messages(app) == []
        assert app.query_one("#command").value == "/he"
        assert app.is_running

    run(steps)
