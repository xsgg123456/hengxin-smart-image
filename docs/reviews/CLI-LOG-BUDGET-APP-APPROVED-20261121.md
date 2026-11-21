# 国内与海外 CLI 单轮日志应用审查

**Stage 1 PASS，Stage 2 PASS。** 候选为 `e9218c19591de03d998908101e674c584fee80ad1e58bedd4e4c277d2b9b3707`。开始审查与运行测试后两次取得相同的 `review-status.currentId`。范围为清单中的 30 个后端 Python 文件及其对 Product-Spec.md:1653、DEV-PLAN.md:1891–1892 的实现。以下应用路径相对于 `hengxin-smart-image/backend/`。生产部署属于 DEV-PLAN.md:1893 的下一阶段，本次核对了源码中的正式调用入口。

## Stage 1 · 需求与既有阻断项

| 条目 | 判定与证据 |
| --- | --- |
| 分段编码的图片命令 | PASS。所有 `command_execution` 都进入结构化摘要，无须猜测命令使用哪种解码器；摘要只包含固定枚举、字节数、省略标记、最多两个限长文件名及可选的 32 位退出码。见 app/execution/log_capture.py:18、:158、:176、:194。tests/test_log_capture.py:66 和 :93 分别验证折行 Base64、分段十六进制和自定义数据，逐字段核对实际详细日志，并确认失败状态及合法目标文件名仍可用。本轮 Windows、Linux 均通过。上份报告的 HIGH 在此候选关闭。 |
| 结构化工具结果及迟到的回复 | PASS。详情容器校验元素、重复键和结束状态，数组逐项释放，见 app/execution/capture_json.py:35、app/execution/detail_json.py:44、:50、:74。Linux 真实子进程输出 28,000 个 MCP 片段后，国内外两个正式读端都取得正确会话、完成状态及最终图片链接；非法记录仍被拒绝，见 tests/test_log_capture.py:47、:124。 |
| 跨预算工具状态 | PASS。跟踪已展示工具的 ID，跨预算仍写其终态，见 app/execution/log_capture.py:148、:207、:215。tests/test_log_capture.py:77–91 核对 A、B 两组开始和结束以及后续普通工具 C 的省略，未留下已展示但无法关闭的 A 或 B。 |
| 早期 stderr 诊断 | PASS。凭据错误在行内跨块识别后写固定诊断码，新执行时清除，取消、超时及存储失败保有优先级。见 app/execution/log_capture.py:65、:103、:248，app/execution/credential_errors.py:17、:45。Linux 真实子进程用例将早期错误挤出尾部并再启动一轮，覆盖分类与重置，见 tests/test_log_capture.py:144。 |
| 单轮、合并预算及提示 | PASS。每次 execute 单独创建采集器。两个管道共用 128 MiB 计数，开头空间扣除尾部和摘要预留，保留最近 24 条来源、类型、字节数及省略次数；精简事件仅发送一次。见 app/execution/process.py:43、:87，app/execution/log_capture.py:12、:54、:66、:77、:115、:263。国内和海外分别在 app/modules/domestic_studio/runner.py:135 和 app/overseas/execution/runner.py:137 调用同一 execute；API 对话入口在 app/modules/api_image_edits/conversation_runner.py:181。 |
| 文件传图、独立完成证据与双组交付 | PASS。两组将文件路径带入提示，见 app/execution/workspace.py:28、app/modules/domestic_studio/execution_workspace.py:77、app/overseas/studio/execution.py:101。独立事件记录保留会话、最终回复、用量、必要错误，见 app/execution/capture_json.py:155。Linux 单进程 257 MiB 后晚到的最终链接和完成回执在本次重跑通过，见 tests/test_log_capture.py:181。双组业务测试分别模拟海外命令流和国内 stderr，核验超过 256 MiB、详情文件总预算、实际下载或入库字节、重复调度仅执行一次，见 tests/test_log_budget_delivery_linux.py:53、:62、:76、:88。双组业务用例的运行结果采用派发方此前在 Linux 的成功记录。 |
| 历史会话、取消、超时、失败、恢复 | PASS。旧日志按行读取；本机 tests/test_event_stream_files.py:18、:49 核验超过 64 MiB 的历史日志并拒绝坏证据。恢复入口复核会话、回执、文件摘要和大小，见 app/overseas/studio/recovery.py:68、:86、:97 和 app/overseas/studio/image_recovery.py:66、:94、:110。真实子进程轮询取消、超时、非零退出及磁盘写失败在本次 Linux 回归通过，见 app/execution/process.py:49、:95、:99、:105，tests/test_execution_process.py:15、tests/test_log_capture.py:208。 |
| 工作台和范围 | PASS。复用已存在的 notice，文案在 app/execution/event_file.py:8，共用映射在 app/overseas/studio/transcript.py:17，国内在 app/modules/domestic_studio/transcript.py:45 消费。tests/test_event_stream_files.py:35 核对精简提示先于会话启动时的落库和去重。候选未新增页面、路由或表，也未修改页面样式。独立前端预览和发布工具在派发范围外。 |

## Stage 2 · 代码质量与安全

| 检查 | 结果和依据 |
| --- | --- |
| 职责和边界 | PASS。采集、详情容器校验、安全读取、正式语义解析分别位于 app/execution/log_capture.py:48、detail_json.py:8、safe_stream.py:51、capture_json.py:155。审查的 30 个 Python 文件最长 297 行（tests/test_api_cli_conversation.py），最长实现文件为 276 行（app/execution/log_capture.py）。 |
| 命令执行与文件安全 | PASS。进程通过参数数组启动，提示由 stdin 送入，见 app/execution/process.py:86；tests/test_execution_process.py:27 用真实子进程验证。POSIX 读端逐级禁止跟随链接，并用文件描述符、inode、链接数和读取后复核防止证据被替换，见 app/execution/safe_stream.py:55、:67、:73。对候选文件扫描 shell=True、动态执行、常见硬编码密钥前缀及前端危险输出模式，无命中。 |
| 测试真实性 | PASS。Linux 用例经真正的 stdout/stderr 管道、退出码、进程组和 /dev/full，见 tests/test_log_capture.py:18、:135、:149、:195、:211。双组集成仅替换 CLI 为可控子进程，仍经正式 runner、采集器和交付链，见 tests/test_log_budget_delivery_linux.py:53、:79、:91。 |
| 视觉检查适用性 | 本次未改变渲染页面或布局，新增文案进入已有工作台 notice。实际验证为消息持久化与去重，见 app/overseas/studio/transcript.py:20、tests/test_event_stream_files.py:35；本轮未进行浏览器像素比对。 |

## 本次独立运行记录

编译 30 个候选文件，Python 内置 compile 退出码为 0，原始输出为

```text
30 changed Python files compiled
```

Windows 后端虚拟环境运行 test_log_capture、test_event_stream_files、test_log_budget_delivery_linux、test_execution_process、test_api_cli_conversation、test_studio_skill_trigger。退出码为 0，原始结果行为

```text
33 passed, 9 skipped, 2 warnings, 10 subtests passed in 7.94s
```

隔离 Linux 容器只读挂载当前后端，关闭网络，独立复跑 test_log_capture 和 test_execution_process。退出码为 0，原始结果行为

```text
12 passed, 10 subtests passed in 7.68s
```

Windows 的两条告警来自 Starlette/anyio 测试依赖。Linux 双组数据库交付和更广定向回归属于派发方交接证据，本次独立容器运行统计仅含上述两个测试文件。
