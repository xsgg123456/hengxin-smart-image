# 部署镜像保留最终审查（2026-10-14）

## 快照、范围与结论

- candidateId：`27aa7dbce2f209544dee113125a6a42b0fdbae4804c0a200befe6374aae23bad`。
- **Stage 1：PASS。Stage 2：PASS。** 本轮没有发现需要阻断的新增问题。完整历史回归存在一项 HEAD 已有失败，不能宣称全部测试全绿。
- 使用 `.agents/skills/code-review/SKILL.md`。审查范围为送审时全部 Git diff，以及未跟踪的 `scripts/release/release-retention*.py`、`release-build.py`、`test_release_retention*.py`、`test_release_wiring.py`；包含全部发布入口、打包选择器及对应测试、`.agents/skills/release-builder/SKILL.md:26`。源需求为 `Product-Spec.md:1` 同日全部八条、`DEV-PLAN.md:1`、`Product-Spec-CHANGELOG.md:1`、`docs/RELEASE-RETENTION.md`。
- 首次及验证结束的 `harness.py review-status` 均返回上述 currentId；未发现受控代码快照变化。期间主 Agent 补充了普通运维 Markdown 的本地 Docker 只读验证记录，不改变代码快照。本报告不沿用旧失败快照的通过结论。
- 仅执行本地读取、临时状态/模拟 Docker 测试、Python 编译和报告写入；未访问生产、未部署/清理生产、未提交、未写 clean。主 Agent 可据本报告为同一 candidateId 登记两阶段 PASS，登记后仍应检查快照匹配。

## Stage 1：Spec Compliance

下表的“完整实现”指本地代码与所列验证证据满足本轮交付范围，不代表已经在生产启用。

| 需求 | 结论 | 代码与验证证据 |
|---|---|---|
| 国内、海外、中立身份独立记录 current/previous；用实际镜像 ID 和部署前快照，不猜日期；未变化或重复完成不推进 | 完整实现 | `scripts/release/release-retention-docker.py:8` 三组拓扑、`:35` 实际容器 Image；`release-retention-state.py:56` 逐组 advance；`release-retention.py:65` completed 去重。`test_release_retention.py:67` A/B/C 与重复、`:83` 海外单组推进通过。 |
| 原安装/健康/入口/业务验证返回后才更新；部署或恢复失败不推进、不清理；清理失败不触发原关闭/回滚 | 完整实现 | `release-retention.py:90` 先存 pending，`:92` 调用 main，`:93` 异常只存失败再抛出，`:102` 后处理处于原 main 异常处理之外，`:20` 独立吞掉清理异常并告警。实际 `member-release-deploy.py:71`、`native-studio-deploy.py:97` 在验证完成后返回；所有入口外层接线测试 `test_release_wiring.py:39` 通过。失败/恢复与清理异常测试通过。 |
| 验证成功先写独立回执；首次读取快照/台账写失败可补记、不重放部署；补记核健康和 before/candidate 范围；回执也丢失则保护并人工复核 | 完整实现，旧 R1 已关闭 | `release-retention.py:103` 回执写入先于 `finalize`；`:71` 在原 main 前拦截重试；`:35` 校验回执与 pending 一致、服务集合及镜像范围；`:43` 经 Docker.snapshot 复核健康；`:139` 专用 finalize。`test_release_retention.py:190` 快照瞬断、`:207` 台账写失败/漂移拒绝/恢复不重放均通过。另独立注入回执写入 OSError，原历史与 pending 保留且 cleanup 未调用。人工处理边界见 `docs/RELEASE-RETENTION.md:37`。 |
| 构建、准备、部署、恢复、初始化和清理共用互斥锁；候选跨阶段持久保护 | 完整实现 | `release-retention.py:62`、`:121` 共用 Store.locked；`release-retention-state.py:78` 操作系统文件锁；`release-retention.py:88`、`:98` 记录阶段与候选。锁竞争/异常释放及 build/prepare 测试通过。所有 Python 入口 AST 接线测试通过。 |
| 所有容器含停止容器、各业务上一版、在途候选和部署前镜像保护；额外引用优先 | 完整实现 | `release-retention-docker.py:32` 使用 ps -aq；`:71` 容器引用保护，`:76` current/previous，`:83` pending ID、当前候选标签解析与 before。`test_release_retention_docker.py:75` 起的保护/外部别名测试、`:126` 起的删除前新增引用测试通过。运维规则明确额外引用允许超过两版（`docs/RELEASE-RETENTION.md:11`）。 |
| 仅删除明确项目镜像，不强删容器或卷；多标签/外部别名保护 | 完整实现 | `release-retention-docker.py:54` 精确仓库前缀筛选，`:92` 全部标签/摘要归属检查，`:102` 每次删除前重算，`:107` 只按具体标签执行非强制 image rm；外部 tag/digest 与命令边界测试通过。 |
| 首次显式登记上一版并核镜像/运行快照；历史缺失、损坏、漂移拒绝清理；初始运维 ID 不硬编码 | 完整实现 | `release-retention.py:124` 初始化，`:130` 禁覆盖已有历史；`release-retention-docker.py:61` 项目镜像解析，`:67` 历史/漂移/存在性检查；`release-retention-state.py:25`、`:96` 校验台账。CLI 初始化/补齐/缺失镜像及损坏/漂移测试通过。实现无 Spec 所列初始短 ID 常量。 |
| 专属 Buildx、默认缓存、显式完整重建；专属未使用缓存目标 2 GiB，不接管默认 builder | 完整实现命令契约 | `release-build.py:6` 专属名称，`:9` 创建及 driver 校验，`:25` --load 构建，`:31` 显式 no-cache；`release-retention-docker.py:111` 有 pending 不清缓存，`:116` 只 prune 指定 builder。构建/错误 driver 测试及 reviewer 默认缓存独立断言通过。未执行真实构建和缓存删除。 |
| 数据库、对象存储、图片、任务、认证、会话、备份、CLI、发布目录、基础镜像不清理；Compose 链不删、不自动回库 | 完整实现本次清理边界 | 新模块唯一 Docker 修改命令为 `release-retention-docker.py:107` image rm 和 `:116` buildx prune；无卷/容器/业务目录/数据库删除。`release-build.py:13`、`:33` 仅专属 builder 创建与构建。所有原部署业务验证、备份和异常处理主体在 diff 中保留，未改 Compose 链。 |
| 验收覆盖独立推进、A/B/C、部署失败、清理失败、重复、中断、初始化缺失/损坏、漂移、多标签/外部引用、在途、锁竞争和数据操作禁止 | 完整实现本地验收 | 35 项 retention 状态/CLI/Docker 测试与 25 项入口/打包接线测试，共 60 passed。故障恢复用真实临时 Store，注入的异常发生在可达的 snapshot/ledger.write 边界；非仅纯函数成功测试。详细原始输出见下文。 |
| 打包带 helpers，保留原入口参数/验证顺序 | 完整实现选择器及接线 | `package-overseas.py:11`、`:31`、`:66`，`package-delivery.py:12`、`:22`，其余 package 同类白名单/必选校验；`test_release_wiring.py:14` 遍历所有包，验证四 helper、拒绝测试及伪路径。`member-release-resume.py:111` 与 `overseas-codex-deploy.py:225` 适配原特殊参数。实际发布包尚未构建。 |
| 发布技能增加统一总时限轮询、单次探测剩余时限、实际生效后再执行依赖步骤 | 完整实现规范修改 | `.agents/skills/release-builder/SKILL.md:26` 单行新增完整表达三项要求，无新增业务行为。属于已授权通用发布规范。 |
| 本轮本地实现/隔离验证，不生产操作或自动提交推送 | 符合 | `DEV-PLAN.md:3`、`:8`，`docs/RELEASE-RETENTION.md:3`；本报告所列执行命令均本地测试、读取或报告写入。 |

部分实现：无。未实现：无。Spec 漂移：未发现未授权的新页面、API、表或业务能力；新增 init/preview/cleanup/abandon/finalize 均服务于需求中的保留与恢复生命周期（`release-retention.py:115`）。

UI 一致性与引导真实性：本轮无页面、视觉或业务交互变更，`DEV-PLAN.md:3` 明确无 UI；无需设计稿/邻居渲染比较。运维命令与 `release-retention.py:115` 的真实 CLI 匹配；成功后故障补记和回执未落盘的人工边界均已说明。

## Stage 2：Code Quality

- **质量 PASS**：新增核心文件分别为 155、123、118、33 行，测试最大 224 行；状态/原子存储、Docker 边界、构建和入口编排分离（`release-retention-state.py:25`、`:69`，`release-retention-docker.py:22`，`release-build.py:25`，`release-retention.py:55`）。没有新增 any；采用字典运行时校验，错误默认拒绝清理。既有各入口动态加载/打包白名单模式有重复，本轮遵循项目先例，未构成阻断问题。
- **安全 PASS**：扫描新增四模块的 eval、shell=True、前端密钥前缀、硬编码密码/密钥模式未命中。`release-retention-docker.py:16` 使用参数数组 subprocess、无 shell 拼接；`release-retention-state.py:12` 限制 release，`:72`、`:80`、`:97` 拒绝关键路径符号链接，`:106` 限定报告文件名；`:109` 临时文件、fsync、replace 以及目录 fsync 提供持久原子替换。固定 `/var/lib/hengxin-release` 是需求中的服务器状态路径，不是泄露个人路径。
- **测试真实性 PASS（限本地范围）**：测试真实写入临时 JSON 与争用文件锁，Docker 元数据和发布动作明确模拟。`test_release_retention.py:190`、`:206` 验证故障恢复不能调用原 main；`test_release_retention_docker.py:126` 注入新引用，断言删除命令不存在；`test_release_wiring.py:39` 防止 managed 被放进原失败分支。测试替换旧 builder 调用是为隔离 Docker，真实 builder 参数由独立合同测试覆盖，没有删去安装哈希不符等原失败断言（`test_overseas_deploy.py:200`）。
- **外部接口复核**：独立读取 Docker 官方 [buildx ls](https://docs.docker.com/reference/cli/docker/buildx/ls/) 与 [buildx prune](https://docs.docker.com/reference/cli/docker/buildx/prune/)，确认 `.Builder`、`--builder`、`--max-used-space 2gb` 及 in-use 缓存不可回收语义。主 Agent 另有本机 CLI 只读证据；本 reviewer 未运行真实镜像构建或删除。
- **视觉对比**：不适用，无 UI 改动，依据 `DEV-PLAN.md:3`，未伪称打开了页面。
- **限制明确**：生产初始化、实际 Docker 构建、实际回收空间和线上业务验收未执行（`docs/RELEASE-RETENTION.md:63`）。锁只能覆盖共用状态目录的新入口，外部 Docker 操作及旧包不受控制；文档已明确这些边界。

## 独立执行的原始验证结果

解释器：`hengxin-smart-image/backend/.venv/Scripts/python.exe`。

```text
python -m pytest scripts/release/test_release_retention.py scripts/release/test_release_retention_cli.py scripts/release/test_release_retention_docker.py scripts/release/test_release_wiring.py -q
............................................................             [100%]
60 passed in 0.47s
exit_code=0

python -m pytest scripts/release -q
FAILED scripts/release/test_release_native.py::NativeReleaseTests::test_frontend_manifest_matches_seven_native_files
1 failed, 327 passed, 1 skipped, 117 subtests passed in 9.99s
exit_code=1

python -m pytest -q <全部 scripts/release/*-tests.py>
113 passed, 3 skipped, 26 subtests passed in 1.85s
exit_code=0

python -m compileall -q scripts/release
stdout: （空）
stderr: （空）
exit_code=0

git -c core.safecrlf=false diff --check
stdout: （空）
stderr: （空）
exit_code=0
```

完整目录唯一失败原始断言：

```text
> self.assertTrue(manifest['composeBaseOverlays'][-1].endswith('annotation-20260924-6b43b3c/api-override.yaml'))
E AssertionError: False is not true
scripts\release\test_release_native.py:100: AssertionError
```

reviewer 独立从 Git HEAD 提取 `test_release_native.py`、`image-inputs-native.py`、`image-inputs-frontend.py` 到临时目录，只跑该节点，结果：

```text
FAILED ::NativeReleaseTests::test_frontend_manifest_matches_seven_native_files
1 failed in 1.60s
HEAD isolated exit_code=1
```

三个文件本轮无 diff，HEAD 隔离输出同一第 100 行断言，确认不是本轮新回归。它仍是项目既有失败，没有算作通过。

额外独立故障注入及默认缓存断言输出：

```text
receipt-write failure: original history and pending protection preserved; cleanup not called
default build: cache enabled, isolated builder selected
exit_code=0
```

最终快照复查的 `currentId` 保持 `27aa7dbce2f209544dee113125a6a42b0fdbae4804c0a200befe6374aae23bad`。此报告只批准本地送审实现，不授权生产操作或 Git 提交。
