# Codex 生产升级配置审查

候选：`5a0ef222b100104f6956df5467b70d039b1ae61a085420db0843731503384538`。

范围：根目录 Product-Spec.md、Product-Spec-CHANGELOG.md、DEV-PLAN.md；项目子目录 docs/CODEX-UPGRADE-20260923.md、docs/CODEX-EXECUTION.md、infra/.env.vps.example、infra/compose.yaml。下列项目代码路径均相对 `hengxin-smart-image/`。仅审查本次维护增量，不宣称重新验收整个产品。

结论：Stage 1 PASS；Stage 2 PASS。仅批准所列仓库配置与文档；生产切换、运行中 Worker 的最终验收尚未完成，不属于本报告的通过声明。未发现 HIGH、MEDIUM 或 LOW 代码问题。

## Stage 1：Spec Compliance

| 条目 | 结论与证据 |
|---|---|
| 生产统一目标版本 | 完整实现配置：Product-Spec.md:328、Product-Spec-CHANGELOG.md:3 要求 0.156.1；infra/.env.vps.example:19、:20 显式设置版本及对应绝对路径。独立 Compose 渲染两值一致。 |
| 版本传入应用并保留强校验 | 完整实现：infra/compose.yaml:21 透传 CODEX_VERSION；backend/app/core/config.py:9、:20 接收配置；backend/app/execution/codex_runner.py:78 严格比较 CLI 实际版本，backend/app/worker/health.py:33 比较就绪版本。未绕过校验。 |
| 本地旧环境兼容 | 完整实现：infra/compose.yaml:21 默认 0.153.4，backend/app/core/config.py:20 同值；infra/compose.local-codex.yaml:8、:14 保留旧路径。独立叠加本地 Compose 渲染仍为 0.153.4。docs/CODEX-EXECUTION.md:7 明确区分生产目标与历史本地部署。 |
| 保留认证、任务隔离、历史会话 | 仓库实现保留：backend/app/execution/workspace.py:38、:50 设置目录及认证权限；:65 启用隔离，:102 绑定配置二进制；codex_runner.py:134 使用原会话 ID resume。相关代码无本次 diff。生产新版能力仅有主 Agent 提供的实测记录，未由 reviewer 登录验证。 |
| 包校验、固定安装、回退、空闲切换 | 运维计划完整：DEV-PLAN.md:461；docs/CODEX-UPGRADE-20260923.md:11 至 :14 规定安装校验、隔离验证、空闲切换与运行复核。该文件:28 起记载切换前证据，:37 明示最终切换待补充；不能据静态配置宣称已上线。 |
| UI、引导、设计一致性 | 不适用：本次 diff 仅文档、部署模板，无页面、组件、提示或交互改动；无需页面视觉比较。 |
| Spec 漂移 | 未发现：上述七文件全部服务于 DEP-001 生产升级和本地兼容，没有新增 API、表、页面或业务功能。 |

完整实现：生产与本地配置分离、版本透传、文档同步。部分实现/未实现的仓库条目：无。生产最终切换属于待执行运维验收，不计作已验证能力。

## Stage 2：Code Quality

- 质量通过：infra/compose.yaml:21 采用现有环境插值形式，变量名与 Settings 对应；该运行配置 129 行，无新函数、类型、重复逻辑或异常处理分支。文档长度规则不作为既有产品文档重构要求。
- 安全扫描通过（仅本次增量）：infra/.env.vps.example:19、:20 与 infra/compose.yaml:21 仅版本/路径/环境变量；无新增凭证、eval、SQL、HTML 注入或前端密钥。绝对路径是明确要求的固定运行时目录，未发现用户输入拼接命令。服务器权限/AppArmor 的正确应用需运行证据，不能由模板推断。
- 测试真实性：backend/tests/test_codex_runner.py:37 固定模拟旧版本，:43 模拟沙箱命令，:44 模拟 CLI 版本，因此这组单测证明编排回归，不能证明新版二进制可执行。主 Agent 另提供 Linux 真实沙箱的新会话、旧会话续接与工具写读证据；本报告未独立执行这些远端操作。
- 视觉比较不适用：infra/compose.yaml:21 是唯一 YAML 行增量，无 UI 渲染变更。

## 验证与原始输出

本次没有需要重新编译的应用源代码修改。独立执行 Compose 配置解析，清除当前验证进程继承的 CODEX_VERSION 后退出码均为 0；以下保留筛选后的原始输出（重复服务行省略）：

```text
docker compose --env-file .env.vps.example -f compose.yaml config
WARNING: Error loading config file: open C:\Users\82358\.docker\config.json: Access is denied.
WARNING: Error loading config file: open C:\Users\82358\.docker\config.json: Access is denied.
      CODEX_BINARY: /opt/hengxin-runtime/codex-0.156.1/codex
      CODEX_VERSION: 0.156.1

docker compose --env-file .env.example -f compose.yaml -f compose.local-codex.yaml config
WARNING: Error loading config file: open C:\Users\82358\.docker\config.json: Access is denied.
WARNING: Error loading config file: open C:\Users\82358\.docker\config.json: Access is denied.
      CODEX_BINARY: /opt/hengxin-runtime/codex-0.153.4/codex
      CODEX_VERSION: 0.153.4
```

`git diff --check` 无输出。一次尝试使用不存在的 `.env.local.example` 失败，改用实际 `.env.example` 后完成以上本地验证；这不是应用缺陷。当前 shell 的 `python` 命令不存在，因此未声称独立执行 Python 测试或 harness 命令。

主 Agent 转交的测试末行（非 reviewer 独立执行）：

```text
57 passed, 1 skipped, 2 warnings in 10.86s
```

主 Agent 说明两项为既有 Starlette/httpx、anyio 弃用警告；Linux 三次调用均 RC=0、turn_completed=true、error=null，旧会话跨版本续接工具写读 `probe.txt=HX_UPGRADE_1561`。这些是转交证据，未取得完整原始远端输出，不扩大其证明范围。

## 快照与审查期间变化

审查期间 docs/CODEX-UPGRADE-20260923.md 从待验证更新为切换前验证记录，已重新读取并纳入本次结论；仍保留生产切换待完成说明。两个受控配置文件的 CRLF 归一 SHA256 与 candidate.files 完全匹配：

```text
infra/compose.yaml 7c8194e5e83d6b0fb64b489bda87cdd23024c75e87b47d06dc713d1a8166f056
infra/.env.vps.example 85b5a2c24ed87524524ce83a7799f933e8f13b8c1a729127557f984936850e29
```

主 Agent 应使用 review-approve 登记此候选及两阶段 PASS，并用 review-status 检查全仓快照；生产后续文档证据应复核，受控代码/config 再变更须重新送审。本 reviewer 未修改实现、未提交、未写 clean、未访问服务器或凭证。
