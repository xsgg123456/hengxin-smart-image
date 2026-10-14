# 部署镜像保留审查（2026-10-14）

## 快照与结论

- candidateId：`b63e9553233abaebf3ade6dc95140e74e5d7339ef18252b46e9c965b360bbdfc`。
- 范围：当前全部 git diff；新增 `scripts/release/release-retention*.py`、`release-build.py`、`test_release_retention*.py`、`test_release_wiring.py`；需求为 `Product-Spec.md:1` 的 2026-10-14 小节、`DEV-PLAN.md:1`、`docs/RELEASE-RETENTION.md`，包含已确认的 `.agents/skills/release-builder/SKILL.md:26` 限时轮询规范修改。
- Stage 1：**FAIL，1 项 HIGH**。Stage 2：**未执行**，遵循 HIGH 阻断规则；不存在两阶段 PASS 授权。
- 审查及复现时 `harness.py review-status` 的 currentId 与送审编号一致；报告完成时再次检查已变为 `47888d9b9caf05c578f18c9b0d57fbb63c71dd08ac80bc877fffc2e64e64c4d1`，主 Agent 已开始修复。因此本报告结论和行号仅适用于送审 b63e 快照，不能覆盖正在修改的新版本。reviewer 未修改代码、未访问生产、未提交、未写 clean，唯一写入为本报告。

## Stage 1：问题

### HIGH R1：原部署已成功、随后读取快照或写台账失败，会陷入所有正常恢复入口均无法解除的状态

需求原文：`Product-Spec.md:4`「清理失败只告警并保留重试能力」，`:9` 验收包含「重复执行、中断恢复」；`DEV-PLAN.md:5` 要求持久部署前快照及重复/恢复通过。运维文档 `docs/RELEASE-RETENTION.md:35`要求按原 recover/resume 步骤恢复。

代码证据：

- `scripts/release/release-retention.py:59` 在调用原部署前持久化 pending.before；`:61` 调用原部署。
- `scripts/release/release-retention.py:72` 成功后第一次 Docker 快照可能瞬时失败，`:76` 写台账也可能失败；`:77` 仅告警返回，没有可持久消费的成功状态或独立补记入口。
- `scripts/release/release-retention.py:48` 下一次 deploy 拒绝已有 before；`:44` 将恢复导向原 main。真实 `scripts/release/native-studio-deploy.py:111` 已将 PHASE 写为 complete，而其 `:121` 的 recover 只允许 verify-installed 阶段，无法处理成功后的台账故障。
- `scripts/release/release-retention.py:96` init 拒绝 pending.before；`:112` abandon 必须通过 plan；`scripts/release/release-retention-docker.py:74` plan 又拒绝旧台账与已成功新镜像的漂移。因此 preview/cleanup/abandon 均无法修复；新发布也会被 `release-retention.py:55` 的旧 current 挡住。

隔离复现：临时真实 Store、FakeDocker 初始 A；模拟原部署完成并写 PHASE=complete、运行镜像切到 B，随后一次 snapshot 抛 RuntimeError。恢复正常 snapshot 后，分别调用 managed deploy 和由真实 native-studio-deploy.recover 实现的恢复回调。原始关键输出：

```text
after successful main: pending= ['A'] completed= []
deploy blocked: RuntimeError Interrupted deployment: use recovery
recover blocked: AssertionError
cleanup count= 0
```

未发生误删或业务停机；严重性来自核心生命周期不能闭环，且阻塞后续正常发布。现有 `scripts/release/test_release_retention.py:140` 只证明当场不清理，未验证故障解除后能补记；`:95` 使用可无条件完成的假恢复函数，未覆盖真实恢复入口的阶段限制。

修复验收：提供与原部署/迁移分离的成功补记流程，保留真实 before、验证后的 after 及可核验成功证据；重试只补记和清理，不重放部署。至少覆盖原 main 成功后 snapshot 瞬断、台账写失败、进程中断、重复补记及 live 漂移拒绝。成功回执 + finalize 可以覆盖取得 after 后的台账写失败，但仅在 after 成功时写回执不足以覆盖本次复现；第一次 snapshot 失败也需要有明确、受验证约束的人工复核登记或独立重验路径，不能自动把未知结果视为成功。

## Stage 1：逐条需求核对

| Spec 条目 | 结果 | 证据与验证 |
|---|---|---|
| 国内/海外/身份独立 current/previous，以实际 ID 和部署前快照推进；未变化及重复不推进 | 完整实现常规路径 | `release-retention-state.py:56` 按 group 比较；`release-retention.py:39` 完成快照去重；`test_release_retention.py:67` A/B/C 与重复、`:83` 海外独立推进，复跑通过。|
| 原发布安装/健康/业务验证返回后才推进；失败不推进；清理失败不进入原停机路径 | 部分实现 | `release-retention.py:60`、`:70` 保持原 main 和后处理边界；`member-release-deploy.py:71`、`native-studio-deploy.py:97` 原发布验证后返回；`test_release_retention.py:95`、`:128` 通过。成功后登记异常不能恢复，见 R1。|
| 构建/准备/部署/恢复/init/cleanup 共用锁 | 完整实现 | `release-retention.py:35`、`:92`，`release-retention-state.py:78` 非阻塞 OS 锁；`test_release_retention.py:170` 两个 Store 争锁及异常释放通过；`test_release_wiring.py:39` 所有 Python 入口外层 managed 接线通过。|
| 持久保护 built/prepared/failed、全部容器含停用、各上一版和部署前镜像 | 完整实现已测路径 | `release-retention.py:57`、`:63`、`:67`；`release-retention-docker.py:31` 使用 ps -aq，`:71`、`:83` 汇总保护且实时解析候选 tag；`test_release_retention.py:117` 及 Docker 保护测试通过。|
| 仅项目镜像，无强制容器/卷删除；多标签及外部引用保护 | 完整实现 | `release-retention-docker.py:53` 仓库过滤，`:92` 全部标签/摘要属于项目才入候选，`:104` 逐镜像重查，`:107` 只非强制 image rm；`test_release_retention_docker.py:75` 外部别名、`:102` 命令边界、`:126` 新引用重查测试通过。|
| 显式初始化上一版、镜像存在及运行状态校验；未初始化/损坏/漂移拒绝清理 | 完整实现常规路径 | `release-retention.py:94`、`:104`；`release-retention-docker.py:61`、`:68`、`:80`；`release-retention-state.py:25`、`:96`；CLI init/补缺/缺失镜像测试及损坏/漂移测试通过。R1 状态不能通过 init 越过，保护是正确的，但缺少恢复入口。|
| 专属 Buildx、默认缓存、显式完整重建、2 GiB 未使用缓存目标、不接管旧 builder | 完整实现命令契约 | `release-build.py:6`、`:9`、`:25`；`release-retention-docker.py:111` 有 pending 不 prune，`:116` 显式 builder + max-used-space；构建和错误 driver 测试通过。对照 Docker 官方 [ls](https://docs.docker.com/reference/cli/docker/buildx/ls/) 的 Builder 模板及 [prune](https://docs.docker.com/reference/cli/docker/buildx/prune/) 参数；未运行真实 Docker，不能声称实际空间已回收。|
| 数据库/存储/图片/任务/认证/会话/备份/CLI/发布目录/基础镜像不清理；保留 Compose 链、不自动回库 | 完整实现本次清理边界 | 新增清理唯一 Docker 修改命令在 `release-retention-docker.py:107`、`:116`，无业务数据、容器、卷删除命令；原部署异常/迁移/备份逻辑未改。`docs/RELEASE-RETENTION.md:58`记录历史入口和迁移边界。|
| 测试覆盖双业务/A-B-C/失败/重复/中断/损坏/漂移/引用/在途/锁/数据禁止 | 部分实现 | 本次复跑 58 项新 retention 与接线测试通过；R1 中断恢复缺口有独立复现。|
| 所有包带入 helpers，既有 Python 入口受管理，历史 shell 不用于新发布 | 完整实现选择器和入口接线 | `package-overseas.py:11`、`:31`、`:66`，`package-delivery.py:12`、`:22` 及各包同类修改；`test_release_wiring.py:14` 所有 packager 必选四 helper、排除测试/伪路径通过。实际安装包构建未执行，包 selector 验证不替代安装验收。|
| 新增限时轮询规范 | 完整实现规范修改 | `.agents/skills/release-builder/SKILL.md:26` 包含总时限、单次探测剩余时限及确认生效后执行依赖步骤。属于已授权规则更新，不是本轮新增业务功能。|
| 本地实施，不生产部署/清理/提交/推送 | 符合 | 本审查仅本地临时状态、模拟 Docker、pytest、compileall、只读 git/harness 与报告写入。无生产操作。|

UI/设计与引导：本轮没有 UI、页面、业务 API 或视觉变更，设计稿/邻居页面渲染比较不适用（`DEV-PLAN.md:3`）。运维恢复说明存在 R1 所述不可达分支，需要同步修订。

Spec 漂移：上述差异中未发现新增未授权业务功能；初始化、preview、abandon、专属 builder、helper 打包均服务于本条生命周期。Stage 2 的全面质量、安全扫描和视觉流程未执行，不把 Stage 1 边界核对当成 Stage 2 PASS。

## 本地验证原始结果

解释器：`hengxin-smart-image/backend/.venv/Scripts/python.exe`。

```text
python -m pytest scripts/release/test_release_retention.py scripts/release/test_release_retention_cli.py scripts/release/test_release_retention_docker.py scripts/release/test_release_wiring.py -q
..........................................................               [100%]
58 passed in 0.54s
exit_code=0
```

完整目录复跑曾传入一个不存在的 deselect 节点，因此实际上没有跳过失败用例，真实结果如下：

```text
FAILED scripts/release/test_release_native.py::NativeReleaseTests::test_frontend_manifest_matches_seven_native_files
1 failed, 325 passed, 1 skipped, 117 subtests passed in 9.92s
exit_code=1
```

失败原始断言：

```text
> self.assertTrue(manifest['composeBaseOverlays'][-1].endswith('annotation-20260924-6b43b3c/api-override.yaml'))
E AssertionError: False is not true
scripts\release\test_release_native.py:100: AssertionError
```

`test_release_native.py:100` 与 `image-inputs-frontend.py` 本轮均无修改；主 Agent 另行报告已从 HEAD 原文件复现同失败（本审查未重复其 HEAD 隔离试验）。不把此既有失败算作本轮缺陷，也不将完整回归标为全绿。

编译原始结果：

```text
python -m compileall -q scripts/release
stdout: （空）
stderr: （空）
exit_code=0
```

## 交接

修复 R1 后重新 review-prepare，从 Stage 1 复审新快照；通过后再进入 Stage 2。不得给当前 candidate 登记两阶段 PASS。
