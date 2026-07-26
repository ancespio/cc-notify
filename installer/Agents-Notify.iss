#define AppName "Agents-Notify"
#define AppVersion "1.0.3"
#define Publisher "ancespio"

[Setup]
AppId={{3D8A5962-28DE-4FA9-93D6-86A2A66F9B2B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#Publisher}
DefaultDirName={autopf}\Agents-Notify
DefaultGroupName=Agents-Notify
DisableProgramGroupPage=yes
UsePreviousGroup=no
OutputDir=..\dist-installer
OutputBaseFilename=Agents-Notify-Setup-v1.0.3
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\Agents-Notify.exe
SetupIconFile=..\build\agents-notify.ico
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoCompany={#Publisher}
SetupLogging=yes

[Files]
Source: "..\dist\Agents-Notify.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[InstallDelete]
Type: files; Name: "{app}\Agent-Notify.exe"
Type: filesandordirs; Name: "{commonprograms}\Agent-Notify"

[Icons]
Name: "{group}\Agents-Notify 设置"; Filename: "{app}\Agents-Notify.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\Agents-Notify.exe"; Parameters: "--onboarding"; Description: "运行 Agents-Notify 首次配置向导"; Flags: postinstall nowait skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{app}\Agents-Notify.exe"; Parameters: "--stop-tray --disable-autostart --remove-hooks --silent --home ""{code:GetConfiguredHome}"""; Flags: runhidden waituntilterminated; RunOnceId: "RemoveAgentNotify"

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
  if FileExists(ExpandConstant('{app}\Agents-Notify.exe')) then
  begin
    Exec(
      ExpandConstant('{app}\Agents-Notify.exe'),
      '--stop-tray --silent',
      '',
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
    );
  end
  else if FileExists(ExpandConstant('{app}\Agent-Notify.exe')) then
  begin
    Exec(
      ExpandConstant('{app}\Agent-Notify.exe'),
      '--stop-tray --silent',
      '',
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
    );
  end;
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
          '是否同时删除 Agents-Notify 的用户配置、日志和迁移备份？' +
          Chr(13) + Chr(10) +
          '选择“否”可在以后重新安装时继续使用当前配置。',
          mbConfirmation,
          MB_YESNO or MB_DEFBUTTON1
        ) = IDYES;
  end;
  if (CurUninstallStep = usPostUninstall) and DeleteUserData then
  begin
    DelTree(
      ExpandConstant('{userappdata}\Agents-Notify'),
      True,
      True,
      True
    );
    DelTree(
      ExpandConstant('{userappdata}\Agent-Notify'),
      True,
      True,
      True
    );
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then
  begin
    WizardForm.FinishedLabel.Caption :=
      'Agents-Notify v1.0.3 已安装。' + #13 + #10 +
      '点击“完成”后会打开首次配置向导，可按需跳过任意渠道。' + #13 + #10 +
      '以后可双击 Agents-Notify.exe 或使用开始菜单修改设置。';
  end;
end;
