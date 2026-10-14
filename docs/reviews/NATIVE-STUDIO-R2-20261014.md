# 原生工作台独立审查 R2（2026-10-14）

- candidateId：`44eb80aab167f00adc67f56985a9e4b6957347d0866b8fb23a470298a7833a08`。
- **Stage 1：FAIL（1 项 HIGH）。Stage 2：未执行。不得登记两阶段 PASS。**
- 使用 `.agents/skills/code-review/SKILL.md`，遵守 `docs/HARNESS-REVIEW.md`。本轮重新读取需求和实现，独立运行收取器复现及后端专项；未修改实现、提交、部署、批准或调用收费模型。
- 范围：当前全部 Git diff/untracked 源码，包括海外 studio、runner、db/cleanup、0015 迁移及测试；工作台前端/API/Markdown/轮询及测试、依赖与锁文件；0.2.32 打包、新迁移发布脚本及测试。依据 Product-Spec.md:1100 原生工作台迭代、DEV-PLAN.md 最后迭代、docs/NATIVE-STUDIO-RELEASE-20261014.md。
- 开始时独立 `review-status` 返回 `currentId` 与上述候选一致、`approved:false`。主 Agent 收到问题后确认冻结实现，等待本报告；结束时再次核对，候选仍相同。普通 Markdown 报告不属于代码快照。

## Stage 1 阻断问题

### HIGH S1-01：图片文件名可解除前文“草稿，暂不交付”范围

需求原文（Product-Spec.md:1106）：“临时图、草稿、试验图、中间文件不显示、不归档”；“Markdown正文中的图片也遵守同一交付门禁”。

位置：`hengxin-smart-image/backend/app/overseas/studio/delivery.py:21`、`:40`、`:51`。

`FORMAL` 检测整个 Markdown inline token 的原始 `content`，包含图片 URL。`![预览](/work/final.png)` 的文件名匹配 `\bfinal\b`，于是 `elif formal` 新建 `blocked=False` 的范围，将前文明确的非交付状态清除。此处没有任何实际“正式交付”声明，仅文件名改变就会改变交付资格。

可达输入：CLI 成功完成、本轮真实有效 PNG、合法当前 session、无错误。最终回复：

```markdown
这是草稿，暂不交付。

![预览](/work/final.png)
```

**独立实跑证据**：临时目录内建立 work/home 和 `.codex/generated_images/session`，创建 12×13 蓝色 PNG，直接调用生产 `collect_delivery()`，不是仅测试正则。`turn_completed=True`、`error=None`、`session_id='session'`、`baseline={}`。下列为原始 JSON 输出（使用 Unicode 转义避免终端编码干扰）：

```text
{"final_text": "\u8fd9\u662f\u8349\u7a3f\uff0c\u6682\u4e0d\u4ea4\u4ed8\u3002\n\n![preview](/work/a.png)", "accepted": [], "warnings": []}
{"final_text": "\u8fd9\u662f\u8349\u7a3f\uff0c\u6682\u4e0d\u4ea4\u4ed8\u3002\n\n![preview](/work/final.png)", "accepted": ["/work/final.png"], "warnings": []}
{"final_text": "## \u4e2d\u95f4\u6587\u4ef6\n![preview](/work/a.png)", "accepted": [], "warnings": []}
{"final_text": "## \u6b63\u5f0f\u4ea4\u4ed8\n![result](/work/final.png)", "accepted": ["/work/final.png"], "warnings": []}
```

**R1 修复效果**：原来的 a.png 跨段落草稿和“中间文件”标题反例均已拒收；明确正式交付对照组仍接收。但将相同草稿图片命名为 final.png 即可再次穿透，故不能认为交付门禁修复完成。

**影响链**：`backend/app/overseas/studio/execution.py:88` 收取、`:117` 写 Picture；`queries.py:51` 返回图片 DTO；`frontend/src/views/overseas/studio/studio-markdown.ts:36` 将 sourcePath 映射成真实图片；`StudioTurns.vue:12` 展示和选取，`backend/app/overseas/studio/service.py:93` 允许 SKU 归档。下游鉴权不能纠正图片分类错误。

**修复验收**：正式范围切换必须依据实际说明文字，不能由路径、链接目标、图片 alt、代码等引用数据触发。相同非交付声明搭配 a.png/final.png/deliverable.png 等文件名，应全部拒收；真正独立的正式交付段落仍可重新进入交付范围。补 collector 与真实 runner→API 用例，保持 reply/transcript 原文完整，并证明非交付图片不进入 Picture/DTO/正文渲染。不得通过改写用户输入或强制模型交付话术规避。

现有 `tests/test_studio_formal_delivery.py:61` 使用 a.png；`tests/test_overseas_studio_execution.py:100` 使用 output0.png，均未覆盖文件名触发范围切换。独立运行 47 项全通过仍可复现上述错误。

## Stage 1 逐项核对

以下路径中 backend/、frontend/ 前缀均位于 `hengxin-smart-image/`。匹配仅指该项代码和所列验证范围，整个 Stage 1 仍 FAIL。

| 需求/验收项 | 结论 | 代码和证据 |
|---|---|---|
| 普通消息原样，首轮仅指定人设 | 匹配 | `backend/app/overseas/studio/execution.py:47`、`:61`；`tests/test_overseas_studio_conversations.py:37` 真实 worker 捕获两轮 prompt，含前后空白精确比较；本轮专项通过。 |
| 仅主动附件/Skill，不追加商品背景、步骤、数量、交付格式 | 匹配 | `studio/service.py:51`、`:63` 只保存所选输入；`execution.py:64`–`:68` 只追加选中引用。`test_overseas_studio_execution.py:66` 原附件验证、本轮专项通过。 |
| 原 CLI 隔离、会话归属与权限 | 匹配 | `execution.py:19` 独立 conversation home；`:38` workspace-write；`queries.py:14` 统一 task.read/design；`transcript.py:91` claim/lease 与 task/turn/conversation 核验。`test_overseas_studio_transcript.py:42` 撤权 403、`:83` 错会话拒收，本轮通过。 |
| 所有公开 assistant 文字完整持久化并按首次出现顺序显示 | 匹配 | `studio/transcript.py:15`、`:40` Text 快照；`queries.py:92` 递增 ID；`studio-transcript.ts:4` 同轮 item 更新原位替换；长文、代码、多条与更新事件专项通过。 |
| 公开摘要与工具状态，禁止任意 stdout/隐藏推理 | 匹配 | `transcript.py:30` 仅公开 reasoning.text；`:35` 固定工具标签，未知种类忽略；`test_overseas_studio_transcript.py:42` 的 SECRET/PRIVATE_STDOUT/PRIVATE_CHAIN 均不进入 API，本轮通过。 |
| Markdown、代码、链接、HTML 不执行，图片下载授权 | 匹配，但上游分类有 HIGH | `studio-markdown.ts:4` html:false、`:13` 图片批准映射、`:18` 本地链接无映射仅显示文字；`api/overseas/studio.ts:33` 精确 task/picture URL DTO 校验；R2 S1-01 会污染批准映射。 |
| 近实时回显、分页、半行 UTF-8、重连去重 | 匹配 | `transcript.py:54` 持久 byte offset，完整行后才推进；`queries.py:94` 500+1 分页；`use-studio.ts:34` 活跃轮 1000ms、`:42` 连续读页；本轮半行/502 条/重复读取测试通过。 |
| 过程默认展开、终态可折叠 | 匹配 | `StudioTranscript.vue:4` details open 绑定 running；`StudioTurns.vue:30` 状态映射。独立目视 `output/playwright/studio-native/running-markdown.png`，执行消息展开可读。 |
| 看历史不强拉底，底部跟随 | 匹配（提供的隔离浏览器证据） | `StudioTurns.vue:37`–`:41` 更新前测位置、更新后跟随；`tests/studio-native.browser.mjs:74`、`:83` 实际 scrollTop 断言；日志 PASS。 |
| 隐藏/卸载停止请求，恢复补齐 | 匹配 | `use-studio.ts:62` visibility abort/恢复；`:105` 卸载清理；`:34` 可见性/完成态调度。前端 356 项与刷新浏览器日志通过，未自行重跑全套。 |
| 失败、停止、未知执行仍保公开文字 | 匹配 | `runner.py:158` final_poll；`transcript.py:49` 独立保存；`tests/test_overseas_studio_transcript.py:96` failure/cancel/crash 真实 runner→数据库/API，本轮专项通过。 |
| 图片无效/保存失败不抹文字并明确告知 | 匹配 | `execution.py:89` 整体异常转 warning，逐图保存异常隔离；`:109` 原文结果；`test_overseas_studio_transcript.py:125` 故障收取保文，本轮通过。 |
| 仅成功 final 明确引用；不扫描发现图片 | 匹配 | `delivery.py:82` 完成/error/final 条件，`:93` 只遍历 references；本轮 `test_studio_formal_delivery.py:28` 未引用文件不收、失败/未完成不收。 |
| 有效性/归属/历史隔离、重复图去重 | 匹配 | `delivery.py:97` `_local_file`，`:102` 有效图片校验；`backend/app/execution/final_delivery.py:45` 输入/Skill/路径/旧会话/历史边界；本轮相关 collector 专项通过。 |
| 草稿/临时/试验/中间图片不得显示归档，正文同门禁 | **不匹配 HIGH** | `delivery.py:40`、`:51` 图片 URL 触发正式范围；实跑证据见 S1-01。R1 原始两例虽已修复，最终要求仍未满足。 |
| 新会话保历史、材料、图片、归档 | 匹配 | `service.py:73` 仅添加 Conversation；`queries.py:67` 查询所有历史轮；`test_overseas_studio_conversations.py:16` 历史/材料/独立 home，`:57` 多会话删除保归档，本轮通过。 |
| active/uncertain 不 reset，pending 不重复，幂等/并发 | 匹配 | `service.py:26` 非 TERMINAL 均阻止；`:16` actor/task lock 与幂等；`use-studio.ts:14` pending 锁、`:79` 未知响应保原 key；PG 用例 `test_overseas_studio_postgres.py:15`、`:33` 真实竞争，提供 66 passed、0 skip 记录。 |
| 会话分界、人设仅新上下文首次；确认后清草稿 | 匹配 | `StudioTurns.vue:5`、`:19` 分界；`OverseasStudio.vue:20` 确认说明；`use-studio.ts:76` 成功后清空；`execution.py:61` 无 previous_session 才人设。新会话专项通过。 |
| 预览、引用修改、按 SKU 归档保留 | 匹配，但可归档集合受 S1-01 污染 | `StudioTurns.vue:14` 预览、`:15` 修改；`use-studio.ts:102` 引用；`service.py:93` SKU 归属、重复保护和独立 archive protect。新会话/归档保留专项通过。 |
| 0.2.31 上传、北京时间、Skill 名称描述、刷新行为保持 | 匹配（改动边界及回归） | `api/overseas/studio.ts:44` 原 20 MiB 与扩展名；`OverseasStudio.vue:14` 复用 StudioSkillSelect；`use-studio.ts:53` 手动/自动状态分离。北京时间公共实现与 Skill 包无本轮变化；前端 356 passed、既有刷新/Skill 浏览器 PASS。 |
| 桌面/390px、引导文案对应真实 handler | 匹配（截图/隔离测试范围） | `OverseasStudio.vue:5`、`:13`、`:20` 操作与 handler；独立目视 running-markdown.png、mobile-confirm.png，代码/链接和执行消息可读，窄屏确认框按钮与文字未越界；浏览器 `:115` 页宽断言。没有执行生产登录验收。 |
| 0014→0015、旧数据保持、重复迁移、国内0028不变 | 匹配（隔离 PG 证据） | `backend/migrations/overseas/versions/0015_studio_transcript.py:10` 添加表/列并取消 task 唯一约束；`:48` 旧 reply 去重回填，`:56` 禁降级；`test_overseas_studio_migration.py:16` 真实旧数据逐列比较与国内快照比较；提供 PG 日志 66 passed。 |
| 0.2.32 同安装测试镜像用于 api/migrate | 匹配（实现及隔离发布测试） | `scripts/release/package-overseas.py:16`、`:181`；`native-studio-runtime.py:37` 同 identity overlay、`:80` 重检安装测试 image；`overseas-deploy.py:46` 安装测试镜像凭据；发布重点 73 passed。 |
| 双轮排空、完整备份、失败关闭、仅前进、不动国内/Skill | 匹配（实现及隔离发布测试） | `native-studio-deploy.py:50` 关闭/停止→排空→backup COMPLETE→迁移；`overseas-hotfix-deploy.py:70` 双轮排空；`native-studio-runtime.py:118` 异常重关入口并记录实际 schema；`:70`、`:111` Skill 验证；无国内迁移/重启。生产未执行，不算上线验收通过。 |

### 漂移与未实现

- 未发现本范围新增候选图区或无需求业务页面。新增 Transcript 表、增量 API、Conversation API、sourcePath 和发布脚本分别对应本轮完整文字、重置上下文、图片映射及迁移发布需求（`models.py:64`、`router.py:32`、`:37`、`queries.py:51`）。
- 正式交付分类未完整实现，见 HIGH S1-01。生产切换及真实页面验收仍待后续执行；不得将隔离测试或本报告当作部署成功证据。

## 验证与编译原始输出

Reviewer 独立运行（退出码 0）：

```text
.venv/Scripts/python.exe -m pytest -q tests/test_studio_formal_delivery.py tests/test_overseas_studio_transcript.py tests/test_overseas_studio_conversations.py tests/test_overseas_studio_execution.py
...............................................                          [100%]
47 passed, 2 warnings in 6.52s
```

两条 warning 为 Starlette/httpx 和 anyio BlockingPortal 弃用。47 项通过不覆盖 S1-01 的文件名反例。收取器独立复现退出码 0，错误接收结果已原样列出。

以下为本轮实际读取的主 Agent 验证日志摘录，未冒充 reviewer 重新执行：

```text
# output/native-studio-backend-full-r2.log
2047 passed, 188 skipped, 15 warnings in 250.78s (0:04:10)
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

主 Agent 提供 typecheck/build exit 0；已读取日志中无编译错误。完整后端 188 项条件 skip 不计已验证；3 条后加的真实 runner 门禁测试包含在本 reviewer 的 47 项实跑内。发布全目录有既存 `scripts/release/test_release_native.py:100` overlay 顺序断言失败，提供日志说明 HEAD 与当前 image-inputs-frontend.py 均以 materials overlay 结尾而旧断言期待 annotation；此处如实记录失败，未将全目录写为全绿。

## Stage 2

**未执行。** Stage 1 HIGH 已触发停止规则。本轮不出具文件大小/any/安全扫描/测试真实性全审或邻居页面实际视觉对比的 PASS。修复后必须重新固定快照，由 fresh reviewer 从 Stage 1 开始审查；本报告不能用于 review-approve。
