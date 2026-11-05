# 批量标注发布工具独立审查

审查日期：2026-11-05。candidateId：`bf83c9582a4f9210e63c38c9ee32b75a96ea514c562694586419142538b474c6`。

范围：`scripts/release/studio-batch-{baseline,runtime,package,deploy,native,recovery}.py`、`test_studio_batch*.py`，以及其实际调用的既有发布 helper。依据：`docs/STUDIO-BATCH-RELEASE-PLAN-20261105.md`、`docs/STUDIO-BATCH-ANNOTATION-20261105.md`、Product-Spec 本轮增量。业务功能和页面由另一 reviewer 审查，本报告不重复验收。

结论：**Stage 1 FAIL；Stage 2 未执行**。存在恢复路径 HIGH 问题，不能据本报告登记两阶段 PASS。未修改代码、未提交、未执行生产命令。读取了已有只读基线记录；未将记录当作本次重新实查。生产安装测试、数据库恢复实测、切换、回滚演练与正式入口视觉均尚未验证。

## Stage 1：发现的问题

### HIGH R1：consumer 已暂停时，恢复流程反而要求它正在消费

- 要求：发布计划第 23 行允许暂停 consumer 后优雅停止 native；第 73、75 行要求切换前恢复，并在停机超时时保留保护。
- 触发：`studio-batch-deploy.py:91` 已成功 pause，此后写 gate、停止 native 或 systemd 操作失败；worker 仍运行但 `active_queues=[]`。这是真实可达的中间状态。
- 差异：`studio-batch-recovery.py:32` 在尚无 `NATIVE_STOP_STARTED`，或任一 native PID 仍大于零时，调用 `r.worker('idle')`。`skill-platform-worker.py:40` 的 idle 分支调用 `account-worker.py:21` 的 identify；后者第 30 行明确要求队列为 `['overseas.cli']`。已暂停 consumer 因此必然报 `Unexpected worker queues`。
- 结果：`studio-batch-recovery.py:35` 只启动 API、刷新网关然后抛错；走不到第 43 行的恢复启动或第 45 行的 consumer resume。API 恢复接纳但 consumer 仍暂停；重复恢复仍会遇到同一错误。暂停后尚未请求 systemd stop 的情况也无法恢复，不只是需要等待真实 inactive 的合法保护情形。
- 验证：本地临时目录构造 gate 已写、consumer 已暂停状态；调用真实 `recover` 和真实 `account-worker.identify`，仅替换 Celery control 数据及外部 I/O。未执行生产命令。原始输出：

```text
PARTIAL_GATE_RECOVERY_ERROR: Unexpected worker queues
WORKER_CALLS: [('idle',)]
HOST_COMMANDS: [('docker', 'start', 'hengxin-overseas-api-1')]
CONSUMER_RESUMED: False
```

- 修复验收要求：根据实际队列/固定 node 区分 paused 与 consuming，已暂停状态走对应的排空核验；若 native stop job pending，保持保护并拒绝提前恢复 API；可恢复状态正确恢复 consumer/native 后再开放 API。覆盖 pause 成功后、native stop 前失败，以及 outbox 已停而 worker 尚未停的路径。现有 `test_studio_batch_recovery.py:42` 把 worker 直接 mock 掉，没有验证这一真实前提。

### MEDIUM R2：前端 dist 没有与声明的 commit/candidate 绑定

- 要求：发布计划第 20 行“包括候选包在内全部从干净固定commit生成”。
- 已实现：`studio-batch-package.py:20` 检查源码 clean；第 34–35 行逐项比较源码与固定 commit；第 70 行复查 commit/candidate。
- 差异：第 56 行直接收集现存、Git 忽略的 `frontend/dist`；第 73 行仅比较打包前后是否变化。没有检查 dist 来自该 commit 的构建证据，也没有在固定源码上重建。`polling-runtime.py:33` 的前端验证只检查入口和资源存在。
- 证据：提供引用 `/assets/old-build.js` 的 HTML 和普通旧 JS，真实 `verify_frontend` 接受，输出 `STALE_DIST_STRUCTURE_ACCEPTED: True (no commit input in verifier)`。源码审核通过及 package.json 为 0.2.64，不能证明 JS 属于该版本。
- 影响：保留旧 dist 后提交新源码，打包工具仍可能生成带新 commit/candidate 的旧 UI 包。当前尚无正式包，未断言本次实际 dist 已过期。
- 修复验收要求：打包时从固定干净源码构建，或核对可信构建凭据中的源码身份、依赖锁文件与完整 dist hashes；覆盖旧 dist/改写 dist 拒绝测试。

## Stage 1：逐项对照

以下“匹配”只表示本地代码与命令边界匹配，不表示生产执行通过。

| 计划条目 | 结论 | 证据与验证方式 |
| --- | --- | --- |
| 基线版本、镜像、0026，不迁移 | 匹配 | `studio-batch-runtime.py:11` 固定版本和镜像；`studio-batch-deploy.py:23` 每阶段查 schema；`polling-database.py:65` 仅备份和隔离恢复，无迁移。读取现有基线 JSON，记录 33 Compose 文件、两 native 同源。 |
| API 五文件、native 一文件 | 匹配 | `studio-batch-runtime.py:13`、`:15` 明确集合；`:38` 与 `:60` 拒绝额外 API 文件；新增范围测试实际运行通过。 |
| 步骤 1：clean、固定 commit、review | 部分实现 | `studio-batch-package.py:20`、`:24`、`:35`、`:70`；`package-delivery.py:70` 要求 approved。候选包也拒绝脏源码。前端来源缺口见 R2；当前快照尚未批准，提交和发布不在本次已完成范围。 |
| 步骤 2：包 allowlist、递归测试依赖、隐私、哈希 | 匹配，来源绑定除外 | `studio-batch-package.py:39` 固定 API；`:51` 调用 `sku-package.py:16` 递归 AST 收集测试依赖；`:53` helper 白名单；`:36` 源码隐私；`package-overseas.py:135` 收集资源并校验资源类型/隐私；`studio-batch-runtime.py:50` 校验包内字节及完整文件集。正式 package-audit 尚未生成/验收。 |
| 步骤 3：prepare 不切换、安装测试隔离 | 匹配 | `studio-batch-deploy.py:27` 仅构建和快照；`sku-deploy.py:112` 独立 PG、network none、测试容器共享该隔离网络，只读挂载 `/app/tests`，默认镜像身份，无生产 env-file；`:106` 必须 passed、禁止 failed/skipped；`:138` 绑定 manifest/image。新增命令边界测试通过，真实镜像测试未执行。 |
| 步骤 4：gate 在途、导入、停止顺序 | 顺序匹配，恢复失败 | `studio-batch-deploy.py:78` 两次导入及 worker idle；`:87` Docker 无限 graceful timeout、调用端 60 秒；`:91` pause 后 native.stop。`sku-native.py:96` no-SIGKILL/infinity，outbox 先停、总计 60 秒；R1 阻塞异常恢复。 |
| 步骤 4：备份与隔离恢复 | 匹配 | `polling-database.py:19` 关闭 gate；`:65` 私有备份；`:30` 独立 PG 恢复后比较逐表 fingerprints、schema、版本；`:81` 写 COMPLETE；`:85` native 安装前重新校验恢复证据和 live DB。真实 dump/restore 未执行。 |
| 步骤 5：native 精确替换和真实身份 | 匹配 | `studio-batch-native.py:15` 先 stopped/backup_verified；`:25` 原始字节备份；`:40` 独占临时文件后原子 replace；`:48` runuser 实际路径编译；`:96` 实际安装模块验证自定义/旧 payload；`sku-native.py:180` 两单元 PID、UID999、cwd 验证。临时文件系统故障、备份篡改、恢复顺序测试通过；生产身份执行未执行。 |
| 步骤 6：全部 Compose、image-only、网关 DNS | 匹配 | `account-runtime.py:92` 捕获全部 live 标签路径及 hashes；`:103` 按原顺序加入；`studio-batch-deploy.py:59` overlay 仅 image，`:62` 比较完整配置；`:117` 仅 api --no-deps；`:118` 紧接网关 refresh。`skill-folders-gateway.py:40` 固定 web 身份后 nginx -t/reload。 |
| 步骤 6：保留业务与静态资源、resume 字节 | 匹配 | `sku-deploy.py:29` 检查其他容器/Skill；`sku-native.py:36` 其他源码和单元保护；`studio-batch-deploy.py:128` 环境 hash、`:132` 国内/海外 ready；`sku-frontend.py:28` 保留旧 hash 文件并备份入口；`studio-batch-deploy.py:145` 安装与公网 HTML/入口 JS/CSS 逐字节核对。实际部署未执行。 |
| 步骤 7：正式入口、三种宽度、不收费生成 | 待主 Agent 生产验收 | 发布计划第 26 行明确；`studio-batch-deploy.py:162` 返回仍需浏览器视觉验收，未伪称完成。本范围没有页面/UI 改动；不以工具测试代替生产交互验收。 |
| 候选包仅 prepare/test | 匹配 | `studio-batch-deploy.py:21` mode 门禁；gate、backup、native、api、verify、resume、recover 均要求 release；新增 candidate 测试通过。 |
| 切换前恢复与切换后回滚 | 部分实现 | R1。正常路径 `studio-batch-recovery.py:39` 先 restore native，再第 49 行恢复旧 API；第 57 行恢复 HTML，第 60 行刷新网关。无 live DB 回灌/降级调用，publisher 无 stop 命令。 |
| 中断 native 修复、保留备份和保护 | 匹配，停机恢复缺口见 R1 | `studio-batch-native.py:18` 仅首次备份；`:32` 复用记录，`:40` 不覆盖残留临时文件；`:56` 原始文件恢复。`sku-native.py:153` recovery 启动拒绝 pending job。真实损坏恢复演练未执行。 |
| Spec 漂移 | 本范围未发现新增业务范围 | `studio-batch-runtime.py:13` 仅约定的 API/native 文件；`studio-batch-deploy.py:174` 为计划定义的发布与恢复动作，没有新增业务 API/表。 |

## 验证原始输出

执行：`python -m unittest discover -s scripts/release -p 'test_studio_batch*.py' -v`。21 个用例逐个输出 `ok`，原始结尾：

```text
----------------------------------------------------------------------
Ran 21 tests in 0.849s

OK
```

对六个发布工具和三个测试模块逐一执行 `compile(path.read_bytes(), str(path), 'exec')`，不写 pyc、不导入生产模块：

```text
COMPILE_PASS: 9 files
```

这证明 Python 语法编译通过，不证明 Docker/systemd/PG 生产执行成功。主 Agent 提供的另 36 个复用测试结果未在本轮独立复跑，不充作本报告亲自执行的证据。

## 快照与下一轮

审查期间执行 harness review-status，`currentId` 与本报告 candidateId 一致，`approved=false`。报告为普通 Markdown，不改变受控代码快照。修复 R1/R2 后必须重新 review-prepare，交新 candidateId，重新从 Stage 1 审查。**Stage 2 代码质量、安全扫描、视觉对比未执行**；不得把本报告或现有 21 项绿灯转为两阶段通过凭据。
