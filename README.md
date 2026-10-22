# Synthase

A lab databank for a school science project, run full screen inside Windows PowerShell. It stores projects, experiments, measured values and compounds exactly as you type them, keeps a history of every change, and later saves curve fits you can look up again. Synthase uses no AI and gives the same answer for the same input every time. All lab data stays on your own computer, never in this repo.

**Synthase is being rebuilt.** The old app was retired (see [decision 0020](docs/decisions/0020-clean-slate.md)) and the new one is built from the feature spec, [`docs/spec.md`](docs/spec.md), starting with the Ledger. Typing `synthase` opens the app, which so far runs `help` and `exit`; the commands that store data arrive one by one. The version stays at `v0.2.0` until the owner decides to change it. See [ROADMAP.md](ROADMAP.md) for what is being built and in what order.

## Install (Windows PowerShell)

1. **Check your processor.** Windows Settings → **System** → **About** → **System type**. It says either "ARM-based processor" or "x64-based processor".
2. **Install Python 3.13** from [python.org](https://www.python.org/downloads/windows/). Synthase needs exactly 3.13 ([why](docs/decisions/0002-python-version.md)), built for your own processor ([why](docs/decisions/0020-clean-slate.md)):
   - ARM-based processor: choose **Windows installer (ARM64)**.
   - x64-based processor: choose **Windows installer (64-bit)**.

   An x64 Python on an ARM laptop is not enough: the setup script refuses it and says what to install.
3. **Install Git for Windows,** then open a **new** PowerShell window so it can find `git`:
   ```powershell
   winget install --id Git.Git -e
   ```
4. **Get the code** into a folder outside OneDrive (OneDrive can lock files while Python uses them), then run the setup script there:
   ```powershell
   New-Item -ItemType Directory -Force "$env:USERPROFILE\dev"
   cd "$env:USERPROFILE\dev"
   git clone https://github.com/smajeh-dot/Synthase.git
   cd Synthase
   .\scripts\setup.ps1
   ```
   If PowerShell says running scripts is disabled, run this once and try again. It lets scripts made on your own computer run, still blocks unsigned scripts downloaded from the internet, and only affects your user account:
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   ```
   The script checks Python 3.13, creates a private Python folder for Synthase (`.venv`), installs Synthase, installs the update hook and puts `synthase` on your PATH ([how](docs/decisions/0011-setup-script.md)). It names anything that goes wrong and how to fix it, and ends with `Setup finished.`
5. **Check it works.** Open a **new** PowerShell window and type this from any folder:
   ```powershell
   synthase
   ```
   The app opens full screen in that folder. Type `help` to see the commands, and `exit` (or press Ctrl+D) to leave. A folder with no project says `No Synthase project here.`; that's expected until `project create` is built.

**Without Git,** download a ZIP copy instead: on the GitHub page, click **Code** → **Download ZIP** in your browser, unzip it outside OneDrive, open PowerShell in the unzipped folder (the one with `pyproject.toml` in it) and run `.\scripts\setup.ps1`. Use the browser: downloading the ZIP with `Invoke-WebRequest` can save a small web page instead of the code. A ZIP copy can't update itself with `git pull` (see below).

## Updating after a change is merged

In a code folder made with `git clone`, one command does everything. Open PowerShell in the code folder and run:
```powershell
git pull
```
When the pull brings in changes, git runs the setup script for you, so any new dependency or command is installed with the new code. You'll see `Synthase: the pull brought in changes, so the setup script is running again.`, then the setup's own lines. If git says `Already up to date`, nothing changed and nothing runs. This works once you have run `.\scripts\setup.ps1` in that folder, which installs the git "hook" that does it ([how](docs/decisions/0021-update-with-git-pull.md)).

If the setup fails during a pull, the code is still updated. Fix the problem it names, then run `.\scripts\setup.ps1` again. Close `synthase` in other windows before you pull: Windows won't let the setup replace a program that is running.

**To get a clone,** follow steps 3 and 4 of the install above.

**A ZIP copy** has no git, so the setup script says it skipped the hook. To update it, download and unzip the code again, then run `.\scripts\setup.ps1` in the new folder.

If PowerShell says running scripts is disabled, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once (see step 4 for what it means), then run the script again.

**To take `synthase` off your PATH:** Windows Settings → search "Edit environment variables for your account" → select **Path** → **Edit** → remove the line ending in `Synthase\bin` → **OK**. You can then delete that `Synthase` folder in `%LOCALAPPDATA%` too.
