; installer/setup.iss
#define AppName "MeadowLark"
#define AppExe  "MeadowLark.exe"

[Setup]
; AppId matches the AppName Inno used implicitly before this was set — this means
; existing installs are detected and upgraded in-place with no migration code needed.
AppId=MeadowLark
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=TheGene
DefaultDirName={autopf}\MeadowLark
DefaultGroupName={#AppName}
OutputDir=..\installer_output
OutputBaseFilename=MeadowLark-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\MeadowLark\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";       Filename: "{app}\{#AppExe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Add app directory to user PATH so ffmpeg.exe is found by shutil.which()
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsAddPath(ExpandConstant('{app}'))

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', OrigPath)
  then begin Result := True; exit; end;
  Result := Pos(';' + Uppercase(Param) + ';',
                ';' + Uppercase(OrigPath) + ';') = 0;
end;
