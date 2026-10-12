# Phase23 生图、返工、审核与归档合同

Phase22验收提交后实施，保留五角色与独立资源边界。目标是确认方案下按SKU真实执行，单图返工不影响其他图，全部审核通过才能整套归档。

1. 图片槽位/版本持久化及0008冻结迁移；每个确认方案SKU对应一个generation作业，交付数量、图片顺序、尺寸必须与冻结方案一致。协议交付outputs.json的`images:[{position,path}]`（position从0开始、path为工作目录内相对路径），复用一期安全文件读取/图片校验，拒绝链接、越界、缺失、重复及损坏图片。产物私有存储、checksum、宽高、方案/作业/版本可追溯；成功SKU不会因其他SKU失败而重复生成。
2. 每张图片保留版本历史，审核绑定当前版本。负责人/设计主管可以审核、对当前图发起返工、重试失败SKU；超管需兼任设计角色。返工冻结当前版本、整体意见与画布标注，只清除目标图审核，不改其他图片版本/审核；活动/uncertain作业不能重试，旧底图或旧任务版本409，幂等请求不创建重复作业。返工失败保留已有图片并可明确重试。
3. 复用AnnotationCanvas，标注坐标按原始图片像素校验，意见/点数/范围有上限。输入包含原图与标注几何及文字，模型知道哪些是定位说明；标注不叠入正式输出。真实图、历史版本、加载/错误/无图和局部失败均可见。
4. 整套全部当前版本通过且无在途/未知作业才能归档。归档冻结全部SKU及图片版本，之后禁止变更该任务的图/方案。成品库按品名、品牌、SKU检索、分页与鉴权下载，下载内容仅含冻结版本并按原图校验读取。跨业务/跨任务/改派后权限拒绝。
5. 完整单测、PG竞争/迁移、真实私有存储/HTTP/本地进程替身联调、前端类型构建与浏览器、独立两阶段审查后单独本地提交；不收费执行不部署。

## 接口合同

- GET `/tasks/{id}/pictures` -> `{items:[{id,taskId,sku,position,title,version,approved,status,url,width,height,history:[{version,url,width,height,note,createdAt}]}],taskVersion}`。无产物时version=0，url=null；status体现pending/ready/reworking/failed，历史不可冒充当前成功。
- GET `/pictures/{id}/versions/{version}/content` -> 鉴权私有图片，可`download=true`；no-store。
- POST `/pictures/{id}/approve` -> body`{version,taskVersion}`；POST `/pictures/{id}/revisions` -> `{version,taskVersion,note,marks}`；均必带Idempotency-Key，返回TaskDetail。
- POST `/tasks/{id}/generation/retry` -> `{version,sku}`：仅目标失败SKU，返回TaskDetail。
- POST `/tasks/{id}/archive` -> `{version}`，Idempotency-Key，返回TaskDetail。
- GET `/archives?product=&brand=&sku=&search=&page=1&pageSize=20` -> `{items:[{id,taskId,productName,brand,skus:[{code}],pictureCount,createdAt}],total,page,pageSize}`；GET `/archives/{id}/download` -> ZIP，文件名可安全识别SKU和顺序。

所有写动作与任务/图片/作业状态同事务，统一锁顺序权限→task→执行gate→job；原件/正式图片不自动清理。前端沿用既有海外Pictures/Annotation/Archive布局和共享画布，正式页面不导入模拟会话。

资源上限：单图片10MiB、单SKU本轮产物总计256MiB，归档原件总计1GiB；ZIP使用有界内存临时流。标注整体意见与单条意见各1000字符，最多100条标注，每笔最多2000点、合计10000点；所有坐标有限且落在原图像素边界内。失败返工可用当前旧图重新发起，历史图不能覆盖当前版本。

返工交付不能把原图改名复制后冒充新版本：产物checksum与冻结原图相同时拒绝，且在写入对象存储前完成检查。
