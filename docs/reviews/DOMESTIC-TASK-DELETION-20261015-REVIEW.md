# 国内 API 执行提示与真实删除独立审查

- 审查日期：2026-10-15。
- candidateId：`b0f88b90893b4749a29d4d6b5a4ce150c40afd30e2bf6adfcd4a475e5c24c3d9`。
- 分支：`codex/domestic-task-deletion`；派发基线：`469be7b`。
- Stage 1：**FAIL，2 项 HIGH**。
- Stage 2：**未执行**。按 code-review skill，Stage 1 存在 HIGH 时停止，不授予代码质量或完整视觉比较 PASS。
- reviewer 只读实现与证据、执行两项隔离复现并写本报告；未修改实现、未提交、未调用生产写操作。
- 收尾 `harness.py review-status` 的 currentId 与上述 candidateId 一致，approved=false。此次报告不能批准修复后的新快照。

## 审查合同与范围

合同：Product-Spec.md:1166 同日追加、DEV-PLAN.md:1427 同日追加、Design-Brief.md 同日末尾、docs/DOMESTIC-TASK-DELETION-20261015.md:5。

代码范围覆盖此次全部 54 个受控变更文件：

- 后端 api_image_edits：activity、claims、conversation_runtime、deletion、deletion_files、deletion_models、deletion_paths、deletion_records、deletion_state、models、presentation、router、service、summaries。
- 后端 retention/api.py、retention/worker.py、0029_api_task_deletions.py。
- 后端测试 files_helpers、test_api_cli_activity、test_api_image_domain、test_api_image_revision_guards、test_api_image_task_slots、test_api_task_deletion、test_api_task_deletion_faults、test_api_task_deletion_migration、test_api_task_deletion_paths、test_api_task_deletion_postgres、test_api_task_deletion_recovery、test_capacity_admission、test_list_summaries、test_management_api_usage、test_usage_generated_totals。
- 前端 package.json、api-image-edits-validate.ts、api-image-edits.ts、types/api-image-edits.ts、CliActivityTag.vue、RealRecords.vue、RealTaskDetail.vue、use-records.ts、api-image-activity.test.ts、records-polling.test.ts。
- infra/hengxin-domestic-deletions.service、scripts/api-activity/browser.mjs。
- scripts/release/domestic-{deploy,runtime,gate,drain,backup,verify}.py、package-domestic.py、test_domestic_{deploy,package,safety}.py。

下文后端路径以 `hengxin-smart-image/backend/`、前端路径以 `hengxin-smart-image/frontend/` 为根；其余路径以仓库为根。

## Stage 1 阻断问题

### HIGH-1：真实正常删除响应不满足前端校验，删除成功闭环不可用

- Spec 原文：Product-Spec.md 同日条目要求“完成全部物理清理后才反馈删除成功并移除列表；失败显示删除未完成并可重试”。
- 后端 `app/modules/api_image_edits/deletion.py:20` 的 dto 无条件输出 `message: row.error`；正常受理、重试受理、成功回执的 error 为 None，HTTP JSON 因而为 `message: null`（同文件:29、:39、:131）。
- 前端 `src/api/api-image-edits-validate.ts:57` 只接受 message 未定义或字符串，明确拒绝 null。`src/api/api-image-edits.ts:25` 和 :26 的删除及回执查询都应用该校验。
- 影响：真实 202 受理与最终 deleted 响应均被当作无效响应；`src/views/hengxin/api-image-edits/use-records.ts:38` 无法正常应用回执，:85 的成功提示路径不能到达。物理删除可能实际发生，但 UI 持续报告“删除状态尚未确认”。
- 漏测原因：`tests/api-image-activity.test.ts:36` 及 `scripts/api-activity/browser.mjs:22`、:39、:123 的正常 mock 省略 message，没有使用后端真实 payload。367 项测试与浏览器 errors=[] 不能证明此契约匹配。
- 独立复现：在前端目录运行 Node/tsx，直接导入生产 validator，结果如下（exit 0）：

```text
{"payload":{"state":"deleting","message":null},"accepted":false}
{"payload":{"state":"deleted","message":null},"accepted":false}
```

- 修复验收：统一 nullable 字段合同；使用后端完整 DTO 对 DELETE 202、GET deleting、GET deleted、failed/retry 做客户端测试与浏览器测试。不得只修改 mock 以继续规避真实 payload。

### HIGH-2：发布包必选打包器本身触发隐私扫描，授权发布无法完成

- DEV-PLAN.md:1433 要求中文提交后执行隐私审计并产出发布包。
- `scripts/release/package-domestic.py:13` 将 package-delivery.py 等本地打包 helpers 加入 HELPERS；:15 将它们列为 REQUIRED，:21 又将它们加入 selected，:61 对真实源码执行 privacy_check。
- package-delivery.py 内含隐私检查规则，真实扫描该源码必然抛出隐私错误。此问题由主线程先发现，reviewer 已用真实源文件独立复现，未伪造包内文件。
- 独立复现原始输出（exit 1；堆栈绝对路径略去不影响含义）：

```text
selected: scripts/release/package-delivery.py
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "scripts/release/package-delivery.py", line 66, in privacy_check
    raise ValueError(f'Privacy scan failed: {name}')
ValueError: Privacy scan failed: scripts/release/package-delivery.py
```

- `scripts/release/test_domestic_package.py:17` 用空字节填 REQUIRED 文件，:51 的包构建用该假源码，未覆盖实际打包器内容。因此其通过不消除此阻断。
- 修复验收：仅选择服务器安装运行必需文件；本地 helpers 可继续要求已追踪，但不要把它们强制放进运行包。使用真实全部 selected 文件再次 dry-run 隐私扫描，不削弱隐私检查规则。

## Stage 1 逐条覆盖

下列“匹配”指实现及列明证据匹配该局部合同，不代表本 candidate 整体验收通过。

| 合同条目 | 判定 | 代码及验证证据 |
|---|---|---|
| 列表与对应图片卡片分别显示等待修改/图片修改中 | 匹配 | 后端 activity.py:10 用 Job 与 Turn 实际状态聚合；summaries.py:13、presentation.py:14 共享该投影；前端 RealRecords.vue:11、RealTaskDetail.vue:26、CliActivityTag.vue:2。test_api_cli_activity.py:42 覆盖实际 SQL 状态组合。 |
| CLI 结束隐藏提示，保留原 API 状态/筛选/统计/正式成品 | 匹配 | activity.py:20 判终态；前端 types/api-image-edits.ts:35 的标签映射，RealRecords.vue:42 原统计仍只用 API 状态；test_api_cli_activity.py:48 同时断言 status、result、versions 不变。 |
| 复用轮询，关闭重开继续同步 | 匹配 | use-records.ts:55 的原轮询补读 CLI 活动，types/api-image-edits.ts:34；records-polling.test.ts:65 起覆盖关闭、重开与结束；浏览器报告 lists=8、errors=[]，限定为 mock 情境。 |
| 无执行才允许删除：API 排队/执行/重试/收图/uncertain 均拒绝 | 匹配 | deletion_state.py:26 的 task/item/attempt/channel 联合检查；test_api_task_deletion.py:37 起参数覆盖六态、lease；test_api_task_deletion_recovery.py:18 验证真实 failure/collection 路径而非将旧恢复字节误判执行中。 |
| CLI 排队/执行/停止/未知拒绝，候选与待答复须有结束证据 | 匹配 | deletion_state.py:49 查询 turn/job 结束、lease、executionDispatched/identity；deletion.py:64 原生节点再核 PID/boot/birth，活进程不清理；faults 测试涵盖 alive、wrong_node、unverifiable。 |
| 前端禁删及原因、具名二次确认 | 匹配 | RealRecords.vue:15 tooltip/禁用，:52 ElMessageBox 纯文本任务名及永久范围；types/api-image-edits.ts:36 无 canDelete 明确认可时关闭入口。 |
| 任务、图片、历史版本、轮次、CLI 会话与排队记录永久清理 | 后端匹配，端到端部分实现 | deletion_records.py:15 删除业务表、Job/Outbox/Retention/Capacity，deletion_files.py:25 收集原图/素材/结果/版本/候选/标注，:80 清理衍生前缀；test_api_task_deletion.py:92 检查对象、目录、各表为空。前端反馈被 HIGH-1 阻断。 |
| 任务私有工作目录清理、共享引用/Skill/auth/runtime/其他任务保护 | 匹配 | deletion_files.py:44 校验跨任务及 FileRecord/SkillVersionRecord 引用；deletion_paths.py:43 仅 api-edits/UUID，:22 拒绝越界链接/跨设备/非私有材料；tests/test_api_task_deletion_paths.py:24、:40、:77、:87、:114 覆盖邻居、共享认证、恶意链接、IPC 与 uid1000/1001。 |
| 保留最少统计与无内容回执 | 匹配 | deletion_records.py:19 preserve 并匿名 task_name；deletion.py:131 完成后 manifest={}；deletion_models.py:11 只保留任务/操作者ID、状态与时间；test_management_api_usage.py:74、test_usage_generated_totals.py:70 检查历史汇总。 |
| 持久可恢复、失败可重试、完整物理删除才完成 | 后端匹配，端到端部分实现 | deletion.py:94 先提交 manifest/文件围栏，再清理并同事务删除数据库记录及完成回执；:134 异常持久失败并退避，:145 重启扫描；faults.py:21 注入对象/目录/数据库/假成功故障，重启恢复。前端完整成功路径为 HIGH-1。 |
| 与新启动/claim/adopt/迟到结果/自动清理互斥 | 匹配 | deletion.py:24 锁 channel/task；service.py:24 guard、claims.py:46/:91 围栏、conversation_runtime.py:29 父任务锁与围栏、retention/api.py:29 与 worker.py:45 围栏；test_api_task_deletion_postgres.py:34/:64/:79/:94/:109 覆盖独立事务与重复清理。 |
| 不追溯旧软删任务 | 匹配 | deletion.py:35 拒绝 deleted_at；0029_api_task_deletions.py:12 仅建空表；test_api_task_deletion.py:128 及 test_api_task_deletion_migration.py:8 验证旧任务与文件不动。 |
| 原生 uid1001 权限、只运行显式删除、保留 worker 环境链 | 匹配 | infra/hengxin-domestic-deletions.service:8 使用 codex、:12 retention=false、:13 deletions-only；domestic-runtime.py:29 核对环境链及 root uid/gid/mode，:104 用99新指针保留原95配置；:115 运行进程argv/uid检查。 |
| 国内双层关流覆盖 SSE，海外与身份服务保持 | 匹配 | domestic-gate.py:10 的 ^~ /api/v1/；:46 内部/本机TLS/公网六次503；domestic-runtime.py:93 检查其他容器ID，domestic-deploy.py:56 same_settings 及 :75 仅国内服务；test_domestic_safety.py:20 的500065536海外限制保持原文。 |
| 排空 durable/Celery/broker/unacked，超时不强停未知执行 | 匹配 | domestic-drain.py:17、:43 两次稳定空状态，:60 outbox停止后重查再停执行器；test_domestic_safety.py:106 测忙等待，:119 测探测超时。 |
| 国内备份隔离恢复、0029 不改旧行不触发历史删除 | 匹配 | domestic-backup.py:33 真dump/restore_check，:15 行哈希，:27 要求仅多空api_task_deletions；domestic-deploy.py:64 至 :72 按顺序执行；尚未在生产执行，不能声明生产备份成功。 |
| reviewed commit、真实隐私检查、包哈希及包内镜像测试 | 部分实现 | package-domestic.py:43 检查已审快照/commit，:57 比较源码，:75 归档哈希；实际打包被 HIGH-2 阻断，包内安装测试仍属后续发布门禁。 |
| 失败关流留恢复证据，不盲目停未知执行或回灌DB | 匹配 | domestic-deploy.py:91 记录 RECOVERY_REQUIRED 并重新关流，:118 明确无recover入口；test_domestic_deploy.py:80 注入四阶段故障；docs/DOMESTIC-TASK-DELETION-20261015.md“失败恢复操作边界”补充状态驱动人工恢复。现有实现支持安全停留，不等于已验证可自动回滚。 |
| UI 与既有设计一致、窄屏标签不越界 | 局部匹配 | CliActivityTag.vue:3 是 primary/small ElTag；RealTaskDetail.vue:135 flex-wrap；已目视 output/playwright/api-activity/running-list.png 与 running-narrow.png：原状态、蓝色小标签、正式成品入口可见，390px标签在卡片内。Stage 2邻居基准页实时对比未执行。 |

## 未实现、漂移与发布边界

- 未发现合同外新页面或统计/筛选功能。回执 API、表与 native service 均为真实删除所需（router.py:113、deletion_models.py:11、infra/hengxin-domestic-deletions.service:1）。
- `domestic-deploy.py:118` 没有恢复子命令不单独构成 HIGH：盲目回灌数据库反而违反本次明确约束。审查期间主线程补充了普通 Markdown 文档（不改变代码 candidate），reviewer 已读取：docs/DOMESTIC-TASK-DELETION-20261015.md“失败恢复操作边界”明确开流前无活动/无回执才恢复旧应用；开流后或无法证明未开流则保留0029向前修复；完整Compose链与99指针/前端/代理恢复，禁止回灌DB。可认定人工恢复路径已描述，但不能将文档步骤写成已完成的生产恢复验证。
- 生产删除、付费生成与线上安装未执行；此报告不授予生产功能实测结论。

## 已读取的测试与编译证据

下列为工作区日志原始输出摘录，不是 reviewer 重跑全部测试的声明。

`output/api-ui-tests.log`：

```text
ℹ tests 367
ℹ suites 0
ℹ pass 367
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8952.8878
```

`output/api-ui-typecheck.log`：

```text
npm warn Unknown project config "package-manager-strict-version". This will stop working in the next major version of npm. See `npm help npmrc` for supported config options.
npm warn Unknown project config "manage-package-manager-versions". This will stop working in the next major version of npm. See `npm help npmrc` for supported config options.

> hengxin-smart-image-frontend@0.2.37 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

`output/api-ui-build.log` 结尾：

```text
dist/assets/index-Cna1t7aF.js                                                             963.71 kB │ gzip: 307.80 kB
✓ built in 45.36s
```

`output/playwright/api-activity/report.json`：

```json
{"lists":8,"deletes":2,"errors":[]}
```

该浏览器证明隔离 mock 下的交互，不证明真实删除 DTO；HIGH-1 已独立反证。

收尾已取得并实际解析 `output/domestic-backend-final.xml`，冻结候选 Linux 全量后端为 2515 passed、195 skipped、0 failures、0 errors。原始 testsuite 属性如下：

```text
{'name': 'pytest', 'errors': '0', 'failures': '0', 'skipped': '195', 'tests': '2710', 'time': '313.240', 'timestamp': '2026-10-15T07:32:42.999344+00:00', 'hostname': '110fbbdedba6'}
```

此前Unix socket路径失败来自旧运行快照，当前候选使用/tmp/hx-ipc短路径并已通过最终全量。主线程另报真实PG、Linux专项和发布专项通过，reviewer已检查对应测试实现。全量后端通过不抵消前后端契约和实际打包失败。

## 交接

修复两个 HIGH，并将真实后端 DTO 和真实打包源文件纳入验证；重新 review-prepare 后从 Stage 1 重派审查，再执行 Stage 2。不得针对当前 candidate 登记两阶段 PASS。
