from pathlib import Path

SETUP_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "setup.ps1"


def test_setup_script_is_plain_ascii():
    # Windows PowerShell 5.1 reads a script without a byte order mark in the old
    # Windows character set, so any other character could break it (decision 0011).
    # Windows CI runs the script itself.
    SETUP_SCRIPT.read_bytes().decode("ascii")
