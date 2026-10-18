import csv
import shutil
import subprocess
import sys
import sysconfig
from importlib.metadata import version

import pytest

import synthase
from synthase.cli import main
from synthase.compounds import REGISTER_NAME, Compound, list_compounds
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


# --- syn compound add, with invented compounds only ---

ADDED_A = (
    "Added SYN-001: Test compound A\n"
    "  class        chalcone\n"
    "  SMILES       CCO\n"
    "  formula      C2H6O\n"
    "  molar mass   46.1 g/mol\n"
    "  status       planned\n"
    'Add more details later with "syn compound edit SYN-001".\n'
)
CLASS_PROMPT = "Class (Schiff base, chalcone, starting material, other): "
PROMPTS = ["Label: ", CLASS_PROMPT, "SMILES: ", "Status [planned]: ", "Notes: "]


@pytest.fixture
def workspace(tmp_path, capsys):
    return make_workspace(tmp_path / "ws", capsys)


def make_workspace(path, capsys):
    assert main(["init", str(path)]) == 0
    capsys.readouterr()
    return path


def answer(monkeypatch, *replies):
    """Type ``replies`` at the prompts, then run out of input.

    Returns the list the prompts are collected in.
    """
    prompts = []
    waiting = iter(replies)

    def typed(prompt):
        prompts.append(prompt)
        reply = next(waiting, EOFError)
        if isinstance(reply, type) and issubclass(reply, BaseException):
            raise reply
        return reply

    monkeypatch.setattr("builtins.input", typed)
    return prompts


def test_compound_add_with_flags_prints_the_new_entry(workspace, capsys):
    argv = ["compound", "add", "--label", "Test compound A", "--class", "chalcone"]
    assert main([*argv, "--smiles", "CCO"]) == 0
    assert capsys.readouterr().out == ADDED_A


def test_prompts_and_flags_give_the_same_entry(tmp_path, capsys, monkeypatch):
    by_flags = make_workspace(tmp_path / "flags", capsys)
    flags = ["--label", "Test compound A", "--class", "Chalcone", "--smiles", "CCO"]
    assert main(["compound", "add", *flags, "--notes", "invented"]) == 0
    flags_out = capsys.readouterr().out

    by_prompts = make_workspace(tmp_path / "prompts", capsys)
    prompts = answer(monkeypatch, "Test compound A", "Chalcone", "CCO", "", "invented")
    assert main(["compound", "add"]) == 0
    prompts_out = capsys.readouterr().out

    assert prompts == PROMPTS
    assert list_compounds(by_prompts) == list_compounds(by_flags)
    assert prompts_out == (
        "New compound. Press Enter to skip any question except the label.\n\n"
        + flags_out
    )
    assert "  notes        invented\n" in flags_out


def test_prompts_skip_every_blank_answer_but_the_label(workspace, capsys, monkeypatch):
    answer(monkeypatch, "Test compound A", "", "", "", "")
    assert main(["compound", "add"]) == 0
    assert capsys.readouterr().out.endswith(
        "Added SYN-001: Test compound A\n"
        "  status       planned\n"
        'Add more details later with "syn compound edit SYN-001".\n'
    )
    assert list_compounds(workspace) == [Compound(1, "Test compound A")]


def test_prompts_ask_again_after_each_wrong_answer(workspace, capsys, monkeypatch):
    assert main(["compound", "add", "--label", "Test compound A"]) == 0
    capsys.readouterr()
    prompts = answer(
        monkeypatch,
        "",
        "test COMPOUND a",
        "Test compound B",
        "ketone",
        "chalcone",
        "C1CC",
        "CCO",
        "finished",
        "purified",
        "",
    )
    assert main(["compound", "add"]) == 0
    assert prompts == [
        "Label: ",
        "Label: ",
        "Label: ",
        CLASS_PROMPT,
        CLASS_PROMPT,
        "SMILES: ",
        "SMILES: ",
        "Status [planned]: ",
        "Status [planned]: ",
        "Notes: ",
    ]
    out = capsys.readouterr().out
    for message in (
        "A compound needs a label, such as a short name.",
        '"Test compound A" is already SYN-001. Choose another label.',
        '"ketone" isn\'t a compound class. Choose one of: '
        "Schiff base, chalcone, starting material, other.",
        'RDKit can\'t read the SMILES "C1CC".',
        '"finished" isn\'t a status.',
    ):
        assert message in out
    assert "Added SYN-002: Test compound B" in out
    added = list_compounds(workspace)[1]
    assert added == Compound(
        2,
        "Test compound B",
        "chalcone",
        "CCO",
        "C2H6O",
        pytest.approx(46.069, abs=0.001),
        "purified",
    )


@pytest.mark.parametrize(
    ("flags", "message"),
    [
        (["--smiles", "C1CC"], 'RDKit can\'t read the SMILES "C1CC".'),
        (["--class", "ketone"], '"ketone" isn\'t a compound class.'),
        (["--status", "finished"], '"finished" isn\'t a status.'),
        (["--label", "test compound A"], "is already SYN-001."),
    ],
)
def test_flags_with_a_wrong_answer_fail_and_save_nothing(
    workspace, capsys, flags, message
):
    assert main(["compound", "add", "--label", "Test compound A"]) == 0
    capsys.readouterr()
    argv = ["compound", "add", "--label", "Test compound B", *flags]
    assert main(argv) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert message in captured.err
    assert [c.label for c in list_compounds(workspace)] == ["Test compound A"]


def test_flags_need_a_label(workspace, capsys):
    assert main(["compound", "add", "--smiles", "CCO"]) == 1
    assert capsys.readouterr().err == (
        'Give the label with --label, or run "syn compound add" with no flags '
        "to be asked for each field.\n"
    )
    assert not (workspace / REGISTER_NAME).exists()


@pytest.mark.parametrize("stop", [EOFError, KeyboardInterrupt])
def test_stopping_partway_adds_nothing(workspace, capsys, monkeypatch, stop):
    answer(monkeypatch, "Test compound A", "chalcone", stop)
    assert main(["compound", "add"]) == 1
    assert capsys.readouterr().err == "Nothing was added.\n"
    assert not (workspace / REGISTER_NAME).exists()


def test_compound_add_without_a_workspace_says_to_run_init(capsys):
    assert main(["compound", "add", "--label", "Test compound A"]) == 1
    assert 'Run "syn init"' in capsys.readouterr().err


def test_compound_on_its_own_shows_its_help(capsys):
    assert main(["compound"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("usage: syn compound")
    assert "add a compound to the register" in out


def test_compound_help_text(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert "compound keep track of the project's compounds, from idea to tested" in out
    with pytest.raises(SystemExit):
        main(["compound", "add", "--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert (
        "Add a compound to the register. With no options, Synthase asks for each "
        "detail; press Enter to skip any but the label. With options, it asks "
        "nothing."
    ) in out


# --- syn compound show and list, with invented compounds only ---


def add_three(capsys):
    for flags in (
        ["--label", "Test compound A", "--class", "chalcone", "--smiles", "CCO"],
        ["--label", "Test compound B", "--status", "purified"],
        ["--label", "Test compound C", "--class", "chalcone", "--notes", "invented"],
    ):
        assert main(["compound", "add", *flags]) == 0
    capsys.readouterr()


TABLE = (
    "ID       Label            Class     Status    Formula  Molar mass (g/mol)\n"
    "SYN-001  Test compound A  chalcone  planned   C2H6O    46.1\n"
    "SYN-002  Test compound B  -         purified  -        -\n"
    "SYN-003  Test compound C  chalcone  planned   -        -\n"
)


def test_show_prints_the_card_then_what_is_missing(workspace, capsys):
    add_three(capsys)
    assert main(["compound", "show", "syn-1"]) == 0
    assert capsys.readouterr().out == (
        "SYN-001: Test compound A\n"
        "  class        chalcone\n"
        "  SMILES       CCO\n"
        "  formula      C2H6O\n"
        "  molar mass   46.1 g/mol\n"
        "  status       planned\n"
        "\n"
        "Still missing:\n"
        "  no notes yet\n"
    )
    assert main(["compound", "show", "2"]) == 0
    assert capsys.readouterr().out == (
        "SYN-002: Test compound B\n"
        "  status       purified\n"
        "\n"
        "Still missing:\n"
        "  no class yet\n"
        "  no SMILES yet, so no formula or molar mass\n"
        "  no notes yet\n"
    )


def test_show_says_when_nothing_is_missing(workspace, capsys):
    argv = ["compound", "add", "--label", "Test compound A", "--class", "other"]
    assert main([*argv, "--smiles", "C", "--notes", "invented"]) == 0
    capsys.readouterr()
    assert main(["compound", "show", "SYN-001"]) == 0
    out = capsys.readouterr().out
    assert "  notes        invented\n" in out
    assert out.endswith("\nNothing missing.\n")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("SYN-042", "There's no compound SYN-042 in the register."),
        ("abc", '"abc" isn\'t a compound ID. IDs look like SYN-001.'),
    ],
)
def test_show_with_an_unknown_id_fails_cleanly(workspace, capsys, text, message):
    add_three(capsys)
    assert main(["compound", "show", text]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(message)


def test_list_prints_every_compound_and_the_count(workspace, capsys):
    add_three(capsys)
    assert main(["compound", "list"]) == 0
    assert capsys.readouterr().out == TABLE + "3 compounds.\n"


@pytest.mark.parametrize(
    ("filters", "ids", "summary"),
    [
        (["--status", "planned"], ["SYN-001", "SYN-003"], "2 of 3 compounds"),
        (["--class", "Chalcone"], ["SYN-001", "SYN-003"], "2 of 3 compounds"),
        (["--status", "purified"], ["SYN-002"], "1 of 3 compounds"),
    ],
)
def test_list_filters_keep_the_right_rows(workspace, capsys, filters, ids, summary):
    add_three(capsys)
    assert main(["compound", "list", *filters]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[0] for line in lines[1:-1]] == ids
    assert lines[-1].startswith(summary)


def test_list_names_the_filters_it_used(workspace, capsys):
    add_three(capsys)
    assert main(["compound", "list", "--status", "PLANNED", "--class", "chalcone"]) == 0
    assert capsys.readouterr().out.endswith(
        "2 of 3 compounds (status: planned, class: chalcone).\n"
    )
    assert main(["compound", "list", "--status", "tested"]) == 0
    assert capsys.readouterr().out == "No compounds match (status: tested).\n"


def test_list_with_an_unknown_filter_fails(workspace, capsys):
    assert main(["compound", "list", "--class", "ketone"]) == 1
    assert "isn't a compound class" in capsys.readouterr().err


def test_list_and_show_never_create_the_register(workspace, capsys):
    assert main(["compound", "list", "--csv", str(workspace / "t.csv")]) == 0
    assert capsys.readouterr().out == (
        'The register is empty. Add a compound with "syn compound add".\n'
    )
    assert main(["compound", "show", "1"]) == 1
    assert not (workspace / REGISTER_NAME).exists()
    assert not (workspace / "t.csv").exists()


def test_csv_matches_the_table(workspace, capsys, tmp_path):
    add_three(capsys)
    saved = tmp_path / "compounds.csv"
    assert main(["compound", "list", "--csv", str(saved)]) == 0
    out = capsys.readouterr().out
    assert out.startswith(TABLE)
    assert out.endswith(f"Saved the table to {saved.resolve()}\n")
    assert saved.read_bytes().startswith(b"\xef\xbb\xbf")
    with saved.open(encoding="utf-8-sig", newline="") as file:
        table = list(csv.reader(file))
    printed = [line.split("  ") for line in TABLE.splitlines()]
    printed = [[cell.strip() for cell in line if cell.strip()] for line in printed]
    assert table == [[cell if cell != "-" else "" for cell in r] for r in printed]


def test_csv_saves_only_the_filtered_rows(workspace, capsys, tmp_path):
    add_three(capsys)
    saved = tmp_path / "purified.csv"
    assert main(["compound", "list", "--status", "purified", "--csv", str(saved)]) == 0
    with saved.open(encoding="utf-8-sig", newline="") as file:
        assert [row[0] for row in csv.reader(file)] == ["ID", "SYN-002"]


@pytest.mark.parametrize(("reply", "replaced"), [("y", True), ("", False)])
def test_csv_asks_before_replacing_a_file(
    workspace, capsys, monkeypatch, tmp_path, reply, replaced
):
    add_three(capsys)
    saved = tmp_path / "compounds.csv"
    saved.write_text("invented, keep me\n", encoding="utf-8")
    prompts = answer(monkeypatch, reply)
    assert main(["compound", "list", "--csv", str(saved)]) == 0
    assert prompts == [f"{saved} already exists. Replace it? [y/N] "]
    out = capsys.readouterr().out
    if replaced:
        assert "Saved the table to" in out
        assert "SYN-003" in saved.read_text(encoding="utf-8-sig")
    else:
        assert out.endswith(f"Kept the existing {saved}. The table was not saved.\n")
        assert saved.read_text(encoding="utf-8") == "invented, keep me\n"


def test_csv_that_cannot_be_written_fails_with_a_hint(workspace, capsys, tmp_path):
    add_three(capsys)
    assert main(["compound", "list", "--csv", str(tmp_path / "no" / "t.csv")]) == 1
    err = capsys.readouterr().err
    assert err.startswith(f"Couldn't save {tmp_path / 'no' / 't.csv'}:")
    assert "If it is open in Excel, close it and try again." in err


def test_show_and_list_help_text(capsys):
    for command, text in (
        ("show", "Show everything recorded about one compound, and what is still "),
        ("list", "List every compound in a table. Filter it with --status or "),
    ):
        with pytest.raises(SystemExit):
            main(["compound", command, "--help"])
        assert text in " ".join(capsys.readouterr().out.split())
