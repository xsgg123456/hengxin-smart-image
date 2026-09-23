# 详情图镜头提示词审查

candidateId：`90829f4285c9afb9251bc30a6d49c38db98bf83d0c8a98850314e7d31c52e1ff`。

结论：Stage 1 PASS；Stage 2 PASS。未发现本次增量的 HIGH、MEDIUM 或 LOW 问题。结论仅覆盖仓库实现，不表示生产发布或实际生成图片效果已验收。

范围：根目录 Product-Spec.md:3、DEV-PLAN.md:3、Product-Spec-CHANGELOG.md:3 的详情图条目；项目目录 backend/app/execution/prompts.py、backend/tests/test_task_prompt.py。其余 CLI 升级配置复核既有 docs/CODEX-UPGRADE-20260923-REVIEW.md；以下代码路径相对 hengxin-smart-image/。使用 code-review 技能及 docs/HARNESS-REVIEW.md 协议。

## Stage 1：Spec Compliance

| Spec 条目 | 结论及证据 |
|---|---|
| 两个详情图技能增加指定完整短句 | 完整实现。Product-Spec.md:5 对应 prompts.py:29、:30、:31；仅两个完整名称集合命中，插入位置、文字、逗号与原文一致。test_task_prompt.py:35、:55、:56 检验完整提示行，独立测试通过。 |
| 两主图保留原句 | 完整实现。prompts.py:30 的空字符串分支保留原句；test_task_prompt.py:38、:39、:57 覆盖两个主图名称，确保不含新增短句。 |
| 首次和返工都适用 | 完整实现。prompts.py:27 的模式分支不受 current/session 条件限制，返工标识在 :36 后追加；test_task_prompt.py:42、:49、:52、:58 覆盖两个阶段。实际执行调用位于 codex_runner.py:147，共用该函数。 |
| 多素材保留“这些” | 完整实现。prompts.py:28 保留原素材数量判断；test_task_prompt.py:43、:48、:53 覆盖 1 和 2 个素材。 |
| 其他技能不变，完整名称匹配 | 完整实现。prompts.py:9 从实际 skillPath 提取名称，:30 使用精确集合；test_task_prompt.py:40 覆盖相似前缀但不同的技能名称。materials.py:89、:90 与 workspace.py:21、:24 确认测试路径结构对应生产构造。 |
| 商品/文字模式不变 | 完整实现。prompts.py:27 将新增逻辑限定在 wallpaper，:32、:35 两分支无 diff；test_task_prompt.py:28 至 :32 独立测试通过。 |
| Skill 正文与绑定不变 | 完整实现。review-status 相对上一已批准快照仅列出 prompts.py、test_task_prompt.py；本次无技能文件、绑定或材料构造修改。 |
| UI、引导真实性、设计一致性 | 不适用。本次 prompts.py:29 的服务端模型指令增量无页面或用户引导改动。没有新页面可与邻居页面做视觉对比。 |
| Spec 漂移 | 未发现。代码 diff 仅增加 Product-Spec.md:5 明确要求的短句和相应测试；没有新增 API、表、页面或其他业务行为。 |

部分实现、未实现：无。DEV-PLAN.md:7 的生产切换与服务验证由主 Agent 后续执行，不计入本次仓库实现 PASS。

## Stage 2：Code Quality

- 质量 PASS：prompts.py:29 的 camera_scope 名称对应内容，复用现有拼接与模式分支，未引入重复入口或异常吞噬；文件 41 行，测试文件 82 行。无新增 any 或外部依赖，原函数未标注类型属于既有代码，本次不扩大重构。
- 测试真实性 PASS：test_task_prompt.py:35 至 :58 的 20 个参数组合覆盖 5 个技能名称 × 2 种返工状态 × 2 种素材数，断言完整行、短句有无及返工标识；:10 的清单结构与 materials.py:90 的生产路径一致。其余既有 11 项测试保留。此证据证明提示词组装，不证明图像模型一定遵从指令。
- 安全扫描 PASS（仅增量）：完整审阅 prompts.py:29 至 :31 与 test_task_prompt.py:35 至 :58 的新增行，无密钥、eval、SQL、HTML 注入或命令执行。测试 /work 路径是既有容器输入契约；新增中文短句为常量，不增加输入插值能力。
- 视觉比较不适用：本次只有服务端指令与测试变化，无渲染代码。输出图片效果仍须真实任务单独验收。
- CLI 升级配置复核 PASS：infra/compose.yaml:21、infra/.env.vps.example:19、:20 内容与既有升级报告一致，两个文件归一化 SHA256 分别仍为 `7c8194e5e83d6b0fb64b489bda87cdd23024c75e87b47d06dc713d1a8166f056`、`85b5a2c24ed87524524ce83a7799f933e8f13b8c1a729127557f984936850e29`，未将新提示词变更冒认为旧报告已审。

## 独立验证及原始输出

在 backend 目录执行 `uv run pytest tests/test_task_prompt.py -q`，退出码 0：

```text
...............................                                          [100%]
31 passed in 0.14s
```

执行 `uv run python -m compileall app/execution/prompts.py tests/test_task_prompt.py`，退出码 0：

```text
Compiling 'tests/test_task_prompt.py'...
```

compileall 对已有有效缓存的文件不重复打印；两个路径均包含在命令中。`git diff --check` 退出码 0，仅 Git 行尾提示：

```text
warning: in the working copy of 'hengxin-smart-image/backend/tests/test_task_prompt.py', CRLF will be replaced by LF the next time Git touches it
```

主 Agent 补充回归摘要（未由 reviewer 独立重跑）：六个提示词、材料、返工、执行器、进程、本地技能测试文件合计 52 passed、3 skipped、2 项既有弃用 warning；py_compile 通过。该摘要不替代上述独立证据。

环境限制：最初直接调用 python 不在 PATH；改用 uv 后以上测试、编译和快照核对成功。随后可选的商品/文字模式与所有技能名称交叉探针因 uv 缓存权限失败，改用 .venv Python 又无法创建进程，故未将该探针标为通过。现有商品/文字测试及模式分支静态证据已覆盖本次变更边界。

## 快照一致性

独立执行 `uv run python ../../.codex/hooks/harness.py review-status`，原始输出：

```json
{"currentId": "90829f4285c9afb9251bc30a6d49c38db98bf83d0c8a98850314e7d31c52e1ff", "reviewedId": "5a0ef222b100104f6956df5467b70d039b1ae61a085420db0843731503384538", "changedFiles": ["hengxin-smart-image/backend/app/execution/prompts.py", "hengxin-smart-image/backend/tests/test_task_prompt.py"], "approved": false}
```

审查文件的 CRLF 归一 SHA256 与 candidate.files 一致：prompts.py 为 `1969541b82651cd5558a5dc1955992b9cdad3bd7fbcfd7af1e3154c72e39c21e`；test_task_prompt.py 为 `b618e74811530b148ab45a332076e9971ec0c67c768ff07cbbe86048f125a801`。审查期间未发现受控代码变化。报告是普通 Markdown，不改变代码候选；主 Agent 应登记同一 candidateId 的两阶段 PASS，并于交付前再次核对 review-status。reviewer 未修改实现、未提交、未写 clean。
