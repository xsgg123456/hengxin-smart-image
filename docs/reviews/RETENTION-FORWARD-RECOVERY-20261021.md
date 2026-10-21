# 三天清理发布前向恢复独立审查

- 最终 candidateId：`4f221d6033b84061122e77f7b85945ebd92c65b3533c3941aac6a71e7d68aab4`。
- 结论：**Stage 1 PASS；Stage 2 PASS**。无未解决的 HIGH / MEDIUM 问题。
- 范围：`scripts/release/retention-management-recover-switch.py`、`test_retention_management_recover_switch.py`、`retention-management-native.py`、`test_retention_management_native.py`。基线 HEAD 为 `bec8dd7`。仅审恢复流程与就绪超时修正，不重复宣称已验收业务 UI 或已完成生产恢复。
- 依据：`Product-Spec.md:1`、`docs/CLI-RETENTION-MANAGEMENT-20261021.md:20` 的实施顺序及前向恢复要求、对应 VALIDATION 文档、主 Agent 的固定故障现场交接、`docs/HARNESS-REVIEW.md:7`。
- 快照变化：初始 `4379bdb56949209a66093b180f1855d65fd2b948ec43f131bcf23c5c4538ce8b` 审查期间，生产只读预检发现已启动 worker 的两张心跳表变化，使原迁移后全表指纹检查拒绝恢复。主 Agent 修改为仅豁免心跳内容、保留其他保护，并重新固定上述最终候选。本报告 PASS 仅适用于最终候选；旧候选不能据此批准。

## Stage 1：Spec Compliance — PASS

| 范围内要求 | 结论与证据 |
|---|---|
| 限定已经核实的 switch 故障，不重放完整发布 | 完整实现。恢复脚本 `:10` 固定 bec8dd7；`:35` 校验 release/phase/error、迁移与排空标记、未清理/未验证/未恢复；`:131` 限定命令参数。`test_retention_management_recover_switch.py:58` 覆盖错误阶段和重复恢复拒绝。 |
| 原包及已安装版本可信 | 完整实现。恢复脚本 `:87` 调用原 runtime.validate；`retention-management-runtime.py:16` 校验发布、迁移、前端版本和全文件 hash；恢复脚本 `:42` 核对安装测试镜像与 PREPARED，`:53` 校验 native 后端 hash，`:65` 核对已更新三容器和仍停止的两个原 producer。 |
| 备份已验证、迁移保留业务数据和调度 | 完整实现。恢复脚本 `:44` 确认0032与暂停；`:48` 要求 COMPLETE；`:21` 比较业务指纹、表集合、列与精确调度，仅允许 `api_worker_heartbeats`、`worker_heartbeats` 内容变化。两表定义是运行状态，见 `backend/app/modules/api_image_edits/heartbeat_models.py:9`、`backend/app/worker/models.py:7`（均位于 hengxin-smart-image 子目录）。`:50` 调用 migrated 确认未伪造清理观察记录。新增测试 `test_retention_management_recover_switch.py:83` 验证心跳允许、业务/列/调度变化拒绝。 |
| 入口关闭、清理停止、native 策略与环境不漂移 | 完整实现。恢复脚本 `:46` 验证入口关闭；`:54` 要求三单元工作目录正确、两个清理 PID 为0；`:58` 对照原 native 快照的策略、argv、环境，仅忽略四个 systemd 瞬态变量；`:73` 检查无关服务、挂载、配置及海外版本。 |
| 实际就绪检查允许超过20秒且保持超时边界 | 完整实现。恢复脚本 `:77` 用原 READINESS、当前工作目录/环境执行45秒检查，并确认同一 PID；`retention-management-native.py:132` 保留总120秒截止，`:144` 单次上限45秒。原探针校验实际 Celery 节点、队列、并发及72小时常量。测试见 `test_retention_management_recover_switch.py:69`、`test_retention_management_native.py:135`、`:154`。 |
| 发布前端 → 首扫 → producer → 开放 → 台账 | 完整实现。恢复脚本 `:89` 先 native 和 API 就绪；`:95` 发布并验证前端；`:99` 在可能删除前先写屏障；`:101` 启动两清理并验证真实首扫/native；`:105` 启动 producer、校验安装；`:108` 解暂停，`:110` 开放并公开验证，`:113` 写发布记录。顺序回归见测试 `:32`，原合同见 `retention-management-deploy.py:59`。 |
| 失败保留数据与回执，不回滚数据库 | 完整实现。恢复脚本 `:117` 写阶段错误并关闭入口；finally 内逐个温和停止清理，失败落 STOP_REQUIRED。没有旧 DB restore、降级、回执删除或重放迁移调用。成功仅将原故障记录重命名存档（`:115`），写 VERIFIED。故障注入测试 `:44` 覆盖首扫、installed、开放失败。 |
| 接回原发布生命周期 | 完整实现。恢复脚本 `:136` 调用原 `release-retention.managed`；该 helper `:57` 对 recover 要求原 pending.before、持锁运行，只有恢复返回成功后才写成功凭据并推进台账（`:37`、`:107`）。 |
| UI、提示真实性与范围漂移 | 本次无 UI、文案、API、数据库结构变化；仅恢复已经批准的发布。视觉对比不适用，不能把本报告作为新的页面视觉验收。四文件 diff 与候选范围吻合。 |

部分实现/未实现：范围内未发现。上述表格逐项覆盖本次恢复交接要求；业务页面和72小时业务规则本身沿用基线审查，本次未重新执行其全部验收。

生产证据由主 Agent 只读实查提供，reviewer 未连接生产：原指纹差异仅 API 心跳7→8行、CLI心跳1→1行，其他旧表精确一致；最终恢复脚本原字节 SHA256 为 `ed3b6588b5507634caca5b2e68aaa39fd905745267d30b80debf03f8c8b98a77`，原包完整 manifest 校验通过，原始输出：

```text
RECOVERY_PREFLIGHT_PASS ed3b6588b5507634caca5b2e68aaa39fd905745267d30b80debf03f8c8b98a77
```

该证据只说明预检成功，尚未执行 recover，不代表真实首扫、公开入口与正式管理页已完成验收。

## Stage 2：Code Quality — PASS

- 质量：恢复脚本136行、native151行、对应测试99/165行，均低于300行。恢复脚本按 preserved/preflight/ready/recover 分工（`:21`、`:35`、`:77`、`:86`），复用原受校验 helper；只有恢复状态及45秒探针是新增逻辑。
- 安全：恢复脚本 `:79` 使用固定参数数组调用 subprocess，无 shell=True、eval、用户 SQL 拼接或硬编码秘密；`:133` umask0077，写入沿用 private；环境只用于运行探针，不打印。固定 `/opt` 路径属于本次明确限定的服务器合同。失败处理 `:117` 不恢复旧数据库、不擦除清理回执。未发现新增安全问题。
- 测试真实性：独立运行恢复、native、deploy、verify、drain及发布台账测试127项全部通过，真实 PostgreSQL 测试未跳过。恢复编排/故障测试使用替身验证顺序，不冒充生产删除实测；心跳豁免测试确实对业务、列、调度分别注入变化并要求拒绝。完整生产 preflight 为主 Agent 提供的独立实查证据。
- 视觉对比：无前端变更，本次不适用；未打开业务页面，不声称已做视觉验证。
- `git diff --check` 退出0、无输出。编译使用 Python compile 读取四个候选文件，不运行恢复入口；输出如下。

## 独立测试与编译原始输出

使用 `hengxin-smart-image/backend/.venv/Scripts/python.exe`，`TEST_DATABASE_URL` 指向授权的本机65435隔离 retention_test 库。测试文件：test_retention_management_recover_switch、native、deploy、verify、drain，以及 test_release_retention、cli、failures。

```text
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 3.59s
retention-management-recover-switch.py: compile OK
retention-management-native.py: compile OK
test_retention_management_recover_switch.py: compile OK
test_retention_management_native.py: compile OK
```

最终核对 review-status 的 currentId 为本报告候选。由主 Agent 使用同一 candidateId 登记两阶段 PASS；本 reviewer 未写 clean、未修改代码、未执行生产恢复、未批准其他快照。
