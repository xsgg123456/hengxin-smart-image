# Phase22 方案分析与确认实施合同

依赖Phase21验收提交后实施。以DEV-PLAN Phase22和海外二期Spec为准；不改变五角色、独立资源或收费验证边界。

1. 冻结资料与方案版本：新增Plan持久记录、冻结0007迁移。有效资料提交后在同一任务事务创建首轮analysis作业；旧submitted任务提供设计操作启动分析。分析包含全部SKU，冻结任务信息、原件标识/checksum、完整解析版本和Skill内容，后续改配置不影响在途作业。验收事务回滚、重复提交、资料缺失及全量输入。
2. 分析协议：读取输入资料，仅把资料作为数据；CLI交付plan.json，逐SKU列出图片title、description、prompt、width、height。SKU集合必须精确匹配且无重复，每SKU至少1图，图片尺寸为正整数且不超过8192，整套最多100图、单个文本有合理上限；拒绝空产物、错SKU、缺字段、越界路径和不完整CLI回执。固定安全边界不能从资料覆盖。复用Phase21协议registry和事务publish，成功与Plan版本原子发布。
3. 修改/确认/重试：设计负责人及设计主管操作，超管需兼任业务角色；所有写操作携带task version和幂等键。意见非空才创建reanalysis，保留旧方案；分析中不能确认，旧版本冲突409；确认冻结当前完整方案，一次性按SKU创建generation作业且不重复。失败/取消可显式新建分析版本，uncertain/活跃作业不能重试。
4. 真实方案界面：续建既有方案展示的SKU标签、图片建议与意见/确认布局，正式入口不加载模拟adapter；展示历史、完整建议、错误/加载/空态、确认冲突刷新和只读权限。真实任务状态随执行结果刷新，无假百分比。
5. 单测/PG竞争/迁移、前端类型构建/浏览器、真实隔离HTTP与完整回归后独立两阶段审查，批准同快照后独立本地Git提交。

## API合同

- GET `/tasks/{id}/plans` -> `{items:[{id,taskId,version,status,jobId,feedback,content,createdAt}], taskVersion}`；历史按version降序，content为`{skus:[{code,pictures:[{title,description,prompt,width,height}]}]}`或null。
- POST `/tasks/{id}/analysis` body `{version,feedback}`，`Idempotency-Key`必需；首次/失败重试允许空feedback，有ready方案重分析必须非空。返回任务详情；状态analyzing。
- POST `/tasks/{id}/plans/{planId}/confirm` body `{version}`，同幂等规则；返回任务详情，状态generating。
- 首次提交/补交资料无需再点击分析。设计确认方案后Phase23负责执行generation协议；本阶段验证原子入队与固定输入，不伪称图片交付。

模型与服务按职责拆为plans/{models,schemas,service,analysis,router}.py。前端按现有组件抽取可复用展示，所有新逻辑用真实API；既有专用预览保留。
