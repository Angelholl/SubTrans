; Inno Setup 6 script for SubTransJAV (D2026-0929-05 P2/07 定案)
; 版本号可由命令行覆盖：iscc /Dversion=1.2.3 packaging/setup.iss
; [Files] 源路径相对本脚本：../Temp/pyinstaller_dist/SubTransJAV/*，
;         与 CI 中 `pyinstaller --distpath Temp/pyinstaller_dist` 的产物对齐。
; 词典去捆绑（D3，D2026-1001）：单安装器单产物，不再捆日语词典
;   （system.dic ~208MB）——语法提示运行时自动降级，词典经 GUI 引擎页 /
;   CLI --dict-download 按需下载；可选 /Dsuffix 追加到安装器文件名。

#define MyAppName "SubTrans"
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
; 安装器自身图标（D2026-1004-01）：相对本 .iss 所在目录解析
SetupIconFile=..\subtransjav\webview_gui\assets\icon.ico
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
OutputDir=..\Temp\innoinstall
OutputBaseFilename=SubTrans-setup-{#version}{#suffix}
PrivilegesRequired=admin
DisableProgramGroupPage=yes
; 关停运行中实例防文件占用，D2026-1003-01 批A
CloseApplications=yes

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

; 守卫反转记录：D2026-0929-07 原守卫（卸载永不删除任何用户数据）经
; D2026-1003-01 拍板⑥追认反转：数据删除仅经 InitializeUninstall 一问制
; （默认保留 + 锚点硬门槛 + 量级清单），[UninstallDelete] 保持空段仍绝不静默清理。
; 决策文档所写 settings.json 系误记，实盘锚点以 config/user_settings.json
; 与 config/refine_stage_settings.json 为准。
[UninstallDelete]

[Code]
// WebView2 Runtime 检测：与 main.py 运行时探测同 GUID 口径
// {F3017226-FE2A-4295-8BDF-00C3A9A7E4C5} = WebView2 Evergreen Runtime
const
  WebView2Guid = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2DlUrl = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';

  // 与 [Setup] AppId 同源（永不变更）；用于拼接卸载注册表键 {AppId}_is1
  AppIdStr = '{8F3A5C1E-6B2D-4E9A-9C47-1D0B5A7E2F31}';

  // 卸载注册表根键（Inno 6 在其后追加 {AppId}_is1）
  UninstSubKey = 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\';

function WebView2Installed(): Boolean;
begin
  Result :=
    RegKeyExists(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + WebView2Guid) or
    RegKeyExists(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WebView2Guid);
end;

// ---------------------------------------------------------------------------
// 批A（D2026-1003-01）安装器生命周期：R1 升级检测 + R2 卸载一问制
// ---------------------------------------------------------------------------

// 批A 共用：读已装信息（卸载注册表 {AppId}_is1 的 DisplayVersion/InstallLocation）。
// HKLM 优先 HKCU 兜底；loc 剥首尾引号与尾反斜杠；未装则两值均返回空串。
procedure ReadInstalledInfo(var ver: String; var loc: String);
var
  key: String;
begin
  ver := '';
  loc := '';
  key := UninstSubKey + AppIdStr + '_is1';
  // 64 位安装模式下 HKLM 即 64 位视图，Inno 的卸载键写在该视图
  if not RegQueryStringValue(HKLM, key, 'DisplayVersion', ver) then
    RegQueryStringValue(HKCU, key, 'DisplayVersion', ver);
  if not RegQueryStringValue(HKLM, key, 'InstallLocation', loc) then
    RegQueryStringValue(HKCU, key, 'InstallLocation', loc);
  // loc 剥首尾引号
  if (Length(loc) >= 2) and (loc[1] = '"') and (loc[Length(loc)] = '"') then
    loc := Copy(loc, 2, Length(loc) - 2);
  // 剥尾反斜杠（顺带容忍正斜杠写法）
  while (Length(loc) > 0) and
        ((loc[Length(loc)] = '\') or (loc[Length(loc)] = '/')) do
    loc := Copy(loc, 1, Length(loc) - 1);
end;

function _IsDigits(const s: String): Boolean;
var
  i: Integer;
begin
  Result := Length(s) > 0;
  for i := 1 to Length(s) do
    if (s[i] < '0') or (s[i] > '9') then
    begin
      Result := False;
      Break;
    end;
end;

function _NextSeg(var s: String): String;
var
  p: Integer;
begin
  p := Pos('.', s);
  if p = 0 then
  begin
    Result := s;
    s := '';
  end
  else
  begin
    Result := Copy(s, 1, p - 1);
    s := Copy(s, p + 1, MaxInt);
  end;
end;

// 版本点分段比较：全数字段按数值、否则按字符串；返回 -1/0/1（old 对 new）。
// 缺段按 '0' 处理（'1.0' 与 '1.0.0' 等价）。
function CompareVersion(const oldV, newV: String): Integer;
var
  sa, sb, ca, cb: String;
begin
  sa := oldV;
  sb := newV;
  Result := 0;
  while (Result = 0) and ((sa <> '') or (sb <> '')) do
  begin
    ca := _NextSeg(sa);
    cb := _NextSeg(sb);
    if ca = '' then ca := '0';
    if cb = '' then cb := '0';
    if _IsDigits(ca) and _IsDigits(cb) then
    begin
      if StrToInt64(ca) < StrToInt64(cb) then
        Result := -1
      else if StrToInt64(ca) > StrToInt64(cb) then
        Result := 1;
    end
    else
    begin
      if Lowercase(ca) < Lowercase(cb) then
        Result := -1
      else if Lowercase(ca) > Lowercase(cb) then
        Result := 1;
    end;
  end;
end;

// .data-root 指针由 paths.py 以 UTF-8 落盘（read_text(encoding='utf-8')），
// LoadStringFromFile 在 Unicode Inno 6 中返回原始字节的 AnsiString，
// 直接按 ANSI 码页强转会在中文路径上乱码，故手工按 UTF-8 解码
// （1-3 字节序列覆盖路径常见字符；4 字节序列以 '?' 占位）。
function Utf8BytesToStr(const raw: AnsiString): String;
var
  i, n, b, cp: Integer;
begin
  Result := '';
  n := Length(raw);
  i := 1;
  while i <= n do
  begin
    b := Ord(raw[i]);
    if b < $80 then
    begin
      Result := Result + Chr(b);
      i := i + 1;
    end
    else if (b and $E0) = $C0 then
    begin
      if (i + 1 <= n) and ((Ord(raw[i + 1]) and $C0) = $80) then
      begin
        cp := ((b and $1F) shl 6) or (Ord(raw[i + 1]) and $3F);
        Result := Result + Chr(cp);
        i := i + 2;
      end
      else
      begin
        Result := Result + '?';
        i := i + 1;
      end;
    end
    else if (b and $F0) = $E0 then
    begin
      if (i + 2 <= n) and ((Ord(raw[i + 1]) and $C0) = $80) and
         ((Ord(raw[i + 2]) and $C0) = $80) then
      begin
        cp := ((b and $0F) shl 12) or ((Ord(raw[i + 1]) and $3F) shl 6) or
              (Ord(raw[i + 2]) and $3F);
        Result := Result + Chr(cp);
        i := i + 3;
      end
      else
      begin
        Result := Result + '?';
        i := i + 1;
      end;
    end
    else
    begin
      Result := Result + '?';
      i := i + 1;
    end;
  end;
end;

// R2 数据根四级解析（与 subtransjav/paths.py data_root() 对齐，仅安装器口径）：
// 1) 环境变量 SUBTRANSJAV_DATA_ROOT（非空才生效）；
// 2) 指针文件 .data-root（frozen 下固定在 exe 同目录 = {app}，单行绝对路径）；
// 3) frozen 默认 %LOCALAPPDATA%\SubTransJAV；LOCALAPPDATA 缺失回退家目录
//    （paths.py 同级写法 = os.environ.get('LOCALAPPDATA') or Path.home()，
//    此处 Path.home() 对应 %USERPROFILE%）。
function ResolveDataRoot(const appLoc: String; var srcLabel: String): String;
var
  env, content: String;
  raw: AnsiString;
begin
  Result := '';
  srcLabel := '';
  // 1) 环境变量
  env := Trim(GetEnv('SUBTRANSJAV_DATA_ROOT'));
  if env <> '' then
  begin
    Result := env;
    srcLabel := '环境变量';
    Exit;
  end;
  // 2) 数据目录指针 .data-root（exe 同目录；单行 trim 后须为绝对路径）
  if appLoc <> '' then
  begin
    if LoadStringFromFile(appLoc + '\.data-root', raw) then
    begin
      content := Trim(Utf8BytesToStr(raw));
      if (content <> '') and
         (((Length(content) >= 2) and (content[2] = ':')) or
          (content[1] = '\') or (content[1] = '/')) then
      begin
        Result := content;
        srcLabel := '数据目录指针';
        Exit;
      end;
    end;
  end;
  // 3) 默认位置（LOCALAPPDATA 空则家目录回退，对齐 paths.py 第 3 级）
  env := GetEnv('LOCALAPPDATA');
  if env = '' then
    env := GetEnv('USERPROFILE');
  if env <> '' then
  begin
    Result := env + '\SubTransJAV';
    srcLabel := '默认位置';
  end;
end;

// 递归求目录字节数（内部实现）：深度上限 12 防 junction 死循环。
function _DirSizeBytesDeep(const dir: String; depth: Integer): Int64;
var
  FindRec: TFindRec;
begin
  Result := 0;
  if depth > 12 then
    Exit;
  if FindFirst(dir + '\*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
        begin
          // Inno 6 PascalScript 的 TFindRec：目录位=Attributes $10，大小=SizeHigh/SizeLow
          if (FindRec.Attributes and $10) <> 0 then
            Result := Result + _DirSizeBytesDeep(dir + '\' + FindRec.Name, depth + 1)
          else
            Result := Result + (Int64(FindRec.SizeHigh) shl 32) + Int64(FindRec.SizeLow);
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

function DirSizeBytes(const dir: String): Int64;
begin
  Result := _DirSizeBytesDeep(dir, 0);
end;

// B/KB/MB/GB 自适应一位小数
function HumanSize(const bytes: Int64): String;
var
  v: Extended;
  unitName: String;
begin
  v := bytes;
  unitName := 'B';
  if v >= 1024 then
  begin
    v := v / 1024;
    unitName := 'KB';
  end;
  if v >= 1024 then
  begin
    v := v / 1024;
    unitName := 'MB';
  end;
  if v >= 1024 then
  begin
    v := v / 1024;
    unitName := 'GB';
  end;
  Result := Format('%.1f %s', [v, unitName]);
end;

// 锚点硬门槛：9 锚与 subtransjav/data_migration.py 旧根白名单 + 运行时落盘
// 对齐（glossary_conflict_watch.json 实际位于 Temp/translation_memory/，
// 非 config\；config\templates 为角色卡/模板目录；user_dirs.json 为
// webview_gui/user_dirs.py 持久登记文件）。任一命中即视为存在用户数据。
function HasAnyAnchor(const root: String): Boolean;
begin
  Result :=
    FileOrDirExists(root + '\config\user_dirs.json') or
    FileOrDirExists(root + '\config\user_settings.json') or
    FileOrDirExists(root + '\config\refine_stage_settings.json') or
    FileOrDirExists(root + '\config\api_keys.bin') or
    FileOrDirExists(root + '\config\glossary.csv') or
    FileOrDirExists(root + '\config\glossary_learned.csv') or
    FileOrDirExists(root + '\config\templates') or
    FileOrDirExists(root + '\Temp\translation_memory\tm.db') or
    FileOrDirExists(root + '\Temp\translation_memory\glossary_conflict_watch.json');
end;

// 深度门槛：解析结果明显不该被 DelTree 的路径一律拒删。
// 覆盖：空串 / 盘符根（C: 与 C:\）/ %WINDIR% / %ProgramFiles%（大小写不敏感）/
// 与安装目录 {app} 同径（大小写不敏感）。
function IsUnsafeRoot(const root, appLoc: String): Boolean;
var
  lowRoot, lowLoc: String;
begin
  Result := True;
  if Trim(root) = '' then
    Exit;
  if (Length(root) <= 3) and (Length(root) >= 2) and (root[2] = ':') then
    Exit;
  lowRoot := Lowercase(root);
  if (lowRoot = Lowercase(GetEnv('WINDIR'))) or
     (lowRoot = Lowercase(GetEnv('ProgramFiles'))) then
    Exit;
  // 与 {app} 同径比较（大小写不敏感；双方剥尾反斜杠后比）
  lowLoc := Lowercase(appLoc);
  while (Length(lowRoot) > 0) and (lowRoot[Length(lowRoot)] = '\') do
    lowRoot := Copy(lowRoot, 1, Length(lowRoot) - 1);
  while (Length(lowLoc) > 0) and (lowLoc[Length(lowLoc)] = '\') do
    lowLoc := Copy(lowLoc, 1, Length(lowLoc) - 1);
  if (lowLoc <> '') and (lowRoot = lowLoc) then
    Exit;
  Result := False;
end;

var
  DataDelete: Boolean;       // InitializeUninstall 定，usPostUninstall 执行
  DataRoot, DataSrc: String; // 解析结果与来源标签

function InitializeSetup(): Boolean;
var
  RC: Integer;
  ver, loc, body: String;
begin
  Result := True;
  // 既有 WebView2 检测原样保留在最前（不阻断安装：运行时 main.py 会再次探测）
  if not WebView2Installed() then
  begin
    if MsgBox(
        '检测到系统未安装 Microsoft WebView2 Runtime（SubTrans 界面运行所必需）。' + #13#10 +
        '是否打开官方下载页面安装后再继续？', mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open', WebView2DlUrl, '', '', SW_SHOW, ewNoWait, RC);
    end;
  end;
  // R1 升级检测（D2026-1003-01 批A）：已装版本 vs 本次版本
  ReadInstalledInfo(ver, loc);
  if ver <> '' then
  begin
    // CompareVersion(old, new)：-1=升级 0=同版 1=降级，与消息语义对齐
    case CompareVersion(ver, '{#version}') of
      -1: body := '检测到已安装 SubTrans ' + ver + '（' + loc + '）。' +
                  '本次将原地更新到 {#version}。';
       0: body := '检测到已安装 SubTrans ' + ver + '（' + loc + '）。' +
                  '本次将重新安装/修复 {#version}。';
       1: body := '警告：本次将把 SubTrans 从 ' + ver +
                  ' 回退到较低版本 {#version}。';
    end;
    body := body + #13#10 + '本地数据（翻译记忆库/词典/设置/角色卡）完整保留。';
    if MsgBox(body, mbInformation, MB_OKCANCEL) = IDCANCEL then
      Result := False;
  end;
end;

// R2 卸载一问制（D2026-1003-01 批A）：默认保留 + 锚点硬门槛 + 量级清单
function InitializeUninstall(): Boolean;
var
  ver, loc, root, body: String;
begin
  Result := True;
  ReadInstalledInfo(ver, loc);
  if loc = '' then
    loc := ExpandConstant('{app}');
  root := ResolveDataRoot(loc, DataSrc);
  DataRoot := root;
  // ① 深度门槛：解析结果异常（盘符根/系统目录/安装目录等）一律不删
  if IsUnsafeRoot(root, loc) then
  begin
    DataDelete := False;
    MsgBox('数据目录解析结果异常（' + root + '），为安全起见不执行任何删除；' +
           '如需清理请手动核查。', mbInformation, MB_OK);
    Exit;
  end;
  // ② 锚点预检：无任何用户数据锚点 → 按保留处理（防误删可重下载资源目录）
  if not HasAnyAnchor(root) then
  begin
    DataDelete := False;
    MsgBox('未在 ' + root + ' 识别到本地数据文件，本次卸载按保留数据处理。' + #13#10 +
           '若曾用环境变量 SUBTRANSJAV_DATA_ROOT 自定义数据目录，请自行核查实际位置；' +
           '仅含模型/词典等可重新下载资源的目录亦会拒删，可手动清理。',
           mbInformation, MB_OK);
    Exit;
  end;
  // ③ 一问制（锚点命中才到此）：默认按钮=否（保留数据）
  body := '是否同时删除本地数据？【推荐保留】（选「否」保留数据）' + #13#10 +
          '数据目录：' + root + '（来源：' + DataSrc + '）' + #13#10 + #13#10 +
          '将删除的内容与量级：' + #13#10 +
          '  翻译记忆库：' + HumanSize(DirSizeBytes(root + '\Temp\translation_memory')) + #13#10 +
          '  词典：' + HumanSize(DirSizeBytes(root + '\dict')) + #13#10 +
          '  ASR 模型：' + HumanSize(DirSizeBytes(root + '\models\asr')) + #13#10 +
          '  配置与角色卡：' + HumanSize(DirSizeBytes(root + '\config')) + #13#10;
  if FileExists(root + '\config\api_keys.bin') then
    body := body + '  API 密钥文件将被删除，卸载后须重新录入。' + #13#10;
  body := body + '~\.cache\whisper 原生缓存与数据根外的自定义词典目录不在删除范围。';
  DataDelete := (MsgBox(body, mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES);
end;

procedure CurUninstallStepChanged(CurStep: TUninstallStep);
begin
  if CurStep = usPostUninstall then
  begin
    if DataDelete then
    begin
      if DelTree(DataRoot, True, True, True) then
        ForceDirectories(DataRoot) // 保留空目录（与「保留语义」一致，目录占位可被应用重建）
      else
        MsgBox('数据清理未完成（可能存在被占用文件）；已保留残余，请手动删除：' + DataRoot,
               mbInformation, MB_OK);
    end;
  end;
end;
