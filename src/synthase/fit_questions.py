"""The questions the app asks for fit check (decision 0019).

Like compound_questions.py, nothing here prints or asks anything. The answers
turn into the same options ``syn fit check`` takes, so the same file gives the
same report either way.
"""

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from synthase.compound_questions import Answers, Flow, Question
from synthase.compounds import CompoundError
from synthase.fit_check import (
    FitError,
    Table,
    find_column,
    read_table,
    shares_x,
    split_unit,
)
from synthase.fit_text import (
    ARE_REPEATS,
    NO_COLUMN,
    NO_PATH,
    UNIT_OF,
    UNIT_SKIP,
    USING,
    WHICH_FILE,
    WHICH_X,
    WHICH_Y,
    preview,
)


@dataclass(frozen=True)
class Chosen:
    """The file chosen, already read."""

    path: Path
    table: Table


def fit_flow() -> Flow:
    """The questions for fit check: file, columns, units and repeats."""
    return Flow(
        (),
        (
            Question("file", WHICH_FILE, check_file, skippable=False, shown=shown),
            Question("x", x_text, check_x, skippable=False, asked=ask_columns),
            Question("y", y_text, check_y, skippable=False, asked=ask_columns),
            Question(
                "x_unit", unit_text("x"), unit_check("x"), current=unit_current("x")
            ),
            Question(
                "y_unit", unit_text("y"), unit_check("y"), current=unit_current("y")
            ),
            Question(
                "repeats",
                repeats_text,
                check_repeats,
                yes_no=True,
                default_yes=True,
                asked=ask_repeats,
            ),
        ),
    )


def fit_args(answers: Answers) -> argparse.Namespace:
    """The options ``syn fit check`` would be given for these answers."""
    chosen = answers["file"]
    x, y = columns(answers)
    return argparse.Namespace(
        file=chosen.path,
        x=x,
        y=y,
        x_unit=answers.get("x_unit"),
        y_unit=answers.get("y_unit"),
        repeats=answers.get("repeats"),
        model=None,
    )


def table_of(answers: Answers) -> Table:
    return answers["file"].table


def columns(answers: Answers) -> tuple[str, str]:
    """The x and y columns: the only two when the file has two, else as chosen."""
    names = table_of(answers).columns
    if len(names) == 2:
        return names[0], names[1]
    return answers["x"], answers["y"]


def ask_columns(answers: Answers) -> bool:
    return len(table_of(answers).columns) > 2


def check_file(text: str, answers: Answers) -> Chosen:
    if not text.strip():
        raise CompoundError(NO_PATH)
    # A file dragged into PowerShell arrives in quotes.
    path = Path(text.strip().strip('"'))
    try:
        return Chosen(path, read_table(path))
    except FitError as error:
        raise CompoundError(str(error)) from None


def shown(answers: Answers) -> str:
    """The preview of the file chosen, and which columns are used if only two."""
    chosen = answers["file"]
    table = chosen.table
    rows = [cells for _, cells in table.rows]
    text = preview(table.name, table.columns, rows)
    if not ask_columns(answers):
        x, y = columns(answers)
        text += "\n" + USING.format(x=x, y=y)
    return text


def listed(names: list[str]) -> str:
    return ", ".join(names)


def x_text(answers: Answers) -> str:
    return f"{WHICH_X} ({listed(list(table_of(answers).columns))})"


def y_text(answers: Answers) -> str:
    return f"{WHICH_Y} ({listed(left(answers))})"


def left(answers: Answers) -> list[str]:
    """The columns still to choose from once x is chosen."""
    return [name for name in table_of(answers).columns if name != answers["x"]]


def pick(table: Table, typed: str) -> str:
    """The column ``typed`` names in ``table``, as the file spells it."""
    try:
        return table.columns[find_column(table, typed)]
    except FitError:
        message = NO_COLUMN.format(column=typed, columns=listed(list(table.columns)))
        raise CompoundError(message) from None


def check_x(text: str, answers: Answers) -> str:
    return pick(table_of(answers), text)


def check_y(text: str, answers: Answers) -> str:
    table = table_of(answers)
    return pick(Table(table.name, tuple(left(answers)), ()), text)


def column_of(axis: str, answers: Answers) -> str:
    return columns(answers)[1 if axis == "y" else 0]


def unit_text(axis: str) -> Callable[[Answers], str]:
    def text(answers: Answers) -> str:
        name, found = split_unit(column_of(axis, answers))
        return (UNIT_OF if found else UNIT_SKIP).format(name=name)

    return text


def unit_current(axis: str) -> Callable[[Answers], str | None]:
    def current(answers: Answers) -> str | None:
        return split_unit(column_of(axis, answers))[1]

    return current


def unit_check(axis: str) -> Callable[[str, Answers], str | None]:
    """Enter keeps the unit in the column's name, or skips it if there isn't one."""

    def check(text: str, answers: Answers) -> str | None:
        return text.strip() or unit_current(axis)(answers)

    return check


def indexes(answers: Answers) -> tuple[int, int]:
    table = table_of(answers)
    x, y = columns(answers)
    return table.columns.index(x), table.columns.index(y)


def ask_repeats(answers: Answers) -> bool:
    return shares_x(table_of(answers), *indexes(answers))


def repeats_text(answers: Answers) -> str:
    x, y = columns(answers)
    return ARE_REPEATS.format(x=split_unit(x)[0], y=split_unit(y)[0])


def check_repeats(text: str, answers: Answers) -> bool:
    """Yes unless the answer is n or no, as with the --repeats default."""
    return text.strip().lower() not in ("n", "no")
