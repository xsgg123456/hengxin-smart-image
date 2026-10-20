# 国内 API 简化整改发布增量：独立审查

- 审查日期：2026-10-20；角色：code-reviewer；使用 `.agents/skills/code-review/SKILL.md` 两阶段流程。
- 最终审查 candidateId：`7454079f6ad2229cb2bc2a98ee0e00c88e0e3eff066dd719384c66ecc19e17cd`。
- 结论：**Stage 1 PASS；Stage 2 PASS；开放 HIGH 0、MEDIUM 0。**
- 范围：发布适配代码、验证工具及版本变更。该结论用于同快照代码提交和已授权发布流程执行；**不是生产发布完成证明**。审查者未连接生产、未运行发布、未改产品代码、未提交、未登记 review-approve。

## 快照与材料

初始派发候选为 `2549d60b8c74966efc16e3f6e69e541e8d85a54c8899ba0a27ea47351c807421`。首次 `review-status` 已发现当前变为上述 `7454079…`，立即通知主 Agent。主 Agent 确认变化为 `api-simple-handoff.py` 的 NULL 状态拒绝及 `test_api_simple_isolation.py` 的三个真实 PostgreSQL 回归；已重新阅读全部两文件并将其纳入本报告，未直接延用旧快照结论。

主 Agent 最终重新 `review-prepare` 返回同一 `7454079…`；七个发布源码/测试文件冻结记录位于忽略的 `output/api-retry-simple-release-20261020/adapter-frozen-hashes.json`。

相对已批准产品快照 `19ff4eb28e6ef86981da5efa160f313380f4dcd1f20897d39c6998441d8d7eca`，harness 实际 changedFiles 为：

- `hengxin-smart-image/frontend/package.json`；
- `scripts/api-retry/production-browser.mjs`；
- `scripts/release/{api-simple-deploy.py,api-simple-handoff.py,package-api-simple.py}`；
- `scripts/release/{test_api_simple_deploy.py,test_api_simple_handoff.py,test_api_simple_isolation.py,test_package_api_simple.py}`。

产品源码及其隔离验证结论沿用 `docs/reviews/API-RETRY-SIMPLIFICATION-20261020.md:5` 对应的已批准快照；本次并未把全部工作区相对 HEAD 的旧脏改动误当新发布增量。版本文件只有 `0.2.44 → 0.2.45`，见 `hengxin-smart-image/frontend/package.json:3`。

正式发布合同为 `docs/API-RETRY-SIMPLIFICATION-RELEASE-20261020.md:1`，产品边界为 `docs/API-RETRY-SIMPLIFICATION-20261020.md:5`；`DEV-PLAN.md:3`、`Product-Spec-CHANGELOG.md:1` 已同步发布授权。下列路径均相对仓库根目录，`R/` 表示 `scripts/release/`，`B/` 表示 `hengxin-smart-image/backend/app/modules/api_image_edits/`；正文的 `frontend/` 简写表示 `hengxin-smart-image/frontend/`。

## Stage 1：Spec Compliance — PASS

### 发布合同逐条核对

|合同条目|实现与证据|
|---|---|
|规划 1：只读确认生产拓扑、版本、在途工作，不输出凭据|代码匹配。`R/api-simple-deploy.py:34` 强制国内0031、海外0019、前端0.2.44；`:48` 读取基线与拓扑。沿用 `R/api-retry-deploy.py:48` 固定容器ID/镜像、原生PID/cwd/argv/environment哈希。主 Agent 的真实只读结果由发布合同记录，本 reviewer 未重复连接生产；发布时仍执行这些断言。|
|规划 2：0.2.45；仅国内三服务及前端；历史数据、配置保持|完整实现。`frontend/package.json:3`、`R/package-api-simple.py:27` 固定0.2.45；`R/api-simple-deploy.py:53` overlay 仅 SERVICES，`:40` 只放行 image/build。`R/api-retry-deploy.py:17` 三服务为 api/api-image-worker/api-image-outbox；`:67` 比对无关国内容器、海外、身份及原生进程/配置不变。`R/test_api_simple_deploy.py:135` 验证 migrate、普通outbox、环境变量变化被拒绝。|
|规划 3：工具测试、正式构建、依赖审计、快照审查；打包前提交且干净|完整实现及本地证据齐备，原始结果见下。`R/package-overseas.py:180` 打包先检查 tracked 干净、approved 快照、已提交 helper、每文件等于 HEAD；`:210` 再检查 HEAD/快照未漂移。`R/package-delivery.py:70` 拒绝未批准快照。提交仍由主 Agent 按 `docs/HARNESS-REVIEW.md:5` 后续执行。|
|规划 4：归档/源码哈希、实际镜像安装测试后固定拓扑|完整实现。`R/package-api-simple.py:12` 保留全部依赖并加新入口/handoff；`R/package-overseas.py:166` 逐成员/哈希验证归档。`R/api-simple-deploy.py:21` 验证 manifest 版本/迁移/必要文件并运行 hashes；`:147` 仅调用旧模块 build。`R/overseas-deploy.py:29` 实际构建、校验镜像内全部后端源码哈希并在该镜像运行安装测试，成功才写 INSTALL_TEST_IMAGE_ID；`R/member-release-runtime.py:99` prepare/deploy 均核对镜像身份。服务器实际构建/传输尚未执行，不能称已通过。|
|规划 5：关接纳、安全交接、温和停止、备份/隔离恢复、切换及只读验收|完整实现。`R/api-simple-deploy.py:98` 至`:127` 执行顺序与合同相符；`R/domestic-gate.py:41` 同时关闭两层国内代理并从本地/域名实际验证503；`R/api-retry-deploy.py:130` docker stop --timeout=-1，客户端超时不强杀。备份、切换及恢复时序详见下表。生产浏览器 `scripts/api-retry/production-browser.mjs:12` 拒绝页面写请求，`:49` 只下载已有文件，`:59` 只验证失败入口，未点击生图/重试。|
|规划 6：台账、备份定位、发布记录|完整实现。`R/api-simple-deploy.py:94` 以 release 定位备份，`:128` 写三份 release manifest 和 VERIFIED；`:131` 失败记录 phase/backup 并重新关接纳。`R/release-retention.py:57` 共锁贯穿每次操作，`:101` 成功后再登记快照/回执；账本未确认时禁止清理。仓库发布记录目前明确“准备中”，实际执行后的记录属于尚未完成发布工作，不伪报成功。|

### 运行边界与竞态核对

|边界|实现与验证|
|---|---|
|不运行 migrate、不改0031结构、不清零 bounded-v2|匹配。`R/api-simple-deploy.py:74` 比较所有表列名投影、全部API行指纹及原 cycle 数；`:108`/`:116` 无 migrate 服务。`R/test_api_simple_deploy.py:55` 断言没有迁移调用，`:97` 以97个历史轮次验证保留并拒绝清零/改列/改行。|
|仅允许确定的持久状态，拒绝有效/残缺lease|匹配。`R/api-simple-handoff.py:40` uncertain 只能 token/lease 齐全且已过期；queued/retry_wait/终态必须双无租约，collecting还必须有URL或bytes回执；running和未知状态一律拒绝。`R/test_api_simple_handoff.py:21`、`:41` 覆盖允许/拒绝矩阵；`R/test_api_simple_isolation.py:73` 通过真实PG执行相同SQL验证，并核对原行未改。|
|拒绝未结束/运行中attempt、CLI活动/uncertain、不明状态、旧通道占用|匹配。`R/api-simple-handoff.py:6` 单条SQL读取证据，attempt需 completed_at 且处于允许终结态，CLI仅允许既有终结/候选态；NULL task/CLI/attempt亦计未知。`:8` 对通道 item/token/lease 任意残留计数。`R/test_api_simple_isolation.py:97`、`:109`、`:119`、`:137` 逐项真实PG验证。|
|暂停、停outbox、连续两次broker和DB空闲，再停worker|匹配。`R/api-simple-deploy.py:99` 先停API，再`:101`暂停通道；`R/api-simple-handoff.py:87` 确认暂停、停outbox、wait_idle、停worker、再次读取DB。`:69` 每轮同时要求安全持久状态与 `R/member-release-drain.py:64` 的三种Celery状态、队列和unacked均空，两次连续成功；忙碌会清零计数。`R/test_api_simple_handoff.py:75`、`:99`、`:111` 验证顺序、停后变化拒绝、连续性和超时。|
|1200秒只作发布等待上限；未知在途不强杀|匹配。`R/api-simple-handoff.py:69` 以单调时钟计算总剩余，broker/SQL各使用剩余期限，SQL返回后再次检验总期限；超时不写 EXECUTORS_STOPPED。`R/api-retry-deploy.py:130` 无kill升级；`R/test_api_retry_isolation.py:28` 在真实Docker忽略SIGTERM进程上验证客户端超时后容器仍运行。|
|完整备份、隔离恢复、全部API行/列/轮次保存|匹配。`R/api-simple-deploy.py:66` 包装原备份并保存原cycle与终态保护集；`R/api-retry-deploy.py:169` 停执行器标记后保存配置/前端入口/台账、完整数据库dump，在隔离容器恢复核对API指纹。`R/member-release-backup.py:114` 使用实际DB镜像、network none、独立卷、pg_restore --exit-on-error，无写回生产DB。|
|新worker在全指纹检查前不得恢复旧uncertain|匹配。`R/api-simple-deploy.py:108` 只启API/worker，`:111` 确认outbox停，`:112` 再验双idle，`:113` 比对全指纹后`:116` 才启动outbox。`B/worker_health.py:21` 启动信号只更新心跳；`B/celery_app.py:18` 仅任务触发execute；`B/outbox.py:13` 为发布者。`B/claims.py:73` 即使通道暂停仍会恢复过期状态，因此这里停outbox及清空broker是必要保护，不能仅依赖paused。|
|恢复后保留旧终态图片/审计/版本/文件|匹配。`R/api-simple-handoff.py:99` 对原成功/失败items、关联attempt、全部version及version所指file保存逐行哈希；`:115` 允许新增但拒绝原行删除或变化。`R/api-simple-deploy.py:119` 在恢复outbox后核对；`R/test_api_simple_isolation.py:154` 实际PG验证新增通过、改旧file失败。|
|旧静态资产与配置保持|匹配。`R/member-release-runtime.py:105` 同路径旧资产内容不同即失败；`R/overseas-runtime.py:124` 增量复制，不清空旧assets，index经临时文件替换。`R/api-simple-deploy.py:58`/`:91` 验证Compose只改三服务image/build，代理最终恢复原内容，见 `R/domestic-gate.py:78`。|
|失败保留现场、无自动rollback/覆盖生产数据|匹配。`R/api-simple-deploy.py:131` 捕获异常仅保存恢复证据、关接纳并抛出，不重启旧代码、不恢复数据库；`:115` 在启动outbox前标明新策略可能生效。`R/test_api_simple_deploy.py:75` 注入十处阶段故障，验证没有restart/down/migrate/自动恢复。|

完整实现：上述发布增量。部分实现/未实现：没有代码层缺失。实际生产构建、部署、浏览器验收和发布台账结果尚待主 Agent 执行，不属于本报告已经验证的事实。

Spec 漂移：未发现新增产品功能、表或API；`R/api-simple-deploy.py:147` 仅复用旧build函数，不调用旧overseas部署；`R/package-api-simple.py:26` 模块内适配不修改旧入口文件。产物仍按原白名单包含共用依赖，其包含不代表重启海外/原生服务。

UI 一致性：本次 changedFiles 无UI组件/样式变化，`frontend/package.json:3` 仅版本。实际页面与邻居基准的已审视觉证据见 `docs/reviews/API-RETRY-SIMPLIFICATION-20261020.md` 的 Stage 2；本次发布脚本尚未运行，不把截图代码当生产截图。

## Stage 2：Code Quality — PASS

- **结构/类型：通过。** 新增源码/测试均小于300行，最长 `R/test_api_simple_isolation.py:168`。deploy负责阶段编排，handoff负责只读证据/安全判定，package负责版本和白名单适配。`R/api-simple-handoff.py:23` 严格检查字段集合、标量类型、ID唯一性；不是把缺字段/字符串计数视为空闲。
- **测试真实性：通过。** `R/test_api_simple_deploy.py:15` 明确为编排mock，证明顺序和故障处理，不冒充真实部署。`R/test_api_simple_isolation.py:24` 创建唯一名、无网络PG容器，实际执行EVIDENCE和保护哈希SQL；`:44` 的SQL字段类型已对照 `B/models.py:53`、`:103`、`:142`，UUID/bytea/timestamptz类型一致。其简化表夹具不证明全生产迁移；真实恢复机制另由旧隔离集成测试验证。
- **打包依赖/隐私：通过。** `R/package-api-simple.py:12` 沿链保留 REQUIRED 并加入两新入口；`R/test_package_api_simple.py:17` 逐依赖验证选择/缺失拒绝，`:41` 拒绝本地QA、临时备份路径、.env/db/auth。`R/package-overseas.py:110` 拒绝符号链接，`:180` 仅提取已提交白名单文本，调用 `R/package-delivery.py:55` 私密内容扫描；构建资产经 `R/package-management.py:62` 后缀/敏感文件名/内容检查，归档再次校验。
- **安全扫描：未发现本轮新增问题。** 搜索新增文件中的eval、innerHTML、暴露VITE密钥、常见密钥前缀、shell=True、硬编码password、用户绝对路径，无危险匹配。handoff动态SQL仅用 `R/api-simple-handoff.py:99` 常量表/谓词；数据库字段名的引用由 `R/api-retry-deploy.py:146` 正则限制。`scripts/api-retry/production-browser.mjs:4` 读取外部cookie文件、不打印token；`:12` 禁页面写请求，所有主动HTTP调用均为GET。
- **断言门禁不被优化模式关闭：通过。** `R/api-simple-deploy.py:156` 必经 `R/release-retention.py:63`，明确拒绝 Python -O；共享锁在`:65`进入，覆盖build/prepare/deploy及台账操作。
- **视觉对比：本次无新UI增量。** 延用已批准同产品源码的实际1440px邻居对比和390px交互证据；本次生产只读脚本 `scripts/api-retry/production-browser.mjs:32`、`:52`、`:55` 提供发布后截图/旧结果读取/失败入口检查。失败样本未找到时脚本不会宣称检查过失败入口，见`:55`条件分支；正式发布记录须按实际checks说明范围。
- **既有依赖风险保留。** `output/api-retry-simple-release-20261020/dependency-audit.json:4819` 为 critical 0、high 70、moderate 48、low 5。锁文件不在本次 changedFiles；本报告不把“没有新增依赖变化”描述成“没有漏洞”。

## 编译与测试原始输出

审查者独立编译新增发布源码和浏览器脚本，退出码0：

```text
python -m compileall -q scripts/release/api-simple-deploy.py scripts/release/api-simple-handoff.py scripts/release/package-api-simple.py
PYTHON_COMPILE_EXIT=0
node --check scripts/api-retry/production-browser.mjs
NODE_SYNTAX_EXIT=0
```

初次系统Python缺少pytest，未把该失败计为测试通过；随后使用项目 `.venv/Scripts/python.exe` 独立执行三个新增非Docker模块：

```text
184 passed in 0.52s
```

直接读取主 Agent 本地完整发布测试日志 `output/api-retry-simple-release-20261020/release-tests.log`：

```text
1107 passed, 1 skipped, 309 subtests passed in 90.33s (0:01:30)
```

该运行由主 Agent 明确启用 `HX_API_SIMPLE_DOCKER_TEST=1` 与 `HX_API_RETRY_DOCKER_TEST=1`；1项skipped由主 Agent说明为既有test_delivery_native的Windows符号链接权限1314，未计为通过。新增适配专项日志 `output/api-retry-simple-release-20261020/adapter-tests.log`：

```text
227 passed in 49.23s
```

专项覆盖43项真实隔离PG用例，包括最终新增的3个NULL状态用例；其余184项由审查者独立再次运行通过。

正式构建日志 `output/api-retry-simple-release-20261020/frontend-build.log`：

```text
> hengxin-smart-image-frontend@0.2.45 build
> vue-tsc --noEmit && vite build
✓ built in 33.70s
```

日志前有npm对两项既有项目配置的unknown-config警告；构建仍成功，不隐瞒警告、不将其当编译错误。

## 执行边界

审查仅批准所列快照的代码与流程。实际归档隐私审计结果、传输校验、服务器镜像安装测试、生产备份恢复校验、存量任务交接、无关服务保持、浏览器验收及台账成功须在后续执行中分别取得证据。不得据此宣称已部署、证明远端调用已停止或保证上游无重复计费。

主 Agent 应仅对与本报告一致的candidate执行 `review-approve`；受控文件再变更须重新固定快照并复核。审查者不向 `.needs-review` 写 clean。
