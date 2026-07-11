#define MyAppName "Primelock GIS"
#define MyAppPublisher "Primelock GIS coursework project"
#define MyAppExeName "PrimelockGIS.exe"

#ifndef MyAppVersion
  #error MyAppVersion must be supplied by tools\build_windows_installer.py
#endif
#ifndef MyAppVersionQuad
  #error MyAppVersionQuad must be supplied by tools\build_windows_installer.py
#endif
#ifndef RuntimeRoot
  #error RuntimeRoot must point to the validated portable runtime tree
#endif
#ifndef ReleaseDir
  #error ReleaseDir must be supplied by tools\build_windows_installer.py
#endif
#ifndef InstallerReadme
  #error InstallerReadme must be supplied by tools\build_windows_installer.py
#endif
#ifndef AppIcon
  #error AppIcon must be supplied by tools\build_windows_installer.py
#endif

[Setup]
AppId={{B2C1B6A0-5B6D-4B0B-9DD5-13B4BE0F512D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion={#MyAppVersionQuad}
VersionInfoProductVersion={#MyAppVersionQuad}
VersionInfoDescription=Offline per-user installer for Primelock GIS
DefaultDirName={localappdata}\Programs\Primelock GIS
DefaultGroupName=Primelock GIS
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.10240
OutputDir={#ReleaseDir}
OutputBaseFilename=PrimelockGIS-Windows-x64-Setup-v{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
CloseApplications=yes
RestartApplications=no
Uninstallable=yes
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\app\PrimelockGIS-v{#MyAppVersion}.ico
InfoBeforeFile={#InstallerReadme}
SetupIconFile={#AppIcon}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopiconenglish"; Description: "Create an &English desktop shortcut / 创建英文版桌面快捷方式"; GroupDescription: "Additional shortcuts / 附加快捷方式："; Flags: unchecked
Name: "desktopiconchinese"; Description: "Create a &Chinese desktop shortcut / 创建中文版桌面快捷方式"; GroupDescription: "Additional shortcuts / 附加快捷方式："; Flags: unchecked

[Files]
Source: "{#RuntimeRoot}\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RuntimeRoot}\START_PRIMELOCK_GIS.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RuntimeRoot}\启动_PRIMELOCK_GIS_中文版.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RuntimeRoot}\README_FIRST_先读我.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RuntimeRoot}\先读我_中文版.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RuntimeRoot}\THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RuntimeRoot}\VERSION.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Primelock GIS (English)"; Filename: "{app}\app\{#MyAppExeName}"; Parameters: "launch --language en"; WorkingDir: "{app}\app"; IconFilename: "{app}\app\PrimelockGIS-v{#MyAppVersion}.ico"; IconIndex: 0; Comment: "Open the Primelock GIS viewer and support panel in English"
Name: "{group}\Primelock GIS（中文）"; Filename: "{app}\app\{#MyAppExeName}"; Parameters: "launch --language zh-CN"; WorkingDir: "{app}\app"; IconFilename: "{app}\app\PrimelockGIS-v{#MyAppVersion}.ico"; IconIndex: 0; Comment: "以中文打开 Primelock GIS 地图查看器和支持面板"
Name: "{group}\Uninstall Primelock GIS"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Primelock GIS (English)"; Filename: "{app}\app\{#MyAppExeName}"; Parameters: "launch --language en"; WorkingDir: "{app}\app"; IconFilename: "{app}\app\PrimelockGIS-v{#MyAppVersion}.ico"; IconIndex: 0; Comment: "Open the Primelock GIS viewer and support panel in English"; Tasks: desktopiconenglish
Name: "{autodesktop}\Primelock GIS（中文）"; Filename: "{app}\app\{#MyAppExeName}"; Parameters: "launch --language zh-CN"; WorkingDir: "{app}\app"; IconFilename: "{app}\app\PrimelockGIS-v{#MyAppVersion}.ico"; IconIndex: 0; Comment: "以中文打开 Primelock GIS 地图查看器和支持面板"; Tasks: desktopiconchinese

[Run]
Filename: "{app}\app\{#MyAppExeName}"; Parameters: "launch --language en"; WorkingDir: "{app}\app"; Description: "Launch Primelock GIS in English / 启动英文版 Primelock GIS"; Flags: nowait postinstall skipifsilent
