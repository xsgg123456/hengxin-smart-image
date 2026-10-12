# Phase24 管理中心真实接入合同

Phase23验收提交后实施，直接续建已有五项管理界面：调用统计、执行监控、用户与角色、Skill管理、系统配置。现有成员管理保持，其他页面正式入口使用海外API，不导入模拟会话或国内管理API。

1. 统计/监控：从海外Job及图片版本持久事实聚合排队、执行、成功/失败、生成/返工图片数；按当前海外任务权限SQL过滤，分页前筛选，支持时间范围/任务/类型/状态。Token仅在真实CLI解析usage提供时记录，费用无来源返回null并显示未提供，不能用事件数冒充调用数。人工等待不计运行并发；uncertain单列且计占槽。
2. Skill：独立Skill及不可变版本表，复用一期包/名称/内容安全校验；支持创建、查看、发布新版本、停启、按analysis/generation/revision设置默认绑定。禁止路径穿越和配置外目录读取；存储结构化文本files快照，不从客户端任意绝对路径加载。已有版本不改写；新作业冻结绑定内容，在途不被配置变更污染。没有自定义绑定时使用已实现的通用协议Skill，不伪造业务效果。
3. 配置：独立持久单例配置与审计、version乐观并发；可管理执行接纳暂停、并发1–5及新作业超时（沿用一期10–7200秒及队列安全边界）。认证秘密/真实二进制/存储凭据由服务环境维护，前端不得读取。修改配置仅影响海外后续领取/新作业快照；降低并发不杀在途；自动清理仍关闭、无UI暗开关。
4. 授权：stats.read按既有五角色scope查询；监控只返回可见任务及安全状态消息，不暴露输入、原始日志、认证路径。members.manage/skills.manage/settings.manage仅super_admin，且不因管理权限自动获业务动作。主管可看其矩阵允许统计监控，不显示未授权设置入口。
5. 分页/筛选/刷新/错误/空态、409/撤权与窄屏验证；真实数据库API持久化与重启、冻结版本、新旧配置隔离和国内数据不变；完整回归、类型构建与独立两阶段审查后单独本地提交。

接口在实施开始时对齐前后端：`GET /management/usage`、`GET /management/jobs`；`GET/POST /management/skills`、`POST /management/skills/{id}/versions`、`PATCH /management/skills/{id}`；`GET/PATCH /management/settings`（version），所有写接口CSRF、权限和事务审计。业务Skill输出仍由固定产物协议验收，Skill文本不能改变安全边界。

## 前后端接口约定

- usage/jobs共享筛选：`from`/`to` ISO时间（按作业创建时间）、`taskId`、`kind`、`status`；jobs另有page/pageSize。usage返回`{jobs,queued,running,uncertain,succeeded,failed,cancelled,generationImages,revisionImages,inputTokens,outputTokens,cost}`。running仅running/collecting/cancelling，uncertain另列；Token缺失不能用0填充，cost为null。
- jobs返回`{items:[{id,taskId,taskName,kind,status,executionCount,imageCount,inputTokens,outputTokens,createdAt,startedAt,completedAt,error}],total,page,pageSize}`，error只固定安全摘要。业务输入、磁盘/认证路径不返回。
- skills GET返回`{items:[{id,name,stage,enabled,version,currentVersion,versions:[{version,files,createdAt}]}]}`；version为记录乐观版本，currentVersion为最新不可变内容版本。POST body`{name,stage,files}`；发布新版本body`{version,files}`；PATCH body`{version,enabled}`。files形如`{"SKILL.md":"..."}`；返回更新后的完整Skill。名称唯一，写结果未知时刷新核实，不盲重复发布。
- settings GET/PATCH响应`{version,paused,concurrency,timeoutSeconds,defaults:{analysis,generation,revision},autoCleanup:false}`；defaults值为Skill id或null（内置）。PATCH携带version及其余可编辑字段，不接受autoCleanup或任意环境键。默认绑定必须存在、启用、阶段相符。当前绑定禁用后新作业明确拒绝，不静默替换业务Skill。
- 超时必须冻结到新作业payload并在执行时读取，运行中的Job不读取后来变化的超时；暂停/并发在领取时读取数据库当前值。原环境中的最大安全边界继续生效。
- 新分析、确认生成、人工新返工在创建时冻结对应阶段最新绑定和超时；失败SKU重试继承原作业完整冻结输入，不能因重试静默切换Skill或超时。旧Job缺runtime时沿用原环境超时，不读取后来设置的数据库新默认值。
