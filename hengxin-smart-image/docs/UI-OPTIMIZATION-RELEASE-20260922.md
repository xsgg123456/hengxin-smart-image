# 核心 UI 优化合并发布 · 2026-09-22

## 范围与发布顺序

用户授权先提交、再部署真实环境、最后推送。以现网 API 换套图提交57ce288、仓库bc6f749为基线，发布已审共享前端优化：任务图集/查询、单图修改、生成占位、紧凑创建页、模板选择器、模板库/成品库四列和任务列表密度。前端版本0.2.1。同步任务查询 scope 与 ownerName 后端兼容改动；API换套图模块完整保留。

1. 保留同步前stash备份，检查审查凭据、production产物、敏感内容和依赖审计，中文提交。
2. 白名单打包正式前端和完整后端构建源；排除演示素材、测试、缓存、凭据和开发环境文件。
3. 服务器先验证现有API源文件与bc6f749基线一致；备份前端和受限配置，再构建不可变新镜像。只重建API容器，环境变量前后一致，CLI/API生成worker及outbox保持原容器ID/进程号，不执行迁移。
4. 前端保留旧哈希资源、首页最后切换。检查部署文件哈希、API健康、鉴权、API模块路由和真实登录页，然后push。

## 配置与回滚

API使用独立发布目录的api-override.yaml叠加既有3个Compose文件。该overlay仅覆盖api镜像和构建上下文。APP_IMAGE及原生CLI源码不变；API_IMAGE_RELEASE.json继续记录原API生成worker的部署，新增API_RELEASE.json记录HTTP API的新镜像。后续维护HTTP API须沿用其清单中的composeOverride，不能从旧CLI目录重建覆盖。

部署失败时恢复旧首页/发布清单并用原API镜像重建API，保留新旧静态资源及全部业务数据。数据库保持0015，不降级、不恢复历史数据库覆盖新数据。本次不重启生成worker，不触发付费生成。

## 验证基线与边界

合并验证：141项前端测试、806项后端测试通过；160项后端跳过，不算通过。类型检查、production构建、隔离Demo完整回归和新旧模块兼容浏览器检查通过，记录在output/sync-2026-09-22/。依赖审计critical0，既有high62/moderate39/low5，本轮不升级依赖。Node实际24.15.0，项目声明24.18.1。

本次线上健康/静态/鉴权检查不代表收费生图或钉钉双端完整验收。实际发布编号、哈希和结果在部署后补录。

## 已发布结果

- 功能提交 `a215301`，正式版本0.2.1，发布 `ui-20260922-a215301`。两阶段发布审查PASS，批准快照 `5dda9462128054638255fa9225dd6d0670e68b9ccde33e7baef2926a76aa88df`，报告见 `docs/reviews/UI-OPTIMIZATION-RELEASE-20260922.md`（仓库根目录）。
- 正式构建32.02秒，类型检查exit0；568个白名单文件，包SHA256 `352c8a259e8cbae7b732a0fce337d4daf1cad3b6d17de658adf0fd7d84fb382f`。
- 部署日志 `/opt/hengxin-releases/ui-20260922-a215301/deploy.log` 记录DEPLOY_COMPLETE；API新镜像healthy。423个前端文件及新API源码哈希一致，API容器环境变量前后一致。
- 上线前124个API Python文件与合并基线逐一核验一致。CLI/API生成worker与outbox实例标识前后相同，原生CLI Worker MainPID仍为820783，未执行数据库迁移或收费生成。
- 备份 `/opt/hengxin-backups/ui-20260922-a215301/` 含旧前端、清单、原镜像信息和权限600配置；数据库未修改，不备份恢复数据库。回退脚本通过静态审查，未在线故障演练。
- 公网首页SHA256 `20a4d9c2a514fe29eb97bf5e4f4509b141c6392718593f6f7371818879fc0560` 与发布包一致；PG/Redis/MinIO均up。公网auth/me、tasks?scope=mine及API换套图status/tasks匿名均401。实际运行API OpenAPI已包含scope、ownerName和独立换套图路由。
- 已发起内置浏览器打开真实任务中心，标签创建成功但读取页面超时；不将此视为完成登录后视觉或生图验收。完整交互证据来自合并后的隔离Demo回归，真实登录后页面尚未在本轮验收。
- 后续HTTP API维护必须加 `-f /opt/hengxin-releases/ui-20260922-a215301/api-override.yaml`，该文件将api构建上下文固定至本发布payload/src；另外3个Compose文件及.env保持原位置。worker仍使用原镜像，勿将其当作本次需要补重启的服务。
