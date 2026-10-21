> **Partly superseded by [0020](0020-clean-slate.md):** the setup script now wants Python 3.13 built for the laptop's own processor, not the x64 Python that RDKit needed.

# 0011: The PowerShell setup script, for one laptop

## Context
#13 asked for one PowerShell script that takes a fresh Windows laptop to a working `syn` command. Before the triage, the owner set a rule for now (comment on #13, 2026-10-17): **Synthase only needs to work on the owner's own Windows laptop.** Rolling it out to lab partners comes later, after some changes, and will get its own issue.

That laptop already has Python 3.13, a `.venv` and a workspace. The real pain is typing `.\.venv\Scripts\Activate.ps1` before every use, and the `pip install` line after each merge. So the script is mainly an install-and-update step, not a fresh-laptop installer.

The owner chose all the triage defaults below for #13 (2026-10-17).

## Decision
- **Scope:** `scripts/setup.ps1` installs or updates Synthase on the owner's laptop. It is safe to run again after every merge.
  - **Kept, because each is cheap:** a Python 3.13 check with its fix, a fix for blocked scripts (in the README, because PowerShell stops a blocked script before it can print anything), a pip failure message that names RDKit, and a CI run of the script.
  - **Moved to the later lab-partner rollout issue:** a full fresh-laptop walkthrough in the README (installing Python, getting the code) and detailed diagnosis of RDKit install failures.
- **Steps, each printed as one `==>` line ending in `ok`, or followed by `FAIL:` and `Fix:` lines:**
  1. **Python 3.13 for 64-bit Intel/AMD (`win-amd64`).** An existing `.venv` is reused if its Python is both. Any other `.venv` fails, with the fix "install that Python, delete the .venv folder and run this script again". With no `.venv`, the script checks every Python the `py` launcher lists (`py -0p`), then `python`, and uses the first that is both.
  2. **`.venv`** in the code folder: reused, or created with that Python.
  3. **Install:** `python -m pip install -e ".[dev]"` from the code folder. The developer tools stay, so `pytest` still works on the laptop.
  4. **PATH:** see below.
  5. **`syn doctor`**, run through the new PATH folder. The script ends with doctor's exit code (decision 0010).
- **Putting `syn` on the PATH:** the script writes a one-line `syn.cmd` into `%LOCALAPPDATA%\Synthase\bin` that runs `.venv\Scripts\syn.exe`, and adds **only that folder** to the user PATH.
  - Adding `.venv\Scripts` itself was rejected. It would also put the venv's `python` and `pip` on the PATH, and could quietly change what `python` means in other projects.
  - The folder is added at most once. The user PATH is read and written in the registry as it is stored, so entries such as `%USERPROFILE%\…` keep working as they did.
  - The script also adds the folder to the PATH of the window it is running in, so `syn` works there straight away. Other windows need reopening.
  - `syn.cmd` is written in the console's code page, so a code folder path with accented letters still works.
- **ARM laptops use the 64-bit Intel/AMD Python.** The owner's laptop is ARM. Its first run of the script failed with `No matching distribution found for rdkit`, because RDKit publishes Windows installs only for `win-amd64` (checked on PyPI for 2026.9.1). Windows 11 on ARM runs that Python through emulation, so the owner installs it alongside the ARM one and rebuilds `.venv` with it. The script checks the platform as well as the version, and doesn't trust `py -3.13` to choose between the two. Building RDKit from source for ARM, or making it optional, were rejected: the first is impractical and the compound register (M1) needs RDKit.
- **No git:** the script never pulls code. The owner gets new code their usual way, then runs the script. Because the install is editable (`-e`), most code changes take effect without running it. It is needed after a merge that adds a dependency or a new command.
- **Windows PowerShell 5.1 and PowerShell 7 both run it.** The script is plain ASCII, because Windows PowerShell 5.1 misreads other characters in a file without a byte order mark. A test checks this.
- **CI:** after pytest, CI runs `syn init` into a temporary folder (doctor fails without a workspace), runs the script twice, checks the user PATH holds the folder exactly once, then opens a PATH built only from the registry, as a new window would, and checks `syn` resolves to `syn.cmd` there and `syn doctor` passes.

## Consequences
- After a merge, the owner's update step is: get the new code, then `.\scripts\setup.ps1`. Activating `.venv` is no longer needed to use `syn`.
- The script changes the user PATH. The README says how to undo that: Windows Settings → "Edit environment variables for your account" → Path → remove the `Synthase\bin` line.
- Pressing Ctrl+C during a `syn` command asks "Terminate batch job (Y/N)?", because `syn` runs through a `.cmd` file. `syn` commands are quick, so this is minor.
- On the ARM laptop, Synthase runs under emulation, so it starts a little slower. If RDKit ever publishes ARM installs for Windows, this can be revisited.
- The script can only run on Windows, so only Windows CI and the owner's laptop test it.
- Rolling out to lab partners needs its own issue, which picks up the moved items.
