# 海外图片发布配置凭据时序：增量独立复审

- candidateId：`ede03b314995060169e2f6ae7a67991e11308983d6476bd2c8b90a03856d6fb4`。
- 上一批准快照：`f5fc48dc07e5ad03caee0559d16ae908e6b342144996e77d6085e56036502bb1`。
- Stage 1（Spec Compliance）：**PASS**。
- Stage 2（Code Quality）：**PASS**。
- 范围：仅 `scripts/release/studio-delivery-deploy.py` 配置凭据采集时序与 `scripts/release/test_studio_delivery_deploy.py` 新增回归。业务功能逐条结论承接 `docs/STUDIO-DELIVERY-FINAL-REVIEW-20261023.md:23`，覆盖文件排序承接 `docs/STUDIO-DELIVERY-OVERRIDE-REVIEW-20261023.md:21`。

## 快照与差异核验

审查开始及报告写入前，review-status 均显示 currentId 为本候选，changedFiles 仅上述两文件。独立重建旧文件并比较已批准快照的 SHA256：部署脚本仅将同一语句从 `stage(work, 'override-written')` 前移至 daemon-reload 后；测试仅追加第 265 行起的新函数，两文件均精确匹配旧摘要。不是仅依据派发摘要判定差异。重建首次错误地把旧语句放在 stage 后，另一次多保留测试末尾换行，均未匹配；纠正重建逻辑后匹配，送审代码未改动。

业务六文件、其余测试、运行配置和用户预存 AGENTS.md 改动均与上一批准快照相同。本 reviewer 未修改代码、未提交、未登记批准、未写 `.needs-review`。

## Stage 1：Spec Compliance

依据 `Product-Spec.md:1322` 本轮完整章节、`docs/STUDIO-DELIVERY-FIX-20261023.md:3` 至 `:9` 及末尾事故记录。

| 要求 | 结论与证据 |
| --- | --- |
| 原生首轮无 Markdown、多图、同会话同成功轮、生成/公开字节与最终事件一致 | 无变化；上一完整报告 `:25` 至 `:28` 的代码和测试证据仍对应相同摘要。 |
| 排除过程/草稿/否定/失败/停止/未完成，最终清单优先 | 无变化；上一完整报告 `:29` 至 `:32`，包括历史清单修复，未被本增量覆盖。 |
| 历史明确补交、来源与内容校验、拒绝跨会话/输入/Skill/无来源、去重、work 新增门禁、异常提示与不扫描猜交付 | 无变化；上一完整报告 `:33` 至 `:39` 的逐项结论及摘要保留。 |
| 受限维护、原事件与图片核验、排空/台账/事务/删除竞态/审计、幂等、不重跑与不归档、保留原次数时间 | 无变化；上一完整报告 `:40` 至 `:47`，未重复将 SQLite 测试说成真实 PostgreSQL 并发验证。 |
| 实际生产基线增量、保留国内/权限/Skill/模型/提示词、无迁移 | 完整保持；两个差异文件只改变凭据写入顺序及专项测试。部署 `:105`、`:120` 仍仅操作目标 worker，`:156` 仍核对无关拓扑。 |
| 凭据必须反映加载后的本次覆盖配置 | 完整实现；部署 `:117` 先成功执行 daemon-reload，`:118` 才执行 unit() 并保存，`:119` 至 `:120` 随后启动。runtime `:33` 非零/超时抛错，不会在 reload 失败后继续启动；`:163` unit() 使用 systemctl cat。新测试 `:265` 至 `:286` 模拟 reload 前后缓存列表差异，在 start 回调验证凭据已包含新覆盖。 |
| 完整 verify 及验收后恢复接纳 | 完整保持；部署 `:130` 检查实际覆盖内容，`:131` 仍严格比较 unit-installed；`:138` 至 `:156` 验证实际 cwd/argv/PID、ready、API、gate、无关拓扑；`:163` 至 `:169` 仍须完整 verify 与验收回执才能恢复原 gate。没有删除漂移保护来绕过失败。 |
| 指定原 PNG 补回、预览下载及可归档 | 本增量无实现变更，生产操作仍待主 Agent 证据；上一报告 `:50` 与计划 `:9`。本 reviewer 未连接生产，不宣称已恢复或页面已通过。 |
| UI、引导真实性、Spec 漂移 | 无页面、样式、提示、API、数据库或业务行为变化；UI 设计及邻居页面视觉比较不适用。部署 `:117` 至 `:120` 与测试 `:265` 为全部增量，无额外功能。 |

完整实现：本次凭据时序修复及原门禁保持。部分实现/未实现：本增量未发现。HIGH/MEDIUM/LOW 缺陷：无。

## Stage 2：Code Quality

- 结构：部署脚本 206 行，测试 286 行，低于 300 行标准；同一已有语句移动，无新增生产函数或类型复杂度。证据部署 `:116` 至 `:120`、测试 `:265`。
- 测试真实性：缓存状态只由实际 switch 发出的 daemon-reload 更新，start 回调检查落盘凭据，verify 替身核对 phase 与当前 unit；确实证明本次控制流时序。独立将旧版 switch 在内存加载，运行新增测试，旧版在 start 时断言失败。未修改工作区进行反证。测试替换完整 verify，因此不声称这一个用例验证了真实 systemd 或整个安装后健康链。
- 错误处理与安全：reload 或凭据读取/写入失败均先于 start；部署 `:195` 留注意事项，原 gate 保持暂停。runtime `:46` 的私有权限写入、`:33` 参数数组执行均未变。两文件扫描 eval、HTML 注入、前端密钥前缀、OpenAI/Anthropic 密钥模式和 shell=True 无命中。没有新增凭据泄露或命令插值。
- 外部语义核查：systemctl 官方文档说明磁盘文件展示可能与尚未 daemon-reload 的 manager 理解不一致；这支持先 reload 再采集的顺序，但现场旧 drop-in 列表现象仍以主 Agent 的只读现场证据为准。[systemctl 官方文档](https://www.freedesktop.org/software/systemd/man/257/systemctl.html)
- 现场修复边界：计划末尾提出仅当旧回执等于 unit-before，且当前 cat 严格等于原内容追加本次固定 DROP 段时补记回执，随后完整 verify。此为主 Agent 待执行操作，未新增自动修复代码。必须保留原回执/差异证据；不能直接接受任意当前 cat，不得重跑 switch。部署 `:80` 防重入和 `:131` 严格比较继续有效。本报告不把计划视作现场已通过。

## 独立验证原始输出

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest scripts/release/test_studio_delivery_deploy.py -q
.........s............................                                   [100%]
37 passed, 1 skipped in 0.42s
exit_code: 0
```

跳过为 Windows 无法创建目录符号链接，测试 `:68` 至 `:76`；不计为通过。

```text
旧版内容重建及内存反证脚本：
scripts/release/studio-delivery-deploy.py RECONSTRUCTED_PRIOR_MATCH True lines 206
scripts/release/test_studio_delivery_deploy.py RECONSTRUCTED_PRIOR_MATCH True lines 286
OLD_ORDER_MUTATION_REJECTED: receipt assertion fails before start
exit_code: 0

hengxin-smart-image/backend/.venv/Scripts/python.exe -m compileall -q scripts/release/studio-delivery-deploy.py scripts/release/test_studio_delivery_deploy.py
stdout: <empty>
stderr: <empty>
exit_code: 0

git diff --check
warning: in the working copy of 'AGENTS.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'Product-Spec-CHANGELOG.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'Product-Spec.md', CRLF will be replaced by LF the next time Git touches it
exit_code: 0
```

主 Agent 提供的 Linux 1226 passed / 79 skipped、真实事故首轮 1 张/历史补交 1 张/重复新增 0 张、生产 PID/cwd/gate 证据，均为其既有验证，本 reviewer 未重复六分钟业务回归或冒充亲自实查。主 Agent 可据本报告为同一 candidateId 登记两阶段 PASS，再继续受限回执修复、独立完整 verify、原图补收及页面验收。
