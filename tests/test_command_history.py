"""The command history that ↑ and ↓ step through. Every line is invented."""

from synthase import command_history
from synthase.command_history import MAX_LINES, CommandHistory


def test_up_steps_back_and_down_comes_forward_to_the_draft():
    kept = CommandHistory(["help", "exp show all", "exit"])
    assert kept.newer() is None
    assert kept.older("exp") == "exit"
    assert kept.step == 1
    assert kept.older("") == "exp show all"
    assert kept.older("") == "help"
    # The oldest stays put.
    assert kept.older("") == "help"
    assert kept.step == 3
    assert kept.newer() == "exp show all"
    assert kept.newer() == "exit"
    assert kept.newer() == "exp"
    assert kept.step is None


def test_an_empty_history_gives_nothing():
    assert CommandHistory().older("help") is None


def test_the_same_line_twice_is_kept_once():
    kept = CommandHistory()
    for line in ("help", "help", "exit", "help"):
        kept.add(line)
    assert kept.lines == ["help", "exit", "help"]


def test_only_the_latest_lines_are_kept():
    kept = CommandHistory([f"help {n}" for n in range(MAX_LINES)])
    kept.add("exit")
    assert len(kept.lines) == MAX_LINES
    assert kept.lines[0] == "help 1"
    assert kept.lines[-1] == "exit"


def test_saved_lines_go_to_data_history(data):
    kept = CommandHistory(command_history.load(), saved=True)
    kept.add("help")
    kept.add("exp show all")
    assert (data / ".history").read_text("utf-8") == "help\nexp show all\n"
    assert command_history.load() == ["help", "exp show all"]


def test_unsaved_lines_write_nothing(data):
    CommandHistory().add("help")
    assert not (data / ".history").exists()


def test_a_long_history_file_is_cut_back(data):
    lines = [f"exp open E{n:03}" for n in range(MAX_LINES + 5)]
    (data / ".history").write_text("\n".join(lines) + "\n", "utf-8")
    assert command_history.load() == lines[5:]
    assert (data / ".history").read_text("utf-8").splitlines() == lines[5:]
