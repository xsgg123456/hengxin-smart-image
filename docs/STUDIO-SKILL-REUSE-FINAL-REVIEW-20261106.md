# 同会话 Skill 复用与原生发布工具 · 独立复审

结论：**Stage 1 PASS；Stage 2 PASS。** 本次未发现需要阻断源码交付的问题。允许主 Agent 对下述同一快照登记审查批准，随后进入固定提交打包及实际安装验证；此结论不代表已部署、Linux 安装套件已通过或全部历史会话已完成真实模型续聊。

## 快照与范围

- candidateId：`fe2bb8c483ca7ef2298789c9fdcfbf38ba6cd09c1db2f0d2602bd43fa52ec826`。
- 开始及结束前 `review-status.currentId` 均与交接一致，`approved=false`。未观察到受控代码变化；本报告为普通 Markdown，不改变受控快照。由主 Agent 登记批准，本 reviewer 不写 clean、不提交、不修复、不进行生产操作。
- 审查范围：AGENTS.md 一条授权实查规则；materials.py 持久分支；skill_cache.py、skill_content.py；三份 cache 测试、persistent_mounts 测试契约调整；九个 skill-reuse 发布 helper 和两份发布测试。既有挂载、context_fs、安装目录读取、sku-native 等按本次实际调用链审查，不宣称重审历史产品全部功能。
- 已读原文：AGENTS.md、code-review/SKILL.md、HARNESS-REVIEW.md、STUDIO-SKILL-REUSE-20261106.md、STUDIO-SKILL-REUSE-RELEASE-PLAN-20261106.md、STUDIO-SKILL-REUSE-VALIDATION-20261106.md、原失败报告 STUDIO-SKILL-REUSE-REVIEW-20261106.md 全文；Product-Spec.md、DEV-PLAN.md 顶部新增条款。
- 下表 `backend/` 均为 `hengxin-smart-image/backend/`；`release/` 均为 `scripts/release/`。行号绑定本候选。

## Stage 1：旧发现复核

| 原问题 | 复审结论及证据 |
|---|---|
| HIGH：umask 077 下 candidate/vendor 根不可遍历 | 已修复。`release/skill-reuse-test.py:43`、`:67` 对两个根显式 chmod 0755。`release/test_skill_reuse_recovery.py:125` 在真实 Linux root、umask 077 条件下运行实际 candidate/vendor 构建路径，再用 subprocess 的真实 nobody UID/GID 导入两个模块，未 mock chmod 或权限判断。本 reviewer 独立 WSL 执行，15/15 发布测试通过。该测试替换 Docker 和 invoke，不冒充生产解释器、真实 pytest 或 bwrap 安装测试。 |
| MEDIUM：首次 idle 失败留下 owner，recover 缺 GATE_STARTED 而失败 | 已修复。`release/skill-reuse-deploy.py:148` 拒绝全部切换证据，执行原 native preflight、源码/环境、原 PID、active/no-job、原代理哈希核验；`:171` 仅无 GATE_STARTED 时进入该分支，`:227` 成功后释放 owner。`release/test_skill_reuse_recovery.py:55` 走实际 main → gate → idle 失败 → recover，并断言不停止/启动服务、不改代理、不调用 worker；`:78`、`:94`、`:112` 覆盖切换证据、原状态漂移、已开始 gate 拒绝取消路径。独立 Windows/WSL 均通过。 |

## Stage 1：合同逐条核对

这里的“匹配”是源码与本轮隔离证据的结论。生产部署属于后续执行阶段，不能把当前未执行的生产步骤记成已验收。

| 条款 | 结论、实现与验证证据 |
|---|---|
| 仅海外 Studio 持久会话启用 | 匹配。`backend/app/overseas/execution/materials.py:22` 在 persistent 分支接入并提前 return；非持久两来源沿用旧路径。`backend/tests/test_studio_skill_cache.py:149` 证明非持久仍每轮复制。 |
| 完整内容身份，包含名称、相对路径、字节与执行权限规则 | 匹配。`backend/app/overseas/execution/skill_content.py:12` 生成 SHA256/size/mode，`:19` 覆盖两来源；`skill_cache.py:60` 对 name 与完整 entries 规范序列化哈希。原发布批次、对象键不成为内容身份。 |
| A/A、A/B/A、同内容重发、内容变更保留旧版 | 匹配。`skill_cache.py:66` 命中仅校验；`:72` 新内容另建。`backend/tests/test_studio_skill_cache.py:69`、`:89` 逐项断言相同路径、inode/mtime/完整字节、独立内容版本及六类内容变化。 |
| 同会话私有、不跨会话共享 | 匹配。`skill_cache.py:15` 校验 UUID 会话、round、control 和 persistent/work 关系；`:63` 建会话根独立库。`backend/tests/test_studio_skill_cache.py:120` 与 safety `:150` 验证隔离与外来 control 拒绝。 |
| 只把当前版本只读挂到既有路径，库不暴露；取消选择隐藏旧技能 | 源码匹配。`backend/app/execution/workspace.py:103` 仅当前 skill ro-bind，`:108` 对 skills remount-ro；`persistent_mounts.py:41` 空 tmpfs 隐藏原 work/skills。`backend/tests/test_studio_skill_cache.py:168` 检查两条挂载和取消选择；`test_studio_skill_cache_linux.py:15` 包含真实读写拒绝、旧版本不可见和历史保留测试。Windows 未执行真实 bwrap，必须由正式包安装流程补验。 |
| 已安装技能、数据库冻结文本/资源两来源 | 匹配。`skill_content.py:20` 调 frozen_package；`:24` 校验冻结文本及资源；`backend/app/overseas/management/installed_catalog.py:135` 校验冻结名称/checksum/发布树。cache 测试 source fixture `:37` 对两来源参数化；真实 catalog 探针 `release/skill-reuse-catalog-probe.py:25` 读取实际目录并走真实 frozen_package，尚未生产执行。 |
| 命中完整清单/大小/校验及权限校验；资源不重复下载；异常不换版 | 匹配。`skill_cache.py:27` 拒绝多余目录、漏项、大小/哈希/权限不符；`:69` 命中不调用 read。`skill_content.py:40` 仅新写入才读取二进制资源并关闭连接。cache `:69` 核对下载次数；safety `:13` 强制命中不下载且不修补损坏副本。 |
| 首写暂存/校验/原子发布、同会话互斥、失败可重试 | 匹配。`skill_cache.py:62` 使用既有 context_fs.lock；`:72` 私有随机暂存，`:81` 校验、sync 后 rename 并同步 cache。safety `:74` 双线程竞争只产一版；`:95` 写失败回收自身暂存并重试；`:122` 损坏下载关闭资源且可重试。 |
| 拒绝链接、特殊文件、越界、额外文件及损坏，不覆盖旧版 | 匹配。`skill_cache.py:28`、`:36` 使用 context_fs.checked；`backend/app/overseas/studio/context_fs.py:24` 拒绝链接/多硬链接/特殊文件，`:63` 安全 reader 以文件身份及 no-follow 校验；`skill_content.py:13` 校验相对路径。safety `:13`、`:37`、`:66`、`:141` 覆盖损坏、链接、越界和执行权限。POSIX 条件用例仍需正式 Linux 安装验证。 |
| 不删除/重写/摘要历史、附件、图片、工作文件和旧轮次副本 | 匹配。新增业务代码唯一递归删除在 `skill_cache.py:88`，只针对自身 `.stage-` 暂存，受父目录与安全路径检查；不遍历历史回收。cache `:130` 保存完整历史等字节并经过 B/无选择/A 后逐一比较；`:69` 同内容保持 inode/mtime。没有迁移/批量清理或声称立即回收 916MB 的实现。 |
| 沿用会话执行互斥、删除保护、旧会话下轮采用新库 | 匹配。业务接线未改原执行/删除控制器；cache owner 采用真实现有 UUID 目录结构。`backend/tests/test_studio_skill_cache_safety.py:159` 实际调用现有 cleanup_files.erase，确认仅目标会话缓存删除、其它会话不变、对象存储未删。`test_studio_persistent_mounts.py:13` 改为真实结构，`:36` 更新断言为私有 cache，未放宽业务路径校验。 |
| 不改 UI/DB/model/凭据/Skill 正文；上游同步 | 匹配。`Product-Spec.md:1`、`DEV-PLAN.md:1` 指向合同。受控变化只在上述范围，没有页面、接口、表结构、模型、凭据或技能正文变化。`AGENTS.md:36` 仅追加用户授权的连接前查最近部署记录。UI/引导真实性及视觉对照不适用，无新页面可与邻居比较。 |
| 固定提交、审查凭据、包白名单及隐私 | 匹配。`release/skill-reuse-package.py:19` 要求干净提交，`:25` 正式包要求 reviewed_status，`:31` Git 固定提交提取/本地一致/隐私检查，`:55` 结束重验身份；`skill-reuse-runtime.py:45` 验证严格非测试白名单、文件哈希、链接与额外内容；candidate 模式仅允许 prepare/test，deploy `:28` 拒绝其进入 release 动作。 |
| baseline/prepare 先只读实查，不改 API、前端、DB 或实际 Skill | 匹配。`release/skill-reuse-baseline.py:16` 读取实际 API/原生源码/schema；deploy `:50` 固定实际环境与代理原文；`:21` 持续校验 API ID/image/StartedAt、配置、schema、前端、Skill、无关服务与源码。发布文件集合由 runtime `:17` 限定三个模块。 |
| 隔离真实 native 安装测试，不改生产 venv/读取生产凭据 | 源码匹配、实际执行待补。`release/skill-reuse-test.py:60` 复制纯 app 并叠加三模块，`:40` 仅从原 API 镜像导出六个 pytest 模块；`:23` 断言模块根/pytest 根/UID，`:28` unshare 网络与 env -i，`:35` 拒绝 failed/skipped/xfail；`:84` 对最终安装根重复测试。此次只独立证明 umask 权限修复，未声称实际 Linux 套件通过。 |
| 双代理503、旧 worker 排空、持久任务排空、温和停机 | 匹配。`release/skill-reuse-gate.py:68` 保存旧 nginx worker、统一期限、双代理 503 验证后等待旧 worker 退出；deploy `:96` 两次稳定 idle、pause 已识别 consumer 再停止；既有 `release/sku-native.py:108` 安装 no-SIGKILL/无限 systemd stop timeout，调用方有等待期限，超时保留保护。真实关门尚未执行。 |
| host 锁、跨 CLI owner、源码原子安装与 absent 回滚 | 匹配。deploy `:212` host 锁与 `:218` 持久 owner；native `:16` 完整备份校验、`:51` fsync/同文件系统原子替换、`:74` stopped/closed 后安装且不覆盖原备份；`:96` 恢复分阶段校验，`:129` 新模块移到 app 外归档，原模块恢复原字节。独立 WSL 临时目录真实文件 restore 验证原文件、absent 状态和候选归档；系统服务 I/O 为替身。 |
| pending stop 拒绝开放，失败恢复不回灌数据库/会话 | 匹配。deploy `:178` 检查 ActiveState/Job；native `:105`、runtime `:78` 对恢复 PID、原/新来源及无关源码约束。恢复仅源码和 consumer；native `:115` 停止后另取 recovery-preserve，保留重新开放后合法产生的数据。`test_skill_reuse_release.py:146` 验证 pending stop 不可重新开放。 |
| 保留所有会话元数据及表摘要，恢复开放前验证 | 匹配。preserve `:21` lstat 全执行根元数据而不读私密文件字节，`:35` Studio/会话表摘要；deploy `:118` 停稳后 capture，native `:91` 启动前核对，deploy `:128` 健康/原路径测试/保留核对，`:139` 开放后不再套用旧静态会话快照。独立测试证明 metadata 不读文件内容且检测变化。实际生产对比待执行。 |
| 真实 catalog 探针与不重放用户任务 | 匹配。`release/skill-reuse-catalog-probe.py:11` 接受显式代码根、真实技能根和新 scratch；`:38` 无凭据工作区，`:57` A/A 校验路径、字节、inode/mtime及历史 sentinel；无模型调用。计划将其放在候选测试后和正式安装后执行，目前无真实目录通过证据。 |

完整实现：上述本轮源码与运维工具条款均有实现。部分实现、未实现、Spec 漂移：未发现。生产执行与 Linux 环境验证是已声明的后续步骤，不能省略或由本报告替代。

## Stage 2：质量、安全与测试真实性

- **代码结构通过。** 内容描述/缓存发布、基线/打包/测试/关门/保留/安装恢复各有独立模块；本次 18 个 Python 文件均低于 300 行，最大 deploy.py 为 233 行。`skill_content.py:19`、`skill_cache.py:55`、`release/skill-reuse-native.py:74` 的错误路径显式抛出，不静默选择其它内容；未引入 TypeScript any。Python 动态工作区/运维 adapter 延续既有约定。
- **安全扫描通过。** 对本轮业务模块及九个 helper 搜索 eval/exec、shell=True、密钥前缀、密码赋值、前端敏感变量及删除 SQL；无新增硬编码密钥、eval、shell=True 或 DELETE/DROP/TRUNCATE。`release/skill-reuse-preserve.py:42` 对动态表名严格白名单；`:44` 引号包围名称。CLI 子进程参数采用列表，`skill-reuse-test.py:23` 嵌入路径使用 repr，未拼 shell。
- **删除边界通过。** `skill_cache.py:93` 仅删自身失败暂存；`release/skill-reuse-deploy.py:228` 仅删成功结束的发布 owner；`skill-reuse-native.py:133` 把新增源码移至归档，保留其字节。没有针对历史会话、工作目录、附件、数据库、卷或生产镜像的删除代码。vendor `skill-reuse-test.py:54` 删除的是刚创建的无挂载临时容器；非运行 API。
- **恢复与数据保护通过。** `skill-reuse-native.py:16` 对备份清单范围/哈希逐条校验，`:85` 只接受原/候选版本，runtime `:94` 保持恢复 PID 与无关源码限制。独立临时目录测试走实际 backup/restore、guard、原子写与 rename，未把只有 Mock 的恢复调用当成真实文件恢复证据。
- **测试真实性通过。** cache 测试实际调用 materials.prepare 与真实工作区，安装来源 fixture 的伪造范围明确；对缓存哈希、路径、下载次数、inode/mtime、字节、故障重试、互斥、历史、删除兼容都有可观察断言（cache `:69`、`:130`；safety `:74`、`:95`、`:159`）。修改 persistent_mounts fixture 是对齐真实 UUID 合同。发布恢复新测试执行真实 main/gate/recover 分支；Linux权限测试使用真实 UID，替换范围未隐藏。没有用 Windows skip 宣称 POSIX 安全或真实挂载通过。
- **视觉对比不适用。** 受控快照无 UI 文件；`materials.py:22` 为后台准备路径改动。没有新增页面，未打开浏览器，不宣称视觉验收。
- **未发现 HIGH/MEDIUM 阻断项。** 正式机器的解释器、依赖、bwrap、服务关门/启动/恢复、真实 catalog 与会话元数据比较仍需按发布计划实际执行。当前隔离替身测试不能证明这些生产行为已完成。

## 独立验证原始输出

Windows 发布测试命令：`python -m unittest discover -s scripts/release -p 'test_skill_reuse*.py' -v`，退出 0：

```text
Ran 15 tests in 0.320s

OK (skipped=1)
UNGATED_RELEASE_CANCELLED_NO_SERVICE_CHANGED
```

WSL Ubuntu root 同一发布测试命令，退出 0；包含真实 nobody UID 权限用例：

```text
Ran 15 tests in 0.433s

OK
UNGATED_RELEASE_CANCELLED_NO_SERVICE_CHANGED
```

后端在实际 `.venv/Scripts/python.exe` 执行五文件定向 pytest，退出 0：

```text
s..............ss....ss............ [ 97%]
.s                                                                       [100%]
63 passed, 11 skipped in 12.27s
```

首次误用系统 Python 得到以下原始输出，随后改用项目已有 venv 完成上述验证，没有安装依赖或改代码：

```text
C:\Users\82358\AppData\Local\Programs\Python\Python312\python.exe: No module named pytest
```

对上述 18 个 Python 文件直接 `compile(path.read_bytes(), str(path), 'exec')`，退出 0，原始末行：

```text
COMPILE_PASS files=18
```

WSL 临时目录执行实际备份、恢复、运行状态 guard 及原/新文件操作；系统服务和会话采集为替身，无生产连接，退出 0：

```text
RESTORE_REAL_FILES_PASS original_restored=True absent_restored=True candidate_retained=True
```

交接证据核对：已读取 `output/skill-reuse-backend-full.log` 和 `output/skill-reuse-head-failures.log` 尾部原文，分别为 `10 failed, 2725 passed, 430 skipped` 与旧 HEAD 对照 `9 failed, 43 passed`；新增 private-cache 契约相关的第十项在此次 63 项回归中通过。前端 typecheck、527 测试、build 与全 app compileall 为主 Agent 提供证据，本 reviewer 未重复全量执行；不将其写成本人独立验证。

## 交接边界

本报告仅批准所列候选的两阶段源码审查。主 Agent 应再次核对 currentId，使用 review-approve 关联本报告，再按计划中文提交、正式包实际安装测试、真实 catalog 探针、关门排空、保留/健康验证与 resume。任一代码变化需重新固定快照；任一真实安装验证失败需停止切换并处理，不得以本报告覆盖运行失败。
