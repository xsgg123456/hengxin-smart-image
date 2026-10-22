# 自动清理统一修复 · 第三候选独立审查

- candidateId：`e7065e207c2177764b4a71479c8fe44d5cbac22f7d59441dc34f39390e6ddced`。
- **Stage 1：PASS。Stage 2：PASS。** 本范围未发现待修复 HIGH/MEDIUM；可由主 Agent 为上述同一 candidateId 登记两阶段 PASS。本结论不授权提交或部署；Windows 临时目录收尾受工具策略阻止的限制见文末。
- 范围：相对已批准候选 `e40dcd0f8dd9823e4cbb5752a2a4ed376c19f61c6a2365f7ec39b7e42537be5d` 的 14 个 cleanup 增量代码/测试文件。下文 `backend/` 相对 `hengxin-smart-image/`，其他路径相对仓库根。
- 已读 AGENTS、code-review skill、快照协议、Product-Spec/DEV-PLAN 顶部、修复合同全文及前两轮失败报告。前两轮失败没有被旧通过结果抵消，本次从 Stage 1 重新审查。
- 原 records/UI/发布准备继承 `docs/RECORDS-SCOPE-REVIEW-20261022.md:1` 的已审范围；本次 review-status 的 changedFiles 只有下列 cleanup 文件，没有扩展该 UI 验收。
- reviewer 不修改业务代码，不提交、不部署、不访问生产、不写 clean。最终凭据由主 Agent 对同一 candidateId 登记。

## 审查范围

生产代码：`backend/app/execution/cleanup_paths.py`、`cleanup_diagnostics.py`；`backend/app/retention/api.py`、`objects.py`、`paths.py`、`worker.py`；`backend/app/modules/api_image_edits/deletion.py`、`deletion_paths.py`。

测试：`backend/tests/test_cleanup_paths.py`、`test_cleanup_mounts.py`、`test_cleanup_diagnostics.py`、`test_cleanup_retention_safety.py`、`test_cleanup_retry_pg.py`、`test_retention_paths.py`。同时读取相关既有保留、并发、显式删除与统计测试核实契约。

## Stage 1 · 合同逐项对照

| 合同/验收项 | 实现与验证证据 |
| --- | --- |
| 1. 自动缓存/历史与显式删除使用单一底层，入口参数保持 | 完整实现。`backend/app/retention/paths.py:5` 透传 cache_only；`backend/app/modules/api_image_edits/deletion_paths.py:8` 只增加原 api-edits 前缀，均调用 `backend/app/execution/cleanup_paths.py:276`。`backend/tests/test_retention_paths.py:9`、`test_api_task_deletion_paths.py:66` 和本轮 Linux 真实目标哈希验证覆盖两个真实入口。 |
| 1. 数据库和对象回收职责不合并，海外保持 | 完整保持。`backend/app/retention/api.py:120` 目录完成后才在 `:123` 清历史；`backend/app/retention/objects.py:85` 独立对象回收；`backend/app/modules/api_image_edits/deletion.py:127`、`:129`、`:130` 保持显式删除目录/对象/记录阶段。对应 diff 除共享路径接线与脱敏诊断不改变这些业务规则；14 文件无海外文件、迁移或 API 合同新增。 |
| 2. UUID、根/祖先/目标身份及不跟随链接 | 完整实现。`backend/app/execution/cleanup_paths.py:278`、`:280`、`:283` 规范化根和 UUID、拒绝父路径；`:59`、`:65`、`:67` 用 no-follow stat/open 和 inode/device/type 校验；`:166` 从根祖先逐级打开，`:190` 复核。`backend/tests/test_retention_paths.py:42`、`:53`，`test_cleanup_paths.py:53`、`:132` 验证非法标识、非目录、链接及预检后目标替换；失败时 sentinel 保留。 |
| 2. 精确工具链接仅 unlink 自身 | 完整实现。`backend/app/execution/cleanup_paths.py:26` 同时约束 6 段路径、arg0 名称、4 个工具名称与 `/opt/codex`；`:97` 仅 readlink，`:78` 以 O_PATH/O_NOFOLLOW 检查叶节点，`:119` 使用 dir_fd unlink。`backend/tests/test_cleanup_paths.py:105` 拒缓存中的伪工具路径；`test_api_task_deletion_paths.py:38`、`:66` 拒未知名称/目标并接受合法链接。`output/cleanup-unification-20261022/linux-mount-final.py:20` 在隔离 mount namespace 构造真正可读 `/opt/codex`，两个入口删除后目标 SHA256 相同（见下方原始输出）。 |
| 2. 文件类型、硬链接、IPC | 完整实现。`backend/app/execution/cleanup_paths.py:112` 仅接受普通文件/socket/FIFO 且 nlink=1；`:77` 以 O_PATH 检查、不读取 IPC 内容。`backend/tests/test_cleanup_paths.py:30` 真实硬链接两种范围均拒绝且两个文件保留；`test_api_task_deletion_paths.py:77` 真实 socket/FIFO 清理成功。 |
| 2. 跨设备及同设备挂载；证据不可用失败关闭 | 完整实现。`backend/app/execution/cleanup_paths.py:47` 从内核 FD 取 mnt_id；`:69`、`:82` 同时阻止目录及叶节点挂载跳转，`:51`、`:56` 对缺失/非法证据拒绝。配置根之前不强制同设备，根内所有候选强制检查。`backend/tests/test_cleanup_mounts.py:16` 缺失/畸形证据，`:85` 8 类真实同设备 bind，`:94` 同 inode 替换，`:134` 预检后 nested bind 均在本轮 Linux 专项实跑；真实 tmpfs 也拒绝且 sentinel 保留。 |
| 2. 实际递归删除重复挂载检查，不依赖只读预检 | 完整实现，关闭第二轮 HIGH。`backend/app/execution/cleanup_paths.py:88` 同一 walker 支撑预检和删除；`:100` 每层打开后再次检查身份/挂载，`:106` 只沿已检查 FD 递归，`:108`、`:109` 删除目录前重验并 dir_fd rmdir。`:127`、`:196`、`:199` 复核顶层和残留。POSIX 不再调用 shutil.rmtree。`linux-nested-race-green.py:23` 在预检后真实挂入外部目录，两种范围均 CROSS_DEVICE 且 sentinel_intact=true；不是模拟设备号。 |
| 2. Windows 保守路径 | 完整实现。`backend/app/execution/cleanup_paths.py:205`、`:223` 拒绝 symlink/junction，`:228` 拒非普通叶节点与硬链接，`:263`、`:268` 重验身份。`backend/tests/test_cleanup_paths.py:193` 的 root/task/cache 三个真实 junction 用例在本轮 Windows 专项实跑；没有把 Windows 跳过的 Linux 能力当作已验证。 |
| 3. 24h 只 cache/plugins，72h 整 UUID | 完整实现。`backend/app/retention/state.py:7`、`:8`、`:63`、`:65` 保持阈值；`backend/app/execution/cleanup_paths.py:174`、`:181` 限定缓存两目录，`:187` 历史才选择整个会话，`:188` 先预检全部缓存。`backend/tests/test_cleanup_paths.py:42`、`test_retention_paths.py:80`、`test_api_retention.py:44` 验证范围、23h 不到期、24h 清缓存且原会话可恢复；`test_cleanup_retention_safety.py:49`、`:53` 验证缓存→历史。 |
| 3. 原图、素材、正式成品、采用版本、归档/用量、外部资料保护 | 完整保持。`backend/app/retention/api.py:64` preserve 汇总，`:77`、`:80` 仅清会话历史；`backend/app/retention/objects.py:27`、`:29`、`:35`、`:57` 保留业务/采用版本/冻结 JSON/共享 key 引用。`backend/tests/test_cleanup_retention_safety.py:31`、`:47`、`:52`、`:55` 在合法工具链接场景逐阶段比较所有对象原字节与元数据；`test_api_retention.py:64`、`:188` 验证采用/跨任务引用；`test_retention_concurrency.py:140` 验证采用竞争；`test_api_usage_facts.py:87` 为用量保留回归。邻居目录、共享 auth、外部程序/bind sentinel 有独立文件系统断言，未将“返回失败”等同于“没有误删”。 |
| 4. 活动/未确认保护、锁及持久屏障 | 完整保持。`backend/app/retention/api.py:20` 父锁，`:39` 保护未知/活动状态及进程身份，`:104`、`:106` 持久 pending；`backend/app/retention/state.py:21`、`:41` 拦截清理期间提交；`backend/app/modules/api_image_edits/deletion.py:114` 显式删除 fence。`backend/tests/test_retention_concurrency.py:87`、`:103`、`:122`、`:188`、`:222`、`:241` 在真实 PostgreSQL 独立事务中验证竞争、未知状态和屏障。 |
| 4. 每小时重试、25 条、两阶段、失败恢复/幂等计数 | 完整保持。`backend/app/retention/worker.py:80`、`:83` 保持上限与到期筛选；`backend/app/retention/api.py:136`、`objects.py:109` 保持一小时；`api.py:128` 成功后才 finish。`backend/tests/test_cleanup_retry_pg.py:35`、`:42`、`:44`、`:47` 从真实扫描的失败 pending 到 59min 不动、1h 恢复、重复不重计；`:50`、`:53` 保证 last_activity 和累计。`test_cleanup_retention_safety.py:98` 在目录已删、DB 已修改后注入故障，验证回滚和下一次成功只计一次。 |
| 5. 稳定分类、脱敏位置、不泄漏原始异常 | 完整实现。`backend/app/execution/cleanup_diagnostics.py:26` 区分安全、权限、IO、锁、完整性、存储、未知；`:45` 仅应用内相对模块和行号，`:57` UUID/stage/异常名白名单，`:69` 不输出异常正文、SQL、locals、链。接线在 `retention/api.py:131`、`objects.py:107`、`worker.py:71`、`:95`、`:136` 及 `modules/api_image_edits/deletion.py:135`。`backend/tests/test_cleanup_diagnostics.py:16`、`:43`、`:50` 和业务层 `test_cleanup_retention_safety.py:86`、`:117` 验证分类及脱敏。 |
| 5. --once 和真实 main 生命周期异常 | 完整实现，关闭两轮日志 HIGH。`backend/app/retention/worker.py:114` 将配置、factory、首次 heartbeat、上下文关闭纳入边界；`:123` 与 `:138` 用 SystemExit(1) from None 结束，不再重新打印原始异常。`backend/tests/test_cleanup_diagnostics.py:66` 两种 --once 调用和 `:90` 四种真实 main 子进程均断言 exit=1、稳定错误码以及 stdout/stderr 无 SQL/token/DSN/Traceback。reviewer 独立运行 19 项全部通过。 |
| 5. 页面/API 原通用文案，无迁移 | 完整保持。`backend/app/retention/api.py:135` 与 `backend/app/modules/api_image_edits/deletion.py:139` 原安全文案保持；差异无模型/迁移/响应字段改动。 |
| 执行授权边界、发布依赖、UI/引导和 Spec 漂移 | 匹配。`Product-Spec.md:1`、`DEV-PLAN.md:1`、修复合同 `:3`、`:31` 明确只开发验证及未来原生执行器发布依赖；没有执行旧 records 发布脚本。无新页面、文案引导、API、表或未授权功能。原 UI 与已审快照相同，本轮不产生新的视觉比较对象，不声称重新完成浏览器 UI 验收。 |

部分实现/未实现：本范围代码检查、专项及本候选全量验证中未发现产品功能缺口。无待修复 HIGH/MEDIUM 项；Windows 测试临时目录收尾限制单独记录。

## Stage 2 · 质量与测试真实性

| 检查项 | 证据和结论 |
| --- | --- |
| 单一职责、重复、文件大小 | `backend/app/execution/cleanup_paths.py:1` 为唯一目录安全核心，288 行；diagnostics 71 行；两个 wrapper 6/9 行；业务文件最大151行，新增/修改测试最大217行。14 文件全部低于300行。预检/实际删除共用 `cleanup_paths.py:88`，避免两个安全遍历实现漂移；业务删除职责仍分开。 |
| 命名、类型、资源管理、失败语义 | `cleanup_paths.py:11` 使用受限错误类，`:71` 任何异常时关闭刚打开的 FD，`:154` ExitStack 管理祖先/候选，`:110` 子 FD finally 关闭；不使用 any 或隐式成功吞错。`:199`、`:272` 检查删除残留。`test_cleanup_paths.py:78`、`:93` 验证权限异常/无效删除不能假成功。Python 函数风格与所在模块先例一致。 |
| 安全扫描 | 对14文件扫描 eval/exec、innerHTML、前端密钥前缀、密钥标记、password 赋值、shell=True、logger.exception/exc_info 和用户绝对路径；无新增可执行注入或秘密值。命中只有合同要求的 `cleanup_paths.py:30` `/opt/codex`、`:50` 内核 `/proc/self/fdinfo`，及相应测试/无 exc_info 断言。数据库使用 SQLAlchemy 参数化表达式（`retention/objects.py:54`、`worker.py:83`）；新增日志不拼 SQL/异常字符串（`cleanup_diagnostics.py:64`）。 |
| 测试前提真实 | `test_cleanup_mounts.py:64` 明确断言同 st_dev，`:56` 使用真实 mount --bind；`:84` 通过 unshare 私有挂载空间；`:113`、`:155` 在 inspect 后插入真实挂载。不是只打桩证明自己。真实 `/opt/codex` 由隔离 namespace 的 tmpfs 提供，保留哈希；真实 UID 测试在 `test_api_task_deletion_paths.py:102` 区分 API UID 与 native UID。 |
| 故障/交互层覆盖 | `test_cleanup_diagnostics.py:66`、`:90` 调用子进程，覆盖入口与上下文生命周期；`test_cleanup_retention_safety.py:98` 真正先修改DB再失败而非只抛纯函数异常；`test_cleanup_retry_pg.py:35` 经过真实 scheduler/PG 行锁、持久化和计数，既有并发测试验证提交/采用/执行竞争。未用纯函数绿灯替代业务入口验证。 |
| 视觉对比 | 不适用于本次增量：14 文件全部后端/测试，`retention/api.py:135` 与 `deletion.py:139` 既有通用文案不变；review-status 未显示继承前端漂移。本报告不虚构打开新页面或邻居页面的验证。 |

## 本候选验证原始输出

已直接读取原始日志；不使用前两轮 151/165 项或旧全量2436项结果批准本候选。

```text
# output/cleanup-unification-20261022/linux-target.log
171 passed, 3 skipped, 2 warnings in 40.24s
# output/cleanup-unification-20261022/windows-target.log
63 passed, 40 skipped, 2 warnings in 17.48s
# output/cleanup-unification-20261022/linux-full.log
2456 passed, 27 skipped, 10 warnings in 377.76s (0:06:17)
# linux-status.log 最后一次 full
full exit_code=0
# reviewer 独立执行（cwd: hengxin-smart-image/backend）
.venv/Scripts/python.exe -m pytest -q tests/test_cleanup_diagnostics.py
...................                                                      [100%]
19 passed in 7.91s
exit_code: 0
# reviewer 独立编译
.venv/Scripts/python.exe -m compileall -q app
exit_code: 0
output: （空）
# reviewer 独立格式差异检查
git diff --check
exit_code: 0
output: 仅 CRLF 将转换为 LF 的提示，无 whitespace error。
```

```json
// linux-nested-race-green.log，两种 scope 皆如此
{"scope":"history","exception":"CleanupSafetyError","code":"CROSS_DEVICE","bind_injected_after_inspection":true,"sentinel_intact":true}
{"scope":"cache","exception":"CleanupSafetyError","code":"CROSS_DEVICE","bind_injected_after_inspection":true,"sentinel_intact":true}
// linux-mount-final.log
{"retention_real_tool_target_sha256_preserved":"7ed8117616c0ef2ee6bb629aeaa9d17a85eff24375d223f81e0bfe3ceb951c4b",
 "deletion_real_tool_target_sha256_preserved":"7ed8117616c0ef2ee6bb629aeaa9d17a85eff24375d223f81e0bfe3ceb951c4b",
 "target_real_mount_refused_and_preserved":true,"cache_real_mount_refused_and_preserved":true,"nested_real_mount_refused_and_preserved":true}
```

`linux-bind-green.log:1` 的 target/cache/nested 三场景还分别显示 same_device=true、CROSS_DEVICE、sentinel_intact=true。`linux-mount-final.log` 同时记录 host_opt_codex_remains_absent=true；临时测试未创建宿主的真实 `/opt/codex`。

reviewer 独立解析本轮 JUnit：linux-target 为174测试/0 errors/0 failures/3 skipped；linux-full 为2483测试/0 errors/0 failures/27 skipped；windows-target 为103测试/0 errors/0 failures/40 skipped，与上述日志数量一致。没有读取旧候选全量 XML 冒充本轮结果。

未变化前端的继承验证原始输出（本次已重新读取，不充当后端修复证据）：

```text
# frontend-tests.log
ℹ tests 355
ℹ pass 355
ℹ fail 0
ℹ skipped 0
# frontend-typecheck.log
> vue-tsc --noEmit
# frontend-build.log
✓ built in 40.60s
```

前端 typecheck/build 退出0依据主 Agent执行记录，日志未报编译错误。依赖配置/弃用提示及大资源提示为继承结果，没有写成零 warning。

## 快照、环境与结论边界

- 审查开始、中途及全量结束后 review-status currentId 均为本候选，changedFiles 均恰好为上述14文件；未发现代码漂移。reviewer 独立比较 `linux-full-source-before.json`、本轮最终 `linux-full-source-after.json`、`reviewer-source-current.json`，564个后端源码/测试/迁移/配置文件两两一致，before_after_changed=[]、reviewer_after_changed=[]。
- Linux 专项3 skip是本轮 Windows junction，Windows已实跑；Windows40 skip为 Linux mount/FD/工具链接/IPC/UID等条件，Linux专项补齐。全量27 skip具体为22项缺独立Redis、1项指定non-root WSL环境、3项本轮Windows junction（本轮Windows已补测），另1项既有 `test_studio_context_safety.py:142` 海外Windows junction（本轮Windows专项未包含，不能宣称已补测）。warnings为既有库弃用和隔离root运行Celery提示，不写成零warning。
- Linux Python3.12.13、锁依赖、PostgreSQL18.6 UTC、独立网络namespace和临时 Unix socket，listen_addresses为空（`linux-environment.log:1`、`linux-runner.sh:32`）。不是生产 PostgreSQL16.15安装包测试；未碰生产两条retry数据。`linux-schema-cleanup.log` 为空，未残留测试新增schema/数据库；`linux-cleanup.log:1` 原始收尾结果如下，证明临时PG已停且独立runtime移除。

```text
cleanup_started exit_code=0
waiting for server to shut down.... done
server stopped
temporary_postmaster_stopped=true
temporary_runtime_removed=true
```

- Windows 测试临时目录收尾受工具策略限制：`output/cleanup-unification-20261022/windows-temp-cleanup.log:1` 记录对 `C:/Users/82358/AppData/Local/Temp/pytest-of-82358/pytest-2377`、`pytest-2378`、`pytest-2379` 的删除命令被自动审批以 `Rejected: blocked by policy` 拒绝，未提供更具体原因，命令未执行、未换手段绕过，三个临时目录保留。这是环境收尾未完成项，不是产品清理功能测试失败；不能宣称所有临时目录已清完。
- 范围外的旧 Asia/Shanghai 极端 Retry-After datetime.max 溢出保持单独记录，本轮按生产已核实 UTC 配置回归；本报告不宣称修复该问题。
- 官方核查依据：[Python dir_fd/no-follow](https://docs.python.org/3.12/library/os.html#files-and-directories) 支持相对于已打开目录操作；[Linux fdinfo/mnt_id](https://www.kernel.org/doc/html/v6.8/filesystems/proc.html) 用挂载身份补充设备号。安全结论还依赖本候选真实挂载和竞态测试，不仅依据文档。
- 本候选的产品功能/安全与代码质量两阶段通过，验证数据、环境限制及残留已明确列出。主 Agent 应用本报告路径登记同一候选，再执行 review-status 确认批准匹配；保持不提交、不部署，不宣称线上失败记录已恢复。
