"""The history log: every change, ever, one JSON line each (spec C171).

`data\\history.jsonl` is only ever added to. Each line records the hash of the
file it changed, as Synthase left it; a file whose hash no longer matches was
changed outside Synthase, and that is logged too. The rules are in
docs/decisions/0025-ids-history-lock.md.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

from synthase.storage import BROKEN, StorageError, data_folder, shown

FILE = "history.jsonl"
# The data files whose hand-edits are noticed, in the order they are checked.
TRACKED = ("synthase.toml", "experiments.toml", "compounds.toml")

CHANGED = "{file} was changed outside Synthase. The change is noted in the history."
DELETED = "{file} was deleted outside Synthase. The deletion is noted in the history."


def now() -> str:
    """The time now, as stored: ISO 8601 with its UTC offset."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def shown_time(stamp: str) -> str:
    """A stored time as shown: ``2026-10-21 14:32:07``."""
    return datetime.fromisoformat(stamp).strftime("%Y-%m-%d %H:%M:%S")


def file_hash(path: Path) -> str | None:
    """The SHA-256 of a file's bytes, or None if it doesn't exist."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return None


def log(
    action: str,
    file: str,
    *,
    id: str | None = None,
    name: str | None = None,
    old: object = None,
    new: object = None,
) -> dict:
    """Add one line for a change just saved to ``file`` (a name in data\\)."""
    entry = {
        "ts": now(),
        "action": action,
        "id": id,
        "name": name,
        "old": old,
        "new": new,
        "file": file,
        "sha256": file_hash(data_folder() / file),
    }
    with open(data_folder() / FILE, "a", encoding="utf-8", newline="\n") as out:
        out.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def entries() -> list[dict]:
    """Every line of the log, oldest first. A broken line is refused."""
    path = data_folder() / FILE
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    result = []
    for number, line in enumerate(lines, start=1):
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            raise StorageError(BROKEN.format(file=shown(path), line=number)) from None
    return result


def check_external_edits() -> list[str]:
    """Log and report each data file changed or deleted outside Synthase.

    A file is compared with the last hash logged for it. One never logged
    counts only if it exists. Each change is reported once, because the new
    hash is logged with it.
    """
    last: dict[str, str | None] = {}
    for entry in entries():
        if entry.get("file"):
            last[entry["file"]] = entry.get("sha256")
    messages = []
    for name in TRACKED:
        path = data_folder() / name
        current = file_hash(path)
        if name in last:
            if current == last[name]:
                continue
        elif current is None:
            continue
        log("external_edit", name)
        message = DELETED if current is None else CHANGED
        messages.append(message.format(file=shown(path)))
    return messages
