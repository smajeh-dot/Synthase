"""The fit manual (docs/fit-manual.md) says only what fit check really does.

Each example report in the manual is checked against what syn fit check prints
for the same invented file, and every command, option, shape and config value
the manual names must exist.
"""

import argparse
import re
from pathlib import Path

import pytest

from synthase.cli import build_parser, main
from synthase.config import read_template
from synthase.fit_check import THRESHOLDS
from synthase.fit_shapes import SHAPES
from synthase.workspace import create_workspace

MANUAL = Path(__file__).parent.parent / "docs" / "fit-manual.md"
GROWTH = "dose (µM),growth,note\n1,0.90,a\n2,0.80,b\n4,0.60,c\n8,0.35,d\n16,0.20,e\n"


@pytest.fixture
def text():
    return MANUAL.read_text(encoding="utf-8")


@pytest.fixture
def workspace(tmp_path):
    return create_workspace(tmp_path / "ws", lambda prompt: "").path


def printed(capsys, *argv):
    main(["fit", "check", *argv])
    return capsys.readouterr().out


def fit_check_parser():
    root = build_parser()
    top = next(
        action
        for action in root._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    fit = top.choices["fit"]
    sub = next(
        action
        for action in fit._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    return sub.choices["check"]


def test_the_manual_names_only_real_options_and_shapes(text):
    parser = fit_check_parser()
    real = {option for action in parser._actions for option in action.option_strings}
    named = set(re.findall(r"`(--[a-z-]+)(?: [A-Z]+)?`", text))
    named |= set(re.findall(r" (--[a-z-]+)", text))
    assert {"--x", "--y", "--x-unit", "--y-unit", "--model", "--no-repeats"} <= named
    assert named - {"--help", "--version"} <= real
    model = next(a for a in parser._actions if "--model" in a.option_strings)
    assert set(model.choices) == set(SHAPES)
    for shape, settings in SHAPES.items():
        assert f"| `{shape}` | {settings} |" in text


def test_the_manual_names_the_real_config_values(text):
    template = read_template()
    for key in THRESHOLDS:
        group, name = key.split(".")
        section = template.split(f"[{key}]")[1].split("\n[")[0]
        value = re.search(r"^value = (.+)$", section, re.MULTILINE).group(1)
        assert f"| `{key}` | {value} |" in text, key
    for command in ("config fit", "config set fit.min_distinct_x", "syn doctor"):
        assert command in text
    assert "syn init" not in text


def test_the_example_report_is_what_syn_prints(text, workspace, tmp_path, capsys):
    from conftest import doses_a_text

    path = tmp_path / "doses.csv"
    path.write_text(doses_a_text(), encoding="utf-8")
    output = printed(capsys, str(path))
    example = text.split("```\nChecking doses.csv")[1].split("```")[0]
    assert "Checking doses.csv" + example.splitlines()[0] == output.splitlines()[0]
    # The manual shortens the example with "...", so each row it shows must
    # appear, word for word, in what syn prints.
    shown = [line for line in example.splitlines() if line.startswith("  ")]
    assert len(shown) >= 3
    for line in shown:
        if "..." not in line:
            assert line in output.splitlines(), line
    assert "Checks: 11 run, 10 passed, 1 flagged." in example
    assert "Checks: 11 run, 10 passed, 1 flagged." in output


def test_the_worked_example_is_what_syn_prints(text, workspace, tmp_path, capsys):
    path = tmp_path / "growth.csv"
    path.write_text(GROWTH, encoding="utf-8")
    assert f"```\n{GROWTH}```" in text
    output = printed(capsys, str(path), "--x", "dose", "--y", "growth")
    for sentence in (
        "5 points for 4 settings is 1.25 per setting, fewer than 5.",
        "5 different dose values.",
        "5 different dose values, at least the 5 needed.",
        "Too few repeats to compare. Suspect points are checked after fitting.",
        "No unit given for growth.",
    ):
        assert sentence in text, sentence
        assert sentence in output, sentence
    line = printed(capsys, str(path), "--x", "dose", "--y", "growth", "--model", "line")
    assert "5 points for 2 settings is 2.50 per setting, fewer than 5." in line
    assert "5 points for 2 settings is 2.50 per setting, fewer than 5." in text


def test_the_manual_is_for_windows_and_holds_no_personal_details(text):
    assert "```powershell" in text
    for word in ("bash", "brew", "sudo", "apt ", "export "):
        assert word not in text
    assert "@" not in text
