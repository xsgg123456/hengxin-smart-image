# 国内 CLI 三天清理与管理中心正式接入

状态：2026-10-21 16:22已完成正式接入、生产启用和真实首扫，0.2.46/0032。既有超过三天会话未获新宽限；正式管理页与保留文件验证通过。发布过程及首轮真实数量见 [发布记录](CLI-RETENTION-MANAGEMENT-RELEASE-20261021.md)。

## 已批准范围

- 国内 API 图片修改 CLI 会话闲置满72小时清历史；24小时缓存规则保持。有效活动计时与执行保护保持，查看/刷新/SSE/管理查询不续期。保留正式成品、全部采用版本、归档、原图、素材、调用/Token汇总。
- 现有会话不重新给宽限。迁移重算active条目的旧7天下次时间，不刷新last_activity_at；pending保持重试屏障。尚未initialized的已有活动记录也不能被首次扫描覆盖成新活动时间；确实缺失登记的资源从可证明的最新提交/执行结束/采用/会话时间建立基线，不凭安装时间续期。
- 每小时扫描，单轮最多25会话及25对象回执。旧会话超过72小时下一轮开始分批处理；仍有执行或无法确认归属时保护。历史删除和物理对象回收分阶段展示，全部完成才计入历史成功。
- 管理中心新增自动清理页；超级管理员和设计主管可见，后端独立鉴权。以scripts/retention-preview/retention.vue及RetentionDetail.vue批准预览为视觉基准，继承真实Art/Element组件和样式。正式页无场景选择器、模拟数据和演示定时器。
- 展示策略、真实心跳、最近扫描开始/结束/状态、预计下次扫描；15秒可关闭轮询，隐藏页暂停。心跳30秒、超过120秒未知/超时；采集失败不能当0或在线。
- 今日/累计缓存及历史成功数，当前失败待重试和已到期待处理数量。失败/保护/文件回收中不计成功，重试不重复累计。新记录起算时间明确，不补造旧完整日志。
- 历史及待清理列表支持任务名/会话ID、类型、结果、北京时间日期范围、分页。详情显示最后活动/到期/处理时间、实际删除对话轮数及对象数、保留说明，原任务删除仍可读摘要。
- 扫描、回执及心跳持久化；清理结果与DB状态同事务提交，回执不能受会话/原任务删除级联影响。保留90天已完成明细及扫描，未完成记录不按天裁掉；累计统计长期保存。不保存提示词/聊天正文/凭据/服务器私有路径，不估算释放空间。

## 实施顺序与验收

1. 固定规则、API合同和批准视觉，更新Spec/Brief/计划；完成标准为上下游口径一致。
2. 后端新增0032增量迁移、清理记录/心跳/统计及只读管理API；完成标准为72h与存量调度、同事务记录、对象失败重试、并发去重、活动保护、权限/分页/时区实测通过。
3. 正式前端替换预览数据，接真实API、权限和系统配置入口；完成标准为状态/筛选/抽屉/轮询/异常/窄屏浏览器验证通过，所有7天有效规则改3天。
4. 完整测试、类型/构建、真实PG迁移并发、独立两阶段审查；修复后重新固定候选。只在批准快照下交付。
5. 实查生产版本和原生路径，适配已有版本化发布与备份恢复流程。停止新接纳并排空有关执行；先停清理、备份、增量迁移、安装全部规则消费者、启动API和页面，最后启动新清理服务。以首次真实扫描验证实际结果，不提前手动删除。
6. 检查公开健康、正式登录管理页、心跳/扫描/回执和保护图片，核对海外/身份/无关服务不变。保留可恢复备份；清理已发生后不能用恢复旧DB制造已删文件的引用，回退优先暂停清理而不抹除屏障与回执。

## 前后端固定合同

时间ISO8601含时区；展示北京时间；计数非负整数，服务采集未知用null。接口位于 /api/v1/management/retention，沿用CurrentUser身份；非super_admin/design_manager返回403。

GET /summary 返回：
```
{checkedAt, policy:{enabled,cacheIdleHours:24,historyIdleHours:72,batchSize,scanIntervalSeconds:3600,detailRetentionDays:90},
 service:{state:'online'|'offline'|'unknown'|'disabled',heartbeatAt:null|string,scanState:'running'|'completed'|'failed'|'unknown',lastStartedAt:null|string,lastFinishedAt:null|string,nextScanAt:null|string},
 statisticsSince:null|string, counts:{cacheToday,cacheTotal,historyToday,historyTotal,retry,overdue,protected,objectsPending}}
```

GET /records?tab=history|pending&keyword=&kind=cache|history&result=&dateFrom=YYYY-MM-DD&dateTo=YYYY-MM-DD&page=1&pageSize=20 返回 {items:Row[],total,page,pageSize}。空kind/result不传。日期按北京时间，history筛处理时间，pending筛到期时间。pageSize最大100；稳定排序。参数无效422。

Row：{id:string,resourceId:string,taskId:null|string,taskName:string,imagePosition:number,kind:'cache'|'history',result:'cache_cleared'|'complete'|'objects_pending'|'retry'|'protected'|'waiting'|'due'|'processing',processedAt:null|string,lastActivityAt:string,dueAt:string,nextAttemptAt:null|string,detail:string,turnsRemoved:number,objectsRemoved:number,objectsPending:number,taskDeleted:boolean}。

GET /records/{id}?tab=history|pending 返回同一Row。不存在404。pending的id可取RetentionEntry UUID，history取持久回执UUID；实际对象回收中的记录可使用其历史id，前端带服务端返回的detailTab:'history'|'pending'（Row追加该字段）。禁止将用户输入拼进SQL或私有路径。

主线程维护本合同；实现者发现接口需要变更先反馈，避免前后端漂移。

## 相关源文档及基线

Product-Spec.md本日条目覆盖原10月10日的7天与首次宽限历史约定；Design-Brief.md本日条目覆盖新增页面。生产上轮已知为0.2.45/国内0031，发布必须重新实查。当前原生清理hengxin-retention.service，每小时循环。SSH主机必须核对racknerd-058889d；本机hengxin-prod别名属于其他项目。

继续使用项目已锁定SQLAlchemy/Alembic与Vue/Element，无依赖升级。实现参考官方事务/线程边界与迁移文档：[SQLAlchemy Session](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)、[Alembic operations](https://alembic.sqlalchemy.org/en/latest/ops.html)。
