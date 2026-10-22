"""Opening the folder, the status line and the error log. Every path is invented."""

from pathlib import Path

from synthase import error_log, history
from synthase.startup import (
    NO_PROJECT,
    Startup,
    open_folder,
    shorten_path,
    status_line,
)
from synthase.storage import FolderState

FOLDER = "C:\\Users\\you\\Lab\\aspirin"
HOME = "C:\\Users\\you"


def test_a_path_that_fits_is_kept():
    assert shorten_path(FOLDER, 40, HOME) == FOLDER


def test_a_long_path_shortens_home_first_then_the_middle():
    assert shorten_path(FOLDER, 20, HOME) == "~\\Lab\\aspirin"
    long = "C:\\Users\\you\\Lab\\Year 13\\Chemistry\\aspirin"
    assert shorten_path(long, 25, HOME) == "~\\Lab\\Year 13\\…\\aspirin"
    assert shorten_path(long, 12, HOME) == "~\\…\\aspirin"


def test_the_status_line_leads_with_the_context():
    startup = Startup(Path(FOLDER), FolderState.PROJECT, "Aspirin synthesis")
    line = status_line(startup, 118)
    assert line.plain == f"Aspirin synthesis · {FOLDER}"
    line = status_line(startup, 118, context="E002")
    assert line.plain == f"Aspirin synthesis/E002 · {FOLDER}"


def test_the_status_line_keeps_the_refusal_whole():
    hint = ("hint", NO_PROJECT)
    startup = Startup(Path(FOLDER), FolderState.NO_PROJECT, refusal=hint, flag=hint)
    line = status_line(startup, 78).plain
    assert line.endswith(f" · › {NO_PROJECT}")
    assert len(line) <= 78


def test_a_broken_history_line_is_refused(data):
    history.log("create_project", "synthase.toml")
    with open(data / history.FILE, "a", encoding="utf-8") as log:
        log.write("not json\n")
    startup = open_folder()
    assert startup.flag == ("error", "data\\history.jsonl has a mistake")
    assert startup.refusal[1].startswith("data\\history.jsonl has a mistake on line 2")
    assert not startup.locked


def test_the_error_log_entry(data):
    try:
        raise ValueError("an invented problem")
    except ValueError as error:
        entry = error_log.entry("exp export csv", error)
    first, versions, *rest = entry.splitlines()
    assert first.endswith("  exp export csv")
    assert versions.startswith("Synthase ") and " · Python 3.13" in versions
    assert rest[0] == "Traceback (most recent call last):"
    assert rest[-1] == "ValueError: an invented problem"
    assert error_log.write(entry) == "data\\error.log"
    assert error_log.write(entry) == "data\\error.log"
    assert (data / "error.log").read_text(encoding="utf-8") == f"{entry}\n\n" * 2


def test_only_y_or_yes_means_yes():
    assert all(map(error_log.is_yes, ["y", "Y", "yes", "YES", " yes "]))
    assert not any(map(error_log.is_yes, ["", "n", "no", "yeah", "maybe"]))
