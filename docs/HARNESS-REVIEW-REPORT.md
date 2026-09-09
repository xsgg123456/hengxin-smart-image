# Harness 独立审查报告

日期：2026-09-09。candidateId：`dbda170a01fa1c4bd31bdb72c467a8abd502983781c2a776a816c89c87c105ed`。

**Stage 1：FAIL（2 项 HIGH、1 项 MEDIUM）。Stage 2：未执行。禁止据此登记 PASS。**

## 范围与版本证据

依据 `docs/HARNESS-REVIEW-PLAN.md:5`、`docs/HARNESS-REVIEW.md:5` 和 `.agents/skills/code-review/SKILL.md:22`。范围为 `.codex/hooks/harness.py`、新增 `review_gate.py/review_files.py/review_store.py`、三个测试文件、`.gitignore`、AGENTS、README、开发/修复/审查技能和 `.codex/agents/code-reviewer.toml`。不审产品功能或 UI。`git diff -- .codex/hooks.json` 输出为空。

审查后只读调用 `validate(root,state)`、`snapshot(root)`、`status(state,current)` 得到：

```text
currentId=dbda170a01fa1c4bd31bdb72c467a8abd502983781c2a776a816c89c87c105ed
candidateId=dbda170a01fa1c4bd31bdb72c467a8abd502983781c2a776a816c89c87c105ed
reviewedId=null
approved=false
```

未发现送审期间快照变化。真实 CLI `review-status` 未成功：子 Agent 对 `.codex` 仅有读取权限，`harness.py:141` 无条件 bootstrap 在读取前触碰 signals；原始错误：

```text
Harness hook failed: [Errno 13] Permission denied: 'D:\\Work_Project\\hengxin-smart-image\\.codex\\evolution\\signals.jsonl'
```

## Stage 1：功能逐项核对

| Spec 条目 | 结论与证据 |
| --- | --- |
| 1. prepare 固定候选；approve 同编号、同内容、两阶段 PASS、仓库内报告哈希 | 完整实现。`review_gate.py:30`、`:33`、`review_store.py:43`；真实 Git 回归 `test_review_gate.py:86`、`:93`、`:140`、`:164`。 |
| 2. status/Stop 保留批准、指出差异；旧 clean 无效 | 批准保存与差异完整实现：`review_gate.py:8`、`:13`、`:54`，`test_review_gate.py:69`、`:75`、`:103`。只读语义存在 MEDIUM，见 M1。 |
| 3. index 对 HEAD 的变化匹配 approval；拒绝复合脚本、-a、路径提交 | 部分实现。快照比对正确：`review_gate.py:72`；索引错版、部分提交、删除、提交后 Stop 见 `test_review_gate.py:184`、`:193`、`:206`、`:230`。Shell 入口存在 H1/H2，能绕过约束。 |
| 4. checkpoint 一次、绑定快照、不授权提交 | 完整实现。`review_gate.py:45`、`:58`、`:72`；`test_review_gate.py:216`、`:224`。 |
| 5. 配置/技能规则纳入，生成物/普通报告排除，CRLF 归一，其它空白受控 | 完整实现。`review_files.py:15`、`:36`、`:115`；`test_review_gate.py:114`、`:124`、`:132`，`test_review_recovery.py:78`。符号链接内容读取而非追踪，父目录安全检查 `review_files.py:101`。 |
| 6. 初始 dirty、不可信旧状态、暂存分离、故障路径、旧类型检查/推送保护 | 已列回归通过；Shell 漏洞用例缺失，故整体部分实现。初始 HEAD 基线 `review_store.py:140`，损坏严格校验 `:60`；相应用例 `test_review_gate.py:51`、`:57`、`:61`、`:65`、`:169`。完整 56 项日志见下。 |
| 7. 同步框架说明、保持 hook、独立审核与新凭据登记 | 文档同步实现：`AGENTS.md:103`、`.agents/skills/dev-builder/SKILL.md:83`、`bug-fixer/SKILL.md:32`、`code-review/SKILL.md:48`、`.codex/agents/code-reviewer.toml:23`、`README.md:63`。本次审查失败，登记尚不可进行。 |
| CLI JSON 参数及接口 | 已实现 `harness.py:199`、`review_gate.py:21`、`:54`、`:72`；CLI 只读权限限制见 M1。 |
| 原子写、串行锁、超时不删他人锁 | 完整实现 `review_store.py:92`、`:107`；真实并发与超时测试 `test_review_recovery.py:91`、`:123`。 |
| 报告失效阻断、可重新 prepare/approve、恢复不放宽状态结构 | 完整实现 `review_gate.py:26`、`review_store.py:60`；`test_review_recovery.py:24`、`:51`、`:68`。 |
| UI/设计、引导真实性、Spec 漂移 | 无 UI 改动，视觉项不适用；README 声称拒绝复合脚本与实际不一致，归入 H1。新增模块属于框架 Spec，未发现额外产品功能。 |

## HIGH：提交入口未满足安全要求

### H1：消息参数中的 Shell 子表达式可在检查后重新暂存

位置：`.codex/hooks/harness.py:103`。Spec `docs/HARNESS-REVIEW.md:11` 要求拒绝复合脚本，避免预检查后改变暂存内容。当前 parser 对 `-m` 的下一个 token 直接跳过，因此双引号中的 `$()` 被当作普通消息。

隔离临时 Git 仓库前提：HEAD 为 app.py v1，批准并暂存 v2，工作区修改为未审 v3。只调用实际 `handle('pre-tool-shell', ...)`，待测命令作为数据，没有执行提交：

```text
git commit -m "$(git add app.py)复合提交"
root_count=1 result=None
```

`None` 表示门禁放行。PowerShell 会执行双引号内的子表达式，所以真实 Shell 执行时先暂存 v3，再提交 v3，预检看到的 v2 无法约束实际提交。PowerShell 行为依据：[Microsoft about_Quoting_Rules](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_quoting_rules?view=powershell-7.6)。这发生在同一次被允许的工具调用，属于本次 Spec 明确要求防止的边界，不是外部进程竞态。

修复要求：提交命令必须拒绝可执行插值/命令替换以及参数值中的动态 Shell 表达式；增加上述 index/worktree 分离的入口回归，覆盖消息和其他允许带值选项。

### H2：合法紧凑 Git 全局参数导致整段检查跳过

位置：`.codex/hooks/harness.py:56`、`:163`。两个 parser 前缀只识别 `-C` 后有空白，`git -C. commit` 不产生目标仓库，因而连 `commit_mode_error` 都不会调用。

同一隔离仓库，仅调用真实入口的结果：

```text
git -C. commit -am 未审提交
root_count=0 result=None
```

这里不仅缺少索引验证，也跳过 `-a` 拒绝与类型检查。Git 的 `-C` 是有效的全局工作目录参数，见 [Git 官方命令文档](https://git-scm.com/docs/git)。修复应支持合法参数形式，或对检测到 commit 但无法可靠解析的 Git 调用明确拒绝，不能静默跳过。增加紧凑 `-C`、`-c` 和未支持全局选项的回归。

## MEDIUM：M1，review-status 并非真正只读

位置：`.codex/hooks/harness.py:141`、`.codex/hooks/review_gate.py:26`、`.codex/hooks/review_store.py:142`。Spec `docs/HARNESS-REVIEW.md:16` 明确“只读显示”，但 CLI 先创建/触碰 evolution 文件，transaction 创建锁并每次重写状态。批准字段虽未变化，实际需要写权限，导致独立 reviewer 的只读上下文无法调用协议规定的 status。应提供只读状态路径，不触碰 evolution 或重写审查凭据，增加只读/无状态变更验证。

## 验证原始输出

主 Agent 完整离线验证日志已逐项读取，来源 `output/harness-review-validation.log:74`：

```text
----------------------------------------------------------------------
Ran 56 tests in 54.125s

OK
PASS: offline harness checks. Runtime discovery/trust: inspect Codex /hooks and /skills.
```

reviewer 独立运行七个受审 Python 文件的 `py_compile`，缓存指向排除的 output 目录。编译器无 stdout/stderr，退出结果：

```text
py_compile exit_code=0
```

上述通过不能覆盖 H1/H2：现有回归未包含这些可达输入。Stage 1 有 HIGH，按技能要求停止，**Stage 2 代码质量、全面安全扫描和视觉审查未执行**。修复后需重新 prepare，以新 candidate 重新从 Stage 1 审查；本报告不能批准后续快照。
