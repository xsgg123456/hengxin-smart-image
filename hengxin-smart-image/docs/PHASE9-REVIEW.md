# Phase 9 独立审查报告

- 日期：2026-09-10。
- candidateId：`3f3398f33c1f98f0730c04d1a871f0596fe3caf0477910429e4409ab2cc0dd6a`。
- 范围：Phase 9 execution 模块、attempts/迁移/config/tasks/worker、相关测试及 infra 脚本；依据 Product-Spec 9.1、9.2、AC-015/021–025、DEV-PLAN Phase 9、PHASE9-PLAN.md、CODEX-EXECUTION.md。
- 使用 `.agents/skills/code-review/SKILL.md`；仅审查，未修改实现。
- 用户预存 `.agents/skills/dev-builder/SKILL.md`、`.codex/hooks.json` 修改不纳入 Phase 9 缺陷；根 output 为运行产物。
- **Stage 1：FAIL。Stage 2：未执行（存在 HIGH）。不得批准此 candidate。**
- 主 Agent 在审查中开始修复；下述原始行号来自首次读取的代码。新代码的局部验证另列，不能将旧 candidate 结论套用到新快照。

## Stage 1：关键不匹配

### HIGH-1：复制历史图或原输入可冒充本轮生成结果

需求：PHASE9-PLAN.md:5 要求“以明确 session/turn/call 关联原生图片”；DEV-PLAN.md:309 要求真实图片传输；执行提示自身也禁止原输入冒充结果（backend/app/execution/workspace.py:85）。

证据：`backend/app/execution/output_collector.py:108` 仅检查旧路径内容未变，`:111` 将不在旧文件名集合中的文件当新图，`:124` 只核对数量和清单，`:132` 只解码。`backend/app/execution/events.py:30` 开始的解析不采集图片工具调用与产物关联；`backend/app/execution/codex_runner.py:138` 不传入调用事实。因此旧图保留原样、复制到一个新文件名，就满足所有判断。首次生成复制输入到该目录同样没有来源屏障。多图清单也由模型写入，不能单独充当工具生成证据。

独立实际复现：先写 old.png，snapshot_outputs，shutil.copyfile 到 exec-new.png，collect_outputs(expected_count=1)。原始输出：

```text
historical_copy_accepted= 1 exec-new.png
```

修复标准：依据实际 CLI 会话/本轮调用记录校验真实图像工具与文件关联；至少拒绝历史和输入复制冒充，并测试“仅文字结束+复制文件”不能成功。仅要求新文件名、修改时间或提示模型不能复制不构成证明。

### HIGH-2：可恢复的完整图片也一律失败，未实现恢复发布

需求原文：Product-Spec.md:306 AC-025，“能恢复的结果继续收集，不能确认时显示状态待核实并禁止返工/重试”。

证据：`backend/app/worker/reconcile.py:46` 已调用 collector 验证产物，`:48` 得到完整数量；但 `:56` 固定记录 failed_without_retry，`:70` 对未删除任务无条件 end failed。没有重新取得恢复发布权、上传及发布路径。即使 CLI 已成功、进程确认退出、图片完整，仅 PG 尚未提交，仍永久丢失业务交付，需用户再发收费调用。CODEX-EXECUTION.md:21 的“结束为失败或取消”相对上游 AC-025 构成需求漂移；失败自动重跑 0 不意味着禁止恢复已有结果。

修复标准：保持同任务互斥，在核实旧进程退出、轮次/取消/当前任务有效及本轮产物真实性后，以新的受控恢复凭据收集已有结果，不再启动 CLI；取消及旧执行者迟到仍不得发布。无法确认时维持 uncertain。

### HIGH-3：认领后、版本检查期间删除会永久占用执行容量

需求原文：Product-Spec.md:275–276 删除需持久取消并停止执行；AC-023 要求取消轮次停止重派、重启不复活。

原快照证据：`backend/app/execution/codex_runner.py:67` 先认领；`:73` 执行版本检查；期间删除会使 `:79` valid=false，`:80` 直接 return。此时尚未创建 `:91` 的 attempt，也没有 end cancelled。租约过期后 `backend/app/modules/tasks/claims.py:41` 的扫描置 uncertain；reconcile.py:18 仅查询有 attempt 的轮次，无法收敛。claims.py:65 的全局 occupied 计入 uncertain；并发 1 时其他任务也无法执行。

审查中主 Agent 已加入启动前取消分支。临时独立测试将 DELETE 注入版本检查，**新代码**原始输出：

```text
delete_preflight_job= cancelled attempt= None
.
1 passed, 2 warnings in 1.30s
```

此修复不属于原 candidate；需新快照复核。测试位于根 output/test_review_preflight_cancel.py，未改业务代码。

## Stage 1：逐项覆盖

“代码匹配”表示所述静态路径存在，未替代 Linux/PG/真实 CLI 验收；本报告不声称整个 Phase 通过。

| 需求 | 判定与证据 |
|---|---|
| 9.1 新任务先持久入队，不预造 ID | 代码匹配：backend/app/modules/tasks/service.py:20 写 Job/Round/Outbox；:61 提交；session 只在 codex_runner.py:83 后建立。 |
| 9.1 首次实际执行创建并绑定唯一会话 | 代码匹配：codex_runner.py:108 监测 thread.started 后持久化；attempts.py:16 session_id 唯一。test_execution_records.py:30 覆盖跨任务唯一约束。 |
| 9.1 本轮结束退出，保留材料，人工查看不挂进程 | 代码匹配：process.py:57 finally 停止执行；workspace.py:19 持久任务 home；runner 无人工等待分支。整个进程树的 Linux 证据尚待最终回归。 |
| 9.1 单张/整套返工用同一 ID 启动新进程 | 代码匹配：codex_runner.py:119 指定 previous resume，无 --last；materials.py:30 选择单张或整套；results.py:18 映射真实目标 slot。真实返工跨重建验收尚待最终证据。 |
| 9.1 新业务任务独立会话及环境 | 代码匹配：workspace.py:21 UUID 任务目录，:67 外层仅挂本任务 home/work；attempts.py:16 唯一会话。verify_phase9_sandbox.py:25 测跨任务读写，:59 比较 ID。派发称已实测，本次未独立重跑。 |
| 9.1 归档不执行 CLI，不销毁可返工会话 | 本次无归档新增执行路径；执行器仅由 worker/tasks.py:46 generation 分支调用。归档完整流程按 DEV-PLAN.md:312 留 Phase 11，未将未来功能算现有缺陷。 |
| 9.1 删除清理不破坏进程/归档引用 | 部分实现：cancellations.py:17 持久取消，results.py:14 发布前 valid；启动前取消存在 HIGH-3。本次未引入会话清理。 |
| 9.1 Worker 重建恢复；缺材料失败保旧图 | 代码匹配：workspace.py:21 持久 home、轮次目录独立；codex_runner.py:103 缺会话材料抛错，不建替代会话；results.py:14 屏障及事务。跨重建的完整平台证据待验证。 |
| 9.2.1 同任务全阶段互斥、不同任务隔离 | 部分实现：service.py:91 ACTIVE 阻止新轮次；claims.py:13 PG 短锁及 gate；workspace.py:52 沙箱白名单。HIGH-3 导致不能解除的占用。 |
| 9.2.2 幂等、异内容冲突、先授权 | 代码匹配：service.py:39 authorize 先于 replay，accept_round:80 同样先授权，:88 等锁后再次 replay，:91 冲突。既有 PG 并发最终回归待提交。 |
| 9.2.3 重复消息仅一次实际启动、不长持数据库锁 | 代码匹配：claims.py:57 仅 queued 可认领、:65 原子 gate；codex_runner.py:97 下载/执行在业务锁事务之外；attempts.py:28 round_id 唯一。实际独立 PG Worker 证据待验证。 |
| 9.2.4 失效执行不发布，迟到不改当前图 | 代码匹配：results.py:12–15 发布事务重新锁定并 valid；:30–35 同事务更新版本；runner.py:145 调此入口。上传后删除/旧凭据实际回归待验证。 |
| 9.2.5 不确定先核实，不盲重跑 | 部分实现：claims.py:44 标 uncertain；reconcile.py:24–27 核实 boot/PID/start。可恢复产物缺发布路径，HIGH-2。 |
| 9.2.6 删除持久化并确认停止，退出页面不取消 | 部分实现：cancellations.py:21 持久意图；runner.py:117 monitor，process.py:45 取消终止；原快照 HIGH-3。 |
| AC-015 | 同 9.1 会话/进程路径；缺完整平台首次+单张+整套+重建实机链证据，不能标通过。 |
| AC-021 | service.py:78 内部返工 seam及 claims.py:57；用户入口留 Phase 10。当前阶段独立 PG 争用证据待主 Agent 最终提供。 |
| AC-022 | claims.py:48–76、attempts.py:28、test_codex_runner.py:88 重投只调用一次；模拟不替代多 Worker 实机认领。 |
| AC-023 | HIGH-3；另有 runner 模拟取消用例 test_codex_runner.py:116，真实进程取消、上传后取消完整证据未完成。 |
| AC-024 | workspace.py:19、codex_runner.py:103/120；隔离脚本及本地目录测试存在，平台重建续接仍待最终证据。 |
| AC-025 | HIGH-2；uncertain 不重新启动代码存在，但可恢复结果分支未实现。 |
| Phase9 冻结素材及指定 Skill 下载 | 代码匹配：materials.py:11 校验实际对象 hash；:49 验证冻结 Skill checksum 并重新验证包；:35 读取冻结图片。test_codex_runner.py:151 损坏 Skill 不启动。 |
| Phase9 argv+stdin，不拼接用户 shell | 代码匹配：process.py:42 Popen(argv)，:38 request stdin；workspace.py:95 JSON 编码用户 note。Linux process 测试未在 Windows 伪装通过。 |
| Phase9 图片解码/slot/目录边界/上传 | 部分实现：collector.py:19 路径和链接边界、:81 slot、:132 解码；runner.py:144 上传、results.py:18 slot发布；缺原生来源真实性，HIGH-1。 |
| Phase9 超时、退出、对账 | 部分实现：process.py:48 超时、:25 终止；reconcile.py:24 身份；HIGH-2/3。 |
| Phase9 attempt/操作者/耗时/usage 去重与未知 null | 代码匹配：attempts.py:29–40 关联及起止时间，:50 usage 主键及 SQL NULL；events.py:51 terminal去重，runner.py:37 持久完成。启动前意图也存 attempt，实际调用统计须区分 process_id/status（本期未审 Phase13统计）。 |
| Phase9 Worker 心跳、依赖检查及检查时间 | 代码存在：health.py:14 pulse 写 checked_at 和文件可用性，:29 五秒循环。这里只证明配置文件存在，不证明认证有效、服务依赖健康；正式 Phase13展示需准确区分。 |
| Phase9 migration/config/infra | migration 0006_execution.py:16 建四表、:21 逆序删除；config.py:45 互斥执行器及 visibility 余量；service.py:29 冻结3600/重跑0；service.example:13 KillMode=control-group。SQLite迁移回归通过，最终 Linux PG 迁移日志尚未取得。 |

## UI、引导与范围漂移

本次没有新增页面或视觉组件；queries.py:44 仅把实际 sessionId 输出到既有详情。真实浏览器邻居渲染比对属于 Stage 2，本次因 HIGH 未执行，不标视觉通过。未来 Phase 10/11 功能未计为本期缺失。

明确漂移：CODEX-EXECUTION.md:21 无条件失败恢复，与 AC-025 不匹配（HIGH-2）。其余新增四表、执行适配和测试基础设施均在 DEV-PLAN Phase 9 明列范围内。PHASE9-PLAN.md:29 “当前代码尚未接入真实执行器”已落后实现，待主 Agent 随最终验证同步文档。

## 编译及测试原始证据

最初 .venv 启动器不可用，非编译错误，原始输出：

```text
Unable to create process using '"C:\Users\82358\AppData\Local\Programs\Python\Python312\python.exe" -m compileall -q app migrations'
```

改用主 Agent 提供的 Codex runtime Python，PYTHONPATH 指向 backend/.venv/Lib/site-packages 及 backend。执行 `python -m compileall -q app migrations`：原始 stdout/stderr 为空，exit code 0。

执行 `python -m pytest tests/test_execution_outputs.py tests/test_execution_records.py tests/test_codex_runner.py -q -p no:cacheprovider --basetemp <独占output目录>`：

```text
...................s..............................                       [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
49 passed, 1 skipped, 2 warnings in 2.62s
```

这些通过用例没有覆盖历史复制冒充；独立复现已经证明缺陷，不以测试绿灯替代真实性审查。取消临时测试最初因不加载项目 conftest 缺环境配置收集失败；补加载相同 conftest 后运行通过的是主 Agent 已修改后的分支。

## 快照变化及交接

主 Agent 明确告知审查中开始修复 HIGH-1/2/3。已经观察到 runner.py 原79–80行的提前返回变为先 end cancelled；局部验证完成时该文件 SHA256 为 `9E263AA53693E9DD9D343DBBEAEB06B02A0DFAABE9487EF19E01481076DD1F4B`。原 candidate 不再代表随后工作树。

必须重新 review-prepare 后从 Stage 1 复核变更，取得真实 Linux/PG/图片传输及生命周期证据，再进入 Stage 2。报告不写 clean，不登记 review-approve，不宣称 Phase 9 完成。
