; Inno Setup 6 script for SubTransJAV (D2026-0929-05 P2/07 定案)
; 版本号可由命令行覆盖：iscc /Dversion=1.2.3 packaging/setup.iss
; [Files] 源路径相对本脚本：../Temp/pyinstaller_dist/SubTransJAV/*，
;         与 CI 中 `pyinstaller --distpath Temp/pyinstaller_dist` 的产物对齐。
; 词典组件化（2.0.0b0）：完整版 iscc /Ddict_src=<system.dic 所在目录>
;   （默认指向 full 构建 dist 内的真实词典目录）；lite 版安装器
;   /Ddict_src 指向空目录 + /Dsuffix=-lite（词典条目挂 Components: full，
;   lite 组件不装 → 精简安装不含 system.dic，语法提示运行时自动降级）。
; 可选 /Dsuffix=-lite 追加到安装器文件名以区分两份产物。

#define MyAppName "SubTransJAV"
#ifndef version
#define version "0.0.0-dev"
#endif
#ifndef suffix
#define suffix ""
#endif
#ifndef dict_src
; 默认 = full 构建 dist 内真实词典目录（CI 传参覆盖）
#define dict_src "..\Temp\pyinstaller_dist\SubTransJAV\_internal\sudachidict_core\resources"
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
Name: full; Description: 完整安装（含日语语法词典，约 217MB）
Name: compact; Description: 标准安装（含日语语法词典）
Name: custom; Description: 自定义安装（可选是否含日语语法词典）

[Components]
Name: "full"; Description: "完整安装（含日语语法词典，约 217MB）"; Types: full compact
Name: "lite"; Description: "精简安装（不含词典，语法提示不可用）"; Types: custom

[Files]
; onedir 全量递归打包（含 _internal）；system.dic 从通用条目剔除，
; 由下方词典条目按组件（Components: full）单独落位。
Source: "..\Temp\pyinstaller_dist\SubTransJAV\*"; DestDir: "{app}"; Excludes: "system.dic"; Flags: recursesubdirs createallsubdirs ignoreversion
; 日语语法词典（~208MB）：仅完整组件安装；lite 安装器以 /Ddict_src 指向空目录
Source: "{#dict_src}\system.dic"; DestDir: "{app}\_internal\sudachidict_core\resources"; Components: full; Flags: ignoreversion skipifsourcedoesntexist

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
