#define AppName "Agent-Notify"
#define AppVersion "1.0.2"
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
OutputBaseFilename=Agent-Notify-Setup-v1.0.2
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
Filename: "{app}\Agent-Notify.exe"; Parameters: "--onboarding"; Description: "运行 Agent-Notify 首次配置向导"; Flags: postinstall nowait skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{app}\Agent-Notify.exe"; Parameters: "--stop-tray --disable-autostart --remove-hooks --silent --home ""{code:GetConfiguredHome}"""; Flags: runhidden waituntilterminated; RunOnceId: "RemoveAgentNotify"

[Code]
var
  DeleteUserData: Boolean;

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
    Sleep(2000);
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

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    if UninstallSilent then
      DeleteUserData := False
    else
      DeleteUserData :=
        MsgBox(
          '是否同时删除 Agent-Notify 的用户配置、日志和迁移备份？' +
          Chr(13) + Chr(10) +
          '选择“否”可在以后重新安装时继续使用当前配置。',
          mbConfirmation,
          MB_YESNO or MB_DEFBUTTON1
        ) = IDYES;
  end;
  if (CurUninstallStep = usPostUninstall) and DeleteUserData then
    DelTree(
      ExpandConstant('{userappdata}\Agent-Notify'),
      True,
      True,
      True
    );
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then
  begin
    WizardForm.FinishedLabel.Caption :=
      'Agent-Notify v1.0.2 已安装。' + #13 + #10 +
      '点击“完成”后会打开首次配置向导，可按需跳过任意渠道。' + #13 + #10 +
      '以后可双击 Agent-Notify.exe 或使用开始菜单修改设置。';
  end;
end;
