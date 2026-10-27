"""The compound library: one table per ID in `data\\compounds.toml`.

Fields are stored exactly as typed. Molar mass, density and purity are a value
and a unit, as in spec Section 3; nothing is calculated and the formula is never
checked against the molar mass. The wording is in
docs/decisions/0037-compound-library.md.
"""

import tomlkit

from synthase import history
from synthase.experiments import inline
from synthase.ids import id_number, next_id, record_id
from synthase.storage import data_folder, read_toml, save_toml
from synthase.suggest import closest
from synthase.values import EntryError, check_number, check_unit

FILE = "compounds.toml"

# The fields, in the order they are asked and stored (spec C72).
FIELDS = ("name", "formula", "molar_mass", "density", "purity", "note")
UNIT_FIELDS = ("molar_mass", "density", "purity")
LABELS = {
    "name": "Name",
    "formula": "Formula",
    "molar_mass": "Molar mass",
    "density": "Density",
    "purity": "Purity",
    "note": "Note",
}

UNIT_FORMAT = "Type the value and its unit, e.g. 138.120 g/mol"
NEEDS_UNIT = "Each needs a value and a unit."
NONE_YET = "There are no compounds yet."
USE_CREATE = "Use 'compound create' to add one."
UNKNOWN = "Unknown compound '{text}'."
ADDED = "Added {id} ({name})."
ADDED_BARE = "Added {id}."
UPDATED = "Updated {id} ({name})."
UPDATED_BARE = "Updated {id}."
UNCHANGED = "Nothing changed. Nothing was saved."

# A field as stored: text, or {value, unit} for the unit fields.
Fields = dict[str, "str | dict[str, str]"]


class CompoundError(Exception):
    """A compound that can't be found: the message to show.

    The first line is what is wrong; each further line is a suggestion.
    """

    @property
    def lines(self) -> list[str]:
        return str(self).split("\n")


def _ids(doc) -> list[str]:
    """The compound IDs in a file's text, in number order."""
    found = [key for key in doc if id_number(key, "C") is not None]
    return sorted(found, key=lambda key: id_number(key, "C"))


def ids() -> list[str]:
    """Every compound's ID, in number order."""
    return _ids(read_toml(data_folder() / FILE))


def read_unit_field(text: str) -> dict[str, str]:
    """A typed `value unit`, checked as in decision 0032, kept as typed."""
    parts = text.split(None, 1)
    if len(parts) < 2:
        raise EntryError(NEEDS_UNIT)
    return {"value": check_number(parts[0]), "unit": check_unit(parts[1].strip())}


def check_unit_field(text: str) -> str | None:
    """Why a typed `value unit` is refused, or None."""
    try:
        read_unit_field(text)
    except EntryError as error:
        return str(error)
    return None


def shown(stored: object) -> str:
    """A stored field as typed: `Salicylic acid` or `138.120 g/mol`."""
    if isinstance(stored, dict):
        return f"{stored.get('value', '')} {stored.get('unit', '')}".strip()
    return "" if stored is None else str(stored)


def _plain(table) -> Fields:
    """A compound's known fields as plain text and dicts."""
    fields: Fields = {}
    for name in FIELDS:
        if name not in table:
            continue
        value = table[name]
        if isinstance(value, dict):
            fields[name] = {k: str(v) for k, v in value.items()}
        else:
            fields[name] = str(value)
    return fields


def get(compound_id: str) -> Fields:
    """A compound's stored fields."""
    return _plain(read_toml(data_folder() / FILE)[compound_id])


def build(answers: dict[str, object], old: Fields | None = None) -> Fields:
    """The fields a walk-through's answers make.

    A skipped or cleared field is left out. An answer equal to what ``old``
    shows keeps the stored field untouched; anything else is read afresh.
    """
    old = old or {}
    fields: Fields = {}
    for name in FIELDS:
        answer = answers.get(name)
        if not answer:
            continue
        if name in old and answer == shown(old[name]):
            fields[name] = old[name]
        elif name in UNIT_FIELDS:
            fields[name] = read_unit_field(str(answer))
        else:
            fields[name] = str(answer)
    return fields


def _write(table, fields: Fields) -> None:
    """Set a table's known fields to ``fields``, leaving anything else alone."""
    for name in FIELDS:
        if name not in fields:
            if name in table:
                del table[name]
            continue
        value = fields[name]
        if isinstance(value, dict):
            table[name] = inline(**value)
        else:
            table[name] = value


def create(fields: Fields) -> str:
    """Save a new compound with the next `C` ID, and log it. Returns the ID.

    The counter is saved after the compound itself, so nothing is used up if
    saving fails (C173).
    """
    new_id = next_id("C")
    path = data_folder() / FILE
    doc = read_toml(path)
    table = tomlkit.table()
    _write(table, fields)
    doc[new_id] = table
    save_toml(path, doc)
    history.log("add_compound", FILE, id=new_id, new=fields)
    record_id(new_id)
    return new_id


def edit(compound_id: str, fields: Fields) -> bool:
    """Save a compound's new fields and log the change. False if nothing changed."""
    path = data_folder() / FILE
    doc = read_toml(path)
    old = _plain(doc[compound_id])
    if old == fields:
        return False
    _write(doc[compound_id], fields)
    save_toml(path, doc)
    history.log("edit_compound", FILE, id=compound_id, old=old, new=fields)
    return True


def find(text: str) -> str:
    """The ID typed, or CompoundError saying it isn't there, with the two
    closest IDs or every ID when nothing is close."""
    known = ids()
    if not known:
        raise CompoundError(f"{NONE_YET}\n{USE_CREATE}")
    if text in known:
        return text
    matches = closest(text, known)
    hint = (
        f"Did you mean: {', '.join(matches)}?"
        if matches
        else f"Compounds: {', '.join(known)}."
    )
    raise CompoundError(f"{UNKNOWN.format(text=text)}\n{hint}")


def listing() -> list[tuple[str, str, str]]:
    """Each compound's ID, name and formula, in ID order."""
    doc = read_toml(data_folder() / FILE)
    return [
        (key, shown(doc[key].get("name")), shown(doc[key].get("formula")))
        for key in _ids(doc)
    ]


def label_of(fields: Fields) -> str:
    """The name for the `Added` and `Updated` lines, or an empty string."""
    return shown(fields.get("name"))
