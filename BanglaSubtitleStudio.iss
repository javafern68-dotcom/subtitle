#define MyAppName "Bangla Subtitle Studio"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Bangla Subtitle Studio"
#define MyAppExeName "Bangla Subtitle Studio.exe"

[Setup]
AppId={{7A926CF8-4A2F-485B-9FA4-A56D69B8D7C5}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=installer
OutputBaseFilename=Bangla_Subtitle_Studio_Setup_V1
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Automatic Bangla subtitle, logo and color editor
VersionInfoProductName={#MyAppName}

[Files]
Source: "dist\Bangla Subtitle Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Desktop shortcut তৈরি করুন"; GroupDescription: "Shortcuts:"; Flags: checkedonce

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} চালু করুন"; Flags: nowait postinstall skipifsilent
