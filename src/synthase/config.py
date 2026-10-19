"""The config: every scientific constant, with its unit, source and status.

The format is described in docs/decisions/0008-config-format.md. The template
in this package holds placeholders only; the real values live in the
workspace's config.toml.
"""

import re
import tomllib
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

WORKSPACE_CONFIG_NAME = "config.toml"
TEMPLATE = files("synthase") / "config_template.toml"
FIELDS = ("name", "value", "unit", "source", "verified")
# The [folders] table: where each area's tables are saved (decision 0015).
FOLDERS_TABLE = "folders"
FOLDER_AREAS = ("compounds",)


class ConfigError(Exception):
    """A config file that can't be used, with a message for the user."""


@dataclass(frozen=True)
class ConfigValue:
    key: str
    name: str
    value: object
    unit: str
    source: str
    verified: bool

    @property
    def warning(self) -> str:
        """The warning to show next to any result that uses this value.

        Empty when the value has been verified.
        """
        if self.verified:
            return ""
        return (
            f"Warning: {self.name} ({self.describe()}) has not been checked "
            "against the literature yet. Treat results that use it as provisional."
        )

    def describe(self) -> str:
        """The value and its unit as plain text, e.g. ``0.1 OD600``."""
        text = self.value_text()
        return f"{text} {self.unit}" if self.unit else text

    def value_text(self) -> str:
        """The value alone as plain text, e.g. ``0.1`` or ``1600–1650``."""
        value = self.value
        if isinstance(value, list) and isinstance(value[0], dict):
            parts = [f"≤{band['max']:g} {band['label']}" for band in value[:-1]] + [
                f">{value[-2]['max']:g} {value[-1]['label']}"
            ]
            return ", ".join(parts)
        if isinstance(value, list):
            return f"{value[0]:g}–{value[1]:g}"
        if isinstance(value, str):
            return value
        return f"{value:g}"


class Config:
    """The loaded config entries, looked up by key, e.g. ``mic.growth_threshold``."""

    def __init__(
        self,
        entries: dict[str, ConfigValue],
        path: Path | Traversable,
        folders: dict[str, str] | None = None,
    ):
        self._entries = entries
        self._folders = folders or {}
        self.path = path

    def get(self, key: str) -> ConfigValue:
        try:
            return self._entries[key]
        except KeyError:
            raise ConfigError(
                f"The config has no entry called [{key}]. "
                "Check the spelling, or compare your config with the template."
            ) from None

    def keys(self) -> list[str]:
        return list(self._entries)

    def folder(self, area: str) -> str:
        """The folder set for ``area`` under [folders], or "" if none is set."""
        return self._folders.get(area, "")


def read_template() -> str:
    """The template's text, for copying into a new workspace."""
    return TEMPLATE.read_text(encoding="utf-8")


def load_config(workspace: Path | None = None) -> Config:
    """Load ``<workspace>/config.toml``, or the template if there isn't one.

    Any entry missing from the workspace config is taken from the template, so
    it stays unverified and keeps its warning.
    """
    entries, folders = _read(TEMPLATE)
    path: Path | Traversable = TEMPLATE
    if workspace is not None:
        workspace_file = Path(workspace) / WORKSPACE_CONFIG_NAME
        if workspace_file.is_file():
            workspace_entries, workspace_folders = _read(workspace_file)
            entries.update(workspace_entries)
            folders.update(workspace_folders)
            path = workspace_file
    return Config(entries, path, folders)


def _problem(path, where: str, what: str, fix: str = "that entry") -> ConfigError:
    return ConfigError(
        f"Your config file has a problem: {path}{where}: {what}. "
        f"Fix {fix}, or compare it with the template."
    )


def _read(path: Path | Traversable) -> tuple[dict[str, ConfigValue], dict[str, str]]:
    try:
        data = tomllib.loads(path.read_bytes().decode("utf-8"))
    except UnicodeDecodeError:
        raise _problem(
            path, "", "it is not saved as UTF-8 text", "the file's encoding"
        ) from None
    except tomllib.TOMLDecodeError as error:
        message = str(error)
        match = re.search(r" \(at line (\d+), column \d+\)$", message)
        if match is None:
            raise _problem(path, "", message, "the file") from None
        raise _problem(
            path, f", line {match[1]}", message[: match.start()], "that line"
        ) from None

    entries = {}
    folders = {}
    for area, area_entries in data.items():
        if not isinstance(area_entries, dict):
            raise _problem(
                path,
                "",
                f"'{area}' is outside any entry. "
                "Put it inside an entry such as [area.entry]",
                "that line",
            )
        if area == FOLDERS_TABLE:
            folders = _folders(path, area_entries)
            continue
        for entry_name, fields in area_entries.items():
            key = f"{area}.{entry_name}"
            entries[key] = _entry(path, key, fields)
    return entries, folders


def _folders(path, settings: dict) -> dict[str, str]:
    """The [folders] settings, each a folder path or "" for not set."""
    for area, folder in settings.items():
        if area not in FOLDER_AREAS:
            raise _problem(
                path,
                f", [{FOLDERS_TABLE}]",
                f"unknown folder setting '{area}'. "
                f"The settings are: {', '.join(FOLDER_AREAS)}",
                "that line",
            )
        if not isinstance(folder, str):
            raise _problem(
                path,
                f", [{FOLDERS_TABLE}]",
                f"'{area}' must be a folder path in quotes, or \"\" for none",
                "that line",
            )
    return {area: folder.strip() for area, folder in settings.items()}


def _entry(path, key: str, fields) -> ConfigValue:
    def fail(what: str) -> ConfigError:
        return _problem(path, f", entry [{key}]", what)

    if not isinstance(fields, dict):
        raise fail("must be a table with the fields " + ", ".join(FIELDS))
    for field in fields:
        if field not in FIELDS:
            raise fail(f"unknown field '{field}'")
    for field in FIELDS:
        if field not in fields:
            raise fail(f"missing '{field}'")

    for field in ("name", "unit", "source"):
        if not isinstance(fields[field], str):
            raise fail(f"'{field}' must be text in quotes")
    for field in ("name", "source"):
        if not fields[field].strip():
            raise fail(f"'{field}' must not be empty")
    if not isinstance(fields["verified"], bool):
        raise fail("'verified' must be true or false")
    problem = _value_problem(fields["value"])
    if problem:
        raise fail(problem)

    return ConfigValue(
        key=key,
        name=fields["name"],
        value=fields["value"],
        unit=fields["unit"],
        source=fields["source"],
        verified=fields["verified"],
    )


def _is_number(value) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _value_problem(value) -> str:
    """What's wrong with an entry's value, or "" if nothing is."""
    if _is_number(value) or isinstance(value, str):
        return ""
    if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
        return _bands_problem(value)
    if isinstance(value, list) and len(value) == 2 and all(map(_is_number, value)):
        return "" if value[0] <= value[1] else "a range must go from low to high"
    return (
        "'value' must be a number, text in quotes, a range [low, high] "
        "or a list of bands"
    )


def _bands_problem(bands: list[dict]) -> str:
    for band in bands:
        for field in band:
            if field not in ("max", "label"):
                return f"unknown band field '{field}'"
        if not isinstance(band.get("label"), str) or not band["label"].strip():
            return "every band needs a 'label' in quotes"
    if "max" in bands[-1]:
        return "the last band must have no 'max', because it covers everything above"
    limits = [band.get("max") for band in bands[:-1]]
    if not all(map(_is_number, limits)):
        return "every band except the last needs a number for 'max'"
    if any(low >= high for low, high in zip(limits, limits[1:], strict=False)):
        return "the band limits must increase from one band to the next"
    if len(bands) < 2:
        return "a list of bands needs at least two bands"
    return ""
