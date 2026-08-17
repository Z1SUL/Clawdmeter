; Clawd on ESP32 Windows installer (Inno Setup).
;
; Fully offline: bundles the portable Python runtime from runtime\python\
; (built once via daemon\README-windows.md's "Building runtime\python\
; yourself" recipe) with bleak/httpx/pystray/Pillow already installed into
; it, so the target machine needs neither Python nor an internet connection.
;
; Per-user install (no admin, no UAC prompt): DefaultDirName lives under
; %LocalAppData%\Programs, matching HKCU-only autostart (same posture as
; install-windows.ps1 / install.bat - see daemon/README-windows.md).
;
; MyAppName is the display name (shown in the wizard, Start Menu, Apps &
; Features); MyAppId is the space-free internal identifier used for the
; install folder name, the autostart registry value name, and similar
; machine-facing strings - kept separate so folder/registry paths never
; need quoting gymnastics just because the product name has a space in it.
;
; Build: "C:\Users\<you>\AppData\Local\Programs\Inno Setup 6\ISCC.exe" clawd_on_esp32.iss
; Output: ..\dist\ClawdOnESP32Setup.exe

#define MyAppName "Clawd on ESP32"
#define MyAppId "ClawdOnESP32"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Clawd on ESP32"

[Setup]
AppId={{6BF1D675-FB2D-4439-9140-775EC89A062D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppId}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename={#MyAppId}Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableWelcomePage=no
DisableDirPage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Code]
// On a reinstall/upgrade over an existing install, a running tray/daemon
// process holds runtime\python\pythonw.exe (and its loaded .pyd/.dll's)
// open - Windows won't let [Files] overwrite or add sibling files in a
// locked directory tree, so new files (e.g. this build's tkinter DLLs)
// can silently fail to land while the installer reports success (field
// bug: a reinstall added tkinter support but the running instance's lock
// kept it out). Stop it here, before any file is touched.
//
// PrepareToInstall, not InitializeSetup: {app} isn't resolved yet at
// InitializeSetup time (runs before the install-directory page), so
// ExpandConstant('{app}\...') there raises "constant before it was
// initialized" - PrepareToInstall runs after {app} is finalized but
// before [Files] starts copying, which is exactly the window needed here.
// Harmless no-op on a first-time install - {app}\daemon\stop_daemon.ps1
// doesn't exist yet.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ScriptPath: String;
  TargetPath: String;
  ResultCode: Integer;
begin
  Result := '';
  ScriptPath := ExpandConstant('{app}\daemon\stop_daemon.ps1');
  if FileExists(ScriptPath) then begin
    TargetPath := ExpandConstant('{app}\daemon\tray_windows.py');
    Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      '-NoProfile -ExecutionPolicy Bypass -File "' + ScriptPath + '" -TargetScript "' + TargetPath + '"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;

[Files]
Source: "..\daemon\__init__.py"; DestDir: "{app}\daemon"; Flags: ignoreversion
Source: "..\daemon\autostart_windows.py"; DestDir: "{app}\daemon"; Flags: ignoreversion
Source: "..\daemon\claude_usage_daemon_windows.py"; DestDir: "{app}\daemon"; Flags: ignoreversion
Source: "..\daemon\icon_assets.py"; DestDir: "{app}\daemon"; Flags: ignoreversion
Source: "..\daemon\settings_windows.py"; DestDir: "{app}\daemon"; Flags: ignoreversion
Source: "..\daemon\stop_daemon.ps1"; DestDir: "{app}\daemon"; Flags: ignoreversion
Source: "..\daemon\tray_windows.py"; DestDir: "{app}\daemon"; Flags: ignoreversion
Source: "..\daemon\config.example"; DestDir: "{app}\daemon"; Flags: ignoreversion
Source: "..\daemon\README-windows.md"; DestDir: "{app}\daemon"; Flags: ignoreversion
Source: "..\daemon\hooks\*"; DestDir: "{app}\daemon\hooks"; Flags: ignoreversion recursesubdirs
Source: "..\firmware\src\logo.h"; DestDir: "{app}\firmware\src"; Flags: ignoreversion
Source: "..\runtime\python\*"; DestDir: "{app}\runtime\python"; Flags: ignoreversion recursesubdirs

[Registry]
; Same HKCU\...\Run key/value the in-app "Start at login" tray-menu toggle
; already manages (daemon\autostart_windows.py) - the toggle keeps working
; after an installer-based setup. uninsdeletevalue removes it on uninstall.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppId}"; ValueData: """{app}\runtime\python\pythonw.exe"" ""{app}\daemon\tray_windows.py"""; Flags: uninsdeletevalue

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\runtime\python\pythonw.exe"; Parameters: """{app}\daemon\tray_windows.py"""; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\runtime\python\pythonw.exe"; Parameters: """{app}\daemon\tray_windows.py"""; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent; Description: "Launch {#MyAppName} now"

[UninstallRun]
; Force-stop any running instance before its files are removed (the bundled
; pythonw.exe / loaded .pyd's are locked while the process is alive - can't
; delete them out from under it). Matched by full tray_windows.py path, not
; just image name, so this can never touch an unrelated pythonw.exe process.
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\daemon\stop_daemon.ps1"" -TargetScript ""{app}\daemon\tray_windows.py"""; Flags: runhidden waituntilterminated; RunOnceId: "Stop{#MyAppId}"

[UninstallDelete]
; Inno only auto-removes directories that end up empty after deleting the
; files it tracked in [Files] - running the app generates daemon\__pycache__\
; (untracked bytecode cache), which leaves that non-empty and the whole
; install folder behind as an orphaned shell otherwise. Force-remove the
; entire {app} tree so uninstall is actually clean.
Type: filesandordirs; Name: "{app}"
