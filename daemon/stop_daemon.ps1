<#
.SYNOPSIS
  Stops a running Clawd on ESP32 tray/daemon process, matched precisely by the
  full path of the tray_windows.py it was launched with (not just by image
  name) so this never touches an unrelated pythonw.exe on the machine.

.PARAMETER TargetScript
  Full path to the tray_windows.py this install/instance uses.

.NOTES
  Shared by uninstall.bat and the Inno Setup installer's [UninstallRun] step
  - one implementation, two callers. Force-stops (no graceful BLE
  disconnect) - the tray icon's own "Quit" menu item is the clean-shutdown
  path; this is the best-effort one for install/uninstall scripts.
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$TargetScript
)

$hit = $false
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^python' -and $_.CommandLine -and $_.CommandLine.Contains($TargetScript)
} | ForEach-Object {
    $hit = $true
    Write-Host ("Stopping PID " + $_.ProcessId)
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
if (-not $hit) {
    Write-Host "No running Clawd on ESP32 process found."
}
