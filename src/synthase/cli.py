"""The ``syn`` command-line entry point."""

import argparse

from synthase import __version__


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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    # No commands exist yet, so a bare `syn` shows the help text.
    parser.print_help()
    return 0
