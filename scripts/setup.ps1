# Installs or updates Synthase on this laptop, puts `syn` on your PATH and runs
# `syn doctor`. Safe to run again after every merge. Design: docs/decisions/0011.
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
$shim = Join-Path $bin 'syn.cmd'

# Prints the version, then the full path, of the Python that runs it.
$probe = "import sys; print('%d.%d' % sys.version_info[:2]); print(sys.executable)"

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

# Runs $probe with a Python command such as `py -3.13`. Returns the version and
# path, or nothing if that command isn't there or isn't Python.
function Get-PythonInfo([string[]]$command) {
    if (-not (Get-Command $command[0] -ErrorAction SilentlyContinue)) { return }
    $arguments = @($command | Select-Object -Skip 1) + @('-c', $probe)
    $out = @(& $command[0] @arguments 2>$null)
    if ($LASTEXITCODE -eq 0 -and $out.Count -ge 2) {
        return @{ Version = $out[0].Trim(); Path = $out[1].Trim() }
    }
}

Write-Host 'Synthase setup'

# 1. Python 3.13 (decision 0002)
Write-Step 'Checking Python 3.13'
$venvExists = Test-Path $venvPython
if ($venvExists) {
    $python = Get-PythonInfo @($venvPython)
    if (-not $python -or $python.Version -ne '3.13') {
        Stop-Setup "The .venv folder doesn't use Python 3.13." `
            "delete the .venv folder in $repo, then run this script again."
    }
} else {
    $python = Get-PythonInfo @('py', '-3.13')
    if (-not $python -or $python.Version -ne '3.13') {
        $python = Get-PythonInfo @('python')
    }
    if (-not $python -or $python.Version -ne '3.13') {
        Stop-Setup 'Python 3.13 was not found.' `
            'install Python 3.13 from https://www.python.org/downloads/windows/, then run this script again.'
    }
}
Write-Ok "Python $($python.Version)"

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
Write-Step 'Installing Synthase and its dependencies (RDKit is about 30 MB)'
Push-Location $repo
& $venvPython -m pip install --quiet --disable-pip-version-check -e '.[dev]'
$pipExit = $LASTEXITCODE
Pop-Location
if ($pipExit -ne 0) {
    Stop-Setup 'pip could not install Synthase (often RDKit, the chemistry library).' `
        'check your internet connection and run this script again. The error above says what went wrong.'
}
Write-Ok ''

# 4. `syn` on the PATH, through a folder that holds only syn.cmd, so the venv's
#    own python and pip stay off the PATH.
Write-Step 'Putting syn on your PATH'
New-Item -ItemType Directory -Force -Path $bin | Out-Null
# cmd reads .cmd files in the console's code page, so a path with accented
# letters must be written in that code page too.
$oem = [Text.Encoding]::GetEncoding([Globalization.CultureInfo]::CurrentCulture.TextInfo.OEMCodePage)
$syn = Join-Path $venv 'Scripts\syn.exe'
[IO.File]::WriteAllText($shim, "@`"$syn`" %*`r`n", $oem)

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

# 5. The self-test, through the PATH folder (decision 0010)
Write-Host '==> Running syn doctor ...'
& $shim doctor
$doctorExit = $LASTEXITCODE
Write-Host ''
if ($doctorExit -eq 0) {
    Write-Host 'Setup finished. Open a new PowerShell window and type "syn" from any folder.'
} else {
    Write-Host 'Setup finished, but syn doctor found a problem. Follow its Fix: lines above, then run "syn doctor" again.'
}
exit $doctorExit
