# CLI 单图多轮修改闭合审查

日期：2026-10-06。candidateId：`4fca61a4301e3381b08db8ba117adedeb1c86b3bcaee1d0ba1a27cb3cb6be062`。

**Stage 1：PASS。Stage 2：PASS。** 本轮未发现需要阻断的缺陷；前三轮已报告问题均有修复与验证证据。

审查范围：当前快照的全部 34 个受控变更文件，包括会话后端、迁移、队列/容量、前端及专项测试、SSE 代理。依据 Product-Spec.md 与 DEV-PLAN.md 末尾 2026-10-06 节、docs/CLI-IMAGE-CONVERSATION-20261006.md，执行 code-review skill 与 HARNESS-REVIEW 协议。已读前三份审查报告，复用其未变范围的证据，独立阅读当前关键服务/执行/停止/路由/编辑器与测试，重点验证最终容量和取消 delta。没有修复代码、提交、登记批准或写 clean。

以下 B 为 `hengxin-smart-image/backend/app/modules/api_image_edits/`，F 为 `hengxin-smart-image/frontend/src/views/hengxin/api-image-edits/`；测试路径均相对 `hengxin-smart-image/`。

## Stage 1：逐项需求符合性

| 需求 | 结论与证据 |
|---|---|
| 仅图片修改切 CLI，文字及 API 初生成保持；旧 revise 兼容 | 完整实现。F/RealRevisionDialog.vue:8、47；B/versions.py:107；frontend/tests/api-image-conversation.browser.mjs:116–118 验证文字仍发送 text_edit。原首次 API 执行协议未更改。 |
| 固定 v2 提示词、编号/整体意见、三图及可选标注顺序 | 完整实现。B/conversation.py:108、116、125，runner.py（即 conversation_runner.py）:29、43；服务端重建固定提示词，追加路径和交付约定。独立专项覆盖冻结输入及忽略客户端替代 prompt。 |
| 每 item 独立持久会话，隔离工作区，精确 resume，缺失明确失败 | 完整实现。B/conversation_models.py:10；B/conversation_runner.py:118、128、134、147。独立专项覆盖首轮/续接及会话文件缺失。 |
| 未派发预检失败可恢复，真正派发后缺会话不偷偷替代 | 完整实现。B/conversation_runner.py:119、160–171。backend/tests/test_api_cli_preflight.py:17、41 的恢复与替代拒绝用例独立通过。 |
| 每轮冻结底图/原图/素材/标注、完整意见、操作者及执行提示词 | 完整实现。B/conversation.py:96–126，B/conversation_runner.py:137–139。候选检查同会话，版本按 item 查找；独立专项通过。 |
| 幂等、同 item 一轮活动 | 完整实现。B/conversation.py:79–88；B/conversation_runtime.py:41。真实 PG 并发提交/领取测试通过。 |
| 复用队列、进程、公开事件与文件验证，旧套图协议保持 | 完整实现。B/conversation_runner.py:8–18、171、188；backend/app/worker/tasks.py:46；backend/app/modules/tasks/claims.py:66。没有改变旧套图的执行参数/收图协议。 |
| 纯文字 waiting_user，合法图片候选，无效交付为错误 | 完整实现。B/conversation_runner.py:178–190。独立纯文字、候选、缺失图片和失败专项通过。 |
| 候选显式采用、原子版本、最初原图尺寸、失败取消保留旧图 | 完整实现。B/conversation.py:161–183；B/conversation_runner.py:69–90。PG 采用冲突与原尺寸专项通过，32×32 输出归一为初始 8×6。 |
| SSE 持久编号、按序推送、游标重放、去重及心跳 | 完整实现。B/conversation.py:49；B/conversation_router.py:45、58–83；F/conversation-feed.ts:3。真实 uvicorn TCP SSE 与 PG 专项独立通过。 |
| SSE 鉴权、禁用/删除重校验；只播公开消息、无增量则整条 | 完整实现。B/conversation_router.py:47–48、78–80；B/conversation_runtime.py:112；backend/app/execution/public_messages.py:13。撤权断流及 reasoning 不出现在公开事件中的断言通过。 |
| 关闭/断线不取消后台，停止及租约丢失不自动重跑 | 完整实现。F/use-image-conversation.ts:74；B/conversation_runtime.py:119；B/conversation_stop.py:11。最后 delta 保留未知执行的 uncertain/held，取消 outbox 仅重派停止核验而非 execute，见下节。 |
| 沿用 AnnotationEditor/Canvas 原布局及框选/画笔/编号/缩放平移/撤销删除清空/上传预览 | 完整实现。F/ImageConversationEditor.vue:6 直接复用原组件；公共画布无本次改动。独立打开新旧渲染截图核对原工具位置关系；浏览器证据包含原尺寸标注和提交。原全画布矩阵沿用前次未变组件证据，不宣称此次重跑矩阵。 |
| 不加常驻工具排；过程历史按需展开 | 完整实现。F/ImageConversationHistory.vue:2；F/ImageConversationEditor.vue:5。新截图中的历史为折叠入口，框选/画笔及缩放工具保持。 |
| 候选续改/采用、历史选择底图、标注按轮保存、新底图不继承、查看不清草稿 | 完整实现。F/ImageConversationEditor.vue:39–65；B/conversation.py:124。browser.mjs:101–113 按版本查找底图并验证实际 fileId、下载请求和参考图 URL；result.json 五组通过且 errors=[]。 |
| 跨用户采用版本冲突、API/CLI 双向互斥 | 完整实现。B/conversation.py:168；B/versions.py:110、164。真实 PG 并发与双向互斥专项独立通过。 |
| 任务/文件删除不发迟到结果 | 完整实现。B/service.py:89、B/files.py:54；B/conversation_runner.py:49、79–82。活动删除保护和取消后候选不可发布专项通过。 |
| 迁移、API/worker 注册、SSE 定向代理 | 完整实现。backend/migrations/versions/0023_api_cli_conversations.py:12；backend/app/main.py:57；worker/tasks.py:46；infra/nginx.vps.conf:10、nginx.media.conf:115。此次 PG fixture 执行迁移；两份 nginx -t 沿用主线程此前记录，未独立复跑。 |
| 不收费、不部署，技术成功不等于视觉合格 | 满足本次验证边界。backend/tests/test_api_cli_conversation.py:44 的 fake executor 和 frontend/tests/api-image-conversation.browser.mjs:22 的隔离 mock 不调用真实模型；没有真实生图质量或生产发布结论。 |

部分实现、未实现、无依据新增业务范围：本轮未发现。新增三表、会话 API、组件与 worker kind 均对应本次需求。UI 引导的继续、采用、停止、历史和恢复均有实际处理函数，未发现死引导（F/ImageConversationEditor.vue:46、51、85、90、94）。

## Stage 2：问题闭合与质量

1. **原 HIGH 预检后无法首次创建已闭合**：B/conversation_runner.py:119–125 只依据真实 dispatch/process 证据判定既往调用；:169 先持久化 dispatch fence，再执行。backend/tests/test_api_cli_preflight.py:17 独立覆盖 version/inputs/sandbox 故障后恢复，:41 保留真正派发但无 session 的拒绝保护。
2. **预检容量 held 已闭合**：B/conversation_runner.py:156、167、202 在明确未派发时发布容量；backend/tests/test_api_cli_preflight.py:20、63 开启容量策略，失败及取消断言 published。
3. **执行完成后收图失败 held 已闭合**：B/conversation_runner.py:172 记录明确返回，:196–203 在 completed 时结束为 failed/cancelled 并 published；:49–59 的 completion_allowed 同时要求 token 匹配，防止失效持有者发布结果。backend/tests/test_api_cli_capacity_completion.py:16–50 在真实 PG、容量 gate 开启前提下验证 missing 图片、store.put 失败及执行后取消，均无候选、状态正确且 published。published 仍待磁盘采样记账，不等于立即声称空间已回收（backend/app/capacity/admission.py:22、57）。
4. **未知执行取消仍保持保护**：B/conversation_runner.py:196 在 spawned 且未 completed 时优先 uncertain，取消请求不改成假 cancelled；B/conversation_runtime.py:37 使取消中的 uncertain outbox 保持开放；backend/app/worker/outbox.py:31 重派到 B/conversation_stop.py:11，依据执行节点/进程凭据核验后才能释放。新增测试 :42–46 独立验证 held 与开放 outbox；原停止凭据专项亦通过。没有凭据继续阻塞是需求中的保守保护，不是自动重跑入口。
5. **浏览器历史底图与旧脚本问题已闭合**：frontend/tests/api-image-conversation.browser.mjs:44 按 baseVersion 查询，:110–112 检验实际绑定及加载路径；旧 api-image-edit-modes.browser.mjs:1–2 标明 legacy 和替代。读取当前 result.json 五组、errors=[]；本 reviewer 未再次启动浏览器。
6. **结构/类型**：新增运行、停止、服务和路由各有职责，当前 runner 203 行、runtime 127 行；未超过 300 行。前端请求使用 unknown 校验，F/ImageConversationEditor.vue:25 等采用明确类型。安全扫描未发现新增显式 any。
7. **安全**：扫描新 conversation 后端/前端生产文件，eval、HTML 注入入口、前端 KEY/SECRET/TOKEN 和 sk-ant-/sk-proj- 无命中；B/conversation.py:98、103 校验底图归属，router.py:47 鉴权，runner.py:147 使用进程参数列表。未发现新增安全 HIGH；此为代码审查而非渗透测试。
8. **视觉对比**：此次实际打开 output/playwright/api-image-conversation/conversation.png 与 output/playwright/api-image-edit-modes/editor-1280.png。三图参考、左画布/右意见、工具与上传按钮、撤销删除清空、底部预览的布局关系一致，新增状态和历史沿用蓝白 Element 风格。视口不同，不宣称像素相等；纯色 fixture 不用于判断生图质量。对应 F/ImageConversationEditor.vue:6 与 RealRevisionDialog.vue:130。
9. **测试真实性**：新增五例启用实际 capacity policy，断言数据库 reservation 而非仅 UI 状态；未知执行异常是可达的进程边界，采用保守分支合理。PG 并发、SSE TCP 及故障用例均实际执行。模型调用和浏览器 API 为测试替身，结论范围明确。

HIGH/MEDIUM/LOW 未闭合问题：无新增；此前三轮具体问题全部闭合。

## 独立运行与编译原始输出

使用独立 PostgreSQL 55439，仅随机 schema。命令为 `.venv/Scripts/python.exe -m pytest -q tests/test_api_cli_capacity_completion.py tests/test_api_cli_preflight.py tests/test_api_cli_conversation.py tests/test_api_cli_concurrency.py tests/test_api_cli_sse_http.py tests/test_capacity_admission.py`。

```text
.....................................                                    [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\Work_Project\hengxin-smart-image\hengxin-smart-image\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
37 passed, 2 warnings in 12.47s
```

进程 exit_code=0。`.venv/Scripts/python.exe -m compileall -q app migrations`：原始 stdout 为空，exit_code=0。

前端生产代码未在最后 delta 更改；独立前轮 typecheck 原始输出见 FINAL 报告：

```text
> hengxin-smart-image-frontend@0.2.16 typecheck D:\Work_Project\hengxin-smart-image\hengxin-smart-image\frontend
> vue-tsc --noEmit
```

该前轮命令 exit_code=0。主线程提供前端 217 单测、build PASS、两份 nginx -t PASS 与后端全量记录，作为补充，非本轮 reviewer 独立重跑结论。没有将跳过测试或模型质量说成已验证。

## 快照与交接

审查开始 review-status currentId 与 candidateId 一致。仅报告写入不参与代码快照。主 Agent 应在登记前再次核对同一快照，以本报告 Stage 1/Stage 2 PASS 执行 review-approve；不得以历史失败报告或写 clean 替代批准。
结束校验：报告写入后 review-status currentId 仍为 4fca61a4301e3381b08db8ba117adedeb1c86b3bcaee1d0ba1a27cb3cb6be062，审查期间未发现代码快照变化。
