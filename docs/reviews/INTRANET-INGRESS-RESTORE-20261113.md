# 入口恢复及安装测试隔离审查

- candidateId：`6a04eecc792cab3d59d402a1ed12acd8b6d61477c4a015c2f5b6c6a7e99ac837`
- 范围：`release_cli.py`、新增 `restore_ingress.py` / `test_restore_ingress.py`、`test_engine.py`、`test_joint_studio_engine.py` 的本次差异，以及 `docs/INTRANET-RELEASE-TOOLS.md:21` 合同增补。路径前缀为 `scripts/release/intranet/`。
- 依据：`Product-Spec.md:1500` 引用内网发布合同；本次精确行为以 `docs/INTRANET-RELEASE-TOOLS.md:21` 为准。业务 UI / 已审功能及生产安装脚本不在本次代码审查范围。
- 结论：**Stage 1 PASS；Stage 2 PASS**。无 HIGH / MEDIUM 阻塞项。审查期间 `review-status` 的 currentId 与送审编号一致；报告不批准其它快照，由主 Agent 登记凭据。

## Stage 1：Spec Compliance — PASS

| 合同条目 | 结论及证据 |
|---|---|
| 正式恢复入口沿用全局锁及主机限制 | 完整实现。`release_cli.py:19` 检查主机和 root，`:24` 持有原锁，`:25` 检查拆分迁移，`:30` 检查联合迁移，`:46` 路由新动作。原锁实现 `scripts/release/release-retention-state.py:91`。 |
| 仅已完成联合升级、普通发布空闲的当前版本 | 完整实现。`restore_ingress.py:11` 读取台账及联合标记；`:13` 要求 version 2、无 pending / migration_pending、complete 及 domestic publisher；`:17` 要求后台已开放。 |
| 完整核验源码、配置、运行环境及健康 | 完整实现。`restore_ingress.py:20` 使用正式 capture(runtime=True) 并与 current 严格比较，`:21` 调用 catalog.before。复用链为 `release.py:41`、`scope_snapshot.py:64`（源码/配置/健康/运行环境采集）、`catalog.py:100`（台账及镜像核验）；未增加跳过校验分支。 |
| 核验后再次确认状态未变化 | 完整实现。`restore_ingress.py:22` 再读台账和联合标记；`:24` 再查 workers 和 ingress，异常均在开放之前退出。 |
| 仅恢复 HTTP 入口并留回执 | 完整实现。`restore_ingress.py:28` 先保存 verified 和当前状态摘要，`:30` 唯一 gate 写入目标为 ingress，`:31` 保存 opened；不调用服务切换、数据迁移或台账 save。`joint_studio_paths.py:44` 原接口校验 marker 身份、写入、同步及回读。已开放时仍验证、无写入。 |
| 安装测试不能误写生产路径 | 完整实现本次修复。`test_engine.py:49` 拒绝逃离临时目录的模拟写入；`test_joint_studio_engine.py:155` 将两个 gate 方法隔离到内存并注册清理。原生产误写故障路径仍在 `test_joint_studio_engine.py:184` 运行，未删除断言或跳过测试。 |
| UI / 引导真实性 / Spec 漂移 | 无 UI 变更，不适用设计稿和邻居页面视觉比对。`release_cli.py:9` 的新命令对应真实实现；未发现超出合同的新业务功能、表或接口。 |

部分实现：无。未实现：无。

## Stage 2：Code Quality — PASS

- 结构及错误处理：新增实现仅 32 行，单一职责；所有核验失败自然抛出，正式入口由 `release.py:240` 输出拒绝。`restore_ingress.py:27` 至 `:31` 的副作用顺序清楚，预写回执失败不会打开入口。开放后回执失败会报错，需按实际 marker 复核，不能把异常当作从未开放。
- 测试真实性：`test_restore_ingress.py:26` 核验只改 ingress 且台账不变；`:36` 覆盖 pending、迁移、未完成标记、后台关闭、源码漂移、核验中台账/后台漂移；`:54` 覆盖已开放幂等。快照比较使用真实 `snapshot.same`。独立复跑三个变更测试文件共 36 项通过。
- 测试覆盖边界：新增测试未逐一注入 marker 二次变化、catalog 抛错及回执写入故障；这些路径通过顺序代码审查确认失败传播，不声称已做故障注入。线上实际开放与业务可用性仍属于主 Agent 的发布验收。
- 安全：对新增恢复模块、CLI 与新增测试执行密钥/危险函数模式扫描，没有匹配。无 eval、SQL、shell 字符串拼接或新增凭据；新逻辑只调用原受保护 gate 接口。证据 `restore_ingress.py:11` 至 `:31`、`release_cli.py:19` 至 `:32`。
- 原测试隔离不牺牲故障验证：`test_joint_studio_engine.py:202` 仍要求迁移后失败报 RECOVERY_UNCONFIRMED，`:204` 至 `:207` 仍检查 schema、回退文件、候选配置和停止入口行为；本次只替换外部 gate 副作用。

## 验证原始输出

独立语法编译：五个送审 Python 文件执行 `python -m py_compile`，无诊断输出，显式退出状态：

```text
py_compile exit=0
```

独立 WSL Ubuntu 复跑，使用 `/tmp/hengxin-domestic-studio-python/bin/python -m pytest`，目标为 `test_restore_ingress.py test_joint_studio_engine.py test_engine.py -q`：

```text
....................................                                     [100%]
36 passed in 3.22s
```

主 Agent 全套运行日志 `output/explicit-skill-ingress-tests.log` 已直接读取，测试输出：

```text
........................................................................ [ 17%]
............s........................................................... [ 35%]
...................................ss..........s........................ [ 53%]
....s............................................................ [ 70%]
........................................................................................................................                 [100%]
396 passed, 5 skipped, 15 subtests passed in 13.93s
```

5 项 skipped 不计为验证通过。首次尝试默认 WSL `/usr/bin/python3` 返回 `No module named pytest`，随后切换现有测试 venv 完成上述独立复跑；未安装依赖或操作远端。
