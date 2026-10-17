"""Tests for the workspace that `syn init` creates.

Every workspace here is made in a temporary folder. The conftest fixture points
APPDATA and the Documents folder there too.
"""

import sys
from pathlib import Path

import pytest

from synthase import workspace
from synthase.config import WORKSPACE_CONFIG_NAME, load_config, read_template
from synthase.workspace import (
    FOLDERS,
    WorkspaceError,
    check_outside_code_folder,
    code_folder,
    create_workspace,
    current_workspace,
)
from synthase.workspace import documents_folder as real_documents_folder

INVENTED_CONFIG = "# invented values the owner has checked\n"


def never_asked(prompt):
    raise AssertionError(f"asked unexpectedly: {prompt}")


def answer(reply, prompts):
    def ask(prompt):
        prompts.append(prompt)
        return reply

    return ask


def test_creates_folder_layout_and_config(tmp_path):
    result = create_workspace(tmp_path / "ws", never_asked)
    for name in FOLDERS:
        assert (tmp_path / "ws" / name).is_dir()
    config = tmp_path / "ws" / WORKSPACE_CONFIG_NAME
    assert config.read_text(encoding="utf-8") == read_template()
    assert load_config(tmp_path / "ws").path == config
    assert result.config == "copied"


def test_default_path_is_synthase_data_in_documents(tmp_path):
    result = create_workspace(None, never_asked)
    assert result.path == (tmp_path / "Documents" / "Synthase-data").resolve()
    assert (result.path / WORKSPACE_CONFIG_NAME).is_file()


def test_absolute_path_is_kept_outside_the_repo_and_read_back(tmp_path):
    create_workspace(tmp_path / "ws", never_asked)
    pointer = workspace.settings_folder() / workspace.POINTER_NAME
    assert pointer.is_relative_to(tmp_path / "AppData")
    assert not pointer.resolve().is_relative_to(code_folder())
    assert current_workspace() == (tmp_path / "ws").resolve()


def test_relative_path_is_saved_as_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    create_workspace(Path("ws"), never_asked)
    assert current_workspace().is_absolute()
    assert current_workspace() == (tmp_path / "ws").resolve()


def test_running_init_again_points_at_the_new_workspace(tmp_path):
    create_workspace(tmp_path / "old", never_asked)
    create_workspace(tmp_path / "new", never_asked)
    assert current_workspace() == (tmp_path / "new").resolve()


def test_no_workspace_yet_says_to_run_init():
    with pytest.raises(WorkspaceError, match='Run "syn init"'):
        current_workspace()


def test_moved_workspace_says_how_to_fix_it(tmp_path):
    create_workspace(tmp_path / "ws", never_asked)
    (tmp_path / "ws").rename(tmp_path / "moved")
    with pytest.raises(WorkspaceError, match="can't be found"):
        current_workspace()


@pytest.mark.parametrize("inside", [".", "data", "src/synthase/lab", ".venv/data"])
def test_path_inside_the_repo_is_refused(inside):
    target = code_folder() / inside
    existed = target.exists()
    with pytest.raises(WorkspaceError) as error:
        create_workspace(target, never_asked)
    message = str(error.value)
    assert message.startswith("Synthase can't create the workspace there:")
    assert "inside Synthase's own code folder" in message
    assert "uploaded to GitHub by mistake" in message
    assert target.exists() == existed
    with pytest.raises(WorkspaceError):
        current_workspace()


def test_code_folder_is_the_checkout():
    assert (code_folder() / "pyproject.toml").is_file()
    assert Path(workspace.__file__).resolve().is_relative_to(code_folder())


def test_folder_next_to_the_repo_is_allowed():
    # Same name with a suffix: a plain text prefix check would wrongly refuse it.
    check_outside_code_folder(Path(f"{code_folder()}-data"))


def test_path_that_is_a_file_is_refused(tmp_path):
    (tmp_path / "notes.txt").write_text("", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="is a file"):
        create_workspace(tmp_path / "notes.txt", never_asked)


def test_existing_folder_without_config_is_not_asked_about(tmp_path):
    (tmp_path / "ws" / "raw").mkdir(parents=True)
    result = create_workspace(tmp_path / "ws", never_asked)
    assert result.config == "copied"


def test_existing_workspace_asks_before_replacing_config(tmp_path):
    create_workspace(tmp_path / "ws", never_asked)
    prompts = []
    create_workspace(tmp_path / "ws", answer(False, prompts))
    assert len(prompts) == 1
    assert prompts[0].startswith(
        f"A workspace already exists at {(tmp_path / 'ws').resolve()}."
    )
    assert prompts[0].endswith("Type yes to replace it [no]: ")


def test_no_keeps_config_and_remembers_workspace(tmp_path):
    create_workspace(tmp_path / "ws", never_asked)
    config = tmp_path / "ws" / WORKSPACE_CONFIG_NAME
    config.write_text(INVENTED_CONFIG, encoding="utf-8")
    results = tmp_path / "ws" / "results"
    results.rmdir()

    result = create_workspace(tmp_path / "ws", answer(False, []))

    assert result.config == "kept"
    assert config.read_text(encoding="utf-8") == INVENTED_CONFIG
    assert results.is_dir()
    assert current_workspace() == (tmp_path / "ws").resolve()
    assert list((tmp_path / "ws").glob("config.toml.bak-*")) == []


def test_yes_backs_up_config_then_copies_template(tmp_path):
    create_workspace(tmp_path / "ws", never_asked)
    config = tmp_path / "ws" / WORKSPACE_CONFIG_NAME
    config.write_text(INVENTED_CONFIG, encoding="utf-8")

    result = create_workspace(tmp_path / "ws", answer(True, []))

    assert result.config == "replaced"
    assert config.read_text(encoding="utf-8") == read_template()
    backups = list((tmp_path / "ws").glob("config.toml.bak-*"))
    assert backups == [result.backup]
    assert result.backup.read_text(encoding="utf-8") == INVENTED_CONFIG


def test_replacing_config_leaves_data_folders_alone(tmp_path):
    create_workspace(tmp_path / "ws", never_asked)
    export = tmp_path / "ws" / "raw" / "invented-plate.csv"
    export.write_text("A1,0.5\n", encoding="utf-8")
    create_workspace(tmp_path / "ws", answer(True, []))
    assert export.read_text(encoding="utf-8") == "A1,0.5\n"


def test_backup_never_overwrites_an_earlier_backup(tmp_path, monkeypatch):
    create_workspace(tmp_path / "ws", never_asked)
    monkeypatch.setattr(workspace, "_timestamp", lambda: "20260101-120000")
    first = create_workspace(tmp_path / "ws", answer(True, [])).backup
    second = create_workspace(tmp_path / "ws", answer(True, [])).backup
    assert first != second
    assert first.is_file() and second.is_file()


@pytest.mark.skipif(sys.platform != "win32", reason="asks Windows for Documents")
def test_windows_finds_the_documents_folder():
    documents = workspace._windows_documents()
    assert documents.is_absolute()
    assert documents.is_dir()


def test_documents_falls_back_to_home_folder(monkeypatch):
    # Imported before the conftest fixture swapped it for a temporary folder.
    monkeypatch.setattr(sys, "platform", "linux")
    assert real_documents_folder() == Path.home() / "Documents"


def test_settings_folder_without_appdata(monkeypatch):
    monkeypatch.delenv("APPDATA")
    assert workspace.settings_folder() == Path.home() / ".config" / "synthase"
