# 国内、海外 CLI 单轮日志应用复审

候选 `a912fb0271ce107ae21d7bd586e3b26c05cce03db5815a35c1262fa4b2d573f7`，main 基线 `0193719`。进入审查和编写报告前两次独立运行 `review-status`，currentId 均匹配。范围为候选所列 30 个后端 Python 文件、Product-Spec.md:1653 和 DEV-PLAN.md 的国内与海外执行日志条目。下文应用文件路径相对于 `hengxin-smart-image/backend/`。内网工具、生产发布以及独立前端预览由其他任务验收。

**Stage 1 FAIL，发现 1 项 HIGH。Stage 2 未执行。** 当前候选已修复旧报告中的四个具体输入，但合法的另一种编码仍能让整张图片进入详细日志。后续代码修改应另行固定候选。

## 阻断项

| 优先级 | 需求与实际差异 | 证据 |
| --- | --- | --- |
| HIGH | Product-Spec.md:1653 要求“命令里的大段编码图像不写入详细日志”。Python 标准库 `bytes.fromhex` 可以从分段十六进制还原图片。该命令的所有图片字节均保留在详情中。 | 生成 32×32 的真实 RGB PNG，把 3,172 字节编码为 84 段、每段最多 76 个十六进制字符，通过相邻 Python 字符串写入普通 `command_execution.command`。经正式 `LogCapture.feed`、`finish` 后，`detail.log` 中的命令与原命令逐字相同。关键字分支和后备正则见 app/execution/log_capture.py:15、:39、:163。现有分片测试仅使用 `base64.b64decode`，见 tests/test_log_capture.py:73。 |

独立复核原始输出：

```text
PNG bytes: 3172 encoded parts: 84 preserved: 84 full original command retained: True
roundtrip bytes match: True
```

## 上次四项及其余需求逐项核对

| 条目 | 结果和依据 |
| --- | --- |
| 28,000 个片段的结构化 MCP 工具结果 | 原问题已修复。大记录的详情容器单独验证语法、嵌套和对象键，同名键按解码后的名称检查。数组中已完成的对象释放后再处理下一项，见 app/execution/capture_json.py:35、app/execution/detail_json.py:44、:50、:74。本机运行合法及重复键、错误分隔符、错误数字等分支通过，见 tests/test_log_capture.py:47。Linux 子进程和双正式读端的最终图片链接断言见同文件:94、:105。 |
| Python 折行 Base64 | 旧例已修复，命中编码关键字后仅输出摘要，保留图片路径。见 app/execution/log_capture.py:161、:172 及 tests/test_log_capture.py:66、:87。其他编码仍违反需求，见上表。 |
| 预算边界前已展示工具的终态 | A 开始后由 stderr 触发精简，B 开始、A/B 结束；已展示工具均获得完成事件，后续完全省略的 C 不会留下运行项。本机用例通过，见 tests/test_log_capture.py:77、:89。集合跟踪与终态处理见 app/execution/log_capture.py:197、:205，国内外公共行消费见 app/modules/domestic_studio/transcript.py:45、app/overseas/studio/transcript.py:32。 |
| 早期 stderr 凭据错误 | 单行关键字跨块匹配，生成固定诊断码，新调用清除旧标记，取消、超时和存储错误优先。见 app/execution/log_capture.py:62、:100、:238，app/execution/credential_errors.py:17、:45。Linux 子进程用例将早期错误挤出尾部后断言分类并再次执行验证重置，见 tests/test_log_capture.py:114。 |
| 单轮独立预算、头部、近期摘要、省略计数和提示 | 每次 execute 新建采集器；stdout/stderr 共用预算，三份详细文件合计受 128 MiB 限制，仅发一次精简事件，保存最近 24 项与省略数。见 app/execution/process.py:85、app/execution/log_capture.py:51、:63、:74、:112、:253。单次提示在会话开始前也能持久化，见 tests/test_event_stream_files.py:35。 |
| 图片路径、迟到回复、完成状态与图片交付 | 路径指引分别接入 app/modules/domestic_studio/execution_workspace.py:78 与 app/overseas/studio/execution.py:102，独立事件序列保留完成、回复与用量，见 app/execution/capture_json.py:155。双组 257 MiB 场景检查落盘大小、精简提示和退出回执，海外检查下载字节，国内核对对象存储的图片字节；重复调度仅执行一次。见 tests/test_log_budget_delivery_linux.py:62、:76、:88。 |
| 历史会话、失败、恢复与禁止自动重跑 | 本机通过双读端 65 MiB 历史流及超限、硬链接拒读用例，见 tests/test_event_stream_files.py:18、:49。恢复仍验证摘要、字节游标、退出回执及会话；图片恢复读取产物前后均核对日志，见 app/overseas/studio/recovery.py:68、:86、:97 和 app/overseas/studio/image_recovery.py:66、:78、:110。取消、超时、磁盘错误及残留进程检查见 app/execution/process.py:49、:55、:98、:105；Linux 进程故障测试见 tests/test_execution_process.py:14、tests/test_log_capture.py:178。 |
| UI 与范围 | 工作台复用已有 notice 记录，文案见 app/execution/event_file.py:8，映射在 app/overseas/studio/transcript.py:19，国内及 API 会话分别在 app/modules/domestic_studio/transcript.py:45 和 app/modules/api_image_edits/conversation_runtime.py:133 消费。候选未新增页面、路由或数据表，未发现应用范围漂移。 |

## 编译与回归

对 30 个变动后端文件运行 Python 内置 compile，退出码 0，原始标准输出：

```text
30 changed Python files compiled
```

Windows 后端虚拟环境运行 pytest，覆盖 test_log_capture、test_event_stream_files、test_log_budget_delivery_linux、test_execution_process、test_api_cli_conversation、test_studio_skill_trigger。退出码 0。原始结果行：

```text
32 passed, 9 skipped, 2 warnings, 10 subtests passed in 7.88s
```

派发方另外报告 Linux 进程测试 8/8、双组 257 MiB 图片交付及下载、定向 51 项及 5 个子测试、前端 616 项通过。上述 Linux 和前端结果为交接证据。本机独立运行的项目和计数见前段。

Stage 1 的 HIGH 触发 code-review 技能的停止条件。本报告不提供 Stage 2 PASS 或批准凭据。
