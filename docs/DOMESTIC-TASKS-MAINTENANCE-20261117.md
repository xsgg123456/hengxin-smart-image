# 国内业务任务 0043→0044 专项维护方案

本方案仅覆盖国内任务实体与历史会话归属升级。已于2026-11-17取得用户具体维护授权并完成一次性0043→0044升级，详见 [实际部署验收](DOMESTIC-TASKS-DEPLOYED-20261117.md)。下文保留维护设计及隔离验证记录；该迁移不得重跑，不得把历史命令当作下次发布指令。

## 规划与验收

1. 固定入口、源基线和迁移摘要：仅 `release.py tasks-prepare --scope domestic --mode full`，现行国内业务提交 `c79924625230275bad65fa778020d5b4a3b272e0`、schema `0043`。只新增 `backend/migrations/versions/0044_domestic_tasks.py`，摘要由已审工具固定；其它迁移、依赖和运行输入不得变化。普通 prepare 仍拒绝 schema 变化。
2. 准备事务：复用现有锁、stage 清单、scope 配置备份及持久 pending，并增加专项持久标记。准备失败/进程中断必须可核实恢复；未完成禁止普通发布、回退、清理和恢复入口。
3. 国内停机迁移：关闭国内 API/UI，既有两类队列排空；排不空恢复原国内接入，禁止强杀。停止国内三个原生服务和所有国内应用容器，确认 PID/cgroup/容器均不在执行。仅国内 PostgreSQL 完整 `pg_dump -Fc`，`pg_restore --list` 校验及文件大小/SHA256回执；在停止后采集历史行摘要，再执行单事务0044。
4. 切换验收：仅国内新源码/前端；真实国内schema为0044，历史所有 Studio 表既有行（排除新增task_id）数量与摘要完全一致，任务归属与五业务绑定正确。海外/shared源码、schema、容器ID/StartedAt、原生PID/启动时间、数据容器、镜像与依赖均不变。核验通过后推进国内当前/上一成功版并沿用原两版清理及净释放量回执。
5. 故障验证：准备、备份、迁移未提交、迁移已提交、切换中断、核验/台账写入中断、未知schema、候选漂移与普通rollback拒绝，分别隔离注入；不得将本地模拟称为生产演练。

## 影响和恢复

国内五工作台及同国内部署组的 API 换套图在排空后短暂停用。只停止国内服务；共享账号、海外服务和数据容器不重启。现有 `/var/lib/hengxin-domestic/release-gate` 实际被三组共用，本流程不关闭它，避免海外被连带封控。

唯一共同代码例外是 `backend/app/modules/auth/dingtalk.py` 的国内登录返回路径白名单，旧SHA256 `7b60c964a4b54c9d29ae55aadf8ed739f7c37cbcbabb8dbb8dce079a8e86bc1d` 到新 `ef7cbbbffd754d9e552117e15487a896b088927261847524edf8ca1e9b6a29a1`；只由国内新源码加载，shared仍保留旧挂载和进程。不是通用公共代码放行。0044迁移最终LF摘要为 `c6a9fb63e97f4b9460ebc37667a4116ae72bd380574f7baa0770093534bf0d01`。

迁移期间使用仅国内的持久启动围栏：原生服务既有91停止配置增加始终不满足的启动条件，国内容器关闭自动重启。围栏在新源码配置完整安装后解除，防止工具被杀或主机重启时旧worker在新schema运行。围栏和数据库迁移进程锁、数据库事务咨询锁共同保证没有旧新worker混跑；未知状态保持停机，不手写open绕过。

迁移前失败可恢复原国内代码、重启策略和接入。0044提交后只允许前向恢复同一份已审候选；不自动回到0043，不降级、不倒灌数据库。上一成功0043源码和附带备份仍按两版规则保留，但普通rollback跨schema时明确拒绝。只有后续同0044版本间才可正常回退。备份只作独立审批的灾难恢复依据，不能覆盖期间产生的业务数据或海外状态。

## 命令约定

通过唯一正式工具入口：`release.py tasks-prepare --scope domestic --mode full --release <已stage的国内包>`，随后 `tasks-deploy --scope domestic`；中断使用 `tasks-recover --scope domestic`，核验重试使用 `tasks-finish --scope domestic`。`tasks-status`仅输出阶段及受控工作目录。未开始迁移可通过tasks-recover核验恢复并结束事务；禁止普通cancel丢弃维护标记。

主 Agent 2026-11-17已读服务器普通verify通过；本实现者只读SSH核查为国内0043、海外overseas_0026。执行前必须重新核对实际版本，不能用本文替代实时核验。

## 实现自检证据（未发布）

- 使用现有本地隔离容器 `hx-task-20261117-python`，仅补齐测试需要的git；root身份完整发布工具套件：451 passed、5 skipped、15 subtests passed。5项依赖未提供的独立数据库/环境条件被跳过，不称已验。Python编译与diff空白检查通过；新增各脚本均低于300行。
- 专项用例覆盖固定基线/迁移摘要/其它迁移和依赖拒绝、唯一登录白名单例外、旧schema回退拒绝、备份失败不迁移、迁移提交后父进程中断不重跑、历史摘要不一致保持pending、迁移前恢复旧码/提交后只前向恢复、取消/恢复台账写入中断重入和未知schema拒绝。既有Linux真实文件锁继承与原生安全停止测试在root套件中通过。
- 后端实现者另在真实隔离PostgreSQL验证0043→0044历史数据与复合归属约束；本发布工具套件未执行生产迁移或数据库恢复。
- 只读生产预采样覆盖17张既有Studio表，当时24会话、12轮次、350条transcript、116上传、40图片、2结果文件、2删除回执。工具仅输出各表数量/SHA256；真正迁移验收会在国内排空并持久停止后重新采样，不把在线预采样当最终基线。

## 独立审查缺陷修复复验（2026-11-17，未发布）

- 重启策略：`scope_actions.Actions.start_apps` 的两个启动调用改走当前 `u.app_command`，确保专项 `--force-recreate` 实际作用到启动链。`freeze` 核验并记录完整 `RestartPolicy`，包含 `on-failure:N` 的 `MaximumRetryCount`；旧版恢复、候选启动及幂等 `tasks-finish` 都重新 inspect 并逐项核对当前 Compose 的策略和次数，不靠健康状态或成功回执推断恢复。策略不一致不得写首次恢复/应用成功回执；已提交迁移仍只允许前向恢复。
- 配置隔离：`verify_after` 以全部 `before.configs` 为基线，只替换 prepared 中固定的国内 Compose SHA256 和国内三个原生源码 drop-in SHA256，再与 `after.configs` 完整比较。海外、shared、国内环境文件及网关配置的任意新增、删除或修改均拒绝；国内允许变动项也必须恰好匹配已准备摘要。
- 核验失败关闭入口：`finish` 在 capture、verify、catalog 或台账/完成标记写入失败时仅关闭国内 API/UI，保留 worker、pending 与持久恢复阶段。重试先验证迁移和已应用候选，再仅启动实际停止的入口，重新完整验收；台账已写而完成标记未写的窗口可重入。已确认成功之后单独的垃圾清理失败如实报错，不因此关闭业务入口。
- 真实 Docker：宿主 Docker Compose v5.6.1，`TEST_TASKS_DOCKER=1 python -m unittest discover -s scripts/release/intranet -p test_domestic_tasks_restarts_docker.py -v` 最终 **4 tests / OK，37.340 秒**。独立随机项目实测普通 `update --restart=no → stop → up` 保持原容器 ID 且策略仍为 `no`；真实专项 hook 恢复 `unless-stopped` 与 `on-failure:7`。覆盖实际 engine journal 的迁移前失败恢复、候选成功、提交后启动失败再前向恢复；每条路径均核验海外/shared对照容器的 ID、StartedAt、RestartPolicy 不变。数据库提交、原生服务和业务健康端点在这四条 Docker 用例中模拟，不宣称真实生产迁移演练。
- 完整 Linux 发布回归：独立容器 `hx-tasks-release-restart-check`，在既有测试镜像基础上仅于该容器安装 PostgreSQL 17 客户端，root 执行 `python -m pytest scripts/release/intranet -q -rs`，最终 **504 passed、4 skipped、15 subtests passed，58.72 秒**。4 个 skip 正是上一条已经在宿主实际执行通过的 Docker opt-in 用例。另三项真实数据库 fence、真实 UID 1001 子进程、publisher namespace/身份、pg_dump/pg_restore 与迁移失败事务均实际执行通过；未 unset DSN 跳过。数据库使用随机独立 `hx_tasks_release_*_test`，不触碰并行后端测试 schema。
- 环境障碍已定位并重验：首次默认容器缺少 MINIO 测试配置、PostgreSQL 客户端且 bwrap 无 namespace 权限；补齐独立测试环境后通过。仅临时测试容器的执行进程使用 `docker exec --privileged`，未修改宿主 namespace 策略或生产依赖。所有自建数据库、Compose 容器与网络均在测试结束清理，临时验证容器随后删除；复查 `hx-tasks-restart-*` 容器和网络为零。
- 新增 `test_domestic_tasks_restarts.py`、`test_domestic_tasks_restarts_docker.py`、`test_domestic_tasks_verify.py`、`test_domestic_tasks_finish.py`；既有迁移状态机用例明确 mock 独立策略检查层，其策略故障覆盖由新增实际 scoped dispatch 测试承担。Python 编译和变更空白检查通过。后续仍需主 Agent 固定新 candidate 并重新执行两阶段独立审查，不能复用修复前凭据。
