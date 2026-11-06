# 历史技能副本清理最终候选独立审查

- 最终 candidateId：`0fd53137b91c9823ee21b9a2d7c6d310578211a4c99a3b6543a31a5d5c3edcd7`。
- 范围：`scripts/release/skill-history-files.py`、`scripts/release/skill-history-cleanup.py`、`scripts/release/test_skill_history_cleanup.py`。
- 行号简称：下文 `files.py` 指 `scripts/release/skill-history-files.py`，`cleanup.py` 指 `scripts/release/skill-history-cleanup.py`。
- **Stage 1：PASS。Stage 2：PASS。无未关闭 HIGH/MEDIUM 发现。** 本结论仅授权主 Agent 为上述最终快照登记审查凭据，不代替生产备份下载校验、加锁执行及执行后验收。
- 依据：AGENTS.md、code-review skill、docs/HARNESS-REVIEW.md、`docs/SKILL-HISTORY-CLEANUP-20261106.md:3-12` 及主 Agent 明确交接。最新清理授权覆盖 Product-Spec 中此前“不批量清理旧副本”的旧边界。
- reviewer 只读代码、执行 Linux 临时文件测试并写报告；未修代码、未提交、未生产操作、未执行模型调用。UI、设计稿及邻居视觉比对不适用：三个文件仅提供维护 CLI 和测试。

## 快照变化与问题闭环

审查期间主 Agent 修改代码两次，本报告逐次重新核对，未把旧结论覆盖新版本。

| 候选 | 当时结论 | 证据及闭环 |
|---|---|---|
| `35d02753f35824a4a048c126ebb388ac0a5788d7866ecda82a76adc0c01daaee` | Stage 1 FAIL，Stage 2 未执行 | 旧 files.py:51-56 仅 fsync 文件，无父目录同步。独立跟踪首次 purge 前事件为 `['fsync_file', 'fsync_file', 'purge', 'purge']`，目录同步数为 0，不满足持久保存 verified 收据要求。 |
| `31c9d5c8a6a78d2f82d63496f65fe01cb886002d0276021ed46f4a6085b2230d` | Stage 1 FAIL，Stage 2 未执行 | 新增目录同步解决前项，但旧 files.py:188-194 回滚每包后立即同步；持续目录 fsync EIO 在第一个回滚后中止，独立临时目录复现原路径存在 `[True, False, True]`，隔离余项 `[True, False]`。 |
| `0fd53137b91c9823ee21b9a2d7c6d310578211a4c99a3b6543a31a5d5c3edcd7` | Stage 1 PASS，Stage 2 PASS | 当前 files.py:188-205 先尝试全部逆序 rename，再汇总同步失败；持续 EIO 测试证明三个原路径全部恢复。save:60-66 在文件 fsync 后同步父目录。独立完整测试 11/11 PASS、编译 PASS。 |

目录同步判断依据 Linux 官方 fsync(2)：文件同步不能单独保证新目录项持久化，需同步父目录。此结论是系统调用语义与实际调用顺序证据，不声称实施了真实断电实验。[Linux fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html)

## Stage 1：逐项对照最终实现

下表脚本路径以 `scripts/release/` 为前缀；应用证据以 `hengxin-smart-image/backend/app/overseas/` 为前缀。

| 合同要求 | 结论 | 文件、行号及验证 |
|---|---|---|
| 仅固定海外 Studio 根、旧轮次技能包，不改当前 cache 和安装版本库 | 匹配 | cleanup.py:15-21 海外上下文及固定根；:167 限定独立工作目录；files.py:91-98 限定 UUID/rounds/UUID/skills/name 五段路径及根边界。范围测试拒绝越界及错误层级。 |
| 同会话、同名、完整字节及权限一致，每组原路径保留一份 | 匹配 | files.py:69-88 含根 `.`、子目录 mode/uid/gid 和文件哈希；cleanup.py:81-87 按 conversation/name/entries 分组。files.py:160-171 拒绝 keep/drop 重叠和跨会话，重验全部包；根 mode/owner 两项测试通过。 |
| 重新清点，关联数据库轮次、冻结安装版本，异常排除整会话 | 匹配 | cleanup.py:57-91 关联 Turn/Job，比对 round/control 输入及 DB payload，再核对冻结版本完整文件集合；异常会话从 selected 排除。不靠文件夹名推断版本。 |
| 独立内容备份、原路径清单和逐文件校验；本地确认后 apply | 工具实现匹配；外部操作尚须完成 | cleanup.py:95-103 保存 plan、备份并 verify、输出双 SHA；:110-116 同时核对外部确认的 plan/backup SHA 和脚本 SHA。files.py:119-153 每组一份备份，精确验证成员、根/子目录权限属主及文件字节。独立篡改备份实验被拒绝。reviewer 未下载生产备份，主 Agent 必须对最终候选重新 plan/backup，下载后调用 verify_backup 并核对双 SHA，不能复用旧候选确认。 |
| Task 行锁阻止同任务提交/删除，跳过全部在途及删除态 | 静态匹配；不冒称真实 DB 并发测试 | cleanup.py:120-139 Task 锁先于 context flock，检查两类删除记录和非终态/未退出进程。execution/queue.py:29 经 tasks/queries.py:19 锁 Task；tasks/deletion.py:34、studio/conversation_cleanup.py:114 同样先锁 Task。execution/claims.py:69-70 仅接受 queued，已被 busy_query 排除。studio/context_fs.py:167-186 采用同一 flock 文件。 |
| 锁内重验输入及完整保留/删除包，仅移动明确重复叶目录 | 匹配 | cleanup.py:140-144 重验 round 输入 SHA；files.py:169-185 重验 entries、精确 target、同设备 rename，保留清单内原路径。 |
| 非目标文件元数据、七表摘要和保留包比较后才能清除 | 匹配工具约定的元数据证据 | files.py:101-117 检查类型/mode/inode/uid/gid/size/mtime/ctime/链接目标；仅 drops 排除、其 skills 父目录放宽 size/time。:172-186 前后比较非目标及 keep。cleanup.py:24-39 摘要覆盖会话、轮次、上传、transcript、图片、产物和 jobs。无数据写入 SQL。atime 不在字段中；不能将证据说成所有扩展属性或访问时间也逐一保持。 |
| 首次 purge 前异常恢复；持久保存 verified 后清除 | 匹配 | files.py:60-66 文件 fsync 后目录 fsync；:175 journal 在移动前保存；:187 verified 保存仍在 rollback try 内；:188-205 全部逆序恢复后再汇总同步失败。真实 DB 漂移、ENOSPC、持续 EIO 回归验证原路径恢复。若文件系统本身拒绝 rename，代码逐项尝试并明确报需检查，不能虚构底层故障时恢复成功。 |
| purge 后故障保留收据、不假报全批成功 | 匹配 | files.py:207-212 错误向外抛出，cleanup.py:145-154 仅成功返回后写 completed/result。独立第二次 purge EIO：verified/journal 仍在、keep 完整、quarantine 剩一包，无成功返回。 |
| 聊天、上下文、附件、工作文件、历史输入和轮次目录保持 | 删除范围匹配；非模型续聊验收 | files.py:179-184 只移动技能包，:211 只清除隔离包。test_skill_history_cleanup.py:64-72 验证 history 字节、inode/mtime、keep、skills 父目录。真实生产保留/健康证据须执行后另验；本审查没有真实模型续聊结论。 |
| 实际量、保留量、跳过项及健康报告，不提交/部署应用 | 工具输出匹配；生产结果待执行 | cleanup.py:98-103、:145-154 输出计划/实际包数、allocated、preservedEntries、skipped 及汇总。健康检查由操作阶段完成，估算不算实际释放量。没有应用代码/API/表结构/UI 变更，未发现 scope creep。 |

完整实现：上述维护工具行为。部分实现/未实现：范围内无代码缺失；本地备份确认、生产 apply、实际回收及健康验收是后续操作，不声称已经完成。

## Stage 2：代码质量、安全与测试真实性

| 项目 | 结论与证据 |
|---|---|
| 职责、结构、长度 | PASS。files.py:13-213 为路径/清单/归档/回滚，cleanup.py:15-177 为业务筛选与 CLI，test_skill_history_cleanup.py:17-141 为隔离测试；实际分别 213/177/141 行，均未超 300 行。函数和变量可对应操作阶段，无 Any 类型绕过。 |
| 错误处理 | PASS。files.py:13-15 显式 require，不依赖可优化移除的 assert；cleanup.py:164 拒绝优化模式；files.py:188-205 对恢复失败汇总并报人工检查，保持备份与 journal；:207-212 不把 purge 异常转为成功。 |
| 密钥、执行和 SQL 扫描 | PASS。扫描 eval/exec、前端危险 HTML、KEY/SECRET/TOKEN、sk-ant/sk-proj、password 及 subprocess，未命中硬编码凭据或命令执行。cleanup.py:26-39 SQL 字符串拼接仅来自七个固定表名/固定 where 片段；conversation 通过 UUID 及 `:c` 绑定，不拼接外部输入。固定绝对路径 :20/:167 是明确操作范围门禁。 |
| 文件删除和归档安全 | PASS。files.py:18-35 拒绝父链 symlink、非普通文件及文件硬链接，O_NOFOLLOW 读；:91-98 目标结构严格，:207-211 仅允许 quarantine 子路径且要求抗 symlink rmtree。归档只逐项读取比对，不调用 extractall。前提是 root 管理目录、既有业务锁协议，不声称抵御拥有 root 权限的恶意并发篡改。 |
| 测试真实性 | PASS。11 项测试使用真实 Linux TemporaryDirectory 与真实 rename/rmtree/文件读取；root 权限测试在 WSL root 执行，未 skip。同步顺序通过 fstat(fd) 验证真实文件/目录类型，持续故障真正经过多个包回滚。额外独立篡改备份和第二次 purge 失败实验验证了失败拒绝及部分完成。 |
| 视觉与 Spec 漂移 | 不适用视觉；无漂移。三个文件均为 CLI 维护工具，无新页面或交互文案；业务范围见 cleanup.py:15-21、:157-177。 |

LOW 后续建议及验证边界：测试目前没有用真实 PostgreSQL 构造同时 enqueue/delete 与 apply 的争锁场景（cleanup.py:120-139）；本次锁结论来自对现有生产调用链的静态核对。未做实际断电/内核故障实验。正式执行必须保留逐会话收据、已核验本地备份及最终健康/数据保留证据，不能把单元测试通过当作已清理生产。

## 最终候选独立验证原始输出

命令：`wsl -u root -- python3 -m unittest discover -s /mnt/d/Work_Project/hengxin-smart-image/scripts/release -p test_skill_history_cleanup.py -v`

```text
test_backup_roundtrip_preserves_all_skill_bytes (test_skill_history_cleanup.HistoryCleanupTests.test_backup_roundtrip_preserves_all_skill_bytes) ... ok
test_changed_copy_is_rejected_without_removing_anything (test_skill_history_cleanup.HistoryCleanupTests.test_changed_copy_is_rejected_without_removing_anything) ... ok
test_cross_conversation_and_wrong_targets_rejected (test_skill_history_cleanup.HistoryCleanupTests.test_cross_conversation_and_wrong_targets_rejected) ... ok
test_database_drift_restores_every_moved_package (test_skill_history_cleanup.HistoryCleanupTests.test_database_drift_restores_every_moved_package) ... ok
test_links_refused (test_skill_history_cleanup.HistoryCleanupTests.test_links_refused) ... ok
test_persistent_sync_failure_still_restores_all_paths (test_skill_history_cleanup.HistoryCleanupTests.test_persistent_sync_failure_still_restores_all_paths) ... ok
test_receipt_fsyncs_file_then_parent_directory (test_skill_history_cleanup.HistoryCleanupTests.test_receipt_fsyncs_file_then_parent_directory) ... ok
test_receipt_write_failure_restores_every_moved_package (test_skill_history_cleanup.HistoryCleanupTests.test_receipt_write_failure_restores_every_moved_package) ... ok
test_remove_only_duplicate_packages_preserves_history_and_keep (test_skill_history_cleanup.HistoryCleanupTests.test_remove_only_duplicate_packages_preserves_history_and_keep) ... ok
test_root_owner_drift_is_not_a_duplicate (test_skill_history_cleanup.HistoryCleanupTests.test_root_owner_drift_is_not_a_duplicate) ... ok
test_root_permission_drift_is_not_a_duplicate (test_skill_history_cleanup.HistoryCleanupTests.test_root_permission_drift_is_not_a_duplicate) ... ok

----------------------------------------------------------------------
Ran 11 tests in 0.056s

OK
```

额外独立实验：真实临时包，第二个 rmtree 注入 EIO；随后归档重写保持文件长度但修改字节，调用 verify_backup。

```text
PARTIAL_PURGE_ERROR [Errno 5] Injected second purge failure
VERIFIED_AND_JOURNAL_RETAINED True
PARTIAL_PURGE_REMAINING [False, True]
KEEP_UNCHANGED True
CORRUPT_BACKUP_REJECTED Backup content differs
```

编译命令：

```text
wsl -u root -- python3 -m py_compile /mnt/d/Work_Project/hengxin-smart-image/scripts/release/skill-history-files.py /mnt/d/Work_Project/hengxin-smart-image/scripts/release/skill-history-cleanup.py /mnt/d/Work_Project/hengxin-smart-image/scripts/release/test_skill_history_cleanup.py
```

原始 Python stdout/stderr 为空，工具 `exit_code: 0`。WSL 启动另有 localhost/NAT 代理提示，终端编码乱码，不属于 Python 编译输出。最终 review-status currentId 必须保持上述 `0fd531...`；由主 Agent 对同一 candidate 执行 review-approve，本 reviewer 未写 clean、未登记批准。
