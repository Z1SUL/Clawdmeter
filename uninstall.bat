@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo   Clawdmeter - Windows Uninstall
echo ==============================================
echo.
echo This turns off "start at login" and stops the tray/daemon process if
echo one is running right now. It does not delete anything - the .venv,
echo config, and daemon logs under %%LOCALAPPDATA%%\Clawdmeter are left in
echo place. Stopping here is a force-stop, not the tray icon's own "Quit"
echo (which disconnects the device cleanly first) - the device may take a
echo few seconds longer to notice the link dropped and go back to idle.
echo.

set VENV_PY=%~dp0.venv\Scripts\python.exe
if exist "%VENV_PY%" (
    set PY_EXE=%VENV_PY%
) else (
    set PY_EXE=python
)

rem %~dp0 ends in a trailing backslash, which breaks a Python raw string
rem (r'...\') with "unterminated string literal" - strip it before embedding.
set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

"%PY_EXE%" -c "import sys; sys.path.insert(0, r'%REPO_ROOT%'); import daemon.autostart_windows as a; a.disable()"
if errorlevel 1 (
    echo [ERROR] Could not disable autostart - see the message above.
    echo You can also do this manually via the tray icon's right-click menu.
    pause
    exit /b 1
)

echo.
echo Stopping any running Clawdmeter tray/daemon process...
powershell -NoProfile -Command "$ts = Join-Path '%REPO_ROOT%' 'daemon\tray_windows.py'; $hit = $false; Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python' -and $_.CommandLine -and $_.CommandLine.Contains($ts) } | ForEach-Object { $hit = $true; Write-Host ('Stopping PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }; if (-not $hit) { Write-Host 'No running Clawdmeter process found.' }"

echo.
echo Done. Autostart is off and any running instance has been stopped.
echo.
pause
