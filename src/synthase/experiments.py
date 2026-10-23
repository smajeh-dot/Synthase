"""Experiments: one table per ID in `data\\experiments.toml`.

Creating, finding and remembering the open one. The layout, wording and rules
are in docs/decisions/0033-experiments.md.
"""

import tomlkit
from tomlkit.items import InlineTable

from synthase import history
from synthase.commands import read_value_line
from synthase.ids import id_number, next_id, record_id
from synthase.storage import data_folder, read_toml, save_toml
from synthase.suggest import closest
from synthase.values import Entry, EntryError, read_entry

FILE = "experiments.toml"
# The ID of the experiment last opened here, kept apart from the data files so
# choosing one is not a logged change to them.
LAST = ".last-experiment"
# The x unit a new experiment starts with (spec C107).
X_UNIT = "s"

SOURCE = "Load starting values from a file, or enter them manually? [f/m]"
FORMAT = "Enter one value per line:  name  value  unit  [+/- uncertainty]  [# note]"
FILE_NOT_BUILT = "Loading values from a file isn't built yet."
TYPE_F_OR_M = "Type f or m."
LINE_SHAPE = "Each line needs a name, a value and a unit."
DUPLICATE = "{name} is already entered in this experiment."
NONE_YET = "There are no experiments yet."
UNKNOWN = "Unknown experiment '{text}'. "
SEVERAL = 'Several experiments are called "{title}": {ids}. Open one by its ID.'
CREATED = 'Created {id} "{title}"  ·  {created}  ·  {count}'
OPENED = 'Opened {id} "{title}".'
AUTO_OPENED = 'Opened {id} "{title}" from last session'


class ExperimentError(Exception):
    """An experiment that can't be found: the message to show."""


def _ids(doc) -> list[str]:
    """The experiment IDs in a file's text, in number order."""
    found = [key for key in doc if id_number(key, "E") is not None]
    return sorted(found, key=lambda key: id_number(key, "E"))


def _title(doc, experiment_id: str) -> str:
    title = doc[experiment_id].get("title")
    return title if isinstance(title, str) else ""


def ids() -> list[str]:
    """Every experiment's ID, in number order."""
    return _ids(read_toml(data_folder() / FILE))


def title(experiment_id: str) -> str:
    """An experiment's title as stored, or "" if it has none."""
    return _title(read_toml(data_folder() / FILE), experiment_id)


def check_source(answer: str) -> str | None:
    """Why the answer to the file-or-manual question is refused, or None."""
    if answer == "m":
        return None
    return FILE_NOT_BUILT if answer == "f" else TYPE_F_OR_M


def read_line(text: str) -> Entry:
    """A typed `name value unit [+/- unc] [# note]` line, checked as in 0032."""
    parts = read_value_line(text)
    if parts is None:
        raise EntryError(LINE_SHAPE)
    return read_entry(parts)


def counted(count: int) -> str:
    return f"{count} value" + ("" if count == 1 else "s")


def find(text: str) -> str:
    """The ID of the experiment typed as an ID or as its exact title.

    An ID wins over a title. Otherwise ExperimentError says why, with the two
    closest IDs or titles, or every ID when nothing is close.
    """
    doc = read_toml(data_folder() / FILE)
    known = _ids(doc)
    if not known:
        raise ExperimentError(NONE_YET)
    if text in known:
        return text
    same = [key for key in known if _title(doc, key) == text]
    if len(same) == 1:
        return same[0]
    if same:
        raise ExperimentError(SEVERAL.format(title=text, ids=", ".join(same)))
    titles = [t for key in known if (t := _title(doc, key))]
    matches = closest(text, [*known, *titles])
    if matches:
        rest = f"Did you mean: {', '.join(matches)}?"
    else:
        rest = f"Experiments: {', '.join(known)}."
    raise ExperimentError(UNKNOWN.format(text=text) + rest)


def _inline(**parts: str) -> InlineTable:
    """`{ value = "2.003", unit = "g" }`, each part written as text."""
    fields = ", ".join(
        f"{k} = {tomlkit.string(v).as_string()}" for k, v in parts.items()
    )
    return tomlkit.parse(f"x = {{ {fields} }}")["x"]


def stored(entry: Entry) -> dict[str, str]:
    """A value as it is stored: its value and unit, then `unc` and `note` if typed."""
    parts = {"value": entry.value, "unit": entry.unit}
    if entry.uncertainty is not None:
        parts["unc"] = entry.uncertainty
    if entry.note is not None:
        parts["note"] = entry.note
    return parts


def create(new_title: str, entries: list[Entry]) -> tuple[str, str]:
    """Save a new experiment with the next `E` ID, and log it.

    Returns the ID and the stored time. The counter is saved after the
    experiment itself, so nothing is used up if saving fails (C173).
    """
    new_id = next_id("E")
    created = history.now()
    path = data_folder() / FILE
    doc = read_toml(path)
    table = tomlkit.table()
    table["title"] = new_title
    table["created"] = created
    table["x_unit"] = X_UNIT
    values = tomlkit.table()
    for entry in entries:
        values[entry.name] = _inline(**stored(entry))
    table["values"] = values
    doc[new_id] = table
    save_toml(path, doc)
    history.log("create_experiment", FILE, id=new_id, new=new_title)
    for entry in entries:
        history.log("add", FILE, id=new_id, name=entry.name, new=stored(entry))
    record_id(new_id)
    return new_id, created


def remember(experiment_id: str) -> None:
    """Keep which experiment is open, for the next start. Never stops a command."""
    try:
        (data_folder() / LAST).write_text(experiment_id + "\n", encoding="utf-8")
    except OSError:
        pass


def last_opened() -> str | None:
    """The experiment last opened here, if it still exists; otherwise None."""
    try:
        text = (data_folder() / LAST).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return text if text in ids() else None
