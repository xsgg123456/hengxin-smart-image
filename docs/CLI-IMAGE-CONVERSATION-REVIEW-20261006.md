# CLI 单图多轮修改独立审查（2026-10-06）

- candidateId：`eb701f2c3a7cdc04289dd92e8f594fb620cf383850acdcae09285ab6a44b1c10`
- Stage 1：**FAIL（HIGH × 1）**。
- Stage 2：**未执行**，按 code-review skill 的 HIGH 阻断规则停止。
- 范围：本候选全部 31 个受控变更文件；API 单图 conversation 服务、迁移、执行/停止/SSE、容量和旧通道互斥、前端编辑器/历史/客户端、代理及专项测试。普通历史文档不作为代码变更审查。
- 依据：Product-Spec.md 最后“2026-10-06 · API 图片修改接入 CLI 多轮对话”、DEV-PLAN.md 同日期末段及 docs/CLI-IMAGE-CONVERSATION-20261006.md。
- 审查开始及结束均运行 review-status，currentId 均为上述 candidateId；未发现审查中代码变化。未写 clean、未登记批准、未修复代码、未提交。

## HIGH：首次执行前失败会永久阻断本图片创建 CLI 会话

**位置**：`hengxin-smart-image/backend/app/modules/api_image_edits/conversation_runtime.py:67`；`hengxin-smart-image/backend/app/modules/api_image_edits/conversation_runner.py:98`、`:108`、`:111`。

**需求原文**：“每个 API item 独立持久 CLI 会话；首次创建，后续按精确会话 ID resume”；“会话缺失明确失败，不隐式新建”。实际把“已领取队列任务”当成“已经创建过 CLI 会话”，扩大了会话缺失保护的范围。

claim 在任何 CLI 预检之前就写入 started_at。第一次 --version 检查失败时，execute 从未调用、会话从未创建，该轮标记 failed。修复运行环境后用户提交第二轮，earlier 查询看到第一轮 started_at 非空，而 session_id 为空，于是再次失败“原会话编号缺失，无法继续；禁止创建替代会话”。第三轮及以后同理；页面没有恢复该 item 首次会话创建的途径。

**独立复现**：通过内存 pytest plugin 替换既有测试函数，使用原 files_env/cli_enabled fixture，先令 runner.subprocess.run 返回 returncode=1，再恢复正确版本并手动提交第二轮；两个轮次均 failed，fake executor 累计调用 **0 次**。没有修改仓库测试文件，没有启动实际模型。回归用例预期修复环境后应首次执行一次，断言失败。

**修复方向**：持久记录真正的启动证据，区分可证明尚未启动的失败与已经启动但会话编号未知。前者允许后续显式提交首次创建；后者继续保持 uncertain/缺失会话防重跑保护。不能简单删除 missing-session 检查或将所有无 session_id 的失败都自动重开。

**测试缺口**：`hengxin-smart-image/backend/tests/test_api_cli_conversation.py:179` 只覆盖实际执行后删除已存在的会话文件，没有覆盖预检失败后恢复环境的首会话创建。

## Stage 1 逐项核对

以下“匹配”只指已核对的代码路径和列明证据，不代表本候选整体通过。路径 B 为 `hengxin-smart-image/backend/app/modules/api_image_edits/`，F 为 `hengxin-smart-image/frontend/src/views/hengxin/api-image-edits/`。

| Spec 条目 | 结论 | 代码及验证证据 |
|---|---|---|
| 图片修改切 CLI，文字/API 初始生成保持 | 匹配 | F/RealRevisionDialog.vue:9、:40、:115；image 使用独立组件，旧 revise 保留；专项 test_api_cli_conversation.py:232 验证互斥两方向；浏览器记录第五组文字模式仍发 /revise |
| 固定 v2 提示词与意见拼接 | 匹配 | B/conversation.py:116 服务端重新构造固定模板；B/conversation_runner.py:42 原文前缀后追加绑定/交付约定；专项 :83 验证客户端 prompt 不得覆盖模板 |
| 当前选定底图、原图、素材、可选标注顺序 | 匹配 | B/conversation.py:96、:108、:125；B/conversation_runner.py:28；专项 :83、:135；浏览器记录显示三图及标注上传 |
| 每 item 独立会话与精确 resume，不使用最近会话 | 部分实现，有 HIGH | B/conversation_models.py:14 item_id 唯一；B/conversation_runner.py:114、:121、:135 隔离目录/精确 ID；正常续接专项 :106 通过，但首次预检失败后永久无法创建，见 HIGH |
| 原会话确实缺失须失败 | 匹配 | B/conversation_runner.py:111、:121；专项 :179 通过；不可用此通过结论覆盖上项错误 |
| 轮次输入、意见、操作者、执行提示词留存 | 匹配 | B/conversation.py:122、:125；B/conversation_runner.py:126；文件锁定及引用保护 B/files.py:52；专项 :83 |
| 幂等、同 item 最多一个活动轮次 | 匹配 | B/conversation.py:42、:79；B/versions.py:65；PG test_api_cli_concurrency.py:62、:93 真实并发只创建一轮，重复领取只一个 token |
| CLI 队列/进程/解析/文件验证复用 | 匹配 | B/conversation_runner.py:8、:146、:152、:163；backend/app/worker/tasks.py 新 kind 分派；原 generation 路径保留。真实上游模型执行未验证 |
| 纯文字进入 waiting_user，无效交付失败 | 匹配 | B/conversation_runner.py:156、:160；专项 :106、:179。messages 仅来自公共消息筛选器，不用 reasoning 填充文字回复 |
| 候选不自动发布，采用原子新增版本且尺寸回原图 | 匹配 | B/conversation_runner.py:49、:59、:79；B/conversation.py:161、:172；专项 :106、:252 验证 32×32 输出归一到最初 8×6，采用前 currentVersion 不变 |
| 跨用户采用版本冲突 | 匹配 | B/conversation.py:168 校验 expectedVersion；PG test_api_cli_concurrency.py:62 两用户采用结果 200/409，版本只新增一个 |
| 失败/取消保留旧图、过期 lease 不重试、停止隔离迟到结果 | 匹配已测路径 | B/conversation_runtime.py:45、:73、:119；B/conversation_runner.py:53、:67；B/conversation_stop.py:11；专项 :154、:165、:194、:211 验证失败、过期、取消后无候选及执行节点核验停止 |
| 旧 API 图片返工与 CLI 同图互斥 | 匹配 | B/versions.py:110、:164；B/conversation.py:88；专项 :83、:232 |
| 任务/文件删除不能发布迟到结果 | 匹配代码路径 | B/service.py:89 拒绝删除活动 item；B/files.py:52 拒绝删除轮次引用；B/conversation_runtime.py:73 与 runner.py:67 再验 task、lease、取消状态；专项 :83 覆盖删除拒绝 |
| SSE 持久编号/补发/去重/心跳/短事务 | 匹配 | B/conversation.py:49；B/conversation_models.py:44 唯一约束；B/conversation_router.py:45、:58、:74；frontend/src/api/api-image-conversation.ts:25、:50；专项 SSE TCP 实测先收到首帧再产生新事件、Last-Event-ID 只补后续 |
| SSE 鉴权、禁用撤权及只播公开消息 | 匹配 | B/conversation_router.py:47、:80；B/conversation_runtime.py:111；backend/app/execution/public_messages.py:14 白名单过滤；专项 :106 不含 reasoning，test_api_cli_sse_http.py:25 撤权断流/后续 403 |
| 浏览器断线不取消；交错快照不覆盖新事件 | 匹配 | B/conversation_router.py:67 只结束流；F/use-image-conversation.ts:17、:41；F/conversation-feed.ts:3；frontend/tests/api-image-conversation.test.ts:10 旧快照不得擦除新消息 |
| 原 AnnotationEditor/Canvas、框选/画笔/缩放平移/编号意见/上传预览保持 | 接入匹配，视觉验收未全部复验 | F/ImageConversationEditor.vue:6 复用原组件，公共画布无 diff；RealRevisionDialog.vue:130 保留原高度样式；已实际查看 output/playwright/api-image-conversation/conversation.png，左右结构、工具和上传入口存在。浏览器脚本验证原尺寸标注与预览。HIGH 出现后没有继续全视口或邻居页面 Stage 2 视觉复验 |
| 历史按需展开、选择版本/候选底图、显式采用 | 匹配 | F/ImageConversationHistory.vue:2、:5、:13；F/ImageConversationEditor.vue:46、:51、:91；浏览器记录第二至四组 |
| 标注按轮次保存，新底图不继承，查看不清草稿 | 匹配已测路径 | B/conversation.py:123；F/ImageConversationEditor.vue:39、:40、:56；历史仅 details 展开不换 draftKey；浏览器记录关闭重开草稿恢复、候选后空草稿、旧底图等待恢复 |
| 不增加常驻工具排、文字入口隔离 | 匹配 | F/ImageConversationEditor.vue:5 使用折叠历史；F/RealRevisionDialog.vue:16 复用 footer；:42 模式锁，浏览器第五组验证文字修改使用当前正式版本 |
| 代理定向禁缓冲 | 配置存在 | infra/nginx.vps.conf、infra/nginx.media.conf 新 conversation/events location；主线程已提供 nginx 1.27 -t 通过，此次 reviewer 未重跑容器配置验证 |
| 不部署/不收费；技术成功不等于视觉合格 | 遵守 | 本次只有隔离 DB/HTTP/fake executor 测试；无真实模型、部署、提交。任何真实生成质量、生产完整代理链结论均不在本报告 |

未发现需要另列的未实现新增页面或业务范围漂移；新增会话表/API、组件、worker kind 均服务已授权范围。此处不代替 Stage 2 质量或安全扫描结论。

## 独立测试与编译输出

命令：backend `.venv/Scripts/python.exe -m pytest tests/test_api_cli_conversation.py tests/test_api_cli_concurrency.py tests/test_api_cli_sse_http.py -q`，TEST_DATABASE_URL 指向主线程提供的独立 PostgreSQL 55439，PG fixture 只创建/销毁随机 schema。

原始末尾输出：

```text
................                                                         [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
.venv\Lib\site-packages\starlette\testclient.py:53
  DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
16 passed, 2 warnings in 10.21s
```

随后执行 `.venv/Scripts/python.exe -m compileall -q app migrations`：**exit_code=0，stdout 为空**（-q 模式原始输出）。

独立故障探针原始关键输出（Windows 管道中文出现编码乱码，保留不伪造原文）：

```text
REVIEW_PROBE: [('failed', '�Ự��ͼƬУ��ʧ�ܣ�����ִ�л���'), ('failed', 'ԭ�Ự���ȱʧ���޷���������ֹ��������Ự')] execute_calls= 0
E   AssertionError: First invocation failed before spawn, repaired environment must permit first session creation
<stdin>:20: AssertionError
FAILED tests/test_api_cli_conversation.py::test_missing_session_refuses_new_thread_and_invalid_delivery_fails
1 failed, 2 warnings in 2.12s
```

代码中的对应错误原文分别为“会话或图片校验失败，请检查执行环境”和“原会话编号缺失，无法继续；禁止创建替代会话”。探针仅在内存替换测试函数，原有测试名仍显示，不代表已修改该测试文件。首次探针在 pytest 初始化前 import 测试模块导致环境校验失败，调整为 fixture 初始化后导入才得到上述有效复现。

主线程提供的后端全量 1441 passed/125 skipped、前端 217 passed/build、Nginx 和 5 组浏览器结果为补充材料；本 reviewer 本轮没有重跑其全部命令，不以这些记录冲销 HIGH。

## 交接

Stage 1 失败，应先修复首次启动证据判定并补回归，再 review-prepare 获取新 candidateId，重新从 Stage 1 审查。本报告不得用于 review-approve；Stage 2 的质量、安全扫描、邻居实际页面视觉对比及全量验证结论均未签发。
