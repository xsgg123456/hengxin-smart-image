# 国内 API 重试提示独立预览审查

- candidateId：`9f9be3235b2ff3c62bdbfbafbe127a6d1d32a43cc1f8861dcb6222762e238fc1`
- 结论：Stage 1 **PASS**；Stage 2 **PASS**。仅批准本报告限定的独立模拟预览和技能规则变更。
- 范围：`output/api-retry-vue-preview-20261020` 的真实 Vue 页面复用、重试提示及模拟交互；`.agents/skills/dev-builder/SKILL.md:52`；`.codex/evolution/proposals.md:32`。
- 需求依据：主 Agent 交接的用户要求——真实前端一比一独立预览、取消管理员核实入口、显示完成数和自动重试/可重试、单图及未完成批量重试、成功图保留。`Product-Spec.md:3` 的成功图不重做作为背景约束；本次不验收整个正式产品，不授予正式实施、收费生成或部署权限。
- 快照边界：`output/` 被 Git 忽略，不受上述 candidateId 覆盖。另保存 `output/api-retry-vue-preview-20261020/review-hashes.json`，覆盖预览全部 src 文件，文件 SHA256 为 `7635c38d7cf68916e7e3de0d6328ab4465ee65d686c4639c6d0ff3a1d62d6e25`。审查末尾复核 `changedDuringReview: []`。主 Agent 应核对 candidateId 后登记两阶段 PASS，不能把本报告用于其它预览版本。

## Stage 1：需求符合性

下文 `P/` 表示 `output/api-retry-vue-preview-20261020/`。

| 条目 | 结论及证据 |
| --- | --- |
| 复用真实前端 | 完整实现。`output/api-retry-ui-preview-20261020/prepare_vue.py:5` 指向真实 frontend，`:8` 开始复制 src/public；`P/src/api/api-image-edits.ts:5` 强制使用 RealRecords。逐文件字节比对确认 572 个 src 文件完全一致；ChannelNotice/RealCreate 另外仅换行差异。`P/src/views/hengxin/api-image-edits/RealTaskDetail.vue:145` 保留原结果网格样式。没有以旧 HTML 代替 Vue 预览。 |
| 独立模拟边界 | 完整实现。`P/src/api/api-image-edits.ts:39` 未模拟的业务请求直接抛出“独立预览不调用业务接口”；`P/src/views/hengxin/api-image-edits/RetryPreviewControls.vue:3` 标记“独立预览 · 模拟数据”。浏览器重试交互期间 `/api/v1/` 业务请求为零。 |
| 取消管理员核实入口 | 完整实现。`P/src/views/hengxin/api-image-edits/RealTaskDetail.vue:10` 起操作区无核实按钮；`RealRecords.vue:20` 的详情绑定不再连接 resolve。`P/check-preview.mjs:14` 断言“核实已停止”按钮数量为零，独立重跑通过。残留 emit 类型不会生成入口。 |
| 完成数量及状态 | 完整实现。`RealTaskDetail.vue:17` 显示完成数，`:18` 进度只计算成功数量，`:78` 汇总完成/生成/自动重试/等待/可重试；`RealRecords.vue:13` 显示列表完成数及可重试数。截图确认显示 6/11，独立浏览器验证 7/11 和 11/11。 |
| 自动重试提示及停止 | 完整实现（模拟）。`retry-status.ts:7` 返回自动重试说明；`ItemRetryStatus.vue:4` 提供停止入口，`:27` 调用 stopItem；`P/src/api/retry-preview.ts:75` 将目标项切换为可重试。浏览器实际点击停止后出现“重试这张”。 |
| 单图重试 | 完整实现（模拟）。`RealTaskDetail.vue:34` 入口及`:121` 处理，`P/src/api/retry-preview.ts:74` 仅筛选指定 item；`:48` 至 `:61` 模拟生成及完成。真实按钮点击后完成数从 6/11 变为 7/11。 |
| 未完成批量重试 | 完整实现（模拟）。`RealTaskDetail.vue:14` 显示“重试未完成的 5 张”；`P/src/api/retry-preview.ts:48` 仅处理 failed，`:73` 批量调用。切换部分完成后点击批量重试，浏览器验证全部 11/11。 |
| 已成功图片保留 | 完整实现。`P/src/api/retry-preview.ts:48` 过滤失败项，不处理成功项。独立浏览器在停止及单图重试前后读取同一任务前六个 item，深度相等断言通过，包含结果、版本及源图。 |
| 长期规则采纳 | 完整实现。`.agents/skills/dev-builder/SKILL.md:52` 明确真实页面/组件/样式复用及同视口对照；`.codex/evolution/proposals.md:32` 标记已采纳，`:34` 引用用户纠正原文及落点。规则未扩大为正式实施授权。 |

部分实现、未实现：本次限定条目无。Spec 漂移：无；场景控制条为独立模拟预览必要操作。原页面新建、修改、修复、整套 ZIP 等既有入口没有在本次模拟实现，属于明确排除范围，不据此声称正式能力验证通过。

## Stage 2：质量、边界及视觉

- **代码质量 PASS**：新增 `P/src/api/retry-preview.ts:1` 共 86 行，`RetryPreviewControls.vue:1` 共 16 行；变动组件最大 168 行。新增逻辑使用 ApiItem/ApiTask 类型，无新增 any。模拟状态与真实页面分离；`:21` 切场景清除定时器，`:53` 至 `:56` 用轮次及状态避免已停止回调错误完成。
- **测试真实性 PASS**：`P/check-preview.mjs:15` 至 `:29` 操作真实 Vue 按钮并断言 UI 状态，未用直接修改数据代替交互。审查独立重跑 exit 0；另验证成功项数据保持及无业务请求。测试证明本地模拟交互，不证明上游 API 或真实生成语义。
- **安全 PASS（限定增量）**：新增两个文件检索 eval、innerHTML、dangerouslySetInnerHTML、密钥前缀、VITE 密钥变量及 any，零命中；`api-image-edits.ts:39` 禁止回落业务网络。`retry-preview.ts:81` 下载仅查模拟图片记录，使用本地静态 URL。未审查全仓历史安全性。
- **实际视觉对照 PASS**：使用真实原组件基准 `http://127.0.0.1:3027/#/api-image-edits/records?task=preview-retry-11` 和预览 3026，均为 1440×1000。审查实际查看 `P/review-baseline.png` 与 `P/preview-partial.png`：同侧栏、抽屉、素材卡、三列结果卡和按钮样式；变化是获准的提示与诊断信息位置。DOM 实测双方抽屉 1040px、结果网格 1000px、三列各 324px、gap 14px、图片区域约 294px，同字体。浮点测量出现 0.0000305px 差异，来自矩形浮点值，不是样式差异。样式依据 `RealTaskDetail.vue:145`；新增提示依据 `:6`、诊断折叠依据 `:39`。
- **LOW 清理建议（不阻塞）**：`RealTaskDetail.vue:72` 的 channelMessage、`:73` 的 resolve emit、`ItemRetryStatus.vue:11` 的 friendlyTime 为复制后遗留未使用定义。仅增加维护噪声，不影响本次模拟；若未来正式实施，应清理并按正式需求重新审查。

## 验证原始输出

审查者独立执行 `node check-preview.mjs`，退出码 0：

```text
{"checks":["真实 Vue 页面加载","停止自动重试","单图重试后由6/11变7/11","切换部分完成","批量重试后11/11","无管理员核实入口","无页面运行时异常"],"errors":[]}
{"errors":[]}
```

审查者额外浏览器断言，退出码 0：

```text
{"successItemsPreserved":true,"businessRequests":[]}
```

审查者独立执行 `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit`，退出码 0，原始 stdout/stderr 均为空。

主 Agent 提供的构建证据（本审查未重复构建）：`node node_modules/vite/bin/vite.js build --mode mock --outDir dist-preview`，退出码 0。交接摘要如下，非审查者获取的原始构建日志：

```text
4649 modules
built in42.78s
```

完整构建日志未随交接提供；不把上述摘录包装成完整日志。独立类型检查、浏览器实际渲染及交互均已通过。正式产品源文件未出现 Git 差异；受控变更为上述技能规则，本报告为新增审查记录。
