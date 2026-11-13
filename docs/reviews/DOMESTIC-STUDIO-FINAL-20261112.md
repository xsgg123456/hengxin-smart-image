# 国内 AI 工作台及联合发布独立审查 · 2026-11-12

## 审查结论、快照与边界

- **candidateId：`4a88a7404641e882b1f19445fcd04c24de70f84a4b0387fd11333688b9532369`。Stage 1：FAIL。Stage 2：未执行。** 不批准此候选提交或部署。发现 HIGH 后按主 Agent 要求结束本轮；下表逐项登记已核查和未核查部分，不能理解成已完成所有条目的验收。
- 范围：`Product-Spec.md:1-12` 的五个国内工作台、权限、Skill 管理、会话及文件、成品归档、恢复、国内外兼容，以及 `DEV-PLAN.md:1-24` 的联合发布接线、0032→0043 迁移、前向恢复、台账和后续发布清理门禁。预览为 `hengxin-smart-image/frontend/preview-domestic-studio/`，正式实现见 `hengxin-smart-image/frontend/src/views/hengxin/domestic-studio/`；对照 `Design-Brief.md:1-3`。
- 审查前和写报告前，`review-status` 的 `currentId` 均等于上述 candidateId；本轮未修改业务代码、未执行 `review-approve`、未写 clean、未提交或访问生产。报告 Markdown 不属于受控代码快照。主 Agent 修复后必须重新 prepare，从 Stage 1 起重审。
- 真实数据库故障探针仅连接本机隔离 PostgreSQL `127.0.0.1:35439`，使用随机独立测试 schema 或新建并删除的随机 `*_test` 数据库。上传探针只使用测试内容和本地 HTTP 存储替身。没有连接真实生产 MinIO、调用付费模型或切换生产。主 Agent 提供的已有测试结果不是本 reviewer 的独立重跑结果。

## Stage 1 · HIGH

### H1. 迁移未结束时仅凭一次 schema 读取允许恢复旧代码

**要求**：迁移前可恢复旧代码；迁移后只能前向恢复，故障及重入不得绕过门禁（`Product-Spec.md:12`、`DEV-PLAN.md:13-20`）。

**实际调用链**：`scripts/release/intranet/joint_studio_engine.py:32-48` 在备份后写入 `phase=migrating`，然后通过 `native_run` 运行 Alembic；`hengxin-smart-image/scripts/migration245/unify_release.py:60-66,161-164` 使用普通 `subprocess.run`。发布父进程意外终止不能证明迁移子进程已退出，也不能证明数据库端事务已结束。重新进入时，`scripts/release/intranet/joint_studio_release.py:160-182` 只比较 `snapshot.schemas`，读到 0032 即调用旧版恢复、写回旧台账及 `rolled-back`；`joint_studio_engine.py:69-74,138-144` 的内层保护同样只检查当前 schema。两处均未就 `migrating` 固定并核实迁移进程及数据库端未决事务。因此恢复时刻读到 0032，不能排除之后已有迁移提交到 0043，最终形成旧代码与新库并存且终态记录为 rolled-back 的状态。

**独立进程故障注入**：隔离测试使用真实 `Upgrade.recover` 和真实 `recover_or_refuse` 判断；原版恢复和数据库版本以 fixture 替身表示。真实子进程被父进程通过 `subprocess.run` 启动，父进程被终止后子进程仍可继续；恢复后才放行子进程修改模拟 schema。原始输出：

```text
launcher_terminated= 1
child_pid= 43696
recovery_phase_before_child_commit= rolled-back
schema_when_old_code_restored= 0032
recovery_actions= ['old-recovery']
schema_after_child_commit= 0043
migration_marker_phase_after_commit= rolled-back
.
1 passed in 5.12s
```

探针为本机临时文件 `C:/Users/82358/AppData/Local/Temp/test_joint_migration_orphan_review.py`；未将模拟 schema 充当真实 Alembic 迁移结果。

**数据库端独立探针**：随机本地 PostgreSQL 测试库中，先写未提交的 0043，再在同一 SQL 批次内执行 `pg_sleep` 与 `COMMIT`；中途终止客户端，观察服务端仍在处理、另一连接仍读到 0032，随后该批次提交。原始输出：

```text
database_before_client_exit= 0032
backend_before_client_exit= active:PgSleep
migration_client_exit= -15
backend_after_client_exit= active:PgSleep
database_after_client_exit= 0032
backend_final= gone
database_final= 0043
```

该批量 SQL **不是实际 Alembic 逐条发送语句的复现**；其证据是客户端退出或一次读到旧版本不能证明数据库端操作终止。修复应使恢复同时处理迁移进程与数据库事务两个边界，在无法确认时保持入口关闭和待核实，不依靠一次 schema 查询、人工改台账或杀进程后的瞬时读数证明安全。

### H2. 上传进程死亡后远端 PUT 可迟于删除清单；对真实 MinIO 的时序尚未验证

**要求**：会话及原始文件仅创建者可见，删除需清理源会话资料且归档独立（`Product-Spec.md:6,9,11`；`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:43-50`）。

**实际调用链**：`hengxin-smart-image/backend/app/modules/domestic_studio/file_service.py:22-49` 在按会话 OS 锁内调用 `store.put`，而 `backend/app/storage/minio_store.py:72-75` 将 PUT 交由远端对象服务。API 进程死亡时 OS 锁随进程释放；`backend/app/modules/domestic_studio/conversation_cleanup.py:81-100,126-163` 可以取得该锁，列举当时已有对象后删除会话并登记 deleted。代码没有在删除前证明**远端已接收但尚未完成的写入**均已结束，也没有在会话已删除后继续对迟到 PUT 执行可验证的回收。现有 `backend/tests/test_domestic_cross_uid_linux.py:24-85` 杀的是上传事务的 PG 连接，上传进程仍存活、持有锁并等待返回，不能覆盖 API 进程死亡这一时序。

**独立故障注入**：使用真实 `file_service.upload`、真实 `MinioStore.put` 和 MinIO Python SDK，真实隔离 PostgreSQL、真实会话删除流程；对象服务是本机受控 HTTP 替身。替身先收全请求体并等待，杀死上传 API 进程后先做源删除，最后允许对象服务提交。原始输出：

```text
server_received_bytes_before_api_exit= 26
api_process_exit= 1
cleanup_status= deleted
source_row_present= False
cleanup_returned= True
objects_at_cleanup= 0
objects_after_remote_commit= 1
late_bytes= b'private process-death data'
.
1 passed in 9.45s
```

探针 `C:/Users/82358/AppData/Local/Temp/test_domestic_upload_process_death_review.py`。这证明当前**应用协议**无法排除符合该时序的迟到对象；替身不是 MinIO 服务端，不能声称已在本项目实际 MinIO 版本复现。Go 的 [net/http 官方文档](https://pkg.go.dev/net/http#Request.Context) 说明连接关闭会取消请求上下文，但不提供已经启动的存储写入必定在锁释放前完成或撤销的应用级收据。须以实际 MinIO 故障注入验证，并设计跨进程死亡与远端 PUT 的确定性收敛/清理；只靠 OS 锁或瞬时列举不足以证明删后无残留。

### H3. 恢复写回旧台账后、写终态前再次中断，重试永久拒绝

**要求**：联合发布故障及重入须可恢复，独立发布和清理不得绕过门禁（`DEV-PLAN.md:16-20`）。

`scripts/release/intranet/joint_studio_release.py:175-182` 在 schema 未迁移时先写旧台账 `self.tool.save(old)`，再单独写 `rolled-back` 或 `cancelled`。若两次持久化之间中断，下一次进入 `recover` 时，台账已是 old，marker 仍是 `interrupted`/`deploying`；`joint_studio_release.py:167-174` 不接受这个可达组合并报错。与此同时 `joint_studio_marker.py:6-21` 与 `release_cli.py:30-33` 继续阻止普通发布；`stage.py:71-80`、`full_cleanup.py:12-16` 也受阻。

隔离 fixture 在真正 `Upgrade.recover` 完成旧台账写回之后、终态 marker 之前注入进程中断，恢复后重试，原始输出：

```text
phase_after_crash= interrupted
ledger_is_old= True
recovery_retry= Joint ledger changed during recovery
normal_release_guard= Resolve the pending domestic Studio migration first
.
1 passed in 5.34s
```

探针 `C:/Users/82358/AppData/Local/Temp/test_joint_rollback_reentry_review.py`；测试中的恢复运行时为替身，不表示实际服务被停止或重启。这里观察到的是发布/清理控制面被卡住，并未观察到生产业务中断或数据丢失。

## Stage 1 · 逐项对照与审查进度

| Spec 条目 | 已见证据及本轮结论 |
| --- | --- |
| 五入口、独立成品库、管理中心 Skills 菜单 | 静态部分核对：五个名称和路径见 `frontend/src/api/hengxin/domestic-workspaces.ts:3-8`，菜单见 `frontend/src/router/modules/index.ts:12-30`。未独立逐入口浏览器验收。 |
| 空白对话、无预设及自动发送 | 静态部分核对：`frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:15-22` 使用隐藏空引导参数、空输入绑定与手动发送。未逐项追踪所有预填和自动发送路径，不判完整通过。 |
| 本人多会话、创建/切换/重命名/删除，附件隔离 | 静态部分核对：`backend/app/modules/domestic_studio/conversation_service.py:29-47,70-105` 按 owner/workspace 查找，`conversation_deletion.py:14-60` 检查删除权限。上传进程死亡后远端迟到写存在 H2 未闭环；其他跨用户矩阵未完成。 |
| 消息真实姓名和北京时间，输入、附件、停止、连续对话 | 静态部分核对：`backend/app/modules/domestic_studio/queries.py:68-108` 输出 actor 和时间，`frontend/src/views/shared/studio/StudioTurns.vue:6-7,50-54` 格式化显示；`turn_service.py:40-116` 处理提交与停止。未独立验证真实身份、模型及全部交互。 |
| 未确认进程不得重生；部分保存后可只补收 | 静态部分核对：`backend/app/modules/domestic_studio/recovery.py:38-76` 在原节点验证进程及重新收取；`delivery_capture.py:20-60` 针对损坏副本逐项处理，`runner.py:64-82` 处理 partial。未独立完整重跑上轮损坏副本、进程组与大文件矩阵。 |
| 五个教程入口、真实待补充 | 静态部分核对：共用组件 `frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:3,29` 显示入口和“教程待补充”。未逐入口实测。 |
| 仅新品归档、国内共享副本、源会话仍私有、删除源后保留 | 静态部分核对：`backend/app/modules/domestic_studio/policy.py:12-30` 限制工作台，`archive_service.py:71-98,101-176` 规划并校验副本；`archive_router.py:21-64` 接入共享读取。H2 的源对象清理边界未通过，完整隔离、源删后归档和 ZIP 未独立重验。 |
| 成品库搜索、来源、详情、删除、下载及图片保护 | 静态部分核对：`backend/app/modules/domestic_studio/archive_queries.py:18-93` 和 `archive_router.py:36-97` 有对应接口；`frontend/src/views/hengxin/domestic-studio/library.vue:5-11` 为页面入口。角色、下载内容和图像保护未独立实测。 |
| 超管 Skill 上传、校验、差异更新、启停、删除、ZIP、五入口绑定且初始空 | 静态部分核对：`backend/app/modules/auth/permissions.py:5-8` 将管理权限限定超管；`management_router.py:26,82-163` 提供管理接口，`bindings.py:37-82`、`skill_state.py:29-60` 和 `skill_publication.py:85-118` 共享准入锁与绑定保护；`backend/migrations/versions/0033_domestic_studio_bindings.py:5-26` 建表不插绑定。未完成并发矩阵、实际完整文件夹与 ZIP 验收；未完成无额外版本管理的全量界面审查。 |
| 国内身份、持久执行、国内外隔离，原业务不受影响 | 静态部分核对：`backend/app/worker/tasks.py:47-51` 接国内任务，`backend/app/modules/domestic_studio/recovery_transport.py:5-13` 使用国内独立队列前缀；`scripts/release/intranet/domestic_studio_wiring.py:42-114` 构造独立挂载和 publisher。未独立验证真实服务、真实模型、旧国内业务及海外完整回归。 |
| 显式受保护模式、UID/GID、独立 Skill 根/UDS/锁 | 静态部分核对：`backend/app/modules/domestic_studio/protected.py:5-9`、`maintenance_lock.py:15-31`、`scripts/release/intranet/joint_studio_paths.py:31-50`、`joint_studio_verify.py:36-87` 有相关保护和安装后核验；本轮未以生产身份或真实 Docker 安装重测。 |
| 只读基线、排空、备份、迁移、前向恢复、台账及后续发布清理 | 不通过：H1、H3。部分实现见 `joint_studio_release.py:76-109,160-188`、`joint_studio_engine.py:32-74`、`joint_studio_state.py:37-66`、`release_cli.py:30-33`。未完成后续独立发布、GC 全路径审计。 |
| 已确认预览的视觉和交互、未授权功能漂移 | 尚未完成：本轮未在同视口渲染预览与正式页面，未做数值和截图对比，也未完整盘点全部新增页面、接口及表的漂移。不能依据本报告声明 UI 或 scope 通过。 |
| 构建、测试、独立两阶段审查、中文提交及生产验收 | 不通过：Stage 1 有 HIGH。下面仅列本 reviewer 的有限测试；未执行 Stage 2，未提交、未部署或作真实入口验收。 |

上表路径中 `backend/`、`frontend/` 均相对应用目录 `hengxin-smart-image/`。

## 其他观察 · MEDIUM

- **附件并发内存风险有待量化。** `backend/app/modules/domestic_studio/router.py:146-155` 接受最多 500,000,000 字节并调用 `backend/app/execution/bounded_read.py:19-31`；该函数先积累所有 1 MiB 块再 `join`，并非流式直传，合并时近两份内容同时驻留。本 reviewer 对 32 MiB 模拟异步流的独立 `tracemalloc` 输出如下；不能线性外推为实际生产 RSS 或断言一定 OOM：

```text
input_bytes=33554432 current_bytes=33554465 peak_bytes=67113377
```

  主 Agent 给出的只读现网基线为 domestic-api 未设置容器级内存限制，主机总内存 16,720,592,896 字节、当时 available 12,452,139,008 字节、Swap 4,294,963,200 字节；本 reviewer 未再连接生产，该时点可用量不代表永久容量。未验证真实 500 MB、多并发、图片解码和同机其他业务下的峰值。

## 本 reviewer 独立执行的有限验证

- 前端在 `hengxin-smart-image/frontend` 执行 `pnpm run typecheck`，退出码 0；原始输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.

> hengxin-smart-image-frontend@0.2.69 typecheck D:Work_Projecthengxin-smart-imagehengxin-smart-imagerontend
> vue-tsc --noEmit
```

- 本地 Python 对 `backend/app/modules/domestic_studio/` 和 `scripts/release/intranet/` 的 Python 文件逐个调用 `compile`（不生成字节码）；原始输出：`COMPILE_OK files=99`。这是语法检查，不是全项目构建。
- 现有发布工具测试 `test_joint_studio_release.py` 和 `test_joint_studio_engine.py`，Windows 本地运行原始输出：

```text
..............                                                           [100%]
14 passed in 1.52s
```

  这些测试未覆盖上述父进程死亡后子进程仍在迁移，亦未覆盖旧台账已写而终态 marker 未写的崩溃窗口。`test_joint_studio_release.py:46-83,96-145` 在 orchestration 测试中替换了迁移、服务恢复和 runtime 捕获，不构成实际 Docker/生产恢复证明。
- H1/H2/H3 的独立故障探针原始输出分别如上。真实 MinIO、大文件并发、生产安装、真实身份和收费模型未验证。

## Stage 2

**未执行。** 因 Stage 1 存在 HIGH，本轮没有系统完成代码质量、安全扫描、测试真实性全面审计及新页面与邻居基准页面的实际视觉对比；上述局部读取和测试不构成 Stage 2 通过。
