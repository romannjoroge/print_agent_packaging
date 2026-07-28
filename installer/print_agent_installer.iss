; Print Agent Inno Setup Installer Script
;
; Build with Inno Setup 6+:
;   iscc installer/print_agent_installer.iss
;
; Prerequisites on the build machine:
;   1. Python 3.10+ installed
;   2. pip install pyinstaller winservicetools
;   3. pip install -r requirements.txt (from the print_agent project)
;   4. Build the config GUI exe:
;      pyinstaller build/config_gui.spec
;   5. Copy dist/print_agent_config.exe to the build output

#define MyAppName "Print Agent"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Print Agent"
#define MyAppExeName "print_agent_config.exe"

[Setup]
AppId={B1E2F3A4-5678-9ABC-DEF0-123456789ABC}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\PrintAgent
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=
OutputDir=..\installer_output
OutputBaseFilename=PrintAgentSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Config GUI exe (PyInstaller-built)
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Service script and dependencies
Source: "..\service.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\config_manager.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\config_gui.py"; DestDir: "{app}"; Flags: ignoreversion

; print_agent package (the core project)
Source: "..\..\print_agent\print_agent\*"; DestDir: "{app}\print_agent"; Flags: ignoreversion recursesubdirs

; Default config file (only installed if none exists)
Source: "..\config.example.yaml"; DestDir: "{app}"; DestName: "config.yaml"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\Configure Print Agent"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall Print Agent"; Filename: "{uninstallexe}"

[Run]
; Install and start the Windows service via winservicetools
; winservicetools.exe is installed into the Python Scripts dir by pip
Filename: "winservicetools.exe"; Parameters: "install --script ""{app}\service.py"""; StatusMsg: "Installing Print Agent service..."; Flags: runhidden waituntilterminated
Filename: "sc.exe"; Parameters: "start PrintAgent"; StatusMsg: "Starting Print Agent service..."; Flags: runhidden waituntilterminated

; Optionally launch the config GUI after install
Filename: "{app}\{#MyAppExeName}"; Description: "Configure Print Agent"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Stop and remove the service before uninstalling
Filename: "sc.exe"; Parameters: "stop PrintAgent"; Flags: runhidden waituntilterminated
Filename: "sc.exe"; Parameters: "delete PrintAgent"; Flags: runhidden waituntilterminated

[Code]
// Ensure service is stopped and removed before files are deleted during uninstall
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    Exec('sc.exe', 'stop PrintAgent', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec('sc.exe', 'delete PrintAgent', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
