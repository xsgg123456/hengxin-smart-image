# 国内 AI 工作台最终独立审查 R13

- candidateId：`31f55ef259f5ebef1abc5411db027109fd89c8be98ccaef3acda0380ba900a7f`。
- 日期：2026-11-13。审查范围：Product-Spec、DEV-PLAN、Design-Brief 顶部国内工作台合同，五工作台、私有会话/文件、成品库、Skills 管理及共享复用边界；重点复核联合发布 R12 三项修复、真实进程/UID/socket、标记与恢复。候选外部署助手另列摘要，不纳入候选批准。
- 已读取 `.agents/skills/code-review/SKILL.md`、`.codex/agents/code-reviewer.toml`、`docs/HARNESS-REVIEW.md`、三份源文档和 R12 报告。开始与报告收束前 `review-status.currentId` 均等于上述 candidateId；未修改受控代码、规则或 `.needs-review`，未提交或批准。无生产连接或修改。
- **Stage 1：FAIL，1 项 HIGH。Stage 2：未执行。不得据本报告登记两阶段 PASS、提交为已审完成或部署。**
- 报告落盘后主 Agent 通知将进入修复。本 reviewer 随即停止读取待改代码和继续测试；以上结论只针对已固定的 R13 快照，不能覆盖随后修改。后续必须新 candidateId 与 fresh reviewer。

## H1 · HIGH：异常终止后遗留的 mode 000 凭据 socket 阻断非 root 服务重启及前向恢复

需求依据：`DEV-PLAN.md:18` 要求迁移后经验证的前向恢复；`:48` 要求进程中断、后台封控及恢复；`Product-Spec.md:13` 要求真实执行与原业务保持。发布完成前必须能在受控权限下恢复候选服务。

代码链：

1. `hengxin-smart-image/scripts/migration245/unify_release.py:422` 在发布时保存 socket inode/mode 并 chmod 000。候选启动时 `backend/app/execution/credential_broker.py:71-81` 先调用 `_remove_stale()`，之后才以闭门权限绑定新 socket。
2. 同文件 `:85-101` 的旧 socket 探测使用当前服务 UID 的 `connect()`，只允许 `ECONNREFUSED` 继续删除；mode 000 的 socket 即使没有监听者，非 root 拥有者也没有连接所需写权限，因此得到 EACCES，抛出 `ValueError: cannot replace broker socket`。
3. `backend/app/account_management/service.py:74-86` 的 `ControlServer` 与 `BusinessBroker` 均继承该实现。其 `:134-150` 的信号/ExitStack 清理只覆盖正常退出，SIGKILL 不执行该清理。`scripts/release/intranet/joint_studio_ingress.py:185-208` 在 `start_apps()` 后的 callback 才记录新 inode，没有在启动前处理已停止服务的旧 000 inode；`joint_studio_forward.py:32-65` 的前向恢复与 `joint_studio_ingress.py:227-233` 的 `ensure_private()` 都会再次进入该启动路径。
4. 缺陷结果是候选凭据服务无法恢复，健康检查/新 inode 登记不能完成，发布保持维护状态。这里没有发现 gate 自动放开；这是恢复可用性阻断，不是本轮已证明的数据泄露。

**独立真实 Linux 复现：** `output/review-r13-stale-socket-kill.py` 运行当前 `app.execution.credential_broker.main`，使用独立 `/tmp/hx-r13-broker-*`、UID/GID 65534、真实 Unix socket 与真实子进程。先启动 0660 socket，模拟真实发布 chmod 000，SIGKILL，随后相同非 root UID 重启；root 探测确认旧 socket 已无监听者。没有使用真实凭据、模型、生产 socket 或 systemd 服务。原始输出（`output/review-r13-stale-socket-kill.log`）：

```text
INITIAL_OWNER 65534
INITIAL_MODE 0o660
TERMINATED_EXIT -9
STALE_SOCKET_EXISTS True
STALE_SOCKET_MODE 0o0
RESTART_EXIT 1
RESTART_ERROR ValueError: cannot replace broker socket
ROOT_PROBE_ERRNO 111
REPRODUCED: dead mode-000 socket blocks non-root broker restart
```

另一个独立试验 `output/review-r13-stale-socket.py` 对真实 broker main 发 SIGTERM，得到相同残留与重启失败，退出码为 -15。**它没有 systemd 的 RuntimeDirectory 清理，不能据此声称生产正常首次发布必然失败。** 主 Agent 追加的生产只读核查指出：auth 使用 `RuntimeDirectoryPreserve=no`，systemd 正常 stop 会清理其目录；accounts 使用 `RuntimeDirectoryPreserve=yes`，正常退出会运行应用清理，异常终止则可保留 000 socket。该生产配置由主 Agent 提供，读取脚本为 `output/domestic-socket-readonly.py:12-24`，本 reviewer 没有重新连接生产。HIGH 精确针对 accounts 异常残留及恢复路径，不把 auth 正常 stop 的独立进程试验误当生产复现。

Linux 上连接 pathname stream socket 要求 socket 写权限，与本次实际 errno 一致，见 [Linux man-pages 原文](https://kernel.googlesource.com/pub/scm/docs/man-pages/man-pages/+/refs/tags/man-pages-6.13/man/man7/unix.7)。

修复验收必须覆盖：闭门期凭据服务异常退出留下 000 socket、真实非 root UID 重启、`ensure_private` 重启、迁移后 forward recover；同时拒绝 live socket、未知 inode、被替换路径及仍有子进程的服务。不能临时开放 socket 探测，也不能在缺少停止和身份凭据时盲删。修复由主 Agent 执行，本 reviewer 未改代码。

## R12 修复的本轮核验

| 条目 | 证据与准确结论 |
| --- | --- |
| 非 Celery 后台过早运行 | 静态接入已存在：`backend/app/retention/worker.py:117-153` 在清理前等待并允许停止；三 outbox、variant 与海外导入循环均调用 gate（`backend/app/worker/outbox.py:9`、`backend/app/modules/api_image_edits/outbox.py:9`、`backend/app/overseas/execution/outbox.py:6`、`backend/app/modules/files/variant_worker.py:17`、`backend/app/overseas/drafts/worker.py:65`）。`joint_studio_gate_wiring.py:11-17,20-64` 给七容器/七原生服务配置 gate，并检查实际 env/mount。没有本轮逐个启动真实生产服务的证据，不能称全链已验收。 |
| 三 Celery 消费 gate | `backend/app/execution/release_gate.py:53-58` 使用 worker_init；独立真实 Redis/Celery 测试证明闭门不消费，开门后消费。具体测试 `backend/tests/test_release_gate.py:112-159` 使用独立随机队列并清理该队列。 |
| socket 创建瞬间权限 | `backend/app/execution/credential_broker.py:72-81` 在 bind 前设置 umask 0777；`backend/tests/test_release_gate.py:95-109` 实际观察 bind 后权限为 000，通过。但该测试正常 context close 且以 root 运行，没有证明 H1 中非 root stale socket 恢复。 |
| 正式网关启动后发布进程被杀 | `joint_studio_ingress.py:253-294` 保持 ingress closed，经正式 API、网关路由、快照核验后恢复 socket/worker 并验活，最后开放 ingress；`backend/app/execution/release_gate.py:61-78` 阻止业务请求，只放 GET 健康。独立 SIGKILL 测试通过；其 gateway/systemd/HTTP 操作为替身，进程、文件 marker 与 ASGI gate 为真实，不能把此证据表述为完整生产 Docker 故障演练。 |
| marker 身份和持久化 | `joint_studio_paths.py:23-49` 检查 root 0755 目录、root 0644 单硬链接 marker；写后 fsync 目录并重读。`backend/app/execution/release_gate.py:17-40` 校验身份、O_NOFOLLOW 读取且缺失/异常闭门。已跑发布测试；本轮未做断电文件系统实测。 |
| seal 与前向恢复 | `joint_studio_ingress.py:215-225` 先关闭 ingress，停止入口，workers 曾 open 时原有 drain，停止后台后关闭 workers；`joint_studio_forward.py:10-29` 用 SendSIGKILL=no 的停止配置。`joint_studio_engine.py:74-81,155-173` 区分迁移前旧代码恢复和迁移后拒绝回滚。上述正常控制流可读且测试通过，整体仍受 H1 阻断。 |

## Stage 1 · 当前合同逐项覆盖

下表“有实现”仅指已检查对应代码；缺少本轮完整运行证据的项目写明边界，均不借用 R10/R11 旧结论当本轮 PASS。以下 backend/frontend 均相对 `hengxin-smart-image/`，发布脚本相对仓库根。

| 合同条目 | 实现与本轮验证状态 |
| --- | --- |
| 新品两入口、替换三入口、独立成品库、管理中心超管 Skills | 有实现：`frontend/src/api/hengxin/domestic-workspaces.ts:3-8` 精确列五项；`frontend/src/router/modules/index.ts:12-30` 配置分组/一级成品库/超管菜单。未逐一浏览器操作。 |
| 五入口直接进入，空白，无欢迎/推荐/预填/自动发送 | 有实现：`frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:15-27,62-70` 使用共享会话与 hide-empty-guide，输入框是要求说明；`frontend/src/views/shared/studio/StudioTurns.vue:3` 条件隐藏空态。未独立对五入口全部状态运行浏览器验证。 |
| 会话新建、切换、重命名、删除；空会话和执行中切换 | 有实现：`DomesticWorkspace.vue:100-117` 连接共享新建/选择/重命名/删除；`backend/app/modules/domestic_studio/conversation_service.py:18-42,70-105` 提供所有权/幂等/版本保护。整组 HTTP 回归本轮未完成，不能判通过。 |
| 会话及文件仅创建者可见 | 有实现：`backend/app/modules/domestic_studio/router.py:28-41`、`conversation_service.py:18-27`、`file_service.py:75-96` 按 actor/workspace/channel 限制；`queries.py:41-54,68-76` 只列本人。已读 `backend/tests/test_domestic_studio_http_pg.py:46-75` 的跨身份真实 HTTP 测试，但本轮整组未跑完。 |
| 真人姓名、用户右/Codex 左、北京时间 | 有实现：`backend/app/modules/domestic_studio/queries.py:74-92` 从用户记录取姓名与消息时间；`frontend/src/views/shared/studio/StudioTurns.vue:6-7` 显示姓名、Codex、formatBeijingTime；`frontend/src/views/shared/studio/studio.css` 提供 user/assistant 方向。未连接真实钉钉身份或重做视觉验证。 |
| 连续对话、附件、结果、修改、停止与异常复用 | 有实现：`DomesticWorkspace.vue:15-36,81-105` 引入共享组件/单图批量编辑；`backend/app/modules/domestic_studio/turn_service.py:42-116` 冻结输入与 enqueue/cancel；`runner.py:86` 接真实执行器。未实际调用用户 Skill/模型；上线初始无 Skill 是明确约定，不是缺陷。 |
| 部分收取保留文字/已有文件，手动取回不重跑模型 | 有实现：`backend/app/modules/domestic_studio/runner.py:66-83` 保存已有结果和 partial 回复；`recovery.py:39-65` 核实原进程后只调用 deliver。未独立跑完全部收图故障场景。 |
| 进程不明保持待核实/占用，只原节点核实 | 有实现：`runner.py:23-38`、`recovery.py:39-47,69-78` 检查 node/PID/boot/birth，无法证明终止不重生成。未重跑真实 sandbox 全链。 |
| 上传/输出/归档迟到写保留凭据，不假称已删，不重写同对象 | 有实现：`backend/app/modules/domestic_studio/file_service.py:29-70`、`output_intents.py:13-61`、`archive_service.py:214-260`、`conversation_cleanup.py:81-114`。独立跨 UID 隔离 PostgreSQL 用例正确环境下 1 passed；未重跑真实 MinIO 所有迟到写。 |
| 大附件有界处理 | 有实现入口：`backend/app/modules/domestic_studio/archive_router.py:72-98` 用 8 MiB spool/分块输出，`backend/app/overseas/studio/files.py` 的共用 copy_to；未本轮量测全链内存峰值，不能以存在流式函数替代内存验收。 |
| 各入口教程占位，不编造内容 | 有实现：`DomesticWorkspace.vue:3,33` 标题使用入口 config.title，内容“教程待补充”；无虚构教程链接。未浏览器逐个点击。 |
| 仅两新品按产品名称归档，替换后端拒绝 | 有实现：`backend/app/modules/domestic_studio/policy.py:12-30`，`archive_service.py:124-125` 服务端强制检查；`DomesticWorkspace.vue:14-15,75-78` 限制前端入口。 |
| 独立归档、全体国内成员读取、源仍私有、删源不破坏副本 | 有实现：`archive_service.py:38-53,164-207` 创建独立对象与快照；`archive_router.py:36-45` 使用国内 User 依赖；`archive_queries.py:48-90` 校验独立清单；`conversation_cleanup.py:44-57` 校验副本。未重跑源删除后的完整 HTTP/MinIO 组合。 |
| 成品搜索产品名/来源、详情/删除/下载/图片保护，无假图 | 有实现：`archive_queries.py:34-46,59-95`、`archive_router.py:48-98`、`frontend/src/views/hengxin/domestic-studio/library.vue:11,37-46`；归档内容来自受检文件记录，无预览内存图代入此路径。本轮未实际下载全套 ZIP。 |
| 超管文件夹上传、校验、同名确认更新、启停/删除、ZIP，无版本页/编辑器 | 有实现：`backend/app/modules/domestic_studio/management_router.py:26,77-163`；`frontend/src/views/hengxin/admin/skills.vue:3-8` 复用 shared Skills；未重新实操上传/同名更新/ZIP。后端冻结与版本字段不等同新增面向用户版本管理。 |
| 固定绑定、初始全空、超管替换/解除、普通用户不选择，绑定禁删停 | 有实现：`backend/migrations/versions/0033_domestic_studio_bindings.py:10-26`；`bindings.py:30-82`；`policy.py:33-51`；`turn_service.py:48-52,77-87` 拒绝客户端 skillId 并冻结提交。缺真实 Skill 配置不列未实现。 |
| 国内身份、库、对象、队列隔离，API 换套图、海外与共享认证保持 | 有实现路径：`router.py:28-29`、`runner.py:9-19`、`scripts/release/intranet/domestic_studio_wiring.py:42-114`、`joint_studio_gate_wiring.py:11-64`；但 H1 影响联合恢复。未完成本轮全部旧业务回归或生产入口验收。 |
| 审查/构建通过后中文提交、排空备份迁移、部署正式验收 | **不匹配完成标准：H1 HIGH，Stage 1 未通过。** `joint_studio_release.py:111-219` 有发布/恢复流程，但不能安全恢复某些凭据异常残留。本轮未编译、提交、安装或部署。 |
| Spec 漂移 | 未完成全量盘点：已见新增业务入口对应合同，gate 属 DEV-PLAN 明确授权修复；无法仅凭以上路径断言所有新增表/API/共享改动都无漂移。待 H1 修复后继续两阶段完整审查。 |

## 独立测试原始输出与边界

发布脚本套件，使用已提供的本机隔离 PostgreSQL 地址与测试凭据，未连接生产；日志 `output/review-r13-release.log`：

```text
........................................................................ [ 19%]
........................................................................ [ 38%]
........................................................................ [ 58%]
................................................................. [ 75%]
...................................................................... [ 94%]
....................                                                     [100%]
371 passed, 9 subtests passed in 30.11s
```

该命令只跑 `scripts/release/intranet`，未包括主 Agent 390 项所含的其它目录，不能写成390项重跑。

真实 gate 进程/socket/Redis/Celery 定向测试，日志 `output/review-r13-process.log`：

```text
......                                                                   [100%]
6 passed, 1 warning in 7.03s
```

跨 API/worker UID 文件锁与迟到写，正确设置 `PYTHONPATH=.` 后，日志 `output/review-r13-cross-uid-corrected.log`：

```text
.                                                                        [100%]
1 passed in 11.03s
```

本轮曾发起 `tests/test_domestic*.py`，发现 HIGH 后中止自己的测试进程。原日志 `output/review-r13-domestic.log` 包含未完成进度、一个 F 和 KeyboardInterrupt/pytest teardown KeyError，不计通过数。F 经单独复验（`output/review-r13-cross-uid.log`）定位为审查命令漏设 PYTHONPATH，导致辅助子进程 `ModuleNotFoundError: No module named 'app'`；补全环境的定向测试已通过。没有把该环境错误列成产品缺陷，也未把中止全套视为已完成。自己的测试进程已退出。

**编译输出：本轮未执行编译/类型检查，故无可报告的本轮编译结果。** 主 Agent 提供的前端564项、国内/海外构建及旧轮视觉只作索引。因 HIGH 停在 Stage 1，本轮没有启动浏览器、重跑 R11 视觉、执行本机 Docker smoke 或 Stage 2 的完整质量/安全扫描。

## 候选外部署助手只读复核

以下位于 ignored `output/domestic-studio-release-bin/`，不属于 candidateId。仅静态读取，没有制包、SSH、上传、安装、激活或执行生产。

- `build_committed.py:12-42` 以当前 HEAD 制包并检查清单/来源/内容；`install_committed.py:17-50` 以 Git blob 对照归档后构造 inactive 工具树。不得现在拿旧 HEAD 制包当作本候选。
- `upload_and_stage.py:14-19,42-65` 对齐 commit、包与工具清单后调用 stage；`server_verify_tools.py:11-39`、`server_verify_candidate.py:11-42` 校验目录、实际文件集合与字节摘要。
- `server_installed_checks.py:20-46` 安排安装后隔离测试/私有入口 smoke；`server_publisher_smoke.py:27-114` 使用临时无网络容器验证 publisher UID/socket 并清理。**未执行，不证明 H1 已覆盖。**
- `server_activate_tools.py:27-57` 在已有发布锁内核对台账/运行态后切工具链接；`run_server_helper.py:14-46` 将当前 HEAD 的安装/包身份注入检查器；新增 `server_joint_release.py:9-31` 检查 active 工具链接和三 scope/commit 后调用已安装 prepare、deploy、verify/status，不提供自动恢复。此助手会继承候选 H1，不可据静态检查放行。
- 该目录在审查期间由主 Agent 新增/更新 `server_joint_release.py`、`run_server_helper.py`，其最终读取摘要如下；受控候选未变。执行前仍须核对同一内容和新批准候选/提交/产物，不以本报告授权这些脚本的未来版本。

| 文件 | 本轮读取 SHA-256 |
| --- | --- |
| build_committed.py | `cb1047492a1e1b58c00a73a0a8756b4fbaf3fd38e8ba5c999a919d7e7c85e322` |
| install_committed.py | `7bc3be91cb2975113cea5ecc71e50d13bc3579d50871d36cc2ddb866968684eb` |
| run_server_helper.py | `039d4a9e85dd28fdc2ea3e54e002344ad9cef35be9e8d733213e63e7bfb6d457` |
| server_joint_release.py | `1fe278c3df07fcc3e64246f5f5b7357b93d4f0d75cf9aec66fcaa91e7cff354c` |
| server_installed_checks.py | `dd7f3d5c80dba98798d3433e4ad6740feeb2da1a86214eb2a08511719b89153d` |
| server_activate_tools.py | `c6c7ec61bc87bb3f17f47712e518f3484ba4f526e754091aade4fda511226c6a` |
| server_publisher_smoke.py | `02ea7ba52243eb1ed623a4049dcb9a6bfc93d14f1ad5f0af193bf76ab2f91fed` |
| server_verify_candidate.py | `e9d72386c57b04b3c80cbaf1efe8b75d1f4df31086c2f668f2b22b26537c998b` |
| server_verify_tools.py | `8a440e7d732cc5ec63b4f04f1dde70deab8a4d57ab9759ca2133d4d5d80c8375` |
| upload_and_stage.py | `335371c929ddd0ba2ba005ad2b5e1bc755a0d0d39865384d4d0ed30fdc91fbb4` |

## Stage 2 与交付边界

**Stage 2 未执行。** H1 必须修复并重新 review-prepare，从 Stage 1 复审；没有完整质量、安全、文件大小/类型扫描或新的实际视觉结论。仍需完成安装后的 Linux 原生目录/真实 UID/socket、生产排空/备份/迁移/源码及三组台账一致性、正式入口与身份隔离核验。所有生产操作均未由本 reviewer 执行。

五工作台初始绑定为空符合 Spec；真实 Skill 由用户上线后上传并绑定，教程由用户提供。真实模型和用户 Skill 未调用应作为后续功能验收边界，不能要求编造配置，也不能把模拟结果冒充真实生图。本报告不批准发布，不证明已上线。
