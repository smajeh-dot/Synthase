"""The ``syn`` command-line entry point."""

import argparse
import os
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

from synthase import __version__
from synthase.compound_text import (
    aligned,
    batch_cells,
    card,
    card_lines,
    field_sections,
    history_lines,
    list_summary,
    section_lines,
    spectrum_cells,
    spectrum_name,
)
from synthase.compounds import (
    CLASSES,
    CLEAR,
    DEFAULT_STATUS,
    DETAIL_GROUPS,
    DETAIL_PARSERS,
    DETAILS,
    SPECTRUM_KINDS,
    STATUSES,
    TABLE_HEADINGS,
    Batch,
    Change,
    Compound,
    CompoundError,
    add_batch,
    add_compound,
    archive_compound,
    as_text,
    check_label,
    check_rf,
    compound_history,
    compound_spectra,
    edit_batch,
    edit_compound,
    get_batch,
    get_compound,
    get_spectrum,
    link_spectrum,
    list_compounds,
    parse_batch_date,
    parse_batch_value,
    parse_class,
    parse_field,
    parse_mass,
    parse_spectrum_kind,
    parse_status,
    parse_yield,
    read_smiles,
    remove_batch,
    spectra_path,
    table_row,
    unlink_spectrum,
)
from synthase.config import ConfigError, load_config
from synthase.doctor import run_checks
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

COMPOUND_BATCH_HELP = (
    "Add a batch made of a compound: the date, the mass made and the yield. "
    "With no options, Synthase asks for each; press Enter for today's date, or "
    "to skip the mass or the yield (but not both)."
)

COMPOUND_SPECTRUM_HELP = (
    "Link a spectra file to a compound. The file must be inside the workspace, "
    'for example in a "spectra" folder. With no file, Synthase asks for it and '
    "its kind."
)

COMPOUND_EDIT_BATCH_HELP = (
    "Correct a batch's date, mass or yield. With no options, Synthase asks about "
    "each and shows its current value; press Enter to keep it, or type - to clear "
    "the mass or yield. With options, it changes only those. Changing a value "
    "that is already set always asks first."
)

COMPOUND_REMOVE_BATCH_HELP = (
    "Remove a batch entered by mistake, after a yes. Nothing is deleted: it is "
    'hidden from "syn compound show" but stays in "syn compound history", and '
    "the other batches keep their numbers."
)

COMPOUND_UNLINK_HELP = (
    "Remove a spectra link made by mistake, after a yes. The file itself is not "
    'touched, and the link stays in "syn compound history". With no file, '
    "Synthase lists the linked files and asks which one."
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
    batch = compound_commands.add_parser(
        "batch", help="add a batch made of a compound", description=COMPOUND_BATCH_HELP
    )
    batch.add_argument("id", metavar="ID", help="its ID, such as SYN-001")
    batch.add_argument(
        "--date", help="the date it was made, such as 2026-10-18 (default: today)"
    )
    batch.add_argument("--mass", help="the mass made, in mg or g, such as 152 mg")
    batch.add_argument(
        "--yield",
        dest="yield_percent",
        metavar="PERCENT",
        help="the percentage yield, such as 64.2",
    )
    edit_batch_command = compound_commands.add_parser(
        "edit-batch",
        help="correct a batch's date, mass or yield",
        description=COMPOUND_EDIT_BATCH_HELP,
    )
    remove_batch_command = compound_commands.add_parser(
        "remove-batch",
        help="remove a batch entered by mistake",
        description=COMPOUND_REMOVE_BATCH_HELP,
    )
    for command in (edit_batch_command, remove_batch_command):
        command.add_argument("id", metavar="ID", help="its ID, such as SYN-001")
        command.add_argument(
            "batch", metavar="BATCH", help="the batch number, such as 1"
        )
    edit_batch_command.add_argument("--date", help="the date it was made")
    edit_batch_command.add_argument(
        "--mass", help="the mass made, in mg or g, such as 152 mg (- clears it)"
    )
    edit_batch_command.add_argument(
        "--yield",
        dest="yield_percent",
        metavar="PERCENT",
        help="the percentage yield, such as 64.2 (- clears it)",
    )
    spectrum = compound_commands.add_parser(
        "spectrum",
        help="link a spectra file in the workspace to a compound",
        description=COMPOUND_SPECTRUM_HELP,
    )
    spectrum.add_argument("id", metavar="ID", help="its ID, such as SYN-001")
    spectrum.add_argument(
        "file", nargs="?", type=Path, metavar="FILE", help="the file to link"
    )
    spectrum.add_argument(
        "--kind",
        help=", ".join(SPECTRUM_KINDS[:-1]) + f" or {SPECTRUM_KINDS[-1]}",
    )
    unlink = compound_commands.add_parser(
        "unlink",
        help="remove a spectra link made by mistake",
        description=COMPOUND_UNLINK_HELP,
    )
    unlink.add_argument("id", metavar="ID", help="its ID, such as SYN-001")
    unlink.add_argument(
        "file", nargs="?", metavar="FILE", help="the linked file, as the card shows it"
    )
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
        if args.compound_command == "batch":
            return compound_batch(args)
        if args.compound_command == "spectrum":
            return compound_spectrum(args)
        if args.compound_command == "edit-batch":
            return compound_edit_batch(args)
        if args.compound_command == "remove-batch":
            return compound_remove_batch(args)
        if args.compound_command == "unlink":
            return compound_unlink(args)
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
    print_lines(card_lines(card(compound, workspace)))
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
    summary = list_summary(
        shown, everything, args.status, args.compound_class, archived=args.all
    )
    if not shown:
        print(summary)
        return 0

    rows = [table_row(compound) for compound in shown]
    print_table(TABLE_HEADINGS, rows)
    print(summary)
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
    # A batch's value, logged as "batch 1 mass", is asked about as "batch 1's mass".
    batch, _, part = change.name.rpartition(" ")
    name = f"{batch}'s {part}" if batch.startswith("batch ") else f"the {change.name}"
    if change.new is None:
        question = f'Clear {name} ("{change.old}")? [y/N] '
    else:
        question = f'Change {name} from "{change.old}" to "{change.new}"? [y/N] '
    if ask_yes(question):
        return True
    print(f'Kept {name} as "{change.old}".')
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
    print_lines(history_lines(compound, changes))
    return 0


def print_lines(lines: list[str]) -> None:
    for line in lines:
        print(line)


def print_table(headings: tuple[str, ...], rows: list[tuple[str | None, ...]]) -> None:
    """Print a table in aligned columns, with - in each blank cell."""
    print_lines(aligned([headings, *rows]))


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
    """Print each filled field of ``compound``, then its details by group."""
    print_lines(section_lines(field_sections(compound, workspace)))


def compound_batch(args: argparse.Namespace) -> int:
    try:
        workspace = current_workspace()
        compound = get_compound(workspace, args.id)
    except (WorkspaceError, CompoundError) as error:
        print(error, file=sys.stderr)
        return 1
    flags = (args.date, args.mass, args.yield_percent)
    try:
        if all(flag is None for flag in flags):
            made_on, mass_g, yield_percent = ask_batch(compound)
        else:
            made_on = parse_batch_date(args.date or "")
            mass_g = None if args.mass is None else parse_mass(args.mass)
            yield_percent = (
                None if args.yield_percent is None else parse_yield(args.yield_percent)
            )
        compound, batch = add_batch(workspace, args.id, made_on, mass_g, yield_percent)
    except CompoundError as error:
        print(error, file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print()
        print("Nothing was added.", file=sys.stderr)
        return 1
    print(f"Added batch {batch.number} to {compound.id}: {compound.label}")
    print(f"  {aligned([batch_cells(batch)])[0]}")
    if batch.warning:
        print(batch.warning)
    if compound.status == DEFAULT_STATUS:
        print(
            f'{compound.id} is still "{DEFAULT_STATUS}". Change it with '
            f'"syn compound edit {compound.id} --status synthesised".'
        )
    return 0


def ask_batch(compound: Compound) -> tuple[date, float | None, float | None]:
    """Ask for a new batch's date, mass and yield, until each is usable.

    Raises EOFError or KeyboardInterrupt if the user stops partway.
    """
    print(
        f"New batch of {compound.id}: {compound.label}. Press Enter for today's "
        "date, or to skip the mass or the yield."
    )
    made_on = ask_until("Date made (e.g. 2026-10-18): ", parse_batch_date)
    mass_g = ask_until(
        "Mass made (e.g. 152 mg): ",
        lambda text: parse_mass(text) if text.strip() else None,
    )

    def check_yield(text: str) -> float | None:
        if text.strip():
            return parse_yield(text)
        if mass_g is None:
            raise CompoundError("A batch needs its mass made, its yield or both.")
        return None

    yield_percent = ask_until("Yield in % (e.g. 64.2): ", check_yield)
    return made_on, mass_g, yield_percent


def compound_edit_batch(args: argparse.Namespace) -> int:
    try:
        workspace = current_workspace()
        compound, batch = get_batch(workspace, args.id, args.batch)
    except (WorkspaceError, CompoundError) as error:
        print(error, file=sys.stderr)
        return 1
    flags = {
        "made_on": args.date,
        "mass": args.mass,
        "yield_percent": args.yield_percent,
    }
    try:
        if all(flag is None for flag in flags.values()):
            flags = ask_edit_batch(compound, batch)
        compound, batch, changes = edit_batch(
            workspace, args.id, args.batch, confirm_change, **flags
        )
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
        f"to batch {batch.number} of {compound.id}: {compound.label}"
    )
    print(f"  {aligned([batch_cells(batch)])[0]}")
    if batch.warning:
        print(batch.warning)
    return 0


def ask_edit_batch(compound: Compound, batch: Batch) -> dict[str, str | None]:
    """Ask about the batch's date, mass and yield, showing the current values.

    Returns the answers by edit_batch option, with None for each to keep.
    Raises EOFError or KeyboardInterrupt if the user stops partway.
    """
    print(
        f"Editing batch {batch.number} of {compound.id}: {compound.label}. "
        "Press Enter to keep a value, or type - to clear the mass or yield."
    )
    answers: dict[str, str | None] = {}
    for option, part, question, current in (
        ("made_on", "date", "Date made", batch.made_on),
        ("mass", "mass", "Mass made", batch.mass),
        ("yield_percent", "yield", "Yield in %", batch.yield_text),
    ):
        shown = "" if current is None else f" [{current}]"

        def check(text: str, part: str = part) -> str | None:
            answer = text if text.strip() else None
            if answer is not None:
                parse_batch_value(part, answer)
            if part == "yield" and (
                after(answers["mass"], batch.mass_g) is None
                and after(answer, batch.yield_percent) is None
            ):
                raise CompoundError("A batch needs its mass made, its yield or both.")
            return answer

        answers[option] = ask_until(f"{question}{shown}: ", check)
    return answers


def compound_remove_batch(args: argparse.Namespace) -> int:
    try:
        workspace = current_workspace()
        compound, batch = get_batch(workspace, args.id, args.batch)
        question = (
            f"Remove batch {batch.number} of {compound.id} ({batch.details})? "
            "It is hidden from the card but kept in the history, and the other "
            "batches keep their numbers. [y/N] "
        )
        if not ask_yes(question):
            print(f"Kept batch {batch.number} of {compound.id} as it was.")
            return 0
        remove_batch(workspace, args.id, args.batch)
    except (WorkspaceError, CompoundError) as error:
        print(error, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        print("Nothing was changed.", file=sys.stderr)
        return 1
    print(
        f"Removed batch {batch.number} from {compound.id}: {compound.label}. "
        f'It stays in "syn compound history {compound.id}".'
    )
    return 0


def compound_spectrum(args: argparse.Namespace) -> int:
    try:
        workspace = current_workspace()
        compound = get_compound(workspace, args.id)
    except (WorkspaceError, CompoundError) as error:
        print(error, file=sys.stderr)
        return 1
    try:
        if args.file is None and args.kind is None:
            file, kind = ask_spectrum(workspace, compound)
        elif args.file is None:
            print(
                f'Give the file to link, as in "syn compound spectrum {compound.id} '
                'spectra\\IR.csv --kind IR".',
                file=sys.stderr,
            )
            return 1
        else:
            file, kind = args.file, args.kind
        compound, spectrum = link_spectrum(workspace, args.id, file, kind)
    except CompoundError as error:
        print(error, file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print()
        print("Nothing was linked.", file=sys.stderr)
        return 1
    print(f"Linked to {compound.id}: {compound.label}")
    print(f"  {aligned([spectrum_cells(spectrum, workspace)])[0]}")
    return 0


def ask_spectrum(workspace: Path, compound: Compound) -> tuple[Path, str | None]:
    """Ask for the file to link and its kind, until each is usable.

    Raises EOFError or KeyboardInterrupt if the user stops partway.
    """
    print(f"Link a spectra file to {compound.id}: {compound.label}.")

    def check_file(text: str) -> Path:
        if not text.strip():
            raise CompoundError("Type the file's path, or drag the file in.")
        # A file dragged into PowerShell arrives in quotes.
        file = Path(text.strip().strip('"'))
        spectra_path(workspace, file)
        return file

    file = ask_until("File: ", check_file)
    kind = ask_until(f"Kind ({', '.join(SPECTRUM_KINDS)}): ", parse_spectrum_kind)
    return file, kind


def compound_unlink(args: argparse.Namespace) -> int:
    try:
        workspace = current_workspace()
        compound = get_compound(workspace, args.id)
        file = args.file
        if file is None:
            file = ask_linked(workspace, compound)
        compound, spectrum = get_spectrum(workspace, args.id, file)
        name = spectrum_name(spectrum)
        question = (
            f"Unlink {name} from {compound.id}? The file itself is not touched. [y/N] "
        )
        if not ask_yes(question):
            print(f"Kept the link to {name}.")
            return 0
        unlink_spectrum(workspace, args.id, file)
    except (WorkspaceError, CompoundError) as error:
        print(error, file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print()
        print("Nothing was changed.", file=sys.stderr)
        return 1
    print(f"Unlinked {name} from {compound.id}: {compound.label}.")
    return 0


def ask_linked(workspace: Path, compound: Compound) -> str:
    """List the files linked to ``compound``, numbered, and ask which one.

    Returns its path. Raises EOFError or KeyboardInterrupt if the user stops.
    """
    linked = compound_spectra(workspace, compound)
    if not linked:
        raise CompoundError(f"{compound.id} has no spectra linked.")
    print(f"Spectra linked to {compound.id}: {compound.label}")
    rows = [
        (str(number), *spectrum_cells(spectrum, workspace))
        for number, spectrum in enumerate(linked, start=1)
    ]
    for line in aligned(rows):
        print(f"  {line}")
    choices = "1" if len(linked) == 1 else f"1-{len(linked)}"

    def check(text: str) -> str:
        if text.strip() not in [row[0] for row in rows]:
            raise CompoundError(f"Type the number of the file to unlink ({choices}).")
        return linked[int(text) - 1].path

    return ask_until(f"Which one? ({choices}): ", check)
