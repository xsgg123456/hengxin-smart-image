# Codex 海外 API 恢复验收脚本增量审查

日期：2026-10-19。审查者：独立 code-reviewer，使用 `.agents/skills/code-review/SKILL.md`。仅审查、执行本地测试及写报告，无实现修改、生产写入或服务重启。

## 快照、范围及结论

- candidateId：`93821a0c156617daca1bd8df6c5fd49397a33ff496029f5a012e7eafd0bb5a4a`。
- 前置已审快照：`b11247ee966582088d185f478decf2622ae5fda1a403e8ea9973a5478c05cef3`，报告 `docs/reviews/CODEX-AUTH-DUAL-20261019.md`。
- `review-status` 独立确认本次增量仅 `scripts/release/codex-auth-api-recover.py`、`scripts/release/codex_auth_api_semantics.py`、`scripts/release/test_codex_auth_api_recover.py`。本报告不重新批准前置产品范围，不把主 Agent 转述的实际出图当作 reviewer 独立实查。
- **Stage 1：PASS。Stage 2：PASS。无阻断 HIGH/MEDIUM。** 本结论批准脚本按冻结 Compose、旧镜像和固定发布身份补充语义验收的实现；实际部署完成还需成功运行该脚本并保存凭据。缺失原完整 inspect，无法证明原 raw hash 差异仅来自数组顺序。

## Stage 1：Spec Compliance

依据 `Product-Spec.md:1237`–`:1238` 和 `DEV-PLAN.md` 末尾“海外API追加发布”：仅更新海外 API 两个错误映射文件，保持其他容器及两域 worker；结合主 Agent 明确交接的只读恢复范围。以下路径均相对 `scripts/release/`。

| 本次验收要求 | 结论与证据 |
| --- | --- |
| 只接受本次旧/新容器和镜像 | 完整实现。`codex-auth-api-recover.py:21` 校验 prepared 中旧 ID、旧/新镜像，`:23` 限定 started，`:37` 校验实际新容器、镜像和 Running；常量见 `codex_auth_api_semantics.py:6`–`:10`。异域旧 ID 在 `test_codex_auth_api_recover.py:111` 拒绝且没有主机命令。 |
| 原冻结 Compose、安装清单和测试凭据仍有效 | 完整实现。`codex-auth-api-recover.py:24`–`:34` 校验包、manifest、镜像绑定测试凭据、配置文件摘要、唯一镜像 override 及固定原服务 hash；`:42`–`:45` 读取实际两个源码摘要并拒绝 `/app/` Python 文件层改动。原服务 hash 不是重新生成后自行接受的基线。 |
| 完整 Config/HostConfig 比较，只规范化无序字段 | 完整实现。`codex_auth_api_semantics.py:42`–`:88` 按冻结服务、旧镜像及明确默认值重建；`:95`、`:99` 比较整个字典，额外未知字段也拒绝。Env 映射去序，`:27`–`:31` 拒绝格式错误与重复键；`:97`–`:98` 仅排序 Binds/Mounts。其余命令、用户、标签、端口、资源、安全、健康等差异不被整体忽略。 |
| 挂载和网络保持 | 完整实现。`codex_auth_api_semantics.py:100`–`:104` 比较挂载目标、类型、来源、读写及网络名/别名；重复实际挂载目标拒绝。主机 Mounts/Binds 选项另受完整 HostConfig 相等约束。动态 IP、endpoint ID 不被宣称为历史恒等。 |
| API 健康，其他实例不变 | 完整实现。`codex-auth-api-recover.py:38` 查 healthy，`:46` 比较其他拓扑，`:47` 执行 ready 请求，`:49` 结束前再查容器 ID 及其他实例。原 `codex-auth-api.py:36` 同时记录两域 worker 的 cwd/PID。 |
| 不改失败基线、不重启、输出单独凭据 | 完整实现。`codex-auth-api-recover.py:17`–`:19`、`:50` 核验原准备/阶段/安装等文件摘要；唯一业务证据写入为 `:60` 的 `API_RECOVERY_VERIFIED.json`，未写 prepared.config、api-stage 或 API_FAILURE，未调用 switch。`:70` 仅打开发布互斥锁。`test_codex_auth_api_recover.py:73` 检查原文件字节不变及主机命令类别。 |
| 明确原始证据缺口，不掩盖 raw hash 失败 | 完整实现。`codex-auth-api-recover.py:54` 同时记原/观察摘要，`:58`–`:59` 明写原完整 inspect 缺失、确切差异字段未证明、补充凭据不能替代原摘要。不能据本次通过把原 raw hash 校验改称通过。 |

部分实现、未实现、Spec 漂移：本次范围无。UI/设计对比不适用：三个文件均为发布验证及测试，无页面或样式改动；没有宣称浏览器视觉通过。

## Stage 2：Code Quality

- 结构与错误处理：PASS。三个文件分别 76、104、120 行，验证编排、语义模型和回归分离；`codex_auth_api_semantics.py:44` 对未支持服务字段拒绝；主机命令由原 `codex_auth_runtime.py:39` 使用 argv 数组、捕获输出及超时，不拼 shell。
- 安全/脱敏：PASS。`codex-auth-api-recover.py:51`–`:59` 输出仅身份/摘要/固定说明，不输出完整 Compose、inspect 或 Env 值；语义失败为固定错误（`codex_auth_api_semantics.py:29`、`:31`、`:95`、`:99`）。独立注入环境秘密哨兵及安全参数漂移均拒绝，异常未含哨兵。没有新增密钥常量、动态 eval、SQL 或前端注入入口。镜像/容器 hash 属发布身份，不是凭据。
- 测试真实性：PASS，18 项覆盖顺序容忍、15 类实质差异、证据保留/不重启、错误发布身份。额外独立 3 项验证环境变化、重复键及安全字段变化均拒绝且不泄漏值。边界：测试 fixture 在 `test_codex_auth_api_recover.py:32` 使用生产 expected 函数构造 live，证明差异检测，不独立证明 Docker 的所有默认值；真实环境运行通过方能补足默认值与当前 Docker 的一致性证据。不得用 18 项测试替代生产运行凭据。
- 可复用性边界：脚本刻意固定此次镜像/容器、Compose 标签版本及 HostConfig 默认值（`codex_auth_api_semantics.py:6`、`:63`、`:70`），不作为通用跨版本恢复工具。未发现本次范围需要修复的问题。
- 视觉邻居对比：不适用本次发布脚本增量；未执行生产浏览器检查。

## 独立执行原始输出

命令：`hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q scripts/release/test_codex_auth_api_recover.py`

```text
..................                                                       [100%]
18 passed in 0.19s
```

逐文件 `compile(source, filename, 'exec')`（不写 pyc），另以秘密哨兵进行语义漂移探测：

```text
COMPILE_OK scripts\release\codex-auth-api-recover.py LINES 76
COMPILE_OK scripts\release\codex_auth_api_semantics.py LINES 104
COMPILE_OK scripts\release\test_codex_auth_api_recover.py LINES 120
REJECTED_WITH_SAFE_ERROR env-value Frozen API Config semantics differ
REJECTED_WITH_SAFE_ERROR duplicate-env Duplicate runtime environment key
REJECTED_WITH_SAFE_ERROR host-security Frozen API HostConfig semantics differ
INDEPENDENT_DRIFT_AND_REDACTION_PASS 3
```

`git diff --check` 退出 0，仅三个既有 Markdown 文件 CRLF→LF 提示。审查起始 `review-status` 原始输出：

```json
{"currentId":"93821a0c156617daca1bd8df6c5fd49397a33ff496029f5a012e7eafd0bb5a4a","reviewedId":"b11247ee966582088d185f478decf2622ae5fda1a403e8ea9973a5478c05cef3","changedFiles":["scripts/release/codex-auth-api-recover.py","scripts/release/codex_auth_api_semantics.py","scripts/release/test_codex_auth_api_recover.py"],"approved":false}
```

主 Agent 负责最终 `review-status`、对同 candidate 的 `review-approve` 及实际只读恢复执行。本 reviewer 不登记批准、不写 `.needs-review`。国内/海外真实图片与存储验收见 `docs/CODEX-AUTH-RECOVERY-20261019.md`；本 reviewer 仅阅读该记录，未独立执行其中生产请求。
