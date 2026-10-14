# 原生工作台 R9 独立两阶段审查（2026-10-14）

- candidateId：`91e4e338da03ba37009b74a37450ebbcee4f4a07b901a490b24035b00bb9c7dc`。
- **Stage 1：PASS；Stage 2：PASS。** 未发现本候选范围内需修复的 HIGH/MEDIUM 问题。该结论批准代码审查，不代表生产安装测试或部署已经完成。
- 范围：海外 studio、execution/runner、db、任务清理、0015 迁移和相关测试；前端 studio API、组件、Markdown、轮询、版本依赖和测试；native-studio deploy/runtime、package-overseas 和相关测试。不是历史全产品重审。
- 原文依据：AGENTS.md、`.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`、`Product-Spec.md:1100` 原生工作台完整章节、`DEV-PLAN.md:1372`、`docs/NATIVE-STUDIO-RELEASE-20261014.md:1`；视觉继承 Design-Brief 与现有工作台/任务列表。旧失败报告用于定位回归，未继承旧阶段 PASS。
- 开始与收尾 `review-status` 的 currentId 均等于本 candidateId。未改实现、提交、批准、部署或调用生产模型。仅写本报告与 output 隔离证据；使用主 Agent 的本地正式 dist 3026 预览和一次性 Chromium，未操作用户 Chrome 或停止服务。

下文 `backend/`、`frontend/` 均相对 `hengxin-smart-image/`；其他路径相对仓库根目录。

## Stage 1：逐条符合性

| Spec 条目 | 结论与代码、验证证据 |
|---|---|
| 普通消息原样；每个新 CLI 会话首轮只有一句协作人设 | 完整实现。`backend/app/overseas/studio/execution.py:60` 按 previous_session 决定人设，`:64` 保留原始 text；`backend/tests/test_overseas_studio_conversations.py:38` 精确比较首轮/续轮及前后空白。独立专项通过。 |
| 只主动选附件/Skill；不重复商品、步骤、数量或强制交付格式；不改 Skill | 完整实现。`studio/service.py:51` 仅读取显式 ID，`execution.py:49` 仅复制本轮 inputs、`:65` 仅追加所选文件引用；本次差异无 Skill 内容改动。prompt 测试和浏览器原样发送/清空后的空引用断言通过。 |
| CLI 隔离和业务权限保持 | 完整实现。`execution.py:19` 独立 conversation home/精确 resume，`:40` workspace-write；`queries.py:14` 任务权限；`transcript.py:90` claim、lease、task、conversation 归属校验。独立 session/claim/越权测试通过。 |
| 新对话新上下文，保留历史文字、材料、正式图与归档 | 完整实现。`service.py:73` 只新增 Conversation；`queries.py:63` 读取全部历史；`test_overseas_studio_conversations.py:16` 验证新 home、不 resume、历史材料保留，`:55` 验多会话清理仍保独立归档。独立测试通过；浏览器新对话后长文仍在。 |
| 无在途才可重置，uncertain 阻止；幂等和并发 | 完整实现。`service.py:16` 父任务锁/请求幂等，`:26` 非 TERMINAL 阻断；`use-studio.ts:14` pending/active 锁，`:79` 未知结果保留相同 payload/key。独立 HTTP/前端/断线重试浏览器通过。真实 PostgreSQL 用例 `test_overseas_studio_postgres.py:15`、`:31` 使用 Barrier 与独立事务，已读取提供的 66 passed/0 skipped 日志，本 reviewer 未重跑 PG。 |
| 多条及更新的公开 assistant 文字完整、按序持久化 | 完整实现。`transcript.py:41` 追加事件快照，`:54` 持久字节游标；`queries.py:92` 顺序读取；`studio-transcript.ts:4` 按 turn/item 原位合并且拒绝旧快照回退。独立长文、半行 UTF-8、502 条分页、重复读取、跨轮同 itemId 测试通过。 |
| 公开摘要和工具状态；不暴露内部推理、原始工具输出或凭据 | 完整实现。`transcript.py:15` 只允许公开消息/摘要与工具名状态白名单；命令、arguments、aggregated_output、隐藏 reasoning 均不进入 DTO。`test_overseas_studio_transcript.py:43` 用 SECRET/PRIVATE 哨兵实测。公开 reasoning.text 的语义另与官方 SDK 定义核对，见 Stage 2。 |
| Markdown 代码/普通外链，HTML 不执行 | 完整实现。`studio-markdown.ts:3` html:false，`:5` 外链仅 HTTP(S)，`:12` 属性转义并带 noopener/noreferrer；`StudioMarkdown.vue:5` 唯一渲染来源。独立长文/HTML/恶意协议测试与正式 dist 浏览器通过。 |
| 增量近 1 秒、刷新/重连/分页不丢失不重复 | 完整实现。`use-studio.ts:34` 活跃 1000ms、`:43` 连续取页；`runner.py:129` 终态尾读；`transcript.py:54` 不提前消费半行。独立浏览器连续分页/更新/断线补齐/reload，以及后端 UTF-8/尾行测试通过。此为事件粒度目标，不承诺模型每秒发事件。 |
| 执行中过程默认展开，终态可折叠；历史滚动不拉底 | 完整实现。`StudioTranscript.vue:4` open 绑定 running；`StudioTurns.vue:37` 更新前测旧位置、`:38` 仅近底部跟随。独立浏览器断言 scrollTop=100 保持、底部跟随、终态折叠通过。 |
| 隐藏/卸载停请求，返回补齐；静默刷新保草稿和选择 | 完整实现。`use-studio.ts:53` 手动 loading 与自动读取分离，`:62` 隐藏 abort/可见同步，`:105` 卸载清理；`frontend/tests/overseas-studio.test.ts:111`、`:189` 实测隐藏/卸载/取消。357 项全量及新旧两份浏览器通过。 |
| 图片收取失败与文字独立；失败/停止已收文字仍可查 | 完整实现。`execution.py:85` 全体收取异常隔离、`:93` 逐图保存隔离、`:108` deliveryError；`runner.py:158` 异常尾读。独立真实 runner→DB/API failure/cancel/crash/收图异常与浏览器保文断言通过。 |
| 仅成功本轮 final 的明确引用；不扫描目录发现图片 | 完整实现。`delivery.py:145` 成功/final 门禁，`:149` 从 final Markdown 取引用；`execution.py:37` baseline 只排除历史，不作为发现源。无引用目录内 PNG、代码/裸路径、混合坏图专项通过。 |
| 文件真实有效、任务/会话归属和历史隔离 | 完整实现。`delivery.py:157` 复用 `_local_file`，`:163` validate_image；`backend/app/execution/final_delivery.py:47` 限定工作区/当前 session、保护 inputs/Skill/历史、拒绝路径逃逸/硬链接。独立真实 PNG、坏字节、跨会话、历史和受保护路径测试通过。 |
| 临时/草稿/试验/中间不入 Picture、不归档，无候选区 | 完整实现。`delivery.py:18` 否定分类、`:55`/`:70` 全递归可见文字/title/归一、`:85` 跨段及父标题作用域；`execution.py:117` 仅发布验证成功图片。279 专项和旧 15 类×5位置矩阵独立重跑全部拒收；正向 `/work/final.png` 仍接收。未新增候选区。 |
| R9：正文图片/本地链接仅文字，正式图片仅现有卡片展示 | 完整实现。`studio-markdown.ts:6` 无条件图片转文字、`:11` 本地链接转文字；`StudioTranscript.vue:3` 不再接收 pictures，`StudioTurns.vue:8`/`:9` 同样不传图片映射，`:14` 仅正式 Picture 卡片加载。独立正式 dist 同轮旧过程/拒收段/正式段复用 sourcePath：0 正文 img、1 卡片 img。R8 HIGH 已消除，见下方矩阵。 |
| 正式图预览、引用修改、SKU 归档保持 | 完整实现。`StudioTurns.vue:14` 预览、`:15` 修改；`use-studio.ts:102` 引用、`:84` SKU 归档；`service.py:93` SKU/重复归档约束及归档保护。独立 `test_overseas_studio.py:127` 验错误 SKU/部分归档/重复与冲突/ZIP/完成，6 项核心回归通过。 |
| 新对话确认、分界、成功清草稿；引导真实；桌面/390px | 完整实现。`OverseasStudio.vue:20` 明确保历史及清草稿，`StudioTurns.vue:5`/`:19` 分界，`use-studio.ts:75` 成功才清。输入/素材/Skill/发送/停止均有处理，无死引导。独立浏览器失败保草稿、相同 key 重试、成功清空、390px 控件/对话框无溢出通过，截图已目视。 |
| 0.2.31 任意扩展图需上传、北京时间、Skill 真名描述、静默刷新保留 | 范围内回归匹配。图需上传/全局时间/Skill 包不在本次实现差异内；`OverseasStudio.vue:14` 保留真实 Skill 选择器，`use-studio.ts:53` 保留静默读取。独立前端全量及刷新/Skill 桌面移动浏览器通过。工作台附件格式约束不是图需上传规则，未混淆两者。 |
| 海外0014→0015，历史保留；国内0028/身份不变 | 实现完整。`migrations/overseas/versions/0015_studio_transcript.py:10` 增量结构、`:48` 幂等历史回填、`:56` 禁降级；`tasks/cleanup_records.py:22` 删除顺序补 transcript。`test_overseas_studio_migration.py:15` 真实 PG 已填历史/重复迁移/国内快照不变；提供 PG 66 passed 已读，生产迁移待执行。 |
| 0.2.32，同一个实际安装测试镜像供 API/migrate | 实现完整。`scripts/release/native-studio-runtime.py:12` 固定版本，`:37` 两服务同 identity，`:80` 迁移前复核；`scripts/release/member-release-runtime.py:99` 比对 INSTALL_TEST_IMAGE_ID。独立发布测试通过。最终实际安装镜像全量仍必须在提交后、生产切换前执行。 |
| 关接纳、双排空、完整备份后迁移切换 | 实现完整。`native-studio-deploy.py:50` 关入口/停止 API，`:55` 双排空，`:58` COMPLETE 备份门禁，`:65` 迁移；`overseas-hotfix-deploy.py:69` 停 outbox 前后双轮稳定 DB/broker 核查。独立发布顺序/备份失败测试通过，未执行生产操作。 |
| 失败入口关闭、证据记录、只前进；禁止降库/盲恢复/未知重放 | 实现完整。`native-studio-deploy.py:20` 禁重放，`:37` 恢复约束；`native-studio-runtime.py:118` 独立记录关入口/API、阶段与实际 schema。独立13种阶段故障、迁移校验失败、关闭失败和镜像漂移测试通过。 |
| 14 Skill/181 文件、国内/身份不动；无生产付费调用 | 实现及执行边界匹配。代码差异无 Skill 包/国内身份实现；`native-studio-runtime.py:70`/`:111` 校验 Skills、`:110` 资源不变验证。审查所有浏览器业务 API 为本地隔离 fixture，无生产调用。现场14/181与国内身份不变仍须发布后验收。 |

未实现/部分实现：本候选范围内未发现。Spec 漂移：`models.py:64` 新 Transcript、`router.py:33` 新会话和`:38` 增量接口均有上述 Spec 依据；无未经要求的新页面、候选区或 Skill 改写。

### R8 结构性缺陷与历轮反例复核

| 形态 | R9 验证结果 |
|---|---|
| 同轮早期公开消息引用后来成为正式图的路径 | 正式 dist：旧消息为文字，0 正文 img。 |
| 最后回复同时有草稿段和正式段，复用相同 sourcePath | 正式 dist：全部正文引用为文字，仅1个正式 Picture 卡片 img。 |
| 本地源路径/API 图片路径/相对路径/自定义协议链接 | 独立 renderer 单测：无本地导航锚点，无 img；路径文字保留。 |
| 远程图片、data 图片、原始 HTML 图片 | 独立浏览器/单测：不加载 img，HTML 为文字；普通 HTTPS 网页链接保留。 |
| 后端前置/后置段落、标题、alt、title、嵌套title、实体/装饰/否定交付 | 279专项通过；旧75组合 accepted_positions 均为空，negative_parent/nested_title/entity 拒收。 |
| 只有真实正式交付引用 | 后端接受 `/work/final.png`；前端正式卡片仍加载，可走既有图片操作。 |

证据：`frontend/tests/studio-native.browser.mjs:103`、`frontend/tests/studio-markdown.test.ts:15`；独立运行日志 `output/native-studio-r9-review-browser.log`、`output/native-studio-r9-review-matrix.log`。不是以“没有临时字节入库”替代“旧过程位置不得显示图片”：两条均分别核查。

## Stage 2：代码质量、测试真实性、安全和视觉

- **代码质量 PASS**：`delivery.py:1` 169行，`transcript.py:1` 109行，`execution.py:1` 128行，`use-studio.ts:1` 107行，`studio-markdown.ts:1` 27行，发布脚本126/139行；受审生产文件均未超过300行。持久化/收取/查询/渲染/发布分离。`frontend/src/api/overseas/studio.ts:39` 验证增量DTO，`:33` 固定本任务图片URL。未发现新增 TypeScript any、eval 或密钥；AbortSignal.any/Python any 为函数名称。`git diff --check` exit0，仅既有 CRLF 提示。
- **测试真实性 PASS**：`test_overseas_studio_transcript.py:43` 真文件字节、事务和HTTP断言；`:94` 真 runner 的 failed/cancelled/uncertain 分支；`test_overseas_studio_execution.py:94` 真 PNG→collector→对象存储→API，收费执行被替换；`test_overseas_studio_postgres.py:15`/`:31` 真 PG Barrier 并发，不以 SQLite 假装锁验证。`test_native_studio_deploy.py:99` 断言实际编排顺序及故障阻断，不声称 mock 是生产执行。R9浏览器使用正式 dist/真实Vue DOM，覆盖网络丢响应和复用路径，修补R8测试盲区。收费CLI生产端到端未执行，属明确边界。
- **安全扫描 PASS（本次变更）**：新增 `StudioMarkdown.vue:1` v-html 仅接 `studio-markdown.ts:3` html:false 的输出，自定义图片/链接属性均 escape；本地图不自动授权，HTTP(S)外链带 noopener/noreferrer。与 [markdown-it 官方安全说明](https://raw.githubusercontent.com/markdown-it/markdown-it/master/docs/safety.md) 的关闭HTML方案核对后，结合实际XSS/协议测试判断，未把v-html词命中直接当漏洞。未发现新增硬编码密钥、危险执行或输入拼接SQL；0015的SQL是常量，业务查询是ORM。绝对路径用于既有受控发布/隔离边界，未输出凭据。
- **公开数据边界 PASS**：`transcript.py:31` 只读取 agent_message/reasoning.text；[官方 Codex SDK items.ts](https://raw.githubusercontent.com/openai/codex/main/sdk/typescript/src/items.ts) 将 ReasoningItem 标为公开摘要语义，工具命令/arguments/result 未通过白名单。`queries.py:14`、`router.py:14`、`transcript.py:97` 和 `delivery.py:157` 分别覆盖读取授权、浏览器写入保护、执行归属、文件边界；对应独立测试通过。
- **视觉 PASS**：独立浏览器实际打开 `/overseas/tasks/t` 工作台，再点击“返回任务列表”打开邻居 `/overseas/tasks`，非只数组件。目视 `output/playwright/studio-native-r9-review/studio.png`、`neighbor.png`，以及 `output/playwright/studio-native/mobile-confirm.png`。白底卡片均16px圆角；启用主按钮均 RGB(93,135,255)、白字、6px圆角、14px字号、32px高，字体一致。工作台压缩页头、扩大聊天符合既有批准方向，390px确认文案/按钮完整且无横向溢出。代码依据 `OverseasStudio.vue:4`、`studio.css:12`/`:39` 与既有任务列表。首次自动颜色比较捕捉到按钮从禁用转启用的过渡帧，等待500ms稳定后重验一致；未改产品样式。证据 `output/native-studio-r9-review-visual.log`。

既有问题单独保留，不伪装全库全绿：

1. 发布全目录历史失败：`scripts/release/test_release_native.py:100` 仍期望 annotation overlay 排末尾，而 HEAD/当前 `scripts/release/image-inputs-frontend.py:39` 以 materials overlay 结尾。这两文件本候选无差异；不阻断新 native-studio 路径73项专项，但全发布目录不是全通过。后续修测试应单独审查。
2. 已提供依赖审计 `output/native-studio-dependency-audit.json` 为 critical0/high70/moderate48/low5；主 Agent 标注与0.2.31一致。这里记录既有告警，未声称全依赖无漏洞，也未据此作无依据的新增安全问题结论。

## 验证与编译原始输出

本 reviewer 独立执行，最终命令均 exit0：

```text
# 后端 formal_delivery/transcript/conversations/execution
# output/native-studio-r9-review-backend.log
279 passed, 2 warnings in 15.53s
# 旧工作台权限、原件、归档/ZIP、显式完成
# output/native-studio-r9-review-core.log
6 passed, 2 warnings in 3.85s
# 前端 pnpm test：output/native-studio-r9-review-frontend.log
ℹ tests 357
ℹ suites 0
ℹ pass 357
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8681.0847
# pnpm typecheck：output/native-studio-r9-review-typecheck.log
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
> hengxin-smart-image-frontend@0.2.32 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
# 发布专项：output/native-studio-r9-review-release.log
73 passed, 26 subtests passed in 4.09s
# 新工作台浏览器：output/native-studio-r9-review-browser.log
PASS: incremental pages/updates, full messages/long text, safe Markdown and delivery images, failure/cancel/reload, scroll follow/history, draft selection persistence, idempotent new conversation, 390px
# 旧刷新/Skill浏览器：output/native-studio-r9-review-refresh.log
PASS: idle/active/completed polling, manual spinner, silent auto refresh, error recovery, draft/attachment/skill/scroll persistence; full descriptions desktop/mobile
# 独立邻居实际渲染：output/native-studio-r9-review-visual.log
PASS: actual built studio and neighboring task-list rendered in isolated browser; same card/primary-button design tokens
```

两条后端 warnings 为 Starlette/httpx 和 anyio BlockingPortal 弃用。初次发布测试命令误写 hotfix 测试文件名、旧浏览器默认3018未启动，均为审查执行错误；更正为实际 `overseas-hotfix-tests.py` 与已运行3026后完成上述测试，未修改实现以通过测试。

以下为读取并核对的主 Agent 原始证据，不冒称本 reviewer 独立重跑：

```text
# R9最终正式构建 output/native-studio-frontend-r9-build.log，exit0
> hengxin-smart-image-frontend@0.2.32 build D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit && vite build
vite v7.1.7 building for production...
✓ 4736 modules transformed.
✓ built in 36.01s
# 真实隔离PG专项 output/native-studio-backend-pg-20261014.log
66 passed, 2 warnings in 48.13s
# R7旧快照整库 output/native-studio-backend-full-r7.log
2166 passed, 188 skipped, 15 warnings in 250.38s (0:04:10)
# 发布全目录历史记录 output/native-studio-release-tests.log
Result: 1 failed, 242 passed, 1 skipped, 117 subtests passed in 13.78s
Exit code: 1
```

本 reviewer 的三份浏览器验收实际加载上述 R9 正式 dist；没有用旧构建冒充R9。R7整库不等于R9整库，188 skipped 不算通过。最终提交对应的实际安装镜像全量、备份排空/迁移/切换、生产版本与真实入口/14 Skill及181文件/国内身份不变核验仍为后续发布门禁，不能以本报告替代。生产任务为空，未在生产做有数据工作台/新对话/生图操作验收。

**结论：此 candidateId 两阶段 PASS，可由主 Agent 用同编号及本报告路径登记 review-approve。登记前须再次确认快照一致；若改代码或依赖必须重新固定并复核。未写 `.needs-review` clean，未执行批准或提交。**
