; Inno Setup 6 script for SubTransJAV (D2026-0929-05 P2/07 定案)
; 版本号可由命令行覆盖：iscc /Dversion=1.2.3 packaging/setup.iss
; [Files] 源路径相对本脚本：../Temp/pyinstaller_dist/SubTransJAV/*，
;         与 CI 中 `pyinstaller --distpath Temp/pyinstaller_dist` 的产物对齐。
; 词典去捆绑（D3，D2026-1001）：单安装器单产物，不再捆日语词典
;   （system.dic ~208MB）——语法提示运行时自动降级，词典经 GUI 引擎页 /
;   CLI --dict-download 按需下载；可选 /Dsuffix 追加到安装器文件名。

#define MyAppName "SubTransJAV"
#ifndef version
#define version "0.0.0-dev"
#endif
#ifndef suffix
#define suffix ""
#endif
#define MyAppExeName "SubTransJAV.exe"

[Setup]
; AppId 固定 GUID：卸载/升级识别口径，永不变更
AppId={{8F3A5C1E-6B2D-4E9A-9C47-1D0B5A7E2F31}
AppName={#MyAppName}
AppVersion={#version}
DefaultDirName={autopf}\SubTransJAV
DefaultGroupName={#MyAppName}
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
OutputDir=..\Temp\innoinstall
OutputBaseFilename=SubTransJAV-setup-{#version}{#suffix}
PrivilegesRequired=admin
DisableProgramGroupPage=yes

[Languages]
; 简中语言文件随仓库分发（choco innosetup 不含 Unofficial 语言包），
; 相对路径按 .iss 所在目录解析 → packaging/ChineseSimplified.isl
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Types]
Name: full; Description: 标准安装

[Files]
; onedir 全量递归打包（含 _internal）；Excludes 作双保险——spec 已无条件剔除词典数据（D3 去捆绑口径）
Source: "..\Temp\pyinstaller_dist\SubTransJAV\*"; DestDir: "{app}"; Excludes: "system.dic"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

; D2026-0929-07 守卫：用户数据在 %LOCALAPPDATA%\SubTransJAV，
; 卸载永不删除任何用户数据。[UninstallDelete] 显式留空即默认不清理；
; 若未来需清理，只允许清理 {app} 内由安装器写入的临时件，绝不触及 LOCALAPPDATA。
[UninstallDelete]

[Code]
// WebView2 Runtime 检测：与 main.py 运行时探测同 GUID 口径
// {F3017226-FE2A-4295-8BDF-00C3A9A7E4C5} = WebView2 Evergreen Runtime
const
  WebView2Guid = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2DlUrl = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';

function WebView2Installed(): Boolean;
begin
  Result :=
    RegKeyExists(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + WebView2Guid) or
    RegKeyExists(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WebView2Guid);
end;

function InitializeSetup(): Boolean;
var
  RC: Integer;
begin
  Result := True;
  if not WebView2Installed() then
  begin
    if MsgBox(
        '检测到系统未安装 Microsoft WebView2 Runtime（SubTransJAV 界面运行所必需）。' + #13#10 +
        '是否打开官方下载页面安装后再继续？', mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open', WebView2DlUrl, '', '', SW_SHOW, ewNoWait, RC);
    end;
    // 不阻断安装：允许先装应用，运行时 main.py 会再次探测并提示
  end;
end;
