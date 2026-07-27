; Print Agent Inno Setup Installer Script
;
; Build with Inno Setup 6+:
;   iscc installer/print_agent_installer.iss
;
; Prerequisites:
;   1. Run PyInstaller to build both exes first:
;      pyinstaller build/service.spec
;      pyinstaller build/config_gui.spec
;   2. Copy the built exes to dist/ (PyInstaller default output)

#define MyAppName "Print Agent"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Print Agent"
#define MyAppExeName "print_agent_config.exe"
#define MyServiceExeName "print_agent_service.exe"

[Setup]
AppId={{B1E2F3A4-5678-9ABC-DEF0-123456789ABC}
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
; Main executables
Source: "..\dist\{#MyServiceExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Default config file (only installed if none exists)
Source: "..\config.example.yaml"; DestDir: "{app}"; DestName: "config.yaml"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\Configure Print Agent"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall Print Agent"; Filename: "{uninstallexe}"

[Run]
; Install and start the Windows service
Filename: "{app}\{#MyServiceExeName}"; Parameters: "install"; StatusMsg: "Installing Print Agent service..."; Flags: runhidden waituntilterminated
Filename: "{app}\{#MyServiceExeName}"; Parameters: "start"; StatusMsg: "Starting Print Agent service..."; Flags: runhidden waituntilterminated

; Optionally launch the config GUI after install
Filename: "{app}\{#MyAppExeName}"; Description: "Configure Print Agent"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Stop and remove the service before uninstalling
Filename: "{app}\{#MyServiceExeName}"; Parameters: "stop"; Flags: runhidden waituntilterminated
Filename: "{app}\{#MyServiceExeName}"; Parameters: "remove"; Flags: runhidden waituntilterminated

[Code]
// Ensure service is stopped before files are deleted during uninstall
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    // Try to stop and remove the service (silently ignore errors if already removed)
    Exec(ExpandConstant('{app}\{#MyServiceExeName}'), 'stop', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(ExpandConstant('{app}\{#MyServiceExeName}'), 'remove', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
