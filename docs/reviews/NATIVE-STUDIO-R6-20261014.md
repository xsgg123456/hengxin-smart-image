# 原生工作台独立审查 R6（2026-10-14）

- candidateId：`fbd870cfae4572f463a05a867c529fe732dd55ab48521a61ee79706867f3e859`。
- **Stage 1：FAIL（1 项 HIGH）；Stage 2：已做检查记录如下，不给 PASS。不得登记两阶段 PASS。**
- 范围：海外 studio、execution/runner、db、任务清理、0015 迁移及测试；前端 studio API/组件/Markdown/轮询/版本依赖及测试；native-studio deploy/runtime/package-overseas 及测试。不是历史全产品重审。
- 依据：已读取 AGENTS.md、`.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、`Product-Spec.md:1100` 最后原生工作台章节、DEV-PLAN.md 最后迭代、`docs/NATIVE-STUDIO-RELEASE-20261014.md`。R1–R5 报告只作为缺陷历史，不替代本轮核查。
- 开始及最后一次 `review-status` 的 currentId 均与上述 candidateId 一致。没有修改实现、批准、提交、部署或生产模型调用。只创建本报告和 output 下的独立浏览器脚本/截图；自己启动的 127.0.0.1:3026 预览已停止，未操作用户 Chrome。

## Stage 1 阻断

### HIGH S1-01：图片 alt 中的 HTML 字符实体仍可绕过否定交付

需求 `Product-Spec.md:1106`：“临时图、草稿、试验图、中间文件不显示、不归档”，“Markdown正文中的图片也遵守同一交付门禁”。Markdown 字符实体不能将一个否定交付引用变成正式图片。

位置：`hengxin-smart-image/backend/app/overseas/studio/delivery.py:47` 的 `visible_text()` 已递归，但 `:51` 的文本叶节点白名单只有 `text/code_inline/image`，遗漏 Python MarkdownIt 的 `text_special`。图片 alt 子树中的 `&#111;` 解析为 `text_special(content='o')`，随后被丢弃。因此 `n&#111;t **final images**` 进入规则时变成 `nt final images`，原文又因字符实体而不匹配 `not`；`:63` 返回非否定，`:104` 引用解析及 `:125` 收取继续执行。

独立复现使用 TemporaryDirectory、本轮 work/home、`.codex/generated_images/session`、空 baseline，以及 Pillow 创建的真实 12×13 PNG。直接调用生产 `collect_delivery`，summary 为成功完成、无 error、session_id=session；没有绕开文件归属或真实图片校验。首轮带拒收断言的探针退出 1。随后不带断言的诊断退出 0，原始输出：

```text
plain accepted= [] warnings= []
render= <p><img src="/work/final.png" alt="not final images" /></p>
visible_text= 'not final images'
entity-alt accepted= ['/work/final.png'] warnings= []
render= <p><img src="/work/final.png" alt="nt final images" /></p>
visible_text= 'nt final images'
token image 'n&#111;t **final images**'
token text 'n'
token text_special 'o'
token text 't '
token strong_open ''
token text 'final images'
token strong_close ''
token text ''
entity-body accepted= [] warnings= []
entity-title accepted= [] warnings= []
hardbreak accepted= [] warnings= []
setext-parent accepted= [] warnings= []
positive accepted= ['/work/final.png'] warnings= []
```

输入分别是：

```markdown
![not final images](/work/final.png)
![n&#111;t **final images**](/work/final.png)
```

语义与渲染需要准确区分：上面 `render` 是 Python MarkdownIt 自带 renderer，它也遗漏该 alt 实体，实际输出 `nt`，不能称它已显示 `not`。独立使用已安装的前端 markdown-it 15.0.2 默认 renderer 解析同一输入，原始输出为：

```text
JS standard render= <p><img src="/work/final.png" alt="not final images"></p>
```

正式前端使用自定义 renderer，`frontend/src/views/overseas/studio/studio-markdown.ts:15` 转义 `token.content`，会保留 alt 原始写法；本报告不把默认 JS renderer 冒称正式页面。缺陷是后端丢失已解析出的否定字符、把该文件授予正式交付身份。影响链：`backend/app/overseas/studio/execution.py:93` 保存图片，`:118` 创建 Picture，`queries.py:51` 返回正式图片 DTO；前端 `StudioTurns.vue:12` 提供选图，服务端 `service.py:93` 支持归档。因此可突破“不显示、不归档”的核心边界。

已有 152 项全部通过，但 `backend/tests/test_studio_formal_delivery.py:162` 的新增 alt/title 组没有字符实体；runner→API 反例在 `test_overseas_studio_execution.py:94` 同样未覆盖。R6 已修好 R5 的强调嵌套，遗漏另一种真实 token 类型。

修复验收：按解析器的完整文本节点语义提取内容，包含 `text_special`；对 alt、嵌套 alt、下载包裹、实体及转义建立系统性对照，否定仍优先，原文完整保留，肯定正式交付对照仍成功。补 collector 和真实 runner→API 断言，重新固定 candidate 后从 Stage 1 重审。

## Stage 1 逐项覆盖

下表 backend/、frontend/ 相对 `hengxin-smart-image/`。完整实现仅指该条代码与所列证据，不代表总体验收通过。

| 条目 | 结论及本轮证据 |
|---|---|
| 普通消息原样；每新 CLI 会话仅首次人设 | 完整实现。`backend/app/overseas/studio/execution.py:62`–`:69` 条件拼接；`tests/test_overseas_studio_conversations.py:37` 捕获准确 prompt、保留前后空白。本轮专项通过。 |
| 只引用主动选择的附件/Skill；不重复背景/步骤/数量/强制格式 | 完整实现。`studio/service.py:51`–`:64` 只读取显式 IDs；`execution.py:53`–`:68` 只追加必要路径；未修改 Skill 包。本轮执行测试通过。 |
| CLI 隔离、归属、权限保持 | 完整实现。`execution.py:19` 按 conversation home，`:40` workspace-write；`transcript.py:90` claim/lease/task/conversation 校验；`queries.py:14` 任务权限。专项包含撤权、错误 claim 和 session。 |
| 新对话重置上下文、保历史资料/图片/归档 | 完整实现。`service.py:73` 只新增 Conversation，`queries.py:63` 返回历史；`test_overseas_studio_conversations.py:16` 验新 home/不 resume/保素材，`:57` 验多会话清理后归档仍可访问。本轮通过。 |
| active/uncertain 阻止；并发和幂等 | 完整实现。`service.py:16` 锁与幂等，`:26` 非 TERMINAL 拦截；`use-studio.ts:14` 锁、`:79` 未知结果原 key 重试。本轮后端/前端/浏览器通过。真实 PG 并发源码 `test_overseas_studio_postgres.py:17`、`:34`，提供 PG 日志 66 passed，未重跑 PG。 |
| 多条/更新公开消息完整顺序持久化；公开摘要/工具状态 | 完整实现。`transcript.py:15` 白名单、`:41` 追加快照、`:54` 完整读取；`queries.py:92` 有序游标；`studio-transcript.ts:4` 按 turn/item 替换且不移动。独立专项包含长文、UTF-8 半行、隐藏字段；浏览器多条/长文通过。 |
| Markdown 代码/链接、HTML 禁止执行、下载鉴权 | 部分实现。`studio-markdown.ts:4` 关闭 HTML，`:18` 本地链接仅批准映射可导航，API `studio.ts:33` 绑定 task/picture；XSS 测试和浏览器通过。但正式图片映射受 S1-01 污染，不能整体通过。 |
| 1 秒级播报、分页/重连不丢失不重复 | 完整实现。`use-studio.ts:34` 活跃 1000ms，`:43` 连续翻页；`transcript.py:54` 字节游标、`runner.py:129` final_poll；`queries.py:95` 500+1。独立测试含 502 条、断线、更新和尾行。 |
| 执行中展开、终态可折叠；历史滚动不拉底 | 完整实现。`StudioTranscript.vue:4` 受 running 控制，`StudioTurns.vue:37`–`:42` 更新前测距/更新后跟随。本轮真实浏览器 scrollTop 和折叠断言通过。 |
| 隐藏/卸载停请求，恢复补齐；静默刷新 | 完整实现。`use-studio.ts:53` 手动 loading 分离，`:62` abort/恢复，`:105` 卸载。独立 356 测试与新旧两份浏览器通过。 |
| 图片失败不丢文字、独立告知；失败/取消保文 | 完整实现。`execution.py:85`–`:108` 逐图错误隔离、deliveryError；`runner.py:158` 异常尾读。专项真实 runner→DB/API 覆盖 failure/cancel/crash/收取失败。 |
| 仅成功本轮最终引用、不扫描发现图片；有效性/历史/归属 | 文件来源门禁完整。`delivery.py:125` 成功 final 门禁，`:138` `_local_file` 与图片字节校验；`execution.py:37` baseline 只排除历史。独立专项包括跨会话/inputs/Skill/坏图混合/无引用。 |
| 临时/草稿/试验/中间不显示不归档，无候选区；正文同门禁 | **部分实现/HIGH**。`delivery.py:51` 遗漏 text_special，见 S1-01。未新增候选区。 |
| 保留预览、引用修改、SKU 归档 | 操作实现存在。`StudioTurns.vue:14` 预览、`:15` 修改引用，`use-studio.ts:102` 引用，`service.py:93` SKU 与归档保护；但可选择集合受 S1-01 污染。 |
| 新对话确认/分界/成功清草稿；真实引导；桌面与390px | 完整实现。`OverseasStudio.vue:20` 确认，`StudioTurns.vue:5`/`:19` 分界，`use-studio.ts:75` 成功清空。本轮隔离浏览器确认失败保草稿、幂等恢复、新消息原文、390px 控件在界内。 |
| 0.2.31 上传不限扩展、北京时间、真实 Skill 名描述保留 | 本次差异未修改图需上传/北京时间/Skill 包；工作台选择 `OverseasStudio.vue:14` 保留。独立全前端 356 及刷新/完整 Skill 描述浏览器通过。工作台附件限制不是图需上传规则。 |
| 0014→0015 增量保历史、国内0028/身份不变 | 实现匹配。`migrations/overseas/versions/0015_studio_transcript.py:10` 增量、`:48` 幂等回填、`:56` 禁降级；`tasks/cleanup_records.py:23` 清理 transcript。提供 PG 日志 66 passed，生产迁移未执行。 |
| 0.2.32、安装测试同一镜像用于 API/migrate | 实现匹配。`native-studio-runtime.py:12` 固定版本、`:37` 双服务同 identity、`:80` 迁移前重核；`member-release-runtime.py:99` 要求 INSTALL_TEST_IMAGE_ID 一致，`overseas-deploy.py:25` 实际镜像测试。本轮发布专项通过，最终安装实测待修复通过/提交之后、切换之前执行。 |
| 关接纳、双排空、完整备份、迁移切换 | 实现匹配。`native-studio-deploy.py:50` 关闭/停止 API，`:55` 排空，`:58` COMPLETE 备份后迁移；独立发布专项通过，不冒充执行过生产操作。 |
| 失败关入口、仅前进、不降库/盲恢复/重放 | 实现匹配。`native-studio-deploy.py:20` 重放门禁、`:37` 恢复约束；`native-studio-runtime.py:118` 失败关闭及实际 schema 记录；独立故障发布测试通过。 |
| 14 Skill/181文件不变，国内身份不动，不发生产付费调用 | 本次代码差异不含包；`native-studio-runtime.py:70`/`:111` 验证 Skills，`native-studio-deploy.py:69` 仅海外切换、`:98` 验资源不变。本 reviewer 无生产操作，现场最终不变性仍待发布验收。 |

未实现：未发现整项新增缺失。部分实现：图片否定交付门禁及受其影响的展示/归档链。Spec 漂移：`models.py:64` Transcript、`router.py:33` 新会话、`:38` 增量 API 均有需求依据，未发现无依据的新页面/表/候选区。完整交付仍缺修复、重新审查、提交、同镜像安装回归与生产验收。

## 已执行的 Stage 2 检查记录（不构成 PASS）

本轮在常规专项和逐条源码核对未发现 HIGH 时进入 Stage 2；最后补充独立语法边界探针才发现 S1-01。发现后停止继续检查并退回 Stage 1，保留真实做过的证据，不将它们包装为两阶段通过。

- 代码质量：studio 生产模块 0–150 行；新增 transcript 109 行、delivery 150 行、renderer 45 行、merge 13 行、composable 107 行；职责按收取/持久化/查询/交互分离。`frontend/src/api/overseas/studio.ts:39` 运行时验证增量 DTO，`:33` 限定图片 URL；扫描未发现新增 TypeScript any（AbortSignal.any 是 API 名称）、eval 或硬编码密钥。`git diff --check` 无空白错误，只有既有 CRLF→LF 提示。S1-01 说明解析器文本节点处理仍不完整，不据长度/类型检查给总 PASS。
- 测试真实性：`test_overseas_studio_transcript.py:43` 使用真实文件字节、后端事务及 HTTP 返回，半行 UTF-8 前提可达；`:94` 的 failure/cancel/crash 分别走真实 runner，fake 仅代替外部收费执行；`test_overseas_studio_execution.py:94` 真建 PNG、走 collector→存储→API；`test_overseas_studio_postgres.py:17` 使用 Barrier/独立 Session，不把 SQLite 顺序运行冒称 PG 并发。浏览器 fixture `frontend/tests/studio-native.browser.mjs:28` 拦截请求，但运行正式构建/真实 Vue DOM；坏网络、新会话、失败保文、分页/更新均有行为断言。盲区是 S1-01 的实体节点，生产收费 CLI 端到端本轮未执行。
- 安全检查：`StudioMarkdown.vue:1` 是唯一新增 v-html 汇点，来源限定为 `studio-markdown.ts:4` 的 html:false renderer，自定义属性经 `:6` escape，非批准本地图/远程图不加载，外链 noopener/noreferrer。已对照 [markdown-it 官方安全说明](https://github.com/markdown-it/markdown-it/blob/master/docs/safety.md) 的关闭 HTML 方案，并独立运行 XSS/协议/授权 URL 测试；没有仅凭 v-html 词命中判漏洞。`queries.py:15` 读取权限、`router.py:14` 写入 browser_request、`transcript.py:97` 归属、`delivery.py:138` 文件校验均已核对。SQL 是 ORM 或 `0015_studio_transcript.py:48` 常量 SQL，未见新增用户输入字符串拼接。交付分类缺陷仍是核心阻断。
- 依赖边界：提供的 `output/native-studio-dependency-audit.json` 为 critical 0/high 70/moderate 48/low 5；主 Agent 标注与 0.2.31 一致。这里保留既有告警，不宣称全依赖无漏洞。
- 实际邻居视觉对比：独立启动正式 dist，隔离 Chromium 中打开工作台 `/overseas/tasks/t`，通过“返回任务列表”实际进入邻居 `/overseas/tasks`，目视两张新截图：`output/playwright/studio-native-r6-review/studio.png`、`neighbor.png`。代码依据 `OverseasStudio.vue:4`/`studio.css:39`–`:41` 与邻居 `OverseasWorkspace.vue:14`。两者白底卡片 16px 圆角；同为启用状态主按钮 RGB(93,135,255)、白字、6px 圆角、14px 字号、32px 高；字体一致。工作台压缩标题扩大对话符合既有批准方向。390px 新对话截图 `output/playwright/studio-native/mobile-confirm.png` 已目视，确认内容/按钮在界内，无横向溢出。初次比较误选了禁用归档按钮，其浅蓝不等于视觉回归；改为启用按钮对照后通过，没有修改产品代码。

## 测试与编译原始输出

本 reviewer 独立执行：

```text
# backend：正式交付 + transcript + conversations + execution，exit 0
152 passed, 2 warnings in 9.92s
# frontend pnpm test，exit 0
ℹ tests 356
ℹ suites 0
ℹ pass 356
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8921.2879
# frontend pnpm typecheck，exit 0
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
> hengxin-smart-image-frontend@0.2.32 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
# release：native-studio deploy/runtime + overseas-hotfix + package，exit 0
73 passed, 26 subtests passed in 3.55s
# 原生工作台隔离浏览器，exit 0
PASS: incremental pages/updates, full messages/long text, safe Markdown and delivery images, failure/cancel/reload, scroll follow/history, draft selection persistence, idempotent new conversation, 390px
# 旧刷新/Skill 隔离浏览器，exit 0
PASS: idle/active/completed polling, manual spinner, silent auto refresh, error recovery, draft/attachment/skill/scroll persistence; full descriptions desktop/mobile
# reviewer 自建邻居视觉 fixture，exit 0
PASS: actual built studio and neighboring task-list rendered in isolated browser; same card/primary-button design tokens
```

后端 2 warnings 是 Starlette/httpx、anyio BlockingPortal 弃用。以上通过不覆盖 S1-01。

已读主 Agent 提供日志，以下不是本 reviewer 重跑：

```text
# output/native-studio-backend-pg-20261014.log
66 passed, 2 warnings in 48.13s
# output/native-studio-backend-full-r5.log（仅 R5 旧快照）
2141 passed, 188 skipped, 15 warnings in 242.46s (0:04:02)
# output/native-studio-build.log（前端本轮未变化）
✓ built in 37.70s
# output/native-studio-release-tests.log（发布目录全回归）
Result: 1 failed, 242 passed, 1 skipped, 117 subtests passed in 13.78s
Exit code: 1
```

发布全目录失败为 `scripts/release/test_release_native.py:100` 旧 overlay 顺序断言；提供证据指出 HEAD 已以 materials overlay 结尾，本次两文件未变。保留这一失败，不能写“全部测试全绿”。R5 整库不是 R6 整库；R6 实际安装镜像测试尚待后续，不计已通过。生产任务为空来自主 Agent 的实查，本 reviewer 没有操作生产会话，不能称在生产完成新对话/生图现场验收。

**结论：修复 S1-01 后重新固定快照并重新派发独立审查；本报告不授权 review-approve，不写 `.needs-review`。**
