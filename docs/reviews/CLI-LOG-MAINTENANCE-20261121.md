# 国内、海外 CLI 日志后端维护工具独立审查

**Stage 1 PASS；Stage 2 PASS。** 候选快照 `4a9ab0e2c1ed0a21fcf2c938fd87fae204c5da1ef3b38472d6a41030c6079243`。审查前后运行 `review-status` 均得到该编号及相同的 5 个代码改动。基准提交为 `406eaf4abec3c6f8715d3e90e26d25d33ca218ae`。本报告覆盖该提交之后的发布工具和专项操作说明。生产安装、发布、健康和实际净释放量需由执行人凭生产回执验收。

审查文件为 `scripts/release/intranet/` 下的 `cli_log_candidate.py`、`cli_log_maintenance.py`、`release.py`、`release_cli.py`、`test_cli_log_maintenance.py`，以及 `docs/CLI-LOG-MAINTENANCE-20261121.md` 和 `docs/INTRANET-RELEASE-TOOLS.md`。下表中未带目录的 Python 文件均在该发布工具目录。依赖模块只读交叉检查。

## Stage 1 · 需求符合性

| 验收项 | 核对结果与证据 |
| --- | --- |
| 两个生产基线、两份固定补丁 | 通过。独立临时 Git 对象库分别重建国内 `2d42d0d782429453f86ba31ba22f50e0a32c0d4d` 和海外 `476d7c610a303a79b84e9e88ac87a0b4773eb623`。差异分别为 21、17 个文件，均来自指定应用提交的路径清单。固定父提交、树、作者、日期和消息共同确定候选。见 `cli_log_candidate.py:12`、`:28`、`:41`、`:62`，以及专项文档第 11–16 行。 |
| 暂存与后端清单 | 通过。门禁要求二版台账中的已暂存目录，逐组核实新旧完整提交、scope、构建来源和全部后端文件摘要。实际文件由 `snapshot.py:23` 调用 `hengxin-smart-image/scripts/migration245/unify_release.py:167` 遍历校验。正式压缩包逐成员复核结果见下表。见 `cli_log_maintenance.py:27`、`:36`，`stage.py:42`。 |
| 前端、共享服务和另一组 | 通过。专项入口固定 backend 模式，各组的前端提交必须匹配固定值。事务继续使用原前端目录。Compose 仅替换目标服务的源码挂载，前端不在停启清单。其余服务的容器 ID、启动时间和原生进程身份参与比较。见 `release_cli.py:94`，`release.py:105`、`:159`，`scope_engine.py:38`、`:91`，`scope_snapshot.py:126`、`:138`。 |
| 数据库、镜像、卷和依赖 | 通过。按实际组阻断 schema 漂移，拒绝改迁移、依赖和运行时输入；重新抓取镜像、schema、数据身份及原生环境，比较事务前后。恢复同样验证数据身份。见 `cli_log_maintenance.py:30`、`:33`，`snapshot.py:34`、`:148`，`scope_snapshot.py:109`，`release.py:131`。本地保存的生产准备回执记录国内 0046、海外 overseas_0029、pending 为空。 |
| 逐组准备、排空和接单恢复 | 通过。操作顺序为国内通过 verify 后再发海外，见专项文档第 3、32–39 行。每次受主机、root 和台账锁约束，已有 pending 和未完成的迁移阻断准备。目标组先关接单、排空，再停服务并切换；排空失败走事务恢复。见 `release_cli.py:29`、`:36`，`release.py:72`、`:115`，`engine.py:159`、`:213`，`scope_actions.py:26`、`:83`。 |
| 事务成功、取消、中断、回退 | 通过。准备绑定目标前后端和维护标记，部署先备份，实际版本与服务验证通过后才保存完成。未开始可取消，已开始走 recover。回退检查本组前一版的 schema，并从当前配置重算本组变更。见 `release.py:101`、`:141`、`:171`、`:204`、`:234`，`scope_release.py:44`；双组成功/排空失败/未切换测试在 `test_cli_log_maintenance.py:49`，交错发布回退测试在 `test_scope_flow.py:187`。 |
| 两版保留与清理 | 通过。成功事务原子推进本组 current/previous，复核另一组不变；所有组的两版进入保护集。自动清理在成功保存之后，独立的清理警告不撤销已成功的发布。见 `release.py:174`、`:184`，`scope_catalog.py:30`、`:51`，`full_cleanup.py:11`、`:63`，`test_scope_flow.py:281`、`:323`。专项文档第 39 行要求核对实际净释放量。 |
| 包内超限交付 | 通过。核对从正式包读取后端、使用固定应用提交中的专项测试、按业务分别运行的脚本和日志。国内和海外用例各通过 1 项，分别用时 14.77、6.44 秒。另一业务用例由 `-k` 排除。见 `Product-Spec.md:1651`，专项文档第 20 行，`output/cli-log-maint-20261121/late_delivery.py:37`、`:58`，`packaged-domestic.log`、`packaged-overseas.log` 末尾。 |
| 范围、界面和运维指引 | 通过。变更新增一个限定业务的 CLI 准备动作、一个本地打包入口和专项策略。沿用现有部署、verify、cancel、recover 和 rollback 入口。见 `release_cli.py:9`、`:94`、`:105`，专项文档第 20–43 行，`docs/INTRANET-RELEASE-TOOLS.md:3`。本次无页面或设计稿变更，视觉比较不适用。 |

本人从两个正式包逐一校验所有成员、内容摘要、来源清单、scope 和固定后端清单摘要。两个包各有 4 项运行时输入。

| 业务 | 压缩包成员数，含清单 | 后端文件 | 本次压缩包 SHA256 |
| --- | ---: | ---: | --- |
| 国内 | 1112 | 503 | `899c44f407d8fd8bb04a3666e6ef877b479d3c6092e1e4ee8d7f67e9075a9a0b` |
| 海外 | 619 | 514 | `bb01b35ac2c7bf67445e3b94c319870a964a00bea2ac8f6cb30dfb7ff5259112` |

打包确定性覆盖候选源码和完整后端清单。两次以相同输入调用现有 `package_release.py:223`，解压得到相同 tar，gzip 头时间相差 1 秒，压缩包 SHA256 随之变化。专项文档第 14、20、28 行要求对此次实际包取摘要并校验传输。生产核对以上表本次包为准。

## Stage 2 · 实现质量

- **结构与安全通过。** 打包器 70 行，专项策略 45 行，测试 120 行，Release 类所在文件 259 行，命令路由 128 行。候选生成使用参数数组调用 Git、临时对象库和固定的许可范围；服务端复用旧工具的锁与事务机。五文件扫描未检出硬编码私钥、令牌、密码赋值、动态求值或 shell 执行。见 `cli_log_candidate.py:28`、`:39`、`:50`，`cli_log_maintenance.py:27`，`release_cli.py:31`。
- **测试真实性通过。** 专项测试使用替身后端目录和故障注入，覆盖 2 组 × 3 种发布结果、13 种准备前漂移、CLI 路由和回滚。见 `test_cli_log_maintenance.py:17`、`:49`、`:77`、`:110`。真实包及 Git 候选另外独立核实，生产网断开、仓库只读的 Linux 全套测试使用的五个源文件与送审文件逐一比对字节相同。可选跳过项未算作通过。见 `output/cli-log-maint-20261121/tool_suite.py:28`。
- **编译与原始执行结果。** 对五个文件用 Python 内置 `compile(..., 'exec')` 编译，退出码 0。Linux 全套隔离测试退出码 0。

```text
compile OK: release, release_cli, cli_log_candidate, cli_log_maintenance, test_cli_log_maintenance
618 passed, 10 skipped, 21 subtests passed in 18.59s
```

本次两阶段未发现阻断项。该结论限于上述候选快照与发布工具范围。
