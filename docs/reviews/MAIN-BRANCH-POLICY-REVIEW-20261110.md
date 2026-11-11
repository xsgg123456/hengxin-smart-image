# main 开发规则独立审查 · 2026-11-10

candidateId：`c51d3871e99a71cea5ecde6f5bf1ce82eebfecac6e152047e0558493e1d97375`。

**Stage 1：PASS；Stage 2：PASS。** 无 HIGH / MEDIUM / LOW 问题。

## 范围与依据

按 `.agents/skills/code-review/SKILL.md` 审查，仅覆盖 `AGENTS.md:179` 新增的本项目 main 开发规则及相邻保护约束。主 Agent 提供的用户意图：删除除 main 外的本地、远程分支，此后本项目直接在 main 开发。分支实际删除、合并完整性和服务器状态不属于此次审查，未执行 Git 变更、未连接服务器。

这是项目工作约定变更，不涉及产品功能、设计稿或应用运行代码；不扩展为全量产品 Spec 验证。相对已批准快照 `46915ca57b8d4bba90af8cac90f408a654bff857fdd888e5c93dcbb3d5c1b8e6`，`review-status` 实查唯一受控差异为 `AGENTS.md`；`git diff -- AGENTS.md` 仅新增第 179 行。既有迁移代码结论沿用 [上一份报告](INTRANET-245-BOOT-DIRS-REVIEW-20261110.md:3)，不将其测试表述为本次重新执行。工作区另有普通需求、计划和报告 Markdown 改动，不在本次范围。

## Stage 1 · Spec Compliance

| 检查项 | 结论与证据 |
|---|---|
| 完整实现：此后直接 main 开发 | PASS。`AGENTS.md:179` 明确“统一直接在 main 分支开发”，禁止主动创建或切换功能分支；只有用户另行明确要求时可例外，与用户意图相符。 |
| 审查、测试、提交要求保留 | PASS。`AGENTS.md:179` 明确不免除这三项；`:104`、`:105` 保留快照审查和提交凭据要求，`:154` 保留四步验证。 |
| main 自动推送保护 | PASS。`AGENTS.md:180` 原规则未变化，仍明确 main/master 始终不自动推送；新增行没有推送授权。 |
| 部分实现、未实现、Spec 漂移 | 无。`AGENTS.md:179` 只限定本项目工作分支及既有验收义务，没有新增页面、API、数据模型或应用行为。 |
| UI 一致性、引导真实性 | 不适用。唯一增量 `AGENTS.md:179` 是研发规则，不是产品 UI、提示或导航。 |

## Stage 2 · Code Quality

| 检查项 | 结论与证据 |
|---|---|
| 表达与结构 | PASS。`AGENTS.md:179` 放在“本项目安装适配”中，明确默认行为、用户覆盖条件和验收义务；文件共 182 行。无应用类型、错误处理或函数结构变更。 |
| 安全 | PASS。直接检查 `AGENTS.md:179` 全部新增文本，无密钥、执行命令、危险函数、SQL、外部路径或权限放宽；`:180` 的推送保护未受影响。 |
| 测试真实性 | PASS（文档校验范围）。实查差异与快照，不新增镜像文本内容的测试；`:104`、`:105`、`:154` 的验证约束仍存在。未声称运行应用单测或端到端测试。 |
| 视觉对比 | 不适用。`AGENTS.md:179` 未改变任何页面或视觉资产。 |
| 编译结果 | 不适用，未执行编译。此次唯一受控增量为 `AGENTS.md:179` 的自然语言规则，没有可编译产物。 |

## 原始验证输出

`python .codex/hooks/harness.py review-status`，退出码 0：

```json
{"currentId": "c51d3871e99a71cea5ecde6f5bf1ce82eebfecac6e152047e0558493e1d97375", "reviewedId": "46915ca57b8d4bba90af8cac90f408a654bff857fdd888e5c93dcbb3d5c1b8e6", "changedFiles": ["AGENTS.md"], "approved": false}
```

`git diff --check -- AGENTS.md`，退出码 0，原始标准输出和标准错误均为空。

报告仅作为该 candidate 的两阶段审查结论；主 Agent 应使用 `review-approve` 登记同一快照，不写 `.needs-review` 的 clean。若后续受控内容变化，应重新固定快照并复核。
