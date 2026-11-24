[Setup]
AppId={{D32E4A64-9A42-4E8D-AC79-1AFD64FB1A10}
AppName=Nexa AI
AppVersion=1.1.0
AppPublisher=Nexa AI
DefaultDirName={localappdata}\Programs\NexaAI
DefaultGroupName=Nexa AI
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\output
OutputBaseFilename=NexaAI-Setup-1.1.0-Windows-x64
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\NexaAI.exe
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
DiskSpanning=no
VersionInfoVersion=1.1.0.0
VersionInfoProductName=Nexa AI
VersionInfoDescription=Offline local AI desktop assistant

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\NexaAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\THIRD-PARTY-NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Nexa AI"; Filename: "{app}\NexaAI.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Nexa AI"; Filename: "{app}\NexaAI.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\NexaAI.exe"; Description: "Launch Nexa AI"; Flags: nowait postinstall skipifsilent
