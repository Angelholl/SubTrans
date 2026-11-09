#!/usr/bin/env python
"""guard_banned_paths — 敏感路径入库守卫（v1.3.1 D10，D2026-0925-02；
名单随公开仓收窄换代扩面，D2026-1028-01／D2026-1106-01／D2026-1106 自检轮）。

三条纪律铁律：
1. 只看 git tracked/indexed 文件（``git ls-files``），绝不扫描工作树
   含 ignored 文件（ignored 树外签注面不属于仓库基线）。
2. 路径名单制，不做内容扫描——命中名单即违规，不判断文件内容。
3. 命中 tracked/indexed 文件匹配名单 → 打印违规项并退出码 1，否则 0。

用法::

    python tools/guard_banned_paths.py            # 全量 tracked 文件
    python tools/guard_banned_paths.py --staged   # 只查 staged（git diff --cached --name-only）

名单来源：.gitignore 敏感/禁推段现值（敏感数据段 + TM 备份段 + 内部工作材料段
+ 公开仓收窄第二批 + 治理运行时段 + C22 门控运行态 + 本地测试证据段 + 禁入库段）
+ docs/decision-log.md 条目 D2026-0916-01（1.2 收尾清单："internal_docs/、api_keys.bin、
sexual_terms.csv、真实 glossary、敏感 Temp 脚本移至仓库树外"）。逐条对照见 BANNED_PATTERNS。

口径两条：①**同族通配优先**——AGENTS.md 禁推清单原文即 `tools/ab_compare*`／
`tools/ruling_b6*`／`判批6*.bat` 且带「等」字（开放族），逐件枚举防不住同族新文件；
②`.auto/` 会话态目录**不可 gitignore**（插件工具链显式命名该路径会 pathspec 报错），
故该面只有本守卫一道防线。

双向防漂移（tests/test_guard_banned_paths.py）：正向＝名单每条有 .gitignore 或
decision-log 出处；反向＝.gitignore 每个禁推段每条规则都必须有名单对应——段内
新增规则而守卫漏收即红。D2026-1106 合规轮后公开仓收窄清单（D2026-1028-01 三令
＋D2026-1106-01 第二批）已扩到 30+ 条，本名单曾停在 2026-09 口径的 9 条，即该
轮自检迭代补的缺口。
"""

import argparse
import contextlib
import fnmatch
import subprocess
import sys

# 排除名单（路径模式，fnmatch 语义）。source 标注每条的契约出处，
# 由 tests/test_guard_banned_paths.py 做名单-契约防漂移断言。
BANNED_PATTERNS = [
    # ---- 来源 1：.gitignore 敏感数据段（字面规则现值）----
    ("config/api_keys.bin", ".gitignore: 敏感数据（严禁入库）"),
    ("config/glossary.csv", ".gitignore: 敏感数据（严禁入库）"),
    ("config/glossary.csv.bak-*", ".gitignore: 敏感数据（严禁入库）"),
    ("config/glossary_learned.csv", ".gitignore: 敏感数据（严禁入库）"),
    ("config/refine_stage_settings.json", ".gitignore: 敏感数据（严禁入库）"),
    ("config/user_dirs.json", ".gitignore: 敏感数据（严禁入库）"),
    ("create_shortcut.py", ".gitignore: 敏感数据（严禁入库）"),
    ("Temp/*", ".gitignore: 运行数据 Temp/"),
    # ---- 来源 1b：.gitignore「TM 备份」敏感段（私有译文备份，存量达
    # 2.4 万行级真实译文，decision-log 条目 D2026-0918-01 全量清空留痕为证）----
    ("tm.db.bak-*", ".gitignore: TM 备份敏感段（私有翻译数据，严禁入库）"),
    ("tm_full_backup_*.csv", ".gitignore: TM 备份敏感段（私有翻译数据，严禁入库）"),
    # ---- 来源 2：decision-log 条目 D2026-0916-01 收尾清单（树外同级目录契约）----
    ("internal_docs/*", "decision-log 条目 D2026-0916-01 internal_docs/ 移至树外"),
    ("sexual_terms.csv", "decision-log 条目 D2026-0916-01 sexual_terms.csv 移至树外"),
    # ---- 来源 3：decision-log 条目 D2026-1028-01 公开仓 push 面收窄（owner 三令）
    # 内部工作材料/评测产物只 commit 留本地，严禁出现在公开仓 ----
    ("artifacts/*", "decision-log 条目 D2026-1028-01 禁推清单（artifacts/）"),
    ("spike/*", "decision-log 条目 D2026-1028-01 禁推清单（spike/）"),
    # ---- 来源 4：decision-log 条目 D2026-1106-01 公开仓收窄第二批（领域调校包/
    # 过程文档/评测工具/内部入口脚本/判定材料工具移出公开仓）----
    ("AGENTS.md", "decision-log 条目 D2026-1106-01 第二批（根级本地件）"),
    ("docs/design/*", "decision-log 条目 D2026-1028-01 禁推清单（docs/design/**）"),
    ("docs/archive/*", "decision-log 条目 D2026-1028-01 禁推清单（docs/archive/**）"),
    ("docs/governance/*", "decision-log 条目 D2026-1028-01 禁推清单（docs/governance/**）"),
    ("docs/decision-log*", "decision-log 条目 D2026-1028-01 禁推清单（决策留档本地）"),
    ("docs/roadmap.md", "decision-log 条目 D2026-1028-01 禁推清单（roadmap 本地）"),
    ("docs/模型与转写实测推荐.md", "decision-log 条目 D2026-1106-01 第二批（内部评测文档）"),
    ("docs/examples/jav-domain/*", "decision-log 条目 D2026-1106-01 第二批（领域调校包）"),
    ("docs/cps-batchE-20260929.json", "decision-log 条目 D2026-1106-01 第二批（判定材料）"),
    ("docs/cps-batchE-20260929.txt", "decision-log 条目 D2026-1106-01 第二批（判定材料）"),
    ("docs/cps-定标报告-20260930.md", "decision-log 条目 D2026-1106-01 第二批（判定材料）"),
    ("docs/B2-门②语料基线-20260926.md", "decision-log 条目 D2026-1106-01 第二批（判定材料）"),
    ("docs/真机走查清单-*.md", "decision-log 条目 D2026-1106-01 第二批（走查材料）"),
    ("docs/模型测试两轮交接.md", "decision-log 条目 D2026-1106-01 第二批（过程文档）"),
    ("docs/测试基线语言假设分类-*.md", "decision-log 条目 D2026-1106-01 第二批（过程文档）"),
    ("docs/mimosa-findings-甄别表.md", "decision-log 条目 D2026-1106-01 第二批（深扫甄别材料）"),
    ("docs/领域包-hardened-审计-*.md", "decision-log 条目 D2026-1106-01 第二批（审计材料）"),
    ("docs/evidence-manifest.md", "decision-log 条目 D2026-1106-01 第二批（证据台账）"),
    # 评测/判定工具按**同族通配**收（AGENTS.md 原文即 `tools/ab_compare*`／
    # `tools/ruling_b6*` 口径，且清单带「等」字＝开放族）：逐件枚举防不住同族新文件。
    ("tools/ab_compare*", "decision-log 条目 D2026-1028-01 禁推清单（评测工具同族）"),
    ("tools/ruling_b6*", "decision-log 条目 D2026-1106-01 第二批（判定工具同族）"),
    ("tools/sensitive_b6*", "decision-log 条目 D2026-1106-01 第二批（判定工具同族）"),
    ("tools/model_matrix_run.py", "decision-log 条目 D2026-1028-01 禁推清单（评测工具）"),
    ("tools/spike_review_report.json", "decision-log 条目 D2026-1106-01 第二批（评测产物）"),
    ("tests/test_gen_sensitive_trans.py", "decision-log 条目 D2026-1106-01 第二批（判定材料测试）"),
    ("tests/test_sensitive_b6*", "decision-log 条目 D2026-1106-01 第二批（判定材料测试同族）"),
    ("tests/test_ruling_b6*", "decision-log 条目 D2026-1106-01 第二批（判定材料测试同族）"),
    ("判批6*.bat", "decision-log 条目 D2026-1106-01 第二批（本地入口脚本同族）"),
    ("敏感句网页.bat", "decision-log 条目 D2026-1106-01 第二批（本地入口脚本）"),
    # ---- 来源 7：.gitignore 本地测试证据段（注释自述「体积大且含片名/路径」——
    # 正是公开面合规最直接的泄漏载体，仓库只留 manifest/README）----
    (".abtest/*", ".gitignore: 本地测试证据（含片名/路径，仓库只留 manifest/README）"),
    (".abtest2/*", ".gitignore: 本地测试证据（含片名/路径，仓库只留 manifest/README）"),
    (".tmp374/*", ".gitignore: 本地测试证据（含片名/路径，仓库只留 manifest/README）"),
    (".tmp/*", ".gitignore: 本地测试证据（含片名/路径，仓库只留 manifest/README）"),
    # ---- 来源 8：.gitignore 两处「禁入库」段——CT2 引擎/模型下载残留兜底
    # （106MB/1.21GB/2.9GB 量级）与会话态工具产物（实验 dashboard 静态页）----
    ("runtime/*", ".gitignore: CT2 引擎/模型下载残留兜底（禁入库）"),
    ("autoresearch-dashboard.html", ".gitignore: 会话态工具产物（禁入库）"),
    # ---- 来源 9：autoresearch 会话态目录（decision-log 条目 D2026-1105-07 把
    # `.auto` 列入 message 面违禁模式；D2026-1106-04 脱敏规则 3 同项。该目录
    # 不可 gitignore——插件工具链显式命名该路径会 pathspec 报错——故只能由本
    # 守卫把守：内含 prompt.md/ledger 等内部评测口径与机制记录，入库即公开）----
    (".auto/*", "decision-log 条目 D2026-1105-07 违禁模式清单／D2026-1106-04 脱敏规则 3"),
    # ---- 来源 5：.gitignore 治理运行时段（账本收口治理的脚本副本/安全源/
    # 统计产物——含内部扫描关键词源，入库即等于把判定口径本身公开）----
    ("governance/scan-min/*", ".gitignore: 账本收口治理运行时（误入公开仓库防御）"),
    ("governance-secret-keywords.json", ".gitignore: 账本收口治理运行时（误入公开仓库防御）"),
    # ---- 来源 6：C22 门控运行态（decision-log 条目 D2026-1031-04 ① 终裁后
    # --enable 本地写，门控状态属本地运行态不随产品发布）----
    ("config/fullchain_c22.json", "decision-log 条目 D2026-1031-04 ① C22 门控运行态本地写"),
    # ---- 来源 10：.gitignore real 语料载体段（D2026-1109-01 案D′ 兜底联动）：
    # real 池载体（greal_v1.json/labels.sha256）与 golden root 指针树外保存，
    # 永不入库。`golden/*` 只锚仓根 golden/ 段，不命中 tests/fixtures/
    # hallucination_golden/（tracked 构造池夹具，合法入库）——fnmatch 整路径
    # 匹配，非子串匹配，出处靠段锚定而非字面巧合。----
    ("golden/*", "decision-log 条目 D2026-1109-01 兜底联动（real 语料载体树外）"),
    (".golden-root", "decision-log 条目 D2026-1109-01 兜底联动（golden root 指针树外）"),
]


def _git(args: list) -> list:
    """跑 git 取文件列表，逐行返回。"""
    out = subprocess.run(["git"] + args, capture_output=True, text=True,
                         check=True)
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def list_tracked() -> list:
    """全量 tracked/indexed 文件（不含工作树新增、不含 ignored）。"""
    return _git(["ls-files"])


def list_staged() -> list:
    """只查 staged 文件。"""
    return _git(["diff", "--cached", "--name-only"])


def match_any(path: str) -> list:
    """返回命中的 (pattern, source) 列表。"""
    hits = []
    norm = path.replace("\\", "/")
    for pattern, source in BANNED_PATTERNS:
        if fnmatch.fnmatch(norm, pattern):
            hits.append((pattern, source))
    return hits


def main(argv=None) -> int:
    # Windows CI 控制台常为 cp1252 等窄码页，中文文案直接 encode 即崩
    # （UnicodeEncodeError，回归自 test_clean_repo_exits_0 的 CI 失败）。
    # 只放宽 errors 不改 encoding：本地 cp936 中文照常显示，窄码页降级为
    # \uXXXX 转义而非崩溃；流不可 reconfigure（已关闭/被替换）时静默跳过，
    # 不影响守卫判定。
    for stream in (sys.stdout, sys.stderr):
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        with contextlib.suppress(OSError, ValueError):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(
        prog="guard_banned_paths",
        description="敏感路径入库守卫：tracked/indexed 文件命中排除名单即违规")
    parser.add_argument("--staged", action="store_true",
                        help="只查 staged 文件（默认查全量 tracked）")
    args = parser.parse_args(argv)

    files = list_staged() if args.staged else list_tracked()
    violations = []
    for path in files:
        for pattern, source in match_any(path):
            violations.append(f"{path}  [命中名单: {pattern} — {source}]")

    if violations:
        print("[违规] 以下 tracked/indexed 文件命中敏感路径排除名单：",
              file=sys.stderr)
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        print(f"共 {len(violations)} 项违规（名单契约见 tools/guard_banned_paths.py"
              " 与 decision-log 条目 D2026-0916-01／D2026-1028-01／D2026-1106-01）",
              file=sys.stderr)
        return 1
    scope = "staged" if args.staged else "tracked"
    print(f"[OK] {scope} 文件共 {len(files)} 个，均未命中敏感路径排除名单")
    return 0


if __name__ == "__main__":
    sys.exit(main())
