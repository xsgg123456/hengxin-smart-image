# API 换套图正式实现 · 2026-09-22

用户在预览验收与范围对齐后授权开始正式开发。承接六项：10+1严格分批、单图首调+3次指数退避(1/2/4秒)、记录页紧凑缩略图/静默刷新/操作人、整套ZIP、基于当前结果的单图修改、持久化历史版本。此文件取代预览阶段仅模拟的限制，前端视觉依照两个预览计划及截图。开发与测试先本地完成，不把预览或模拟服务当真实上游效果验收。

## 执行步骤及验收

1. 数据与业务接口：迁移0016，ApiItem逐项租约；成功结果版本独立保存、当前版本指针；修改输入冻结在item，重试不换基础图。旧结果回填V1、旧租约兼容。新增修改/单项重试/恢复/ZIP接口，幂等、权限与文件引用保护；验收跨重试/恢复/删除引用/迁移存量。
2. Worker：每张独立租约/心跳，通道行锁只用于短事务领取和汇总；一次任务当前十张全部终态后下一批。线程池最多10，独立数据库Session，超时/上游失败按三次退避；已收响应的落盘重试只重收图片。进程丢失且无法确定调用停止仍需核实，迟到回写按租约拒绝。配置密钥/额度错误暂停通道供管理员修复。
3. 正式前端：RealRecords/use-records修复尺寸及静默轮询；RealTaskDetail及正式修改/历史组件按预览落地；真实API契约验证、网络不确定重放原幂等键、防重复提交。下载最新选定结果；修改/打包期间不切当前版本。
4. 完整验证：后端单测及隔离PostgreSQL并发/迁移、前端类型/全套测试/正式构建、浏览器交互与断网/失败路径、代码快照独立审查。发布需单列证据，不调用收费生成测试代替用户验收。

## 前后端契约

原 task DTO 扩展 operator:string（创建人显示名），batch:{current,total,running}。
item新增 currentVersion:number|null、versions:数组、revision:null|{state,text,annotation:ApiPicture|null,operator,baseVersion:number,retries:number,error:string|null}。item.state仍为当前工作状态，result始终可保留上次成功图；revision.state跟随item.state。
version={number:number,picture:ApiPicture,created:string,operator:string,text:string,annotation:ApiPicture|null,baseVersion:number|null}，编号按历史最大值递增。
POST /tasks/{taskId}/items/{itemId}/revise，Idempotency-Key，body={baseVersion:number,text:string,annotationFileId?:UUID|null}，至少文字或标注一种，返回{taskId}。
POST /tasks/{taskId}/items/{itemId}/retry，Idempotency-Key，返回{taskId}。
POST /tasks/{taskId}/items/{itemId}/restore，Idempotency-Key，body={version:number}，返回{taskId}。
GET /tasks/{taskId}/zip，认证下载当前结果快照，全部成功才可用，返回application/zip。
所有原接口保持兼容，旧任务operator以创建人显示名为准，历史版本不做独立删除。任务共享权限沿用shared_resources。

## 分工与实现接口

主Agent负责 claims/execution/outcomes/heartbeat/state/control/relay/celery 与并发测试。
后端业务worker负责 models迁移/service/files/presentation/router/schemas、新versions.py和ZIP模块、版本领域测试。
前端worker负责正式类型/客户端/校验/Real页面/hooks/正式弹框与前端测试。预览文件保留。
ApiItem新增lease_token UUID nullable、lease_until datetime nullable；主Agent owned返回(gate,item)但所有租约在item上，release_item(item)释放；ApiChannel旧租约字段仅迁移兼容。
ApiItem修改字段由业务worker确定，提供 versions.execution_inputs(session,item,task)->(sourceApiFile, optionalAnnotationApiFile, prompt)或None（普通生成），versions.publish_result(session,item,task,file_id)在collect成功事务调用；主Agent不直写版本表。修改输入仅当前图+可选标注，relay第二张可None，不内置提示词。
