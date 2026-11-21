# 国内与海外 CLI 单轮日志应用审查

候选 `480ae63574eb4776584ed99a0ec32a739413b9fc498e6e0c98ec7f7399dfaccc`。审查开始时，`review-status.currentId` 与派发编号相同。基线为 main 的 `0193719`。范围为应用后端、相应测试、Product-Spec.md 第 1650–1652 行和 DEV-PLAN.md 第 1891–1892 行。发布工具、部署、未跟踪的前端独立预览由其他任务处理。下文应用路径从 `hengxin-smart-image/backend/` 起算。

**Stage 1 FAIL。Stage 2 未执行。** 同一份合法工具输出经新采集后，两组原本可交付的最终图片均被拒绝。另有可重建的编码图片写入详细日志、工具状态失真及必要诊断丢失。

## Stage 1 退回项

| 优先级 | 要求及差异 | 独立验证及代码位置 |
| --- | --- | --- |
| HIGH | Product-Spec.md:1652 要求大输出精简后继续交付。合法的结构化 MCP 结果会使整轮失效，即使记录远小于预算。 | 给 `LogCapture.feed` 每次传入 64 KiB。一个 `mcp_tool_call.result.content` 包含 28,000 个正常文本片段，行长 840,094 字节，随后是最终图片链接和完成事件。两组解析原流均交付，采集后两组均返回 `invalid_event_stream`。`app/execution/capture_json.py:48` 在应被精简的结果中累计标点，超限在第 51 行抛错。`app/execution/log_capture.py:117` 将合法记录写为 `null`。国内监视器可因此主动停止执行，见 `app/modules/domestic_studio/transcript.py:48`。 |
| HIGH | Product-Spec.md:1652 要求命令里的大段编码图片不写入详细日志。Python 合法的相邻字符串字面量会原样落盘。 | 用 32×32 RGB 图生成 3,172 字节 PNG，将 Base64 按每行 76 个字符折为带引号的字符串，传给 `base64.b64decode(...)`。写入普通 `command_execution.command` 后，`detail.log` 的命令与原命令相等，全部 56 段均可读。`app/execution/log_capture.py:14` 和第 35 行的过滤器只处理连续串和空白分隔的折行，第 130 行直接采用该结果。 |
| MEDIUM | 已经对工作台展示的工具在结束后仍显示运行中，破坏两组既有过程语义。 | 先记录 A.started，通过 stderr 跨过预算，再依次记录 B.started、A.completed、B.completed、turn.completed。用工作台实际的 `public_item` 解码，只剩 A.running、精简提示、B.running、B.completed。合并器仅保存首个代表工具的终态，见 `app/execution/log_capture.py:139`、第 148 行。海外状态计算见 `app/overseas/studio/transcript.py:32`，国内共用读取见 `app/modules/domestic_studio/transcript.py:45`。 |
| MEDIUM | Product-Spec.md:1652 要求必要错误证据独立保存。仅经 stderr 报告的早期凭据错误随尾部滚动消失。 | 第一行写入 `codex_login::auth failed to refresh token`，随后写 4,096 行普通进度，传入非零退出回执。实测分类为 `execution_failed`。此例中普通详情尚保有原诊断，但分类器只读 stderr 尾部。`app/execution/log_capture.py:162`、`app/execution/credential_errors.py:33`。现有早期诊断用例只覆盖 JSON error 事件，见 `tests/test_event_stream_files.py:61`。 |

## 其余验收条目

| 条目 | 核对结果 |
| --- | --- |
| 每轮共享 128 MiB、近期摘要及省略数 | stdout/stderr 共用字节计数和开头预算，另预留 128 KiB stderr 尾部及 64 KiB 汇总空间，保留最近 24 条来源、类型、长度和省略计数。见 `app/execution/log_capture.py:11`、第 48、72、90、188 行。两组大输出测试以三文件总尺寸断言，见 `tests/test_log_budget_delivery_linux.py:62`。 |
| 图片路径、精简提示 | 两组工作台输入图片时附加路径指引，见 `app/modules/domestic_studio/execution_workspace.py:78`、`app/overseas/studio/execution.py:102`。精简事件仅首次写入，见 `app/execution/log_capture.py:65`。国内与海外工作台共用消息映射，见 `app/overseas/studio/transcript.py:19`、`app/modules/domestic_studio/transcript.py:45`。本地测试验证早于 thread.started 的提示也只保存一次，见 `tests/test_event_stream_files.py:35`。 |
| 完成、最终回复、图片及会话证据 | `app/execution/capture_json.py:148` 单存会话、轮次、回复及用量。大单串命令及 stderr 模式已有覆盖，Linux 两组图片断言见 `tests/test_log_budget_delivery_linux.py:76`、第 88 行。派发方提供两组 Linux 运行通过及前端 616/616，审查本机为 Windows。结构化 MCP 失败已在上表实证。 |
| 旧日志和历史恢复 | 共享流式读端支持旧 JSONL，审查本机通过两组解析同一份超过 64 MiB 的历史文件、拒绝硬链接及单行超限用例，见 `tests/test_event_stream_files.py:18`、第 49 行。海外恢复仍以原始摘要、字节游标、会话及退出回执为证据，见 `app/overseas/studio/recovery.py:59`、第 68、86、97 行和 `app/overseas/studio/image_recovery.py:59`。上述新采集时丢失的有效记录无法通过这些校验恢复。 |
| 取消、超时、磁盘错误和重跑 | `app/execution/process.py:55` 检查取消及超时并在第 98 行收进程，捕获 ENOSPC 等写错误为 storage_failed，再于第 105 行检查进程组。Linux 真进程取消超时和 /dev/full 用例分别见 `tests/test_execution_process.py:14`、`tests/test_log_capture.py:95`。本地未复跑 Linux 专项。历史修复的执行次数校验见 `app/overseas/studio/recovery.py:59`。 |
| UI 一致性与范围 | 本候选通过既有工作台的 notice 行显示过程提示，见 `app/overseas/studio/transcript.py:19`。审查范围内没有新页面、布局、API 路由或数据库表。 |

## 编译及运行证据

对 29 个发生变化的后端 Python 文件逐一执行内置 `compile(source, path, 'exec')`。原始标准输出如下，退出码为 0。

```text
29 changed Python files compiled
```

Windows 后端虚拟环境执行 `python -m pytest -q -p no:cacheprovider tests/test_log_capture.py tests/test_event_stream_files.py tests/test_log_budget_delivery_linux.py`。原始结果行如下。

```text
6 passed, 4 skipped, 2 warnings, 5 subtests passed in 4.81s
```

使用同一进程和两个正式读端重放结构化工具事件，原始结果如下。

```text
legacy.jsonl parse_events None True ![result](/work/result.png)
legacy.jsonl read None True ![result](/work/result.png)
events.jsonl parse_events invalid_event_stream False None
events.jsonl read invalid_event_stream False None
MCP record bytes: 840094
stderr-only early failure classification: execution_failed detail retained: True
PNG bytes 3172 Base64 parts 56 preserved 56 identical command True
```

收尾时再次运行 `review-status`，工作区编号已变为 `d134f4af89f952c78ff6a692a74eb8b2b8724a8eff9d69f48f5b8938aed4bd48`。本报告的复现和结论归属开头所列候选。下一次送审应重新固定候选并验证以上四个输入。
