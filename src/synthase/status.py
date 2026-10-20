"""The app's status line: the workspace folder and how many values are unverified.

The wording and the path shortening are in docs/decisions/0016-full-screen-app.md.
"""

from dataclasses import dataclass
from pathlib import Path

from textual.markup import escape

from synthase.config import WORKSPACE_CONFIG_NAME, ConfigError, load_config
from synthase.workspace import NoWorkspace, WorkspaceMissing, current_workspace

ELLIPSIS = "…"


@dataclass(frozen=True)
class Status:
    kind: str  # "found", "none", "moved" or "problem"
    path: Path | None = None
    unverified: int = 0


def read_status() -> Status:
    try:
        path = current_workspace()
    except NoWorkspace:
        return Status("none")
    except WorkspaceMissing:
        return Status("moved")
    if not (path / WORKSPACE_CONFIG_NAME).is_file():
        # load_config() would fall back to the template; decision 0010 forbids that.
        return Status("problem", path)
    try:
        config = load_config(path)
    except ConfigError:
        return Status("problem", path)
    unverified = sum(not config.get(key).verified for key in config.keys())
    return Status("found", path, unverified)


def status_markup(status: Status, width: int) -> str:
    """The status line as content markup, its path shortened to fit ``width``."""
    if status.kind == "none":
        return "[$accent]›[/] No workspace yet. Type init to create one."
    if status.kind == "moved":
        return "[b $caution]![/] Workspace not found. Type init to choose it."
    if status.kind == "problem":
        mark = "[b $error]✗[/]"
        rest = "config.toml has a problem, run doctor"
        tail = f"{mark} [$error]{rest}[/]"
    else:
        if status.unverified == 0:
            mark, rest = "✓", "all config values verified"
        else:
            plural = "value" if status.unverified == 1 else "values"
            mark = "[b $warning]?[/]"
            rest = f"{status.unverified} config {plural} unverified"
        tail = f"{mark} {rest}"
    label = "Workspace: "
    room = width - len(label) - len(" · ") - len(f"? {rest}")
    path = shorten_path(str(status.path), room)
    return f"{label}{escape(path)}[$faint] · [/]{tail}"


def shorten_path(path: str, room: int, home: str | None = None) -> str:
    """``path`` as it is if it fits in ``room`` cells, otherwise shortened.

    First the home folder becomes ``~``, then middle folders become ``…``,
    keeping the first folder and the workspace's own folder name.
    """
    if len(path) <= room:
        return path
    home = str(Path.home()) if home is None else home
    sep = "\\" if "\\" in path else "/"
    if path.lower().startswith(home.lower() + sep):
        path = "~" + path[len(home) :]
        if len(path) <= room:
            return path
    parts = path.split(sep)
    if len(parts) <= 2:
        return path
    head, middle, last = parts[0], parts[1:-1], parts[-1]
    for keep in range(len(middle) - 1, -1, -1):
        shorter = sep.join([head, *middle[:keep], ELLIPSIS, last])
        if len(shorter) <= room:
            return shorter
    return sep.join([head, ELLIPSIS, last])
