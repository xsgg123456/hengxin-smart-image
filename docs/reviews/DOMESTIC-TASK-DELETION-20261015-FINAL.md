# 国内 API 执行提示与真实删除：最终独立两阶段复审

- 日期：2026-10-15；分支：`codex/domestic-task-deletion`；基线 HEAD：`469be7b`。
- candidateId：`899a00b62e7b111b3a033b7599fc30f910608fc137c4c796f88f6a09e090c378`。
- **Stage 1：PASS。Stage 2：PASS。当前范围无新增 HIGH / MEDIUM 阻断。**
- 本报告批准的是上述代码快照的实现审查，不代表安装包已生成、安装镜像测试已完成或生产部署已完成。完整历史发布测试仍有一项既存失败，详见下文；不得称全部发布测试绿色。
- reviewer 读取 code-review skill、docs/HARNESS-REVIEW.md、上轮报告及合同原文；重新对照当前实现、独立运行测试与真实源码隐私预检，并启动隔离浏览器复核渲染。未修改受控源码、未提交、未登记 approve、未操作生产。按主 Agent 后续授权，仅在 output 下增加隔离浏览器证据。

## 范围与合同

产品合同：Product-Spec.md:1166；开发范围：DEV-PLAN.md:1427；视觉合同：Design-Brief.md 最后“国内 API 轻量执行提示与删除”条目；发布与人工恢复边界：docs/DOMESTIC-TASK-DELETION-20261015.md:5。

范围为 review-status 列出的全部 54 个受控文件：后端活动投影、删除准入/清理/围栏/迁移、相关既有回归测试；前端客户端/类型/标签/列表/详情/轮询与测试；原生删除服务；隔离浏览器脚本；国内发布及打包脚本与测试。精确文件清单见本报告末尾。上轮报告只作为问题线索，不沿用旧 PASS。

## Stage 1：Spec Compliance

| 合同条目 | 结论及本次证据 |
|---|---|
| 列表、对应图片卡片显示 CLI 等待修改/图片修改中 | 完整实现。backend/app/modules/api_image_edits/activity.py:10 批量聚合实际 turn/job；presentation.py:14、summaries.py:13 输出两级字段；frontend/src/views/hengxin/api-image-edits/RealRecords.vue:11、RealTaskDetail.vue:26 使用 CliActivityTag.vue:2。独立浏览器实际观察 queued/running 两处状态。 |
| CLI 结束消失，保持原 API 状态、统计、筛选、正式成品 | 完整实现。activity.py:17 只有已终结证据归 idle；frontend/src/types/api-image-edits.ts:35 映射标签；RealRecords.vue:42 原统计仍按 API 状态。backend/tests/test_api_cli_activity.py:46 检查投影且正式版本不变；浏览器结束后标签消失，当前 V1 始终可见。 |
| 复用现有轮询及修改弹窗，关闭重开同步 | 完整实现。frontend/src/views/hengxin/api-image-edits/use-records.ts:55 原轮询加入 CLI 活动判断，RealTaskDetail.vue:44 保留原修改组件；frontend/tests/records-polling.test.ts:65 覆盖关闭/重开/结束。本次该真实 composable 测试通过，浏览器关闭后等待轮询、再重开成功。 |
| API 排队/执行/重试/收图/未知禁止删除 | 完整实现。backend/app/modules/api_image_edits/deletion_state.py:26 同时检查 task/item/attempt/channel，非终态、未结束、任何租约均拒绝。tests/test_api_task_deletion.py:37 及 test_api_task_deletion_recovery.py:18 覆盖；后者实际调用 failure/collection 路径，终态遗留重试材料不冒充执行。独立专项通过。 |
| CLI 排队/执行/停止/未知禁止，候选/待回复须结束 | 完整实现。deletion_state.py:51 联查 turn/job/finish/lease/identity；deletion.py:64 在原生节点核验原进程已退出才清理。tests/test_api_task_deletion.py:58、:67、:82 覆盖候选与待回复；test_api_task_deletion_faults.py:73 覆盖活进程、错节点、无法核实，保留对象与目录。 |
| 前端禁用并解释原因，具名确认永久范围 | 完整实现。frontend/src/types/api-image-edits.ts:36 默认无法确认即禁用；RealRecords.vue:15 tooltip；:52 ElMessageBox 插值纯文本任务名及完整不可恢复范围。独立浏览器验证取消请求数为 0，确认才受理；没有 HTML 渲染或失效引导。 |
| 受理后拒绝新操作、claim/adopt/迟到结果 | 完整实现。backend/app/modules/api_image_edits/deletion.py:24 channel→task→receipt 锁定准入；service.py:24、claims.py:46/:91、conversation_runtime.py:29 检查持久围栏；versions.py:65 的 target 经过 find_task 锁定，现有 submit/adopt 继续使用该入口。test_api_task_deletion_postgres.py:36、:59、:71 分别覆盖独立事务竞争与拒绝；冻结后 Linux 完整 XML 中这些需 PG 用例跳过，真实 PG 专项另由主 Agent 提供，不能混称为本地 SQLite 验证。 |
| 与自动清理互斥 | 完整实现。retention/api.py:29、retention/worker.py:45 在父锁后拒绝有删除回执任务；deletion_state.py:61 拒绝已有 pending retention。tests/test_api_task_deletion.py:140、test_api_task_deletion_faults.py:38、test_api_task_deletion_postgres.py:67 对照该行为。 |
| 任务/图片/版本/轮次/会话/排队记录真删 | 完整实现。deletion_records.py:15 删 ConversationEvent/Turn/Job/Outbox/Conversation/Retention/Capacity/Version/Attempt/Item/Operation/Dispatch/Task，并删独占文件与衍生记录。tests/test_api_task_deletion.py:82 经过真实 HTTP 受理、执行清理、逐表与对象断言；本次独立执行通过。 |
| 专属原图/素材/结果/候选/标注/缩略图清理 | 完整实现。deletion_files.py:25 枚举任务、版本、轮次及快照 fileIds，:80 删除精确对象与任务文件衍生前缀，包含中断写入；deletion.py:80 删除后 stat，假成功视作失败。tests/test_api_task_deletion.py:94、faults.py:21 的 false_success 断言通过。 |
| 工作资料真删，保留共享引用、Skill、认证、运行环境、邻居任务 | 完整实现。deletion_files.py:44 检查其他任务及通用 FileRecord/SkillVersionRecord；:64 先持久冻结独占 ApiFile。deletion_paths.py:43 仅 UUID 私有目录，逐祖先 NOFOLLOW，拒绝未知链接/硬链接/跨设备；:15 只放行已知沙箱工具链接并仅 unlink。tests/test_api_task_deletion.py:123 检查最后引用才删；paths.py:24、:40、:77、:87、:114 检查邻居、认证、symlink、IPC、真实 uid。本地未冒称运行 Linux 专属用例，Linux 完整结果已解析为无失败。 |
| 最少统计脱敏、无内容回执 | 完整实现。deletion_records.py:19 preserve 后 task_name 改为“已删除任务”；deletion.py:131 完成后清空 manifest/error；deletion_models.py:11 无聊天/提示词/图片内容字段。tests/test_management_api_usage.py:74、test_usage_generated_totals.py:70 保留统计，test_api_task_deletion.py:106 验证完成回执无内容。 |
| 持久可恢复、失败可重试、全部物理完成才成功 | 完整实现。deletion.py:94 分事务持久文件围栏、再次锁定核查、先清目录和对象再事务删记录；:134 失败状态与退避落库，:145 重启续扫；faults.py:21 注入目录/对象/数据库/假成功并重新 run_pending。本次独立 55 个后端专项均通过。 |
| 前端 202 不报成功，失败重试，真实 deleted 回执才移除 | 完整实现；上轮 HIGH-1 已消除。后端 deletion.py:20 永远输出 message，前端 types/api-image-edits.ts:9 为必填 string/null，api-image-edits-validate.ts:57 接受 null 并拒绝缺字段及对象；use-records.ts:84 仅 deleted 移除。本次客户端/轮询 5 测试通过；真实浏览器覆盖 DELETE 202、GET deleting/failed/deleted 的 message:null，非法 deleted.message={} 保留行且无成功 toast。 |
| 不追溯旧软删 | 完整实现。deletion.py:35 拒绝旧 deleted_at；0029_api_task_deletions.py:12 仅建表，downgrade 保留围栏；tests/test_api_task_deletion.py:112 与 migration 测试证明旧文件/行不动。 |
| 原生 uid1001、只显式删除、保留完整环境链 | 完整实现。infra/hengxin-domestic-deletions.service:8 使用 codex、:12 retention=false、:13 deletions-only；scripts/release/domestic-runtime.py:29 核对既有两份 EnvironmentFile 与 root 权限，:104 只写99新指针，:115 验证实际 cwd/argv/uid。安装后的具体值仍须发布阶段实查。 |
| 国内双层关流含 SSE，不误伤海外/身份 | 完整实现。domestic-gate.py:9 的 ^~ /api/v1/ 覆盖正则 SSE，:46 校验内部/本机TLS/公网六个503；domestic-runtime.py:93 核对海外/身份容器ID和其他原生目录，domestic-deploy.py:75 仅国内五服务。test_domestic_safety.py:20 保留海外 500065536 字节限制，独立21专项通过。 |
| 排空 durable/Celery/broker/unacked，两次稳定，未知/超时不强停 | 完整实现。domestic-drain.py:17 收集真实探针，:43 两次连续零，:60 停 outbox 后再复核；:24 超时仅终止探针自身进程组。test_domestic_safety.py:94/:106/:119 覆盖被忙打断、超时不得停执行器。 |
| 国内备份隔离恢复，迁移不改旧行 | 完整实现。domestic-backup.py:15 逐表计数与全行哈希，:33 真 dump/restore_check，:27 要求只增加空回执表；domestic-deploy.py:67 备份验证后迁移再 verify_after。代码路径完整，但本次未执行生产备份/恢复。 |
| 已审提交、真实隐私审计、安装包及镜像验证门禁 | 实现完整，实际发布待执行。上轮 HIGH-2 已消除：package-domestic.py:15/:20 不再选择 helpers，:49 仍要求 helpers 已提交，:61 保持原隐私检查。独立读取实际源码+dist共1336文件，privacy/validate PASS；test_domestic_package.py:96 真实源码回归通过。:43 的 build 必须 clean+reviewed，domestic-deploy.py:112 调用包内镜像测试，overseas-deploy.py:29 核验镜像源文件哈希并以 --init/--network none 测试，随后 image_id 门禁。 |
| 失败关流，状态驱动人工恢复，不回灌DB、不退旧围栏代码 | 完整实现。domestic-deploy.py:92 记录 phase 并重新关流，不强停未知执行器；:118 明确无 recover。docs/DOMESTIC-TASK-DELETION-20261015.md“失败恢复操作边界”要求开流后/回执非空保留0029并向前修；开流前可证明空闲时恢复完整原配置链。仅审查了路径和故障测试，不声称实际生产恢复验证。 |

以上 backend/、frontend/、infra/ 相对路径均以 `hengxin-smart-image/` 为根。本轮合同没有未实现的开发条目；Git提交、真实安装包、安装后与生产验收是顺序在审查后的工作，不因本报告被提前标记完成。

## Stage 2：Code Quality

| 检查 | 结论与证据 |
|---|---|
| 结构、文件长度、类型 | PASS。全部54个受控文件逐个计数均≤300行；新模块职责区分准入、文件引用、路径清理、业务清理和调度（deletion_state.py:26、deletion_files.py:64、deletion_paths.py:43、deletion_records.py:15、deletion.py:94）。前端新增代码没有 TypeScript any，ApiDeletion 必填 nullable 与生产 JSON 一致；独立 vue-tsc exit 0。 |
| 并发锁与失败恢复 | PASS。deletion.py:24/:56 保持 channel→task→receipt 锁序；文件冻结持久提交后再物理处理，并在物理阶段重新检查共享归属；文件 find_file 状态保护在 files.py:19，提交入口使用加锁读取，防止失败后复用半删文件。faults.py:21、postgres.py:86/:101 测重复清理、失败续扫与冻结文件拒复用。 |
| 安全扫描 | PASS。54文件搜索 eval、dangerouslySetInnerHTML、innerHTML、前端 KEY/SECRET/TOKEN、用户绝对路径、硬编码密码及常见key前缀，无新危险命中。domestic-backup.py:19 的拼接表名先用限定正则验证且来源pg_tables；deletion 路径采用UUID/目录描述符/NOFOLLOW，未知节点与存储异常关闭式失败。扫描的 Python any 是内建函数，不是类型绕过。无新增依赖版本；既有依赖审计 high 70 是基线风险，不称依赖无漏洞。 |
| 测试真实性 | PASS。实际客户端测试使用完整后端 DTO 与202状态（frontend/tests/api-image-activity.test.ts:33），而非省略字段；真实源码隐私测试不是空内容 fixture（scripts/release/test_domestic_package.py:96）。后端恢复测试调用实际失败/收图流程（test_api_task_deletion_recovery.py:18），注入失败后重新维护入口读取持久状态（faults.py:47）。PG测试用独立事务；uid测试实际切1000/1001，未把 mock 当权限实测。发布流程单测证明顺序/失败边界，不冒称生产备份成功。 |
| 既有测试修改合理性 | PASS。test_api_image_domain.py:64、test_api_image_task_slots.py:59 改为排队不可删除符合新合同；test_capacity_admission.py:87 先验证受理不释放容量，再验证物理清理完成释放；test_list_summaries.py:36 保持恒定查询数14且禁止提示词/聊天/结果payload投影，没有用删断言掩盖功能缺失。 |
| 视觉邻居比较与裁切 | PASS。reviewer 实际打开同一生产构建的隔离页面，分别渲染既有 idle 基准、queued/running、390px、失败重试、完成空态；亲自目视 `output/playwright/api-activity-final-review/neighbor-idle-list.png`、`running-list.png`、`neighbor-idle-detail.png`、`queued-detail.png`、`running-narrow.png`、`delete-failed.png`、`deleted.png`。Art/Element 字体、卡片、按钮和原状态一致；蓝色 small 标签独立于绿色原状态，布局自然换行；390px标签处于卡片内，失败行重试按钮处于单元格内，页脚返回可达。RealTaskDetail.vue:135 flex-wrap 与 CliActivityTag.vue:13 小间距对应实图。列表/卡片使用同组件 idle 邻居基准，未冒称与未知设计稿比对。 |
| 发布影响范围 | PASS。domestic-runtime.py:67 将原完整Compose链叠加新镜像并 same_settings；:93 验证其他组身份不变；domestic-deploy.py:75 只重建国内五服务。删除服务独立、retention关闭；共享前端仅更入口与资产，不修改海外路由、后台或认证实现。实际服务器核验仍是发布门禁。 |
| Spec 漂移 | 未发现。新增回执API（router.py:113）、空表（deletion_models.py:11）与原生服务都对应持久真删；没有新增统计、筛选、业务页面或收费行为。 |

## 本次独立执行与原始输出

前端实际客户端/轮询（exit 0）：

```text
node --import tsx --test tests/api-image-activity.test.ts tests/records-polling.test.ts
ℹ tests 5
ℹ suites 0
ℹ pass 5
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 820.9937
```

后端专项（项目 `.venv/Scripts/python.exe`，exit 0）：

```text
pytest -q -p no:cacheprovider tests/test_api_task_deletion.py tests/test_api_task_deletion_faults.py tests/test_api_task_deletion_recovery.py tests/test_api_task_deletion_migration.py tests/test_api_cli_activity.py
55 passed, 2 warnings in 14.25s
```

两条 warning 是现有 Starlette TestClient/httpx 与 anyio BlockingPortal 废弃提示。系统 Python 首次尝试缺 pytest，随后改用项目现有解释器成功；未安装或改变依赖。

国内发布专项（exit 0）：

```text
pytest -q -p no:cacheprovider scripts/release/test_domestic_package.py scripts/release/test_domestic_deploy.py scripts/release/test_domestic_safety.py
.....................                                                    [100%]
21 passed in 0.63s
```

真实源码和最终dist预检（exit 0）：

```json
{"files": 1336, "privacy": "PASS", "validate": "PASS", "helpersExcluded": true, "exceptions": {"backend/tests/test_public_messages.py": ["existing synthetic negative fixture", "existing synthetic negative fixture"], "backend/tests/test_round_materials.py": ["existing synthetic negative fixture"]}}
```

精确豁免仍为既有2个文件、3个合成负例匹配（package-delivery.py:28），不是放宽规则或新增豁免。此次仅预检，没有伪造 clean/commit 来调用正式 build。

隔离浏览器本次运行（exit 0）：

```json
{"lists":11,"deletes":2,"errors":[]}
```

完整记录：output/playwright/api-activity-final-review/report.json。两个 DELETE 均202+message:null，正常查询与完成均 message:null；非法 deleted.message={} 被拒绝，最终合法回执才 toast 并移除。所有API/图片请求受专用context拦截，未发生产写操作。邻居截图是在现有受控浏览器脚本基础上于 output 临时副本追加 idle 状态，不修改源文件。

独立类型检查（exit 0，原始输出）：

```text
npm warn Unknown project config "package-manager-strict-version". This will stop working in the next major version of npm. See `npm help npmrc` for supported config options.
npm warn Unknown project config "manage-package-manager-versions". This will stop working in the next major version of npm. See `npm help npmrc` for supported config options.

> hengxin-smart-image-frontend@0.2.37 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

已直接读取的冻结构建日志（主 Agent 执行，reviewer 未重跑构建；output/api-ui-build.log 结尾原文）：

```text
dist/assets/index.vue_vue_type_style_index_0_lang-BfGQNTy1.js                             814.14 kB │ gzip: 275.63 kB
dist/assets/index-BsDlh9gU.js                                                             963.71 kB │ gzip: 307.80 kB
✓ built in 34.20s
```

output/api-ui-tests.log 原文：

```text
ℹ tests 368
ℹ suites 0
ℹ pass 368
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9114.4995
```

实际解析 output/domestic-backend-final.xml 的原始属性：

```text
{'name': 'pytest', 'errors': '0', 'failures': '0', 'skipped': '195', 'tests': '2710', 'time': '313.240', 'timestamp': '2026-10-15T07:32:42.999344+00:00', 'hostname': '110fbbdedba6'}
```

即冻结 Linux 全量2515通过、195跳过、0失败。真实PG删除5通过、旧API执行PG2通过、Linux专项52通过是主 Agent 独立环境证据；reviewer 核查相应测试实现及最终全量XML，不冒称在本机重跑PG/uid专项。

## 已知基线失败与交接限制

output/domestic-release-tests.xml 实际属性：

```text
{'name': 'pytest', 'errors': '0', 'failures': '1', 'skipped': '1', 'tests': '684', 'time': '15.873', 'timestamp': '2026-10-15T15:40:19.907882+08:00', 'hostname': 'zhangshuai'}
scripts\release\test_release_native.py:100: in test_frontend_manifest_matches_seven_native_files
    self.assertTrue(manifest['composeBaseOverlays'][-1].endswith('annotation-20260924-6b43b3c/api-override.yaml'))
E   AssertionError: False is not true
```

该历史测试期待 annotation 为最后 overlay，而 scripts/release/image-inputs-frontend.py:39 已在 HEAD 中追加 materials。`test_release_native.py`、`image-inputs-frontend.py`、`image-inputs-native.py` 相对 HEAD 均无差异。本轮新国内部署使用读取的完整Compose链，未进入此历史入口；不能据此宣布完整发布套件绿色，也不把该既存断言问题归为本轮引入缺陷。当前新增国内专项21/21通过。

同一 candidate 的 Stage 1 / Stage 2 均通过。由主 Agent 使用 review-approve 登记此报告和该 candidate，再按授权执行中文提交、正式包构建、包内镜像测试与生产部署。开流后或回执非空必须保留0029围栏并向前修；本报告不授权跳过这些安装/生产验证，不代替真实发布完成凭据。

## 精确受控范围

下列清单由本次 review-status 的 changedFiles 取得；报告及 output 证据不改变受控代码快照。

- `hengxin-smart-image/backend/app/modules/api_image_edits/activity.py`
- `hengxin-smart-image/backend/app/modules/api_image_edits/claims.py`
- `hengxin-smart-image/backend/app/modules/api_image_edits/conversation_runtime.py`
- `hengxin-smart-image/backend/app/modules/api_image_edits/deletion.py`
- `hengxin-smart-image/backend/app/modules/api_image_edits/deletion_files.py`
- `hengxin-smart-image/backend/app/modules/api_image_edits/deletion_models.py`
- `hengxin-smart-image/backend/app/modules/api_image_edits/deletion_paths.py`
- `hengxin-smart-image/backend/app/modules/api_image_edits/deletion_records.py`
- `hengxin-smart-image/backend/app/modules/api_image_edits/deletion_state.py`
- `hengxin-smart-image/backend/app/modules/api_image_edits/models.py`
- `hengxin-smart-image/backend/app/modules/api_image_edits/presentation.py`
- `hengxin-smart-image/backend/app/modules/api_image_edits/router.py`
- `hengxin-smart-image/backend/app/modules/api_image_edits/service.py`
- `hengxin-smart-image/backend/app/modules/api_image_edits/summaries.py`
- `hengxin-smart-image/backend/app/retention/api.py`
- `hengxin-smart-image/backend/app/retention/worker.py`
- `hengxin-smart-image/backend/migrations/versions/0029_api_task_deletions.py`
- `hengxin-smart-image/backend/tests/files_helpers.py`
- `hengxin-smart-image/backend/tests/test_api_cli_activity.py`
- `hengxin-smart-image/backend/tests/test_api_image_domain.py`
- `hengxin-smart-image/backend/tests/test_api_image_revision_guards.py`
- `hengxin-smart-image/backend/tests/test_api_image_task_slots.py`
- `hengxin-smart-image/backend/tests/test_api_task_deletion.py`
- `hengxin-smart-image/backend/tests/test_api_task_deletion_faults.py`
- `hengxin-smart-image/backend/tests/test_api_task_deletion_migration.py`
- `hengxin-smart-image/backend/tests/test_api_task_deletion_paths.py`
- `hengxin-smart-image/backend/tests/test_api_task_deletion_postgres.py`
- `hengxin-smart-image/backend/tests/test_api_task_deletion_recovery.py`
- `hengxin-smart-image/backend/tests/test_capacity_admission.py`
- `hengxin-smart-image/backend/tests/test_list_summaries.py`
- `hengxin-smart-image/backend/tests/test_management_api_usage.py`
- `hengxin-smart-image/backend/tests/test_usage_generated_totals.py`
- `hengxin-smart-image/frontend/package.json`
- `hengxin-smart-image/frontend/src/api/api-image-edits-validate.ts`
- `hengxin-smart-image/frontend/src/api/api-image-edits.ts`
- `hengxin-smart-image/frontend/src/types/api-image-edits.ts`
- `hengxin-smart-image/frontend/src/views/hengxin/api-image-edits/CliActivityTag.vue`
- `hengxin-smart-image/frontend/src/views/hengxin/api-image-edits/RealRecords.vue`
- `hengxin-smart-image/frontend/src/views/hengxin/api-image-edits/RealTaskDetail.vue`
- `hengxin-smart-image/frontend/src/views/hengxin/api-image-edits/use-records.ts`
- `hengxin-smart-image/frontend/tests/api-image-activity.test.ts`
- `hengxin-smart-image/frontend/tests/records-polling.test.ts`
- `hengxin-smart-image/infra/hengxin-domestic-deletions.service`
- `scripts/api-activity/browser.mjs`
- `scripts/release/domestic-backup.py`
- `scripts/release/domestic-deploy.py`
- `scripts/release/domestic-drain.py`
- `scripts/release/domestic-gate.py`
- `scripts/release/domestic-runtime.py`
- `scripts/release/domestic-verify.py`
- `scripts/release/package-domestic.py`
- `scripts/release/test_domestic_deploy.py`
- `scripts/release/test_domestic_package.py`
- `scripts/release/test_domestic_safety.py`

收尾快照复核：currentId 与派发 candidateId 完全相同，54个受控文件未在审查期间变化；approved=false，由主 Agent 登记。

主 Agent 收尾仅同步 DEV-PLAN 第5步失败恢复措辞为状态驱动恢复、开流后保留0029向前修，与已审发布文档和实现一致；这是普通Markdown合同澄清，不改变54文件受控快照或本次结论。
