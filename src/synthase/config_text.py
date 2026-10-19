"""The text /config shows: the settings in config.toml, or one value in full.

The checks that come first, and the folder lines, are syn doctor's own, so the
two say the same thing. Like doctor.py, nothing here prints anything. The
details are in docs/decisions/0016-full-screen-app.md under "Details settled
for #60".
"""

from dataclasses import dataclass

from synthase.config import FOLDER_AREAS, Config, ConfigValue
from synthase.doctor import Check, check_config, check_table_folder, check_workspace

CONFIG_HEADINGS = ("Entry", "Value", "Unit", "Verified", "Source")
# The words carry the meaning, so it never depends on colour (decision 0016).
VERIFIED = "✓ yes"
UNVERIFIED = "? no"
ONE_NAME = "/config takes one entry name, e.g. /config mic.growth_threshold."
EVERY_ENTRY = "Type /config to see every entry."


@dataclass(frozen=True)
class Settings:
    """What /config found: the failing check, or the config and folder checks."""

    problem: Check | None
    config: Config | None = None
    folders: tuple[Check, ...] = ()


def read_settings(init: str = "syn init") -> Settings:
    """The workspace config, checked as syn doctor checks it.

    ``init`` is how a Fix line says to run init.
    """
    workspace, folder = check_workspace(init)
    if not workspace.passed:
        return Settings(workspace)
    config, loaded = check_config(folder)
    if loaded is None:
        return Settings(config)
    folders = tuple(check_table_folder(folder, loaded, area) for area in FOLDER_AREAS)
    return Settings(None, loaded, folders)


def config_entries(config: Config) -> list[ConfigValue]:
    return [config.get(key) for key in config.keys()]


def settings_heading(config: Config) -> str:
    return f"Settings in {config.path}"


def verified_text(entry: ConfigValue) -> str:
    return VERIFIED if entry.verified else UNVERIFIED


def config_row(entry: ConfigValue) -> tuple[str, ...]:
    """One table row: entry, value, unit, verified and source. "-" if blank."""
    return (
        entry.key,
        entry.value_text(),
        entry.unit or "-",
        verified_text(entry),
        entry.source,
    )


def count_line(config: Config) -> str:
    """How many values are still unverified, e.g. ``3 of 13 values are …``."""
    entries = config_entries(config)
    unverified = sum(not entry.verified for entry in entries)
    if not unverified:
        return f"All {len(entries)} values are verified."
    verb = "is" if unverified == 1 else "are"
    return f"{unverified} of {len(entries)} values {verb} still unverified."


def entry_key(typed: str) -> str:
    """The key a name typed after /config means, ignoring capitals and [ ]."""
    return typed.strip().lower().removeprefix("[").removesuffix("]")


def entry_rows(entry: ConfigValue) -> list[tuple[str, str]]:
    """One value in full, as names and what they are."""
    return [
        ("Name", entry.name),
        ("Value", entry.value_text()),
        ("Unit", entry.unit or "-"),
        ("Source", entry.source),
        ("Verified", verified_text(entry)),
    ]
