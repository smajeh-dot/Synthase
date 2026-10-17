# Synthase

Lab calculations and data analysis for a school chemistry and microbiology project, run from the terminal. Synthase works offline, uses no AI, and gives the same answer for the same input every time. All lab data stays on your own computer, never in this repo.

See [ROADMAP.md](ROADMAP.md) for what is being built and in what order.

## Quick start (Windows PowerShell)

1. **Install Python 3.13** from [python.org](https://www.python.org/downloads/windows/). Synthase needs exactly 3.13 ([why](docs/decisions/0002-python-version.md)). Then check that it's there:
   ```powershell
   py -3.13 --version
   ```
2. **Get the code.** On GitHub, click **Code** → **Download ZIP**, unzip it, and open PowerShell in the unzipped folder (the one with `pyproject.toml` in it).
3. **Create a virtual environment** (a private Python folder just for Synthase) and switch it on:
   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   If PowerShell says running scripts is disabled, run this once and try again. It lets scripts made on your own computer run (such as `Activate.ps1`), still blocks unsigned scripts downloaded from the internet, and only affects your user account:
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   ```
4. **Install Synthase** with its developer tools. This also downloads RDKit (about 30 MB), the chemistry library Synthase uses:
   ```powershell
   python -m pip install -e ".[dev]"
   ```
5. **Check it works:**
   ```powershell
   syn --version
   syn --help
   pytest
   ```
6. **Create your workspace and run the self-test.** `syn init` makes the folder for your lab data, outside the code folder. `syn doctor` then checks everything is set up, says how to fix anything that isn't, and lists every config value you haven't checked against the literature yet:
   ```powershell
   syn init
   syn doctor
   ```

7. **Put `syn` on your PATH.** Run the setup script from the code folder:
   ```powershell
   .\scripts\setup.ps1
   ```
   It checks Python 3.13, reuses `.venv` (or creates it), installs Synthase, puts `syn` on your PATH and finishes by running `syn doctor`. After that, `syn` works in any **new** PowerShell window, from any folder, without activating `.venv` ([how](docs/decisions/0011-setup-script.md)).

## Updating after a change is merged

1. Get the new code the way you usually do.
2. Run the setup script again from the code folder. It's safe to run as often as you like:
   ```powershell
   .\scripts\setup.ps1
   ```

Most code changes work straight away, because Synthase is installed in "editable" mode (`-e`): `syn` runs the code in this folder directly. The script is only needed when a change adds a dependency or a new command, but running it every time does no harm.

If PowerShell says running scripts is disabled, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once (see step 3 for what it means), then run the script again.

**To take `syn` off your PATH:** Windows Settings → search "Edit environment variables for your account" → select **Path** → **Edit** → remove the line ending in `Synthase\bin` → **OK**. You can then delete that `Synthase` folder in `%LOCALAPPDATA%` too.
