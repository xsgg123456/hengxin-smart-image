# 原生工作台独立审查 R7（2026-10-14）

- candidateId：`28ed2e274df4bc384e74f57b404a2646c038c7f64ccc50254ced1bcc5c8ebd86`。
- **Stage 1：FAIL（HIGH）；Stage 2：未执行。不得登记两阶段 PASS。**
- 范围：海外 studio、execution/runner、db、任务清理、0015 迁移及测试；前端 studio API、组件、Markdown、轮询、版本依赖及测试；native-studio deploy/runtime/package-overseas 及测试。不是历史全产品重审。
- 依据：AGENTS.md、code-review/SKILL.md、docs/HARNESS-REVIEW.md、Product-Spec.md:1100 原生工作台章节、DEV-PLAN.md 最后迭代、docs/NATIVE-STUDIO-RELEASE-20261014.md。旧报告仅作为缺陷历史，没有继承其 PASS。
- 开始和结束读取 review-status，currentId 均与 candidateId 相同。未修改实现、批准、提交、部署、调用生产模型或操作用户浏览器。只新增本报告和 output 下独立探针。

## Stage 1 阻断：明确试验、初稿、未完成说明仍被收为正式图片

**HIGH S1-01**。需求 `Product-Spec.md:1106`：“临时图、草稿、试验图、中间文件不显示、不归档”，“Markdown正文中的图片也遵守同一交付门禁”。

位置：`hengxin-smart-image/backend/app/overseas/studio/delivery.py:19` 与 `:25` 的非交付分类遗漏常见明确说明；`:69` 因此返回 false，`:107` 提取引用，`:152` 收入正式交付集合。最小输入：

```markdown
## Test images
For testing only.

![Image](/work/final.png)
```

本 reviewer 使用 TemporaryDirectory，创建真实 12×13 PNG、本轮 work/home、`.codex/generated_images/session`、空 baseline；调用生产 collect_delivery，summary 设置成功完成、无 error、session_id=session。返回 `['/work/final.png']`，warnings 为 `[]`。这不是绕开文件校验的字符串单测；图像字节、会话根和历史门禁均走生产实现。

一次性拓展为 **15 条说明 × 前置段落、后置段落、标题、alt、title 共 75 个输入**。下列 11 条在五个位置全部误收（55 个反例）：

| 明确非交付说明 | 实际结果 |
|---|---|
| `For testing only.` | 五位置均收取 |
| `Experimental images.` | 五位置均收取 |
| `For experimentation only.` | 五位置均收取 |
| `This is a rough sketch.` | 五位置均收取 |
| `This is a preliminary version.` | 五位置均收取 |
| `This is a work in progress.` | 五位置均收取 |
| `这些图片仅用于测试。` | 五位置均收取 |
| `这些是初稿。` | 五位置均收取 |
| `这些是工作稿。` | 五位置均收取 |
| `这些是中间版本。` | 五位置均收取 |
| `这些图片尚未完成。` | 五位置均收取 |

对照 `This is a working draft.`、`这是试验图。`、`These are draft images.`、`These are not final images.` 在五位置均拒收，说明不是调用前提失效，而是类别识别不完整。

另有同门禁的结构性边界：

```markdown
![![Image](unused "n&#111;t final images")](/work/final.png)
```

也返回 `['/work/final.png']`、warnings `[]`。`delivery.py:60` 的 title 检查仅遍历当前 token 的直接 children；嵌套 image 的 title 未递归处理，raw content 的实体又不会直接匹配 not。这里不能称嵌套 title 是浏览器实际显示的悬浮标题：它位于外层 alt 子树。本项是“所有标签使用同样否定解析”实现不完整的附加证据，核心 HIGH 不依赖此较特殊输入。

影响链：`backend/app/overseas/studio/execution.py:93` 保存图片、`:118` 创建 Picture，`queries.py:51` 输出正式图片 DTO；`frontend/src/views/overseas/studio/StudioTurns.vue:12` 提供选图与预览，`studio-markdown.ts:35` 将 sourcePath 加入正文批准映射；`backend/app/overseas/studio/service.py:93` 支持 SKU 归档。因此误收可以变为前端可显示、可引用修改、可归档的正式图片，不只是内部分类标签偏差。

测试盲区：`backend/tests/test_studio_formal_delivery.py:109` 和 `:162` 围绕已有关键词/否定 token 做了较多变体，但没有覆盖上述常见试验、初稿与未完成语义；`:162` 的 title 用例只覆盖一层。`test_overseas_studio_execution.py:94` 的 runner→API 反例也没有这些输入。当前已有 163 项全通过不能证明此门禁完整。

修复验收：一次覆盖这些明确非交付类别与作用域，在保留原始公开文字的前提下拒收；递归核查标签元数据；保留正式交付独立段落、同级正式标题、真实成品及文件名的正向对照，避免仅扩大模糊关键词造成正常交付全面误杀。补 collector 和真实 runner→API 回归，然后重新固定 candidate 并从 Stage 1 重审。

独立可重跑探针：`output/native-studio-r7-review-probe.py:1`；输出 `output/native-studio-r7-review-probe.log`。命令：

```powershell
.\hengxin-smart-image\backend\.venv\Scripts\python.exe output/native-studio-r7-review-probe.py
```

## Stage 1 逐条核对

下表 backend/、frontend/ 相对 `hengxin-smart-image/`。完整实现指源码和所列证据支持该条，不代表整体验收通过；未执行的验证明确列出。

| 条目 | 结论与证据 |
|---|---|
| 普通消息原样；新 CLI 会话仅首轮一句人设 | 完整实现。`backend/app/overseas/studio/execution.py:62` 原样追加 text，previous_session 控制人设；`backend/tests/test_overseas_studio_conversations.py:37` 比对完整含首尾空白的两个 prompt，本轮通过。 |
| 仅主动附件/Skill 引用，不重复商品背景/步骤/数量格式，不改 Skill | 完整实现。`studio/service.py:51` 只处理显式 IDs，`execution.py:53` 只写本次 inputs，`:67` 按选择补 Skill 路径。当前差异无 Skill 包改动；`test_overseas_studio_execution.py:51` 与首轮测试本轮通过。 |
| 保持 CLI 隔离与访问权限 | 完整实现。`execution.py:19` 按 conversation 建 home、检查精确旧 session；`:40` workspace-write；`queries.py:14` 权限；`transcript.py:90` 校验 claim/lease/task/conversation。`test_overseas_studio_transcript.py:80` 归属与 session 栅栏本轮通过。 |
| 新对话新上下文，历史材料/对话/图片/归档保留 | 完整实现。`service.py:73` 只新增 Conversation，`queries.py:63` 读取所有历史轮次；`test_overseas_studio_conversations.py:16` 校验新 home、不 resume 和材料保留，本轮通过；`:57` 多会话清理与归档保全也通过。 |
| active/uncertain 阻止，幂等并发 | 实现匹配。`service.py:16` 锁/幂等、`:26` 拦截所有非终态；`use-studio.ts:79` 未知结果保 key，`:85` 重试。独立专项覆盖幂等和 uncertain；真实并发测试 `test_overseas_studio_postgres.py:17`/`:34` 使用 Barrier 与独立 Session，已读提供的 PG 66 passed 日志，本轮未重跑 PG。 |
| 完整多条/更新 assistant 文字，有序持久化；公开摘要/工具状态 | 完整实现。`transcript.py:15` 公共事件白名单、`:41` 持久快照、`:54` 完整读取；`queries.py:92` 升序游标，`studio-transcript.ts:4` 按 turn/item 原位更新。`test_overseas_studio_transcript.py:42` 长文、UTF-8 半行、重复/更新、工具脱敏本轮通过。 |
| Markdown 代码、链接；HTML 不执行；图片/下载鉴权 | 部分实现。`studio-markdown.ts:4` html:false，`:18` 链接只允许批准本地映射或 HTTP(S)，`queries.py:14` 服务端鉴权。正式图片映射受 S1-01 污染，本条不能整体通过。安全深审属于 Stage 2，本轮未执行。 |
| 近 1 秒播报；刷新/重连、分页去重 | 实现匹配。`use-studio.ts:34` 活跃 1000ms，`:43` 连续分页；`runner.py:129` final_poll，`transcript.py:54` 字节游标；`queries.py:95` 500+1。独立后端 502 条分页、尾行、更新测试通过；本轮未重新运行前端浏览器。 |
| 执行中展开，终态折叠；历史滚动不拉底 | 实现匹配。`StudioTranscript.vue:4` open 绑定 running；`StudioTurns.vue:37` 更新前记录距离、`:42` 更新后按 nearBottom 跟随。此前浏览器证据不继承为本轮实测 PASS。 |
| 隐藏/卸载停请求，恢复补齐；静默刷新 | 实现匹配。`use-studio.ts:53` 手动 loading 分离、`:62` 可见性 abort/恢复、`:105` 卸载清理。R7 无此处改动；本轮未重跑浏览器，不宣称现场验收。 |
| 失败/停止保留公开文字；图片收取失败独立告知 | 完整实现。`execution.py:85` 收图异常隔离、`:108` deliveryError；`runner.py:158` 异常尾读；`StudioTurns.vue:10`/`:11` 两种错误独立显示。`test_overseas_studio_transcript.py:94`/`:120` 真实 runner 失败、取消、crash/收图失败本轮通过。 |
| 仅当前成功 final 引用；不扫描发现图片；真实图像、历史/归属校验 | 文件来源实现完整。`delivery.py:130` 成功门禁，`:143` `_local_file` 与 baseline，`:150` validate_image；`execution.py:37` baseline 用于排除历史。独立专项覆盖跨会话/inputs/Skill/坏图混合/无引用。 |
| 临时/草稿/试验/中间不展示、不归档；无候选区；正文同门禁 | **部分实现/HIGH**。`delivery.py:19`/`:25` 类别遗漏，见 S1-01。未新增候选区。R7 text_special 已修，实体、不可见、全角的已有专项通过，不能抵消本次反例。 |
| 保留预览、引用修改、SKU 归档 | 实现存在，但集合受 S1-01 影响。`StudioTurns.vue:14`/`:15` 预览/修改；`use-studio.ts:102` 引用；`service.py:93` SKU/版本归档。当前误收集合使整体边界不通过。 |
| 新对话确认、历史分界、成功后清草稿；引导真实性 | 实现匹配。`OverseasStudio.vue:20` 确认与影响说明，`StudioTurns.vue:5`/`:19` 分界，`use-studio.ts:75` 成功清空；失败保留。现有 placeholder、发送、Skill/附件按钮都有处理。未执行本轮桌面/390px真实页面对比。 |
| 0.2.31 上传不限扩展/北京时间/真实 Skill 名描述保留 | 本次变更未修改图需上传、北京时间实现和 Skill 包；`OverseasStudio.vue:14` 保持既有 Skill 选择器。工作台附件自身限制不是图需上传规则。源码边界匹配；不将旧浏览器通过冒称本轮复验。 |
| 0014→0015 增量与历史兼容、国内0028/身份不变 | 实现匹配。`migrations/overseas/versions/0015_studio_transcript.py:10` 增量结构、`:48` 幂等回填、`:56` 禁降级；`tasks/cleanup_records.py:22` 清理新 transcript；提供的真实 PG 测试日志 66 passed 已读取，生产迁移未执行。 |
| 0.2.32；测试过的同镜像用于 API/migrate | 实现匹配。`scripts/release/native-studio-runtime.py:12` 固定版本/Schema，`:37` 同 identity overlay，`:80` 迁移前重核；`member-release-runtime.py:99` 核对 INSTALL_TEST_IMAGE_ID，`overseas-deploy.py:25` 运行镜像测试。最终生产安装验证仍未执行。 |
| 关接纳、双排空、完整备份、迁移切换 | 实现匹配。`native-studio-deploy.py:50` 关闭 API 接纳，`:55` 排空，`:58` COMPLETE 备份后才迁移、`:69` 切换海外 API/worker。本轮只读代码，未执行生产操作。 |
| 失败保持关闭；只前进、禁降库/盲恢复/重放 | 实现匹配。`native-studio-deploy.py:20` 重放栅栏、`:37` 恢复约束；`native-studio-runtime.py:118` 记录关闭结果/实际 Schema/异常阶段。未执行实际失败恢复。 |
| 14 Skill/181文件、国内/身份不动，无生产付费调用 | 差异范围不含 Skill 包、国内/身份实施；`native-studio-runtime.py:70`/`:111` 验证 Skill、`:110` resources_unchanged。reviewer 无生产操作；生产最终不变性仍需发布验收。 |

未实现：未发现整项新增功能缺失。部分实现：非交付分类与受影响的图片展示、修改引用、归档。Spec 漂移：`models.py:64` Transcript、`router.py:33` 新会话、`:38` 增量接口均有需求依据，未发现无依据的新页面/表/候选区。

## 验证、编译与边界

本 reviewer 独立运行四组后端专项（formal_delivery/transcript/conversations/execution），退出 0，原始汇总：

```text
163 passed, 2 warnings in 10.57s
```

两条 warnings 为 Starlette/httpx 和 anyio BlockingPortal 弃用。独立探针原始输出节选（完整矩阵见上述日志）：

```text
{"notice": "For testing only.", "accepted_positions": ["before", "after", "heading", "alt", "title"]}
{"notice": "Experimental images.", "accepted_positions": ["before", "after", "heading", "alt", "title"]}
{"notice": "For experimentation only.", "accepted_positions": ["before", "after", "heading", "alt", "title"]}
{"case": "r6_entity", "result": [[], []]}
{"case": "negative_parent", "result": [[], []]}
{"case": "nested_title", "result": [["/work/final.png"], []]}
{"case": "positive", "result": [["/work/final.png"], []]}
```

已读取提供的日志，不是本 reviewer 重跑：

```text
# output/native-studio-backend-pg-20261014.log
66 passed, 2 warnings in 48.13s
# output/native-studio-build.log
✓ built in 37.70s
```

主线程本轮完整后端日志 `output/native-studio-backend-full-r7.log` 在报告编写时仍运行中，不计已通过；R5 的 2141 passed 属于旧快照。提供的发布全目录历史记录有 242 passed、1 skipped 和 1 failed（test_release_native.py:100 的旧 overlay 顺序断言，本轮相关两文件未改），不能宣称全部全绿。

**Stage 2 未执行**：发现 Stage 1 HIGH 后停止质量、安全深审、邻居视觉与编译重跑。旧 R6 的前端356项、类型、发布专项和邻居截图不继承为 R7 两阶段 PASS。下一步由主 Agent 修复，重新固定快照后派独立审查；本报告不能用于 review-approve，不写 `.needs-review`。
