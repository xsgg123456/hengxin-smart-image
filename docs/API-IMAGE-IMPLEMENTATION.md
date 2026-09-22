# 独立 API 换套图实施计划（2026-09-22）

用户已批准开发。此文接续交互预览，规定真实前后端交付边界；不等于已经验证或部署。

## 隔离与目标
复用现有 FastAPI/SQLAlchemy/PostgreSQL、认证和 MinIO 适配器；独立 api_image_edits 业务模块、表、文件记录/存储前缀、接口、Celery app/队列、outbox 调度及 worker。不得引用 CLI Task/Skill/Round/Job/执行闸门，不改 CLI 的默认 worker/队列行为。共享服务器/数据库/Redis/存储故障仍可能共同影响两边。真实配置不依赖 CODEX 配置或认证；默认关闭 API_IMAGE_ENABLED，可独立启停。

## 规则
- 有序原图 1–20 张，共用素材 1 张，JPG/PNG/WebP 单张10MiB，任务名称1–60、提示词1–4000。后端冻结输入/提示词/模型参数；明确原图ID数组和素材ID，不依据异步上传完成顺序判断角色。
- 固定 endpoint=/v1/images/edits，model=gpt-image-2.5-sunburst，size=1024x1024，resolution=1K，quality=xhigh，n=1；每次两张图使用 images[].image_url 的 Base64 data URL。密钥服务端 SecretStr 配置，禁止入Git/日志/浏览器。
- 模块全局并发1，按先提交任务及原图顺序执行。数据库原子认领/独立闸门防多Worker重复。保存任务和待投递记录同事务，消息重放不生成重复图片。退避1/2/4秒，初次之外最多3次，遵循合理Retry-After，重试状态/计数持久化。
- 明确未发送的连接失败、429和可重试5xx自动重试；参数错误单项失败；401/403、明确额度/模型配置错误暂停通道。读超时/发出后断线/工作进程丢失为uncertain，不自动重新生成，通道闸门保持阻塞，超级管理员核实旧调用停止后可显式将uncertain置failed并释放闸门，记录操作人，再手动重试；不能把本地幂等宣称为上游不重复扣费保证。
- 结果URL下载后校验图片并存MinIO，成功落存才成功；已获得结果地址时只重试下载/落存，不重复生成。限制HTTPS结果域名白名单、重定向与下载大小/时限，不对图片CDN发送API密钥。
- 全员认证授权角色可查看/删除本模块业务记录；上传/元数据/下载单独端点与文件表，只能引用本模块有效文件。删除为软删除，不删除其他任务仍引用文件；运行/uncertain任务不能删除。原CLI资源清理不可触及API文件。
- 单项状态queued/running/retry_wait/collecting/succeeded/failed/uncertain；任务queued/running/succeeded/partial_failed/failed/uncertain。失败保留成功结果、继续后续；只重试失败项，成功项不变。读数不伪造：总耗时、排队/生成耗时、实际请求与重试次数，费用未提供则null。
- 前端沿用当前预览布局，demo/mock继续显式模拟，production使用独立真实client，禁止失败回落示例。提供上传状态/失败清理/幂等提交及重试/分页查询/轮询/单图下载/删除确认；真实界面没有演示暂停与场景选择。此轮无ZIP、成品库或CLI会话返工。

## 前后端契约（所有路径前缀 /api/v1/api-image-edits）
- GET /status → {enabled:boolean, paused:boolean, reason:string|null}；不会回传key。
- POST /files multipart file → {fileId:string,name:string,url:string}；GET /files/{id}/content?download=true；DELETE /files/{id}（仅未引用文件）。
- POST /tasks，Idempotency-Key header，{name,prompt,originalFileIds:string[],materialFileId:string} → 202 {taskId:string}。
- GET /tasks?page=1&pageSize=20&search=&status= → {items:Task[],total:number,page:number,pageSize:number}。
- GET /tasks/{id} → Task；POST /tasks/{id}/retry（Idempotency-Key）→ {taskId}；DELETE /tasks/{id} → {deleted:true}。
- POST /channel/resume 仅超管恢复已修复配置；POST /tasks/{id}/resolve 仅超管，{confirmedStopped:true}核实不确定请求停止，标失败后手动重试。
- Task={id,name,prompt,created:string,status:string,material:Picture,items:Item[],events:string[],metrics:{requestCount:number,retryCount:number,elapsedSeconds:number|null,queueSeconds:number|null,generationSeconds:number|null},error:string|null}。requestCount 为网络尝试次数（不计本地配置拒绝），retryCount 包含生成的自动/手动重试，不包含收图重试；前端规格标为请求规格，实际返回尺寸保持上游原图，不隐式缩放。搜索支持名称或编号。
- Picture={name,url,fileId}。Item={id,position:number,source:Picture,state:string,retries:number,nextAttemptAt:string|null,result:Picture|null,error:string|null}。position从1开始，按position排序。事件为脱敏摘要。前端可自行映射中文标签，不使用CLI状态契约。

## 开发顺序与完成标准
1. 数据/上传/幂等任务与迁移：api_image_edits/models.py、files.py、service.py、router.py及新迁移；测试权限、输入验证、重复提交、独立文件及CLI表不变。
2. adapter与worker：独立config.py、relay.py、downloads.py、execution.py、celery_app.py、outbox.py；覆盖全局串行、故障重试、结果下载失败不重生、重投/重启uncertain、独立启停及迁移往返。
3. 前端真实client与预览页面连接：独立api/types/composable，路由开放；保留现有视觉，测试上传/提交/轮询/失败恢复/删除，真实模式无示例回落。
4. 集成和审查：隔离测试环境验证新模块，后端/前端回归、构建、浏览器真实HTTP闭环、有限真实中转站出图；记录未验证项。独立code-reviewer审查批准快照后交付，不自动部署或推送。

配置和运行命令放运行文档；示例env无密钥。本机测试资源使用独立目录/库/端口，不修改线上数据库或运行中的CLI业务。
