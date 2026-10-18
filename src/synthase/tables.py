"""Saving result tables as CSV, as the roadmap asks of every table."""

import csv
from collections.abc import Iterable, Sequence
from pathlib import Path


def write_csv(
    path: Path, headings: Sequence[str], rows: Iterable[Sequence[str | None]]
) -> None:
    """Save a table as CSV, leaving blank (None) cells empty.

    The file starts with a byte-order mark (utf-8-sig): without it, Excel on
    Windows garbles any letter outside plain English.
    """
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(headings)
        writer.writerows(rows)
