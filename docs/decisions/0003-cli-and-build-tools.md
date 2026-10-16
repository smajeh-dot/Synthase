# 0003: Command-line parser and build tools

## Context
The `syn` command needs a command-line parser, and the package needs a build backend so that `pip install` works. The project rule is to add a dependency only when a feature needs it.

## Decision
- **Parser:** Python's built-in `argparse`. It handles `--help`, `--version` and subcommands without any extra dependency. Click or Typer can be reconsidered if a later command needs something `argparse` can't do.
- **Build backend:** `hatchling`. It is only needed while installing, never at run time, and it supports the `src/` layout with very little configuration.
- **Developer tools:** pytest and ruff are an optional `dev` extra, installed with `pip install -e ".[dev]"`. That works with plain pip on Windows, with no extra tools.
- **Version:** written once, in `pyproject.toml`. The code reads it back from the installed package's metadata.

## Consequences
- `syn` has no run-time dependencies yet.
- Lint and test settings live in `pyproject.toml`, so there is one file to read.
- Synthase has to be installed (`pip install -e .`) before it can run, because the version comes from the installed metadata.
