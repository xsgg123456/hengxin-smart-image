# 任务素材与 Codex 播报第二次独立审查

- 日期：2026-09-11。
- candidateId：`cab7ec014ce5aab1d4214748c4f9ca24a4512ca097bb81db60e14be827a4da6a`。
- **Stage 1：FAIL（1 项 HIGH）；Stage 2：未执行。不得登记两阶段 PASS。**
- 先读取 code-review/SKILL.md、docs/HARNESS-REVIEW.md、旧报告 TASK-MATERIALS-BROADCASTS-REVIEW.md，再核对当前实现；不沿用旧 candidate 的批准结论。

## 快照与审查范围

根目录 `D:/solveproblems/SOP/hengxin-smart-image`；以下 backend/、frontend/、docs/ 均相对其 `hengxin-smart-image/` 子目录。需求为根目录 Product-Spec.md:247–249、关联公开安全约束 :254，以及 Product-Spec-CHANGELOG.md:7–9。实现说明为 docs/TASK-MATERIALS-BROADCASTS.md:5–19。

开始及报告落盘前两次只读 review-status 的 currentId 均为本次 candidateId，approved 均为 false；未观察到代码快照变化。reviewedId 均为 `d72977c9af60222a295907a95c130640873f2c54e7166263f60c1ab6a2c1b378`。本次只审此前已批准快照之外的下列十文件增量，不审全仓其它已有功能：

1. backend/app/contracts/execution.py
2. backend/app/execution/observation.py
3. backend/app/execution/public_messages.py
4. backend/tests/test_observation.py
5. backend/tests/test_public_messages.py
6. frontend/src/views/hengxin/components/ExecutionProgress.vue
7. frontend/src/views/hengxin/components/TaskDetail.vue
8. frontend/src/views/hengxin/components/TaskSources.vue
9. frontend/src/views/hengxin/components/execution-presentation.ts
10. frontend/tests/execution-presentation.test.ts

补充只读核对原有 API、权限、轮询及 output/playwright/local-codex/backfill_public_messages.py；未运行补录、重启服务、写实际数据库、改代码、commit、spawn 或 approve。仅新增本报告。

## Stage 1：HIGH 安全问题

### H1-R：数字单级绝对路径仍原样公开

**违反需求**：Product-Spec.md:248 要求过滤“本地路径”，:254 要求不得暴露“本机路径”。

**位置**：backend/app/execution/public_messages.py:33–34。

第33行的 `(?!\d+(?:\s|$|[，。；）)]))` 不仅保留分数、日期，还无条件豁免 `/123`、`/2026` 等单级数字绝对路径，即使上下文明确写“工作目录”。第34行要求 ASCII 字母等起始，不能补救。独立调用实际 public_message，输入为正常 completed agent_message：

| 输入 | 实际输出 | 判定 |
|---|---|---|
| `工作目录：/123` | `Codex：工作目录：/123` | FAIL，完整本地路径公开 |
| `工作目录：/123。` | `Codex：工作目录：/123。` | FAIL，句号结尾同样漏检 |
| `工作目录：/2026\n继续处理` | `Codex：工作目录：/2026\n继续处理` | FAIL，换行结尾同样漏检 |
| `/123/` | `Codex：[路径已省略]` | PASS，相同目录加尾斜杠才过滤 |
| `/123/result.png` | `Codex：[路径已省略]` | PASS，多级路径修复有效 |
| `第 1/2 张，2026/09/11 完成。` | 原文加 Codex 前缀 | PASS，分数/日期保留 |

公开链路证据：observation.py:52–55 接受非空返回，:124–125 加入事件，:108 持久化；modules/tasks/observations.py:39 输出保存的 events；ExecutionProgress.vue:48 文本插值显示，没有第二次路径过滤。此结论证明可公开链路的缺口，不声称实际数据库已经出现泄露。

测试缺口：test_public_messages.py:35–41 的数字例子是 `/123/private/result.png`，test_observation.py:109、:118 是 `/123/private.png`；二者均不能证明单级 `/123` 被过滤。不应把这些用例概括为已覆盖所有数字目录。

修复验收：数字单级绝对路径在句尾、标点前、空白前均不可见，同时保留合法分数及日期；应区分上下文中的数字表达式与绝对路径，不能仅凭斜杠后全为数字就整体豁免。补纯函数和测试 API 断言后重新固定快照。本问题与旧 H1 属于同一需求缺口的相近边界，不扩展范围。

安全原则参考：OWASP 建议同时进行语法及业务语义验证，并指出仅依赖禁止模式存在绕过风险；本报告的 FAIL 依据是上述本地实际输出，而非泛化风险推测。[OWASP Input Validation](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)

## 旧反例复核

| 旧项及相近边界 | 本轮结论与证据 |
|---|---|
| H1 `/客户资料/内部图.png`、`/2026/客户图.png`、`/123/private/result.png` | 原三条反例均修复，实际输出仅 Codex 前缀及路径占位；public_messages.py:33。H1 整体仍因 H1-R 不通过。 |
| H2 `pass<b></b>word=demo123` | 返回 None，原反例修复；public_messages.py:30、:39。 |
| H2 `to` + 三反引号围栏 `text\nx\n` + `ken=demo123` | 返回 None，原反例修复；public_messages.py:25、:39。 |
| 波浪线围栏拼接 password、Markdown 链接文字拼接 password | 两条均返回 None；public_messages.py:26、:28、:39，最终检查覆盖这些变换。 |
| H2 检查顺序 | 原文检查 :23 保留，格式清理及 strip 后 :39 再查，之后仅加固定前缀及限长 :41；本轮复核 H2 PASS。 |

## Stage 1：范围内逐项对照

以下“代码匹配”指本轮阅读当前实现所得，不冒充未运行的浏览器验证或测试结果。

| Spec 验收点 | 当前实现与判定 |
|---|---|
| :247 冻结 sources、数量、名称、缩略图、原图 | 代码匹配：TaskDetail.vue:16 传 task.sources；TaskSources.vue:3、:7–13、:22 使用同一 sources 的 URL。未以输出图或当前模板替代。 |
| :247 空态、加载/失败可辨认、整套/单图返工原素材 | 代码匹配：TaskSources.vue:5、:10–11；TaskDetail.vue:98、:102 的返工参数不替换 :16 素材来源。实际原图交互本轮未重测。 |
| :248 仅 user-facing agent_message | 代码匹配：public_messages.py:12–19 限定 completed 与 agent_message；test_public_messages.py:10–20 覆盖错误通道/畸形输入。 |
| :248 reasoning、命令及工具原文不公开 | 通道选择代码匹配：observation.py:52–64 只取筛选消息或固定活动文案；test_observation.py:20–40、:105–120 有事件文件至 API 的用例。不能据此宣称该通道内任意文本均安全，见 H1-R。 |
| :248 纯文本、限长、代码块、链接目标、控制字符 | 代码匹配：public_messages.py:18、:20、:25–31、:41；ExecutionProgress.vue:48 纯文本插值；test_public_messages.py:50–64 包含相关断言，本轮未复跑这些测试。 |
| :248 路径、凭证 | **部分实现**：旧 H2 PASS；路径剩余 HIGH，见 H1-R。最终文本二次 SENSITIVE 检查见 :39。 |
| :248 技术清单语句 | 代码匹配实现说明：public_messages.py:37 删除 manifest/slot 语句，test_public_messages.py:32 保留普通图片说明并排除清单说明。 |
| :248 Codex 归属，模型文本不改平台验收 | 代码匹配：public_messages.py:5、:41；ExecutionProgress.vue:39、:44；Observer.event :78–86 仅记事件，phase :88–93 独立更新阶段；observations.py:21 以数据库终态为准。 |
| :249 默认最近几条、展开全部保留记录 | 代码匹配：execution-presentation.ts:9、:19 默认3条；ExecutionProgress.vue:39–49；test execution-presentation.test.ts:20–31。事件上限仍为 observation.py:86 的100条，不声称无限历史。 |
| :249 系统时间线独立折叠、连续重复合并 | 代码匹配：ExecutionProgress.vue:52–63；execution-presentation.ts:11–17 按系统事件序列合并并区分阶段、时间有无；对应测试 :34–52。 |
| 切任务/身份/轮次重置，刷新保留展开状态 | 代码匹配实现说明 :9：ExecutionProgress.vue:85–95；execution-presentation.ts:33–38 同步监听；对应测试 :76–117 覆盖重置及同上下文刷新。 |
| :249 历史补录无伪造时间 | 代码匹配：contracts/execution.py:13 允许 null；execution-presentation.ts:22–23 明确历史时间缺失；test_observation.py:121–126 经 API 验证 null 的测试存在。 |
| :249 补录不改状态/结果/绑定/系统事件 | 脚本只读核对：backfill_public_messages.py:35–36 限已结束轮次，:39–42 保留非播报事件，:54 限上限，:56–60 仅 observation 并断言原系统事件相同。安全过滤共享 public_message，因此同受 H1-R 影响；未运行脚本或核查真实 DB 前后。 |
| 既有权限、claim、轮询回归 | 代码匹配增量边界：router.py:15、:40–42 保留 SharedUser；observations.py:14–17 校验轮次归属；observation.py:98–106 当前轮及双 claim 检查；components/execution-poller.ts:16、:22–26、:34–36 保留身份、过期响应和取消轮询。不是全仓权限审计。 |
| UI 一致性与引导真实性 | 组件代码使用既有 ElCard/hx 样式：TaskSources.vue:2、:24–31；ExecutionProgress.vue:2、:107–115。预览及展开文案都有对应处理。本轮未打开实际页面，不将主 Agent 的大图/窄屏/切轮截图说明当独立视觉 PASS。 |
| Spec 漂移 | 本轮新增素材组件、播报转换与 DTO 时间兼容对应 :247–249；未发现范围内新增无需求业务页面/API/表。依据 TaskDetail.vue:16、TaskSources.vue:1–32、execution-presentation.ts:1–40、contracts/execution.py:9–13。 |

## 独立运行证据与编译边界

使用 `python -B -` 经 importlib 加载实际 public_messages.py；不导入数据库模块，不创建文件。输入中文用 Unicode 转义，JSON ensure_ascii=True。两次复现均 exit_code=0。关键原始输出：

```text
{"input": "/123/private/result.png", "output": "Codex\uff1a[\u8def\u5f84\u5df2\u7701\u7565]"}
{"input": "pass<b></b>word=demo123", "output": null}
{"input": "to```text\nx\n```ken=demo123", "output": null}
{"input": "pass~~~text\nx\n~~~word=demo123", "output": null}
{"input": "[pass](https://example.invalid)word=demo123", "output": null}
{"input": "\u5de5\u4f5c\u76ee\u5f55\uff1a/123", "output": "Codex\uff1a\u5de5\u4f5c\u76ee\u5f55\uff1a/123"}
{"input": "\u5de5\u4f5c\u76ee\u5f55\uff1a/123\u3002", "output": "Codex\uff1a\u5de5\u4f5c\u76ee\u5f55\uff1a/123\u3002"}
{"input": "\u5de5\u4f5c\u76ee\u5f55\uff1a/2026\n\u7ee7\u7eed\u5904\u7406", "output": "Codex\uff1a\u5de5\u4f5c\u76ee\u5f55\uff1a/2026\n\u7ee7\u7eed\u5904\u7406"}
```

主 Agent 提供全后端573 passed/39 skipped、补断言后定向36 passed、前端79 passed、typecheck/build成功；docs/TASK-MATERIALS-BROADCASTS.md:13–14 仅含摘要。**本轮未重跑全量/定向 pytest、前端测试或编译；无本轮编译原始输出，不伪造或用摘要代替。** 本轮独立证据为真实过滤函数输出和当前代码核查。

## Stage 2

**未执行**。按 code-review/SKILL.md 的“Stage 1 有 HIGH 问题就停在 Stage 1”，本轮不执行 Stage 2 质量、全面安全扫描及邻居页面实际视觉对比。Stage 1 失败不得批准该 candidate；修复 H1-R 后应重新 review-prepare，从 Stage 1 复核新快照，随后才进入 Stage 2。
