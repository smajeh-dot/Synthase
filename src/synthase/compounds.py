"""The compound register: every compound in the project, from idea to tested.

This is the shared command layer for `/compound` (decision 0012). It does the
work and raises CompoundError with a message for the user, but never prints or
asks anything; the command line and the app do that. The rules are in
docs/decisions/0014-compound-register.md.
"""

import re
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from synthase.numbers import sig_figs

REGISTER_NAME = "compounds.sqlite"
SCHEMA_VERSION = 1
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

# The columns of a Compound, in order.
COLUMNS = "id, label, class, smiles, formula, molar_mass, status, notes, archived"

# The table `list` shows and saves as CSV.
TABLE_HEADINGS = ("ID", "Label", "Class", "Status", "Formula", "Molar mass (g/mol)")

# The fields logged in the change log, as (column, Compound attribute).
LOGGED_FIELDS = (
    ("label", "label"),
    ("class", "compound_class"),
    ("smiles", "smiles"),
    ("status", "status"),
    ("notes", "notes"),
)

# How each logged field is named to the user.
FIELD_NAMES = {
    "label": "label",
    "class": "class",
    "smiles": "SMILES",
    "status": "status",
    "notes": "notes",
    "archived": "archived",
}

# Typed in place of a value, this clears the field.
CLEAR = "-"


class CompoundError(Exception):
    """A compound or register that can't be used, with a message for the user."""


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
        return FIELD_NAMES[self.field]


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
        if _simplify(choice) == wanted:
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
) -> Compound:
    """Add a compound to the register, and log it, in one step.

    Only ``label`` is required. Class and status may be given in any form
    parse_class and parse_status accept.
    """
    label = check_label(workspace, label)
    compound_class = parse_class(compound_class or "")
    status = parse_status(status or "")
    smiles = (smiles or "").strip() or None
    formula, molar_mass = read_smiles(smiles) if smiles else (None, None)
    notes = (notes or "").strip() or None

    with _open(workspace) as db:
        _refuse_repeat(db, label)
        cursor = db.execute(
            "INSERT INTO compounds (label, class, smiles, formula, molar_mass, "
            "status, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (label, compound_class, smiles, formula, molar_mass, status, notes),
        )
        compound = Compound(
            cursor.lastrowid,
            label,
            compound_class,
            smiles,
            formula,
            molar_mass,
            status,
            notes,
        )
        _log(
            db,
            compound.number,
            [
                Change(column, None, getattr(compound, attribute))
                for column, attribute in LOGGED_FIELDS
                if getattr(compound, attribute) is not None
            ],
        )
    return compound


def parse_field(workspace: Path, number: int, field: str, text: str) -> str | None:
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
) -> tuple[Compound, list[Change]]:
    """Fill in or change fields of compound ``text``, and log it, in one step.

    A field left as None or blank is kept; CLEAR empties it. Every value is
    checked before anything is asked. Filling a blank field needs nothing
    more, but changing a set one happens only if ``confirm`` says yes.
    Returns the compound as saved and the changes made.
    """
    compound = get_compound(workspace, text)
    given = (label, compound_class, smiles, status, notes)
    wanted = []
    for (column, attribute), value in zip(LOGGED_FIELDS, given, strict=True):
        if value is None or not value.strip():
            continue
        new = parse_field(workspace, compound.number, column, value)
        old = getattr(compound, attribute)
        if new != old:
            wanted.append(Change(column, old, new))
    changes = [change for change in wanted if change.old is None or confirm(change)]
    if not changes:
        return compound, []

    attributes = dict(LOGGED_FIELDS)
    updates = {attributes[change.field]: change.new for change in changes}
    if "smiles" in updates:
        smiles = updates["smiles"]
        formula, molar_mass = read_smiles(smiles) if smiles else (None, None)
        updates.update(formula=formula, molar_mass=molar_mass)
    compound = replace(compound, **updates)
    with _open(workspace) as db:
        _refuse_repeat(db, compound.label, compound.number)
        db.execute(
            "UPDATE compounds SET label = ?, class = ?, smiles = ?, formula = ?, "
            "molar_mass = ?, status = ?, notes = ? WHERE id = ?",
            (
                compound.label,
                compound.compound_class,
                compound.smiles,
                compound.formula,
                compound.molar_mass,
                compound.status,
                compound.notes,
                compound.number,
            ),
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
    *fields, archived = row
    return Compound(*fields, archived=bool(archived))


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


def missing_fields(compound: Compound) -> list[str]:
    """What is still blank in ``compound``, one plain sentence each."""
    missing = []
    if compound.compound_class is None:
        missing.append("no class yet")
    if compound.smiles is None:
        missing.append("no SMILES yet, so no formula or molar mass")
    if compound.notes is None:
        missing.append("no notes yet")
    return missing


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
        if version == 0:
            db.executescript(
                f"BEGIN; {SCHEMA} PRAGMA user_version = {SCHEMA_VERSION}; COMMIT;"
            )
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
        if _version(db, path) == 0:
            return []
        return db.execute(sql, parameters).fetchall()


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
