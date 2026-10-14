# 工作台与Skill统一合并发布 · 0.2.31

用户已授权修复自动刷新和Skill名称/描述、管理与工作台同步，测试后连同上传放宽及北京时间修复一起上线。

## 有序交付与验收
1. 需求同步：Product-Spec、DEV-PLAN、变更日志先同步，沿用既有UI布局。
2. 实现：后端读取完整性校验后的SKILL标题，前端静默自适应更新与完整描述展示。保持Skill安装包/标识/历史冻结不变。
3. 验证：前后端全回归、构建、浏览器正常/错误/空闲/执行与可见性、独立两阶段审查。
4. 发布：0.2.31；既有overseas-hotfix-deploy无迁移流程，基线0.2.30，国内0028/海外0014；生产安装镜像测试、备份、关海外接纳、双轮排空、替换海外API/原生执行代码及共享前端，再健康/权限/静态资源/页面验收。
5. 已授权提交已审源码，使用中文提交信息；不推送、不改Skill包、不触发收费模型。

## 恢复原则
沿用发布编排：失败关闭海外入口，保留PHASE、FAILURE和备份，实查后恢复旧应用；绝不以旧数据库覆盖新业务数据。不重启国内和身份服务。

## 合并回归证据
- 前端347 passed/0 failed，typecheck exit0；output/studio-frontend-tests.log、studio-frontend-typecheck.log。
- 生产构建exit0，38.33s；output/workbench-release-build.log。
- Linux只读仓库、无网络全回归：2007 passed、185 skipped、15 warnings，263.39s；output/workbench-release-backend-full.log。环境跳过不计已验证。
- 浏览器隔离接口测试PASS：草稿/附件/Skill/滚动保持，手动与静默刷新、错误恢复、完成停止，390px长描述全文滚动及说明弹窗；output/studio-refresh-browser.log、output/playwright/studio/。可见性/卸载/竞争及权限由真实hook定时器测试覆盖。
- 发布脚本13项、打包25项通过。依赖审计critical=0；既有high70/moderate48/low5，本次未修改依赖。
- 生产只读预检：0.2.30、国内0028/海外0014、在途0、删除0、worker空闲。真实Skill14包181文件，保持不可变安装版本。
