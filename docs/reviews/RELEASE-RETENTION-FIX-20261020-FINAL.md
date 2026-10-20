# 部署回收遗漏修复独立复审（2026-10-20）

- candidateId：`6ff55ec8ef949bbfad5cf9215c990bdab88e4ca8ddb4f3209dac1e93f8cdc9b0`
- Stage 1：**PASS**。Stage 2：**PASS**。未发现本候选范围内需阻断交付的 HIGH / MEDIUM 问题。
- 审查范围：相对 HEAD 的发布回收实现、测试、需求及运维文档全部差异，包括三个新增文件 `release-retention-failures.py`、`test_release_retention_failures.py`、`test_release_retention_dangling.py`；对既有锁、成功回执、打包接线及原生发布入口做必要关联审查。
- 依据：AGENTS.md、code-review/SKILL.md、docs/HARNESS-REVIEW.md、Product-Spec.md:1 的 2026-10-20 条目及其依赖的 2026-10-14 回收规则、DEV-PLAN.md:5、docs/RELEASE-RETENTION.md、docs/RELEASE-RETENTION-FIX-20261020.md。
- 本次从 Stage 1 重新完整审查，通过后执行 Stage 2，未沿用上一快照的通过结论。只操作本地临时测试台账，未连接生产、执行真实镜像清理、重启服务或修改会话数据。

## Stage 1：Spec Compliance

### 前次问题复核

前报告 candidate `63f77b7535460a50253801eb53fb3c854b7d2363f670904817aa57c8a378d1d3` 的 M1 已修复。`scripts/release/release-retention-failures.py:8` 现在同时要求三个业务之一的完整连字符前缀和非空后缀。裸 `domestic` / `overseas` / `identity`、空后缀以及未知业务均不能进入自动退休范围。

证据：`scripts/release/test_release_retention_failures.py:136` 的 7 个参数用例覆盖 `scope`、`seed_legacy`、已有基线的 `preview` 和 `retire`，检查台账字节不变、没有 Docker 写操作；此次独立全量测试全部通过。正常业务前缀的构建/准备失败仍通过 `:41` 的完整 managed 生命周期推进和退休测试。

### 完整实现逐项对照

| 需求条目 | 结论、代码位置与验证证据 |
| --- | --- |
| Spec:3，本项目无标签镜像发现 | 完整实现。`scripts/release/release-retention-docker.py:55` 合并仓库标签查询与项目 label + dangling 查询，去重后 inspect；`:94` 再核对标签、摘要及项目标记。`test_release_retention_dangling.py:18` 覆盖无标签、本项目/其它项目、无标记、外部标签及摘要别名；`:72` 覆盖查询与 inspect 之间元数据变化。 |
| Spec:3，所有容器、三业务 current/previous、在途及恢复引用 | 完整实现。`release-retention-docker.py:33` 使用 `docker ps -aq`，`:72` 检查三组完整历史、健康、运行快照及保留镜像存在，`:88` 保护 pending ID、当前同名标签和 before。`test_release_retention_dangling.py:35`、`:49` 验证停止容器、三业务不同镜像和 before 引用；`test_release_retention_docker.py:97`、`:153` 验证漂移、缺失及不健康时拒绝。 |
| Spec:3，删除前重查、不强删、不涉及其它项目 | 完整实现。`release-retention-docker.py:111` 重算计划，`:114` 按标签或完整无标签 ID 删除，无 image rm force 参数。`test_release_retention_dangling.py:85`、`:98`、`:128` 验证命令、竞态与删除拒绝；`test_release_retention_docker.py:84` 验证外部别名保护。 |
| Spec:4，同业务后续真实成功且无引用才退休，不按时间猜测 | 完整实现。`release-retention-state.py:67` 仅在验证后且实际切换镜像时递增对应业务计数；`release-retention.py:96`、`:108`、`:110` 保证原入口成功后才落回执并 finalize；`release-retention-failures.py:47` 要求计数严格大于失败基线，并检查候选 ID/标签引用。`test_release_retention_failures.py:41`、`:61`、`:71`、`:240` 分别覆盖同业务成功、其它业务无效、旧成功无效及失败重试重置基线。 |
| Spec:4，未知范围、部署/恢复现场和成功回执保留 | 完整实现。`release-retention-failures.py:7` 限定业务前缀、failed 阶段且无 before；`:57` 检查回执存在。`test_release_retention_failures.py:98` 覆盖 before、receipt、停止容器、current、previous、其它 pending、未知范围、built、prepared；`:136` 补足裸名称/空后缀边界。 |
| Spec:4，保存退休审计且原子解除保护 | 完整实现。`release-retention-failures.py:76` 在深拷贝中同时移除 pending、保存原记录/原因/替代成功计数，`:83` 写成功后才更新内存。`release-retention-state.py:119` 使用临时文件、fsync、replace 和 POSIX 目录 fsync。`test_release_retention_failures.py:49` 验证审计内容，`:155` 验证写失败保留台账和内存 pending、停止后续清理。 |
| Spec:5，旧台账先在锁内种基线，再等待新成功 | 完整实现。`release-retention-state.py:37` 兼容可选计数；`release-retention.py:64` 先取得共用锁再调用 seed；手动 cleanup 同在 `:126` 的锁内。`release-retention-failures.py:23`、`:68` 种基线；`test_release_retention_failures.py:82` 以已有计数 5 验证不得立即退休，下一成功到 6 才退休。 |
| Spec:5，人工 abandon、原恢复流程继续可用 | 完整实现。`release-retention.py:79` 要求 before 恢复快照，`:147` abandon 仍检查回执、健康和历史一致；`test_release_retention.py:95`、`:190` 覆盖恢复/拒绝缺失快照，`test_release_retention_cli.py:48` 验证 abandon 仅解除保护。 |
| Spec:6，同名重建保护旧候选、已完成发布禁止重建/准备 | 完整实现。`release-retention.py:70` 限制 completed 操作，`:92` 在调用构建前持久保存当前候选；`release-retention-docker.py:88` 同时保护保存 ID 与变化后的同名标签。`test_release_retention_failures.py:197` 验证构建失败后的旧/新两 ID 均保护，`:212` 验证已完成发布 build/prepare 被拒绝且台账不变。 |
| Spec:6，真正 pending 阻止缓存回收，仅专属 builder 约 2 GB | 完整实现。`release-retention-docker.py:118` 仅 pending 空时调用 prune；`:123` 明确 builder 和 `2gb`。`release-build.py:7`、`:19` 校验名称及 docker-container driver，不操作默认 builder。`test_release_retention_failures.py:54` 验证退休后 prune，`:61` 验证仍有失败 pending 不 prune；`test_release_retention_docker.py:128`、`:191` 验证未完成与错误 driver 保护。 |
| Spec:6，清理失败只告警，不改变部署成功或停服务 | 完整实现。`release-retention.py:21` 捕获回收异常，`:114` 位于成功记账之后，既有入口失败处理外。`test_release_retention.py:128` 验证成功返回值和 completed 保留；`test_release_retention_failures.py:155`、`test_release_retention_dangling.py:128` 验证失败后停止回收。 |
| Spec:7，数据库/图片/卷/会话/认证/任务/CLI/历史配置链保护 | 本地代码完整实现边界。新增生产操作仅为台账审计与原有受限 Docker 清理；`release-retention-failures.py:68` 无业务文件操作，`release-retention-docker.py:105` 无容器、卷、system prune 或服务重启命令。`test_release_retention_cli.py:67` 验证 preview 不改台账、cleanup 不改 groups，且无 systemctl/rm/docker stop/volume/system 调用。 |
| Spec:8，生命周期/边界/竞态/故障/编译/接线验收 | 本地验收通过。具体独立测试和编译输出见下文；打包证明位于 `test_release_wiring.py:13`，全部包的 allowlist/glob 包含新 helper；CLI 验证 `:41` 检查 managed 位于入口异常处理外。 |

### 尚待执行的交付步骤

Product-Spec.md:7、:8 和 DEV-PLAN.md:9、:10 要求的 Git 提交、服务器工具安装、哈希/preview、当前和回滚镜像、服务及会话前后保护检查，是此次独立代码审查之后的交付步骤。此次报告只批准本地候选实现，不声称生产更新或整项交付已完成。`docs/RELEASE-RETENTION-FIX-20261020.md:25` 明确记录服务器更新计划。

### UI、一致性与 Spec 漂移

本候选没有 UI、页面、用户引导、组件或设计稿变更，因此 UI 一致性和邻居页面视觉对比不适用；没有以截图替代发布工具行为验证。差异仅涉及上述 4 个运行 helper、5 个测试文件及需求/运维说明，没有新增业务 API、数据库表或页面，未发现范围漂移。

## Stage 2：Code Quality

| 检查项 | 结论与证据 |
| --- | --- |
| 职责、命名、体积 | PASS。新 failures helper 85 行，负责范围、基线、引用、预览和退休；Docker helper 125 行，state 136 行，CLI 163 行；修改/新增测试最大为 failures 测试 250 行，均小于 300。实现与入口分离，`release-retention-failures.py:14`、`:23` 复用统一 scope 和 record，未引入前端 any 类型。 |
| 类型与损坏输入 | PASS。`release-retention-state.py:37`、`:48` 校验计数、业务键、非负精确 int（拒绝 bool）及基线不能超过计数；`:11` 和 `release-retention.py:31` 限制 release，避免回执路径穿越。`test_release_retention_failures.py:189` 验证非法计数拒绝清理。 |
| 异常、持久化、并发 | PASS。`release-retention-state.py:90` 共用独占锁，`:119` 原子写；`release-retention-failures.py:72` 每次退休前重新核对引用；`release-retention.py:21` 清理异常不回流部署。`test_release_retention.py:176` 锁排他，`test_release_retention_failures.py:155`、`:169`、`:223` 覆盖落盘失败、新引用、健康/漂移/回滚缺失故障。 |
| 测试真实性 | PASS。新增生命周期测试使用真实临时 Store 和实际 managed/finalize/cleanup 路径，仅替换 Docker 命令执行器；`test_release_retention_failures.py:18` 实际抛构建/准备错误，`:26` 更新运行容器镜像，验证结果包括台账、审计、命令、返回值。Runner 在 `test_release_retention_docker.py:44` 按查询过滤元数据，修正了原先返回所有镜像的宽松前提。无标签测试验证外部项目与摘要的排除，以及 inspect/删除前变化；并非仅断言纯函数正常返回。 |
| 打包测试范围例外 | PASS。`test_release_wiring.py:35` 只排除没有 Docker 镜像发布的原生 credential-broker 入口。`codex-auth-deploy.py:12` prepare 复制原生源码，`:102` switch 排空并切换选定 worker，`:178` 独立 flock。原入口未改；`test_codex_auth_deploy.py:105`、`:120`、`:133`、`:220` 保留排空、限定停止、失败不盲回滚和拒绝覆盖测试，均包含在本次回归。 |
| 安全扫描 | PASS。对 9 个候选 Python 文件搜索 eval、innerHTML/dangerouslySetInnerHTML、前端 KEY/SECRET/TOKEN、常见密钥前缀、shell=True、密码赋值及用户绝对路径，无命中。人工核对 `release-retention-docker.py:18` 使用参数数组和 check=True，无 shell 拼接；`release-retention-failures.py:57` 只读经过 release 校验的回执路径。`test_release_wiring.py:20` 的 exec 仅编译受版本控制打包脚本的指定 allowlist AST，不处理运行时外部输入。未发现硬编码密钥、注入或新增业务目录删除。 |
| 视觉对比 | 不适用。无前端/页面变化；本次不启动业务页面或宣称浏览器视觉验收。 |

Docker 官方文档核对：所用 reference、label 和 dangling 过滤参数以及完整 ID 输出在 [image ls](https://docs.docker.com/reference/cli/docker/image/ls/) 有定义；非强制删除边界参考 [image rm](https://docs.docker.com/reference/cli/docker/image/rm/)。专属 builder 的 `--max-used-space` 参数参考 [buildx prune](https://docs.docker.com/reference/cli/docker/buildx/prune/)。这些文档用于确认命令合同，不替代服务器版本与实际运行验收。

### 验证边界

本 reviewer 独立运行模拟 Docker 命令与真实临时台账测试，没有重复操作真实 Docker daemon。主 Agent 的 Docker Desktop 29.4.3 隔离 smoke（本项目/其它项目无标签发现、停止容器拒绝删除及引用解除后删除）属于 `docs/RELEASE-RETENTION-FIX-20261020.md:22` 附近的交接证据，不混作本 reviewer 执行结果。Docker 命令检查与删除之间仍有外部管理操作的时间窗口；所有受控入口遵守共用锁，外部 Docker 操作不受锁控制的边界已在 `docs/RELEASE-RETENTION.md:54` 明示。未对未测能力作通过声明。

## 独立验证输出

全量命令：`.\hengxin-smart-image\backend\.venv\Scripts\python.exe -m pytest scripts/release -q`

```text
863 passed, 1 skipped, 309 subtests passed in 38.39s
```

退出码 0。没有 deselect 任何用例；skip 不计作通过。

历史命名命令：使用 `rg --files scripts/release -g '*-tests.py'` 获取 6 个文件，再传给同一解释器的 `-m pytest ... -q`。

```text
........................................................................ [ 62%]
sss.........................................   [100%]
113 passed, 3 skipped, 26 subtests passed in 1.69s
```

退出码 0。

编译命令：`.\hengxin-smart-image\backend\.venv\Scripts\python.exe -m compileall -f scripts/release`，退出码 0，强制编译整个发布目录成功。另外逐一强制编译 4 个运行变更文件，原始输出如下（退出码 0）：

```text
Compiling 'scripts/release/release-retention.py'...
Compiling 'scripts/release/release-retention-docker.py'...
Compiling 'scripts/release/release-retention-state.py'...
Compiling 'scripts/release/release-retention-failures.py'...
```

命令：`git diff --check`。退出码 0，原始输出：

```text
warning: in the working copy of 'DEV-PLAN.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'Product-Spec-CHANGELOG.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'Product-Spec.md', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'scripts/release/test_release_wiring.py', CRLF will be replaced by LF the next time Git touches it
```

两次文件检索最初使用 Windows 下不可展开的 `scripts/release/package*.py` / `test_*.py` 路径导致 rg 路径错误，已改用目录加 `-g` 重跑并读取结果；不计作验证通过或代码失败。

## 快照与移交

审查开始及完成前 `harness.py review-status` 的 `currentId` 均为上述 candidateId，没有发现审查中的代码变化。`approved: false` 表示 reviewer 尚未且不会代为登记批准。本 reviewer 只创建本报告，不修改实现、不提交、不写 `.needs-review`、不运行 review-approve。

主 Agent 可据本报告为同一 candidateId 登记 Stage 1 PASS / Stage 2 PASS；登记前及提交/交付前仍应检查快照匹配。后续服务器安装与服务/会话保护验收完成后另记实际证据。
