# Installs or updates Synthase on this laptop and puts `synthase` on your PATH.
# Safe to run again at any time, and in a git clone every `git pull` that brings
# in changes runs it for you. Design: docs/decisions/0011, 0020 and 0021.
#
# Run it from the Synthase code folder:   .\scripts\setup.ps1
#
# Keep this file plain ASCII: Windows PowerShell 5.1 misreads anything else.

# Each step checks its own result, so errors print and the step decides.
$ErrorActionPreference = 'Continue'

$repo = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $repo '.venv'
$venvPython = Join-Path $venv 'Scripts\python.exe'
$bin = Join-Path $env:LOCALAPPDATA 'Synthase\bin'
$appShim = Join-Path $bin 'synthase.cmd'
# The old plain command line, retired in decision 0020.
$oldShim = Join-Path $bin 'syn.cmd'

# Prints the version, the platform (such as win-arm64) and the full path of the
# Python that runs it.
$probe = "import sys, sysconfig; print('%d.%d' % sys.version_info[:2]); print(sysconfig.get_platform()); print(sys.executable)"

# The laptop's own processor, read from the system settings, because an
# emulated PowerShell reports the emulated one. Synthase runs on a Python built
# for this processor (decision 0020), so an ARM laptop needs the ARM64 Python.
$machine = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment').PROCESSOR_ARCHITECTURE
if ($machine -eq 'ARM64') {
    $wantPlatform = 'win-arm64'
    $installer = 'Windows installer (ARM64)'
} else {
    $wantPlatform = 'win-amd64'
    $installer = 'Windows installer (64-bit)'
}
$installFix = "install Python 3.13 from https://www.python.org/downloads/windows/ using `"$installer`""

function Write-Step([string]$text) {
    Write-Host "==> $text ... " -NoNewline
}

function Write-Ok([string]$detail) {
    if ($detail) { Write-Host "ok ($detail)" } else { Write-Host 'ok' }
}

function Stop-Setup([string]$problem, [string]$fix) {
    Write-Host ''
    Write-Host "FAIL: $problem"
    Write-Host "Fix: $fix"
    exit 1
}

# Runs $probe with a Python command such as `python`. Returns the version,
# platform and path, or nothing if that command isn't there or isn't Python.
function Get-PythonInfo([string[]]$command) {
    if (-not (Get-Command $command[0] -ErrorAction SilentlyContinue)) { return }
    $arguments = @($command | Select-Object -Skip 1) + @('-c', $probe)
    $out = @(& $command[0] @arguments 2>$null)
    if ($LASTEXITCODE -eq 0 -and $out.Count -ge 3) {
        return @{ Version = $out[0].Trim(); Platform = $out[1].Trim(); Path = $out[2].Trim() }
    }
}

function Test-RightPython($info) {
    return $info -and $info.Version -eq '3.13' -and $info.Platform -eq $wantPlatform
}

# Every installed Python the py launcher knows, then `python` on the PATH. An
# ARM laptop can have an ARM and an x64 Python 3.13 side by side, so each is
# checked rather than trusting `py -3.13` to pick the right one.
function Find-Python {
    $candidates = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($line in @(& py -0p 2>$null)) {
            if ($line -match '([A-Za-z]:\\.*\.exe)') { $candidates += , @($Matches[1]) }
        }
    }
    $candidates += , @('python')
    foreach ($candidate in $candidates) {
        $info = Get-PythonInfo $candidate
        if (Test-RightPython $info) { return $info }
    }
}

# True when $path is inside a folder OneDrive syncs. Syncing locks and copies
# files while Python writes them, which can break .venv.
function Test-InOneDrive([string]$path) {
    foreach ($root in @($env:OneDrive, $env:OneDriveConsumer, $env:OneDriveCommercial)) {
        if ($root -and $path.StartsWith($root.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

Write-Host 'Synthase setup'

# 0. A warning, not a stop: the code folder should not be synced by OneDrive.
if (Test-InOneDrive $repo) {
    Write-Host "WARNING: the code folder $repo is inside OneDrive."
    Write-Host '         OneDrive can lock or duplicate files while Python uses them, which can break .venv.'
    Write-Host "         Fix: put the code in a folder outside OneDrive, such as $env:USERPROFILE\dev\Synthase, and run this script there."
}

# 1. Python 3.13 (decision 0002), built for this laptop's processor (decision 0020)
Write-Step 'Checking Python 3.13'
$venvExists = Test-Path $venvPython
if ($venvExists) {
    $python = Get-PythonInfo @($venvPython)
    if (-not (Test-RightPython $python)) {
        if ($python) { $found = "Python $($python.Version) for $($python.Platform)" } else { $found = 'a Python that does not run' }
        Stop-Setup "The .venv folder uses $found. Synthase needs Python 3.13 for $wantPlatform, this laptop's own processor." `
            "$installFix, if you don't have it yet. Then delete the .venv folder in $repo and run this script again."
    }
} else {
    $python = Find-Python
    if (-not $python) {
        Stop-Setup "Python 3.13 for $wantPlatform, this laptop's own processor, was not found." `
            "$installFix, then run this script again."
    }
}
Write-Ok "Python $($python.Version), $($python.Platform)"

# 2. The virtual environment
Write-Step 'Virtual environment .venv'
if ($venvExists) {
    Write-Ok 'already there, reusing it'
} else {
    & $python.Path -m venv $venv
    if ($LASTEXITCODE -ne 0) {
        Stop-Setup 'Python could not create the .venv folder.' `
            'read the error above, fix it, then run this script again.'
    }
    Write-Ok 'created'
}

# 3. Synthase and its dependencies, with the developer tools
Write-Step 'Installing Synthase and its dependencies'
Push-Location $repo
& $venvPython -m pip install --quiet --disable-pip-version-check -e '.[dev]'
$pipExit = $LASTEXITCODE
Pop-Location
if ($pipExit -ne 0) {
    Stop-Setup 'pip could not install Synthase.' `
        'check your internet connection and run this script again. The error above says what went wrong.'
}
$installed = @(& $venvPython -c 'import synthase; print(synthase.__version__)' 2>$null)
if ($LASTEXITCODE -ne 0 -or $installed.Count -lt 1) {
    Stop-Setup 'Synthase was installed but Python cannot load it.' `
        "delete the .venv folder in $repo and run this script again."
}
Write-Ok "Synthase $($installed[0].Trim())"

# 4. In a git clone, a post-merge hook that runs this script again after every
#    git pull that brings in changes (decision 0021). Only post-merge is
#    written, so other hooks such as pre-commit stay as they are.
Write-Step 'Installing the update hook'
$gitDir = Join-Path $repo '.git'
if (Test-Path $gitDir -PathType Container) {
    $hook = Join-Path $gitDir 'hooks\post-merge'
    # LF endings whatever the checkout did, because Git for Windows runs hooks
    # with sh, which reads a CR as part of the command.
    $want = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'post-merge')) -replace "`r`n", "`n"
    $have = if (Test-Path $hook) { [IO.File]::ReadAllText($hook) } else { $null }
    if ($have -ceq $want) {
        $hookState = 'already there'
    } else {
        try {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $hook) | Out-Null
            [IO.File]::WriteAllText($hook, $want, [Text.Encoding]::ASCII)
        } catch {
            Stop-Setup "The update hook could not be written to ${hook}: $($_.Exception.Message)" `
                'close any program using that file, then run this script again.'
        }
        $hookState = 'installed'
    }
    Write-Ok "$hookState`: .git\hooks\post-merge"
} else {
    Write-Host 'skipped (this copy has no .git folder; to update, download it again and run this script)'
}

# 5. `synthase` on the PATH, through a folder that holds only synthase.cmd, so
#    the venv's own python and pip stay off the PATH.
Write-Step 'Putting synthase on your PATH'
New-Item -ItemType Directory -Force -Path $bin | Out-Null
# cmd reads .cmd files in the console's code page, so a path with accented
# letters must be written in that code page too.
$oem = [Text.Encoding]::GetEncoding([Globalization.CultureInfo]::CurrentCulture.TextInfo.OEMCodePage)
$app = Join-Path $venv 'Scripts\synthase.exe'
[IO.File]::WriteAllText($appShim, "@`"$app`" %*`r`n", $oem)
if (Test-Path $oldShim) { Remove-Item $oldShim }

function Test-OnPath([string]$pathList) {
    foreach ($entry in $pathList -split ';') {
        $expanded = [Environment]::ExpandEnvironmentVariables($entry).TrimEnd('\')
        if ($expanded -eq $bin.TrimEnd('\')) { return $true }
    }
    return $false
}

# Read and write the user PATH exactly as stored, so entries such as
# %USERPROFILE%\... stay as they are.
$key = Get-Item 'HKCU:\Environment'
$userPath = $key.GetValue('Path', '', 'DoNotExpandEnvironmentNames')
if (Test-OnPath $userPath) {
    $where = 'already there'
} else {
    $kind = if ($userPath) { $key.GetValueKind('Path') } else { 'ExpandString' }
    $newPath = (@($userPath -split ';' | Where-Object { $_ }) + $bin) -join ';'
    Set-ItemProperty -Path 'HKCU:\Environment' -Name Path -Value $newPath -Type $kind
    # Setting and clearing a variable through .NET tells Windows the user
    # environment changed, so new windows see the new PATH.
    [Environment]::SetEnvironmentVariable('SYNTHASE_SETUP', '1', 'User')
    [Environment]::SetEnvironmentVariable('SYNTHASE_SETUP', $null, 'User')
    $where = 'added'
}
if (-not (Test-OnPath $env:Path)) { $env:Path = "$env:Path;$bin" }
Write-Ok "$where`: $bin"

# 6. Typing `synthase` in a new window must run synthase.cmd, not some other
#    program or command with the same name found first.
Write-Step 'Checking what "synthase" runs in a new window'
$sessionPath = $env:Path
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
$first = Get-Command synthase -All -ErrorAction SilentlyContinue | Select-Object -First 1
$env:Path = $sessionPath
if (-not $first) {
    Stop-Setup "A new window cannot find synthase, although $bin is on your PATH." `
        'sign out of Windows and back in, then run this script again.'
}
$target = if ($first.CommandType -eq 'Application') { $first.Source } else { "the PowerShell $($first.CommandType.ToString().ToLower()) named $($first.Name)" }
if ($target -ne $appShim) {
    $fix = 'remove or rename that one (a PowerShell alias or function lives in your profile: type notepad $PROFILE to open it), then run this script again.'
    # A profile can be one of several files, so name the one the function is in.
    if ($first.CommandType -eq 'Function' -and $first.ScriptBlock.File) {
        $file = $first.ScriptBlock.File
        $fix = "remove or rename the function `"$($first.Name)`" in $file (type notepad `"$file`" to open it), then run this script again."
    }
    Stop-Setup "In a new window, typing synthase runs $target instead of $appShim." $fix
}
Write-Ok $appShim

Write-Host ''
Write-Host 'Setup finished. Open a new PowerShell window and type "synthase" from any folder.'
exit 0
