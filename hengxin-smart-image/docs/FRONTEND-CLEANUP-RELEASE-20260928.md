# 前端清理 0.2.12 发布

用户已授权 Git 提交、打包、部署。业务提交 `7b41062`：移除系统配置和模块默认绑定的文字 Skill 选择器，单图文字任务移除整套修改按钮和相应提示，保留单张画布、历史多图及其他模式。生产 IT Skill 和 IT测试666 模板删除已单独完成，见 IT-SKILL-REMOVAL-20260928.md。

## 发布计划

只更新前端0.2.11→0.2.12，后端/schema0020/原生CLI/Compose链保持现状，不停止执行服务。使用 frontend-static.py 打包已提交且已审源码对应的构建，白名单资产隐私扫描、归档字节回读和SHA清单；备份入口、package及FRONTEND_RELEASE，资源先落盘再原子替换入口。同名资源若内容不同则拒绝，旧哈希资源保留；失败恢复旧静态入口及元数据，不恢复数据库。

## 发布前证据

- pnpm test：197通过；pnpm build（含类型检查）：成功，31.91秒，日志 output/frontend-cleanup-tests.txt、frontend-cleanup-build.txt。
- 独立发布测试4项通过：正常安装保留后端/旧资源、拒绝损坏包、拒绝覆盖内容不同的同名资源、切换后校验失败回退入口和元数据。
- pnpm audit --prod：critical0、high33、moderate30、low1；依赖未变，既有告警不在本轮升级。
- 业务页面浏览器证据及审查见 TEXT-DEFAULT-UI-REVIEW-20260928.md、TEXT-WHOLE-UI-REVIEW-20260928.md。

发布增量独立审查、安装包校验和生产结果待追加；此准备记录不代表已部署。
