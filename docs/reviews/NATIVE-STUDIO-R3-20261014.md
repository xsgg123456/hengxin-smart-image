# 原生工作台独立审查 R3（2026-10-14）

- candidateId：`4d7e993e0339f10016bc82230f1ffc75a9598344e7644d0f44bf25d311c6ed87`。
- **Stage 1：FAIL（1 项 HIGH）。Stage 2：未执行。不得登记两阶段 PASS。**
- 已读取 AGENTS.md、`.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、Product-Spec.md 最后原生工作台章节、DEV-PLAN.md 最后迭代和本次发布合同。独立检查当前实现并执行专项与反例，不依赖前两轮结论替代本轮审查。
- 范围：本次全部受控代码差异，包括海外 studio、公共海外 runner、db/cleanup、0015 迁移及测试；工作台前端/API/Markdown/轮询及测试、版本与锁文件；0.2.32 打包与迁移发布脚本及测试。依据 `Product-Spec.md:1100` 至本章节末尾，以及 `docs/NATIVE-STUDIO-RELEASE-20261014.md`。
- 初次与报告落盘后的 `review-status` 的 currentId 均与上述候选一致，approved 为 false，审查期间未发现快照漂移。发现问题后主 Agent 明确保持源码冻结。本轮只新增本报告，未修改实现、提交、部署、批准或执行付费模型。

## Stage 1 阻断问题

### HIGH S1-01：否定“正式交付”的正文仍被识别为正式声明，预览图进入成品集合

需求原文（`Product-Spec.md:1106`）：“仅接收本轮最终回复或明确正式交付事件引用、且有效性与归属校验通过的图片”；“临时图、草稿、试验图、中间文件不显示、不归档”；“Markdown正文中的图片也遵守同一交付门禁”。

位置：`hengxin-smart-image/backend/app/overseas/studio/delivery.py:18`、`:21`、`:36`、`:54`、`:65`。

R3 已禁止路径、图片 alt、链接标签和代码声明正式范围，但 `formal_prose()` 对可见正文仍只检查是否包含正式词组。`NON_DELIVERY` 不识别“并非最终交付”“不是正式交付”“not final images”。这些表达中的正式词组反而匹配 `FORMAL`，使 `delivery_blocks()` 保持或新建 `blocked=False`。明确只供预览、否定正式交付的图片因此被收取，且不产生警告。

这不是模糊语义或假造状态：以下均是正常可达的成功 CLI 最终回复，图片为本轮工作目录内真实有效 PNG、会话归属正确。

```markdown
以下图片仅供预览，并非最终交付。

![预览](/work/a.png)
```

同样错误的最小正文包括“这不是正式交付。”和英文“These are not final images.”。

**独立复现方法**：用 `TemporaryDirectory` 建立 work/home 和 `.codex/generated_images/session`，Pillow 创建 12×13 蓝色 PNG；直接调用当前生产 `collect_delivery()`。summary 为 `turn_completed=True, error=None, session_id='session'`，workspace.baseline 为 `{}`。不是只测试正则，也没有把非法路径或损坏图片伪装成可达输入。

原始输出（Python `json.dumps` Unicode 转义；退出码 0）：

```text
{"final_text": "\u8fd9\u662f\u8349\u7a3f\uff0c\u6682\u4e0d\u4ea4\u4ed8\u3002\n\n![\u9884\u89c8](/work/a.png)", "accepted": [], "warnings": []}
{"final_text": "\u4ee5\u4e0b\u56fe\u7247\u4ec5\u4f9b\u9884\u89c8\uff0c\u5e76\u975e\u6700\u7ec8\u4ea4\u4ed8\u3002\n\n![\u9884\u89c8](/work/a.png)", "accepted": ["/work/a.png"], "warnings": []}
{"final_text": "\u8fd9\u4e0d\u662f\u6b63\u5f0f\u4ea4\u4ed8\u3002\n\n![\u9884\u89c8](/work/a.png)", "accepted": ["/work/a.png"], "warnings": []}
{"final_text": "These are not final images.\n\n![Preview](/work/a.png)", "accepted": ["/work/a.png"], "warnings": []}
{"final_text": "## \u6b63\u5f0f\u4ea4\u4ed8\n![\u56fe\u7247](/work/a.png)", "accepted": ["/work/a.png"], "warnings": []}
```

**影响链**：`studio/execution.py:89` 收取结果，`:103` 存储，`:120` 创建 Picture；`studio/queries.py:51` 返回图片 DTO；`frontend/src/views/overseas/studio/studio-markdown.ts:42` 将 sourcePath 映射为授权图片；`StudioTurns.vue:12` 提供勾选，`studio/service.py:93` 允许 SKU 归档。下游文件鉴权只验证访问权限，不会纠正非交付分类。

**修复验收**：否定正式交付的可见说明必须优先排除，不能因为其中包含正式词组就解除非交付范围。覆盖中文“不是/并非/尚非/暂不作为”等和英文否定、仅供预览，以及前置/后置说明、段落和标题作用域；保留真正独立的肯定正式交付对照。补 collector 和真实 runner→API 回归，证明正文原样保留、无 Picture/DTO/可归档图片。不要通过强加用户提示词或修改 Skill 内容回避。修复后重新固定 candidateId，从 Stage 1 重新审查。

**前两轮修复结论**：`tests/test_studio_formal_delivery.py:61` 的跨段落/父标题排除、`:89` 的路径/alt/link/code 反例当前均通过；R1/R2 已知反例被修复。但现有用例没有覆盖否定正式声明，本轮独立 56 项通过仍可复现 S1-01。

## Stage 1 逐项对照

以下 backend/、frontend/ 路径前缀均为 `hengxin-smart-image/`。表内匹配限于所列代码与证据，整个 Stage 1 仍为 FAIL；没有把后续生产执行当作已完成。

| 需求/验收项 | 结论 | 实现及验证证据 |
|---|---|---|
| 普通消息原样；每个新 CLI 会话首次仅指定人设 | 匹配 | `backend/app/overseas/studio/execution.py:62` 人设仅无 previous_session 时添加、`:64` 直接追加原文；`tests/test_overseas_studio_conversations.py:37` 实际 worker 捕获首轮/续轮精确 prompt，本轮专项通过。 |
| 只引用主动附件/Skill，无自动商品/任务背景、步骤或格式 | 匹配 | `studio/service.py:51`、`:60` 输入来自显式 ID；`execution.py:65`、`:67` 仅附选中文件路径；schemas 不 trim 原文。原件字节与多轮专项通过。 |
| 原 CLI 权限与隔离不放宽 | 匹配 | `execution.py:19` 会话独立 home、`:41` workspace-write；`queries.py:14` 统一 task.read/design；`transcript.py:97` claim/lease 和 task/turn/conversation 所有权核验。错误会话及撤权 403 专项通过。 |
| 所有公开 assistant 文字完整有序持久化 | 匹配 | `transcript.py:31`、`:41` Text 快照而非截取末条；`queries.py:92` ID 增量读取；`frontend/.../studio-transcript.ts:4` 同轮 item 原位更新；长文、更新、多条、末尾 UTF-8 实跑通过。 |
| 公开摘要与工具状态，禁止任意工具输出/隐藏推理 | 匹配 | `transcript.py:31` 仅公开 reasoning.text，`:36` 工具仅固定标签，未知类型忽略；`tests/test_overseas_studio_transcript.py:42` SECRET_API_KEY、PRIVATE_STDOUT、PRIVATE_CHAIN 均不出现在 API，本轮通过。 |
| Markdown/代码/链接与 HTML 不执行 | 匹配（交付分类另见 HIGH） | `frontend/.../studio-markdown.ts:4` html:false，`:13` 图片只经批准映射，`:18` 未批准本地链接为文字；`api/overseas/studio.ts:33` 图片 URL 按当前任务/图片 ID 精确校验；独立查看运行态截图，HTML 字面显示、代码块和外链可读。 |
| 1 秒级增量、分页重连去重、不漏末尾 | 匹配 | `transcript.py:54` byte cursor/半行保护与 final drain；`queries.py:92` 500+1 分页；`use-studio.ts:34` 活跃轮 1000ms、`:42` 连续页；本轮 502 条分页、半行 UTF-8、重复 poll 测试通过。 |
| 执行过程默认展开、终态折叠 | 匹配 | `StudioTranscript.vue:4` open 绑定 running，`StudioTurns.vue:30` 在途状态；已目视 running-markdown.png，执行消息展开；提供浏览器断言终态关闭。 |
| 历史阅读滚动保留，底部跟随 | 匹配（提供浏览器证据） | `StudioTurns.vue:37`–`:41` DOM 更新前测位置后跟随；`tests/studio-native.browser.mjs:74`、`:83` 实际 scrollTop/底部距离断言，日志 PASS。本轮未重跑浏览器。 |
| 隐藏/卸载停止请求，返回补齐 | 匹配 | `use-studio.ts:34` 可见性调度、`:62` 隐藏 abort 和恢复、`:105` 卸载取消；已读前端 356 项与刷新浏览器日志。 |
| 失败/停止/未知执行保留公开文字 | 匹配 | `backend/app/overseas/execution/runner.py:158` 异常 final_poll；`transcript.py:49` 独立写回复；`test_overseas_studio_transcript.py:96` failure/cancel/crash 经真实 runner→DB/API，本轮通过。 |
| 图片失败不影响文字，明确告知 | 匹配 | `execution.py:88` 整体异常警告、`:93` 逐图存储隔离、`:107` reply 独立返回；`test_overseas_studio_transcript.py:125` 收取异常仍 succeeded/保文/无图，专项通过。 |
| 本轮成功 final 引用且不扫描发现图片 | 匹配 | `delivery.py:97` 完成/error/final 门禁、`:102` 仅解析引用；`execution.py:37` baseline 扫描仅用于历史排除；无引用文件、失败/未完成拒收专项通过。 |
| 本地文件所有权、真实图片、历史隔离与去重 | 匹配 | `delivery.py:109` 复用 `_local_file`，`:114`–`:118` 读字节/validate_image/去重；`backend/app/execution/final_delivery.py:45` 禁跨目录、输入、Skill、跨会话、历史及硬链接；专项通过。 |
| 非交付图片不得显示、归档，Markdown 同一门禁 | **不匹配 HIGH** | `delivery.py:18`、`:36`、`:65` 将否定正式声明当肯定；独立真实图片反例见 S1-01。API/正文/归档集合均受影响。 |
| 新对话重置上下文，保留历史/材料/图片/归档 | 匹配 | `service.py:73` 仅新增 Conversation；`queries.py:67` 查询全部历史轮；`test_overseas_studio_conversations.py:16`、`:57` 独立 home、保留材料和归档，多会话删除兼容专项通过。 |
| 并发/重复请求安全；running/uncertain 禁止重置 | 匹配 | `service.py:16` actor/task 锁与幂等，`:26` 非 TERMINAL 全阻止；`use-studio.ts:14` pending 锁、`:79` 未知结果保留相同 key。已读 PG 测试 `test_overseas_studio_postgres.py:15`、`:33`，日志 66 passed、无 skip。 |
| 新会话确认、分界与成功清草稿 | 匹配 | `OverseasStudio.vue:20` 确认文案，`StudioTurns.vue:5`、`:19` 分界；`use-studio.ts:76` 仅成功后清空；提供浏览器重试相同 key 和原文发送断言通过。 |
| 预览、修改引用和 SKU 归档保持 | 匹配，但可操作集合受 HIGH 污染 | `StudioTurns.vue:14` 预览、`:15` 修改；`use-studio.ts:102` 引用；`service.py:93` SKU 校验/归档保护/重复保护；专项覆盖归档保留。 |
| 既有 0.2.31 四项保持：图需上传、北京时间、Skill 标题描述、静默刷新 | 匹配（源码变更边界与提供回归） | `OverseasStudio.vue:14` 继续复用 StudioSkillSelect；`use-studio.ts:53` 手动 loading 与后台刷新分离；图需上传、公共时间实现与 Skill 包本轮无改动，前端 356 项和旧刷新/Skill 浏览器 PASS。工作台独立附件格式未误当图需不限格式。 |
| 桌面/390px，与已有工作台结构一致、引导真实 | 匹配（本轮截图检查范围） | `OverseasStudio.vue:5`、`:13`、`:20` 按钮对应真实 handler；`studio.css:13` 等复用样式变量；已目视 running-markdown.png 和 mobile-confirm.png，主要内容、按钮、确认框不越界。新旧邻居实时视觉比对属于 Stage 2，未执行。 |
| 海外0014→0015，旧会话/回复保持、重复迁移，国内0028不变 | 匹配（提供隔离 PG 证据） | `backend/migrations/overseas/versions/0015_studio_transcript.py:10` 添加列/表、去任务唯一约束、`:48` 旧 reply 去重回填、`:56` 禁降级；已读 `test_overseas_studio_migration.py:16` 旧行逐列/国内快照/重复 upgrade 验证，66 passed。 |
| 0.2.32；同一已安装测试镜像用于 api/migrate | 匹配（代码与提供测试） | `scripts/release/native-studio-runtime.py:12` 版本/schema、`:37` image identity overlay、`:80` 再核对 identity；`overseas-deploy.py:46` 安装测试镜像凭据；发布重点日志 73 passed。实际生产镜像与迁移仍待发布阶段。 |
| 关闭接纳、双排空、备份、失败保持关闭、前进恢复 | 匹配（代码与提供测试） | `native-studio-deploy.py:50` 关闭入口/停 API→drain→COMPLETE backup→migration；`overseas-hotfix-deploy.py:70` outbox 停止前后双排空；`native-studio-runtime.py:118` 异常关闭并记录真实 schema；`native-studio-deploy.py:20` 拒绝重放。尚未生产执行。 |
| 不重启国内/身份，不改14份Skill，不生产收费调用 | 匹配（本次实现边界） | `native-studio-runtime.py:70`、`:111` 只验证 Skill；`native-studio-deploy.py:69` 仅切换海外 native/API、`:98` resources_unchanged；测试隔离进程边界；reviewer 未发起生产操作。生产最终核对仍待发布。 |

### 完整、部分、未实现与漂移

- 完整实现的逐项证据见表；正式交付分类为部分实现，否定声明的排除不满足验收。
- 未发现本范围新增候选区、无需求页面或业务扩展。`models.py:64` Transcript、`router.py:32` Conversation API、`:37` transcript API、`queries.py:51` sourcePath 分别对应完整文字、新上下文、增量读取及图片门禁需求。
- 生产提交、切换、安装验证和真实页面验收属于审查后步骤，尚未完成；不作为本轮源码缺失，也不声称已经验证。

## 验证与编译原始输出

Reviewer 本轮独立执行（退出码 0）：

```text
.venv/Scripts/python.exe -m pytest -q tests/test_studio_formal_delivery.py tests/test_overseas_studio_transcript.py tests/test_overseas_studio_conversations.py tests/test_overseas_studio_execution.py
........................................................                 [100%]
56 passed, 2 warnings in 9.52s
```

两个 warning 为 Starlette/httpx 和 anyio BlockingPortal 弃用。56 项通过不能覆盖本轮反例；S1-01 另行调用真实收取器的错误输出已原样列出。

以下为已读取的主 Agent 提供日志摘录，未冒充本 reviewer 重跑：

```text
# output/native-studio-backend-pg-20261014.log
66 passed, 2 warnings in 48.13s
# output/native-studio-frontend-tests.log
ℹ tests 356
ℹ pass 356
ℹ fail 0
ℹ skipped 0
# output/native-studio-frontend-final-typecheck.log
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
> hengxin-smart-image-frontend@0.2.32 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
# output/native-studio-build.log
✓ built in 37.70s
# output/native-studio-browser.log
PASS: incremental pages/updates, full messages/long text, safe Markdown and delivery images, failure/cancel/reload, scroll follow/history, draft selection persistence, idempotent new conversation, 390px
# output/native-studio-refresh-browser.log
PASS: idle/active/completed polling, manual spinner, silent auto refresh, error recovery, draft/attachment/skill/scroll persistence; full descriptions desktop/mobile
# output/native-studio-release-tests.log
Result: 73 passed, 26 subtests passed in 3.01s
Exit code: 0
Result: 1 failed, 242 passed, 1 skipped, 117 subtests passed in 13.78s
Exit code: 1
```

主 Agent 提供 typecheck/build exit 0，已读编译日志无编译错误。发布全目录存在 `scripts/release/test_release_native.py:100` 历史 overlay 顺序断言失败；日志说明 HEAD 和当前 image-inputs-frontend.py 已以 materials overlay 结尾，而旧断言期待 annotation；两文件非本次修改。此处如实记失败，不写发布全目录全绿。

本报告编写时 `output/native-studio-backend-full-final.log` 仍在追加，尚无最终 summary；**不将最终整库回归标记为已完成**。本轮已存在 HIGH，即使随后整库全绿也不能解除此阻断。

## Stage 2

**未执行。** `.agents/skills/code-review/SKILL.md` 明确要求 Stage 1 有 HIGH 则停止，因此没有出具代码质量、全量安全扫描、测试真实性全审或打开邻居页面实时视觉对比的 PASS。读到相关源码不等于完成 Stage 2。

修复交由主 Agent 按 Stage 1 失败路由处理；重新固定快照后由 fresh reviewer 从 Stage 1 开始。本报告不能用于 review-approve，未写 `.needs-review`。
