"""The ``syn`` command-line entry point."""

import argparse
import os
import sys
from collections.abc import Callable
from pathlib import Path

from synthase import __version__
from synthase.compounds import (
    CLASSES,
    CLEAR,
    DEFAULT_STATUS,
    DETAIL_GROUPS,
    DETAIL_PARSERS,
    DETAILS,
    FIELD_NAMES,
    STATUSES,
    TABLE_HEADINGS,
    Change,
    Compound,
    CompoundError,
    add_compound,
    archive_compound,
    as_text,
    check_label,
    check_rf,
    compound_history,
    edit_compound,
    get_compound,
    list_compounds,
    missing_fields,
    parse_class,
    parse_field,
    parse_status,
    purity_warnings,
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
    "Check that Python, RDKit, the workspace, the config and the table folders "
    "are all set up, with the fix for anything that isn't, and list every config "
    "value not yet checked against the literature. Exits with code 1 if any check "
    "fails."
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

COMPOUND_EDIT_HELP = (
    "Fill in or change a compound's details. With no options, Synthase asks "
    "about each one and shows its current value; press Enter to keep it, or type "
    "- to clear it. With options, it changes only those. Changing a value that is "
    "already set always asks first."
)

COMPOUND_ARCHIVE_HELP = (
    'Hide a compound you have given up on from "syn compound list". Nothing is '
    'deleted: "syn compound show" still finds it, and "syn compound restore" '
    "brings it back."
)

COMPOUND_RESTORE_HELP = 'Bring an archived compound back into "syn compound list".'

COMPOUND_HISTORY_HELP = (
    "Show every change recorded for one compound, oldest first, with the date "
    "and the old and new values."
)

LABEL_NEEDED = (
    'Give the label with --label, or run "syn compound add" with no flags '
    "to be asked for each field."
)

# The fields add and edit take, as Compound attributes and option names.
FIELDS = ("label", "compound_class", "smiles", "status", "notes", *DETAILS)

# What each group of details covers, and the question for each field.
GROUP_CONTENTS = {
    "Characterisation": "melting point, Rf",
    "Handling": "appearance, colour, solubility, DMSO stock, storage",
    "Safety": "risk assessment, hazards",
}
QUESTIONS = {
    "melting_point": "Melting range in K (e.g. 455-457)",
    "rf": "Rf (0 to 1)",
    "rf_solvent": "Rf solvent system (e.g. hexane:ethyl acetate 3:1)",
    "appearance": "Appearance and colour",
    "coloured": "Coloured in solution, so it needs a compound-only blank? (yes/no)",
    "solubility": "Solubility",
    "dmso_stock": "DMSO stock concentration (mg/mL, µg/mL or mM)",
    "storage": "Storage conditions",
    "risk_assessment": "Risk assessment (the date it was done, e.g. 2026-10-18, or no)",
    "hazards": "Hazard notes",
}

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
    add_field_options(add, f"{DEFAULT_STATUS} (the default), ")
    edit = compound_commands.add_parser(
        "edit",
        help="fill in or change a compound's details",
        description=COMPOUND_EDIT_HELP,
    )
    edit.add_argument("id", metavar="ID", help="its ID, such as SYN-001")
    edit.add_argument("--label", help="a new short name for it")
    add_field_options(edit, f"{DEFAULT_STATUS}, ", " (- clears it)")
    for name, short, description in (
        ("archive", "hide a compound you have given up on", COMPOUND_ARCHIVE_HELP),
        ("restore", "bring an archived compound back", COMPOUND_RESTORE_HELP),
        ("history", "show every change made to a compound", COMPOUND_HISTORY_HELP),
    ):
        command = compound_commands.add_parser(
            name, help=short, description=description
        )
        command.add_argument("id", metavar="ID", help="its ID, such as SYN-001")
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
        "--all", action="store_true", help="also show archived compounds"
    )
    listing.add_argument(
        "--csv",
        metavar="FILE",
        type=Path,
        help="also save the table as a CSV file. A file name alone goes in the "
        "compounds folder set in config.toml, or in the workspace's results folder",
    )
    return parser


def add_field_options(
    parser: argparse.ArgumentParser, first_status: str, clears: str = ""
) -> None:
    """The --class, --smiles, --status and --notes options of add and edit."""
    parser.add_argument(
        "--class",
        dest="compound_class",
        metavar="CLASS",
        help=", ".join(CLASSES[:-1]) + f" or {CLASSES[-1]}" + clears,
    )
    parser.add_argument("--smiles", help="its structure, written as a SMILES" + clears)
    parser.add_argument(
        "--status",
        help=first_status + ", ".join(STATUSES[1:-1]) + f" or {STATUSES[-1]}",
    )
    parser.add_argument("--notes", help="anything else worth recording" + clears)
    parser.add_argument(
        "--mp",
        dest="melting_point",
        metavar="RANGE",
        help="melting range in kelvin, such as 455-457" + clears,
    )
    parser.add_argument(
        "--rf", help="Rf value, from 0 to 1, with --rf-solvent" + clears
    )
    parser.add_argument(
        "--rf-solvent",
        metavar="SOLVENT",
        help="the solvent system the Rf was measured in" + clears,
    )
    parser.add_argument("--appearance", help="its appearance and colour" + clears)
    parser.add_argument(
        "--coloured",
        metavar="YES/NO",
        help="coloured in solution, so a plate needs a compound-only blank" + clears,
    )
    parser.add_argument("--solubility", help="what it dissolves in" + clears)
    parser.add_argument(
        "--dmso-stock",
        metavar="CONCENTRATION",
        help="DMSO stock concentration in mg/mL, µg/mL or mM, such as 10 mg/mL"
        + clears,
    )
    parser.add_argument("--storage", help="storage conditions" + clears)
    parser.add_argument(
        "--risk-assessment",
        metavar="DATE/no",
        help="the date the risk assessment was done, such as 2026-10-18, or no"
        + clears,
    )
    parser.add_argument("--hazards", help="hazard notes" + clears)


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
        if args.compound_command == "edit":
            return compound_edit(args)
        if args.compound_command == "archive":
            return compound_archive(args.id)
        if args.compound_command == "restore":
            return compound_restore(args.id)
        if args.compound_command == "history":
            return compound_history_command(args.id)
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
    flags = {field: getattr(args, field) for field in FIELDS}
    try:
        if any(flag is not None for flag in flags.values()):
            if args.label is None:
                print(LABEL_NEEDED, file=sys.stderr)
                return 1
            compound = add_compound(workspace, **flags)
        else:
            first, details = ask_compound(workspace)
            compound = add_compound(workspace, *first, **details)
            print()
    except CompoundError as error:
        print(error, file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print()
        print("Nothing was added.", file=sys.stderr)
        return 1
    print_added(compound, workspace)
    return 0


def ask_compound(
    workspace: Path,
) -> tuple[tuple[str, str | None, str | None, str, str], dict[str, str | None]]:
    """Ask for each field of a new compound, until every answer is usable.

    Returns the first five answers, then any details by field. Raises
    EOFError or KeyboardInterrupt if the user stops partway.
    """
    print("New compound. Press Enter to skip any question except the label.")
    label = ask_until("Label: ", lambda text: check_label(workspace, text))
    compound_class = ask_until(f"Class ({', '.join(CLASSES)}): ", parse_class)
    smiles = ask_until("SMILES: ", check_smiles)
    status = ask_until(f"Status [{DEFAULT_STATUS}]: ", parse_status)
    notes = input("Notes: ")
    details = ask_details(workspace, None)
    return (label, compound_class, smiles, status, notes), details


def ask_details(workspace: Path, compound: Compound | None) -> dict[str, str | None]:
    """Ask about each group of details the user wants to fill in.

    ``compound`` is the one being edited, or None for a new one. Returns the
    answers by field, with None for each one to keep.
    """
    verb = "Add" if compound is None else "Edit"
    answers: dict[str, str | None] = {}
    for group, fields in DETAIL_GROUPS:
        contents = GROUP_CONTENTS[group]
        if not ask_yes(f"{verb} {group.lower()} details ({contents})? [y/N] "):
            continue
        for field in fields:
            current = None if compound is None else getattr(compound, field)
            if field == "rf_solvent" and compound is None and not answers.get("rf"):
                continue
            shown = "" if current is None else f" [{as_text(current)}]"

            def check(
                text: str, field: str = field, current: object = current
            ) -> str | None:
                if not text.strip():
                    answer = None
                elif compound is None:
                    DETAIL_PARSERS[field](text)
                    answer = text
                else:
                    parse_field(workspace, compound.number, field, text)
                    answer = text
                if field == "rf_solvent":
                    old_rf = None if compound is None else compound.rf
                    check_rf(after(answers.get("rf"), old_rf), after(answer, current))
                return answer

            answers[field] = ask_until(f"{QUESTIONS[field]}{shown}: ", check)
    return answers


def after(answer: str | None, current: object) -> object:
    """What a field holds after ``answer``: kept, cleared or replaced."""
    if answer is None:
        return current
    return None if answer.strip() == CLEAR else answer


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
        workspace = current_workspace()
        compound = get_compound(workspace, text)
    except (WorkspaceError, CompoundError) as error:
        print(error, file=sys.stderr)
        return 1
    archived = " (archived)" if compound.archived else ""
    print(f"{compound.id}: {compound.label}{archived}")
    print_fields(compound, workspace)
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
        shown = list_compounds(
            workspace, args.status, args.compound_class, archived=args.all
        )
        everything = list_compounds(workspace, archived=True)
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
    hidden = 0 if args.all else sum(compound.archived for compound in everything)
    if not shown:
        if filters:
            print(f"No compounds match ({filters}).")
        else:
            print("Every compound is archived. Add --all to see them.")
        return 0

    rows = [table_row(compound) for compound in shown]
    print_table(TABLE_HEADINGS, rows)
    total = len(everything) - hidden
    count = f"{total} compound{'' if total == 1 else 's'}"
    if filters:
        count = f"{len(shown)} of {count}"
    if hidden:
        them = "it" if hidden == 1 else "them"
        filters = "; ".join(
            part
            for part in (filters, f"{hidden} archived, hidden; add --all to see {them}")
            if part
        )
    print(f"{count} ({filters})." if filters else f"{count}.")
    return 0 if args.csv is None else save_csv(args.csv, workspace, rows)


def compound_edit(args: argparse.Namespace) -> int:
    try:
        workspace = current_workspace()
        compound = get_compound(workspace, args.id)
    except (WorkspaceError, CompoundError) as error:
        print(error, file=sys.stderr)
        return 1
    flags = {field: getattr(args, field) for field in FIELDS}
    try:
        if all(flag is None for flag in flags.values()):
            flags = ask_edit(workspace, compound)
        compound, changes = edit_compound(workspace, args.id, confirm_change, **flags)
    except CompoundError as error:
        print(error, file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print()
        print("Nothing was changed.", file=sys.stderr)
        return 1
    if not changes:
        print("Nothing was changed.")
        return 0
    print(
        f"Saved {len(changes)} change{'' if len(changes) == 1 else 's'} "
        f"to {compound.id}: {compound.label}"
    )
    print_fields(compound, workspace)
    return 0


def ask_edit(workspace: Path, compound: Compound) -> dict[str, str | None]:
    """Ask about each field of ``compound``, showing its current value.

    Returns the answers by field, with None for each field to keep. Raises
    EOFError or KeyboardInterrupt if the user stops partway.
    """
    print(
        f"Editing {compound.id}: {compound.label}. "
        "Press Enter to keep a value, or type - to clear it."
    )
    answers = []
    for field, question, current in (
        ("label", "Label", compound.label),
        ("class", f"Class ({', '.join(CLASSES)})", compound.compound_class),
        ("smiles", "SMILES", compound.smiles),
        ("status", f"Status ({', '.join(STATUSES)})", compound.status),
        ("notes", "Notes", compound.notes),
    ):
        shown = "" if current is None else f" [{current}]"

        def check(text: str, field: str = field) -> str | None:
            if not text.strip():
                return None
            parse_field(workspace, compound.number, field, text)
            return text

        answers.append(ask_until(f"{question}{shown}: ", check))
    return dict(zip(FIELDS[:5], answers, strict=True)) | ask_details(
        workspace, compound
    )


def confirm_change(change: Change) -> bool:
    """Ask before changing or clearing a value that is already set."""
    if change.new is None:
        question = f'Clear the {change.name} ("{change.old}")? [y/N] '
    else:
        question = (
            f'Change the {change.name} from "{change.old}" to "{change.new}"? [y/N] '
        )
    if ask_yes(question):
        return True
    print(f'Kept the {change.name} as "{change.old}".')
    return False


def compound_archive(text: str) -> int:
    try:
        workspace = current_workspace()
        compound = get_compound(workspace, text)
        if compound.archived:
            raise CompoundError(f"{compound.id} is already archived.")
        question = (
            f"Archive {compound.id} ({compound.label})? It stays in the register "
            'but is hidden from "syn compound list". [y/N] '
        )
        if not ask_yes(question):
            print(f"Kept {compound.id} as it was.")
            return 0
        archive_compound(workspace, text)
    except (WorkspaceError, CompoundError) as error:
        print(error, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        print("Nothing was changed.", file=sys.stderr)
        return 1
    print(
        f"Archived {compound.id}: {compound.label}. "
        f'Undo with "syn compound restore {compound.id}".'
    )
    return 0


def compound_restore(text: str) -> int:
    try:
        compound = archive_compound(current_workspace(), text, archived=False)
    except (WorkspaceError, CompoundError) as error:
        print(error, file=sys.stderr)
        return 1
    print(
        f"Restored {compound.id}: {compound.label}. "
        'It shows in "syn compound list" again.'
    )
    return 0


def compound_history_command(text: str) -> int:
    try:
        compound, changes = compound_history(current_workspace(), text)
    except (WorkspaceError, CompoundError) as error:
        print(error, file=sys.stderr)
        return 1
    print(f"History of {compound.id}: {compound.label}")
    width = max((len(change.name) for change in changes), default=0)
    for change in changes:
        when = (change.changed or "")[:16].replace("T", " ")
        old, new = (
            "(blank)" if value is None else value for value in (change.old, change.new)
        )
        print(f"  {when}  {change.name:<{width}}  {old} -> {new}")
    return 0


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


def print_added(compound: Compound, workspace: Path) -> None:
    print(f"Added {compound.id}: {compound.label}")
    print_fields(compound, workspace)
    print(f'Add more details later with "syn compound edit {compound.id}".')


def print_fields(compound: Compound, workspace: Path) -> None:
    """Print each filled field of ``compound``, one per line, then its details.

    The details come under a heading for each group that has any.
    """
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
    for group, fields in DETAIL_GROUPS:
        lines = [
            f"  {FIELD_NAMES[field]:<20}{detail_text(compound, field)}"
            for field in fields
            if getattr(compound, field) is not None
        ]
        if group == "Characterisation":
            lines += [f"  {line}" for line in purity_lines(compound, workspace)]
        if lines:
            print(group)
            print("\n".join(lines))


def detail_text(compound: Compound, field: str) -> str | None:
    if field == "risk_assessment" and compound.risk_assessment != "no":
        return f"done on {compound.risk_assessment}"
    if field == "risk_assessment":
        return "not done"
    return as_text(getattr(compound, field))


def purity_lines(compound: Compound, workspace: Path) -> list[str]:
    """The purity flag for ``compound``'s melting range, if it has one."""
    if compound.melting_point is None:
        return []
    try:
        return purity_warnings(compound, load_config(workspace))
    except ConfigError as error:
        return [f"The melting range can't be checked against the purity rule. {error}"]
