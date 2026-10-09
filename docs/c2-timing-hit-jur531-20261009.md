# C2 实测报告：jur-531 timing 精确命中率与重号 timing（D2026-1009-01 C2 / D2026-1009-02 批0 收口门）

- 实测日期：2026-10-09（批0 执行轮）
- 数据：`E:\无字幕\新建文件夹\四次测试\`（owner 真机数据）——原始源文 `4k2.me@jur-531.ja.merged.whisperjav.srt`（1518 cue）+ 质量报告导读 json（66 条；树外留存副本 `D:\SubTransJAV-internal-archive\hro2-golden-inputs-20260925\` 含源文 SRT 与 sha256 清单）
- 方法：与生产同源——复用 `subtransjav/refine/action_retranslate.py` 的 `_load_source_map`（timing→text 映射，`setdefault` 精确匹配首个）与 `refine/filters.py` 的 `parse_srt`；待修集合取 `_select_items` 缺省口径（`status=open` 且 `current_text` 非 None）。生产函数映射与独立复算逐键相等（`prod==manual: True`）。

## 结果

| 指标 | 数值 |
|---|---|
| 源文 cue 总数 | 1518 |
| 源文重号 timing | **0 组**（0.0% / 1518 唯一 timing） |
| 待修条目（open+有现译） | 46 |
| timing 精确命中 | **46 / 46（100.0%）** |
| 未命中（将退化为导读摘录） | 0（0.0%） |
| 命中中受重号折叠影响 | 0（0.0% of hits） |
| category 细分 | untranslated 26/26（100%）· cps_too_fast 20/20（100%） |

未命中明细与重号命中明细：均为空。

## 结论

- **C2 门 PASS**：jur-531 全量待修条目 timing 精确命中率 100%，重号 timing 为 0，`--action-source` 传参后全部条目可按 timing 对齐恢复完整源文，无退化、无折叠错配。
- `cps_too_fast` 条目 `source_excerpt` 恒空（`quality_report.py` 来源 E 恒空串）在 timing 全命中前提下不影响源文恢复，维持"不做行为变更"的批0 范围裁定。
- 局限如实注明：单样本（N=1 部）；重号 timing 在该样本为 0，折叠取首语义（`setdefault`）的正确性风险在本样本未被实际触发——留待后续真实任务批量修复的退化/错配计数观察（digest 上报后可从放弃/退化统计感知），不构成批0 放行阻塞。

## 复现

```bash
cd /d/SubTransJAV
.venv/Scripts/python.exe - <<'EOF'
import json, sys
from pathlib import Path
sys.path.insert(0, r'D:\SubTransJAV')
from subtransjav.refine.action_retranslate import _load_source_map
D = Path(r'E:\无字幕\新建文件夹\四次测试')
g = json.loads((D / '4k2.me@jur-531.ja.merged.whisperjav_质量报告导读.json').read_text(encoding='utf-8'))
fixable = [it for it in g['items'] if it.get('status')=='open' and it.get('current_text') is not None]
m = _load_source_map(str(D / '4k2.me@jur-531.ja.merged.whisperjav.srt'), fixable)
print(len(fixable), sum(1 for it in fixable if it.get('timing') in m))
EOF
```

预期输出：`46 46`。
