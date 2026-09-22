# API 换套图优化生产发布 · 2026-09-22

用户明确授权打包部署到现有生产 https://zhitu.qhhengxin.top/ 。承接正式实现与最终审查快照，原CLI Worker/Outbox及Skill目录保持现状。

## 发布计划

1. 核对已审快照，更新前端0.2.2发布元数据，白名单打包当前完整API源码/迁移/锁文件与正式前端；排除演示图片、测试、缓存、凭据、用户数据。
2. 只读预检生产任务与租约、Celery active、数据库0015及服务镜像。新镜像在关闭接纳前构建，并验证运行时导入。核对产物SHA256与成员哈希。
3. 备份数据库、前端、服务镜像/Compose清单和受限配置。关闭HTTP接纳与API outbox，温和停止独立API Worker；二次确认没有仍在执行的调用。已有失败/uncertain历史保留，不能以发布名义清空或伪成功。
4. 在新增发布overlay中显式指定API/migrate/API Worker/API outbox新镜像和构建源，不改CLI APP_IMAGE及服务。迁移0016回填已有结果V1和租约，启动并检查，最后原子切前端首页并重载Nginx。
5. 核对迁移版本、服务健康、Worker队列/并发实现、源文件和静态文件哈希、外网首页与鉴权；能够使用既有真实登录态时做只读UI检查，不创建会话绕过认证、不自动发起收费生图。

## 回退

保留旧镜像和overlay，失败时停止新API接纳/Worker并检查在途任务，恢复旧API服务镜像和前端首页；0016新增表字段保留，不用数据库旧备份覆盖新业务数据。新版本已产生修改时，旧Worker无法正确处理冻结修改输入，必须保持API换图通道暂停再修复；不能直接开启旧Worker重放新修改。数据库dump做可读取校验。

## 当前状态

生产预检主机racknerd-058889d，原HTTP API ui-20260922-a215301，原独立换图Worker/Outbox api-image-20260922-57ce288；CLI原生Worker active，磁盘可用65GiB。

## 发布结果

- 2026-09-22 18:41（北京时间）完成部署，生产URL https://zhitu.qhhengxin.top/ 。发布 api-opt-20260922-27d41a2，代码提交27d41a228ea932c4f74e2be83d1ba10fb7e224d8，前端0.2.2。
- 受控代码快照d3590c3b44e08e9b62f547c445d508765409f99bdadfda86d9cfa592bc1b8b8b；独立增量审查两阶段PASS，详见根目录docs/API-IMAGE-OPTIMIZATION-RELEASE-REVIEW.md。
- 白名单发布包591文件、4,785,634字节，SHA256 5c63f5e399122608e4a9dc7aa84e0c0b142edf6255674acd7d0995cda7c4193b。前端构建35.19秒。排除演示图片、数据库、凭据、缓存及开发路径。
- API、独立API Worker、API Outbox均运行hengxin-smart-image-backend:api-opt-20260922-27d41a2。每个容器146个后端文件、线上438个前端文件与发布清单哈希完全匹配。
- 数据库0016，历史成功20张已回填20条V1记录；成功20、失败1、待核实1与上线前一致。历史待核实请求仍会阻止换图队列继续派发，需要管理员核实原请求后通过现有恢复操作处理；发布未自动重放或修改此请求状态。
- 原CLI Worker PID与CLI Outbox容器ID不变，原Skill目录、环境配置及CLI发布清单保持原状。
- /与/api/v1/health/ready均200，PostgreSQL/Redis/MinIO ready；匿名访问换图列表、通道状态及auth/me均401。API Worker ping成功，仅消费api_image_edits队列；Celery进程concurrency=1，批内10图并发由已审ThreadPoolExecutor实现。
- 真实浏览器加载生产登录页成功，无pageerror、无HTTP5xx。没有可用真实登录态，本次未冒充会话，也没有在生产发起收费生图。完整业务链路依据正式开发阶段的真实HTTP+模拟上游验证，详见IMPLEMENTATION-VALIDATION。
- pnpm audit：critical 0，既有high 62、moderate 39、low 5；本次未更改依赖锁文件，不宣称全部漏洞已清零。

## 备份与证据

服务器发布目录/opt/hengxin-releases/api-opt-20260922-27d41a2，新增api-override.yaml覆盖4个API相关服务。后续Compose操作应沿用此overlay；APP_IMAGE仍对应CLI原配置，不能裸运行Compose重建API。

备份/opt/hengxin-backups/api-opt-20260922-27d41a2，包含database.dump、可读目录清单、前端与受限配置归档、旧镜像及CLI进程标识；目录0700。pg_restore --list成功读取18,218字节目录。回退保留0016数据并暂停API换图通道。

本地证据output/api-optimization-release/：package-audit.json、release.json、build.log、pnpm-audit.json、verify.log、browser-evidence.json与production-login.png。服务器deploy.log最终为DEPLOY_COMPLETE。
