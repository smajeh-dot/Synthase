"""fit check: the group A checks, their words, and syn fit check.

Every file here is invented or generated (see conftest.py). The expected
numbers are worked out by hand in the comments.
"""

import re

import pytest

from synthase.cli import main
from synthase.config import load_config, read_template
from synthase.fit_check import FitError, check_file, split_unit
from synthase.fit_text import count_line
from synthase.workspace import create_workspace

# No output may grade the data, judge a fit or suggest a shape.
GRADE_WORDS = (
    "good fit",
    "bad fit",
    "best model",
    "best fit",
    "grade",
    "recommend",
    "excellent",
    "poor",
)


def never(prompt):
    return False


@pytest.fixture
def workspace(tmp_path):
    return create_workspace(tmp_path / "ws", never).path


def config_with(folder, verified=False, **values):
    """A workspace config from the template, with ``values`` changed by key,
    e.g. min_distinct_x=2 for fit.min_distinct_x."""
    text = read_template()
    for name, value in values.items():
        entry = re.escape(f"[fit.{name}]")
        text = re.sub(
            rf"({entry}\nname = [^\n]*\nvalue = )[^\n]*", rf"\g<1>{value}", text
        )
    if verified:
        text = text.replace("verified = false", "verified = true")
    folder.mkdir(exist_ok=True)
    (folder / "config.toml").write_text(text, encoding="utf-8")
    return load_config(folder)


def run(tmp_path, text, config=None, **options):
    """Check ``text`` saved as data.csv, against the template's values."""
    path = tmp_path / "data.csv"
    path.write_text(text, encoding="utf-8")
    return check_file(path, config or load_config(), **options)


def finding(report, code):
    return next(f for f in report.findings if f.code == code)


def test_four_points_at_three_x_values_cant_fit_four_settings(fit_files):
    report = check_file(fit_files / "tiny.csv", load_config())
    # Worked by hand: 4 points ≤ 4 settings, and 3 different x values < 4.
    a1, a2 = report.findings[:2]
    assert (a1.level, a1.text) == ("fail", "4 points can't fit 4 settings.")
    assert a1.fix == "Measure more points, or choose a shape with fewer settings."
    assert (a2.level, a2.text) == (
        "fail",
        "Only 3 different x values. A shape with 4 settings needs at least 4.",
    )
    assert a2.fix == "Measure at more x values, or choose a shape with fewer settings."
    assert (
        finding(report, "A7").text == "3 different x values, fewer than the 5 needed."
    )
    assert report.failed
    assert (
        count_line(report.findings) == "Checks: 11 run, 7 passed, 2 flagged, 2 failed."
    )


def test_doses_a_splits_into_thirds_of_the_log_range(fit_files):
    report = check_file(fit_files / "doses-a.csv", load_config())
    assert report.heading == (
        "Checking doses-a.csv: dose (µM) against response, any shape (up to 4 settings)"
    )
    # Worked by hand: log2 of the doses runs 0 to 9 steps above 0.5, so the
    # thirds end at 4 and 32 µM. 0.5, 1, 2 | 4, 8, 16 | 32, 64, 128, 256 µM,
    # 3 repeats each: 9, 9 and 12 points.
    assert [(f.code, f.level, f.text) for f in report.findings] == [
        ("A1", "ok", "30 points for 4 settings, 7.50 per setting."),
        ("A2", "ok", "10 different dose values."),
        ("A3", "ok", "Every dose and response value is a number."),
        ("A4", "ok", "The response values vary, from 0.133 to 0.993."),
        ("A5", "ok", "Both columns have 30 values, and no row appears twice."),
        ("A6", "ok", "Every dose value is above 0."),
        ("A7", "ok", "10 different dose values, at least the 5 needed."),
        ("A8", "ok", "Thirds of the log dose range hold 9, 9 and 12 points."),
        ("A9", "ok", "No suspect points among the repeats."),
        ("A10", "flag", "No unit given for response. Tables show it without one."),
        ("A11", "info", "10 dose values with 3 repeats each."),
    ]
    assert count_line(report.findings) == "Checks: 11 run, 10 passed, 1 flagged."
    assert not report.failed


def test_a_shape_sets_the_number_of_settings(fit_files):
    report = check_file(fit_files / "tiny.csv", load_config(), shape="line")
    assert report.heading.endswith("shape line (2 settings)")
    # Worked by hand: 4 points > 2 settings, but fewer than 5 × 2 = 10.
    assert finding(report, "A1").level == "flag"
    assert finding(report, "A1").text == (
        "4 points for 2 settings is 2 per setting, fewer than 5."
    )
    assert finding(report, "A2").text == "3 different x values."
    assert finding(report, "A6").text == "The line shape can use x values of any sign."


def test_as_many_x_values_as_settings_leaves_nothing_to_check(tmp_path):
    config = config_with(tmp_path / "ws", min_distinct_x=2)
    text = "x,y\n" + "".join(f"{x},{x}\n{x},{x + 0.5}\n" for x in range(1, 5))
    report = run(tmp_path, text, config, shape="growth")
    # Worked by hand: 4 different x values, and growth has 4 settings.
    assert finding(report, "A7").level == "flag"
    assert finding(report, "A7").text == (
        "4 different x values, as many as the shape has settings, so the curve "
        "passes through every one and leaves nothing to check it against."
    )
    report = run(tmp_path, text, config, shape="line")
    assert finding(report, "A7").text == "4 different x values, at least the 2 needed."


def test_units_come_from_the_column_names_or_the_options(tmp_path):
    text = "Dose [µM],growth (OD600)\n1,0.1\n2,0.2\n"
    report = run(tmp_path, text)
    assert report.heading.startswith(
        "Checking data.csv: Dose (µM) against growth (OD600)"
    )
    assert finding(report, "A10").text == "Units: Dose in µM, growth in OD600."
    report = run(tmp_path, "dose,growth\n1,0.1\n2,0.2\n", x_unit="mM")
    assert finding(report, "A10").text == (
        "No unit given for growth. Tables show it without one."
    )
    assert "dose (mM) against growth," in report.heading
    report = run(tmp_path, "dose,growth\n1,0.1\n2,0.2\n")
    assert finding(report, "A10").text == (
        "No unit given for dose or growth. Tables show them without one."
    )


@pytest.mark.parametrize(
    ("column", "split"),
    [
        ("dose (µM)", ("dose", "µM")),
        ("temperature [K]", ("temperature", "K")),
        ("time(min)", ("time", "min")),
        ("growth", ("growth", None)),
        ("(µM)", ("(µM)", None)),
    ],
)
def test_a_unit_is_the_bracketed_end_of_a_name(column, split):
    assert split_unit(column) == split


def test_values_that_arent_numbers_are_listed_by_line(tmp_path):
    report = run(tmp_path, "x,y\n1,0.5\nn/a,0.6\n3,<0.1\n4,1e-2\n5,inf\n")
    a3 = finding(report, "A3")
    assert a3.level == "fail"
    assert a3.text == (
        '3 values aren\'t numbers: line 3 ("n/a"), line 4 ("<0.1") and line 6 ("inf").'
    )
    assert a3.fix == "Correct them in the file, or delete those rows."
    # Only the rows with two numbers are points: lines 2 and 5.
    assert finding(report, "A1").text == "2 points can't fit 4 settings."


def test_columns_of_different_lengths_fail_and_pasted_rows_are_flagged(tmp_path):
    report = run(tmp_path, "x,y\n1,0.5\n2,0.6\n3,\n4,\n")
    a5 = finding(report, "A5")
    assert a5.level == "fail"
    assert a5.text == "x has 4 values but y has 2. Lines 4 and 5 have only one."
    assert a5.fix == "Fill in the missing values, or delete those rows."
    # Line 4 is line 2 again, well and all.
    text = "x,y,well\n1,0.5,A1\n2,0.6,A2\n1,0.5,A1\n"
    a5 = finding(run(tmp_path, text, x="x", y="y"), "A5")
    assert (a5.level, a5.text) == (
        "flag",
        "Line 4 repeats an earlier line exactly. Check nothing was pasted twice.",
    )


def test_y_values_that_never_change_leave_nothing_to_fit(tmp_path):
    a4 = finding(run(tmp_path, "x,y\n1,0.5\n2,0.50\n3,0.5\n"), "A4")
    assert (a4.level, a4.text) == (
        "fail",
        "Every y value is 0.5, so there is nothing to fit.",
    )
    assert a4.fix == "Check the right column was chosen for y."


def test_x_values_at_or_below_zero(tmp_path):
    text = "x,y\n0,1\n0,1.1\n1,0.8\n2,0.6\n4,0.4\n8,0.2\n"
    report = run(tmp_path, text)
    # Worked by hand: the two points at 0 can't go on the log scale, so the
    # thirds of log 1 to log 8 (edges at 2 and 4) hold 1, 1 and 2 of the rest.
    assert finding(report, "A6").level == "flag"
    assert finding(report, "A6").text == (
        "2 x values are 0, such as an untreated control. "
        "They are left out of the log scale."
    )
    assert finding(report, "A8").text == (
        "Thirds of the log x range hold 1, 1 and 2 points (2 points at 0 left out)."
    )
    below = text.replace("0,1.1", "-1,1.1")
    report = run(tmp_path, below)
    assert finding(report, "A6").text == (
        "1 x value is below 0, so an s-curve can't be fitted."
    )
    # With a value below 0 the range can't be on a log scale.
    assert finding(report, "A8").text.startswith("Thirds of the x range hold")
    report = run(tmp_path, below, shape="s-curve")
    a6 = finding(report, "A6")
    assert (a6.level, a6.text) == (
        "fail",
        "1 x value is below 0, and the s-curve shape needs x above 0.",
    )


def test_suspect_points_are_listed_and_kept(tmp_path):
    text = "x,y\n1,0.50\n1,0.52\n1,0.90\n2,0.40\n2,0.41\n2,0.42\n4,0.2\n"
    report = run(tmp_path, text)
    # Worked by hand at x = 1: the median is 0.52 and the deviations 0.02, 0
    # and 0.38, so their median is 0.02. 0.6745 × 0.38 / 0.02 = 12.8 > 3.5,
    # while 0.6745 × 0.02 / 0.02 = 0.67 is not. At x = 2 nothing is that far.
    a9 = finding(report, "A9")
    assert a9.level == "flag"
    assert a9.text == (
        "1 suspect point among the repeats: line 4 (x 1, y 0.90). "
        "They are kept: check them against your notes."
    )
    # Never removed: all 7 points are still counted.
    assert finding(report, "A1").text.startswith("7 points for 4 settings")
    assert finding(report, "A11").text == "3 x values with 1 to 3 repeats each."


def test_values_that_share_an_x_can_be_separate_points(tmp_path):
    text = "x,y\n1,0.50\n1,0.52\n1,0.90\n2,0.4\n"
    report = run(tmp_path, text, repeats=False)
    assert finding(report, "A9").text == (
        "Values that share an x aren't repeats, so suspect points are checked "
        "after fitting."
    )
    assert finding(report, "A11").text == (
        "1 x value has more than one y value, treated as separate points, not repeats."
    )
    report = run(tmp_path, "x,y\n1,0.5\n2,0.4\n3,0.3\n")
    assert finding(report, "A9").text == (
        "Too few repeats to compare. Suspect points are checked after fitting."
    )
    assert finding(report, "A11").text == (
        "Each x value appears once, so there are no repeats."
    )


def test_thirds_short_of_points_are_flagged(tmp_path):
    text = "x,y\n" + "".join(f"{x},{x}\n" for x in (1, 2, 3, 4, 5, 6, 7, 8, 100))
    report = run(tmp_path, text, shape="line")
    # Worked by hand: thirds of 1 to 100 end at 34 and 67, so they hold 8, 0
    # and 1 of the 9 points. 0 and 1 are both below 20% of 9 (1.8).
    a8 = finding(report, "A8")
    assert (a8.level, a8.text) == (
        "flag",
        "Thirds of the x range hold 8, 0 and 1 points: 2 thirds hold less than "
        "20% of them.",
    )


def test_a_file_saved_by_excel_is_read(tmp_path):
    path = tmp_path / "excel.csv"
    text = "﻿dose (µM),response,,\r\n1,0.5,,\r\n2,0.4,,\r\n,,,\r\n"
    path.write_bytes(text.encode("utf-8"))
    report = check_file(path, load_config())
    assert report.heading.startswith("Checking excel.csv: dose (µM) against response")
    assert finding(report, "A5").text == (
        "Both columns have 2 values, and no row appears twice."
    )


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("", "data.csv is empty."),
        ("x,y\n", "data.csv has column names but no rows of values."),
        ("x;y\n1;2\n", "data.csv seems to use semicolons between values."),
        ("x\n1\n", "data.csv has only one column."),
        ("x,,y\n1,2,3\n", "Column 2 of data.csv has no name."),
        ("x,X\n1,2\n", 'Two columns of data.csv are called "X".'),
        ("x,y\n1,2,3\n", "Line 2 of data.csv has more values than there are"),
        ("a,b,c\n1,2,3\n", "data.csv has 3 columns, so say which to use with --x"),
    ],
)
def test_files_that_cant_be_read_say_why(tmp_path, content, message):
    with pytest.raises(FitError) as error:
        run(tmp_path, content)
    assert str(error.value).startswith(message)


def test_files_that_arent_there_or_arent_text(tmp_path):
    with pytest.raises(FitError, match="There's no file at"):
        check_file(tmp_path / "missing.csv", load_config())
    with pytest.raises(FitError, match="is a folder, not a file"):
        check_file(tmp_path, load_config())
    path = tmp_path / "data.csv"
    path.write_bytes("dose,réponse\n1,2\n".encode("cp1252"))
    with pytest.raises(FitError, match="isn't saved as UTF-8 text"):
        check_file(path, load_config())


def test_columns_are_chosen_by_name_ignoring_capitals_and_units(tmp_path):
    text = "well,Dose (µM),growth\nA1,1,0.5\nA2,2,0.4\n"
    report = run(tmp_path, text, x="dose", y="GROWTH")
    assert "Dose (µM) against growth" in report.heading
    report = run(tmp_path, text, x="dose (µm)", y="growth")
    assert "Dose (µM) against growth" in report.heading
    with pytest.raises(FitError) as error:
        run(tmp_path, text, x="time", y="growth")
    assert str(error.value) == (
        'There\'s no column called "time". The columns are: well, Dose (µM), growth.'
    )
    with pytest.raises(FitError, match="The x and y columns must be different"):
        run(tmp_path, text, x="growth", y="growth")
    # With two columns, naming one picks the other for the other axis.
    report = run(tmp_path, "a,b\n1,2\n3,4\n", y="a")
    assert "b against a" in report.heading


def test_a_threshold_that_isnt_a_number_is_refused(tmp_path):
    config = config_with(tmp_path / "ws", outlier_flag='"high"')
    with pytest.raises(FitError) as error:
        run(tmp_path, "x,y\n1,2\n", config)
    assert str(error.value) == (
        "[fit.outlier_flag] must be a number for fit check. "
        "Set it with config set fit.outlier_flag."
    )


def test_syn_fit_check_prints_the_report(workspace, fit_files, capsys):
    code = main(["fit", "check", str(fit_files / "tiny.csv")])
    out = capsys.readouterr().out
    assert code == 1  # a check failed
    lines = out.splitlines()
    assert lines[0] == "Checking tiny.csv: x against y, any shape (up to 4 settings)"
    assert lines[1] == ""
    assert lines[2] == "  ✗ FAIL  A1   4 points can't fit 4 settings."
    assert lines[3] == (
        "               › Fix: Measure more points, or choose a shape with fewer "
        "settings."
    )
    assert "  · info  A11  3 x values with 1 to 2 repeats each." in lines
    assert "  ✓ ok    A3   Every x and y value is a number." in lines
    assert "  ! flag  A7   3 different x values, fewer than the 5 needed." in lines
    assert lines[-3] == "Checks: 11 run, 7 passed, 2 flagged, 2 failed."
    assert lines[-2] == (
        "Warning: these checks used values not yet checked against the literature: "
        "points per setting (5), fewest different x values (5), least share of "
        "points in each third of the x range (0.2), suspect-point limit (3.5). "
        "Treat the results as provisional."
    )
    assert lines[-1] == 'Run "syn doctor" to see them.'


def test_syn_fit_check_without_a_failure_exits_0_and_verified_values_warn_not(
    workspace, fit_files, capsys
):
    config_with(workspace, verified=True)
    code = main(["fit", "check", str(fit_files / "doses-a.csv")])
    out = capsys.readouterr().out
    assert code == 0
    assert out.splitlines()[-1] == "Checks: 11 run, 10 passed, 1 flagged."
    assert "Warning" not in out


def test_syn_fit_check_options(workspace, fit_files, capsys):
    code = main(
        [
            "fit",
            "check",
            str(fit_files / "doses-a.csv"),
            "--y-unit",
            "OD600",
            "--model",
            "s-curve",
            "--no-repeats",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith(
        "Checking doses-a.csv: dose (µM) against response (OD600), shape s-curve "
        "(4 settings)\n"
    )
    assert "Units: dose in µM, response in OD600." in out
    assert "treated as separate points, not repeats." in out


def test_syn_fit_check_errors(workspace, tmp_path, capsys):
    assert main(["fit", "check", str(tmp_path / "missing.csv")]) == 1
    assert "There's no file at" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["fit", "check", "data.csv", "--model", "spline"])
    assert "invalid choice: 'spline'" in capsys.readouterr().err


def test_syn_fit_without_a_command_shows_its_help(capsys):
    assert main(["fit"]) == 0
    assert "check     check a data file is fit to have a curve fitted to it" in (
        capsys.readouterr().out
    )


def test_the_same_file_gives_byte_identical_output(workspace, fit_files, capsysbinary):
    outputs = []
    for _ in range(2):
        main(["fit", "check", str(fit_files / "doses-a.csv")])
        outputs.append(capsysbinary.readouterr().out)
    assert outputs[0] == outputs[1]
    assert outputs[0]


def test_no_output_grades_the_data(workspace, fit_files, tmp_path, capsys):
    files = [fit_files / "doses-a.csv", fit_files / "tiny.csv"]
    bad = tmp_path / "bad.csv"
    bad.write_text("x,y\n1,a\n1,0.5\n1,0.5\n1,0.5\n2,\n", encoding="utf-8")
    files.append(bad)
    for path in files:
        for model in (None, "line", "s-curve"):
            argv = ["fit", "check", str(path)]
            if model:
                argv += ["--model", model]
            main(argv)
            out = capsys.readouterr().out.lower()
            for word in GRADE_WORDS:
                assert word not in out, (path.name, model, word)
