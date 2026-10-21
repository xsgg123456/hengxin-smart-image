# 国内 CLI 三天清理与管理中心审查

审查日期：2026-10-21。独立 code-reviewer 使用 `.agents/skills/code-review/SKILL.md` 与 `docs/HARNESS-REVIEW.md`。仅审查和写报告，未改业务代码、未提交、未登记批准。

## 快照与范围

初始 candidateId：`2398b2d4714e5b15e701a6b1d0d0ca1ff4d2c7b09d8319fea7af35f60edfa128`。

审查期间主线程修复时间测试，候选变为 `ed9ecf5e3048e98b2b307a737eb45fd6cf1bf05e6c58e69acb2c88962e7afefc`，已读取差异。此处不将初始快照结论直接批准后续快照。

范围：本轮全部 git diff 与未跟踪交付文件，覆盖后端 retention/管理合同和路由/0032迁移/主动删除回执衔接、正式前端页面/API/状态与权限、发布助手和测试、隔离真实 HTTP QA。已有独立预览沿用 `docs/reviews/RETENTION-PREVIEW-20261021.md`；不重新批准其模拟能力为生产能力。需求依据为 `docs/CLI-RETENTION-MANAGEMENT-20261021.md:5`、`Product-Spec.md:1`、`Design-Brief.md:1`。

最终 candidateId：`a78cb15f95a3b52f7965bbd35ab33526cfb85967e7dd95d025d6bf00d8f8dad0`。

最终结论：**Stage 1 PASS；Stage 2 PASS**。最终 review-status 的 currentId 与该编号相同；批准登记由主 Agent 执行。本地实现、发布助手和隔离验证通过，不代表生产切换已完成。

增量复核：`ed9…` 后新增 queries.py 的 cache_pending 优先级修复及 HTTP 回归；中间候选 `f7df6ef0c93515a6f35cfca78408c96c2714c51e04d1924f22e157762b29451c` 的 SQLite dueAt 断言精度不符，最终仅按 SQLite datetime 的秒精度比较，未放松类型、重试、详情和计数断言。所有增量已独立读取；最终定向 PG/SQLite 42 项通过。

## 发现的问题

1. **已关闭 MEDIUM / Stage 1：缓存重试跨72小时后被管理页错误归类为历史到期，失败数量漏报。** `hengxin-smart-image/backend/app/retention/queries.py:31` 的 `is_history` 根据活动超过72小时直接为真，没有优先尊重 `cache_pending`。实际执行 `state.py:62` 优先恢复 pending 屏障；因此24小时缓存清理失败后，到73小时仍应显示缓存/失败待重试，修复前查询却换成历史记录连接，返回 history/due，summary 的 retry 统计也漏掉该会话。合同要求“当前失败待重试”和 pending 屏障真实保持。独立探针 `output/retention-management-20261021/test_review_pending_barrier.py:10` 使用真实清理事务和 SQLite，输出 `ACTUAL history due`，断言失败。最终 `queries.py:31` 已用 `status != cache_pending` 优先保留缓存动作；`test_retention_management.py:25` 补真实HTTP列表/筛选/详情/summary回归，独立原探针现输出 `ACTUAL cache retry`、`1 passed`。
2. **已定位 / Stage 2：原时间恢复测试前提不稳定。** 初始 `tests/test_api_retention.py:148` 将恢复的持久活动最大时间与旧 entry 时间精确相等，实际相差258微秒。主线程现已在 `:142` 固定 conversation/turn 的持久活动时间并断言恢复最新 finished_at；复验该测试通过。业务恢复算法未因此修改。
3. **已定位 / 验证环境：Linux 进程回归初始8失败。** 主线程 Docker 未加 init，pytest 为 PID 1；已有 supervisor 将父进程 PID 1 视为父已退出。加 `--init` 后同组原始输出为 `26 passed, 1 skipped, 1 warning in 44.85s`，见 `output/retention-management-20261021/backend-process-retest.log:1`。这些进程实现不在本轮修改范围。

## Stage 1：Spec Compliance — PASS（逐条合同检查）

| 合同条目 | 实现与证据 |
| --- | --- |
| 24h缓存、72h历史，无新宽限 | `backend/app/retention/state.py:8`、`:62` 明确阈值；`worker.py:18` 缺失登记从持久活动恢复，不以安装时间续期；`0032_retention_observability.py:48` 只重排 active，保留 pending 和 last_activity_at。`test_retention_observability_pg.py:23` 在真实 PG 验证迁移重复执行与屏障保留。 |
| 有效活动与只读不续期 | `conversation.py:143`、`:172`、`:204` 和 `conversation_runtime.py:54` 只在写入活动调用 touch；新增查询 `retention_router.py:22`、`:28`、`:46` 均只读；`state.py:35` 保持有效时间单调。 |
| 执行中、未知归属保护 | `retention/api.py:19` 锁父任务、会话和条目，`:38` 检查终态、租约、进程身份；`:88` 先提交 pending 屏障再清文件。真实 PG 并发用例见 `test_retention_concurrency.py:87`、`:103`、`:122`、`:140`、`:222`。 |
| 保留正式成品/全部采用版本/归档/原图/素材/汇总 | `retention/api.py:60` 先 preserve 用量事实，只删会话轮次/事件/相关 job；`objects.py:23` 检查版本、原图、结果、素材和冻结 JSON 引用。`test_api_retention.py:65` 验证采用版本和对象不变，`:189` 验证跨图片引用。 |
| 每小时、单轮25会话及对象 | `worker.py:76` min(batch,25)、稳定排序、同轮 retry_objects；`:119` 非主动删除循环间隔3600。 |
| 历史和物理回收分阶段，完成才计数且去重 | `events.py:17` 按资源/类型/活动唯一回执，`:38` pending非零不计数，`:55` 物理删除后递减/完成；`objects.py:84` 行锁与重试；`deletion_records.py:47` 主动删除衔接对象回执。`test_retention_observability_pg.py:57` 真实并发验证一次累计。 |
| 持久心跳、扫描起止和失败 | `service.py:13` 独立事务写心跳，`:28` 30秒独立线程，失败不造新时间；`:48`、`:61` 持久扫描状态；`summary.py:9` 120秒阈值及下次计划。`test_retention_observability_pg.py:88`、`:112`、`:131` 验证线程、故障与扫描失败。 |
| 今日/长期计数、起算、未知 | `summary.py:9` 按北京时间成功完成日计数，累计取长期表；`events.py:38` 不重复累计；前端 `retention.vue:5`、`:24` 和 `RetentionService.vue:3` 明示采集失败/过期快照。pending 缓存重试跨72小时漏报已按发现1修复并复验。 |
| 历史与待清理、搜索/类型/结果/日期/分页/详情 | `queries.py:20`、`:29`、`:59` 服务端联合视图和绑定过滤，日期以北京日边界；`retention_router.py:28` 校验参数/页大小/稳定排序，`:46` 详情404及detailTab。缓存屏障归类问题已修复并由HTTP及独立探针复验。 |
| 删除任务后摘要可读 | `observability_models.py:12` 无业务FK；`queries.py:20` 外连接判 task_deleted；`test_retention_management.py:192` 主动删除后摘要与累计保留。 |
| 90天已完成明细/扫描，未完成与长期累计保留 | `service.py:61` 仅按 completed_at/finished_at 裁剪；totals 不删除；`test_retention_management.py:130` 清理100天后的完成记录仍保留累计和未完成记录。 |
| 不存聊天/提示词/密钥/路径，不估空间 | `observability_models.py:12` 仅任务名/ID/计数/时间/状态；`queries.py:80` 固定序列化字段；`api.py:132` 错误正文固定。前端没有空间估算字段。 |
| 管理角色、后端独立权限 | `retention_router.py:17` CurrentUser角色明确限定；`frontend/src/router/modules/index.ts:17` 路由仅超管/主管，`:23` 不缓存；`test_retention_management.py:50` 验证两个允许角色及两个拒绝角色。 |
| 15秒可停轮询，隐藏页暂停，身份与竞态 | `use-retention.ts:14` epoch与序号校验，`:44` 身份变化清所有快照/详情，`:50` document.hidden、开关、卸载清计时。独立运行 `retention-state.test.ts:20`、`:35`、`:50`、`:63` 全通过。 |
| 已批准布局、取消演示控制、配置入口和3天提示 | `retention.vue:2`–`:41` 正式Art与Element组件，`RetentionDetail.vue:4`、`RetentionPolicy.vue:4`；`ExecutionSettingsCards.vue:14` 导航真实页面；`ImageConversationEditor.vue` 的现行提示为3天。独立实际打开18925自动清理/执行监控，菜单、标题、蓝色刷新按钮、卡片密度一致；查看主线程390和1280截图无页面横溢出。 |
| 发布排空、可恢复备份、增量迁移 | `retention-management-deploy.py:16` 关入口/停API/排空/备份/迁移顺序；`drain.py:67` 先停清理，CLI两次稳定空闲与API安全交接；`backup.py:32` dump恢复验证及全表指纹，`:63` 校验迁移仅调度和新增表变化。 |
| 五国内容器+三原生，保留策略与海外/身份 | `runtime.py:14` SERVICES来自原五服务清单；`:45` 只改镜像构建；`:68` 保留其他进程/挂载/文件指纹；`native.py:61` 复用最新依赖且只切工作目录/命令路径，`:104` 比对环境和策略。 |
| 清理最后启动、实际扫描验收、物理删除后不恢复旧DB | `deploy.py:62` 写不可逆标记后启动清理，`:67` 首轮观测后才恢复outbox与入口；`:81` 失败关入口/停清理，不恢复旧库；`verify.py:78` 必须真实新扫描完成和新心跳。独立发布风险测试50项通过。生产执行及正式登录验收仍由主线程实施，不在本地审查中冒充完成。 |

路径缩写说明：表内 `backend/`、`frontend/` 位于 `hengxin-smart-image/`；未带目录的 backend 文件隶属上文同名模块或 `backend/tests/`；发布文件位于 `scripts/release/`。

Spec漂移：未发现合同外正式功能；新增数据库表、只读API、QA辅助和增量发布脚本均为本轮合同所需（合同`:17`）。发现1已关闭；本轮未解决的部分实现、整项缺失、HIGH/MEDIUM问题均为零。

## Stage 2：Code Quality — PASS

- 结构：本轮修改/新增代码文件均不超过300行。`observability_models.py:12`、`events.py:17`、`queries.py:20`、`summary.py:9` 分离模型/事务/查询/统计；前端 `types/retention.ts:1` 与 `api/retention.ts:8` 定义并检查传输类型，无新增 TypeScript any。
- 安全扫描：本轮代码扫描 eval/innerHTML/dangerouslySetInnerHTML/敏感VITE变量/常见真实密钥前缀未命中；Python `any()` 是内置聚合，非类型逃逸。`queries.py:59` 绑定参数和LIKE转义；`retention_router.py:46` UUID入参；`native.py:53` 拒绝systemd转义注入；备份使用private写入。`live-app.py:17` 仅localhost且数据库名必须_test，内置值明确test凭据，QA不入发布包（`test_package_retention_management.py:55`）。
- 依赖风险边界：现有依赖审计 `output/retention-management-20261021/dependency-audit.json` 报 critical=0、high=72、moderate=50、low=6；本轮未改依赖或锁文件。这是既有依赖风险，不属于本次新增代码漏洞修复范围，不能据此报告声称整个项目不存在漏洞。
- 实际视觉：独立打开 `http://127.0.0.1:18925/#/management/retention` 和邻居 `/management/monitor` 并截图检查；1280宽下侧栏/工作标签/标题/按钮/卡片一致，h1共用 `prototype.css:4` 28px，section body共用`:8` 23px，KPI共用`:48` 16px间距。主线程 `browser-local.json` 记录390/1280、真实HTTP+PG、筛选、详情、503过期与恢复，errors=[]、generationCalls=0；独立已读取该证据并查看窄屏截图。
- 测试真实性：组件测试使用stub验证接线，未当成真实Element渲染证据；实际浏览器补足渲染。PG用例真竞争锁/迁移/回执，不将SQLite作为并发证明。发现1来自独立额外边界探针，原测试未覆盖缓存失败跨72h，最终补回归并通过。

## 编译和验证原始输出

主线程生产构建日志 `output/retention-management-20261021/frontend-build.log:3`：

```text
> hengxin-smart-image-frontend@0.2.46 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
✓ 4665 modules transformed.
✓ built in 36.09s
```

独立 reviewer 执行四份发布风险测试：

```text
..................................................                       [100%]
50 passed in 0.99s
```

独立 reviewer 执行 retention API、组件与状态三份前端测试：

```text
ℹ tests 10
ℹ suites 0
ℹ pass 10
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 1253.6441
```

初始全量后端及定向复验（保留失败事实，不宣称初跑全绿）：

```text
9 failed, 2215 passed, 125 skipped, 8 warnings in 302.73s (0:05:02)
8 failed, 27 passed, 1 skipped, 4 warnings in 33.34s
26 passed, 1 skipped, 1 warning in 44.85s
```

独立新增缓存屏障探针：

```text
ACTUAL history due
FAILED ...test_cache_retry_remains_visible_after_history_deadline
1 failed, 2 warnings in 2.16s
```

最终独立原探针和主线程 PG/SQLite 定向复验：

```text
ACTUAL cache retry
1 passed, 2 warnings in 2.42s
..........................................                               [100%]
42 passed, 2 warnings in 18.36s
```

最后一项读取 `output/retention-final-targeted.log:1`。初始全量失败中的时间断言、进程环境，以及新增回归秒精度差异均已闭环，没有隐藏首次失败记录。

生产发布、正式登录和首轮真实扫描验收由主线程继续执行；本报告仅允许登记最终候选的两阶段审查通过，不能据此称生产已完成。
