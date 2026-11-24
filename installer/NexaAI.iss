[Setup]
AppId={{D32E4A64-9A42-4E8D-AC79-1AFD64FB1A10}
AppName=Nexa AI
AppVersion=1.4.0
AppPublisher=NTech
DefaultDirName={localappdata}\Programs\NexaAI
DefaultGroupName=Nexa AI
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\output
OutputBaseFilename=NexaAI-Setup-1.4.0-Windows-x64
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\nexa-ai.ico
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\NexaAI.exe
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
DiskSpanning=no
VersionInfoVersion=1.4.0.0
VersionInfoProductName=Nexa AI
VersionInfoDescription=Single-model offline Qwen3 4B AI, voice and n8n desktop assistant

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"


[Files]
Source: "..\dist\NexaAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\THIRD-PARTY-NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\nexa-ai.ico"; DestDir: "{app}\assets"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Nexa AI"; Filename: "{app}\NexaAI.exe"; IconFilename: "{app}\assets\nexa-ai.ico"; WorkingDir: "{app}"
Name: "{autodesktop}\Nexa AI"; Filename: "{app}\NexaAI.exe"; IconFilename: "{app}\assets\nexa-ai.ico"; WorkingDir: "{app}"

[Run]
Filename: "{app}\NexaAI.exe"; Description: "Launch Nexa AI"; Flags: nowait postinstall skipifsilent
