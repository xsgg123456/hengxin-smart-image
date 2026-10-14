# 原生工作台 R8 独立审查（2026-10-14）

- candidateId：`76f87f7587485713c68a1cece35d6785f4e56747af52d824ea8a8b9f96d19a4d`。
- **Stage 1：FAIL（HIGH）；Stage 2：未执行。不得登记两阶段 PASS。**
- 范围：海外 studio、execution/runner、db、任务清理、0015 迁移及测试；前端 studio API、组件、Markdown、轮询、版本依赖及测试；native-studio deploy/runtime/package-overseas 及测试。不是历史全产品重审。
- 依据：AGENTS.md、code-review/SKILL.md、docs/HARNESS-REVIEW.md、Product-Spec.md:1100 最后原生工作台章节、DEV-PLAN.md 最后迭代、docs/NATIVE-STUDIO-RELEASE-20261014.md。独立读取实现，旧报告只作历史证据。
- 开始与结束的 review-status currentId 均等于上述 candidate。未改实现、提交、批准、部署、调用生产模型或操作用户 Chrome。仅新增本报告与 output 隔离探针；使用自己的本地 3026 预览及一次性 Chromium。

## Stage 1 阻断：文件路径批准被扩大到未经批准的正文位置

**HIGH S1-01**。Spec `Product-Spec.md:1106` 明确：“Markdown正文中的图片也遵守同一交付门禁，过程输出中的临时图片路径只作文字，不加载图片。”

`frontend/src/views/overseas/studio/StudioTranscript.vue:3` 向同轮所有公开 assistant 消息传入完整 `pictures`；`studio-markdown.ts:13` 仅凭路径在 approved Map 中就产生 `<img>`；`:35` 根据 Picture.sourcePath 建整轮映射，没有消息或引用位置身份。后端拒收的段落、alt、title，也没有传递到前端形成位置门禁。

最小正常可达流程：先前公开消息为 `这是草稿，暂不交付。\n\n![过程草稿](/work/final.png)`；同轮最后回复使用 `/work/final.png` 正式交付。后台保存一个正式 Picture 后，前面的草稿消息立即改为加载该图片。另一种情况不需要多消息：最终回复自身同时包含草稿段落及独立正式段落，并复用同一路径：

```markdown
这是草稿，暂不交付。

![非交付段落](/work/final.png)

## 正式交付

![正式图片](/work/final.png)
```

后端正确只将正式段落引用收入集合；前端却为两处引用都渲染图片。本 reviewer 用真实 PNG、合法本轮 workspace/session 和空历史 baseline 验证 collect_delivery，再用生产 renderStudioMarkdown 与正式 dist 的真实 Chromium 验证显示，均可重现。不是增加新的否定词反例，而是**引用位置的批准丢失**。

边界说明：三个位置读取的是同一个最终已批准对象的字节。本轮没有证明旧临时图像字节进入 Picture 或归档；错误是过程/拒收位置被重新升级为可加载图片，并会使旧过程记录展示后来文件内容。该行为直接不满足上述独立展示要求。

### 同类矩阵

| 输入形态 | 后端行为 | 前端实际行为 | 结论 |
|---|---|---|---|
| 先前公开 assistant 草稿消息，同轮 final 使用同路径 | final 可接收一个正式图 | 草稿消息产生 1 个 img | 不匹配 |
| final 草稿段落 + 正式段落，同路径 | 草稿单独 0；加正式段落 1 | 2 个 img | 不匹配 |
| final 草稿标题 + 同级正式标题，同路径 | 草稿单独 0；加正式段落 1 | 2 个 img | 不匹配 |
| final 草稿 alt + 正式段落，同路径 | 草稿单独 0；加正式段落 1 | 2 个 img | 不匹配 |
| final 草稿 title + 正式段落，同路径 | 草稿单独 0；加正式段落 1 | 2 个 img | 不匹配 |
| final 草稿下载链接 + 正式段落，同路径 | 草稿单独 0；加正式段落 1 | 草稿链接也指向正式对象 | 相同位置身份丢失 |
| 只有正式引用 | 接收 1 | 1 个 img | 正向对照 |
| tool/摘要不给 approved Map | 不适用 | 草稿引用 0 个 img | 对照，问题在 message 分支 |

证据：`output/native-studio-r8-collector-probe.py:1` / `.log`，`output/native-studio-r8-render-probe.ts:1` / `.log`，`output/native-studio-r8-browser-probe.mjs:1` / `.log`。浏览器截图 `output/playwright/native-studio-r8-reused-path.png`。实际浏览器原始输出：

```text
{"case":"same-path-reused","expectedMarkdownImages":1,"actualMarkdownImages":3,"images":[{"alt":"过程草稿","src":"/api/overseas/v1/tasks/t/studio/pictures/p/content","naturalWidth":120,"complete":true},{"alt":"非交付段落","src":"/api/overseas/v1/tasks/t/studio/pictures/p/content","naturalWidth":120,"complete":true},{"alt":"正式图片","src":"/api/overseas/v1/tasks/t/studio/pictures/p/content","naturalWidth":120,"complete":true}]}
```

测试盲区：`frontend/tests/studio-markdown.test.ts:15` 仅覆盖不同 sourcePath 的正式/临时图；`tests/studio-native.browser.mjs:103` 将正式交付放入不同轮次、不同路径，未覆盖同轮复用路径和同正文不同资格位置。后端 279 项通过不能证明前端位置门禁。

修复验收：不能用整轮路径集合授权所有 Markdown 出现位置。可保留经批准位置的身份，或将 Markdown 图片/本地文件引用统一显示为文字、正式图集中通过现有 Picture 卡片展示；后者应在源文档固定呈现约定，保留原文、外部普通链接及正式图预览/修改/SKU 归档。覆盖上述矩阵、刷新恢复与进行中→完成，重新固定快照并从 Stage 1 重审。

## Stage 1 逐条核对

以下 backend/、frontend/ 相对 `hengxin-smart-image/`。实现匹配指列出代码与验证支持该项，不等于整个候选已通过。因 S1-01 停止后未运行的浏览器或发布操作明确列出。

| Spec 项 | 结论、位置与证据 |
|---|---|
| 普通消息原样；每个新 CLI 会话首轮一句人设 | 完整实现。`backend/app/overseas/studio/execution.py:60` 按 previous_session 控制人设，`:64` 原样 text；`backend/tests/test_overseas_studio_conversations.py:38` 精确比对首尾空白和首/续轮，本轮通过。 |
| 只主动选中附件/Skill；无重复背景、步骤、数量；不改 Skill | 完整实现。`studio/service.py:51` 只解析显式 ID；`execution.py:49`–`:68` 只构造本轮输入和选中 Skill 引用；同一 prompt 测试通过。当前差异无 Skill 包内容变更。 |
| CLI 隔离与权限 | 完整实现。`execution.py:19` conversation 独立目录、精确 resume，`:40` workspace-write；`queries.py:14` 任务授权；`transcript.py:90` claim/lease/task/conversation 校验。归属/会话栅栏专项本轮通过。 |
| 新对话新上下文；保留历史、资料、成品归档 | 完整实现。`service.py:73` 仅新增 Conversation；`queries.py:63` 查询所有历史；`test_overseas_studio_conversations.py:16` 新 home、不 resume、历史保全和 `:55` 清理保归档本轮通过。 |
| 活跃/uncertain 阻止重置；幂等、并发 | 实现匹配。`service.py:16` 父行锁/幂等；`:26` 阻断非终态；`use-studio.ts:79` 未知结果保 key。独立后端专项通过；PG `test_overseas_studio_postgres.py:15`/`:31` 使用独立 Session/Barrier，提供的 66 passed 日志已读，本轮未重跑 PG。 |
| 完整多条/更新文字、有序持久化；摘要/工具状态 | 完整实现。`transcript.py:15` 公开白名单，`:41` 持久快照，`:54` 字节游标；`queries.py:92` 顺序 API；`studio-transcript.ts:4` 按 turn/item 原位更新。本轮长文、半行 UTF-8、重复/更新和工具脱敏专项通过。 |
| Markdown 文本、代码/普通链接；HTML 不执行；鉴权图像 | 部分实现。`studio-markdown.ts:4` html:false、`:18` 链接限制；`queries.py:14` 服务端授权。S1-01 使同门禁不通过。浏览器本轮复现三个已加载 img；安全深审未进入。 |
| 增量 1 秒目标、刷新重连、分页去重 | 实现匹配。`use-studio.ts:34` 活跃 1000ms，`:43` 连续分页；`runner.py:129` final_poll，`transcript.py:54` 字节边界，`queries.py:95` 500+1。独立后端分页/尾行/重复专项通过；本轮未重跑完整前端播报验收脚本。 |
| 执行默认展开、终态可折叠；历史滚动不强拉底 | 源码匹配。`StudioTranscript.vue:4` open=running；`StudioTurns.vue:37` 更新前测距，`:42` nearBottom 跟随。原有测试与提供日志支持，本轮浏览器仅跑门禁反例，不冒称完整交互已重验。 |
| 隐藏/卸载停请求、可见补齐；静默刷新保草稿/选择 | 源码匹配。`use-studio.ts:53` 手动 loading 分离；`:62` 可见性 abort/恢复；`:105` 卸载清理。已读实现和现有回归，不将此前浏览器 PASS 继承为本轮 PASS。 |
| 失败/停止保文字；图片错误独立 | 完整实现。`execution.py:85` 图片异常隔离、`:108` deliveryError；`runner.py:158` 异常尾读；`StudioTurns.vue:10`/`:11` 两种错误。本轮真实 runner 失败/取消/crash/收图失败测试通过。 |
| 当前成功 final 引用；禁止目录发现图片；历史/所有权/真实字节校验 | 文件收取实现匹配。`delivery.py:145` 成功门禁，`:157` `_local_file` baseline，`:163` validate_image；`execution.py:37` 快照仅供历史排除。独立 collector 与 runner 测试覆盖坏图混合、跨会话/inputs/Skill/历史/未引用文件，全部通过。 |
| 临时/草稿/试验/中间不展示、不归档；无候选区；Markdown 同门禁 | **部分实现/HIGH**。R7 原 75 组合、本轮递归 title 均已修；但 `StudioTranscript.vue:3` 与 `studio-markdown.ts:13` 存在 S1-01。未新增候选区，未证明临时字节入库；前端过程位置展示仍不匹配。 |
| 正式图预览、引用修改、SKU 归档 | 实现保留。`StudioTurns.vue:14`/`:15` 预览和修改；`use-studio.ts:102` 引用；`service.py:93` 校验 SKU、保护归档。对应后端专项通过；本轮不作生产归档操作。 |
| 新对话确认/历史分界、成功清草稿；真实引导 | 实现匹配。`OverseasStudio.vue:20` 确认，`StudioTurns.vue:5`/`:19` 分界；`use-studio.ts:75` 成功清理、失败保留。placeholder、Skill、素材、发送均有处理；本轮未重新验收 390px。 |
| 0.2.31 图需任意扩展/北京时间/Skill 真名称描述/静默刷新保留 | 本次变更范围不含图需上传/全局时间/Skill 包；`OverseasStudio.vue:14` 保持既有选择器、`use-studio.ts:53` 保持静默刷新。工作台附件限制与图需上传为不同范围。源码边界匹配，完整旧功能浏览器未重跑。 |
| 0014→0015、历史兼容、国内0028/身份不变 | 实现匹配。`backend/migrations/overseas/versions/0015_studio_transcript.py:10` 增量结构，`:48` 幂等历史回填，`:56` 禁降级；`tasks/cleanup_records.py:22` 新 transcript 清理。已读真实 PG 66 passed 日志；未做生产迁移。 |
| 0.2.32、实际测试过同一镜像供 API/migrate | 实现匹配。`scripts/release/native-studio-runtime.py:12` 固定版本，`:37` 同 image overlay，`:80` 迁移前核对；`member-release-runtime.py:99` 比对 INSTALL_TEST_IMAGE_ID，`overseas-deploy.py:25` 镜像安装测试。最终实际安装全量尚未执行，不算已完成。 |
| 关接纳、双排空、完整备份、迁移切换 | 实现匹配。`native-studio-deploy.py:50` 关闭/停止 API，`:55` drain，`:58` COMPLETE 备份门禁后才 migrate，`:69` 切换。只读代码，生产操作未执行。 |
| 失败保持关闭、只前进、禁降库/盲恢复/重放 | 实现匹配。`native-studio-deploy.py:20` 重放栅栏，`:37` 恢复约束；`native-studio-runtime.py:118` 记录关闭结果、阶段、实际 schema。未执行实际失败恢复。 |
| 14 Skill/181 文件、国内/身份不动；无收费调用 | 差异范围不含 Skill 包、国内/身份代码；`native-studio-runtime.py:70`/`:111` Skill 验证、`:110` 资源不变核查。reviewer 无生产操作；生产数量/身份不变仍为最终发布验收。 |

未实现：未发现整项新增功能完全缺失。部分实现：Markdown 同门禁及过程临时路径纯文字呈现。Spec 漂移：`models.py:64` Transcript、`router.py:33` 新会话、`:38` 增量接口均有需求依据，未发现新增无依据页面/候选区。

## 验证、编译与边界

本 reviewer 独立执行四组后端专项 formal_delivery/transcript/conversations/execution，退出 0，原始汇总：

```text
279 passed, 2 warnings in 11.51s
```

两条 warnings 为 Starlette/httpx 与 anyio BlockingPortal 弃用。另独立重跑 `output/native-studio-r7-review-probe.py:1`，15 条说明 × 5 位置全部 accepted_positions=[]，nested_title 也为 []，positive 保留 `/work/final.png`。R7 原 HIGH 已修，不能抵消新结构性问题。

编译仅核对主 Agent 提供日志，本 reviewer 发现 Stage 1 HIGH 后未重跑编译。原始末行 `output/native-studio-build.log`：

```text
✓ built in 37.70s
```

已读取、不是本轮独立重跑：

```text
# output/native-studio-backend-pg-20261014.log
66 passed, 2 warnings in 48.13s
# output/native-studio-backend-full-r7.log（R7 旧快照）
2166 passed, 188 skipped, 15 warnings in 250.38s (0:04:10)
```

R8 仅 collector/测试变动不等于已执行 R8 整库。最终实际安装镜像全量仍为生产切换前门禁。提供的发布全目录记录另有 242 passed、1 skipped、117 subtests passed 与 1 个历史失败（test_release_native.py:100 旧 overlay 顺序；相关两文件本轮未改），不能称全发布目录全绿。

**Stage 2 未执行**：按 skill 遇 Stage 1 HIGH 即停止；代码质量、安全深审、邻居视觉和完整编译未重新执行。R6 的 Stage 2 部分证据不继承为当前 PASS。主 Agent 修复后重新 review-prepare，并派 fresh reviewer 从 Stage 1 审查。本报告不可用于 review-approve，不写 `.needs-review`。

报告落盘及最后一次快照核对后，主 Agent 通知开始下一轮文档/前端修复。以上结论只对应原 `76f87f…` 快照和已记录证据，不能覆盖或批准随后新代码；新版本必须重新固定快照并独立审查。
