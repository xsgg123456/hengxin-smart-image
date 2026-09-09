# 前后端接口契约

更新：2026-09-09。当前需求依据 Product-Spec v0.17；前端类型源为 `frontend/src/types/hengxin.ts`，管理类型另见 `frontend/src/types/management.ts`。本文汇总前端契约、目标 OpenAPI 及 Phase 6–8 真实接入；任务并发与受理已在 Phase 8 接入，CLI 和返工业务按 Phase 9–10 实现。

## Phase 5 后端基础补充

FastAPI 在 `/openapi.json` 发布业务的目标结构（28 个方法、20 条路径）；Phase 5 时业务方法均明确返回 501 `NOT_IMPLEMENTED`，正式实现按 Phase 6–13 接替。身份未接入前保留前端 mock 预览，HTTP 模式不回退。分页暂定默认 1/20，pageSize 上限 100，非法参数统一 422。可选传输字段在后续业务序列化中应省略未提供值；必要 nullable 字段必须保留 null。业务写入幂等键的前端传输在 Phase 8 接入；Phase 5 仅内部测试入口实施该机制。

已实现 `/api/v1/health/live` 与 `/api/v1/health/ready`（后者依赖 PG 迁移、Redis、MinIO 授权探针；失败 503）。测试模式显式开启 `ENABLE_TEST_JOBS` 后，`POST /api/v1/internal/test-jobs` 接受 `{value,delaySeconds?}` 与必填 `Idempotency-Key`，同事务持久写入测试作业/outbox 后返回 202 `{jobId,status,result,executionCount}`；同键同内容返回同一作业，同键不同内容返回 409。`GET /api/v1/internal/test-jobs/{id}` 查询 PG 状态。该入口默认关闭且生产禁止开启，不是图片生成 API。独立 outbox 派发进程持续重派未完成作业；纯计算 Worker 通过 PG 行锁与原子提交防止重复完成，不能据此宣称外部 AI 调用恰好一次。

Phase 4 管理、身份及配置补充见 [PHASE4-CONTRACT.md](PHASE4-CONTRACT.md)，与本文后续补充共同组成当前前端契约。产品权限与会话并发规则以 Product-Spec v0.17 为准；各阶段真实实现的边界见文末 Phase 7/8 补充。

本文最初由 Phase 1 建立，已合并 Phase 2–4 的分页、文件引用、结果版本及管理查询。早期契约不覆盖后续字段；真实业务行为仍按 DEV-PLAN 分阶段接入。

## 模式与边界

- `pnpm dev` / `pnpm build:preview` 显式使用 mock 模式。模拟服务采用独立内存，刷新重置，不读写原型 localStorage；不执行真实 Skill、不上传到 MinIO、不建立真实 CLI 会话。
- `pnpm dev:api` / `pnpm build` 使用 `/api/v1` HTTP 服务。模拟模块仅动态加载于 mock 模式；请求失败不回退模拟服务。HTTP 默认超时 10 秒，图片上传 60 秒，无自动重试写操作。
- Art 用户展示使用业务用户 ID；仅模拟服务提供四角色身份预览。真实模式必须先从 `/auth/me` 获取启用且已授权的身份，身份无效时阻断入口；Phase 6 起 HTTP 启动不读取聚合快照，各业务页面独立显示加载失败，显示错误与重试。真实钉钉登录仍为 Phase 12。
- 页面禁止直接写业务集合，调用 model 门面再由 HengxinService 选择适配器。示例文件只在 mock 模式使用。当前保留原型布局和浏览器内示例下载；正式文件上传、鉴权下载与服务端 ZIP 分别在后续阶段接入。

## 基础约定

JSON 字段 camelCase；ID 为不可解释的字符串；时间为带时区 ISO 8601，展示可按 Asia/Shanghai 格式化。文件使用稳定 fileId，对象存储路径不作为公开链接；url 是受控预览地址（Phase 6 为逐次鉴权的稳定 API 路径），urlExpiresAt 为空仅限本地示例或明确不适用。服务端负责生成业务 ID、归属与审计，不能信任客户端提供的 ownerId。

错误响应为 `{ "code": "CONFLICT", "message": "任务正在处理中", "requestId": "..." }`。401 未认证、403 无权限、404 不存在、409 冲突、422 输入无效、5xx 服务异常；前端额外使用 UNAVAILABLE（网络/超时）、INVALID_RESPONSE（无法解析或非 JSON）。用户界面展示 message，不展示凭据与服务器路径。

分页使用 PageQuery `{page, pageSize, search?, mode?}`，page 从 1 开始；PageResult 为 `{items, page, pageSize, total}`。列表空结果返回 items=[]、total=0，不返回 404。分页端点已在前端 Phase 2–4 细化；工作区快照仅保留启动兼容，不驱动模板、任务或成品列表。

## 当前业务接口契约

下表路径均以 `/api/v1` 为前缀；管理部分见 PHASE4-CONTRACT 及本文 Phase 7 补充。身份、文件、模板和 Skill 已接真实服务；Phase 8 接入任务创建、分页、详情和删除，执行来源及能力见文末补充。成品归档、返工和其他尚未实施的管理接口仍返回 501。

| 方法与路径 | 请求 | 目标成功响应 |
|---|---|---|
| GET /auth/me | Cookie 会话 | 200 User |
| GET /workspace | 无 | 200 Workspace，启动兼容快照 |
| GET /templates | TemplateQuery | 200 PageResult&lt;Template&gt; |
| GET /templates/:id | 无 | 200 Template |
| GET /templates/:id/versions | 无 | 200 Template[]，按版本倒序 |
| POST /templates | TemplateInput | 200 Template |
| PUT /templates/:id | TemplateInput | 200 Template；expectedVersion 冲突返回 409 |
| DELETE /templates/:id | 无 | 204；历史任务快照不变 |
| GET /skills | mode? | 200 SkillVersion[] |
| POST /files | multipart/form-data 的 file | 200 Picture，含 fileId |
| GET /tasks | TaskQuery | 200 TaskPage |
| GET /tasks/:id | 无 | 200 TaskDetailData |
| POST /tasks | CreateTaskInput | 202 Accepted，taskId/roundId/state=排队中 |
| POST /tasks/:id/rounds | RevisionInput | 202 Accepted；target=null 为整套，否则为从 0 开始的固定图片位置 |
| DELETE /tasks/:id | 无 | 200 DeletionReceipt |
| GET /archives | PageQuery | 200 PageResult&lt;Archive&gt; |
| GET /archives/:id | 无 | 200 Archive |
| POST /tasks/:id/archives | 无 | 200 Archive；同一结果重复操作返回同条记录 |
| DELETE /archives/:id | 无 | 204；对应任务图片保留 |

GET /workspace 是过渡性聚合读取，不能用于生产无限量加载。前端列表已使用分页与任务详情查询。Phase 2 起，CreateTaskInput.sources 提交已受理的 fileId；Picture.url 只供预览，不能作为服务端任意远程 URL 下载入口。Phase 6 接真实上传后校验文件权限及有效性；Picture.fileId 的可选类型仅兼容历史/展示数据，不免除新提交的文件校验。首次生成/返工的 202 仅代表受理，不代表执行完成。

## 数据与状态

- User：id/name/role/status；role 为 super_admin、design_manager、designer、operator 或 null；status 为 pending、active、disabled。
- FileRecord：id/name/mimeType/size/width/height/ownerId/url/urlExpiresAt。size 单位字节，宽高为像素。
- SkillVersion：id/name/mode/version/checksum/status，状态 uploaded/installing/available/disabled/failed。
- Template：id/name/mode/images/skill/skillVersionId/notes/updatedAt/active/version/ownerId。skill 保留展示名，skillVersionId 引用具体版本；未绑定时可为空，可生成任务必须冻结有效版本。
- Task：id/name/mode、模板引用及版本、skillVersionId、ownerId、sessionId、state、progress、sources、images、feedback、time、archived、currentRoundId。
- Round：id/taskId/operatorId/target/note/state/createdAt/startedAt/finishedAt/error。
- ImageVersion：id/taskId/roundId/slot/version/fileId/current。Picture 是图片展示结构；前端 Phase 3 已通过 ResultSlot/ResultVersion 展示固定图片位置及历史版本，真实模型在 Phase 8、返工持久化在 Phase 10 接入。
- Archive：id/taskId/name/mode/images/time/ownerId/imageVersionIds，冻结结果，不随返工覆盖。
- 管理：ExecutionAttempt 按真实启动去重，usage 可为 null（未提供，不能显示 0）；WorkerStatus 区分 idle/running/unavailable/unknown；SystemConfig 包含版本、并发、超时秒数、上传字节限制和默认 Skill 引用。查询、保存与审计接口已由 Phase 4 定义并实现模拟交互，真实采集/管理在 Phase 9/13 接入。

TaskState 使用排队中、执行中、待查看、部分失败、失败，保持现有视图兼容；Phase 5 后端序列化须遵守同枚举或显式映射。归档是结果快照，不替代执行状态。progress 为 0–100 或 null，null 表示无可靠比例；模拟进度仅演示状态变化。真实阶段需在 UI 以阶段文字展示 null，不能假设其为 0%。

当前模拟服务保证类型匹配、异步受理返回标识、串行返工、目标图片独立版本更新、归档快照与读写拷贝隔离；已完成 Phase 1–4 范围内的前端验证，证据见对应 PHASE*-VALIDATION.md；不据此宣称真实业务、跨 Worker 互斥或容量验收完成。

上传 JPG/PNG/WebP、单文件 10 MiB、每组 20 张及图片加自然语言文字表单已确认；任务名必填、SKU 可选。删除保留期限、历史与归档细则及运行参数中仍属建议的部分按 PRD 第 11 节管理，不因模拟实现而变成已批准规则。HTTP 写操作幂等键与持久化 outbox 在后端阶段实现；当前 UI 防止重复点击，不宣称跨网络重放幂等。


## Phase 2 契约扩展（2026-09-09）

依据 PRD v0.13：上传 JPG/PNG/WebP，每文件最大10 MiB，每组最多20张；名称必填、SKU可选、文字要求必填、输出数按模板/输入图。以下扩展先用于前端适配，后端实现仍在Phase5之后。

- Template 增加 skillVersionId（可空）、notes、updatedAt；skill 保留展示名，active 表示可用。TemplateInput 为 id?、name、mode、images、skillVersionId、active、notes、expectedVersion?，归属由服务填写，不采信客户端角色/ownerId。
- TemplateQuery 继承 PageQuery，增加 sort=updated/name/images、activeOnly?；GET /templates 返回 PageResult<Template>，GET /templates/:id 用于跨页模板跳转。POST /templates 新建，PUT /templates/:id 更新，expectedVersion 不匹配返回409并保留编辑输入。
- GET /skills?mode=... 返回 SkillVersion[]，新增 isDefault 布尔标记；仅状态available且类型匹配的版本能绑定。每个模拟模块预置一个默认可用版本，真实默认/专用Skill配置的管理规则仍待Q-002确定，Phase2不实现Skill安装/发布。
- POST /files 接收 multipart/form-data 的 file，返回 Picture（name/url/fileId）。模拟上传创建内存文件引用；本地图片解码通过后才提交；真实上传落地在Phase6。本地预览与模拟接收不声称已写入MinIO。
- CreateTaskInput 增加 sku?、templateVersion?、skillVersionId?；sources 必须包含已受理的fileId。模拟服务检查输入文件与版本，冻结素材顺序、模板版本、Skill版本、SKU与要求，任务输出仍为示例。
- 故障场景由仅mock模式的 URL search 参数 scenario 选择：default、empty、no-skills、upload-error、save-error、submit-error、list-error。error场景只让相应首次操作失败，重试恢复；切换场景刷新整个页面并清空模拟工作区。测试实例隔离，不污染真实模式。
- 页面取消/关闭编辑不会提交；请求进行中按钮锁定，重复响应与过期列表响应不会覆盖最新选择。上传队列按选择顺序展示，失败项保留、单项可重试或移除，存在失败/进行中项时禁止保存/提交。

Phase 2 历史引用：Task 可携带 templateSnapshot（完整 Template，含有序图片与 Skill 版本），创建时由服务端取当前版本生成，客户端不能自填；旧 Phase 1/历史响应可无此字段。编辑和删除模板不改变已受理任务的快照。

## Phase 3：任务、返工和成品接口

沿用 Spec REQ-004/005/006 建议默认方案，仍仅前端模拟与真实 HTTP 适配，不代表后端落地。

- `GET /tasks` 接收 TaskQuery（PageQuery + state?: TaskState|'processing'|'error'），按时间倒序及 ID 稳定排序；返回 TaskPage（PageResult<Task> + stats: {total,processing,ready,archived}，统计为全工作区）。支持名称、编号、SKU 搜索及类型筛选。
- `GET /tasks/:id` 返回 TaskDetailData：{task,slots:ResultSlot[],rounds:Round[]}。ResultSlot={slot:number,versions:ResultVersion[],currentVersionId:string|null,error:string|null}；ResultVersion=Picture + {id,version:number,roundId,createdAt}。只有成功结果进入版本列表，槽位顺序固定。Task 增加可选 outputCount/error，images 只含当前已成功的图，不能用该数组下标作为返工目标，返工必须用 slot。
- `POST /tasks/:id/rounds` 使用 RevisionInput，新增 retry?:boolean；正常修改要求非空意见、同一任务串行。重试只允许失败/部分失败任务；重试上一失败范围，保留原轮次意见。服务从任务冻结 Skill、模板和素材取得执行上下文，不接受前端自行切换。成功后目标槽新增版本，失败不更改旧 currentVersionId。首次生成在完成前不预填输出图片。
- `DELETE /tasks/:id` 返回 DeletionReceipt={id,operatorId,deletedAt}，模拟服务记入 Workspace 可选 deletions。删除运行任务在本阶段取消模拟计时，任务详情返回404，已归档图片与版本引用保留。后端阶段实现真实执行取消/引用计数。
- `GET /archives` 接收 PageQuery，返回 PageResult<Archive>；`GET /archives/:id` 详情；`POST /tasks/:id/archives` 只允许完整当前结果（待查看且所有槽可用），按当前 imageVersionIds 幂等创建不可变归档。历史查看不改变归档选择，归档按钮只保存当前整套版本。
- `DELETE /archives/:id` 沿用204，删除不删除任务当前图。读写失败保留界面上下文；受理后的读取故障不重复返工/归档写入。
- 页面使用独立列表/详情查询与离页停止的轮询，工作区快照仅用于启动兼容，不再驱动任务/成品列表。深链接可直接查询列表当前页以外的任务。
- 新 mock 场景：execution-error（首次生成失败）、partial-result（首次执行部分失败）、revision-error（首次返工执行失败）、archive-error（首次归档写失败）；默认场景不触发。模拟明确标识，重试恢复。下载保持实际图片 MIME/字节，不把 HTML/JSON 网关错误保存为图片；整套完整读取后一次保存 ZIP，任一文件失败可重试、不输出残缺包。

删除审计补充：模拟 Workspace.deletions 统一记录模板、任务、成品删除，DeletionReceipt 可带 resourceType（template/task/archive），由服务填充实际 operatorId 与删除时间。不存在的记录不重复记审计；真实 DELETE 成品/模板仍返回204，审计由后端持久化。

## 会话与并发安全补充（2026-09-09，Phase 8–10 待实现）

业务规则以 Product-Spec 第 9.1–9.2 节及 AC-004、010、015、021–025 为准；本文规定对应传输行为。当前 Phase 5 业务路由仍返回 501，以下字段与约束由后续阶段同步更新前端类型、响应校验和 OpenAPI。

- `POST /tasks` 和 `POST /tasks/:id/rounds` 必须携带非空 `Idempotency-Key`，缺失/非法返回 422。范围由可信操作者、操作类型和目标任务（创建时无目标）共同限定，服务端保存载荷指纹与原受理回执；不能相信前端传入的身份建立范围。
- 同范围、同键、同内容的重放返回原 202 受理回执和同一 taskId/roundId，不新建轮次/outbox，不重新启动 CLI；回执中的受理状态不替代 GET 查询的当前状态。同键异内容返回 409 `CONFLICT`；幂等读取仍须经过当前身份/授权校验。
- 同一任务已有未结束轮次时，不同新请求返回 409 `TASK_BUSY`，不追加隐藏的返工队列；同一已受理请求的重放优先按幂等规则返回。互斥覆盖排队、执行、收集结果、取消处理和状态核实期间，按 taskId 对所有用户/Worker 生效；其中状态待核实优先返回下文的 `EXECUTION_UNCERTAIN`。
- 前端重复发送同一次操作时复用原键；用户发起新的业务操作或安全获准后的明确重试使用新键。409 或无法确认是否受理时保留表单与意见，不能自动换键再次提交。
- `GET /tasks/:id` 的 `TaskDetailData` 增加 `executionControl: {canRevise: boolean, canRetry: boolean, blockedReason: string | null}`，由服务端依据当前身份、任务/轮次状态及会话可用性计算。忙碌或执行状态待核实时两项均为 false，并给出可展示原因；前端禁用相应按钮，提交接口仍独立复核。保留现有 TaskState 枚举，内部状态通过状态映射与 blockedReason 说明，不把进程/数据库内部细节直接暴露给用户。
- 旧执行尚未核实停止或结果不确定时，新的返工/重试返回 409 `EXECUTION_UNCERTAIN`；原会话材料确认不可恢复时返回 409 `SESSION_UNAVAILABLE`，保留旧结果且不能自动切换会话。不能仅凭前端“失败”状态、租约过期或进程心跳缺失允许重新执行。
- `DELETE /tasks/:id` 的回执表示逻辑删除及取消意图已持久化，不承诺上游调用或费用已撤销。排队任务不得再启动，运行任务由执行管理停止并核实；图片版本最终提交再次校验任务未删除、轮次有效及认领凭证。成功、已确认失败、已完成取消的轮次停止重派，待核实轮次不因消息补发再次启动。
- sessionId 只由服务端根据实际 CLI 事件绑定。新任务受理时可以尚未取得 sessionId；每轮进程结束后保留同任务会话记录，返工按精确 ID 续接，禁止按用户或共享“最近会话”选择。执行环境不能跨任务读取或修改输入、输出、临时文件与会话材料；这不改变员工对共享业务资源的查看权限。前端不能指定任意会话 ID。

实现验收按 DEV-PLAN Phase 8 的多进程竞争、Phase 9 的实际 CLI 中断/续接与容器重建、Phase 10 的双用户返工分别取证；本补充不将现有 mock 串行行为计为后端并发安全已通过。

## Phase 6 身份与文件接入

- GET /auth/me：服务端显式 ENABLE_DEV_IDENTITY 后读取固定开发用户，默认关闭、生产拒绝启用。请求中的角色、用户 ID、模拟角色参数均不能指定可信身份。开发数据不自动关联钉钉成员；Phase 12 接真实会话。

- POST /files：multipart 单文件，200 Picture{name,url,fileId}；JPG/PNG/WebP 实际解码通过且最多 10 MiB 后保存原字节到私有 MinIO，PG 保存大小、尺寸、类型、校验和、owner_id。浏览器负责每组20张上限，Phase 7/8 在业务组提交时追加服务端数量校验。
- GET /files/{id}：200 Picture，稳定引用可在刷新后重新获取；不是素材库或草稿列表。
- GET /files/{id}/content：每次鉴权后流式预览原图，download=true 设置附件下载。有效四角色可跨创建人访问；匿名/停用/待授权拒绝，未知/未完成文件不可读取。url 使用同源 /api/v1/files/{id}/content，浏览器不访问 MinIO 内网地址、不持久化签名链接。
- 真实前端只以 /auth/me 作为身份入口，各页独立请求模板/Skill等；后续业务仍501并保留错误和重试，不把未实现解释为空数据。素材组件在这些接口失败时仍可上传/预览/下载，生成保持禁用。移除图片仅取消当前表单选择，不删除服务器对象；草稿恢复/生命周期仍属后续范围。

## Phase 7 模板与 Skill 接入

- 模板 CRUD、分页搜索排序及 GET /templates/:id/versions 接真实 PostgreSQL。编辑要求 expectedVersion，竞争返回409。图片必须是1–20个ready文件引用，名称/url从服务端取得；逻辑删除保留快照、原始对象和实际操作者审计。四角色共享操作。
- Template.skillBinding 为 specific 或 module_default；skillVersionId 是保存时冻结的实际版本。TemplateInput.skillVersionId=null 使用该模块当时可用默认；无默认保存草稿，显式不可用版本可保留为草稿，类型错配或不存在422。切换默认不改旧模板，重新保存才解析新默认。
- GET /skills 仅返回可用版本；GET /management/skills、POST /management/skills（multipart file/mode/version，201）、POST /management/skills/:id/install、PUT /management/skills/:id/status 仅超级管理员可用。安装受理返回200 installing，需继续查询安装结果。上传失败可重传内容相同的原版本包；成功版本不可覆盖。
- GET/PUT /management/skills/defaults 仅超管，返回/提交 `{wallpaper: string|null, product: string|null, text: string|null}`，三个键必需；必须是对应模块可用版本。绑定和启停保存审计记录。
- ZIP最大20MiB，解压100MiB、单文件20MiB、1000条目、压缩比100；验证CRC、拒绝路径穿越/符号链接/特殊文件。根或唯一顶层目录内SKILL.md须UTF8 YAML name/description；可选hengxin-skill.json声明mode/version及requires.executables/pythonModules，依赖须预装，不执行安装脚本或联网装依赖。
- Worker使用持久化skill_data卷，按作业租约、心跳和独立尝试目录安装，成功原子发布不可变目录，失败不影响旧版。失败/成功/取消为终态，活跃租约不重复派发；测试包验证安装流程，不代表实际图像生成Skill已交付。

## Phase 8 任务接入契约

- POST /tasks 必须携带 Idempotency-Key，成功202 Accepted。同操作者、操作、目标及键相同且内容一致重放原回执；同键不同内容409。新请求冻结服务器模板快照、可用Skill版本、ready素材和要求，文字不需模板。缺少执行器时新请求503且不入库，不影响原已受理请求重放。
- GET /tasks、GET /tasks/:id、DELETE /tasks/:id接真实数据库，四角色共享。删除回执表示逻辑删除和取消意图已保存，原文件及历史不回收。迟到/过期/已取消执行不能发布结果；执行待核实时不重新启动或允许新轮次。
- Task新增可选executionSource（fixture/unavailable/cli），真实接口明确来源；fixture结果必须显示测试标记。TaskDetailData新增必需executionControl（canRevise/canRetry/blockedReason），前端按服务端能力控制按钮。Phase8返工HTTP尚未接入，两能力返回false并说明原因；模拟预览仍保留既有返工演示。
- 默认不启用测试执行器，仅APP_ENV=test与ENABLE_FIXTURE_EXECUTOR=true同时满足才可生成fixture；fixture复制冻结图片为独立可读结果，不生成CLI会话或虚构usage。GENERATION_CONCURRENCY默认1，范围1–10；过期未知执行保持占用，不能自动接管再次运行。
- HTTP前端同一次不确定提交保留请求键和输入快照；受理后的详情读取失败保留taskId并引导查询，不重新创建。轮询按运行/空闲状态3/10秒，离页停止。真实CLI和用户返工分别Phase9/10接入。
