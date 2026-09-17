# 最终回复收图收尾独立审查 · 2026-09-17

- candidateId：`59d22f5a86e4d5cde79d48205c0c2765552296f38fdb2a231c7588b30b3304bb`。
- **Stage 1：PASS。Stage 2：PASS。** 本次审查范围内未发现待修复的 HIGH/MEDIUM 问题。
- 需求依据：`Product-Spec.md:477`、`:479`，`DEV-PLAN.md:3`。执行 `.agents/skills/code-review/SKILL.md` 和 `docs/HARNESS-REVIEW.md`。
- 范围：相对已批准 `0bb045467430d622862ddc3483a30b47df7324d1143f5e6bdbf905ac5c2691d1` 的 14 个后端文件，含新增 collector 与两份测试。既有 Astra/high 差异核对保留；不重审历史全产品功能，不把未实现的后续阶段当缺陷。
- 两次失败报告分别针对旧候选；本次从 Stage 1 重新审查当前实现，并独立验证此前失败输入。审查期间读到的快照编号保持一致；本 reviewer 只新增本报告，未改代码、测试或业务 Skill，未提交、部署、调用模型、写 clean 或批准凭据。

以下代码路径以 `hengxin-smart-image/` 为前缀；根目录需求文档除外。

## Stage 1：Spec Compliance

| 当前要求 | 结论与代码、测试证据 |
|---|---|
| 两个业务 Skill 保持原样 | 完整实现。当前 14 文件变更清单不含业务 Skill；`backend/app/execution/materials.py:64` 核验冻结版本，`:75` 校验本地发布内容，`:88` 保留旧 ZIP 完整读取。未增写业务 Skill 的步骤。 |
| `$Skill名称` 调用；只给目录、实际底图与素材、修改要求和补充意见 | 完整实现。`backend/app/execution/prompts.py:9` 至 `:34`，无 manifest、原生输出限制或内部任务清单。`:33` 的 JSON 是对用户意见的引用编码，不是平台交付协议。`backend/tests/test_task_prompt.py:16`、`:45` 通过。 |
| 壁纸固定要求，商品与文字使用各自要求 | 完整实现。`backend/app/execution/prompts.py:23` 至 `:27`；`backend/tests/test_task_prompt.py:16`、`:29` 通过，未给商品/文字任务附加手机屏幕指令。 |
| 返工提供当前图、原图和引用的修改意见 | 完整实现。`backend/app/execution/prompts.py:17`、`:28`；`backend/app/execution/materials.py:44` 按本轮选中槽准备当前结果。`backend/tests/test_task_prompt.py:35`、`backend/tests/test_revision_execution.py:43` 与端到端返工测试通过。 |
| 完整 Skill 在 `/work/skills/{name}` 及私有 HOME 发现目录只读可用 | 完整实现。`backend/app/execution/workspace.py:92` 至 `:103` 同一冻结目录两处 ro-bind，tmpfs 遮盖旧发现状态，保留本地版本和解压后的旧 ZIP；`backend/tests/test_local_skills_linux.py:61` 对完整脚本、双路径字节一致、只读和邻居不可见有真实 bwrap 断言。主线提供 Linux 76 passed 证据，未冒充本 reviewer 在 Windows 独立运行 Linux。 |
| 唯一来源为本次 CLI 完成前最终 assistant 答复 | 完整实现。`backend/app/execution/final_delivery.py:59` 校验当前 events、会话、错误、最后 agent_message 与 turn.completed；不反向搜索较早消息。`backend/tests/test_final_delivery.py:53`、`:67`、`:250` 通过。 |
| 候选、工具输出、过程消息、旧轮答复不作成品 | 完整实现。`backend/app/execution/final_delivery.py:80`、`:217` 只解析最终答复；`backend/app/execution/codex_runner.py:148` 使用本轮 control events。`backend/tests/test_final_delivery.py:44`、`:53` 通过；真实归档回放也通过。 |
| 支持 Skill 合成、修复后的成品；不要求原生 bytehash 或平台清单 | 完整实现。`backend/app/execution/codex_runner.py:167` 调用最终收集器，未调用 provenance；`backend/app/execution/final_delivery.py:189` 允许本轮 work 成品。`backend/tests/test_final_delivery_roundtrip.py:27` 制造与原生候选不同的修复字节及过时 manifest，`:70` 验证实际发布和下载仍等于修复成品。 |
| 明确编号优先，否则按展示顺序对应底图 | 完整实现。`backend/app/execution/final_delivery.py:19`、`:36`、`:44` 提取数字、中文数字、标题与列表上下文，`:222` 校验完整编号集合后排序。`backend/tests/test_final_delivery.py:159`、`:167`、`:198`、`:229` 通过；另见下方独立 HTTP 变体实测。 |
| 前两轮错槽修复：括号编号、第 N 张、带说明标题、纯数字标签、编号列表 | 已修复。`backend/app/execution/final_delivery.py:36`、`:44` 与 `:151`；`backend/tests/test_final_delivery.py:159`、`:198` 覆盖乱序 4/2/3/1、标题附说明及中间解释文本。独立将这些输入注入真实 runner 流程后，下载字节与槽位顺序一致。 |
| 预览和下载同图去重，冲突或重复文件不得占多个槽 | 完整实现。`backend/app/execution/final_delivery.py:158` 规范化 work 相对/绝对路径并合并编号，冲突拒绝；`:232` 再按实际路径检查重复。`backend/tests/test_final_delivery.py:174`、`:183`、`:206`、`:218` 通过；四图预览+下载 HTTP 变体通过。 |
| 完整数量，不猜缺失槽位；单张返工能保留原图编号 | 完整实现。`backend/app/execution/final_delivery.py:220` 要求唯一引用数完全一致，`:225` 单图允许正的原任务编号。`backend/tests/test_final_delivery.py:92`、`:109`、`:218` 通过；实际单张返工 `![4]` 变体仍只更新所选槽。 |
| 只允许本轮 work 非保护目录，或本会话 baseline 外新增原生文件 | 完整实现。`backend/app/execution/final_delivery.py:174` 至 `:198`，拒绝其他绝对路径、路径穿越和 inputs/targets/current/skills 等目录；`:186` 按历史文件名拒绝，即使历史内容被改也不收。`backend/app/execution/codex_runner.py:116` 启动前存 baseline。`backend/tests/test_final_delivery.py:98`、`:133` 通过。 |
| 阻止链接、重复文件；校验格式、解码、大小和基本尺寸安全 | 完整实现。`backend/app/execution/final_delivery.py:198`、`:202`、`:237`、`:241` 复用安全路径及受控读取；`backend/app/modules/files/validation.py:35` 校验实际格式、所有帧及像素上限。`backend/tests/test_final_delivery.py:139`、`:151`、`:236` 覆盖损坏、目录、重复和硬链接。本机软链接创建条件跳过，未算通过；主线 Linux 专项补充相关证据。 |
| 缺失、不完整和无效图片明确失败；不宣称视觉合格 | 完整实现。`backend/app/execution/diagnostics.py:14` 新增安全的缺失/不完整/历史图错误；runner `:186` 和恢复 `:161` 分类失败。`backend/tests/test_observed_runner.py:46`、`:61`、`:74` 及 `backend/tests/test_execution_reconcile.py:232` 通过。代码只有技术校验，没有视觉合格证明。 |
| 取消、失去认领权不发布；历史任务不自动重跑 | 完整实现。`backend/app/execution/codex_runner.py:161` 检查停止条件，`backend/app/modules/tasks/results.py:13` 原子核验认领；恢复 `backend/app/worker/reconcile.py:27`、`:99` 检查当前轮次及原进程死亡，恢复分支不启动 CLI。`backend/tests/test_codex_runner.py:156`、`backend/tests/test_execution_reconcile.py:97`、`:123`、`:138`、`:199` 通过。 |
| 新执行及返工统一 final-reply-v1；marker 模型不可见 | 完整实现。`backend/app/execution/codex_runner.py:119` 在 control 写 marker；`backend/app/execution/workspace.py:90` 仅挂载 home 和本轮 work，未挂载 control。新建与 resume 走同一 marker/collector 路径；`backend/tests/test_codex_runner.py:67` 和返工回归通过。 |
| 恢复新协议共用 collector；旧无 marker 保留 manifest/provenance | 完整实现。`backend/app/worker/reconcile.py:134` 至 `:150` 显式区分新/旧协议，未知协议不降级。`backend/tests/test_execution_reconcile.py:223`、`:232`、`:240` 及既有恢复测试通过。 |
| 新建和 resume 保持 Astra/high | 完整实现。`backend/app/execution/codex_runner.py:132` 至 `:137` 两分支后的公共参数一致；`backend/tests/test_codex_runner.py:113`、`:136` 通过。此次未发起付费模型请求。 |
| UI、引导真实性与 Spec 漂移 | 本候选不新增或修改前端页面、组件、API、表。新增内容为 Spec 明确要求的内部协议、收图逻辑及失败提示；未发现超出本次范围的功能。`backend/app/execution/diagnostics.py:14` 文案与实际失败条件一致。视觉页面对比不适用于此次纯后端变更，不沿用旧视觉验收作为新证据。 |

部分实现：无。未实现：无。此结论限于上述当前调整，不是对所有 Markdown 扩展语法、任意自然语言表达或生成图片视觉效果的保证。

## Stage 2：Code Quality

| 项目 | 结论与证据 |
|---|---|
| 结构、命名、类型、文件大小 | 通过。新 collector `backend/app/execution/final_delivery.py:59`、`:110`、`:174`、`:209` 按事件、引用、路径、图片校验拆分；生产入口有类型信息、固定返回图片列表。全部 14 文件均不超过 300 行：collector 246、runner 206、diagnostics 249、prompts 34、workspace 105、reconcile 167；八份测试分别 200/243/257/88/114/90/111/56 行。无新增 any 类型或动态执行。 |
| 错误处理及稳定恢复 | 通过。`backend/app/execution/final_delivery.py:74`、`:237` 将读取/解码异常转为固定错误；`backend/app/execution/diagnostics.py:14` 不暴露原始路径或上游错误。`backend/app/worker/reconcile.py:161` 新协议确定失败可结束，`:164` 未知基础设施异常保留 uncertain，未盲目重放。相关 runner/恢复故障测试通过。 |
| 测试真实性 | 通过。`backend/tests/test_final_delivery_roundtrip.py:19` 使用 HTTP 接纳，`:27` 仅模拟付费 CLI 边界，真实执行素材准备、collector、发布、测试对象存储和 HTTP 下载；`:70` 断言初次、单图、整套的实际字节。测试图与 native 候选不同，不是以原生哈希假前提绕过需求。独立乱序标题/列表注入及归档 events 回放均通过。 |
| 安全扫描 | 通过。本轮六个生产文件扫描 `eval(`、`exec(`、`dangerouslySetInnerHTML`、`innerHTML`、暴露 VITE KEY/SECRET/TOKEN、硬编码 key 前缀和 password 赋值，无命中。`backend/app/execution/workspace.py:90` 使用 argv 挂载、`:98` 拒绝发现目录链接；无 shell 拼接、SQL 文本拼接或新增凭据暴露。固定绝对路径为受控沙箱目标，非用户任意路径。 |
| 安全文件读取 | 通过。`backend/app/execution/final_delivery.py:176` 限制路径、`:202` 拒绝硬链接、`:237` 调用受控读取。`backend/app/execution/diagnostics.py:79` 的 POSIX 分支逐级 O_NOFOLLOW、dir_fd 打开，校验普通文件/单链接/大小及读取前后元数据；`backend/app/modules/files/validation.py:40` 限制解码及全部帧。生产执行须 Linux 隔离，Windows fallback 只作为本地验证边界。未发现此次差异新增可利用的越界读取路径。 |
| 视觉对比 | 不适用。14 文件清单仅后端及测试，没有需要打开并与邻居基准比较的新页面。未对线上图片效果或现有 UI 做新通过声明。 |

## 独立验证与原始输出

运行目录：`hengxin-smart-image/backend`；设置 `PYTHONUTF8=1`，使用既有 `.venv/Scripts/python.exe`，未安装或改依赖。

1. `.venv/Scripts/python.exe -m pytest tests/test_final_delivery.py tests/test_final_delivery_roundtrip.py tests/test_codex_runner.py tests/test_execution_reconcile.py tests/test_revision_execution.py tests/test_task_prompt.py -q`：

```text
............................................................s........... [ 65%]
......................................                                   [100%]
109 passed, 1 skipped, 2 warnings in 8.94s
```

2. `.venv/Scripts/python.exe -m pytest ../../output/diagnostics/exact-prompt/test_replay_delivery.py tests/test_observed_runner.py -q`：

```text
.....                                                                    [100%]
5 passed, 2 warnings in 2.58s
```

真实归档回放脚本 `output/diagnostics/exact-prompt/test_replay_delivery.py:18` 复制原始 events 与四张 PNG 到测试工作区，`:35` 断言下载字节等于归档成品；此脚本仅是本地实验，不属于批准代码快照。

3. 独立端到端输入变体：不改任何文件，以内存 pytest plugin 包装 `backend/tests/test_final_delivery_roundtrip.py:27` 的 CLI mock，依次替换最终答复为：四图 4/2/3/1 带说明标题和中间解释文本、每张同时预览及下载；单图 `![4]`；整套 4/2/3/1 的 `N、[下载成品]` 列表。保留 `:70` 的真实 HTTP、runner、下载字节断言。

```text
.                                                                        [100%]
1 passed, 3 warnings in 1.42s
```

4. `.venv/Scripts/python.exe -m compileall -q app tests`：

```text
stdout: （空）
stderr: （空）
exit_code: 0
```

两条常规 warning 为既有 Starlette/httpx、anyio BlockingPortal 弃用提示；内存 plugin 多一条 anyio 已导入无法重写断言的提示，无测试失败。

## 主线补充证据与交付边界

已读取 `output/final-delivery-backend-tests.log` 尾部，原始结果为：

```text
711 passed, 146 skipped, 14 warnings in 37.07s
```

`docs/FINAL-REPLY-DELIVERY-VALIDATION.md:9` 记录同候选 Linux 76 passed、前端 110 passed 及含类型检查的 build 通过。它们是主线执行证据，本 reviewer 未重复整套 Linux/前端测试。条件跳过不当成验证通过。

本次完成的是代码与本机交付链路审查；未部署此次代码，未再次调用付费模型，未证明线上网页真实生成已通过，也未把文件有效性和下载字节一致当成视觉效果合格。

主 Agent 可用本报告为同一 candidateId 登记 Stage 1/Stage 2 PASS；登记及完成交付前仍须 `review-status` 确认当前代码一致。任何后续代码修改须重新固定候选并复核差异。
