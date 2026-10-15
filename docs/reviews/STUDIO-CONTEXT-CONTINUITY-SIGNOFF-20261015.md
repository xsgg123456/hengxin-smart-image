# Studio 文件连续性：最终候选独立审查

- 日期：2026-10-15。
- candidateId：`7b8d6f6ac459c8408f92e118e5f92cf0b2ae3083d625755c0c2ed7521a912df2`。
- **Stage 1：PASS。Stage 2：PASS。HIGH 0，MEDIUM 0，LOW 0。**
- 结论仅覆盖本报告所列源码快照；不等于生产部署、业务旧文件恢复或整个发布阶段已经完成。
- 审查开始、相关测试完成后及报告交付前均以 `python .codex/hooks/harness.py review-status` 核对 candidate；没有发现审查期间受控代码变化。Markdown 报告不属于受控代码快照。
- reviewer 只读实现，执行本地临时目录测试和编译，仅新增本报告；未修改实现、commit、spawn、登记批准、写 `.needs-review`、连接生产或调用付费模型。由主 Agent 按 `docs/HARNESS-REVIEW.md:10` 登记同一 candidate 的两阶段 PASS。

## 审查合同与范围

读取 `.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、`Product-Spec.md:1157` 新增完整条目、DEV-PLAN 同日“工作台多轮文件连续性与旧会话恢复”、CHANGELOG、`docs/STUDIO-CONTEXT-CONTINUITY-PLAN-20261015.md` 和 VALIDATION 文档。前三轮及第四轮失败报告仅作为复核线索，未沿用它们的旧候选结论。

以下 `B/` 表示 `hengxin-smart-image/backend/`。本次审查包含 git diff 与未跟踪实现，共 30 个受控文件：

- `B/app/execution/{workspace,persistent_mounts}.py`、`B/app/overseas/execution/materials.py`。
- `B/app/overseas/studio/{execution,delivery,context_fs,context_assets,context_migration,context_workspace,work_baseline,restore_context}.py`。
- `B/tests/studio_context_probe.py`、`test_overseas_studio_execution.py`、`test_studio_context_{assets,edited_versions,migration,notice,probe,safety,work_conflicts}.py`、`test_studio_{persistent_mounts,restore_context,work_baseline}.py`。
- `scripts/release/{overseas-context-deploy,overseas-context-recovery,package-overseas}.py` 及 `test_overseas_context.py`、`test_overseas_context_recovery.py`、`test_package_overseas.py`。
- `hengxin-smart-image/frontend/package.json:3`：仅版本由 0.2.35 改为 0.2.36。

只读追踪既有 Studio service/queries/schemas、runner/claims、归档/任务清理和继承的发布脚本，以核对调用前提、隔离及回归边界。

## Stage 1：Spec Compliance — PASS

本节按本轮 Spec 全部增补条款及方案中的输入、迁移、交付、恢复、发布约束拆项；没有将其他历史阶段未实现事项当成本次缺陷。

| 合同/验收项 | 结论及代码证据 | 验证证据 |
| --- | --- | --- |
| 同 conversation 持久 work；原件、研究/脚本/笔记持续可读 | 完整实现。`B/app/overseas/studio/context_workspace.py:78` 按会话 prepare，`:130` 始终指向 persistent/work；`execution.py:39` 仍以 conversation 定位 HOME。 | `B/tests/test_studio_context_assets.py:33` 三轮同目录/同原件/笔记、下载一次；`test_overseas_studio_execution.py:66` 实际 runner 路径验证续接和中间文件。当前独立相关测试通过。 |
| 纯文字后续轮、重新进入及 worker 重建不依赖进程内缓存；新对话和任务隔离 | 完整实现。`context_workspace.py:40` 从磁盘清单载入；`execution.py:22` 校验 turn/job/task/conversation；`:34` 只收当前会话已 dispatched 历史。`service.py:73` 创建独立 conversation。 | `test_studio_context_assets.py:96` 新会话空原件/无旧笔记；真实 Linux probe 三轮重新构造 Workspace，结果逐轮 isolated=true，证据见下节。 |
| 仅已明确提供的图需、上传、图片引用进入会话；新增/同名/内容版本不覆盖 | 完整实现。`B/app/overseas/studio/service.py:51` 明确选择附件/图片，`:60` 冻结统一原件字段；`queries.py:30`、`:44` 归属校验；`context_assets.py:30` 资源身份及 checksum 路径，`:40` 注册 history/current 输入。 | `test_studio_context_assets.py:56` 同名两资源及同资源新版本三份字节均保留；公开索引不含 bucket/object_key。`studio_context_probe.py:37` 覆盖七种文件后追加同名第八份。 |
| 原件只读、完整性检查及缺失恢复；工作文件可编辑 | 完整实现。`context_assets.py:67` 校验每个已登记原件，`:89` 优先校验旧本地原件，否则读取冻结存储源并校验大小/hash；`B/app/execution/persistent_mounts.py:38` inputs/index/input 只读挂载，work 仍可写。 | `test_studio_context_assets.py:70` 删除/篡改后恢复；`:86` 错误字节阻止首次布局提交；真实沙箱 original 写入被拒、派生笔记跨轮可写可读。 |
| 每轮日志、input、Skill 独立；未选不带旧 Skill；用户原消息不改 | 完整实现。`B/app/overseas/execution/materials.py:13` control 与 round_work 独立写入，`:22`/`:37` 冻结完整 Skill 包；`workspace.py:93`、`:100`、`:108` 挂载本轮并隐藏旧发现目录。`studio/execution.py:84` 原样拼接用户正文，Skill 仍来自本轮 payload。 | `test_studio_persistent_mounts.py:24` 选中/未选均检查挂载；`test_studio_context_safety.py:47` 防受控路径重定向；真实 probe 首轮 Skill 有、后两轮无。未新增选择记忆 UI。 |
| 原件复用而非每轮重新复制；磁盘不足明确阻止 | 完整实现。`context_assets.py:75` 仅不匹配原件加入 pending；`context_fs.py:160` 保留空间并明确错误；`context_migration.py:229` 复制前检查空间。 | `test_studio_context_assets.py:33` read 调用次数=1；`test_studio_context_safety.py` 真实文件与磁盘错误注入用例包含在当前独立测试中。 |
| 旧目录仅按 DB 归属恢复；普通隐藏文件与历史不丢；平台私有目录不导入 | 完整实现。`context_migration.py:39` 仅枚举 history 轮次；`:21`/`:24` 排除受控目录并保留普通隐藏文件；`restore_context.py:37`–`:45` 二次核对历史任务、job kind 与 payload 会话/轮次。 | `test_studio_context_migration.py:26` 真实旧形态原件/研究文件；`:171` 普通隐藏文件保留且私有目录不导入；`test_studio_restore_context.py:41` 保留旧源、回复和执行次数。 |
| 同名与文件/目录冲突全部来源可追溯，无歧义旧路径不静默择一 | 完整实现。`context_migration.py:75` 检出内容及前缀冲突；`:139` 盘点现有未登记工作文件；`:188` 合并来源；`:231` 先 journal、复制全部来源后才移除歧义入口。 | `test_studio_context_migration.py:60`、`:79`；`test_studio_context_work_conflicts.py:31`、`:46`、`:74` 验证源字节集合、未登记/已编辑工作内容、前缀冲突和不相关文件不变。旧 H1 已闭环。 |
| 已公开恢复版本可正常编辑；增量迁移保留编辑内容及可用旧源，不虚报不可用版本 | 完整实现。`context_migration.py:101` reconcile 识别当前编辑版本；`:120` recovery_target 保留有效当前映射，对已占用恢复路径另选目标；`:206` 保留无竞争的普通编辑路径。 | `test_studio_context_edited_versions.py:47`、`:59`、`:69`、`:86`、`:122`、`:143` 覆盖正常编辑、再次编辑、增量、复制/metadata 中断、重试前再编辑和保留副本。旧 H2 已闭环。 |
| 首次原子启用、失败保留旧源、重试安全，回退新增轮次重新盘点 | 完整实现。`context_workspace.py:93` 独立 staging，`:112`/`:114` 完成索引/manifest 后 `:120` rename；已有布局 `context_migration.py:190` 载 journal 并 reconcile；非 managed 历史每次扫描。 | `test_studio_context_migration.py:91`、`:125`、`:183`；`test_studio_context_work_conflicts.py:103`、`:144` 覆盖回退新增、复制中断、索引/manifest 写失败及重试。 |
| 必要恢复索引提示直到真实 dispatched 历史出现才消耗，包括此次 journal 中断变体 | 完整实现。`context_workspace.py:89` 以历史集合判断旧提示是否已送达；`:101` **在 apply 前**检查未提交 journal，`:103` 即使 migrated=0 仍视为恢复；`:106` 持久化新的通知历史；`:114` 提交后才 `:117` 删 journal；`:133` 提供本轮通知。`execution.py:87` 加实际索引路径。 | `test_studio_context_notice.py:11` 准备/取消不消耗；`:34` 分别故障注入 context-index.json/manifest.json，先消耗旧通知，再产生回退冲突，断言重试通知、全部字节、歧义入口移除、journal 清理、未派发再次提醒及真正派发后停止提醒；`:77` 在线冲突路径验证。两参数均在当前独立集通过。旧 M1/M1-R 已闭环。 |
| 旧 sessionId 与历史业务数据不改，缺失 session 明确失败 | 完整实现。`execution.py:32`、`:44` 拒绝缺失身份/会话文件，`:57` resume 精确 ID；`restore_context.py:21` 恢复只写会话文件布局，不写业务轮次/结果。 | `test_overseas_studio_execution.py:151` uncertain 不重复启动，`:163` session 缺失不创建替代；`test_studio_restore_context.py:41` 两次 apply 后 session、reply、execution_count 均不变。 |
| 只收最终回复明确正式交付的本轮新增/修改图；未变旧图、原件/Skill、草稿拒收 | 完整实现。`execution.py:75` 启动前 snapshot；`delivery.py:147` 按最终引用收图，`:165` 对实际已验证字节 hash 比较；`work_baseline.py:142` 缺失/非法 baseline fail closed，`:153` 未变旧图拒绝。既有 `_local_file` 仍检查受控路径、session/历史 native 输出。 | `test_studio_work_baseline.py:55`、`:68`、`:80`、`:109`、`:119`、`:134`、`:141`、`:147` 证明新增/修改、仅元数据变化、跨会话、native 历史、坏 baseline 与混合有效/无效引用。 |
| 修改产物生成独立版本；归档不受工作文件覆盖；删除清理整个会话 | 完整实现。`execution.py:115` 独立 picture UUID/object；既有 `B/app/overseas/archives/snapshot.py:56` 写独立 archives key 并回读校验；`tasks/cleanup_files.py:63` 按 DB conversation 枚举整个 studio 根，`:131` 删除该范围，包含新 persistent 子目录。 | `test_studio_work_baseline.py:90` 修改工作图不改变已收取字节；已存 Linux 全回归覆盖 `test_overseas_task_deletion.py:68` 的删除/归档。未改变归档和清理实现。 |
| 500 MB 与每轮两组 100 个限制、既有国内/海外旧执行保持 | 完整实现。`context_assets.py:17` 原件上限 500,000,000；既有 `studio/schemas.py:12`/`:13` 仍各限 100；`workspace.py:93`/`:108` 只在 persistent 分支生效，`materials.py:16` 对旧调用回落原 work。 | 当前独立 runner 集通过；读取既有 Linux 全量 2446 passed/189 skipped、相关 373 passed/1 skipped 证据，见下文版本边界。未修改原格式解析和上传 UI。 |
| 恢复 CLI 显式目标、只读盘点、digest 重查、在途/未知进程阻断 | 完整实现。`restore_context.py:23` UUID、`:29` task 锁、`:33` 忙/未知进程拒绝、`:53` inspect、`:63` 应用前 digest 重查。 | `test_studio_restore_context.py:41` dry-run 不创建 persistent、错误 digest 拒绝及重复安全；`:63` 源变化拒绝；`:72` 未确认进程拒绝。 |
| 发布固定 0.2.35/adf861b→0.2.36、备份排空、安装验证和恢复三次真实读取后开放 | 发布实现完整，生产执行待主 Agent 完成。`overseas-context-deploy.py:18`/`:23` 固定基线，`:47` 检查实际 API/native/代理，`:70`/`:83` 固定目标清单，`:107` 在备份排空后调用恢复。`overseas-context-recovery.py:36` 重核服务停止/无待办，`:54` 安装沙箱探测，`:64`/`:66` 盘点+受限恢复，`:69`–`:85` 验全部源覆盖和三次读取才标记。 | 当前发布相关独立集 99 passed/24 subtests，特别 `test_overseas_context.py:41` 顺序、`:51` 恢复失败不切换/不开放、`:79` 禁止 Python -O；`test_overseas_context_recovery.py:43`/`:58` 故障不标成功。 |
| 不自动付费生成、不做 Skill 跨页面选择记忆，无额外产品漂移 | 完整实现。`B/tests/studio_context_probe.py:19` 使用 sandbox_command 的实际边界但执行 `/usr/bin/python3`，添加 unshare-net；恢复工具仅 invoke 维护 CLI/probe。前端只改 package 版本，无页面/API/表增补。 | 审阅全部修改及未跟踪实现；未发现本轮 Spec 未授权的产品功能。真实模型调用未执行且不声明已验证。 |

部分实现/未实现：在本次**源码审查范围**内无。实际安装产物全量测试、生产切换和指定业务恢复属于尚待执行的发布步骤，详见限制，不算已验收。

UI 一致性/引导真实性：没有新增页面、组件、布局、颜色或交互变更，故设计数值及“新页与邻居页”渲染对比不适用，本 reviewer 没有打开浏览器。新增恢复提示所指 `.context-files.json` 确由 `context_workspace.py:112` 写入、`persistent_mounts.py:40` 只读挂载；没有死引导。

## Stage 2：Code Quality — PASS

| 检查 | 结论与证据 |
| --- | --- |
| 职责、命名、类型、文件规模 | 原件/文件系统/迁移/工作区/输出基线/运维恢复分模块，未混入页面或业务结算。29 个修改/新增 Python 文件逐一计数均≤300行：最大 `scripts/release/test_overseas_context.py` 295行，运行模块最大 `context_migration.py` 263行。`context_assets.py:13` 对输入基本类型、hash、大小显式校验；`context_workspace.py:40` 对私有清单字段、UUID、路径校验。无新增 TS any。 |
| 错误处理、提交顺序与重入 | `context_fs.py:115` 原子临时文件/fsync/replace，`:166` OS 锁与身份复核；`context_workspace.py:122` 初次失败只清理已核对的 staging。增量先写 journal 再保存来源，索引/manifest 完成后删 journal，不以拷贝次数代替恢复状态（`:101`）。当前故障注入用例运行通过。 |
| 测试真实性 | notice 新例先建立并消耗一次真实形态通知，再新增旧布局轮次，错误发生在 metadata 提交而非人为直接改标志；随后同时断言通知、路径与源字节。冲突/编辑测试用临时真实文件，非仅 mock 返回值。`test_overseas_studio_execution.py:18` mock CLI 只证明 runner 接线，未当成真实模型效果；`studio_context_probe.py:19` 的实际 namespace 检验与之分开。发布测试明确为 mock 故障矩阵，未当成已执行部署。 |
| **安全扫描** | 未发现新增硬编码密钥、eval、shell=True、危险反序列化、浏览器 innerHTML 或动态 SQL 拼用户输入。批量扫描唯一匹配是 `scripts/release/test_package_overseas.py:79` 隐私审计的合成路径反例。恢复 subprocess 为参数数组（`overseas-context-recovery.py:19`/`:26`）；UUID与digest固定目标（`:44`）；公开索引省略对象存储字段（`context_assets.py:112`）。未形成需外部资料裁定的可疑安全结论，无新增依赖/API版本变更。 |
| 文件/挂载隔离 | `context_fs.py:23` 检查全部父路径、软/硬链接、junction、特殊文件；`:65` POSIX dir_fd+O_NOFOLLOW 及读前后身份检查；`persistent_mounts.py:26` 检查来源及目标类型；`work_baseline.py:32`/`:75` 对目录和读取竞态 fail closed。相关 Windows 条件跳过明确列出，Linux 留存证据补 POSIX 分支。 |
| 版本与发布质量 | `package-overseas.py:146` 要求所有新增 runtime/recovery/probe 文件；`:175` 要求已审、已提交内容，打包前后比较快照和 HEAD；`:163` 验 tar 成员与实际字节。`overseas-context-deploy.py:128` 禁止优化模式绕过断言。当前独立发布测试通过。 |
| 差异与视觉 | `git diff --check` 退出0，只有 Git 的 CRLF→LF 提示，没有差异格式错误。无 UI 源码变化，视觉对比不适用；没有将此写成“页面视觉已实测通过”。 |

未发现待修复 HIGH/MEDIUM/LOW；未新增安全问题或范围漂移。

## 本 reviewer 独立执行的验证

在 `B/` 执行：

```text
./.venv/Scripts/python.exe -m pytest -q tests/test_studio_context_assets.py tests/test_studio_context_migration.py tests/test_studio_context_work_conflicts.py tests/test_studio_context_edited_versions.py tests/test_studio_context_notice.py tests/test_studio_context_safety.py tests/test_studio_context_probe.py tests/test_studio_persistent_mounts.py tests/test_studio_restore_context.py tests/test_studio_work_baseline.py tests/test_overseas_studio_execution.py
```

原始结果摘要（exit_code=0）：

```text
............................s....................ssssss.....s........... [ 59%]
s.......................ss...ss...................                       [100%]
109 passed, 13 skipped, 2 warnings in 27.99s
```

13 个 skip 来自当前 Windows 的 symlink 权限、POSIX FIFO/文件名/链接边界等平台条件，不记为通过。警告为现有 FastAPI/Starlette 对 httpx 与 anyio BlockingPortal 的弃用提示。

仓库根目录执行：

```text
./hengxin-smart-image/backend/.venv/Scripts/python.exe -m pytest -q scripts/release/test_overseas_context.py scripts/release/test_overseas_context_recovery.py scripts/release/test_package_overseas.py
................................................ [ 48%]
...................................................                      [100%]
99 passed, 24 subtests passed in 3.54s
```

编译命令及工具原始退出/输出（在 B/）：

```text
./.venv/Scripts/python.exe -m compileall -q app tests ../../scripts/release
{"exit_code":0,"output":""}
```

## 已读取的其他验证证据与限制

- `output/context-notice-final-linux.log`：当前最后提醒修复相关 Linux 集，`83 passed, 1 skipped, 2 warnings in 24.50s`。该 Linux 执行由主 Agent 提供，本 reviewer 读取原始日志，未声称自己重跑。
- `output/context-release-candidate-linux-tests.log`：**最后通知修复之前**的 Linux 全量，`2446 passed, 189 skipped, 15 warnings in 266.54s (0:04:26)`。`output/context-final-targeted-linux-tests.log` 相关集 `373 passed, 1 skipped`。不能把前候选全量当作最终安装产物测试；最后改动已由本轮相关测试覆盖，安装后仍需按计划跑全量。
- `output/context-release-final-tests.log`：发布与旧发布回归 `157 passed, 72 subtests passed in 5.16s`；当前 reviewer 独立补跑范围为上文99项，无需重复此前整套耗时集。
- `output/context-frontend-tests.log`：`pass 364`、`fail 0`；`output/context-frontend-build.log`：`✓ built in 32.11s`。本次未改页面源码，不重跑前端，也不据这些日志宣称真实生产页面已验收。
- `output/context-isolated-sandbox.json:1` 原始退出码0、stderr空：threeRounds 原件数7/7/8，三轮 derived/readonly/isolated 全true；旧布局4个源文件、2个冻结输入全部覆盖，三次独立读到4文件且 allHashesMatch=true。审阅 `studio_context_probe.py:19` 实际 Bubblewrap 调用、`:110` 源计划覆盖核对及 `:140` 恢复后只读挂载流程，证明该证据是实际文件隔离读取，不是模拟生成成功。测试文件与业务文件分离，没有模型付费调用。
- `docs/STUDIO-CONTEXT-CONTINUITY-VALIDATION-20261015.md` 已明确部署/业务恢复未发生。目标任务现存两原件/187研究文件的盘点与业务快照由主 Agent 维护；本 reviewer 不连接生产核验，也不以该数量判定字体、Logo或产品照片素材充足。

本报告允许主 Agent 为上述同一 candidate 登记代码两阶段 PASS。后续如修改受控代码，应重新固定候选并复核；正式交付仍须完成已授权的安装产物测试、备份排空、明确会话恢复、源覆盖及三次真实沙箱读取、生产版本/健康验证。
