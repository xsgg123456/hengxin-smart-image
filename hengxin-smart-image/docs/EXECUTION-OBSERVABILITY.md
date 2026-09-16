# 生图过程可观测：实现与验收任务

依据PRD“生图过程可观测补充”，实现顺序：

1. 后端持久化：execution_attempts增加nullable JSON observation，旧记录兼容；只在当前claim有效时更新实时事件，每2秒最多落一次心跳，阶段变更立即记录。事件只写固定摘要，最多100条；不得让观测错误触发重复执行。完成标准：阶段/心跳跨API重启可读、旧claim不覆盖新状态。
2. 失败诊断：区分启动、CLI超时/退出、输出清单、来源验证、图片校验、存储和发布失败；安全解释Skill清单的逐图错误。完成标准：截图中尺寸失败可见具体归类和建议，敏感文本不进入API，原执行状态不变。
3. 详情接口：GET /api/v1/tasks/{id}/execution，可选roundId查询历史轮次，沿用shared_resources权限和任务删除检查，禁止跨任务轮次读取。不从API进程读取Worker文件系统。
4. 前端：任务详情增加过程卡片，当前阶段、耗时、最后活动、发现图片数（待校验）、时间线及错误建议、可复制诊断编号。每2秒读取当前活动轮次，终态停止，离开清理，切任务不串响应。旧记录/fixture明确说明缺少详细观测；请求错误有重试入口。复用现有Art/Element Plus样式，小屏不溢出。
5. 验证：单测覆盖日志增量/半行/错误文本脱敏、终态/旧claim保护、接口权限/旧数据；前端契约/时间格式测试及typecheck，浏览器验证截图中的失败任务原因可见，以及真实Worker阶段更新。独立两阶段review后登记候选。

## 接口约定

响应字段：taskId、roundId、status（原round数据库状态）、source（cli/fixture/unavailable）、diagnosticId（attempt UUID或null）、stage、label、startedAt、finishedAt、updatedAt、lastActivityAt、totalImages、detectedImages（未知为null）、legacy（boolean）、events、failure。

时间为ISO8601字符串或null；stage使用queued/preparing/starting/generating/validating/storing/publishing/completed/failed/cancelled/uncertain。stage表达已观测阶段，终态由数据库状态覆盖，不能显示旧心跳为执行中。

events每项：sequence（整数）、stage、message（固定业务摘要）、at（ISO8601）。failure为null或{code,message,action,stage,slotErrors:[{slot,code,message}]}。slot为原任务从0开始的位置。前端正文使用message/action，code和diagnosticId只用于诊断详情。

本版不提供虚构百分比/预计完成时间，也不声称已接入OpenTelemetry。task/round/attempt标识用于关联后端证据；后续可按OpenTelemetry扩展trace关联与聚合告警。

## 开发机验证记录（2026-09-11）

- Ubuntu 24.04 WSL 后端全量 pytest：546 passed、39 skipped（现有平台/外部环境条件用例），无失败。包含新增诊断、安全清单读取、事件增量、旧claim隔离、授权和迁移兼容、真实runner编排中的故障分支。
- Node 24.18.1 / pnpm 10.33.4：前端 typecheck 退出码0，测试69/69通过。覆盖迟到响应、终态停止HTTP轮询、历史轮次、格式与权限身份切换。
- 前端生产构建 `pnpm build` 成功，3311模块，Vite阶段32.05秒；存在既有登录组件同时静态/动态导入提示。后端Docker镜像构建成功。
- 本地 PostgreSQL 已升级至0008，API/Outbox/WSL真实Worker已重启。未改变现有任务结果和文件。
- 历史失败任务633a1c0b-b480-497b-b4fe-7939511e15e4：按保留的manifest安全补充逐图尺寸诊断。API与页面均显示输出1254×1254、目标800×800，标记Skill报告；legacy=true且events为空，不伪造历史过程。
- 真实新任务95216b25-fd45-4b5c-a5d8-f248e2378b1b，轮次5bd8a9de-64fa-49a7-a43a-a25a1b374158，诊断a16cdd8a-3d90-43a1-a7ad-e84f668dc1c1：本地原生Codex CLI生成一张成功，08:42:02Z开始、08:44:12Z结束。21条持久化事件覆盖准备、启动、模型处理、图片发现、校验、存储、发布、完成，检测图片1/1。浏览器自动从模型处理中更新到已完成，展示当前v1结果。
- 此真实测试仅在独立单图模板与任务备注中采用用户已授权的尺寸豁免，保留原生输出，没有修改安装的Skill或系统验收逻辑；不代表整个Phase11A业务验收完成。
- 浏览器现有约967px视口及临时390×844窄屏：新增过程卡片、下拉选项、诊断长编号均正常换行，无横向溢出；测试后恢复原视口。实际页面确认默认“当前轮次”与成功态固定耗时。
- 收尾补查：创建attempt前的CLI版本探测失败也保留固定STARTUP_FAILED诊断，任意历史错误原文不进入接口；相关runner与观测回归14/14通过。
- 审查修复F-02：0张、仅历史图片、图片减少不记录“检测到生成图片”；仅新增数量上升时记录。四文件专项164/164通过；最终后端全量548 passed、39 skipped、无失败（19.51秒），新镜像构建成功。
- 最终补丁部署后API重读，成功任务21事件与历史失败逐图诊断均完整保留。结果文件dba38d53-a703-4214-a500-a82186f44ce3实际下载HTTP200、image/png，Pillow verify通过，原生1254×1254，未缩放。
- 独立最终复审Stage1/Stage2均PASS，F-01/F-02关闭。候选cf684d12aba467de7ab6d2569ecce26f53f48cc443ba2665e880fe5edbb6bb7c已登记review-approve；完整报告见EXECUTION-OBSERVABILITY-FINAL-REVIEW.md。本增量完成，不代替Phase11A其它业务验收。
