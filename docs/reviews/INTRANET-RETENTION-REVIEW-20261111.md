# 内网源码保留两版独立审查

日期：2026-11-11。角色：独立 code-reviewer，使用 `.agents/skills/code-review/SKILL.md`。

- candidateId：`f8bc2039dcb56931f4c4e667f40e9f41424ae57393e4b9b9d62da7b19aa85604`。
- Stage 1：**FAIL**（1 HIGH、1 MEDIUM）。Stage 2：**未执行**，按技能规定在 Stage 1 HIGH 处停止。
- 审查范围：`scripts/release/intranet/release.py`、`cleanup.py`、`cleanup_history.py`、`cleanup_refs.py`、`test_release.py`、`test_cleanup.py`、`test_cleanup_refs.py`；追溯既有 `snapshot.py`、`operations.py`、`stage.py`、`release-retention-state.py` 及 `migration245/unify_release.py` 的校验契约。
- 源合同：`docs/INTRANET-RELEASE-TOOLS.md:52` 自动保留两版全部条目，`Product-Spec.md:1482`，`DEV-PLAN.md:1694`。无 UI 变更，设计稿、页面视觉对比不适用。
- 审查开始及结束检查时 `review-status.currentId` 均等于以上 candidateId。报告只评价该快照；主 Agent 后续修复须重新 prepare、独立审查，不得将本报告登记 PASS。
- reviewer 未操作线上、未修改实现、未提交；仅写此报告并执行本地测试、编译与隔离引用扫描探针。

## Stage 1 问题

### HIGH S1-01：systemd 引用扫描遗漏未加载的 vendor 单元

合同 `docs/INTRANET-RELEASE-TOOLS.md:55`：核查 systemd 配置引用，无法核查则停止删除。

实现 `scripts/release/intranet/cleanup_refs.py:94` 使用 `systemctl list-units --all --type=service`，只覆盖当前内存中单元；`:100` 仅递归 `/etc/systemd/system` 和 `/run/systemd/system`。未加载、未启用但已安装于 `/usr/lib/systemd/system` 或 `/usr/local/lib/systemd/system` 的服务及其 drop-in 不在扫描范围。若该服务 WorkingDirectory/ExecStart 指向历史运行版本，该引用不会进入保护集；`cleanup.py:75` 和 `:83` 会把完整且属于 history 的版本列为删除候选，`:119` 可以删除它。后续启动该服务将失去所需源码。

这不是假设命令语义：[systemctl 官方文档](https://www.freedesktop.org/software/systemd/man/latest/systemctl) 明确区分内存中单元与 `list-unit-files` 的已安装单元；[systemd.unit 官方文档](https://www.freedesktop.org/software/systemd/man/250/systemd.unit.html) 列出 vendor 单元搜索路径。

本地隔离探针使用实际 `collect()`，替换外部进程、台账和文件系统入口：设置未加载的 vendor 服务引用 old，`list-units` 为空，vendor 文件可读。原始输出：

```text
configured_unit=/usr/lib/systemd/system/historical-worker.service
configured_reference=/opt/hengxin-unified-releases/old/backend
scanned_unit_folders=['/etc/systemd/system', '/run/systemd/system']
old_reference_protected=False
```

修复标准：覆盖实际 systemd 单元搜索路径及相应 drop-in，未加载单元也必须核查；遍历/读取不完整应拒绝删除。增加 vendor-only 未加载单元的回归测试。现有 `test_cleanup_refs.py:53` 只模拟 loaded service，不能证明完整覆盖。

### MEDIUM S1-02：部分删除失败后，重复清理不能继续回收

合同 `docs/INTRANET-RELEASE-TOOLS.md:57` 要求中途异常可重复执行。

实现 `cleanup.py:119` 调用递归删除，`:124` 捕获错误并中止；如果错误发生在已删除部分清单文件之后，留下的不完整目录下次在 `:79` 重新进入 `eligible()`，`:50` 调用完整 manifest 校验。既有 `hengxin-smart-image/scripts/migration245/unify_release.py:184` 将缺文件判为 inventory mismatch，于是 `cleanup.py:80` 将残目录列为 `unrecognized-or-unsafe-release`，以后也不再续清。回执没有被恢复逻辑消费。源码控制流可确定此结果；reviewer 未在 Linux 执行真实部分删除故障注入。

现有 `test_cleanup.py:165` 的故障替身在删除任何内容前直接抛 OSError，只证明无修改失败；`:74` 的重复清理只覆盖完整成功后的空操作。两者没有证明部分删除后重试。

修复标准：保留可验证的私有删除凭据，在重新验证根、目录身份、剩余内容及引用后安全续清，或提供等价恢复路径。不能简单关闭 manifest 校验或把任意残目录加入可删范围。增加真实“先删一个清单文件再报错”的隔离测试及换目录/新增引用拒绝用例。

## Stage 1 逐项对照

下表“实现匹配”指该条代码与合同对应；Linux 专用用例在本机跳过，未冒充本机实测。整阶段仍为 FAIL。

| 合同条目 | 结论 | 实现及验证证据 |
|---|---|---|
| 成功发布、验证、持久化台账后自动清理 | 实现匹配 | `release.py:112` 验证、`:123` 保存 completed、`:132` 调用 cleanup；`test_release.py:104` 断言调用时持久台账已更新 |
| 失败/未完成发布不清理 | 实现匹配 | `release.py:124` 失败恢复并抛出，清理在 try/except 外；`cleanup.py:89` pending 拒绝；`test_release.py:123`、`test_cleanup.py:86` |
| 清理失败不回退已成功业务 | 实现匹配 | `release.py:132` 位于恢复块之外，`:137` 捕获 housekeeping 异常；`test_release.py:216` full/frontend 两模式断言 restore 不被调用 |
| 手动默认预览、--apply 才删除 | 实现匹配 | `release.py:191`、`:207`，`cleanup.py:93` 预览提前返回；`test_release.py:233` 实测参数行为 |
| 共用发布锁 | 实现匹配 | `release.py:202` 锁包含 cleanup；`test_release.py:233` 在 execute 内二次获取锁应失败，本机通过 |
| 清理前核验线上完整基线及 runtime | 实现匹配 | `cleanup.py:91` 使用 runtime=True；`snapshot.py:89` 核验源码/服务/依赖/schema/数据/config，`:137` 比较全字段；`test_cleanup.py:93` 覆盖漂移拒绝 |
| init/verify/recover/rollback/cancel 不自动清理 | 实现匹配 | `release.py:41`、`:151`、`:167`、`:177`、`:214` 无 cleanup 调用；唯一自动调用点 `:132` |
| current/previous 前后端并集保留 | 实现匹配 | `cleanup_refs.py:29`–`:38`，`test_cleanup.py:63`、`test_cleanup_refs.py:15` 覆盖分离路径 |
| 原生解释器、二进制及依赖引用保留 | 实现匹配 | `cleanup_refs.py:39`–`:42` 保存并解析解释器路径；`cleanup.py:48` 依赖目录拒绝；`test_cleanup.py:177`、`:115` |
| 全部容器，包括停止容器的挂载 | 实现匹配 | `cleanup_refs.py:80` docker ps -aq、inspect 所有结果，`:84` 包括祖先目录挂载保护；`test_cleanup_refs.py:53`、`:76` |
| 宿主进程 cwd/exe/命令/环境/fd/maps | 实现匹配 | `cleanup_refs.py:45`–`:74` 读取各项，读取权限错误向上传播，进程仍存在但元数据消失时拒绝；`test_cleanup_refs.py:29`、`:45` |
| 挂载点及 systemd 配置引用，检查失败关闭 | **部分实现，HIGH** | `cleanup_refs.py:87` mountinfo roots/targets 解码；systemd 不完整，见 S1-01；读取异常传播不弥补漏扫目录 |
| venv/依赖/链接/不安全权限/非清单文件/挂载保守保留 | 实现匹配 | `cleanup.py:27`–`:60`；`unify_release.py:69` 禁 symlink、非 root/可写权限及硬链接，`:167` 完整清单；`test_cleanup.py:115`、`:134` |
| 仅受控根的完整历史运行版本，stage 不删除 | 实现匹配 | `cleanup.py:29` 固定直接子目录，`:75` history 门槛；`cleanup_history.py:12` 台账及 applied 事务识别，`:42` 摘要绑定原 compose；`test_cleanup.py:63`、`:182` |
| 删除前重查引用、目录身份 | 实现匹配 | `cleanup.py:108`–`:119` 重查 root fd 身份、引用和候选 inode/device；fd-relative rmtree，`:95` 要求平台支持抗符号链接删除；`test_cleanup.py:150` |
| 不复制待删源码，不删除事务备份/镜像/业务数据/旧根依赖 | 实现匹配 | `cleanup.py:119` 唯一删除点，目标受控 root 的直接子目录；`cleanup_history.py:12` 只读事务；本次 diff 无其它删除或公网入口 |
| 兼容静态资源保留 | 实现匹配 | 原 `release.py:67` keep_assets 保持；`cleanup.py:51` 验证 legacy compatibility-files 与清单一致；`test_release.py:188`、`test_cleanup.py:125` |
| 计划/回执私有保存、保留原因和删除路径 | 实现匹配 | `cleanup.py:92`、`:102`、`:122`、`:135`；`release-retention-state.py:86` 0700 状态根，`:119` mkstemp/原子保存。apply 删除前落盘计划；preview 返回只读计划 |
| 同范围前后占用、回执增长、无额外源码副本 | 实现匹配，线上净回收待验收 | `cleanup.py:14` st_blocks 不跟随链接，`:98`、`:129` 前后同 root，`:136` 计状态目录增长，`:137` 净额；`test_cleanup.py:74` 对比真实前后计量。主 Agent 需另计安装工具占用，不能把 preview 候选体积认作已释放 |
| 中途异常可重复执行 | **部分实现，MEDIUM** | 完整成功后重跑可空操作；部分删除后不能恢复，见 S1-02 |
| 不改成功台账、不重新切换业务 | 实现匹配 | `cleanup.py:87` 只读 data、保存独立报告，`:119` 只删候选源码；`test_cleanup.py:165` 对比 intranet.json 字节 |
| 隔离测试覆盖清单 | 部分覆盖 | 已覆盖分离状态、依赖、失败发布、清理失败、链接/挂载/未知目录、完整成功重复；缺 vendor 未加载单元和部分删除重试，见以上问题 |
| 独立审查后安装、预览、存量清理、PID/容器/版本/数据不变 | 未验收，不冒充代码缺陷 | 合同 `:58` 的后续交付环节；当前快照 FAIL 不允许进入激活与删除。本地读取 `output/intranet-retention/preview.log:1` 有两侧 RUNTIME_OK 和唯一 36,528,128-byte 候选，deleted=[]；这是预览证据，不是净释放或部署验收 |

完整实现项如上。未完整实现项：systemd 配置引用保护、部分删除故障重试。未实施交付：新工具激活及实际清理验收。未发现超出本轮合同新增业务功能的 Spec 漂移；限本次七个代码文件 diff 的范围。无 UI 文案或页面变化。

## 本地验证原始输出

默认解释器不含 pytest，首次未能执行：

```text
C:\Users\82358\AppData\Local\Programs\Python\Python312\python.exe: No module named pytest
```

改用仓库现有 venv，未安装或升级依赖：

```text
hengxin-smart-image/backend/.venv/Scripts/python.exe -B -m pytest -p no:cacheprovider scripts/release/intranet hengxin-smart-image/scripts/migration245/test_unify_release.py -q
ssssssssssssssssssssssss.........................
................ [ 61%]
.........................................                                [100%]
82 passed, 24 skipped, 7 subtests passed in 12.79s
```

24 个跳过项为 Linux 文件权限、/proc、符号链接及 fd 删除语义；本机 Windows 无法据此证明实际删除行为。主 Agent 提供 Linux `106 passed, 7 subtests passed` 声明，本 reviewer 未独立执行线上测试，不用声明替代本地原始输出。

编译验证采用 Python `compile(path.read_bytes(), str(path), 'exec')` 遍历 `scripts/release/intranet/*.py`，不生成 pycache：

```text
COMPILE_OK 15 Python files
```

## Stage 2

未执行。Stage 1 存在 HIGH，不能输出代码质量、安全扫描或视觉检查的 PASS。本报告不授权 review-approve；修复后重新固定快照并从 Stage 1 开始审查。
