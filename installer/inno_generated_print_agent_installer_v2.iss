; Print Agent Inno Setup Installer Script
;
; Installs the config GUI, service exe, and registers the Windows service.

#define MyAppName "Print Agent"
#define MyAppVersion "1.0.2"
#define MyAppPublisher "Roman Njoroge"
#define MyAppExeName "print_agent_config.exe"
#define MyServiceExeName "print_agent_service.exe"

[Setup]
AppId={{CABFEEBF-8945-4CD6-892C-0E7F1BC0D63A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
OutputDir=C:\Odoo\module_local_scripts\print_agent_packaging\installer_output
OutputBaseFilename=PrintAgentSetup
SolidCompression=yes
WizardStyle=modern dynamic
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Config GUI exe (PyInstaller-built)
Source: "C:\Odoo\module_local_scripts\print_agent_packaging\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Service exe (PyInstaller-built, self-contained — no Python needed)
Source: "C:\Odoo\module_local_scripts\print_agent_packaging\dist\{#MyServiceExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Default config file (only installed if none exists)
Source: "C:\Odoo\module_local_scripts\print_agent_packaging\config.example.yaml"; DestDir: "{app}"; DestName: "config.yaml"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Register the frozen exe as the service binary via sc.exe create
Filename: "{app}\{#MyServiceExeName}"; Parameters: "install"; StatusMsg: "Installing Print Agent service..."; Flags: runhidden waituntilterminated

; Start the service
Filename: "sc.exe"; Parameters: "start PrintAgent"; StatusMsg: "Starting Print Agent service..."; Flags: runhidden waituntilterminated

; Optionally launch the config GUI after install
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Stop and remove the service before uninstalling
Filename: "sc.exe"; Parameters: "stop PrintAgent"; Flags: runhidden waituntilterminated
Filename: "sc.exe"; Parameters: "delete PrintAgent"; Flags: runhidden waituntilterminated

[Code]
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
