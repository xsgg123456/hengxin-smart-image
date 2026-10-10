# CLI 预览并发文案增量审查

日期：2026-10-10。审查角色：code-reviewer；使用 `.agents/skills/code-review/SKILL.md`。

- candidateId：`60ef436c1af3e94a5b9f7a9f71e764116ab555788546e5894686825aa372c844`。
- **Stage 1：PASS；Stage 2：PASS。**
- 范围：`hengxin-smart-image/frontend/src/views/hengxin/admin/preview/MonitorPreview.vue`、同目录 `SettingsPreview.vue` 的 CLI 容量与快照提示文案，以及 `docs/MANAGEMENT-API-PREVIEW-20261010.md:18` 的核查记录。下文两组件简称均指上述完整路径。
- 承接已批准快照 `36733de102400ffdc1139f06564d6e0222e99790411a1045acd739df3f88f3f8` 与 `docs/MANAGEMENT-API-PREVIEW-REVIEW-20261010.md`；未变化的统计、权限、隔离、交互测试与设计结论沿用该报告。本次不重复批准生产能力或部署。
- 独立 `review-status` 确认当前编号与送审编号相同，较已批准版本仅上述两个 Vue 文件改变。审查期间未修改业务代码。

## Stage 1：Spec Compliance

依据 `Product-Spec.md:930` 指向的专项预览文档及其第 18 行新增核查口径，逐项结果如下。

| 条目 | 证据与结论 |
|---|---|
| 监控容量由 1 修正为 5 | 完整实现。`MonitorPreview.vue:99` 为全站最多 5 个 CLI 图片修改轮次，明确 2026-10-10 16:19 核查快照。`MonitorPreview.vue:35` 实际绑定该说明。 |
| 配置页容量一致 | 完整实现。`SettingsPreview.vue:47` 值为“全站最多 5 个执行轮次”，说明生效并发与节点容量均为 5。 |
| 区分全站容量、同图串行与 API 任务并发 | 完整实现。`MonitorPreview.vue:99`、`SettingsPreview.vue:47` 均明确同一图片会话串行，并与 API 任务并发区分。`MonitorPreview.vue:102` 模拟运行 1 个不构成容量 5 的矛盾。 |
| 核查快照与实时/模拟数据边界 | 完整实现。`SettingsPreview.vue:7、18、47` 明确只有并发为已核查快照，其余为示例，不实时读取或修改生产。`MonitorPreview.vue:7、14、99` 分别限定模拟状态/任务与容量快照。 |
| 源文档同步、范围隔离 | 完整实现。`docs/MANAGEMENT-API-PREVIEW-20261010.md:18` 记录纠错、时间与生产未变更；该新增明确条目限定前文通用“全部模拟”口径。代码仍为本地常量、computed 与定时刷新（`MonitorPreview.vue:86、113`；`SettingsPreview.vue:46、57`），未新增调用或保存。 |

生产数值来源为主 Agent 提供的本轮只读核查：管理设置 concurrency=5、有效配置 generation_concurrency=5、Worker 心跳 capacity=5/concurrency=5、24 条已存在轮次冻结 concurrency 均为 5。审查者未再次连接生产；本报告核验预览与该核查材料一致，不声称独立重测生产调度。

部分实现、未实现、Spec 漂移：本次增量范围内无。未发现 HIGH/MEDIUM 问题。

## Stage 2：Code Quality

- 代码质量：PASS。两文件分别 118 行和 62 行；修正为展示字符串，不改变类型、控制流或组件结构，未引入 any（`MonitorPreview.vue:99`；`SettingsPreview.vue:7、18、47`）。
- 安全：PASS。对两文件扫描 eval、innerHTML、v-html、dangerouslySetInnerHTML、密钥模式、fetch 与 axios 无命中；实际 import 与刷新函数无生产请求（`MonitorPreview.vue:65、113`；`SettingsPreview.vue:37、57`）。
- 测试证据：已读取此次 `output/playwright/management-preview/cli-capacity-typecheck.log`；主 Agent 记录该命令退出 0，并已通过真实浏览器监控段落与配置值 waitFor 验证。旧完整行为测试仅作为未改变行为的基线，不冒充此次生产并发测试。
- 视觉：独立通过 Playwright CLI 对当前系统配置页面截图 `output/playwright/management-preview/cli-capacity-review.png`，目视确认最新提示、容量 5 和快照说明实际渲染，说明自然换行，无文字重叠。与既有真实邻居页面截图 `output/playwright/management-preview/baseline.png` 对照，标题、侧栏、页签、白色卡片、蓝色控件及表格字体保持一致。结构证据为 `SettingsPreview.vue:2–22`。监控组件只替换脚注字符串，沿用 `MonitorPreview.vue:35` 的普通段落呈现；本轮未重拍监控及窄屏，不扩大此前视觉验收结论。

## 原始编译证据

本轮类型检查日志原文如下；退出 0 由执行该检查的主 Agent 提供，审查者独立读取日志内容：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.

> hengxin-smart-image-frontend@0.2.19 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

本次未重跑完整构建；此前构建、全套单测与浏览器证据见前序报告，不能视为生产部署。由主 Agent 对上述 candidateId 登记两阶段 PASS；本报告未执行 review-approve，未写 `.needs-review`，未提交代码。
