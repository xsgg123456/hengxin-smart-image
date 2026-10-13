# AI 工作台正式实施 · 2026-10-13

用户已授权本地正式开发；不部署、不修改生产数据、不发起收费模型测试。已确认交互以 frontend/preview-ai-studio 为准，正式实现禁止模拟回复或静态样图。

## 顺序与验收
1. 单角色权限：前端单选、接口最多一个角色、数据库唯一user_id；super_admin具备全部海外capabilities/任务范围和直接业务操作，不突破业务状态。多角色含super_admin收敛到super_admin；其他多角色迁移拒绝并报成员ID要求明确选择，不猜职责。保留最后管理员保护与审计。主实现独立迁移overseas_0011。
2. 工作台持久化与执行：新建Task workflow='studio'，迁移前任务workflow='legacy'；预审新任务仅进入studio，旧流程保留。新增studio会话/轮次/附件/产物模型，复用海外job队列、租约、取消、存储、Codex沙箱，支持真实多轮resume和文字/多图交付，不要求plan.json/固定图数。每任务一次一轮，任务/附件权限与幂等必须真实校验。工作台迁移overseas_0012接0011。
3. 素材/Skills：前序material通过引用复用，工作台附件支持JPG/PNG/WebP、PDF/DOCX/PPTX/XLS/XLSX/CSV/TXT（旧DOC/PPT明确转换提示）；原件进入执行目录，必要提取支持复用现有解析。新增完整Skill包二进制资源能力、保留版本冻结；前端选可用Skill，服务端验证版本。不得仅接现有文本Skill冒充完整包支持。
4. 正式前端：在OverseasTasksPage根据workflow选择新工作台，旧流程继续；删除海外home菜单/关联路由页签，品牌首页跳转tasks。侧栏显示真实素材，上传/拖入/批量引用/移除，持续消息、执行进度、停止、结果缩略图/放大/单图引用/本组全选、分批归档SKU选择、完成任务。刷新恢复，不丢历史；未知结果不自动重发。
5. 归档：所选产物不可变版本按SKU入库，归档不完成任务；完成任务显式确认且无活动执行。旧整套归档仍兼容，成品库能显示/下载新归档。
6. 验证：权限/幂等/并发/状态/文件/迁移专项，现有前后端全回归、类型、构建、隔离浏览器验证、独立快照审查。使用隔离测试数据库/存储，真实CLI未调用须明确，不拿mock当真实模型验证。

## 工作台API约定（新增，前后端共同消费）
前缀 /api/overseas/v1，仍使用身份request封装和X-HX-Request/Idempotency-Key。JSON驼峰，UUID字符串，DTO须验证。
- TaskDetail新增workflow: 'legacy'|'studio'；状态新增studio/completed。
- GET /tasks/{id}/studio -> {taskId,completed,turns:[{id,text,skillName,status,reply,error,jobId,jobVersion,attachments:[Asset],referencePictures:[Picture],pictures:[Picture],createdAt}],materials:[Asset],skills:[{id,name,version}],activeTurnId:null|string}。
- Asset={id,name,contentType,sizeBytes,url,source:'task'|'upload'}。url为同域鉴权content路由；材料ID统一为task:<uuid>或upload:<uuid>，避免原件重存。接口显式返回可供选择且有权限的素材。
- Picture={id,name,url,width,height,turnId,sku:null|string,archived:boolean}；id指不可变产物，不是数组序号。
- POST /tasks/{id}/studio/files，multipart file -> Asset。支持多文件由前端逐个传；单个20MiB。GET /tasks/{id}/studio/files/{fileId}/content。
- POST /tasks/{id}/studio/turns {text,skillId:null|string,attachmentIds:string[],referencePictureIds:string[]} -> GET studio同shape，要求Idempotency-Key。本轮可纯附件；允许文字回复，skill可选。拒绝跨任务引用、completed和并发轮次。
- GET /tasks/{id}/studio/events?after=0 -> {items:[{id,turnId,kind,text,createdAt}],cursor}，持久游标增量消息，前端轮询恢复（可后续SSE）；不展示内部秘密或原始思维链，仅用户可见助手文字/执行状态。
- POST /tasks/{id}/studio/turns/{turnId}/cancel {version} -> studio同shape，版本对应jobVersion。
- POST /tasks/{id}/studio/archive {pictureIds:string[],sku:string} -> studio同shape，Idempotency-Key；所选全部指向本任务实际SKU，已归档相同版本/SKU不重复。
- POST /tasks/{id}/studio/complete {} -> studio同shape，Idempotency-Key；禁止活动job或无归档完成。
- 文档preview复用现有reader或原件下载，不把文档下载声明为全文可视预览。

## 归属
权限执行者：auth/members/permissions、任务中额外角色判断、迁移0011、成员前端/api与权限测试。不得改Task.workflow相关。
后端执行者：studio/*、迁移0012、tasks/models/queries/service/requirements中workflow接线、execution接线、archives兼容、main/db/migration env，以及studio测试。与权限执行者共享tasks文件时仅改各自有关段并协商。
前端执行者：正式studio Vue组件/API、TasksPage接线、任务状态/菜单页签、材料交互及前端测试；不改成员页面。
主Agent：完整Skill包能力和集成、文档、全回归、审查。其他执行者不覆盖主Agent的management/skills相关代码。

验收补充：reply 在排队阶段可为 null；referencePictures 保留本轮引用的历史图片及原 turnId，刷新后仍可查看。上传限制在 multipart 流读取阶段生效。工作台按实际顶部位置占满剩余视口，输入区保持可见。
