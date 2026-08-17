@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo   Clawdmeter - Windows Install
echo ==============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    rem No system Python - install-windows.ps1 falls back to the bundled
    rem portable runtime at runtime\python\ if this repo has one, so only
    rem hard-fail here when NEITHER is available.
    if not exist "%~dp0runtime\python\python.exe" (
        echo [ERROR] Python was not found on PATH, and this copy has no
        echo bundled runtime ^(runtime\python\^) either.
        echo.
        echo Install Python 3.11+ from https://www.python.org/downloads/
        echo ^(check "Add python.exe to PATH" during setup^), then double-click
        echo this file again.
        echo.
        pause
        exit /b 1
    )
    echo No system Python found - using the bundled portable runtime instead.
    echo.
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-windows.ps1"
set INSTALL_RESULT=%ERRORLEVEL%

echo.
if %INSTALL_RESULT% neq 0 (
    echo [ERROR] Install failed - see the messages above for details.
) else (
    echo Done. Look for the Clawdmeter icon in your notification area.
    echo It will now also start automatically at every login.
)
echo.
pause
