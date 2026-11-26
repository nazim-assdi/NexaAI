[Setup]
LicenseFile=..\licenses\QWEN-RESEARCH-LICENSE.txt
AppId={{D32E4A64-9A42-4E8D-AC79-1AFD64FB1A10}
AppName=Nexa AI
AppVersion=2.1.1
AppPublisher=NTech
DefaultDirName={localappdata}\Programs\NexaAI
DefaultGroupName=Nexa AI
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\output
OutputBaseFilename=NexaAI-Setup-2.1.1-Windows-x64
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
VersionInfoVersion=2.1.1.0
VersionInfoProductName=Nexa AI
VersionInfoDescription=Bundled Ollama + Qwen2.5-Coder 3B and Gemini Assistant

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\NexaAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\build-assets\ollama\*"; DestDir: "{app}\runtime\ollama"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\licenses\QWEN-RESEARCH-LICENSE.txt"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "..\licenses\QWEN-NOTICE.txt"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "..\THIRD-PARTY-NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\nexa-ai.ico"; DestDir: "{app}\assets"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Nexa AI"; Filename: "{app}\NexaAI.exe"; IconFilename: "{app}\assets\nexa-ai.ico"; WorkingDir: "{app}"
Name: "{autodesktop}\Nexa AI"; Filename: "{app}\NexaAI.exe"; IconFilename: "{app}\assets\nexa-ai.ico"; WorkingDir: "{app}"

[Run]
Filename: "{app}\NexaAI.exe"; Description: "Launch Nexa AI"; Flags: nowait postinstall skipifsilent
