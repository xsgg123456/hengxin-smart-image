# 管理中心 API 统计交互预览独立审查

日期：2026-10-10。审查角色：code-reviewer；依据 `.agents/skills/code-review/SKILL.md`。

## 快照与范围

- 初始 candidateId：`cff0b038b13e49c3d76f587d3eb61b4c0b6ca7ee4e6940451ab8521587d5aef4`。
- 中间 candidateId：`46ea30639c983815c7c5497e9d13e07ccee25bf5e0638320ef5e4e2c6222d727`。审查期间补充统计测试，并检测到自动生成的组件声明变化；已通知主 Agent并复核处理。
- **最终 candidateId：`36733de102400ffdc1139f06564d6e0222e99790411a1045acd739df3f88f3f8`。Stage 1：PASS；Stage 2：PASS。** 以下最终结论只适用于此快照。
- 最终增量复核：`961fb942429b8588ee655707fb30e90367f941a9b21b590003eaab86a928157d` 之后，主 Agent 仅在 `UsagePreview.vue:108–111` 窄屏媒体查询内增加 `.hx-admin-query-row > .el-button { margin-left: 0; }`，消除 Element Plus 相邻按钮外边距导致的重置按钮偏移。已核读该差异、重跑后的类型检查与 browser-layout.log；自动生成声明再次恢复 HEAD 后固定上述最终候选。中间 `f85250f8d6a2d1a8bb5d3a0659fb885a4207573c715323fe1564596f0f900fe2` 不获批准。
- 范围：`hengxin-smart-image/frontend/src/router/management-preview.ts`、`src/router/modules/index.ts`、`src/views/hengxin/admin/preview/` 四文件、`tests/management-preview.test.ts`。以下代码路径均相对于 `hengxin-smart-image/frontend/`。
- 源文档：完整读取 `docs/MANAGEMENT-API-PREVIEW-20261010.md`；承接 `Product-Spec.md:930`、`DEV-PLAN.md:1094` 与 `Design-Brief.md:79、81、119`。既有 dev-builder skill 修改不属于本轮复审。
- 仅审查本地 mock 预览；不批准生产统计、后端整改、部署、提交或生产清理。
- 表格内 `UsagePreview.vue`、`MonitorPreview.vue`、`SettingsPreview.vue`、`usage-data.ts` 均指 `src/views/hengxin/admin/preview/` 下同名文件。

## Stage 1：Spec Compliance

**PASS。** 专项源文档全部条目已对照，未发现剩余 HIGH/MEDIUM 不匹配；桌面与窄屏证据齐备。

| Spec 条目 | 实现与证据 | 结论 |
|---|---|---|
| 1：复用正式侧栏、页头、页签、卡片、主题与控件 | `src/router/modules/index.ts:31–42` 保留原父布局；`UsagePreview.vue:2–38`、`MonitorPreview.vue:2–45`、`SettingsPreview.vue:2–32` 使用 hx-page、art-card、Element Plus。既有 `src/views/hengxin/prototype.css:3–5、38–58、75–76` 提供标题、卡片、筛选与响应式。独立查看 baseline.png 对照新 usage.png、consumption.png、monitor.png，侧栏、页签、字体、蓝色主按钮、卡片圆角匹配。 | 完整实现 |
| 2：业务成果与执行消耗分别计数 | `UsagePreview.vue:24–35、85–95` 分页签展示；`usage-data.ts:5–9、46–51` 分离任务、图片、API 尝试、重试、CLI 轮次、版本、采用。独立执行得到 52 任务、376 当前图片、394 版本、385 采用、435 请求、42 重试、9 CLI 轮次，与最终截图一致。 | 完整实现 |
| 2：日期、人员、执行类型、分页、汇总不随分页 | `UsagePreview.vue:15–20、38、75–84、98–100`；`usage-data.ts:42–74` 在分页前筛选聚合。`tests/management-preview.test.ts:30–50` 核验人员、时间、类型与逐行汇总守恒。分页仅 slice 展示行，汇总无 page 依赖。 | 完整实现 |
| 2：人员每日展开、关联 API 任务预览 | `UsagePreview.vue:41–61、96–102` 为嵌套本地抽屉；每日行保留开始/产出/采用日期；任务概览声明完整历史范围。没有真实图片或生产详情请求。 | 完整实现 |
| 3：API 与 CLI 分渠道监控、状态与心跳 | `MonitorPreview.vue:14–35、68–112` 实现排队、运行、重试等待、收图、异常、心跳；正常/异常/未知/空闲独立。`count()` 在 unknown 下返回“未知”，idle 下才返回 0。`browser-monitor.log` 实际断言四个未知卡片均为“未知”。 | 完整实现 |
| 3：任务本地详情 | `MonitorPreview.vue:38–61、109–112` 仅本地 Incident，说明不触发生成/重试/采用；`browser-monitor.log` 实际打开异常任务抽屉。 | 完整实现 |
| 4：只读 API/CLI 作用范围与保留策略 | `SettingsPreview.vue:10–31、41–55` 分别说明准入、图片并行、轮次并发和时限；1 天私有缓存/插件、7 天会话过程、正式图片/必要素材保留；统计摘要标为拟议。无保存按钮或写接口，刷新仅本地 timer（57–61 行）。`browser-monitor.log` 验证无生产保存入口。 | 完整实现 |
| 5：权限、角色、Skill 沿用，管理员模拟个人 | `src/router/modules/index.ts:31–42` 保留父级 super_admin/design_manager 和子级限制；`UsagePreview.vue:8、16、71–76、102` 管理员切换模拟设计师甲，个人视角不显示人员筛选。没有给普通角色解锁管理中心。 | 完整实现 |
| 5：北京时间与独立事件日 | `UsagePreview.vue:3、13、43、47、52` 明确日期口径；`usage-data.ts:31–32、55–71` 对创建/执行/产出/采用分别过滤聚合；10 月 1 日创建和执行非零但版本/采用为 0，10 月 2 日才有版本、10 月 3 日才有采用，由测试证明。 | 完整实现 |
| 5：库存和历史发生量、成功率和待核实分开 | `UsagePreview.vue:20、28–30、83–94` 注明库存仅按人员变化；请求成功率使用成功/已知请求，图片交付成功率使用交付/已知图片，未知单列且不进分母。`usage-data.ts:58` 库存无日期过滤；测试覆盖未来空日期仍保留 52 套库存。 | 完整实现 |
| 5：无 Token/费用回执显示未提供 | `UsagePreview.vue:4、30、58`、`MonitorPreview.vue:57`，未把缺失值显示成 0 或猜测费用。CLI 内部请求明确未提供（UsagePreview.vue:29、52）。 | 完整实现 |
| 6：明确模拟、加载/空/错误可交互 | 三页页首都明确模拟/只读；`UsagePreview.vue:21–22、73–82` 提供 skeleton、空记录、错误重试；`check-usage.js` 覆盖人员、CLI、个人、空/错误重试/加载。52/376 明确是模拟快照，无生产实时声明。 | 完整实现 |
| 范围隔离与 Spec 漂移 | `src/router/management-preview.ts:2–7` 要求 MODE=mock 且 managementPreview=api；其他模式或无参数返回原组件，users/skills 不受替换。`tests/management-preview.test.ts:6–16` 覆盖 production/development/demo/undefined 与原管理页回退。git diff 中无后端/正式管理页改动。 | 无未授权业务扩展 |

未实现或部分实现：本轮授权预览范围内未发现。`output/playwright/management-preview/browser-layout.log` 记录真实日期输入、未来空区间库存保留、480px 抽屉关闭、700px 监控；页面 clientWidth/scrollWidth 分别 450/450、660/660。已独立目视 usage-mobile.png、usage-narrow.png、monitor-narrow.png、settings-narrow.png，窄屏控件换行、卡片和表格文字可读。生产真实能力属于另行实施范围。

## Stage 2：Code Quality

**PASS。** 已发现问题完成修复及证据替换，没有剩余阻断问题。

审查期间提出并处理的问题：

1. **MEDIUM，已修复**：初始测试仅验证路由，无法证明核心统计语义。主 Agent 在 `tests/management-preview.test.ts:18–50` 增加请求守恒、CLI 独立计数、无产出/采用时日期为空、每日聚合与顶部守恒、人员/日期/类型过滤、跨日归属、未来无事件时库存不消失。独立运行 3 项全部通过。
2. **证据失效，已替换**：初始 usage/consumption 截图为旧数据（443/443、17 CLI），不能代表候选。已重新读取新截图并对照独立计算的 394/385、9 CLI、42 重试。
3. **快照范围变动，已解决**：检测到 `src/types/import/components.d.ts` 自动生成差异，主 Agent 恢复 HEAD 原内容后重新固定最终快照；独立运行 `git diff --exit-code -- hengxin-smart-image/frontend/src/types/import/components.d.ts` 无输出、退出 0。最终 `review-status` 当前编号与最终 candidateId 一致，变化范围恢复为七个送审文件。业务逻辑在审查中未再改变；补充测试和最后的窄屏按钮 CSS 已独立复核。

代码质量检查：

- 类型与职责：`usage-data.ts:1–11、46–77` 定义指标和纯聚合，页面承担呈现；其余两页纯本地只读状态。送审文件各自小于 300 行，无显式 any。`UsagePreview.vue:98` 筛选变更重置页码并关闭旧详情，避免 stale 详情。
- 生命周期：`MonitorPreview.vue:113–117`、`SettingsPreview.vue:57–61` 清理 timeout；无长期订阅或请求。
- 安全扫描：对全部送审源文件扫描 eval、innerHTML、v-html、硬编码 key/token/password 等模式，无命中；逐个检查 import 和事件回调，无 fetch/axios/生产客户端调用、字符串 SQL 或原始命令执行。路由必须双条件 opt-in，普通 URL 参数不能切换生产页面。
- 测试真实性：统计测试基于实际确定性事件，用跨指标守恒和跨日不同数值约束结果，不以不可达输入伪造通过；故障/交互层由真实 Playwright 场景补齐。生产 API、真实权限后端、真实心跳未在预览中验证，也不在本轮范围。
- 视觉：已独立比较原管理页与调用统计/监控真实渲染截图，配置路由淡入期间旧截图已替换为稳定页面截图；窄屏 480/700px 截图与浏览器尺寸断言通过。原有标题 28px/窄屏 24px、卡片数值 27px、16px 网格间距及 Element Plus 蓝色控件来自 `prototype.css:4、32、48–52`，没有另造主题。

## 原始验证输出

独立运行 `pnpm typecheck`，exit_code=0，stdout：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.

> hengxin-smart-image-frontend@0.2.19 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

独立运行 `pnpm exec tsx --test tests/management-preview.test.ts`，exit_code=0，原始输出：

```text
✔ management preview requires both explicit mock mode and opt-in query (0.7366ms)
✔ preview events preserve counts and separate CLI rounds from API attempts (0.4286ms)
✔ daily summaries reconcile and event dates remain independent (3.177ms)
ℹ tests 3
ℹ suites 0
ℹ pass 3
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 289.2162
```

主 Agent 全套测试原始日志 `output/playwright/management-preview/unit-tests.log`，已读取：

```text
ℹ tests 224
ℹ suites 0
ℹ pass 224
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 4737.5499
```

监控浏览器日志 `output/playwright/management-preview/browser-monitor.log` 原始结果：

```json
{"passed":true,"checks":["monitor four states","unknown not zero","incident drawer","refresh loading","settings read-only"],"unknown":["未知","未知","未知","未知"]}
```

主 Agent 预览构建原始日志 `output/playwright/management-preview/build.log`，已读取命令和结尾：

```text
> hengxin-smart-image-frontend@0.2.19 build:preview D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vite build --mode mock --outDir dist-preview
vite v7.1.7 building for mock...
✓ built in 41.37s
```

最终窄屏 CSS 调整后再次运行类型检查，`typecheck-final.log` 仍为 `vue-tsc --noEmit` 且主 Agent 记录退出 0；browser-layout.log 也重新通过。构建日志属于最后一条局部 CSS 调整之前，最终 CSS 已经 mock 开发服务实际编译呈现。预览构建通过不等于生产部署。

统计交互日志 `output/playwright/management-preview/browser-usage.log` 的原始结果：

```json
{"passed":true,"checks":["person filter","CLI filter","personal scope","empty","error retry","loading"],"person":"新建任务\n18\n所选期间 · 创建事件\n历史生成版本\n137\n所选期间 · 产出事件\n历史采用记录\n134\n所选期间 · 采用事件\n当前图片库存\n130\n当前快照 · 仅按人员过滤","cli":"API 请求尝试\n0\n含首次请求与重试\n其中失败重试\n0\n包含在请求尝试内\nCLI 修改轮次\n9\n不换算模型内部请求\n执行记录数\n9\n首次、修改与 CLI 执行"}
```

布局交互日志 `output/playwright/management-preview/browser-layout.log` 原始结果：

```json
{"passed":true,"checks":["date filter via input","empty historical range preserves inventory","480px drawer close","700px monitor"],"layout":{"client":450,"scroll":450},"monitor":{"client":660,"scroll":660}}
```

本报告不登记 review-approve，不写 `.needs-review`。由主 Agent 为上述最终 candidateId 登记两阶段 PASS；不得据此批准其他快照或宣称生产整改完成。
