# API 单图 CLI 多轮修改最终验收复核

日期：2026-10-06。candidateId：`aeee8491e2346fb6744ffc0a33a1b6fd9b47b8a634b1c6cd8b62320a8f55a8dd`。

**Stage 1：PASS。Stage 2：FAIL。** 仍有一项 MEDIUM 容量异常收尾缺陷，不得登记本快照两阶段 PASS。

范围为当前全部未提交会话后端、迁移、队列/容量集成、会话前端、浏览器及后端专项、Nginx 配置。依据 Product-Spec.md / DEV-PLAN.md 最后 2026-10-06 节、docs/CLI-IMAGE-CONVERSATION-20261006.md；已读 AGENTS、code-review skill、HARNESS-REVIEW 协议。复用前轮 FINAL 报告中未变部分的逐项证据，独立阅读当前关键代码并复跑后端专项；不将旧失败快照直接批准到新快照。仅写报告，没有修复、提交或写 clean。下列代码路径以 hengxin-smart-image/ 为基准。

## Stage 1：逐项符合性

| Spec 要求 | 结论、位置及证据 |
|---|---|
| 仅图片改 CLI，文字及首次 API 保持 | 完整实现。frontend/src/views/hengxin/api-image-edits/RealRevisionDialog.vue:8、47；browser.mjs:116 的 text_edit 断言仍在，既有 API 首生成未改协议。 |
| 固定提示词、编号与整体意见、三图/可选标注顺序 | 完整实现。backend/app/modules/api_image_edits/conversation.py:110、119；conversation_runner.py:29。独立测试验证服务器模板、意见与冻结输入，客户端 prompt 不可覆盖模板。 |
| 每 item 独立持久会话、隔离目录、精确 resume、缺失明确失败 | 完整实现。conversation_models.py:10；conversation_runner.py:115、122、143；首轮、续接和缺失专项通过。executionDispatched 的持久 fence 位于 :162，启动前错误恢复专项通过。 |
| 冻结底图/原图/素材/标注、完整意见、操作者与执行提示词 | 完整实现。conversation.py:95、122；conversation_runner.py:133。候选仅能引用本会话，历史已发布底图按版本查找。 |
| 幂等与同图互斥 | 完整实现。conversation.py:79、87；conversation_runtime.py:40。真实 PG 并发测试通过。 |
| 复用队列/进程/事件/文件验证，旧 CLI 协议保持 | 完整实现。conversation_runner.py:8；worker/tasks.py:46；modules/tasks/claims.py:66。容量异常收尾质量缺陷另列 Stage 2。 |
| 纯文字 waiting_user、合法图片候选、无效交付错误 | 完整实现。conversation_runner.py:177、181；test_api_cli_conversation.py:178 无效图片确实进入 failed，候选和文字专项通过。 |
| 显式采用、原子版本、最初原尺寸、失败取消保留旧图 | 完整实现。conversation.py:161；conversation_runner.py:49；真实 PG 采用冲突及尺寸专项通过。 |
| 持久 SSE 编号顺序、游标补发、去重、心跳、鉴权与撤权 | 完整实现。conversation.py:49；conversation_router.py:45、58；frontend/src/views/hengxin/api-image-edits/conversation-feed.ts:3。真实 uvicorn TCP SSE 专项此次独立复跑通过。 |
| 公开消息白名单、无 reasoning/命令/凭据、无增量则整条 | 完整实现。conversation_runtime.py:108；原有 execution/public_messages.py:13。专项断言秘密推理不在事件中。 |
| 浏览器关闭不取消；停止/租约过期不自动重试 | 完整实现。use-image-conversation.ts:74；conversation_stop.py:11；conversation_runtime.py:118。停止、过期和迟到输出专项通过。 |
| 原 AnnotationEditor/Canvas 布局和全工具；过程历史按需展示 | 完整实现。ImageConversationEditor.vue:6；原公共画布无本次修改。已直接查看新 conversation.png 与历史 editor-1280.png：三图、左右区、框选/画笔、缩放、拖动、撤销删除清空、上传、预览仍保持既有位置关系。非相同视口，不宣称像素相等或本轮重跑完整画布矩阵。 |
| 候选续改/采用、历史选底图、标注按轮留存、新底图不继承、查看不清草稿 | 完整实现。ImageConversationEditor.vue:39、44、58；ImageConversationHistory.vue:8。修正后的 browser.mjs:44 按版本绑定底图，:110–112 检查实际 fileId、下载地址及参考图，不再只看标题。提供的 result.json 五组通过、errors=[]；本 reviewer 阅读代码与结果，未独立再跑浏览器。 |
| 跨用户版本冲突、API/CLI 双向互斥、删除不发迟到结果 | 完整实现。conversation.py:168；versions.py:110、164；service.py:89；files.py:54；conversation_runner.py:53。独立 PG 专项通过。 |
| 迁移/注册及 SSE 代理 | 完整实现。migrations/versions/0023_api_cli_conversations.py:12；main.py:57；infra/nginx.vps.conf:10、nginx.media.conf:115。迁移由本轮 PG fixture 执行；Nginx 配置采用前轮记录，未重复 nginx -t。 |

部分实现/完全未实现：本轮无新增此类项。Spec 漂移：会话表、接口及组件均对应本次需求，没有无来源的新业务范围。没有生产部署或收费模型视觉效果的验证结论。

## Stage 2：仍需修复

### MEDIUM：执行已结束后的无效图片异常仍永久持有容量

位置：backend/app/modules/api_image_edits/conversation_runner.py:165、181、194；capacity/admission.py:22；capacity/observation.py:38。

`execute` 正常返回后 `completed=True`，随后最终交付引用不存在的图片，`collect_final_outputs` 抛出异常。异常分支将轮次结束为 failed，但容量核销只在 `not spawned` 时调用 published。此时 spawned=True，因此 reservation 留在 held。采样只把 published 转 accounted，held 会永久计入 pendingBytes。重复无效交付会阻塞后续新任务，而该 failed 轮次没有 uncertain 停止回收入口。

上轮“启动前失败”的修复确已成立，但没有覆盖同一容量生命周期中的“执行已结束、结果校验失败”。这不是执行状态不明，不能以不确定保护解释永久 held。建议确定已完成的失败收尾也发布容量核销，并对无效交付、归一/存储失败补 gate 开启的回归；真正派发状态不明继续持有。

独立真实 PostgreSQL 复现：复用现有 test_missing_session_refuses_new_thread_and_invalid_delivery_fails，通过内存 pytest plugin 在调用前执行现有 policy(factory) 打开容量，在调用后检查各轮 reservation。没有修改任何生产/测试源文件，原用例断言成立，新增容量断言失败。关键原始输出：

```text
CAPACITY_PROBE: [('failed', True, 'held'), ('failed', None, 'published')]
E   AssertionError: [('failed', True, 'held'), ('failed', None, 'published')]
FAILED tests/test_api_cli_conversation.py::test_missing_session_refuses_new_thread_and_invalid_delivery_fails
1 failed, 3 warnings in 2.52s
```

元组依次为轮次状态、executionDispatched、reservation.state。第三项 warning 来自该临时 hookwrapper 主动抛出的断言，其余两项为现有 Starlette 弃用警告。

## Stage 2：已闭合问题与其他维度

- 启动前容量：conversation_runner.py:71、108、160、194 已发布明确未派发的容量；tests/test_api_cli_preflight.py:17、63 启用真实 gate，三类预检失败及启动前停止均通过。缺会话禁止替代测试通过。
- 历史底图测试：frontend/tests/api-image-conversation.browser.mjs:44 按版本表选底图，:110–112 同时验证绑定与实际加载路径。夹具图片仍同色，但实际文件身份断言足以关闭此前“只验证标题”的缺陷，不把它说成视觉模型验证。
- 旧脚本用途：frontend/tests/api-image-edit-modes.browser.mjs:1 明确 legacy，:2 指向新验收脚本，旧低优先级问题已闭合。
- 质量：沿用前报告对新增生产文件小于 300 行、模块单一职责、客户端 unknown 校验的检查；当前 runner 195 行，新增修复没有混入额外业务。conversation_runner.py:184 错误收尾仍有上项缺陷，因此 Stage 2 不通过。
- 安全：本轮对 conversation 后端及前端生产文件重扫 eval、HTML 注入入口、前端密钥、sk-ant-/sk-proj- 未命中；conversation.py:95 归属约束、conversation_router.py:45 鉴权、runner.py:143 参数列表仍保留。无新增安全 HIGH；不等于渗透测试。
- 视觉：实际打开新旧两张渲染截图，原组件布局一致；新增状态/折叠历史与原蓝白 Element 样式相容。截图是测试夹具，非生图质量证据。

## 独立测试与编译输出

执行四个 test_api_cli_* 文件及 test_capacity_admission.py，使用专用 PostgreSQL 的随机 schema，未发真实模型请求：

```text
................................                                         [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
.venv\Lib\site-packages\starlette\testclient.py:53
  DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
32 passed, 2 warnings in 11.53s
```

`.venv/Scripts/python.exe -m compileall -q app migrations` 原始 stdout 为空，exit_code=0。

前端生产文件无本轮 delta；前轮 typecheck 输出 `vue-tsc --noEmit`、exit_code=0，详见 CLI-IMAGE-CONVERSATION-REVIEW-FINAL-20261006.md 原始记录。主 Agent 提供的前端 217 项、build PASS、后端全量 1441 passed/125 skipped，本 reviewer 未重跑，不作为本次独立结果。此次 32 项全部通过没有推翻上述容量探针失败；专项尚缺确定完成后的容量断言。

修复路由：bug-fixer 修异常收尾及回归后，重新冻结快照、从 Stage 1 起复核。不得批准当前 candidateId。

## 快照变化告知

审查开始 currentId 与提供候选 aeee8491e2346fb6744ffc0a33a1b6fd9b47b8a634b1c6cd8b62320a8f55a8dd 一致。报告写入前再次 review-status 返回 currentId=cc42158e69f2b62f4f50345cffbc5eae9c625f2d33035d8dc330d3d6df877e66，且出现新测试 test_api_cli_capacity_completion.py；说明主线程收到阻塞反馈后已开始修复。本文 FAIL 与探针证据仅针对送审 aeee8491 快照，不评判修复中的新快照；32 项运行期间可能与修改重叠，也不能作为新候选的独立批准证据。需重新 prepare 和独立复核。
