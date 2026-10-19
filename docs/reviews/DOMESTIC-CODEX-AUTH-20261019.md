# 国内 Codex 认证修复独立审查（旧候选，未批准）

- 日期：2026-10-19。
- candidateId：`81afaca4b8ced93f72e755fa21b7d3fffdfaecb371464f320663d9ec42733613`。
- 范围：`hengxin-smart-image/backend/app/execution/{managed_credentials.py,managed_credentials_files.py,workspace.py}`、`app/modules/api_image_edits/{conversation_runner.py,conversation_errors.py}`；对应四个专项测试文件；`scripts/release/domestic-auth-deploy.py`；Spec、DEV-PLAN、CHANGELOG 增补。
- 已读取 code-review skill、HARNESS-REVIEW 协议及 Spec 末节原文。开始及结束的 `review-status` 均返回上述 currentId；本次审查期间未观察到代码快照变化。
- 主 Agent 在审查期间通知用户扩大范围至海外共同修复，要求停止出 PASS、后续新快照重新审查。本报告只记录原候选，不覆盖海外扩展版本，不构成发布授权。

## Stage 1：FAIL

### HIGH：旧会话 auth.json 缺失时可静默换账号

Spec `Product-Spec.md:1227` 明确要求：“原账号/工作区发生变化时拒绝静默续接旧会话。”

实际实现仅以私有 `auth.json` 保存的身份作比较：`managed_credentials.py:184` 允许文件不存在，`:86`–`:88` 对 `previous is None` 直接返回。`conversation_runner.py:131`–`:139` 已知旧会话编号时仍调用同一个同步入口，只要求 sessions 中有旧会话文件，没有要求该旧会话的原凭据或独立身份锚点存在。因此旧会话文件保留、私有 auth.json 被删除/丢失、主登录换账号时，会先写入新账号凭据，再继续原会话。

无网络、临时目录实测：构造保留旧会话文件的 home、缺失私有 auth.json，主凭据为另一账号，直接调用真实 `sync_credentials(source, home, 600)`。退出码 0，原始输出：

```text
existing_session_preserved= True
accepted_account= new-workspace
missing_private_auth_rejected=False
```

修复验收：已有会话必须具备可验证的原身份；缺失身份资料应失败并提示管理员恢复，不能把“缺文件”当新会话。新会话仍允许首次写入。增加真实 runner 旧 session + 缺失 auth + 主账号变化的回归，并证明 execute 未调用。现有 `test_managed_credentials.py:114` 覆盖已有文件内身份缺字段/不同账号，但未覆盖整个私有凭据文件缺失。

### Spec 逐项核对

| Spec | 当前证据及结论 |
|---|---|
| 1226：仅国内、会话/输入/历史/正式图片不变，不自动重放或采用 | 代码范围符合：`conversation_runner.py:121`、`:154` 保留原 session，`:177` 单次 execute，`:90` 仍只设置 candidate；专项 `test_api_conversation_auth_errors.py:19` 验证失败 currentVersion 保持 1。生产历史文件不变尚仅为主 Agent 提供的证据，本 reviewer 未实查生产。 |
| 1227：独占刷新、跨进程锁、按时长预刷新、原子写入、私有不含刷新令牌、身份连续性 | 部分实现。`managed_credentials.py:179`–`:196` 锁内重读、timeout+300、剥离 refresh；`managed_credentials_files.py:51`–`:65` 原子替换；身份连续性有上述 HIGH。POSIX 并发测试本轮 Windows 跳过，不能据此宣称 Linux 跨进程实测通过。 |
| 1228：拒绝链接/非普通文件、0600、脱敏、有界刷新、失败不重发 | 实现证据：`managed_credentials_files.py:10`–`:33`、`:80`–`:104`；`:44`–`:45` / `:58`–`:65` POSIX 权限与持久化；`managed_credentials.py:101`–`:135` 有界子进程、固定错误；`conversation_runner.py:207` 只公开平台异常。专项覆盖硬链接、刷新失败、原子失败、超时和脱敏。Windows 跳过符号链接项及 POSIX 项，生产路径边界需 Linux 实证补齐。 |
| 1229：认证/超时/日志超限/其他退出分别提示，不改失败历史 | `conversation_errors.py:18`–`:50` 固定白名单提示，`:42`–`:47` 优先真实停止原因；`conversation_runner.py:184`–`:186` 接入。专项真实 runner 验证认证失败；历史批量更改逻辑未新增。 |
| 1230：专项、独立审查、安装测试、排空备份、真实图片候选与正式版保持 | 专项本轮执行结果见下；独立审查 FAIL。部署脚本 `domestic-auth-deploy.py:74` 起安装凭据检查及维护排空仅作静态阅读，未执行生产。安装测试/正式切换/真实图片修改仍由主 Agent 后续验收，不得以本报告代替。 |

UI 一致性：本候选没有页面布局、样式、组件变更；固定错误文案通过 runner/API 专项检查。本次未执行真实浏览器验证。

Spec 漂移：旧候选差异未增加页面、API 或数据库表；新增脚本及认证模块对应本轮合同。用户新要求海外覆盖不在本候选的正式 Spec 或实现范围内，需要新快照审查。

## 独立验证原始结果

在 `hengxin-smart-image/backend` 执行：

```text
.venv/Scripts/python.exe -m pytest tests/test_managed_credentials.py tests/test_api_conversation_auth_errors.py tests/test_api_cli_conversation.py tests/test_execution_workspace.py -q
..........................sss...s......s................................ [ 98%]
s                                                                        [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
.venv\Lib\site-packages\starlette\testclient.py:53
  DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
67 passed, 6 skipped, 2 warnings in 6.18s
```

退出码 0。跳过包括生产 POSIX flock 并发测试与本地无权限的符号链接测试，不能把跳过算通过。未执行编译命令，不声称编译验证通过。

## Stage 2：未执行

Stage 1 发现 HIGH，按 skill 停止 Stage 2。未给出代码质量、安全扫描、邻居页面视觉验收 PASS。由主 Agent 修复并对扩展范围重新 `review-prepare`、交 fresh reviewer 从 Stage 1 开始；不得对本候选执行两阶段 PASS 登记。
