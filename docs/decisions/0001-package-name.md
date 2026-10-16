# 0001: Package name

## Context
Synthase needs a package name for `pyproject.toml`. The obvious name, `synthase`, is already taken on PyPI (the Python package index): someone has reserved it with an empty placeholder release (version 0.0.1). Using a taken name would cause confusion if Synthase is ever published, and `pip install synthase` would fetch the wrong package.

## Decision
- The package (distribution) name is `synthase-lab`. It was free on PyPI when checked on 2026-10-16.
- The Python import name stays `synthase`, so code reads `import synthase`.
- The command stays `syn`.

## Consequences
- `pyproject.toml` uses `name = "synthase-lab"`, and code that looks up the installed version asks for `synthase-lab`.
- The project, the repo and the app are still called Synthase everywhere a person reads it.
- If the reserved `synthase` package were ever installed in the same environment, the two would clash on the import name. Synthase always runs in its own virtual environment, so this is not expected to happen.
