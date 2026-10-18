"""The compound register: every compound in the project, from idea to tested.

This is the shared command layer for `/compound` (decision 0012). It does the
work and raises CompoundError with a message for the user, but never prints or
asks anything; the command line and the app do that. The rules are in
docs/decisions/0014-compound-register.md.
"""

import re
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager, suppress
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path

from synthase.config import Config
from synthase.numbers import sig_figs

REGISTER_NAME = "compounds.sqlite"
SCHEMA_VERSION = 4
CLASSES = ("Schiff base", "chalcone", "starting material", "other")
STATUSES = ("planned", "synthesised", "purified", "characterised", "tested")
DEFAULT_STATUS = STATUSES[0]

SCHEMA = """
CREATE TABLE compounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    class TEXT,
    smiles TEXT,
    formula TEXT,
    molar_mass REAL,
    status TEXT NOT NULL,
    notes TEXT,
    archived INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    compound_id INTEGER NOT NULL REFERENCES compounds (id),
    made_on TEXT,
    mass_g REAL,
    yield_percent REAL
);
CREATE TABLE spectra (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    compound_id INTEGER NOT NULL REFERENCES compounds (id),
    path TEXT NOT NULL,
    added TEXT NOT NULL
);
CREATE TABLE changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    compound_id INTEGER NOT NULL REFERENCES compounds (id),
    changed TEXT NOT NULL,
    field TEXT NOT NULL,
    old TEXT,
    new TEXT
);
"""

# Version 2 (#35): characterisation, handling and safety. Melting points are
# in kelvin (decision 0014).
DETAILS_SCHEMA = """
ALTER TABLE compounds ADD COLUMN mp_low REAL;
ALTER TABLE compounds ADD COLUMN mp_high REAL;
ALTER TABLE compounds ADD COLUMN rf REAL;
ALTER TABLE compounds ADD COLUMN rf_solvent TEXT;
ALTER TABLE compounds ADD COLUMN appearance TEXT;
ALTER TABLE compounds ADD COLUMN coloured INTEGER;
ALTER TABLE compounds ADD COLUMN solubility TEXT;
ALTER TABLE compounds ADD COLUMN dmso_stock REAL;
ALTER TABLE compounds ADD COLUMN dmso_stock_unit TEXT;
ALTER TABLE compounds ADD COLUMN storage TEXT;
ALTER TABLE compounds ADD COLUMN risk_assessment TEXT;
ALTER TABLE compounds ADD COLUMN hazards TEXT;
"""

# Version 3 (#36): the kind of each linked spectrum.
SPECTRA_SCHEMA = """
ALTER TABLE spectra ADD COLUMN kind TEXT;
"""

# Version 4 (#46): when a batch or spectra link was removed. Removed rows are
# kept, so nothing is deleted and batch numbers never change.
REMOVED_SCHEMA = """
ALTER TABLE batches ADD COLUMN removed TEXT;
ALTER TABLE spectra ADD COLUMN removed TEXT;
"""

# What takes the register to each version from the one before.
UPGRADES = {1: SCHEMA, 2: DETAILS_SCHEMA, 3: SPECTRA_SCHEMA, 4: REMOVED_SCHEMA}

# The columns of a Compound, in order.
COLUMNS = (
    "id, label, class, smiles, formula, molar_mass, status, notes, archived, "
    "mp_low, mp_high, rf, rf_solvent, appearance, coloured, solubility, "
    "dmso_stock, dmso_stock_unit, storage, risk_assessment, hazards"
)

# The table `list` shows and saves as CSV.
TABLE_HEADINGS = ("ID", "Label", "Class", "Status", "Formula", "Molar mass (g/mol)")

# The characterisation, handling and safety fields, by group. Each one is
# named by its Compound attribute, in the change log too.
DETAIL_GROUPS = (
    ("Characterisation", ("melting_point", "rf", "rf_solvent")),
    (
        "Handling",
        ("appearance", "coloured", "solubility", "dmso_stock", "storage"),
    ),
    ("Safety", ("risk_assessment", "hazards")),
)
DETAILS = tuple(field for _, fields in DETAIL_GROUPS for field in fields)

# The fields logged in the change log, as (column, Compound attribute).
LOGGED_FIELDS = (
    ("label", "label"),
    ("class", "compound_class"),
    ("smiles", "smiles"),
    ("status", "status"),
    ("notes", "notes"),
) + tuple((field, field) for field in DETAILS)

# How each logged field is named to the user.
FIELD_NAMES = {
    "label": "label",
    "class": "class",
    "smiles": "SMILES",
    "status": "status",
    "notes": "notes",
    "archived": "archived",
    "melting_point": "melting point",
    "rf": "Rf",
    "rf_solvent": "Rf solvent system",
    "appearance": "appearance",
    "coloured": "coloured",
    "solubility": "solubility",
    "dmso_stock": "DMSO stock",
    "storage": "storage conditions",
    "risk_assessment": "risk assessment",
    "hazards": "hazard notes",
    "batch": "batch",
    "spectrum": "spectrum",
}

# The parts of a batch that can be corrected, named as the user sees them.
BATCH_PARTS = ("date", "mass", "yield")

# The kinds of spectrum a linked file may be.
SPECTRUM_KINDS = ("IR", "1H NMR", "13C NMR", "mass spec", "UV-vis", "other")

# The units a batch's mass may be given in, with their size in grams.
MASS_UNITS = {"mg": 0.001, "g": 1.0}

# The units a DMSO stock concentration may be given in.
STOCK_UNITS = ("mg/mL", "µg/mL", "mM")

# Typed in place of a value, this clears the field.
CLEAR = "-"

# A number as typed, without a sign.
NUMBER = r"(?:\d+(?:\.\d*)?|\.\d+)"


class CompoundError(Exception):
    """A compound or register that can't be used, with a message for the user."""


@dataclass(frozen=True)
class MeltingRange:
    """A melting range in kelvin; low equals high for a sharp melting point."""

    low: float
    high: float

    @property
    def width(self) -> float:
        # Rounded so that, say, 457.1 - 455.1 counts as exactly 2.
        return round(self.high - self.low, 6)

    def __str__(self) -> str:
        if self.low == self.high:
            return f"{self.low:g} K"
        return f"{self.low:g}–{self.high:g} K"


@dataclass(frozen=True)
class Stock:
    """A stock solution's concentration, in one of STOCK_UNITS."""

    value: float
    unit: str

    def __str__(self) -> str:
        return f"{self.value:g} {self.unit}"


@dataclass(frozen=True)
class Batch:
    """One batch of a compound, numbered from 1 in the order added."""

    number: int
    made_on: str
    mass_g: float | None = None
    yield_percent: float | None = None

    @property
    def mass(self) -> str | None:
        """The mass to 3 s.f., in mg below 1 g and in g from 1 g up."""
        if self.mass_g is None:
            return None
        if self.mass_g < 1:
            return f"{sig_figs(self.mass_g * 1000)} mg"
        return f"{sig_figs(self.mass_g)} g"

    @property
    def yield_text(self) -> str | None:
        if self.yield_percent is None:
            return None
        return f"{sig_figs(self.yield_percent)}%"

    @property
    def warning(self) -> str:
        """A warning about the yield, or "" if there is nothing to say."""
        if self.yield_percent is not None and self.yield_percent > 100:
            return "A yield over 100% usually means the product is still wet or impure."
        return ""

    @property
    def details(self) -> str:
        """The date, mass and yield, such as "2026-10-18, 152 mg, 64.2%"."""
        parts = [self.made_on, self.mass, self.yield_text]
        return ", ".join(part for part in parts if part)

    def __str__(self) -> str:
        return f"{self.number}: {self.details}"


@dataclass(frozen=True)
class Spectrum:
    """A spectra file linked to a compound, by its path in the workspace."""

    path: str
    kind: str | None
    added: str

    def __str__(self) -> str:
        return self.path if self.kind is None else f"{self.kind} {self.path}"


@dataclass(frozen=True)
class Compound:
    number: int
    label: str
    compound_class: str | None = None
    smiles: str | None = None
    formula: str | None = None
    molar_mass: float | None = None
    status: str = DEFAULT_STATUS
    notes: str | None = None
    archived: bool = False
    melting_point: MeltingRange | None = None
    rf: float | None = None
    rf_solvent: str | None = None
    appearance: str | None = None
    # Coloured in solution, so a plate needs a compound-only blank (M3).
    coloured: bool | None = None
    solubility: str | None = None
    dmso_stock: Stock | None = None
    storage: str | None = None
    # "no", or the date the risk assessment was done, as YYYY-MM-DD.
    risk_assessment: str | None = None
    hazards: str | None = None

    @property
    def id(self) -> str:
        return format_id(self.number)


@dataclass(frozen=True)
class Change:
    """One field's change, as logged: None stands for a blank value."""

    field: str
    old: str | None
    new: str | None
    changed: str | None = None

    @property
    def name(self) -> str:
        # A batch correction is logged under its own name, such as "batch 1 mass".
        return FIELD_NAMES.get(self.field, self.field)


def format_id(number: int) -> str:
    return f"SYN-{number:03d}"


def parse_id(text: str) -> int:
    """The number in a compound ID, given as SYN-001, syn-1 or plain 1."""
    match = re.fullmatch(r"(?:syn-)?(\d+)", text.strip(), re.IGNORECASE)
    if match is None:
        raise CompoundError(
            f'"{text.strip()}" isn\'t a compound ID. IDs look like SYN-001.'
        )
    return int(match.group(1))


def _choice(text: str, choices: tuple[str, ...], what: str) -> str | None:
    """The choice ``text`` names, ignoring capitals, hyphens and underscores."""
    wanted = _simplify(text.replace("-", " ").replace("_", " "))
    if not wanted:
        return None
    for choice in choices:
        if _simplify(choice.replace("-", " ")) == wanted:
            return choice
    raise CompoundError(
        f'"{text.strip()}" isn\'t a {what}. Choose one of: {", ".join(choices)}.'
    )


def _simplify(text: str) -> str:
    return " ".join(text.split()).casefold()


def parse_class(text: str) -> str | None:
    """The class ``text`` names, or None if it is blank."""
    return _choice(text, CLASSES, "compound class")


def parse_status(text: str) -> str:
    """The status ``text`` names, or planned if it is blank."""
    return _choice(text, STATUSES, "status") or DEFAULT_STATUS


def read_smiles(smiles: str) -> tuple[str, float]:
    """The molecular formula and molar mass (g/mol) of a SMILES.

    The molar mass uses RDKit's standard atomic weights (decision 0014).
    """
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors
    from rdkit.rdBase import BlockLogs

    smiles = smiles.strip()
    if any(character.isspace() for character in smiles):
        raise CompoundError(
            f'The SMILES "{smiles}" has a space in it. A SMILES is one word: '
            "check it, or leave it blank and add it later."
        )
    # RDKit prints its own error for an unreadable SMILES; the message below
    # replaces it.
    blocked = BlockLogs()
    molecule = Chem.MolFromSmiles(smiles)
    del blocked
    if molecule is None or molecule.GetNumAtoms() == 0:
        raise CompoundError(
            f'RDKit can\'t read the SMILES "{smiles}". '
            "Check it, or leave it blank and add it later."
        )
    return rdMolDescriptors.CalcMolFormula(molecule), Descriptors.MolWt(molecule)


def parse_melting_point(text: str) -> MeltingRange:
    """The melting range ``text`` gives, in kelvin: ``455-457`` or ``456``."""
    match = re.fullmatch(
        rf"({NUMBER})\s*K?\s*(?:(?:-|–|to)\s*({NUMBER})\s*K?)?",
        text.strip(),
        re.IGNORECASE,
    )
    if match is None:
        raise CompoundError(
            f'"{text.strip()}" isn\'t a melting range. Type it in kelvin, '
            "lower temperature first, such as 455-457."
        )
    low = float(match.group(1))
    high = low if match.group(2) is None else float(match.group(2))
    if low <= 0:
        raise CompoundError("A melting point is always above 0 K.")
    if low > high:
        raise CompoundError(
            f"The melting range runs from high to low ({low:g} to {high:g} K). "
            "Type the lower temperature first."
        )
    return MeltingRange(low, high)


def parse_rf(text: str) -> float:
    """The Rf value ``text`` gives, from 0 to 1."""
    text = text.strip()
    if re.fullmatch(rf"-?{NUMBER}", text) is None:
        raise CompoundError(
            f'"{text}" isn\'t an Rf value. Type a number from 0 to 1, such as 0.45.'
        )
    rf = float(text)
    if not 0 <= rf <= 1:
        raise CompoundError(f'An Rf value is between 0 and 1. "{text}" isn\'t.')
    return rf


def parse_yes_no(text: str) -> bool:
    answer = text.strip().casefold()
    if answer in ("yes", "y"):
        return True
    if answer in ("no", "n"):
        return False
    raise CompoundError(f'Answer yes or no. "{text.strip()}" isn\'t either.')


def parse_stock(text: str) -> Stock:
    """The concentration ``text`` gives, such as ``10 mg/mL``."""
    units = ", ".join(STOCK_UNITS[:-1]) + f" or {STOCK_UNITS[-1]}"
    match = re.fullmatch(rf"({NUMBER})\s*(\S*)", text.strip())
    if match is None:
        raise CompoundError(
            f'"{text.strip()}" isn\'t a concentration. Type a number and a unit '
            f"({units}), such as 10 mg/mL."
        )
    number, typed = match.groups()
    # µ is hard to type on most keyboards, so u stands in for it.
    wanted = typed.replace("u", "µ").casefold()
    unit = next((unit for unit in STOCK_UNITS if unit.casefold() == wanted), None)
    if unit is None:
        raise CompoundError(
            f"Give the unit as well, one of {units}, such as 10 mg/mL."
            if not typed
            else f'"{typed}" isn\'t a unit Synthase knows. Use {units}.'
        )
    value = float(number)
    if value == 0:
        raise CompoundError("A DMSO stock concentration must be above zero.")
    return Stock(value, unit)


def parse_risk_assessment(text: str) -> str:
    """``no``, or the date ``text`` gives as YYYY-MM-DD or DD/MM/YYYY."""
    text = text.strip()
    if text.casefold() in ("no", "n"):
        return "no"
    if text.casefold() in ("yes", "y"):
        raise CompoundError(
            "Type the date the risk assessment was done instead of yes, "
            "such as 2026-10-18 or 18/10/2026."
        )
    return _parse_date(text, "the risk assessment was done", ", or no").isoformat()


def _parse_date(text: str, event: str, other: str = "") -> date:
    """The past or present date ``text`` gives, as YYYY-MM-DD or DD/MM/YYYY.

    ``event`` says what the date is of, as in "the batch was made".
    """
    text = text.strip()
    if match := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text):
        year, month, day = match.groups()
    elif match := re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text):
        day, month, year = match.groups()
    else:
        raise CompoundError(
            f'"{text}" isn\'t a date. Type the date {event}, '
            f"such as 2026-10-18 or 18/10/2026{other}."
        )
    try:
        when = date(int(year), int(month), int(day))
    except ValueError:
        raise CompoundError(f'"{text}" isn\'t a real date.') from None
    _refuse_future(when, event)
    return when


def _refuse_future(when: date, event: str) -> None:
    if when > date.today():
        raise CompoundError(
            f"{when.isoformat()} is in the future. Type the date {event}."
        )


def parse_batch_date(text: str) -> date:
    """The date a batch was made: today if ``text`` is blank."""
    if not text.strip():
        return date.today()
    return _parse_date(text, "the batch was made")


def parse_mass(text: str) -> float:
    """The mass ``text`` gives, such as ``152 mg``, in grams."""
    units = " or ".join(MASS_UNITS)
    match = re.fullmatch(rf"({NUMBER})\s*(\S*)", text.strip())
    if match is None:
        raise CompoundError(
            f'"{text.strip()}" isn\'t a mass. Type a number and a unit ({units}), '
            "such as 152 mg."
        )
    number, typed = match.groups()
    if not typed:
        raise CompoundError(f"Give the unit as well, {units}, such as 152 mg.")
    if typed.casefold() not in MASS_UNITS:
        raise CompoundError(f'"{typed}" isn\'t a unit Synthase knows. Use {units}.')
    grams = float(number) * MASS_UNITS[typed.casefold()]
    _check_mass(grams)
    return grams


def _check_mass(grams: float) -> None:
    if grams <= 0:
        raise CompoundError("The mass made must be above zero.")


def _check_yield(percent: float) -> None:
    if percent < 0:
        raise CompoundError("A yield can't be below 0%.")


def parse_yield(text: str) -> float:
    """The percentage yield ``text`` gives, such as ``64.2`` or ``64.2%``."""
    text = text.strip()
    match = re.fullmatch(rf"(-?{NUMBER})\s*%?", text)
    if match is None:
        raise CompoundError(
            f'"{text}" isn\'t a yield. Type a percentage, such as 64.2.'
        )
    percent = float(match.group(1))
    _check_yield(percent)
    return percent


def parse_batch_number(text: str) -> int:
    """The batch number ``text`` gives, such as ``2``."""
    text = text.strip()
    if not re.fullmatch(r"\d+", text) or int(text) == 0:
        raise CompoundError(
            f'"{text}" isn\'t a batch number. Batches are numbered 1, 2, 3 and so on.'
        )
    return int(text)


def parse_batch_value(part: str, text: str) -> object:
    """The new value ``text`` gives for a batch's ``part``: None if it is cleared.

    ``part`` is one of BATCH_PARTS. The date comes back as YYYY-MM-DD.
    """
    cleared = text.strip() == CLEAR
    if part == "date":
        if cleared:
            raise CompoundError("A batch always has a date, so it can't be cleared.")
        return parse_batch_date(text).isoformat()
    if cleared:
        return None
    return parse_mass(text) if part == "mass" else parse_yield(text)


def parse_spectrum_kind(text: str) -> str | None:
    """The kind of spectrum ``text`` names, or None if it is blank."""
    return _choice(text, SPECTRUM_KINDS, "kind of spectrum")


def _plain(text: str) -> str:
    return text.strip()


# How each characterisation, handling and safety field is read from what the
# user types (never blank or CLEAR).
DETAIL_PARSERS: dict[str, Callable[[str], object]] = {
    "melting_point": parse_melting_point,
    "rf": parse_rf,
    "rf_solvent": _plain,
    "appearance": _plain,
    "coloured": parse_yes_no,
    "solubility": _plain,
    "dmso_stock": parse_stock,
    "storage": _plain,
    "risk_assessment": parse_risk_assessment,
    "hazards": _plain,
}


def as_text(value: object) -> str | None:
    """A field's value as the change log and the questions show it."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def check_label(workspace: Path, label: str, number: int | None = None) -> str:
    """``label`` without surrounding spaces, if no other compound has it.

    ``number`` is the compound being relabelled, which may keep its own label.
    """
    label = label.strip()
    if not label:
        raise CompoundError("A compound needs a label, such as a short name.")
    register = workspace / REGISTER_NAME
    if not register.exists():
        return label
    with _open(workspace) as db:
        _refuse_repeat(db, label, number)
    return label


def _refuse_repeat(
    db: sqlite3.Connection, label: str, number: int | None = None
) -> None:
    for other, existing in db.execute("SELECT id, label FROM compounds"):
        if other != number and _simplify(existing) == _simplify(label):
            raise CompoundError(
                f'"{existing}" is already {format_id(other)}. Choose another label.'
            )


def add_compound(
    workspace: Path,
    label: str,
    compound_class: str | None = None,
    smiles: str | None = None,
    status: str | None = None,
    notes: str | None = None,
    **details: str | None,
) -> Compound:
    """Add a compound to the register, and log it, in one step.

    Only ``label`` is required. Class and status may be given in any form
    parse_class and parse_status accept. ``details`` gives any of the fields
    in DETAILS, as typed.
    """
    label = check_label(workspace, label)
    compound_class = parse_class(compound_class or "")
    status = parse_status(status or "")
    smiles = (smiles or "").strip() or None
    formula, molar_mass = read_smiles(smiles) if smiles else (None, None)
    notes = (notes or "").strip() or None
    values = {
        field: DETAIL_PARSERS[field](text)
        for field, text in details.items()
        if text is not None and text.strip()
    }
    compound = Compound(
        0,
        label,
        compound_class,
        smiles,
        formula,
        molar_mass,
        status,
        notes,
        **values,
    )
    _check_rf(compound)

    with _open(workspace) as db:
        _refuse_repeat(db, label)
        saved = _saved(compound)
        cursor = db.execute(
            f"INSERT INTO compounds ({', '.join(saved)}) "
            f"VALUES ({', '.join('?' * len(saved))})",
            tuple(saved.values()),
        )
        compound = replace(compound, number=cursor.lastrowid)
        _log(
            db,
            compound.number,
            [
                Change(column, None, as_text(getattr(compound, attribute)))
                for column, attribute in LOGGED_FIELDS
                if getattr(compound, attribute) is not None
            ],
        )
    return compound


def _check_rf(compound: Compound) -> None:
    check_rf(compound.rf, compound.rf_solvent)


def check_rf(rf: object, rf_solvent: object) -> None:
    """Refuse an Rf value without the solvent system it was measured in."""
    if rf is not None and rf_solvent is None:
        raise CompoundError(
            "An Rf value needs the solvent system it was measured in, "
            'such as "hexane:ethyl acetate 3:1".'
        )


def _saved(compound: Compound) -> dict[str, object]:
    """The columns saved for ``compound``, except its ID and archived flag."""
    melting_point = compound.melting_point
    stock = compound.dmso_stock
    return {
        "label": compound.label,
        "class": compound.compound_class,
        "smiles": compound.smiles,
        "formula": compound.formula,
        "molar_mass": compound.molar_mass,
        "status": compound.status,
        "notes": compound.notes,
        "mp_low": None if melting_point is None else melting_point.low,
        "mp_high": None if melting_point is None else melting_point.high,
        "rf": compound.rf,
        "rf_solvent": compound.rf_solvent,
        "appearance": compound.appearance,
        "coloured": None if compound.coloured is None else int(compound.coloured),
        "solubility": compound.solubility,
        "dmso_stock": None if stock is None else stock.value,
        "dmso_stock_unit": None if stock is None else stock.unit,
        "storage": compound.storage,
        "risk_assessment": compound.risk_assessment,
        "hazards": compound.hazards,
    }


def parse_field(workspace: Path, number: int, field: str, text: str) -> object:
    """The value ``text`` gives ``field`` of compound ``number``.

    ``field`` is a column in LOGGED_FIELDS. CLEAR gives None, which empties
    the field; label and status can't be emptied.
    """
    text = text.strip()
    if text == CLEAR:
        if field in ("label", "status"):
            raise CompoundError(
                f"A compound always has a {field}, so it can't be cleared."
            )
        return None
    if field == "label":
        return check_label(workspace, text, number)
    if field == "class":
        return parse_class(text)
    if field == "smiles":
        read_smiles(text)
        return text
    if field == "status":
        return parse_status(text)
    if field in DETAIL_PARSERS:
        return DETAIL_PARSERS[field](text)
    return text


def edit_compound(
    workspace: Path,
    text: str,
    confirm: Callable[[Change], bool],
    label: str | None = None,
    compound_class: str | None = None,
    smiles: str | None = None,
    status: str | None = None,
    notes: str | None = None,
    **details: str | None,
) -> tuple[Compound, list[Change]]:
    """Fill in or change fields of compound ``text``, and log it, in one step.

    ``details`` gives any of the fields in DETAILS. A field left as None or
    blank is kept; CLEAR empties it. Every value is checked before anything
    is asked. Filling a blank field needs nothing more, but changing a set
    one happens only if ``confirm`` says yes. Returns the compound as saved
    and the changes made.
    """
    compound = get_compound(workspace, text)
    given = {
        "label": label,
        "compound_class": compound_class,
        "smiles": smiles,
        "status": status,
        "notes": notes,
        **details,
    }
    wanted = {}
    for column, attribute in LOGGED_FIELDS:
        value = given.get(attribute)
        if value is None or not value.strip():
            continue
        new = parse_field(workspace, compound.number, column, value)
        if new != getattr(compound, attribute):
            wanted[attribute] = new
    _check_rf(replace(compound, **wanted))
    changes = []
    updates = {}
    for column, attribute in LOGGED_FIELDS:
        if attribute not in wanted:
            continue
        old = getattr(compound, attribute)
        change = Change(column, as_text(old), as_text(wanted[attribute]))
        if old is None or confirm(change):
            changes.append(change)
            updates[attribute] = wanted[attribute]
    if not changes:
        return compound, []

    if "smiles" in updates:
        smiles = updates["smiles"]
        formula, molar_mass = read_smiles(smiles) if smiles else (None, None)
        updates.update(formula=formula, molar_mass=molar_mass)
    compound = replace(compound, **updates)
    # A no to one question can still part an Rf from its solvent system.
    _check_rf(compound)
    with _open(workspace) as db:
        _refuse_repeat(db, compound.label, compound.number)
        saved = _saved(compound)
        db.execute(
            f"UPDATE compounds SET {', '.join(f'{column} = ?' for column in saved)} "
            "WHERE id = ?",
            (*saved.values(), compound.number),
        )
        _log(db, compound.number, changes)
    return compound, changes


def archive_compound(workspace: Path, text: str, archived: bool = True) -> Compound:
    """Hide compound ``text`` from the list, or with archived=False, bring it back.

    Nothing is deleted, and the change is logged.
    """
    compound = get_compound(workspace, text)
    if compound.archived == archived:
        raise CompoundError(
            f"{compound.id} is already archived."
            if archived
            else f"{compound.id} isn't archived, so there's nothing to restore."
        )
    with _open(workspace) as db:
        db.execute(
            "UPDATE compounds SET archived = ? WHERE id = ?",
            (int(archived), compound.number),
        )
        _log(
            db,
            compound.number,
            [Change("archived", _yes_no(not archived), _yes_no(archived))],
        )
    return replace(compound, archived=archived)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def compound_history(workspace: Path, text: str) -> tuple[Compound, list[Change]]:
    """Compound ``text`` and every change logged for it, oldest first."""
    compound = get_compound(workspace, text)
    found = _read(
        workspace,
        "SELECT field, old, new, changed FROM changes WHERE compound_id = ? "
        "ORDER BY id",
        (compound.number,),
    )
    return compound, [Change(*row) for row in found]


def _log(db: sqlite3.Connection, number: int, changes: list[Change]) -> None:
    changed = _now()
    db.executemany(
        "INSERT INTO changes (compound_id, changed, field, old, new) "
        "VALUES (?, ?, ?, ?, ?)",
        [(number, changed, change.field, change.old, change.new) for change in changes],
    )


def add_batch(
    workspace: Path,
    text: str,
    made_on: date | None = None,
    mass_g: float | None = None,
    yield_percent: float | None = None,
) -> tuple[Compound, Batch]:
    """Add a batch to compound ``text``, and log it, in one step.

    The date defaults to today. A batch needs its mass, its yield or both.
    Takes numbers rather than typed text, so /yield (M3) can call it.
    """
    compound = get_compound(workspace, text)
    made_on = made_on or date.today()
    _refuse_future(made_on, "the batch was made")
    if mass_g is None and yield_percent is None:
        raise CompoundError("A batch needs its mass made, its yield or both.")
    if mass_g is not None:
        _check_mass(mass_g)
    if yield_percent is not None:
        _check_yield(yield_percent)
    with _open(workspace) as db:
        (count,) = db.execute(
            "SELECT COUNT(*) FROM batches WHERE compound_id = ?", (compound.number,)
        ).fetchone()
        batch = Batch(count + 1, made_on.isoformat(), mass_g, yield_percent)
        db.execute(
            "INSERT INTO batches (compound_id, made_on, mass_g, yield_percent) "
            "VALUES (?, ?, ?, ?)",
            (compound.number, batch.made_on, mass_g, yield_percent),
        )
        _log(db, compound.number, [Change("batch", None, str(batch))])
    return compound, batch


def compound_batches(workspace: Path, compound: Compound) -> list[Batch]:
    """Every batch of ``compound`` not removed, in the order added."""
    return [
        batch for _, batch, removed in _all_batches(workspace, compound) if not removed
    ]


def _all_batches(
    workspace: Path, compound: Compound
) -> list[tuple[int, Batch, str | None]]:
    """Every batch of ``compound``, removed ones too, in the order added.

    Each comes with its row ID and when it was removed. Batches are numbered
    by counting every row, so removing one never renumbers the rest.
    """
    found = _read(
        workspace,
        "SELECT id, made_on, mass_g, yield_percent, removed FROM batches "
        "WHERE compound_id = ? ORDER BY id",
        (compound.number,),
    )
    return [
        (row_id, Batch(number, *values), removed)
        for number, (row_id, *values, removed) in enumerate(found, start=1)
    ]


def get_batch(workspace: Path, text: str, number: str) -> tuple[Compound, Batch]:
    """Compound ``text`` and its batch ``number``, which must not be removed."""
    compound = get_compound(workspace, text)
    return compound, _find_batch(workspace, compound, number)[1]


def _find_batch(workspace: Path, compound: Compound, text: str) -> tuple[int, Batch]:
    number = parse_batch_number(text)
    every = _all_batches(workspace, compound)
    if number > len(every):
        kept = [batch.number for _, batch, removed in every if not removed]
        there = f"Its batches are {_listed(kept)}." if kept else "It has no batches."
        raise CompoundError(f"{compound.id} has no batch {number}. {there}")
    row_id, batch, removed = every[number - 1]
    if removed:
        raise CompoundError(
            f"Batch {number} of {compound.id} was removed on {removed[:10]}."
        )
    return row_id, batch


def _listed(numbers: list[int]) -> str:
    """``numbers`` as "1", "1 and 3" or "1, 3 and 4"."""
    words = [str(number) for number in numbers]
    if len(words) == 1:
        return words[0]
    return f"{', '.join(words[:-1])} and {words[-1]}"


def edit_batch(
    workspace: Path,
    text: str,
    number: str,
    confirm: Callable[[Change], bool],
    made_on: str | None = None,
    mass: str | None = None,
    yield_percent: str | None = None,
) -> tuple[Compound, Batch, list[Change]]:
    """Correct the date, mass or yield of batch ``number`` of compound ``text``.

    Works as edit_compound does: the values are typed text, a value left as
    None or blank is kept, CLEAR empties the mass or yield, and changing a set
    value happens only if ``confirm`` says yes. Each change is logged as, say,
    "batch 1 mass". Returns the compound, the batch as saved and the changes.
    """
    compound = get_compound(workspace, text)
    row_id, batch = _find_batch(workspace, compound, number)
    current = {
        "date": batch.made_on,
        "mass": batch.mass_g,
        "yield": batch.yield_percent,
    }
    wanted = {}
    for part, value in zip(BATCH_PARTS, (made_on, mass, yield_percent), strict=True):
        if value is None or not value.strip():
            continue
        new = parse_batch_value(part, value)
        if new != current[part]:
            wanted[part] = new
    asked = _corrected(batch, {**current, **wanted})
    if asked.mass_g is None and asked.yield_percent is None:
        raise CompoundError("A batch needs its mass made, its yield or both.")
    changes = []
    for part, new in wanted.items():
        old = _batch_text(batch, part)
        change = Change(f"batch {batch.number} {part}", old, _batch_text(asked, part))
        if old is None or confirm(change):
            changes.append(change)
            current[part] = new
    if not changes:
        return compound, batch, []

    batch = _corrected(batch, current)
    with _open(workspace) as db:
        db.execute(
            "UPDATE batches SET made_on = ?, mass_g = ?, yield_percent = ? "
            "WHERE id = ?",
            (batch.made_on, batch.mass_g, batch.yield_percent, row_id),
        )
        _log(db, compound.number, changes)
    return compound, batch, changes


def _corrected(batch: Batch, values: dict[str, object]) -> Batch:
    return replace(
        batch,
        made_on=values["date"],
        mass_g=values["mass"],
        yield_percent=values["yield"],
    )


def _batch_text(batch: Batch, part: str) -> str | None:
    """How ``batch``'s ``part`` is shown and logged."""
    return {"date": batch.made_on, "mass": batch.mass, "yield": batch.yield_text}[part]


def remove_batch(workspace: Path, text: str, number: str) -> tuple[Compound, Batch]:
    """Hide batch ``number`` of compound ``text`` from the card, and log it.

    Nothing is deleted, and the other batches keep their numbers.
    """
    compound = get_compound(workspace, text)
    row_id, batch = _find_batch(workspace, compound, number)
    with _open(workspace) as db:
        db.execute("UPDATE batches SET removed = ? WHERE id = ?", (_now(), row_id))
        _log(db, compound.number, [Change("batch", str(batch), "removed")])
    return compound, batch


def link_spectrum(
    workspace: Path, text: str, file: Path, kind: str | None = None
) -> tuple[Compound, Spectrum]:
    """Link the spectra file ``file`` to compound ``text``, and log it.

    A relative ``file`` counts from the current folder, or from the workspace
    if the current folder has no such file. It must be inside the workspace.
    ``kind`` may be given in any form parse_spectrum_kind accepts.
    """
    compound = get_compound(workspace, text)
    kind = parse_spectrum_kind(kind or "")
    path = spectra_path(workspace, file)
    with _open(workspace) as db:
        for (linked,) in db.execute(
            "SELECT path FROM spectra WHERE compound_id = ? AND removed IS NULL",
            (compound.number,),
        ):
            if linked.casefold() == path.casefold():
                raise CompoundError(f"{linked} is already linked to {compound.id}.")
        spectrum = Spectrum(path, kind, _now())
        db.execute(
            "INSERT INTO spectra (compound_id, path, added, kind) VALUES (?, ?, ?, ?)",
            (compound.number, path, spectrum.added, kind),
        )
        _log(db, compound.number, [Change("spectrum", None, str(spectrum))])
    return compound, spectrum


def spectra_path(workspace: Path, file: Path) -> str:
    """``file``'s path inside the workspace, with / between folders.

    A relative ``file`` counts from the current folder, or from the workspace
    if the current folder has no such file.
    """
    file = Path(file).expanduser()
    if not file.is_absolute() and not file.exists() and (workspace / file).exists():
        file = workspace / file
    file = file.resolve()
    if not file.exists():
        raise CompoundError(f"There's no file at {file}.")
    if not file.is_file():
        raise CompoundError(f"{file} is a folder, not a file.")
    try:
        inside = file.relative_to(workspace.resolve())
    except ValueError:
        raise CompoundError(
            f"Spectra files must be inside the workspace ({workspace}). "
            'Copy it in, for example into a "spectra" folder, then link it.'
        ) from None
    return inside.as_posix()


def compound_spectra(workspace: Path, compound: Compound) -> list[Spectrum]:
    """Every spectra file linked to ``compound`` and not unlinked, in order."""
    return [spectrum for _, spectrum in _linked(workspace, compound)]


def _linked(workspace: Path, compound: Compound) -> list[tuple[int, Spectrum]]:
    """Every link of ``compound`` not unlinked, with its row ID, in order."""
    found = _read(
        workspace,
        "SELECT id, path, kind, added FROM spectra "
        "WHERE compound_id = ? AND removed IS NULL ORDER BY id",
        (compound.number,),
    )
    return [(row_id, Spectrum(*values)) for row_id, *values in found]


def get_spectrum(workspace: Path, text: str, file: str) -> tuple[Compound, Spectrum]:
    """Compound ``text`` and its link to ``file``."""
    compound = get_compound(workspace, text)
    return compound, _find_spectrum(workspace, compound, file)[1]


def _find_spectrum(
    workspace: Path, compound: Compound, file: str
) -> tuple[int, Spectrum]:
    """The link to ``file``, typed as the card shows it or as it was linked.

    Capitals, and backslashes or slashes between folders, don't matter, so a
    file that has since moved can still be found.
    """
    linked = _linked(workspace, compound)
    if not linked:
        raise CompoundError(f"{compound.id} has no spectra linked.")
    typed = file.strip().strip('"')
    # A file that is still there is found the same way as when it was linked.
    with suppress(CompoundError):
        typed = spectra_path(workspace, Path(typed))
    wanted = typed.replace("\\", "/").casefold()
    for row_id, spectrum in linked:
        if spectrum.path.casefold() == wanted:
            return row_id, spectrum
    paths = ", ".join(str(Path(spectrum.path)) for _, spectrum in linked)
    raise CompoundError(
        f'"{file.strip()}" isn\'t linked to {compound.id}. '
        f"Its linked files are: {paths}."
    )


def unlink_spectrum(workspace: Path, text: str, file: str) -> tuple[Compound, Spectrum]:
    """Hide the link from compound ``text`` to ``file``, and log it.

    The file itself is not touched, and the link stays in the register.
    """
    compound = get_compound(workspace, text)
    row_id, spectrum = _find_spectrum(workspace, compound, file)
    with _open(workspace) as db:
        db.execute("UPDATE spectra SET removed = ? WHERE id = ?", (_now(), row_id))
        _log(db, compound.number, [Change("spectrum", str(spectrum), "removed")])
    return compound, spectrum


def get_compound(workspace: Path, text: str) -> Compound:
    """The compound whose ID is ``text``, in any form parse_id accepts."""
    number = parse_id(text)
    found = _read(workspace, f"SELECT {COLUMNS} FROM compounds WHERE id = ?", (number,))
    if not found:
        raise CompoundError(
            f"There's no compound {format_id(number)} in the register. "
            'Run "syn compound list" to see every ID.'
        )
    return _compound(found[0])


def _compound(row: tuple) -> Compound:
    (
        archived,
        mp_low,
        mp_high,
        rf,
        rf_solvent,
        appearance,
        coloured,
        solubility,
        dmso_stock,
        dmso_stock_unit,
        storage,
        risk_assessment,
        hazards,
    ) = row[8:]
    return Compound(
        *row[:8],
        archived=bool(archived),
        melting_point=None if mp_low is None else MeltingRange(mp_low, mp_high),
        rf=rf,
        rf_solvent=rf_solvent,
        appearance=appearance,
        coloured=None if coloured is None else bool(coloured),
        solubility=solubility,
        dmso_stock=None if dmso_stock is None else Stock(dmso_stock, dmso_stock_unit),
        storage=storage,
        risk_assessment=risk_assessment,
        hazards=hazards,
    )


def list_compounds(
    workspace: Path,
    status: str | None = None,
    compound_class: str | None = None,
    archived: bool = False,
) -> list[Compound]:
    """Every compound in ID order, or only those with the status and class given.

    Status and class may be given in any form parse_status and parse_class
    accept. Archived compounds are left out unless ``archived`` is true.
    """
    wanted_status = None if status is None else parse_status(status)
    wanted_class = parse_class(compound_class or "")
    everything = [
        _compound(row)
        for row in _read(workspace, f"SELECT {COLUMNS} FROM compounds ORDER BY id")
    ]
    return [
        compound
        for compound in everything
        if wanted_status in (None, compound.status)
        and wanted_class in (None, compound.compound_class)
        and (archived or not compound.archived)
    ]


def missing_fields(
    compound: Compound,
    batches: list[Batch] | None = None,
    spectra: list[Spectrum] | None = None,
) -> list[str]:
    """What is still blank in ``compound``, one plain sentence each.

    ``batches`` and ``spectra`` are its batches and linked files; None leaves
    them out of the check.
    """
    missing = []
    if compound.compound_class is None:
        missing.append("no class yet")
    if compound.smiles is None:
        missing.append("no SMILES yet, so no formula or molar mass")
    if compound.notes is None:
        missing.append("no notes yet")
    for field, blank in (
        ("melting_point", "no melting point yet"),
        ("rf", "no Rf value yet"),
        ("appearance", "no appearance yet"),
        ("coloured", "not recorded whether it is coloured"),
        ("solubility", "no solubility yet"),
        ("dmso_stock", "no DMSO stock concentration yet"),
        ("storage", "no storage conditions yet"),
        ("risk_assessment", "no risk assessment recorded"),
        ("hazards", "no hazard notes yet"),
    ):
        if getattr(compound, field) is None:
            missing.append(blank)
        elif field == "risk_assessment" and compound.risk_assessment == "no":
            missing.append("risk assessment not done yet")
    if batches == []:
        missing.append("no batches yet")
    if spectra == []:
        missing.append("no spectra linked yet")
    return missing


def purity_warnings(compound: Compound, config: Config) -> list[str]:
    """Lines flagging a melting range wider than the config's purity rule.

    The rule's own warning follows while it is unverified. Empty when the
    range is within the rule, or not recorded.
    """
    if compound.melting_point is None:
        return []
    rule = config.get("melting_point.purity_range")
    width = compound.melting_point.width
    if width <= rule.value:
        return []
    flag = (
        f"! The melting range is {width:g} K wide, wider than the {rule.name} "
        f"({rule.describe()}), so the sample may not be pure."
    )
    return [flag, rule.warning] if rule.warning else [flag]


def table_row(compound: Compound) -> tuple[str | None, ...]:
    """``compound``'s row under TABLE_HEADINGS, with None for a blank cell."""
    molar_mass = None if compound.molar_mass is None else sig_figs(compound.molar_mass)
    return (
        compound.id,
        f"{compound.label} (archived)" if compound.archived else compound.label,
        compound.compound_class,
        compound.status,
        compound.formula,
        molar_mass,
    )


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def _open(workspace: Path) -> Iterator[sqlite3.Connection]:
    """The register as one transaction: committed and closed at the end.

    It is created, with every table, if it doesn't exist yet.
    """
    path = workspace / REGISTER_NAME
    # isolation_level=None: transactions start only where BEGIN says.
    with closing(sqlite3.connect(path, isolation_level=None)) as db:
        version = _version(db, path)
        db.execute("PRAGMA foreign_keys = ON")
        _upgrade(db, version)
        db.execute("BEGIN")
        try:
            yield db
        except BaseException:
            db.rollback()
            raise
        db.commit()


def _read(
    workspace: Path, sql: str, parameters: tuple[object, ...] = ()
) -> list[tuple]:
    """The rows ``sql`` selects from the register, opened read-only.

    A register that doesn't exist yet has no rows, and isn't created.
    """
    path = workspace / REGISTER_NAME
    if not path.exists():
        return []
    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        version = _version(db, path)
        if version == 0:
            return []
        if version == SCHEMA_VERSION:
            return db.execute(sql, parameters).fetchall()
        # An older register is read through an upgraded copy in memory; the
        # file itself is upgraded by the next command that writes to it.
        with closing(sqlite3.connect(":memory:", isolation_level=None)) as copy:
            db.backup(copy)
            _upgrade(copy, version)
            return copy.execute(sql, parameters).fetchall()


def _upgrade(db: sqlite3.Connection, version: int) -> None:
    """Bring the register from ``version`` up to SCHEMA_VERSION, in one step.

    Version 0 is a new, empty file.
    """
    if version == SCHEMA_VERSION:
        return
    steps = "".join(UPGRADES[n] for n in range(version + 1, SCHEMA_VERSION + 1))
    db.executescript(f"BEGIN; {steps} PRAGMA user_version = {SCHEMA_VERSION}; COMMIT;")


def _version(db: sqlite3.Connection, path: Path) -> int:
    """The register's schema version, if this Synthase can use it."""
    try:
        version = db.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.DatabaseError:
        raise CompoundError(
            f"{path} isn't a compound register Synthase can read. "
            "If you replaced it, put the original back from a backup."
        ) from None
    if version > SCHEMA_VERSION:
        raise CompoundError(
            f"{path} was made by a newer version of Synthase. "
            "Update Synthase, then try again."
        )
    return version
