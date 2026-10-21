# Synthase

Lab calculations and data analysis for a school chemistry and microbiology project, run from the terminal. Synthase works offline, uses no AI, and gives the same answer for the same input every time. All lab data stays on your own computer, never in this repo.

See [ROADMAP.md](ROADMAP.md) for what is being built and in what order.

## Quick start (Windows PowerShell)

1. **Install Python 3.13** from [python.org](https://www.python.org/downloads/windows/). Synthase needs exactly 3.13 ([why](docs/decisions/0002-python-version.md)). Choose **Windows installer (64-bit)**, even on an ARM laptop: RDKit, the chemistry library, has no ARM version for Windows, and Windows 11 runs the 64-bit Intel/AMD version through emulation ([why](docs/decisions/0011-setup-script.md)). Then check that it's there:
   ```powershell
   py -3.13 --version
   ```
2. **Get the code.** On GitHub, click **Code** → **Download ZIP**, unzip it, and open PowerShell in the unzipped folder (the one with `pyproject.toml` in it).
3. **Create a virtual environment** (a private Python folder just for Synthase) and switch it on. On an ARM laptop that also has the ARM Python, skip steps 3 to 5 and run the setup script (step 7) instead: it picks the right Python.
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

## Using the app

Synthase has a full-screen app, and the plain command line (`syn`) described above. Both do the same work.

**Open it:** after the setup script (step 7), open a **new** PowerShell window and type this from any folder:
```powershell
synthase
```
It works best in Windows Terminal, which is the default on Windows 11. The app opens in the same window, and your PowerShell comes back when you close it.

Type a command, such as `doctor`, and press Enter. A `/` in front (`/doctor`) works too, but isn't needed. Anything that isn't a command gets "unknown command, try help".

| Key | What it does |
|---|---|
| Enter | Runs what you typed |
| Up and down arrows | Step back and forward through the commands you typed before |
| Tab | Completes the command or topic you are typing, or lists the choices |
| Esc or Ctrl+C | Cancels a question the app is asking you |
| Page Up and Page Down | Scroll the output |
| Ctrl+Q, or type `quit` | Closes the app |

Type `help` for the list of commands, or `help compound` to see one command's options. The plain command line still works as before, for example `syn compound list`.

Manuals: [fit check](docs/fit-manual.md), for checking a file of measurements before a curve is fitted to it.

## Updating after a change is merged

In a code folder made with `git clone`, one command does everything. Open PowerShell in the code folder and run:
```powershell
git pull
```
When the pull brings in changes, git runs the setup script for you, so any new dependency or command is installed with the new code. You'll see `Synthase: the pull brought in changes, so the setup script is running again.`, then the setup's own lines. If git says `Already up to date`, nothing changed and nothing runs. This works once you have run `.\scripts\setup.ps1` in that folder, which installs the git "hook" that does it ([how](docs/decisions/0021-update-with-git-pull.md)).

If the setup fails during a pull, the code is still updated. Fix the problem it names, then run `.\scripts\setup.ps1` again. Close `synthase` in other windows before you pull: Windows won't let the setup replace a program that is running.

**To get a clone,** once, instead of a ZIP download:
1. Install Git for Windows, then open a **new** PowerShell window so it can find `git`:
   ```powershell
   winget install --id Git.Git -e
   ```
2. Clone the code into a folder outside OneDrive, then run the setup script there:
   ```powershell
   New-Item -ItemType Directory -Force "$env:USERPROFILE\dev"
   cd "$env:USERPROFILE\dev"
   git clone https://github.com/smajeh-dot/Synthase.git
   cd Synthase
   .\scripts\setup.ps1
   ```

**A ZIP copy** has no git, so the setup script says it skipped the hook. To update it, download and unzip the code again, then run `.\scripts\setup.ps1` in the new folder.

If PowerShell says running scripts is disabled, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once (see step 3 for what it means), then run the script again.

**To take `synthase` off your PATH:** Windows Settings → search "Edit environment variables for your account" → select **Path** → **Edit** → remove the line ending in `Synthase\bin` → **OK**. You can then delete that `Synthase` folder in `%LOCALAPPDATA%` too.
