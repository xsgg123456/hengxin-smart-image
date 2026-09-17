# 固定生产模型增量审查

- 日期：2026-09-17；基线：`c607164`。
- 最终 candidateId：`0bb045467430d622862ddc3483a30b47df7324d1143f5e6bdbf905ac5c2691d1`。
- 范围：`backend/app/execution/codex_runner.py`、`backend/tests/test_codex_runner.py` 相对基线的改动；依据根目录 `Product-Spec.md:13`、`DEV-PLAN.md:3–7`。不重新验收整个产品历史功能或部署完成情况。
- Stage 1：**PASS**。Stage 2：**PASS**。本报告不代替主 Agent 的 review-approve。

## Stage 1：Spec Compliance

| 本轮全部需求 | 结论与证据 |
|---|---|
| 首次执行显式指定 gpt-6-astra/high | 完整实现。`backend/app/execution/codex_runner.py:133–139` 在两分支后统一追加模型和 TOML 配置参数；`backend/tests/test_codex_runner.py:64–65,100–114` 检查参数及首次执行成功状态。 |
| 返工续接显式指定相同模型与强度 | 完整实现。`codex_runner.py:135–139` 将参数放在 resume 子命令后；原 session ID 与 stdin 占位符保留。`test_codex_runner.py:123–137` 通过真实提交、执行、返工 API 和再次执行路径，直接在调用结束后断言 resume、session、参数位置和模型/强度。 |
| 不跟随账号默认模型 | 完整实现。`codex_runner.py:138` 显式 CLI 参数为固定常量，调用路径不从账号读取模型。`app/execution/workspace.py:94–96` 原样展开参数数组。 |
| 不改变 Skill 绑定、提示词，不自动重跑历史失败任务 | 匹配。基线差异仅涉及 CLI 参数构建和测试；`codex_runner.py:109,147–149` 材料准备与提示词调用保持不变，`codex_runner.py:71–73` 既有 claim 准入未改，无历史任务遍历或重试入口新增。 |

部分实现、未实现、Spec 漂移：本轮代码范围内未发现。UI/引导文案/视觉对比不适用：代码差异不含页面或样式；不对既有 UI 作通过声明。

CLI 边界：以上独立测试 mock 了 CLI 和 OS 隔离，不代表真实生成效果验收。主 Agent 补充服务器同隔离环境只读查询结果为 `MODEL_HIGH_SUPPORTED True`、`MODEL_CONFIG {model:gpt-6-astra,model_reasoning_effort:high,model_provider:null}`，并报告 CLI 0.153.4 接受 exec/resume 参数。这些为主 Agent 提供的证据，非 reviewer 自行执行的生产查询。部署及真实生成不在本次代码审查结论内。

## Stage 2：Code Quality

- 结构与范围通过：`codex_runner.py:133–139` 仅一个公共模型参数定义，无重复分支常量或新依赖；文件 220 行，测试文件 187 行，均不超过 300 行；本轮无新增 any 或异常处理路径。
- 安全扫描通过（限本轮差异）：新增内容为固定参数；`app/execution/process.py:43–44` 使用 argv 数组启动、无 shell=True。对两个送审文件搜索 eval、innerHTML、公开密钥前缀、API 密钥和 shell=True 无命中。未新增 SQL、凭据或用户输入拼接。
- 测试真实性通过：首次路径最终验证 Job succeeded；返工测试实际走 API 和原 session 续接，并在外层直接断言模型/强度（`test_codex_runner.py:113,128–137`）。独立变异实验仅在内存把 resume 模型改为 `deliberately-wrong-model`，测试在第 136 行按预期失败，证明断言能识别错误。
- 故障路径回归：`test_codex_runner.py:140–186` 的取消、超时、未知、租约过期、损坏 Skill 等既有用例随本次专项回归执行；未宣称覆盖真实服务端模型拒绝响应。

### 审中变化与已解决问题

原候选 `ccf9cd0f702a2b9caae3f62442a86647bce9636c95f863114b60356983963bf2` 存在 MEDIUM 测试盲区：返工的参数断言位于 execute mock 内，被 `run_generation` 的 except Exception 捕获；在内存将返工模型改错后仍 `1 passed`。主 Agent 将直接断言加到测试外层，并把公共模型参数放在 resume 子命令后。期间观察到中间快照 `a54fb098cedc1a4e21ede1a4011b3330a67bcec6bb916992dac9a30995cd6135`，未批准。收到最终候选后重新核查差异、两阶段检查、回归、编译和变异测试；末次 review-status currentId 与最终候选一致。旧结论未复用为新版本批准。

## 独立验证原始输出

在 backend 目录，设置 `CODEX_VERSION=0.153.4` 后执行：

```text
uv run pytest -q tests/test_codex_runner.py tests/test_observed_runner.py tests/test_execution_workspace.py tests/test_revisions.py tests/test_task_prompt.py
....................s..........................................          [100%]
62 passed, 1 skipped, 6 warnings in 7.10s
```

六条警告为 Starlette/httpx、anyio 弃用和四角色权限测试中 NULL primary key 的 SQLAlchemy 警告，不是本次新增。条件跳过不计为通过。

```text
uv run python -m compileall -f app/execution/codex_runner.py tests/test_codex_runner.py
Compiling 'app/execution/codex_runner.py'...
Compiling 'tests/test_codex_runner.py'...
```

编译退出码 0。变异实验原始关键输出（故意注入错误，无磁盘代码改动）：

```text
tests\test_codex_runner.py:136: in test_revision_explicitly_pins_model_and_effort
    assert calls[0][0][calls[0][0].index('--model') + 1] == 'gpt-6-astra'
E   AssertionError: assert 'deliberately-wrong-model' == 'gpt-6-astra'
1 failed, 2 warnings in 1.84s
```

主 Agent 后补服务器解析原始摘要（帮助命令不触发生成）：

```text
codex exec --sandbox workspace-write resume --model gpt-6-astra -c model_reasoning_effort=high --help
返回码 0
RESUME_OPTIONS_OK
```
