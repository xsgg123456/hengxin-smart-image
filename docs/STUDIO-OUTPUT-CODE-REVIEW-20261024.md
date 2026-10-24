# 工作台开放输出独立代码审查（2026-10-24）

## 结论与范围

- **Stage 1：FAIL，存在 1 项 HIGH。Stage 2：未执行完整审查，不得登记 PASS。**
- 接收的 candidateId：`43f307c317e106afe5d749e75e85f12ff87a3d21b6113f1fa054b2d74a8a2a5c`。
- 范围：`git diff HEAD` 与新增文件中的本轮合同、后端输出/取回/状态/清理/迁移及测试、前端组件/API及测试、发布脚本。根 `AGENTS.md` 为用户预先修改，读取但不批准其改动，也不属于本轮建议提交范围。
- 依据：全文读取 `docs/STUDIO-OUTPUT-IMPLEMENTATION-20261024.md`；核对 Product-Spec、DEV-PLAN 最新覆盖条款及 Design-Brief 的既有工作台样式要求；使用 `.agents/skills/code-review/SKILL.md` 和 `docs/HARNESS-REVIEW.md`。
- 快照变化：审查启动的 Vite 3034 自动重写 `frontend/src/types/import/components.d.ts`（删去未加载的 Element 声明，候选原文件与 HEAD 相同），已通知主 Agent 恢复；本次 Vite PID 53464 已停止。随后 `review-status` 当前编号为 `cabb1231842b23cc0206d3a483070127f6ec3f31e44f18973695ec6ea57fbeed`，不能用原候选批准新内容。发布清单的后续 transport 增补尚未作为本报告的已审 delta。
- 本报告不含任何生产部署完成声明；没有向生产执行写操作，没有改生产代码、提交或写 `.needs-review`。

下文 `B/` 为 `hengxin-smart-image/backend/`，`F/` 为 `hengxin-smart-image/frontend/`；行号均为审查时源文件行号。

## HIGH：同轮同版本先取工作文件再取副本产生重复结果

**合同原文**（实施合同第 16 行）：“重复取同一版本返回已有结果”。用户效果表第 27 行：“同一次收取不生成重复结果”。

**实际差异**：`B/app/overseas/studio/recovery_files.py:63-69` 仅对非 snapshot 执行 `existing()`；工作文件使用 `uuid5(turnId, target + checksum)`，副本固定使用 manifest 的 `pictureId`。当同一轮、同一路径、同一字节同时存在于工作目录和本轮副本时，先取工作文件、再取副本会插入两个不同 ID，重复展示并重复存储同一版本。图片和普通文件共用此分支。

可达前提：自动阶段已成功捕获副本，但对象保存失败；设计师从列表先选择“工作文件”，随后又选同文件“本轮副本”。列表确实同时枚举两者（`B/app/overseas/studio/recovery_listing.py:123-132`），用户无需修改任何内部数据即可触发。

**独立复现**：`output/test_review_dedupe_probe.py:8`，复用普通设计师 HTTP fixture、真实文件系统、真实 SQL 会话，仅对象存储为测试替身。写入 `design.zip`、建立同轮同字节快照，调用列举 API，然后按 work → snapshot 分两次调用取回 API。

原始失败输出（随机 ID 均为隔离测试数据）：

```text
>       assert first['saved'] == second['saved'], (first, second)
E       AssertionError: ({'saved': [{'id': '320c58d5-7e5a-573a-af11-e14cdcb65ff7', 'kind': 'file'}], 'errors': []}, {'saved': [{'id': '9e23b9c8-b3fc-5f01-ada3-c2d7922030fe', 'kind': 'file'}], 'errors': []})
FAILED ../../output/test_review_dedupe_probe.py::test_work_then_snapshot_same_version_does_not_duplicate
1 failed, 2 warnings in 3.08s
```

修复方向：同一轮工作原件与其冻结副本应解析到同一个稳定结果；既要修复 work → snapshot，也要保留 snapshot → work 的幂等性、同路径新版和后续正式轮次独立交付。不能简单跨轮吞掉所有同 checksum 副本。需要补一条真正走 HTTP/保存路径的顺序回归。

## Stage 1：逐条合同对照

“匹配”表示列出的实现与证据满足该子项，不代表整体通过。

| 合同条目 | 判断 | 文件/行号与验证证据 |
| --- | --- | --- |
| 1：仅明确最终本地链接自动收取，不要求 JSON | 匹配 | `B/app/overseas/studio/delivery.py:19-38,60-96`，从 final_text 解析本地链接并校验范围；`B/tests/test_studio_file_links.py` 覆盖普通文件链接。 |
| 1：原生附件需同轮最终回复及实际路径证据，ImageView 不算成品 | 匹配 | `B/app/overseas/studio/native_images.py:73-76,98-107,123-141,241-269`；`B/tests/test_studio_native_images.py:254` 覆盖查看图与生成图像素相同的排除；真实事故回放独立通过。 |
| 1：无文件文字轮结束且可继续 | 匹配 | `B/app/overseas/studio/delivery_job.py:68-93`，expected=0 正常 succeeded；`B/tests/test_studio_open_outputs.py:59-82`、真实事故下一轮请求断言 `:120`。 |
| 2：保存原件、无格式接收白名单、普通文件独立记录 | 匹配 | `B/app/overseas/studio/output_files.py:23-35`、`output_store.py:13-22`、`models.py:88-100`；PNG/ZIP/未知/空/坏图混合测试 `B/tests/test_studio_open_outputs.py:35-56`。 |
| 2：图片预览/修改/归档沿用，普通卡片名称/大小/下载 | 匹配 | `F/src/views/overseas/studio/StudioTurns.vue:12-19` 和 `StudioOutputs.vue:2-7`；两个独立浏览器脚本通过，普通输出不加入图片选择。 |
| 2：预览失败仍能下载原件 | 匹配 | `F/src/views/overseas/studio/StudioAssetImage.vue:4,24-30`，下载独立调用原件地址；`F/tests/studio-preview-download.test.ts:9`；浏览器实际下载事件成功。 |
| 3：逐文件成功保留、失败有终态及手动入口 | 匹配 | `B/app/overseas/studio/delivery_job.py:129-165` 分项捕获/保存后统一结束；`output_store.py:25-60` 逐对象提交；`F/src/views/overseas/studio/StudioTurns.vue:34-36` 明确 partial。 |
| 3：正常模型退出后收取失败不锁执行、不无限重试 | 匹配 | `B/app/overseas/execution/runner.py:187-199`、`delivery_job.py:80-86` 删除旧重试字段并 claims.end(succeeded)；`B/tests/test_studio_receipt_continuation.py:13-52` 独立通过。 |
| 3：重启核实原退出、保留副本，不重跑模型；真实异常保持实际状态 | 匹配 | `B/app/overseas/studio/delivery_recovery.py:21-67` 先 context.success 后换租约；`delivery_job.py:105-106,132-134` 不重新捕获可变原件；`runner.py:139-149,200-208` 保留失败/未知路径；`B/tests/test_studio_delivery_recovery.py:189` 模拟真实 WorkerInterrupted。 |
| 4：先捕获已识别输出副本，下一轮覆盖后仍可取 | 匹配 | `B/app/overseas/studio/delivery_snapshot.py:58-91` 不可变字节；`delivery_job.py:129-150` 完成捕获阶段才发布/结束；续聊测试 `B/tests/test_studio_receipt_continuation.py:26-47` 真覆盖工作文件后下载旧字节。 |
| 4：副本失败如实提示，无全工作目录历史系统 | 匹配 | `B/app/overseas/studio/delivery_job.py:133-147`；`F/src/views/overseas/studio/StudioRecoveryDialog.vue:11` 明示已覆盖无副本不可恢复。 |
| 5：普通设计师手动列举 work、关联 native、副本，绕过自动识别 | 匹配 | `B/app/overseas/studio/recovery_listing.py:117-155`、`recovery_files.py:48-82`；`B/tests/test_overseas_studio_file_recovery.py:31-45,70-94,119-149` 使用 designer，不要求管理员。 |
| 5：当前会话写入时等待，不阻止其他会话及已存结果 | 匹配 | `B/app/overseas/studio/recovery_files.py:13-27`、`recovery_listing.py:48-52`；`B/tests/test_overseas_studio_file_recovery.py:171-206`。 |
| 6：同版本重复取回幂等 | **不匹配 / HIGH** | `B/app/overseas/studio/recovery_files.py:63-69`；独立 work → snapshot 探针失败。现有 `:87` 重复工作文件、`:149` 重复副本测试各自通过但未覆盖跨来源顺序。 |
| 6：同名新版与后续正式轮次保留关系 | 匹配（仍需修复时保持） | `B/app/overseas/studio/recovery_files.py:68-69` 新字节参与 ID；`delivery_snapshot_fs.py:46-48` 自动 ID 包含 jobId；`B/tests/test_overseas_studio_file_recovery.py:97-106`。 |
| 6：手动新增不修改已冻结清单 | 匹配 | `B/app/overseas/studio/recovery_files.py:68-72` 新数据库记录，未调用 snapshots.capture/begin；`output_store.py:63-84` 只刷新已有保存计数。 |
| 6：500 MB、取消旧10 MiB、0 B及预览降级 | 匹配 | `B/app/overseas/studio/output_files.py:26-35`、`files.py:26-51`、`recovery_listing.py:158-173`；`B/tests/test_studio_open_outputs.py:141-154` 独立验证真实大于10 MiB PNG仍是图片。 |
| 6：会话范围/权限/系统配置隔离 | 匹配 | `B/app/overseas/studio/recovery_files.py:13-27`、`recovery_listing.py:18,64-80,146-154`、`recovery_router.py:19-27`；跨会话候选、角色变化及受保护目录测试有断言。 |
| 6：任务/会话删除纳入新记录及对象，拒绝迟到发布 | 匹配 | `B/app/overseas/studio/conversation_cleanup.py:46-51,99-108`、`tasks/cleanup_files.py:19-24,35-50`、`tasks/cleanup_records.py:24`；`output_store.py:29-59` 发布前后 guard；`B/tests/test_studio_output_lifecycle.py:22-51` 以及手动迟到删除测试 `test_overseas_studio_file_recovery.py:226-239`。 |
| 6：完成只读、历史下载、解冻后再取；不新增普通文件归档完成要求 | 匹配 | `B/app/overseas/studio/recovery_files.py:23-24`、`files.py:115-122`；图片完成流程未加入 OutputFile；`B/tests/test_studio_open_outputs.py:132-138`；`F/src/views/overseas/studio/OverseasStudio.vue:42`。 |
| Redis/native 补充：API不读私有盘，不传文件字节，不启新模型任务 | 匹配 | `B/app/overseas/studio/recovery_router.py:19-27`、`recovery_transport.py:60-88,91-105`；独立 `test_studio_recovery_transport.py:59-86,102-123` 使用分离 API/native 根目录并禁止 API 调 candidates。 |
| Redis/native 补充：重新鉴权，短时请求、超时明确、坏请求不阻断下一条 | 匹配 | `B/app/overseas/studio/recovery_transport.py:19-28,94-105,108-134`；`B/tests/test_studio_recovery_transport.py:126-138,160-175,198-245` 独立通过。真实 Redis 尚未本地实测，列为发布验证边界。 |
| UI 引导及既有视觉一致性 | 匹配 | `F/src/views/overseas/studio/StudioRecoveryDialog.vue:4-19,30-40` 指向真实接口和明确状态；`StudioOutputs.vue:2-6` 复用附件样式；实际运行新取回页面与已有工作台基准渲染，查看桌面和390px截图。 |
| 实施计划：源文档、独立表、迁移、故障回归 | 已有实现，整体验收未通过 | 实施合同 `:40-44` 对应 `B/migrations/overseas/versions/0022_studio_output_files.py:10-31` 仅新增表，原业务语义保持；本报告 HIGH 阻断“独立审查通过”。 |
| 发布：原流程、排空备份、仅增表、限定事故 settle | 代码已实现；实际发布未验收 | `scripts/release/studio-output-deploy.py:72-101`；`studio-output-settle.py:13-31,44-77` 固定 job/events SHA、阶段门禁；`studio-output-settle-runtime.py:38-81` 校验进程/退出/权限/删除/审计。没有泛化强停；安装包 Linux/PG/Redis和正式入口验收仍待主 Agent 发布阶段。 |

## 部分实现、未实现与 Spec 漂移

- 部分实现：同版本幂等仅在同来源重复选择及 snapshot → work 顺序成立；work → snapshot 不成立，见 HIGH。
- 生产实测尚未完成：不能把隔离 SQLite、内存 Redis 替身、mock HTTP UI 宣称为实际 Linux/PG/Redis/正式入口通过，证据边界见下。
- 未发现新增超出合同的产品页面/归档功能；新增 OutputFile、取回 API、Redis metadata 传输和限定发布 settle 分别由实施合同 `:12,15-16,38,45` 支撑。已有管理员历史补收接口只适配文件记录与 partial 状态（`B/app/overseas/studio/delivery_repair.py:56-63,89-95`）。

## 已完成的验证及原始输出

独立运行（不是照抄主 Agent 声明）：

```text
STUDIO_INCIDENT_FIXTURE=<ignored private fixture>
python -m pytest tests/test_studio_open_outputs.py tests/test_studio_recovery_transport.py tests/test_studio_receipt_continuation.py -q
20 passed, 2 warnings in 15.15s

node tests/studio-outputs.browser.mjs
PASS: mixed outputs, partial terminal/send enabled, output download, failed preview original download, recovery partial/retry/empty, desktop/mobile clipping; no model calls

node tests/studio-delivery-status.browser.mjs
PASS: capturing, partial image, saving/waiting counts, completion, desktop/mobile clipping; no model calls
```

事故原始 rollout SHA 在 `B/tests/test_studio_open_outputs.py:92` 校验；测试把保全事件/工作文件写入隔离执行目录，并核对执行一次、原回复、原文档下载、activeTurnId为空及下一轮可提交（`:95-120`）。报告没有复制原客户内容。

已读取主线程日志的原始末尾（不是本 reviewer 重跑全套）：

```text
# output/studio-output-final-backend.log
885 passed, 43 skipped, 1881 deselected, 2 warnings in 236.07s (0:03:56)

# output/studio-output-final-unit.log
ℹ tests 396
ℹ suites 0
ℹ pass 396
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 9052.599

# output/studio-output-production-build.log
dist/assets/index-7p9zuagU.js  963.71 kB │ gzip: 307.80 kB
✓ built in 30.53s
```

`F/package.json:17` 的正式 build 为 `vue-tsc --noEmit && vite build`。上述日志证实该构建成功；存在既有弃用提示及构建体积提示，不等于运行验证。初轮全后端 Windows 有 Linux safe-open/symlink 用例环境失败，未在本地伪称解决；Linux安装包、真实PG及Redis验证仍为发布门禁。

实际查看的截图：`output/playwright/studio-outputs/desktop-partial.png`、`mobile-dialog.png`，与 `output/playwright/studio-delivery-status/desktop-baseline-complete.png`。新弹窗继承 Element 蓝色按钮、白底圆角与既有密度；390px 页脚折行但可达，错误项可读。浏览器数据为隔离测试数据。

## Stage 2 状态及提前记录的质量项

Stage 1 HIGH 确认后停止继续质量审查；**Stage 2 未执行完整审查**。此前通读清理路径时已经记录一个 MEDIUM：`B/app/overseas/tasks/cleanup_records.py:7` 重复导入 OutputFile，`:24` 重复同一删除条件，产生无意义第二次 DELETE，主 Agent 已收到修正建议。它不是本次 HIGH 的原因。

修复 HIGH 与该重复项、恢复生成文件、合并发布清单最后差异后，重新 `review-prepare`，由独立 reviewer 从 Stage 1 起复核新快照，随后才允许 Stage 2。原候选不提供任何批准凭据。
