"""The values of an experiment: adding, editing, deleting and their history.

A value is one inline table in `[E002.values]` of `data\\experiments.toml`, as
decision 0033 describes, and every change is logged. The wording and look are in
docs/decisions/0036-value-commands.md.
"""

import tomlkit

from synthase import history
from synthase.experiments import FILE, inline, stored
from synthase.storage import data_folder, read_toml, save_toml
from synthase.suggest import closest
from synthase.values import Entry

NO_EXPERIMENT = "No experiment is open."
EXISTS = "{name} already exists in {id}."
USE_EDIT = "Use 'value edit' to change it."
MISSING = "There is no value '{name}' in {id}."
NO_HISTORY = "There is no history for '{name}' in {id}."
NO_VALUES = "{id} has no values yet."
USE_ADD = "Use 'value add' to store one."
USE_ADD_NEW = "Use 'value add' to store a new one."
# What `history` calls each logged action, padded so the names line up.
ACTIONS = {"add": "added", "edit": "edited", "delete": "deleted"}
ACTION_WIDTH = 9


class ValuesError(Exception):
    """A value that can't be found or stored: the message to show.

    The first line is what is wrong; each further line is a suggestion.
    """

    @property
    def lines(self) -> list[str]:
        return str(self).split("\n")


def _from_stored(name: str, parts: dict) -> Entry:
    return Entry(
        name,
        str(parts["value"]),
        str(parts["unit"]),
        None if "unc" not in parts else str(parts["unc"]),
        None if "note" not in parts else str(parts["note"]),
    )


def names(experiment_id: str) -> list[str]:
    """The value names of an experiment, in the order they are stored."""
    doc = read_toml(data_folder() / FILE)
    return list(doc[experiment_id].get("values", {}))


ADDED = "Added {name}: {entry}"
UPDATED = "Updated {name}: {old} -> {new}{removed}"
DELETED = "Deleted {name}."


def exists_message(name: str, experiment_id: str) -> str:
    return EXISTS.format(name=name, id=experiment_id)


def text(entry: Entry, note: bool = True) -> str:
    """An entry as typed: ``2.2110 g +/- 0.001 # Balance B2``."""
    shown = f"{entry.value} {entry.unit}"
    if entry.uncertainty is not None:
        shown += f" +/- {entry.uncertainty}"
    if note and entry.note is not None:
        shown += f" # {entry.note}"
    return shown


def brief(entry: Entry) -> str:
    """Only the value and unit, as `Updated` shows each side (spec D8)."""
    return f"{entry.value} {entry.unit}"


def _unknown(
    template: str, name: str, experiment_id: str, known: list[str], add: str = ""
) -> ValuesError:
    """A name that isn't there: what is wrong, what could be meant, and ``add``."""
    if not known:
        if template == NO_HISTORY:
            return ValuesError(template.format(name=name, id=experiment_id))
        return ValuesError(f"{NO_VALUES.format(id=experiment_id)}\n{USE_ADD}")
    matches = closest(name, known)
    hint = (
        f"Did you mean: {', '.join(matches)}?"
        if matches
        else f"Values: {', '.join(known)}."
    )
    lines = [template.format(name=name, id=experiment_id), hint]
    return ValuesError("\n".join([*lines, add] if add else lines))


def read(experiment_id: str, name: str) -> Entry:
    """A stored value, or ValuesError saying it isn't there."""
    doc = read_toml(data_folder() / FILE)
    values = doc[experiment_id].get("values", {})
    if name not in values:
        raise _unknown(MISSING, name, experiment_id, list(values))
    return _from_stored(name, values[name])


def add(experiment_id: str, entries: list[Entry]) -> None:
    """Store new values and log each. A name already stored is refused, and
    then nothing is saved."""
    path = data_folder() / FILE
    doc = read_toml(path)
    table = doc[experiment_id]
    if "values" not in table:
        table["values"] = tomlkit.table()
    values = table["values"]
    for entry in entries:
        if entry.name in values:
            message = exists_message(entry.name, experiment_id)
            raise ValuesError(message + "\n" + USE_EDIT)
        values[entry.name] = inline(**stored(entry))
    save_toml(path, doc)
    for entry in entries:
        history.log("add", FILE, id=experiment_id, name=entry.name, new=stored(entry))


def edit(experiment_id: str, entry: Entry) -> Entry:
    """Replace a stored value as a whole and log it. Returns the old entry."""
    path = data_folder() / FILE
    doc = read_toml(path)
    values = doc[experiment_id].get("values", {})
    if entry.name not in values:
        raise _unknown(MISSING, entry.name, experiment_id, list(values), USE_ADD_NEW)
    old = _from_stored(entry.name, values[entry.name])
    values[entry.name] = inline(**stored(entry))
    save_toml(path, doc)
    history.log(
        "edit",
        FILE,
        id=experiment_id,
        name=entry.name,
        old=stored(old),
        new=stored(entry),
    )
    return old


def delete(experiment_id: str, name: str) -> Entry:
    """Remove a stored value and log it. Returns the entry removed."""
    path = data_folder() / FILE
    doc = read_toml(path)
    values = doc[experiment_id].get("values", {})
    if name not in values:
        raise _unknown(MISSING, name, experiment_id, list(values))
    old = _from_stored(name, values[name])
    del values[name]
    save_toml(path, doc)
    history.log("delete", FILE, id=experiment_id, name=name, old=stored(old))
    return old


def removed(old: Entry, new: Entry) -> str:
    """What an edit left out: ``(uncertainty and note removed)``, or nothing."""
    cleared = []
    if old.uncertainty is not None and new.uncertainty is None:
        cleared.append("uncertainty")
    if old.note is not None and new.note is None:
        cleared.append("note")
    return f" ({' and '.join(cleared)} removed)" if cleared else ""


def versions(experiment_id: str, name: str) -> list[str]:
    """Every version of a value in this experiment, oldest first, as lines.

    Read from the history log. A name never stored is refused, with the names
    this experiment has ever had to suggest from.
    """
    lines = []
    ever: list[str] = []
    for item in history.entries():
        if item.get("id") != experiment_id or item.get("action") not in ACTIONS:
            continue
        if item["name"] not in ever:
            ever.append(item["name"])
        if item["name"] != name:
            continue
        action = ACTIONS[item["action"]]
        shown = ""
        if item["action"] == "add":
            shown = text(_from_stored(name, item["new"]))
        elif item["action"] == "edit":
            old = text(_from_stored(name, item["old"]))
            shown = f"{old} -> {text(_from_stored(name, item['new']))}"
        lines.append(
            f"{history.shown_time(item['ts'])}  {action.ljust(ACTION_WIDTH)}{name}"
            + (f"  {shown}" if shown else "")
        )
    if not lines:
        raise _unknown(NO_HISTORY, name, experiment_id, ever)
    return lines
