# 内网国内现有功能验收范围审阅

- candidateId：`bc6c7c26b148e39b0589889dc4347fcd13ab60d2240235944a0cf01a24bab222`
- 日期：2026-11-11。执行技能：`.agents/skills/code-review/SKILL.md`。
- 范围：国内 API 新建换套图、记录、图片预览、API 文字修改/修复文案、Codex 图片修改会话/标注/候选采用、历史恢复及下载；附并发和只读数据库验收指标。
- 本报告为 Stage 1 静态范围梳理，不是运行验收 PASS。未连接服务器、未操作浏览器、未调用模型、未修改业务代码。实际运行证据由主 Agent 收集后再独立审阅。
- 用户最新收敛：3个任务各1张原图，总共3张API输出，复用其中2–3张验证Codex并行；表中分支是覆盖目录，不要求为每项新增收费图片，也不声称本轮能覆盖所有故障/历史兼容分支。
- 用户本轮授权在 .245 真实生成与修改；公网旧生产仅只读取素材。历史条款中的禁止收费测试不阻止本轮已授权测试。旧 CLI 工作流与国内 Skills 不恢复、不列为必测（Product-Spec.md:5，docs/INTRANET-245-PLAN-20261110.md:21）。

## 1. 当前契约与入口

下文 `F/` 为 `hengxin-smart-image/frontend/src/views/hengxin/api-image-edits/`，`B/` 为 `hengxin-smart-image/backend/app/modules/api_image_edits/`。表中“待实测”表示存在静态入口，并不代表功能已运行通过。

| 范围 | 当前操作与验收分支 | 静态证据 | 状态 |
|---|---|---|---|
| 新建换图 | `/api-image-edits/create`；上传前 N 张原图和末张共用素材；点击/拖拽/粘贴、拖动排序/前后移/设为素材、移除、失败重传；限制 JPG/PNG/WebP、单图10 MiB、20原图+1素材 | F/RealImageSequence.vue:2、4、13、14 | 待实测 |
| 输入与提交 | 名称最多60字、提示词最多4000字；默认完整提示词允许编辑/清空；至少1原图+1素材；上传完成才可提交；切页保留草稿；未知结果确认复用原请求 | F/RealCreate.vue:6、12、20、21；Product-Spec.md:153 | 待实测 |
| 提交落点 | 提交后进入 `/api-image-edits/records?task=ID`，关闭页面不取消后台生成；结果按原图顺序 | F/RealCreate.vue:22、40 | 待实测 |
| 记录筛选 | 默认我的任务；全部任务及创建人；状态、今天/7天/30天/自定义时间、名称/编号搜索、重置、刷新、分页、统计随范围变化 | F/RealRecords.vue:4、10、11、12、13、14；F/use-records.ts:26、36、90、91 | 待实测 |
| 详情/预览 | 记录打开详情；共用素材；每图原图/成品对照；结果原图放大；折叠输入与提示词；CLI活动状态与原API任务状态分开展示 | F/RealTaskDetail.vue:18、21、22、23、36 | 待实测 |
| API初始生成 | 新建整套走 API；逐图成功/失败/等待/重试；成功图片保留；最终 PNG 与最初原图宽高一致 | Product-Spec.md:152、160、83；B/dimensions.py:30；B/models.py:98 | 待实测 |
| 修改执行器 | 当前无 API/Codex 选择器。弹窗只有“图片修改/文字修改”；图片修改自动走 Codex 会话，文字修改走 API revise | Product-Spec.md:1023；F/RealRevisionDialog.vue:4、48、98 | 静态匹配，待实测 |
| Codex首轮 | 详情成品卡“修改图片”→图片修改→输入意见/可选标注→预览提交内容→确认；默认当前正式成品+原图+素材+可选标注 | F/RealTaskDetail.vue:28；F/ImageConversationEditor.vue:7、47、88、95 | 待实测 |
| Codex续聊 | 同一item精确会话；关闭重开/刷新恢复；候选作为下一轮底图；历史展开选正式版本或旧候选；纯文字回复继续意见；每轮素材/提示词冻结 | Product-Spec.md:1024、1025、1027、1029；F/ImageConversationEditor.vue:52、57、74、88 | 待实测 |
| 候选采用 | 生成候选不改变正式图片；“采用此图”才增加并切换版本；并发采用校验 expectedVersion；失败/停止不覆盖旧成品 | F/RealRevisionDialog.vue:16；F/ImageConversationEditor.vue:107；B/conversation.py:176、184、189、196 | 待实测 |
| 活动与停止 | 详情/记录显示等待修改或图片修改中；同item活动互斥；关闭弹窗后台继续；停止本轮有真实停止状态；SSE断线/重连按事件号恢复，不重复提交 | Product-Spec.md:1028、1030、1269；F/ImageConversationEditor.vue:38、43、111；B/conversation_router.py:32、54、57 | 待实测 |
| API文字修改 | 切换文字修改，当前成品+可选标注，必须文字意见；提交预览检查模式/图数/完整提示词；成功自动成为新正式版本 | Product-Spec.md:135、139、150、151；F/RealRevisionDialog.vue:10、65、77、104 | 待实测 |
| 修复文案 | 成品卡“修复文案”直接提交，不要求意见；当前成品+对应最初原图、不带共用素材；新版本标记操作类型 | Product-Spec.md:149；F/RealTaskDetail.vue:29、87、90 | 待实测 |
| 标注 | 框选/画笔、编号与逐条意见、整体意见、撤销/删除/清空、拖动/缩放/平移、已有标注上传/拖拽/粘贴、三/四图预览；图片与文字模式草稿隔离；新候选底图不继承旧标注 | Product-Spec.md:265、1014、1029；F/RealRevisionDialog.vue:10、65；F/ImageConversationEditor.vue:46 | 待实测 |
| 历史版本 | 详情历史版本，选中预览/对照/下载；恢复弹窗确认，不重新生成、不删除其他版本；后续修改与ZIP用恢复版 | F/RealTaskDetail.vue:30；F/RealVersionDialog.vue:77、83、89 | 待实测 |
| 下载 | 单张当前成品、历史版本、整套ZIP；整套要求每张 succeeded 且有 result；比较下载字节/PNG尺寸与版本fileId对应 | F/RealTaskDetail.vue:9、25、76、108；F/RealVersionDialog.vue:73；B/router.py:59、161 | 待实测 |
| 重试/停止 | 未完成整套重试、失败单张重试、自动重试停止；未知提交显示确认原请求；保留已成功结果；失败不覆盖已有版本 | F/RealTaskDetail.vue:11、31、95；F/ItemRetryStatus.vue:16、23；Product-Spec.md:79、83 | 待实测 |
| 删除 | 活动任务禁止；空闲测试任务可走确认/取消/删除回执；必须物理清理完成才移除；不得用旧生产任务测试 | Product-Spec.md:1271、1273、1275；F/use-records.ts:104、113、119；B/deletion_models.py:11 | 待实测；仅当主Agent纳入测试任务清理 |

## 2. 不应误列为当前可点击功能

1. “API / Codex 执行器选择”不存在，是修改类型决定通道；符合最新 Product-Spec.md:1023。旧 API `image_edit` 1/2/3/4图冻结重试属于兼容分支，不可从普通新图片修改操作创建；`F/RealRevisionDialog.vue:48` 总是进入 CLI，只有旧 pending 才走原 API 确认。
2. 已退役图片处理/任务中心/模板/归档/国内 Skills 地址会重定向。代码：`hengxin-smart-image/frontend/src/router/business-route-access.ts:13`、`:18`。不能因仓库仍有旧实现就要求跑旧整套 CLI 工作流。
3. 会话过期分支依赖真实 retention.status=expired；界面“开启新会话”不是常驻随意重置按钮。`F/ImageConversationEditor.vue:30`、`:64`、`:88`。三天清理、24小时缓存按 Product-Spec.md:75，不能沿用旧7天。
4. 无管理员“核实未知API结果”的必测按钮；最新要求取消此门槛（Product-Spec.md:79）。CLI uncertain 不受这一 API 简化覆盖。

## 3. 并发与只读核验

- API任务调度上限5，单任务按10图分批（B/scheduling.py:5、:6、:21、:25、:30）。最新通道另有默认每5秒1次发送、最多10在途，不应按旧50张预期真实调用并发（Product-Spec.md:83，B/config.py:26、:27）。收集 .245 生效配置，不能把默认值当已部署事实。
- 统计在途必须按 `ApiItem.state == uncertain OR 存在 running attempt`，不能只看任务 running 数（B/limiter.py:10）。还要记录冷却、单探测、next_send_at，限制可能使并行提交实际串行发送（B/limiter.py:17）。等待且无在途释放任务槽（B/scheduling.py:17、:28）。
- CLI计数 `job_records.kind=api_cli_edit` 且 status∈running/collecting/cancelling/uncertain；上限取冻结 concurrency 与当前配置最小值（B/conversation_runtime.py:72）。配置默认1不代表 .245 实际1（backend/app/core/config.py:47）。同item活动轮互斥（B/conversation.py:18、:46）。
- 建议同时提交若干不同测试任务并轮询时间线；证明不同task/item归属、候选/输出不串、没有超配额。仅最终都成功不足以证明并发重叠；保留 started_at/finished_at 或attempt created_at/completed_at区间。

| 表 | 只读指标与关联 | 证据 |
|---|---|---|
| api_image_tasks | id/name/owner_id/operator_id/material_id/state/started_at/completed_at；测试名与taskId固定映射 | B/models.py:31 |
| api_image_items | task_id/position/source_id/result_id/current_version/state；按position逐张对应原图；revision_snapshot、attempts、retry_cycle_id、next_attempt_at | B/models.py:50 |
| api_image_files | id/checksum/size_bytes/content_type/width/height/status；对生产只读取原图/素材副本，.245上传后核对哈希；输出/下载/ZIP逐张核对 | B/models.py:14 |
| api_image_attempts | item_id/state/created_at/completed_at/request_width/height/return_width/height/request_id；区别调用计数与任务数 | B/models.py:90 |
| api_image_versions | item_id/number/file_id/kind/base_version；候选未采用时版本数不增，采用只增一次，恢复只改当前引用 | B/models.py:145；B/conversation.py:189 |
| api_image_operations | operator_id+key唯一、payload_hash；重复确认不创建新操作 | B/models.py:117 |
| api_image_channel | paused/next_send_at/cooldown_until/probe_attempt_id/recovering/recovery_limit | B/models.py:127 |
| api_image_dispatch / api_worker_heartbeats | 排队派发/完成与真实worker心跳，不能只以HTTP健康代表可执行 | B/models.py:109；B/heartbeat_models.py:10 |
| api_edit_conversations | item_id/session_id/last_event_id；跨轮session_id保持、跨item不同 | B/conversation_models.py:11 |
| api_edit_turns | conversation_id/job_id/status/base_version/base_turn_id/base_file_id/annotation_id/candidate_id/adopted_version/started_at/finished_at | B/conversation_models.py:19 |
| api_edit_events | conversation_id+number唯一；关闭重开恢复后不丢失、不重复展示 | B/conversation_models.py:43 |
| job_records | 与turn.job_id关联；执行次数及活动状态，停止/失败/候选完成可交叉核对 | B/conversation_models.py:22；B/conversation_runtime.py:72、:84 |

只读核查不导出凭据、原始process_identity、内部完整执行日志；用任务/图片/会话ID及安全状态、必要图片摘要形成证据。

## 4. 可疑行为与尚未证实的问题

- 待验证（不定级为已证实缺陷）：成品卡 `canRevise` 仅检查 API item.state、通道和本地命令，没有检查 cliActivity（F/RealTaskDetail.vue:83）。这允许活动 CLI 期间重新打开会话，属于必要行为；但同卡“修复文案”也可能保持可点。实测应验证服务器拒绝与 CLI 同图并发返工且不新增收费调用，不能仅以按钮可点击就判数据竞争。
- 待验证：390px窄窗口，修改编辑器在900px以下有600px最小高度（F/RealRevisionDialog.vue:132），需实际确认标注区/意见/提交按钮可滚动到达；静态CSS不能证明不可用，也不能证明通过。
- 迄今未发现足以凭静态证据认定的 HIGH 缺失；未对整个仓库历史Spec逐条做全量审查。本报告只覆盖所派发当前国内范围。

## 5. 快照、编译与阶段状态

审查时只读 `review-status` 原始输出：

```text
{"currentId": "bc6c7c26b148e39b0589889dc4347fcd13ab60d2240235944a0cf01a24bab222", "reviewedId": "bc6c7c26b148e39b0589889dc4347fcd13ab60d2240235944a0cf01a24bab222", "changedFiles": [], "approved": true}
```

该结果只表示既有快照凭据匹配，不表示本次真实端到端验收通过。未执行编译，故无编译原始输出。Stage 1：等待真实运行证据；Stage 2：未执行（不在本次静态范围梳理任务内）。不得据本报告新增两阶段 PASS 或向 `.needs-review` 写 clean。后续代码变化须重新固定快照并复核。
