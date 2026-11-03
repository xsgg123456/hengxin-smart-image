# SKU 回填、个人草稿及异步附件 · 实施合同（2026-11-03）

用户已确认 preview-sku-import 交互，授权正式实现、中文Git提交、生产部署。追加确认每用户自动保存全部已填信息，退出/刷新不得清空；上游附件必须后台异步导入，网络/对象存储期间不得持有数据库事务或行锁。

## 产品验收
1. 新建仅一个必填SKU，无添加/移除SKU；历史多SKU原数据和编辑兼容，不截断。
2. 点击获取需求；单条回填，多条弹窗人工选择一条，0条/失败保留内容。6字段 platformName/brandName/title/productName/language/designerName 对应目标平台/品牌/任务名称/品名/语言/负责设计。映射有效平台、语言及唯一有资格设计师；异常/空值保留已有值并提示人工处理。覆盖有内容的表单需确认，仍可手动修改。变更SKU使旧请求结果失效，来源不一致不得误提交。
3. 选定需求全部附件：PPT/PPTX(不区分大小写)到图片需求，其余到竞品；两类多份，单份非空且<=500,000,000字节。按源附件ID去重，切换需求确认替换。保留现有单轮附件数量保护，不静默截断上游数据；超限明确错误。
4. 每个海外账号一份新建图需草稿，持久保存不完整字段、所选来源、手动及导入附件关联、任务状态、提交幂等键。字段输入先按账号保存本地恢复副本，再防抖异步保存服务器；显示加载/保存中/已保存/失败及重试。初始化恢复前禁止编辑覆盖；串行保存、版本冲突不静默覆盖、多标签页和账号切换隔离。只在正式提交成功或主动确认清空时清空。已保存附件恢复时重新鉴权；未完成的本地上传明确提示重选，后台导入自动恢复进度。不能刷新时假装文件已保存。
5. 附件导入持久队列：请求只登记任务返回，后台有限并发领取/续租/重试；下载及对象存储在数据库事务外；短事务登记结果，草稿代次/归属校验防清空或替换后旧任务回写。进度轮询、失败重试/移除，成功不重传，服务重启可恢复；源密钥仅服务端环境，不进源码/日志/浏览器。固定上游基址，下载重定向约束，500MB流式上限及临时文件清理。禁止客户端提交任意下载URL。
6. 获取不自动提交；导入未终结或失败未处理不得提交。提交前确认草稿已保存；失败保留草稿，成功创建任务和消费草稿同事务，刷新/重试不重复建任务。多附件贯通提交/审核/退回重提/工作台资料读取。
7. 真实页面保留已确认预览样式，移除所有演示数据、场景开关、假下载和模拟成功。

## 执行次序与完成标准
1. 文档及契约：本合同、Spec/Brief/计划/变更记录同步，明确所有权与接口。
2. 后端草稿/查询/导入：增量迁移overseas_0026，持久队列、权限/代次/幂等/失败测试，网络IO期间不持事务证据。
3. 前端及多附件：按预览接真实接口和持久化，单SKU/恢复/覆盖选择/分类/重试/重载浏览器验证；旧任务兼容。
4. 全回归、类型/正式构建、安装态Linux/PostgreSQL测试；固定快照独立两阶段审查后中文Git提交。
5. 目标0.2.60：只读核查当前生产，固定API与native真实不同基线，停止接纳与排空、备份及隔离恢复、迁移与增量发布，配置上游凭据，保留国内/Skill/原生执行配置及历史记录；健康、后台恢复与正式页面目视验证。生产不创建演示任务/不触发生图。记录回退路径与实际验收边界。

## 服务契约（前后端共用）
基址 /api/overseas/v1。复用海外会话、CSRF请求头、task.create权限。
- GET /requirement-source?sku=... -> {sku,count,truncated,list:[需求原字段,files:[id,filename,size,contentType,category],matchedDesigner:{id,name,department}|null]}。不给客户端密钥或下载签名。
- GET /requirement-draft -> Draft。
- PUT /requirement-draft {version,fields} -> Draft。fields为现有TaskDraft(无materialIds): name,productName,brand,platform,language,market,skus:[{code}],designerId；允许不完整字段，最长遵循现有输入。
- POST /requirement-draft/source {version,sku,requirementId,fields} -> Draft；核实选定源，保存回填内容与源并排队附件，不等待附件传输。
- POST /requirement-draft/imports/{id}/retry -> Draft；DELETE同路径移除/取消该附件。
- DELETE /requirement-draft/materials/{id} -> Draft；删除草稿关联并取消对应源导入，不删除上游。
- DELETE /requirement-draft {version} -> Draft；用户明确清空，代次更换、取消旧导入。
- Draft={id,version,fields,source:{sku,requirementId}|null,materials:Material[],imports:Import[],updatedAt,submitKey,lastSubmittedTaskId?,lastSubmittedKey?,matchedDesigner:{id,name,department}|null}。恢复未确认提交时，必须用lastSubmittedKey精确匹配本地提交键，再认领lastSubmittedTaskId。
- Import={id,sourceFileId,filename,size,kind,state:queued|running|ready|failed|cancelled,progress,error:string|null,materialId:string|null}。
- 上传现有 /materials?kind=... 增加可选 draftId=UUID；成功保存时在同一数据库提交挂到该用户当前草稿，旧代次拒绝；返回Material不变，前端随后重读草稿。
- 正式create TaskDraft增加可选draftId/draftVersion；同原Idempotency-Key提交，服务内核对草稿归属/版本/就绪和字段附件一致，并在同一提交中标记消费/清空。旧不带草稿的客户端保持兼容；新页面带草稿创建时服务端限制1个SKU，历史重提保留多SKU。每轮附件总上限100份，超限报错，不截断。
- 草稿version只保护用户写入；后台进度与附件结果不能用旧字段覆盖用户新输入，客户端轮询只更新导入/附件/服务端版本，不覆写正在编辑字段。冲突保留本地恢复副本并明确处理。

注：接口实现若需调整必须先由主Agent统一通知前后端，禁止各自猜契约。
