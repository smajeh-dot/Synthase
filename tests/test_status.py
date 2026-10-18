from pathlib import Path

from textual.content import Content

from synthase.config import read_template
from synthase.status import Status, read_status, shorten_path, status_markup
from synthase.workspace import remember

HOME = r"C:\Users\you"


def test_read_status_without_a_workspace():
    assert read_status() == Status("none")


def test_read_status_when_the_workspace_has_moved(tmp_path):
    remember(tmp_path / "gone")
    assert read_status() == Status("moved")


def test_read_status_with_a_broken_config(tmp_path):
    (tmp_path / "config.toml").write_text("[mic\n", encoding="utf-8")
    remember(tmp_path)
    assert read_status() == Status("problem", tmp_path)


def test_read_status_without_config_toml(tmp_path):
    # Not the template's values: decision 0010 never silently uses the template.
    remember(tmp_path)
    assert read_status() == Status("problem", tmp_path)


def test_read_status_counts_unverified_values(tmp_path):
    (tmp_path / "config.toml").write_text(read_template(), encoding="utf-8")
    remember(tmp_path)
    status = read_status()
    assert status.kind == "found"
    assert status.unverified > 0  # the template's values are all unverified


def plain(status, width=120):
    """The status line as it reads on screen."""
    return Content.from_markup(status_markup(status, width)).plain


def found(count, path=r"C:\Users\you\Documents\Synthase"):
    return Status("found", Path(path), count)


def test_status_wording_for_each_count():
    start = r"Workspace: C:\Users\you\Documents\Synthase · "
    assert plain(found(2)) == start + "? 2 config values unverified"
    assert plain(found(1)) == start + "? 1 config value unverified"
    assert plain(found(0)) == start + "✓ all config values verified"


def test_status_wording_for_a_config_problem(tmp_path):
    text = plain(Status("problem", tmp_path), width=400)
    assert text == f"Workspace: {tmp_path} · ✗ config.toml has a problem, run /doctor"


def test_status_wording_when_the_workspace_has_moved():
    assert plain(Status("moved")) == "! Workspace not found. Type /init to choose it."


def test_a_path_that_fits_is_kept_whole():
    path = r"C:\Users\you\Documents\Synthase"
    assert shorten_path(path, 40, HOME) == path


def test_the_home_folder_becomes_a_tilde_first():
    path = r"C:\Users\you\OneDrive\Documents\Synthase"
    assert shorten_path(path, 35, HOME) == r"~\OneDrive\Documents\Synthase"


def test_middle_folders_become_an_ellipsis_next():
    path = r"C:\Users\you\OneDrive - Personal\Documents\Lab work\Synthase"
    shorter = r"~\OneDrive - Personal\…\Synthase"
    assert shorten_path(path, len(shorter), HOME) == shorter


def test_only_the_last_folder_is_kept_when_nothing_else_fits():
    path = r"C:\Users\you\OneDrive - Personal\Documents\Lab work\Synthase"
    assert shorten_path(path, 5, HOME) == r"~\…\Synthase"
