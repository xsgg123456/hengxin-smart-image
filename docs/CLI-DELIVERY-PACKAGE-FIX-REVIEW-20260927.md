# CLI 发布包测试样例补齐独立审查（2026-09-27）

- candidateId：`c35e1d7114f32ec02bbfbac1150ba1dd8da1d9d8e0b1f743293d7b2a02596461`。
- 范围：`scripts/release/package-delivery.py`、`scripts/release/test_package_delivery.py` 的增量；同时阅读全文核查两个既有 JSON 样例及其消费测试。使用 code-review skill。
- 基线：已读 `docs/CLI-DELIVERY-RELEASE-REVIEW-20260927.md`，其登记候选为 `04acd36b4ce951ac8bb160b56f576a32ddecd5de92255cc53efc7f7d004a8631`；本报告不把旧结论直接用于新代码。实际 review-status 的 changedFiles 恰为上述两文件。
- 结论：**Stage 1 PASS；Stage 2 PASS**。无 HIGH/MEDIUM 问题。本次仅证明补包修正，未证明新镜像安装测试或生产部署完成。

## Stage 1 · Spec Compliance

| 范围内要求 | 结论与证据 |
|---|---|
| 白名单打包后端及安装验证用例（DEV-PLAN.md:5） | 完整实现。package-delivery.py:14–16 精确增加两条 JSON 路径；:97 将 EXACT 全部列为必需文件。test_image_revision_prompt.py:31–45 在收集时读取这两文件，补齐的是已有测试依赖。 |
| 扫描凭据与个人数据（DEV-PLAN.md:5） | 完整实现。cli_revision_briefs.json:1–22 的4例及 unannotated_revision_briefs.json:1–32 的6例均为固定提示词、通用修改意见和 `/work/*.png` 或图1/图2/图3占位引用；消费测试 test_image_revision_prompt.py:35–36、48–54 明确构造同样假路径。全文未见用户身份、业务记录、凭据或个人目录。两文件独立 JSON 解析和 privacy_check 均通过，无隐私豁免。 |
| 保留发布范围、无运行时产品变化（Product-Spec.md:3–5） | 匹配。git diff 仅两文件5行新增、1行删除；仅扩大精确静态样例集合及测试断言，没有 API、Worker、模型、Skill、数据库、前端或部署流程代码变化。其余发布要求仍由基线实现及主流程后续验收负责。 |
| 闭合选择规则 | 匹配。package-delivery.py:37–47 仍只有精确 EXACT、既定 Python 目录和既定脚本名；未放开 JSON 后缀或整个 fixtures 目录。test_package_delivery.py:18–27 验证指定样例包含与 fixtures/auth.json 排除。 |
| UI、引导真实性、Spec 漂移 | 本增量无页面、文案引导或产品行为新增，不适用设计及邻居页面渲染比对；新增文件选择属于已批准安装验证范围（DEV-PLAN.md:5–6）。 |

部分实现、未实现：本次增量范围内无。镜像构建、镜像内运行时测试和生产切换尚待主流程执行，不能以本报告替代。

## Stage 2 · Code Quality

- 通过：package-delivery.py:14–16 使用既有集合精确扩展，未改控制流；两文件实测152行与96行，均未超过300行。
- 安全通过：package-delivery.py:49–62 的原有扫描仍作用于新增样例；:85–96 的符号链接、提交字节一致性和隐私检查均保留；没有动态执行或新的敏感路径。两份 JSON 的全文和消费者证明它们是合成回归样例。
- 测试真实性通过：test_package_delivery.py:18–27 直接调用真实 selected；:48–88 在临时 Git 仓库运行真实 build 并验证归档、元数据和脏工作树拒绝。独立运行5项均通过；另外直接验证两个实际 JSON 均被选入、可解析且隐私扫描无豁免通过。临时归档测试用占位字节，不将其声称为真实镜像测试。
- 代码语法编译通过：下列原始输出来自 Python compile；没有替代完整 Docker 构建。审查未修改实现、未访问生产、未提交。

## 原始验证输出

`python -m unittest discover -s scripts/release -p test_package_delivery.py -v`：

```text
test_archive_and_guards (test_package_delivery.PackagingTests.test_archive_and_guards) ... warning: unable to access 'C:\Users\82358/.config/git/ignore': Permission denied
warning: unable to access 'C:\Users\82358/.config/git/ignore': Permission denied
warning: unable to access 'C:\Users\82358/.config/git/ignore': Permission denied
warning: unable to access 'C:\Users\82358/.config/git/ignore': Permission denied
ok
test_closed_allowlist (test_package_delivery.PackagingTests.test_closed_allowlist) ... ok
test_fixture_exemptions_are_exact_and_still_scan_other_content (test_package_delivery.PackagingTests.test_fixture_exemptions_are_exact_and_still_scan_other_content) ... ok
test_missing_review_is_rejected (test_package_delivery.PackagingTests.test_missing_review_is_rejected) ... ok
test_privacy_blocks_real_credentials_and_personal_paths (test_package_delivery.PackagingTests.test_privacy_blocks_real_credentials_and_personal_paths) ... ok

----------------------------------------------------------------------
Ran 5 tests in 1.366s

OK
```

独立样例选择、JSON解析、隐私检查及内存语法编译：

```text
FIXTURE_PASS cli_revision_briefs.json 4
FIXTURE_PASS unannotated_revision_briefs.json 6
COMPILE_PASS scripts/release/package-delivery.py lines 152
COMPILE_PASS scripts/release/test_package_delivery.py lines 96
```

送审快照实查：

```json
{"currentId":"c35e1d7114f32ec02bbfbac1150ba1dd8da1d9d8e0b1f743293d7b2a02596461","reviewedId":"04acd36b4ce951ac8bb160b56f576a32ddecd5de92255cc53efc7f7d004a8631","changedFiles":["scripts/release/package-delivery.py","scripts/release/test_package_delivery.py"],"approved":false}
```

主 Agent 应登记此 candidate 的两阶段 PASS；新版本包与镜像必须重新构建并完成安装验证后，才能继续生产发布验收。
