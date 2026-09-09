# Phase 8 Task 3 前端独立审查

2026-09-09。使用 `.agents/skills/code-review/SKILL.md`。本报告只审前端 Task 3；后端数据库、Worker、取消屏障由主 Agent 验收。未把既有 Phase 6/7 模板历史与 Skill 管理改动当成本轮新增。

**结论：Stage 1 不通过，1 项 HIGH；Stage 2 未执行。** 组件存活期间的请求恢复正确，但实际 401 登录链路会卸载组件并遗失幂等键及用户输入。浏览器集成与视觉截图尚未提供，未宣称通过。

## Stage 1：问题

### HIGH F8-001：401 卸载表单后丢失待确认请求，重新登录可产生重复任务

- 标准：Product-Spec.md:105、270 要求重复请求不重复创建、保留意见；PHASE8-PLAN.md:7 要求网络不确定时不换键重复新建，错误表单保留。派发材料明确要求 401 不清除既有 uncertain 状态。
- 代码证据：`frontend/src/views/hengxin/task-submission.ts:7` 的 accepted/uncertain/pending 和第 8 行 attempt 全是实例局部状态；`frontend/src/views/hengxin/use-create-task.ts:12` 每次挂载新建实例，第 16 行草稿同样仅存于实例。
- 生产触发链：`frontend/src/api/hengxin/http.ts:22` 收到 401 派发 unauthorized；`frontend/src/main.ts:43`–51 设置 bootstrap.ready=false、authRequired=true 并清工作标签；`frontend/src/App.vue:10`–13 将 RouterView 替换为登录页。表单及其请求状态被卸载。相同用户重新认证后，原键、原快照和编辑意见均无恢复来源。
- 复现步骤：① POST 已入库但响应丢失，uncertain=true；② 确认原请求时登录过期返回 401（或其他业务查询触发同事件）；③ 重新登录同用户；④ 重新输入相同内容提交。新实例生成新 UUID，服务端按不同新请求受理，不能利用旧键返回原任务。
- 独立运行最小复现：第一次 `useTaskSubmission` 的 send 抛 UNAVAILABLE；用相同输入创建第二实例并提交，模拟上述卸载/重建。原始输出：

```json
{"beforeUnmountUncertain":true,"afterRemountUncertain":false,"originalKeyPreserved":false,"postCount":2}
```

- 测试盲区：`frontend/tests/task-submission.test.ts:73`–82 直接抛 ApiError，在同一个实例继续调用；既没有执行 HTTP 401 事件，也没有卸载/重新挂载，不能证明“重新认证”安全。现有用例通过不反驳本缺陷。
- 修复验收：将待确认原请求、已受理回执和草稿放入可跨认证卸载恢复的状态层，按可信操作者和入口隔离；同用户重新认证保留原键，其他用户不显示或重放前一用户草稿。补真实 401 事件导致表单卸载/重建的回归。页面刷新恢复是否纳入范围由主 Agent依当前验收边界决定，不能用刷新测试替代此必现认证链路。

## Stage 1：逐项覆盖

以下“代码匹配”只表示静态实现与注明的测试范围匹配，不代表浏览器或后端全链路验收。

| 需求 / 本阶段条目 | 结论 | 证据与验证边界 |
|---|---|---|
| REQ-003 三入口、壁纸/商品需模板，文字无需模板且需意见 | 代码匹配 | `frontend/src/views/hengxin/use-create-task.ts:21`–24、32–34、69–77；`components/CreateTask.vue:7`、28。三入口浏览器真实提交待集成证据。 |
| REQ-003 名称必填、SKU 可选 | 代码匹配 | `use-create-task.ts:69`–77；`components/CreateTask.vue:26`–28。未新增约束或字段。 |
| REQ-003 空文件、可读类型、10 MiB、每组 20 张 | 既有实现匹配 | `frontend/src/views/hengxin/use-image-upload.ts:67`–70、88–99；`frontend/src/api/hengxin/limits.ts:1`–3。提交由 uploadBlocked 阻断未 ready 图片，`use-create-task.ts:23`。 |
| REQ-003 输入/模板/Skill 快照 | 前端传输匹配；服务端另验 | `use-create-task.ts:75`–77 传模板版本、Skill、来源副本；`task-submission.ts:12`–17 保存发送快照；首次发出后修改输入不改变原请求，独立测试通过。服务器真正冻结版本未在本报告验收。 |
| REQ-003 / 9.2.2 同键重放、不确定不换键 | **部分实现 / HIGH** | `task-submission.ts:14`–24 在单实例内正确；组件重建缺陷见 F8-001。 |
| 202 只受理，不同步等待生成或详情读取 | 代码及隔离测试匹配 | `frontend/src/api/tasks.ts:3` 直接返回 POST；`frontend/src/api/hengxin/http.ts:75` 显式发送 Idempotency-Key；`use-create-task.ts:75`–79 收回执直接导航；`tests/task-submission.test.ts:35`–54 POST 成功后 GET 失败不再 POST。浏览器路由读取失败待集成验证。 |
| 已受理回执仅显式另建释放 | 单实例匹配；跨卸载同 F8-001 | `task-submission.ts:10`、32–34；`components/CreateTask.vue:39`–41 提供查看回执/另建任务，已有回执禁提交。 |
| 网络错误保留输入及编辑意见 | 单实例匹配；认证错误不匹配 | `use-create-task.ts:80`–82 只写 error，不清输入；`task-submission.ts:28`–30 从旧快照确认，不覆盖当前编辑；401 导致输入整体卸载见 F8-001。 |
| REQ-004 全员查询、分页、筛选及逻辑删除入口 | 代码匹配；四角色/审计后端另验 | `frontend/src/views/hengxin/components/use-task-list.ts:18`、20–22、32–33；`components/Tasks.vue:19`、44–54 无 owner/role 前端限制，危险删除确认；`frontend/src/api/hengxin/http.ts:55`–57；删除回执守卫 `validate.ts:80`–81。 |
| REQ-004 真实状态及结果展示、独立查询 | 代码匹配；文件可读性浏览器另验 | `components/use-task-detail.ts:15`–25、36；`components/ResultCard.vue:3`–11 从版本 URL 渲染并有图片加载错误；`validate.ts:54`–56、63–70 校验槽位和当前版本引用。未将 URL 字符串存在等同于实际图片已可读取。 |
| REQ-004 关闭页面/退出不取消已提交任务 | 前端代码匹配；后台续跑另验 | `components/use-task-list.ts:35`–36、`components/use-task-detail.ts:34` 清计时器而不 DELETE；删除仅由 `components/Tasks.vue:44`–49 用户确认触发。 |
| 3/10 秒轮询及离开停止 | 代码与延迟策略测试匹配 | `frontend/src/views/hengxin/task-state.ts:3`；`components/use-task-list.ts:28`、35–36；`components/use-task-detail.ts:25`、29–34；`tests/task-submission.test.ts:94`–95。真实计时与切页行为待浏览器证据。 |
| 9.2.1/5 忙碌与待核实禁止返工/重试 | 代码及 DTO 测试匹配 | `frontend/src/types/hengxin.ts:138`–139 必需 executionControl；`validate.ts:65`–67 拒绝缺失/错误布尔；`task-state.ts:6`–10 取服务端能力；`components/TaskDetail.vue:12`、16、50–60 展示原因并双重阻断；失败状态不会自行开放操作。 |
| fixture 来源与真实功能引导 | 代码匹配 | `task-state.ts:4`–5；`components/Tasks.vue:15` 测试任务标签；`components/TaskDetail.vue:11` 测试警告；真实归档在第 8、80 行双重禁用，9 行解释后续开放；`components/CreateTask.vue:43`–45 区分真实与模拟文案。 |
| 原布局 / 长文本 UI | 静态复用，实际未验 | `components/CreateTask.vue:5`、32；`components/TaskDetail.vue:2`、18 保持既有卡片/抽屉/结果网格；`frontend/src/views/hengxin/prototype.css:7`、22–23、30–33 保持 300px 摘要、22px 间距及响应断点。无新截图，长任务名/模板名、长意见、测试标签、禁用原因是否溢出未验。 |
| 角色变化 | 读取入口代码匹配；身份恢复不匹配 | `components/Tasks.vue:19` 全员同入口；`frontend/src/main.ts:53`–65 切身份清 UI，防旧身份视图沿用。提交恢复必须增加操作者隔离，见 F8-001。四角色真实用例尚未取得。 |
| 9.2.3/4/6 数据库原子认领、旧执行屏障、持久取消 | 本报告不代验后端 | 前端仅在 `http.ts:55`–57 查询/删除。主 Agent须以实际 Worker/PG 证据覆盖，不能从前端按钮锁推导完成。 |
| CLI 会话隔离、用户返工、归档 | 按阶段未实现，不记缺陷 | DEV-PLAN.md:291 起为 Phase 9 CLI，Phase 10 用户返工、Phase 11 归档；当前前端展示后续开放及服务器禁用能力，未发现本轮新增虚构已生成引导。 |

未发现本轮新增页面或业务范围漂移；模板历史与 Skill 默认绑定属于既有 Phase 7，不作 scope creep。

## 测试与编译证据

本审查独立运行 `D:/Apps/nodejs/node.exe node_modules/tsx/dist/cli.mjs --test tests/task-submission.test.ts`，退出码 0，原始输出：

```text
✔ 响应丢失后重放同键原快照，变更输入保留且不能静默创建第二任务 (21.4646ms)
✔ 202 后详情读取失败仍保留原任务 ID，不再次 POST；重复点击不并行受理 (21.8429ms)
✔ 明确校验拒绝后编辑采用新键；503 不伪成功且不清空表单 (0.5858ms)
✔ 不确定请求重放被401拒绝仍须保留原键，不能因重新认证静默重复创建 (0.333ms)
✔ 操作资格坏 DTO 拒绝；失败状态不能覆盖服务端禁用，fixture 与轮询来源准确 (7.8718ms)
✔ 模拟同键重放只创建一个任务，同键异内容拒绝且保留返工资格 (62.7662ms)
ℹ tests 6
ℹ suites 0
ℹ pass 6
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 513.0605
```

另读取实现者已有 `frontend/phase8-test.log`，没有在本次重新跑全部 47 项；日志原文末段：

```text
ℹ tests 47
ℹ suites 0
ℹ pass 47
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1663.2752
```

读取 `frontend/phase8-build.log`，未在本审查重新编译或独立跑类型检查。可观察的 Vite 构建原始输出摘录（完整原文保留于该日志）：

```text
🚀 API_URL = /api/v1
🚀 VERSION = hx-frontend-1
vite v7.1.7 building for production...
transforming...
✓ 3302 modules transformed.
rendering chunks...
[plugin vite:reporter]
(!) D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/views/auth/dingtalk-login.vue is dynamically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/core/ComponentLoader.ts, D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/router/routes/staticRoutes.ts but also statically imported by D:/Work_Project/hengxin-smart-image/hengxin-smart-image/frontend/src/App.vue?vue&type=script&setup=true&lang.ts, dynamic import will not move module into another chunk.
✓ built in 29.15s
```

## Stage 2 状态

**未执行。** Stage 1 存在 HIGH，按技能要求停止；不输出代码质量、安全扫描或邻居页面视觉比较“通过”结论。修复 F8-001 后从 Stage 1 重审，并取得浏览器三入口、错误恢复、四角色、结果下载与长文本截图证据后才能进行最终验收。
