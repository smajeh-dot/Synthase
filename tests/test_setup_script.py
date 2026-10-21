from pathlib import Path

SETUP_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "setup.ps1"
HOOK_TEMPLATE = SETUP_SCRIPT.parent / "post-merge"


def test_setup_script_is_plain_ascii():
    # Windows PowerShell 5.1 reads a script without a byte order mark in the old
    # Windows character set, so any other character could break it (decision 0011).
    # Windows CI runs the script itself.
    SETUP_SCRIPT.read_bytes().decode("ascii")


def test_hook_template_is_ascii_with_lf_endings():
    # Git for Windows runs hooks with sh, which reads a CR as part of the
    # command (decision 0021).
    text = HOOK_TEMPLATE.read_bytes().decode("ascii")
    assert "\r" not in text
    assert text.startswith("#!/bin/sh\n")


def test_hook_template_runs_the_setup_script():
    assert "-File scripts/setup.ps1" in HOOK_TEMPLATE.read_text(encoding="ascii")


def test_clash_fix_names_the_profile_file():
    # A profile can be one of several files, so the Fix: line names the one the
    # clashing function is in (#94). CI checks the message on Windows.
    script = SETUP_SCRIPT.read_text(encoding="ascii")
    assert "$first.ScriptBlock.File" in script
    assert 'remove or rename the function `"$($first.Name)`" in $file' in script
