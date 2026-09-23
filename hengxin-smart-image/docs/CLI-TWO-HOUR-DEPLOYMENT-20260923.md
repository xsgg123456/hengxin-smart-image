# CLI整轮两小时发布

用户授权将生产CLI整轮提高至7200秒，首轮和最多一次干预共享额度；队列visibility为7800秒。轮次提交时冻结时限，因此既有轮次仍按原额度执行，已失败轮次不自动恢复。独立API换图的请求超时和五任务并发不变。

## 计划与验收

1. 后端环境上限、管理输入契约、前端响应校验支持7200秒，Compose与VPS示例配置7200/7800。内置本地默认3600/4200保留兼容，生产显式覆盖。
2. 备份原生Worker配置、原生改动文件、Compose环境/overlay及前端入口。旧Worker取消消费后自然排空才更新源码、环境并重启；新请求可入库排队。
3. API和CLI Outbox使用新镜像及7200/7800配置，专用API图像Worker/Outbox镜像保持原值。旧CLI Outbox镜像不支持7200环境，必须同步更新。
4. 生产SystemSettings此前只有concurrency=5，无单独timeout覆盖；新部署环境直接作为生效值，无需修改业务数据库或冒记操作人。
5. 安装前端新静态资源再原子替换index，保留旧资源兼容已开页面；验证API健康、管理配置实际值、新旧轮次冻结语义、Worker环境和broker visibility。

## 已有证据

- 后端专项62通过，前端设置专项12通过，vue-tsc与compileall成功，前端生产构建成功。
- 新镜像无网络隔离安装测试62通过。
- 包含609个白名单文件，5063289字节，SHA256 `0a35dfe01e04fa6f0ddf7a031f344bbb69d5ccd8a77b49e0e790d808b103318e`；私钥、凭据及个人路径扫描通过。

## 回退

先停止新任务消费，排空所有两小时轮次后再恢复旧镜像和环境，不能让旧3600容量Worker承接未结束的7200轮次。保持已冻结轮次及业务数据，前端可恢复备份入口。发布目录 `/opt/hengxin-releases/cli-two-hour-20260923`，备份 `/opt/hengxin-backups/cli-two-hour-20260923`。

## 生产验收完成

- 独立审查两阶段PASS，候选 `0d022306567a537d110c03e55298f2785d7890aa6f6c340d5537b5d56387549a`。
- 2026-09-23北京时间17:11完成原生Worker安全切换；全部在途任务先自然结束，新PID1186623，ping成功、celery消费恢复、心跳ready、CLI0.156.1。
- 原生Worker、API、CLI Outbox均核验执行7200、队列7800、broker visibility7800；管理生效timeoutSeconds=7200、timeoutCapacity=7200，concurrency=5。未改系统配置业务记录，沿用版本3部署默认值。
- 原生3个文件与前端457个文件哈希匹配发布包。API/CLI Outbox镜像 `hengxin-smart-image-backend:cli-two-hour-20260923`。API专用换图Worker/Outbox未切换。
- 公开健康与首页均200。旧轮次仍冻结3600；没有自动重跑失败轮次或创建收费测试任务。
- 后续Compose操作使用本发布目录api-override.yaml。用户已授权提交本轮更改到本地Git，未要求推送。
