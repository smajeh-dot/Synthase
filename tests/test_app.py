"""Headless tests of the full-screen app, driven by Textual's test pilot."""

import asyncio
import os
from datetime import date

from synthase import __version__
from synthase import app as app_module
from synthase.app import (
    NOT_YET,
    PLACEHOLDER,
    UNKNOWN,
    CardMessage,
    ChangeLog,
    CompoundTable,
    Fields,
    Flag,
    Message,
    SynthaseApp,
)
from synthase.cli import main
from synthase.commands import ROOT_HINT, SUBCOMMANDS_HINT
from synthase.compound_questions import add_flow
from synthase.compound_text import field_sections, section_lines
from synthase.compounds import (
    CLASSES,
    STATUSES,
    Change,
    add_batch,
    add_compound,
    archive_compound,
    compound_history,
    get_compound,
    list_compounds,
)
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
        await type_line(app, pilot, "/Compound Unlink 1")
        assert messages(app)[-1] == ("error", NOT_YET.format(name="compound unlink"))
        assert NOT_YET.format(name="compound unlink") == (
            "/compound unlink isn't in the app yet. For now, run syn compound unlink "
            "in PowerShell."
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


def test_status_line_with_config_toml_missing(tmp_path):
    folder = invented_workspace(tmp_path, unverified=2)
    (folder / "config.toml").unlink()

    async def steps(app, pilot):
        expected = f"Workspace: {folder} · ✗ config.toml has a problem, run /doctor"
        assert status_text(app) == expected
        await type_line(app, pilot, "/doctor")
        assert status_text(app) == expected

    run(steps, size=(200, 30))


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


def invented_register(tmp_path):
    """Three invented compounds: A melts over too wide a range and has a batch,
    B is archived, C is a Schiff base."""
    folder = doctor_workspace(tmp_path, unverified=13)
    add_compound(
        folder, "Test compound A", "chalcone", smiles="CCO", melting_point="455-461"
    )
    add_batch(folder, "1", date(2026, 10, 18), 0.152, 64.2)
    add_compound(folder, "Test compound B", "chalcone")
    add_compound(folder, "Test compound C", "Schiff base", status="synthesised")
    archive_compound(folder, "2")
    return folder


def test_compound_show_shows_the_card_for_any_form_of_id(tmp_path):
    invented_register(tmp_path)

    async def steps(app, pilot):
        for typed in ("SYN-001", "syn-1", "1"):
            await type_line(app, pilot, f"/compound show {typed}")
        cards = app.query(CardMessage)
        assert len(cards) == 3
        assert len({card.text for card in cards}) == 1
        assert shown(app, ".msg.-card .title")[0] == "SYN-001: Test compound A"
        assert shown(app, ".msg.-card .heading")[:2] == ["Characterisation", "Batches"]
        assert shown(app, ".msg.-card .rows.-batches .value")[0] == "64.2%"
        assert "18/10/2026" in shown(app, ".msg.-card .rows.-batches .name")
        flags = [(flag.kind, flag.text) for flag in app.query(Flag)][:4]
        assert flags[0] == (
            "caution",
            "The melting range is 6 K wide, wider than the melting-point purity "
            "rule (2 K), so the sample may not be pure.",
        )
        assert flags[1][0] == "warning"
        assert flags[1][1].startswith("Warning: melting-point purity rule")
        assert flags[2] == ("hint", "Still missing:")
        missing = shown(app, ".msg.-card .missing")
        assert missing[0] == "no notes yet"
        assert "no Rf value yet" in missing

    run(steps, size=(120, 30))


def test_compound_list_filters_and_counts_as_syn_does(tmp_path, capsys):
    invented_register(tmp_path)
    for filters in ([], ["--class", "chalcone", "--all"], ["--status", "purified"]):
        main(["compound", "list", *filters])
    printed = capsys.readouterr().out.splitlines()

    async def steps(app, pilot):
        await type_line(app, pilot, "/compound list")
        table, summary = messages(app)[-2:]
        assert table[1].splitlines()[1:] == [
            "SYN-001  Test compound A  chalcone  planned  C2H6O  46.1",
            "SYN-003  Test compound C  Schiff base  synthesised  -  -",
        ]
        assert summary == ("normal", printed[3])
        assert summary[1] == "2 compounds (1 archived, hidden; add --all to see it)."

        await type_line(app, pilot, "/compound list --class Chalcone --all")
        table, summary = messages(app)[-2:]
        assert [row.split()[0] for row in table[1].splitlines()[1:]] == [
            "SYN-001",
            "SYN-002",
        ]
        assert summary == ("normal", printed[7])
        assert summary[1] == "2 of 3 compounds (class: chalcone)."
        archived = app.query(CompoundTable).last().query(".cell.-archived")
        assert [str(cell.render()) for cell in archived][:2] == [
            "SYN-002",
            "Test compound B (archived)",
        ]

        await type_line(app, pilot, "/compound list --status purified")
        assert messages(app)[-1] == ("normal", printed[8])
        assert printed[8] == "No compounds match (status: purified)."

    run(steps, size=(80, 24))


def test_compound_history_shows_the_change_log_oldest_first(tmp_path):
    invented_register(tmp_path)

    async def steps(app, pilot):
        await type_line(app, pilot, "/compound history syn-2")
        log = app.query(ChangeLog).last()
        assert log.title == "History of SYN-002: Test compound B"
        names = [name for _, name, _ in log.rows]
        assert names == ["label", "class", "status", "archived"]
        assert log.rows[0][2] == "(blank) → Test compound B"
        assert log.rows[3][2] == "no → yes"
        today = date.today().strftime("%d/%m/%Y")
        assert all(when.startswith(today) for when, _, _ in log.rows)

    run(steps)


def test_compound_list_csv_asks_before_replacing(tmp_path):
    folder = invented_register(tmp_path)
    path = folder / "results" / "compounds.csv"

    async def steps(app, pilot):
        await type_line(app, pilot, "/compound list --csv compounds.csv")
        assert messages(app)[-1] == ("success", f"Saved the table to {path}")
        path.write_text("an older table", encoding="utf-8")

        await type_line(app, pilot, "/compound list --csv compounds.csv")
        assert bar_question(app) == f"{path} already exists. Replace it? [y/N]"
        await pilot.press("escape")
        assert messages(app)[-1] == ("cancel", "Cancelled. The table was not saved.")

        await type_line(app, pilot, "/compound list --csv compounds.csv")
        await type_line(app, pilot, "n")
        assert messages(app)[-1] == (
            "normal",
            f"Kept the existing {path}. The table was not saved.",
        )
        assert path.read_text(encoding="utf-8") == "an older table"

        await type_line(app, pilot, "/compound list --csv compounds.csv")
        await type_line(app, pilot, "yes")
        assert messages(app)[-1] == ("success", f"Saved the table to {path}")

    run(steps)
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    assert lines[0] == "ID,Label,Class,Status,Formula,Molar mass (g/mol)"
    assert lines[1:] == [
        "SYN-001,Test compound A,chalcone,planned,C2H6O,46.1",
        "SYN-003,Test compound C,Schiff base,synthesised,,",
    ]


def test_compound_list_csv_path_in_quotes_keeps_backslashes(tmp_path):
    folder = invented_register(tmp_path)
    (folder / "results" / "June tables").mkdir()
    path = folder / "results" / "June tables" / "list.csv"

    async def steps(app, pilot):
        await type_line(app, pilot, f'/compound list --csv "{path}"')
        assert messages(app)[-1] == ("success", f"Saved the table to {path}")

    run(steps)
    assert path.is_file()


def test_compound_errors_match_syn(tmp_path, capsys):
    invented_register(tmp_path)
    for argv in (["show", "9"], ["show", "nine"], ["list", "--status", "nonsense"]):
        main(["compound", *argv])
    errors = capsys.readouterr().err.splitlines()

    async def steps(app, pilot):
        await type_line(app, pilot, "/compound show 9")
        assert messages(app)[-1] == (
            "error",
            errors[0].replace('"syn compound list"', '"/compound list"'),
        )
        assert messages(app)[-1][1] == (
            'There\'s no compound SYN-009 in the register. Run "/compound list" '
            "to see every ID."
        )
        await type_line(app, pilot, "/compound history nine")
        assert messages(app)[-1] == ("error", errors[1])
        await type_line(app, pilot, "/compound list --status nonsense")
        assert messages(app)[-1] == ("error", errors[2])

        await type_line(app, pilot, "/compound show")
        assert messages(app)[-2:] == [
            ("error", "the following arguments are required: ID"),
            ("hint", "Type /help compound show to see how it's used."),
        ]
        await type_line(app, pilot, "/compound list --csv")
        assert messages(app)[-2][1] == "argument --csv: expected one argument"
        await type_line(app, pilot, '/compound list --csv "open')
        assert messages(app)[-1] == ("error", "a quote isn't closed")

        await type_line(app, pilot, "/compound")
        assert messages(app)[-1] == (
            "hint",
            SUBCOMMANDS_HINT.format(name="compound", first="compound add"),
        )
        await type_line(app, pilot, "/compound frob")
        assert messages(app)[-1] == ("error", UNKNOWN)
        assert app.is_running

    run(steps)


def test_an_empty_register_says_how_to_add_one(tmp_path):
    doctor_workspace(tmp_path, unverified=13)

    async def steps(app, pilot):
        await type_line(app, pilot, "/compound list")
        assert messages(app)[-1] == (
            "normal",
            'The register is empty. Add a compound with "/compound add".',
        )

    run(steps)


def test_compound_without_a_workspace_points_to_init():
    async def steps(app, pilot):
        await type_line(app, pilot, "/compound list")
        assert messages(app)[-1] == (
            "error",
            'There is no workspace yet. Run "/init" to create one.',
        )

    run(steps)


async def answer_each(app, pilot, answers):
    """Type each answer in turn, checking the bar asks ``question`` first."""
    for question, typed in answers:
        assert bar_question(app) == question
        await type_line(app, pilot, typed)


def test_compound_add_by_answering_the_questions(tmp_path):
    folder = invented_workspace(tmp_path, unverified=0)

    async def steps(app, pilot):
        await type_line(app, pilot, "/compound add")
        assert answering(app)
        assert app.query_one("#bar").border_title == (
            " Answering /compound add · Esc cancels "
        )
        await answer_each(
            app,
            pilot,
            [
                ("Label:", "Test compound A"),
                (f"Class ({', '.join(CLASSES)}):", "Chalcone"),
                ("SMILES:", "C1CC"),
            ],
        )
        # A SMILES that can't be read is explained and asked again.
        assert messages(app)[-1][0] == "error"
        await answer_each(
            app,
            pilot,
            [
                ("SMILES:", "CCO"),
                ("Status [planned]:", ""),
                ("Notes:", ""),
                ("Add characterisation details (melting point, Rf)? [y/N]", "y"),
                ("Melting range in K (e.g. 455-457):", "455-457"),
                ("Rf (0 to 1):", ""),
                (
                    "Add handling details (appearance, colour, solubility, DMSO "
                    "stock, storage)? [y/N]",
                    "n",
                ),
                ("Add safety details (risk assessment, hazards)? [y/N]", ""),
            ],
        )
        assert not answering(app)
        compound = get_compound(folder, "1")
        assert messages(app)[-3:] == [
            ("success", "Added SYN-001: Test compound A"),
            ("normal", "\n".join(section_lines(field_sections(compound, folder)))),
            ("hint", 'Add more details later with "/compound edit SYN-001".'),
        ]
        assert "melting point" in shown(app, ".-card .name")

    run(steps)
    compound = get_compound(folder, "1")
    assert (compound.compound_class, compound.smiles, compound.formula) == (
        "chalcone",
        "CCO",
        "C2H6O",
    )
    _, changes = compound_history(folder, "1")
    assert [(c.field, c.old, c.new) for c in changes] == [
        ("label", None, "Test compound A"),
        ("class", None, "chalcone"),
        ("smiles", None, "CCO"),
        ("status", None, "planned"),
        ("melting_point", None, "455–457 K"),
    ]


def test_compound_add_cancelled_adds_nothing(tmp_path):
    folder = invented_workspace(tmp_path, unverified=0)

    async def steps(app, pilot):
        await type_line(app, pilot, "/compound add")
        await type_line(app, pilot, "Test compound A")
        await pilot.press("escape")
        await pilot.pause()
        assert messages(app)[-1] == ("cancel", "Cancelled. Nothing was added.")

    run(steps)
    assert list_compounds(folder, archived=True) == []


def test_compound_add_with_options_asks_nothing_and_matches_syn(tmp_path, capsys):
    folder = invented_workspace(tmp_path, unverified=0)
    added = []

    async def steps(app, pilot):
        await type_line(
            app, pilot, '/compound add --label "Test compound B" --smiles CCO'
        )
        assert not answering(app)
        added.extend(text for _, text in messages(app)[-3:])
        await type_line(app, pilot, "/compound add --smiles CCO")
        assert messages(app)[-1] == (
            "error",
            'Give the label with --label, or run "/compound add" with no flags '
            "to be asked for each field.",
        )
        await type_line(app, pilot, "/compound add --label x --mp 999-1")
        assert messages(app)[-1][0] == "error"

    run(steps)
    main(["compound", "add", "--label", "Test compound C", "--smiles", "CCO"])
    printed = capsys.readouterr().out.rstrip("\n")
    expected = (
        printed.replace("SYN-002", "SYN-001")
        .replace("Test compound C", "Test compound B")
        .replace('"syn compound edit', '"/compound edit')
    )
    assert "\n".join(added) == expected
    assert [c.label for c in list_compounds(folder)] == [
        "Test compound B",
        "Test compound C",
    ]


def test_compound_edit_by_answering_asks_before_each_change(tmp_path):
    folder = invented_workspace(tmp_path, unverified=0)
    add_compound(folder, "Test compound A", "chalcone", smiles="CCO")

    async def steps(app, pilot):
        await type_line(app, pilot, "/compound edit syn-1")
        assert app.query_one("#bar").border_title == (
            " Answering /compound edit · Esc cancels "
        )
        assert messages(app)[-1] == (
            "normal",
            "Editing SYN-001: Test compound A. Press Enter to keep a value, "
            "or type - to clear it.",
        )
        await answer_each(
            app,
            pilot,
            [
                ("Label [Test compound A]:", ""),
                (f"Class ({', '.join(CLASSES)}) [chalcone]:", ""),
                ("SMILES [CCO]:", "CCN"),
                (f"Status ({', '.join(STATUSES)}) [planned]:", "purified"),
                ("Notes:", "invented note"),
                ("Edit characterisation details (melting point, Rf)? [y/N]", ""),
                (
                    "Edit handling details (appearance, colour, solubility, DMSO "
                    "stock, storage)? [y/N]",
                    "",
                ),
                ("Edit safety details (risk assessment, hazards)? [y/N]", ""),
                ('Change the SMILES from "CCO" to "CCN"? [y/N]', "no"),
            ],
        )
        assert messages(app)[-1] == ("normal", 'Kept the SMILES as "CCO".')
        await answer_each(
            app,
            pilot,
            [('Change the status from "planned" to "purified"? [y/N]', "yes")],
        )
        assert not answering(app)
        compound = get_compound(folder, "1")
        assert messages(app)[-2:] == [
            ("success", "Saved 2 changes to SYN-001: Test compound A"),
            ("normal", "\n".join(section_lines(field_sections(compound, folder)))),
        ]
        assert isinstance(app.query(Message).last(), Fields)

    run(steps)
    compound = get_compound(folder, "1")
    assert (compound.smiles, compound.status, compound.notes) == (
        "CCO",
        "purified",
        "invented note",
    )
    _, changes = compound_history(folder, "1")
    assert changes[-2:] == [
        Change("status", "planned", "purified", changes[-2].changed),
        Change("notes", None, "invented note", changes[-1].changed),
    ]


def test_compound_edit_with_options_asks_only_confirmations(tmp_path):
    folder = invented_workspace(tmp_path, unverified=0)
    add_compound(folder, "Test compound A", smiles="CCO")

    async def steps(app, pilot):
        # Filling a blank value asks nothing.
        await type_line(app, pilot, "/compound edit SYN-001 --mp 455-457")
        assert not answering(app)
        assert messages(app)[-2][1] == "Saved 1 change to SYN-001: Test compound A"
        # Changing a set one asks; Esc cancels and changes nothing.
        await type_line(app, pilot, "/compound edit SYN-001 --mp 450-452 --notes x")
        assert bar_question(app) == (
            'Change the melting point from "455–457 K" to "450–452 K"? [y/N]'
        )
        await pilot.press("escape")
        await pilot.pause()
        assert messages(app)[-1] == ("cancel", "Cancelled. Nothing was changed.")
        # A no keeps it, and with nothing else to change nothing is saved.
        await type_line(app, pilot, "/compound edit 1 --smiles -")
        await answer_each(app, pilot, [('Clear the SMILES ("CCO")? [y/N]', "")])
        assert messages(app)[-2:] == [
            ("normal", 'Kept the SMILES as "CCO".'),
            ("normal", "Nothing was changed."),
        ]
        await type_line(app, pilot, "/compound edit 1 --rf 0.4")
        assert messages(app)[-1][1].startswith("An Rf value needs the solvent system")
        await type_line(app, pilot, "/compound edit 9 --notes x")
        assert messages(app)[-1][1].endswith('Run "/compound list" to see every ID.')
        assert not answering(app)

    run(steps)
    compound = get_compound(folder, "1")
    assert (compound.smiles, compound.notes) == ("CCO", None)
    assert str(compound.melting_point) == "455–457 K"
    assert len(compound_history(folder, "1")[1]) == 4


def test_compound_archive_asks_first_and_restore_does_not(tmp_path):
    folder = invented_workspace(tmp_path, unverified=0)
    add_compound(folder, "Test compound A")
    question = (
        "Archive SYN-001 (Test compound A)? It stays in the register but is "
        'hidden from "/compound list". [y/N]'
    )

    async def steps(app, pilot):
        await type_line(app, pilot, "/compound archive 1")
        assert app.query_one("#bar").border_title == (
            " Answering /compound archive · Esc cancels "
        )
        await answer_each(app, pilot, [(question, "")])
        assert messages(app)[-1] == ("normal", "Kept SYN-001 as it was.")
        await type_line(app, pilot, "/compound archive 1")
        await pilot.press("escape")
        await pilot.pause()
        assert messages(app)[-1] == ("cancel", "Cancelled. Nothing was changed.")
        assert not get_compound(folder, "1").archived
        await type_line(app, pilot, "/compound archive SYN-001")
        await answer_each(app, pilot, [(question, "y")])
        assert messages(app)[-1] == (
            "success",
            'Archived SYN-001: Test compound A. Undo with "/compound restore SYN-001".',
        )
        await type_line(app, pilot, "/compound archive 1")
        assert messages(app)[-1] == ("error", "SYN-001 is already archived.")
        await type_line(app, pilot, "/compound restore 1")
        assert not answering(app)
        assert messages(app)[-1] == (
            "success",
            'Restored SYN-001: Test compound A. It shows in "/compound list" again.',
        )
        await type_line(app, pilot, "/compound restore 1")
        assert messages(app)[-1] == (
            "error",
            "SYN-001 isn't archived, so there's nothing to restore.",
        )

    run(steps)
    _, changes = compound_history(folder, "1")
    assert [(c.field, c.old, c.new) for c in changes[-2:]] == [
        ("archived", "no", "yes"),
        ("archived", "yes", "no"),
    ]


def test_compound_batch_by_answering_and_with_options(tmp_path):
    folder = invented_workspace(tmp_path, unverified=0)
    add_compound(folder, "Test compound A")
    today = date.today().strftime("%d/%m/%Y")

    async def steps(app, pilot):
        await type_line(app, pilot, "/compound batch 1")
        assert messages(app)[-1] == (
            "normal",
            "New batch of SYN-001: Test compound A. Press Enter for today's date, "
            "or to skip the mass or the yield.",
        )
        await answer_each(
            app,
            pilot,
            [
                ("Date made (e.g. 18/10/2026):", ""),
                ("Mass made (e.g. 152 mg):", ""),
                ("Yield in % (e.g. 64.2):", ""),
            ],
        )
        # Neither a mass nor a yield is explained, and the yield is asked again.
        assert messages(app)[-1] == (
            "error",
            "A batch needs its mass made, its yield or both.",
        )
        await answer_each(app, pilot, [("Yield in % (e.g. 64.2):", "104")])
        assert not answering(app)
        assert messages(app)[-4:] == [
            ("success", "Added batch 1 to SYN-001: Test compound A"),
            ("normal", f"1  {today}  -  104%"),
            (
                "caution",
                "A yield over 100% usually means the product is still wet or impure.",
            ),
            (
                "hint",
                'SYN-001 is still "planned". Change it with '
                '"/compound edit SYN-001 --status synthesised".',
            ),
        ]
        assert shown(app, ".rows.-batches .name")[-3:] == ["1", today, "-"]
        await type_line(app, pilot, "/compound batch 1")
        await pilot.press("escape")
        await pilot.pause()
        assert messages(app)[-1] == ("cancel", "Cancelled. Nothing was added.")
        await type_line(app, pilot, "/compound edit 1 --status synthesised")
        await type_line(app, pilot, "y")
        await type_line(
            app,
            pilot,
            '/compound batch 1 --date 2026-10-18 --mass "152 mg" --yield 64.2',
        )
        assert not answering(app)
        assert messages(app)[-2:] == [
            ("success", "Added batch 2 to SYN-001: Test compound A"),
            ("normal", "2  18/10/2026  152 mg  64.2%"),
        ]
        await type_line(app, pilot, "/compound batch 1 --mass 152")
        assert messages(app)[-1] == (
            "error",
            "Give the unit as well, mg or g, such as 152 mg.",
        )

    run(steps)
    _, changes = compound_history(folder, "1")
    assert [c.new for c in changes if c.field == "batch"] == [
        f"1: {date.today().isoformat()}, 104%",
        "2: 2026-10-18, 152 mg, 64.2%",
    ]


def test_compound_edit_batch_asks_before_each_change(tmp_path):
    folder = invented_workspace(tmp_path, unverified=0)
    add_compound(folder, "Test compound A")
    add_batch(folder, "1", date(2026, 10, 18), 0.152, 64.2)

    async def steps(app, pilot):
        await type_line(app, pilot, "/compound edit-batch 1 1")
        assert messages(app)[-1] == (
            "normal",
            "Editing batch 1 of SYN-001: Test compound A. Press Enter to keep a "
            "value, or type - to clear the mass or yield.",
        )
        await answer_each(
            app,
            pilot,
            [
                ("Date made [18/10/2026]:", "17/10/2026"),
                ("Mass made [152 mg]:", "125 mg"),
                ("Yield in % [64.2%]:", "-"),
                (
                    'Change batch 1\'s date from "18/10/2026" to "17/10/2026"? [y/N]',
                    "n",
                ),
            ],
        )
        assert messages(app)[-1] == ("normal", 'Kept batch 1\'s date as "18/10/2026".')
        await answer_each(
            app,
            pilot,
            [
                ('Change batch 1\'s mass from "152 mg" to "125 mg"? [y/N]', "y"),
                ('Clear batch 1\'s yield ("64.2%")? [y/N]', "yes"),
            ],
        )
        assert not answering(app)
        assert messages(app)[-2:] == [
            ("success", "Saved 2 changes to batch 1 of SYN-001: Test compound A"),
            ("normal", "1  18/10/2026  125 mg  -"),
        ]
        # Filling a blank value asks nothing.
        await type_line(app, pilot, "/compound edit-batch SYN-001 1 --yield 50")
        assert not answering(app)
        assert messages(app)[-2][1] == (
            "Saved 1 change to batch 1 of SYN-001: Test compound A"
        )
        # Clearing both is refused before anything is asked.
        await type_line(app, pilot, "/compound edit-batch 1 1 --mass - --yield -")
        assert not answering(app)
        assert messages(app)[-1] == (
            "error",
            "A batch needs its mass made, its yield or both.",
        )
        await type_line(app, pilot, "/compound edit-batch 1 1 --mass 1")
        assert messages(app)[-1][0] == "error"
        await type_line(app, pilot, "/compound edit-batch 1 1 --mass 99mg")
        await pilot.press("ctrl+c")
        await pilot.pause()
        assert messages(app)[-1] == ("cancel", "Cancelled. Nothing was changed.")
        await type_line(app, pilot, "/compound edit-batch 1 4 --mass 99mg")
        assert messages(app)[-1] == (
            "error",
            "SYN-001 has no batch 4. Its batches are 1.",
        )

    run(steps)
    _, changes = compound_history(folder, "1")
    assert [(c.field, c.old, c.new) for c in changes[-3:]] == [
        ("batch 1 mass", "152 mg", "125 mg"),
        ("batch 1 yield", "64.2%", None),
        ("batch 1 yield", None, "50.0%"),
    ]


def test_compound_remove_batch_asks_first_and_keeps_the_numbers(tmp_path):
    folder = invented_workspace(tmp_path, unverified=0)
    add_compound(folder, "Test compound A", status="synthesised")
    add_batch(folder, "1", date(2026, 10, 18), 0.152, 64.2)
    add_batch(folder, "1", date(2026, 10, 18), 0.140, 50.0)
    question = (
        "Remove batch 2 of SYN-001 (18/10/2026, 140 mg, 50.0%)? It is hidden from "
        "the card but kept in the history, and the other batches keep their "
        "numbers. [y/N]"
    )

    async def steps(app, pilot):
        await type_line(app, pilot, "/compound remove-batch 1 2")
        await answer_each(app, pilot, [(question, "no")])
        assert messages(app)[-1] == ("normal", "Kept batch 2 of SYN-001 as it was.")
        await type_line(app, pilot, "/compound remove-batch 1 2")
        await answer_each(app, pilot, [(question, "y")])
        assert messages(app)[-1] == (
            "success",
            "Removed batch 2 from SYN-001: Test compound A. "
            'It stays in "/compound history SYN-001".',
        )
        await type_line(app, pilot, "/compound remove-batch 1 2")
        assert messages(app)[-1][1].startswith("Batch 2 of SYN-001 was removed on ")
        await type_line(app, pilot, "/compound batch 1 --mass 99mg")
        assert messages(app)[-2][1] == "Added batch 3 to SYN-001: Test compound A"
        await type_line(app, pilot, "/compound show 1")
        assert shown(app, "CardMessage .rows.-batches .name")[::3] == ["1", "3"]

    run(steps)
