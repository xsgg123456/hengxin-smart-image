# 任务素材与执行播报独立审查

- 日期：2026-09-11。
- candidateId：`6e59a777339bc88a8b20be8bb49ee3fd13399dc2c8784f7460666f409e57130a`。
- **Stage 1：FAIL；2 项 HIGH。Stage 2：未执行。**
- 依据：`.agents/skills/code-review/SKILL.md`、`docs/HARNESS-REVIEW.md`；本轮仅报告，不改代码、不提交、不 spawn、不登记 review-approve、不运行补录脚本或写真实数据库。

## 快照与范围

根目录 `D:/solveproblems/SOP/hengxin-smart-image`。下文 `backend/`、`frontend/`、`docs/` 指代码子目录 `hengxin-smart-image/` 下的路径；Product-Spec 指根目录文件。

审查开始和结束分别执行只读 `review-status`，两次 currentId 均等于上述 candidateId，未观察到代码快照变化；approved 均为 false。此前 reviewedId 为 `d72977c9af60222a295907a95c130640873f2c54e7166263f60c1ab6a2c1b378`。本报告不重新批准全仓脏改动。

范围为 Product-Spec.md:247–249、Product-Spec-CHANGELOG.md:7，以及 review-status 相对此前已批准快照列出的十个文件：

- backend/app/contracts/execution.py
- backend/app/execution/observation.py
- backend/app/execution/public_messages.py
- backend/tests/test_observation.py
- backend/tests/test_public_messages.py
- frontend/src/views/hengxin/components/ExecutionProgress.vue
- frontend/src/views/hengxin/components/TaskDetail.vue
- frontend/src/views/hengxin/components/TaskSources.vue
- frontend/src/views/hengxin/components/execution-presentation.ts
- frontend/tests/execution-presentation.test.ts

补充只读核查现有 API 权限、claim、轮询及 `output/playwright/local-codex/backfill_public_messages.py`。普通 Markdown 不属于代码快照，需求依据另按上述行号记录。

## Stage 1：需修问题

### H1 HIGH：中文及数字开头的绝对路径泄露

**违反 Spec**：Product-Spec.md:248 要求过滤“本地路径”；同节 :254 要求不得暴露“本机路径”。

**位置**：backend/app/execution/public_messages.py:32–34，尤其 :33。

POSIX 路径首字符仅允许 `[A-Za-z_.~]`，中文、数字开头均漏检；:34 的相对路径补偿同样要求 ASCII 字母等起始，不能覆盖这些输入。直接调用真实 public_message 函数复现：

| agent_message.text | 实际输出 | 期望 |
|---|---|---|
| `/客户资料/内部图.png` | `Codex：/客户资料/内部图.png` | 路径不可见 |
| `/2026/客户图.png` | `Codex：/2026/客户图.png` | 路径不可见 |
| `/123/private/result.png` | `Codex：/123/private[路径已省略]` | 不保留私有目录片段 |

输入均为合法 `item.completed / agent_message`，并非 reasoning 或伪造 API 响应。EventTail 在 observation.py:52–55 直接接纳返回值；:124–125 写事件，:108 持久化；modules/tasks/observations.py:39 原样输出 events；ExecutionProgress.vue:48 纯文本显示。因此这是真实公开链路上的过滤缺口，HTML 转义不能阻止路径内容泄露。

修复验收：覆盖 Unicode、数字目录、多级路径及中文标点邻接；不可仅追加固定中文目录名。补充 public_message 和 EventTail/API 回归断言，确认整个路径与私有片段不可见。已有 test_public_messages.py:35–40 未覆盖这些路径。

### H2 HIGH：凭证检查早于文本变换，清理后形成的凭证未再检测

**违反 Spec**：Product-Spec.md:248 要求过滤“凭证”。

**位置**：backend/app/execution/public_messages.py:23–30、:38–41。

SENSITIVE 只在原文检查一次；后续删除代码块和标签会拼接字符，形成此前不存在的凭证关键词，随后直接发布。

| agent_message.text | 实际输出 | 期望 |
|---|---|---|
| `pass<b></b>word=demo123` | `Codex：password=demo123` | 舍弃整条 |
| `to` + 三反引号代码块 `text\nx\n` + `ken=demo123` | `Codex：token=demo123` | 舍弃整条 |
| `password=demo123`（对照） | `None` | 舍弃整条 |

demo123 是审查用假值，未读取或输出真实凭据。披露路径与 H1 相同；一次性历史补录也调用同一函数（脚本 :49、:56–60），因此同样受影响。

修复验收：保留原文检查，并在所有可能拼接文本的变换结束后重新检查最终公开内容；覆盖代码围栏、HTML、链接文字变换等边界。已有 test_public_messages.py:23–26 只覆盖未被拆开的关键词，不能证明此边界安全。规范化后验证的原则可参考 [OWASP Input Validation](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)；本缺陷结论以本地可重复输出为依据。

## Stage 1：逐条对照

“代码匹配”仅表示静态实现与条目相符；不冒充本审查未执行的浏览器或测试结果。

| 验收点 | 结论与证据 |
|---|---|
| 原始 sources、缩略图、名称、数量、原图 | 代码匹配：TaskDetail.vue:16 直接传 task.sources；TaskSources.vue:3、:7–13、:22 渲染数量、名称及原 URL 预览，未取输出版本或模板。 |
| 空、加载、失败态；返工继续原素材 | 代码匹配：TaskSources.vue:5、:10–11；TaskDetail.vue:16 与 :98、:102 的返工参数独立，未替换素材来源。实际图片交互仅有主 Agent 记录 docs/TASK-MATERIALS-BROADCASTS.md:17，本审查未重测。 |
| 只取 completed agent_message | 代码匹配：public_messages.py:12–19 严格检查事件及 item 类型；test_public_messages.py:10–20 有对应用例。 |
| reasoning、工具原文不外露 | 代码匹配此通道边界：observation.py:52–64 只发布筛选消息或固定活动文案；test_observation.py:20–40、:105–117 覆盖工具摘要及 reasoning 排除。不能据此推导 agent_message 内任意敏感内容均安全，见 H1/H2。 |
| 纯文本、限长、控制字符、代码及链接处理 | 代码具备：public_messages.py:18、:20、:25–31、:41；ExecutionProgress.vue:48 使用文本插值。路径和凭证部分失败，见 H1/H2；Spec :248 整条判定为部分实现。 |
| manifest/slot 技术说明 | public_messages.py:37 已有删除规则；test_public_messages.py:32 有断言；独立调用亦确认标准 manifest.json/slot 0 句被移除。该修复不能覆盖 H1/H2。 |
| 明确归属 Codex，不用模型文本修改平台状态 | 代码匹配：public_messages.py:5、:41 添加前缀；ExecutionProgress.vue:44 明确平台校验为准；Observer.event(:78–86) 只添加消息，平台 phase(:88–93) 单独更新；observations.py:21 以数据库终态覆盖。 |
| 默认三条、展开全部保留记录 | 代码匹配：execution-presentation.ts:9、:19；ExecutionProgress.vue:39–49；Observer 保留上限见 observation.py:86。“全部”是当前保留事件而非无限历史。 |
| 系统时间线独立折叠、重复合并 | 代码匹配：ExecutionProgress.vue:52–63；execution-presentation.ts:11–17 按系统事件序列合并；observation.py:81–86 先去除相邻同阶段同文案事件。 |
| 切轮、切任务、切身份重置 | 代码匹配：ExecutionProgress.vue:85–95；execution-presentation.ts:33–38 同步监听上下文；tests/execution-presentation.test.ts:76–117 覆盖重置与同上下文刷新。 |
| 历史 null at 不伪造时间 | 代码匹配：contracts/execution.py:13；execution-presentation.ts:22–23 显示“历史输出，未记录时间”；test_observation.py:118–123 有 API null 用例。 |
| 补录不改状态、结果、绑定、系统事件 | 脚本静态匹配：output/playwright/local-codex/backfill_public_messages.py:35–36 限终态，:39–42 保留非播报事件，:56–60 仅写 observation、at=None，并断言原系统事件前缀相同。未运行脚本或核验真实 DB 前后快照；安全筛选仍受 H1/H2 影响。 |
| 现有权限、claim、轮询保持 | 增量未修改权限/轮询模块；router.py:15、:40–42 保留 SharedUser，observations.py:14–17 校验轮次属于任务；observation.py:98–106 保留当前轮与双 claim 检查。execution-poller.ts:16、:22–26、:34–36 保留身份门禁、过期响应丢弃和停轮询路径；新增展示没有写平台状态入口。此结论为增量静态回归，并非全仓身份隔离审计。 |
| UI 一致性 | TaskSources.vue:2、:24–31 与 ExecutionProgress.vue:2、:107–115 使用既有 ElCard/hx 样式。未提供本轮专门设计稿；未独立打开页面核对视觉或素材失败态，因此不标视觉 PASS。 |
| Spec 漂移 | 本轮组件及展示逻辑均对应 Spec :247–249；未发现增量新增业务页面/API/表。公开消息脱敏未达标，不属于可接受的需求漂移。 |

## 独立复现原始输出

以 `python -B -` 从标准输入运行，用 importlib 加载实际 public_messages.py，不修改文件、不连接数据库。中文输入使用 Unicode 转义，JSON 使用 ensure_ascii=True，避免 Windows 管道编码影响。进程 exit_code=0，原始输出如下：

```text
{"input": "/\u5ba2\u6237\u8d44\u6599/\u5185\u90e8\u56fe.png", "output": "Codex\uff1a/\u5ba2\u6237\u8d44\u6599/\u5185\u90e8\u56fe.png"}
{"input": "/2026/\u5ba2\u6237\u56fe.png", "output": "Codex\uff1a/2026/\u5ba2\u6237\u56fe.png"}
{"input": "/123/private/result.png", "output": "Codex\uff1a/123/private[\u8def\u5f84\u5df2\u7701\u7565]"}
{"input": "pass<b></b>word=demo123", "output": "Codex\uff1apassword=demo123"}
{"input": "to```text\nx\n```ken=demo123", "output": "Codex\uff1atoken=demo123"}
{"input": "api[](https://example.invalid)_key=demo123", "output": "Codex\uff1aapi[]([\u94fe\u63a5\u5df2\u7701\u7565])_key=demo123"}
{"input": "password=demo123", "output": null}
```

## 测试、编译与 Stage 2 边界

docs/TASK-MATERIALS-BROADCASTS.md:13–14 记录主 Agent 执行的 pytest 570 passed/39 skipped、前端 79 passed、typecheck 与 build 成功，但该文件只有摘要，没有编译原始输出。此处不编造日志，不将这些摘要当作独立复跑结果。

本审查实际执行了上述无数据库复现和两次快照检查；没有重跑全套测试、typecheck/build 或付费生成。**编译：本次未执行，无本次编译原始输出。** 已有绿色测试未覆盖 H1/H2，不能消除实测反例。

Stage 1 有 HIGH，按 skill 停止；**Stage 2 代码质量、全面安全扫描、邻居页面实际视觉对比均未执行，不能登记 PASS**。主 Agent 应先修复 H1/H2、补充回归，再重新 review-prepare，从 Stage 1 重派独立审查；已持久化播报是否包含这些边界须另行只读核查，本报告未认定真实数据已泄漏。
