# install-windows.ps1 - Clawd on ESP32 Windows turnkey bootstrap (D-09)
#
# Gets a working Python (system Python if found -> venv + pip install; else
# the in-repo portable runtime at runtime\python\, which already has every
# dependency baked in), registers the tray app to launch at login
# (HKCU\...\Run, no admin required), and starts the tray app immediately.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File install-windows.ps1
#
# Or, if you have already set a permissive execution policy:
#   .\install-windows.ps1
#
# To disable autostart later: right-click the tray icon -> uncheck "Start at login"
# Or remove manually: reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v ClawdOnESP32 /f
#
# Security: this script downloads nothing from the internet. It installs only
# the packages listed in the in-repo daemon\requirements-windows.txt (system-
# Python path), or uses the already-populated in-repo runtime\python\ folder
# (no-system-Python path) - either way nothing is fetched at install time.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Log {
    param([string]$Msg)
    $ts = Get-Date -Format "HH:mm:ss"
    Write-Host "[$ts] $Msg"
}

$RepoRoot = $PSScriptRoot
if (-not $RepoRoot) {
    $RepoRoot = (Get-Location).Path
}

Log "=== Clawd on ESP32 Windows Install ==="
Log "Repository root: $RepoRoot"

# ------------------------------------------------------------------
# Guard: refuse to install from a WSL path (APP-02 / SC#4 / SC#5)
# ------------------------------------------------------------------
# If $RepoRoot lives on the WSL share (\\wsl$\... or \\wsl.localhost\...),
# the venv and the HKCU\Run autostart entry would both point at a path that
# disappears when WSL is shut down -- exactly the WSL-dependence this project
# exists to eliminate. Copy the repo to a native Windows path first.
if ($RepoRoot -match '\\\\wsl(\$|\.localhost)\\') {
    throw @"
Refusing to install from a WSL path:
  $RepoRoot

The Clawd on ESP32 daemon must be WSL-independent. Installing from the WSL share
would make the virtual environment and login-autostart entry point at a path
that is unreachable once WSL shuts down.

Fix: copy this repository to a native Windows location and run the installer
there, e.g.

  Copy-Item -Recurse '$RepoRoot' "$env:USERPROFILE\ClawdOnESP32"
  cd "$env:USERPROFILE\ClawdOnESP32"
  powershell -ExecutionPolicy Bypass -File install-windows.ps1
"@
}

# ------------------------------------------------------------------
# Step 1+2: Get a working Python.
# ------------------------------------------------------------------
# Prefer the system interpreter when present - unchanged venv + pip install
# behavior, so existing installs and dev machines with Python already on
# PATH are unaffected. Falls back to the in-repo portable runtime
# (runtime\python\) when no system Python is found: that folder ships with
# bleak/httpx/pystray/Pillow already installed into its own site-packages
# (built the same way this venv step would, just done once ahead of time),
# so a brand-new machine with nothing installed still works with zero
# internet access and no separate Python setup step.
$SystemPython = Get-Command python -ErrorAction SilentlyContinue
if ($SystemPython) {
    Log "System Python found: $($SystemPython.Source)"

    $VenvDir = Join-Path $RepoRoot ".venv"
    if (Test-Path $VenvDir) {
        Log "Virtual environment already exists at .venv - skipping creation"
    } else {
        Log "Creating virtual environment at .venv ..."
        & python -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment (exit $LASTEXITCODE)" }
        Log "Virtual environment created"
    }

    $PythonExe = Join-Path $VenvDir "Scripts\python.exe"
    $RequirementsFile = Join-Path $RepoRoot "daemon\requirements-windows.txt"
    Log "Installing dependencies from daemon\requirements-windows.txt ..."
    & $PythonExe -m pip install --quiet -r $RequirementsFile
    if ($LASTEXITCODE -ne 0) { throw "pip install failed (exit $LASTEXITCODE)" }
    Log "Dependencies installed"
} else {
    $BundledPython = Join-Path $RepoRoot "runtime\python\python.exe"
    if (-not (Test-Path $BundledPython)) {
        throw @"
No Python found on PATH, and no bundled runtime at runtime\python\ either.

Install Python 3.11+ from https://www.python.org/downloads/ (check "Add
python.exe to PATH" during setup) and run this installer again - or make
sure you got this repository as a release/copy that includes the
runtime\python\ folder.
"@
    }
    Log "No system Python on PATH - using the bundled portable runtime at runtime\python\"
    Log "(it already has bleak/httpx/pystray/Pillow installed - nothing to download or create)"
    $PythonExe = $BundledPython
}

# ------------------------------------------------------------------
# Step 3: Register autostart (HKCU\Run, per-user, no admin needed)
# ------------------------------------------------------------------
# Derive all paths at install time - never hard-code an absolute path that
# breaks when the repository is moved (CLAUDE.md "repoint ExecStart" lesson,
# RESEARCH Anti-Pattern).
$TrayScript = Join-Path $RepoRoot "daemon\tray_windows.py"

Log "Registering autostart (HKCU\Software\Microsoft\Windows\CurrentVersion\Run) ..."
# Invoke the autostart helper via the just-created venv python so sys.executable
# resolves to the venv's pythonw.exe (the path that will be written to the registry).
& $PythonExe -c @"
import sys, os
sys.path.insert(0, r'$RepoRoot')
import daemon.autostart_windows as a
a.enable(tray_script=r'$TrayScript')
"@
if ($LASTEXITCODE -ne 0) { throw "Autostart registration failed (exit $LASTEXITCODE)" }
Log "Autostart registered - Clawd on ESP32 will launch automatically at next logon"

# ------------------------------------------------------------------
# Step 4: Launch the tray app (headless - BASE pythonw.exe, no console window)
# ------------------------------------------------------------------
# Use the BASE interpreter's pythonw.exe, NOT the venv's Scripts\pythonw.exe.
# The venv pythonw is a redirector stub that re-launches the CONSOLE python.exe
# build as a child (a CPython venv-launcher bug), popping a black console window.
# tray_windows.py adds the venv site-packages to sys.path itself, so the venv's
# dependencies still resolve. (See autostart_windows._command - same rationale.)
# This also just works for the bundled-runtime path above: runtime\python\ isn't
# a venv, so sys.base_exec_prefix there resolves to itself.
$BasePrefix  = & $PythonExe -c "import sys; print(sys.base_exec_prefix)"
$BasePythonw = Join-Path $BasePrefix "pythonw.exe"

Log "Launching tray app ..."
$StartArgs = @{
    FilePath         = $BasePythonw
    ArgumentList     = "`"$TrayScript`""
    WorkingDirectory = $RepoRoot
}
Start-Process @StartArgs
Log "Tray app started - look for the Clawd on ESP32 icon in your notification area"
Log "=== Install complete ==="
