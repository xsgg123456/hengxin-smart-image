# 打包中文路径增量独立审查

日期：2026-09-23。使用 code-review 技能。Stage 1 **PASS**；Stage 2 **PASS**。无 HIGH / MEDIUM 问题。

candidateId：`bd3fadbae87721b28465382208bae51756836b2843361d1a7ac27ca3e01044f4`。

范围：基于提交 `ff7eaaf`，仅 `scripts/release/package-image-inputs.py:20`、`:26`、`:27` 的路径解析修复。已读 `Product-Spec.md:3` 的发布授权及 `docs/IMAGE-INPUTS-RELEASE-REVIEW-20260923.md:3` 的既有两阶段通过报告；业务、前端和部署流程不重新验收。不运行打包入口、不操作生产、不修改实现、不提交。

## Stage 1：需求符合性 — PASS

| 检查项 | 结论及证据 |
|---|---|
| 修复必要性 | 完整实现。旧 `git ls-files` 输出在本仓库有 1 条路径不能通过 `Path.relative_to`；改为 NUL 分隔 UTF-8 解码后，1017 条真实受跟踪路径全部通过。位置：`scripts/release/package-image-inputs.py:20`、`:28`。独立运行原、新解析验证，未执行复制。 |
| 尾部空项 | 完整实现。真实 Git 输出末项为空；`:26`、`:27` 在路径转换前跳过，避免尾部空路径错误。 |
| 白名单与授权范围 | 匹配。`:22` 至 `:24` 的精确白名单、`:29` 的源码/迁移前缀及 `:31` 至 `:35` 的产物和发布脚本范围原样保留；独立断言当前文件严格等于 HEAD 文件仅替换上述三行后的内容。 |
| 部分实现、未实现、Spec 漂移 | 本增量无。独立精确差异断言证明无业务变更；对应 `Product-Spec.md:5` 的既有发布范围。 |
| UI 与引导 | 不适用。唯一变化为打包路径解析（`:20`、`:26`），未修改页面、提示或设计。 |

## Stage 2：代码质量、安全及验证 — PASS

- `scripts/release/package-image-inputs.py:20` 使用参数数组调用 Git，无 shell 拼接；UTF-8 与 NUL 解析保留中文及换行文件名。`:26` 的空项判断明确。文件共 67 行，语法编译成功。
- `scripts/release/package-image-inputs.py:15` 的批准快照门槛、`:39` 至 `:44` 的符号链接、敏感文件及内容检查、`:49` 的哈希记录均未变化。精确差异断言证明本增量未添加凭据、危险执行或放宽安全检查；结论限定本次增量，不声称全仓库零漏洞。
- 测试直接采用本仓库真实 Git 输出，复现旧解析失败并验证全部路径通过；没有以模拟路径替代故障前提。未执行完整打包/上线，不以此报告声称生产发布成功。
- 无 UI 变更，视觉对比不适用；既有页面验收见前述发布审查报告。

独立执行原始输出：

```text
PYTHON_COMPILE_PASS
EXACT_DIFF_PASS: only NUL UTF-8 parsing and empty-entry skip changed
PATH_PARSE_PASS: 1017 paths; old parser failures=1
EMPTY_TERMINATOR_SKIP_PASS: True
{"currentId": "bd3fadbae87721b28465382208bae51756836b2843361d1a7ac27ca3e01044f4", "reviewedId": "fae9bcd2ee24175304d2981f25e535a9746ff6440abda36c99ff89ba80545357", "changedFiles": ["scripts/release/package-image-inputs.py"], "approved": false}
```

审查完成时 currentId 与交接 candidateId 一致，未发现审查中代码变化。`approved: false` 是本候选尚未登记批准；主 Agent 应使用 review-approve 将本报告两阶段 PASS 绑定同一 candidateId，不写 clean。两个既有未跟踪 PERFORMANCE 文档不在范围。
