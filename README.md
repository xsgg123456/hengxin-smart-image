# hengxin-smart-image

本仓库用于开发恒信 AI 换套图系统，已安装 Agent Harness（Codex 版）。截至 2026-09-09，正式前端 Phase 1–4 已验收；后端基础 Phase 5 已完成技术验证和两阶段审查，待用户验收；后端业务 Phase 6–14 尚未开始。开发顺序仍是先完成前端，再逐模块接入后端及联调。

正式前端位于 `hengxin-smart-image/frontend/`，进入该目录执行 `pnpm install --frozen-lockfile`、`pnpm dev`，预览 [http://127.0.0.1:3008](http://127.0.0.1:3008)。当前使用独立内存模拟服务，刷新重置数据。后端已具备 FastAPI、数据库、对象存储、测试队列和 outbox 基础；业务接口目前返回 501，真实上传、图片生成和钉钉鉴权尚未接入。前端预览和基础队列验证不代表真实业务或并发容量已通过。

## 文档入口

| 要了解的内容 | 文档 |
|---|---|
| 当前需求和确认边界 | [Product-Spec.md](Product-Spec.md)；历史变更见 [CHANGELOG](Product-Spec-CHANGELOG.md) |
| 当前进度和后续开发顺序 | [DEV-PLAN.md](DEV-PLAN.md) |
| 页面规范与原型用途 | [Design-Brief.md](Design-Brief.md)、[原型说明](prototype/README.md) |
| 前后端接口 | [API-CONTRACT.md](hengxin-smart-image/docs/API-CONTRACT.md)、[管理接口补充](hengxin-smart-image/docs/PHASE4-CONTRACT.md) |
| 后端启动与基础验证 | [后端开发说明](hengxin-smart-image/docs/BACKEND-DEVELOPMENT.md)、[Phase 5 验证记录](hengxin-smart-image/docs/PHASE5-VALIDATION.md) |
| 后端架构和隔离调研 | [架构评估](hengxin-smart-image/docs/BACKEND-ARCHITECTURE-ASSESSMENT.md)、[Codex CLI 隔离评估](hengxin-smart-image/docs/CODEX-CLI-ISOLATION-ASSESSMENT.md) |

`PHASE*-PLAN/REVIEW/VALIDATION.md` 保留当时的执行与验收证据，旧版本号不代表当前需求版本。调研文档中的推荐方案不等于已选定实现；实际完成状态以 DEV-PLAN 为准。

## 开始使用

在 Codex 中打开本仓库，先读取需求、计划和最近阶段的验证记录。例如：

> 查看 Phase 5 的验收证据，并按 DEV-PLAN.md 整理 Phase 6 用户归属与真实文件存储的开发准备。

也可在终端从仓库根目录运行 `codex`，通过 `/skills` 查看技能、`/hooks` 查看门禁。旧会话未必重新加载新配置，安装后应开启新会话。

流程：`Product-Spec.md` → 可选 `Design-Brief.md` 与设计稿 → `DEV-PLAN.md` → 项目代码 → 两阶段审查 → 构建发布。需求和规划文档应提交到 Git。

## 安装内容

| 位置 | 用途 |
| --- | --- |
| `AGENTS.md` | 总体研发流程与编排 |
| `.agents/skills/` | 11 个技能及其模板、参考和示例 |
| `.codex/agents/` | code-reviewer、evolution-runner |
| `.codex/config.toml` | 项目级 hooks 与多代理配置，继承用户模型和权限 |
| `.codex/hooks.json` | 6 个 hook 的唯一注册源 |
| `.codex/hooks/harness.py` | Windows / POSIX 共用的 hook 实现 |
| `.codex/evolution/` | 本地纠正信号和待审阅建议 |
| `scripts/check_harness.py` | 可重复运行的离线自检 |

来源：用户提供的 `Agent-Harness-Code/codex 版`。原始说明保留在 `.codex/UPSTREAM-INSTALL.md`，全部来源文件及原始 SHA-256 记录在 `.codex/upstream-manifest.json`；源目录未修改。

## 环境与验收

需要 Git、Python 3.11+ 和支持项目 skills/custom agents/hooks 的 Codex。本机安装验证使用 Codex CLI 0.153.4、Python 3.12。Python 只用标准库，无 pip 依赖。Windows 通过 `python` 执行，macOS/Linux 使用 `python3`。

```powershell
python scripts/check_harness.py
```

自检覆盖文件完整性、技能与 TOML/JSON 配置、进化队列、审查门禁、补丁删除、Shell 写入、TypeScript 编译成功/失败以及自动推送保护。此处 Python 标准库和 Node 说明仅针对 Harness 自检；产品技术栈已确定 Vue/TypeScript、Python FastAPI、PostgreSQL 和 MinIO，具体依赖按 DEV-PLAN.md 安装。

本机已通过 Codex 实际加载检查：11 个项目技能启用、2 个角色进入模型上下文、6 个 hook 被发现且配置解析无错误。6 个 hook 已通过 Codex 原生信任界面启用。信任记录属于本机；其他机器克隆后仍需在 `/hooks` 审阅并信任，修改 hook 定义也会要求重新信任。

## 本次兼容修复

- 补齐 `hooks.json` 的顶层 `hooks`，匹配当前 Codex 的 `Bash`、`apply_patch` 等工具事件。
- 用 Python 标准库替代 Bash/jq/lsof 依赖，原 `.sh` 文件保留为 POSIX 兼容入口。
- 从真实补丁路径和 Git 文件内容变动维护审查标记，覆盖普通 Shell 写入、数组命令和子目录。首次启动按 HEAD 与工作区差异建立基线，保留已有未提交修改；Stop 再次检查磁盘，防止写入 `clean` 后的额外修改漏审。空审查状态也会拦截停止。
- 提交前优先运行项目已安装的 vue-tsc，未安装时使用本地 TypeScript 编译器；支持带引号、空格的 `git -C` 路径并检查实际目标仓库。只解析 Git 提交前缀，兼容 PowerShell here-string。依赖缺失或类型检查失败明确阻止提交，不临时下载编译器。
- 开发服务启动前报告常见端口占用，由 Agent 检查进程或换端口。
- 自动推送默认关闭。需要时执行 `git config --local harness.autoPush true`；仅单条 `git commit` 命令明确成功后推送普通分支，`main/master` 不自动推送。复合命令、包装脚本、`git -C` 调用跳过自动推送；未返回结构化成功状态的客户端会提示手动核查。
- 自进化运行状态不上传 Git，SessionStart 自动补建；最终采纳的规则仍进入版本控制。
- 已有 origin 直接复用，不创建嵌套仓库或另一个远程仓库。

## 使用边界

Hooks 是 Codex 生命周期检查，不是服务端分支保护；外部编辑器、普通终端提交不会直接触发 Codex hook。审查标记用于协作，不能替代 CI 或人工审查。TypeScript 提交检查面向常见 `tsconfig.json` 工程；其他语言或特殊 monorepo 构建流程应在选定技术栈后补齐。

设计稿步骤使用当次环境已连接的设计工具；现有页面继续以已认可原型和 Design-Brief 为准。发布步骤需要对应平台的账号与项目配置，这些在实际产品开发和发布阶段确定。

Codex 格式依据：[Hooks](https://learn.chatgpt.com/docs/hooks)、[Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)。
