# 单图文字任务移除整套修改 · 独立审查

日期：2026-09-28。执行角色：code-reviewer；已读取 `.agents/skills/code-review/SKILL.md`。仅审本轮窄范围需求，不代表全产品重新验收。

- candidateId：`fb4929d00b1fa27a45a0f8af64c224b5c75fdf557da97c738b5cc9a7c880f853`。
- 本轮代码：`hengxin-smart-image/frontend/src/views/hengxin/components/TaskDetail.vue`，仅按钮条件、说明条件和 computed 三处。下文组件路径以 `frontend/src/views/hengxin/` 为基准，其余根目录路径明确标识。
- 需求依据：根目录 `Product-Spec.md:7`、`Design-Brief.md:3`、`DEV-PLAN.md:5`、`Product-Spec-CHANGELOG.md:3`。最新确认覆盖此前“仅评估”的旧阶段记录。
- 上轮三文件默认 Skill 清理保持原样，其审查结论见 `TEXT-DEFAULT-UI-REVIEW-20260928.md:5`，candidate `7fa6c543e691396f6c4d9aaca318dd64cba5aada652c514974626527de8c6684`。本报告不把其旧版“本轮不删除修改入口”结论用于当前新需求。
- 独立运行 review-status：当前 candidate 与派发值一致，相对已审快照 changedFiles 只有 TaskDetail.vue；审查中未发现代码快照变化。CHANGELOG 移动普通 Markdown 条目不改变代码 candidate。

## Stage 1 · Spec Compliance：PASS

| 本次全部需求条目 | 结论与证据 |
| --- | --- |
| 单图文字详情去掉整套修改按钮 | 完整实现。`components/TaskDetail.vue:85` 在 text 且 slots≤1 时返回 false；`:9` 使用 v-if。根目录 `output/text-whole-ui-browser-single.txt:2` 实际浏览器计数 whole=0。外层 `:7` 要求 task 与 data 已加载，未加载时不会误显示按钮。 |
| 说明不再引导整套修改 | 完整实现。`components/TaskDetail.vue:10` 使用同一条件切换文案，单图为“下载和归档”。浏览器原始正文 `output/text-whole-ui-browser-single.txt:2` 与截图均一致。 |
| 保留“修改这张”及可选画布 | 完整实现。`components/ResultCard.vue:12` 原按钮及事件未改；`components/TaskDetail.vue:23`、`:34`、`:115` 保留卡片事件、画布和选定版本。浏览器脚本 `output/text-whole-ui-browser-single.txt:5` 确实点击该按钮，`:2` 返回 canvas=1 与“修改第 1 张图片 · 基于 V1”弹窗正文。未改按钮命名。 |
| 历史多图文字继续保留整套修改 | 完整实现。`components/TaskDetail.vue:85` slots>1 返回 true。`output/text-whole-ui-browser-regression.txt:2` 历史文字任务 whole=1；任务名称及四张图前提可追溯至 `hengxin-smart-image/frontend/src/api/hengxin/fixtures.ts:17`、`:23`。 |
| 壁纸、商品继续保留整套修改 | 完整实现。`components/TaskDetail.vue:85` 非 text 恒为 true，原 editable 禁用条件和 edit(null) 保持。`output/text-whole-ui-browser-regression.txt:2` 两类任务 whole 均为 1，模式对应 fixtures.ts:17。 |
| 后端接口、历史轮次保持 | 完整实现。本轮差异只有上述三处展示代码，无后端文件变化；`components/TaskDetail.vue:30` RoundHistory、`:91` service.revise、`:142` 原提交载荷保留。单图浏览器正文仍有“执行与修改记录（1）”“第 1 轮 · 整套”；这属于明确保留的历史记录，不是遗漏删除按钮。 |
| 沿用现有视觉 | 完整实现。`components/TaskDetail.vue:9`、`:10` 未更换组件/class，`prototype.css:25`、`:26`、`:30` 的字号、间距、结果网格保持。reviewer 实际打开 `output/text-whole-ui-single.png`，确认仅余下载/归档按钮、说明无整套修改、单张卡片仍含修改这张，无重叠或截断。 |
| 仅本地、不提交、不部署 | 本轮 diff 无发布配置或版本变化，reviewer 未执行提交/部署。此审查不声明生产环境已经更新。 |

部分实现：无。未实现：无。HIGH：无。Spec 漂移：无新增页面、API、表或业务流程。引导真实性：单图说明与现有下载/归档行为一致，多图条件继续对应已有整套修改弹窗（`components/TaskDetail.vue:35`）。

## Stage 2 · Code Quality：PASS（含验证边界）

- 质量：`components/TaskDetail.vue:85` 一个有语义的 computed 供按钮和文案复用，无重复判定，无新增 any、断言、异步分支或异常吞没；文件 183 行，小于 300 行。task 与 slots 同来自 `components/use-task-detail.ts:18`、`:45` 的同一 data，切换任务清空旧 data（`:32`），不存在本次引入的模式/数量分离状态。
- 安全扫描：扫描 TaskDetail.vue 与 ResultCard.vue 中 eval、innerHTML、dangerouslySetInnerHTML、VITE 密钥变量、已知 API key 前缀，未命中；本次新增 `TaskDetail.vue:9`、`:10`、`:85` 均为 Vue 条件与固定文本，无输入执行、SQL、密钥或新增绝对路径。
- 测试真实性：原始 `output/text-whole-ui-tests.txt:203` 为 197/197。抽查 `hengxin-smart-image/frontend/tests/api-image-version-preview.test.ts:15`、`:42`，明确属于 API 图编辑预览状态测试，不能证明共享 TaskDetail 的按钮 DOM；本轮按钮条件与画布可达性由两份实际浏览器日志补足。日志记录真实页面导航、按钮点击、canvas 与弹窗正文，不只是孤立布尔表达式。
- LOW 验证边界：没有新增自动化单测锁定 showWholeRevision；浏览器为隔离 mock，历史多图回归确认入口存在，未执行真实后端返工或付费生成。对未改提交逻辑不作新一轮端到端成功承诺。
- LOW 视觉证据边界：独立目视打开本轮单图详情截图；也打开已有 `output/text-cli-neighbor.png`，其为既有画布弹窗，可确认共同按钮色彩与控件风格，但不能代替同版壁纸/商品详情的并排视觉比对。邻居详情仅有本轮 DOM 回归，没有新截图；主 Agent 明确要求按现有证据结束、不重启浏览器。故未宣称完成同版邻居视觉验收。考虑本次没有布局/CSS变更（TaskDetail.vue:9、:10），此边界作为非阻断项记录。

## 编译与验证原始输出

reviewer 已读取主 Agent 的完整日志。根目录 `output/text-whole-ui-build.txt:3`、`:10`、`:424` 原文：

```text
> hengxin-smart-image-frontend@0.2.11 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4480 modules transformed.
✓ built in 29.41s
```

构建有 pnpm 配置警告及 dingtalk-login 静态/动态重复导入提示（`output/text-whole-ui-build.txt:1`、`:12`），不宣称零警告。恢复自动生成 components.d.ts 后主 Agent 再运行 `pnpm exec vue-tsc --noEmit` 返回 0，原始 `output/text-whole-ui-typecheck.txt:1` 只有：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
```

测试原文（`output/text-whole-ui-tests.txt:203`）：

```text
ℹ tests 197
ℹ suites 0
ℹ pass 197
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 3905.6167
```

浏览器原始计数（完整正文及执行脚本保留在 `output/text-whole-ui-browser-single.txt:2`、`output/text-whole-ui-browser-regression.txt:2`）：单图 whole=0、canvas=1；壁纸、商品、历史四图文字 whole 各为 1。没有用测试总数替代这些直接行为证据。

结论：当前 candidate 本次范围 Stage 1 PASS、Stage 2 PASS；无阻断问题，两个 LOW 验证边界如上。只写报告，未修复、未提交、未部署、未写 clean。主 Agent 应以此报告对同一 candidate 执行 review-approve，再用 review-status 确认交付匹配。
