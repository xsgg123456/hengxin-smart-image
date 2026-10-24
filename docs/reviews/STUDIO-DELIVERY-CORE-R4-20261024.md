# 工作台可靠收图核心审查 R4 · 2026-10-24

- 最终 candidateId：`12a9780008a7c301e8fd684eebcc856bb34b85983a3aa01289c95a5a3bcb7f97`。
- 初始派发 candidateId：`ee44d8a1ac47e54e2f77fbbe2139894c7f3f6543e149a1be44419dfb3b711c47`。审查中主 Agent 因 release 测试删除无用 import 更新候选；本报告按最终候选重新核对范围文件。复现时海外后端、backend/tests、frontend/src、frontend/tests 共 1095 个文件的归一化摘要与最终候选全部一致，`changedFiles=[]`，见 `output/studio-delivery-reliability-20261024/reviewer-r4-snapshot.json`。
- 范围：本轮全部海外后端差异及新增 completion、delivery、native、恢复/repair 模块，相关 runner/reconcile 接线；前端保存状态 DTO、StudioTurns 及测试。合同 1–5 和原八图 repair 代码逐条检查。
- 排除：release 脚本由另一 reviewer 审查；实际生产安装、原八图生产写入、发布与 Git 操作；用户修改的 AGENTS.md。未修改产品代码、Skills、未启动模型、未 spawn 子 Agent。
- 依据：`Product-Spec.md:1336`、`DEV-PLAN.md:1558`、`docs/STUDIO-DELIVERY-RELIABILITY-20261024.md:5-24`；已读取前两份 FAIL 报告。按“正常 final 实际输出即收、同会话历史无旧轮成功/交付门槛、不扫临时目录”的当前合同审查。
- 规划：最终识别 → 私有保全/逐图补收 → 租约、取消删除及状态 → repair；Stage 1 通过后才进入 Stage 2。

## 结论

**Stage 1：FAIL，HIGH 1 项。Stage 2：未执行。不得登记两阶段 PASS。**

前两轮 HIGH 已复验修复：同会话历史图本轮原生重展不再要求本轮新生成；旧轮成功生成后整轮失败/中断也不再否决后轮正常交付。证据：`backend/app/overseas/studio/native_images.py:201-251`，`tests/test_studio_delivery_native_history.py:8,56`、`test_studio_delivery_native_presentations.py:126,174`，以及前两轮原始独立反例本轮均通过。

当前仍有一个额外门槛：当前轮早前一次 imagegen 工具失败，会否决之后成功生成并在正常结束 final 中展示的图片。

## HIGH-1：本轮 imagegen 失败后重试成功，正常 final 原生图仍被拒收

**需求原文**：合同 `docs/STUDIO-DELIVERY-RELIABILITY-20261024.md:7`：“正常结束时 Codex 最后回复实际输出的图片就是收图依据……原生附图均接收”；`:9`：“只保留真实文件、会话归属、可解码图片及已有资源上限等必要校验”；`:22` 限制的是 CLI 非零退出、取消或成功回执缺失。

**合法可达输入**：同一轮第一次 imagegen 返回失败，模型处理工具错误并再次生成；第二次生成 completed，存在同会话可解码 PNG，最终公开展示该 PNG；最后 AgentMessage(final_answer)、task_complete、CLI turn.completed 和 exit_code=0 全部正常。失败那次没有作为最终图片展示。

**实现差异**（代码路径均以 `hengxin-smart-image/` 为前缀）：

1. `backend/app/overseas/studio/native_images.py:72-75` 对当前轮任何 `image_gen.generation` 的非 completed 状态或 failure 字段直接抛错，尚未读到后面的成功生成和实际最终呈现。
2. 同文件 `:170-181` 虽识别 `failed_image`，但只有 `targets is not None` 的历史目标查询分支处理该值；当前最终呈现路径 `targets=None` 继续进入 `active.item(payload)`，触发上述异常。
3. `backend/app/overseas/studio/delivery_evidence.py:33-37` 将异常变为“交付记录不可读”；`delivery_job.py:133-135` 无法固定 selection；`runner.py:187-196` 保留 collecting。`delivery_recovery.py:63-69` 自动补收仍会解析同一失败事件，不能恢复。

**实际结果**：图片 0 张，`collecting` / `capturing`，`expected=null`、`saved=0`；重试收图后仍相同，执行次数和 CLI 调用次数均为 1。它没有错误地重新生图，但已正常输出的图片永远无法保存，当前会话保持占用。

**独立复现**：`output/studio-delivery-reliability-20261024/test_reviewer_r4_current_generation_retry.py:16`，走真实 Studio API、runner、数据库、快照/补收调用及下载接口；只替换 CLI 进程边界与外部对象存储。控制组与失败组只有“插入早前 imagegen failed 事件”这一区别（`:33-36`）。两组最后成功生成/原生展示/终态/退出码和 PNG 字节相同；`:60-70` 检查自动恢复和下载。不修改业务数据库制造成功状态，不调用模型。

命令（backend 工作目录）：

```text
.venv/Scripts/python.exe -m pytest ../../output/studio-delivery-reliability-20261024/test_reviewer_r4_current_generation_retry.py -q -s --junitxml=../../output/studio-delivery-reliability-20261024/reviewer-r4-current-retry.xml
```

原始关键输出：

```text
{"earlierFailure": false, "before": {"state": "complete", "expected": 1, "saved": 1}, "status": "succeeded", "deliveryStatus": {"state": "complete", "expected": 1, "saved": 1}, "pictureCount": 1, "executionCount": 1, "cliCalls": 1, "originalSha256": "440eff07bd2494e5d9cb8f843fbce5d9343094c4e56634e5199ae83d84a9e209"}
{"earlierFailure": true, "before": {"state": "capturing", "expected": null, "saved": 0}, "status": "collecting", "deliveryStatus": {"state": "capturing", "expected": null, "saved": 0}, "pictureCount": 0, "executionCount": 1, "cliCalls": 1, "originalSha256": "440eff07bd2494e5d9cb8f843fbce5d9343094c4e56634e5199ae83d84a9e209"}
E       AssertionError: Handled earlier tool failure vetoes valid final native image
E       assert 0 == 1
WARNING  app.overseas.studio.delivery_evidence:delivery_evidence.py:36 Studio native delivery evidence rejected
WARNING  app.overseas.studio.delivery_recovery:delivery_recovery.py:67 Studio delivery recovery pending job=0d8ba369-4419-4d9b-8b93-cc1c8bf02c07
1 failed, 1 passed, 2 warnings in 2.89s
```

**修复验收**：当前整轮仍必须正常退出、有有效终态和准确会话/轮次边界；最终选中的真实像素必须能解析到安全文件并校验。已被处理的非终态工具失败不能否决后续有效 final；失败工具没有展示的候选也不能混收。至少补测“当前轮先失败再成功最终原生展示”、原生历史图在当前过程工具失败后重新展示、最终成功图后有无关失败工具但整轮正常结束，以及真正 CLI/终态失败继续拒收。修复后重新固定快照，从 Stage 1 复核。

## Stage 1 逐条核对

“完整实现”只表示该行具体行为通过了本轮证据检查，整阶段仍因 HIGH-1 失败。以下代码和 tests 路径以 `hengxin-smart-image/` 为前缀。

| 合同条目 | 结果 | 当前代码和本轮验证证据 |
| --- | --- | --- |
| 1：正常退出、精确完成回执、中途确认不是最终消息 | 完整实现 | `backend/app/overseas/studio/completion.py:47-129`、`backend/app/overseas/execution/runner.py:138-156`；`tests/test_studio_completion.py:29,50,79,94,101,110,145` 通过。非零退出和成功回执缺失不因有文件而成功，`test_studio_delivery_fencing.py:136` 通过。 |
| 1：最终文字图片/下载链接，无标题、固定措辞或“预览”门槛 | 完整实现 | `backend/app/overseas/studio/delivery.py:22-43,79-100`；`tests/test_studio_delivery_bridge.py:51,57,80,177` 通过，覆盖最终 8 条 JPG 引用、17 个过程图不扩张最终集合。 |
| 1：显式最终链接不被无关原生解析故障阻断 | 完整实现 | `backend/app/overseas/studio/delivery_evidence.py:16-29`；`tests/test_studio_delivery_bridge.py:161,169` 通过。 |
| 1：当前正常 final 原生附图，无本轮必须新生成/旧轮已交付条件 | 部分实现，HIGH-1 | 历史定位改为 `native_images.py:201-251`，仅查询当前选中摘要；前两独立反例通过。当前轮早前失败工具仍会拒收后续成功 final，见 HIGH-1。 |
| 1：历史 work/native 文件可重新交付，已存图片本轮仍展示 | 完整实现（本行既有场景） | `delivery.py:109-121` 不传已交付禁用表；`native_images.py:201-251` 不检查旧轮结局；`tests/test_studio_delivery_recovery.py:170`、`test_studio_delivery_native_history.py:8,56`、`test_studio_delivery_native_presentations.py:126,174` 通过。 |
| 1：精确执行边界、补收不读后来轮次、最后批次按实际顺序 | 完整实现（本行既有场景） | `native_rollout.py:109-138`、`native_images.py:113-131,224-251`；`tests/test_studio_delivery_native_presentations.py:42,53,63,86,115,157` 通过，包含 end cursor、无 end 时截止本轮、历史最终批次不混入本轮过程生成。 |
| 2：私有最终回复、选择路径、逐图字节/摘要，原子提交与落盘 | 完整实现 | `delivery_context.py:21-44`、`delivery_job.py:124-164`、`delivery_snapshot.py:28-92`、`delivery_snapshot_fs.py:48-56,76-112,130-154`；`tests/test_studio_delivery_snapshot.py:36,77,84,108,123,148,227,242` 通过。Windows 不替代真实 Linux 目录 fsync 验证；Linux 证据由主 Agent 汇总。 |
| 2：保全未齐时原任务保持活动、禁止后轮覆盖；失败保留恢复依据 | 完整实现 | `runner.py:187-196`、`delivery_job.py:103-117`；`tests/test_studio_delivery_recovery.py:16,92,112,146` 通过，覆盖原文件覆盖、回执复制、退出状态/正文持久化失败、捕获前/中断以及后轮阻塞。 |
| 3：复用原 Job/Turn，确定性身份、对象台账、逐图事务 | 完整实现 | `delivery_snapshot_fs.py:48-50`、`delivery_job.py:60-100`；`tests/test_studio_delivery_recovery.py:16,53,70` 通过，含单图上传失败、上传结果不明、上传成功而 DB 提交失败。 |
| 3：只补缺失项，已上传对象校验后复用，图片关联与记录原子提交 | 完整实现 | `delivery_job.py:70-100`、`files.py:54-69`；`test_studio_delivery_recovery.py:53,70` 验证重试没有第二次 put，结果图片和对象一致。 |
| 3：失效租约、迟到上传、取消及任务/会话删除不可发布结果 | 完整实现（本地故障场景） | `delivery_job.py:22-35,88-100`、`delivery_recovery.py:45-57`、`backend/app/overseas/execution/reconcile.py:28-40`；`tests/test_studio_delivery_fencing.py:39,63,80,100` 通过。真实 PostgreSQL 多 worker 争抢由另组执行，本报告不将 SQLite 测试等同 PG 验证。 |
| 4：实际保存数量、已存图立即可见、全部保存才交付完成 | 部分实现，HIGH-1 | 正常保存故障链有 `delivery_job.py:38-57,163-179`、`queries.py:103-115`；前端 `src/views/overseas/studio/StudioTurns.vue:11-15,31-36` 和 `src/api/overseas/studio.ts:19-23,47`，专项 3/3 通过。HIGH-1 未枚举已展示图片，永久停在 capturing。 |
| 4：自动补收退避、无新模型调用、同轮不重复，跨轮独立对象 | 完整实现 | `delivery_job.py:103-117`、`delivery_recovery.py:19-72`、`delivery_snapshot_fs.py:48-50`；`tests/test_studio_delivery_recovery.py:53,70,170`、`test_studio_delivery_repair.py:94` 通过。新 HIGH 的补收也没有增加模型调用，但不能成功。 |
| 5：真实文件、可解码、归属/受保护输入/逃逸/链接及资源上限 | 完整实现（可执行用例） | `delivery.py:46-62,109-121`、`delivery_snapshot_fs.py:76-112`、既有 `backend/app/execution/final_delivery.py:48-81`；`tests/test_studio_delivery_snapshot.py:184,191,217` 与 native 校验用例通过；4 个符号链接用例因 Windows 权限 skip，未计作验证通过。 |
| 5：缺文件、存储/DB/崩溃恢复、当前/历史原生、取消删除与哈希测试 | 部分实现 | 核心 180 passed、4 skipped，前两原始反例通过；新增“当前工具失败后正常 final”反例 1 failed。既有通过数量不能覆盖该核心缺口。 |
| repair：维护权限、暂停/排空、原成功退出、事件/逐图 hash、审计和幂等 | 完整实现（代码范围） | `image_recovery.py:30-56`、`delivery_repair.py:23-44,48-87`；`tests/test_studio_delivery_repair.py:58,82,94` 通过。恢复用例将执行器设为失败仍能经 regular reconcile 完成，未重新生图。 |
| 6：指定原八图真实生产补回及发布/浏览器/下载哈希/提交推送 | 本子范围不验收 | `output/studio-delivery-reliability-20261024/original-eight.json:1` 记录指定任务/轮次的 8 张 1600×1600 原 JPG hash；`native-original-replay.json:1` 记录生产旧原生单图回放 1 图、SHA256 `12df42e3…`。这是主 Agent 保存的只读证据，未宣称本 reviewer 独立完成生产补回/预览/下载。发布另组审查且仍需等待核心通过。 |
| 不修改 Skills、保留国内业务、多会话 | 范围符合，整体回归待汇总 | `git diff --name-only -- .agents hengxin-smart-image/backend/app/execution` 无输出；本轮改动在 overseas，runner 新路径由 `job.kind == 'studio'` 和 handler collect 选择，`runner.py:138-169`。没有新增页面/API/表；保存状态在既有消息组件内实现，未发现合同外功能。完整安全/视觉质量审查不在本轮已执行阶段。 |

## 独立测试与编译证据

核心命令（backend 工作目录），包含前两原始反例，而非仅看新回归的断言：

```text
.venv/Scripts/python.exe -m pytest tests/test_studio_completion.py tests/test_studio_delivery_bridge.py tests/test_studio_delivery_recovery.py tests/test_studio_delivery_fencing.py tests/test_studio_delivery_repair.py tests/test_studio_delivery_snapshot.py tests/test_studio_native_images.py tests/test_studio_delivery_native_presentations.py tests/test_studio_delivery_native_history.py ../../output/studio-delivery-reliability-20261024/test_reviewer_native_history_e2e.py ../../output/studio-delivery-reliability-20261024/test_reviewer_r3_historical_failed_turn.py -q --junitxml=../../output/studio-delivery-reliability-20261024/reviewer-r4-core-tests.xml
180 passed, 4 skipped, 2 warnings in 29.85s
```

4 项跳过均为 Windows 符号链接权限；2 个警告是 Starlette 的 httpx/anyio 接口弃用。新增独立失败用例输出见 HIGH-1，其失败不被上述统计抵消。

其余本轮变更涉及的既有执行、文本流、最终收图、旧恢复及 work baseline 用例独立回归：

```text
.venv/Scripts/python.exe -m pytest tests/test_overseas_studio_execution.py tests/test_overseas_studio_transcript.py tests/test_studio_formal_delivery.py tests/test_studio_image_recovery.py tests/test_studio_native_recovery.py tests/test_studio_work_baseline.py -q --junitxml=../../output/studio-delivery-reliability-20261024/reviewer-r4-existing-tests.xml
362 passed, 4 skipped, 2 warnings in 39.05s
```

报告结束前再次将范围文件与复现时保存的候选摘要比较：`changedSinceReproduction=[]`。

前端状态验证（frontend 工作目录）：

```text
node node_modules/tsx/dist/cli.mjs --test tests/studio-delivery-status.test.ts
✔ 保存进度DTO兼容旧响应并接收真实数量，拒绝未知状态和非法数字 (1.0243ms)
✔ 真实消息组件收图期间立即展示已存图片并更新进度，完成后移除提示 (12.7426ms)
✔ 旧轮次没有收图状态时不增加提示或额外操作 (1.2821ms)
ℹ tests 3
ℹ suites 0
ℹ pass 3
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 932.7755
```

**编译未执行**：Stage 1 已有 HIGH，不以主 Agent 提供的构建通过结果替代本 reviewer 的独立编译证据。

## Stage 2

**未执行。** 按 code-review skill，Stage 1 有 HIGH 时停止，未给出代码质量、安全扫描或邻居页面实时视觉比较 PASS。该报告不生成审查批准凭据，不写 clean；后续修复必须固定新快照并从 Stage 1 重审。
