import io
import sys

import pytest

from synthase import doctor
from synthase.cli import main
from synthase.config import load_config
from synthase.workspace import create_workspace


def never(prompt):
    return False


@pytest.fixture
def workspace(tmp_path):
    return create_workspace(tmp_path / "ws", never).path


def run_doctor(capsys):
    code = main(["doctor"])
    return code, capsys.readouterr().out


def test_every_check_passing(workspace, capsys):
    code, out = run_doctor(capsys)
    assert code == 0
    assert out.count("  ok    ") == 4
    assert "FAIL" not in out
    assert f"  ok    Workspace found at {workspace}" in out
    assert "RDKit" in out and "(ethanol, CCO)" in out
    assert out.rstrip().endswith("All checks passed.")


def test_missing_workspace(capsys):
    code, out = run_doctor(capsys)
    assert code == 1
    assert '  FAIL  There is no workspace yet. Run "syn init" to create one.' in out
    assert (
        "  FAIL  Config not checked\n"
        "        Fix: get the workspace check passing first." in out
    )
    assert "can't be listed until the config is fixed" in out
    assert out.rstrip().endswith(
        '2 checks failed. Fix them, then run "syn doctor" again.'
    )


def test_moved_workspace(workspace, capsys):
    workspace.rename(workspace.with_name("moved"))
    code, out = run_doctor(capsys)
    assert code == 1
    assert f"  FAIL  The workspace at {workspace} can't be found." in out


def test_workspace_missing_a_folder(workspace, capsys):
    (workspace / "maps").rmdir()
    code, out = run_doctor(capsys)
    assert code == 1
    assert f"  FAIL  The workspace at {workspace} is missing: maps" in out
    assert f'Fix: run syn init "{workspace}".' in out
    # The config is still there, so it is still checked.
    assert "  ok    Config is valid" in out
    assert out.rstrip().endswith('1 check failed. Fix it, then run "syn doctor" again.')


def test_workspace_missing_its_config_is_not_replaced_by_the_template(
    workspace, capsys
):
    (workspace / "config.toml").unlink()
    code, out = run_doctor(capsys)
    assert code == 1
    assert f"  FAIL  The workspace at {workspace} is missing: config.toml" in out
    assert "  FAIL  Config not checked" in out
    assert "can't be listed until the config is fixed" in out


def test_invalid_config(workspace, capsys):
    (workspace / "config.toml").write_text("[mic.growth\n", encoding="utf-8")
    code, out = run_doctor(capsys)
    assert code == 1
    assert "  FAIL  Your config file has a problem: " in out
    assert "line 1" in out
    assert "can't be listed until the config is fixed" in out


def test_unverified_values_are_listed_with_their_source(workspace, capsys):
    code, out = run_doctor(capsys)
    assert code == 0
    config = load_config(workspace)
    assert f"Unverified config values ({len(config.keys())})." in out
    for key in config.keys():
        entry = config.get(key)
        assert f"  {key}" in out
        assert f"{entry.name}: {entry.describe()}" in out
    assert out.count("source: UNVERIFIED placeholder") == len(config.keys())


def test_verified_values_are_not_listed(workspace, capsys):
    config_file = workspace / "config.toml"
    text = config_file.read_text(encoding="utf-8")
    first = 'source = "UNVERIFIED placeholder: check against the literature"\n'
    text = text.replace(
        first + "verified = false",
        'source = "Invented test reference"\nverified = true',
        1,
    )
    config_file.write_text(text, encoding="utf-8")
    code, out = run_doctor(capsys)
    assert code == 0
    total = len(load_config(workspace).keys())
    assert f"Unverified config values ({total - 1})." in out
    assert "mic.growth_threshold" not in out
    assert "Invented test reference" not in out


def test_all_values_verified(workspace, capsys):
    config_file = workspace / "config.toml"
    text = config_file.read_text(encoding="utf-8")
    config_file.write_text(
        text.replace("verified = false", "verified = true"), encoding="utf-8"
    )
    code, out = run_doctor(capsys)
    assert code == 0
    assert "Every config value has been verified." in out
    assert "Unverified config values" not in out


def test_rdkit_missing(workspace, capsys, monkeypatch):
    # A None entry makes Python treat the module as not installed.
    monkeypatch.setitem(sys.modules, "rdkit", None)
    monkeypatch.setitem(sys.modules, "rdkit.Chem", None)
    code, out = run_doctor(capsys)
    assert code == 1
    assert "  FAIL  RDKit is not installed, or it won't load" in out
    assert "Fix: with the virtual environment switched on" in out


def test_rdkit_that_cannot_read_the_test_structure(workspace, capsys, monkeypatch):
    monkeypatch.setattr(doctor, "TEST_SMILES", "not a structure")
    code, out = run_doctor(capsys)
    assert code == 1
    assert "can't read a test structure" in out


def test_wrong_python_version():
    check = doctor.check_python((3, 12, 1))
    assert not check.passed
    assert check.text == "Python 3.12.1, but Synthase needs Python 3.13"
    assert "py -3.13 -m venv .venv" in check.fix


def test_right_python_version():
    check = doctor.check_python((3, 13, 2))
    assert check.passed
    assert check.text == "Python 3.13.2"


def test_wrong_python_version_fails_doctor(workspace, capsys, monkeypatch):
    monkeypatch.setattr(doctor, "REQUIRED_PYTHON", (3, 99))
    code, out = run_doctor(capsys)
    assert code == 1
    assert "but Synthase needs Python 3.99" in out


def test_output_saved_in_an_old_windows_character_set_does_not_crash(
    workspace, monkeypatch
):
    # PowerShell's `syn doctor > out.txt` writes cp1252, which has no ⁻ or ≤.
    saved = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", saved)
    assert main(["doctor"]) == 0
    saved.flush()
    text = saved.buffer.getvalue().decode("cp1252")
    assert "cm?¹" in text
    assert "?0.5 synergy" in text
    assert "All checks passed." in text
