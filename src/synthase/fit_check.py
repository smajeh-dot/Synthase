"""fit check: whether a data file is fit to have a curve fitted to it.

Reads a CSV with the standard library only, then works out the group A checks,
A1 to A11. Nothing is fitted, saved or printed, and no point is ever removed:
fit_text.py turns each finding into words. The checks are described in
docs/decisions/0019-fit-check.md.
"""

import csv
import io
import math
import re
import statistics
from dataclasses import dataclass
from pathlib import Path

from synthase.config import Config, ConfigValue
from synthase.fit_shapes import LOG_X_SHAPES, MOST_SETTINGS, SHAPES
from synthase.fit_text import (
    BLANK_NAME,
    EMPTY_FILE,
    LONG_ROW,
    NO_COLUMN,
    NO_FILE,
    NO_ROWS,
    NOT_A_FILE,
    NOT_A_NUMBER,
    NOT_READABLE,
    NOT_UTF8,
    ONE_COLUMN,
    SAME_COLUMN,
    SAME_NAME,
    SEMICOLONS,
    WHICH_COLUMNS,
    Finding,
    a1_points,
    a2_distinct,
    a3_numbers,
    a4_spread,
    a5_rows,
    a6_sign,
    a7_enough_x,
    a8_thirds,
    a9_suspects,
    a10_units,
    a11_repeats,
    column_label,
    heading,
)

# The config values the checks use, in the order the warning names them.
THRESHOLDS = (
    "fit.min_points_per_setting",
    "fit.min_distinct_x",
    "fit.coverage_min_fraction",
    "fit.outlier_flag",
)
# A plain decimal number, such as 12, -0.5, .25 or 1.5e-3.
NUMBER = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?")
# A unit in brackets at the end of a column name, such as "dose (µM)".
UNIT = re.compile(r"(.+?)\s*[(\[]([^()\[\]]+)[)\]]")
# A robust z-score divides by the median absolute deviation over this, so that
# it matches a standard deviation for normally spread values: the upper
# quartile of the standard normal distribution, about 0.6745.
MAD_SCALE = statistics.NormalDist().inv_cdf(0.75)
# Repeats needed at one x before its points can be compared with each other.
LEAST_REPEATS = 3


class FitError(Exception):
    """A file or a choice fit check can't use, with a message saying why."""


@dataclass(frozen=True)
class Table:
    """A CSV file's column names, and each row of values with its line number."""

    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple[int, tuple[str, ...]], ...]


@dataclass(frozen=True)
class Point:
    line: int
    x: float
    y: float
    x_text: str
    y_text: str


@dataclass(frozen=True)
class Report:
    """The heading, one finding per check, and the config values they used."""

    heading: str
    findings: tuple[Finding, ...]
    used: tuple[ConfigValue, ...]

    @property
    def failed(self) -> bool:
        return any(finding.level == "fail" for finding in self.findings)


def read_table(path: Path) -> Table:
    """The file at ``path`` read as a comma-separated table with a header row.

    Raises FitError if it can't be read that way.
    """
    if not path.exists():
        raise FitError(NO_FILE.format(path=path))
    if path.is_dir():
        raise FitError(NOT_A_FILE.format(path=path))
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise FitError(
            NOT_READABLE.format(path=path, reason=error.strerror or error)
        ) from None
    try:
        # utf-8-sig also reads Excel's "CSV UTF-8", which starts with a BOM.
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise FitError(NOT_UTF8.format(name=path.name)) from None
    reader = csv.reader(io.StringIO(text, newline=""))
    header: list[str] | None = None
    rows = []
    for cells in reader:
        cells = [cell.strip() for cell in cells]
        if not any(cells):
            continue
        if header is None:
            header = cells
            # Excel can leave empty columns after the last name.
            while header and not header[-1]:
                header.pop()
            continue
        rows.append((reader.line_num, cells))
    if header is None:
        raise FitError(EMPTY_FILE.format(name=path.name))
    _check_header(header, path.name)
    width = len(header)
    table_rows = []
    for line, cells in rows:
        if any(cells[width:]):
            raise FitError(LONG_ROW.format(line=line, name=path.name))
        padded = (cells + [""] * width)[:width]
        table_rows.append((line, tuple(padded)))
    if not table_rows:
        raise FitError(NO_ROWS.format(name=path.name))
    return Table(path.name, tuple(header), tuple(table_rows))


def _check_header(header: list[str], name: str) -> None:
    if len(header) == 1:
        message = SEMICOLONS if ";" in header[0] else ONE_COLUMN
        raise FitError(message.format(name=name))
    seen: set[str] = set()
    for number, column in enumerate(header, start=1):
        if not column:
            raise FitError(BLANK_NAME.format(number=number, name=name))
        if column.lower() in seen:
            raise FitError(SAME_NAME.format(name=name, column=column))
        seen.add(column.lower())


def split_unit(column: str) -> tuple[str, str | None]:
    """A column name and the unit in brackets at its end, if it has one."""
    match = UNIT.fullmatch(column)
    if match is None:
        return column, None
    return match.group(1), match.group(2).strip()


def find_column(table: Table, typed: str) -> int:
    """The column ``typed`` names, by its full name or its name without the unit.

    Capitals are ignored.
    """
    wanted = typed.strip().lower()
    for index, column in enumerate(table.columns):
        if wanted in (column.lower(), split_unit(column)[0].lower()):
            return index
    raise FitError(NO_COLUMN.format(column=typed, columns=", ".join(table.columns)))


def choose_columns(table: Table, x: str | None, y: str | None) -> tuple[int, int]:
    """The x and y columns: as given, or the only two when the file has two."""
    if (x is None or y is None) and len(table.columns) != 2:
        raise FitError(
            WHICH_COLUMNS.format(
                name=table.name,
                count=len(table.columns),
                columns=", ".join(table.columns),
            )
        )
    x_index = 0 if x is None else find_column(table, x)
    if y is None:
        y_index = 1 - x_index
    else:
        y_index = find_column(table, y)
    if x is None and y is not None:
        x_index = 1 - y_index
    if x_index == y_index:
        raise FitError(SAME_COLUMN)
    return x_index, y_index


def shares_x(table: Table, x_index: int, y_index: int) -> bool:
    """Whether any x value has more than one y value, among the numeric points."""
    seen: set[float] = set()
    for _, cells in table.rows:
        x, y = read_number(cells[x_index]), read_number(cells[y_index])
        if x is None or y is None:
            continue
        if x in seen:
            return True
        seen.add(x)
    return False


def thresholds(config: Config) -> dict[str, ConfigValue]:
    """The four fit values, each checked to be a number."""
    values = {}
    for key in THRESHOLDS:
        entry = config.get(key)
        if isinstance(entry.value, bool) or not isinstance(entry.value, int | float):
            raise FitError(NOT_A_NUMBER.format(key=key))
        values[key] = entry
    return values


def read_number(text: str) -> float | None:
    """``text`` as a number, or None if it isn't a plain decimal number."""
    if not NUMBER.fullmatch(text):
        return None
    value = float(text)
    return value if math.isfinite(value) else None


def check_file(
    path: Path,
    config: Config,
    x: str | None = None,
    y: str | None = None,
    x_unit: str | None = None,
    y_unit: str | None = None,
    repeats: bool | None = None,
    shape: str | None = None,
) -> Report:
    """Run checks A1 to A11 on the file at ``path``.

    ``repeats`` says whether y values that share an x are repeats of one
    measurement; None means yes. ``shape`` is a name from SHAPES, or None for
    any shape. Raises FitError if the file or a choice can't be used.
    """
    limits = thresholds(config)
    table = read_table(path)
    x_index, y_index = choose_columns(table, x, y)
    x_name, x_found = split_unit(table.columns[x_index])
    y_name, y_found = split_unit(table.columns[y_index])
    x_unit = x_unit or x_found
    y_unit = y_unit or y_found
    repeats = repeats is not False
    settings = SHAPES[shape] if shape else MOST_SETTINGS

    points: list[Point] = []
    bad: list[tuple[int, str]] = []
    one_only: list[int] = []
    x_count = y_count = 0
    seen: set[tuple[str, ...]] = set()
    repeated: list[int] = []
    for line, cells in table.rows:
        x_text, y_text = cells[x_index], cells[y_index]
        x_count += bool(x_text)
        y_count += bool(y_text)
        if bool(x_text) != bool(y_text):
            one_only.append(line)
        x_value, y_value = read_number(x_text), read_number(y_text)
        for text, value in ((x_text, x_value), (y_text, y_value)):
            if text and value is None:
                bad.append((line, text))
        if x_value is not None and y_value is not None:
            points.append(Point(line, x_value, y_value, x_text, y_text))
        if cells in seen:
            repeated.append(line)
        seen.add(cells)

    groups: dict[float, list[Point]] = {}
    for point in points:
        groups.setdefault(point.x, []).append(point)
    distinct = len(groups)
    needs_log = shape is None or shape in LOG_X_SHAPES
    below = sum(point.x < 0 for point in points)
    zeros = sum(point.x == 0 for point in points)
    least_points = limits["fit.min_points_per_setting"].value
    least_x = limits["fit.min_distinct_x"].value
    least_share = limits["fit.coverage_min_fraction"].value
    outlier = limits["fit.outlier_flag"].value

    findings = (
        a1_points(len(points), settings, least_points),
        a2_distinct(distinct, settings, x_name),
        a3_numbers(bad, x_name, y_name),
        a4_spread(*_lowest_highest(points), y_name),
        a5_rows(x_count, y_count, one_only, repeated, x_name, y_name),
        a6_sign(below, zeros, needs_log, shape, x_name),
        a7_enough_x(distinct, settings, least_x, x_name),
        a8_thirds(*_thirds(points, needs_log and not below), least_share, x_name),
        a9_suspects(
            _suspects(groups, outlier) if repeats else None, repeats, x_name, y_name
        ),
        a10_units(x_name, x_unit, y_name, y_unit),
        a11_repeats([len(group) for group in groups.values()], repeats, x_name, y_name),
    )
    title = heading(
        table.name,
        column_label(x_name, x_unit),
        column_label(y_name, y_unit),
        shape,
        settings,
    )
    return Report(title, findings, tuple(limits.values()))


def _lowest_highest(points: list[Point]) -> tuple[str | None, str | None]:
    """The lowest and highest y as typed, the same text if every y is equal."""
    if not points:
        return None, None
    lowest = min(points, key=lambda point: point.y)
    highest = max(points, key=lambda point: point.y)
    if lowest.y == highest.y:
        return lowest.y_text, lowest.y_text
    return lowest.y_text, highest.y_text


def _thirds(points: list[Point], log: bool) -> tuple[list[int] | None, bool, int]:
    """How many points fall in each third of the x range, the scale, and how
    many points at 0 were left out of a log scale.

    The counts are None when every point has the same x. On a log scale points
    at 0 can't be placed, so they are left out. A point on the edge between two
    thirds goes in the upper one, so a doubling series splits as hand-worked.
    """
    used = [point for point in points if point.x > 0] if log else list(points)
    left_out = len(points) - len(used)
    if not used:
        return [], log, left_out
    place = [math.log10(point.x) if log else point.x for point in used]
    low, high = min(place), max(place)
    if low == high:
        return None, log, left_out
    width = (high - low) / 3
    edges = (low + width, low + 2 * width)
    counts = [0, 0, 0]
    for value in place:
        third = sum(value > edge or math.isclose(value, edge) for edge in edges)
        counts[third] += 1
    return counts, log, left_out


def _suspects(
    groups: dict[float, list[Point]], limit: float
) -> list[tuple[int, str, str]] | None:
    """The repeats far from the others at their x, by robust z-score.

    None when no x has enough repeats to compare. An x whose repeats mostly
    agree exactly has no spread to measure against, so it is skipped.
    """
    compared = [group for group in groups.values() if len(group) >= LEAST_REPEATS]
    if not compared:
        return None
    suspects = []
    for group in compared:
        ys = [point.y for point in group]
        middle = statistics.median(ys)
        spread = statistics.median(abs(y - middle) for y in ys)
        if spread == 0:
            continue
        for point in group:
            if MAD_SCALE * abs(point.y - middle) / spread > limit:
                suspects.append((point.line, point.x_text, point.y_text))
    return sorted(suspects)
