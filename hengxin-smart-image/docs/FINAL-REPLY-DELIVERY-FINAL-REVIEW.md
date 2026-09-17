# 最终回复收图第二次独立审查 · 2026-09-17

- candidateId：`da161b3df27bd6905fcb356c5df5dca38f68c7a2a5b2abf8e298ddedd85773ce`。
- 范围：相对已批准 `0bb045467430d622862ddc3483a30b47df7324d1143f5e6bdbf905ac5c2691d1` 的 14 个后端代码/测试文件（runner、diagnostics、final_delivery、prompts、workspace、reconcile 和对应测试）；同时核对工作树既有 Astra/high 参数。需求依据 `Product-Spec.md:477`、`:479` 和 `DEV-PLAN.md:3`。不重新验收历史全产品功能。
- 审查前及完成下面复现后，`review-status` 的 currentId 均为上述候选。主线收到问题后将继续修复；本报告只对上述候选有效，不覆盖后续版本。
- **Stage 1：FAIL。Stage 2：未执行。** 有 HIGH 结果错配，不能登记两阶段 PASS。
- 使用 `.agents/skills/code-review/SKILL.md` 与 `docs/HARNESS-REVIEW.md`；只写本报告，未改生产代码、测试或审查凭据，未提交、部署或调用生图。

## Stage 1：HIGH · FR-03 清晰编号标题带说明时仍静默错槽

需求原文 `Product-Spec.md:479`：“按清晰编号或展示顺序对应本轮底图；只接收完整数量，不猜测缺失槽位”。

`backend/app/execution/final_delivery.py:21` 的 `_HEADING` 仅允许纯编号标题，`:133` 用 fullmatch 筛选上一行；带自然说明的明确编号标题被丢弃。`:135` 无法取得编号，`:206` 后全部为 None，跳过编号排序，直接按展示顺序返回。因此以下明确标注图号的回复会成功交付错误槽位：

```markdown
### 主图 4（已修复）
![成品](/work/final_4.png)
### 主图 2（已修复）
![成品](/work/final_2.png)
### 主图 3（已修复）
![成品](/work/final_3.png)
### 主图 1（已修复）
![成品](/work/final_1.png)
```

独立实验创建四张不同颜色有效 PNG，写入当前调用 thread.started、最终 agent_message、turn.completed，通过生产收集器读取，实际返回 4、2、3、1。`backend/app/modules/tasks/results.py:15` 按槽升序取结果，`:20` zip 发布，因此图 4 被存入第一槽，图 1 被存入第四槽。`![4](...)` 以及 `4、[下载成品](...)` 这两类直接数字编号也复现相同结果；`final_delivery.py:20` 没有相应编号识别。

进一步进行了内存输入变体验证：复用 `tests/test_final_delivery_roundtrip.py:70` 的真实 HTTP 接纳、runner、测试存储、下载测试，仅在 CLI mock 完成后将最终回复改为上述带说明标题和 4、2、3、1 展示顺序。未改文件与业务代码。任务状态“待查看”断言通过，随后 `:74` 下载字节与正确槽位断言失败，证明问题不仅存在于纯解析函数，还会实际发布错图。

建议：提取当前图片所属的明确编号上下文，支持标签纯数字、直接数字列表、带说明的相邻编号标题；冲突或无法解释的明确编号应失败，不能退回展示顺序。补充乱序标题与真正发布槽位的回归。

## Stage 1：逐条核对

下列路径以 `hengxin-smart-image/` 为前缀。独立专项回归 98 项通过、1 项条件跳过；功能通过证据不覆盖 FR-03。

| 当前需求 | 结论及证据 |
|---|---|
| 两个业务 Skill 原样；名称调用和简洁 prompt | 完整实现。git diff 无业务 Skill 文件变化；`backend/app/execution/prompts.py:9` 使用 `$名称`，`:10` 至 `:34` 仅列目录、底图、素材、模式要求和引用意见，无后台 manifest、内部任务清单和原生哈希要求。`tests/test_task_prompt.py:16`、`:29` 通过。 |
| 完整冻结 Skill 两处只读、任务私有发现目录 | 代码完整。`backend/app/execution/materials.py:64` 校验冻结版本，`:75` 校验本地内容；`backend/app/execution/workspace.py:92` 至 `:103` 对本地/旧 ZIP Skill 进行两处 ro-bind，遮盖历史 HOME 发现目录。`tests/test_local_skills_linux.py:61` 包含实际双路径只读与邻居隔离断言。真实 Linux 69 项为主线提供证据，本 reviewer 未重跑 Linux，不声称独立实测。 |
| 壁纸固定文案；商品/文字使用各自要求；全部输入可见 | 完整实现。`backend/app/execution/prompts.py:11` 至 `:27`；`tests/test_task_prompt.py:16`、`:29`、`:45` 通过。 |
| 返工保留当前图、原图、修改意见并引用 | 完整实现。`backend/app/execution/prompts.py:17` 至 `:34`；`tests/test_task_prompt.py:35` 验证本轮单图编号、原图/当前图、JSON 引用意见；`tests/test_final_delivery_roundtrip.py:70` 验证单张与整套返工。 |
| 只读本次调用完成前最终 assistant 答复 | 完整实现。`backend/app/execution/final_delivery.py:37` 至 `:69` 校验事件、session、最后完成项及 turn.completed；`:72` 排除代码文本。`tests/test_final_delivery.py:53`、`:67`、`:115`、`:228` 通过。 |
| 不收候选、较早消息、旧轮答复，允许修复成品 | 完整实现。`backend/app/execution/codex_runner.py:167` 使用最终回复收集器，无 provenance 哈希要求；`final_delivery.py:200` 仅读明确引用，不扫描候选。`tests/test_final_delivery.py:44`、`:53`、`:86` 及真实归档回放通过。 |
| 明确编号优先，否则展示顺序；完整数量 | **部分实现，FR-03 HIGH。** `final_delivery.py:203` 检查唯一引用数量，`:206` 检查/排序已识别编号，但带说明编号标题、直接数字标签及数字列表仍可能错槽。 |
| 上轮 FR-01：括号编号、第 N 张、中文编号 | 指定问题已修复。`final_delivery.py:19` 至 `:33`、`:135`；`tests/test_final_delivery.py:159`、`:167` 通过。独立原复现输出变为 1、2、3、4。不能据此认定所有清晰编号已正确处理，FR-03 仍在。 |
| 上轮 FR-02：同图预览/下载合并，跨编号同文件拒绝 | 指定问题已修复。`final_delivery.py:142` 规范化 work 相对/绝对路径并保留编号、检测冲突；`tests/test_final_delivery.py:174`、`:183` 通过。独立四张预览+下载乱序复现返回 1、2、3、4。 |
| 本轮 work 排除输入/当前图/Skill；原生仅本会话新增 | 完整实现。`final_delivery.py:158` 至 `:190`，原生历史 baseline 按路径拒绝；`codex_runner.py:116` 启动前快照。`tests/test_final_delivery.py:98`、`:133` 通过。 |
| 越界、链接、重复文件、格式/解码/大小限制 | 功能检查完整。`final_delivery.py:159`、`:182`、`:186`、`:216`、`:221`、`:227`；复用 `output_collector.py:21` 和 `diagnostics.py:79` 受控读、`modules/files/validation.py:35` 解码安全限制。损坏、目录、越界、重复路径/编号及硬链接测试通过；本机符号链接测试条件跳过，不视为通过。此处是 Spec 安全功能核对，非 Stage 2 安全扫描。 |
| 缺失/不完整/无效明确失败，不声称视觉合格 | 完整实现。`backend/app/execution/diagnostics.py:14` 提供交付缺失/不完整错误；runner `:186` 处理失败。`tests/test_execution_reconcile.py:232` 验证恢复缺图明确失败。没有新增视觉合格承诺。 |
| 取消、失去认领权不得发布；隔离和单/整套返工 | 完整实现。runner `:161` 停止检查、`:181` 原子发布；`modules/tasks/results.py:13` 核验认领有效性。`tests/test_codex_runner.py:156` 与 `tests/test_final_delivery_roundtrip.py:70` 通过。后者默认输入下通过，FR-03 输入变体失败。 |
| 新执行/返工统一协议；旧恢复兼容、未知协议不降级 | 完整实现。runner `:119` 写 final-reply-v1；`backend/app/worker/reconcile.py:134` 至 `:150` 分流新 collector 与旧 manifest/provenance，`:158` 收图失败结束。`tests/test_execution_reconcile.py:223`、`:232`、`:240` 及旧恢复专项通过。 |
| 新任务和 resume 固定 Astra/high | 完整实现。`codex_runner.py:132` 至 `:137` 公共参数固定；`tests/test_codex_runner.py:113`、`:136` 通过。未重新查询生产模型或调用生图。 |
| UI 一致性、引导真实性、Spec 漂移 | 本候选无前端页面、组件、路由、表或 API 新增，无需新 UI 与邻居页面视觉对比；只新增后端内部交付 marker 和错误文案，符合 `Product-Spec.md:479`。不对既有 UI 作新验收声明。 |

## 独立验证原始输出

运行目录 `hengxin-smart-image/backend`，使用现有 `.venv/Scripts/python`，不安装或修改依赖。

生产 collector 复现输出：

```text
parenthesized ['final_1.png', 'final_2.png', 'final_3.png', 'final_4.png']
ordinal ['final_1.png', 'final_2.png', 'final_3.png', 'final_4.png']
preview_download ['final_1.png', 'final_2.png', 'final_3.png', 'final_4.png']
numeric_alt ['final_4.png', 'final_2.png', 'final_3.png', 'final_1.png']
explicit_number ['final_4.png', 'final_2.png', 'final_3.png', 'final_1.png']
heading_with_description ['final_4.png', 'final_2.png', 'final_3.png', 'final_1.png']
```

命令 `.venv/Scripts/python -m pytest tests/test_final_delivery.py tests/test_final_delivery_roundtrip.py tests/test_execution_reconcile.py tests/test_task_prompt.py tests/test_codex_runner.py -q`：

```text
.....................................................s.................. [ 72%]
...........................                                              [100%]
98 passed, 1 skipped, 2 warnings in 7.78s
```

命令 `.venv/Scripts/python -m compileall -q app tests`：stdout/stderr 为空，退出码 0。

命令 `.venv/Scripts/python -m pytest ../../output/diagnostics/exact-prompt/test_replay_delivery.py -q`：

```text
.                                                                        [100%]
1 passed, 2 warnings in 2.21s
```

回放使用已归档真实 events 与四张 PNG，覆盖本机 HTTP 接纳到下载字节一致，不等于线上网页生成已修复。主线全量后端、Linux、前端验证见 `docs/FINAL-REPLY-DELIVERY-VALIDATION.md:11`，本 reviewer 未重跑该三套全量，不把提供方证据当独立执行。

仅变更 CLI mock 最终文本的内存端到端实验关键原始输出（退出码 1；未改测试文件）：

```text
F                                                                        [100%]
__________ test_four_repaired_outputs_and_single_then_full_revision ___________
tests\test_final_delivery_roundtrip.py:74: in test_four_repaired_outputs_and_single_then_full_revision
    assert images(real_env, created) == first
E   AssertionError: assert [b'\x89PNG\r\...ND\xaeB`\x82'] == [b'\x89PNG\r\...ND\xaeB`\x82']
FAILED tests/test_final_delivery_roundtrip.py::test_four_repaired_outputs_and_single_then_full_revision
1 failed, 2 warnings in 2.04s
```

两条 warning 均为已有 Starlette/httpx 与 anyio BlockingPortal 弃用提示。

## Stage 2

**未执行**：Stage 1 存在 HIGH，按 skill 停止；不出具代码质量、安全扫描或两阶段 PASS。主 Agent 修复后重新 review-prepare，从 Stage 1 审查新候选，不得将本报告用作新版本批准依据。
