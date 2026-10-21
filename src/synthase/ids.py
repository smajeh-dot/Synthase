"""Data IDs: a capital letter and a number, such as E002 or C014 (spec D26).

The next ID is the counter in `data\\synthase.toml` plus one, never lower than
the highest ID already in that kind's file. Counters only go up, so an ID is
never reused, even after its entry is deleted in Notepad (C84, C167). The rules
are in docs/decisions/0025-ids-history-lock.md.
"""

import re

from synthase import history
from synthase.storage import MARKER, data_folder, read_toml, save_toml

# The file each kind of ID lives in. Analysis records (A) come with F4.
KIND_FILES = {"E": "experiments.toml", "C": "compounds.toml"}
ID = re.compile(r"([A-Z])(\d{3,})")


def id_number(text: str, letter: str) -> int | None:
    """The number in an ID of the given letter, or None if it isn't one."""
    match = ID.fullmatch(text)
    if match is None or match[1] != letter:
        return None
    return int(match[2])


def format_id(letter: str, number: int) -> str:
    """Three digits, growing to four after 999 (C82)."""
    return f"{letter}{number:03d}"


def _counter(letter: str) -> int:
    counters = read_toml(data_folder() / MARKER).get("counters", {})
    return int(counters.get(letter, 0))


def next_id(letter: str) -> str:
    """The ID the next new entry of this kind gets. Saves nothing."""
    found = [
        id_number(key, letter) for key in read_toml(data_folder() / KIND_FILES[letter])
    ]
    highest = max([_counter(letter), *(n for n in found if n is not None)])
    return format_id(letter, highest + 1)


def record_id(new_id: str) -> None:
    """Move the counter up to an ID that has just been saved, and log it.

    Called after the entry itself is saved, so a walk-through cancelled with
    Ctrl+C uses no ID (C173).
    """
    letter = new_id[0]
    number = id_number(new_id, letter)
    if number is None:
        raise ValueError(f"{new_id!r} is not a data ID")
    path = data_folder() / MARKER
    doc = read_toml(path)
    counters = doc.setdefault("counters", {})
    counters[letter] = max(int(counters.get(letter, 0)), number)
    save_toml(path, doc)
    history.log("issue_id", MARKER, id=new_id)
