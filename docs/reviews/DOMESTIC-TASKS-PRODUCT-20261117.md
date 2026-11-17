# 国内任务产品代码两阶段审查

审查日期：2026-11-17。独立 reviewer，仅审查、运行隔离测试和记录证据；未修复实现、未提交、未登记批准。

## 快照与范围

- 初始 candidateId：`c23cdb297170bc6348baf72114f1887bd1556417ff23e46c49aaeefc6f2d80ec`。开始时 `harness.py review-status` 的 currentId 与此一致。
- 最终 candidateId：`bdc78af52f5564caa852690e03d2626b14a94ce73ff07e295256dcc2bff51fe5`。最终 `review-status` 的 currentId 已独立核对一致。
- 最终产品范围内容复核：64 个变更文件，与补强测试后已审文件逐文件 SHA256 相同，差异列表 `[]`；有序文件摘要集合 SHA256 为 `a542e3b3939793a17d5cf5a37e47eff426365992b8b8065840dbe7c0868acc74`。此结论仅覆盖下述产品范围，不批准发布工具。
- 范围：相对 HEAD 的全部 `hengxin-smart-image/backend`、`hengxin-smart-image/frontend` 修改及新增源码/测试；`frontend/preview-task-center` 作为确认设计参考。包含新增 0044；不审 `scripts/release/intranet`，该范围由另一 reviewer 负责。三个 auth 文件仅 CRLF 状态噪音，无内容差异。
- 需求：`Product-Spec.md:1` 最新任务迭代全部条目；设计：`Design-Brief.md:1`、确认预览；计划：`DEV-PLAN.md:1` 步骤 1–3 及步骤 4 的产品测试/构建部分。
- 审查中主 Agent 修改 `backend/app/modules/domestic_studio/task_queries.py` 和 `backend/tests/test_domestic_tasks_pg.py`，修复本报告发现的计数问题、补强恢复请求负例；已重新读代码并运行测试。发布工具并行修复及 `components.d.ts` 生成噪音另有变化。主 Agent 重新固定最终快照后，本 reviewer 已重新核对产品内容，无未审产品改动；发布工具由其独立 reviewer 复核。

以下代码路径前缀：**B = `hengxin-smart-image/backend/`；F = `hengxin-smart-image/frontend/`**。每项均给出相对此前缀的真实文件与行号。

## Stage 1 · Spec Compliance

**结论：PASS（仅本报告产品范围，绑定最终 candidateId）。** 初始快照发现 1 项 MEDIUM，未发现 HIGH。计数修复已复核，当前无未解决的功能问题。

### 已修复的问题

**S1-M1：状态标签汇总被当前状态筛选清零，与确认交互不一致。**

- 需求/设计证据：`Design-Brief.md:5` 要求状态汇总；`F/preview-task-center/TaskPreview.vue:8` 的三个状态按钮各自计算范围内数量，不随当前状态清空其他按钮。
- 原实现：`B/app/modules/domestic_studio/task_queries.py:45` 的 listing 在计算 counts 前应用 status。隔离真实 API `GET /api/v1/management/domestic-studio/tasks?status=completed`，7 个进行中任务时返回 `{"total":0,"counters":{"total":0,"active":0,"completed":0}}`。浏览器 mock 在 `F/tests/workspace-sessions.browser.mjs:40` 先计数后过滤，因此原浏览器通过不能证明真实后端此行为。
- 修复：同文件 `:54` 先按成员/业务/名称计算 counts，再对列表应用 status；total 使用最终状态数。`B/tests/test_domestic_tasks_pg.py:87` 经真实 HTTP 验证普通/管理两入口，并加入其他成员、业务、名称的干扰数据。独立复跑通过，计数始终 `{total:2,active:1,completed:1}`，状态筛选后的列表 total 为 1。

### 逐条需求核对

| Spec 条目 | 结论与实现证据 | 验证证据 |
|---|---|---|
| 成员→多个任务→多个独立方案；五业务固定绑定 | 完整。`B/app/modules/domestic_studio/task_models.py:11`、`conversation_models.py:26` 的 owner/workspace 复合 FK；`turn_service.py:19` 的附件/图片按 conversation 校验 | `B/tests/test_domestic_tasks_pg.py:61` 跨任务读、上传、文件 URL、轮次操作拒绝；独立 PG 重跑 |
| 三角色业务菜单首先看本人任务 | 完整。`F/src/router/modules/index.ts:12` 保留五业务入口；`views/hengxin/domestic-studio/workspace.vue:1` 接 TaskPage；`B/app/modules/domestic_studio/task_router.py:16` 强制 actor.id | `F/tests/business-route-access.test.ts:46`；真实列表只返回当前 owner，普通直访管理返回 403 |
| 名称/状态筛选、分页、空态、新建/进入/重命名 | 完整。`F/src/views/hengxin/domestic-studio/TaskList.vue:3`、`TaskPage.vue:52`、`use-tasks.ts:33`；`B/app/modules/domestic_studio/task_queries.py:45` | 真实 HTTP CRUD/筛选；浏览器分页、搜索、返回保留筛选报告 `output/playwright/task-manager/report.json` |
| 名称 1–60 字符，业务固定，创建不执行 AI、不创建空会话 | 完整。`B/app/modules/domestic_studio/task_schemas.py:9`、`task_service.py:56` 只建 Task/receipt；`F/src/views/hengxin/domestic-studio/TaskPage.vue:25` 业务禁用输入 | `test_domestic_tasks_pg.py:36` 验证空/空白/超长/控制字符及 zero conversations；真实浏览器由 0 显式创建到 2 个方案 |
| 每任务最多 10 个方案，显式新建 | 完整。`B/app/modules/domestic_studio/conversation_service.py:72` 按 task_id 计数；`F/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:82` 传 autoCreate=false | `B/tests/test_domestic_tasks_pg.py:138` 两任务各建 10 个，第 11 个拒绝；`F/tests/domestic-tasks.test.ts:120` 零会话不自动创建 |
| 多轮消息、草稿、附件、线程与结果独立 | 完整。`F/src/views/shared/studio/use-studio-sessions.ts:88` 每会话 controller；`studio-composer-draft.ts:16` actor/task/conversation 键；`B/app/modules/domestic_studio/queries.py:40` 任务列表隔离 | 五入口 15 次发送及两方案草稿/刷新；真实 API 接受发送 queued，回复由 fixture 模拟，未冒称真实模型调用 |
| 任务完成与执行状态分别展示；完成须空闲 | 完整。`TaskList.vue:6`、`TaskPage.vue:16` 分别显示任务状态/执行数量；`B/app/modules/domestic_studio/task_service.py:70` 检查 Job、Upload、output intent、archive、会话删除 | `B/tests/test_domestic_task_lifecycle_pg.py:25` 阻塞真实上传存储阶段，完成/删除均 409，释放后完成成功 |
| 完成只读、下载保留；重开后继续 | 完整。`task_service.py:26`/`:103`；`F/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:17`/`:28` 隐藏 composer、显示完成提示；文件 GET 不调用 writable | `test_domestic_tasks_pg.py:114` 新旧发送/改名/上传闭锁及 reopen；真实完成/重开浏览器证据由主 Agent 提供并核对实现 |
| 失败/断线保留原幂等键，不重复创建任务 | 完整。`B/app/modules/domestic_studio/task_service.py:45` receipt/body hash；`F/src/views/hengxin/domestic-studio/use-tasks.ts:63` sessionStorage 保存原请求，pending 阻止新操作 | 同 key 重复/异 body/并发 6 次只建一条；`F/tests/domestic-tasks.test.ts:71` 跨挂载恢复原 key |
| 危险操作确认，任务及会话可重命名/删除 | 完整。`F/src/views/hengxin/domestic-studio/TaskPage.vue:56`、`DomesticWorkspace.vue:124` 确认框；后端按版本和 owner 验证 | HTTP 乐观版本冲突、持久删除回执测试；任务不会仅从列表隐藏 |
| 删除无在途任务，清理成功才报告成功，失败可重试，归档保留 | 完整。`B/app/modules/domestic_studio/task_deletion.py:15` 必须无剩余 Conversation 且 manifest 全部 deleted；`conversation_cleanup.py:158` 完成实际文件擦除后 reconcile | `test_domestic_tasks_pg.py:183` store.remove 故障→delete_failed→重试；`test_domestic_task_lifecycle_pg.py:55` 实际本地目录消失、源对象净减少、独立 ArchiveFile 字节保留 |
| 管理中心唯一任务入口，在调用与执行之后；仅超管 | 完整。`F/src/router/modules/index.ts:25` 新菜单及旧地址隐藏重定向；`B/app/modules/domestic_studio/task_router.py:59` 使用 Admin 依赖 | 普通接口 403、撤权后 403；正式静态构建读取菜单和管理列表 |
| 管理全员筛选/分页，任何任务包括本人均只读 | 完整。`task_router.py:59` 只有 GET；`TaskPage.vue:18` 始终走 ManagedTaskWorkspace；`ManagedTaskWorkspace.vue:18` 只使用 useMonitor | 管理 API POST/PATCH/DELETE 均 405；mock 37 个请求全 GET；本人/他人管理详情无 composer/新建/完成入口 |
| 全部方案、完整已提交消息、真实 Skill、公开过程、附件结果、预览下载 | 完整。`B/app/modules/domestic_studio/admin_details.py:72`、`:96`；`admin_queries.py:81` siblings 只限当前 task；`F/src/views/hengxin/admin/workspace-sessions/SessionDetail.vue:10` | 独立重跑 admin PG：历史/过程分页、未提交上传隐藏、跨会话文件拒绝；浏览器文件与图片报告 |
| 自动同步/暂停/手动刷新、断线反馈、迟到响应隔离 | 完整。`F/src/views/hengxin/domestic-studio/use-tasks.ts:34` epoch；`admin/workspace-sessions/use-monitor.ts:25` epoch+AbortController；`ManagedTaskWorkspace.vue:22` | mock 故障、延迟后切换、恢复及 readonly 浏览器测试；`domestic-tasks.test.ts:55` 任务/筛选迟到响应 |
| 撤权清敏感内容；管理选择不改业务状态/线程/草稿 | 完整。`use-tasks.ts:25`/`:109`、`use-monitor.ts:13`/`:69`；管理后端仅 projection/audit | 暂停同步后的 identity.advance 立即清空；真实管理阅读前后 Task/Conversation/Turn/Job JSON SHA256 均 `41CBB2227A76922937BD32A6328CD5ED9A198B43366A41B4AC06522E14BBB379` |
| 旧个人接口不能绕过归属、业务或状态 | 完整。`B/app/modules/domestic_studio/task_scope.py:13`、`conversation_service.py:29`；新路由 `router.py:183` 克隆原 handler/dependencies；旧 handler 最终也调用 channel_task | 新旧完成闭锁、跨 task 文件/轮次测试；archive 的新旧路由均在 `archive_router.py:22` 进入原 prepare 锁 |
| 历史按 owner+业务归到历史任务；ID/线程/文件/恢复凭据保持 | 完整。`B/migrations/versions/0044_domestic_tasks.py:49` 只按 owner/workspace 回填 task_id；原身份字段、目录、快照及恢复模块未改写 | `test_domestic_tasks_migration_pg.py:16` 真 PG 逐字段比较、分组/FK/重复升级拒绝；注意其中历史 payload 为隔离测试数据，不是生产历史验收 |
| 旧书签/页签/草稿兼容，不产生游离会话 | 完整。`F/src/router/modules/index.ts:25`、`TaskPage.vue:68` 恢复旧管理 session 对应 task；`task-storage.ts:7` 仅迁移服务端确认所属会话的 draft/pending；旧 create 无 task 返回 422 | 浏览器旧管理 session 地址恢复；`domestic-tasks.test.ts:101` 原 key/图片引用/附件改写及不覆盖；后端 legacy receipt 测试 |
| 沿用 Skill、上传、改图、取回、归档；海外/API换套图边界不扩张 | 完整。`F/src/api/shared/studio.ts:93` 显式 domestic-task 分支保持 overseas 默认；`DomesticWorkspace.vue:31`–`:39` 复用原组件；后端新路由只由国内 main 注册 | 前端 584 全套回归；后端国内文件/归档/恢复回归；未将 mock 回复等同真实模型结果 |
| 正式 UI 无预览身份/示例数据/演示回复；空态不作虚假引导 | 完整。`TaskPage.vue:5`、`ManagedTaskWorkspace.vue:7`；preview 只在独立 Vite input，正式路由不引用 | 实际静态生产构建页面已检查；展示的“隔离联调回复”来自明确 fixture 数据，正式组件无硬编码示例回复 |

Stage 1 不含生产上线结论。当前生产版本/角色/真实历史及海外保持仍由发布验收负责。

## Stage 2 · Code Quality

**结论：PASS（仅本报告产品范围，绑定最终 candidateId）。** 在计数修复的 Stage 1 复核通过后执行收尾检查。未发现未解决的质量或安全问题。

- 结构/类型：新增任务模型、查询、生命周期、删除、路由、scope 分离；新增前端 API DTO 有运行时守卫，拒绝跨 task/owner/workspace 的 managed sessions。证据 `B/app/modules/domestic_studio/task_scope.py:33`、`task_service.py:33`、`F/src/api/hengxin/domestic-tasks.ts:19`/`:33`。所有本次生产源码文件均不超过 300 行，最大为既有 `auth/dingtalk.py` 263 行；新文件无 TypeScript any 类型，`AbortSignal.any` 是平台方法而非 any 类型。
- 安全：扫描本次任务相关模块未发现 eval、dangerouslySetInnerHTML、innerHTML、前端密钥变量、硬编码 API key 或用户绝对路径。SQL 查询使用 SQLAlchemy 表达式；迁移 SQL 使用参数绑定，`0044_domestic_tasks.py:52`。任务归属和状态在服务端验证，不以 UI 隐藏替代鉴权。
- 测试真实性：上传并发通过真实线程阻塞 store.put；删除测试比较原始/剩余 bytes 与本地目录；管理权限使用实际角色回读而非只 mock 前端；新计数测试 HTTP+PG 断言同时校验干扰数据范围。证据 `B/tests/test_domestic_task_lifecycle_pg.py:25`/`:48`、`test_domestic_studio_admin_pg.py:154`、`test_domestic_tasks_pg.py:87`。
- LOW 测试盲区（已补强并复核）：原 completed recover-files 使用 `files:[]` 并接受 409 或 422，不能单独证明合法 recovery 请求的状态门禁。主 Agent 已在 `B/tests/test_domestic_tasks_pg.py:114` 改为合法非空 payload、新旧路由精确断言 409，且将 native recovery 替换为调用即失败，避免参数 422 或实际下发掩盖门禁缺失。独立复跑该用例 `1 passed, 2 warnings in 7.78s`。本次只变测试，未变实现。
- 视觉：实际打开确认预览 3038、静态生产构建 3040 的任务列表/详情，以及邻居“调用与执行”。列表卡片 16px 圆角/24px padding、标题 26px、筛选 300/240px、表格 cell 20px、窄屏 16px padding 与预览一致，证据 `F/src/views/hengxin/domestic-studio/tasks.css:1`–`:40` 对照 `F/preview-task-center/style.css:1`。实际 390px 页面表单/同步/只读说明完整，表格内部滚动。管理详情沿用已上线只读组件，符合 Design-Brief 复用说明。
- 视觉产物：`output/playwright/task-product-review-list.png`、`task-product-review-detail.png`、`task-product-review-mobile.png`、`task-product-preview-list.png`、`task-product-review-neighbor.png`。邻居 fixture 的统计 API 不齐，显示错误反馈；只用其实际布局/按钮/卡片作视觉基准，未将其数据能力标为通过。两个人工浏览 session 已关闭。
- Spec 漂移：新增 Task/TaskRequest、0044、task URL、管理入口、旧入口 redirect 都对应最新 Spec；未发现额外生产功能。预览身份切换及 seed 明确隔离在 preview 目录，不作为生产实现。

## 验证原始输出

独立执行（隔离 `hengxin_tasks_test`，每测试生成独立 schema，未连接生产）：

```text
docker exec -e PYTHONPATH=/workspace/hengxin-smart-image/backend -w /workspace/hengxin-smart-image/backend hx-task-20261117-python python -m pytest -q -p no:cacheprovider tests/test_domestic_tasks_pg.py tests/test_domestic_task_lifecycle_pg.py tests/test_domestic_tasks_migration_pg.py tests/test_domestic_studio_admin_pg.py
.................                                                        [100%]
17 passed, 2 warnings in 21.95s
```

两条 warning 是现有 Starlette/httpx 与 anyio 弃用提示。首次修复前独立任务套件输出 `10 passed, 2 warnings in 18.98s`，没有用旧结果覆盖修复后结果。

测试盲区补强后的独立增量验证原始输出：

```text
tests/test_domestic_tasks_pg.py::test_completion_blocks_new_and_legacy_writes_and_can_reopen
.                                                                        [100%]
1 passed, 2 warnings in 7.78s
```

核对主 Agent 原始日志：

```text
# output/task-frontend-unit.log
ℹ tests 584
ℹ suites 0
ℹ pass 584
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 17812.5392

# output/task-frontend-typecheck.log
> hengxin-smart-image-frontend@0.2.74 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit

# output/tasks-production-build.log
✓ built in 48.86s

# output/tasks-backend-domestic-tests.txt（原环境失败，不能省略）
E   ModuleNotFoundError: No module named 'app'
1 failed, 220 passed, 22 skipped, 2 warnings in 171.59s (0:02:51)

# output/tasks-backend-full.log（原环境失败，不能说全绿）
E   Failed: Linux release verification requires an installed Bubblewrap
2 failed, 3419 passed, 256 skipped, 6 warnings in 656.95s (0:10:56)

# output/tasks-bubblewrap-isolated-final.log（原两用例补齐环境后复跑，已读取）
..                                                                       [100%]
2 passed in 3.78s
```

受影响套件的 PYTHONPATH 失败主 Agent 已另以 29 passed/1 skipped 复跑；完整套件两项 Bubblewrap 原用例在独立无网络、只读源码、允许 user namespace 的测试容器中补齐环境后复跑通过，未改产品沙箱实现。已直接读取原始复跑日志。skip 不计为已经验证。

## 最终交接结论

- 初始 c23cdb…：存在已确认 MEDIUM 计数问题，不能直接批准。
- 当前产品代码的计数修复已复核，Stage 1 功能及 Stage 2 检查无未解决 HIGH/MEDIUM；LOW 测试盲区也已补强并复核。
- 最终 `bdc78af52f5564caa852690e03d2626b14a94ce73ff07e295256dcc2bff51fe5`：**产品范围 Stage 1 PASS、Stage 2 PASS**。发布工具、生产部署验收不在此 PASS 范围。
- 由主 Agent 汇总同快照其他范围报告并执行 review-approve，本 reviewer 未登记批准、未写 clean。
