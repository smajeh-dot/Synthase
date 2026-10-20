"""Changing the workspace config.toml: a value, its source, its mark, a folder.

Each plan_… function works out one change and its words without saving
anything, so the app can ask first; save() then writes it. Every change is
checked by load_config()'s own rules before it is saved, and tomlkit keeps the
rest of the file, comments and order included. Like config_text.py, nothing
here prints anything. The details are in docs/decisions/0017-editing-config.md.
"""

import os
import re
from dataclasses import dataclass, replace
from pathlib import Path

import tomlkit
from tomlkit.items import Item

from synthase.config import (
    FOLDER_AREAS,
    FOLDERS_TABLE,
    WORKSPACE_CONFIG_NAME,
    ConfigError,
    ConfigValue,
    _value_problem,
    check_text,
    load_config,
)
from synthase.config_text import entry_key
from synthase.workspace import back_up as back_up_config

NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
RANGE = re.compile(rf"({NUMBER})\s*(?:[-–]|\s)\s*({NUMBER})")
BAND = re.compile(rf"(?:≤|<=)?\s*({NUMBER})\s+(.+)")
LAST_BAND = re.compile(rf"(?:>\s*({NUMBER})\s+)?(.+)")
UNVERIFIED_AGAIN = "It will be marked unverified until you check it again."
NOW_UNVERIFIED = "It is now unverified."


@dataclass(frozen=True)
class Edit:
    """One change to config.toml, worked out but not yet saved.

    ``new_bytes`` is None when there is nothing to change; ``done`` then says so.
    ``question`` is empty when the change needs no question. ``note`` is shown
    before the question, and ``hint`` after the change is saved.
    """

    path: Path
    old_bytes: bytes
    new_bytes: bytes | None
    done: str
    question: str = ""
    note: str = ""
    hint: str = ""


def plan_set(workspace: Path, name: str, typed: str) -> Edit:
    """Change an entry's value, marking it unverified."""
    file = _File(workspace)
    entry = file.entry(name)
    value = _typed_value(entry, typed)
    if value == entry.value:
        return file.unchanged(f"{entry.name} is already {entry.describe()}.")
    new = replace(entry, value=value, verified=False)
    return file.change(
        entry,
        {"value": _value_toml(value), "verified": "false"},
        done=f"Changed {entry.name} to {new.describe()}. {NOW_UNVERIFIED}",
        question=(
            f"Change {entry.name} from {entry.describe()} to {new.describe()}? "
            f"{UNVERIFIED_AGAIN} Type yes to change it [no]"
        ),
    )


def plan_source(workspace: Path, name: str, source: str) -> Edit:
    """Change an entry's source; a verified entry is marked unverified."""
    file = _File(workspace)
    entry = file.entry(name)
    source = source.strip()
    if source == entry.source:
        return file.unchanged(f'The source of {entry.name} is already "{source}".')
    fields = {"source": _string(source)}
    done = f"Changed the source of {entry.name}."
    question = ""
    if entry.verified:
        fields["verified"] = "false"
        done += f" {NOW_UNVERIFIED}"
        question = (
            f'{entry.name} is verified. Change its source to "{source}"? '
            f"{UNVERIFIED_AGAIN} Type yes to change it [no]"
        )
    hint = f"Type config verify {entry.key} once you have checked the value against it."
    return file.change(entry, fields, done=done, question=question, hint=hint)


def plan_verify(workspace: Path, name: str) -> Edit:
    """Mark an entry as checked against its source."""
    file = _File(workspace)
    entry = file.entry(name)
    if entry.verified:
        return file.unchanged(f"{entry.name} is already verified.")
    if entry.source.strip().upper().startswith("UNVERIFIED"):
        raise ConfigError(
            f"Set its source first: config source {entry.key} <reference>."
        )
    return file.change(
        entry,
        {"verified": "true"},
        done=f"Marked {entry.name} ({entry.describe()}) as verified.",
        question=(
            f"Mark {entry.name} ({entry.describe()}) as checked against "
            f'"{entry.source}"? Type yes to mark it verified [no]'
        ),
    )


def plan_folder(workspace: Path, area: str, typed: str) -> Edit:
    """Set, or with "" clear, the folder an area's tables are saved in."""
    file = _File(workspace)
    area = area.strip().lower()
    if area not in FOLDER_AREAS:
        raise ConfigError(
            f"There's no folder setting called '{area}'. "
            f"The settings are: {', '.join(FOLDER_AREAS)}."
        )
    folder = typed.strip().strip("\"'").strip()
    current = file.config.folder(area)
    if folder == current:
        if folder:
            return file.unchanged(f"Tables for {area} are already saved in {folder}.")
        return file.unchanged(f"The {area} folder is already not set.")
    if folder:
        done = f"Tables for {area} will be saved in {folder}."
    else:
        done = (
            f"Cleared the {area} folder, so its tables are saved in the "
            "workspace's results folder."
        )
    return file.change_folder(area, _folder_toml(folder), done)


def save_edit(edit: Edit, back_up: bool) -> Path | None:
    """Save ``edit``, first keeping the old file as a .bak copy if ``back_up``.

    Returns the backup's path, or None when no backup was made.
    """
    path = edit.path
    try:
        changed = path.read_bytes() != edit.old_bytes
    except OSError:
        changed = True
    if changed:
        raise ConfigError(
            f"{WORKSPACE_CONFIG_NAME} changed while you were answering, so nothing "
            "was saved. Type the command again."
        )
    backup = back_up_config(path) if back_up else None
    new = path.with_name(f"{path.name}.new")
    try:
        new.write_bytes(edit.new_bytes)
        os.replace(new, path)
    except OSError as error:
        new.unlink(missing_ok=True)
        raise ConfigError(
            f"Couldn't save {path}: {error.strerror or error}. Nothing was changed. "
            "If it is open in another program, close it and try again."
        ) from None
    return backup


class _File:
    """The workspace config.toml as it is now, read once for one change."""

    def __init__(self, workspace: Path):
        self.path = Path(workspace) / WORKSPACE_CONFIG_NAME
        if not self.path.is_file():
            raise ConfigError(
                f"There's no {WORKSPACE_CONFIG_NAME} in {workspace}, "
                "so there is nothing to change."
            )
        self.config = load_config(workspace)
        self.old_bytes = self.path.read_bytes()
        self.text = self.old_bytes.decode("utf-8")
        self.newline = "\r\n" if "\r\n" in self.text else "\n"

    def entry(self, name: str) -> ConfigValue:
        return self.config.get(entry_key(name))

    def unchanged(self, done: str) -> Edit:
        return Edit(self.path, self.old_bytes, None, done)

    def change(
        self,
        entry: ConfigValue,
        fields: dict[str, str],
        done: str,
        question: str = "",
        hint: str = "",
    ) -> Edit:
        """``entry`` with ``fields`` set to new TOML values, copied in if need be."""
        area, name = entry.key.split(".", 1)
        text, note = self.text, ""
        if not _has(tomlkit.parse(text), area, name):
            text = self._append(text, _entry_toml(load_config(None).get(entry.key)))
            note = (
                f"[{entry.key}] isn't in {WORKSPACE_CONFIG_NAME} yet, so it will be "
                "copied from the template."
            )
        document = tomlkit.parse(text)
        table = document[area][name]
        for field, value in fields.items():
            _put(table, field, value)
        return self._edit(document, done, question, note, hint)

    def change_folder(self, area: str, value: str, done: str) -> Edit:
        text = self.text
        if FOLDERS_TABLE not in tomlkit.parse(text):
            text = self._append(text, f"[{FOLDERS_TABLE}]\n")
        document = tomlkit.parse(text)
        _put(document[FOLDERS_TABLE], area, value)
        return self._edit(document, done)

    def _append(self, text: str, addition: str) -> str:
        if text and not text.endswith("\n"):
            text += self.newline
        return text + self.newline + addition.replace("\n", self.newline)

    def _edit(self, document, done, question="", note="", hint="") -> Edit:
        # tomlkit writes new lines with \n; keep the file's own line endings.
        text = document.as_string().replace("\r\n", "\n")
        text = text.replace("\n", self.newline)
        check_text(self.path, text)
        return Edit(
            self.path,
            self.old_bytes,
            text.encode("utf-8"),
            done,
            question,
            note,
            hint,
        )


def _has(document, area: str, name: str) -> bool:
    return area in document and name in document[area]


def _put(table, field: str, value: str) -> None:
    """Set ``field`` to the TOML ``value``, keeping a comment on its line."""
    new: Item = tomlkit.parse(f"x = {value}").item("x")
    if field in table:
        old = table.value.item(field)
        new.trivia.comment_ws = old.trivia.comment_ws
        new.trivia.comment = old.trivia.comment
    table[field] = new


def _typed_value(entry: ConfigValue, typed: str) -> object:
    """The value ``typed`` means, as the same kind as the entry's value."""
    typed = typed.strip()
    value = entry.value
    if isinstance(value, list) and isinstance(value[0], dict):
        new = _typed_bands(typed)
        kind = "a list of bands"
    elif isinstance(value, list):
        match = RANGE.fullmatch(typed)
        new = [_number(match[1]), _number(match[2])] if match else None
        kind = "a range of two numbers"
    elif isinstance(value, str):
        new = typed or None
        kind = "text"
    else:
        new = _number(typed) if re.fullmatch(NUMBER, typed) else None
        kind = "a number"
    if new is None:
        raise ConfigError(
            f"[{entry.key}] takes {kind}, e.g. config set {entry.key} "
            f"{_example(value)}."
        )
    # _typed_bands gives a problem as text; any other text is a text value.
    bands_problem = isinstance(new, str) and kind != "text"
    problem = new if bands_problem else _value_problem(new)
    if problem:
        raise ConfigError(f"That value can't be used for [{entry.key}]: {problem}.")
    return new


def _typed_bands(typed: str) -> list[dict] | str | None:
    """Bands typed as config shows them; None if not bands, or a problem."""
    parts = [part.strip() for part in typed.split(",")]
    if len(parts) < 2 or not all(parts):
        return None
    bands = []
    for part in parts[:-1]:
        match = BAND.fullmatch(part)
        if match is None:
            return None
        bands.append({"max": _number(match[1]), "label": match[2].strip()})
    match = LAST_BAND.fullmatch(parts[-1])
    if match[1] is not None and _number(match[1]) != bands[-1]["max"]:
        return (
            "the last band covers everything above the band before it, "
            f"so it starts at >{bands[-1]['max']:g}"
        )
    bands.append({"label": match[2].strip()})
    return bands


def _number(text: str) -> int | float:
    return int(text) if re.fullmatch(r"[+-]?\d+", text) else float(text)


def _example(value) -> str:
    """The value as config set takes it, e.g. ``1 3`` for a range."""
    if isinstance(value, list) and isinstance(value[0], dict):
        limits = [f"{band['max']:g} {band['label']}" for band in value[:-1]]
        return ", ".join([*limits, value[-1]["label"]])
    if isinstance(value, list):
        return f"{value[0]:g} {value[1]:g}"
    if isinstance(value, str):
        return value
    return f"{value:g}"


def _string(text: str) -> str:
    return tomlkit.string(text).as_string()


def _folder_toml(folder: str) -> str:
    """A folder in single quotes, which keep backslashes, when it can be."""
    if "'" in folder:
        return _string(folder)
    return tomlkit.string(folder, literal=True).as_string()


def _value_toml(value) -> str:
    """A value as TOML, laid out as the template lays it out."""
    if isinstance(value, list) and isinstance(value[0], dict):
        lines = []
        for band in value:
            fields = [f"max = {band['max']!r}"] if "max" in band else []
            fields.append(f"label = {_string(band['label'])}")
            lines.append(f"    {{ {', '.join(fields)} }},\n")
        return "[\n" + "".join(lines) + "]"
    if isinstance(value, list):
        return f"[{value[0]!r}, {value[1]!r}]"
    if isinstance(value, str):
        return _string(value)
    return repr(value)


def _entry_toml(entry: ConfigValue) -> str:
    """A whole entry as the template writes it, to copy into config.toml."""
    return (
        f"[{entry.key}]\n"
        f"name = {_string(entry.name)}\n"
        f"value = {_value_toml(entry.value)}\n"
        f"unit = {_string(entry.unit)}\n"
        f"source = {_string(entry.source)}\n"
        f"verified = {'true' if entry.verified else 'false'}\n"
    )
