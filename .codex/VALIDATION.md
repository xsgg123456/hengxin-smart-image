# Harness 运行验收

验收环境：Windows，Codex CLI 0.153.4，Python 3.12，Git 2.55.0。验收日期：2026-09-08。

## 验收范围

此次验收覆盖框架安装、配置加载、工具入口、质量门禁和克隆恢复。项目尚无业务 Product-Spec、应用代码及部署环境，因此不将业务开发至生产发布的全流程标记为已验证。

## 已完成的实际检查

- Codex app-server `skills/list`：11 个项目技能启用，无技能加载错误。
- `hooks/list`：6 个项目 hook 均为 trusted，配置无错误或警告。
- Codex 生成的模型输入包含 code-reviewer、evolution-runner 和项目规则。
- 真实 `codex exec` 会话执行 `git status --short`，命令退出码 0，并返回 `HARNESS_RUNTIME_OK`。
- 从 GitHub 克隆到中文、空格目录，从仓库外运行自检：通过；本地进化状态自动创建，工作区仍干净。
- 回归测试覆盖普通/数组命令、真实 Windows 注册入口、子目录、首次干净仓库、已有未提交修改/删除/新增、clean 后新增修改、编译成功/失败、带空格的目标仓库、PowerShell here-string、自动推送默认关闭/保护分支/复合命令/dry-run 等。
- 本轮完整自检结果：`Ran 23 tests ... OK`。

运行完整自检：

```powershell
python scripts/check_harness.py
```

## 本轮复查修复

1. 首次克隆的只读操作不再误标记所有已有代码为待审查；已有 dirty 内容仍要求审查。
2. 数组形式的命令输入不再导致补丁路径解析异常。
3. Stop 对磁盘再次取快照，clean 之后的未观察修改不能直接放行。
4. 带引号或空格的 `git -C` 使用实际目标仓库进行编译检查。
5. Git 前缀解析不再将普通 PowerShell here-string 误当作无法解析的命令。

## 必须保留的边界

- Hooks 是本机 Codex 的协作检查，不是服务端保护，不能保证任意 shell 包装、别名或外部提交都被拦截。中文提交要求已写入 AGENTS.md 和开发技能，由 Agent 遵循，目前没有 Git commit-msg 强制校验。
- 新机器或改动 hook 定义后，需要该机器在 Codex `/hooks` 中重新信任；信任不会随仓库传播。
- 当前编译门禁面向常规 TypeScript 项目。确定真实技术栈后，需要增加该项目的测试、构建与 CI 命令。
- macOS/Linux 保留兼容入口，但本轮没有这些系统的实机验收。
- 设计、部署、自进化建议采纳仍依赖实际输入、外部工具账号或用户决定；不能通过安装检查证明未来每次模型执行都正确。

结论以复现、测试和真实运行结果为依据，不承诺软件永远零缺陷。发现新故障时应补回归用例后修复。
