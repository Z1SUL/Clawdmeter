@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo   Clawd on ESP32 - Windows Uninstall
echo ==============================================
echo.
echo This turns off "start at login" and stops the tray/daemon process if
echo one is running right now. It does not delete anything - the .venv,
echo config, and daemon logs under %%LOCALAPPDATA%%\ClawdOnESP32 are left in
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
echo Stopping any running Clawd on ESP32 tray/daemon process...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0daemon\stop_daemon.ps1" -TargetScript "%REPO_ROOT%\daemon\tray_windows.py"

echo.
echo Done. Autostart is off and any running instance has been stopped.
echo.
pause
