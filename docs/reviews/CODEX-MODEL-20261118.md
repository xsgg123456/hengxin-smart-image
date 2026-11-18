# 国内、海外 Codex 模型与模型发布入口审查

主树初始 candidateId 为 `5509cf2ffe657a061f4c40965ce2b1327cd83edef2859e86905a351db116122c`。审查中模型发布策略增加了候选提交与打包来源一致性检查，运行时脚本及测试随后落地。复审快照为 `66a4312dcca8f11e04a44bd7c9cadd564a040f80af54b40048994e2a7d7c2606`。本报告覆盖业务模型、五份相关测试、需求与计划、分组后端发布与维护互斥入口。服务二进制升级事务内部由独立 reviewer 审查。以下业务代码路径相对 `hengxin-smart-image/backend/`，发布路径相对 `scripts/release/intranet/`。

## Stage 1  PASS（模型与模型发布）

| 需求 | 核查证据 |
| --- | --- |
| 国内五工作台每次执行使用指定模型、推理和 Fast，续聊保留原 ID | `app/modules/domestic_studio/task_schemas.py:5` 列出五工作台；共用 `app/modules/domestic_studio/runner.py:124` 和 `:127`、`app/modules/api_image_edits/execution_policy.py:2`。独立 PostgreSQL 实例执行 `tests/test_domestic_runner_pg.py:76`，真实创建两轮并断言第二次 argv 使用首轮原 ID。 |
| API 图片 CLI 会话及管理显示 | `app/modules/api_image_edits/conversation_runner.py:156`、`:158`、`:160`，`app/modules/management/execution_settings.py:24`；`tests/test_api_cli_conversation.py:111` 走新会话及续聊，`tests/test_management_api_monitor_settings.py:105` 验证公开设置。 |
| 海外设计工作台的新/续聊以及原 ID | `app/overseas/studio/execution.py:62`、`:65`，公共 Fast 参数 `app/overseas/execution/runner.py:107`。行为断言见 `tests/test_studio_model_selection.py:9`、`tests/test_overseas_runner.py:80`。 |
| 海外分析、重新分析、生成、返工 | `app/overseas/plans/analysis.py:49`、`app/overseas/generation/delivery.py:116` 注册四项任务。导入真实处理器确认均使用默认 CLI 参数路径 `app/overseas/execution/runner.py:104`。 |
| 独立生图及账号探针保持各自策略 | `app/modules/api_image_edits/config.py:9` 中图片模型为 gpt-image-2.5-sunburst；`app/account_management/probe.py:28` 仍为 low、read-only。 |
| 按业务基线精确发布三个文件 | `model_maintenance.py:3`、`:20`，`scope_changes.py:153`、`:159`。从 Git 归档检查国内 494、海外 482 份后端文件。三个旧哈希在两组完全一致，三个新哈希逐一命中策略；真实导入图中策略常量归国内、其余两文件为两业务共用。拒绝额外文件、错误基线/提交来源及缺失文件的测试见 `test_model_maintenance.py:48`。 |
| 分组切后端、排空失败恢复、保留前端及上一成功版本 | `release_cli.py:53`、`scope_engine.py:45`、`:120`、`scope_actions.py:27`、`engine.py:162`、`release.py:155`、`scope_snapshot.py:142`、`scope_release.py:54`。模拟完整发布/回退、排空失败、运行源未切换分别核验两业务台账与非目标服务，见 `test_model_maintenance.py:66`、`test_scope_engine.py:95`。 |
| 运行时维护与模型发布互斥 | `release_cli.py:27`、`:36`、`stage.py:70`、`:74` 在台账锁内调用维护标记门禁。二进制版本及生产冒烟以运行时审查与部署验收为准。 |
| UI、Spec 漂移 | `Product-Spec.md:3`、`DEV-PLAN.md:3`、`Product-Spec-CHANGELOG.md:3` 与变更范围匹配，无前端文件、页面、路由或数据库迁移。 |

## Stage 2  FAIL（66a4312 快照）

MEDIUM。干净 Python 进程单独执行既有 stage CLI 用例失败。实际入口 `stage.py:72` 导入完整运行时模块，`codex_runtime_maintenance.py:37` 在导入时解析 systemd 路径；`test_stage_web.py:63` 允许使用仅提供 staging 能力的 adapter。模块若在先前测试中被缓存，该回归会被掩盖。生产 engine 具有 SYSTEMD，当前证据指向载入耦合和可重现的隔离测试故障。

```text
E   AttributeError: 'types.SimpleNamespace' object has no attribute 'SYSTEMD'
scripts\release\intranet\codex_runtime_maintenance.py:37: AttributeError
1 failed, 56 passed, 2 skipped, 10 subtests passed in 11.82s
```

两个跳过项是 `test_scope_flow.py:308` 和 `:323` 的 Linux 文件描述符回收用例。五份业务测试在新建、退出时销毁的 PostgreSQL 18 实例和临时存储运行。原始汇总如下。

```text
48 passed, 2 warnings in 17.29s
```

运行代码差异仅为同名常量替换与结构化参数数组，见 `app/modules/api_image_edits/execution_policy.py:2`、`app/overseas/execution/runner.py:105`、`app/overseas/studio/execution.py:62`。新增模型策略仅涉及常量、字典和摘要比较，见 `model_maintenance.py:20`；未新增秘密、动态命令、SQL 或网络访问。三文件跨基线直接编译原始输出如下。

```text
compiled backend/app/modules/api_image_edits/execution_policy.py
compiled backend/app/overseas/execution/runner.py
compiled backend/app/overseas/studio/execution.py
```
## 上轮复审  Stage 1 PASS / Stage 2 PASS

上轮 candidateId 为 `9f57d81a83f0c8ad1a892d9e0a0bc2c1607147e832f88a3f962dc6e3b5534763`。结论限于本报告的模型、发布入口和互斥范围。已在本快照逐项复核 Stage 1 对照表。相对 66a4312，运行时标记读取与校验独立为 `codex_runtime_marker.py:9`、`:21`，`stage.py:72`、`release_cli.py:34` 直接导入轻量门禁。在新 Python 进程从两个实际命令路由进入，同时验证两类行为：空闲时 domestic 和 overseas 均仅调用后端发布；running 时两个入口均在任何发布动作前拒绝。此前 MEDIUM 问题已关闭。运行时事务、共享账号控制组及 sosreport 台账校正由对应审查报告覆盖。

四个发布测试文件在 WSL Ubuntu 独立运行。Windows 两个因文件描述符语义跳过的现有用例也通过。以下为功能与编译原始输出。

```text
domestic routed to backend
overseas routed to backend
interlock refused: Resolve pending Codex runtime maintenance with recover
interlock refused: Resolve pending Codex runtime maintenance with recover
both entrypoints verified in a fresh process
59 passed, 10 subtests passed in 4.05s
compiled 13 model release, marker and test modules
```

## 最终复审  Stage 1 PASS / Stage 2 PASS

candidateId 为 `b38d1bb383266e7fc72752b1e4238da8140805c2716e0db2071641f8c25e9ed3`。本次复核模型和模型发布路由。三份模型源码重新比对 `model_maintenance.py:8` 的 SHA-256 并编译通过。独立复核 `release_cli.py:34`、`:53` 和 `stage.py:72`，两个入口均使用 `codex_runtime_marker.py:21` 的门禁。账号服务停止后遗留 socket 的匹配处理由运行时专项覆盖。Linux 上重新运行 staging、模型准入、分组事务和回退路径的四份测试，原始输出如下。

```text
verified and compiled backend/app/modules/api_image_edits/execution_policy.py
verified and compiled backend/app/overseas/execution/runner.py
verified and compiled backend/app/overseas/studio/execution.py
59 passed, 10 subtests passed in 4.63s
```
## 运行时拆分后最终复核  Stage 1 PASS / Stage 2 PASS

最终 candidateId 为 `4eb0424bff2b7a166b447e9e02a1cf1e4fd94bb23ee4a98dadb0b04c4b8ab274`，范围为国内和海外业务模型、模型发布路由及其维护门禁。三份业务源码重新核对 `model_maintenance.py:8` 记载的哈希并编译。拆分后 `release_cli.py:34` 与 `stage.py:72` 仍从独立门禁模块导入 guard，`release_cli.py:53` 将 prepare-model 路由到目标组后端。当前快照在 WSL Ubuntu 上重跑四份发布测试，原始输出如下。

```text
3 reviewed business source hashes matched; 3 files compiled
59 passed, 10 subtests passed in 3.40s
```
