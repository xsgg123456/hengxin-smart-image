# 国内 API 提示简化与取消人工核实：独立审查

- 日期：2026-10-20；审查角色：code-reviewer；按 `code-review` skill 执行。
- 最终 candidateId：`19ff4eb28e6ef86981da5efa160f313380f4dcd1f20897d39c6998441d8d7eca`。
- 结论：**Stage 1 PASS；Stage 2 PASS；开放 HIGH 0、MEDIUM 0。**
- 限定范围：本轮国内 API 代码与隔离验证；不构成生产部署验收或真实上游执行/计费保证。
- 源文档：`docs/API-RETRY-SIMPLIFICATION-20261020.md:1`、`Product-Spec.md:1`、`DEV-PLAN.md:1`；旧 `docs/API-RETRY-PLAN-20261020.md:9` 的未覆盖约束继续有效。视觉依据既有真实页面、Design-Brief 及已认可预览。

## 快照与审查范围

初始送审候选为 `4d025fb87c0f1f3925d4a36d239c8deb80b0252df61a104c0528721a392a8b1b`。审查期间发生修改，未将初始结论直接批准到新版本：

1. 审查发现状态筛选两个“处理中”、处理中统计漏计 uncertain；修复涉及 `frontend/src/types/api-image-edits.ts`、`frontend/src/views/hengxin/api-image-edits/RealRecords.vue`、`frontend/tests/api-image-activity.test.ts`。
2. 全量发现容量测试仍要求旧 uncertain 永久占有 token；仅修订 `backend/tests/test_capacity_admission.py` 的过期恢复预期并增强容量/删除保护断言，后端产品源码未变。
3. 中间快照 `009ba61bb9f4fa6d1c49a98114eff51e17b68408cc218719785f4f8127eeacd0` 后，仅 `scripts/api-retry/browser.mjs` 增加真实筛选、统计与选择动作回归；最终重新 prepare 为上述 `19ff4e…`。

以上差异均已重新阅读、复核对应测试及构建；报告落盘前 `review-status` 返回 currentId 与最终候选一致。主 Agent 应据此运行 `review-approve`，本审查未写 `.needs-review`、未登记批准、未改产品代码、未提交。

以下简写均相对 `hengxin-smart-image/`：`B` = `backend/app/modules/api_image_edits/`；`BT` = `backend/tests/`；`F` = `frontend/src/views/hengxin/api-image-edits/`；`FT` = `frontend/tests/`。

已查全部工作区 diff 及本轮未跟踪源码：

- 后端：`B/{claims,control,deletion_state,execution,outcomes,relay,retry_policy,router,schemas,state}.py`，并沿调用关系检查 limiter、service、versions、heartbeat、retry_stop、scheduling、config。
- 后端测试：本轮修改的 execution、execution_pg、parallel、relay、collection_block、retry_gate_pg、retry_policy、task_deletion_recovery、capacity_admission 及新增 `BT/test_api_retry_recovery.py`。
- 前端：API client、类型、RealCreate、RealRecords、RealTaskDetail、ApiResultPicture、ChannelNotice、ItemRetryStatus、item-command、retry-status、use-channel、use-records、删除 use-retry-clock；共享 GenerationPlaceholder 的可选 simple 属性；相关 activity、retry、retry-component、pagination、polling 测试。
- 验收工具：`scripts/api-retry/{browser.mjs,simple-live-app.py,simple-live-browser.mjs}`。
- 文档/框架：源合同、Spec、计划、变更记录、旧合同覆盖说明、两份上一轮预览报告；`.agents/skills/dev-builder/SKILL.md:52` 的真实页面同视口复用规则符合本轮交付，未扩大产品范围。

## Stage 1：Spec Compliance — PASS

### 本轮合同逐项检查

|合同条目|结论及证据|
|---|---|
|范围 1：简短总进度、每图状态、失败重试、保留成功|完整实现。`F/retry-status.ts:12` 统一生成总进度；`F/RealTaskDetail.vue:14` 单处呈现、`:21` 每图标签、`:31` 失败单张入口；`:64` 保留已有 result。`FT/api-image-retry-component.test.ts:79` 验证混合状态只存在一个失败单图重试，成功 fileId 保留。|
|范围 2：取消管理员核实，限定本地结束或租约失效，保护执行权|完整实现。`B/outcomes.py:27` 将本地结束 uncertain 作为原重试门禁的 retryable 结果，但 attempt 审计仍记 uncertain；`B/claims.py:73` 仅恢复无有效租约的 running/uncertain。`B/state.py:16` 通道行锁，`B/claims.py:31` 撤销旧 token，`:113` 验证所有权；`:129` 禁止过期执行者取得新发送许可。`BT/test_api_retry_recovery.py:60` 验证有效租约即使停止/超期仍受保护；`BT/test_api_image_execution_pg.py:84` 验证回执先到与恢复先到两个顺序，`:109` 验证并发恢复只抽样一次。|
|范围 2：页面及接口不再要求人工核实|完整实现。`B/router.py:121` 保留配置恢复端点，旧 resolve 路由及 ResolveTask schema、control.resolve 已删除；前端 API client 的 resolve 方法和 `F/RealRecords.vue` 对应入口已删除。`BT/test_api_image_execution.py:128` 验证旧端点 404、普通用户直接重试；`scripts/api-retry/simple-live-browser.mjs:38` 检查 OpenAPI 无 resolve。配置问题的管理员 resume 仍保留，符合指定边界。|
|范围 3：已有 URL/bytes 只收图，历史终态审计不重做|完整实现。`B/claims.py:24`、`:32` 结果优先进入 collecting；`B/execution.py:153` 跳过生成；`B/service.py:82`、`B/versions.py:76` 手动重试有回执时不开生图新轮。`BT/test_api_retry_recovery.py:102` 覆盖 URL/bytes、停止、截止、暂停和耗尽；`:156` 验证终态旧 uncertain 审计和结果版本不变。|
|范围 4：保留预算、时间、门禁、输入、幂等、停止与错误分类|完整实现，逐条原合同检查见下一表。`B/claims.py:17` 不重设 cycle/deadline/容量/修改快照；`B/outcomes.py:43` 先检查耗尽原因。`BT/test_api_retry_recovery.py:31`、`:79`、`:176`、`:196` 覆盖原轮不清零、停止/期限/次数、预发送失败不回写历史 uncertain。|
|范围 5：混合仅失败单张，终态批量|完整实现。`B/service.py:77` 保留 failed/partial_failed 整套资格，`:80` 只选 failed；`B/versions.py:152` 单张仅要求该图 failed。`F/RealTaskDetail.vue:11` 批量等任务结束，`:95` 单张资格与原未决操作相容。`FT/api-image-retry-component.test.ts:109` 和真实 HTTP/PG 浏览器流程验证终态批量及 CLI 保护。|
|范围 6：海外及 CLI 机制不改|完整实现。本轮 diff 无海外/CLI 执行、取消、恢复文件变化；共享 `frontend/src/views/hengxin/components/GenerationPlaceholder.vue:11` 的 simple 为默认不启用的可选属性，只有 API 图片组件使用。`frontend/src/types/api-image-edits.ts:35` 保留独立 CLI/deletion 活动态，`FT/api-image-activity.test.ts:10` 验证 CLI 不混入 API 统计。|
|范围 7：新合同只覆盖人工核实与提示，不重做原发布|完整实现。Spec/计划顶部及旧合同覆盖说明对应本次代码 diff；未新增迁移、发布配置或生产执行入口。|
|页面 1：总进度一句话，全失败不说部分完成，繁忙/不可用短句|完整实现。`F/retry-status.ts:12` 至 `:29`；`FT/api-image-retry.test.ts:27` 对全失败、混合、成功、保存、停止逐项断言；`:44` 检查繁忙和不可用。|
|页面 2：七类短状态、单张/批量入口、未决提交复用原键|完整实现。`frontend/src/types/api-image-edits.ts:33`、`F/retry-status.ts:8`；`F/item-command.ts:13` 复用 pending 的 command/key，`:36` 刷新恢复；`F/use-records.ts:10` 持久保存批量 key。`FT/api-image-retry.test.ts:57` 验证停止未知后刷新同键；组件测试 `:92` 验证单图同键；`FT/records-polling.test.ts:96` 验证批量同键。|
|页面 3：移除技术叠加/人工核实，保留停止及真实操作|完整实现。`F/ItemRetryStatus.vue:3` 仅保留简短停止按钮；`F/RealCreate.vue:19` 采用简短说明；`F/RealTaskDetail.vue:36` 保留输入区域，删除面向用户的原始事件/错误堆叠。`scripts/api-retry/browser.mjs:69` 实际断言禁词不出现；`:86` 检验防双击和刷新恢复。|
|页面 4：刷新/下载/提交失败不误导，内部错误不外露|完整实现。`F/use-records.ts:42`、`:51` 保留上次数据并区分加载与刷新；`:115` 批量短错误；`F/RealTaskDetail.vue:113`、`:126` 下载错误不改图片状态；`F/item-command.ts:24` 单张/停止不显示原响应。`FT/records-pagination.test.ts:54`、`FT/records-polling.test.ts:65`、`FT/api-image-retry-component.test.ts:123` 验证故障路径。|
|页面 5：各状态及桌面/390px 可操作|完整实现，证据分层：`FT/api-image-retry.test.ts:27` 覆盖正常、等待、重试、保存、部分/全失败、混合、停止、完成、原未知状态；`:44` 覆盖繁忙/不可用；组件及轮询测试覆盖三类失败；正式 dist 浏览器 8 组检查和真实 HTTP/PG 3 组流程通过。`scripts/api-retry/browser.mjs:54`、`scripts/api-retry/simple-live-browser.mjs:60` 逐按钮滚动检查可见边界，非仅检查页面横向溢出。|
|实施 1：先同步源文档及计划|完整实现。`Product-Spec.md:1`、`DEV-PLAN.md:1` 与本轮合同一致；历史内容明确为原实现，覆盖范围清楚。|
|实施 2：后端仅改恢复及关联接口|完整实现。后端 diff 限于恢复、终结、删除旧 resolve、对应安全提示；未改变重试参数/调度算法/生产 schema。证据见 `B/claims.py:17`、`B/outcomes.py:27` 及原合同表。|
|实施 3：前端真实状态/真实组件，无演示模块|完整实现。`F/RealRecords.vue:19` 接真实详情，`F/RealTaskDetail.vue:103` 调真实 API；mock 与 FakeClient 只存在 tests/scripts。正式前端未引入 preview、演示场景切换或假成功定时器。|
|实施 4：回归、类型、构建、隔离并发/浏览器、独立审查|完整实现。原始结果与首轮失败修复记录见下；跳过项明确保留，不计作通过。未触发收费上游或生产部署。|

### 原合同保留项逐条检查

|旧合同条目|结论及证据|
|---|---|
|1：每新轮20次、手动新轮、同图互斥和幂等|匹配。`B/retry_policy.py:33`、`B/versions.py:152`、`B/service.py:31`；`BT/test_api_retry_policy.py:24` 验证20/21和手动新轮；`F/RealTaskDetail.vue:95` 防并行未决重试。旧“未知永久不重开”仅在新合同规定的本地结束/过期恢复条件被覆盖。|
|2：equal jitter、持久抽样、Retry-After 下限|匹配。`B/retry_policy.py:72`；`B/outcomes.py:36` 使用数据库时间换算 HTTP date；`B/claims.py:39` 恢复只写一次 nextAttemptAt。`BT/test_api_retry_policy.py:128`、`:144`、`:176` 与并发恢复用例验证。|
|3：首次许可起45分钟、发送前计数、收图不计生成|匹配。`B/retry_policy.py:81`、`B/claims.py:126`、`B/execution.py:172`；`BT/test_api_retry_policy.py:55`、`:161`、`:191` 验证截止、准备后许可及已发结果继续收集。|
|4：300秒请求、60秒下载、600秒租约、停止不丢回执|匹配。`B/config.py:20` 至 `:25` 未改；`B/heartbeat.py:11` 心跳验证所有权/期限；`B/retry_stop.py:12` 不撤销真实在途/回执；`BT/test_api_retry_policy.py:76`、`BT/test_api_retry_gate_pg.py:161` 覆盖停止与最终发送竞争。|
|5：全局5秒发送、10在途、跨进程统一门禁|匹配。`B/limiter.py:17`、`:38` 与 `B/state.py:16`；`BT/test_api_retry_gate_pg.py:64`、`:83` 使用多进程/真实 PG 验证。只释放本地结束或被锁内恢复的未知执行，历史审计不占活跃在途。|
|6：5次临时失败冷却、单探测、代次和慢恢复、收图豁免|匹配。`B/limiter.py:46`、`:62` 未改；`B/outcomes.py:42` 将已结束 unknown 送入原门禁；`BT/test_api_retry_gate_pg.py:109` 验证单探测、迟到成功不能清新冷却、逐步扩容；`:217` 验证超长 Retry-After 不能被管理员 resume 绕过。|
|7：保留不可重试分类和请求证据、不得泄露原响应|匹配。`B/relay.py:158` 保留 HTTP/channel/permanent 分流，only uncertain 的处理由新合同覆盖；`B/outcomes.py:33` 仅存适配器 code；`BT/test_api_image_relay.py:53`、`:66` 与前端 secret 响应故障测试验证。|
|8：等待让出任务名额、5任务/每任务10、批次和冻结输入|匹配。`B/scheduling.py:5`、`:9` 未改；`B/execution.py:33`、`B/versions.py:28` 使用原冻结快照；`BT/test_api_image_parallel.py:14` 与 `BT/test_api_retry_recovery.py:31` 验证。|
|9：持久轮次/共享时钟、历史终态不重开、旧轮不清零|匹配。`B/retry_policy.py:26`、`:40`、`B/claims.py:65` 只选择活跃图片；`BT/test_api_retry_recovery.py:120` 保留 legacy-v1 的4次预算，`:156` 保护历史终态审计。|
|10：真实停止与合法手动排队，不绕过认证暂停|匹配。技术计数/倒计时展示被新合同明确替代；`F/use-channel.ts:9` 只因配置/加载失败阻止新操作，临时冷却可排队；后端仍经 `B/limiter.py:17`。`scripts/api-retry/browser.mjs:104` 验证冷却时重试与停止失败恢复。|
|历史尝试兼容及接口合同|匹配。`B/limiter.py:10` 不数全表历史 uncertain；`B/retry_policy.py:90` 保留兼容 retry 对象；原 stop 端点与 channel 可选状态未删除；`FT/api-image-retry.test.ts:14` 验证旧记录兼容和字段拒错。新合同删除 resolve，不涉及 CLI 的独立机制。|

部分实现：无。未实现：无。Spec 漂移：未发现超范围产品页面/API/表；新增脚本仅为隔离验收工具，`scripts/api-retry/simple-live-app.py:16` 限定本机 `_test` 数据库，`:109` 只绑定 loopback。原发布流程在本轮不执行。

### 已关闭问题

- **MEDIUM / Stage 1：筛选同名、统计漏计。** 初始 `frontend/src/types/api-image-edits.ts:32` 将 running/uncertain 都叫“处理中”，`F/RealRecords.vue:43` 又漏计 uncertain。审查者通过 18924 的真实 dist 下拉实际复现两个同名选项。修复后 `types/api-image-edits.ts:32` 为“处理中 / 等待结果”，`:34` 与 `F/RealRecords.vue:43` 统一活跃集合。`FT/api-image-activity.test.ts:10`、最终浏览器 `scripts/api-retry/browser.mjs:132` 检查唯一名称、统计1套及实际选中。审查者重新载入最终 dist 独立复验两个不同选项，问题关闭。
- **回归旧预期不匹配。** Linux 全量唯一失败原 `BT/test_capacity_admission.py:117` 断言过期仍 uncertain/token不变。新合同要求锁内恢复，修订后的 `:120` 检查 retry_wait/token撤销，同时新增容量 cycle、held/60MiB、attempt审计、删除409验证。完整容量模块 Linux 10/10 通过；不是删除断言或放宽容量保护，问题关闭。

## Stage 2：Code Quality — PASS

- **结构/类型：匹配。** 所有本轮修改及新增 `.py/.ts/.vue/.mjs` 均少于300行，最长 `BT/test_api_retry_gate_pg.py` 251行；前端无新增 TypeScript any。`B/claims.py:17` 集中处理恢复，`F/retry-status.ts:3` 集中短文案，`F/item-command.ts:9` 沿用单一命令状态机；错误后 busy 在 finally 复位，`F/use-records.ts:118` 与 `F/use-channel.ts:33` 解绑计时器/监听。
- **测试真实性：匹配。** `FT/api-image-retry-component.test.ts:42` 编译真实 SFC 后触发实际 handler，替换子组件仅用于轻量挂载，不把其结果当 CSS 证据。`BT/test_api_image_execution_pg.py:109` 是真实数据库锁竞争；`BT/test_api_retry_gate_pg.py:37` 使用独立进程发送门禁；`BT/test_api_retry_recovery.py:176` 特意区分发送前失败和已发送 unknown，防止旧审计被误改。浏览器夹具故障注入与真实 HTTP/PG 流程分别记录，未混为生产端到端验证。
- **安全扫描：未发现本轮新增安全问题。** 已搜索 eval、innerHTML、dangerouslySetInnerHTML、暴露 VITE 密钥、常见密钥前缀、绝对用户路径、any 和动态函数。产品代码无危险动态执行或新增凭据。`FT/api-image-retry-component.test.ts:47` 等 new Function 仅编译仓库内测试源码；`scripts/api-retry/simple-live-app.py:20` 的 key 为明确测试常量；`:42` 的 schema 由 UUID hex 生成，`:45`/`:116` 的 SQL 标识符不来自用户输入，测试库/loopback 限制在`:16`/`:17`。真实用户错误不渲染上游响应，证据见 Stage 1。
- **视觉复用：匹配。** 审查者实际打开 18924 正式构建记录页和成功详情，查看3/3、下载/版本/修改入口，未重放 seed。并打开 `output/api-retry-vue-preview-20261020/review-baseline.png`、`scenarios/partial.png`，对照正式 `output/api-retry-simple-20261020/live-mixed.png`、`live-completed.png`：1440px 同宽视口抽屉 x=400、宽1040，保留白底、蓝色按钮、卡片、共享素材和三列网格；`F/RealTaskDetail.vue:2`、`:133`、`:134`、`:136` 对应宽度、14px间距/内边距、180px图片区域。删繁复提示与预览栏，未另造界面。390px `live-narrow-stopped.png` 的单列/状态/单张重试完整可见，对应 `:146`、`:147` 断点。最终 `output/playwright/api-retry/waiting-result-filter.png` 目视确认“等待结果”筛选、行标签及处理中1套一致。

## 编译与验证原始输出

审查者独立执行类型检查和 Python 编译，退出码均0：

```text
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit
REVIEW_TYPECHECK_EXIT=0
python -m compileall -q hengxin-smart-image/backend/app/modules/api_image_edits hengxin-smart-image/backend/tests/test_api_retry_recovery.py scripts/api-retry/simple-live-app.py
REVIEW_COMPILEALL_EXIT=0
```

已直接读取主 Agent 的最终日志：

`output/api-retry-simple-20261020/frontend-tests-final.log`：

```text
ℹ tests 322
ℹ suites 0
ℹ pass 322
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 10032.5974
```

`output/api-retry-simple-20261020/frontend-build-final.log`：

```text
✓ built in 40.83s
```

`output/api-retry-simple-20261020/backend-full.log`（保留首次失败，不称此运行全绿）：

```text
FAILED tests/test_capacity_admission.py::test_delete_request_retains_capacity_until_actual_cleanup_and_expired_lease_never_releases
1 failed, 2201 passed, 25 skipped, 6 warnings in 410.22s (0:06:50)
```

产品后端源码未改，仅修正上述旧合同断言后，`output/api-retry-simple-20261020/capacity-final-linux.log`：

```text
10 passed, 2 warnings in 5.13s
```

该全量执行与完整失败模块复验共同覆盖本轮后端回归；没有伪造一次新的“全量0失败”运行。依赖仓库宿主环境的补充结果 `output/api-retry-simple-20261020/backend-repository.log`：

```text
96 passed, 12 skipped in 1.99s
```

最终正式 dist 浏览器：`output/api-retry-simple-20261020/browser-fixtures-final.log` 8组检查，`requests: 6`，`errors: []`；`output/playwright/api-retry/evidence.json` 显示响应丢失后的两次停止使用相同幂等键。真实 HTTP/PG：`output/api-retry-simple-20261020/browser-live.log` 3组流程，`errors: []`；`live-evidence.json` 保存最终任务、POST及原成功 fileId。入口/断言源码分别为 `scripts/api-retry/browser.mjs:64` 和 `scripts/api-retry/simple-live-browser.mjs:31`。

## 验证边界

- 后端全量的25项及仓库测试12项 skipped 仍是跳过，不记作通过；本轮没有真实收费生图、外部模型质量或生产部署验证。
- `simple-live-app.py:61` 覆盖身份依赖提供普通 operator，真实业务权限/路由/schema/PG仍执行；上游 FakeClient 和内存文件不证明真实身份提供方登录、MinIO或供应商端到端可用。
- 当前上游没有已验证的取消/查询/幂等能力。本次证明的是本地有效租约保护、恢复 token 隔离及回执只收图；不能证明超时后的远端计算已停止，也不能保证无远端重复计费。`B/execution.py:181`、`B/claims.py:17` 与本轮合同明确该边界。
- 批准仅对应最终 candidateId。后续受控源码变化须重新 prepare/复核，不能以本文覆盖新快照。
