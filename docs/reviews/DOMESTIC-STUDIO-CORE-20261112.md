# 国内 AI 工作台核心后端独立审查 · 2026-11-12

- **送审 candidateId：** `1fb7df3fa56c3e2487c4665924ba8076220c26d07f2c80bc83ffdf7d047b487a`。审查开始时 `review-status.currentId` 与送审编号一致。
- **范围：** `hengxin-smart-image/backend/app/modules/domestic_studio/` 的五入口、Skill 绑定、会话、发送、附件、执行、恢复、归档与删除；`backend/app/{execution,worker,retention}` 相关改动及复用的海外逻辑；国内 0033–0043 迁移及对应测试。为核验补收链路，检查了国内工作台及共享前端 API 的相关接线。本报告不覆盖完整前端视觉、发布实施或全产品审查。
- **依据：** `Product-Spec.md:1-11`、`DEV-PLAN.md:1-10`、`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md` 的会话和归档权限约束，以及 `AGENTS.md`、`.agents/skills/code-review/SKILL.md`。
- **Stage 1：FAIL（存在 HIGH）。Stage 2：未执行。** 以下事实和行号对应送审候选审查时所见；主 Agent 审查中已并行修改部分文件。旧结论不能批准后来的快照，修复后须重新固定快照并从 Stage 1 起复审。
- 未访问生产数据库、对象存储或生产服务；没有真实模型调用。所用 PostgreSQL 仅为授权的 `127.0.0.1:35439/hx_studio_test`，每个用例使用随机 schema。

## Stage 1 · HIGH 问题

### 1. 进程组尚有子进程时可误判为停止或完成

`backend/app/execution/verified_stop.py:18-30` 只检查记录的组长 PID；组长不存在时返回已停止。国内 `backend/app/modules/domestic_studio/recovery.py:25-35,38-45` 据此将不明取消置为 `cancelled`、释放容量，或在仅确认组长不存在后补收。正常执行亦有同样缺口：原候选 `backend/app/execution/process.py:24-32,43-66` 在组长已退出时不再检查进程组；`domestic_studio/runner.py:124-137` 据退出回执继续收取并结束轮次。旧国内 API 也使用同一进程执行原语（`backend/app/modules/api_image_edits/conversation_runner.py:12,179-180`）。

**影响：** 组长先退出但后代仍运行时，原进程仍可能写共享工作目录或调用模型，而系统已允许同会话新轮次或释放并发额度；补收也可能读到仍在变化的文件。不得把进程不明当成已结束。

**独立复现：** WSL 中启动本审查自建的独立进程组，让组长退出、子进程保持运行，再调用原候选 `stopped`；最后仅清理该自建进程组。原始结果：

```text
leader_alive= False
child_alive_in_original_group= True
verified_stop_reports_stopped= True
```

应核实完整进程组退出证据；覆盖正常退出、取消、崩溃后恢复和共享旧国内/海外调用。原候选测试 `backend/tests/test_verified_stop.py:6-30` 以替身只模拟组长，没有覆盖真实残留子进程。

### 2. 归档元数据缺失时，源会话仍可被物理删除

实施记录的权限约束要求删除源之前确认归档独立、**完整且可读**。原候选 `backend/app/modules/domestic_studio/conversation_cleanup.py:42-53,124-147` 只遍历当下存在的 `ArchiveFile` 行、核对路径和读取其字节，没有核对 `Archive.snapshot` 所列文件是否每项都有对应行、类型是否一致；而 `archive_queries.py:47-68` 的详情读取会拒绝缺失行。

**独立故障注入：** 在隔离 PostgreSQL 内成功归档后，模拟一条归档图片元数据行缺失；在同一个隔离假对象存储中，源删除仍执行且真实删掉原图，而归档详情仍不可读。此为人为注入缺行，不声称现有正常路径必然产生该损坏。原始结果：

```text
archive_detail_before_deletion= 503
source_cleanup_accepted= True
source_original_survives= False
1 passed, 2 warnings in 7.95s
```

应在源删除前把归档快照中各文件 ID、类型及对应副本清单逐项核对并校验字节；缺行、错类型、损坏或快照不完整时保留源。测试脚本为本机临时文件 `C:/Users/82358/AppData/Local/Temp/test_hx_archive_completeness_probe.py`。

### 3. 大文件复制或清理时持有全局权限锁和执行门，其他成员的停止及执行检查被阻塞

原候选 `backend/app/modules/domestic_studio/archive_service.py:125-149` 先获取成员权限锁和全局 `ExecutionGate`，然后在同一事务中逐个读取、写入并再次读取所有归档对象。每个上传文件允许 500 MB（`backend/app/overseas/studio/files.py:29-34,57-64`）。`conversation_cleanup.py:124-147` 同样在执行门内读取归档并进行对象删除和核验。国内发送、停止等请求需要这些锁（`turn_service.py:42-45,91-96`），国内进程监控也需要执行门（`transcript.py:30-38`）。监控被阻塞时，执行循环里的超时和日志大小检查不能继续（原候选 `backend/app/execution/process.py:48-59`）。

**独立 PostgreSQL 双连接复现：** 暂停首个 `store.open`，另一个事务探测权限锁、获取执行门：

```text
permissions_lock_available= False
admission_lock_sqlstate= 55P03
1 passed, 2 warnings in 8.38s
```

这证明存储等待期间全局锁被占；没有测量真实网络或 500 MB 文件耗时。应将慢 I/O 移出全局锁，并以持久状态、归档/删除互斥与重新核对保护崩溃和并发。测试脚本为本机临时文件 `C:/Users/82358/AppData/Local/Temp/test_hx_archive_lock_probe.py`。

### 4. 收取失败的服务端恢复入口未接入实际工作台

`backend/app/modules/domestic_studio/runner.py:64-78` 在文件收取失败时将轮次置为 `uncertain`；`turn_service.py:120-147` 和 `router.py:114-120` 只提供服务端的原进程核验及补收请求。`frontend/src/api/shared/studio.ts:91-118` 没有调用该入口的方法，`frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:14-22,54-58` 和 `frontend/src/views/shared/studio/use-studio.ts:153-169` 只接了发送和停止，用户不能发起补收；同一会话的未终态作业又阻止发送新轮（`turn_service.py:57-60`）。

此外，候选国内页面及路由没有海外“取回文件”的选择入口：海外 `frontend/src/views/overseas/studio/OverseasStudio.vue:22,42` 与 `backend/app/overseas/studio/recovery_router.py:30-36` 提供该路径。原候选国内 `delivery_capture.py:12-17,21` 固定初次自动识别的选择和警告，重试相同清单不能证明解决未识别但原文件尚存的情形。须覆盖原调用不重复、丢响应重试以及自动识别失败时的可恢复路径；不能以直接停止冒充收取成功。

### 5. 国内实际运行拓扑的 Skill 安装与只读挂载尚未接入

`backend/app/modules/domestic_studio/management_router.py:53-60,66-74` 要求国内 Skill 根目录和独立 publisher socket；工作台读取本身依赖该 catalog（`router.py:41-44`）。现有 `hengxin-smart-image/infra/compose.yaml` 的国内 API/outbox 配置和现有原生服务未提供所需国内根目录、publisher 服务、socket 和只读挂载；实施记录“当前进度”亦明确该接线和联合发布仍未完成。

因此不能按现有拓扑宣称五入口、真实 Skill 或发布可用。实际已有证据区分容器内 API/outbox 和宿主机原生执行/删除服务（`docs/INTRANET-245-PLAN-20261110.md:91`、`infra/compose.yaml`、`infra/hengxin-domestic-deletions.service`）；`backend/app/retention/worker.py:129-141` 将清理交给删除服务。必须另行完成受保护目录、身份及权限、独立发布服务和可恢复联合迁移的隔离验收。

## Stage 1 · 逐项核对及实测边界

| 需求 | 核对结果和证据 |
| --- | --- |
| 五入口、空绑定、拒绝自选 Skill | **部分验证。** `policy.py:11-52` 固定五入口及归档许可，`bindings.py:74-82` 和 `turn_service.py:42-50,67-81` 在发送事务内冻结绑定并拒绝客户端 Skill；`0033_domestic_studio_bindings.py:11-26` 不插默认绑定。独立空 schema 升级后绑定数为 0；真实部署目录未接线，见 HIGH 5。 |
| 会话、附件按创建者隔离 | **所测通过，非全链路认证证明。** `conversation_service.py:17-38,64-104` 限当前成员及工作台；`file_service.py:39-61` 限本人文件；`test_domestic_studio_http_pg.py:39-76`、`test_domestic_files_pg.py` 覆盖跨成员拒绝。普通成员角色集合见 `backend/app/modules/auth/permissions.py:5-23`。实际钉钉及生产身份未测。 |
| 创建/重命名/发送幂等 | **所测通过。** `conversation_service.py:52-81,85-103` 和 `turn_service.py:42-54,67-87` 在锁内核对请求回执并事务写入；`backend/app/core/idempotency.py:8-26` 对同键异内容返回 409；`test_domestic_turns_pg.py:60-82` 验证同键只有一个作业/轮次/引用。真实断网及浏览器端跨刷新链路不在本次独立验证范围。 |
| 对话、姓名和时间 | **代码已接入，未独立验证真实身份时钟。** `queries.py:22-25,75-98` 返回发送者和 UTC 时间，`transcript.py:13-22,30-48` 持久化公开消息；共享 `StudioTurns.vue:6-7,50-54` 以北京时间显示。用户真实姓名在响应时取当前国内用户记录（`queries.py:74,89`）。 |
| 附件、输出和多轮执行 | **部分验证。** `file_service.py:21-36` 存私有原件，`execution_workspace.py:23-63` 校验冻结 Skill、会话及历史输入，`output_store.py:15-57` 校验并保存输出；模拟 CLI 测试覆盖一个成功结果。完整真实多轮、实际二进制及原生沙箱未验证；进程组问题见 HIGH 1。 |
| 停止、失败与只补收 | **不通过。** 服务端的不明状态不直接重新调用模型（`runtime.py:60-69,89-98`、`recovery.py:67-76`），但 HIGH 1 和 HIGH 4 分别说明进程组证据及用户恢复链路缺失。 |
| 仅新品归档、共享副本与私有原件 | **部分验证。** `policy.py:11-28` 拒绝三种替换工作台；`archive_service.py:36-50,59-119` 建立独立清单和目标，`archive_router.py:36-67` 对授权国内成员提供共享读取；`test_domestic_archive_pg.py:205-240` 测试其他成员可读副本且不能读原件。完整性故障时源删除不安全，见 HIGH 2。 |
| 归档失败、源删除及重试 | **部分验证。** `archive_service.py:122-164` 的复制失败保留源，`conversation_deletion.py:14-47` 和 `conversation_cleanup.py:121-155` 保存删除状态并允许重试；`test_domestic_archive_pg.py:102-179` 覆盖模拟存储失败与重试。缺行故障及长时间持锁不通过，见 HIGH 2、3。此测试使用内存对象存储，不等于真实 MinIO 故障验证。 |
| Skill 角色、绑定保护和 ZIP | **范围内代码已接线，未重做完整管理专项。** `management_router.py:24-27,77-119,122-157` 将管理限制于超级管理员；`skill_state.py:28-60`、`skill_publication.py:84-106` 阻止绑定中停用或删除；前端 `SkillFolderActions.vue:32-40` 与 `skill-folder-zip.ts:5-52` 生成并校验 ZIP。完整交互及视觉另见 `docs/reviews/DOMESTIC-STUDIO-SKILLS-R9-20261112.md`，该报告本身为 Stage 1 FAIL。 |
| 清理 Skill 历史包 | **未证实完整回收。** `skill_publication.py:99-111` 保留被历史作业引用的包；`conversation_cleanup.py:99-107` 会删引用，但未触发对应的无引用包回收。不能将数据库记录删除或接口成功表述为已回收磁盘空间。 |
| 迁移 | **空库正向链路所测通过。** 本审查在随机 schema 从头升级至 0043，核对 11 张核心新表和空绑定，见下方原始输出。未以生产等量既有数据执行升级、回滚或恢复；0033–0043 的 `downgrade` 均显式拒绝自动降级。 |
| Spec 漂移 | 本次核查未发现普通用户选择 Skill 或默认绑定的代码（`policy.py:33-52`、`queries.py:99-106`）；未完成全项目 API、页面和表的漂移盘点。 |

## 独立测试及编译原始输出

在 `hengxin-smart-image/backend` 设置 `HX_BUSINESS_CONTEXT=domestic`、`APP_ENV=test`、授权测试数据库及测试 MinIO 凭据后运行：

```text
.venv/Scripts/python.exe -m pytest tests/test_domestic_archive_pg.py tests/test_domestic_conversations_pg.py tests/test_domestic_turns_pg.py tests/test_domestic_runtime_pg.py tests/test_domestic_runner_pg.py tests/test_domestic_files_pg.py tests/test_domestic_recovery_lock_pg.py tests/test_domestic_studio_http_pg.py tests/test_domestic_execution_workspace_pg.py tests/test_domestic_queries_pg.py tests/test_domestic_output_store_pg.py tests/test_domestic_delivery_capture.py tests/test_domestic_delivery_context.py tests/test_domestic_transcript_pg.py tests/test_verified_stop.py tests/test_worker_lease_timezone.py -q
.....................................                                    [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
37 passed, 2 warnings in 27.08s
```

该组测试启动时快照与候选一致，但测试期间存在并行修改，因此不把该次结果视为整个候选的原子运行凭据。两个额外故障注入分别见 HIGH 2、3；其测试替身、数据库和操作均局限于临时环境。

完整 Alembic 空库正向链路的隔离脚本先创建随机 schema，迁移后删除该 schema；输出：

```text
schema= hx_studio_7b623872a54c4b1e8e93c009f361cef0
migration_head= 0043
binding_rows= 0
required_tables_missing= []
```

首次调用该临时脚本因临时脚本目录不在 `PYTHONPATH` 报 `ModuleNotFoundError: No module named 'app'`；设置项目后端目录为 `PYTHONPATH` 后得到上述成功结果。

```text
.venv/Scripts/python.exe -m alembic heads
0043 (head)

.venv/Scripts/python.exe -m compileall -q app/modules/domestic_studio app/worker app/retention/worker.py app/execution migrations/versions
compileall exit=0
```

`compileall` 是 Python 语法检查，不是生产安装构建；它运行时工作树已变化，不能证明送审候选或后来快照完整通过。

## 未执行项

由于 Stage 1 有 HIGH，未执行 Stage 2 的系统代码质量、安全扫描及邻居基准页面实际视觉对比。本报告不宣称海外全量兼容、真实 MinIO、完整进程组故障矩阵、收费模型、真实身份、内网部署和恢复已验证。主 Agent 未授权本 reviewer 修复，也未调用 `review-approve`。

## 报告写入时的快照变化

相对送审候选的当前受控快照：`05340295c815d203ce34c970fd7117f5cb49e726eefafb7b4ab5b0fc1924028d`。下列文件在审查期间改变或新增；本报告不判定这些新内容：

- `hengxin-smart-image/backend/app/execution/process.py`
- `hengxin-smart-image/backend/app/execution/process_group.py`
- `hengxin-smart-image/backend/app/execution/verified_stop.py`
- `hengxin-smart-image/backend/app/modules/api_image_edits/conversation_stop.py`
- `hengxin-smart-image/backend/app/modules/domestic_studio/archive_deletion.py`
- `hengxin-smart-image/backend/app/modules/domestic_studio/archive_queries.py`
- `hengxin-smart-image/backend/app/modules/domestic_studio/archive_service.py`
- `hengxin-smart-image/backend/app/modules/domestic_studio/conversation_cleanup.py`
- `hengxin-smart-image/backend/app/modules/domestic_studio/conversation_deletion.py`
- `hengxin-smart-image/backend/app/modules/domestic_studio/queries.py`
- `hengxin-smart-image/backend/app/modules/domestic_studio/recovery.py`
- `hengxin-smart-image/backend/app/overseas/execution/reconcile.py`
- `hengxin-smart-image/backend/app/overseas/tasks/cleanup_process.py`
- `hengxin-smart-image/backend/tests/process_group_linux_probe.py`
- `hengxin-smart-image/backend/tests/studio_delivery_helpers.py`
- `hengxin-smart-image/backend/tests/test_api_cli_conversation.py`
- `hengxin-smart-image/backend/tests/test_domestic_archive_pg.py`
- `hengxin-smart-image/backend/tests/test_domestic_runner_pg.py`
- `hengxin-smart-image/backend/tests/test_domestic_studio_http_pg.py`
- `hengxin-smart-image/backend/tests/test_overseas_runner.py`
- `hengxin-smart-image/backend/tests/test_process_group_linux.py`
- `hengxin-smart-image/backend/tests/test_studio_delivery_postgres.py`
- `hengxin-smart-image/backend/tests/test_studio_delivery_repair.py`
- `hengxin-smart-image/backend/tests/test_verified_stop.py`
- `hengxin-smart-image/frontend/src/api/shared/studio.ts`
- `hengxin-smart-image/frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue`
- `hengxin-smart-image/frontend/src/views/shared/studio/studio-session-api.ts`
- `hengxin-smart-image/frontend/src/views/shared/studio/use-studio.ts`
- `hengxin-smart-image/frontend/tests/studio-sessions-fixture.ts`
