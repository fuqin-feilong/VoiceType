; VoiceType 安装包脚本（Inno Setup 6）
; 编译：ISCC.exe packaging\installer.iss

#define MyAppName "VoiceType"
#ifndef MyAppVersion
  #define MyAppVersion "0.4.0"
#endif
#define MyAppPublisher "VoiceType"
#define MyAppExeName "VoiceType.exe"

[Setup]
AppId={{9C3E2B41-7A55-4F0E-9B7A-1D2C3E4F5A60}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\VoiceType
DefaultGroupName=VoiceType
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=VoiceType-{#MyAppVersion}-setup
SetupIconFile=..\src\voicetype\assets\voicetype.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"
Name: "autostart"; Description: "Start VoiceType when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "..\dist\VoiceType\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\VoiceType"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall VoiceType"; Filename: "{uninstallexe}"
Name: "{autodesktop}\VoiceType"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "VoiceType"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch VoiceType"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c taskkill /IM {#MyAppExeName} /F"; Flags: runhidden; RunOnceId: "KillApp"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
