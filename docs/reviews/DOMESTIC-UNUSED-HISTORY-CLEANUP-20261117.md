# 国内未使用历史任务一次性清理审查

日期：2026-11-17。结论：**Stage 1 PASS；Stage 2 PASS；无阻断项**。这是执行前的脚本审查，不是生产清理完成证明。reviewer 没有执行 apply、生产写入、修复或提交。

## 审查身份与边界

- candidateId：主 Agent 未提供；两份代码位于 Git 忽略的 output，不在 harness 代码快照内。本报告只批准下列原始字节 SHA256，不能用于批准当前前端变更，也不替代 review-prepare/review-approve 的受控代码凭据。
- `output/cleanup-unused-history.py`：`31cfa1e1fb9493903ac8cfd0e550cb922fc97420b64527bb39ab145851dc2904`。
- `output/run-unused-history.py`：`62f2fa007cd0c7d4413f159bcca4d37c0f969f98bd4bcb7235e46039834081c1`。
- 固定清单 `output/tasks-unused-manifest.json`：`dd28af04d88afafd35918767b448101c58d89bac3bf47d0519727e095be2ca22`。审查开始、结束两脚本摘要相同；清单与 inspect 原始 JSON 相等。不公开成员完整身份及任务内容。
- 依据：本次用户明确授权“你先帮我把那些没有实际使用过的历史任务 直接全部强制清理掉 除了 张帅 的”；AGENTS.md 的实际资源清理验收和国内边界；`docs/INTRANET-RELEASE-TOOLS.md:5`、`docs/DOMESTIC-TASKS-DEPLOYED-20261117.md:7` 的现行版本。此次是授权数据维护，无新增产品功能或 UI，设计/邻居页面视觉比较不适用。
- 以下 `B/` 表示 `hengxin-smart-image/backend/`。只读追踪的删除、上传、维护锁及原生调用实现与指定生产提交 `02ddb53749a9e16580a965b64ea13ffdd19aef51` 无内容差异；工作区其它前后端修改不在本次范围。

## Stage 1：功能与授权范围

| 验收项 | 结论与证据 |
| --- | --- |
| 仅清理未使用历史任务 | 完整。`output/cleanup-unused-history.py:87` 限制历史名称、version=1、无删除状态；`:33` 检查 thread/turn/upload/archive/task_request/deletion 全为零；`:43` 另外扫描真实对象和执行目录。固定清单为17任务17会话，6类usage计数均0，真实对象、文件、目录均0。 |
| 张帅及已用任务保留 | 完整。`:82` 校验固定管理员身份和名称，`:85` 排除所有同名账号，`:88` 排除保护成员；`:67` 对剩余任务/会话、全部12类使用表及张帅workspaces做全行摘要。候选中保护成员数0。剩余6任务7会话是预期验收值，尚未执行后验。 |
| 固定范围及漂移整批拒绝 | 完整。`:103` 要求17项；`:106` 单事务，`:107` 权限锁、`:108` 全候选成员资格核验、`:110` admission锁、`:113` 全候选任务/会话锁；`:115` 重新生成完整清单且要求严格相等，先校验全部再提交任何删除。 |
| 并发上传/执行边界 | 完整。`B/app/modules/domestic_studio/task_service.py:70` 对会话使用NOWAIT锁；`file_service.py:45` OS锁贯穿上传，`:48` 先提交Upload意图再PUT，`:59` 持会话锁写存储，`:67` 重验权限。上传已开始则候选usage或NOWAIT检查拒绝；尚未建立意图则受权限锁阻挡，删除提交后由`conversation_service.py:42`拒绝。未发现等待会话锁造成的权限锁反向死锁。 |
| 原生删除而非硬删/假成功 | 完整。维护脚本`:119` 仅调`task_deletion.request`；`B/app/modules/domestic_studio/task_deletion.py:35` 持久化删除状态，`conversation_deletion.py:51`创建清理回执。`conversation_cleanup.py:142` 取得共享OS锁，`:169`固化资源清单，`:179`删除资源，`:186`删除会话及过程记录，最后更新回执。Task保留必要墓碑元数据符合本次交接约定。 |
| 实际资源回收验收 | 完整。维护脚本`:125`逐任务核原生deleted状态、会话物理消失、两类对象前缀与执行目录不存在；`:142`核保留数据摘要。当前原资源为0，预期文件净释放0字节；清理回执、审计及维护锁可产生少量元数据，不能宣称释放大文件或数据库文件空间。 |
| 目标环境与海外隔离 | 完整。`output/run-unused-history.py:15`核主机、`:19`核pending/schema、`:20`核固定后端commit、`:21`选择国内deletions上下文、`:22`核实际cwd。没有迁移、服务重启、海外写入或付费模型调用路径。 |
| 真实操作者审计与重试 | 完整。维护脚本`:120`追加MemberAudit，操作者为固定管理员，记录目标和清单摘要；`:106`使审计与删除受理同事务。重复apply因快照变化拒绝，不重复提交。网络失败可能已提交，须先verify；delete_failed不在此脚本中自动重开，应读取回执后另行审查定向恢复，不能重新扩大清单。 |

部分实现、未实现、Spec漂移：本次授权范围内未发现。没有增加管理员跨用户通用删除接口；仅此固定清单维护调用。

## Stage 2：质量、安全与验证

- 代码质量通过：153行核心脚本、35行运行入口，inspect/apply/verify分离；异常导致单事务回滚，SSH/原生执行有超时。依据：核心脚本`:81`、`:102`、`:125`，运行入口`:25`。未为一次性维护引入生产模块或依赖。
- SQL及凭据扫描通过：核心脚本`:30`拼接的表名/where均来自本文件固定调用，任务参数使用绑定；无用户SQL输入、硬SQL DELETE、eval或硬编码密码/token。运行入口`:12`使用repr构造Python值，`:25`使用参数数组调用SSH。`hengxin-smart-image/scripts/migration245/unify_release.py:59`捕获原生输出并对异常做脱敏；`:138`只读服务PID/environment，`:160`以原服务UID/GID、env、cwd执行，不伪造登录。注意contexts会读取所有已登记原生服务元数据，实际运行仅选择国内deletions，未打印环境凭据。
- 路径边界通过：核心脚本`:49`核root及父级符号链接，`:53`核会话目录在执行root内；原生`B/app/modules/domestic_studio/conversation_cleanup.py:65`核对象前缀、目录命名空间，`maintenance_lock.py:19`、`:26`、`:46`核生产锁目录与文件身份。此次17个目录原本均不存在。
- 验证真实性：reviewer独立读取既有真实inspect日志并与manifest比较、统计范围、执行纯语法compile，没有通过执行维护模块来编译，没有生产写入或模拟删除冒充实测。没有执行生产故障注入；删除完成必须由主 Agent 后续取得verify回执，核17 deleted、保留6任务7会话以及preserved_unchanged=true。

原始检查输出（退出码0；compile仅编译字符串，不执行模块）：

```text
manifest_sha256=dd28af04d88afafd35918767b448101c58d89bac3bf47d0519727e095be2ca22
inspect_log_matches_manifest=True
tasks=17
conversations=17
protected_candidates=0
usage_totals={'archives': 0, 'deletions': 0, 'requests': 0, 'threads': 0, 'turns': 0, 'uploads': 0}
resources={'objects': 0, 'file_count': 0, 'file_bytes': 0, 'directory_exists': 0}
preserved_tables=15
COMPILE PASS output\cleanup-unused-history.py
COMPILE PASS output\run-unused-history.py
```

最终可执行结论：仅以上两份SHA256脚本及固定清单可进入已授权apply；任何脚本或清单改动需重新复核。执行后verify失败、漂移或回执未完成时，不得报告清理成功。
