"""The ``syn`` command-line entry point."""

import argparse
import sys
from collections.abc import Callable
from functools import partial
from pathlib import Path

from synthase import __version__
from synthase.compound_questions import (
    Answers,
    Flow,
    add_flow,
    batch_flow,
    change_question,
    compound_answers,
    edit_batch_flow,
    edit_flow,
    is_yes,
    kept_message,
    spectrum_flow,
    unlink_flow,
)
from synthase.compound_text import (
    EMPTY_REGISTER,
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
    DEFAULT_STATUS,
    DETAILS,
    SPECTRUM_KINDS,
    STATUSES,
    TABLE_HEADINGS,
    Change,
    Compound,
    CompoundError,
    add_batch,
    add_compound,
    archive_compound,
    compound_history,
    edit_batch,
    edit_compound,
    get_batch,
    get_compound,
    get_spectrum,
    link_spectrum,
    list_compounds,
    parse_batch_date,
    parse_mass,
    parse_yield,
    remove_batch,
    table_row,
    unlink_spectrum,
)
from synthase.config import ConfigError, load_config
from synthase.doctor import report_text, run_checks
from synthase.tables import (
    TableFolderError,
    kept_text,
    not_saved_text,
    place_table,
    replace_question,
    saved_text,
    write_csv,
)
from synthase.workspace import (
    DEFAULT_NAME,
    WorkspaceError,
    create_workspace,
    current_workspace,
    init_text,
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
    return is_yes(reply)


def init(path: Path | None) -> int:
    try:
        created = create_workspace(path, ask_yes)
    except WorkspaceError as error:
        print(error, file=sys.stderr)
        return 1

    text = init_text(created)
    print(text.first)
    for name, contents in text.rows:
        print(f"  {name:<12} {contents}")
    if text.next is not None:
        print(text.next)
    print(text.last)
    return 0


def doctor() -> int:
    report = run_checks()
    text = report_text(report, rerun='"syn doctor"')
    print(text.heading)
    print()
    for check in report.checks:
        print(f"  {check.word:<6}{check.text}")
        if check.fix:
            print(f"        Fix: {check.fix}")
    print()

    print(text.unverified_title)
    if text.unverified:
        width = max(len(key) for key, _, _ in text.unverified) + 3
        for key, value, source in text.unverified:
            print(f"  {key:<{width}}{value}")
            print(f"  {'':<{width}}{source}")
    print()

    print(text.last)
    return 1 if report.failed else 0


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
            answers = compound_answers(ask_questions(add_flow(workspace)))
            compound = add_compound(workspace, **answers)
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


def ask_questions(flow: Flow) -> Answers:
    """Show the opening lines, then ask each question in ``flow`` that applies.

    Each question is asked until its answer is usable. Running out of input
    at a [y/N] question counts as no. Raises EOFError or KeyboardInterrupt if
    the user stops partway.
    """
    print_lines(list(flow.opening))
    answers: Answers = {}
    while (question := flow.next_question(answers)) is not None:
        if question.yes_no:
            answers[question.key] = ask_yes(question.prompt)
        else:
            check = partial(question.answer, answers=answers)
            answers[question.key] = ask_until(question.prompt, check)
    return answers


def ask_until[T](prompt: str, check: Callable[[str], T]) -> T:
    """Ask until ``check`` accepts the answer, explaining each refusal."""
    while True:
        try:
            return check(input(prompt))
        except CompoundError as error:
            print(error)


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
        print(EMPTY_REGISTER)
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
            flags = compound_answers(ask_questions(edit_flow(workspace, compound)))
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


def confirm_change(change: Change) -> bool:
    """Ask before changing or clearing a value that is already set."""
    if ask_yes(change_question(change)):
        return True
    print(kept_message(change))
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
    if path.exists() and not ask_yes(f"{replace_question(path)} [y/N] "):
        print(kept_text(path))
        return 0
    try:
        write_csv(path, TABLE_HEADINGS, rows)
    except OSError as error:
        print(not_saved_text(path, error), file=sys.stderr)
        return 1
    print(saved_text(path))
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
            answers = ask_questions(batch_flow(compound))
            made_on = answers["made_on"]
            mass_g = answers["mass_g"]
            yield_percent = answers["yield_percent"]
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
            flags = ask_questions(edit_batch_flow(compound, batch))
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
            answers = ask_questions(spectrum_flow(workspace, compound))
            file, kind = answers["file"], answers["kind"]
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


def compound_unlink(args: argparse.Namespace) -> int:
    try:
        workspace = current_workspace()
        compound = get_compound(workspace, args.id)
        file = args.file
        if file is None:
            file = ask_questions(unlink_flow(workspace, compound))["file"]
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
