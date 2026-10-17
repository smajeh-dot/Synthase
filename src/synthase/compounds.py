"""The compound register: every compound in the project, from idea to tested.

This is the shared command layer for `/compound` (decision 0012). It does the
work and raises CompoundError with a message for the user, but never prints or
asks anything; the command line and the app do that. The rules are in
docs/decisions/0014-compound-register.md.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

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

# The fields logged in the change log, as (column, Compound attribute).
LOGGED_FIELDS = (
    ("label", "label"),
    ("class", "compound_class"),
    ("smiles", "smiles"),
    ("status", "status"),
    ("notes", "notes"),
)


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

    @property
    def id(self) -> str:
        return format_id(self.number)


def format_id(number: int) -> str:
    return f"SYN-{number:03d}"


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


def check_label(workspace: Path, label: str) -> str:
    """``label`` without surrounding spaces, if no other compound has it."""
    label = label.strip()
    if not label:
        raise CompoundError("A compound needs a label, such as a short name.")
    register = workspace / REGISTER_NAME
    if not register.exists():
        return label
    with _open(workspace) as db:
        _refuse_repeat(db, label)
    return label


def _refuse_repeat(db: sqlite3.Connection, label: str) -> None:
    for number, existing in db.execute("SELECT id, label FROM compounds"):
        if _simplify(existing) == _simplify(label):
            raise CompoundError(
                f'"{existing}" is already {format_id(number)}. Choose another label.'
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
        changed = _now()
        db.executemany(
            "INSERT INTO changes (compound_id, changed, field, old, new) "
            "VALUES (?, ?, ?, NULL, ?)",
            [
                (compound.number, changed, column, getattr(compound, attribute))
                for column, attribute in LOGGED_FIELDS
                if getattr(compound, attribute) is not None
            ],
        )
    return compound


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
