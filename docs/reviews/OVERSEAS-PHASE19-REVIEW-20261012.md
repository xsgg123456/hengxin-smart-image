# Phase19 独立代码审查（2026-10-12）

- candidateId：`2d209e8a64c497bc42eeccb3eedbdcc7eb47cedf8193ebde97390fa9f832063c`。
- 结论：**Stage 1 FAIL（1 项 MEDIUM）；Stage 2 PASS**。不得批准本快照交付。Stage1 无 HIGH，主 Agent 明确要求继续完成质量审查并汇总发现。
- 审查前及专项验证后（修复前）`harness.py review-status` 均返回上述 currentId。报告交接时主线程已修改 Workspace 空态及故障浏览器断言，最终只读检查 currentId 已为 `900230fb36faedc903aa46285d53eed0ea06c31056ef260fcad12d120814f7cc`；本报告结论只覆盖旧候选，不覆盖这些新修改。reviewer未修改代码、未登记批准、未写 clean。
- 本报告路径中的 backend/frontend/infra 均相对 `hengxin-smart-image/`。

## 范围与输入

读取 AGENTS.md、code-review/SKILL.md、docs/HARNESS-REVIEW.md、DEV-PLAN.md:102 的19.1–19.3、Product-Spec.md:956及:967海外正式需求、Design-Brief.md:167、OVERSEAS-FULLSTACK-PLAN-20261012.md，以及 Phase19 CONTRACT/BACKEND/INTEGRATION/VALIDATION 和 frontend/PHASE19-TASKS.md 原文。

审查范围：backend/app/core/idempotency.py、app/modules/tasks/idempotency.py、app/overseas/{db,main,tasks/**}、migrations/overseas/{env.py,versions/0004_tasks.py}；对应任务、改派、PG、迁移、配置、数据库测试；infra/identity-test/{run,checks,provider_app,phase19_checks,phase19_fixtures}.py；frontend/PHASE19-TASKS.md所列15项候选。全快照中的CreatePage/PreviewWorkspace/WorkspacePage/OverseasDetail仅审查本次兼容接线，不把既存模拟闭包当作本Phase正式交付。

既存技能、.gitignore、Design-Brief、package.json、locales及其余预览不算本次新增，不回滚、不要求混入提交。

## Stage 1：Spec Compliance

### 问题

**S1-01 / MEDIUM / 引导真实性**：`frontend/src/views/overseas/OverseasWorkspace.vue:41` 固定空态“暂无匹配任务，请提交图需或清空筛选”。普通设计、设计主管和纯超级管理员无创建权限（`backend/app/overseas/permissions.py:37`）；正式页面已按canCreate隐藏提交按钮（`frontend/src/views/overseas/OverseasTasksPage.vue:21`），却仍向这些身份提示提交图需。与合同按task.create提供入口及skill引导真实性要求不匹配。应按allowed分支：有权限保留提交引导，无权限只提示清空筛选或联系运营，并补无create身份空态浏览器断言。

### 逐项实现核对

|条目|结果|代码与验证证据|
|---|---|---|
|真实基础信息、品牌/平台/市场/备注、多SKU，无颜色|完整实现|tasks/schemas.py:17；Create.vue:23、:52；真实浏览器保存2SKU并刷新读取|
|必填、长度、平台白名单、1–100SKU、去空白大小写不敏感重复、禁止额外字段|完整实现|tasks/schemas.py:5、:9、:24、:32；test_overseas_tasks.py:65、:71；独立pytest通过|
|必选有效设计；无效、停用、纯管理员候选拒绝|完整实现|tasks/service.py:16、:47；queries.py:76；test_overseas_tasks.py:77、:86、:105|
|独立5表、UUID/海外成员外键、SKU顺序/唯一、事件版本唯一|完整实现|tasks/models.py:10、:26、:36、:50、:62；0004_tasks.py:22；迁移专项独立通过|
|0003升级保留既有成员/角色/会话/审计与国内库|完整实现|test_overseas_tasks_migration.py:9、:30；实际迁移测试执行通过|
|一期中立幂等原语复用且旧fingerprint语义保留|完整实现|core/idempotency.py:9、:14；modules/tasks/idempotency.py:6、:18；本轮独立国内任务/并发/输入回归通过|
|创建事务原子、事件/outbox/request同事务、重放200首次201|完整实现|tasks/service.py:39；router.py:17；test_overseas_tasks.py:45、:118；失败后5表零残留断言|
|相同key同体只写一次，异体409，操作者隔离，重放返回当前DTO并重查授权|完整实现|service.py:40、:43；assignment.py:11、:16；PG同键竞争与assignment重放版本3断言通过|
|SQL先范围/条件后count与分页、稳定排序、名称/品名/品牌/SKU/ID搜索、mine交集|完整实现|queries.py:53；test_overseas_assignment.py:55；HTTP集成phase19_checks.py:61–79静态审查及独立专项|
|详情404/403；真实当前任务capabilities|完整实现|queries.py:16、:24、:39；assignment测试范围矩阵与真实浏览器直链通过|
|五角色及兼任：运营本人、运营主管全、设计本人、设计主管全+改派、超管全+改派但无隐含create/design|完整实现|permissions.py:24、:67、:80同源复用；tasks/queries.py:35、:55；独立五角色/兼任真实浏览器通过|
|候选搜索分页、最小字段、启用设计及设计主管，未把第一页视为全名单|完整实现|queries.py:76；DesignerPicker.vue:21、:27；故障浏览器实际选第2页设计|
|改派版本正整数、陈旧/相同负责人409、审计版本递增、状态/SKU不变|完整实现|schemas.py:40；assignment.py:20–33；test_overseas_assignment.py:20、:99独立通过|
|权限锁→幂等锁→行锁，等待后刷新操作者/候选|完整实现|service.py:9；assignment.py:11–20；members/service.py:17、:22；真实PG12项包含8种等锁停用/撤权竞争，全部独立通过|
|原设计即时失权、新设计接续、兼任仍保留本人创建读权限、停用负责人可改派|完整实现|queries.py:39；test_overseas_assignment.py:77、:89、:127；真实浏览器旧设计刷新拒绝/新设计可读通过|
|仅created保存；不上传/不创建AI作业、不发布outbox、不添加待分配或审核资料流程|完整实现|service.py:29、:48；router.py:17–45仅任务与分配API；Create.vue:79 slots；真实/故障浏览器正式入口无上传与示例|
|正式3路由续建原3组件、真实adapter隔离模拟状态|完整实现|identity-main.ts:21；OverseasTasksPage.vue:3、:12、:21；tasks.ts:48；正式依赖无preview-adapter/workflow，干净基线叠加候选构建成功|
|保存中防重复、错误保留输入、不确定重试相同key、内容变更新key、成功清key|完整实现|TasksPage.vue:57；tasks.ts:67；Create.vue:7、:22；独立单测及断网重试浏览器断言通过|
|加载/空/错误、列表分页刷新、撤权/401/403清内容菜单、409刷新重选|功能完整；空态文案部分实现|TasksPage.vue:45–55、:66–81；Portal.vue:68–90；故障浏览器通过。文案缺陷见S1-01|
|设计视觉及390px关键按钮可达|完整实现|Create.vue:141、TasksPage.vue:84、TaskInfo.vue:41；故障浏览器祖先裁切验证、真实390截图视查通过|

未实现项：本Phase没有功能整体缺失；Phase20资料与Phase21执行按明确边界不计缺陷。Spec漂移：未发现额外正式业务页面/API/表；原模拟流程属于已说明的本地预览闭包。

## Stage 2：Code Quality

- **PASS / 结构**：新增后端模块1–89行，业务职责拆分为schemas/queries/service/assignment；迁移冻结独立schema定义（0004_tasks.py:12），未通过导入未来运行模型改变历史。前端组件分别负责表单、候选、列表、任务信息与编排（TasksPage.vue:28、DesignerPicker.vue:13），未超300行；此次业务TypeScript无any。
- **PASS / 安全**：tasks/router.py:17、:43复用浏览器写保护及CurrentMember；core/idempotency.py:20使用参数化SQL；queries.py:61以SQLAlchemy条件和autoescape处理搜索。扫描未发现新增eval/innerHTML/危险HTML渲染/前端密钥。事件、姓名、备注用Vue插值（TaskInfo.vue:7、:19、:23）。测试隔离凭据不是生产密钥。infra/phase19_fixtures.py:29枚举数据库表名后用identifier_preparer.quote转义，非请求拼表名。
- **PASS / 测试真实性**：PG测试实际等待pg_locks未授予的advisory锁后改变权限并commit（test_overseas_tasks_postgres.py:81），不是顺序假并发；故障注入后复查五表计数（test_overseas_tasks.py:118、test_overseas_assignment.py:99）；真实浏览器仅钉钉provider替身，任务/授权/持久化为真实服务（tests/overseas-tasks-real.browser.mjs:16、:33、:47）。空态权限文案是已发现覆盖盲区，需补测试。
- **PASS / 视觉复用**：实际重跑overseas-shell.browser.mjs，打开海外页面及一期国内卡片基准，比较data-box-mode和computed borderRadius相等（脚本:17、:55）。视查本轮task-real.png/task-real-mobile.png与11-domestic-baseline.png：相同Art侧栏、蓝色按钮、白卡与浅灰背景，卡片16px圆角、20px间距继承公共CSS（prototype.css:8，TaskInfo.vue:3）。390px长名称及UUID换行，关键按钮可滚动到达，无横向文档溢出。
- **PASS / 正式提交依赖闭合**：已读取主线程隔离构建原始日志output/phase19-clean-build.log。git archive HEAD仅导出frontend后叠加14项正式代码/测试候选，未复制预览闭包或既存package/locales变更；仅node_modules junction复用安装依赖。构建通过；正式源码静态导入未发现模拟adapter/workflow（tasks.ts:1、Create.vue:102、Workspace.vue:66、TaskInfo.vue:30）。此结论仅适用于正式入口，不为未提交预览闭包签发交付证明。

## 独立复验原始输出

后端挂载完整代码根只读至/workspace，使用hx-management-test:local的Python，设置独立PG的TEST_DATABASE_URL/TEST_OVERSEAS_DATABASE_URL。命令：

```text
python -m pytest tests/test_overseas_tasks.py tests/test_overseas_assignment.py tests/test_overseas_tasks_postgres.py tests/test_overseas_tasks_migration.py tests/test_tasks.py tests/test_tasks_concurrency.py tests/test_single_revision_inputs.py -q -p no:cacheprovider
86 passed, 12 skipped, 3 warnings in 35.14s
```

首次缺TEST_OVERSEAS_MEMBERS_DATABASE_URL导致12项PG测试跳过，没有当作通过；设置该变量后单独补跑：

```text
python -m pytest tests/test_overseas_tasks_postgres.py -q -p no:cacheprovider
............                                                             [100%]
12 passed, 2 warnings in 8.03s
```

警告为Starlette/httpx、anyio弃用及既有国内测试NULL主键SAWarning，未隐去失败。本次合计98项不同测试通过。

前端独立类型检查：

```text
> hengxin-smart-image-frontend@0.2.21 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

退出0，无类型错误。pnpm报告旧pnpm配置字段被忽略警告；依赖配置未由本Phase改动。

```text
pnpm exec tsx --test tests/overseas-tasks.test.ts
ℹ tests 3
ℹ suites 0
ℹ pass 3
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 252.1623
```

真实及故障浏览器独立运行，均退出0：

```text
PASS real HTTP/DB browser: five roles+dual menus/direct links; multi-SKU create/reload; list scope; manager reassignment/audit; old designer immediate denied; new designer readable; 1366/390 screenshots
PASS task browser: candidates empty/failure/page; multi-SKU; uncertain retry; detail; assignment 409; list pagination/search/error/empty; narrow ancestor clipping; revoke
```

邻居基准脚本独立输出：

```json
{"passed":4,"checks":["复用侧栏导航、任务空态、无资料阻止、文件类型校验、仅竞品资料上传提交、删除确认","复用全局搜索及业务切换后重新挂载","海外与一期卡片模式、实际圆角一致","国内入口进入一期原有模拟页面，保存同视口视觉基准"],"errors":[]}
```

主线程完成、reviewer读取原始日志的隔离构建（非reviewer重复全量构建）：

```text
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
transforming...
✓ 4587 modules transformed.
rendering chunks...
computing gzip size...
✓ built in 31.67s
```

完整原始输出：`output/phase19-clean-build.log`。主线程其他1870项后端全量、264项前端全量及镜像构建记录作为补充输入，本报告不冒充独立复跑。

## 交接

修复S1-01后重新review-prepare并交fresh reviewer复核；当前候选不能登记两阶段PASS。未发现额外HIGH或安全问题，Stage2未发现新的阻断项。本报告不授权提交未审改动。
