# 国内工作台 capability 名称增量审查

- candidateId：`74a90dedea5da675804d29acfdd01fa96b56a411da68ef4965c7582676fc17cc`。
- 基线 HEAD：`2bc8acc7ecf412626a6a635a9413b1644b55417e`；已批准基线为 `DOMESTIC-STUDIO-FINAL-R14-20261113.md` 及 `DOMESTIC-STUDIO-NATIVE-IMPORT-20261113.md`。
- **Stage 1：PASS；Stage 2：PASS。无本增量阻断问题。**
- 范围：`scripts/release/intranet/joint_studio_verify.py` 一行运行逻辑、`test_joint_studio_verify.py` 的回归用例，以及既有恢复路径受影响行为。实施记录追加位于 `docs/DOMESTIC-STUDIO-IMPLEMENTATION-20261112.md:15`。未重复全业务、前端构建和视觉验收；无 UI 变更，视觉比较不适用。
- 已读 AGENTS、code-review SKILL、HARNESS-REVIEW、Spec/DEV-PLAN 顶部原文及两份基线报告。按先需求及恢复路径核查、再质量安全与独立验证执行。未修改产品代码、未提交、未连接生产、未登记批准、未写 `.needs-review`；既有 `=12.1,` 未动。

## Stage 1：需求符合性

本增量对应 `Product-Spec.md:15` 的安全发布要求及 `DEV-PLAN.md:13-21` 的实际身份、迁移后前向恢复要求。主 Agent 交接的生产 inspect 与迁移事实没有被冒充为 reviewer 实测。

| 范围内要求 | 结论和证据 |
| --- | --- |
| 两个等价名称均接受 | 完整实现。`joint_studio_verify.py:62` 仅接受集合 `{'CHOWN'}` 或 `{'CAP_CHOWN'}`；`test_joint_studio_verify.py:42-46` 两种输入独立通过。[Docker 官方说明](https://docs.docker.com/engine/containers/run/) 明确 capability 名称允许 `CAP_` 前缀。 |
| 不接受空、额外或混合能力集合 | 完整实现。`:62` 是集合精确相等，无前缀剥离、子集或字符串包含判断；`test_joint_studio_verify.py:49-55` 实际拒绝空集、SYS_ADMIN、CHOWN 加 SYS_ADMIN、双前缀和两种名称混合；`:71` 另覆盖无前缀额外 SYS_ADMIN。 |
| privileged、只读根、CapDrop、no-new-privileges、端口与网络保持 | 完整实现。`joint_studio_verify.py:60-64` 除能力名字比较外与 HEAD 相同。本 reviewer 独立针对两个合法名称分别把 Privileged 设 true、ReadonlyRootfs 设 false、CapDrop 清空、SecurityOpt 清空、添加 PortBindings、NetworkMode 设 host，12 项全部被真实 configuration 函数拒绝。 |
| 其它身份、挂载、环境和运行时检查保持 | 完整实现。`joint_studio_verify.py:37-58,68-91` 无差异；原有身份/挂载/跨业务环境及 gate 漂移测试 `test_joint_studio_verify.py:58-77` 本轮通过。没有新增权限或用户功能。 |
| 复用既有 0043 前向恢复，不回退数据库 | 完整实现且本增量未更改恢复逻辑。`joint_studio_release.py:180-218` 仍等待迁移事务、判别 schema、只对预期 0043 调用 forward；`joint_studio_forward.py:34-65` 使用 prepared 台账和既有 manifest，校验候选一致性；`joint_studio_release.py:141-177` 仍先核对迁移、实际运行快照，再登记并开放入口，异常 seal。发布/engine 回归本轮通过。 |
| 仅发布工具修复，不要求重建应用 | 匹配。Git 差异只有校验器及其测试，应用、镜像配置、迁移、manifest 生成逻辑无变化；`joint_studio_forward.py:48-59` 仍以原事务 release_manifest 为候选身份。可以安装此已批准工具版本后恢复原 2bc8acc 应用候选；生产工具安装完整性与最终入口验收仍须主 Agent 实查，报告不声称恢复已完成。 |
| UI、文案真实性及 Spec 漂移 | 不适用 UI 比较；本增量未新增页面、API、表、绑定或权限。范围内无部分实现、未实现或确认的 Spec 漂移。 |

Stage 1 无 HIGH，进入 Stage 2。

## Stage 2：质量、安全、测试真实性

- **结构通过。** `joint_studio_verify.py:62` 保留清晰的固定白名单条件，无通用规范化或额外依赖。运行文件 91 行、测试文件 77 行，均低于 300 行；Python 编译通过。
- **安全通过。** `joint_studio_verify.py:60-65` 没有放宽允许能力集合，仅接受同一能力的两种名称；其余权限拒绝分支已独立运行。增量文件检索动态 eval/exec、shell=True、动态 HTML、VITE 密钥、常见密钥前缀和开发者绝对路径无命中。`test_joint_studio_verify.py:69` 的 `OVERSEAS_API_KEY=secret` 是原有拒绝跨业务环境的固定假数据，不是真实密钥。
- **测试前提通过。** `test_joint_studio_verify.py:10-39` 使用 Docker inspect 结构的受控字典，直接调用实际 configuration，不 mock 能力判断；参数化测试 `:42-55` 包含本次生产交接的 CAP_CHOWN 形态。新增用例证明配置判别，不冒称实际 Docker 权限或生产集成测试；独立 12 项 guard 矩阵补足两种合法名称下其余防线。
- **恢复边界如实记录。** 三组测试共 42 passed、1 skipped；跳过的是 `test_joint_studio_release.py:308` 受 `TEST_DOMESTIC_STUDIO_DATABASE_URL` 限制的隔离迁移测试。本次没有修改迁移与恢复实现，既有真实迁移基线见 R14；不将历史证据称为本轮重跑。测试编排有替身，不代表生产恢复已执行。

## 独立验证原始输出

WSL，在 `scripts/release/intranet` 执行：

```text
/tmp/hengxin-domestic-studio-python/bin/python -m pytest test_joint_studio_verify.py test_joint_studio_engine.py test_joint_studio_release.py -q
..........................................s                              [100%]
42 passed, 1 skipped in 1.79s
```

额外通过 stdin 执行 Python 验证脚本：直接对两种 capability 各运行六种权限破坏，并对两个增量文件执行 `compile(source, path, 'exec')`。原始输出：

```text
INDEPENDENT_PRIVILEGE_GUARDS_PASS 12
PYTHON_COMPILE_PASS scripts/release/intranet/joint_studio_verify.py lines= 91
PYTHON_COMPILE_PASS scripts/release/intranet/test_joint_studio_verify.py lines= 77
```

上述命令均退出码 0。WSL 启动有宿主 localhost 代理转发提示，未影响运行。`git diff --check` 退出码 0，仅实施文档 CRLF→LF 提示。初次检索包含不存在的 `joint_studio_cli.py`，后续已定位真实 `joint_studio_release.py` 并完成路径核查。

审查前后 `review-status` 均返回上述 candidateId，changedFiles 仅校验器及其测试，无审查中代码变化。`approved:false` 为尚未由主 Agent 登记本次凭据。主 Agent 可使用同一 candidateId 和本报告登记两阶段 PASS，再继续已授权工具提交、安装和既有事务恢复；本报告不代表生产已经开放。
