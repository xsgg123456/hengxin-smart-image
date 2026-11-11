# 内网历史版本名称保护增量审查

日期：2026-11-11。使用 `.agents/skills/code-review/SKILL.md`，先 Stage 1，后 Stage 2。

- candidateId：`db983d1ec16eb1a0958f5a557c1e62f28a36584070aae43c818dfedfbf444b1e`。
- **Stage 1：PASS；Stage 2：PASS。无 HIGH / MEDIUM 问题。**
- 本次独立增量范围：`scripts/release/intranet/stage.py`、`scripts/release/intranet/test_stage_web.py`；源合同 `docs/INTRANET-RELEASE-TOOLS.md:56`，授权上游 `Product-Spec.md:1482`、`DEV-PLAN.md:1694`。
- 未变部分继承 [最终完整审查](INTRANET-RETENTION-FINAL-20261111.md:1) 中 candidate `1973e99b4ccf98ecaba8debb65e5bc11186af554d78298209ea4956e6df58ae7` 的两阶段逐项证据和明确限制。此报告只批准实现及隔离验证，不代表线上激活、存量删除或净释放已经完成。
- Reviewer 未修改实现、未提交、未登记审批、未操作线上；仅写本报告。

## 快照与继承边界

独立 `review-status` 确认当前为本报告新 candidate。读取前报告全部合同表、质量表和验证边界后，将当前 candidate 的文件摘要字典中仅 `stage.py`、`test_stage_web.py` 两项替换为各自 HEAD blob 摘要，再按 harness 的 `review_files.digest/identity` 计算，结果严格等于上述旧 PASS candidate。未改磁盘文件或审查状态。原始输出：

```text
RECONSTRUCTED_BASELINE 1973e99b4ccf98ecaba8debb65e5bc11186af554d78298209ea4956e6df58ae7
ONLY_TWO_CONTROLLED_FILES_CHANGED_CONFIRMED
```

因此不是仅依据主 Agent 声明继承：旧报告全部受控实现和测试均未变；两文件的 `git diff` 就是本次完整受控增量。普通 Markdown 不纳入 harness 快照，已另行读取合同自动保留两版段及 Spec/计划末尾授权。新增合同为禁止复用已发布名称，与下面实现一致。

继承前报告 Stage 1 每一项：成功发布后清理及失败隔离、预览/显式执行、共用锁与基线检查、非 deploy 操作不清理、当前/上一前后端并集、native/二进制、全部容器及父挂载、进程全部引用、mountinfo、全部 systemd UnitPath 配置及别名、无法检查即停止、依赖/权限/清单保护、历史识别、删除前重查及 fd 安全、部分删除重试、不复制及排除范围、兼容静态资源、私有计划回执、同范围净释放、不改业务台账及隔离覆盖。各项实现路径/行号和验证证据逐项保留在前报告 Stage 1 表。交付阶段待执行条目同样继承，未冒称已完成。

## Stage 1：Spec Compliance

| 条目 | 结论及证据 |
|---|---|
| 旧目录清理后不得复用发布名称 | 完整实现。`stage.py:16` 接收历史集合，`:20`–`:22` 在打开归档及创建目录前拒绝命中路径；`test_stage_web.py:49` 确认目录实际不存在，传入不存在归档仍得到专用拒绝错误，且目录未生成。 |
| 实际 CLI 持锁读取历史并传入解包 | 完整实现。`stage.py:67`–`:69` 在真实 store 锁内执行 `Release.load()`、`cleanup_history.known()` 和 unpack；`test_stage_web.py:58` 使用真实 Store，重入锁失败证明锁已持有，断言历史返回值确实传给 unpack。 |
| 历史与清理识别保持同一来源 | 完整实现。`cleanup_history.py:12`–`:15` 合并 source_history/current/previous，`:17`–`:57` 识别摘要绑定的旧 applied 事务；`stage.py:68` 直接复用。额外独立探针以真实台账文件、真实 load/known/main、真实锁运行，旧目录不存在时仍拒绝，没有打开归档或创建目录，输出见下文。 |
| 新名称与原解包安全行为 | 完整实现。`stage.py:17` 名称校验、`:24` 防覆盖、`:26`–`:53` 归档与摘要检查均保持；`test_stage_web.py:39`、`:79`、`:89` 有效包、防覆盖、越界、symlink 回归通过。 |
| 部分实现、未实现、Spec 漂移 | 无。增量仅增加合同约定的历史名称拒绝及测试；`stage.py:60` CLI 无新增业务页面/API/表。 |
| UI、引导真实性、设计一致性 | 不适用。两文件为既有发布 CLI 与测试，无 UI 或设计变化；`:22` 拒绝提示准确对应已实现检查。 |

Stage 1 无 HIGH 问题，进入 Stage 2。

## Stage 2：Code Quality

| 维度 | 结论及证据 |
|---|---|
| 命名、结构与大小 | PASS。`stage.py:16` 的 used 是只读成员检查，默认不可变 tuple；复用既有历史模块，未重复识别算法。stage 78 行、test_stage_web 145 行，均低于 300。无 TypeScript any 适用项。 |
| 错误处理与安全 | PASS。历史无法读取/校验时由 `stage.py:68` 向外抛错，`:74`–`:78` 明确拒绝；新检查在任何解包写入前。新增代码没有删除调用、外部 shell、字符串执行或凭据。对两文件扫描 eval/exec、shell=True、innerHTML、前端 KEY/SECRET/TOKEN、API key 前缀、password 赋值无命中（rg 返回 1）。 |
| 测试真实性 | PASS。`test_stage_web.py:49` 使用真实不存在目录；`:58` 用真实 Store 验锁，只有历史解析和 unpack 为替身。为覆盖该替身边界，reviewer 另以真实磁盘台账、真实 Release.load/cleanup_history.known/unpack 跑 CLI，主机身份及安全权限边界使用隔离替身；实际拒绝旧名称且无候选写入。未声称该探针验证了生产 root 权限。 |
| 未变质量和删除安全 | 继承前报告 Stage 2 全表；由上述完整快照重建证明相关受控文件未变化。 |
| 视觉对比 | 不适用，无页面/组件/样式变更，未冒称打开页面验证。 |

## 验证原始输出

Reviewer 独立运行：

```text
.\hengxin-smart-image\backend\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider scripts/release/intranet hengxin-smart-image/scripts/migration245/test_unify_release.py -q
ssssssssssssssssssssssssssssssssssssssss.........................
...........................................................              [100%]
84 passed, 40 skipped, 7 subtests passed in 12.39s
```

40 项跳过仍为 Linux 特有权限、symlink、/proc 和 fd 删除测试，见 `test_cleanup.py:21`、`test_cleanup_refs.py:12`；未用 Windows 通过替代 Linux 删除验证。

读取主 Agent 提供的新不可变安装候选 `/opt/hengxin-intranet-tools/releases/db926bde69b81916` 的测试日志 `output/intranet-retention/linux-tests-final.log:1`：

```text
............................................................................................................................              [100%]
124 passed, 7 subtests passed in 2.88s
```

这是主 Agent 提供的 Linux 执行证据，不是 reviewer 连接线上执行的结果。Reviewer 另外以 `compile(path.read_bytes(), str(path), 'exec')` 编译全部内网工具 Python 文件，不生成 pycache：

```text
COMPILE_OK 16 Python files
stage.py 78 lines
test_stage_web.py 145 lines
REAL_LEDGER_HISTORY_CLI_REUSE_REFUSED_WITHOUT_WRITES
```

批准登记必须使用本报告的新 candidateId 和两阶段 PASS；由主 Agent 调用 review-approve，并继续完成工具激活、授权存量清理和净释放/服务数据身份验收。旧报告不能直接批准新快照。
