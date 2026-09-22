# API 换套图最终独立审查

最终 candidateId：`a7b1a5e4174605f26dede0c5ad804cc81d10eaa2f2584c3449dd2719ae93d577`。

**Stage 1：PASS。Stage 2：PASS。当前范围未遗留 HIGH / MEDIUM 问题。** 结论仅批准下述代码快照和范围，不代表上线、钉钉双端或真实 CLI/API 同时生成已验收。

## 范围与快照

依据：Product-Spec.md:3、Design-Brief.md:3、DEV-PLAN.md:718、docs/API-IMAGE-IMPLEMENTATION.md:1 全文、docs/API-IMAGE-RUNBOOK.md:1；保留 Demo 的交互要求另对照 docs/API-IMAGE-PREVIEW-PLAN.md:9。真实实施计划优先于历史“仅预览”边界。

范围：本轮全部未提交的 API 模块、迁移0015、注册/依赖、独立前端 client/types/views/tests、既有路由/登录白名单/WorkspaceStatus 的限定变化、infra 配置与验收脚本；亦重新阅读原预览组件与模拟状态机。下文 B=hengxin-smart-image/backend，F=hengxin-smart-image/frontend，I=hengxin-smart-image/infra；缩写后的路径均相对仓库根。未展开的后端模块文件名（如service.py、B/service.py）均在B/app/modules/api_image_edits/；未展开的前端页面文件名（如RealCreate.vue、F/real-draft.ts）均在F/src/views/hengxin/api-image-edits/；prototype.css在F/src/views/hengxin/，前端api文件在F/src/api/。

初始候选 `f002ad576aca9c81000e69ad3340d3f4f732a28f60c74660ce76b299ec72bda0` 审查中发生变化：主 Agent 修复 RealTaskDetail 单项计数提示、Celery 异常日志边界并新增日志测试，形成 `dcf19c000a8b4975558f1882dda1966697129fdcffb19514ce7efe4e796c7861`；随后修复 TLS 异常分类与增加适配器测试，形成最终候选。审查者逐项重读差异、重验相关用例，最终重新确认 Stage 1 后完成 Stage 2。只最终候选获得本报告 PASS，两个中间候选不获批准。

独立执行 `harness.py review-status` 得到 currentId 与上述最终候选一致；当时 approved=false（待主 Agent 登记）。审查者未改实现、未提交、未调用付费服务、未操作真实测试数据库、未写 clean。

## Stage 1：逐条合规

| 编号 | 需求及结论 | 代码与验证证据 |
|---|---|---|
| S01 | 完整：独立业务表/文件/配置/队列/闸门，不走 CLI | B/app/modules/api_image_edits/models.py:11、:28、:46、:65、:76、:84、:94 定义七表；files.py:28 独立对象前缀；celery_app.py:7 独立 app/队列；config.py:14 独立前缀。domain.py 测试:41 验证 FileRecord/Job 为0；真实 evidence.json:30 记录 CLI files/task_records 为0。 |
| S02 | 完整：默认关闭、独立启停、共享基础设施边界 | config.py:17 默认false；service.py:14、claims.py:26、outbox.py:13 均检查开关；I/compose.api-image.yaml:3、:35 只追加独立worker/outbox及API环境。Runbook:19 说明在途请求边界。 |
| S03 | 完整：1–20有序原图、1素材、名称1–60、提示词1–4000 | schemas.py:6 字段约束、去空白、禁止额外参数、原图去重；service.py:46 仅接受本模块有效文件。B/tests/test_api_image_domain.py:83、:99 验证跨域文件与输入拒绝。 |
| S04 | 完整：10MiB JPG/PNG/WebP 与真正解码 | router.py:35 使用受限multipart与validate_image；B/app/modules/files/multipart.py:19 实际流限长；validation.py:12、:36、:41 校验字节、MIME、格式、全部帧与像素上限；F/real-draft.ts:24 本地拦截。既有配置未改。 |
| S05 | 完整：顺序与角色不依赖上传返回顺序，冻结输入和参数 | F/real-draft.ts:29 先响应式占位，:47 显式 originalFileIds/materialFileId；B/service.py:48–54 冻结prompt/parameters/position；presentation.py:10 排序。F/tests/api-image-draft.test.ts:23 倒序完成用例通过。 |
| S06 | 完整：N原图+共享素材对应N次串行请求，固定协议参数 | config.py:8 固定model/size/resolution/quality/n；relay.py:96–105 每次两张Base64 data URL及固定endpoint；execution.py:19 取对应原图和共享素材。B/tests/test_api_image_relay.py:28 检查请求体和传输层无额外重试。 |
| S07 | 完整：全局并发1、先任务后原图、多worker原子认领 | state.py:16 独立行锁；claims.py:24、:47–61 按创建时间/任务/position取项；heartbeat.py:11 续租；claims.py:64 token fencing。B/tests/test_api_image_execution_pg.py:62、:83 用4线程验证提交/认领及晚到结果；PG执行结果属交接证据，本审查未重跑PG。 |
| S08 | 完整：同事务保存任务/outbox、幂等重放 | service.py:27 payload摘要/操作者/请求键，:40–57 同事务保存；models.py:86 唯一约束；outbox.py:12–27 预约后投递及重投。B/tests/test_api_image_execution.py:193 投递异常与重复消息用例独立通过。 |
| S09 | 完整：初次外最多3次、1/2/4退避、合理Retry-After持久化 | outcomes.py:29–34，Retry-After采用与指数延迟较大者并封顶300秒；relay.py:30 解析数字/日期；service.py:74 手动周期重置。execution测试:81 真实领域循环走4次失败再继续后项。 |
| S10 | 完整：连接失败/429/5xx可重试，参数失败，认证/额度/模型暂停 | relay.py:46、:53 限16KiB/3秒读取错误JSON，code/type受控白名单；:113 连接失败可重试；:125–137 HTTP分类；outcomes.py:35–39 暂停通道。relay测试:44、:56、:65 验证语义优先和限长。首审H1已修复。 |
| S11 | 完整：读超时、发出后断线、TLS读失败、进程丢失均不盲目重生 | relay.py:115–119 TLS保守uncertain及其他HTTP/OSError uncertain；claims.py:12–21、:33–38 租约失效uncertain并fence；outcomes.py:27 保留闸门。relay测试:83模拟200响应后read1抛SSLError；execution测试:37、:125 验证阻塞下一次调用。 |
| S12 | 完整：超管确认旧调用停止、明确失败后手动重试、记录操作者 | router.py:23、:103、:109 manage_system；control.py:21–42 要求确认且禁止释放活跃调用，attempt.resolved_by及事件留痕。execution测试:125、:145 验证普通角色403、false422、活跃409及确认审计。 |
| S13 | 完整：结果URL先持久化，收图失败只收图，落存才成功 | outcomes.py:44–53 保存私有回执；execution.py:31–72 解码/暂存/落存/成功；service.py:73 检测已有回执只collecting。execution测试:105、:162 覆盖下载失败、存储失败、耗尽后手动恢复且生成次数不变；真实证据requestCount仍2。 |
| S14 | 完整：HTTPS域名白名单、禁跳转、限大小/时间、不向CDN发key | downloads.py:16–29 精确host/端口/公网IP检查并绑定IP；:37–77 TLS证书/SNI、无Authorization、redirect=false、下载限长/期限。relay测试:117、:121 检查恶意域/私网/跳转/凭据头。 |
| S15 | 完整：全员授权共享查看/删除，独立上传/元数据/下载，软删除保护引用 | router.py:22 所有业务端点require shared_resources；files.py:17、:49 只ready且未删/拒任何任务引用；service.py:85 运行或uncertain拒删除，其他软删。domain测试:41、:64、:83 验证禁用403、独立文件和软删除。 |
| S16 | 完整：全部单项与任务状态、失败继续、成功保留、只重试失败项 | state.py:9、:33–48 聚合；outcomes.py:18 状态转换；service.py:68–80 仅failed项恢复。execution测试:81、:180 包含partial_failed/保留成功结果/后项继续。 |
| S17 | 完整：请求/生成重试/总耗时/排队/生成耗时真实口径，费用null | execution.py:95 preflight在start_attempt前；claims.py:80 生成后续尝试含手动；presentation.py:14–29 汇总；F/RealTaskDetail.vue:18–19 展示与说明；:45 保留1位小数。execution测试:69缺key实际网络尝试0。编号搜索presentation.py:39，domain测试:75–76。首审M1/M2/M4已修复。 |
| S18 | 完整：请求规格不冒充实际返回尺寸、不隐式缩放 | F/RealCreate.vue:18标请求规格；RealTaskDetail.vue:19说明实际尺寸；B/execution.py:39–41校验后原字节存储。真实证据两张1254×1254，未改为请求1024×1024。首审M3已修复。 |
| S19 | 完整：真实/demo独立，真实错误无示例fallback，无演示控制 | F/create.vue:5、records.vue:5按mode选择；api/api-image-edits.ts:4–32真实client；WorkspaceStatus.vue:3–4排除旧demo工具；RealCreate/RealRecords无场景暂停。client测试:20验证失败拒绝。 |
| S20 | 完整：上传状态、失败移除/重传、草稿保留、幂等提交/重试 | F/real-draft.ts:16–59、:75–88；RealImageSequence.vue:11–14；use-records.ts:5–15、:54–60 保留原重试键；draft测试覆盖乱序、解码失败、移除、断网/401原键、刷新恢复。浏览器脚本还实际执行跨路由草稿、角色排序和清理。 |
| S21 | 完整：分页查询/名称编号搜索/轮询、单图下载、删除确认、错误空态 | F/use-records.ts:25–43 防迟到覆盖、3秒轮询与卸载清理；RealRecords.vue:8、:15、:43–51 分页/确认；RealTaskDetail.vue:47下载；API路径/DTO见router.py:28–111、presentation.py:21–33，额外metadata端点符合文件元数据独立要求。 |
| S22 | 完整：保留明确模拟预览，不污染CLI Demo数据 | F/preview-state.ts:11独立内存、:30 mode保护、:49失败重试、:57单项串行timer；DemoCreate.vue:31场景、PreviewNotice.vue:2边界、TaskDetail.vue:4示例结果标注；ImageSequence.vue:28顺序占位。api-image-preview测试全部通过。 |
| S23 | 完整：无ZIP/成品库/CLI会话返工等范围漂移 | 全量新路由router.py:28–111和RealTaskDetail.vue:9–30只有规定动作；git diff核对共享变化仅main注册、migration模型注册、urllib3锁定、菜单、返回白名单与demo工具排除。 |
| S24 | 完整：迁移、配置、运行与隔离验证材料 | B/migrations/versions/0015_api_image_edits.py:33新增七表，:74降级拒活动项；I/compose.api-image-test.yaml:2专用内存资源/localhost端口；verify_api_image_live.py:58仅接受本地8009。迁移往返/compose config为交接验证记录，本审查只读审计。 |

部分实现：无。未实现：无（限本次实施计划）。范围外的线上发布、双通道同时生成、真实钉钉容器、容量/恢复演练不转称为本次已通过。

## 本轮发现及修复复核

- R1 MEDIUM（已关闭）：旧RealTaskDetail.vue:24拿累计含手动的item.retries展示“自动重试x/3”，手动周期可显示4/3。最终该行改为“等待下一次尝试”；汇总仍按真实生成重试展示。未改变重试业务计数。
- R2 HIGH / Stage 1（已关闭）：旧relay.py:115所有SSLError归channel，会把已发出请求的TLS读取异常当失败释放闸门。本机锁定urllib3的response.py:912–914证实响应读取会包装此异常。最终relay.py:115–117保守uncertain；新增tests/test_api_image_relay.py:83，独立Mock验证输出见下文。官方异常类型资料：[urllib3 exceptions](https://urllib3.readthedocs.io/en/stable/reference/urllib3.exceptions.html)。
- R3 HIGH / Stage 2（已关闭）：旧celery_app.execute直接放行异常，SQLAlchemy写私有URL/字节的异常可能含SQL参数并进入Celery错误日志。最终celery_app.py:17–27捕获入口异常，仅记录固定错误码，无异常文本/traceback，不在异常处理器重调生成，持久状态留待outbox/租约恢复。tests/test_api_image_worker_logging.py:6验证一次调用、私有token不入log、exc_info为空，独立通过。[SQLAlchemy参数日志说明](https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.create_engine.params.hide_parameters)、[Celery任务异常记录](https://docs.celeryq.dev/en/stable/userguide/tasks.html#task-throws)。

## Stage 2：质量、安全、测试真实性与视觉

| 编号 | 结论与证据 |
|---|---|
| Q01 | PASS：领域、认领、结果、上传、下载、展示、控制、outbox分文件；新API后端与前端模块逐文件计数均<300行，最大relay约171行。TS新模块无显式any；真实与Demo分离组件保持清楚职责。前端类型编译exit0。 |
| Q02 | PASS：源码扫描未发现eval/innerHTML/dangerouslySetInnerHTML/前端密钥变量/真实硬编码key；config.py:18 SecretStr且repr隐藏，relay.py:105只服务端Authorization，I/.env.api-image.example:3空值；测试固定凭据明确为临时本地资源，非生产秘密。 |
| Q03 | PASS：参数化ORM查询与搜索转义，presentation.py:39–42无SQL拼用户输入；文件名validation.py:28净化、router.py:63编码Content-Disposition且nosniff；download_result精确白名单、公网地址pinning、TLS证书与禁重定向覆盖SSRF边界。PG测试动态schema仅来自本地uuid4，非用户输入。 |
| Q04 | PASS：身份/角色逐请求检查；共享业务可访问全员资源是明文需求，不能误报为缺少owner过滤。router.py:22/23区分共享与超管；auth/permissions.py:5–18仅四授权角色且active。文件引用检查含已软删任务，保守保留数据；未调用CLI清理器。 |
| Q05 | PASS：异常数据最小化；relay.py:53错误体仅本地判定，outcomes.py:24保存受控code，presentation.py:21不返回result_url/result_bytes；Celery新边界避免异常SQL参数进入日志。TLS不确定分类与旧token拒绝保障故障恢复不盲目重生。 |
| Q06 | PASS：测试真实覆盖故障交互，不只有纯函数：SQLite通过HTTP建任务/上传/授权/软删，并执行领域worker；adapter Mock检查真实生产请求构造与错误响应；PG测试实际行锁并发，未用SQLite结果冒充PG锁行为；前端延迟Promise验证上传乱序、未知提交/401/刷新原键。浏览器脚本经阅读覆盖真实上传、错误图片、排序、草稿、下载及删除取消。 |
| Q07 | PASS（已捕获渲染对照）：实际打开output/api-preview-baseline.png（邻居替换壁纸）、api-preview-create.png、api-live/create-initial.png及real-results.png逐项对照：侧栏/页头/页签、蓝色按钮、标题层级、左表单右摘要、白卡与抽屉延续原框架。F/prototype.css:2–7标题28px、摘要300px/间距22px；RealImageSequence.vue:31–43为3列/12px间距、135px等比预览；RealTaskDetail.vue:58–71为3列结果/14px间距、180px图区。无独立设计稿数值要求。 |
| Q08 | 验证局限：本审查IAB访问3010返回ERR_CONNECTION_REFUSED，未重启Vite，未声称实时重新操作浏览器；视觉采用实际截图和已执行脚本证据。real-upload.png处于路由淡入中间态，不作为稳定视觉验收；create-initial.png保留旧“输出规格”文字，仅用于布局，最终文案以源码及新真实结果截图核对。1280无横溢出由browser-check.cjs:22断言和browser-evidence.json记录支持，未将淡截图当色彩验收。 |

LOW后续增强：F/api/api-image-edits-validate.ts:16–17只严格验证elapsedSeconds，queueSeconds/generationSeconds由展示函数安全降级为“未提供”（RealTaskDetail.vue:45），可以补齐DTO守卫和坏响应测试；当前生产后端明确返回有效数值，不阻断本次功能。轮询迟到与超级管理员确认UI主要依赖代码审计及已有浏览器/领域测试，尚无独立完整浏览器故障矩阵；不将其描述为全故障场景浏览器实测。

## 独立验证原始输出与交接证据

本审查执行SQLite/Mock测试；最终前一快照（含Worker日志修复、仅未加TLS用例）的原始结果：

```text
python -m pytest tests/test_api_image_domain.py tests/test_api_image_execution.py tests/test_api_image_relay.py tests/test_api_image_worker_logging.py -q
............................................                             [100%]
44 passed, 2 warnings in 3.24s
```

两条警告原文（既有依赖弃用，不是测试失败）：

```text
StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
```

最终TLS修改后独立重跑受影响的全部adapter与worker日志测试，以及单独Mock复现：

```text
python -m pytest tests/test_api_image_relay.py tests/test_api_image_worker_logging.py -q
..........................                                               [100%]
26 passed in 1.17s

200 response then SSLError => uncertain TLS_UNCERTAIN requests= 1
```

独立前端类型与全部Node测试原始结果：

```text
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit
[无标准输出，exit_code=0]

node node_modules/tsx/dist/cli.mjs --test --test-concurrency=1 tests/*.test.ts
ℹ tests 137
ℹ suites 0
ℹ pass 137
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 15212.0762
```

主Agent最终构建日志经本审查直接读取；未冒充本审查亲自构建，TLS后端修改不影响这些前端产物：

```text
output/api-live/final-build.log
dist/assets/index-Dz_8-1tN.js  1,619.13 kB │ gzip: 534.51 kB
✓ built in 36.66s

output/api-live/final-demo-build.log
dist-demo/assets/index-Bt6iCvud.js  1,631.23 kB │ gzip: 538.24 kB
✓ built in 33.88s
```

git diff --check exit0；components.d.ts无diff。后端851 passed /112 skipped及PG2项、迁移往返、Compose验证为主Agent交接记录（docs/API-IMAGE-IMPLEMENTATION-VALIDATION.md:5、:31），未由本审查重跑；最后新增日志/TLS测试另计，不篡改全量历史计数。主Agent报告最终API核心45 passed，与本审查44项基线及26项受影响复验相容。

已读output/api-live/evidence.json：2成功、2网络请求、0生成重试、费用null，两张1254×1254，CLI两表0、重复提交同任务、收图恢复无重生。已读browser-evidence.json：passed=true、errors=[]。测试worker临时公网DNS覆盖只用于绕过本机代理假IP解析，正式SSRF规则未放宽；真实中转与数据库证据由主Agent执行，本审查仅检查证据，不重复计费或声称重新运行。

由主Agent以本报告路径和最终candidateId调用review-approve登记两阶段PASS；之后若源码变化须重新固定快照并复核差异。
