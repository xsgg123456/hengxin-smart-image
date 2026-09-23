# 公共运行路径扫描例外独立审查

日期：2026-09-23。使用 code-review skill。candidateId：`3131a577db04fc1d69e529044dbef6c8f9e98b4de412f54f8b82fd23d568cf9a`。

范围：仅 `git diff HEAD -- scripts/release/package-image-inputs.py` 的五行增量（44–48行）。已读取 Product-Spec.md、发布计划及既有 RELEASE-REVIEW、PACK-PATH-REVIEW 报告；本轮不重复验收已审业务、UI或部署编排。未操作生产、执行完整打包、修改实现或提交。

## Stage 1：需求符合性 — PASS

| 验收项 | 结论与证据 |
|---|---|
| 最新代码发布及隐私扫描 | 完整实现。`Product-Spec.md:5`、`hengxin-smart-image/docs/IMAGE-INPUTS-RELEASE-20260923.md:7` 要求发布既有实现并排除凭据。`scripts/release/package-image-inputs.py:45` 与 `:47` 仅对两个精确相对路径处理指定表达式；真实源码旧扫描命中、新扫描通过。原文位置为 `hengxin-smart-image/backend/app/execution/final_delivery.py:189` 和 `hengxin-smart-image/backend/app/execution/workspace.py:69`。 |
| 例外边界 | 完整实现。`:46`、`:48` 使用完整字面表达式替换，非整文件免检。独立执行实际 AST 节点，验证交叉文件、其他文件、改用户名、改目录和改环境变量均拒绝；两项精确表达式通过。 |
| 其余隐私检查保留 | 完整实现。`:49` 原正则未修改；允许表达式后附 Windows、macOS、Linux 个人目录、两种密钥前缀及私钥头仍阻断，22项拒绝 fixture 全通过。 |
| 打包内容保持 | 完整实现。`:43`–`:49` 只改扫描用变量，`:51` 仍复制 source 原文件，`:53` 仅保留原有 CRLF→LF 归一。AST 确认复制参数，精确差异断言确认其余内容等于 HEAD。 |
| 部分实现、未实现、Spec 漂移 | 本增量未发现。仅修正发布扫描误报，没有新增业务功能；证据 `:44`–`:48` 及精确差异断言。 |
| UI、引导及设计稿 | 不适用。改动仅打包扫描逻辑 `:44`–`:48`；没有页面、组件或文案变更。 |

## Stage 2：代码质量、安全与验证 — PASS

- 文件72行，五行增量命名和意图明确，AST解析与编译通过；证据 `scripts/release/package-image-inputs.py:44`–`:48`。无新增依赖、动态执行、shell拼接或凭据。
- 安全检查未整体跳过文件，例外后仍运行同一正则（`:49`）。fixture 使用从实际代码提取的 AST 条件及断言，覆盖真实两个旧误报和22个拒绝案例，不复制一份扫描实现冒充验证。
- 结论限本增量保留现有检测能力，不代表正则能识别所有凭据格式。`:15` 批准快照门槛、`:39`–`:41` 文件限制、`:51` 复制及后续哈希流程未变，精确差异检查通过。
- 无 UI 变化，邻居页面视觉比较不适用；既有视觉与构建证据继承 `docs/IMAGE-INPUTS-RELEASE-REVIEW-20260923.md:22`、`:30`。此次没有运行前端构建或上线验收，不能据本报告宣称部署成功。

独立执行原始输出（Python AST及内存编译，无生成代码改动）：

```text
AST_COMPILE_PASS: 72 lines
EXACT_DIFF_PASS: only five runtime scan exception lines added
SCAN_FIXTURE_PASS: 2 exact allowances; 22 path/secret/near-match rejections
REAL_SOURCE_SCAN_PASS: both old failures now pass
COPY_SOURCE_PASS: scan-only content replacement; original source copied, existing LF normalization retained
{"currentId": "3131a577db04fc1d69e529044dbef6c8f9e98b4de412f54f8b82fd23d568cf9a", "reviewedId": "bd3fadbae87721b28465382208bae51756836b2843361d1a7ac27ca3e01044f4", "changedFiles": ["scripts/release/package-image-inputs.py"], "approved": false}
```

两阶段均 PASS，无 HIGH / MEDIUM 问题。审查完成时 currentId 与交接编号一致，未发现代码变化。主 Agent 应以同一 candidateId 和本报告登记 review-approve；不写 clean。approved=false 表示本轮尚未登记批准。两个既有未跟踪 PERFORMANCE 文档不在审查范围。
