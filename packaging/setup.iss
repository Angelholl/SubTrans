; Inno Setup 6 script for SubTransJAV (D2026-0929-05 P2/07 定案)
; 版本号可由命令行覆盖：iscc /Dversion=1.2.3 packaging/setup.iss
; [Files] 源路径相对本脚本：../Temp/pyinstaller_dist/SubTrans/*，
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
#define MyAppExeName "SubTrans.exe"

[Setup]
; AppId 固定 GUID：卸载/升级识别口径，永不变更
AppId={{8F3A5C1E-6B2D-4E9A-9C47-1D0B5A7E2F31}
AppName={#MyAppName}
AppVersion={#version}
DefaultDirName={code:PickInstallDir|{autopf}\SubTrans}
DefaultGroupName={#MyAppName}
; 安装器自身图标（D2026-1004-01）：相对本 .iss 所在目录解析
SetupIconFile=..\subtrans\webview_gui\assets\icon.ico
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
Source: "..\Temp\pyinstaller_dist\SubTrans\*"; DestDir: "{app}"; Excludes: "system.dic"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

; 旧品牌开始菜单组清理（D2026-1004-04 批1）：对不存在路径无害空操作。
; 红线：任务栏钉扎快捷方式（Quick Launch\User Pinned\TaskBar）永不清理，卸载也不碰。
[InstallDelete]
Name: "{commonprograms}\SubTransJAV"; Type: filesandordirs
; 旧版打包缺陷遗留（D2026-1010-01 测试包轮修复）：spec datas dest 语义误用曾把
; asr_runner.py 装成「同名目录」，升级装时新包要在此落文件→MoveFile 错误 183
; （文件已存在）。升级前先清该名（目录/文件双形态通吃；新 [Files] 必重落为文件）
Name: "{app}\_internal\subtransjav\refine\asr_runner.py"; Type: filesandordirs

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

// '/' → '\' 归一（env/pointer 两来源可能带正斜杠；paths.py 侧 pathlib 天然
// 归一，iss 侧同径/祖先比较与落点 A 推导须先归一才同解）。
function _NormSlashes(const s: String): String;
var
  i: Integer;
begin
  Result := '';
  for i := 1 to Length(s) do
    if s[i] = '/' then
      Result := Result + '\'
    else
      Result := Result + s[i];
end;

// 计数字符（UNC 分享根判据用：反斜杠恰两处＝\\server\share 形态）
function _CountChar(const s: String; const c: Char): Integer;
var
  i: Integer;
begin
  Result := 0;
  for i := 1 to Length(s) do
    if s[i] = c then
      Result := Result + 1;
end;

// 锚点硬门槛：10 锚与 subtrans/data_migration.py 旧根白名单 +
// subtrans/paths.py DATA_ANCHORS + 运行时落盘对齐（glossary_conflict_watch.json
// 实际位于 Temp/translation_memory/，非 config\；config\templates 为角色卡/模板
// 目录；user_dirs.json 为 webview_gui/user_dirs.py 持久登记文件；
// fullchain_c22.json 为 C22 校准门产品态配置行，D2026-1101-01）。任一命中即
// 视为存在用户数据。
// 位置说明：本函数原位于 IsUnsafeRoot 前；D2026-1103-05 项②起 ResolveDataRoot
// 的旧根收养判定亦须调用它，Inno Pascal Script 无前置声明（定义必须先于使用），
// 故整体上移至 ResolveDataRoot 之前。三处锚点清单由 tests 对照钉住。
function HasAnyAnchor(const root: String): Boolean;
begin
  Result :=
    FileOrDirExists(root + '\config\user_dirs.json') or
    FileOrDirExists(root + '\config\user_settings.json') or
    FileOrDirExists(root + '\config\refine_stage_settings.json') or
    FileOrDirExists(root + '\config\api_keys.bin') or
    FileOrDirExists(root + '\config\glossary.csv') or
    FileOrDirExists(root + '\config\glossary_learned.csv') or
    FileOrDirExists(root + '\config\fullchain_c22.json') or
    FileOrDirExists(root + '\config\templates') or
    FileOrDirExists(root + '\Temp\translation_memory\tm.db') or
    FileOrDirExists(root + '\Temp\translation_memory\glossary_conflict_watch.json');
end;

// 旧 frozen 默认位（3.1.1 及以前）：%LOCALAPPDATA%\SubTrans，缺失回退 %USERPROFILE%
// （paths.py legacy_default_data_root 同级写法，Path.home() 对应 %USERPROFILE%）。
function _LegacyDefaultRoot(): String;
var
  env: String;
begin
  Result := '';
  env := GetEnv('LOCALAPPDATA');
  if env = '' then
    env := GetEnv('USERPROFILE');
  if env <> '' then
    Result := env + '\SubTrans';
end;

// 落点 A 默认推导（D2026-1103-05 项②：默认离 C）——与 paths.py
// default_data_root_for 同一规格各实现一次，形态对照表由测试钉住：
//   <安装目录父>\<安装目录名>-data；安装目录为盘符根/UNC 服务根时回退
//   <盘符|服务根>\SubTrans-data；名字已以 -data 结尾得双后缀（规则单一，
//   换取「推导结果恒不等于安装目录」硬不变量）。
// 注：appLoc 来自 {app}/注册表，恒为反斜杠形态，故此处不做 '/' 归一
//     （paths.py 侧 pathlib 天然容两形态）。
function _DefaultDataRootFor(const appLoc: String): String;
var
  d, parent, name: String;
  p: Integer;
begin
  Result := '';
  d := _NormSlashes(Trim(appLoc));
  if d = '' then
    Exit;
  while (Length(d) > 1) and (d[Length(d)] = '\') do
    d := Copy(d, 1, Length(d) - 1);
  // 盘符根（C: / C:\）→ <盘符>:\SubTrans-data
  if (Length(d) = 2) and (d[2] = ':') then
  begin
    Result := d + '\SubTrans-data';
    Exit;
  end;
  p := Length(d);
  while (p > 0) and (d[p] <> '\') do
    p := p - 1;
  if p = 0 then
    Exit;  // 非绝对路径（无分隔符）→ 不推导
  // 根形态（paths.py 侧 pathlib 判 parent==self 即此三类）：UNC 服务根
  // （\\server）、UNC 分享根（\\server\share，反斜杠恰两处）、单根（\）
  if (Length(d) >= 2) and (d[1] = '\') and (d[2] = '\') and
     ((p <= 2) or (_CountChar(d, '\') = 2)) then
  begin
    Result := d + '\SubTrans-data';
    Exit;
  end;
  name := Copy(d, p + 1, Length(d) - p);
  if name = '' then
  begin
    // 尾段为空（d = '\' 一类）→ 视作根
    Result := d + '\SubTrans-data';
    Exit;
  end;
  parent := Copy(d, 1, p - 1);
  Result := parent + '\' + name + '-data';
end;

// .data-root 指针读取（单行 trim 后须为绝对路径；不存在/非法返回空串）。
// 与 ResolveDataRoot 第 2 级、安装期写指针前的「已有有效指针不覆盖」判定共用。
function _ReadDataRootPointer(const appLoc: String): String;
var
  content: String;
  raw: AnsiString;
begin
  Result := '';
  if appLoc = '' then
    Exit;
  if LoadStringFromFile(appLoc + '\.data-root', raw) then
  begin
    content := Trim(Utf8BytesToStr(raw));
    if (content <> '') and
       (((Length(content) >= 2) and (content[2] = ':')) or
        (content[1] = '\') or (content[1] = '/')) then
      Result := content;
  end;
end;

// R2 数据根四级解析（与 subtrans/paths.py data_root() 对齐，仅安装器口径）：
// 1) 环境变量 SUBTRANS_DATA_ROOT（优先；旧名 SUBTRANSJAV_DATA_ROOT 兜底，
//    D2026-1106-02 ①兼容层）（非空才生效）；
// 2) 指针文件 .data-root（frozen 下固定在 exe 同目录 = {app}，单行绝对路径）；
// 3) frozen 默认＝落点 A（安装目录旁路），新默认无锚点而旧 %LOCALAPPDATA%\SubTrans
//    有锚点时收养旧根（护栏 6，不静默迁移）；
// 4) 安装目录不可得时回退旧默认位（保持既有「不抛异常」语义）。
function ResolveDataRoot(const appLoc: String; var srcLabel: String): String;
var
  env, newRoot, oldRoot: String;
begin
  Result := '';
  srcLabel := '';
  // 1) 环境变量（双前缀：SUBTRANS_DATA_ROOT 优先、旧名兜底，D2026-1106-02 ①）
  env := Trim(GetEnv('SUBTRANS_DATA_ROOT'));
  if env = '' then
    env := Trim(GetEnv('SUBTRANSJAV_DATA_ROOT'));
  if env <> '' then
  begin
    Result := env;
    srcLabel := '环境变量';
    Exit;
  end;
  // 2) 数据目录指针（exe 同目录）
  env := _ReadDataRootPointer(appLoc);
  if env <> '' then
  begin
    Result := env;
    srcLabel := '数据目录指针';
    Exit;
  end;
  // 3) 落点 A 默认（含旧默认收养）
  newRoot := _DefaultDataRootFor(appLoc);
  if newRoot <> '' then
  begin
    if HasAnyAnchor(newRoot) then
    begin
      Result := newRoot;
      srcLabel := '默认位置（安装目录旁路）';
      Exit;
    end;
    oldRoot := _LegacyDefaultRoot();
    if (oldRoot <> '') and (oldRoot <> newRoot) and HasAnyAnchor(oldRoot) then
    begin
      Result := oldRoot;
      srcLabel := '旧默认位置沿用';
      Exit;
    end;
    Result := newRoot;
    srcLabel := '默认位置（安装目录旁路）';
    Exit;
  end;
  // 4) 安装目录不可得（注册表陈旧且 {app} 亦空）→ 旧默认位兜底
  newRoot := _LegacyDefaultRoot();
  if newRoot <> '' then
  begin
    Result := newRoot;
    srcLabel := '默认位置（无安装目录兜底）';
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

// （HasAnyAnchor 已上移至 ResolveDataRoot 之前，见该处注释）

// 剥尾反斜杠＋斜杠归一（大小写不敏感比较前的归一；盘符根 C:\ 剥成 C: 以便
// 同径比较；env/pointer 来源可能带正斜杠，不归一则祖先前缀判定漏报）。
function _StripTrailingBackslash(const s: String): String;
begin
  Result := _NormSlashes(s);
  while (Length(Result) > 2) and (Result[Length(Result)] = '\') do
    Result := Copy(Result, 1, Length(Result) - 1);
end;

// 深度门槛：解析结果明显不该被 DelTree 的路径一律拒删。
// 覆盖：空串 / 盘符根（C: 与 C:\ 与 C:/）/ %WINDIR% / %ProgramFiles%（大小写
// 不敏感）/ 与安装目录 {app} 同径（大小写不敏感）/ root 为 {app} 的祖先目录
// （D2026-1103-05 项②护栏 7 新增：新默认落点 A 的安装目录父级旁路一旦与
//  安装目录构成祖先关系，删 root 即连安装目录一起删，复刻 10-30 事故形态）。
function IsUnsafeRoot(const root, appLoc: String): Boolean;
var
  lowRoot, lowLoc: String;
begin
  Result := True;
  if Trim(root) = '' then
    Exit;
  if (Length(root) <= 3) and (Length(root) >= 2) and (root[2] = ':') then
    Exit;
  lowRoot := Lowercase(_StripTrailingBackslash(root));
  // 剥斜杠后仍是盘符根（C: / D:）→ 拒
  if (Length(lowRoot) = 2) and (lowRoot[2] = ':') then
    Exit;
  if (lowRoot = Lowercase(_StripTrailingBackslash(GetEnv('WINDIR')))) or
     (lowRoot = Lowercase(_StripTrailingBackslash(GetEnv('ProgramFiles')))) then
    Exit;
  // 与 {app} 同径比较（大小写不敏感；双方剥尾反斜杠后比）
  lowLoc := Lowercase(_StripTrailingBackslash(appLoc));
  if (lowLoc <> '') and (lowRoot = lowLoc) then
    Exit;
  // root 为 {app} 祖先：root + '\' 是 lowLoc 的前缀
  if (lowLoc <> '') and (lowRoot <> '') and
     (Length(lowRoot) < Length(lowLoc)) and
     (Copy(lowLoc, 1, Length(lowRoot)) = lowRoot) and
     (lowLoc[Length(lowRoot) + 1] = '\') then
    Exit;
  Result := False;
end;

var
  DataDelete: Boolean;       // InitializeUninstall 定，usPostUninstall 执行
  DataRoot, DataSrc: String; // 解析结果与来源标签
  SystemDriveWarned: Boolean; // 离 C 告警只拦一次（D2026-1103-05 项②护栏 4）

// ---------------------------------------------------------------------------
// 目录防误装加固（D2026-1030-04）：3.1.0 实测事故——用户把既往安装目录改名
// 后，Inno 默认 UsePreviousAppDir 仍沿用注册表陈旧 App Path 预填目录页，
// 新版被默认装进改名后腾出名字的开发仓库工作树根。
// 两层加固（UsePreviousAppDir 保持默认，正常升级原位语义不动）：
//   F1 陈旧记录回落（交互向导）：目录页显示时，已装记录路径不存在或疑似
//      开发仓库 → 预填回落 PickInstallDir（与默认同源；无合格候选才用
//      编译默认 {autopf}\SubTrans）；
//   F2 开发仓库拒装（交互+静默双闸）：所选目录含 .git，或含 pyproject.toml
//      且有 subtrans/ 源码包目录 → 目录页 Next 与 PrepareToInstall 拒绝。
// ---------------------------------------------------------------------------

function IsDevRepoDir(const dir: String): Boolean;
var
  trimmed: String;
begin
  trimmed := Trim(dir);
  if (Length(trimmed) >= 2) and (trimmed[1] = '"') and
     (trimmed[Length(trimmed)] = '"') then
    trimmed := Copy(trimmed, 2, Length(trimmed) - 2);
  Result :=
    DirExists(trimmed + '\.git') or
    (FileExists(trimmed + '\pyproject.toml') and
     DirExists(trimmed + '\subtrans'));
end;

// 默认安装目录选盘三级优先（D2026-1105-02，owner 令，取代 D2026-1104-01
// 项 B4 的「最大空间」单层口径）：
//   层1：盘标含 software/软件 的非系统固定盘（多盘并列取可用空间最大者）；
//   层2：D 盘（非系统盘、可访问、D:\SubTrans 非开发仓库时）；
//   层3：无合格候选 → 回落编译默认 Param（{autopf}\SubTrans，系统盘 C 兜底）。
// 用户仍可在目录页改选。{autopf} 弃为默认，仅作层3回落（Param）。
// 定义须先于使用（Pascal Script 无前置声明），且 BestInstallDrive 依赖上方
// IsDevRepoDir。
//
// 取固定盘盘符串（如 C:D:）。输出受系统显示语言影响，故不用本地化文本
// 匹配；此处以 CIM 的 DriveType=3（本地固定盘）为准。失败返回空串＝固定盘
// 集合未知，调用方走回落，不得凭猜选盘。
function FixedDriveLetters(): String;
var
  i, rc: Integer;
  probe: String;
  s: AnsiString;
begin
  Result := '';
  probe := GetTempDir + 'subtrans-drivetypes.txt';
  if FileExists(probe) then
    DeleteFile(probe);
  // 探针文件在四条路径（启动失败／退出码非零／读取失败／成功）一律清理，
  // 不留残留（cmd 重定向即使命令失败也会创建文件，故三个失败分支同样要删）。
  if not Exec(ExpandConstant('{cmd}'),
    '/c powershell -NoProfile -NonInteractive -Command "Get-CimInstance Win32_LogicalDisk | Where-Object DriveType -eq 3 | Select-Object -ExpandProperty DeviceID" > "' + probe + '" 2>nul',
    '', SW_HIDE, ewWaitUntilTerminated, rc) then
  begin
    DeleteFile(probe);
    Log('默认安装盘：无法启动固定盘探测，固定盘集合未知');
    Exit;
  end;
  if rc <> 0 then
  begin
    DeleteFile(probe);
    Log('默认安装盘：固定盘探测退出码 ' + IntToStr(rc) + '，集合未知');
    Exit;
  end;
  if not LoadStringFromFile(probe, s) then
  begin
    DeleteFile(probe);
    Log('默认安装盘：固定盘探测结果读取失败，集合未知');
    Exit;
  end;
  DeleteFile(probe);
  // 逐盘比对 Pos（AnyString 形参可直接吃 AnsiString），只保留字母序形态
  for i := 1 to 26 do
    if Pos(Chr(64 + i) + ':', s) > 0 then
      Result := Result + Chr(64 + i) + ':';
  if Result = '' then
    Log('默认安装盘：固定盘探测结果为空，集合未知');
end;

// 取盘标含 software/软件 的固定盘盘符串（如 E:J:，D2026-1105-02 层1候选集）。
// 盘标匹配在 PowerShell 侧完成（-match 本身大小写不敏感，'software|软件'
// 一并覆盖英文/中文盘标），输出只含盘符 ASCII——规避读回侧 OEM 码页对中文
// 盘标的乱码风险。探针文件四路径一致清理，与 FixedDriveLetters 同规格。
// 失败返回空串＝层1候选集未知，调用方跳过层1，不走猜盘。
function SoftwareLabeledDrives(): String;
var
  i, rc: Integer;
  probe: String;
  s: AnsiString;
begin
  Result := '';
  probe := GetTempDir + 'subtrans-swlabels.txt';
  if FileExists(probe) then
    DeleteFile(probe);
  if not Exec(ExpandConstant('{cmd}'),
    '/c powershell -NoProfile -NonInteractive -Command "Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -eq 3 -and ($_.VolumeName -match ''software|软件'') } | Select-Object -ExpandProperty DeviceID" > "' + probe + '" 2>nul',
    '', SW_HIDE, ewWaitUntilTerminated, rc) then
  begin
    DeleteFile(probe);
    Log('默认安装盘：无法启动盘标探测，层1候选集未知');
    Exit;
  end;
  if rc <> 0 then
  begin
    DeleteFile(probe);
    Log('默认安装盘：盘标探测退出码 ' + IntToStr(rc) + '，层1候选集未知');
    Exit;
  end;
  if not LoadStringFromFile(probe, s) then
  begin
    DeleteFile(probe);
    Log('默认安装盘：盘标探测结果读取失败，层1候选集未知');
    Exit;
  end;
  DeleteFile(probe);
  for i := 1 to 26 do
    if Pos(Chr(64 + i) + ':', s) > 0 then
      Result := Result + Chr(64 + i) + ':';
end;

// 在给定候选盘池内选可用空间最大者（返回形如 'D:\'，无合格候选返回空串）。
// 共用排除：系统盘（GetEnv('SystemDrive')，与 InstallDirOnSystemDrive 同口径）、
// 不可访问盘、候选目录 <盘>:\SubTrans 疑似开发仓库（否则默认目录正好命中
// 开发工作树，会被 NextButtonClick/PrepareToInstall 的开发仓守卫拦死）。
// 并列取字母序小者。
function _PickLargestFrom(const pool, fixed: String): String;
var
  i: Integer;
  bestFree, freeBytes, totalBytes: Int64;
  drv, sysDrive, cand: String;
begin
  Result := '';
  bestFree := -1;
  sysDrive := Lowercase(GetEnv('SystemDrive'));
  if sysDrive = '' then
    sysDrive := 'c:';
  for i := 1 to 26 do
  begin
    drv := Chr(64 + i) + ':\';
    if (Pos(Chr(64 + i) + ':', pool) > 0) and
       (Pos(Chr(64 + i) + ':', fixed) > 0) then
    begin
      if Lowercase(Copy(drv, 1, 2)) = sysDrive then
        Log('默认安装盘候选排除 ' + drv + '：系统盘')
      else if not GetSpaceOnDisk64(drv, freeBytes, totalBytes) then
        Log('默认安装盘候选跳过 ' + drv + '：不可访问')
      else
      begin
        cand := Copy(drv, 1, 2) + '\SubTrans';
        if IsDevRepoDir(cand) then
          Log('默认安装盘候选排除 ' + drv + '：' + cand + ' 疑似开发仓库')
        else
        begin
          Log('默认安装盘候选 ' + drv + '：Free=' + IntToStr(freeBytes) +
              ' Total=' + IntToStr(totalBytes));
          if freeBytes > bestFree then
          begin
            bestFree := freeBytes;
            Result := drv;
          end;
        end;
      end;
    end;
  end;
end;

// 三级优先选盘（D2026-1105-02）：层1=盘标含 software/软件 的固定盘中取
// 可用空间最大者；层2=D 盘（非系统盘、可访问、D:\SubTrans 非开发仓库）；
// 层3=返回空串，由 PickInstallDir 回落编译默认 Param（系统盘 C 兜底）。
function BestInstallDrive(): String;
var
  sw, fixed: String;
  freeBytes, totalBytes: Int64;
begin
  Result := '';
  fixed := FixedDriveLetters();
  if fixed = '' then
  begin
    Log('默认安装盘：固定盘集合未知，不猜盘，走回落');
    Exit;
  end;
  // 层1：software/软件 盘标优先
  sw := SoftwareLabeledDrives();
  if sw <> '' then
  begin
    Result := _PickLargestFrom(sw, fixed);
    if Result <> '' then
    begin
      Log('默认安装盘：层1命中（盘标含 software/软件）→ ' + Result);
      Exit;
    end;
    Log('默认安装盘：层1候选均不合格（系统盘/不可访问/开发仓库），降层2');
  end
  else
    Log('默认安装盘：无盘标含 software/软件 的固定盘，降层2');
  // 层2：D 盘
  if Pos('D:', fixed) = 0 then
    Log('默认安装盘：D 盘不在固定盘集合，降层3')
  else if Lowercase(GetEnv('SystemDrive')) = 'd:' then
    Log('默认安装盘候选排除 D:\：系统盘，降层3')
  else if not GetSpaceOnDisk64('D:\', freeBytes, totalBytes) then
    Log('默认安装盘候选跳过 D:\：不可访问，降层3')
  else if not IsDevRepoDir('D:\SubTrans') then
  begin
    Result := 'D:\';
    Log('默认安装盘：层2命中（D 盘）→ ' + Result);
    Exit;
  end
  else
    Log('默认安装盘候选排除 D:\：D:\SubTrans 疑似开发仓库，降层3');
  // 层3：无合格候选，返回空串 → 调用方回落编译默认 Param（C 盘兜底）
  Log('默认安装盘：层1/层2均无合格候选，回落编译默认目录（C 盘兜底）');
end;

// Scripted constant：DefaultDirName 与 CurPageChanged 回落同源。
// 层1/层2 有候选 → <盘>:\SubTrans；否则 Param（{autopf}\SubTrans，C 盘兜底），
// 交互侧由既有系统盘告警＋改选入口兜住，静默侧由 PrepareToInstall 记日志。
// 两条路均记日志。
function PickInstallDir(Param: String): String;
var
  drv, reason: String;
begin
  drv := BestInstallDrive();
  if drv <> '' then
  begin
    Result := drv + 'SubTrans';
    reason := '三级优先选盘命中（软件盘标/D 盘）';
  end
  else
  begin
    Result := Param;
    reason := '无合格候选盘，回落编译默认目录（C 盘兜底）';
  end;
  Log('默认安装目录选择：' + Result + '（' + reason + '）');
end;

// 安装目录是否落在系统盘 / %ProgramFiles%（D2026-1103-05 项②护栏 4 判据；
// 「父目录不可写」在现实形态上即 Program Files 一类受保护目录，故并入同一
// 判据，不另做写探测）。定义须先于使用（Inno Pascal Script 无前置声明）。
function InstallDirOnSystemDrive(const dir: String): Boolean;
var
  low, sysDrive, pf: String;
begin
  Result := False;
  low := Lowercase(Trim(dir));
  if low = '' then
    Exit;
  sysDrive := Lowercase(GetEnv('SystemDrive'));
  if sysDrive = '' then
    sysDrive := 'c:';
  if Copy(low, 1, Length(sysDrive)) = sysDrive then
  begin
    Result := True;
    Exit;
  end;
  pf := Lowercase(GetEnv('ProgramFiles'));
  if (pf <> '') and (Copy(low, 1, Length(pf)) = pf) then
    Result := True;
end;

procedure CurPageChanged(CurPageID: Integer);
var
  ver, loc: String;
begin
  if CurPageID = wpSelectDir then
  begin
    ReadInstalledInfo(ver, loc);
    if (loc <> '') and
       ((not DirExists(loc)) or IsDevRepoDir(loc)) then
      WizardForm.DirEdit.Text := PickInstallDir(ExpandConstant('{autopf}\SubTrans'));
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    if IsDevRepoDir(WizardForm.DirEdit.Text) then
    begin
      Result := False;
      MsgBox('所选目录疑似开发仓库（含 .git，或 pyproject.toml + subtrans 源码结构），' + #13#10 +
             '不能作为 SubTrans 安装目录，否则会污染开发工作树。' + #13#10 +
             '请另选实际安装目录。', mbError, MB_OK);
      Exit;
    end;
    // 离 C 口径告警＋改选入口（D2026-1103-05 项②护栏 4）：不得静默接受。
    // 只拦一次（SystemDriveWarned），避免「改选→再告警」死循环。
    if (not SystemDriveWarned) and InstallDirOnSystemDrive(WizardForm.DirEdit.Text) then
    begin
      SystemDriveWarned := True;
      if MsgBox('所选安装目录位于系统盘或 Program Files：' + WizardForm.DirEdit.Text + #13#10 +
                '数据目录按默认会落在它的旁路位，同样在系统盘上，与「数据尽量不放系统盘」的默认口径冲突。' + #13#10 +
                '是否返回改选安装目录？（选「否」按当前目录继续，数据目录亦可日后在「设置 → 高级参数 → 数据保存目录」另行指定）',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        Result := False;
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if IsDevRepoDir(WizardDirValue) then
  begin
    Result := '安装目录是开发仓库（含 .git 或 pyproject.toml + subtrans 源码结构），已阻止安装；' +
              '静默安装请用 /DIR= 指定实际安装目录。';
    Exit;
  end;
  // 离 C 口径告警（D2026-1103-05 项②护栏 4）：静默面无 UI 可交互，只记日志
  // 不阻断（已在卡面与执行记录披露）；交互向导侧的告警＋改选见 NextButtonClick。
  if WizardSilent and InstallDirOnSystemDrive(WizardDirValue) then
    Log('[data-root] 静默安装目录位于系统盘/Program Files：' + WizardDirValue +
        '，数据根随之路径旁路落系统盘，未弹告警（无交互界面）');
end;

// 安装期写 .data-root 指针（护栏 5）：提权期写 {app}\.data-root；原地升级
// 已有有效指针一律不覆盖；env 生效时按「优先级不动」不写；写入结果记安装日志，
// 失败显式告警（不得静默回落）。
procedure WriteDataRootPointerAtInstall;
var
  appLoc, existing, root, src: String;
  i: Integer;
  asciiOnly: Boolean;
begin
  appLoc := ExpandConstant('{app}');
  if Trim(appLoc) = '' then
  begin
    Log('[data-root] {app} 为空，跳过指针写入');
    Exit;
  end;
  if (Trim(GetEnv('SUBTRANS_DATA_ROOT')) <> '') or
     (Trim(GetEnv('SUBTRANSJAV_DATA_ROOT')) <> '') then
  begin
    Log('[data-root] 环境变量 SUBTRANS_DATA_ROOT（或旧名 SUBTRANSJAV_DATA_ROOT）已生效（优先级高于指针），不写指针');
    Exit;
  end;
  existing := _ReadDataRootPointer(appLoc);
  if existing <> '' then
  begin
    Log('[data-root] 既有有效指针，原地升级不覆盖: ' + existing);
    Exit;
  end;
  root := ResolveDataRoot(appLoc, src);
  if root = '' then
  begin
    Log('[data-root] 数据根解析为空，跳过写入');
    Exit;
  end;
  // 收养旧默认位时不写指针：写下去来源就变成「数据目录指针」，GUI 与 --where
  // 双双误显「自定义目录」，且首启插桩门（只对默认来源放行）在收养机器上永不
  // 触发——恰是 data_migration 侧要保的既得行为。应用侧同规则推导即得同解。
  if src = '旧默认位置沿用' then
  begin
    Log('[data-root] 收养旧默认位（' + root + '），不写指针：来源标签须保持「默认」，' +
        '否则首启插桩门与来源读数双双失真');
    Exit;
  end;
  // 本机 Inno 6 的 SaveStringToFile 无编码重载（实测 4/5 参形态编译报
  // 「Invalid number of parameters」），落盘按 ANSI 码页；非 ASCII 路径写出去
  // 会被 paths.py 的 UTF-8 读取面读坏，故仅 ASCII 路径写指针——非 ASCII 时
  // 不写，由应用侧按同一规格推导（两侧同算法，无指针亦不歧义）。
  asciiOnly := True;
  for i := 1 to Length(root) do
    if (Ord(root[i]) < 32) or (Ord(root[i]) > 126) then
    begin
      asciiOnly := False;
      Break;
    end;
  if not asciiOnly then
  begin
    Log('[data-root] 数据根含非 ASCII 字符，安装器不写指针（ANSI 落盘会被读坏）: ' + root);
    Exit;
  end;
  if SaveStringToFile(appLoc + '\.data-root', root + #13#10, False) then
    Log('[data-root] 已写 ' + appLoc + '\.data-root → ' + root + '（来源：' + src + '）')
  else
    MsgBox('数据目录指针写入失败：' + appLoc + '\.data-root' + #13#10 +
           '应用将按默认推导定位数据目录；若该位置不可写，请在「设置 → 高级参数 → 数据保存目录」手动指定。',
           mbError, MB_OK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    WriteDataRootPointerAtInstall;
end;

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
  ver, loc, root, body, newRoot, oldRoot: String;
begin
  Result := True;
  ReadInstalledInfo(ver, loc);
  if loc = '' then
    loc := ExpandConstant('{app}');
  root := ResolveDataRoot(loc, DataSrc);
  DataRoot := root;
  // ① 深度门槛：解析结果异常（盘符根/系统目录/安装目录/安装目录祖先等）一律不删
  if IsUnsafeRoot(root, loc) then
  begin
    DataDelete := False;
    MsgBox('数据目录解析结果异常（' + root + '），为安全起见不执行任何删除；' +
           '如需清理请手动核查。', mbInformation, MB_OK);
    Exit;
  end;
  // ①b 新旧两根同时有数据（D2026-1103-05 项②护栏 8）：不得静默二选一删，
  //     默认保留并明示两路径，由用户自行确认保留哪一个。
  newRoot := _DefaultDataRootFor(loc);
  oldRoot := _LegacyDefaultRoot();
  if (newRoot <> '') and (oldRoot <> '') and (newRoot <> oldRoot) and
     HasAnyAnchor(newRoot) and HasAnyAnchor(oldRoot) then
  begin
    DataDelete := False;
    MsgBox('检测到两个数据目录均存在本地数据，为防误删本次卸载不删除任何数据：' + #13#10 +
           '  安装目录旁路：' + newRoot + #13#10 +
           '  旧默认位置：%LOCALAPPDATA%\SubTrans → ' + oldRoot + #13#10 +
           '请自行确认保留哪一个后再手动清理另一个。', mbInformation, MB_OK);
    Exit;
  end;
  // ② 锚点预检：无任何用户数据锚点 → 按保留处理（防误删可重下载资源目录）
  if not HasAnyAnchor(root) then
  begin
    DataDelete := False;
    MsgBox('未在 ' + root + ' 识别到本地数据文件，本次卸载按保留数据处理。' + #13#10 +
           '若曾用环境变量 SUBTRANS_DATA_ROOT（旧名 SUBTRANSJAV_DATA_ROOT）自定义数据目录，请自行核查实际位置；' +
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
          '  CT2 模型：' + HumanSize(DirSizeBytes(root + '\models\ct2')) + #13#10 +
          '  CT2 运行时：' + HumanSize(DirSizeBytes(root + '\runtime\ct2')) + #13#10 +
          '  配置与角色卡：' + HumanSize(DirSizeBytes(root + '\config')) + #13#10;
  if FileExists(root + '\config\api_keys.bin') then
    body := body + '  API 密钥文件将被删除，卸载后须重新录入。' + #13#10;
  // 两根并存时（①b 已在双锚点命中时拦下）此处把另一根的位置也明示，
  // 避免用户以为「删了就干净了」（D2026-1103-05 项②护栏 8）
  if (newRoot <> '') and (newRoot <> root) then
    body := body + '  注：安装目录旁路位 ' + newRoot + ' 不在本次删除范围。' + #13#10;
  if (oldRoot <> '') and (oldRoot <> root) then
    body := body + '  注：旧默认位 ' + oldRoot + ' 不在本次删除范围。' + #13#10;
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
