"""The words fit check shows, in syn and in the app.

fit_check.py works out each finding; this module turns the numbers into words.
Like compound_text.py, nothing here prints anything, so the two always say the
same thing. The checks and their wording are in
docs/decisions/0019-fit-check.md. No line ever grades the data or recommends a
shape: the report only counts.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from synthase.config import ConfigValue
from synthase.numbers import sig_figs

# Each level's symbol and word. The words carry the meaning, so it never
# depends on colour (decision 0016).
LEVELS = {
    "ok": ("✓", "ok"),
    "flag": ("!", "flag"),
    "fail": ("✗", "FAIL"),
    "info": ("·", "info"),
}
# How many listed lines or points a row names before "and N more".
MOST_LISTED = 5

NO_FILE = "There's no file at {path}."
NOT_A_FILE = "{path} is a folder, not a file."
NOT_READABLE = "{path} can't be read: {reason}."
NOT_UTF8 = (
    "{name} isn't saved as UTF-8 text. In Excel, save it as CSV UTF-8 (comma "
    "delimited)."
)
EMPTY_FILE = "{name} is empty."
NO_ROWS = "{name} has column names but no rows of values."
SEMICOLONS = (
    "{name} seems to use semicolons between values. Synthase reads commas only: "
    "in Excel, save it as CSV UTF-8 (comma delimited)."
)
ONE_COLUMN = "{name} has only one column. It needs an x column and a y column."
BLANK_NAME = "Column {number} of {name} has no name. Give every column a name."
SAME_NAME = 'Two columns of {name} are called "{column}". Give each a different name.'
LONG_ROW = "Line {line} of {name} has more values than there are column names."
NO_COLUMN = 'There\'s no column called "{column}". The columns are: {columns}.'
SAME_COLUMN = "The x and y columns must be different."
WHICH_COLUMNS = (
    "{name} has {count} columns, so say which to use with --x and --y. "
    "The columns are: {columns}."
)
NOT_A_NUMBER = "[{key}] must be a number for fit check. Set it with config set {key}."

FIX_POINTS = "Measure more points, or choose a shape with fewer settings."
FIX_X_VALUES = "Measure at more {x} values, or choose a shape with fewer settings."
FIX_NUMBERS = "Correct them in the file, or delete those rows."
FIX_SPREAD = "Check the right column was chosen for y."
FIX_LENGTHS = "Fill in the missing values, or delete those rows."
FIX_BELOW_ZERO = "Check the {x} values, or choose a shape that allows them below 0."


@dataclass(frozen=True)
class Finding:
    """One check's result: its code, level, text and, for a FAIL, the fix."""

    code: str
    level: str  # "ok", "flag", "fail" or "info"
    text: str
    fix: str = ""

    @property
    def word(self) -> str:
        """The symbol and word, such as "✓ ok"."""
        return " ".join(LEVELS[self.level])


def number(value: float) -> str:
    """A worked-out number: a whole number as it is, otherwise to 3 s.f."""
    return str(int(value)) if float(value).is_integer() else sig_figs(value)


def listed(items: list[str]) -> str:
    """``items`` joined as "a, b and c", naming at most MOST_LISTED of them."""
    shown = items[:MOST_LISTED]
    extra = len(items) - len(shown)
    if extra:
        return ", ".join(shown) + f" and {extra} more"
    if len(shown) == 1:
        return shown[0]
    return ", ".join(shown[:-1]) + f" and {shown[-1]}"


def plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def column_label(name: str, unit: str | None) -> str:
    return f"{name} ({unit})" if unit else name


def heading(file: str, x: str, y: str, shape: str | None, settings: int) -> str:
    """The report's first line, naming the file, the columns and the shape."""
    if shape is None:
        chosen = f"any shape (up to {settings} settings)"
    else:
        chosen = f"shape {shape} ({settings} settings)"
    return f"Checking {file}: {x} against {y}, {chosen}"


def a1_points(points: int, settings: int, least: float) -> Finding:
    per = number(points / settings)
    if points <= settings:
        text = f"{points} points can't fit {settings} settings."
        return Finding("A1", "fail", text, FIX_POINTS)
    if points < least * settings:
        text = (
            f"{points} points for {settings} settings is {per} per setting, "
            f"fewer than {number(least)}."
        )
        return Finding("A1", "flag", text)
    text = f"{points} points for {settings} settings, {per} per setting."
    return Finding("A1", "ok", text)


def a2_distinct(distinct: int, settings: int, x: str) -> Finding:
    if distinct < settings:
        text = (
            f"Only {distinct} different {x} values. A shape with {settings} "
            f"settings needs at least {settings}."
        )
        return Finding("A2", "fail", text, FIX_X_VALUES.format(x=x))
    return Finding("A2", "ok", f"{distinct} different {x} values.")


def a3_numbers(bad: list[tuple[int, str]], x: str, y: str) -> Finding:
    if bad:
        cells = [f'line {line} ("{text}")' for line, text in bad]
        text = f"{plural(len(bad), "value isn't a number", "values aren't numbers")}: "
        return Finding("A3", "fail", text + listed(cells) + ".", FIX_NUMBERS)
    return Finding("A3", "ok", f"Every {x} and {y} value is a number.")


def a4_spread(lowest: str | None, highest: str | None, y: str) -> Finding:
    if lowest is None:
        text = f"There are no {y} values to compare."
        return Finding("A4", "fail", text, FIX_SPREAD)
    if lowest == highest:
        text = f"Every {y} value is {lowest}, so there is nothing to fit."
        return Finding("A4", "fail", text, FIX_SPREAD)
    return Finding("A4", "ok", f"The {y} values vary, from {lowest} to {highest}.")


def a5_rows(
    x_count: int, y_count: int, one_only: list[int], repeated: list[int], x: str, y: str
) -> Finding:
    if x_count != y_count:
        lines = listed([str(line) for line in one_only])
        text = (
            f"{x} has {x_count} values but {y} has {y_count}. "
            f"{'Line' if len(one_only) == 1 else 'Lines'} {lines} "
            f"{'has' if len(one_only) == 1 else 'have'} only one."
        )
        return Finding("A5", "fail", text, FIX_LENGTHS)
    if repeated:
        lines = listed([str(line) for line in repeated])
        one = len(repeated) == 1
        verb = "repeats an earlier line" if one else "repeat earlier lines"
        text = (
            f"{'Line' if one else 'Lines'} {lines} {verb} exactly. "
            "Check nothing was pasted twice."
        )
        return Finding("A5", "flag", text)
    text = f"Both columns have {x_count} values, and no row appears twice."
    return Finding("A5", "ok", text)


def a6_sign(
    below: int, zeros: int, needs_log: bool, shape: str | None, x: str
) -> Finding:
    if not needs_log:
        return Finding("A6", "ok", f"The {shape} shape can use {x} values of any sign.")
    if below and shape is not None:
        text = (
            f"{plural(below, f'{x} value is', f'{x} values are')} below 0, "
            f"and the {shape} shape needs {x} above 0."
        )
        return Finding("A6", "fail", text, FIX_BELOW_ZERO.format(x=x))
    if below:
        text = (
            f"{plural(below, f'{x} value is', f'{x} values are')} below 0, "
            "so an s-curve can't be fitted."
        )
        return Finding("A6", "flag", text)
    if zeros:
        text = (
            f"{plural(zeros, f'{x} value is', f'{x} values are')} 0, such as an "
            "untreated control. They are left out of the log scale."
        )
        return Finding("A6", "flag", text)
    return Finding("A6", "ok", f"Every {x} value is above 0.")


def a7_enough_x(distinct: int, settings: int, least: float, x: str) -> Finding:
    values = plural(distinct, f"different {x} value", f"different {x} values")
    if distinct < least:
        text = f"{values}, fewer than the {number(least)} needed."
        return Finding("A7", "flag", text)
    if distinct == settings:
        text = (
            f"{values}, as many as the shape has settings, so the curve passes "
            "through every one and leaves nothing to check it against."
        )
        return Finding("A7", "flag", text)
    return Finding("A7", "ok", f"{values}, at least the {number(least)} needed.")


def a8_thirds(
    counts: list[int] | None, log: bool, left_out: int, least: float, x: str
) -> Finding:
    if counts is not None and not counts:
        return Finding("A8", "flag", f"There are no points to place in the {x} range.")
    if counts is None:
        text = f"Every point has the same {x}, so there is no range to divide."
        return Finding("A8", "flag", text)
    scale = "log " if log else ""
    held = ", ".join(str(count) for count in counts[:-1]) + f" and {counts[-1]}"
    text = f"Thirds of the {scale}{x} range hold {held} points"
    if left_out:
        text += f" ({plural(left_out, 'point', 'points')} at 0 left out)"
    total = sum(counts)
    short = sum(count < least * total for count in counts)
    if short:
        thirds = plural(short, "third holds", "thirds hold")
        share = number(least * 100)
        return Finding("A8", "flag", f"{text}: {thirds} less than {share}% of them.")
    return Finding("A8", "ok", text + ".")


def a9_suspects(
    suspects: list[tuple[int, str, str]] | None, repeats: bool, x: str, y: str
) -> Finding:
    if not repeats:
        text = (
            f"Values that share an {x} aren't repeats, so suspect points are "
            "checked after fitting."
        )
        return Finding("A9", "ok", text)
    if suspects is None:
        text = "Too few repeats to compare. Suspect points are checked after fitting."
        return Finding("A9", "ok", text)
    if suspects:
        points = [f"line {line} ({x} {xv}, {y} {yv})" for line, xv, yv in suspects]
        text = (
            f"{plural(len(suspects), 'suspect point', 'suspect points')} among the "
            f"repeats: {listed(points)}. They are kept: check them against your notes."
        )
        return Finding("A9", "flag", text)
    return Finding("A9", "ok", "No suspect points among the repeats.")


def a10_units(x: str, x_unit: str | None, y: str, y_unit: str | None) -> Finding:
    missing = [name for name, unit in ((x, x_unit), (y, y_unit)) if not unit]
    if len(missing) == 2:
        text = f"No unit given for {x} or {y}. Tables show them without one."
        return Finding("A10", "flag", text)
    if missing:
        text = f"No unit given for {missing[0]}. Tables show it without one."
        return Finding("A10", "flag", text)
    return Finding("A10", "ok", f"Units: {x} in {x_unit}, {y} in {y_unit}.")


def a11_repeats(per_x: list[int], repeats: bool, x: str, y: str) -> Finding:
    values = plural(len(per_x), f"{x} value", f"{x} values")
    if not per_x or max(per_x) == 1:
        text = f"Each {x} value appears once, so there are no repeats."
    elif not repeats:
        shared = sum(count > 1 for count in per_x)
        has = "has" if shared == 1 else "have"
        text = (
            f"{plural(shared, f'{x} value', f'{x} values')} {has} more than one "
            f"{y} value, treated as separate points, not repeats."
        )
    elif min(per_x) == max(per_x):
        text = f"{values} with {per_x[0]} repeats each."
    else:
        text = f"{values} with {min(per_x)} to {max(per_x)} repeats each."
    return Finding("A11", "info", text)


def count_line(findings: Iterable[Finding]) -> str:
    """How many checks ran and how each came out. Counts only, never a grade."""
    findings = list(findings)
    flagged = sum(f.level == "flag" for f in findings)
    failed = sum(f.level == "fail" for f in findings)
    passed = len(findings) - flagged - failed
    parts = [f"{len(findings)} run", f"{passed} passed"]
    if flagged:
        parts.append(f"{flagged} flagged")
    if failed:
        parts.append(f"{failed} failed")
    return "Checks: " + ", ".join(parts) + "."


def unverified_warning(used: Iterable[ConfigValue]) -> str:
    """The one warning naming every unverified threshold the checks used."""
    values = [
        f"{entry.name} ({entry.value_text()})" for entry in used if not entry.verified
    ]
    if not values:
        return ""
    return (
        "Warning: these checks used values not yet checked against the "
        f"literature: {', '.join(values)}. Treat the results as provisional."
    )


SEE_THRESHOLDS_SYN = 'Run "syn doctor" to see them.'
SEE_THRESHOLDS_APP = "See them with config fit."
