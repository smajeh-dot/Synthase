"""The ``syn`` command-line entry point."""

import argparse
import os
import sys
from collections.abc import Callable
from pathlib import Path

from synthase import __version__
from synthase.compounds import (
    CLASSES,
    DEFAULT_STATUS,
    STATUSES,
    TABLE_HEADINGS,
    Compound,
    CompoundError,
    add_compound,
    check_label,
    get_compound,
    list_compounds,
    missing_fields,
    parse_class,
    parse_status,
    read_smiles,
    table_row,
)
from synthase.config import ConfigError, load_config
from synthase.doctor import run_checks
from synthase.numbers import sig_figs
from synthase.tables import TableFolderError, place_table, write_csv
from synthase.workspace import (
    DEFAULT_NAME,
    WorkspaceError,
    create_workspace,
    current_workspace,
)

INIT_HELP = (
    "Create the folder for your lab data, results, notes and config, outside "
    f"Synthase's code folder. Default: Documents\\{DEFAULT_NAME}. If your "
    "Documents folder syncs to OneDrive, the workspace is backed up automatically."
)

DOCTOR_HELP = (
    "Check that Python, RDKit, the workspace and the config are all set up, "
    "with the fix for anything that isn't, and list every config value not yet "
    "checked against the literature. Exits with code 1 if any check fails."
)

COMPOUND_HELP = "keep track of the project's compounds, from idea to tested"

COMPOUND_ADD_HELP = (
    "Add a compound to the register. With no options, Synthase asks for each "
    "detail; press Enter to skip any but the label. With options, it asks nothing."
)

COMPOUND_SHOW_HELP = (
    "Show everything recorded about one compound, and what is still missing."
)

COMPOUND_LIST_HELP = (
    "List every compound in a table. Filter it with --status or --class, "
    "and save it with --csv."
)

LABEL_NEEDED = (
    'Give the label with --label, or run "syn compound add" with no flags '
    "to be asked for each field."
)

WORKSPACE_CONTENTS = (
    ("raw", "plate reader exports, exactly as saved"),
    ("maps", "plate maps (which compound is in which well)"),
    ("results", "tables and figures Synthase makes"),
    ("notebook", "your notebook entries"),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="syn",
        description=(
            "Synthase: lab calculations and data analysis for the project. "
            "Works offline and gives the same answer for the same input."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"syn {__version__}",
        help="show the Synthase version and exit",
    )
    commands = parser.add_subparsers(dest="command", title="commands")
    init = commands.add_parser(
        "init",
        help="create the workspace for your lab data, results, notes and config",
        description=INIT_HELP,
    )
    init.add_argument(
        "path",
        nargs="?",
        type=Path,
        help=f"where to create it (default: Documents\\{DEFAULT_NAME})",
    )
    commands.add_parser(
        "doctor",
        help="check Synthase is installed and set up, and list unverified values",
        description=DOCTOR_HELP,
    )
    compound = commands.add_parser(
        "compound", help=COMPOUND_HELP, description=COMPOUND_HELP.capitalize() + "."
    )
    compound.set_defaults(compound_parser=compound)
    compound_commands = compound.add_subparsers(
        dest="compound_command", title="commands"
    )
    add = compound_commands.add_parser(
        "add", help="add a compound to the register", description=COMPOUND_ADD_HELP
    )
    add.add_argument("--label", help="a short name for it (needed with any option)")
    add.add_argument(
        "--class",
        dest="compound_class",
        metavar="CLASS",
        help=", ".join(CLASSES[:-1]) + f" or {CLASSES[-1]}",
    )
    add.add_argument("--smiles", help="its structure, written as a SMILES")
    add.add_argument(
        "--status",
        help=f"{DEFAULT_STATUS} (the default), "
        + ", ".join(STATUSES[1:-1])
        + f" or {STATUSES[-1]}",
    )
    add.add_argument("--notes", help="anything else worth recording")
    show = compound_commands.add_parser(
        "show",
        help="show everything recorded about one compound",
        description=COMPOUND_SHOW_HELP,
    )
    show.add_argument("id", metavar="ID", help="its ID, such as SYN-001")
    listing = compound_commands.add_parser(
        "list", help="list every compound in a table", description=COMPOUND_LIST_HELP
    )
    listing.add_argument(
        "--status", help="only compounds with this status: " + ", ".join(STATUSES)
    )
    listing.add_argument(
        "--class",
        dest="compound_class",
        metavar="CLASS",
        help="only compounds of this class: " + ", ".join(CLASSES),
    )
    listing.add_argument(
        "--csv",
        metavar="FILE",
        type=Path,
        help="also save the table as a CSV file. A file name alone goes in the "
        "compounds folder set in config.toml, or in the workspace's results folder",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    # Saved to a file, Windows output can't hold characters such as ⁻ or ≤;
    # show ? for them instead of crashing.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        return init(args.path)
    if args.command == "doctor":
        return doctor()
    if args.command == "compound":
        if args.compound_command == "add":
            return compound_add(args)
        if args.compound_command == "show":
            return compound_show(args.id)
        if args.compound_command == "list":
            return compound_list(args)
        args.compound_parser.print_help()
        return 0
    # With no command, a bare `syn` shows the help text.
    parser.print_help()
    return 0


def ask_yes(prompt: str) -> bool:
    """Ask a question; only "yes" or "y" counts as yes, and no input means no."""
    try:
        reply = input(prompt)
    except EOFError:
        print()
        return False
    return reply.strip().lower() in ("y", "yes")


def init(path: Path | None) -> int:
    try:
        created = create_workspace(path, ask_yes)
    except WorkspaceError as error:
        print(error, file=sys.stderr)
        return 1

    if created.config == "copied":
        print(f"Created the Synthase workspace at {created.path}")
        config_line = "every scientific value Synthase uses, all unverified for now"
    else:
        print(f"Using the existing Synthase workspace at {created.path}")
        config_line = (
            "kept as it was"
            if created.config == "kept"
            else "a fresh copy of the template; "
            f"the old one is saved as {created.backup.name}"
        )
    for name, contents in WORKSPACE_CONTENTS:
        print(f"  {name + os.sep:<12} {contents}")
    print(f"  {'config.toml':<12} {config_line}")
    if created.config != "kept":
        print("Next: open config.toml and check each value against the literature.")
    print("Synthase will use this workspace from now on.")
    return 0


def doctor() -> int:
    report = run_checks()
    print(f"Synthase {__version__} self-test")
    print()
    for check in report.checks:
        print(f"  {'ok' if check.passed else 'FAIL':<6}{check.text}")
        if check.fix:
            print(f"        Fix: {check.fix}")
    print()

    unverified = report.unverified()
    if report.config is None:
        print("The unverified config values can't be listed until the config is fixed.")
    elif not unverified:
        print("Every config value has been verified.")
    else:
        print(
            f"Unverified config values ({len(unverified)}). "
            "Results that use them show a warning:"
        )
        width = max(len(entry.key) for entry in unverified) + 3
        for entry in unverified:
            print(f"  {entry.key:<{width}}{entry.name}: {entry.describe()}")
            print(f"  {'':<{width}}source: {entry.source}")
    print()

    if not report.failed:
        print("All checks passed.")
        return 0
    if report.failed == 1:
        print('1 check failed. Fix it, then run "syn doctor" again.')
    else:
        print(f'{report.failed} checks failed. Fix them, then run "syn doctor" again.')
    return 1


def compound_add(args: argparse.Namespace) -> int:
    try:
        workspace = current_workspace()
    except WorkspaceError as error:
        print(error, file=sys.stderr)
        return 1
    flags = (args.label, args.compound_class, args.smiles, args.status, args.notes)
    try:
        if any(flag is not None for flag in flags):
            if args.label is None:
                print(LABEL_NEEDED, file=sys.stderr)
                return 1
            compound = add_compound(workspace, *flags)
        else:
            compound = add_compound(workspace, *ask_compound(workspace))
            print()
    except CompoundError as error:
        print(error, file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print()
        print("Nothing was added.", file=sys.stderr)
        return 1
    print_added(compound)
    return 0


def ask_compound(workspace: Path) -> tuple[str, str | None, str | None, str, str]:
    """Ask for each field of a new compound, until every answer is usable.

    Raises EOFError or KeyboardInterrupt if the user stops partway.
    """
    print("New compound. Press Enter to skip any question except the label.")
    label = ask_until("Label: ", lambda text: check_label(workspace, text))
    compound_class = ask_until(f"Class ({', '.join(CLASSES)}): ", parse_class)
    smiles = ask_until("SMILES: ", check_smiles)
    status = ask_until(f"Status [{DEFAULT_STATUS}]: ", parse_status)
    notes = input("Notes: ")
    return label, compound_class, smiles, status, notes


def ask_until[T](prompt: str, check: Callable[[str], T]) -> T:
    """Ask until ``check`` accepts the answer, explaining each refusal."""
    while True:
        try:
            return check(input(prompt))
        except CompoundError as error:
            print(error)


def check_smiles(text: str) -> str | None:
    smiles = text.strip()
    if smiles:
        read_smiles(smiles)
    return smiles or None


def compound_show(text: str) -> int:
    try:
        compound = get_compound(current_workspace(), text)
    except (WorkspaceError, CompoundError) as error:
        print(error, file=sys.stderr)
        return 1
    print(f"{compound.id}: {compound.label}")
    print_fields(compound)
    print()
    missing = missing_fields(compound)
    if not missing:
        print("Nothing missing.")
        return 0
    print("Still missing:")
    for item in missing:
        print(f"  {item}")
    return 0


def compound_list(args: argparse.Namespace) -> int:
    try:
        workspace = current_workspace()
        shown = list_compounds(workspace, args.status, args.compound_class)
        everything = list_compounds(workspace)
    except (WorkspaceError, CompoundError) as error:
        print(error, file=sys.stderr)
        return 1
    if not everything:
        print('The register is empty. Add a compound with "syn compound add".')
        return 0
    filters = ", ".join(
        f"{name}: {value}"
        for name, value in (
            ("status", None if args.status is None else parse_status(args.status)),
            ("class", parse_class(args.compound_class or "")),
        )
        if value is not None
    )
    if not shown:
        print(f"No compounds match ({filters}).")
        return 0

    rows = [table_row(compound) for compound in shown]
    print_table(TABLE_HEADINGS, rows)
    count = f"{len(everything)} compound{'' if len(everything) == 1 else 's'}"
    print(f"{len(shown)} of {count} ({filters})." if filters else f"{count}.")
    return 0 if args.csv is None else save_csv(args.csv, workspace, rows)


def print_table(headings: tuple[str, ...], rows: list[tuple[str | None, ...]]) -> None:
    """Print a table in aligned columns, with - in each blank cell."""
    cells = [headings, *[[cell or "-" for cell in row] for row in rows]]
    widths = [
        max(len(line[column]) for line in cells) for column in range(len(headings))
    ]
    for line in cells:
        print(
            "  ".join(
                cell.ljust(width) for cell, width in zip(line, widths, strict=True)
            ).rstrip()
        )


def save_csv(name: Path, workspace: Path, rows: list[tuple[str | None, ...]]) -> int:
    try:
        path = place_table(name, workspace, load_config(workspace), "compounds")
    except (ConfigError, TableFolderError) as error:
        print(error, file=sys.stderr)
        return 1
    if path.exists() and not ask_yes(f"{path} already exists. Replace it? [y/N] "):
        print(f"Kept the existing {path}. The table was not saved.")
        return 0
    try:
        write_csv(path, TABLE_HEADINGS, rows)
    except OSError as error:
        print(
            f"Couldn't save {path}: {error.strerror}. "
            "If it is open in Excel, close it and try again.",
            file=sys.stderr,
        )
        return 1
    print(f"Saved the table to {path.resolve()}")
    return 0


def print_added(compound: Compound) -> None:
    print(f"Added {compound.id}: {compound.label}")
    print_fields(compound)
    print(f'Add more details later with "syn compound edit {compound.id}".')


def print_fields(compound: Compound) -> None:
    """Print each filled field of ``compound``, one per line."""
    molar_mass = (
        None
        if compound.molar_mass is None
        else f"{sig_figs(compound.molar_mass)} g/mol"
    )
    for name, value in (
        ("class", compound.compound_class),
        ("SMILES", compound.smiles),
        ("formula", compound.formula),
        ("molar mass", molar_mass),
        ("status", compound.status),
        ("notes", compound.notes),
    ):
        if value is not None:
            print(f"  {name:<13}{value}")
