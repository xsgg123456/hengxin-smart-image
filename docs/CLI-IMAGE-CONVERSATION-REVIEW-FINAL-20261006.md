# API 单图 CLI 多轮修改独立复审

日期：2026-10-06。candidateId：`085ba81e095a7c8b01a8d38ba586b16d0eace437729990ed5247b4a638f8d9f9`。

范围：本次全部未提交的会话后端、0023 迁移、队列/容量集成、前端会话与原修改弹窗、专项测试和两份 Nginx 配置。依据 Product-Spec.md 最后 2026-10-06 节、DEV-PLAN.md 对应末节及 CLI-IMAGE-CONVERSATION-20261006.md；执行 code-review skill。仅审查和写报告，没有修改代码、提交或批准凭据。开始及结束 review-status 均返回上述 currentId，未发现审查中代码变化。

**Stage 1：PASS。Stage 2：FAIL。** 未发现新的 Stage 1 HIGH；Stage 2 有两个 MEDIUM，当前快照不得登记两阶段 PASS。

下列路径以 `hengxin-smart-image/` 为基准。

## Stage 1：逐项需求符合性

| 需求 | 结论与证据 |
|---|---|
| 仅图片修改切 CLI，API 首生成及文字模式保持 | 完整实现。frontend/src/views/hengxin/api-image-edits/RealRevisionDialog.vue:8、47 区分 cliMode；旧分支继续使用原提交逻辑。backend/app/modules/api_image_edits/versions.py:107 保留旧 revise，仅增加互斥。没有修改 API 首生成执行协议。新版浏览器脚本末段检验 text_edit 仍调用 revise。 |
| 固定 image-edit-v2、编号/整体意见、三图及可选标注顺序 | 完整实现。backend/app/modules/api_image_edits/conversation.py:110、119 使用底图/原图/素材/标注顺序并由服务器生成固定提示词；conversation_runner.py:29 只在原提示词后追加文件绑定及交付约定；客户端不能覆盖服务器固定模板。test_api_cli_conversation.py:84 覆盖恶意传入 prompt 被忽略、意见及 policyVersion 保留。 |
| 每 item 独立持久会话、精确 resume、隔离及缺失失败 | 完整实现。backend/app/modules/api_image_edits/conversation_models.py:10 item_id 唯一；conversation_runner.py:106、119、139 绑定 conversation UUID 工作区和明确会话编号。缺少历史会话编号/文件明确失败；复用 execution/workspace.py:30 隔离目录，不使用最近会话。test_api_cli_conversation.py:111、178 覆盖精确续接及缺失拒绝。 |
| 冻结底图、原图/素材/标注、完整意见、操作者及执行提示词 | 完整实现。backend/app/modules/api_image_edits/conversation.py:95、122 冻结所选版本/同 item 候选及输入；conversation_runner.py:128 保存 executionPrompt；conversation_models.py:26 保留 operator_id。外 item 候选在 conversation.py:97 拒绝。 |
| 幂等、同图活动轮次互斥 | 完整实现。backend/app/modules/api_image_edits/conversation.py:79 channel 锁、operation 键、assert_idle；conversation_runtime.py:40 受共享执行门禁保护。PostgreSQL 实测 test_api_cli_concurrency.py 同时提交只产生一轮、重复 claim 只有一方成功、同键只有一条事件。 |
| 复用原队列、进程、公开消息及文件验证；旧套图协议不变 | 完整实现。backend/app/modules/api_image_edits/conversation_runner.py:8 导入既有 execution 工具；worker/tasks.py:46 新增独立 kind 分支；modules/tasks/claims.py:66 只扩充共享并发计数；不改套图收图协议。容量异常收尾问题单列 Stage 2。 |
| 纯文字等待、有效图片候选、无效文件错误 | 完整实现。backend/app/modules/api_image_edits/conversation_runner.py:166、172、176：执行失败和无效文件失败，无交付链接进入 waiting_user，有唯一合法图片进入 candidate。test_api_cli_conversation.py 的文字、缺失文件、超时/进程失败专项均通过。 |
| 显式采用才更新正式版本、原始上传尺寸、失败取消保留旧结果 | 完整实现。backend/app/modules/api_image_edits/conversation_runner.py:49 由 item.source_id 归一尺寸；conversation.py:161 原子写新 ApiVersion 和当前结果。test_api_cli_conversation.py:111、194、247 对版本不提前改变、迟到候选拒绝及 32×32→8×6 原尺寸有断言。 |
| SSE 持久编号、顺序补发、去重、心跳及鉴权 | 完整实现。backend/app/modules/api_image_edits/conversation.py:49 持久事件；conversation_router.py:45、58 每次短事务重查身份和资源、按序查询、支持 Header/after、10 秒心跳；frontend/src/views/hengxin/api-image-edits/conversation-feed.ts:3 处理迟到快照与重复事件；use-image-conversation.ts:43 恢复连接。真实 TCP HTTP 专项复跑通过。 |
| 不泄漏 reasoning/命令/凭证；上游无增量则整条发送 | 完整实现。backend/app/modules/api_image_edits/conversation_runtime.py:108 只使用 execution/public_messages.py:13 的 agent_message 白名单和脱敏；测试明示 reasoning 内容未出现。没有声称 token 流。 |
| 断线或关闭窗口不取消；停轮与租约过期不自动重跑 | 完整实现。frontend/src/views/hengxin/api-image-edits/use-image-conversation.ts:74 仅终止订阅；RealRevisionDialog.vue:2 允许关闭。backend/app/modules/api_image_edits/conversation_runtime.py:118、conversation_stop.py:11 和 worker/outbox.py:31 保留 uncertain fence，停止由所属节点核实进程后释放。取消迟到输出和失效租约专项通过。 |
| 原 AnnotationEditor/Canvas 全部工具与布局 | 完整实现。frontend/src/views/hengxin/api-image-edits/ImageConversationEditor.vue:6 直接使用原组件及引用插槽，原 AnnotationEditor/Canvas 无本次 diff。查看新 conversation.png 与历史 editor-1280.png，三图参考、左画布、工具/缩放、右编号/整体意见、上传标注、底部撤销删除清空和预览均保留；新增过程/历史为折叠内容，不加常驻工具排。图片内容为测试夹具，不能验证生图质量。 |
| 候选续改/采用、历史选底图、标注按轮保存、新底图不继承、查看不清草稿 | 实现完整，浏览器“实际旧底图”验收证据存在 Stage 2 测试缺陷。frontend/src/views/hengxin/api-image-edits/ImageConversationEditor.vue:44、50、58 使用底图身份和等待回复轮次作为 draftKey；ImageConversationHistory.vue:8 只展示轮次材料，不修改编辑器草稿。后端保留 annotation_id，提交不自动继承标注。 |
| 跨用户采用版本冲突、旧 API 与 CLI 双向互斥 | 完整实现。backend/app/modules/api_image_edits/conversation.py:168 检查 expectedVersion；versions.py:110、164 增加 assert_idle。PostgreSQL 双方采用仅一方成功；后端双方向互斥专项通过。 |
| 任务/文件删除不发布迟到结果 | 完整实现。backend/app/modules/api_image_edits/service.py:89 阻止活动会话删除，files.py:54 阻止冻结输入/候选删除；conversation_runner.py:53、66 再查有效性和文件可用性后发布。 |
| 启动前失败恢复与真正派发后的缺会话保护 | 前轮 HIGH 已修复。backend/app/modules/api_image_edits/conversation_runner.py:111 检查 executionDispatched/process_identity，:147 在 execute 前持久化 fence。test_api_cli_preflight.py:15 三种预检失败后重新提交可首次启动，:40 真正 dispatch 后缺 session 禁止替代；四项独立复跑通过。 |
| 迁移、API/worker 注册与 SSE 代理 | 完整实现。backend/migrations/versions/0023_api_cli_conversations.py:12 创建三表，保留回滚数据；backend/app/main.py:57 注册路由；worker/tasks.py:46 分发；infra/nginx.vps.conf:10、nginx.media.conf:115 专用 SSE location 关闭缓冲/缓存/压缩。PG 迁移专项通过，主 Agent 提供两份 nginx -t 通过记录；本 reviewer 未重复容器配置测试。 |

未实现项：本次没有发现完全缺失的 Spec 功能。Spec 漂移：新增三表、会话接口、前端模块均对应本次需求，没有发现无依据新增业务范围。生产部署、真实收费模型效果不在本次已验证范围。

## Stage 2：问题清单

### MEDIUM 1：确定未执行的预检失败永久保留容量占用

位置：backend/app/modules/api_image_edits/conversation_runner.py:179；相关 conversation_runtime.py:60、capacity/admission.py:22、capacity/observation.py:38。

容量启用时，claim 先创建 held reservation，再做版本、输入、隔离环境预检。上述预检失败进入异常分支，只有 finish，没有调用 published；finish 本身只终结 Job/Outbox 和事件。容量采样只把 published 变为 accounted，held 永远继续计入 pending_bytes。用户按新修复反复提交恢复时，每个失败轮次都可新增一份不会自动核销的容量债，最终把后续新任务阻塞在容量等待。

这是静态可达路径证据，当前专项没有启用容量来动态验证该分支；test_api_cli_preflight.py:16 只断言执行和轮次状态。建议确定未派发的失败/取消在同一事务按容量机制发布核销，保留真实执行状态不确定的 reservation。补容量开启的 version/inputs/sandbox 失败→采样→修环境→再次执行断言，不能仅在容量关闭环境证明恢复。

### MEDIUM 2：历史底图浏览器测试使用错误 mock，成功标签过度宣称

位置：frontend/tests/api-image-conversation.browser.mjs:44、107、109。

mock 对所有 baseVersion 都用 item.result 作为 baseFileId/basePicture。采用 V2 后选择 V1 提交，记录却冻结 V2 图片。重新打开时生产组件依据 last.basePicture 渲染，所以测试实际展示 V2，但仅检查弹窗标题“基于 V1”，仍输出“保留实际旧底图”。所有夹具图片内容相同也无法通过肉眼发现错误。

修正 mock 为按 input.baseVersion 查 versions，并使用可区分的版本图片；断言重新打开实际下载/绑定的 fileId 或图像为 V1，候选底图也按实际绑定检验。该问题不直接证明生产底图逻辑错误，但当前所谓“实际旧底图”浏览器 PASS 不成立。

### LOW：旧图片模式浏览器脚本入口预期已过期

位置：frontend/tests/api-image-edit-modes.browser.mjs:33、114。

此旧脚本仍假设新图片修改调用 /revise 且 payload.kind=image_edit。新版实际走 /conversation，本次未运行该脚本，不能把其旧结果当当前回归。建议迁移其适用检查，或明确标为 legacy 客户端专用并给出适用运行方式，避免后续自动/人工误用。

## Stage 2：其余审查结果

- 命名/结构：新增服务、运行、停止、路由、模型和前端状态/请求/历史模块分离，新增生产文件均未超过 300 行；核心客户端使用 unknown 响应校验，无新增显式 any。证据：backend/app/modules/api_image_edits/conversation_runner.py:1、frontend/src/api/api-image-conversation.ts:5、ImageConversationEditor.vue:17。
- 安全扫描：本次新增生产路径未检出 eval、innerHTML/dangerouslySetInnerHTML、明文 API key、前端密钥变量或显式 any。请求采用 ORM 和参数对象；进程参数为列表，底图与候选均服务端查询归属。证据：conversation.py:95、conversation_runner.py:139、conversation_router.py:45。没有发现新增安全 HIGH；此结论不等同渗透测试。
- 视觉：已直接查看 output/playwright/api-image-conversation/conversation.png 与 output/playwright/api-image-edit-modes/editor-1280.png，比对组件布局/按钮/间距关系。截图视口不同，不作像素级相等断言。本 reviewer 没有独立重跑全部画笔/缩放/平移矩阵；原组件未变和历史证据不能扩大为当前全部浏览器回归已通过。
- 测试真实性：真实 PG 并发和真实 uvicorn TCP SSE 具有有效行为断言，身份撤销及断线任务保留均实际执行；模型执行仍为 fake_executor、浏览器为 mock API，因此不能证明真实 Codex 图像质量或生产部署链。

## 本 reviewer 独立运行结果（原始输出）

后端：独立临时 PostgreSQL，测试使用随机 schema；执行四个 test_api_cli_* 文件。

```text
....................                                                     [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
.venv\Lib\site-packages\starlette\testclient.py:53
  DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
20 passed, 2 warnings in 10.18s
```

编译执行 `.venv/Scripts/python.exe -m compileall -q app migrations`，原始 stdout 为空，进程 exit_code=0。

前端类型与新增客户端专项：

```text
[WARN] The "pnpm" field in package.json is no longer read by pnpm. The following keys were ignored: "pnpm.overrides", "pnpm.onlyBuiltDependencies". See https://pnpm.io/settings for the new home of each setting.
> hengxin-smart-image-frontend@0.2.16 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
✔ 交错GET与实时消息不回退，重连重复事件与快照重放只显示一次 (1.2019ms)
✔ 会话请求完整保留底图/意见/幂等键，采用携带预期版本 (16.9057ms)
✔ SSE支持跨chunk、多行JSON、CRLF与心跳，游标字段校验 (0.6029ms)
✔ SSE补发带after/Last-Event-ID并在身份改变时拒绝旧流 (6.3088ms)
✔ 响应丢失后续接原图片请求，冻结意见与key；采用操作不能替换未确认提交 (1.0507ms)
ℹ tests 5
ℹ suites 0
ℹ pass 5
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 352.242
```

该命令进程 exit_code=0。本机 pnpm 配置提示列为执行环境警告，非本次引入的运行代码缺陷。

主 Agent 提供后端全量 1441 passed/125 skipped、前端全量 217 passed 和正式 build PASS；本 reviewer 没有重新运行这些全量命令，故不作为独立复跑结论。浏览器 result.json 五组 errors=[] 已阅读，但历史底图一组受上述 mock 缺陷影响。

修复路由：容量故障由 bug-fixer 处理；浏览器验收与旧测试用途由 dev-builder 更新。修复后重新 review-prepare，新的候选从 Stage 1 起复核，不得批准本编号。
