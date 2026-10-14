# 部署镜像保留与清理

2026-10-14 用户已追加授权同步已审查工具到服务器并初始化启用。采用独立工具目录和共用状态目录，不重启业务、不重放发布、不删除业务数据；启用后进行哈希、运行状态和清理预览验证。旧发布包保持原样，后续发布使用新工具或包含本机制的新包。执行结果见文末启用记录。

## 保留规则

国内、海外和身份服务分别记录 `current`、`previous` 镜像 ID 集合。只有原发布流程的安装、健康及业务验证全部返回成功，才把部署前版本记为上一成功版本。未变更的业务不推进历史；同一已完成发布重复执行只重试清理。

默认台账 `/var/lib/hengxin-release/retention.json`，同目录 `release.lock` 跨入口互斥、原子写入。可通过 `HENGXIN_RELEASE_STATE_DIR` 改路径，但同一主机所有入口必须使用同一路径及 Docker context，不能用不同路径绕过锁。不要手工编辑台账。

保留集合还包括：全部容器引用（含停止的容器）、跨阶段构建/准备的候选、失败待恢复的候选及部署前镜像。多于两版时优先保留这些引用；不会强删容器来凑数量。

清理只删除 `hengxin-smart-image-backend` 仓库中无保护引用的镜像标签；存在其他仓库别名则跳过。删除前再次核对运行状态和引用，不使用强制删除。数据库、对象存储、图片、任务、会话、备份、CLI 环境、发布目录及基础服务均不清理；历史 Compose 配置链仍有用途。

## 首次启用

在服务器用新发布包中的 helper，先根据实际发布记录确认各业务上一成功镜像，再运行初始化。下面的变量必须填写重新核实的值，不按创建时间推断：

```sh
python3 scripts/release/release-retention.py init \
  --domestic-previous "$DOMESTIC_PREVIOUS" \
  --overseas-previous "$OVERSEAS_PREVIOUS" \
  --identity-previous "$IDENTITY_PREVIOUS"
python3 scripts/release/release-retention.py preview
```

参数可以是完整项目镜像标签或完整 SHA256 ID；初始化确认镜像存在、属于项目，当前值来自运行中且健康的 Compose 服务。每组参数代表该组所有服务的上一成功镜像；若历史上同组服务使用不同镜像，不能使用该简化初始化，需要先核实并扩展逐服务初始化，禁止编造统一版本。

初始化可补齐缺失的上一版，不覆盖已有历史；发现版本漂移或未完成的部署则拒绝。未初始化时部署仍可执行，但缺少历史的业务会阻止全部清理。完成该部署后可初始化缺失历史。

## 正常发布与失败恢复

现有 Python 发布入口继续使用原来的 `RELEASE build/prepare/deploy/recover` 参数（以该入口支持的动作为准）。`member-release-resume.py` 保留原有参数；CLI 独立升级入口使用内部固定发布号。构建、准备和恢复入口都使用同一锁，跨进程候选保护写入台账。

部署中断或失败：保留候选与部署前快照，按该发布原有的恢复步骤运行 `recover` 或 `resume`。旧包发生的失败没有本工具快照，不能直接用新工具猜测历史恢复。没有恢复动作的旧入口仍需按原人工恢复方案处理。

原部署验证已返回成功，但读取 Docker 快照或写入台账瞬时失败：独立 `verified-<release>.json` 回执会保留。重新执行该发布入口时只补记，不再部署或调用原恢复流程；也可运行 `python3 scripts/release/release-retention.py finalize --release "$RELEASE"`。补记要求服务仍健康，且镜像属于原部署前版本或该候选版本；出现无关版本会拒绝。已验证的发布不能直接 abandon。

若存储故障导致成功回执本身也未落盘，工具无法可靠区分成功和中断，继续保护镜像、不清理；必须人工检查原发布的验证记录、真实运行及业务状态，按该发布恢复方案处理，禁止伪造成功回执或盲目重放部署。

清理出错：部署成功记录保留，告警不会进入原发布的关闭入口/停服务分支。可查看台账与 `cleanup-plan.json`、`cleanup-result.json`，修复原因后执行：

```sh
python3 scripts/release/release-retention.py preview
python3 scripts/release/release-retention.py cleanup
```

确认某个构建已取消、不再用于部署或恢复后才解除候选保护（不立即删除镜像）：

```sh
python3 scripts/release/release-retention.py abandon --release "$CANCELLED_RELEASE"
```

解除保护要求当前各业务健康且与台账一致；容器仍引用的镜像依然保留。不要在另一终端运行旧脚本或直接 Docker 改动来绕过锁。锁保护新入口之间的并发；外部 Docker 管理操作不受本锁控制。

## 缓存与兼容边界

新构建使用专属 `hengxin-release` Buildx builder（docker-container driver，`--load`），默认复用缓存。此名称仅供本项目使用；不得给其他项目共用。需要全量重建时设置 `HENGXIN_RELEASE_NO_CACHE=1`。

部署验证通过、版本历史完整且无其他在途候选后，才调用该 builder 的 `prune --max-used-space 2gb`。只回收可回收的缓存，正在使用的缓存可能使实际占用超过预算。默认 builder 的旧缓存不接管。Docker/Buildx 不支持该参数或专属 builder 不存在时，清理告警，业务保持运行。接口依据 [Docker Buildx ls](https://docs.docker.com/reference/cli/docker/buildx/ls/) 和 [prune](https://docs.docker.com/reference/cli/docker/buildx/prune/)。

历史 `image-inputs-deploy.sh`、`delivery-deploy.sh` 不接入本机制，不用于新发布；新的 Python 入口也仍保留各自固定版本、迁移与哈希检查，并非任意版本通用发布器。只保留旧镜像不代表数据库迁移可逆，不自动回滚业务数据。

## 本地验证

测试使用临时台账与模拟 Docker 元数据，覆盖独立推进、失败恢复、幂等、锁竞争、运行漂移、引用/别名保护及命令边界；不接触生产数据。独立两阶段审查均通过，详见[最终审查报告](reviews/RELEASE-RETENTION-20261014-FINAL.md)。真实 Docker 构建、生产初始化与上线验证在下一次正式发布执行。

2026-10-14 验证证据：

- 新增状态/清理/初始化及成功后中断测试：35 passed（最终复核以审查报告为准）。
- 发布目录回归（仅排除下面确认存在于 HEAD 的单项失败）：327 passed、1 skipped、1 deselected、117 subtests passed。
- 显式执行命名为 `*-tests.py` 的历史发布测试：113 passed、3 skipped、26 subtests passed。
- Python `compileall` 与 `git diff --check` 通过。
- 本机真实 Docker Desktop Engine 29.4.3 / Buildx 0.33.0 的只读检查确认：`ls --format '{{json .Builder}}'` 返回预期 Name/Driver 字段，build/prune 帮助包含本次使用的 `--load`、`--no-cache`、`--max-used-space` 参数。没有创建 builder、构建镜像或执行真实 prune；不替代生产版本核验。
- 已有失败：`test_release_native.py:100` 期待 Compose 配置链末项为 annotation，实际 `image-inputs-frontend.py` 已追加 materials。本轮未改两文件；从 Git HEAD 提取原文件到临时目录复跑，同样失败，退出码 1。未把这一项计为通过。

本次没有改应用、数据库或前端代码；测试范围是发布工具和模拟部署生命周期，未宣称做过真实生产演练。

## 服务器启用记录（2026-10-14）

用户追加授权后已完成实际服务器同步与初始化，未重放应用发布。审查快照为 `27aa7dbce2f209544dee113125a6a42b0fdbae4804c0a200befe6374aae23bad`。

- 工具入口：`/opt/hengxin-release-tools/current`，原子指向 `versions/<审查快照>`。同步50个运行工具/说明文件，逐一SHA256及Python语法验证通过。
- 共用台账：`/var/lib/hengxin-release/retention.json`（root、0600，目录0700）。国内及身份当前 `da722ad`、上一成功 `c9bd4d2`；海外当前 `7479264`、上一成功 `53cf1de`。上一版经真实部署前保存的Compose及成功验证记录核实，未按日期推断。
- 专用 `hengxin-release` builder 已创建配置，driver为docker-container、状态inactive。未bootstrap、构建或prune；下一次新构建时启用独立缓存。
- 从新入口实际运行 `preview` 成功，待删列表为空；当前四个项目镜像都受保护。
- 前后43个容器（含21个运行容器）的ID、镜像、启动时间、重启次数、状态及挂载一致（挂载按目标路径排序比较）；18个卷列表一致，3个原生工作服务PID/启动时间一致。
- 公网首页200，国内与海外鉴权接口未登录401，均与操作前一致。未执行数据库写入、迁移、业务文件删除或服务重启。
- 服务器证据：`/root/hengxin-retention-enable-20261014/`；本地证据：`output/retention-enable-20261014/`（含before/after、enabled、verification与工具manifest）。

日后查看预览：

```sh
python3 /opt/hengxin-release-tools/current/scripts/release/release-retention.py preview
```

后续发布使用此目录中与目标发布版本匹配的Python入口，或使用包含已审新机制的新发布包；它们共享默认台账。历史包中的旧入口不会自动被改写，不能继续用旧脚本期待自动清理。现有入口仍有固定版本/迁移检查，不能拿旧版本入口重放已完成发布。本次未建立定时删除任务，回收由新发布流程验证成功后触发。
