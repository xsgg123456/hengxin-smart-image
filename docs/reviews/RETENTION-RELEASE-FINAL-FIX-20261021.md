# 国内三天清理发布助手兼容修复最终审查

- 日期：2026-10-21；独立 reviewer 按 `.agents/skills/code-review/SKILL.md` 执行。
- **最终 candidateId：`8f2c6c02113d2fc2c08d1cfed60c1a4ae57a91810ac2574090a13ad425c73ef7`。**
- 最初派发候选：`9645e747113b959f17f0208e78827ca12e10b8b9c3572e319fafc84885c2cde7`。审查期间主 Agent 修正测试独立运行需要的环境变量、Windows Path 比较和 private 写入 mock；已逐项复核，生产实现未变。主 Agent 重新提供上述最终候选。本报告的 PASS 仅授予最终候选。
- 基线：已审提交 `745b608`。范围为 `git diff HEAD` 的六文件：`scripts/release/retention-management-{deploy,drain,native}.py` 及 `test_retention_management_{deploy,drain,native}.py`；扩展只读追踪本发布实际调用的 backup、verify、runtime、API worker 验证及底层 helper。
- 原文依据：`Product-Spec.md:1`、`DEV-PLAN.md:1`、`docs/CLI-RETENTION-MANAGEMENT-20261021.md:1`、`docs/HARNESS-REVIEW.md:1`。本次修复不重新审查已审业务/UI实现，也不代表生产发布完成。
- **Stage 1：PASS。Stage 2：PASS。HIGH/MEDIUM 问题：0。**
- 仅进行了本地代码读取、隔离测试和报告写入；未连接、修改或运行生产服务。reviewer 不执行 review-approve，不写 clean。

## Stage 1：Spec Compliance

### 完整实现

| 本次适用要求 | 结论及证据 |
| --- | --- |
| 当前国内 schema 能执行排空查询，不能依赖退役 files | PASS。`scripts/release/retention-management-drain.py:18` 使用 `image_variants` 的 `api-image-edits` 域及 `api_image_files`；`:51` 与 `:79` 都使用此常量。与现行 `hengxin-smart-image/backend/app/modules/files/variant_worker.py:52` 的消费域、`variants.py:59` 的补登记条件一致。旧 `member-release-drain.py:34` 的 VARIANTS 仍存在于历史 helper，但本发布不调用它。隔离 PG 测试真实执行新 SQL。 |
| 保留执行保护，未知和未完成工作不能误报排空 | PASS。`retention-management-drain.py:14` 包括 CLI 非终态及 NULL；`:18` 包括未完成派生图、token、lease 及 ready 未删除却漏登记原图。`:41` 连续两轮同时确认 DB 及 broker 空闲；`:62` 先停清理、等待 CLI/派生图和 API 持久交接，再停止执行器并复核。`scripts/release/test_retention_management_drain.py:74` 证明计数依次为 0、1、0、1、1、1、3，PG 测试未跳过。 |
| 关闭入口前发现 schema 不兼容 | PASS。`retention-management-deploy.py:34` 在 DEPLOY_STARTED、gate.close 和停止任何服务之前执行两条查询。`test_retention_management_deploy.py:109` 注入 schema mismatch，证明没有启动标记，也没有关闭入口、停止服务或备份行为。 |
| 新原生 worker 的就绪验证不再导入已退役模块 | PASS。`retention-management-deploy.py:58` 改用 `n.ready(work)`；`retention-management-native.py:18` 真实导入 conversation_runner、credential_broker_client、HISTORY_AGE 和 celery_app，不再进入旧 native-verify 的 prompts 导入。`test_retention_management_native.py:112` 执行该完整 Python 字符串，仅 mock inspector；真实当前模块导入成功。上一报告 H1 已消除。 |
| 就绪验证确认三天规则和实际消费者 | PASS。`retention-management-native.py:22` 要求 259200 秒；`:24` 要求唯一 worker 的 pong、同一 node 的队列/统计、唯一 celery 队列及并发 5。`:132` 使用实际进程 cwd/env、codex 用户和目标解释器，单次 subprocess 最多 20 秒、循环预算 120 秒，成功时再次确认 MainPID 未变。`test_retention_management_native.py:112`、`:135`、`:153` 覆盖错误 ping/队列/并发、PID 改变和超时。 |
| 迁移前排空和可恢复备份，迁移后全部消费者及页面就绪，再启动清理 | PASS。`retention-management-deploy.py:38` 至 `:72` 保留 close→drain→backup→COMPLETE→migration→verify_after→native switch→API/worker→ready→publish/frontend→cleanup→first_scan 顺序。`test_retention_management_deploy.py:55` 验证主要顺序及生产者在首次扫描后恢复；`:73` 包含 ready 故障，证明失败不写 VERIFIED。 |
| 清理可能发生后不能恢复旧 DB 或抹去回执 | PASS。`retention-management-deploy.py:67` 在启动前落盘 CLEANUP_MAY_HAVE_DELETED；`:84` 失败记录阶段、关闭入口，并在该标记存在时暂停两项清理服务。没有恢复旧 DB、删除回执或降级 schema 分支。`test_retention_management_deploy.py:73` 的故障注入覆盖此行为。 |
| 复用 backup helper 无退役表硬依赖 | PASS（调用链静态核对）。`retention-management-backup.py:19` 动态枚举 public 表；`:54` 将 restore_check 所用 fingerprint 替换为本发布版本；`member-release-backup.py:114` 隔离恢复后调用替换后的指纹函数。`:63` 校验旧列/旧行及精确新表集合，只允许已批准的 next_cleanup_at 修改；`:12` 的预期调度与 `hengxin-smart-image/backend/migrations/versions/0032_retention_observability.py:49` 一致。未调用 overseas-runtime 的历史 baseline/backup。 |
| 复用 runtime/verify 无退役模块、表导致后续固定失败 | PASS（调用链静态核对及相关测试）。`retention-management-runtime.py:16`、`:28`、`:89` 分别核对本轮 manifest、0031 基线、0032 安装及72h常量；`:68` 验证海外/身份/无关进程保持。`retention-management-verify.py:21`、`:68` 仅使用新五表及当前 HTTP/原生状态。`domestic-deploy.py:36` 的 public_verify 只请求健康/配置/首页；历史 deploy/verify 函数未被本次调用。 |
| image-inputs-worker api-verify 仍能调用当前后端 | PASS。`retention-management-deploy.py:59` 调用 API 分支；`overseas-runtime.py:45` 将 helper 输送给 API worker 容器并重试；`image-inputs-worker.py:31`、`:40`、`:78` 在 api 分支导入当前 API celery/session、验证队列与并发后返回，不进入 `:90` 的旧 prompts 分支。reviewer 额外执行真实 main/api-verify 分支，仅 mock Celery 网络响应，当前导入与分支执行通过。 |

上表未写完整目录的发布脚本均位于 `scripts/release/`。

### 合同范围逐项覆盖与边界

`docs/CLI-RETENTION-MANAGEMENT-20261021.md:5` 起的八条批准范围均已核对与本增量的关系：

1. 72h/24h和成品、版本、原图保留：本增量只读取排空状态并校验72h，不修改清理算法或保留对象；对应上表第1、2、5项。
2. 旧会话无新宽限、pending屏障不变：无迁移代码变更；发布备份对旧数据的指纹及精确调度检查保持，对应第8项。
3. 每小时扫描、每轮25与保护/分阶段成功：无业务改动；原生快照 `retention-management-native.py:53` 保持清理启用和 batch 25，首次真实扫描验证仍在 `retention-management-verify.py:68`。不把排空测试当业务清理测试。
4. 管理页权限与批准视觉：无页面、组件或权限变更；本次不重复视觉验收。
5. 心跳、扫描、轮询与未知状态：无投影/轮询代码变更；发布仍检查新鲜心跳与 completed 首轮扫描，见 `retention-management-verify.py:13`、`:53`。
6. 统计、失败和重试去重：无业务统计代码变更；迁移仍要求空观察起点及一条累计初始化行，见 `retention-management-verify.py:21`。
7. 列表筛选、详情、已删任务摘要：无相关 API/前端变更；不以本轮发布助手测试替代旧候选业务证据。
8. 持久化、90天与长期累计、隐私：无存储策略变更；回执保留、失败暂停规则继续成立，见上表第7、8项。

实施顺序中的步骤1—4属于已审基线，当前增量没有改变源文档、业务实现或UI；步骤5的助手兼容修复是本报告主体；步骤6的正式登录页、真实首轮结果和保护图片生产验收须由主 Agent 在正式发布后完成，本报告没有宣称已经实测。完整产品功能结论应与基线报告一起使用。

### 部分实现、未实现、UI及Spec漂移

- 本次六文件修复范围内无部分实现或未实现项。
- UI一致性、引导真实性和邻居页面视觉对比：不适用，六个变更文件均为发布Python脚本/测试，未变更页面或用户文案。
- 无新增产品 API、页面、数据库表或规则；新增 readiness 及前置 schema 查询直接服务于合同发布步骤5，没有发现 scope creep。证据：`retention-management-deploy.py:34`、`:58`；`retention-management-native.py:18`、`:132`。

## Stage 2：Code Quality

- **质量 PASS**：六文件119/81/151/120/116/165行，均未超过300行。新的SQL常量归属专用drain、readiness归属专用native、deploy只编排调用；错误由既有fail-closed分支处理，见 `retention-management-deploy.py:84`。没有为修复改动旧历史共享助手。
- **测试真实性 PASS**：PG用例创建独立随机schema、明确不存在files，再执行原始SQL，最终rollback，见 `test_retention_management_drain.py:74`；readiness测试实际导入业务模块、只替代Celery响应，见 `test_retention_management_native.py:112`。这覆盖了旧编排mock会掩盖的退役导入故障。PID/超时测试和deploy失败路径同时通过。
- **安全 PASS**：扫描本次生产脚本及测试未发现硬编码真实密钥、shell=True、eval、前端secret暴露。`test_retention_management_native.py:127`、`:129` 的exec只执行仓库固定READINESS常量，用于验证真实探针；不是不可信输入。`:116`—`:118` 的test/test-secret为本地占位测试配置。生产命令采用argv列表，见 `retention-management-native.py:142`；SQL为固定常量，见 `retention-management-drain.py:14`。诊断stderr只写受限private文件，未打印完整环境，见 `retention-management-native.py:149`、`overseas-runtime.py:28`。没有发现新的可疑安全模式需要外部库升级或联网核实。
- **限制说明**：本次没有在真实systemd/runuser/Redis上启动服务，也没有做生产dump/restore。单测验证进程封装/协议与失败路径；真实部署仍需运行既有就绪、首次扫描和生产保留核验。该限制不等于本增量代码缺陷。

## 本次验证原始输出

使用项目后端虚拟环境，指定主 Agent 确认的本地隔离PostgreSQL（127.0.0.1:65435，retention_test）。执行四份 retention_management 发布测试（deploy、drain、native、verify），退出码0：

```text
............................................................             [100%]
60 passed in 2.41s
```

额外以当前后端真实导入运行 `image-inputs-worker.py` 的 main→api-verify，仅替代Celery网络响应，退出码0：

```text
API_WORKER_READY_POOL_5
API_VERIFY_CURRENT_IMPORTS_OK
```

对全部六个diff文件执行Python `compile(source, filename, 'exec')`，退出码0，原始输出：

```text
scripts/release/retention-management-deploy.py: 119 lines
scripts/release/retention-management-drain.py: 81 lines
scripts/release/retention-management-native.py: 151 lines
scripts/release/test_retention_management_deploy.py: 120 lines
scripts/release/test_retention_management_drain.py: 116 lines
scripts/release/test_retention_management_native.py: 165 lines
COMPILE_OK 6 files
```

环境排障记录：最初系统Python没有pytest，输出 `No module named pytest`；换用项目虚拟环境后首次PG连接因采用了错误本地测试用户名而失败，摘要 `1 failed, 59 passed in 2.70s`，核心错误 `FATAL: password authentication failed for user "postgres"`。由主 Agent 提供已确认测试连接后重跑得到上述60 pass，无跳过。没有将这两次失败记为通过或代码缺陷。

最终 review-status 再次核对 currentId 与 `8f2c6c02113d2fc2c08d1cfed60c1a4ae57a91810ac2574090a13ad425c73ef7` 一致，changedFiles仍为本报告六文件。主 Agent 可依据本报告对同一最终候选执行 review-approve；若代码再变更须重新固定并复核，不能用最初候选或先前失败报告替代。
