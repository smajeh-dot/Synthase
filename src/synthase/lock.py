"""The project lock: one Synthase window per project at a time (spec C173).

While a project is open, `data\\.synthase.lock` holds the window's process ID.
A second window refuses to open it. A lock left by a process that has stopped
is ignored. The rules are in docs/decisions/0025-ids-history-lock.md.
"""

import os
import sys

from synthase.storage import StorageError, data_folder

NAME = ".synthase.lock"
IN_USE = (
    "This project is already open in another Synthase window. "
    "Close it there first. If no other window is open, "
    "delete data\\.synthase.lock and try again."
)


def is_running(pid: int) -> bool:
    """Whether a process with this ID is still running."""
    if pid == os.getpid():
        return True
    if sys.platform == "win32":
        return _is_running_on_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _is_running_on_windows(pid: int) -> bool:
    # os.kill(pid, 0) would end the process on Windows, so ask Windows instead.
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    query_limited_information = 0x1000
    access_denied = 5
    still_active = 259

    handle = kernel32.OpenProcess(query_limited_information, False, pid)
    if not handle:
        # A process we may not look at is still a running process.
        return ctypes.get_last_error() == access_denied
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True
        return code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def _holder() -> int | None:
    """The process ID in the lock file, or None if it can't be read."""
    try:
        return int((data_folder() / NAME).read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def acquire() -> None:
    """Take the project's lock, or refuse if another window holds it."""
    path = data_folder() / NAME
    for _ in range(3):
        try:
            with open(path, "x") as file:
                file.write(str(os.getpid()))
            return
        except FileExistsError:
            pid = _holder()
            if pid == os.getpid():
                return
            if pid is not None and is_running(pid):
                raise StorageError(IN_USE) from None
            # Left by a window that has closed: clear it and try again.
            path.unlink(missing_ok=True)
    raise StorageError(IN_USE)


def release() -> None:
    """Give the lock back, if it is this window's."""
    if _holder() == os.getpid():
        (data_folder() / NAME).unlink(missing_ok=True)
