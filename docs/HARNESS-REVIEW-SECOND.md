# Harness 独立审查报告

日期：2026-09-09。candidateId：`4681e4002a717f04ab96b5b1b63763470ce07e1f4c64cc0737cf895080c4b132`。

审查范围：相对 HEAD 的 AGENTS.md、README.md、.gitignore、三个开发/修复/审查 SKILL.md、reviewer TOML、harness.py、review_gate.py、review_files.py、review_store.py 和三个 test_*.py。包含尚未跟踪的新模块。源规格为 docs/HARNESS-REVIEW-PLAN.md 与 docs/HARNESS-REVIEW.md。产品代码、hooks.json 未变化。使用 code-review skill；本任务是框架基础设施，不用产品 Spec 替代源规格。

最终核验 review-status 的 currentId 与上述候选相同，reviewedId 为 null、approved 为 false。审查期间源协议补充了保守命令说明，不改变受控代码快照。输出复现脚本位于 output/reviewer_case_probe.py，不纳入候选。未修改代码或凭据、未在真实仓库提交。

## Stage 1：FAIL

### HIGH H3：Windows 可执行文件大小写使未审提交完全跳过检查

规格：docs/HARNESS-REVIEW-PLAN.md:9 要求“提交前检查暂存内容”，:13 要求“不降低未审代码提交检查”。

实际：.codex/hooks/harness.py:56 的提交识别、:93 的提交模式识别以及 :173 的无法解析兜底均只匹配小写 git/exe。Windows 的合法 `Git commit`、`GIT.EXE commit` 因此没有 targets，也没有 deny，直接返回 None；暂存检查和类型检查都没有执行（:176）。这不是绕过 Codex 的普通终端场景：直接给 pre-tool-shell 提交命令即被放行。

独立真实临时 Git 仓库复现：创建并提交 app.py=print(1)，改成 print(99) 并暂存，未 prepare/approve；同一状态依次调用 hook。随后仅在该临时仓库通过 Git 大写命令实际提交。

原始输出（中文 deny 原因因控制台编码显示乱码，以下保留可读决策字段）：

```text
git commit -m test => {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', ...}}
Git commit -m test => None
GIT.EXE commit -m test => None
actual uppercase Git commit returncode: 0
HEAD: print(99)
```

复现证据：output/reviewer_case_probe.py:8（准备未审内容）、:11（调用真实 hook）、:13（临时库实际执行）、:15（读取 HEAD）。修复应统一可执行文件的大小写识别，并为这些实际可执行命令加入交互层回归；不要对整个命令盲目忽略大小写，Git 的 -C/-c 含义不同。

### 源规格逐项核验

| 条目 | 结论 | 实现及运行证据 |
|---|---|---|
| 1 快照与候选、阶段、报告绑定 | 完整实现 | review_gate.py:31、:34 检查 candidateId/current/stages；review_store.py:43 校验仓库内真实非空报告并计算哈希。change_during_review、new_prepare、failed_or_missing_stage、missing_and_external_reports 用例通过。 |
| 2 Stop/检测保留批准、列出差异、旧 clean 无效 | 完整实现 | review_gate.py:13、:54；harness.py:39 只查询状态；review_files.py:11 排除遗留状态。approval_survives_repeated_stop、status_preserves_previous_approval、legacy_clean 用例通过。 |
| 3 索引匹配、禁止隐式暂存、普通提交不失效 | 部分实现，HIGH | review_gate.py:72 正确比较 HEAD/index/approved；harness.py:90 白名单拒绝 -a/路径/复合脚本。index_old_version、partial_commit、reviewed_index_commit 用例通过，但 H3 绕过整个入口。 |
| 4 单次 checkpoint、原因、修改失效、不能提交 | 完整实现 | review_gate.py:46、:58；check_commit 不读取 checkpoint。两个 checkpoint 用例通过。 |
| 5 受控文件及归一化 | 完整实现 | review_files.py:15 纳入配置/框架规则并排除报告、运行产物；:115 使用 Git 文件清单；:36 仅归一 CRLF；:101 防止读取仓库外路径。config_and_framework、ignored_generated、crlf、skill_reference 用例通过。 |
| 6 临时库覆盖及旧保护 | 指定覆盖通过，但不充分 | test_review_gate.py:18 创建真实隔离 Git 仓库；三个测试文件共 59 项独立通过。test_harness.py:231 验证暂存门禁，:251 后测试编译器成功失败，:282 后验证推送保护。H3 不在原测试覆盖内。 |
| 7 框架文档同步、注册不变、独立审查后登记 | 文档完成，交付未达标 | AGENTS.md:103、dev-builder/SKILL.md:83、bug-fixer/SKILL.md:32、code-review/SKILL.md:48、code-reviewer.toml:23、README.md:63 已切换协议；git diff 未含 hooks.json 或产品代码。因 H3 不允许登记通过。 |
| CLI JSON 参数及 stdin 接口 | 完整实现 | harness.py:212 处理 argv/stdin，:147 路由四种动作；独立 review-status 调用返回正确 JSON。 |
| run/stop/check_commit 输出契约 | 完整实现 | review_gate.py:13、:21、:54、:72；上述 59 项测试覆盖输出及异常路径。 |
| baseline/candidate/approved/checkpoint 存储、原子串行、报告哈希 | 完整实现 | review_store.py:60 严格结构校验，:92 临时文件+fsync+replace，:107 排他锁串行，:134 从 HEAD 初始化。损坏凭据、报告失效恢复、并发等待和锁超时用例通过。 |
| status 只读、迁移、报告变化失败及恢复 | 完整实现 | harness.py:148 绕过 bootstrap；review_store.py:145 无写入或锁创建；status_performs_no_writes 用例通过。review_recovery.py:23 保留旧凭据直至新批准；删除/修改报告恢复用例通过。 |
| 协作门禁边界、UI、漂移 | UI 不适用；未见产品范围漂移 | 源规格 :3、:23；git diff 仅框架范围。报告恢复和锁等待服务于既定凭据协议。H3 属于明确支持的 Windows 入口缺陷，不属于外部进程竞态边界。 |

### 上轮缺陷复核

- H1：harness.py:99 拒绝 `$`、反引号、换行与重定向；test_harness.py:210 的回归包含命令替换，独立运行通过。原复现已封堵。
- H2：harness.py:56、:74 解析紧凑 -C；:173 未识别全局参数显式拒绝；test_harness.py:220 紧凑 -C 的未审/已审两分支通过。原复现已封堵。
- M1：harness.py:148 与 review_store.py:145 实现只读状态；test_harness.py:48 用禁止 bootstrap/write/os.open 的桩核验初始化前后都通过。独立真实 review-status 成功。最初沙箱无法启动本机 Python 是进程权限，不是 status 写权限。

### 独立运行结果

运行命令：Python 3.12 `-B -m unittest discover -s .codex/hooks -p test_*.py -v`，Node PATH 指向 D:/Apps/nodejs。测试中的 Git 提交只在 TemporaryDirectory 中进行。

原始结尾输出：

```text
----------------------------------------------------------------------
Ran 59 tests in 57.191s

OK
```

所有 59 项通过，包括真实注册的 Windows 生命周期命令用例；该用例附 Git 行尾转换 warning，未失败。额外 H3 探针证明现有绿色测试不能代表完整提交门禁达标。

## Stage 2：未执行

Stage 1 存在 HIGH，按 skill 停止。未作 Stage 2 全面代码质量、安全扫描或独立编译认证；没有以主 Agent 的编译日志替代本人执行。UI/视觉对比不适用。

不允许 review-approve 此候选。修复 H3、重新固定候选后，重新从 Stage 1 开始独立审查。

版本后记：报告写入后，主 Agent 通知已修改 harness.py 和测试文件以修复 H3。上述最终快照核验发生于该修改之前；本报告仅覆盖列出的旧 candidateId，不评价也不批准通知中的新代码。按主 Agent 要求报告保存为 HARNESS-REVIEW-SECOND.md。
