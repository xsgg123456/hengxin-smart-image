# Phase 21 独立两阶段审查

- 审查日期：2026-10-12。
- candidateId：`099af606aad6f47adadb999c38c488890269fd5ee5efe7d8db5c5b07bb6c8a5c`。
- Stage 1：**PASS**。Stage 2：**PASS**。未发现本次范围内 HIGH/MEDIUM 阻断问题。
- 审查依据：AGENTS.md、code-review/SKILL.md、docs/HARNESS-REVIEW.md、DEV-PLAN.md:130、docs/OVERSEAS-PHASE21-CONTRACT.md、docs/OVERSEAS-PHASE21-RUNBOOK.md、Product-Spec.md:956、海外完整需求合同及 Design-Brief.md:167。
- 本报告由独立 reviewer 产出；未修改实现、未提交、未写 clean、未登记 review-approve。主 Agent 需登记同一快照。

## 快照与范围

开始及结束读取 `harness.py review-status`，currentId 均为上述 candidateId，审查期间未发现代码快照变化。报告本身不属于代码快照。

审查范围为以下 Phase21 增量，路径均相对 `hengxin-smart-image/`：

- `backend/app/overseas/execution/` 全部13个模块，以及 `backend/app/overseas/{db,main}.py` 的本阶段差异。
- `backend/migrations/overseas/env.py`、`versions/0006_execution.py`。
- `backend/tests/test_overseas_{execution,concurrency,runner,runner_process,execution_migration}.py`；configuration/database/materials_migration/tasks_migration 的路由和迁移 head 断言更新。
- `frontend/src/api/overseas/execution.ts`、`frontend/src/views/overseas/OverseasExecution.vue`、TasksPage 接入；execution 单测和浏览器脚本；旧 tasks-faults 脚本新增两个执行查询 mock。
- `infra/hengxin-overseas-{worker,outbox}.service`、`infra/overseas/regression.py`、`infra/identity-test/phase21_checks.py` 及 run/checks 接入差异。

既有未提交 preview、package.json、locales、Design-Brief、.agents 技能、.gitignore 等保留，不纳入本报告通过范围。Design-Brief 只作为视觉依据。生成 components.d.ts 不在本次差异中。

## Stage 1：Spec Compliance

| 合同条目 | 结论与代码证据 | 验证证据 |
|---|---|---|
| 独立持久 Job/Gate/Outbox/Event、冻结迁移0006 | 完整实现。`backend/app/overseas/execution/models.py:16`、`:23`、`:50`、`:58`；`backend/migrations/overseas/versions/0006_execution.py:14`。仅注册海外元数据，门闩缺失拒绝执行（queue.py:14）。 | 专项迁移重复执行保留任务且只种一行门闩；全量真实PG迁移与HTTP日志确认海外0006、国内0027。孤立worker导入后 create_all 成功。 |
| 事务内冻结输入、四类合法kind、幂等入队、不自行commit | 完整实现。`queue.py:22` 深复制JSON、门闩下检查同键同内容，作业/待发消息/事件同事务 flush；异内容409。没有公共任意payload入队路由（router.py:29）。 | `test_overseas_execution.py:28`；`test_overseas_concurrency.py:64` 实际PG六连接竞争同键及回滚。 |
| 全worker最多5槽，四类共享，排队/人工等待不占执行槽 | 完整实现。`claims.py:58` 在数据库行锁内统计全部 ACTIVE；上限为 min(5,配置)。`models.py:11` 四类，`:12` ACTIVE包含 uncertain/cancelling，queued排除。业务人工等待阶段不创建活动Job。 | `test_overseas_concurrency.py:36` 真实PG、12个并行领取调用/6个作业，只获得5个token且执行计数为5；`test_overseas_execution.py:48` 覆盖四类共享。该测试是多线程独立数据库事务竞争，不冒充5个收费CLI实跑。 |
| 重复消息不重跑、过期先uncertain且不放槽 | 完整实现。`claims.py:48`、`:64`、`:89`；最终或活动状态不再次领取。 | 并发专项拒绝对未知任务及第六个等待任务重新领取；`test_overseas_runner.py:62` 重投执行计数保持1。 |
| 资源不足/暂停保持queued | 完整实现。`runner.py:19` 512MiB磁盘阈值，`:72`/`:75` 执行前及领取时检查；`claims.py:73` 暂停门闩。 | `test_overseas_runner.py:162`、`test_overseas_execution.py:132`。阈值不代表CPU/内存整体配额，运行说明已明确。 |
| 独立队列、持续outbox重投、失败回滚 | 完整实现。`worker.py:7` 强制海外上下文，`:9` 独立broker/overseas.cli；`queue.py:51` 锁定待发记录并周期重新投递；`outbox.py:11` 周期维护。 | `test_overseas_execution.py:88` 验证发布失败回滚及重复投递；`infra/identity-test/phase21_checks.py:38` 真实Redis队列长度及HTTP查询；孤立Celery CLI入口检查成功。 |
| 复用CLI工作目录/进程、独立认证/home、冻结Skill与物料 | 完整实现。`runner.py:11` 直接复用中立执行模块，`:89` 以job/token创建独立home；`materials.py:7` 保存冻结JSON，`:16` 校验Skill名及路径，`:30` 写入冻结内容。 | `test_overseas_runner.py:62` 两作业不同home；`:172` 原始输入后续修改不影响Skill，并拒绝路径穿越；共享workspace/process的既有回归通过。 |
| 实际CLI版本检查与协议关闭，Phase22/23后接业务 | 完整实现。`runner.py:84` 先解析内部协议，再检查CLI版本、sandbox命令、非空提示词；`protocols.py:18` 仅合法kind且拒绝重复注册/缺协议。未将task.created自动变为分析指令。 | `test_overseas_runner.py:78` 无协议不能启动模型；独立Celery入口能导入/识别任务；真实子进程替身验证stdin、完成事件。未调用付费Codex、未验收未来分析/生图效果，符合阶段合同。 |
| 取消限task.design、版本冲突，运行取消不提前放槽 | 完整实现。`cancel.py:11` 锁成员、任务及Job并重验授权；queued可以直接取消，其余转cancelling/保持uncertain；`claims.py:109` 未确认退出不能完成。 | `test_overseas_execution.py:71`、`:132`；真实HTTP验证运营403、旧版本409、设计cancelling、未退出拒绝结束。 |
| 超时/进程组停止、未知进程只核实、迟到不发布 | 完整实现。`runner.py:112` 复用execute，异常无法确认退出时`:139`转uncertain；`reconcile.py:19` 只检查同节点PID/boot/birth，信息缺失或读取失败保留；`claims.py:109` 验证token、ACTIVE、退出，成功另验证租约/取消。 | `test_overseas_runner_process.py:18` Linux真实子进程超时和取消、退出回执；runner.py测试`:100`、`:114`、`:127`、`:145`拒绝迟到/失联，未知保槽，确认退出后失败结束。 |
| 成功须进程退出、协议完成、产物校验和有效所有权 | 完整实现。`runner.py:115`/`:118`/`:128`/`:131`，业务publish与成功在 `claims.py:98` 同事务提交。 | `test_overseas_runner.py:188`、`:204` 成功原子发布/发布异常回滚；`:221` exit0但无turn.completed不成功；`test_overseas_concurrency.py:79` PG发布回滚。 |
| 三个API、每次请求身份/任务授权、游标续传与脱敏 | 完整实现。`router.py:29`、`:36`、`:42` 均注入CurrentMember；读取重新authorize，取消重验设计能力；`events.py:22` 按自增id分页，`:5` 固定消息白名单，Job不输出payload/token/PID/认证。门闩确保事件分配和提交顺序。 | `test_overseas_execution.py:108` 验证游标、白名单和改派后读取/取消403；真实HTTP旧设计撤权、新设计能读取；国内数据库快照保持不变。 |
| 正式任务页真实状态、无假百分比、轮询/离页停止/故障恢复 | 完整实现。`frontend/src/views/overseas/OverseasTasksPage.vue:23`接入；`OverseasExecution.vue:2`使用ElCard/Tag/Button/Alert；`:35`轮询与游标提交，`:73`离页中止请求和关闭确认；API类型校验见`execution.ts:14`。 | 独立重跑浏览器覆盖空态、续传、网络失败恢复、取消确认/409/成功/网络未知、uncertain、离页停止、改派撤权、401/403和只读角色；前端3项执行契约测试通过。 |
| UI一致性及引导真实性 | 完整实现。`OverseasExecution.vue:6`明确“尚未开始”，unknown状态要求核实，不展示虚假完成/重试入口；复用既有卡片和按钮。 | 实际打开任务详情与邻居任务列表；1280×900和390×844无控件裁剪。截图见下文。 |

部分实现：无。未实现：无（限Phase21）。分析方案、SKU生图/返工、管理中心等Phase22–24范围不计为当前缺陷。

## Stage 2：Code Quality

| 项目 | 结论与证据 |
|---|---|
| 结构与类型 | PASS。新增生产Python模块最大143行（runner.py），按queue/claim/runner/reconcile/auth路由分离。前端API使用unknown类型守卫（execution.ts:14），未新增any。OverseasExecution.vue:17维护轮询、取消和销毁生命周期。 |
| 锁与事务 | PASS。claims.py:12固定gate→job顺序；发布涉及Task时claims.py:102先锁Task，与取消Task→gate顺序一致。网络发布失败回滚outbox，不以消息送达替代执行所有权；真实PG事务测试有计数和内容断言。 |
| 测试真实性 | PASS。审核了用例前提，PG测试真实竞争行锁，process测试真实Linux子进程退出；runner替身只证明编排与防迟到，不声明收费执行效果。HTTP用例真实迁移/Redis/三API及独立数据库；浏览器mock明确用于UI故障和权限变化，不替代后端授权验证。 |
| 安全扫描 | PASS。范围内扫描eval、dangerouslySetInnerHTML、innerHTML、VITE秘密变量、模型密钥模式无命中。ORM参数化查询；materials.py:24禁止绝对路径/反斜杠/冒号/..；router.py:42有浏览器写保护；events.py:15不返回原始错误或秘密。infra/regression.py:27的密码为本次临时测试容器专用常量，不是生产凭据。 |
| 孤立worker与prefork | PASS。models.py:8显式注册成员/任务外键依赖；独立Python进程仅导入worker后创建元数据成功，未导入国内app.models。复用app/db/session.py:14的fork池重置，worker.py:22在任务进程取factory。 |
| 运行入口 | PASS。独立容器实际执行Celery `-A app.overseas.execution.worker:celery_app worker --help`退出0；service的队列、并发5、海外上下文、同节点名相互一致（infra/hengxin-overseas-worker.service:10、outbox.service:10）。未进行生产systemd部署验收。 |
| 视觉对比 | PASS。独立重跑浏览器并实际打开邻居任务页，白卡、蓝按钮、浅边框及标题/正文与既有OverseasWorkspace.vue:14一致。OverseasExecution.vue:2继承hx-section和hx-gap；prototype.css:8为23px内边距，:29为18px上间距，:31窄屏17px。新增标题容器12px gap且换行（OverseasExecution.vue:76），390px警告正文换行、刷新可见且无裁剪。 |
| Spec漂移 | 未发现。新增4张执行表、3个查询/取消接口、worker/outbox与执行卡均见本阶段合同。没有新增公共启动任意payload的API。 |

视觉证据：`output/playwright/phase21/execution-desktop.png`、`execution-mobile.png`；reviewer新增邻居实际渲染截图 `output/playwright/phase21/reviewer-neighbor.png`。浏览器脚本执行时API使用隔离fixture，非生产页面数据。

## 验证及原始输出

reviewer独立执行：

```text
python hengxin-smart-image/infra/overseas/regression.py tests/test_overseas_execution.py tests/test_overseas_concurrency.py tests/test_overseas_runner.py tests/test_overseas_runner_process.py tests/test_overseas_execution_migration.py
27 passed, 2 warnings in 9.65s
CLEANED hx-overseas-regression-2cf2d6eb05f4

PASS isolated worker import, complete foreign-key metadata, independent queue, no domestic models
PASS actual Celery CLI worker entrypoint --help

PASS execution: empty; cursor resume; cancel confirmation/conflict/success; uncertain; narrow clipping; route cleanup; reassign/revoke; 401/403; read-only
```

已读取主 Agent 最终原始日志（没有将首轮失败或进行中输出计为通过）：

```text
output/phase21-backend-final.log
1953 passed, 17 skipped, 15 warnings in 295.24s (0:04:55)
CLEANED hx-overseas-regression-e4f2ef476cb7

output/phase21-frontend-tests.log
ℹ tests 273
ℹ pass 273
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0

output/phase21-typecheck.log
> hengxin-smart-image-frontend@0.2.21 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit

output/phase21-build.log
✓ built in 36.67s

output/phase21-http.log
PASS migration domestic 0027
PASS migration overseas overseas_0006
PASS ALL Phase 17 real HTTP integration
PASS ALL Phase 18 real HTTP integration
PASS ALL Phase 19 real HTTP integration
PASS ALL Phase 20 real HTTP integration
PASS real execution Redis/outbox, HTTP cursor, cancel/version, reassignment and domestic isolation
PASS ALL Phase 21 real HTTP integration
CLEANED hx-p21-fd0ac6757e18
```

编译/类型检查通过，无新增编译错误。原始日志保留既有pnpm配置提示、依赖弃用及SQLAlchemy警告；未将这些提示隐藏为“零警告”。全量17个跳过项仍是未验证项，不计入1953个通过。Phase21独立专项27项无跳过。

## 验收边界

本结论批准上述Phase21范围的本地执行底座和状态接入，不表示生产部署、真实钉钉、收费Codex执行、完整5进程模型容量或未来Phase22–25业务已经验收。磁盘阈值只是准入保护；运维配额、账号和沙箱部署仍按运行说明后续验证。审查结束快照仍匹配本报告candidateId；任何后续代码改动需重新固定快照并复核，不能复用本报告直接批准新版本。
