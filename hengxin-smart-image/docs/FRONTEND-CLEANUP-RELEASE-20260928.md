# 前端清理 0.2.12 发布

## 生产结果（2026-09-28 14:51–14:58，Asia/Shanghai）

已部署前端 **0.2.12**，发布提交 `26e3616`，发布标识 `frontend-cleanup-20260928-26e3616`。独立审查 Stage 1/2 PASS，批准快照 `90fbb673eebe3c41d4830652fe84dfaf3d7dfbf6b36bc12cf434b5909f9d6bc5`。

- 归档486文件、4570304字节，SHA256 `6dc39a586f9659d9860f294cdb740f2f4c9a79d4dd1380bd3953d54e89297d67`；服务器上传后哈希一致，全新src目录解包前检查只含普通文件、无重复/越界路径，成员集合精确等于manifest加release.json，逐项内容哈希验证通过。
- 发布目录 `/opt/hengxin-releases/frontend-cleanup-20260928-26e3616`；旧入口/package/FRONTEND_RELEASE备份 `/opt/hengxin-backups/frontend-cleanup-20260928-26e3616`，COMPLETE已写入。保留旧哈希资源，不覆盖后端发布元数据。
- 安装484个前端文件哈希一致；公网首页及2个入口JS/CSS资源哈希一致。ready成功，PostgreSQL/Redis/MinIO均up。
- 五个后端服务、web容器镜像及启动时间与发布前完全一致，原生CLI Worker启动时间不变、active；未重启执行端。发布前无在途任务。
- 公网登录态浏览器实测：系统配置text默认选择器0、壁纸1、商品1；Skill管理text默认选择器0，接口200且目录恰好三项；现有一图文字任务详情whole按钮0、single按钮1。未提交生成或保存生产配置。
- 临时验收会话已撤销，撤销后auth/me401；本地临时cookie文件已删除、浏览器关闭。匿名首次访问401及撤销后401属于预期，未发现发布导致的页面错误。
- 证据：`output/release/frontend-cleanup-20260928-26e3616/` 内package-audit.json、production-verification.json、runtime-after.json、browser-verification.txt、browser-text-task.txt、三张production截图。

生产Skill仍仅jd-detail-screen-swap、jd-detail-screen-swap-790x1500、jd-main-image-wallpaper-camera-swap；此次纯前端发布没有重新加入已移除IT Skill或模板。Git为本地提交，未推送远端。

用户已授权 Git 提交、打包、部署。业务提交 `7b41062`：移除系统配置和模块默认绑定的文字 Skill 选择器，单图文字任务移除整套修改按钮和相应提示，保留单张画布、历史多图及其他模式。生产 IT Skill 和 IT测试666 模板删除已单独完成，见 IT-SKILL-REMOVAL-20260928.md。

## 发布计划

只更新前端0.2.11→0.2.12，后端/schema0020/原生CLI/Compose链保持现状，不停止执行服务。使用 frontend-static.py 打包已提交且已审源码对应的构建，白名单资产隐私扫描、归档字节回读和SHA清单；备份入口、package及FRONTEND_RELEASE，资源先落盘再原子替换入口。同名资源若内容不同则拒绝，旧哈希资源保留；失败恢复旧静态入口及元数据，不恢复数据库。

## 发布前证据

- pnpm test：197通过；pnpm build（含类型检查）：成功，31.91秒，日志 output/frontend-cleanup-tests.txt、frontend-cleanup-build.txt。
- 独立发布测试4项通过：正常安装保留后端/旧资源、拒绝损坏包、拒绝覆盖内容不同的同名资源、切换后校验失败回退入口和元数据。
- pnpm audit --prod：critical0、high33、moderate30、low1；依赖未变，既有告警不在本轮升级。
- 业务页面浏览器证据及审查见 TEXT-DEFAULT-UI-REVIEW-20260928.md、TEXT-WHOLE-UI-REVIEW-20260928.md。

发布增量独立审查与生产验收现已完成，见本记录顶部及 FRONTEND-CLEANUP-RELEASE-REVIEW-20260928.md。
