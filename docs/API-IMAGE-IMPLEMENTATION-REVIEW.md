# API 换套图实施审查

审查快照：`db81f719309cfbf2fc6b23313d26e6d74ff50143c9d07d4b72693f36ff251763`。结论：**Stage 1 FAIL；Stage 2 未执行**。存在 HIGH，不得登记两阶段 PASS。

## 范围和依据

依据 Product-Spec.md:3、DEV-PLAN.md:718、Design-Brief.md:3、docs/API-IMAGE-IMPLEMENTATION.md 全文及 docs/API-IMAGE-RUNBOOK.md。旧预览计划仅用于未被正式实施计划替代的演示交互。范围为本轮 git diff、新 backend/app/modules/api_image_edits 全模块、0015 迁移、注册和依赖、四组新后端测试、独立前端 client/types/views/tests、路由和登录返回白名单、WorkspaceStatus、infra 配置和验证脚本。下文 backend/frontend/infra 均相对 hengxin-smart-image/。

主 Agent 在审查期间报告 Vite 自动重写 frontend/src/types/import/components.d.ts（删除19个旧声明），并计划恢复及清理两个文件末尾空行。该变化不能由本报告批准；修复后必须重新 prepare。审查者未修改实现、未访问真实数据库、未调用付费接口。

## Stage 1 阻断及不匹配

### HIGH H1：明确额度／模型配置错误未暂停通道

契约要求“401/403、明确额度/模型配置错误暂停通道”。backend/app/modules/api_image_edits/relay.py:87–97 在读取错误 JSON 前返回：所有429均 retryable，400均 permanent；错误体实际完全不读取。于是明确 insufficient_quota 连续重试后仍不暂停，后续图片继续请求；400 model_not_found 直接继续下一项。outcomes.py:29–39 只有 kind=channel 才暂停。

独立无网络 Mock 实测原始输出：

```text
429 insufficient_quota => retryable HTTP_429 body_reads= 0
400 model_not_found => permanent HTTP_400 body_reads= 0
```

应限长、限时读取错误体，使用受控 code/type 白名单识别额度及模型配置错误；普通参数400保持单项失败、普通限流429仍可退避；不向日志/UI透传原始错误体。429 可同时表示额度与限流，官方说明支持此区分：[Error codes](https://developers.openai.com/api/docs/guides/error-codes)。这里以本项目明确契约和上述可执行复现为判据，不推断中转站实际每种错误一定采用哪个HTTP状态。

### MEDIUM M1：未发生网络请求也计为“实际请求”

backend/app/modules/api_image_edits/execution.py:92 先 start_attempt；claims.py:82 插入 ApiAttempt；relay.py:53 才检查空密钥并本地拒绝。presentation.py:24 用记录数作为 requestCount。因此模块启用但密钥缺失时，真实网络调用0次，指标却为1。违背“读数不伪造／实际请求次数”。应在登记网络尝试前完成本地配置/参数预检，并明确连接尝试与实际发送的统计口径。

### MEDIUM M2：编号搜索属于死引导

frontend/src/views/hengxin/api-image-edits/RealRecords.vue:8 提示“搜索任务名称或编号”，但 backend/app/modules/api_image_edits/presentation.py:39 仅对 name 过滤。复制当前任务UUID搜索将无结果（除非名称恰好包含UUID）。实现编号匹配或将提示收窄为名称；需回归有记录时按UUID搜索。

### MEDIUM M3：固定请求参数被表述为实际输出规格

frontend/src/views/hengxin/api-image-edits/RealCreate.vue:18 写“输出规格 1024 × 1024”；真实证据 output/api-live/evidence.json:19、:26 为两张1254×1254。backend/app/modules/api_image_edits/config.py:9 的1024×1024是请求参数，execution.py:39–41只校验合法图片，不强制该尺寸。改为“请求规格”，必要时展示实际尺寸；不应为了标签去缩放原始返回结果。已实际查看 create-initial.png 和 real-results.png。

### MEDIUM M4：比较指标未完整展示且重试名称不准确

backend/app/modules/api_image_edits/presentation.py:25–26 已提供 queueSeconds/generationSeconds，但 frontend/src/types/api-image-edits.ts:8 未声明，RealTaskDetail.vue:18 只展示总耗时。正式需求列明排队／生成耗时，应在详情接入。该行“自动重试”对应 claims.py:80–81 累计所有非首次生成尝试，手动重试也增加，标签应改为生成重试或拆分准确计数；收图重试未计入该值，需明确口径。原始浮点秒数397.279851可格式化为1位小数（LOW显示建议）。

## Stage 1 逐项检查

| 契约条目 | 结论与证据 |
|---|---|
| 共享认证/基础设施，独立业务、文件、配置、队列，不走CLI | 实现：models.py:11/28/46/65/76/84/94 七个独立表；files.py:28独立前缀；config.py:14独立环境；celery_app.py:5–10独立app/队列/Redis DB1；main.py:53独立路由。domain测试验证CLI FileRecord/Job不变；真实证据CLI两表计数0。未见CLI业务变更。 |
| 默认关闭、独立启停 | 实现：config.py:17、service.py:14、claims.py:26、outbox.py:13；compose.api-image.yaml:5及独立两个服务。现有运行请求停止边界在Runbook说明。 |
| 1–20原图、1素材、10MiB JPG/PNG/WebP、名称提示范围 | 实现：schemas.py:6–18；router.py:35–44调用既有validation.py:12–14、:36–67；service.py:46引用本模块ready文件。domain测试覆盖空/超限/额外字段和CLI文件拒绝。 |
| 上传异步不乱序、明确角色、冻结输入和参数 | 实现：real-draft.ts:29–31占位、:47显式原图数组/最后素材；service.py:48–54按position冻结；presentation.py:10排序；relay.py:58每次原图+素材。 |
| 固定endpoint/model/size/resolution/quality/n及Base64 | 实现：config.py:8–11、relay.py:55–72；adapter单测实际检查JSON与单次调用。规格展示有M3。 |
| 密钥仅服务端、SecretStr、不向CDN发密钥 | 实现：config.py:18、relay.py:68、downloads.py:44仅Host/Accept；adapter测试检查下载头。完整安全扫描属于未执行Stage2。 |
| 全局1、先任务后原图、原子认领、幂等和outbox | 实现：state.py:16行锁、claims.py:24–61排序/闸门、service.py:40–57同事务、service.py:27–35幂等校验、outbox.py:12–27可靠重投。PG并发测试源码覆盖4线程相同提交和认领，本审查未重跑PG。 |
| 三次1/2/4退避、Retry-After、持久化 | 实现：outcomes.py:29–34、relay.py:30–38，最多3次，合理Retry-After封顶300秒；execution单测走四次失败并继续后项。明确额度分类有H1。 |
| 连接可重试、参数失败、配置暂停 | 部分：relay.py:76–81区分连接与发出后不确定，:89认证状态暂停；错误体分类缺失H1。 |
| 超时/失联uncertain，阻断重生，超管确认审计，fencing | 实现：claims.py:12–21、:33–38，outcomes.py:27–28，control.py:21–42记录resolved_by；router.py:23/:103仅manage_system；heartbeat.py:11–19续租。测试覆盖uncertain不再调用、权限、活跃调用禁止释放；PG测试覆盖过期旧token拒结果。 |
| URL持久收图、安全下载、落存才成功、收图不再生成 | 实现：outcomes.py:44–70、execution.py:31–72、service.py:73；downloads.py:16–29域名/公网IP绑定，:37–77 TLS/禁重定向/限大小时间/无key。单测与真实证据确认收图恢复requestCount保持2。 |
| 授权用户共享查看/删除，独立文件、软删除/引用保护 | 实现：router.py:22/35–111共用权限，files.py:49–57保护所有引用，service.py:85–92软删除与运行/uncertain阻止；domain测试覆盖禁用用户、文件关联、软删除。 |
| 单项/任务状态，部分失败保成功、失败项重试 | 实现：state.py:33–48聚合，service.py:68–80仅failed项，成功result不变；execution单测覆盖失败继续/仅失败重试。 |
| 总耗时、排队/生成耗时、请求/重试次数、未知费用null | 部分：presentation.py:14–29已有字段，M1计数不实，M4展示/命名不全。 |
| demo真实隔离、禁止fallback、正式页无演示控制 | 实现：create.vue:5、records.vue:5按mode选择独立组件；api/api-image-edits.ts:4、:5–32独立真实client无示例fallback；WorkspaceStatus.vue:3–4排除模块；RealCreate/RealRecords无场景选择。 |
| 上传状态、清理、幂等提交重试、分页轮询、下载和删除确认 | 实现：real-draft.ts:16–59与:75–88保留pending；use-records.ts:5–15保留重试key、:25–63分页/防旧响应覆盖/3秒轮询及卸载清理；RealTaskDetail.vue:46下载；RealRecords.vue:44二次确认。浏览器证据有真实上传/下载/失败收图重试/无结果搜索/取消删除。编号搜索M2。 |
| 不做ZIP/成品库/CLI返工 | 实现边界匹配：router.py:28–111、RealTaskDetail.vue:9–30仅本模块动作。未见此类扩展。 |
| HTTP路径及返回契约 | router.py:28–111逐项提供status/files/content/delete/create/list/detail/retry/delete/resolve/resume；presentation.py:21–33、files.py:12–14匹配Task/Picture/Item。额外metadata端点符合“元数据单独端点”。 |
| 迁移、运行配置、隔离验收 | migrations/versions/0015_api_image_edits.py:33–84新增表与防活跃降级；migrations/env.py:14注册；infra/verify_api_image_live.py:58固定localhost:8009。主Agent声明迁移往返和全量构建通过，本审查不冒充复跑。 |
| 保留既有视觉 | Stage1截图观察：共享侧栏/页头/蓝色主题/art-card/双栏和抽屉匹配Design-Brief.md:5；RealCreate.vue:2–24、RealTaskDetail.vue:58–71有对应组件与样式。Stage2邻居实机对比尚未执行。 |

## 验证与限制

独立执行（无付费、SQLite测试资源）：

```text
python -m pytest tests/test_api_image_domain.py tests/test_api_image_execution.py tests/test_api_image_relay.py -q
.....................................                                    [100%]
37 passed, 2 warnings in 3.74s
```

两条warning原文：

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
```

37项通过并不能覆盖H1：tests/test_api_image_relay.py:44的参数化仅按HTTP状态构造错误，没有语义错误体断言。读取的 output/api-live/browser-evidence.json 标记passed=true、errors=[]；evidence.json记录2成功/2请求/0生成重试、已持久结果收图恢复。截图经本审查实际查看，未重新提交生成。完整后端840/112、前端137、tsc、两种build和迁移往返为主Agent交接声明；未提供本审查独立编译原始输出，因此不作为本审查编译PASS。

## Stage 2

**未执行。** H1 为 Stage1 HIGH，按 code-review skill 停止。代码质量、完整安全扫描、邻居页面实际渲染对比、编译验收不得标PASS。先修复上述差异，重新固定candidate，再从Stage1复核进入Stage2。

