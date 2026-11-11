# 内网完整发布保留两版：最终独立审查

- **Stage 1：PASS。Stage 2：PASS。** 未发现本次范围内需要阻断的功能、安全或质量问题。此结论是候选代码及发布前验证通过，不是生产激活或存量清理完成。
- candidateId：`11965bff16c52c557e5565aba95563111bf9cd7b8d52a9d96c0093b5fad4421f`。审查开始及结束前读取 `review-status` 均为同一 currentId；未观察到受控代码变化。
- 审查范围：`scripts/release/intranet/` 新增 `catalog.py`、`catalog_import.py`、`artifact_gc.py`、`image_gc.py`、`full_cleanup.py`、`smoke_docker.py` 和四个对应测试文件；修改 `cleanup_history.py`、`cleanup_refs.py`、`release.py`、`stage.py`、`test_engine.py`、`test_release.py`、`test_stage_web.py`，以及本轮 Spec、CHANGELOG、DEV-PLAN、发布合同。同时读取既有 source GC、engine、snapshot、operations 和私有 Store，检查接线影响。
- 依据：`Product-Spec.md:1484` 及 `docs/INTRANET-RELEASE-TOOLS.md:80` 的七条最终合同、`:95` 的实施边界；已读取 AGENTS、code-review skill 和 `docs/HARNESS-REVIEW.md`。按 Stage 1 全量复核后进入 Stage 2，没有只审前轮差异。
- reviewer 仅审查、运行本地隔离测试并写本报告；没有连接生产、修复代码、激活工具、删除生产对象或提交 Git。Linux/Docker 证据由主 Agent 执行，本审查读取并核对版本绑定。

## Stage 1：合同逐项核对

| 合同 | 结论 | 实现与验证证据 |
|---|---|---|
| 1. 两次成功完整部署为唯一时钟；成功验证后原子保存完整记录 | 完整实现 | `catalog.py:110` 的 advance 无条件把原 current 移到 previous，镜像相同也推进；`:117` 同步状态摘要、17 容器镜像映射和事务。`release.py:115` 完成 apply、运行检查、源码目标检查后在 `:125` 构造 catalog，`:126` 同一次 save；Store 在 `scripts/release/release-retention-state.py:119` fsync、replace、目录 fsync。`image_gc.py:23`、`:40` 校验准确的 17 服务集合。`test_catalog.py:63` 覆盖 A/B/C 相同镜像仍推进；`test_release.py:111` 核对清理调用时成功台账已落盘。 |
| 2. 源码/镜像/包/事务备份的完整清理和引用保护 | 完整实现 | `full_cleanup.py:28` 分派三类资源；`catalog.py:168` 保护两版源码、staged 和两版事务及 last/pending。`cleanup_refs.py:143` 扫描全部容器挂载、进程、挂载及 systemd，`:9` 包括未加载单元。`artifact_gc.py:186`、`:189`、`:195` 检查 owner、路径引用和宿主引用；`:73` 拒绝依赖内容。未知遗留由 `catalog_import.py:93` 明确 unowned，未知镜像由 `image_gc.py:106` 保留。`test_cleanup_refs.py:29`、`:71`、`:107`，`test_artifact_gc.py:79`、`:94`、`:211` 覆盖实际解析、停止容器、保留 owner 和无法核查时拒删。 |
| 3. 源码沿用旧清理器；镜像仅登记的旧 ID、非强制且不 prune 父层 | 完整实现 | `full_cleanup.py:29` 直接调用既有 `cleanup.execute`；`cleanup_history.py:15` 改用已持久化来源，避免删掉原事务后失去识别能力。`image_gc.py:111` 只选择 known 且不在两版/全部容器引用中的 ID；`:121` 删除前再次检查，`:133` 固定 `docker image rm --no-prune`，无 force、全局 prune、容器/卷删除。`test_image_gc.py:75`、`:94`、`:103`、`:111`、`:131` 验证参数、同镜像时钟、停止容器、新引用和 Docker 冲突；最终真实 Docker 隔离日志亦通过。 |
| 4. 包身份摘要、防复用、事务独立生命周期、删除前核查和部分失败恢复 | 完整实现 | `stage.py:75`—`:83` 拒绝已登记包路径，解包前采 proof、解包后再验并登记；`:18`—`:26` 拒绝历史名称与已存在目录。`catalog.py:104` 登记 staged/package，`:120` 事务 owner 使用事务本身，不绑定共享后端源码寿命。`test_catalog.py:81` 使用真实文件清理 A 的 data-backup，同时保留共享 A 源/包及 B/C 备份。`artifact_gc.py:18` 限定目录边界，`:54` 采身份及文件清单，`:139` 删除前再次核实引用和目录描述符，`:208` 持久化原证明，`:90` 仅接受原清单剩余子集。`test_artifact_gc.py:112` 实际注入部分删除并续清；`:130` 拒绝新文件、摘要、身份及注册表篡改。 |
| 5. 首次接管来源绑定；旧备份归属；未知及迁移资料保护 | 完整实现 | `catalog.py:55` 从真实 current/previous 初始化；`:77`、`:82` 要求当前匹配 applied 及上一版唯一事务。`catalog_import.py:15` 核对 applied/candidate 摘要；`:42` 核对包内提交、清单和真实字节；`:76` 同时校验七个原生 env 摘要、两侧 DB 容器身份、dump 大小和 SHA256。只有固定命名边界且具上述证据才注册旧 unify/backup，其他材料 unowned。`test_catalog.py:122`、`:149`、`:177`、`:196`、`:202`、`:220` 覆盖歧义、未应用、篡改、未知事务及旧备份拒绝。 |
| 6. 默认预览、分类隔离、不回退成功业务、真实空间核算 | 完整实现 | `release.py:194` 默认无 --apply，`:208` 使用共享锁；`:133` 将清理置于发布恢复块之外。`full_cleanup.py:12` pending 先阻断、核验当前运行基线；`:25` 只在 apply 写台账；`:35` 每类单独捕获失败继续其它类别。`artifact_gc.py:103` 按 inode 去重实际 blocks，`image_gc.py:72` 使用引擎 LayersSize，`full_cleanup.py:17`、`:50` 用同范围前后占用计入台账和回执变化。`test_full_cleanup.py:50`、`:77` 验证预览不写、分类异常不改变成功状态；`test_image_gc.py:215` 验证共享层仅按引擎差值统计。安装工具位于此运行时核算范围之外，其新增占用须在本次部署前后总体账中另行扣除，不能拿此 CLI 数值冒充整个安装净收益。 |
| 7. 隔离序列/失败/归属测试，真实 Docker、编译、独立审查，随后安装验收 | 发布前代码与验证通过；生产交付步骤待执行 | 本地 reviewer 独立运行 134 passed / 70 skipped / 7 subtests；最终 Linux 安装包 204 passed / 7 subtests，Docker 隔离 PASS，26 个发布 Python 文件独立编译通过，见下方原始输出。安装包 29 文件摘要重算与最终日志绑定一致。正式入口激活、最终初始化预览、授权存量删除、17 容器/7 服务/源码配置身份核对和净释放验收须由主 Agent 在本报告之后执行；没有将其算成已通过的生产验收。 |

失败不推进/不清理：`release.py:127` 恢复后保留 pending；`full_cleanup.py:12` 拒绝 pending。取消/恢复仅登记已核验事务，不推进成功时钟（`catalog.py:125`、`:139`，`release.py:153`、`:180`）。`test_release.py:132` 检查发布失败不调用清理；`:223` 覆盖 full/frontend 清理失败不回滚。

普通发布保持源码切换，不升级镜像/依赖/schema：`catalog.py:114` 明确拒绝部署期间全镜像集合变化；`release.py:64` 调用既有兼容校验；`test_catalog.py:110` 与 `test_release.py:74` 验证漂移/依赖变化拒绝。当前 9 镜像全在用，因此保留 9 个符合合同，不能为了“两个版本”删除在用镜像。

UI 一致性、视觉邻居对比：不适用。本次没有页面、样式或设计稿变化，新增行为是运维 CLI。引导真实性核对了 `docs/INTRANET-RELEASE-TOOLS.md:40`、`:58`、`:95` 与 `release.py:194`、`stage.py:61`：cleanup 默认预览、--apply、recover/cancel、版本包名限制及普通发布边界均有对应实现。

Spec 漂移：未发现额外业务页面、API、数据库表、自动依赖升级或全局清理。清理入口和新增模块对应上述七条合同。

## 前轮两项 HIGH 复核

1. **完整回退日志变化导致 catalog 拒绝：已修复。** `catalog.py:32` 对除 phase/recovering/paused/sockets 外的原始字段生成身份摘要；`:151` 仅 full 已登记事务且恢复状态/marker 合法时允许 started.json 变化；`:159` 继续要求目录身份、配置/备份等原文件不变并限制新增文件。`test_engine.py:82` 实际执行 `engine.apply()`、`engine.recover()` 后调用 catalog，检查原配置恢复、更新后的 started 摘要被接受，再篡改配置备份确认拒绝。此用例已在本地和 Linux 最终测试中通过，补上了前轮 engine/catalog 组合盲区。
2. **Docker smoke 将宿主未知镜像当 known：已修复。** `smoke_docker.py:48` 仅把本次创建的 old/previous/stopped 三个 ID 交给清理器；initial_images 只用于不变性断言（`:52`、`:68`）。`finally` 仅处理 created 列表且先校验本次唯一标签（`:57`—`:69`）。最终真实 smoke 输出证明旧测试镜像删除、上一版/停止/未知镜像保留，测试对象归零，生产 9 镜像/17 容器仍在。

## Stage 2：代码质量与安全

| 检查 | 结论及证据 |
|---|---|
| 文件大小/职责/结构 | PASS。26 个发布 Python 文件均未超过 300 行；新增实现分别为 artifact_gc 224、catalog 180、catalog_import 124、full_cleanup 57、image_gc 157、smoke_docker 76 行。资源类型与 orchestration 分离；公开数据流清晰，未引入 TypeScript any。入口 `release.py:26` 保留既有结构，分类职责见 `full_cleanup.py:28`。 |
| 测试真实性 | PASS。本地跳过的是 POSIX 描述符、权限、/proc、blocks 测试，并非把跳过算通过；同一最终文件集已在 Linux 全量执行。抽查 `test_artifact_gc.py:112` 的真实部分删除、`test_catalog.py:81` 的共享源与独立事务生命周期、`test_engine.py:82` 的真实恢复日志。Docker mock 的参数断言另有真实 smoke 补证（`smoke_docker.py:28`）。主状态机测试仍 mock 外部服务边界（`test_release.py:29`），不据此声称生产真实故障/回退演练完成。 |
| 错误处理 | PASS。`full_cleanup.py:35` 分类错误可观测；`release.py:138` 自动清理失败只告警，不触发业务恢复；`image_gc.py:131`、`:149` 区分命令失败、对象仍存在及最终核查失败；`artifact_gc.py:217` 保留失败凭据。无吞掉异常后宣称资源成功删除的路径。 |
| 安全扫描 | PASS。扫描 eval、shell=True、os.system、内嵌密钥、前端密钥变量、危险 HTML 和递归删除调用，未发现新增可执行注入或真实硬编码凭据。测试中的 VITE_SECRET 为已有隔离测试字面量（`test_package_release.py:40`）；固定 `/opt`、`/var/lib` 是明确边界而非外部输入。`artifact_gc.py:18`、`:37`、`:54`、`:139` 约束边界、无跟随打开、硬链接/挂载/权限与身份；`unify_release.py:69` 验证 root 所有及不可组/全局写。命令为 argv 列表（`image_gc.py:133`），输出只记录异常类型，不泄漏命令 stderr（`unify_release.py:60`）。 |
| 删除范围/净释放 | PASS。生产清理无全局 prune，无容器/卷删除；未知和引用对象保留。源码/事务清理无备份副本，部分失败仅保存摘要凭据（`artifact_gc.py:210`）。`full_cleanup.py:17` 统一测量与分类差值并存；安装工具额外占用仍属于后续部署验收范围。 |

本轮没有需要修复的 HIGH/MEDIUM 项，也没有为凑审查条数增加推测性问题。

## 原始验证输出与版本绑定

reviewer 本地命令：

```text
.\hengxin-smart-image\backend\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider scripts/release/intranet hengxin-smart-image/scripts/migration245/test_unify_release.py -q
sssssssssssssssssssssssssssss.s.............ssssssssssssssssssssssssssss [ 35%]
ssssssssssss............................................................ [ 70%]
............................................................      [100%]
134 passed, 70 skipped, 7 subtests passed in 14.71s
```

首次尝试系统 python 时原始输出为 `No module named pytest`，随后使用项目既有 venv 重跑成功；没有安装或修改依赖。

reviewer 逐文件执行 Python `compile(..., 'exec')`，无写入源码；原始输出：

```text
COMPILE_OK 26 Python files
```

独立按 `output/intranet-complete-retention/install_tools.py:12`—`:17` 的算法重算本地 26 个工具/测试文件加 3 个共享依赖文件，核对 `installation.json`。原始输出：

```text
INSTALLED_TEST_SNAPSHOT_MATCH 455fdb2cee7edcd4 29 files
```

已读取 `output/intranet-complete-retention/checks-455fdb2cee7edcd4.log:1`，原始输出：

```text
........................................................................ [ 35%]
........................................................................ [ 70%]
............................................................      [100%]
204 passed, 7 subtests passed in 5.06s

{"status": "PASS", "old_deleted": true, "previous_kept": true, "stopped_container_kept": true, "unknown_kept": true, "released_layer_bytes": 9118, "test_objects_remaining": 0, "production_images": 9, "production_containers": 17}
```

`output/intranet-complete-retention/run_checks.py:9` 在 Linux 测试前逐项核对安装包 SHA256 并 compile。以上 Linux/Docker 运行不是 reviewer 新连接生产执行；其本地内容摘要与当前候选一致。原预览 `preview-f3b3f843c8c86129.log` 只作既往来源材料，不用于冒充本候选最终生产预览。

## 审批交接与尚待部署的验收

本报告只为上述 candidateId 登记 **Stage 1 PASS / Stage 2 PASS**。主 Agent 可依据 `docs/HARNESS-REVIEW.md:7`—`:10` 用 `review-approve` 关联本报告，再核对 `review-status`。reviewer 不写 `.needs-review` clean，也不代主 Agent登记凭据。

剩余生产步骤：激活最终工具、对最终入口执行初始化及预览、只处理确认归属且无人引用的旧对象、同口径统计扣除新工具/台账/回执后的净释放量、核验 17 容器及 7 原生服务身份/启动时间/代码/业务配置不变。恢复/失败仅有隔离测试，不声称生产故障演练或本轮收费模型任务已执行。这些是合同第 7 条的交付验收，不能被本代码 PASS 替代。
