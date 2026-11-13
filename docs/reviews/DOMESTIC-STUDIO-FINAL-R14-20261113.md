# 国内 AI 工作台最终独立审查 R14

- candidateId：`a8b3f0852b8446b4d4b41ed10b7da6bb8167dfe29d69d226689214a0fbcc4075`。
- **Stage 1：PASS。Stage 2：PASS。没有发现本候选新增的阻断问题；R13 的 HIGH 已闭环。** 保留一项非阻断的既有文件长度债务，见下文。
- 范围：`Product-Spec.md:1-15`、`DEV-PLAN.md:1-49`、`Design-Brief.md:1-3` 的国内五工作台、私有会话、成品库、Skills 管理、共享复用与联合发布恢复。应用目录为 `hengxin-smart-image/`；发布工具为根目录 `scripts/release/intranet/`。不重新验收全部历史产品需求。
- 已读取 code-review SKILL、code-reviewer TOML、HARNESS-REVIEW 协议、三份源文档顶部原文及 R13 风险报告。按先功能/设计、后质量/安全的顺序审查，未改代码/规则、未提交/批准、未连接生产，也未写 `.needs-review`。
- 初始及收束快照一致；当前仍未登记批准，由主 Agent 使用本报告为同一 candidateId 执行 `review-approve`。普通报告不纳入代码快照。根目录既有未跟踪 `=12.1,` 不属于本任务，不作产品审查或提交建议。

## Stage 1：R13 凭据异常恢复复核

R13 的缺陷是非 root 凭据服务异常退出留下 mode 000 的 pathname socket，服务自身无法用 connect 判定它是否失效。本轮没有将正常 systemd stop 与异常残留混为一谈：主 Agent 提供的生产只读配置为 accounts 保留运行目录、auth 正常停止清目录；本 reviewer 不声称正常首次发布必然触发该问题。

| 检查 | 结论与证据 |
| --- | --- |
| 启动前恢复接线 | 匹配。`scripts/release/intranet/joint_studio_ingress.py:181-190` 在真实 `start_apps` 的 before_credentials 回调执行 prepare；`hengxin-smart-image/scripts/migration245/unify_release.py:503-510` 先恢复旧残留，再启动 accounts/auth，再登记新 socket，最后启动其它服务。 |
| 停止状态与子进程 | 匹配。`joint_studio_credentials.py:16-28` 要求 inactive/failed、MainPID 0，存在的 cgroup 及子层不得有进程。`test_joint_studio_credentials.py:107-119` 覆盖残余子 cgroup；active/PID 拒绝用例也实际运行。 |
| 固定路径、原身份与目录链 | 匹配。`joint_studio_credentials.py:31-49,56-73` 仅遍历固定四个 ACCOUNT_SOCKETS，要求原 journal 有非零恢复模式、原服务 UID、单链接 socket、mode 000；逐层 O_DIRECTORY/O_NOFOLLOW 打开受控运行目录，拒绝可写目录链。不是按目录批量删除。 |
| 死 socket 证明与删除 | 匹配。`joint_studio_credentials.py:75-95` 以 root 通过已打开父目录 fd 探测，只有 ECONNREFUSED 可继续；成功连接、权限错误等均拒绝。删除前再查服务停止状态及 dev/inode/UID/GID/mode/nlink，unlink 后 fsync。探测中没有临时 chmod 开放权限。 |
| 新 inode、重复恢复 | 匹配。可接受固定受控路径下符合原服务 UID 的新死 inode，不把所有新 inode 当未知路径。`joint_studio_credentials.py:100-116` 等待新 socket 以 000 创建，再按原非零模式登记其 inode，并重新 gate。真实 UID 65534、真实 Unix socket 和 SIGTERM/SIGKILL 重启、重复 prepare 均通过，见 `test_joint_studio_credentials.py:38-80`。 |
| live/未知身份不误删 | 匹配。`test_joint_studio_credentials.py:83-119` 对真实 live listener、错误 owner、普通文件、非零权限、symlink、缺少 journal、活动服务以及子进程逐项断言拒绝并保留。不是仅凭替身返回“已停止”就断言安全。 |
| ensure_private / forward | 匹配。`joint_studio_ingress.py:217-223` 的 ensure_private 先 seal 再走上述 start；`joint_studio_forward.py:32-65` 前向恢复调用被 `joint_studio_engine.py:147-152,175-185` 包装的 start_apps。迁移前旧恢复仍走原路径；迁移后禁止旧代码恢复（`joint_studio_engine.py:74-81,155-173`）。相应 ingress/release/engine 故障与重复恢复测试通过。 |

本轮定向运行结果：`output/review-r14-release.log` 为 43 passed、1 skipped。随后完整配置发布套件为 **401 passed、9 subtests passed，无跳过**，包括真实 UID 数据库 fence 与实际隔离 PostgreSQL 迁移、备份/还原演练。测试证据不等于已在生产执行恢复。

## Stage 1：当前合同逐项对照

以下 `backend/`、`frontend/` 均相对 `hengxin-smart-image/`。表中“通过”是本候选实现审查与本轮测试的综合结论，真实模型、真实用户 Skill 及生产上线状态另列边界。

| Spec 要求 | 结论、代码与本轮验证 |
| --- | --- |
| 新品两入口、替换三入口，独立成品库、超管 Skills 菜单 | 完整实现。`frontend/src/api/hengxin/domestic-workspaces.ts:3-8` 精确列五项；`frontend/src/router/modules/index.ts:12-34` 分组、成品库一级及超管角色限制。浏览器实际逐一访问五条路由，见 `output/review-r14-five.log:1-2`；角色与路由测试包含在 564 项前端套件。 |
| 直接进入、空白、无欢迎/推荐卡/示例/预填/自动发送 | 完整实现。`frontend/src/views/hengxin/domestic-studio/DomesticWorkspace.vue:15-27` 传 hide-empty-guide 并使用空草稿；`frontend/src/views/shared/studio/StudioTurns.vue:3` 按参数隐藏引导。五入口浏览器空态均为 empty=true、messages=0、automaticWrites=0；没有默认提示词请求。 |
| 每入口持久私有多会话，新建/切换/重命名/删除，空会话可建、切换不终止执行 | 完整实现。`backend/app/modules/domestic_studio/conversation_service.py:18-42,70-105` 所有权、幂等、版本保护；`DomesticWorkspace.vue:65-68,100-119` 复用共享会话管理。真实 PG HTTP 新建/重命名及会话、删除回归通过；前端共享会话交互测试通过。 |
| 会话及原始文件仅创建者可见 | 完整实现。`backend/app/modules/domestic_studio/router.py:28-41`、`conversation_service.py:18-27`、`file_service.py:75-96` 均绑定 actor/workspace/conversation。`backend/tests/test_domestic_studio_http_pg.py:46-75` 用真实 HTTP 和两身份验证会话、附件、取消跨用户为 404，本轮通过。 |
| 真实姓名、右用户/左 Codex、北京时间 | 完整实现。`backend/app/modules/domestic_studio/queries.py:74-92` 读取 UserRecord 和真实消息时间；`frontend/src/views/shared/studio/StudioTurns.vue:6-7` 使用姓名/Codex/formatBeijingTime。实际浏览器把测试 UTC 09:30 渲染为 17:30，目视右用户左 Codex；查询及消息 metadata 测试通过。不把测试姓名当生产钉钉登录实测。 |
| 附件、连续对话、生成文件、修改、停止和异常复用海外语义 | 完整实现。`DomesticWorkspace.vue:15-36,81-105` 复用共享消息与单图/批量编辑；`backend/app/modules/domestic_studio/turn_service.py:42-116` 冻结输入、入队和取消；`backend/app/worker/tasks.py:49-50` 调用国内 runner。HTTP、runner、图片修改与停止回归通过；`test_domestic_real_sandbox_linux.py:24-95` 实际 Bubblewrap 执行本地 CLI stub 并续接同一工作区、保存图片，本轮通过。未调用外部模型。 |
| 部分收取保留文本与已保存文件，手动取回不重新生成 | 完整实现。`backend/app/modules/domestic_studio/runner.py:66-83`、`recovery.py:39-65` 和 recovery_transport 复用收取路径；runner、恢复文件、output_store 回归本轮通过。取回文件按钮在 320/490/799 宽度实际打开成功。 |
| 进程不明保持待核实和占用，只原节点核实 | 完整实现。`backend/app/modules/domestic_studio/recovery.py:27-46,69-78` 核实 node/PID/boot/birth 和进程组；未证明停止则不走正常 claim。runtime/recovery lock 与真实 Linux sandbox 回归通过。 |
| 上传/生成/归档中断写入保留凭据，不假删除、不重复迟到写 | 完整实现。`file_service.py:46-64` 先持久写入凭据；`output_intents.py:13-61` 对对象固定身份且已登记不再次 PUT；`archive_service.py:194-242` 在发起唯一 PUT 前提交意图，`conversation_cleanup.py:81-114,148-184` 与 archive_deletion 核实后清理。真实 PG 迟到上传、归档/输出故障与删除回归通过。大对象与真实 MinIO 历史证据未冒充本轮重跑。 |
| 大附件有界处理 | 完整实现。`file_service.py:29-38` 按 1 MiB 计算摘要；`backend/app/overseas/studio/context_assets.py:98-104` 用 copy_verified 恢复；`backend/app/modules/files/streaming.py:6-17` 按 64 KiB 流式响应并释放连接。审阅原有大文件路径与本轮编译/下载兼容测试；未重复与凭据修复无关的大附件峰值内存压测。 |
| 分入口教程占位，无编造内容 | 完整实现。`DomesticWorkspace.vue:32` 使用入口标题加“使用教程”，内容“教程待补充”。本轮五入口逐一打开教程，均命中准确标题；无示例注入。 |
| 仅新品按产品名称归档，替换必须服务端拒绝 | 完整实现。`DomesticWorkspace.vue:73-75` 只在 camera/case 显示；`backend/app/modules/domestic_studio/policy.py:12-29` 与 `archive_service.py:105-106` 服务端检查。浏览器两项有归档、三项无归档；PG 归档防绕过测试通过。 |
| 归档独立副本、国内成员共享、源私有、删源后不损归档 | 完整实现。`archive_service.py:24-35,105-187` 独立对象与完整对话快照；`archive_queries.py:51-98` 所有详情/文件共用快照与路径校验；`conversation_cleanup.py:44-57` 核实独立副本。归档 HTTP、跨成员、删源留存、篡改清单/对象路径拒绝回归通过。 |
| 成品列表名称搜索/来源、详情、删除、ZIP、图片保护 | 完整实现。`frontend/src/views/hengxin/domestic-studio/library.vue:4-12,38-65`；`backend/app/modules/domestic_studio/archive_queries.py:34-46` 参数化查询；`archive_router.py:37-97` 权限、详情、流式单文件/ZIP，非图片同样 verify_content=True。本轮归档/完整性回归通过。无演示成品图片。 |
| 修改材料、公开过程、终态/错误完整归档 | 完整实现。`archive_service.py:155-187` 保存 edits、transcript、真实 job 状态与独立 event ID；`library.vue:11` 使用共享材料/过程组件。`test_domestic_archive_edits_pg.py` 与前端 `domestic-archive-edits.test.ts` 本轮通过，含旧资料兼容。 |
| Skills 完整文件夹上传校验、同名更新、启停删除、ZIP，无版本管理/在线编辑器 | 完整实现。`backend/app/modules/domestic_studio/management_router.py:83-134` 复用海外 transfer/package；`skill_publication.py:47-119` 完成安装/删除事务；`frontend/src/views/hengxin/admin/skills.vue:4-8` 复用共享目录；`frontend/src/views/shared/skills/SkillFolderActions.vue:3-22` 国内 zipOnly。后端 publisher/management 与前端 Skill 文件夹/ZIP/冲突测试本轮通过。内部并发 version 字段不是用户版本管理功能。 |
| 超管配置固定 Skill、普通用户不能选、服务器拒绝未绑定/停用/伪造，运行中冻结 | 完整实现。`management_router.py:26-27` 使用 manage_system；`policy.py:32-52` 拒绝客户端 Skill ID；`turn_service.py:44-82` 在 admission 锁下冻结；`skill_references.py:15-33` 固定并 pin 请求快照。真实 PG 权限/binding/reference 测试和前端 564 项回归通过。 |
| 绑定中的 Skill 不能直接停用/删除；上线无初始绑定 | 完整实现。`skill_state.py:29-48`、`skill_publication.py:85-109` 在变更前 assert_unbound；迁移仅建立结构，没有插入用户 Skill/绑定。浏览器五入口缺绑定均显示联系管理员且禁止发送；实际隔离 0032→0043 迁移断言绑定表为 0。 |
| 国内身份、库/对象/队列隔离，保留海外/API 换套图与共享认证 | 完整实现。`backend/app/main.py:7-8,62-64` 仅国内注册新路由；国内 output/upload key 含国内命名空间、actor/channel；`frontend/src/api/shared/studio.ts:18-22` 独立国内 URL；`DomesticWorkspace.vue:63` 缓存身份加 domestic 前缀。HTTP 跨身份/业务权限、真实 Linux UID、共享前端与双 scope 构建本轮通过；未重复所有历史线上业务流程。 |
| 构建、独立审查后中文提交及安全发布，未通过不宣称上线 | 实现准备通过。发布工具使用既有锁/台账、实际数据身份、备份、隔离候选、私有健康检查和迁移前后区分。详见下面发布 gate 表。中文提交、生产安装/部署/正式入口核验仍是主 Agent 的后续执行事项，本报告不是上线凭据。 |

本范围没有查到“仅部分实现”或“完全未实现”的合同功能。生产真实 Skill 尚未提供、绑定初始为空、教程待补充均为已授权边界；不会据此要求编造 Skill 或教程。未发现新增超范围业务页面、用户版本管理或国内任务审核流程；新增持久表、发布 gate 和恢复接口服务于明确授权的隔离/恢复要求。

## Stage 1：联合发布隔离与恢复

| 条目 | 本轮证据与结论 |
| --- | --- |
| 候选 API/网关不接纳外部业务 | `joint_studio_private_config.py` 与 `joint_studio_ingress.py:44-109` 检查回环监听、无 host port、私有 nginx；实际本机 Docker 隔离 smoke 返回 private_network_blocked=true。 |
| 所有后台先等待 gate | `joint_studio_gate_wiring.py:11-15,20-64` 对七容器/七 native 明确接线；`backend/app/execution/release_gate.py:44-58` 阻塞 Celery worker_init，retention/deletion、三 outbox、variant、海外导入循环接线存在。真实 Redis/Celery 测试证明闭门不消费、开门后消费；Docker smoke background_gate_verified=true。 |
| socket 自 bind 起 000 | `backend/app/execution/credential_broker.py:71-81` bind 前 umask 0777，之后按 gate 决定权限；`backend/tests/test_release_gate.py:95-109` 实际捕获 bind 后立即权限，本轮通过。 |
| 对外业务请求最后开放 | `joint_studio_ingress.py:248-289` 正式入口健康/源码身份/台账核实后恢复 socket，开 workers 并验活，最后开 ingress；`backend/app/execution/release_gate.py:61-78` 只允许指定 GET 健康。真实进程 SIGKILL 与 ASGI gate 测试、本机 Docker public_request_gate_verified/public_readiness 均通过。 |
| gate 身份/持久化与失败 seal | `joint_studio_paths.py:23-49` root0755/0644 单链接、原子写后 fsync；`joint_studio_ingress.py:197-215` seal 先关入口，再按需 drain、停后台、最后关 worker gate。完整发布故障/重复恢复测试通过。 |
| 迁移与前向恢复 | `joint_studio_engine.py:35-81` 备份校验、0032→0043 与海外 schema 不变；`joint_studio_fence.py` 等待实际迁移子进程/事务；`joint_studio_forward.py:10-65` 禁止强杀停止及前向启动。401 项发布测试中真实隔离迁移、备份/还原、失败事务保持 0032、成功升级 0043、保留原数据断言均通过。 |

## Stage 2：质量、安全与测试真实性

1. **结构/类型通过，既有长度债务单列。** `output/review-r14-scan.json` 扫描全部变更运行代码，未发现新增 `as any`/`: any`；新国内模块、共享前端与联合发布模块均不超过 300 行。唯一超过标准的是既有 `hengxin-smart-image/scripts/migration245/unify_release.py:1-644`：HEAD 638 行，本轮 644 行，增量为固定 socket 常量、pass_fds 和启动前后回调（`:48,164,503`）。记为 **MEDIUM、既有非阻断债务**，不声称满足 300 行标准；不要求在本次发布前重构整个已复用发布脚本。新增恢复逻辑已独立到 116 行的 credentials 模块。
2. **安全扫描通过，没有确认的新增安全问题。** 未发现硬编码密钥、前端 VITE 密钥、开发者绝对路径、动态执行用户字符串或 SQL 拼接。两个命中已核实：`frontend/src/views/shared/studio/StudioMarkdown.vue:1` 的 v-html 来源于 `studio-markdown.ts:3-27`，禁用 HTML、转义属性、只允许 http(s) 外链且加 noopener；`backend/app/overseas/studio/recovery_transport.py:23-30,69` 的 eval 为固定 Redis Lua，数据单独作为 KEYS/ARGV。与 [markdown-it 官方安全说明](https://github.com/markdown-it/markdown-it/blob/master/docs/safety.md) 和 [Redis EVAL 文档](https://redis.io/docs/latest/commands/eval/) 对照一致。共享 Markdown/图片保护测试在本轮前端套件中通过。
3. **权限与数据保护通过。** 以真实 HTTP/PG 两身份校验服务端所有权和超管权限；归档完整性测试使用破坏记录和对象路径验证 fail closed。不是只检查菜单隐藏。`test_domestic_studio_http_pg.py:46-75`、`test_domestic_admin_permissions_pg.py`、`test_domestic_archive_integrity_pg.py` 本轮执行通过。
4. **故障测试具有真实前提。** 新 credentials 测试使用实际 UID 65534、进程、Unix socket、SIGKILL；gate 测试实际使用 Redis/Celery；sandbox 测试实际使用 Bubblewrap 与 CLI stub；迁移实测使用独立 PG。明确替身边界：HTTP 测试替换身份和对象存储，发布编排测试替换 systemd/Docker 操作，SIGKILL gate 测试的 HTTP 健康是替身；本机 Docker smoke 独立补足容器回环/网络隔离，但不等于生产 systemd 全链故障演练。
5. **视觉对比通过。** 本轮实际打开确认预览与正式组件页面，320/489/490/799/800/1920 六宽度比较 toolbar、标题、按钮、composer、session 的位置/高度/字体，测量值一致。实际查看 `output/review-r14-preview-1920.png`、`review-r14-formal-1920.png`、`review-r14-formal-320.png`，浅色 Art 外壳、按钮/留白/输入框匹配；差异仅为测试消息和正式取回入口、预览标识等有意状态差异。320/490/799 实际打开取回、归档并进入成品库。浏览器为本地正式组件＋受控 API 替身，不是生产登录证据。

## 原始验证输出与边界

本轮执行的完整原始日志位于 `output/review-r14-*`。关键输出如下，均为实际执行结果，不以旧报告代替：

```text
# output/review-r14-release-full-configured.log
401 passed, 9 subtests passed in 29.75s

# output/review-r14-backend.log
76 passed, 1 skipped, 1 warning in 61.87s (0:01:01)

# output/review-r14-runtime.log
37 passed, 1 warning in 43.10s

# output/review-r14-frontend-test.log
ℹ tests 564
ℹ suites 0
ℹ pass 564
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 14354.4464

# output/review-r14-compile.log
PYTHON_COMPILE_PASS 207
BASELINE_UNIFY_LINES 638

# output/review-r14-build-domestic.log
✓ built in 46.55s

# output/review-r14-build-overseas.log
✓ built in 34.69s

# output/review-r14-private-docker.log
{"status": "PASS", "private_network_blocked": true, "background_gate_verified": true, "public_request_gate_verified": true, "public_readiness": true, "test_resources_remaining": 0}
```

`vue-tsc --noEmit` 退出码 0，无类型错误；`output/review-r14-typecheck.log` 原始输出仅两条 npm 配置弃用提示：

```text
npm warn Unknown project config "package-manager-strict-version". This will stop working in the next major version of npm. See `npm help npmrc` for supported config options.
npm warn Unknown project config "manage-package-manager-versions". This will stop working in the next major version of npm. See `npm help npmrc` for supported config options.
```

已解释的测试过程差异：第一遍发布全套遗漏测试 MINIO 环境变量，真实 native fence 子进程配置初始化失败，原始 `review-r14-release-full.log` 保留 1 failed/400 passed。按交接给定变量补齐后 fence 组 3 passed，再完整运行得到上述 401+9；未改产品代码。76 项后端组的 1 skipped 是未配置独立 Redis 的归档恢复测试，后续 runtime 组配置 `127.0.0.1:35440/13` 后重跑归档组，37 项无跳过。浏览器五入口第一版替身漏传 archiveId/reopened/completed，客户端正确拒绝；补齐与真实响应一致的 fixture 后五入口全部通过，未修改应用。

`git diff --check` 退出码 0，仅现有 CRLF→LF 提示。前端构建有 outDir 位于项目根外的提示（输出定向到 output），不是编译错误。没有删除非本轮资源；Docker smoke 自查剩余测试资源 0。

## 候选外部署助手只读审查

以下输出目录助手不属于 candidateId 批准范围，其当时 SHA256 单列在 `output/review-r14-helpers-sha256.json`，本轮仅静态审查，没有执行安装/上传/激活/部署：

- `output/domestic-studio-release-bin/build_committed.py:16-74` 从明确 HEAD commit 制作三 scope 包，校验清单、字节摘要、scope/commit、隐私模式；`install_committed.py:19-65` 对照 Git blob 生成 inactive 工具目录并记录 hash。
- `run_server_helper.py:13-52` 只允许命名 helper，检查当前 commit 与安装/包记录；`server_verify_tools.py:13-40` 与 `server_verify_candidate.py:13-41` 在执行前验证 root 身份、受控路径、完整清单与摘要。
- `server_installed_checks.py:29-54` 对 inactive 工具跑隔离测试、Docker 清理与私有入口 smoke；`server_publisher_smoke.py:22-101` 使用无网络只读测试容器、检查真实 UID socket，并只清理其随机测试资源。
- `upload_and_stage.py:43-71` 校验本地/远端摘要后复用 stage；`server_activate_tools.py:27-57` 在既有发布锁下核对空闲台账、运行快照再切换受管工具链接。
- `server_joint_release.py:10-34` 检查 active 工具、三 scope 和同一 commit，复用已安装 joint CLI prepare/deploy，再 verify/status；没有自动强制恢复或自动回滚旧数据库的分支。

这些助手必须在中文提交生成新 HEAD 后使用；本次未对旧 HEAD 制作或执行发布包。两阶段 PASS 允许主 Agent 继续同快照的提交与授权部署，**不表示已上线，也不替代安装后身份/权限测试、真实正式入口与版本核对。** 初始真实 Skill/教程由用户后续提供；当前没有外部模型效果验收。主 Agent 完成生产核验后再宣称上线。

## 提交前空白差异复核附录

- 新 candidateId：`d0dddef585e7d7889764e449ec53cda0eb6b5dcfba9d3f89175e6b8eaa77324b`。**Stage 1：PASS；Stage 2：PASS。** 本附录为新快照的独立差异复核结论，取代正文旧编号作为当前批准目标。
- 直接比较 harness 中已批准的 R14 快照与新 candidate 文件摘要，仅 `hengxin-smart-image/backend/tests/test_domestic_late_outputs_real_minio_pg.py` 变化，证据 `output/review-r14-whitespace-delta.json`；没有其它受控代码变化。
- `git diff` 对照旧暂存版本确认只删除该文件 `:272-273` 的两个 EOF 空白行，最后有效代码仍为 `:271` 的 `proxy.close()`。文件 273→271 行；去除末尾空白后字节内容相等，Python compile 通过。没有测试前提、执行路径或断言变化，原两阶段证据继续适用，无需重复功能回归。
- 历史 Markdown 报告的输出行末空格清理不属于受控代码快照，不影响上述结论。review-status 实测 currentId 等于新编号。主 Agent 应为新编号及更新后的本报告重新登记批准，不沿用旧批准凭据。
