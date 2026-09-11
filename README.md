# hengxin-smart-image

本仓库用于开发恒信 AI 换套图系统，已安装 Agent Harness（Codex 版）。截至 2026-09-10，Phase 1–10 已验收；Phase 11 技术验证与独立两阶段审查通过、待用户验收；Phase 12–14 未开始。阶段进度及后续开发顺序以 [DEV-PLAN.md](DEV-PLAN.md) 为准。

正式前端位于 `hengxin-smart-image/frontend/`，使用 Node.js 24.18.1、pnpm 10.33.4。进入该目录执行 `pnpm install --frozen-lockfile` 后，`pnpm dev` 启动独立内存 mock，刷新重置；`pnpm dev:api` 连接真实后端。预览地址为 [http://127.0.0.1:3008](http://127.0.0.1:3008)。后端已接入开发身份、文件存储、模板与 Skill、任务执行、返工及下载归档；真实 AI 需要专用 Linux Worker。钉钉认证、其余管理接口和生产部署仍属 Phase 12–14，前端预览不代表这些能力或并发容量已通过。

## 文档入口

| 要了解的内容 | 文档 |
|---|---|
| 当前需求和确认边界 | [Product-Spec.md](Product-Spec.md)；历史变更见 [CHANGELOG](Product-Spec-CHANGELOG.md) |
| 当前进度和后续开发顺序 | [DEV-PLAN.md](DEV-PLAN.md) |
| 页面规范与原型用途 | [Design-Brief.md](Design-Brief.md)、[原型说明](prototype/README.md) |
| 前后端接口 | [API-CONTRACT.md](hengxin-smart-image/docs/API-CONTRACT.md)、[管理接口补充](hengxin-smart-image/docs/PHASE4-CONTRACT.md) |
| 后端启动与最新阶段证据 | [后端开发说明](hengxin-smart-image/docs/BACKEND-DEVELOPMENT.md)、[Phase 11 验证记录](hengxin-smart-image/docs/PHASE11-VALIDATION.md) |
| 真实 AI 执行环境 | [Linux Worker 说明](hengxin-smart-image/docs/CODEX-EXECUTION.md)、[Phase 9 实机验证](hengxin-smart-image/docs/PHASE9-VALIDATION.md) |
| 后端架构和隔离调研 | [架构评估](hengxin-smart-image/docs/BACKEND-ARCHITECTURE-ASSESSMENT.md)、[Codex CLI 隔离评估](hengxin-smart-image/docs/CODEX-CLI-ISOLATION-ASSESSMENT.md) |

`PHASE*-PLAN/REVIEW/VALIDATION.md` 保留当时的执行与验收证据，旧版本号不代表当前需求版本。调研文档中的推荐方案不等于已选定实现；实际完成状态以 DEV-PLAN 为准。

## 开始使用

在 Codex 中打开本仓库，先读取需求、计划和最近阶段的验证记录。例如：

> 查看 Phase 11 的验收证据，整理待验收内容和 Phase 12 钉钉双端认证的开发前置条件。

也可在终端从仓库根目录运行 `codex`，通过 `/skills` 查看技能、`/hooks` 查看门禁。旧会话未必重新加载新配置，安装后应开启新会话。

流程：`Product-Spec.md` → 可选 `Design-Brief.md` 与设计稿 → `DEV-PLAN.md` → 项目代码 → 两阶段审查 → 构建发布。需求和规划文档应提交到 Git。

## 安装内容

| 位置 | 用途 |
| --- | --- |
| `AGENTS.md` | 总体研发流程与编排 |
| `.agents/skills/` | 11 个技能及其模板、参考和示例 |
| `.codex/agents/` | code-reviewer、evolution-runner |
| `.codex/config.toml` | 项目级 hooks 与多代理配置，继承用户模型和权限 |
| `.codex/hooks.json` | 5 个 hook 的唯一注册源 |
| `.codex/hooks/harness.py` | Windows / POSIX 共用的 hook 实现 |
| `.codex/hooks/review_*.py` | 审查快照、凭据、暂存区检查与原子状态存储 |
| `docs/HARNESS-REVIEW.md` | 审查、提交和中途暂停的交接协议 |
| `.codex/evolution/` | 本地纠正信号和待审阅建议 |
| `scripts/check_harness.py` | 可重复运行的离线自检 |

来源：用户提供的 `Agent-Harness-Code/codex 版`。原始说明保留在 `.codex/UPSTREAM-INSTALL.md`，全部来源文件及原始 SHA-256 记录在 `.codex/upstream-manifest.json`；源目录未修改。

## 环境与验收

需要 Git、Python 3.11+ 和支持项目 skills/custom agents/hooks 的 Codex。本机安装验证使用 Codex CLI 0.153.4、Python 3.12。Python 只用标准库，无 pip 依赖。Windows 通过 `python` 执行，macOS/Linux 使用 `python3`。

```powershell
python scripts/check_harness.py
```

自检覆盖文件完整性、技能与 TOML/JSON 配置、进化队列、审查门禁、补丁删除、Shell 写入、TypeScript 编译成功/失败以及自动推送保护。此处 Python 标准库和 Node 说明仅针对 Harness 自检；产品技术栈已确定 Vue/TypeScript、Python FastAPI、PostgreSQL 和 MinIO，具体依赖按 DEV-PLAN.md 安装。

初次安装时已通过 Codex 实际加载检查：11 个项目技能启用、2 个角色进入模型上下文、当时的 6 个 hook 被发现并通过本机信任。当前配置取消 Stop 后为 4 类事件、5 个 hook，离线自检已覆盖；当前会话是否已重载仍以运行时状态为准。信任记录属于本机；其他机器克隆后仍需在 `/hooks` 审阅并信任，修改 hook 定义也会要求重新信任。

## 本次兼容修复

- 补齐 `hooks.json` 的顶层 `hooks`，匹配当前 Codex 的 `Bash`、`apply_patch` 等工具事件。
- 用 Python 标准库替代 Bash/jq/lsof 依赖，原 `.sh` 文件保留为 POSIX 兼容入口。
- 审查使用 `review-prepare` 固定候选快照，独立两阶段通过后 `review-approve` 登记同一快照和报告哈希；代码变化检测不会覆盖批准记录。完成交付前用 `review-status` 核对当前内容；旧clean字符串不再授权放行。首次接入以既有HEAD为基线，预先存在的脏改动和未跟踪代码仍需审查。默认不注册 Stop，中途问答或暂停无需 `review-checkpoint`；提交前的审查凭据和类型检查仍保留。协议见 [HARNESS-REVIEW.md](docs/HARNESS-REVIEW.md)。
- 提交前先确认暂存区的受控变化与审查凭据一致，再优先运行项目已安装的vue-tsc或本地TypeScript编译器。支持带引号、空格的git -C目标；要求先单独git add，再另次调用独立git commit，不支持复合脚本、commit -a或路径提交。依赖缺失、未审内容或类型失败均阻止提交，不临时下载编译器。
- 开发服务启动前报告常见端口占用，由 Agent 检查进程或换端口。
- 自动推送默认关闭。需要时执行 `git config --local harness.autoPush true`；仅单条 `git commit` 命令明确成功后推送普通分支，`main/master` 不自动推送。复合命令、包装脚本、`git -C` 调用跳过自动推送；未返回结构化成功状态的客户端会提示手动核查。
- 自进化运行状态不上传 Git，SessionStart 自动补建；最终采纳的规则仍进入版本控制。
- 已有 origin 直接复用，不创建嵌套仓库或另一个远程仓库。

## 使用边界

Hooks 是 Codex 生命周期检查，不是服务端分支保护；外部编辑器、普通终端提交不会直接触发 Codex hook。审查标记用于协作，不能替代 CI 或人工审查。TypeScript 提交检查面向常见 `tsconfig.json` 工程；其他语言或特殊 monorepo 构建流程应在选定技术栈后补齐。

设计稿步骤使用当次环境已连接的设计工具；现有页面继续以已认可原型和 Design-Brief 为准。发布步骤需要对应平台的账号与项目配置，这些在实际产品开发和发布阶段确定。

Codex 格式依据：[Hooks](https://learn.chatgpt.com/docs/hooks)、[Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)。
