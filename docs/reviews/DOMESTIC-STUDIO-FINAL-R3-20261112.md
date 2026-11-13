# 国内 AI 工作台及联合发布独立审查 R3 · 2026-11-12

## 审查结论、候选与范围

- **candidateId：`85375fcfe297193c78923b15daaf2bfef04045ed0aaabf1837de34b5f43187e4`。Stage 1：FAIL；Stage 2：未执行。** 下述 H1 是已独立复现的功能/资源要求不符；不能为该候选登记两阶段 PASS。
- 审查范围：`Product-Spec.md:1-13` 的五个国内工作台、身份、会话、附件、收取、Skill 管理、归档、国内外隔离与部署；`DEV-PLAN.md:1-24` 的联合发布、迁移和恢复；`Design-Brief.md:1-3` 与 `hengxin-smart-image/frontend/preview-domestic-studio/` 确认预览。本轮优先复核上一轮的远端迟到写、迁移恢复和本轮新增事务；发现 HIGH 后停止，不把尚未完成的项目标成通过。
- 开始时及报告前独立执行 `python .codex/hooks/harness.py review-status`，均得到 `currentId` 为上述 candidateId、`approved:false`。本轮只读业务源码，报告和 `output/domestic-studio-r3-memory-probe.py`、`output/domestic-studio-r3-other-memory-probe.py` 不属于受控代码快照；未修改生产、未提交、未写 clean 或 review-approve。后续代码更改必须重新固定候选并从 Stage 1 复审。
- 数据库/对象故障测试仅使用本机隔离 `127.0.0.1:35439/hx_studio_test` 的随机 schema 与 `127.0.0.1:35441` 的随机 MinIO 测试 bucket；内存探针使用临时目录与合成数据流。未访问生产数据，未调用真实模型。

## Stage 1 · HIGH

### H1：发送或恢复工作区附件时，真实执行链同时持有多份完整附件

**Spec 原文**：`Product-Spec.md:8` 要求“大附件以有界方式处理，避免按附件上限重复占用内存”。正式发送会经过该路径，并非只处理上传或归档副本。

**实际调用前提与链路**：用户在当前会话上传两个不同的合法大附件并发送，后端 `turn_service.py:61-76` 将附件作为 `inputs` 冻结；单文件上限为 500,000,000 字节（`backend/app/overseas/upload_limits.py:2`），发送模型允许多个附件（`backend/app/overseas/studio/schemas.py:40-45`）。新会话首次准备或本地原件不在时，国内 worker `backend/app/modules/domestic_studio/execution_workspace.py:59-60` 将对象存储读取回调传给 `backend/app/overseas/studio/context_workspace.py:99`；`context_assets.py:89-102` 调用 `read_source` 获得整份 `bytes`，校验后写文件，进入下一次循环前仍持有上一份 `content`。`backend/app/overseas/studio/files.py:80-85` 用 `read_bounded` 读取；`backend/app/execution/bounded_read.py:4-16` 把全部分块保存在列表中，再 `b''.join(chunks)` 创建整份副本。因此下一份附件读取完成拼接时，旧附件、当前分块、当前完整结果可同时驻留。

**独立复现**：`output/domestic-studio-r3-memory-probe.py` 直接调用真实 `context_assets.restore` 和 `files.read`，只用按请求即时产生内容的本地替身流，构造两份不同 ID 的 64 MiB 文件、真实 SHA-256 和空本地目标，使用真实文件写入及 `tracemalloc`；不模拟数据库或模型进程。WSL 下以 `PYTHONPATH=.` 从 backend 执行该文件，原始输出（WSL 启动提示省略）：

```text
attachments=2 size_each_mib=64 tracemalloc_peak_mib=192.0 restored_files=2
```

这证明测得的 Python 堆峰值为单附件大小的 3 倍。按当前实现与上限线性推算，两份各 500,000,000 字节的文件会形成约 1.4 GiB 的 Python 分配峰值，尚未计算进程其他内存或并发；**该数值是推算，没有在生产或实际 500 MB 文件上观测到 OOM**。对象读错误或 worker 内存不足可能使生成无法正常开始，是否会被系统杀死取决于实际内存和并发。本探针的流是本地替身，未测网络延迟或 MinIO 内部分配，但直接走了与真实 MinIO 返回流相同的读取、校验及工作区写入函数。

**为什么已有测试未覆盖**：`backend/tests/test_domestic_archive_large_real_minio_pg.py:26-50` 的 128 MiB 用例只测归档复制 `archive_service.complete`，并不调用工作区附件准备；`backend/tests/test_bounded_output_read.py:12-23` 只用 8 MiB 检查不预分配整个 500 MB 上限，其 40 MiB 阈值允许多个 8 MiB 副本。自动收取冻结文件的 `backend/app/modules/domestic_studio/delivery_capture.py:48-60` → `backend/app/overseas/studio/delivery_snapshot_fs.py:103-108,135-136` 也调用整文件读取；该路径及海外其他调用方尚未独立测量。应检查共享调用方，修复时维持校验、原子写入、越权及失败恢复语义，再对真实可达的多大附件执行路径做内存验证。


**同类路径补充实测**：`output/domestic-studio-r3-other-memory-probe.py` 以 64 MiB 本地文件直接调用 `backend/app/overseas/studio/recovery_listing.py:159-170` 的真实 `read`，以及国内 `backend/app/modules/domestic_studio/archive_router.py:70-84` 的真实 ZIP 处理。取回路径实际可达前提是原执行已核实停止、用户选择本人会话的工作文件或冻结副本：`recovery_files.py:28-40,120-127`；ZIP 实际可达前提是已有已归档的成品图片、成员请求下载。归档 ZIP 只含 `picture`，并不打包用户上传附件；图片是应用 `validate_stream` 接受的 1×1 PNG，尾随测试字节扩到 64 MiB。数据库归档查询和对象存储为替身，本地校验、读取、压缩包生成与流式消费均是真实代码。原始输出：

```text
recovery_input_mib=64 recovered_mib=64 tracemalloc_peak_mib=128.1
archive_png_accepted_as=image/png png_input_mib=64 tracemalloc_peak_mib=128.1
archive_zip_bytes=67108976
```

两处均测得约两份文件的 Python 堆峰值，尚未测试实际 500 MB、真实 MinIO、浏览器及并发。ZIP 的成品图片不直接等同 Spec 所说上传附件，列为同类资源风险；取回路径是否同时受上述不确定写及大文件要求约束，应在修复时覆盖。不可把此探针当作权限、归档完整性或整个端到端测试。

## Stage 1 · 逐项核查与未验证边界

除 H1 外，下表仅是本轮实际已见代码或独立测试，不将静态存在等同完整验收；代码路径中 `backend/`、`frontend/` 均相对 `hengxin-smart-image/`。

| Spec 条目 | 本轮证据及结论 |
| --- | --- |
| 五入口、新品/替换分组、成品库一级、超管 Skills 二级 | 部分核查：路由及角色在 `frontend/src/router/modules/index.ts:12-30`，工作台配置在 `frontend/src/api/hengxin/domestic-workspaces.ts:3-8`；未独立完成五入口浏览器全流程。 |
| 空白对话、无预设提示词/自动发送、教程待补充 | 部分核查：`frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:17-29` 隐藏空引导并手动发送，教程为空态；未逐入口逐状态对照确认预览。 |
| 私有多会话、切换/重命名/删除、十会话与空会话 | 部分核查：`backend/app/modules/domestic_studio/conversation_service.py:29-47,70-106` 按拥有者和工作台读取并限制创建，`conversation_deletion.py:14-60` 请求删除；限额也见确认预览 `frontend/preview-domestic-studio/SessionPanel.vue:3-5`。未完成跨用户全部 HTTP 矩阵。 |
| 实名与北京时间、输入/附件/连续对话、停止和异常 | 部分核查：`backend/app/modules/domestic_studio/queries.py:68-105` 返回真实用户及时间，`turn_service.py:40-116` 接发送/停止；`frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:19-24` 接入消息和附件。大附件执行准备不通过，见 H1；真实模型、真实身份和全部 UI 交互未验证。 |
| 执行状态不明不重生、确认成功部分文件可手动取回 | 部分核查：`backend/app/modules/domestic_studio/recovery.py:38-76` 要求原节点和进程证据，`runner.py:64-82` 保留 partial；`recovery_files.py:188-201` 逐项取回。未完整重跑进程组、损坏副本和所有恢复矩阵；取回路径的大文件内存未测。 |
| 未确认写入不重复、不得提前删除；大附件有界 | **不通过**：H1。上传/输出/归档意图分别见 `file_service.py:43-69`、`output_store.py:26-59`、`archive_service.py:203-225`，清理检查见 `conversation_cleanup.py:81-99` 和 `output_intents.py:35-62`；下述真实 MinIO 定向测试覆盖了三种迟到结果、附件分片完成迟到及 128 MiB 归档复制，不覆盖所有网络故障/分片时序。 |
| 仅新品归档、产品替换服务端拒绝、国内共享副本、源会话私有 | 部分核查：`backend/app/modules/domestic_studio/policy.py:12-30` 限制归档入口，`archive_service.py:101-176` 固定副本及对话，`archive_router.py:21-32`、`archive_queries.py:10-23` 接入共享读取；未独立完成全角色和全部删除竞态。 |
| 成品库按产品名查询/来源，详情、删除、下载和图片保护 | 部分核查：`archive_queries.py:26-93`、`archive_router.py:36-97` 与 `frontend/src/views/hengxin/domestic-studio/library.vue:2-16` 对应功能。浏览器下载、所有角色及图像保护未独立实测。 |
| 超管 Skill 文件夹校验、同名差异更新、启停/删除、ZIP，无版本管理 | 部分核查：`backend/app/modules/auth/permissions.py:5-8` 将系统管理限制超管；`management_router.py:24-28,77-163` 有对应 API，`skill_publication.py:38-118` 执行发布和保护。未独立重跑整个 Skill 上传/下载及交互矩阵，也未完成漂移盘点。 |
| 五个空绑定、服务端固定绑定、未配置及停用拒绝、在途冻结 | 部分核查：`backend/migrations/versions/0033_domestic_studio_bindings.py:11-26` 不插入绑定；`bindings.py:37-82`、`skill_state.py:29-60` 和 `turn_service.py:40-77` 锁定、检查并冻结。未独立完成所有并发及 UI 路径。 |
| 国内外身份、数据库、对象、队列隔离和既有功能 | 部分核查：`backend/app/modules/domestic_studio/router.py:28-29` 使用国内权限，`recovery_transport.py:6-14` 使用独立前缀，`scripts/release/intranet/domestic_studio_wiring.py:43-114` 设置新服务。未完整实测生产身份、容器隔离、所有海外回归或真实模型。 |
| 0032→0043、排空/备份、迁移中进程与数据库锁、旧台账中断重入、前向恢复 | 部分核查：`scripts/release/intranet/joint_studio_engine.py:33-69` 包含备份及继承进程锁，`joint_studio_fence.py:26-62` 包含进程锁和数据库屏障，`joint_studio_release.py:160-198` 处理旧台账与前向恢复；`backend/migrations/versions/0038_domestic_studio_turns.py:20-58` 包含新意图及附件状态。未独立执行本候选完整故障矩阵或安装测试，不能继承旧候选结论。 |
| 安装身份/可恢复发布及现有工具实际调用 | 未完成：`output/intranet-independent-release/install_tools.py:12-19,35-43` 从当前工作树构造版本目录并写 manifest；`scripts/release/intranet/joint_studio_release.py:204-223` 在主机/root 与发布锁下运行。该安装器在快照外，其内容和最终安装物仍须单独固定、核验，不能由本次代码候选隐含批准。未在真实 Docker 或生产执行安装/激活。 |
| 预览同视口视觉、引导真实性、无未经授权功能 | 未完成：本轮未对正式页面与确认预览做同视口数值和实际交互对照，也未完整盘点新增 API/页面，不能断言匹配或无漂移。 |
| 构建、测试、独立两阶段、提交及正式部署 | 不通过：本候选 Stage 1 有 H1；本轮只做下述有限验证，未提交、部署或正式入口验收。主 Agent 提供的其他测试数字非本 reviewer 的独立重跑。 |

## 独立测试与编译原始输出

在 `backend/` 以隔离测试 PG、MinIO 和 `TEST_DOMESTIC_MINIO_LARGE=1` 执行 `test_domestic_late_outputs_real_minio_pg.py`、`test_domestic_multipart_real_minio_pg.py`、`test_domestic_archive_large_real_minio_pg.py`。首次未配置子进程 `PYTHONPATH`，三条迟到输出测试和大文件归档通过，分片子进程导入失败。原始结果关键行：

```text
E   ModuleNotFoundError: No module named 'app'
1 failed, 4 passed, 1 warning in 28.71s
```

设置 `PYTHONPATH=.:tests` 后单独重跑分片用例，原始汇总：

```text
.                                                                        [100%]
=============================== warnings summary ===============================
../../../../../../tmp/hengxin-domestic-studio-python/lib/python3.14/site-packages/fastapi/testclient.py:1
  /tmp/hengxin-domestic-studio-python/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1 passed, 1 warning in 9.43s
```

因此这五个定向用例分别通过，但不是一次完整五项通过的输出；首次失败由 reviewer 的启动环境造成，不报告为产品缺陷。测试替身及延迟转发的覆盖边界见相应用例，不外推到所有故障。隔离 MinIO 测试会自行清理随机 bucket；未对生产存储操作。

在 `frontend/` 执行 `pnpm run typecheck`，退出码 0，原始输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.

> hengxin-smart-image-frontend@0.2.69 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

这是类型检查，不是生产构建。本 reviewer 本轮未独立重跑全量前后端/发布套件、真实部署身份或真实生图。

## Stage 2

**未执行。** Stage 1 有 HIGH；未系统执行代码质量、安全、测试真实性全面审查，也未打开邻居基准页与正式页做视觉对比。修复后重新固定候选，从 Stage 1 完整复审。
