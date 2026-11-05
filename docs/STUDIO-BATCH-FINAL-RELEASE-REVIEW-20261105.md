# 批量标注发布范围独立复审

日期：2026-11-05。candidateId：`3f9cbe9feb82fd582b56cd1cdedae3f855273ed99c9400be8e0ce7ddc733604a`。

范围：`scripts/release/studio-batch-*.py`、`scripts/release/test_studio_batch*.py`、`docs/STUDIO-BATCH-RELEASE-PLAN-20261105.md`，并追踪实际调用的既有发布 helper。依据：`docs/STUDIO-BATCH-ANNOTATION-20261105.md` 实施顺序第 5 项和发布计划全部步骤、恢复约定。业务功能/UI 由另一 reviewer 审查，本报告不重复验收。

**Stage 1：FAIL。Stage 2：未执行。** 上轮 R1 的暂停 consumer 识别和 R2 的前端源码绑定已修复，但恢复流程在第二次调用时仍会被旧状态凭据阻断。不能据本报告登记两阶段 PASS。没有修改代码、提交或操作生产。

## Stage 1：HIGH 问题

### HIGH R3：已验证 native 的停机恢复不可重入

- 要求原文：发布计划第 74 行“停止两native单元、恢复原始源码并实际重启校验”；第 75 行“保留no-SIGKILL保护并等待真实inactive”；第 76 行覆盖“outbox已停而worker尚存等中间状态”。
- 真实路径：native 安装成功产生 `NATIVE_START_STARTED`、`NATIVE_INSTALLED`、`NATIVE_VERIFIED`；随后 rollback，或 API 切换前 recover，调用 `studio-batch-recovery.py:73` 的 stop_native。停机期间超时、工具退出或进程中断，旧 `NATIVE_VERIFIED` 没有失效。至少一个 unit 的 PID 从已验证 PID 变为 0，是预期的停机结果。
- 阻断一：重试入口 `studio-batch-recovery.py:43` 先调用 state；`studio-batch-deploy.py:20` → `sku-deploy.py:29` → `sku-native.py:54` 仍将所有 native PID 与旧 `NATIVE_VERIFIED` 严格比较，第 56 行拒绝已停止的 PID。尚未进入恢复的 `settled`，因此即使 pending stop 已结束也无法恢复。
- 阻断二：outbox 已停、worker 尚存且合法保护文件仍存在时，`studio-batch-recovery.py:39` 再次调用 `sku-native.stop`；`sku-native.py:103` 对同一保护文件 `open('x')`，直接 FileExistsError。即使修复阻断一，这个状态仍不能继续排空/停止 worker。
- 验证：临时目录创建本流程实际产生的 markers、native 源码与保护文件，真实调用 `sku-native.guard` / `sku-native.stop`；只替换 systemd PID 查询、保护文件目标路径和 Celery 传输，无生产命令。原始输出：

```text
ROLLBACK_RETRY_AFTER_NATIVE_STOP: Restarted native PID drift
SECOND_NATIVE_STOP_WITH_RETAINED_PROTECTION: FileExistsError
SYSTEMCTL_CALLED: False
```

- 影响：API 已关闭，恢复要求等待的 stop 真正结束以后仍被永久门禁挡住，不能按文档恢复接纳。不能靠删除恢复凭据或撤销 no-SIGKILL 保护解决。
- 修复验收：明确记录恢复停机阶段，使正常验证 PID 与恢复中的 PID 规则分离；识别并复用字节完全一致的本轮 stop 保护，拒绝异物；pending job 仍保留保护且不开放 API。测试须从真实 state/guard 入口覆盖 native 已安装验证、outbox 单独停止、双 unit 最终停止和重复恢复调用。

### HIGH R4：恢复源码已落盘、凭据尚未转换时中断，后续恢复入口拒绝旧源码

- 要求原文：发布计划第 74–75 行要求恢复原始源码、保留原始备份并处理中断。
- `studio-batch-native.py:65` 先 `shutil.copy2` 写回旧源码，第 68–72 行才移动 `NATIVE_PATCH_STARTED` / `NATIVE_INSTALLED` / `NATIVE_VERIFIED`。在复制成功至移动 marker 之前中断，是可达状态。
- 重试依旧先走 `sku-deploy.py:29` 的 guard。`sku-native.py:47–48` 看到 `NATIVE_INSTALLED` 就要求当前字节等于新源码；恢复已经写回的合法旧字节因此报 `Native installation incomplete`。实际 restore 第 64 行允许新/旧两种合法字节，但入口门禁阻止到达这里。
- 验证：临时目录使用真实 native 文件、真实 digest 和 guard，模拟旧字节已恢复而上述 markers 尚存；原始输出：

```text
RESTORE_RETRY_AFTER_COPY_BEFORE_MARKERS: Native installation incomplete
```

- 修复验收：恢复写入前持久化可验证的恢复阶段，门禁仅在该阶段允许 manifest/备份所绑定的合法旧或新字节；保持备份校验与路径集合约束。为“旧文件已落盘、marker 尚未转换”注入故障，再从真实 recover/state 入口重试。恢复文件写入本身也应避免中断留下既非旧哈希亦非新哈希的半文件。

## Stage 1：逐项对照

下表“匹配”表示源码/本地验证符合计划，不代表生产部署已执行。

| 合同/计划条目 | 结论 | 证据与验证方式 |
| --- | --- | --- |
| 0.2.63→0.2.64、0026 不迁移、固定镜像基线 | 匹配 | `studio-batch-runtime.py:11`、`:12`；`studio-batch-deploy.py:23`、`:30`、`:34`；`polling-database.py:65` 仅备份/隔离恢复。范围回归通过。 |
| API 五模块、native 仅 image_edits | 匹配 | `studio-batch-runtime.py:13`、`:15`；`:70` 拒绝额外 API；`studio-batch-native.py:34` 精确路径和文件集合校验。 |
| 步骤 1：干净固定提交、正式包要求审查 | 工具匹配；提交/批准待主 Agent | `studio-batch-package.py:20–26` clean 和 reviewed_status；`:68–71` 再核对；`package-delivery.py:70` 拒绝非 approved。dirty candidate 回归通过。 |
| 步骤 2：allowlist、递归依赖、隐私、全文件 hash | 匹配 | `studio-batch-package.py:31–55` 来源逐项比对/隐私扫描/递归测试依赖；`:65` 全文件 SHA；`studio-batch-runtime.py:57–76` 完整文件集合、路径/符号链接、helper/API 集合和摘要验证；包篡改回归通过。 |
| 步骤 2 / 上轮 R2：前端必须来自固定 commit | 已修复 | `studio-batch-build.py:18` git archive；`:28` 全新临时目录；`:46` 禁 tracked dist；`:57–63` 锁定工具版本、frozen lock 安装和真实生产 build；`:64–74` 源码/产物复核与 commit/tree/lock/hash 证据。`studio-batch-package.py:56` 不读工作区 dist；`studio-batch-runtime.py:78–83` 核对包内 provenance。4 个隔离构建回归通过；pnpm 传输在测试中是替身，不冒充实际生产构建。 |
| 步骤 3：prepare 不切换，继承实际 Compose | 匹配 | `studio-batch-deploy.py:27–70` 只构建候选/保存快照；`account-runtime.py:92–110` 保留实际配置路径、顺序、校验和及原 env 来源；deploy 第 59–62 行 overlay 仅 image 且对比完整 config。保留 prior overlay 回归通过。 |
| 步骤 3：镜像实际路径/默认身份、只读挂载、独立 PG | 工具匹配；生产镜像安装测试待执行 | `sku-deploy.py:116–141` 独立 network none PG、容器共享其网络、只读 `/app/tests`、`PYTHONPATH=/app`、不传 --user、无生产 env-file；`:106–108` 必须 passed 且无 failed/skipped；`:138` 绑定 image/manifest。`STUDIO-BATCH-RELEASE-PLAN-20261105.md:45` 明确 UID10001 目录遍历要求。 |
| 步骤 4：先检查在途/导入、停 API 后重查、暂停 consumer | 匹配 | `studio-batch-deploy.py:78–94` 明确顺序；`:87` Docker --time -1、调用端 60 秒；导入竞态、超时不继续、成功顺序回归通过。 |
| 步骤 4：native 禁 SIGKILL、outbox 先停、统一 60 秒 | 正常首次停机匹配；恢复重入失败 | `sku-native.py:13`、`:96–127` 设置并验证 SendSIGKILL=no/TimeoutStopUSec=infinity，统一 deadline，outbox 先停；R3 为重入缺口。 |
| 步骤 4：私有备份、隔离恢复、逐表/schema 一致 | 工具匹配；生产 dump/restore 待执行 | `polling-database.py:19–27` gate/排空/0026；`:30–61` 独立 PG 恢复及 fingerprints/schema/revision 对比；`:65–82` 私有目录、完成凭据；`:85–94` 安装前再次核验。 |
| 步骤 5：原始 native 备份、原子替换、真实身份探针 | 正向安装匹配；恢复中断失败 | `studio-batch-native.py:18–44` 不覆盖原备份、独占临时文件和 replace；`:45–53` 真实服务身份编译/语义探针和启动核验；`:96–115` 实际安装路径执行新/旧 payload 提示词；`sku-native.py:180–185` UID999/cwd。4 个 native 回归通过；R4 是恢复路径缺口。 |
| 步骤 6：native 验证后只切 API、即时网关刷新 | 匹配 | `studio-batch-deploy.py:107–119` old API 停止、备份/native 验收后 --no-deps up，再 refresh；相应命令顺序回归通过。 |
| 步骤 6：保留环境、其他服务、Skill | 匹配 | `sku-deploy.py:29–35` native、Skill 及其他容器保护；`studio-batch-deploy.py:128–134` API/native 环境、国内/海外 ready；`sku-native.py:36–64` 配置及其他源码保护。 |
| 步骤 6：保留 hash 资源、入口备份、最终公网字节 | 匹配 | `sku-frontend.py:28–68` 保留旧资源、备份入口、原子复制；`studio-batch-deploy.py:145–161` 本地全前端 hash 和公网 HTML/入口 JS/CSS 实际字节比对。生产未执行。 |
| 步骤 7：正式入口 1920/1440/390、交互与历史、不收费生成 | 待主 Agent 生产验收 | `STUDIO-BATCH-RELEASE-PLAN-20261105.md:26` 明确；`studio-batch-deploy.py:162` 明确仍需浏览器验收。本发布脚本范围无新 UI，不以脚本检查替代页面验收。 |
| candidate 仅 prepare/test，不得 gate/recover | 匹配 | `studio-batch-deploy.py:19–24` release mode 门禁；候选 gate 与两种恢复拒绝回归通过。 |
| 上轮 R1：pause 成功后、gate 未写、outbox 已停 | 已修复所报初次 gate 路径 | `studio-batch-worker.py:12–20` 固定 node/PID/pool/队列；`studio-batch-recovery.py:14–18` status 选 paused/idle；`:45–50` 补 gate，`:6–11` pending job 拒绝；`:22–27` 先恢复 native/consumer。`test_studio_batch_partial_gate.py:41` 实际调用 worker CLI、identify/idle；7 个回归通过。已验证 native 的后续回滚仍见 R3。 |
| 入队竞态先恢复 consumer/native，再开放 API | 匹配所测路径 | `studio-batch-recovery.py:61–71` partial patch 保留保护，否则先 resume_native，再 docker start 和 refresh；真实 worker CLI 的 raced import 回归通过。 |
| 切换前恢复、切换后回滚；无 DB 回灌 | 部分实现 | `studio-batch-recovery.py:72–96` 正常单次顺序匹配，不含数据库恢复命令；R3/R4 阻断中断后的重试。 |
| Spec 漂移 | 本范围未发现额外业务能力 | `studio-batch-runtime.py:13–21` 仅既定 API/native/测试范围；`studio-batch-deploy.py:174–175` 仅发布计划的操作。构建/worker adapter 是上述发布要求的实现。 |

## 验证原始输出与边界

本 reviewer 执行 `python -m unittest discover -s scripts/release -p 'test_studio_batch*.py' -v`，32 个用例逐个 `ok`，结尾原文：

```text
----------------------------------------------------------------------
Ran 32 tests in 1.572s

OK
```

对全部 8 个 studio-batch 工具和 5 个 test_studio_batch 模块，以 `compile(path.read_bytes(), str(path), 'exec')` 做不写 pyc 的语法编译，原文：

```text
COMPILE_PASS: 13 files
```

这些绿灯不能覆盖 R3/R4。`test_studio_batch_partial_gate.py:80` 将 state 替换为 Mock；`test_studio_batch_recovery.py:86` 同样绕过真实 state，并于第 80 行 mock stop_native；`test_studio_batch_native.py:35` 用 Mock guard/start。因此没有验证恢复入口会接受上一调用留下的合法中间状态。此为本次 Stage 1 缺陷定位所需的测试前提检查，不是 Stage 2 通过结论。

主 Agent 提供的其余测试数和真实隔离 frontend build 正在执行的消息，不作为本报告亲自验证通过的证据。未执行生产安装测试、备份恢复演练、切换或浏览器验收。

## 快照与阶段状态

开始检查时 harness review-status 的 currentId 等于本报告 candidateId，approved=false。本报告只新增普通 Markdown，不改变受控代码。报告完成时主 Agent 已派 worker 修复，末次 status 显示 currentId 为 `5a35269c5f30bfc52ec3dcbd0d31e5e1b9d11a5094b5b6c0f7301c7ae67725be`，并新增 `studio-batch-recovery-state.py`。本报告的结论、行号和复现均针对标题记录的原始 candidate，不覆盖这些后续修改。代码质量、安全扫描和视觉对比 **Stage 2 未执行**，原因是 Stage 1 存在 HIGH。修复后重新 review-prepare，用新 candidateId 从 Stage 1 复审，不能批准本快照。
