# 内网完整发布保留两版审查（首轮）

- 审查结论：**Stage 1 FAIL；Stage 2 未执行。** 两项 HIGH 均已通知主 Agent。主 Agent 随后修改代码，但本报告不批准修改后的版本。
- 派发 candidateId：`7c620917aafdcf928735f5f427099cb511410cacb240662261060a033d5cf9b1`。开始时 `harness.py review-status` 的 currentId 与该编号一致，approved 为 false。
- 范围：`scripts/release/intranet/` 新增 `artifact_gc.py`、`catalog.py`、`catalog_import.py`、`full_cleanup.py`、`image_gc.py`、`smoke_docker.py` 及四个新测试文件；修改 `cleanup_history.py`、`cleanup_refs.py`、`release.py`、`stage.py`、`test_release.py`、`test_stage_web.py`；对应 Product-Spec、CHANGELOG、DEV-PLAN 和发布合同变更。
- 依据：`Product-Spec.md:1484`、`docs/INTRANET-RELEASE-TOOLS.md:80` 的七条合同及 `docs/INTRANET-RELEASE-TOOLS.md:95` 的实施边界。读取了 AGENTS、code-review skill、快照交接协议。
- 审查方式：逐项源码与测试检查、真实日志读取、离线故障复现。未连接或操作生产，未修复实现，未提交 Git。

## Stage 1：发现的问题

### HIGH-1：完整发布回退后，成功事务的清单校验必定拒绝恢复日志变化

要求：既有 `rollback` 应恢复最近成功发布之前的版本，核验后清除 pending；恢复不推进成功保留时钟。见 `docs/INTRANET-RELEASE-TOOLS.md:43`、`:44`、`:95`。

原候选 `catalog.py:126` 的 `finished_attempt()` 对已经登记的成功事务仅允许新增 `rolled-back.json`，要求所有原文件哈希保持不变（原候选 `catalog.py:137`—`:140`）。但完整回退必经 `engine.py:212` 的 `recover()`，它在 `:225` 设置 `state['recovering'] = True`，重写 `started.json`，并在恢复过程中更新 phase、paused、sockets 日志。`release.py:161` 先完成实际恢复，再在 `:166` 调用 `finished_attempt()`，最后才保存清除 pending 的台账（`:167`）。因此正常完整回退已经恢复业务，却因 started.json 的合法变化报错，台账仍为 pending rollback，重复 recover 仍不能通过相同校验。

独立离线复现：复用 `test_engine.py:19` 的 EngineTests 隔离环境，执行真实 `engine.apply()` 和 `engine.recover()`；只将依赖 POSIX 的 artifact proof 替换为对应文件的实际 SHA256 采集，随后调用真实 `catalog.finished_attempt()`。原始输出：

```text
Changed original transaction files: ['started.json']
REPRODUCED: Recovered transaction content drift
```

测试盲区：原候选 `test_release.py:29` 将 catalog.before/advance 整体替换，`test_engine.py:107` 的成功回退测试没有连接完整发布 catalog，分别通过无法证明组合行为正确。

处理要求：受约束地识别恢复日志允许变化的字段，同时严格保护原始 prepared/context、配置和数据库备份；增加真实 engine 恢复与 catalog 的组合回归，再送新快照审查。

### HIGH-2：隔离 Docker 验证把宿主既存未知镜像纳入删除授权

要求：镜像仅删除已登记的本项目历史 ID，未知镜像保留；真实 Docker 验证须隔离。见 `docs/INTRANET-RELEASE-TOOLS.md:86`、`:90`、`:95`。

原候选 `smoke_docker.py:24` 读取全部既存镜像，`:49` 将 `initial_images | {old, previous, stopped}` 传为清理器的 known 集合。`image_gc.py:111` 按 `(present & known) - retained - referenced` 计算删除候选，因此宿主任何既存但无容器引用、且不属于两版 retained 的镜像都会被纳入删除。`smoke_docker.py:52` 的 initial_images 存在性断言发生在删除之后，不能防止误删。

此问题由明确的数据流和删除集合证明；未为复现而删除任何真实未知镜像。已提供的真实测试环境只有九个全部在用的镜像，所以该次日志没有显示实际误删，不据此认定脚本安全。

处理要求：known 仅限本次创建且明确允许测试删除的镜像；既存镜像只用于不变性校验。修复后重跑真实 Docker 隔离验证。

## Stage 1：七条合同逐项覆盖

| 条目 | 结论 | 实现与证据 |
|---|---|---|
| 1. 完整记录、17 容器、成功后原子推进 | 已实现主要路径；回退存在 HIGH-1 | 原候选 `catalog.py:97`—`:109` 推进 current/previous；`image_gc.py:23`、`:40` 校验完整服务集合；`release.py:115`—`:126` 先运行核验再保存；`test_catalog.py:63` 验证同镜像 A/B/C 仍按成功次数推进。 |
| 2. 各类引用与未知遗留保护 | 已实现所审路径 | `catalog.py:146` 保护两版源目录、staged、事务；`cleanup_refs.py:143` 扫描全部容器挂载、进程、挂载、systemd；`artifact_gc.py:186`、`:195` 检查 owners 和实时引用；`catalog_import.py:93` 显式登记 unowned。生产只读预览列出三个未接管目录，未将其列为删除候选。 |
| 3. 源码复用旧清理器、镜像非强制且不 prune | 主清理器匹配；隔离验证有 HIGH-2 | `full_cleanup.py:29` 继续调用既有源码清理器；`image_gc.py:91`—`:157` 只删除 known 旧 ID，保留所有停止容器引用，使用 `docker image rm --no-prune`，无 force；`test_image_gc.py:103` 覆盖停止容器，`:131` 覆盖删除失败。 |
| 4. 包登记、防复用、事务独立生命周期、部分删除续清 | 已实现所审路径；合法回退日志受 HIGH-1 影响 | `stage.py:75`—`:83` 拒绝包路径复用并记录证明；`:18`—`:26` 拒绝历史源名称；`catalog.py:107` 用事务自身作 owner，`test_catalog.py:80` 实际清除 A 事务并保留共享 A 源和 B/C 事务；`artifact_gc.py:90`、`:208`—`:216` 用持久原证明支持部分删除重试。 |
| 5. 首次迁移与旧备份归属 | 已实现所审路径 | `catalog.py:42`—`:81` 验证 current/previous 关联和唯一历史事务；`catalog_import.py:15` 核对 applied/candidate；`:42` 检查包内容哈希与提交；`:76` 核对七个 env 摘要、DB 容器身份、dump 大小和摘要。`test_catalog.py:123`、`:177`、`:202`、`:220` 覆盖歧义、篡改、真实包内容及旧备份拒绝。 |
| 6. 只读预览、分类失败独立、不回滚、净空间 | 已实现所审路径 | `release.py:133` 将清理置于发布恢复块之外；`full_cleanup.py:25`、`:35`、`:50` 区分预览/执行、分类捕获错误、计入 ledger/回执；`image_gc.py:72` 读取 Docker 去重 LayersSize。`test_full_cleanup.py:50`、`:77` 验证无写预览、分类异常与台账不变；`test_image_gc.py:215` 验证共享层差值。工具安装新增空间仍须由部署验收按同范围实际统计，不能以本次代码审查替代。 |
| 7. 验证、审查、安装和实际存量验收 | 部分完成，未达到交付 | 已读取 Linux 测试及 Docker 隔离日志，发现两项 HIGH；本轮未批准代码。新版本尚未激活、正式存量清理和服务不变性最终验收未由本审查验证。不得把预览和旧候选测试当成最终部署通过。 |

UI 一致性/引导真实性：本次变更均为发布 CLI 和运维文档，未新增页面或交互设计，视觉比对不适用。CLI 文档明确 cleanup 预览、apply、不可复用包名和普通发布不升级运行时（`docs/INTRANET-RELEASE-TOOLS.md:25`、`:40`、`:58`、`:95`）。

Spec 漂移：已检查本轮受控变更，未发现新增业务页面、API、数据库表或镜像升级功能；实现范围围绕本次完整发布保留合同。

## 已读取的验证原始输出与边界

`output/intranet-complete-retention/checks-d5eed81e11819956.log:1`：

```text
........................................................................ [ 35%]
........................................................................ [ 70%]
...........................................................       [100%]
203 passed, 7 subtests passed in 4.54s

{"status": "PASS", "old_deleted": true, "previous_kept": true, "stopped_container_kept": true, "unknown_kept": true, "released_layer_bytes": 9117, "test_objects_remaining": 0, "production_images": 9, "production_containers": 17}
```

这些是主 Agent 已运行、reviewer 读取的 Linux/Docker 原始证据；不是 reviewer 另行连接生产执行。测试全绿仍未覆盖上述两个缺陷。

`output/intranet-complete-retention/preview-f3b3f843c8c86129.log:1` 中两侧 RUNTIME_OK，预览 status=preview；源码/镜像 candidates 均为空，artifacts 仅 `/opt/hengxin-lan/unified-backup-20261111` 与 `/opt/hengxin-lan/unify-20261111`；三个初期准备目录在 unowned。该日志是前一安装包的预览，不作为修复后最终候选的验收。

编译：本轮 Stage 1 发现 HIGH 后，未独立执行 Stage 2 编译/质量检查。`output/intranet-complete-retention/run_checks.py:9`—`:12` 包含逐文件摘要校验及 Python `compile`，但所提供日志没有单独的编译结果行；本报告不伪造编译原始输出。

## 快照变化与交接

主 Agent 收到问题后已修改 `smoke_docker.py`、`catalog.py` 并新增 `test_engine.py` 的组合测试。审查过程中再次读取 review-status 得到 currentId `11965bff16c52c557e5565aba95563111bf9cd7b8d52a9d96c0093b5fad4421f`，与送审编号不同。

观察到的修复方向：smoke known 缩至本次三个测试镜像；catalog 保存恢复日志不可变身份，并允许特定恢复进度变化；新增真实 engine.apply/recover 与 catalog 组合测试。以上仅记录变化，不给修改版 PASS。主 Agent 将重新 review-prepare 并派发 fresh reviewer，从 Stage 1 开始复核全部范围及最终 Linux/Docker 证据。

**本报告只对原 candidateId 给出 Stage 1 FAIL。Stage 2 未执行；不得 review-approve，不写 `.needs-review` clean。**
