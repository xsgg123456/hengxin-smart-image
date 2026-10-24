# 海外最终收图可靠性核心终审 · 2026-10-24

- candidateId：`3dd0d892a821a09dbefdb71663f6cfd8a060b3c0de72de27322742c1ee6ffe4d`。
- 本轮独立审查范围：本次海外后端 core 全部差异、completion/native/delivery 快照与补收模块、runner/reconcile/queries 接线，以及前端保存状态 DTO、`StudioTurns.vue`、相关测试。无产品代码修改、无 Skill 修改、无模型调用、无提交、无子 Agent。
- 需求依据：`Product-Spec.md:1336`、`DEV-PLAN.md:1558`、`docs/STUDIO-DELIVERY-RELIABILITY-20261024.md:5`；已逐份读取 CORE、CORE-R3、CORE-R4 失败报告及 RELEASE-R3 独立报告。
- 顺序：最终选择与终态 → 冻结字节与逐图补收 → 并发/取消/删除 → 状态与 repair → Stage 1 无 HIGH 后执行质量、安全、构建和真实组件视觉验证。
- 排除：用户修改的 `AGENTS.md`；生产安装、业务恢复写入、Git 操作。发布分区引用独立报告 `docs/reviews/STUDIO-DELIVERY-RELEASE-R3-20261024.md:3`，不伪称重新审过发布实现。

## 结论

**Stage 1：PASS（上述核心与前端代码范围）。Stage 2：PASS（上述核心与前端代码范围）。未发现剩余 HIGH 或 MEDIUM。**

前三轮 HIGH 原始反例已全部独立复跑通过，并有正式仓库回归用例。最终回复接收不再依赖本轮新生成、历史轮次成功/交付或早前工具全程无错；当前执行仍须正常结束并通过文件、归属、摘要和资源限制。

**这不是整个生产交付完成证明。** 审查期间生产条件改变：主 Agent 提供的当前只读证据 `output/studio-delivery-reliability-20261024/original-current.json:1` 显示指定任务 `f62752ac-d21b-4142-8ea1-379ae71353cc` 删除凭据为 `deleted`，原 workspace 与原图不存在。原先的 `original-eight.json` 是历史只读证据，不能当作现在仍可补收的证明。合同 6 的实际安装、恢复策略、浏览器预览/下载和推送仍须主 Agent 完成；不能运行旧八图请求，不能绕过删除保护或重新生图掩盖。后续发布适配若改代码，必须固定新 candidate 并复核变更，本报告不覆盖未来版本。

## 快照与前轮问题

`output/studio-delivery-reliability-20261024/reviewer-r5-snapshot.json:1` 保存 1564 个 backend、frontend/src、frontend/tests、release 范围文件的 candidate 摘要。使用与 harness 相同的 `review_files.digest`（仅有效 UTF-8 无 NUL 文本做 CRLF 归一）比对，`changedFiles=[]`。与 R4 已保存核心快照相比，仅以下 3 个文件不同：

1. `backend/app/overseas/studio/native_images.py`。
2. `backend/tests/test_studio_delivery_native_history.py`。
3. `backend/tests/test_studio_delivery_native_presentations.py`。

以下相对路径均以 `hengxin-smart-image/` 为前缀，除非以 `docs/`、`output/`、`scripts/` 开始。

| 前轮 HIGH | 本轮结果与证据 |
|---|---|
| 历史原生图本轮重展、无新 generation 被静默丢弃 | 修复。`backend/app/overseas/studio/native_images.py:232` 只选择当前完成呈现，再回查启动 cursor 以前的同会话位置；未知摘要显式失败，不报告 0/0。`backend/tests/test_studio_delivery_native_history.py:10` 与原始独立 `test_reviewer_native_history_e2e.py:15` 均通过。 |
| 历史 generation 完成后旧轮失败，本轮正常重展仍拒收 | 修复。`native_images.py:209` 的历史索引只查完成图片位置，不以旧轮结局为门禁；当前 `_turns` 仍拒绝失败/中断轮。正式回归 `test_studio_delivery_native_history.py:58`、纯解析边界 `test_studio_delivery_native_presentations.py:174`、R3 原始独立反例均通过。 |
| 当前 imagegen 先失败、重试成功，正常 final 被早前失败否决 | 修复。`native_images.py:72`、`:156`、`:179` 跳过失败工具及非终态诊断，保留当前失败终态拒收。`test_studio_delivery_native_history.py:117` 使用真实 runner/API/DB/下载链；`test_studio_delivery_native_presentations.py:193` 与 `:206` 区分恢复成功及没有完成回执。R4 原始控制组和失败组均通过。 |

## Stage 1：合同逐条对照

| 条款 | 结论 | 代码与验证证据 |
|---|---|---|
| 1：正常退出、精确完成回执、中途确认不冒充最终消息 | 完整实现 | `backend/app/overseas/studio/completion.py:49`、`:98`、`:132`；`backend/app/overseas/execution/runner.py:138` 要求 exit 0 和有效完成。`test_studio_completion.py:29`、`:79`、`:94`、`:101`、`:110`、`:145`；`test_studio_delivery_fencing.py:136` 独立通过。 |
| 1：最终文字图片、图片下载链接，无标题或“正式”措辞门槛 | 完整实现 | `delivery.py:22` 遍历实际 Markdown 图片/链接，`:79` 规范化去重；`test_studio_delivery_bridge.py:51`、`:65`、`:80` 通过，“预览”等文本不否决最终引用。 |
| 1：显式最终清单优先，17 个过程图只取最终 8 图；不扫工作目录 | 完整实现 | `delivery.py:92` 显式 links 分支优先；`:99` 才使用原生最终呈现。`test_studio_delivery_bridge.py:57`、`:177` 通过。收图目标来自最终引用或绑定的呈现记录，不枚举工作目录候选图。 |
| 1：文字引用不被无关原生解析失败阻断 | 完整实现 | `delivery_evidence.py:16` 的可选摘要查询失败仅记录日志，仍返回最终显式引用；`test_studio_delivery_bridge.py:161`、`:169` 通过。 |
| 1：同会话历史 work/native 可再次交付，已存图片本轮仍显示 | 完整实现 | `delivery.py:109` 不传历史已交付禁用集，`native_images.py:209`、`:232` 回查历史生成位置；`test_studio_delivery_recovery.py:170` 通过，第二轮图片 ID/对象 key 独立、下载字节相同、原工作文件 mtime 不变。原生无本轮 generation 与旧轮失败见前轮 HIGH 表。 |
| 1：执行边界、最终批次顺序、补收不读取后续轮 | 完整实现 | `native_rollout.py:109` 验证 cursor 身份/边界并截止本轮 `task_complete`；`native_images.py:113` 绑定最后完成文本，`:127` 按实际呈现顺序选图。`test_studio_delivery_native_presentations.py:42`、`:53`、`:63`、`:86`、`:115`、`:157` 通过。 |
| 2：后端私有最终回复、选择路径、逐图字节/摘要，原子提交和落盘 | 完整实现 | `delivery_context.py:21`、`:29`；`delivery_job.py:124` 先持久 selection 和 manifest；`delivery_snapshot.py:28`、`:59`、`delivery_snapshot_fs.py:130`、既有 `context_fs.py:120` 文件 fsync/rename/目录 fsync。`test_studio_delivery_snapshot.py:36`、`:77`、`:108`、`:123`、`:148`、`:227`、`:242` 通过。 |
| 2：捕获未齐不放行后轮，失败保留目录与恢复依据 | 完整实现 | `delivery_job.py:103` 保留 collecting 并退避；`runner.py:187` 正常完成后保存失败不结束成 failed；`delivery_recovery.py:19` 恢复原 invocation。`test_studio_delivery_recovery.py:92`、`:112`、`:146` 通过，包含复制退出回执/DB退出状态/正文持久化故障及捕获中断；下一轮 API 返回 409。 |
| 3：复用原 Job/Turn、确定性图片身份、逐图持久提交 | 完整实现 | `delivery_snapshot_fs.py:48` 身份绑定 job 与 canonical source；`delivery_job.py:60`、`:70` 对象台账先提交，随后逐张保存。`test_studio_delivery_recovery.py:16` 验证单图失败不丢其他图；`:53`、`:70` 验证上传结果不明和对象已存而 DB 提交失败。 |
| 3：只上传缺失项、Picture 与所属轮次关联原子提交 | 完整实现 | `delivery_job.py:88` 先读并校验稳定对象，缺失或损坏才 put，`:99` 再验租约并同事务提交 Picture；`test_studio_delivery_recovery.py:53`、`:70` 的恢复对象字节不变、put 次数仍为 1。 |
| 3：失效租约、迟到上传、取消及任务/会话删除不得发布 | 完整实现 | `delivery_job.py:22` 锁 task/job 校验 token、活跃租约、process_exited 和删除凭据；`:99` 上传后再次检查。`test_studio_delivery_fencing.py:39`、`:63`、`:80`、`:100` 通过，正式取消/删除 API 后旧 collector、reconcile、runner 均不能复活图片。 |
| 4：未齐显示保存中和实际数量、已存图立即可见、全齐才完成 | 完整实现 | `delivery_job.py:38` 从已提交 Picture 统计；`:163` 开始上传已捕获项，`:174` 必须 ready 且 saved==expected 才 succeeded；`queries.py:103` 输出有序图片及状态；前端 `src/api/overseas/studio.ts:19`、`:47` 验证 DTO，`StudioTurns.vue:11`、`:31` 展示进度。API 专项及浏览器 capturing→1/8→complete 实测通过。 |
| 4：自动补收退避，不重复对象、图片或模型执行 | 完整实现 | `delivery_job.py:103` 指数退避封顶 300 秒；`delivery_recovery.py:63` 只调用 deliver；`test_studio_delivery_recovery.py:16`、`:53`、`:70`、`test_studio_delivery_repair.py:94` 对 commands/execution_count、put 次数和对象数作断言，均通过。 |
| 4：跨轮同图独立版本，避免对象删除共享 | 完整实现 | `delivery_snapshot_fs.py:48` 的 UUID5 包含 jobId，`delivery_job.py:65` 对象 key 包含独立图片 ID；`test_studio_delivery_snapshot.py:94`、`test_studio_delivery_recovery.py:170` 验证不同轮图 ID/对象 key 均不同，原字节相同。 |
| 5：真实文件、解码、会话归属、受保护输入、路径逃逸和资源上限 | 完整实现（含平台补证） | `delivery.py:46`、`:109`，既有 `backend/app/execution/final_delivery.py:48`，`delivery_snapshot_fs.py:76`、`:147`；本轮各安全用例通过。Windows 的 8 个平台 skip 未计为通过，Linux 链接边界 10 PASS 的原始证据及范围见下文。 |
| 5：混合文本/图、历史图、失败工具、缺文件、存储/DB/崩溃恢复、迟到租约、取消删除、原图 hash | 完整实现测试覆盖 | 本轮 core 187 PASS、接线 362 PASS，前三轮独立对抗反例均包含在 core 命令；测试前提与正式 API 接线复核见 Stage 2。未将全量数量代替故障路径断言。 |
| 6：repair 权限、暂停/排空、原成功退出、事件和逐图 hash、审计及幂等 | 完整实现（代码） | `image_recovery.py:30`、`delivery_repair.py:23`、`:48`；`test_studio_delivery_repair.py:58`、`:82`、`:94` 通过。重复 repair 不改旧执行事实；收图故障后普通 reconcile 完成，执行器被设为必失败也不触发。 |
| 6：发布前只读核对、备份排空、实际安装、健康；八图生产补收和浏览器/下载 hash；恢复接纳与中文提交推送 | **实施未完成，且原补收前提已失效** | 发布代码审查见 RELEASE-R3 独立报告，不将其模拟部署测试说成安装验证。当前删除证据见 `output/studio-delivery-reliability-20261024/original-current.json:1`；本轮未执行部署/补收/Git，未来适配须重新审查。 |
| 既有多会话、国内业务及 Skills 保持 | 范围符合 | `runner.py:138` 将新完成解析限制于 studio，`:168` collect 为 handler 可选接线；本次 `git diff --name-only -- .agents backend/app/execution backend/app/modules` 对应实际完整路径无输出。无新页面、API 或表，前端仅在原消息组件增加状态。 |

## Stage 2：质量、安全与验证真实性

| 维度 | 结果与证据 |
|---|---|
| 文件大小、职责、命名和类型 | PASS。44 个本次新增/修改 Python/TS/Vue/MJS 文件全部不超过 300 行，最高 294；生产 native 274、delivery job 188、snapshot 114，按解析、存储、恢复职责拆分。清单 `output/studio-delivery-reliability-20261024/reviewer-r5-linecounts.json:1`。前端新增输入按 `unknown` 验证，未新增 `any` 类型，`src/api/overseas/studio.ts:19`。 |
| 错误处理与可恢复性 | PASS。`delivery_job.py:103`、`:151`、`:168` 保存异常保留 pending/captured 项并退避；OwnershipLost 单独抛出。`delivery_context.py:49` 区分明确失败与无法核实的完成，`delivery_recovery.py:35` 不将缺回执视为成功或启动模型。日志仅记录 job/item，不写图片字节或提示词。 |
| **安全扫描** | **PASS：未发现本次引入的密钥、注入或危险动态执行。** 18 个受审产品文件扫描 eval、unsafe HTML、VITE secret、硬编码 token/password、个人绝对路径、插值 SQL、any 类型，结果空；`output/studio-delivery-reliability-20261024/reviewer-r5-security.json:1`。路径安全不能仅靠 grep，已对 `delivery.py:46`、`delivery_snapshot_fs.py:139` 与 `context_fs.py:65` 的无链接读取/安全派生快照路径做人工检查。SQL 使用 SQLAlchemy 绑定表达式，公开图片下载沿用已有归属鉴权。 |
| 测试前提真实性 | PASS。`backend/tests/studio_delivery_helpers.py:21` 通过真实 send API 创建 Job/Turn，并运行正式 runner；仅替换外部 CLI 进程与存储边界。`test_studio_delivery_native_history.py:58` 第一轮经真实失败状态、第二轮 send 返回 200 后再重展，没有直接篡改 DB 伪造成功；`:117` 的两组只差早前工具失败。`test_studio_delivery_recovery.py:70` 在 SQLAlchemy before_commit 注入真实提交边界故障；fencing 用真实取消/删除接口。 |
| 并发与平台证据 | PASS，范围明确。`test_studio_delivery_postgres.py:26` 使用 Barrier 让 2/4 个 recoverer 先读同一 uncertain job 再争抢，断言一个 collector、Picture、ExecutionObject 和一次上传。真实 PostgreSQL 2 PASS 及 Linux 链接 10 PASS 已有独立执行证据，见下文；本轮 Windows 本地没有伪称跑过 PG。 |
| UI 引导真实性 | PASS。`StudioTurns.vue:31` 的“系统会自动补收”由 `delivery_recovery.py:19` 实现；未新增不存在的操作或特殊交付格式要求。完成后提示移除、保存中仍展示已有图，浏览器实测证明。 |
| 实际视觉对比 | PASS。使用正式 build 和真实 Vue 组件、隔离 API fixture，分别打开保存中和既有完成消息状态；截图 `output/playwright/studio-delivery-status/desktop-saving.png`、`mobile-saving.png`、`desktop-baseline-complete.png` 已亲自查看。沿用既有 ElAlert 和卡片样式，没有新按钮或版式；1366×900 与 390×844 进度文字均通过真实边界/裁剪检查。基准消息字体 14px、颜色 rgb(48,49,51)，保持既有控件密度。它是本地真实组件验收，不能替代生产页面验收。 |
| Spec 漂移 | 未发现。`queries.py:103` 与 `StudioTurns.vue:11` 仅扩展合同规定的交付状态；repair 位于运维调用链，不新增用户页面、业务表或自动恢复删除任务行为。 |

未确认协议的边界：本 reviewer 核查了“work 文件经 view_image 是否能形成最终用户原生附图”的疑问。工具给模型检查图片不等于用户最终呈现，不能仅合成一个 input_image 就认定产品缺陷，也不能收取所有过程图。原生产样例在审查期间已删除，读取停止，未取得可支持新增缺陷的真实公开呈现协议。因此本报告没有把这一推测列为 HIGH，也没有声称已验证任意 view_image/work 输出路径的新协议支持。当前确认过的 imagegen 原生协议、显式 work/native 最终引用及历史重展按上表通过。

## 独立执行、编译原始输出

后端 core 命令（backend 工作目录）：

```text
.venv/Scripts/python.exe -m pytest tests/test_studio_completion.py tests/test_studio_delivery_bridge.py tests/test_studio_delivery_recovery.py tests/test_studio_delivery_fencing.py tests/test_studio_delivery_repair.py tests/test_studio_delivery_snapshot.py tests/test_studio_native_images.py tests/test_studio_delivery_native_presentations.py tests/test_studio_delivery_native_history.py ../../output/studio-delivery-reliability-20261024/test_reviewer_native_history_e2e.py ../../output/studio-delivery-reliability-20261024/test_reviewer_r3_historical_failed_turn.py ../../output/studio-delivery-reliability-20261024/test_reviewer_r4_current_generation_retry.py -q --junitxml=../../output/studio-delivery-reliability-20261024/reviewer-r5-core-tests.xml
187 passed, 4 skipped, 2 warnings in 34.47s
```

既有接线回归：

```text
.venv/Scripts/python.exe -m pytest tests/test_overseas_studio_execution.py tests/test_overseas_studio_transcript.py tests/test_studio_formal_delivery.py tests/test_studio_image_recovery.py tests/test_studio_native_recovery.py tests/test_studio_work_baseline.py -q --junitxml=../../output/studio-delivery-reliability-20261024/reviewer-r5-existing-tests.xml
362 passed, 4 skipped, 2 warnings in 48.25s
```

8 项 skip 为 Windows 符号链接/POSIX 文件能力限制，未计作通过。两类 warning 为 Starlette 的 httpx 与 anyio 接口弃用，不影响断言。

前端完整测试：`node node_modules/tsx/dist/cli.mjs --test tests/*.test.ts`。原始文件 `output/studio-delivery-reliability-20261024/reviewer-r5-frontend-tests.txt:1`，末尾原文：

```text
ℹ tests 387
ℹ suites 0
ℹ pass 387
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9074.7616
```

编译：`node node_modules/vue-tsc/bin/vue-tsc.js --noEmit` exit 0，无 stdout；随后 `node node_modules/vite/bin/vite.js build` exit 0。完整原始输出 `output/studio-delivery-reliability-20261024/reviewer-r5-build.txt:1`，末尾：

```text
dist/assets/index-Ds0nk4hC.js 963.71 kB │ gzip: 307.80 kB
✓ built in 34.12s
```

后端：`hengxin-smart-image/backend/.venv/Scripts/python.exe -m compileall -q hengxin-smart-image/backend/app/overseas/studio hengxin-smart-image/backend/app/overseas/execution`，原始结果：

```text
PYTHON_COMPILE_PASS: exit 0
```

浏览器：正式 build 在本地 `127.0.0.1:3034`，运行仓库 `tests/studio-delivery-status.browser.mjs` 与输出目录中的基准状态扩展脚本。原始结果：

```text
PASS: capturing, partial image, saving/waiting counts, completion, desktop/mobile clipping; no model calls
{"baselineBubble":{"fontSize":"14px","color":"rgb(48, 49, 51)","padding":"0px","borderRadius":"0px"},"viewport":"1366x900","evidence":"actual production components with isolated API fixture"}
PASS: capturing, partial image, saving/waiting counts, completion, desktop/mobile clipping; no model calls
```

## 引用的独立 Linux 与发布证据边界

读取 `output/studio-delivery-reliability-20261024/linux-validation/REPORT.md:1` 和对应 XML：完整基线 2544 PASS / 206 条件 skip；其后 studio 全域差异回归 814 PASS / 23 skip；真实 PostgreSQL 2/4 worker 竞争 2 PASS；Linux 文件链接边界 10 PASS。该执行快照早于本次 3 文件工具失败处理 delta，**不能称为当前 candidate 又跑了一次完整 Linux 后端**。当前新增差异已由本报告的 187 项本地 core 独立覆盖；主 Agent 后续 Linux delta 或实际安装证据另行保存。

发布分区既有两阶段 PASS 见 `docs/reviews/STUDIO-DELIVERY-RELEASE-R3-20261024.md:7`，其 candidate 为 `12a9780008a7c301e8fd684eebcc856bb34b85983a3aa01289c95a5a3bcb7f97`，37 项专项和 129 项继承回归原始输出均在报告中。本 reviewer 已核对当前 release 文件与当前 candidate 摘要一致，但 R3 报告未附 7 个文件的逐项 hash、R4 核心 snapshot 也未包含 release；未将主 Agent“release 未变”的说明冒充独立逐字节历史比对。发布源码后续适配必须以新的独立 release 报告和快照为准。

本报告不写 `.needs-review` 的 clean，不调用 review-approve。由主 Agent 按实际审查范围、发布分区凭据和最终快照决定登记；结束本报告不表示生产发布、原任务补收或 Git 推送完成。
