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
4. **Install Synthase** with its developer tools:
   ```powershell
   python -m pip install -e ".[dev]"
   ```
5. **Check it works:**
   ```powershell
   syn --version
   syn --help
   pytest
   ```

Next time, only step 3's `.\.venv\Scripts\Activate.ps1` is needed before using `syn`.
