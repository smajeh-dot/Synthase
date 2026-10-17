"""The ``syn`` command-line entry point."""

import argparse
import os
import sys
from pathlib import Path

from synthase import __version__
from synthase.workspace import DEFAULT_NAME, WorkspaceError, create_workspace

INIT_HELP = (
    "Create the folder for your lab data, results, notes and config, outside "
    f"Synthase's code folder. Default: Documents\\{DEFAULT_NAME}. If your "
    "Documents folder syncs to OneDrive, the workspace is backed up automatically."
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        return init(args.path)
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
