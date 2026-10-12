# Phase22 本地验收

本阶段实现资料提交自动分析、全量输入冻结、严格方案产物协议、方案历史、修改重分析、失败重试及确认后按SKU幂等入队。海外迁移推进0007，国内迁移保持0027。

## 验证证据

- Linux独立PG/Redis专项46通过，覆盖方案API、协议、安全文件、PG竞争及0007迁移；旧资料与执行专项22通过。
- 前端275单测、`pnpm typecheck`及正式生产构建通过。方案浏览器覆盖历史/SKU、409保留意见、网络未知复用原幂等键、执行刷新不打断编辑、失败重试、uncertain禁止重复、只读、撤权及窄屏；既有执行/任务/资料故障浏览器均通过。
- `IDENTITY_TEST_IMAGE=hengxin-smart-image-backend:phase20 python infra/identity-test/run.py --phase22`：真实三API、两库、Redis、两个私有MinIO下Phase17–22全部通过；验证分析输入、无效产物、重分析/重试、旧方案拒绝、重复确认仅一组生成作业和国内数据不变。日志`output/phase22-http.log`。
- `tests/overseas-plans-real.browser.mjs`：真实身份和API，无路由模拟；设计与运营查看确认后的两SKU完整方案，刷新持久化，无页面错误。截图`output/playwright/phase22/real-{designer,operator}.png`；交互及窄屏截图同目录。
- CLI验收使用离线可执行子进程产物替身，实际经过进程管理、退出回执和协议发布；未连接收费模型，不代表真实Codex图像能力已验收。

## 范围与后续

正式方案复用现有布局，独立组件由正式任务详情挂载；不导入模拟adapter。既有未提交专用预览与用户修改保留并排除阶段提交。生成作业已入队，图片协议及交付属于Phase23，不在本阶段宣称图片已生成。

完整Linux后端回归：1986通过、17项既有宿主条件跳过，1项旧路由精确白名单未更新导致失败（320.60s）。补入本阶段3个实际路由后，同环境配置专项31项全部通过（4.07s）；仅修测试预期，没有改业务代码。原始日志`output/phase22-backend-final.log`，修后日志`output/phase22-configuration-final.log`。跳过项不计入通过。

独立审查报告：`docs/reviews/OVERSEAS-PHASE22-REVIEW.md`；Stage1/Stage2均PASS，批准快照`35588976b7e92a1d2732d2687872e952b42157c4dde6149fa26139ebf938e47d`。
