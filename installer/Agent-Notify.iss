#define AppName "Agent-Notify"
#define AppVersion "1.0.0"
#define Publisher "ancespio"

[Setup]
AppId={{3D8A5962-28DE-4FA9-93D6-86A2A66F9B2B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#Publisher}
DefaultDirName={autopf}\Agent-Notify
DefaultGroupName=Agent-Notify
DisableProgramGroupPage=yes
OutputDir=..\dist-installer
OutputBaseFilename=Agent-Notify-Setup-v1.0.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\Agent-Notify.exe
SetupIconFile=..\build\agent-notify.ico
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoCompany={#Publisher}
SetupLogging=yes

[Files]
Source: "..\dist\Agent-Notify.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\Agent-Notify 设置"; Filename: "{app}\Agent-Notify.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\Agent-Notify.exe"; Description: "打开 Agent-Notify 设置"; Flags: postinstall nowait skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{app}\Agent-Notify.exe"; Parameters: "--stop-tray --disable-autostart --remove-hooks --silent --home ""{code:GetConfiguredHome}"""; Flags: runhidden waituntilterminated; RunOnceId: "RemoveAgentNotify"

[Code]
function GetConfiguredHome(Param: String): String;
var
  HomeValue: AnsiString;
begin
  HomeValue := '';
  if not LoadStringFromFile(
    ExpandConstant('{app}\install-home.txt'),
    HomeValue
  ) then
    Result := ExpandConstant('{%USERPROFILE}');
  if HomeValue <> '' then
    Result := String(HomeValue);
  Result := Trim(Result);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  if FileExists(ExpandConstant('{app}\Agent-Notify.exe')) then
    Exec(
      ExpandConstant('{app}\Agent-Notify.exe'),
      '--stop-tray --silent',
      '',
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
    );
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  HomePath: String;
begin
  if CurStep <> ssPostInstall then
    Exit;
  HomePath := ExpandConstant('{param:AGENTHOME|}');
  if HomePath = '' then
    HomePath := ExpandConstant('{%USERPROFILE}');
  SaveStringToFile(
    ExpandConstant('{app}\install-home.txt'),
    HomePath,
    False
  );
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then
  begin
    WizardForm.FinishedLabel.Caption :=
      'Agent-Notify v1.0.0 已安装。' + #13 + #10 +
      '点击“完成”后会打开设置窗口，请配置通知渠道与 Agent Hook。' + #13 + #10 +
      '以后可双击 Agent-Notify.exe 或使用开始菜单修改设置。';
  end;
end;
