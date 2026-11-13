# 国内 AI 工作台恢复与隔离复审 · 2026-11-12

## 结论与范围

- **送审 candidateId：`eca27a61ce087eed4fe4d6952f3c6143ae76a8000cd4a156d8ca6327453ee029`。Stage 1：FAIL；Stage 2：未执行。** 不批准提交或部署。
- 范围为 Product-Spec.md:1-12 的国内五入口、Skill 绑定、本人会话及文件、新品归档和删除、结果补收、国内外隔离与原海外行为，以及上轮 `docs/reviews/DOMESTIC-STUDIO-CORE-20261112.md:13-69` 的五个 HIGH。审查包括 Git 未跟踪的新代码和测试。
- 审查开始时 `review-status` 的 `currentId` 与上述候选完全一致。审查期间主 Agent 修改了代码；本报告只针对送审候选，下面区分候选上实测、混合快照实测和静态核查。末尾记录差异；新快照不得套用本报告的任何通过结论。
- 隔离 PostgreSQL 为 `127.0.0.1:35439/hx_studio_test`，测试 fixture `backend/tests/test_domestic_studio_bindings_pg.py:18-42` 每例创建并删除随机 schema。Redis 为 `127.0.0.1:35440/15`，仅使用 `hx-review-unit:<随机 UUID>:` 测试键。对象存储为测试内存替身；测试文件和进程均由测试创建。不访问生产数据库、生产对象和收费模型。

## Stage 1 · HIGH

### 1. 单个损坏的冻结文件阻断其他文件保存及手动取回

Spec 要求原执行成功后，保留文字和已保存文件，并允许对尚存文件手动取回（`Product-Spec.md:7`）。候选 `backend/app/modules/domestic_studio/delivery_capture.py:31-32` 对所有已冻结结果执行 `list(snapshots.images(...))`；共享读取器在任一文件校验失败时抛出异常（`backend/app/overseas/studio/delivery_snapshot.py:95-114`、`backend/app/overseas/studio/delivery_snapshot_fs.py:137-145`）。`runner.py:64-81,139-145` 因异常将轮次留在 uncertain；`recovery_files.py:24-39,89-100` 则把非终态会话视为 busy，手动取回也被拒绝。

独立故障注入在两个真实冻结结果都写完后，将第一份副本改坏，保留第二份完整副本和两个工作原件。随后再次请求原节点只补收。原始输出：

```text
after_corruption_status= uncertain reply_present= True saved= 0
after_recovery_status= uncertain model_calls= 1 saved= 0
manual_recovery= {'items': [], 'busy': True}
```

这是有意注入的磁盘损坏，不声称正常写入必然损坏。实测表明另一份完整结果及尚存原件无法通过所测入口取回；必须逐文件隔离故障并保留可恢复状态。探针 `C:/Users/82358/AppData/Local/Temp/test_hx_recovery_review_probe.py::test_corrupt_one_frozen_result_blocks_all_receipt` 使用原候选启动。

### 2. 一人上传等待对象存储时，其他成员停止请求被全局权限锁阻塞

候选 `backend/app/modules/domestic_studio/file_service.py:20-34` 在 `lock_actor` 之后、事务提交之前执行 `store.put`。该调用取得的是所有国内成员共用的 PostgreSQL advisory transaction lock（`backend/app/modules/domestic_studio/conversation_service.py:18-27`；`backend/app/modules/auth/member_policy.py:8-13`）；其他成员停止请求同样先取得该锁（`backend/app/modules/domestic_studio/turn_service.py:91-96`）。单个附件可达 500 MB（`backend/app/overseas/upload_limits.py:2`）。

在随机 schema 中，让成员 A 的 `store.put` 暂停，成员 B 对已有排队轮次发出真实停止请求。第二连接设置 300 ms PostgreSQL 锁超时。原始输出：

```text
other_permission_lock_available= False
other_stop_sqlstate= 55P03
stop_after_upload= cancelled
```

这证明存储等待期间其他成员的停止会等待同一把锁；没有测量真实网络的持续时间。上轮归档慢 I/O 的全局锁虽在候选中拆分（`archive_service.py:179-226`），上传仍有同类阻塞。探针 `C:/Users/82358/AppData/Local/Temp/test_hx_recovery_review_probe.py::test_upload_blocks_other_user_stop` 使用原候选启动。

### 3. 上传事务断连后可在会话删除完成后写入残留对象

候选 `file_service.py:20-34` 依赖数据库权限锁和会话行锁覆盖对象写入；候选 `conversation_cleanup.py:82-105,121-165` 清查当时存在的对象并删除源会话；候选 `maintenance_lock.py:7-10` 的原生文件锁只由原生清理/恢复持有，上传 API 未持有。数据库连接在 `store.put` 完成前断开时，数据库锁消失，已经清查完成的对象清单无法包含稍后到达的写入。

独立故障注入：暂停上传写入、终止该测试事务的 PG 连接，完成会话删除，最后放开上传。原始输出：

```text
deletion_request= deleting
cleanup_status= deleted source_row_present= False
post_deletion_orphan_count= 1 orphan_bytes= b'private delayed bytes'
1 passed, 2 warnings in 8.43s
```

**快照边界：** 此探针运行时，上传仍为候选实现，但并发开发已修改 `conversation_cleanup.py` 和 `maintenance_lock.py`；故这次是混合快照，不能当作候选整体的原子测试。候选原文中上传没有持有原生清理锁，清理单独持有锁，上述竞态在原设计中成立。首次探针因隔离 schema 未创建 `Transcript` / `OutputFile` 辅助表而失败；补建测试表后得到以上结果。测试未使用真实 MinIO。需要针对修复后的同一快照复测跨进程、跨 UID、PG 断连及删后迟到写。

### 4. 结果收取有大额峰值分配和所有文件同时驻留内存

候选 `delivery_capture.py:31-32` 先把全部结果转为列表，`runner.py:64-81` 再逐项保存；候选 `delivery_snapshot_fs.py:75-92,105-110,137-145` 最多接受 100 个文件，每个最多 500,000,000 字节，且用 `stream.read(limit + 1)`。这不仅累积所有返回文件，还可能在读取小文件时按上限产生大额临时分配。

独立探针用原候选相同的共享 `snapshots.images()` 与 `list()`，读取三个 8 MiB 自建文件；开始时该共享模块仍匹配候选。Python `tracemalloc` 原始输出：

```text
result_count= 3
retained_payload_bytes= 25165824
traced_current_bytes= 25175123
traced_peak_bytes= 516801450
```

另在 WSL Linux 上对自建 8 MiB 临时文件执行 `read(500000001)`，输出 `8388608 (8389041, 500000346)`。这是 Python 分配跟踪值，不是生产 RSS、实机 OOM 或吞吐测量。候选允许的文件数与大小使结果收取内存随总量增长，且小文件也可能触发大额峰值，可能中断执行和补收。探针为 `C:/Users/82358/AppData/Local/Temp/hx_review_capture_memory.py`。

### 5. 国内真实 Skill 安装与联合发布接线尚未完成

候选工作台 Skill catalog/publisher 依赖国内独立根目录和套接字（`backend/app/modules/domestic_studio/management_router.py:53-74`）；`infra/compose.yaml:38-43,124-137` 的现有配置尚未提供完整国内 Skill publisher、socket 和只读挂载，且执行/删除服务在宿主机（`infra/hengxin-domestic-deletions.service:1-12`）。实施记录明确联合维护迁移、挂载和正式接线仍待完成（`docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:7-12,26-28`）。

因此未满足 Spec 的真实身份、执行、Skill 和可部署验收（`Product-Spec.md:10-12`）。本轮未修改生产，也未调用真实模型。不能据此批准提交、部署或宣称上线。

## Stage 1 · 原五项修复复核

| 上轮问题 | 本轮证据和状态 |
| --- | --- |
| Linux 组长退出后仍有后代 | **所测场景通过。** `backend/app/execution/process_group.py:6-25` 检查整个进程组；`verified_stop.py:10-36` 在剩余进程存在时不放行；`process.py:61-71` 在组未退出时不写退出回执。WSL 真实进程组探针输出 `Linux process-group verification passed`；其组长退出、子进程存活和仅清理测试自建进程组见 `backend/tests/process_group_linux_probe.py:13-64`。这不是完整 PID 命名空间或真实沙箱矩阵。 |
| 归档清单缺项与源删除 | **静态核对已补保护，未独立重跑完整竞态。** 候选 `archive_service.py:63-98` 对快照 seal、文件清单与引用集合逐项核验；`conversation_cleanup.py:42-53,128-153` 删除前核验每个副本；`archive_deletion.py:15-42` 和 `conversation_deletion.py:14-47` 检查删除回执。候选测试 `test_domestic_archive_pg.py:377-410` 包含缺行、错类型、篡改故障注入；本轮未在固定候选重跑全部用例，因此不将完整性和并发矩阵标为 PASS。 |
| 归档/源删除大 I/O 持有共享锁 | **部分修复，整体不通过。** 候选 `archive_service.py:179-226` 将复制 I/O 移到权限锁和 admission gate 之外；`conversation_cleanup.py:121-165` 主要锁删除回执。国内上传仍持有全局权限锁，见 HIGH 2。候选 `maintenance_lock.py:7-10` 还把不同会话的归档、恢复和清理放在同一文件锁；`retention/worker.py:129-141` 同一原生循环串行处理清理和恢复，遇慢对象存储时其他取回可能在 `recovery_transport.py:19-20,60-85` 的 25 秒等待窗口内超时。本项串行等待是代码分析，未单独计时真实存储。 |
| 只补收及手动取回入口 | **已接入口，故障路径不通过。** `DomesticWorkspace.vue:10,14,31` 显示“核实并收取结果”和“取回文件”；`backend/app/modules/domestic_studio/router.py:114-140` 注册相应路由，`recovery_files.py:24-81,113-180` 只枚举和保存本人原生文件。原候选损坏快照时仍无法取得其他文件，见 HIGH 1。 |
| 生产接线 | **未完成。** 见 HIGH 5。 |

## Stage 1 · Spec 逐条对照

| 需求 | 结论及证据 |
| --- | --- |
| 五入口、独立成品库、超管 Skills 菜单 | **代码已接入，部署未验证。** 五个名称和路径在 `frontend/src/api/hengxin/domestic-workspaces.ts:3-8`，菜单在 `frontend/src/router/modules/index.ts:13-30`。生产接线见 HIGH 5。 |
| 空白对话、无预填和自动发送 | **代码局部核对。** `frontend/src/views/shared/studio/use-studio.ts:15,153-159` 输入初始为空且发送由动作触发；`DomesticWorkspace.vue:18-22` 为输入区与未绑定提示。未在固定候选做五入口真实浏览器全状态对照。 |
| 会话创建、切换、重命名、删除；创建者隔离 | **部分核对。** `conversation_service.py:29-47,70-105` 以 owner/workspace 查找并处理创建和重命名；`conversation_deletion.py:14-47` 处理删除；附件读取过滤 owner（候选 `file_service.py:37-59`）。断连删后迟到写不通过，见 HIGH 3；真实钉钉、多用户全链路未测。 |
| 真实姓名和北京时间、连续消息、附件、停止、异常 | **部分核对。** `queries.py:74-98` 组织姓名与时间；`frontend/src/views/shared/studio/StudioTurns.vue:6,50-54` 展示姓名及北京时间；附件和停止分别见 `DomesticWorkspace.vue:21-22` 与 `turn_service.py:91-116`。上传会阻塞其他用户停止，见 HIGH 2；真实模型及身份未测。 |
| 原进程不明不重生；保存失败仅补收 | **不通过。** 不明进程保守核验见 `recovery.py:25-76`；结果与手动恢复故障见 HIGH 1、4。真实 Redis 队列仅做下述限定范围的传输探针。 |
| 各入口教程入口且不编造 | **代码已接入，未逐入口实测。** `DomesticWorkspace.vue:3,29` 显示入口及“教程待补充”；五入口共用组件见 `workspace.vue:1-9`。 |
| 仅新品归档；源会话私有、副本国内成员共享、源删后独立 | **部分核对。** `policy.py:12-30` 限两个入口；`archive_router.py:36-69` 提供授权用户共享归档路由；`archive_service.py:33-52,101-176` 建立独立清单。缺行防护和源删除按上一表处理；新增断连残留见 HIGH 3；真实对象存储和全部并发组合未测。 |
| 成品库搜索、来源、详情、删除、下载及图片保护 | **代码已接入，未独立浏览器验证。** `archive_queries.py:18-93` 支持搜索、来源和详情；`archive_router.py:36-105` 提供读取、管理员删除及下载；`frontend/src/views/hengxin/domestic-studio/library.vue:5-11,43-51` 接入页面。未做真实图片保护、ZIP 大文件及角色矩阵验收。 |
| 超管 Skill 文件夹上传、校验、更新、启停、删除、ZIP、固定绑定 | **部分核对。** `management_router.py:24-27,77-157` 限管理员并提供管理接口；`bindings.py:37-82` 和 `skill_state.py:28-60` 限固定绑定、阻止停用绑定中 Skill；`skill_publication.py:84-106` 限删除；`0033_domestic_studio_bindings.py:11-26` 无初始绑定。此前 Skills 审查报告 `docs/reviews/DOMESTIC-STUDIO-SKILLS-R9-20261112.md` 为 FAIL；本轮未完整重审其所有交互与视觉，不继承其通过结论。 |
| 国内外数据/队列隔离、海外和旧国内功能兼容 | **部分验证。** 国内恢复队列前缀见候选 `domestic_studio/recovery_transport.py:5-13`，海外前缀和默认 handler 见 `overseas/studio/recovery_transport.py:17-18,60-70,91-130`。下述独立 Redis 测试仅证明参数化传输与断连返回；未实测两套真实服务、旧海外全量行为或正式身份。 |
| UI 对照已确认预览、不加未授权功能 | **未完成，不判通过。** 已确认预览为 `frontend/preview-domestic-studio/`，实际页面为 `frontend/src/views/hengxin/domestic-studio/`；本轮未在同视口打开固定候选和预览逐项比对，且完整 API/页面/表的 Spec 漂移盘点未完成。候选没有通过本次 UI 与漂移验收。 |
| 构建、测试、独立双阶段审查、中文提交和部署 | **不通过。** 本报告存在 HIGH，仅做下方限定的局部测试与语法编译；Stage 2、完整构建、生产发布和真实入口验收未执行。 |

## 独立执行输出

两个候选故障注入合计原始结果：

```text
other_permission_lock_available= False
other_stop_sqlstate= 55P03
stop_after_upload= cancelled
.after_corruption_status= uncertain reply_present= True saved= 0
after_recovery_status= uncertain model_calls= 1 saved= 0
manual_recovery= {'items': [], 'busy': True}
.
2 passed, 2 warnings in 11.12s
```

进程组单元测试及子集语法检查（这些文件在审查时未变化；Windows 单元测试跳过真实 Linux 用例，真实 Linux 探针另见上表）：

```text
....s                                                                    [100%]
4 passed, 1 skipped in 0.39s
pytest_exit=0
compileall_exit=0
```

`compileall` 仅覆盖 `app/execution/process.py`、`process_group.py`、`verified_stop.py` 和 `app/overseas/studio/recovery_transport.py`；它不是全项目构建。

隔离 Redis 的随机专属前缀上，采用真实 Redis 连接及测试 handler；内容仅为测试 UUID 和元数据，测试哨兵不属于正式海外或国内队列：

```text
queued_fields= ['actor_id', 'conversation_id', 'expires_at', 'files', 'id', 'operation', 'task_id']
payload_matches_test_ids= True
consumed= True
result= {'actor': '7543f761-bdcb-41df-87d3-e79efe15c9e2', 'items': []}
test_sentinel= intact
disconnected_status= 503 seconds= 0.22
```

不据此声称完成真实国内/海外消费者、真实权限、写入中 Redis 断连或生产拓扑的端到端验收。

## Stage 2

**未执行。** Stage 1 存在 HIGH，因此未进行系统质量审查、安全扫描、测试真实性全面审查及实际邻居页面视觉对比。未调用 `review-approve`，未写 clean、未修复业务代码、未提交或部署。

## 报告写入时的受控快照变化

以下由 harness 的候选文件哈希与写入时工作树比较得到。未跟踪受控文件也纳入；报告 Markdown 不属于受控代码快照。此列表之后若仍有编辑，应由主 Agent 重新固定快照并再次比较，不能用本报告批准后续版本。

- 快照时间：2026-11-12T19:35:07+08:00
- 当前 currentId：`f0eea6c3c2a62f435fe26d45264b236dea85786bdfae5b8233744e87f4867c40`
- 相对 candidate 的变化文件：

  - `=12.1,`
  - `hengxin-smart-image/backend/app/execution/bounded_read.py`
  - `hengxin-smart-image/backend/app/execution/diagnostics.py`
  - `hengxin-smart-image/backend/app/modules/domestic_studio/archive_deletion.py`
  - `hengxin-smart-image/backend/app/modules/domestic_studio/archive_service.py`
  - `hengxin-smart-image/backend/app/modules/domestic_studio/conversation_cleanup.py`
  - `hengxin-smart-image/backend/app/modules/domestic_studio/delivery_capture.py`
  - `hengxin-smart-image/backend/app/modules/domestic_studio/file_service.py`
  - `hengxin-smart-image/backend/app/modules/domestic_studio/maintenance_lock.py`
  - `hengxin-smart-image/backend/app/modules/domestic_studio/output_store.py`
  - `hengxin-smart-image/backend/app/modules/domestic_studio/recovery_files.py`
  - `hengxin-smart-image/backend/app/modules/domestic_studio/recovery_transport.py`
  - `hengxin-smart-image/backend/app/modules/domestic_studio/router.py`
  - `hengxin-smart-image/backend/app/modules/domestic_studio/runner.py`
  - `hengxin-smart-image/backend/app/overseas/studio/delivery_snapshot_fs.py`
  - `hengxin-smart-image/backend/app/overseas/studio/files.py`
  - `hengxin-smart-image/backend/app/overseas/studio/recovery_listing.py`
  - `hengxin-smart-image/backend/tests/test_bounded_output_read.py`
  - `hengxin-smart-image/backend/tests/test_domestic_archive_pg.py`
  - `hengxin-smart-image/backend/tests/test_domestic_delivery_capture.py`
  - `hengxin-smart-image/backend/tests/test_domestic_execution_workspace_pg.py`
  - `hengxin-smart-image/backend/tests/test_domestic_files_pg.py`
  - `hengxin-smart-image/backend/tests/test_domestic_output_store_pg.py`
  - `hengxin-smart-image/backend/tests/test_domestic_turns_pg.py`
