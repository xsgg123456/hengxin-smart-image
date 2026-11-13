# 国内 AI 工作台及联合发布独立复审 R2 · 2026-11-12

## 结论与审查边界

- **candidateId：`8a15c798122abfaad9fbd2b8f5de91a3ab2318c99f0205b03f819a5a979c706f`。Stage 1：FAIL；Stage 2：未执行。** 两处 HIGH 均有独立故障注入证据。不得登记本候选为两阶段 PASS 或据此提交、部署。
- 审查范围：`Product-Spec.md:1-12` 的五个国内工作台、会话、附件、执行结果、恢复、成品归档与删除、Skill、国内外隔离；`DEV-PLAN.md:1-22` 的联合发布及恢复；`Design-Brief.md:1-3` 与确认预览 `hengxin-smart-image/frontend/preview-domestic-studio/`。重点核查上轮的迁移进程/数据库事务、旧台账重入和远端迟到写，及同类归档、输出写入路径。
- 审查开始及写报告前，`python .codex/hooks/harness.py review-status` 的 `currentId` 均等于上述编号，`approved` 为 `false`。本 reviewer 不改业务代码、不批准、不提交、不连接生产；本 Markdown 报告不属于受控代码快照。
- 两个新增故障探针均使用本机隔离 PostgreSQL `127.0.0.1:35439/hx_studio_test`、独立随机测试 schema、由现网版本二进制启动的独立本机 MinIO `127.0.0.1:35441` 和随机新建测试 bucket；通过 MinIO Python SDK 7.2.20 的真实 `put_object` 写入。延迟代理先收完整 PUT，请求超时后再把**原签名请求**转发给该真实 MinIO。仅测试数据；未调用模型、未写生产数据库或存储。测试结束清理自身随机 schema、bucket 和对象。
- 为隔离收图/删除协议，输出探针替换交付捕获与 CLI 进程组检查，模拟已经退出的原 CLI；真实执行 `runner.deliver`、`output_store.save`、数据库事务、会话删除请求和原生清理。归档探针走真实 native 归档 handler、复制、重试及成品删除。两者不是模型端到端或生产部署验收。

## Stage 1 · HIGH

### H1. 生成结果写入超时后，会话可先报告已删除，迟到对象随后出现

**需求**：会话删除需清理源资料；当远端写入结果尚不能确认时保留会话和写入凭据，不显示删除成功（`Product-Spec.md:6-9`）。

**实际调用链**：`hengxin-smart-image/backend/app/modules/domestic_studio/output_store.py:24-41` 在数据库只验证执行权，随后不持久化单次写入凭据就执行 `store.put`；仅返回并校验后才在 `output_store.py:42-55` 写 `Picture`/`OutputFile`。`runner.py:66-83` 捕获该写入异常后把任务置为终态 `partial`。`conversation_deletion.py:30-46` 允许终态任务发起删除；`conversation_cleanup.py:81-107,142-170` 只对 `Upload.status == 'uploading'` 核实未确认写入，输出依据已提交的 `Picture`/`OutputFile` 和当时前缀列举生成清单，然后删除会话并持久记录 `deleted`。旧输出 PUT 若已被远端代理接收但尚未提交，对象不在当时的清单，之后仍可写入。

**独立实测原始输出**：

```text
OUTPUT timeout_job=partial source_receipt=deleted source_row_present=False objects_before_late= 0 objects_after_late= 1 remote_status= 200
```

观察到清理成功且会话行消失以后，真实隔离 MinIO 又出现 1 个对应输出对象。这证明源删除成功不代表相关远端写入已终结或资源已清理；探针未证明该私有对象能被其他用户通过应用读取。`recovery_files.py:113-117,139-160` 的手动取回也在数据库登记前写确定性输出 key，仅用会话 OS 锁保护本地执行；它是否有相同超时/进程退出窗口，本轮仅静态发现、未单独实测，修复时须连同此写入入口覆盖。

### H2. 归档复制超时后重试同一 key，删除成品后旧 PUT 可迟到

**需求**：成品库须支持真实删除和独立保存；中断后的写入和清理须有可验证的结果（`Product-Spec.md:7-9`）。

**实际调用链**：`archive_service.py:37-50` 为归档文件构造确定性对象 key；`archive_router.py:25-31` 先提交清单，再由 `recovery_transport.py:17-34` 在按会话 OS 锁下请求 native 复制。`archive_service.py:179-208,226-240` 在持有数据库事务时 PUT；请求超时后状态转 `copy_failed`，重试复用同一 key 并可校验、标为 `ready`（`archive_service.py:209-225`）。此前超时的 PUT 仍可能在远端执行；文件当前已存在、重试完成或本地 OS 锁释放均不能证明旧 PUT 已结束。`archive_deletion.py:65-95` 删除当前对象后删除行并记 `deleted`，没有登记或核实此旧写入。

**独立实测原始输出**：

```text
ARCHIVE timeout_status=copy_failed retry=ready archive_receipt=deleted archive_row_present=False objects_before_late= 0 objects_after_late= 1 remote_status= 200
```

该序列真实执行归档首次失败、重试为 ready、管理员删除及 native 清理；当删除凭据为 `deleted`、归档记录已消失时，代理才将第一次 PUT 转发给隔离 MinIO，服务返回 200 且归档对象重新出现。单次核验重试后的对象，不能证明同 key 没有更早的未决写入。

## Stage 1 · 逐条对照及进度

以下“部分”只表示所列静态证据已核对，不等于端到端通过；发生 HIGH 后按要求停止，未将没有测试的行为标为完整。

| 需求条目 | 状态与证据 / 未核范围 |
| --- | --- |
| 新品生成两个入口、产品替换三个入口、独立成品库 | 部分：名称和路径见 `hengxin-smart-image/frontend/src/api/hengxin/domestic-workspaces.ts:3-8`，一级菜单见 `frontend/src/router/modules/index.ts:12-21`。本轮未逐入口浏览器实测。 |
| 五入口直接进工作台、空白、无欢迎卡片/示例/预填/自动发送 | 部分：`frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:15-22` 使用空对话及输入；本轮未完整追踪各入口的所有挂载与自动发送路径，也未实际渲染。 |
| 真实姓名和北京时间、消息左右排列 | 部分：`backend/app/modules/domestic_studio/queries.py:68-95` 提供 actor、时间及回复；`frontend/src/views/hengxin/domestic-studio/library.vue:11` 以姓名/时间渲染归档对话。实际登录身份、全工作台视觉和时区边界未独立实测。 |
| 输入、附件、连续对话、停止、错误处理 | 部分：`backend/app/modules/domestic_studio/router.py:144-157` 解析上传；`turn_service.py:42-80,91-116` 创建/停止轮次；真实模型、全部错误及交互未验证。附件迟到写防护的正向代码见下行。 |
| 附件中断时保存凭据，未确认不假称删除；大附件有界上传 | 部分：`file_service.py:29-72` 先提交唯一 `uploading` 行、流式校验和存储，`conversation_cleanup.py:81-90` 对未确认行核验，`queries.py:105-107` 只列 `ready`。主 Agent 报告的 500,000,000 字节真实 MinIO 测试及上传迟到 PUT 测试不是本 reviewer 重跑；本轮两个新探针针对输出及归档，不构成附件全路径通过。 |
| 多会话创建、切换、重命名、删除；同入口/用户隔离 | 部分：`conversation_service.py:29-44,70-109` 按 owner/workspace 限定；`conversation_deletion.py:14-46` 检查所有权及终态。输出远端迟到造成删除不实，见 H1；完整跨用户矩阵和逐项 UI 本轮未测。 |
| 部分收图保留结果、取回原件、不重新调用模型；未核实进程不自动重生 | 部分：`runner.py:66-83` 保留 partial；`recovery.py:39-75` 对 uncertain 原节点核实；`recovery_files.py:89-100,165-178` 支持可用文件选择/取回。实际模型与全部进程故障场景未独立复验，收图写入存在 H1。 |
| 五个教程入口，正式内容缺失时显示待补充 | 部分：共用工作台 `DomesticWorkspace.vue:3,29` 有教程按钮和“教程待补充”；未逐入口实测。 |
| 只有两个新品入口归档；产品替换服务端拒绝 | 部分：`policy.py:12-30` 限定归档工作台，`archive_service.py:101-104` 服务端调用；`DomesticWorkspace.vue:14,64` 对新品显示入口。未逐入口发送实际绕过请求。 |
| 归档独立复制、国内成员可读、源会话仍私有、源删除不破坏归档 | 部分：`archive_service.py:37-50,101-176` 规划副本；`conversation_cleanup.py:44-57` 验证独立副本；`file_service.py:75-81` 限定源文件所有者。完整跨成员 HTTP/源删后下载本轮未独立重测；迟到写和成品删除不实见 H2。 |
| 成品库产品名搜索、来源、详情、下载、删除、图片保护 | 部分：`archive_queries.py:17-47,79-93`、`archive_router.py:36-67,70-97` 和 `frontend/src/views/hengxin/domestic-studio/library.vue:4-11` 提供相关入口；删除有 H2；本轮未实际验收所有权限、ZIP 和图片保护。 |
| 仅超管的 Skills 管理；目录上传校验、同名差异更新、启停、删除、ZIP；无版本管理和在线编辑器 | 部分：`management_router.py:82-160` 有传输、目录、启停及绑定接口，`skill_publication.py:20-28,85-118` 检查超管和绑定保护；未独立完成所有 UI、ZIP 字节、撤权/并发和无额外界面盘点。状态字段 `version` 的存在本身不足以证明有用户可见版本管理。 |
| 五入口固定绑定、未绑定禁发、服务端防绕过、冻结已请求 Skill、初始留空 | 部分：`policy.py:33-51` 拒绝请求自带 Skill，`bindings.py:30-82` 保存/冻结并保护绑定，`turn_service.py:42-80` 写入轮次；`backend/migrations/versions/0033_domestic_studio_bindings.py:5-26` 建表无初始绑定。本轮未独立完整重跑并发和绕过测试。 |
| 国内外身份、库、存储、队列隔离，兼容旧国内 API 和海外 | 部分：`recovery_transport.py:4-14` 使用国内队列前缀；`scripts/release/intranet/domestic_studio_wiring.py:42-104` 配置国内独立挂载及 publisher。未连接生产或执行完整跨业务回归，未据此断言隔离或旧功能全部通过。 |
| 显式受保护模式、UID 10001 / 1001、共享 GID 986、目录/socket | 部分：`domestic_studio_wiring.py:12-29,42-104` 配置路径、组和 protected；`joint_studio_verify.py:36-75` 检查安装；本轮未做实际 Docker 安装和真实身份复测。 |
| 迁移中父进程死亡、子进程/DB 事务结束前不得恢复旧代码 | 部分：`joint_studio_engine.py:33-52` 让备份和 Alembic 继承 fence fd，`joint_studio_fence.py:25-60` 保持 flock 并等待事务级 advisory lock；`backend/migrations/env.py:39-47` 在迁移事务内获取同锁，`joint_studio_release.py:160-175` 持锁等待后再读取 schema。调用链静态核查改善了上轮 H1；本轮未自行重跑 Linux UID、真实 PG 故障测试，不宣称完整通过。 |
| 旧台账已写而终态 marker 未写的重入 | 部分：`joint_studio_release.py:176-191` 识别已恢复旧台账、旧 schema 且有回滚证据时再次核对运行态并补终态；尚未独立运行本候选故障测试。 |
| 备份、排空、前向恢复、台账与后续独立发布/GC | 部分：`joint_studio_engine.py:16-30,55-77` 核验备份和 schema，`joint_studio_release.py:193-198` 选择前向恢复；未完成全部发布/清理路径、真实 Docker 身份及故障矩阵审查。 |
| 确认预览视觉与交互，及额外功能/页面/接口漂移 | 未完成：已读取 `Design-Brief.md:1-3` 和预览 README；未对正式页和预览做同视口渲染、数值对照，亦未完整盘点新增页面/API/表。不得据此声称 UI 或 scope 通过。 |
| 构建、完整测试、审查、中文提交、真实部署及正式入口验收 | 不通过：本候选 Stage 1 有 H1、H2；本 reviewer 仅做下面的有限探针和类型检查，未提交、部署或验收真实入口。 |

表内 `backend/`、`frontend/` 简写均相对于 `hengxin-smart-image/`。既有实现如无明确验证状态，不作通过结论。

## 独立验证原始输出及复现材料

故障探针：`C:/Users/82358/AppData/Local/Temp/test_domestic_review_r2_late_writes.py`。在 `hengxin-smart-image/backend` 用该目录 `.venv/Scripts/python.exe -m pytest -q -s <探针路径> --disable-warnings` 运行；需将 `PYTHONPATH` 指向该 backend 和 `backend/tests`，并设置 `TEST_DOMESTIC_STUDIO_DATABASE_URL` 为上述隔离 `*_test` PostgreSQL。探针假定隔离 MinIO 位于 `127.0.0.1:35441`，并从当前本机测试 MinIO 进程 `/proc/14520/environ` 读取其**临时测试**凭据；更换进程需相应改为新的隔离进程或显式注入临时凭据。不得用于生产。探针目前的断言刻意验证存在缺陷；修复后应反转断言，分别覆盖未确认远端写入时的删除状态、重试及最终无残留。

```text
OUTPUT timeout_job=partial source_receipt=deleted source_row_present=False objects_before_late= 0 objects_after_late= 1 remote_status= 200
.ARCHIVE timeout_status=copy_failed retry=ready archive_receipt=deleted archive_row_present=False objects_before_late= 0 objects_after_late= 1 remote_status= 200
.
2 passed, 2 warnings in 11.73s
```

两条均为小文件单次 PUT，**不等于多部分上传故障注入**。本地锁文件 `hengxin-smart-image/backend/uv.lock:451-463` 固定 MinIO SDK 7.2.20；本机已安装 SDK 的 `api.py:1959-2000` 对单片走 PUT，多片先分片并完成 multipart；`helpers.py:824-840` 用信号量限制并发。不能把本次小文件迟到复现或主 Agent 的成功上传内存峰值，充当多部分中断、重试、abort 及远端残留全覆盖。

前端在 `hengxin-smart-image/frontend` 执行 `pnpm run typecheck`，退出码 0；原始输出：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.

> hengxin-smart-image-frontend@0.2.69 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

这是类型检查，不是完整前端构建；本 reviewer 本轮未运行完整前后端测试、生产安装、真实模型及生产验收。主 Agent 的其他测试数字不能替代本报告的独立验证。

## Stage 2

**未执行。** Stage 1 存在 HIGH，本轮没有系统开展质量/安全扫描、测试真实性全面审查或邻居基准页面与正式页面的实际视觉对比。修复后重新固定 candidateId，从 Stage 1 起复审；不得由旧报告覆盖新快照。
