# 国内五模块退役独立审查（2026-10-16）

## 快照、范围及状态

- 初始 candidateId：`635dd85ea79463554def4d284dc646ad5e86aee1351231b97dbee325c8986c7d`。
- 中间 candidateId：`325cf026b4c344aa88991c899101aa24008299997a2c7c48ae3b32092cdb21af`。
- **最终 candidateId：`2d74fa56fe64546dbaba18f7bad43028177b2a5e878a976209fe1a52263c0630`。Stage 1：PASS；Stage 2：PASS。**
- 审查中代码确有变化：中间快照复核5文件（两个退役残留、三个旧测试）；最终快照复核3文件（恢复API 0024用例、两个浏览器测试）。每轮都重新核对差异，结束时currentId与最终候选一致。
- 范围：相对 `a264e15` 的完整工作树；国内五模块前后端删除、历史迁移冻结、0030、共享执行/媒体/Skill验证、前端入口回收及发布工具。此前国内 retention 开启文档一并核对。海外运行时代码只涉及四处共享模块导入迁移；生产海外不升级。
- 依据：`Product-Spec.md:941`、`Design-Brief.md:1`、`DEV-PLAN.md:1`、`docs/DOMESTIC-RETIREMENT-20261016.md:3`，并遵循 `.agents/skills/code-review/SKILL.md:18` 与 `docs/HARNESS-REVIEW.md:7`。
- 三项MEDIUM发现已全部修复并复验；最终无未解决的本次变更HIGH/MEDIUM。下述既有依赖/文件规模及环境专项测试限制保留。审查者未修改产品代码、未登记批准、未操作生产。

## Stage 1：Spec Compliance

### 发现与修复

1. **MEDIUM，已修复**：旧菜单专属 `newTask` 分支残留。新 `frontend/src/utils/navigation/jump.ts:21` 直接路由跳转；不再执行旧图片处理逻辑。
2. **MEDIUM，已修复**：钉钉授权与回调的旧默认地址残留。新 `backend/app/modules/auth/router.py:43`、`:73` 默认 `/api-image-edits/create`；`dingtalk.py:66` 保持回跳白名单防护。
3. **MEDIUM，已修复**：整删 `HEAD:backend/tests/test_retention_migration_legacy_pg.py:26` 时误删纯API用例 `test_pg_migration_0024_repeated_preserves_business_and_receipts`。它检查0024重复升级、兼容降级、API任务/图片/对话、活动时间与删除回执，不属于旧CLI专属测试。0030用例不能代替0024原用例。最终已恢复至 `backend/tests/test_retention_migration_pg.py:15`，独立AST比较与原函数完全一致；真实PG补跑通过。

以下表格中 backend/frontend 均相对 `hengxin-smart-image/`；每项只判定已检查的实现与测试，不代表生产执行已经完成。

### 完整实现及逐条证据

| 需求条目 | 结论与证据 |
| --- | --- |
| 五模块页面、服务、路由、模型、旧调度分支删除 | 匹配。`backend/app/main.py:43` 仅挂载现行身份、API换图和管理路由；`backend/app/worker/tasks.py:46` 保留 `api_cli_edit`，删除 generation/Skill分支；`backend/tests/test_domestic_retirement.py:166` 和 `test_contracts.py:10` 检查旧HTTP入口不存在。目录删除与HEAD逐项对照。 |
| 共享执行互斥、心跳先抽离 | 匹配。`backend/app/execution/models.py:5`、`backend/app/worker/models.py:7`；独立AST比较 ExecutionGate/WorkerHeartbeat 类与原定义完全一致。`conversation_runtime.py:73` 仅剔除旧generation计数；API并发与过期轮次扫描仍在 `worker/outbox.py:23`。 |
| 海外Skill校验与权限不变 | 匹配。`backend/app/core/skill_package.py:27`、`contracts/skill_package.py:6` 与原实现AST完全一致；海外仅 `execution/materials.py:8`、`management/installed_tree.py:11`、`packages.py:6`、`schemas.py:5` 改导入。海外权限、API、数据库迁移没有功能改动。 |
| 共享上传、预览、标注、下载组件保留 | 匹配。`frontend/src/views/hengxin/components/` 仅删除旧业务组件；现行API页面/共享标注代码无行为改动。`frontend/tests/api-image-conversation.browser.mjs:1` 保留完整画布、标注、候选采用流程，结构化结果在 `output/playwright/api-image-conversation/result.json:1`。 |
| 国内全部角色菜单、搜索、旧固定/当前标签和缓存回收 | 匹配。`frontend/src/router/modules/index.ts:4`、`business-route-access.ts:13`、`routes/staticRoutes.ts:14`、`store/modules/worktab.ts:439`、`domestic-main.ts:37`；独立真实浏览器对四角色注入旧localStorage标签/搜索后验证全部回收，旧地址及别名均落API新建。 |
| 默认入口与身份回跳 | 匹配。`frontend/src/api/hengxin/session.ts:25`、`identity-routing.ts:7`；后端回跳白名单 `backend/app/modules/auth/dingtalk.py:18`、`:66`；上述两处默认值残留已修。 |
| 系统配置去Skill绑定和目录请求，保留现行配置与审计 | 匹配。`backend/app/modules/management/settings.py:35`、`:70`；`frontend/src/views/hengxin/admin/settings.vue:12`、`:33` 和 `settings-editor.ts:5`。独立浏览器实际修改并发1→2，保存v1→v2，断言无Skill请求/字段。历史SettingsAudit未清除。 |
| 调用统计、执行监控、用户/角色保留 | 匹配。`backend/app/main.py:43` 保留管理路由；`management/api_monitor.py:112` 只去旧CLI占用；`frontend/src/views/hengxin/admin/monitor.vue:15` 同步显示现行CLI轮次，`usage.vue:1` 使用现有ApiUsage。 |
| API新建、上传、原图/素材、记录筛选分页、调度重试 | 匹配。`backend/app/modules/api_image_edits/router.py:38`、`:86`、`:91`、`:103` 与原HEAD实现未改变；`conversation_runtime.py:73`、`capacity/observe.py:42` 只去旧业务占用。现行API专项和全套测试覆盖。 |
| API图片修改、文字修改、文案修复、标注、CLI续聊/SSE/停止/候选采用 | 匹配。`backend/app/modules/api_image_edits/router.py:131`、`conversation_router.py:19`、`:26`、`:32`、`:38`、`:57` 保留；API对话浏览器结构化结果及审查者独立 `test_api_cli_conversation.py` 通过。 |
| 历史版本、下载、主动删除与跨任务引用保护 | 匹配。`backend/app/modules/api_image_edits/deletion_files.py:41` 保留ApiTask/Item/Version/Turn及冻结JSON引用检查，并增加同域对象别名保护；`:76` 保留衍生图保护。`deletion.py:94` 业务流程未改；迁移保护API别名旧Skill对象后才删旧表。 |
| 24小时/7天清理、首次发现宽限期、活动会话保护 | 匹配。`backend/app/retention/worker.py:18` 只删除legacy域，已有初始化时间不重置；`:46` 保留PG锁、批次、重试；`:105` 保持自动清理3600秒扫描。`retention/api.py:37`、`:86` 不变；`test_retention_concurrency.py:66`、`:103`、`:140`、`:201` 覆盖并发/候选采用/首次宽限期。 |
| 历史0005/0006/0007迁移链冻结，不向运行时注册旧表 | 匹配。`backend/migrations/legacy_schema.py:5` 独立Base和外键占位表；`versions/0005_tasks.py:3`、`0006_execution.py:3`、`0007_archives.py:3` 仅改模型来源，revision顺序不变。`migrations/env.py:11` 只注册现行模型。 |
| 0030删除精确22表、逆序、循环FK、禁止CASCADE | 匹配。`backend/migrations/versions/0030_retire_legacy.py:11` 明列22表；`:81` 解除 execution_rounds→image_versions循环；`:84` 按固定顺序DROP，无CASCADE。 |
| 非空旧业务、未知引用、运行中旧任务拒绝破坏性升级 | 匹配。0030 `:33` 限PostgreSQL，`:42` 锁定全部表后验证；`:43` 未知保留表FK、`:47` 非空旧业务、`:51` 活动作业、`:55` 保留表对旧Job引用、`:65` 缩略图所有权、`:68` legacy清理状态、`:71` API别名均阻断。`test_domestic_retirement.py:123` 故障场景断言事务前后数据相同。 |
| 保留所有API/认证/设置审计/容量/心跳与清理状态 | 匹配。0030仅删指定Job kind、originals域、legacy_cli域及defaultSkillIds键；不按kind=cli清容量。`test_domestic_retirement.py:77` 真实PG填充API业务、容量预留、审计、心跳、对象回执与主动删除记录，检查所有允许范围以外数据逐行相同，并执行发布SQL指纹。 |
| 空库全链与0029带数据升级 | 匹配。`test_domestic_retirement.py:40` 实际运行0001–0029再0030；`:68` 验证运行时metadata无旧表；`:77` 带数据升级；9项0030测试有真实PG验证。 |
| 当前生产基线0029/.39/海外0017，不复用旧基线 | 匹配。`scripts/release/retirement-runtime.py:52` 三项准确断言；`:70` 校验真实Docker与Compose配置、当前retention=true；`:37` 记录容器镜像ID/native PID/cwd/配置哈希。发布前再次核对快照漂移。 |
| 国内入口关闭、执行器/删除/清理全部排空 | 匹配。`scripts/release/retirement-deploy.py:68` 先双层gate关闭再停API；`retirement-drain.py:30` 确认队列、删除回执/retention对象与pending状态，停止3个旧native，保留超时拒绝；复用domestic-drain逐阶段核对队列与durable状态。 |
| 完整备份、隔离恢复、迁移后逐表精确校验 | 匹配。`retirement-backup.py:83` 保存配置/完整dump，隔离无网络容器恢复并比原始全表指纹；`:48` 仅投影已审0030允许变化；`:112` 迁移后比较原始数据，不能用过滤器掩盖旧行残留。 |
| 三个native同旧cwd切换、retention开关/批25/小时策略保持 | 匹配。`retirement-native.py:22` 采集实际PID/cmdline/env/服务策略；`:76` 要求三者原cwd相同，只改代码目录和目标Python；`:101` 比较所有业务env/资源策略；`retirement-verify.py:33` 观察新invocation实际删除循环与成功清理扫描。 |
| 海外/身份生产不升级、不重启、不迁移 | 匹配。`retirement-deploy.py:88` 仅启动国内服务；`retirement-runtime.py:58` 对照海外/身份容器ID、实际镜像、native PID/cwd及海外0017；共享前端发布采用已有资源哈希碰撞检查。 |
| 不可逆失败不自动旧代码回退/数据库覆盖 | 匹配。`retirement-deploy.py:81` 写不可逆阶段标记，`:98` 异常记录阶段并重新关入口，不调用旧服务恢复；0030 `:88` 明确拒绝无损降级。故障注入测试覆盖drain/backup/fingerprint/switch/verify/public阶段。 |
| 已审提交、隐私审计打包、镜像安装测试 | 工具实现匹配。`scripts/release/package-retirement.py:43` 拒绝退役源码，复用package-overseas的clean tracked/已批准快照/commit字节校验和资源隐私审计；`retirement-deploy.py:118` build走真实镜像源哈希与无网络安装测试。实际提交打包/生产运行属于审查后交付步骤，此报告不冒充执行证据。 |

### Spec 漂移、部分实现、未实现

没有发现新增页面/API/业务表超出下线范围；新共享模块属于搬迁，0030和发布工具属于明确授权。误删API迁移测试已恢复，最终验证已收尾；无部分实现或未实现的本次代码条目。尚未执行的提交打包和生产发布属于后续交付动作，本报告不将其标成产品缺陷或已经通过。

## Stage 2：Code Quality

- 结构与类型：新增运行时代码/迁移/发布工具均小于300行；共享校验器、模型的AST等价已经核实。既有 `frontend/src/store/modules/worktab.ts:1` 为573行（基线已超300），本次只增加无效路由/缓存过滤，记为既有维护债务，不宣称全仓满足行数标准。
- 安全扫描：审查全部新增/修改代码及敏感发布工具，未发现新增硬编码密钥、eval、dangerouslySetInnerHTML、VITE密钥或个人绝对路径。0030 SQL片段来源固定契约/数据库元数据；发布SQL标识符经 `retirement-backup.py:15` 校验、契约通过AST literal读取而不执行。备份、native实际环境快照通过private/umask0077落盘，不输出业务秘密。
- 测试真实性：真实PG覆盖0030失败原子性、API/共享行原样保留及发布指纹SQL；发布cutover顺序/失败测试使用mock验证控制流，不冒称真实生产切换演练。新版本历史迁移测试钉原目标版本，保留升级→降级→再升级；需求迁移逐原列比较任务和运行中Job，断言比旧跨HEAD测试更明确。海外retry参数删除有 `Product-Spec.md:1163` 的解析重试入口退役依据。
- 实际视觉对比：审查者启动本地最终production preview，打开现行API新建与相邻换图记录页并截图、读取computed styles。标题均28px/650/rgb(56,56,83)，常规导航按钮36px高/6px圆角/14px文字，原有卡片、间距及侧栏层级保持。截图 `output/playwright/retirement-review/create.png`、`records.png`，数值 `styles.json:1`。24px粘贴按钮和40px主提交按钮为原有不同用途按钮；未引入重新设计。
- 依赖审计边界：`output/retirement-frontend-audit.json` 原始结果 critical=0/high=36/moderate=34/low=1；锁文件未变。这是既有依赖风险，不是“全仓无安全问题”的证明；本次未引入新依赖或进行未经授权的大范围升级。

## 验证原始输出与限制

审查者独立共享/API/管理/媒体专项命令：

```text
uv run pytest -q tests/test_contracts.py tests/test_skills_packages.py tests/test_api_cli_conversation.py tests/test_management_api_monitor_settings.py tests/test_media_delivery_lifecycle.py tests/test_internal_delivery.py
74 passed, 2 warnings in 8.28s
```

审查者独立浏览器复验：

```text
PASS: 四角色菜单、全部角色旧固定/当前/缓存/搜索标签清理、旧地址及别名落地
PASS: 系统配置读写及现行执行参数完整，无旧Skill请求/字段/选择项
```

执行时先遇3024 preview未启动；启动本地preview后菜单首次遇构建期间加载超时，最终产物稳定后重跑通过。没有把连接失败算成功。

前端全量及最后增量构建：`frontend/output/retirement/tests.log`、`review-fix-tests.log`、`review-fix-typecheck.log`、`review-fix-build.log`：

```text
ℹ tests 280
ℹ pass 280
ℹ fail 0
ℹ skipped 0
> vue-tsc --noEmit
✓ built in 46.76s
```

发布/维护工具 `output/retirement-tools-final.log`：

```text
691 passed, 12 skipped, 237 subtests passed in 37.18s
```

真实HTTP证据：`output/retirement-identity-members.log`、`output/retirement-identity-delete-skills.log`：

```text
PASS ALL member isolation real HTTP integration
PASS ALL requirements review real HTTP integration
PASS ALL delete/archive/installed Skills real HTTP integration
```

第一次不可变Linux全套 `output/retirement-backend-linux-final.log`：

```text
4 failed, 2021 passed, 25 skipped, 6 warnings in 406.16s (0:06:46)
```

4失败分别为历史membership测试升级head却断言0028/0014、已退役解析retry入口、历史0010迁移测试跨到0016列删除。已针对性修正，保留原始失败日志。最终全套与补充测试已通过，详见下方原始输出。

最终不可变Linux完整运行 `output/retirement-backend-linux-verified.log`（四个真实PG测试变量）：

```text
2024 passed, 25 skipped, 6 warnings in 378.71s (0:06:18)
```

25个skip与2049个收集nodeid逐一对齐。22个身份Redis用例因未配置隔离Redis、1个跨UID删除用例需root，随后在无对外端口Redis/隔离root容器连同恢复的0024迁移测试等一起补跑，原始日志 `output/retirement-redis-uid-retention.log`：

```text
38 passed, 2 warnings in 3.11s
```

另1个Windows junction专用测试在Linux按平台跳过，审查者已在本机Windows独立补跑 `tests/test_studio_context_safety.py::test_windows_junction_cannot_import_an_external_directory`：

```text
1 passed in 1.36s
```

唯一未执行的用例是 `backend/tests/test_phase11a_environment.py:168`：它明确要求名为hengxin的现有非root WSL开发运行环境（`:170`），当前容器不符合；这不是产品或0030迁移测试。没有将其宣称通过。全套Linux主运行发生在最后恢复0024单测前，因此使用全套2024通过与新增用例补跑证据组合，不伪称最终2050个用例均在同一个进程执行。

最终两个海外浏览器测试维护只改测试：`frontend/tests/upload-limits.browser.mjs:27` 对现行前三项/查看全部100项UI进行实际检查，保留101上传前拒绝、100上传/发送、移除后补加并精确比对最终100个ID；`overseas-admin-simplify.browser.mjs:27` 补旧归档缺cover时的详情/图片夹具，保留角色、筛选、分页、错误重试与手机裁切断言，并禁止未声明外部请求。原始记录 `output/retirement-browser-refresh.md:34`：

```text
PASS: 101 blocked before upload; 100 upload/send; remove/retry; 500 MB text; desktop/mobile
PASS all-member scope without members.manage, operator filter summary/list, monitor, operator retry, ordinary scope, unified search three fields/reset/page/empty/error/mobile clipping
```

其中500MB浏览器部分只验证文案，不能扩大为实际500MB上传测试。后端文件边界测试与前端数量交互是不同证据。

旧Phase25组合的自动分析断言及overseas-shell主题断言在HEAD原样失败；原始证据分别 `output/retirement-head-identity-phase25.log`、`frontend/output/retirement/head-shell.log`。现行审核→工作台与海外资料/权限/Skill实际HTTP及浏览器已另验。历史自动分析preview脚本不代表当前产品验收；不能据本报告声称所有历史浏览器脚本均绿。

## 交付与批准边界

本报告只审代码与本地/隔离验证；没有执行生产操作。最终candidate已复核，两阶段PASS仅适用于 `2d74fa56fe64546dbaba18f7bad43028177b2a5e878a976209fe1a52263c0630`。只有主Agent可对同一最终candidate执行review-approve；不得向 `.needs-review` 写clean。之后提交、打包镜像安装测试、生产备份/迁移/切换及验收须分别保留实际证据。

## 删除测试逐项核对

下列路径相对 `hengxin-smart-image/`；行号指 `a264e15` 基线已删除文件。逐一读取源码，检查测试直接消费的业务模块/路由。共用ZIP校验 `test_skills_packages.py` 没有删除，已改共享导入；并发助手移至 `backend/tests/concurrency_helpers.py:1`。

| 删除文件（基线位置） | 删除依据/保留处理 |
| --- | --- |
| `backend/tests/intervention_helpers.py:4` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_archives.py:6` | 国内旧成品库归档、并发或布局专属；海外独立archives与测试保留。 |
| `backend/tests/test_archives_concurrency.py:7` | 国内旧成品库归档、并发或布局专属；海外独立archives与测试保留。 |
| `backend/tests/test_builtin_text_tasks.py:8` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_cleanup.py:8` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_cli_intervention.py:7` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_cli_intervention_recovery.py:6` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_codex_runner.py:16` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_delivery_acceptance_flow.py:8` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_delivery_recovery_flow.py:7` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_delivery_snapshot.py:9` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_delivery_storage.py:8` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_execution_provenance.py:1` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_execution_reconcile.py:10` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_execution_records.py:11` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_final_delivery_roundtrip.py:7` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_legacy_retention.py:9` | 仅legacy_cli任务保留清理；API retention并发与迁移套件保留。 |
| `backend/tests/test_local_skill_execution.py:9` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `backend/tests/test_local_skill_tree.py:6` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `backend/tests/test_local_skills.py:11` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `backend/tests/test_local_skills_concurrency.py:11` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `backend/tests/test_local_skills_linux.py:45` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `backend/tests/test_management_usage.py:7` | 旧ExecutionAttempt/ExecutionUsage统计专属；现行API usage/CLI会话统计测试保留。 |
| `backend/tests/test_material_literals.py:4` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_observation.py:9` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_observed_runner.py:9` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_partial_results.py:8` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_repair_delivery.py:3` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_retention_migration_legacy_pg.py:16` | 仅legacy清理并发/冻结用例退役；API 0024用例已原样移至 backend/tests/test_retention_migration_pg.py:15，AST完全一致。 |
| `backend/tests/test_revision_execution.py:7` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_revisions.py:7` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_revisions_concurrency.py:9` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_round_materials.py:8` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_single_revision_inputs.py:6` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_single_revision_materials.py:5` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_single_revision_prompt.py:5` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_skill_catalog.py:15` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `backend/tests/test_skill_catalog_database.py:16` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `backend/tests/test_skill_catalog_frozen.py:12` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `backend/tests/test_skill_catalog_linux.py:21` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `backend/tests/test_skill_catalog_template_concurrency.py:15` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `backend/tests/test_skills.py:13` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `backend/tests/test_skills_concurrency.py:12` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `backend/tests/test_skills_upload_retry.py:7` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `backend/tests/test_task_prompt.py:6` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_task_queries.py:3` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_task_scope.py:4` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_task_snapshots_results.py:6` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_tasks.py:7` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_tasks_concurrency.py:14` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `backend/tests/test_templates.py:6` | 国内模板 CRUD/版本/布局专属；API及海外文件能力不依赖该套件。 |
| `backend/tests/test_templates_concurrency.py:14` | 国内模板 CRUD/版本/布局专属；API及海外文件能力不依赖该套件。 |
| `backend/tests/test_templates_migration.py:9` | 国内模板 CRUD/版本/布局专属；API及海外文件能力不依赖该套件。 |
| `backend/tests/test_templates_skills.py:6` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `frontend/tests/archive-library-layout.browser.mjs:9` | 国内旧成品库归档、并发或布局专属；海外独立archives与测试保留。 |
| `frontend/tests/archive-requests.test.ts:3` | 国内旧成品库归档、并发或布局专属；海外独立archives与测试保留。 |
| `frontend/tests/catalog.test.ts:1` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `frontend/tests/compact-upload.browser.mjs:7` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `frontend/tests/core-task-interactions.browser.mjs:19` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `frontend/tests/core-template-revision.browser.mjs:11` | 国内模板 CRUD/版本/布局专属；API及海外文件能力不依赖该套件。 |
| `frontend/tests/create-first-screen.browser.mjs:8` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `frontend/tests/execution-presentation.test.ts:6` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `frontend/tests/execution-progress.test.ts:4` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `frontend/tests/framework-demo-faults.browser.mjs:15` | 旧任务/模板/成品库全流程demo；共享身份/demo状态/配置测试仍保留并更新。 |
| `frontend/tests/framework-demo.browser.mjs:36` | 旧任务/模板/成品库全流程demo；共享身份/demo状态/配置测试仍保留并更新。 |
| `frontend/tests/legacy-retention.browser.mjs:49` | 仅legacy_cli任务保留清理；API retention并发与迁移套件保留。 |
| `frontend/tests/list-location.test.ts:4` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `frontend/tests/local-skills.test.ts:1` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `frontend/tests/new-task-menu.browser.mjs:7` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `frontend/tests/revision-session.test.ts:4` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `frontend/tests/round-materials.browser.mjs:65` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `frontend/tests/round-materials.test.ts:1` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `frontend/tests/skill-catalog.test.ts:1` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `frontend/tests/skill-groups.test.ts:3` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `frontend/tests/skill-version.test.ts:1` | 国内Skill目录、注册/默认绑定、安装或旧模板绑定专属；海外包校验及权限套件保留。 |
| `frontend/tests/task-creation-session.test.ts:4` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `frontend/tests/task-density.browser.mjs:8` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `frontend/tests/task-outcome.test.ts:3` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `frontend/tests/task-scope.test.ts:1` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `frontend/tests/task-submission.test.ts:6` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `frontend/tests/tasks.test.ts:1` | 旧国内任务创建/执行/修改/收图/材料或该页面交互专属；源码引用已退役模型、服务或路由。 |
| `frontend/tests/template-layout.browser.mjs:10` | 国内模板 CRUD/版本/布局专属；API及海外文件能力不依赖该套件。 |
| `frontend/tests/template-library-layout.browser.mjs:8` | 国内模板 CRUD/版本/布局专属；API及海外文件能力不依赖该套件。 |
| `frontend/tests/template-versions.test.ts:1` | 国内模板 CRUD/版本/布局专属；API及海外文件能力不依赖该套件。 |

配套 `backend/tests/fixtures/cli_revision_briefs.json:1` 是旧CLI任务prompt夹具，随旧runner退役；共享 `unannotated_revision_briefs.json` 保留API条目。混合的身份、上传、下载、缩略图、生命周期、设置、容量、提示词及并发清理测试并未整删，改以现行API数据验证。
