# 发版 checklist（release/2.x 分支制）

> 依据：D2026-0929-05/-07、D2026-1001-02/-03 发版实践沉淀（D2026-1001-03 评议员★1 条件 1 实体化）。
> 每次发版从上到下逐项勾；任一步失败即停，不带病推进。

- [ ] 1. 从 main 切 `release/2.x.y` 分支。
- [ ] 2. 分支上 bump 版本号：`subtransjav/__version__.py`（`__version__`/`__version_display__`/`__version_info__` 三常量）+ `pyproject.toml` 同批，去掉 dev 后缀（如 2.3.0.dev0→2.3.0）；`tests/test_version_consistency.py` 3 钉过。
- [ ] 3. CHANGELOG `[x.y.z]` 小节：只写本版内容，禁止未来计划/排期/内部流程引用，写完关键词自查。
- [ ] 4. 验证链：ruff 全仓 → 定向测试 → 全量测试（基线不降，当前 1601+4）→ 冒烟（`--help`/`--where`）→ Mimosa 深扫与基线比对零新增 → 甄别表增记本次 seal。
- [ ] 5. tag `v2.2.1` → 分支头（tag push 触发 release.yml；git-gate 拦截时走 owner 终端/既裁通道，不绕钩子）。
- [ ] 6. CI release.yml 全绿 → artifact 下载并哈希核验（双 setup.exe + SHA256SUMS 一致）。
- [ ] 7. GitHub Release 建发：notes 只写本版；非草稿非预发布。
- [ ] 8. **main 前进到下一 dev 号**（如 2.3.0 发布后 → 2.3.1.dev0，三常量+pyproject 同批）——D2026-1001-03 ★1 新即时检查点，**遗漏此步=制造新幽灵版本**。
- [ ] 9. main CHANGELOG 同步 [x.y.z] 小节；roadmap 登记发版行（tag/Release id/哈希/notes 口径）。
- [ ] 10. push 后 ls-remote 复核：分支、tag、main 版本号三处一致。
