# 管理中心 API 统计整改：R2 独立审查

- candidateId：`fe0aed04b4e36e3284a4a61441657a8f03dde11ab85305cdff99b17087ba792b`
- Stage 1：**PASS**。Stage 2：**PASS**。本轮未发现 HIGH / MEDIUM 阻断项。
- 范围：`docs/MANAGEMENT-API-IMPLEMENTATION-20261010.md` 全部统一实施口径、交付顺序与本地验收要求；对应当前 Git diff 和未跟踪业务代码、测试、迁移、真实管理页面及显式模拟预览。Product-Spec.md:933 将该合同列为本次正式整改依据。
- 排除：预存 `.agents/skills/dev-builder/SKILL.md` 一行改动；既有自动清理本体，仅审查本次新增清理前事实保全。未重新验收全产品历史功能。
- 依据：code-review skill、docs/HARNESS-REVIEW.md、上述实施合同与 MANAGEMENT-API-VALIDATION-20261010.md。审查仅执行隔离本地测试、读取代码及已有实际浏览器截图；未修改业务代码、commit、部署或执行生产写入。

## Stage 1：逐条核查

以下代码路径均以 `hengxin-smart-image/` 为前缀。完整实现表示与本轮合同匹配。

| 合同条目 | 结论与证据 |
| --- | --- |
| 仅 API 业务统计；兼容旧接口 | 完整实现。`backend/app/main.py:50` 并存注册；`backend/app/modules/management/api_usage.py:68` 使用 API 事实，`:39` 库存只查 ApiTask/ApiItem；`frontend/src/api/api-management-usage.ts:9` 使用新接口。 |
| 各事件按各自发生时间、北京时间归日 | 完整实现。`backend/app/modules/management/api_stats/facts.py:45` 创建、`:50` 尝试、`:67` 发布、`:73` 启动/候选、`:92` 操作分别记录；`backend/app/modules/management/api_usage.py:90` 转上海自然日。`backend/tests/test_management_api_usage.py:45` 验证 UTC 15:59/16:00 跨日及分页不改变全量汇总。 |
| 库存只按创建人过滤，独立于历史日期/类型 | 完整实现。`backend/app/modules/management/api_usage.py:39`、`:108` 独立计算；`frontend/src/views/hengxin/admin/ApiUsage.vue:19` 显著说明；上述测试断言未来日期/restore 筛选仍保持库存。 |
| API 真实尝试含重试，CLI 提交与真实启动分开 | 完整实现。`backend/app/modules/api_image_edits/claims.py:110` 记录尝试；`conversation.py:139` 记录提交；`conversation_runner.py:145` 由进程 started 回调记录启动；`management/api_stats/projection.py:32` 证据不足 quantity=0。`backend/tests/test_api_usage_facts.py:123` 覆盖启动失败、`:136` 覆盖回填后真实启动升级。 |
| CLI 澄清不算失败；候选不等于采用 | 完整实现。`backend/app/modules/management/api_usage_summary.py:5` waiting_user 为成功；`api_stats/facts.py:86` 独立候选，`api_image_edits/conversation.py:195` 用户采用独立事件；`backend/tests/test_management_api_usage.py:29` 与 `test_api_usage_facts.py:86` 断言。 |
| 请求成功率与当前图片交付分开；未知/在途不入分母；旧结果单列 | 完整实现。`backend/app/modules/management/api_usage_summary.py:28` 分状态、`:53` 已知结果分母；`api_usage.py:45` 最新图片状态，`:51` 旧结果数；`frontend/src/views/hengxin/admin/ApiUsage.vue:19`、`:20` 独立说明。真实测试断言成功/失败/未知各一次得到 50%，失败图片仍有旧结果。 |
| 正式生成、候选、采用、恢复独立；无可靠 Token/费用不估算 | 完整实现。`backend/app/modules/management/api_usage_summary.py:11` 分计数；`api_image_edits/versions.py:185` 恢复独立操作，不新写生成；`backend/app/contracts/api_usage.py:42` Token/费用为 None；`frontend/src/views/hengxin/admin/ApiUsage.vue:21`、`:22` 明示。 |
| 未知来源版本单列，不冒充生成/采用 | 完整实现，关闭上轮 HIGH。`backend/app/modules/management/api_stats/projection.py:54` 未知来源标 unknown/legacy_unknown；`api_usage_summary.py:24` 单列 unverifiedVersions；`frontend/src/api/api-management-usage-validate.ts:9` 事件改称“正式版本发布记录”；`ApiUsage.vue:21` 明示“不计生成或采用”。`backend/tests/test_management_api_usage.py:110` 从真实 ApiVersion 投影，空 kind/image_edit/generation 得到未知 2、生成 1、采用 0，回填前后一致。 |
| 提交固定“已提交”；轮次终态/采用实时更新 | 完整实现，关闭上轮 MEDIUM。`backend/app/modules/management/api_stats/facts.py:10` 读取旧持久提交规范化，`:95` 新提交固定 submitted；`projection.py:31` 历史投影同口径；`api_image_edits/conversation.py:202` 采用刷新轮次；`conversation_runtime.py:43` 终态刷新。`backend/tests/test_api_usage_facts.py:86` 断言 candidate→adopted，`:158` 模拟旧持久 running 提交仍显示 submitted。 |
| 冻结发起者，历史归属/重试/类型不猜 | 完整实现。`backend/app/modules/api_image_edits/service.py:76`、`versions.py:158` 冻结重试人；`claims.py:111` 使用冻结值；`management/api_stats/facts.py:53` 既有事实仅更新结果；`projection.py:17` 历史保持未核实。`backend/tests/test_api_usage_facts.py:30` 实际跨人重试及幂等请求验证旧事实不变。 |
| 事实同事务、源键幂等、无过程 FK/正文、GET 不写、清理前保全 | 完整实现。`backend/app/modules/management/api_stats/models.py:10` 无 FK/正文；`facts.py:27` conflict 处理；`projection.py:61` no_autoflush 合并去重；`backfill.py:8` 显式回填；`backend/app/retention/api.py:55` 删除过程数据前保全。`backend/tests/test_api_usage_facts.py:54` 捕获只读 SQL、重复回填零新增、软删保留；`:86` 真实七天清理后事实完全相等；`test_api_usage_facts_pg.py:18` 四线程幂等覆盖。 |
| API/CLI 独立心跳；过期未知；队列失败不填 0；阶段/容量不混 | 完整实现。`backend/app/modules/api_image_edits/worker_health.py:25` 限 API app；`management/api_monitor.py:26` 独立心跳模型、`:89` 独立健康/队列、`:127` 采集失败 None；`frontend/src/views/hengxin/admin/monitor.vue:8`、`:19`、`:20` 明示心跳、容量及跨阶段不可相加。`backend/tests/test_management_api_monitor_settings.py:43`、`:55`、`:91`、`:128` 验证缺失/过期/未来、渠道独立、队列故障和真实 pulse。 |
| 配置来自实际常量/配置；API 只读、CLI 可保存；保留 Skill/钉钉/审计 | 完整实现。`backend/app/modules/management/execution_settings.py:17` 读取实际配置，`api_image_edits/execution_policy.py:2` 执行与显示共享常量；`management/settings_router.py:12`、`:22` 保留权限；`frontend/src/views/hengxin/admin/settings.vue:12`、`:14`、`:17`、`:19` 保留表单与审计、`:40` 保存后刷新实际卡片。独立复跑既有 settings 测试；实际浏览器脚本保存 5→4→5 并显示审计。 |
| 清理开关和 1/7 天只读展示，不冒充服务在线 | 完整实现。`backend/app/modules/management/execution_settings.py:10`、`:27` 读取真实常量及开关；`frontend/src/views/hengxin/admin/ExecutionSettingsCards.vue:14` 清理卡片无操作，显式“不代表清理服务已在线”；配置测试断言 false/1/7。 |
| 管理入口角色限制、后端个人范围、API 详情跳转、删除禁跳 | 完整实现。`frontend/src/router/modules/index.ts:32` 父路由角色；`backend/app/modules/management/api_usage.py:75`、`:82` 限定全员/个人/未知人员；`frontend/src/views/hengxin/admin/ApiUsageDetail.vue:8` 删除禁跳、`:38` 跳 API 记录；`backend/tests/test_management_api_usage.py:88` 和真实 Vue 交互测试验证。 |
| 正式接口无模拟回退；加载/空态/失败/分页 | 完整实现。`frontend/src/router/management-preview.ts:6` 显式 mock 条件；`admin/usage.vue:5` 非模拟读取真实 ApiUsage；`ApiUsage.vue:14` 加载、`:15` 错误、`:24` 空表、`:30` 分页；`frontend/tests/api-management-usage-ui.test.ts:57` 等实际编译组件并触发交互；check-usage.js 注入 503 后隐藏旧汇总并恢复。 |

部分实现、未实现：本轮范围内未发现。Spec 漂移：新增事实表、独立心跳表、接口、只读配置卡片均有合同依据；预览仅显式模拟模式可达，没有发现生产清理开关写入或额外收费调用。

## Stage 2：质量、安全、真实测试与视觉

- 代码结构通过：新增事实写入/历史投影/回填/聚合/监控/配置职责分离（`backend/app/modules/management/api_stats/facts.py:27`、`projection.py:9`、`api_usage.py:68`）；本轮受审代码逐文件计数，无超过 300 行文件。新前端边界先以 unknown 检查契约（`frontend/src/api/api-management-usage-validate.ts:2`、`execution-management.ts:3`），没有新增显式 any 类型。
- 安全扫描通过：核查新接口权限、字段白名单和 ORM 查询；`backend/app/modules/management/execution_settings.py:18` 不返回 Key、Broker 或执行目录；`api_monitor.py:111` 暂停原因只返回已知安全文案。新增业务代码未发现 eval/innerHTML、硬编码密钥、字符串拼 SQL。`frontend/tests/api-management-usage-ui.test.ts:41` 的 new Function 仅编译本仓库 Vue 测试模块，不执行网络/用户输入，非产品执行入口。
- 测试真实性通过：`backend/tests/test_api_usage_facts.py:30` 走真实提交、重试和执行事务；`:86` 模型执行替身仍真实走 started→候选→采用→恢复→清理；`:158` 输入来自可达旧回填状态。`test_management_api_usage.py:110` 从真实源版本查询，无 mock 掩盖计数。日期/权限测试部分替换事实输入，范围明确，由真实投影及事务用例补足。前端单测组件替身不能证明 Element Plus 真实布局，已结合隔离浏览器脚本及截图核对。
- 实际视觉对照通过：打开 `output/playwright/management-real/usage-verified-unknown.png`、`monitor.png`、`settings.png`、`settings-mobile.png`，并打开既有 `output/release/frontend-cleanup-20260928-26e3616/production-settings.png` 对照实际渲染。保留同款侧栏/页签、蓝色眉题、浅底白卡、细边圆角、蓝色按钮和表单间距；480px 配置表为表内横向区域，主页面不溢出，表单单列。对应实现 `frontend/src/views/hengxin/admin/ApiUsage.vue:2`、`monitor.vue:2`、`settings.vue:2`、`ExecutionSettingsCards.vue:2`。本次没有重新访问路由，以免自动生成组件声明改变冻结快照。
- 安全问题：本轮未发现。质量阻断：未发现。

## 验证原始输出与边界

Reviewer 独立复跑（隔离本地 fixture）：

```text
.venv\Scripts\python.exe -m pytest -q tests/test_api_usage_facts.py tests/test_management_api_usage.py tests/test_management_api_monitor_settings.py tests/test_management_settings.py --disable-warnings -p no:cacheprovider
.........................................                                [100%]
41 passed, 2 warnings in 4.82s
```

读取主 Agent 保存的当前候选前端日志，非 reviewer 重跑全套：

```text
> vue-tsc --noEmit && vite build
✓ built in 34.40s
ℹ tests 236
ℹ suites 0
ℹ pass 236
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 5071.4338
```

证据路径：`output/playwright/management-real/build.log:4`、`:455` 和 `frontend-tests.log`。独立 typecheck.log 同样为 `vue-tsc --noEmit`，无类型错误；含 pnpm 配置字段迁移提示，不是编译失败。

读取本轮完整后端 Docker 回归日志 `output/playwright/management-real/backend-tests.log` 尾部原文：

```text
........................................................................ [ 99%]
....                                                                     [100%]
1643 passed, 17 skipped, 15 warnings in 274.41s (0:04:34)
```

PG 全链迁移/降级再升级及实际浏览器功能记录由主 Agent 执行，本 reviewer 读取验证文档、测试源和浏览器脚本/截图，没有将其称为自己亲测。17 skipped 不算已验证。隔离环境可验证业务契约，不能证明生产 Worker 已部署、收费模型可用或所有宿主专用测试通过。

## 快照交接

初始和报告完成后的 `review-status` currentId 均与候选一致，审查期间没有受控代码变化。两阶段结论仅覆盖此 candidateId；主 Agent 登记批准前再次检查相同快照。禁止用旧报告覆盖后续业务代码改动，报告不授权生产部署或自动提交，不向 `.needs-review` 写 clean。

