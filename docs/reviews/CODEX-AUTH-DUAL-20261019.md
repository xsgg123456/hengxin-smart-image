# 国内与海外 Codex 认证独立审查

日期：2026-10-19。审查者：fresh code-reviewer。使用 `.agents/skills/code-review/SKILL.md`。只审查及写报告，未修改实现、提交、执行生产切换或调用模型。

## 快照与结论

- 初始 candidateId：`84d8feca0a6f74f81bc9ea3dde1840c57640d9445e8f953061bd7e0f0d8dcb87`。
- 最终 candidateId：`b11247ee966582088d185f478decf2622ae5fda1a403e8ea9973a5478c05cef3`。
- 审查中主 Agent 修改国内 `conversation_runner.py` 和 `test_api_conversation_auth_errors.py`，修复下述 MEDIUM；本报告已对新内容重新核对并复跑相关回归。DEV-PLAN 增补发布顺序与最新真实验收约束，已读取。
- **最终 Stage 1：PASS（本次代码实现范围）。Stage 2：PASS。** 无未解决 HIGH/MEDIUM。此结论不等同生产发布及真实图片验收完成；待办单列。
- 最终快照须由主 Agent 用 `review-approve` 登记，本报告不修改 `.needs-review`。

范围：本次 git diff 和新增文件，包括 `backend/app/execution/{managed_credentials,managed_credentials_files,credential_identity,credential_broker,credential_broker_client,credential_errors,workspace}.py`、共享配置、国内图片修改 runner/errors、海外 runner/events/studio execution/management monitor、相关专项测试；`scripts/release/codex-auth-deploy.py`、`codex_auth_runtime.py`、`codex_auth_worker.py`、`codex-auth-api.py`、`codex_auth_api_smoke.py` 与两套发布测试。下文 `app/`、`tests/` 均相对 `hengxin-smart-image/backend/`。

## Stage 1：Spec Compliance

需求依据：`Product-Spec.md:1224` 国内认证恢复、`:1232` 同账号海外追加（逐条如下）；`DEV-PLAN.md` 末尾执行与发布增补。无前端、布局或设计稿改动。

| Spec 条目 | 结论与代码/验证证据 |
| --- | --- |
| 1226：会话、输入、历史与正式图片保持；不重放、不自动采用 | 完整实现。`app/modules/api_image_edits/conversation_runner.py:122` 读取原 session，`:157` 使用 resume，`:180` 单次 execute，`:91` 仅设置候选。`tests/test_api_conversation_auth_errors.py:20` 校验失败时无候选、当前正式版本不变；`:72` 验证换账号拒绝续接。真实生产历史保持另列发布验收。 |
| 1227：主凭据独占刷新、锁内重读、预刷新、原子写入、私有无 refresh | 完整实现。`app/execution/managed_credentials.py:173`–`:197` 锁内读取、执行时长加 300 秒、剥离 refresh 并限制返回字段；`managed_credentials_files.py:51` 原子 replace/fsync，`:111` 有界跨进程锁。`tests/test_managed_credentials.py:56` 期限边界、`:229` POSIX 多进程只刷新一次；broker 并发见 `tests/test_credential_broker.py:87`。 |
| 1227：账号/工作区变化拒绝续接 | 完整实现。`managed_credentials.py:66` 同时约束 account/subject 与 access/id token 身份，`credential_identity.py:19` 比较；`:40` 保存独立身份绑定。`tests/test_credential_identity.py:67` 验证删除/改写模型可写私有凭据仍不能换账号。 |
| 1228：文件链接/普通文件/0600、日志脱敏、有界刷新、失败保留旧文件、不重发 | 完整实现。`managed_credentials_files.py:10`、`:20` 拒绝硬链接/非普通文件与 no-follow，`:80` 逐级目录检查；`:36`/`:51` 权限与原子写入。`managed_credentials.py:108` 禁重定向、有界读；`:130` 子进程总时限 30 秒，秘密仅 pipe 传递。`:199`/`:237` 固定安全异常；专项覆盖链接、网络、写入失败及脱敏。 |
| 1229：认证/超时/日志超限/非零退出区分，不伪造历史 | 完整实现，初审遗漏已修。`app/execution/credential_errors.py:16` 只认执行器错误事件/认证 stderr，`:37` 平台停止原因优先；国内 `conversation_runner.py:186`、`:191` 覆盖非零退出与 exit 0 失败事件；`conversation_errors.py:7` 固定中文。`tests/test_api_conversation_auth_errors.py:14` 覆盖 exit 0/1 × 三种认证形态，并校验正式图片。无历史批量改写代码。 |
| 1230：专项回归、审查、安装、排空备份及真实候选验收 | 代码及隔离验证完成；发布和真实图片验收未完成。安装输出已读取，见证据节；`scripts/release/codex-auth-deploy.py:55` 绑定安装标记，`:102` 排空后切换。真实候选不得由单测替代。 |
| 1234：两域用户/业务目录/数据库/Skill隔离，不复制 refresh 实现共享 | 完整实现。`scripts/release/codex_auth_runtime.py:15` 分域 UID/路径，`:125` drop-in 不覆盖 User/Group，独立设置 broker 环境；`app/overseas/execution/runner.py:94`、`:121` 与 `app/overseas/studio/execution.py:40` 均禁旧 auth 拷贝并派发前同步。未更改数据库、Skill、工作目录挂载。 |
| 1235：Unix socket、两 UID 白名单、锁内刷新、沙箱不挂 socket、通信限额 | 完整实现。`credential_broker.py:22` SO_PEERCRED，`:28` 白名单先于凭据读取，`:52` socket 目录/权限和并发上限，`:72` 活跃 socket 不替换；`credential_broker_client.py:9`–`:55` 请求 128/响应 131072 字节、总时限 75 秒；`:71` 拒绝 refresh 和短效响应。`workspace.py:68` 沙箱清空环境，`:95` 起只挂指定系统/私有目录，无 socket/主凭据/control 挂载。 |
| 1236：control 绑定、旧会话身份缺失/变化拒绝、新会话可初始化 | 完整实现。`credential_identity.py:40`–`:62` 限定 home 同级 control、独立锁和身份文件；绑定不存在且旧凭据缺失时 fail closed；已有绑定不信任重写的私有身份。国内 `conversation_runner.py:136`、海外 `runner.py:124` 传 require_existing；`tests/test_credential_identity.py:38`、`:45`、`:51`、`:59` 覆盖缺失/迁移/变更/恢复，`tests/test_overseas_credentials.py:119` 覆盖真实 runner 阻止派发并保留 session。原国内报告 HIGH 已关闭。 |
| 1237：两域备份排空切换、分域真实图片验收、禁止自动采用/历史伪造 | 排空与切换代码完整，生产验收待办。`codex_auth_worker.py:18` 真实 PID/node/pool/queue 核验，`:51` cancel consumer、两轮稳定、数据库 idle 后仅停目标 worker；失败按阶段保留证据，未自动恢复凭据/数据库。`codex-auth-deploy.py:12` 保存原服务及源码清单，`:102` 分域切换、`:135` 新进程验证。真实恢复备份/业务哈希须由主 Agent 发布证据确认。 |
| 1238：所有海外入口安全中文、读取端 API 更新、其余服务不变 | 完整实现。`app/overseas/execution/events.py:8`、`:22`、`:37`、`:45` 写入/列表/事件双向允许列表；`management/monitor.py:25` 同映射；现有 `studio/queries.py:75`/`:105` 读取已安全持久化的 job/event。`runner.py:140`/`:167` 统一失败代码，覆盖工作台和通用协议。`codex-auth-api.py:13` 仅两文件派生镜像、`:57` 完整 Compose 链、`:156` --no-deps/--no-build，`:134` 校验其他服务。监控公开接口独立 12 用例通过。 |

完整实现：上述代码项。部分实现/未实现：代码范围无；生产切换及真实图片为尚未执行的发布验收，不能算成已验证。Spec 漂移：未新增业务页面、表或业务 API；凭据代理和两文件海外 API 发布均在追加授权内。

### 审查中修复的 MEDIUM

初始快照国内 `conversation_runner.py:190` 对 exit_code=0、turn.failed 认证事件只显示“本轮执行或最终回复不完整”，不符合 Spec 1229。独立复现将现有三种认证用例的假执行器出口改为 0，结果 `3 failed, 2 warnings in 2.42s`；正式图片仍受保护。

主 Agent 修复为 `conversation_runner.py:191`–`:195` 对明确认证证据使用固定认证提示，测试 `test_api_conversation_auth_errors.py:14` 参数化 exit 0/1。新 candidate 相关 44 项通过；此问题已关闭，旧 candidate 结论不用于批准新版本。

## Stage 2：Code Quality

- 代码结构：PASS。32 个改动 Python 文件均不超过 300 行，全部语法编译通过；认证存储、身份、broker 服务/客户端、错误映射及发布职责分开。`managed_credentials.py:173`/`:207` 为主入口，`credential_identity.py:40` 管身份边界。无新增依赖/前端类型变更。
- 安全：PASS，未发现本范围可复现的密钥泄漏、命令/SQL 注入或绕过账号连续性。`managed_credentials.py:135` 使用 argv 数组且凭据走 stdin；`codex_auth_runtime.py:39` 无 shell=True，`:125` node 正则验证；`codex_auth_worker.py:31` SQL 为固定查询。全范围危险模式扫描无命中；OPENAI_API_KEY 出现为既有认证格式字段，CLIENT_ID 是公共 OAuth client identifier。生产绝对路径是指定发布目标，不是用户私密路径泄漏。
- 测试真实性：PASS。真实领域 runner/HTTP 查询用例断言未派发、同 session、无候选/正式版保持；凭据测试检查主文件旧字节、链接、身份缺失/被改写、时限与并发，未以“有测试文件”替代行为验证。`tests/test_credential_broker.py:214` 需要 root/Linux 的真实 UID 测试在本 reviewer Windows 环境跳过；Linux 安装输出由主 Agent提供，已查看，独立性边界见下。
- 发布故障/重复调用：PASS。`codex-auth-deploy.py:76`/`:102`、`codex-auth-api.py:148` 对已有阶段拒绝盲目重复变更；安装标记与 manifest/image 绑定；排空失败恢复旧 consumer，停服请求之后不猜测回滚，留 stage/FAILURE 供处理（`codex_auth_worker.py:74`、`codex-auth-deploy.py:185`）。37 项发布回归覆盖不明排空、运行漂移、错误阶段及不触碰其他服务。真实 systemd/Compose 操作仍须上线执行验证。
- UI/视觉：不适用本次代码对比。`git diff` 无前端、样式或组件变化，仅现有错误槽文案；本 reviewer 未打开生产页面，不声称邻居页面/实际图片视觉已验收。公开错误投影由真实 HTTP 专项和安装 smoke 覆盖（`tests/test_overseas_management.py:112`、`scripts/release/codex_auth_api_smoke.py:17`）。
- 无新增待修 HIGH/MEDIUM/LOW。

## 执行与编译证据

初始快照独立执行（backend 下）：

```text
.venv/Scripts/python.exe -m pytest -q tests/test_managed_credentials.py tests/test_credential_identity.py tests/test_credential_broker.py tests/test_credential_errors.py tests/test_api_conversation_auth_errors.py tests/test_api_cli_conversation.py tests/test_execution_workspace.py tests/test_overseas_credentials.py tests/test_overseas_runner.py tests/test_overseas_studio_execution.py
157 passed, 30 skipped, 2 warnings in 21.36s
```

最终快照差异复验及管理投影独立执行：

```text
.venv/Scripts/python.exe -m pytest -q tests/test_api_conversation_auth_errors.py tests/test_api_cli_conversation.py tests/test_credential_identity.py
44 passed, 3 skipped, 2 warnings in 6.35s

.venv/Scripts/python.exe -m pytest -q tests/test_overseas_management.py -k monitor_preserves
12 passed, 4 deselected, 2 warnings in 3.06s
```

发布测试（仓库根目录）：

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q scripts/release/test_codex_auth_deploy.py scripts/release/test_codex_auth_api.py
37 passed in 0.29s
```

编译采用 Python 对 git modified/untracked 的全部 `.py` 逐文件 `compile(source, filename, 'exec')`，不写 pyc；原始输出：

```text
PRODUCTION_SECURITY_PATTERN_MATCHES []
COMPILE_CHANGED_PYTHON_OK 32
CHANGED_PYTHON_ALL_AT_MOST_300_LINES
```

`git diff --check` 返回 0，无空白错误；只提示三个 Markdown 的 CRLF 将转换为 LF。两个 pytest warning 均来自既有 FastAPI/Starlette 的 httpx 与 anyio 弃用提醒。Windows 条件跳过涉及 POSIX/符号链接/真实 UID，不作为已独立执行的 Linux 证明。

主 Agent 提供的 Linux 安装原始文本已只读核对（非本 reviewer 独立启动）：

```text
output/codex-auth-fix/domestic-install-tests-v2.txt:13
138 passed, 2 warnings in 13.79s
output/codex-auth-fix/overseas-install-tests.txt:14
165 passed, 2 warnings in 27.91s
```

上述文件在 git ignored 输出目录；主 Agent 报告国内 v2 已重绑新 manifest，海外代码未变。本 reviewer 未实查生产 PID、安装清单摘要和日志来源，因此真实环境结论限于“读取了所提供的原始输出”，不以此代替生产验收。最终 `harness.py review-status` 观察 currentId 为本报告最终 candidate，未批准（批准由主 Agent 完成）。

## 发布验收待办（非代码缺陷）

1. 对最终 candidate 的安装清单、安装测试绑定及恢复备份完成生产只读核对；保存两域原 session/历史文件与正式图片摘要。不能复用旧 candidate 国内安装凭据。
2. broker 就绪后按各自排空证据切换两 worker，确认 UID、pool=5、node、源码、socket配置；完成原生 verify 后再派生并切换海外两文件 API，验证完整 Compose 链和其他服务未变。依据 `codex-auth-deploy.py:156` 和 `codex-auth-api.py:134`。
3. 按 DEV-PLAN 最新约束，国内保留用户当前正式 V2，提交新独立候选，不重放旧意见、不自动采用；海外已有会话独立完成真实图片交付。核对候选下载/预览、会话 ID、历史材料、正式图片及公开错误提示。Spec `1230`、`1237`、`1238` 的生产完成结论必须等这些证据到齐。
