# 国内 AI 工作台及联合发布独立审查 R12

## 结论与边界

- **candidateId：`110ad795f5c4e52da26ea102720d0c29073d3647c95848dd79d5df72b9109f32`；Stage 1：FAIL；Stage 2：未执行。** 发现后台消费者、凭据 socket 和正式入口异常中断三个 HIGH。不得登记两阶段 PASS、提交或部署此候选。
- 审查范围：`Product-Spec.md:1-13` 的国内五工作台、会话、附件、身份、归档和 Skill；`DEV-PLAN.md:1-18` 的联合升级、排空、备份、身份、台账和中断恢复；`Design-Brief.md:1-3`、用户确认预览 `hengxin-smart-image/frontend/preview-domestic-studio/`。同时只读检查候选外的 `output/domestic-studio-release-bin/`。下文 `backend/` 和 `frontend/` 均相对于 `hengxin-smart-image/`。
- 依据 `review-status`，开始和结束时 `currentId` 均为上述 candidateId，`approved:false`；没有观察到受控代码变化。只写本报告及 `output/` 的独立复现，未修改业务代码或配置、未提交、未批准、未连接生产。FINAL 至 R11 旧报告仅作历史风险索引，不能将旧候选的测试或视觉结论自动作为本候选通过。
- 发现 HIGH 后按 `.agents/skills/code-review/SKILL.md` 停止 Stage 2；下表“部分”只表示已找到所列代码或有限测试，不代表全链路通过。

## Stage 1 · HIGH

### H1：未验证候选时启动非 Celery 消费者；校验失败后的 seal 也未停止它们

`DEV-PLAN.md:16-18` 要求排空后迁移，实际身份、健康、台账和前端接口确认后恢复接纳。`scripts/release/intranet/joint_studio_engine.py:145-150` 将原有 `start_apps` 传入 `PrivateIngress.start`；`joint_studio_ingress.py:187-193` **先完整运行** `start_apps(ctx)`，之后才调用 `_quiesce`。原 `hengxin-smart-image/scripts/migration245/unify_release.py:28-54,503-510` 启动 `hengxin-retention`、`hengxin-domestic-deletions`、`hengxin-overseas-outbox`、三个 Celery worker、国内外 outbox 和 `domestic-image-variants`。这些进程不是只读检查：

- `backend/app/retention/worker.py:126-145` 启动后立即轮询已登记删除、国内会话/归档清理和恢复请求。`backend/app/modules/domestic_studio/conversation_cleanup.py:148-176,186-190` 对到达删除条件的会话清理对象并删除记录。
- `backend/app/retention/worker.py:57-75,78-100` 在自动保留功能启用时扫描到期记录并处理对象；`backend/app/modules/files/variant_worker.py:47-55,63-90,106-128` 在存在待处理记录时读取并写入派生图片。是否存在实际待处理记录取决于运行环境，不能断言此次已发生生产删除。
- `scripts/release/intranet/engine.py:193-209` 的 `_quiesce` 只检查三个 Celery worker 并封控凭据；没有暂停或停止上述辅助服务。`joint_studio_ingress.py:195-199` 的 `seal()` 关闭四个入口后仍只调用 `_quiesce`。因此，即使 `joint_studio_release.py:141-147,172-177` 在身份/源码/挂载核验失败后成功执行 `seal`，上述后台进程仍可继续操作持久数据。

**独立隔离复现：** `output/review-r12-background-repro.py` 运行真实 `PrivateIngress.start`、`unify_release.start_apps`、`engine._quiesce`、`unify_release.drain` 和 `PrivateIngress.seal`；systemd、Docker、Celery 和凭据动作均为内存替身，没有执行真实删除。关键原始输出：

```text
AFTER_PRIVATE_START {"hengxin-retention": true, "hengxin-domestic-deletions": true, "hengxin-overseas-outbox": true, "domestic-image-variants": true}
QUEUES_AFTER_PRIVATE_START {"hengxin-vps-codex-worker": [], "hengxin-overseas-worker": [], "domestic-api-image-worker": []}
AFTER_VERIFICATION_FAILURE_SEAL {"hengxin-retention": true, "hengxin-domestic-deletions": true, "hengxin-overseas-outbox": true, "domestic-image-variants": true}
ENTRY_STATES_AFTER_SEAL {"domestic-web": false, "domestic-api": false, "overseas-api": false, "identity-api": false}
REPRODUCTION PASSED: non-Celery consumers remain running after seal
```

现有 `test_joint_studio_ingress.py:144-153,239-246` 将 `_quiesce` 替换为只记事件的 lambda，没有断言这类后台进程处于安全状态，因此其通过不能证明上述条件成立。修复应覆盖全部会异步修改数据的生产者和消费者、启动窗口、核验失败和前向恢复；不能只隐藏 HTTP 入口或暂停三个队列。

### H2：重启凭据服务后，原有 socket 封控被新的 0660 socket 解除，直到重新排空后才再次封控

`engine.py:162-169` 在旧进程仍运行时调用 `gate_accounts`，随后停止原生服务并迁移。切换后 `unify_release.py:503-509` 先启动两个凭据服务，再启动辅助服务和原生 worker，随后启动容器、检查健康并启动网关。只有整段 `start_apps` 返回后，`joint_studio_ingress.py:187-193` 才执行 `_quiesce` 和重新封控；`engine.py:205-209` 也证明封控位于 `_quiesce` 的排空之后。`backend/app/execution/credential_broker.py:64-74,113-118` 的真实 broker 会移除旧 socket 并新建模式 `0660` 的 socket。

**独立隔离复现：** `output/review-r12-socket-repro.py` 在本机临时目录使用真实 `BrokerServer`、真实 Unix socket 和当前用户身份；未读取实际凭据。原始输出：

```text
FIRST_PROCESS_GATED 0o0
RESTARTED_PROCESS_MODE 0o660 SOCKET_RECREATED True
REPRODUCTION PASSED: a restarted broker creates an ungated socket
```

这证明“候选启动期间凭据 socket 持续封控”不成立。此处并未实测生产客户端或声称存在无权限的外部凭据读取；实际授权仍取决于 socket 目录/文件权限和服务端 peer UID。旧队列曾被排空也不能把新 socket 在整个启动窗口处于封控当作已验证事实。

### H3：进程在正式网关开放后、公开核验完成前被强制终止，不会执行 seal

实际时序需要区分三步：

1. `joint_studio_release.py:141-149` 先确保私有候选并调用 `scope_snapshot.capture`。`joint_studio_ingress.py:147-172` 在各 API 容器内通过 loopback 检查接口，在私有网关检查前端；三个前端的私有路由通过 `joint_studio_ingress.py:109-120` 检验。私有候选的网关 Nginx、端口和 API 监听地址不同于正式配置，见 `joint_studio_private_config.py:63-77`；不能把 API 容器内的健康检查表述成正式网关上的三条 API 路由已经过验证。
2. `joint_studio_release.py:150-165` 在私有快照归一化后验证变更并持久化成功台账（重试时核对台账）；随后 `:166-170` 持久化 `opening`，调用 `open_public`，返回后才写 `complete`。
3. `joint_studio_ingress.py:234-259` 依次恢复凭据和消费者、启动正式 `domestic-web`，**然后**检查公开健康、三个正式 API 路由以及最终 `scope_snapshot`。所以中断时此前已有私有检查和台账，不是完全未验证便开放；缺口是新建正式运行态及其正式路由的公开核验尚未完成，且不会自动回封。

如果公开检查抛出普通异常，`joint_studio_release.py:172-177` 会尝试 `seal`；但 SIGKILL、解释器进程突然消失或机器断电不会执行该 Python 异常分支。`joint_studio_marker.py:19-22` 只拒绝新的发布/清理命令，不是业务入口或独立存活监督。正常的最终公开核验全部成功之后，仅 `complete` 标记写入不确定是不同情形，不能和本缺口混为一谈。

**独立隔离复现：** `output/review-r12-kill-repro.py` 在子进程中运行真实 `PrivateIngress.open_public`，用文件模拟已持久化的 `opening` 及独立存活的外部网关；systemd、Docker、socket、队列和 HTTP 使用替身。父进程在网关启动调用期间、正式验证前向真实子进程发 SIGKILL。原始输出：

```text
CHILD_EXIT -9
PERSISTED_PHASE opening
EXTERNAL_GATEWAY_STILL_ACTIVE True
SEAL_EXECUTED False
REPRODUCTION PASSED: abrupt exit bypasses Python seal
```

该试验没有杀真实 Docker 或生产进程，证明的是控制流程不会在不可捕获退出时自动执行 `seal`；是否存在仓库外的实际主机监督机制本轮未验证。人工再次运行 `recover` 可以处理一部分状态，但不能证明中断到人工介入之间入口自动关闭。需要针对真实容器/进程生命周期验证非终态时的入口和消费者安全边界，以及公开核验完成后的终态写入不确定性。

## Stage 1 · 其他需求逐项状态

| 需求 | 本轮证据和状态 |
| --- | --- |
| 五入口、两新品三替换、独立成品库及超管 Skills | 部分：`frontend/src/api/hengxin/domestic-workspaces.ts:3-8`、`frontend/src/router/modules/index.ts:12-30` 定义入口。没有重新以真实身份逐一操作五入口和权限。 |
| 空白会话、无预填/自动发送 | 部分：`frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:15-27`、`frontend/src/views/shared/studio/StudioTurns.vue:3` 提供隐藏空态引导；没有独立检查全部入口和全部状态。 |
| 会话、文件仅创建人可见；新建、切换、重命名、删除 | 部分：`backend/app/modules/domestic_studio/conversation_service.py:18-42,70-105`、`queries.py:41-54,68-76` 有服务端处理；本轮未重跑完整跨用户 HTTP 和清理链。 |
| 真人姓名、时间和左右方向 | 部分：`backend/app/modules/domestic_studio/queries.py:22-25,74-92`、`frontend/src/views/shared/studio/StudioTurns.vue:6-7` 有对应字段和展示；未验证真实钉钉用户或重跑视觉对照。 |
| 附件、连续对话、生成、修改、停止及异常 | 部分：`DomesticWorkspace.vue:15-36,81-105`、`backend/app/modules/domestic_studio/turn_service.py:42-116` 连接共享组件和服务端；未调用真实 Skill 或模型，也未完整重跑图片编辑及停止故障链。 |
| 保留部分结果、原节点核实、手动取回不重复生成 | 部分：`backend/app/modules/domestic_studio/runner.py:23-38,66-83`、`recovery.py:39-65` 有相关路径；本轮未独立执行进程身份不明或真实文件恢复。 |
| 远端写入不明时保留凭据，不重复写；大附件有界 | 部分：`backend/app/modules/domestic_studio/file_service.py:29-70`、`output_intents.py:13-61`、`archive_service.py:214-260` 有相关路径；本轮未重新运行迟到写及大文件内存验证。 |
| 每入口教程占位 | 部分：`DomesticWorkspace.vue:3,33` 提供按入口标题显示的教程及待补充；本轮未逐一操作。 |
| 仅新品归档，替换服务端拒绝 | 部分：`backend/app/modules/domestic_studio/policy.py:12-30`、`archive_service.py:124-125`、`DomesticWorkspace.vue:14-15,62-64`。本轮策略测试见下，未重新执行完整归档 HTTP。 |
| 所有国内成员可见独立归档，源会话私有，删源不破坏归档 | 部分：`backend/app/modules/domestic_studio/archive_service.py:38-53,164-207`、`archive_queries.py:59-70`、`conversation_cleanup.py:44-57` 有复制和删除前检查；未重跑跨成员、损坏快照和源删除后的真实存储场景。 |
| 成品搜索、来源、详情、逐图资料、删除和 ZIP | 部分：`backend/app/modules/domestic_studio/archive_router.py:36-98`、`archive_edits.py:8-38`、`frontend/src/views/hengxin/domestic-studio/library.vue:11,37-46`。未重跑实际 ZIP、标注和全部归档错误路径。 |
| 超管 Skill 文件夹 CRUD、同名更新、ZIP、无版本管理或在线编辑 | 部分：`backend/app/modules/domestic_studio/management_router.py:26,77-163`、`frontend/src/views/hengxin/admin/skills.vue:3-7`、`frontend/src/views/shared/skills/SkillFolderUpload.vue:2-27`。已跑定向管理测试，未逐一实操 UI 和真实安装后的发布 socket。 |
| 五入口固定绑定初始为空、发送冻结、拒绝绕过、绑定时禁删停 | 部分：`backend/migrations/versions/0033_domestic_studio_bindings.py:10-26`、`backend/app/modules/domestic_studio/bindings.py:30-82`、`policy.py:33-51`；已跑隔离 PostgreSQL 和策略定向测试，未用真实 Skill 执行。 |
| 国内外身份、库、对象、队列隔离并保留旧业务 | 部分：`backend/app/modules/domestic_studio/router.py:28-29`、`scripts/release/intranet/domestic_studio_wiring.py:42-114` 有对应边界；未完成旧业务全量或生产身份验证。 |
| 迁移备份、0032→0043 和前向恢复 | 部分：`scripts/release/intranet/joint_studio_engine.py:18-70,141-143`、`joint_studio_fence.py:26-60`、`joint_studio_forward.py:32-65`；本轮只跑定向发布单测和故障控制流替身，未进行真实生产迁移或新一轮真实备份恢复演练。 |
| 确认预览、测试、审查、提交、部署与正式验收 | 不通过：本报告 Stage 1 有 HIGH。R11 中 320/489/490/799/800/1920 px 的旧快照视觉结果是历史证据，本轮没有重新打开浏览器；未独立执行本候选完整构建、正式身份、真实模型、提交或部署。 |
| Spec 漂移 | 未完成：部分代码引用可见并不等于盘点了所有新增路由、表、页面、组件和功能；不能判定无漂移。 |

## 私有入口、台账和候选外辅助脚本的有限复核

- `scripts/release/intranet/joint_studio_private_config.py:45-81` 从受摘要保护的 Compose 候选生成无宿主端口的网关和仅容器 loopback 监听的三个 API；`joint_studio_ingress.py:46-78,96-102` 检查容器监听、nginx 配置和预检。`normalize` 在 `joint_studio_private_config.py:84-104` 校验原配置与私有配置摘要，将私有 nginx 文件在结果中替换成原文件键；`joint_studio_state.py:12-35` 检查未经许可的配置变化。此为定向静态检查，不构成整个状态机 PASS。
- 本轮实际运行 `python output/domestic_private_host_smoke_local.py`，使用本机 Docker Desktop 的隔离项目、随机标签、本机镜像与本地复制配置。原始输出：

```text
{"status": "PASS", "private_network_blocked": true, "public_readiness": true, "test_resources_remaining": 0}
```

  该烟测证明隔离容器网络及本机恢复监听，不代表生产已安装，也不覆盖 H1–H3 的完整发布状态机。
- `output/domestic-studio-release-bin/build_committed.py:12-42` 对当前 HEAD 制包并核验清单；`install_committed.py:17-50` 从 HEAD 的 Git blob 校验工具内容；`upload_and_stage.py:14-19,42-65` 核验当前 HEAD、包和远端摘要；`run_server_helper.py:19-39` 核验安装版本并以 900 秒超时运行；`server_installed_checks.py:20-43` 包括已安装版本的独立 Docker 私有入口烟测；`server_activate_tools.py:27-57` 用发布锁、台账和运行状态约束激活。这些是只读检查，不等于已安装、上传、激活或执行生产烟测。
- 上述辅助脚本位于 `output/`，**不属于本 candidateId**。本轮读取时 `run_server_helper.py` SHA-256 为 `f8a3be465730945616c80c151686826e5d12dcb16cb558870527595951999c7e`，`server_installed_checks.py` 为 `dd7f3d5c80dba98798d3433e4ad6740feeb2da1a86214eb2a08511719b89153d`。执行前仍须核对辅助脚本、批准快照、提交后的完整 HEAD、包和工具清单；当前 HEAD `979e099b63cba11cad4bd5c2f057e263a4ef8193` 尚不含本候选，不能现在制包部署。

## 本轮独立测试与编译原始输出

隔离 WSL 发布入口及恢复定向测试，`test_joint_studio_ingress.py` 与 `test_joint_studio_release.py`：

```text
.......................s                                                 [100%]
23 passed, 1 skipped in 5.50s
```

另跑 `test_joint_studio_engine.py`、`test_joint_studio_state.py`、`test_joint_studio_verify.py` 和 `test_joint_studio_config.py`：

```text
.......................................                                  [100%]
39 passed in 6.52s
```

隔离测试 PostgreSQL 的国内策略、绑定和管理定向测试；其中数据库连接使用本地测试实例，未使用生产数据：

```text
.....................................................                    [100%]
=============================== warnings summary ===============================
../../../../tmp/hengxin-domestic-studio-python/lib/python3.14/site-packages/fastapi/testclient.py:1
  /tmp/hengxin-domestic-studio-python/lib/python3.14/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
53 passed, 1 warning in 23.05s
```

本轮没有独立运行编译、类型检查或前后端全量测试，因此没有本轮编译输出可报告；以上通过数不证明 H1–H3 已覆盖。主 Agent 提供的构建、全量测试和 R10/R11 测量属于先前证据，不冒充本 reviewer 已重跑。

## Stage 2

**未执行。** 因 Stage 1 有 HIGH，没有开展完整代码质量、安全扫描、测试真实性全量审查或新页面与邻居基准页的实际视觉对比。修复后必须重新 `review-prepare`，将新 candidateId 交独立 reviewer 从 Stage 1 重审；不得用本报告登记两阶段 PASS。真实生产、正式 Skill、模型与生图均未验收。
