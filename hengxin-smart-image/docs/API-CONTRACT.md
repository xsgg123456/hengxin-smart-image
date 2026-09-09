# 前端接口契约 — Phase 1

版本 0.1 · 2026-09-09。对应 DEV-PLAN Phase 1、Product-Spec v0.12。类型源：`frontend/src/types/hengxin.ts`。这是前端承接契约，不代表后端接口已实现；Phase 2–4 逐页细化分页、文件引用与管理查询，Phase 5 对齐 OpenAPI。

## 模式与边界

- `pnpm dev` / `pnpm build:preview` 显式使用 mock 模式。模拟服务采用独立内存，刷新重置，不读写原型 localStorage；不执行真实 Skill、不上传到 MinIO、不建立真实 CLI 会话。
- `pnpm dev:api` / `pnpm build` 使用 `/api/v1` HTTP 服务。模拟模块仅动态加载于 mock 模式；请求失败不回退模拟服务。HTTP 超时 10 秒，无自动重试写操作。
- Art 用户展示使用业务用户 ID；仅模拟服务提供模拟运营。真实模式必须先从 `/auth/me` 获取启用且已授权的身份，身份无效或工作区加载失败时阻断入口，显示错误与重试。真实钉钉登录仍为 Phase 12。
- 页面禁止直接写业务集合，调用 model 门面再由 HengxinService 选择适配器。示例文件只在 mock 模式使用。当前保留原型布局和浏览器内示例下载；正式文件上传、鉴权下载与服务端 ZIP 分别在后续阶段接入。

## 基础约定

JSON 字段 camelCase；ID 为不可解释的字符串；时间为带时区 ISO 8601，展示可按 Asia/Shanghai 格式化。文件使用稳定 fileId，对象存储路径不作为公开链接；url 是短期预览地址，urlExpiresAt 为空仅限本地示例或明确不适用。服务端负责生成业务 ID、归属与审计，不能信任客户端提供的 ownerId。

错误响应为 `{ "code": "CONFLICT", "message": "任务正在处理中", "requestId": "..." }`。401 未认证、403 无权限、404 不存在、409 冲突、422 输入无效、5xx 服务异常；前端额外使用 UNAVAILABLE（网络/超时）、INVALID_RESPONSE（无法解析或非 JSON）。用户界面展示 message，不展示凭据与服务器路径。

分页使用 PageQuery `{page, pageSize, search?, mode?}`，page 从 1 开始；PageResult 为 `{items, page, pageSize, total}`。列表空结果返回 items=[]、total=0，不返回 404。分页端点由 Phase 2–4 细化，Phase 1 使用工作区快照适配已有页面。

## 当前服务接口

| 方法与路径 | 请求 | 成功响应 |
|---|---|---|
| GET /auth/me | Cookie 会话 | 200 User |
| GET /workspace | 无 | 200 Workspace，templates/tasks/archives 三个数组 |
| PUT /templates/:id | Template | 200 Template；更新增加版本 |
| DELETE /templates/:id | 无 | 204；历史任务快照不变 |
| POST /tasks | CreateTaskInput | 202 Accepted，taskId/roundId/state=排队中 |
| POST /tasks/:id/rounds | RevisionInput | 202 Accepted；target=null 为整套，否则从 0 开始图片位置 |
| POST /tasks/:id/archives | 无 | 200 Archive；同一结果重复操作返回同条记录 |
| DELETE /archives/:id | 无 | 204；对应任务图片保留 |

GET /workspace 是 Phase 1 过渡性聚合读取，不能用于生产无限量加载。Phase 2–4 逐页改为分页与任务详情查询。当前 CreateTaskInput.sources 的 Picture.url 是模拟预览输入；在 Phase 6 接真实上传后必须改为受权 fileId，服务端不接受任意远程 URL。首次生成/返工的 202 仅代表受理，不代表执行完成。

## 数据与状态

- User：id/name/role/status；role 为 super_admin、design_manager、designer、operator 或 null；status 为 pending、active、disabled。
- FileRecord：id/name/mimeType/size/width/height/ownerId/url/urlExpiresAt。size 单位字节，宽高为像素。
- SkillVersion：id/name/mode/version/checksum/status，状态 uploaded/installing/available/disabled/failed。
- Template：id/name/mode/images/skill/active/version/ownerId。当前 skill 展示字符串将在 Phase 2 细化为已发布版本引用，任务必须冻结具体 skillVersionId。
- Task：id/name/mode、模板引用及版本、skillVersionId、ownerId、sessionId、state、progress、sources、images、feedback、time、archived、currentRoundId。
- Round：id/taskId/operatorId/target/note/state/createdAt/startedAt/finishedAt/error。
- ImageVersion：id/taskId/roundId/slot/version/fileId/current。当前 Picture 是原型展示投影；真实历史关联在 Phase 3/10 完善。
- Archive：id/taskId/name/mode/images/time/ownerId/imageVersionIds，冻结结果，不随返工覆盖。
- 管理：ExecutionAttempt 按真实启动去重，usage 可为 null（未提供，不能显示 0）；WorkerStatus 区分 idle/running/unavailable/unknown；SystemConfig 包含版本、并发、超时秒数、上传字节限制和默认 Skill 引用。Phase 4 定义查询、保存与审计接口。

TaskState 使用排队中、执行中、待查看、部分失败、失败，保持现有视图兼容；Phase 5 后端序列化须遵守同枚举或显式映射。归档是结果快照，不替代执行状态。progress 为 0–100 或 null，null 表示无可靠比例；模拟进度仅演示状态变化。真实阶段需在 UI 以阶段文字展示 null，不能假设其为 0%。

当前模拟服务保证类型匹配、异步受理返回标识、串行返工、目标图片独立版本更新、归档快照与读写拷贝隔离；尚未覆盖 Phase 2–4 全部异常场景，不据此宣称真实业务验收完成。

上传格式/数量上限、删除保留、正式文字表单等建议默认仍按 PRD 第 11 节管理，不因契约示例而变成已确认需求。HTTP 写操作幂等键与持久化 outbox 在后端阶段实现；当前 UI 防止重复点击，不宣称跨网络重放幂等。


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
