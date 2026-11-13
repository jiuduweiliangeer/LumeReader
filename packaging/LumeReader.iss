#ifndef AppVersion
#define AppVersion "1.1.1"
#endif
#define AppName "轻阅 Lume Reader"
#ifndef SourceDir
#define SourceDir "..\dist\LumeReader"
#endif
#ifndef OutputBaseName
#define OutputBaseName "LumeReader-" + AppVersion + "-Setup-x64"
#endif
[Setup]
AppId={{8EC24CA1-E9B6-4EF5-A7A2-21D281C95FB5}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Lume Reader contributors
DefaultDirName={localappdata}\Programs\LumeReader
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\release
OutputBaseFilename={#OutputBaseName}
SetupIconFile=..\lume\assets\lume.ico
UninstallDisplayIcon={app}\LumeReader.exe
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Lume Reader Setup
VersionInfoCopyright=Copyright (C) 2026 Lume Reader contributors
[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Default.isl,ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\LumeReader.exe"; WorkingDir: "{app}"
Name: "{group}\Uninstall Lume Reader"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\LumeReader.exe"; WorkingDir: "{app}"; Tasks: desktopicon
[Run]
Filename: "{app}\LumeReader.exe"; Description: "{cm:LaunchProgram,Lume Reader}"; Flags: nowait postinstall skipifsilent
