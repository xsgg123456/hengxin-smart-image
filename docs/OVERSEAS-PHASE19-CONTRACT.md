# Phase 19 图需任务、指定设计与改派实施合同

验收补充：任务空态引导同样按当前能力展示；无task.create的成员不提示提交图需，只提供清空筛选或联系运营的引导。

## 顺序、复用与完成标准

1. 固定任务、接口和并发合同。复用Phase18的Member、CurrentMember、permissions及管理事务锁；抽出一期幂等中的无业务依赖原语，一期与海外共用，不能导入国内Task/Job模型到海外。
2. 海外任务/SKU/事件/幂等请求/出站事件独立持久化，迁移0004；验收创建原子性、重复请求、校验、旧库升级与国内库不变。
3. 接范围分页、详情、设计候选、改派；验收五角色及兼任、越权、停用/撤权竞争、陈旧版本、改派后即时权限变化。
4. 直接续建OverseasCreate/OverseasWorkspace/OverseasTaskInfo，通过显式adapter与slots复用真实和预览；不复制整页。接Phase18 Shell/Portal及能力菜单，完成正常/空/加载/错误/409/窄屏交互。
5. 全量回归、编译构建、真实两库HTTP与浏览器、PG竞争、独立两阶段审查。通过后回写DEV-PLAN并中文Git提交，不部署、不推送、不收费调用。

资料上传与至少一份有效资料的完整提交校验按原计划在Phase20接入。Phase19正式入口保存任务基础信息与指定设计，状态为created（图需已保存），仍属于六节点第一个节点；不增加待分配、审核资料或退回运营流程，不伪造已上传、已排队或正在分析。正式按钮为“保存图需”；真实上传/AI按钮暂不出现。创建事务记录task.created出站事件，仅持久化，不启动国内或海外Worker。后续只有完整资料与执行准入验证通过才创建分析作业，不能将task.created直接当分析指令。

## 数据与接口

前缀 `/api/overseas/v1`，写操作复用Origin/X-HX-Request，均需当前海外业务会话。

- POST `/tasks`：仅task.create。必须 `Idempotency-Key`（1–128非空字符）。严格JSON `{name,productName,brand,platform,market,remarks,skus:[{code}],designerId}`，不接收createdBy/status/version/files等客户端指定字段。文本去首尾空白；name/productName/code最多80、brand/market最多60、platform最多40、remarks最多1000；其余必填，remarks默认空。SKU 1–100个，去空白后大小写不敏感重复拒绝。platform允许Amazon/TikTok Shop/Shopee/Lazada/其他，延续原表单选项。首次201，重放200，响应TaskDetail。
- GET `/tasks`：task.read；search最多100，匹配名称/品名/品牌/SKU/完整任务ID；scope=all|mine，默认all，mine为本人创建或本人负责并仍受基础权限约束；status可选，支持created及既有工作流状态标识；page默认1/pageSize默认20最大100。先范围和条件筛选再count/分页，createdAt降序+id稳定排序。响应 `{items:TaskSummary[],total,page,pageSize}`。
- GET `/tasks/{id}`：TaskDetail；不存在404，无范围权限403。任何客户端提供的负责人/创建人都不用于授权。
- GET `/task-designers`：有task.create或task.reassign能力；search/page/pageSize同上，返回 `{items:[{id,name,department}],total,page,pageSize}`。候选仅active且具有designer或design_manager角色；纯super_admin、运营或停用成员不入选。候选分页可查询全部成员，不把第一页误当全名单。
- PATCH `/tasks/{id}/assignment`：仅task.reassign（设计主管/超管），严格 `{designerId,version}`，版本正整数，必须Idempotency-Key。仅有效设计候选，当前负责人相同返回409而不记假变更；陈旧版本409。成功200返回TaskDetail。

TaskSummary：`{id,name,productName,brand,platform,market,remarks,skus:[{code}],status,version,createdAt,updatedAt,createdBy:{id,name},designer:{id,name,status,eligible},capabilities:string[]}`。capabilities来自当前操作者与当前任务权限交集，包含task.read/task.design/task.reassign中真实允许的项；task.design只声明资格，Phase19不提供未实现设计操作。TaskDetail在Summary上增加 `events:[{id,kind,actorId,actorName,title,at,beforeDesignerId,afterDesignerId,version}]`，按版本升序展示创建/改派真实事件。任务信息可显示负责人已停用或已无设计角色；授权判定始终读实时成员状态/角色。

海外表：overseas_tasks、overseas_task_skus、overseas_task_events、overseas_task_requests、overseas_task_outbox，统一海外Base/Timestamps，UUID主键与海外Member外键。SKU按position保持顺序并有(task_id,code_key)唯一约束；任务version从1起，改派递增。请求按actor/operation/target/key唯一；事件按task/version唯一；outbox按event唯一，保存topic/payload/published_at，初始未发布。创建与改派的任务、事件、outbox和幂等记录均同一事务。

## 并发与隔离

- 复用一期规范JSON哈希、幂等key验证及PG事务advisory锁算法，新增公共原语后一期旧fingerprint语义和返回保持不变。
- 所有任务写入统一顺序：Phase18权限事务锁 → 幂等锁 → 当前任务行锁。权限锁后刷新操作者、读取最新角色，候选也实时校验；管理端停用/撤权使用同一权限锁，避免基于过期候选创建或改派。任何等待期间失效的权限拒绝。
- 同key同内容只成功写一次；同key不同内容409。重放仍检查当前操作者权限与任务范围，返回同一任务的当前DTO，不能借历史请求越权或把后续改派回滚。不同操作者的key相互独立。失败回滚不得残留孤立SKU、事件、outbox或请求。
- 列表SQL、详情和未来动作复用Phase18同源策略。改派不改变任务流程状态、SKU或已存在执行状态；仅更新负责人、version和审计，不创建分析/生图作业。原普通设计无其他角色权限时下一请求即403，新设计可读；若兼任运营且本人创建，仍保留运营读取资格，但失去原设计动作资格。
- 无成员/任务/文件通过国内模型或会话读取。Phase19没有文件接口，不用国内文件ID或文件名冒充海外资料。

## 前端与测试合同

正式路由 `/overseas/create`、`/overseas/tasks`、`/overseas/tasks/:id`，保留首页和管理成员。task.create控制提交入口；task.read控制工作流列表；无成品/分析假入口。正式Create复用基本信息/SKU结构并增加必选设计下拉，异步搜索/分页、空候选/失败重试、保存中禁用、错误保留输入。每份未成功的相同提交保留幂等key，成功才清；内容变化生成新key。请求结果不确定时相同内容重试不能新建任务。

Workspace复用列表和查询控件，真实分页与当前页刷新；角色撤销、401/403清理敏感数据并刷新身份/菜单，网络失败不给旧授权可操作内容。TaskInfo复用任务信息/事件布局，显示提交人/设计、SKU、补充说明、真实流转记录；主管/超管有改派控件，409提示刷新后重选，普通运营/设计不出现改派按钮。预览继续使用原内存数据和模拟执行，正式模块不得静态导入preview-adapter或workflow模拟函数。

测试必须覆盖：五角色/兼任范围、分页前筛选和SKU搜索、缺/停用/非设计候选、空白/重复SKU/额外字段、重复key/异body、真实PG并发创建和同版本改派、候选/操作者在等锁时停用撤权、原设计失去范围、停用当前设计后的主管接续、任务与事件/outbox事务回滚、迁移0003保留数据、国内隔离；浏览器多SKU保存/刷新、设计选择空与加载失败、重复重试、五角色菜单/直链、改派冲突/权限刷新、空加载错误祖先裁切及窄屏关键按钮可达。

官方用法核对沿用锁文件版本：[PostgreSQL事务锁](https://www.postgresql.org/docs/17/explicit-locking.html)、[SQLAlchemy populate_existing](https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html)。不新增依赖。
