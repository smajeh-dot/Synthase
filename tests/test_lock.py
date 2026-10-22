import os
import subprocess
import sys

import pytest

from synthase import lock
from synthase.storage import StorageError


@pytest.fixture
def other_process():
    """Another running process, as a second Synthase window would be."""
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    yield process.pid
    process.kill()
    process.wait()


@pytest.fixture
def finished_process():
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait()
    return process.pid


def test_opening_a_project_writes_the_lock(data):
    lock.acquire()
    assert (data / ".synthase.lock").read_text() == str(os.getpid())
    lock.release()
    assert not (data / ".synthase.lock").exists()


def test_a_second_synthase_is_refused(data, other_process):
    (data / ".synthase.lock").write_text(str(other_process))
    with pytest.raises(StorageError) as raised:
        lock.acquire()
    assert str(raised.value) == (
        "This project is already open in another Synthase window. "
        "Close it there first. If no other window is open, "
        "delete data\\.synthase.lock and try again."
    )
    assert (data / ".synthase.lock").read_text() == str(other_process)


def test_a_lock_left_by_a_stopped_process_is_ignored(data, finished_process):
    (data / ".synthase.lock").write_text(str(finished_process))
    lock.acquire()
    assert (data / ".synthase.lock").read_text() == str(os.getpid())


def test_an_unreadable_lock_is_ignored(data):
    (data / ".synthase.lock").write_text("not a number")
    lock.acquire()
    assert (data / ".synthase.lock").read_text() == str(os.getpid())


def test_taking_our_own_lock_again_is_fine(data):
    lock.acquire()
    lock.acquire()
    assert (data / ".synthase.lock").read_text() == str(os.getpid())


def test_releasing_never_removes_another_windows_lock(data, other_process):
    (data / ".synthase.lock").write_text(str(other_process))
    lock.release()
    assert (data / ".synthase.lock").exists()


def test_telling_running_from_stopped(other_process, finished_process):
    assert lock.is_running(os.getpid())
    assert lock.is_running(other_process)
    assert not lock.is_running(finished_process)
