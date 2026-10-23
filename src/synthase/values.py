"""Reading the parts of a value line: name, number, unit and uncertainty.

Each part is checked and handed back exactly as typed; nothing is converted,
rounded or corrected (spec D25). The rules and wording are in
docs/decisions/0032-value-entry.md. The command table (commands.py) splits a
line into its parts; storing them is #105's job.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from synthase.suggest import closest

MAX_NAME = 64
RESERVED_PREFIX = "rxn_"

# Optional sign, digits with an optional decimal point (`.5` and `5.` too), and
# an optional exponent (spec C168).
NUMBER = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
# What a near miss is read as: a comma for the point, letters for 0 and 1.
LOOKALIKES = str.maketrans({",": ".", "O": "0", "o": "0", "l": "1", "I": "1"})

# The recognised units, whole and case-sensitive, typed as they are stored. It
# only catches typos; nothing is converted (spec C70, C169). The order is the
# order suggestions break ties in, so `gg` gives `g, kg`.
UNITS = (
    "g", "kg", "mg", "ug",
    "L", "mL", "uL", "cm^3", "dm^3",
    "mol", "mmol", "umol",
    "mol/dm^3", "mol dm^-3", "M", "mM",
    "g/mol", "g mol^-1", "g/cm^3", "g cm^-3", "g/dm^3", "g dm^-3", "%",
    "K", "degC",
    "s", "min", "h",
    "J", "kJ", "J/mol", "kJ/mol", "J mol^-1", "kJ mol^-1",
    "Pa", "kPa", "bar", "atm",
    "Hz",
    "s^-1", "min^-1", "dm^3/mol/s",
    "none",
)  # fmt: skip

EMPTY_NAME = "A value name can't be empty."
SPACED_NAME = "A value name can't contain spaces."
LONG_NAME = f"A value name can be at most {MAX_NAME} characters."
HASH_NAME = "A value name can't start with '#'."
PLUS_MINUS_NAME = "A value name can't be '+/-'."
RESERVED_NAME = f"Names starting with {RESERVED_PREFIX} are kept for reaction records."
NOT_A_NUMBER = "'{text}' isn't a number."
READING = " Did you mean: {reading}?"
UNKNOWN_UNIT = "Unknown unit '{text}'."
MATCHES = " Did you mean: {matches}?"


class EntryError(Exception):
    """A part of a value line that is refused: the message to show."""


@dataclass(frozen=True)
class Entry:
    """A value line's parts, each exactly as typed."""

    name: str
    value: str
    unit: str
    uncertainty: str | None = None
    note: str | None = None


def check_name(name: str) -> str:
    """The name, if it follows spec C165; otherwise EntryError."""
    if not name:
        raise EntryError(EMPTY_NAME)
    if any(c.isspace() for c in name):
        raise EntryError(SPACED_NAME)
    if len(name) > MAX_NAME:
        raise EntryError(LONG_NAME)
    if name.startswith("#"):
        raise EntryError(HASH_NAME)
    if name == "+/-":
        raise EntryError(PLUS_MINUS_NAME)
    if name.startswith(RESERVED_PREFIX):
        raise EntryError(RESERVED_NAME)
    return name


def check_number(text: str) -> str:
    """The number, kept as text, or EntryError with the closest reading."""
    if NUMBER.fullmatch(text):
        return text
    message = NOT_A_NUMBER.format(text=text)
    reading = text.translate(LOOKALIKES)
    if reading != text and NUMBER.fullmatch(reading):
        message += READING.format(reading=reading)
    raise EntryError(message)


def unit_words(words: list[str]) -> int:
    """How many of the leading ``words`` are the unit: two if they are one.

    Some units hold a space (`mol dm^-3`). A second word is taken only when the
    two make a listed unit, so a forgotten `+/-` still gets the usage line.
    """
    return 2 if " ".join(words[:2]) in UNITS else min(len(words), 1)


def check_unit(text: str) -> str:
    """The unit as typed, if it is in UNITS; otherwise EntryError.

    Spaces inside a unit count once, so `mol  dm^-3` matches `mol dm^-3`.
    """
    unit = " ".join(text.split())
    if unit in UNITS:
        return text
    message = UNKNOWN_UNIT.format(text=text)
    # `1/s` is never accepted; point at `s^-1` when that is a unit.
    inverse = re.fullmatch(r"1/(\S+)", unit)
    if inverse and f"{inverse[1]}^-1" in UNITS:
        matches = [f"{inverse[1]}^-1"]
    else:
        matches = closest(unit, list(UNITS))
    if matches:
        message += MATCHES.format(matches=", ".join(matches))
    raise EntryError(message)


def read_entry(parts: Mapping[str, str | None]) -> Entry:
    """Check a value line's parts, as `commands.Call.args` holds them.

    The first part that is refused raises EntryError.
    """
    name, value, unit = parts["name"], parts["value"], parts["unit"]
    assert name is not None and value is not None and unit is not None
    uncertainty = parts.get("uncertainty")
    return Entry(
        check_name(name),
        check_number(value),
        check_unit(unit),
        None if uncertainty is None else check_number(uncertainty),
        parts.get("note"),
    )
