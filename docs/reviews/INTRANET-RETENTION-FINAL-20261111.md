# 内网源码保留两版最终独立审查

日期：2026-11-11。使用 `.agents/skills/code-review/SKILL.md`，按 Stage 1 → Stage 2 顺序执行。

- 最终 candidateId：`1973e99b4ccf98ecaba8debb65e5bc11186af554d78298209ea4956e6df58ae7`。
- **Stage 1：PASS。Stage 2：PASS。没有待修复的 HIGH / MEDIUM 问题。**
- 范围：`scripts/release/intranet/` 下 `release.py`、`cleanup.py`、`cleanup_history.py`、`cleanup_pending.py`、`cleanup_refs.py`、`test_release.py`、`test_cleanup.py`、`test_cleanup_refs.py`。追溯既有 `snapshot.py`、`operations.py`、`stage.py`、`scripts/release/release-retention-state.py`、`hengxin-smart-image/scripts/migration245/unify_release.py`。
- 源合同：`docs/INTRANET-RELEASE-TOOLS.md:52`“自动保留两版”全部条目；`Product-Spec.md:1482`；`DEV-PLAN.md:1694`。不将全产品历史功能纳入本次变更审查。
- 本报告批准的是代码实现及隔离验证，不代表已经完成线上激活、删除或净释放验收。对应交付仍由主 Agent 完成，见下文。
- Reviewer 未操作线上、未调用模型、未修改实现、未提交或登记 review-approve；仅执行本地只读审查、隔离探针、测试及编译，写本报告。

## 快照变化及复核范围

初收候选 `0c26372cbf176c167ee4eaa6234e4923b8d2a392f6415b471b11d992d8fa86ba`，审查过程中主 Agent 修改了 `cleanup_refs.py`、`test_cleanup_refs.py`。中间候选为 `c6b7560fc20ecfe705a399ebc89d934c18d80ec6fc17b42f1d68a7b07b61bb5f`，最终重新固定为上述 `1973e99b…`。本报告不把旧快照结论直接覆盖新代码；重新读取两文件全文、从 Stage 1 复核全部合同项后才进入 Stage 2，其余六文件沿用本轮独立读取的未变化证据。

`review-status` 对最终快照返回 `currentId=1973e99b4ccf98ecaba8debb65e5bc11186af554d78298209ea4956e6df58ae7`、`approved=false`；八个受控变化文件与上列范围相同。主 Agent 应使用本报告及同一 candidateId 登记两阶段 PASS，不写 `.needs-review` clean。

## Stage 1：逐项合同符合性

下表文件名省略公共前缀 `scripts/release/intranet/`；其它目录均写全路径。每行结论限于代码与所列验证，线上操作另列。

| 合同条目 | 结论 | 代码与验证证据 |
|---|---|---|
| 发布成功、完整验证、保存新台账之后自动清理 | 完整实现 | `release.py:112`–`:123` 完成切换验证并持久化；`:132` 才清理。`test_release.py:104` 的 cleanup 替身实际读取磁盘台账，断言 current 已切换、pending 已清除。 |
| 失败/未完成发布不清理 | 完整实现 | `release.py:124` 恢复后抛错；`cleanup.py:87` 拒绝 pending。`test_release.py:123` 失败路径禁止 cleanup；`test_cleanup.py:86` 覆盖 prepared/deploying/recovered。 |
| 清理失败仅告警，不回退成功业务 | 完整实现 | `release.py:130` 清理在恢复块之外，`:139` 捕获自动清理异常并记录告警。`test_release.py:216` full/frontend 两模式均断言 restore 不被调用、磁盘 current 不回退。 |
| cleanup 默认预览，--apply 才执行删除 | 完整实现 | `release.py:191`、`:207`，`cleanup.py:91` 提前返回预览。`test_release.py:233` 从真实 CLI 入口断言 apply 为 False/True。 |
| 与发布共用锁 | 完整实现 | `release.py:202` 包含 cleanup；`test_release.py:239` 在 execute 内二次获取同一锁失败。底层锁见 `scripts/release/release-retention-state.py:90`。 |
| 清理前重验当前完整基线及运行环境 | 完整实现 | `cleanup.py:89` 调用 runtime=True 并比较 current；`snapshot.py:85` 检查实际源码、前端、native/二进制/依赖、schema、数据与配置，`:113` 运行真实身份 runtime_check。`test_cleanup.py:94` 漂移/无法检查均拒绝。 |
| init/verify/recover/rollback/cancel 不自动清理 | 完整实现 | `release.py:43`、`:150`、`:165`、`:175`、`:213` 均无 cleanup；自动调用仅 `:132`。 |
| 保留 current/previous 前后端目录并集 | 完整实现 | `cleanup_refs.py:65`–`:78`；`test_cleanup_refs.py:15` 四路径断言，`test_cleanup.py:64` 分离前后端且保留未发布候选。 |
| 保留原生解释器及二进制引用 | 完整实现 | `cleanup_refs.py:75` 读取 native/binaries，`:78` 解析解释器真实路径；`test_cleanup_refs.py:15` 使用真实 symlink，`test_cleanup.py:178` 保护上一版解释器所在旧目录。 |
| 全部容器，包括停止容器及父目录挂载 | 完整实现 | `cleanup_refs.py:146` docker ps -aq + inspect，`:150` 使用 parent_mount；`test_cleanup_refs.py:68` 返回停止容器并断言 inspect，`:93` 验证父挂载保护全部子版本。 |
| 宿主进程 cwd/exe/root/命令/环境/fd/maps | 完整实现 | `cleanup_refs.py:81`–`:115` 读取各项；相对 argv、--option=、相对库路径按 cwd 解析。`test_cleanup_refs.py:29` 各来源集合断言，`:45` 活进程元数据缺失拒绝，`:53` 真实 fake-/proc symlink 与相对参数回归。 |
| 挂载点及父目录 bind 引用 | 完整实现 | `cleanup_refs.py:118`–`:140` 解析完整 mountinfo、识别承载文件系统、映射同设备 bind source；根本身挂载拒绝，普通承载根挂载不视为业务引用。`test_cleanup_refs.py:148` 分别断言普通根无保护、根/祖先 bind 保护 old。 |
| systemd 配置含未加载 vendor、drop-in、非 service 单元与别名 | 完整实现 | `cleanup_refs.py:9` 查询实际 UnitPath 并递归扫描全部普通文件；`:28` 解析 unit symlink，`:48` 解析配置中绝对路径的别名；`:153` 补查已加载服务。`test_cleanup_refs.py:103`、`:116`、`:126`、`:136` 分别覆盖 vendor/drop-in、六类后缀、失效链接及 symlink WorkingDirectory。 |
| 无法核查则停止删除 | 完整实现 | `cleanup.py:58` 初次扫描失败直接退出，`:114` 删除前扫描失败进入 errors 并停止后续删除；`cleanup_refs.py:12`、`:114`、`:126` 拒绝不完整检查，权限/读取异常向上传播。明确不存在的可选 UnitPath/失效 unit 不读取虚构配置，但其链接目标仍进入保护。`test_cleanup.py:94`、`test_cleanup_refs.py:45`、`:126`。 |
| venv/依赖/链接/不安全权限/非清单内容/挂载保留 | 完整实现 | `cleanup.py:28`–`:50` 与 `cleanup_pending.py:12`–`:34`；复用 `hengxin-smart-image/scripts/migration245/unify_release.py:69` 的 root 所有权、写权限、symlink/hardlink 检查及 `:167` 完整清单校验。`test_cleanup.py:115`、`:135` 覆盖依赖、未知文件、链接、权限及挂载。 |
| 仅删除受控根完整历史运行目录，不删 stage 候选 | 完整实现 | `cleanup.py:30` 限直接子目录，`:73` history 门槛；`cleanup_history.py:12` 读取 source_history、current/previous 或 applied 事务，`:35` 限备份文件名，`:42` 校验旧 compose 摘要。`test_cleanup.py:64`、`:183` 覆盖未发布候选保留及摘要漂移拒绝。 |
| 删除前再次检查引用和目录身份，防止越界 | 完整实现 | `cleanup.py:104` O_NOFOLLOW 打开 root fd；`:109`–`:123` 重查 root/候选 dev+ino、引用和清单；`:127` 相对 root_fd 删除。`test_cleanup.py:151` 注入计划后新引用并确认不删。 |
| 部分删除后可安全重复执行 | 完整实现 | `cleanup.py:125` 删除前落盘私有证明，`cleanup_pending.py:53` 限同 root 身份、剩余目录/文件为原集合子集且 hash 不变。`test_cleanup.py:198` 真实删除 manifest/index 后抛错，第二次完成删除；`:215` 新增文件、篡改文件、身份变化均拒绝。 |
| 不复制待删目录；不删事务备份、旧 native 根、venv、镜像、数据、上传包 | 完整实现 | 唯一源码删除为 `cleanup.py:127`，范围由 `:30`/`:73` 限定；`cleanup_pending.py:66` 只删除私有证明文件；`cleanup_history.py:12` 只读事务。没有其它删除命令、源码备份或旧公网入口。 |
| 已有页面兼容静态资源继续保留 | 完整实现 | `release.py:65` 仍调用 keep_assets；`cleanup.py:41` 对旧 compatibility-files.json 验证前缀与 manifest hash。`test_release.py:188`、`test_cleanup.py:126`。 |
| 计划/回执私有保存，包含保留原因与删除路径 | 完整实现 | `cleanup.py:82`、`:90`、`:100`、`:130` 记录计划和结果；预览保持只读。状态存储复用 `scripts/release/release-retention-state.py:87` 的 0700 目录及 `:119` 的私有临时文件/原子写入。 |
| 同范围前后占用、回执增量、净释放，不以路径消失替代 | 完整实现 | `cleanup.py:15` 统计 allocated blocks、不跟随链接；`:96`、`:138` 同 root 前后统计，`:143`–`:147` 纳入状态目录净增量。`test_cleanup.py:75` 实际比较 root+state 前后总量与 net_released_bytes。线上工具安装额外占用仍需主 Agent 合并计量。 |
| 不改成功台账、不再次切换业务 | 完整实现 | `cleanup.py:85` 只读 data，写独立清理报告；`test_cleanup.py:166` 比较 intranet.json 字节。手动入口 `release.py:204` 不调用 apply/recover。 |
| 指定隔离回归覆盖 | 完整实现 | 上列文件覆盖分离状态、依赖引用、失败发布、清理失败、链接/挂载/未知目录、重复执行及部分失败。最终 Linux 日志 122 passed、7 subtests passed；Windows 独立运行结果详见下文。 |
| 独立审查后更新工具、预览、清理存量，并确认服务/版本/数据不变 | 交付阶段待执行 | `DEV-PLAN.md:1694` 将其列为审查后的步骤，不能伪装已经验收。当前只读日志 `output/intranet-retention/preview-final.log:1` 两侧 RUNTIME_OK、deleted=[]；唯一候选 36,528,128 bytes。主 Agent 需在批准后执行并提供 PID/容器/数据身份及实际净释放证据。 |

部分实现项、未实现代码项：无。Spec 漂移：本轮八文件仅增加约定的内网源码保留、引用保护、恢复证明与对应测试；未新增业务页面、API、表或功能。无 UI/设计稿变化，UI 一致性、引导真实性、邻居页面视觉对比不适用（`release.py:188` 为 CLI 入口，八文件均 Python 工具/测试）。

## 旧 FAIL 与本轮发现的回归

- 原报告 `docs/reviews/INTRANET-RETENTION-REVIEW-20261111.md` 的 vendor 未加载配置遗漏：最终 `cleanup_refs.py:11` 从真实 UnitPath 扫全部配置，`test_cleanup_refs.py:103` 回归通过。
- 原报告部分删除不能重试：最终私有证明及子集恢复见 `cleanup_pending.py:53`，真实先删文件的测试见 `test_cleanup.py:198`。不再依赖已经删除的 manifest。
- 初收候选仍只读 `.service/.conf`；reviewer 用真实 `unit_configs()` 读取隔离的有效 `.mount` 文件，旧输出 `protected=False`。主 Agent 修复后对最终代码重复探针，原始输出：`non_service_mount_reference_protected=True`。`.mount` 是有效 systemd 配置类型，参见 [systemd.mount 官方文档](https://www.freedesktop.org/software/systemd/man/latest/systemd.mount.html)。
- 中间候选父目录 bind mount 被漏扫：隔离 collect 探针以 `/opt` → `/srv/opt` 的 mountinfo 返回空保护集。最终改为 `cleanup_refs.py:118` 的文件系统映射，Linux `test_cleanup_refs.py:148` 回归覆盖父目录与根 bind，不把普通根挂载错误当作引用。
- 未加载服务的路径别名与相对进程参数：最终分别由 `cleanup_refs.py:48`、`:90` 修复；Linux `test_cleanup_refs.py:136`、`:53` 使用真实符号链接验证。Reviewer 本机 Windows 不具备 symlink 创建权限，未冒称自己执行了这些 Linux 用例。

## Stage 2：代码质量、安全与测试真实性

| 维度 | 结论与证据 |
|---|---|
| 命名、结构、职责及文件大小 | PASS。清理编排/引用/历史识别/删除证明分为四模块，分别见 `cleanup.py:1`、`cleanup_refs.py:1`、`cleanup_history.py:1`、`cleanup_pending.py:1`。八文件行数依次为 release 231、cleanup 148、refs 160、history 57、pending 66、test_release 248、test_cleanup 229、test_cleanup_refs 159，全部不超过 300；不存在 TypeScript any 适用项。沿用项目 Python 动态映射风格，边界清单/路径/字段检查见上述 Stage 1。 |
| 错误处理 | PASS。检查不完整阻止删除，单次删除异常停止后续候选；自动清理告警不触发业务回退，见 `cleanup.py:133`、`release.py:139`。不吞掉权限错误继续删除；失效 unit 链接是明确区分的无目标情形。 |
| 危险调用与凭据扫描 | PASS。对新增 cleanup*.py 及 release.py 搜索 eval/exec、shell=True、innerHTML、API key/token 前缀、硬编码 password，无命中。命令由 `cleanup_refs.py:146`、`:153` 列表参数进入既有 `unify_release.py:60` subprocess.run，不调用 shell；环境/配置只进入保护原因，`cleanup_refs.py:160` 不返回原始敏感文本。匹配到的 /var/lib 和 /proc 路径分别为 `release.py:200`、`cleanup_refs.py:152` 的规定边界，不是开发机泄漏。 |
| 删除安全及恢复证明 | PASS。只有 `cleanup.py:127` 递归删源码，要求平台支持抗 symlink 攻击、root fd 与双重目录身份检查、完整清单、历史证据及两次引用扫描。恢复证明只保存 hash/目录名，无源码副本；`cleanup_pending.py:53` 不因 manifest 消失放宽到任意残目录。 |
| 测试真实性 | PASS。`test_cleanup.py:75` 使用真实隔离文件系统块数和真实 rmtree；`:198` 确实先 unlink 两文件再注入故障，随后恢复真实删除函数；`:215` 修改文件或身份并断言拒绝。`test_release.py:104` 检查持久化顺序，`:216` 检查 full/frontend 两条失败隔离；`:233` 测真实 CLI 参数及锁。不是仅以模拟成功返回值自证。 |
| 测试边界 | 明确。`test_cleanup.py:29` 的 safe 替身保留链接/写权限判断，但未在该 fixture 重测 root UID/hardlink；这些规则本轮通过既有 `unify_release.py:69` 实现审查，未宣称完整端到端权限攻防实测。外部 Docker/systemd/proc 通过边界替身测试；真实线上仅使用主 Agent 提供的只读 preview/运行检查证据，不制造生产失败。 |
| 视觉对比 | 不适用。范围无页面、样式或组件变更；不以未打开页面宣称视觉通过。 |

## 验证原始输出

Reviewer 独立运行最终快照，命令：

```text
.\hengxin-smart-image\backend\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider scripts/release/intranet hengxin-smart-image/scripts/migration245/test_unify_release.py -q
ssssssssssssssssssssssssssssssssssssssss........................
..........................................................                [100%]
82 passed, 40 skipped, 7 subtests passed in 13.59s
```

40 个跳过项为两个 cleanup 测试模块的 Linux 权限、符号链接、/proc 与 fd 删除语义，见 `test_cleanup.py:21`、`test_cleanup_refs.py:12`。本机通过不能替代 Linux 删除验证。

读取主 Agent 在不可变安装候选 `/opt/hengxin-intranet-tools/releases/cabc13ae497d7df7` 执行后保存的 `output/intranet-retention/linux-tests-final.log:1`，原始输出：

```text
..........................................................................................................................                [100%]
122 passed, 7 subtests passed in 2.69s
```

这是主 Agent 提供的真实 Linux 测试日志，reviewer 已检查相应测试前提和断言；reviewer 未连接服务器重复执行，不将其描述为自己的线上实测。

Reviewer 对 `scripts/release/intranet/*.py` 逐文件执行 `compile(path.read_bytes(), str(path), 'exec')`，不生成 pycache，原始输出：

```text
COMPILE_OK 16 Python files
```

代码与隔离验证两阶段通过。主 Agent 登记本候选审批后，再完成最终工具激活、授权存量清理、同范围实际净释放及服务/数据身份不变验收；不能把 preview 的 36,528,128 bytes 宣称为已释放空间。
