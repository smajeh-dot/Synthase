# 0002: Python version

## Context
Synthase runs on a Windows laptop and will depend on RDKit, numpy, pandas and matplotlib. All of them must install from ready-built Windows packages (wheels); building RDKit from source on Windows is not realistic. Checked on PyPI on 2026-10-16, these all ship `win_amd64` wheels for Python 3.12, 3.13 and 3.14:

| Package | Version checked | Windows wheels for |
|---|---|---|
| RDKit | 2026.9.1 | 3.10 to 3.15 |
| numpy | 2.5.4 | 3.12 to 3.15 |
| pandas | 3.0.6 | 3.11 to 3.15 |
| matplotlib | 3.11.2 | 3.11 to 3.15 |

Textual and Rich are pure Python, so they work on any of these.

## Decision
Pin Python 3.13: `requires-python = ">=3.13,<3.14"` in `pyproject.toml`.

- It has two years of bug-fix releases behind it, and every package above supports it.
- It keeps security support until October 2029, beyond the life of the project.
- 3.14 is newer, with a small risk that a library added later lags behind on Windows wheels. 3.12 loses security support in October 2028.

## Consequences
- Installing with any other Python version fails straight away with a clear message from pip.
- CI (#8) and the setup script (#13) use Python 3.13.
- Moving to a newer version is a deliberate change: a new decision record, plus a change to the pin.
