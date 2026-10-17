import shutil
import subprocess
import sys
import sysconfig
from importlib.metadata import version

import pytest

import synthase
from synthase.cli import main
from synthase.workspace import code_folder


def test_package_version_matches_installed_metadata():
    assert synthase.__version__ == version("synthase-lab")


def test_version_prints_package_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"syn {synthase.__version__}"


def test_help_exits_cleanly_and_names_the_command(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.startswith("usage: syn")


def test_no_arguments_shows_help(capsys):
    assert main([]) == 0
    assert capsys.readouterr().out.startswith("usage: syn")


def test_running_as_module_prints_version():
    result = subprocess.run(
        [sys.executable, "-m", "synthase", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == f"syn {synthase.__version__}"


def test_installed_syn_command_prints_version():
    # pip puts the `syn` launcher in the scripts folder of the Python that runs
    # the tests: `.venv\Scripts` in a venv, but `<python>\Scripts` (not the
    # folder holding python.exe) for a plain Windows install, as on CI.
    syn = shutil.which("syn", path=sysconfig.get_path("scripts"))
    assert syn is not None, "syn is not installed: run pip install -e .[dev]"
    result = subprocess.run(
        [syn, "--version"], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == f"syn {synthase.__version__}"


def test_init_creates_workspace_and_lists_what_goes_where(tmp_path, capsys):
    assert main(["init", str(tmp_path / "ws")]) == 0
    out = capsys.readouterr().out
    assert out.startswith(
        f"Created the Synthase workspace at {(tmp_path / 'ws').resolve()}"
    )
    for name in ("raw", "maps", "results", "notebook", "config.toml"):
        assert f"  {name}" in out
    assert "Next: open config.toml and check each value against the literature." in out
    assert (tmp_path / "ws" / "config.toml").is_file()


def test_init_without_a_path_uses_documents(tmp_path, capsys):
    assert main(["init"]) == 0
    assert (tmp_path / "Documents" / "Synthase-data" / "config.toml").is_file()


def test_init_refuses_repo_folder_with_explanation(capsys):
    target = code_folder() / "lab-data"
    assert main(["init", str(target)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "inside Synthase's own code folder" in captured.err
    assert not target.exists()


@pytest.mark.parametrize("reply", ["", "n", "no", "maybe"])
def test_init_prompt_appears_and_keeps_config_unless_yes(
    tmp_path, capsys, monkeypatch, reply
):
    main(["init", str(tmp_path / "ws")])
    prompts = []
    monkeypatch.setattr(
        "builtins.input", lambda prompt: prompts.append(prompt) or reply
    )
    assert main(["init", str(tmp_path / "ws")]) == 0
    assert prompts[0].startswith("A workspace already exists at")
    assert "kept as it was" in capsys.readouterr().out


@pytest.mark.parametrize("reply", ["yes", "Y", " YES "])
def test_init_yes_replaces_config(tmp_path, capsys, monkeypatch, reply):
    main(["init", str(tmp_path / "ws")])
    monkeypatch.setattr("builtins.input", lambda prompt: reply)
    assert main(["init", str(tmp_path / "ws")]) == 0
    assert "the old one is saved as config.toml.bak-" in capsys.readouterr().out


def test_init_with_no_input_counts_as_no(tmp_path, capsys, monkeypatch):
    main(["init", str(tmp_path / "ws")])

    def no_input(prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", no_input)
    assert main(["init", str(tmp_path / "ws")]) == 0
    assert "kept as it was" in capsys.readouterr().out


def test_init_help_mentions_default_and_onedrive(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["init", "--help"])
    assert exit_info.value.code == 0
    out = " ".join(capsys.readouterr().out.split())
    assert "Default: Documents\\Synthase-data." in out
    assert "syncs to OneDrive, the workspace is backed up automatically" in out
