# 单张所见版本与圈注截图生产发布 · 2026-09-21

用户授权打包部署后，发布至 https://zhitu.qhhengxin.top/ 。

- 发布标识：`single-revision-20260921-84d1bee`；批准快照 `84d1beecb927d282f736e9d276c0c4a7cdb074a81c27eae995a0119a2bf1f866`。沿用已批准工作区发布惯例，未新增Git提交。
- 包SHA256：`4c5b1d9218d5c9a62f5856d8f4aa8afd7e29f7e78e50ba747f0e783da7718c63`，533文件，4678521字节。白名单打包及隐私扫描通过，不含环境凭证、会话、数据库和个人目录。
- 依赖审计critical=0；既有high62/moderate39/low5保留，依赖未改动。
- 发布目录 `/opt/hengxin-releases/single-revision-20260921-84d1bee/`；`deploy.exit=0`，日志`DEPLOY_COMPLETE`。
- 备份 `/opt/hengxin-backups/single-revision-20260921-84d1bee/`：数据库、旧应用/配置及Worker配置/覆盖目录。切换前两次无在途任务，未中断生成。
- 数据库由0012升级0013，`execution_rounds.base_version_id`、`annotation_file_id`已存在。API/Outbox镜像均为本发布，原生Worker active，五并发配置保留。
- 原生/前端533文件哈希与包一致；API和Outbox各120个后端文件哈希一致。公开ready的PostgreSQL/Redis/MinIO均up，首页200，匿名auth/me 401。
- 已在登录的生产浏览器打开任务“IT测试6666”的第1张修改弹窗，确认原图预览、“本次基于V1修改”、可选问题截图上传入口及文字意见正常显示，空意见时提交按钮禁用。未提交修改。

## 边界与回滚

本次未自动发起付费生成或修改已有任务。真实生图效果需在网页提交单张返工后验收；本地交互、版本/快照及PostgreSQL验证见 `SINGLE-REVISION-VALIDATION.md`，独立审查见 `SINGLE-REVISION-REVIEW.md`。

回滚先关闭任务接纳、确认无在途执行，再恢复备份应用/配置与旧镜像，启动服务并检查健康。0013仅新增可空字段，应用回滚保留新增字段及迁移文件，避免覆盖部署后的业务数据；不要用旧数据库备份直接覆盖新业务记录。生产Skill目录、模型与五并发设置本次均未变更。
