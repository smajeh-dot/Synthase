"""The error log: what went wrong when a command failed unexpectedly.

The app never shows a Python traceback on its own (spec C183). It writes the
details here and asks whether to show them (owner decision D4). The layout is
in docs/decisions/0027-app-shell.md.
"""

import platform
import traceback
from datetime import datetime

from synthase import __version__
from synthase.storage import data_folder, shown

FILE = "error.log"

QUESTION = "Would you like the error log? [y/n] "
FAILED = "Failed."
HEADING = "Error log"
STAYS = "The log stays in {file}."


def entry(command: str, error: BaseException) -> str:
    """One log entry: when and what was typed, the versions, then the traceback."""
    when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    system = f"{platform.system()} {platform.release()} {platform.machine()}"
    versions = f"Synthase {__version__} · {system} · Python {platform.python_version()}"
    details = "".join(traceback.format_exception(error)).rstrip("\n")
    return f"{when}  {command}\n{versions}\n{details}"


def write(text: str) -> str | None:
    """Add an entry to data\\error.log; the file as shown, or None if it failed."""
    path = data_folder() / FILE
    try:
        with open(path, "a", encoding="utf-8", newline="\n") as log:
            log.write(text + "\n\n")
    except OSError:
        return None
    return shown(path)


def is_yes(answer: str) -> bool:
    """Only y or yes, in any case, shows the log; anything else means no."""
    return answer.strip().lower() in ("y", "yes")
